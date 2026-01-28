"""
LEGO Factory v3 - SCADA Tag Models
===================================
Tag management models for SCADA system.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, ForeignKey, Index, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base, BaseModel, AuditedModel, TimestampMixin


class TagDataType(PyEnum):
    """Tag data types."""
    BOOLEAN = "boolean"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"


class TagCategory(PyEnum):
    """Tag categories for organization."""
    ANALOG_INPUT = "analog_input"
    ANALOG_OUTPUT = "analog_output"
    DIGITAL_INPUT = "digital_input"
    DIGITAL_OUTPUT = "digital_output"
    CALCULATED = "calculated"
    SETPOINT = "setpoint"
    ALARM = "alarm"
    STATUS = "status"


class TagQuality(PyEnum):
    """OPC UA quality codes."""
    GOOD = 192
    GOOD_LOCAL_OVERRIDE = 216
    UNCERTAIN = 64
    UNCERTAIN_LAST_USABLE = 68
    BAD = 0
    BAD_COMM_FAILURE = 24
    BAD_SENSOR_FAILURE = 20
    BAD_OUT_OF_SERVICE = 28


class Tag(AuditedModel):
    """
    SCADA Tag definition.

    Tags represent points in the system that can be read/written.
    They can be physical I/O points or calculated values.
    """
    __tablename__ = 'tags'

    # Identification
    tag_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    data_type: Mapped[TagDataType] = mapped_column(Enum(TagDataType), nullable=False)
    category: Mapped[TagCategory] = mapped_column(Enum(TagCategory), nullable=False)
    area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    equipment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Engineering units
    eng_units: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    eng_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eng_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Display
    format_string: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decimal_places: Mapped[int] = mapped_column(Integer, default=2)

    # Deadband for change detection
    deadband: Mapped[float] = mapped_column(Float, default=0.0)
    deadband_mode: Mapped[str] = mapped_column(String(20), default='absolute')  # absolute, percent

    # Historian settings
    historize: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_rate_ms: Mapped[int] = mapped_column(Integer, default=1000)
    compression_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    compression_deviation: Mapped[float] = mapped_column(Float, default=0.01)
    compression_max_time_seconds: Mapped[int] = mapped_column(Integer, default=60)

    # Source configuration
    source_type: Mapped[str] = mapped_column(String(50), default='internal')  # internal, modbus, opc, calculated
    source_address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Current value (cached)
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_quality: Mapped[int] = mapped_column(Integer, default=192)
    current_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    alarms = relationship("AlarmDefinition", back_populates="tag", lazy="dynamic")

    __table_args__ = (
        Index('ix_tags_area_equipment', 'area', 'equipment'),
        Index('ix_tags_category', 'category'),
    )

    def scale_to_eng(self, raw_value: float) -> float:
        """Scale raw value to engineering units."""
        if self.raw_low is None or self.raw_high is None:
            return raw_value
        if self.eng_low is None or self.eng_high is None:
            return raw_value

        raw_range = self.raw_high - self.raw_low
        if raw_range == 0:
            return self.eng_low

        eng_range = self.eng_high - self.eng_low
        return self.eng_low + (raw_value - self.raw_low) * eng_range / raw_range

    def scale_to_raw(self, eng_value: float) -> float:
        """Scale engineering value to raw units."""
        if self.raw_low is None or self.raw_high is None:
            return eng_value
        if self.eng_low is None or self.eng_high is None:
            return eng_value

        eng_range = self.eng_high - self.eng_low
        if eng_range == 0:
            return self.raw_low

        raw_range = self.raw_high - self.raw_low
        return self.raw_low + (eng_value - self.eng_low) * raw_range / eng_range

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'tag_id': self.tag_id,
            'name': self.name,
            'description': self.description,
            'data_type': self.data_type.value,
            'category': self.category.value,
            'area': self.area,
            'equipment': self.equipment,
            'eng_units': self.eng_units,
            'eng_low': self.eng_low,
            'eng_high': self.eng_high,
            'current_value': self.current_value,
            'current_quality': self.current_quality,
            'current_timestamp': self.current_timestamp.isoformat() if self.current_timestamp else None,
            'historize': self.historize,
        }


class TagValue(Base, TimestampMixin):
    """
    Historical tag values (TimescaleDB hypertable).

    This table stores all historical values and is converted to a
    TimescaleDB hypertable for efficient time-series queries.
    """
    __tablename__ = 'tag_values'

    # Composite primary key: time + tag_id
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False)
    tag_id: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)

    # Value storage
    value_numeric: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_string: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    value_boolean: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Quality
    quality: Mapped[int] = mapped_column(Integer, default=192, nullable=False)

    # Source tracking
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_tag_values_tag_time', 'tag_id', 'time'),
    )


class TagGroup(AuditedModel):
    """Group of tags for organization and batch operations."""
    __tablename__ = 'tag_groups'

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('tag_groups.id'), nullable=True)

    # Tag membership stored as JSON array of tag_ids
    tag_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Relationships
    parent = relationship("TagGroup", remote_side="TagGroup.id", backref="children")

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'parent_id': str(self.parent_id) if self.parent_id else None,
            'tag_ids': self.tag_ids or [],
        }
