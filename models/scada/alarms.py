"""
LEGO Factory v3 - ISA-18.2 Alarm Models
========================================
Alarm management models following ISA-18.2 standard.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, ForeignKey, Index, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base, BaseModel, AuditedModel, TimestampMixin


class AlarmPriority(PyEnum):
    """ISA-18.2 Alarm priorities."""
    EMERGENCY = 1      # Immediate action required
    HIGH = 2           # Prompt action required
    MEDIUM = 3         # Timely action required
    LOW = 4            # Awareness/informational


class AlarmClass(PyEnum):
    """ISA-18.2 Alarm classes."""
    PROCESS = "process"           # Process parameter out of range
    EQUIPMENT = "equipment"       # Equipment malfunction
    SAFETY = "safety"             # Safety-related condition
    ENVIRONMENTAL = "environmental"  # Environmental condition
    QUALITY = "quality"           # Quality deviation
    DIAGNOSTIC = "diagnostic"     # System diagnostic


class AlarmType(PyEnum):
    """Alarm trigger types."""
    HIGH = "high"             # Value exceeds high limit
    HIGH_HIGH = "high_high"   # Value exceeds high-high limit
    LOW = "low"               # Value below low limit
    LOW_LOW = "low_low"       # Value below low-low limit
    DEVIATION = "deviation"   # Deviation from setpoint
    RATE_OF_CHANGE = "rate_of_change"  # Rate of change exceeded
    DIGITAL = "digital"       # Digital state change
    BAD_QUALITY = "bad_quality"  # Quality code indicates bad


class AlarmState(PyEnum):
    """ISA-18.2 Alarm states."""
    NORMAL = "normal"               # No alarm condition
    UNACKED_ACTIVE = "unacked_active"   # Active, not acknowledged
    ACKED_ACTIVE = "acked_active"       # Active, acknowledged
    UNACKED_CLEARED = "unacked_cleared" # Cleared, not acknowledged
    SHELVED = "shelved"             # Temporarily suppressed
    SUPPRESSED = "suppressed"       # Designed out of service
    OUT_OF_SERVICE = "out_of_service"   # Disabled


class AlarmDefinition(AuditedModel):
    """
    Alarm definition following ISA-18.2.

    Defines when and how an alarm should trigger.
    """
    __tablename__ = 'alarm_definitions'

    # Identification
    alarm_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    priority: Mapped[AlarmPriority] = mapped_column(Enum(AlarmPriority), nullable=False)
    alarm_class: Mapped[AlarmClass] = mapped_column(Enum(AlarmClass), nullable=False)
    alarm_type: Mapped[AlarmType] = mapped_column(Enum(AlarmType), nullable=False)

    # Source tag
    tag_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('tags.id'), nullable=False)
    tag = relationship("Tag", back_populates="alarms")

    # Trigger conditions
    setpoint: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high_high_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low_low_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deviation_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rate_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Units per second

    # Deadband and timing
    deadband: Mapped[float] = mapped_column(Float, default=0.0)
    on_delay_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    off_delay_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    # Current state
    current_state: Mapped[AlarmState] = mapped_column(Enum(AlarmState), default=AlarmState.NORMAL)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=True)

    # Shelving
    is_shelved: Mapped[bool] = mapped_column(Boolean, default=False)
    shelved_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shelved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shelve_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Suppression
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppressed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statistics
    activation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activation: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_clear: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ack: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Response guidance
    consequence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrective_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enable/disable
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index('ix_alarms_priority', 'priority'),
        Index('ix_alarms_state', 'current_state'),
        Index('ix_alarms_active', 'is_active'),
    )

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'alarm_id': self.alarm_id,
            'name': self.name,
            'description': self.description,
            'priority': self.priority.value,
            'alarm_class': self.alarm_class.value,
            'alarm_type': self.alarm_type.value,
            'current_state': self.current_state.value,
            'is_active': self.is_active,
            'is_acknowledged': self.is_acknowledged,
            'is_shelved': self.is_shelved,
            'enabled': self.enabled,
            'activation_count': self.activation_count,
            'last_activation': self.last_activation.isoformat() if self.last_activation else None,
        }


class AlarmEvent(Base, TimestampMixin):
    """
    Alarm event history (TimescaleDB hypertable).

    Records all alarm state changes for analysis and compliance.
    """
    __tablename__ = 'alarm_events'

    # Primary key is timestamp + alarm_id for hypertable
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False)
    alarm_id: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # activate, clear, ack, shelve, unshelve
    previous_state: Mapped[str] = mapped_column(String(50), nullable=True)
    new_state: Mapped[str] = mapped_column(String(50), nullable=False)

    # Value at time of event
    trigger_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    limit_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # User/system that caused event
    operator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    equipment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_alarm_events_alarm_time', 'alarm_id', 'timestamp'),
        Index('ix_alarm_events_type', 'event_type'),
    )


class AlarmShelveLog(AuditedModel):
    """Log of alarm shelving operations for audit trail."""
    __tablename__ = 'alarm_shelve_log'

    alarm_definition_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('alarm_definitions.id'), nullable=False)

    action: Mapped[str] = mapped_column(String(20), nullable=False)  # shelve, unshelve
    duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(String(100), nullable=False)

    # Approval if required
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AlarmGroup(AuditedModel):
    """Group of alarms for batch operations."""
    __tablename__ = 'alarm_groups'

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Alarm membership stored as JSON array of alarm_ids
    alarm_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'alarm_ids': self.alarm_ids or [],
        }
