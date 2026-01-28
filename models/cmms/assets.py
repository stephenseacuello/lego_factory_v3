"""
LEGO Factory v3 - CMMS Asset Models
===================================
Asset tracking and meter management.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class AssetStatus(str, Enum):
    """Asset operational status."""
    OPERATIONAL = 'operational'
    DEGRADED = 'degraded'
    DOWN = 'down'
    MAINTENANCE = 'maintenance'
    DECOMMISSIONED = 'decommissioned'
    PENDING_INSTALLATION = 'pending_installation'


class AssetCriticality(str, Enum):
    """Asset criticality classification."""
    CRITICAL = 'critical'       # Production stops if asset fails
    ESSENTIAL = 'essential'     # Significant impact on production
    IMPORTANT = 'important'     # Moderate impact
    STANDARD = 'standard'       # Minimal impact
    NON_CRITICAL = 'non_critical'  # No production impact


class MeterType(str, Enum):
    """Meter measurement type."""
    CONTINUOUS = 'continuous'   # e.g., runtime hours
    GAUGE = 'gauge'             # e.g., temperature
    CHARACTERISTIC = 'characteristic'  # e.g., vibration level


class AssetClass(AuditedModel):
    """Classification for assets (e.g., 3D Printer, CNC Mill)."""

    __tablename__ = 'asset_classes'

    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    parent_class_id = Column(UUID(as_uuid=True), ForeignKey('asset_classes.id'))

    # Default maintenance parameters
    default_pm_interval_days = Column(Integer)
    default_pm_interval_hours = Column(Float)
    expected_lifespan_years = Column(Float)

    # Specification template
    spec_template = Column(JSON, default=dict)

    # Relationships
    parent_class = relationship('AssetClass', remote_side='AssetClass.id', backref='subclasses')
    assets = relationship('Asset', back_populates='asset_class')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'parent_class_id': str(self.parent_class_id) if self.parent_class_id else None,
            'default_pm_interval_days': self.default_pm_interval_days,
            'default_pm_interval_hours': self.default_pm_interval_hours,
        }


class Asset(AuditedModel):
    """Physical asset in the factory."""

    __tablename__ = 'assets'

    asset_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Classification
    asset_class_id = Column(UUID(as_uuid=True), ForeignKey('asset_classes.id'))
    status = Column(SQLEnum(AssetStatus), default=AssetStatus.OPERATIONAL)
    criticality = Column(SQLEnum(AssetCriticality), default=AssetCriticality.STANDARD)

    # Location
    location_id = Column(String(50))
    location_description = Column(String(200))
    work_center_id = Column(String(50))

    # Identification
    serial_number = Column(String(100))
    model_number = Column(String(100))
    manufacturer = Column(String(200))
    vendor_id = Column(String(50))

    # Dates
    purchase_date = Column(Date)
    installation_date = Column(Date)
    warranty_expiry = Column(Date)
    expected_retirement = Column(Date)

    # Financial
    purchase_cost = Column(Float)
    replacement_cost = Column(Float)
    salvage_value = Column(Float)

    # Operational
    machine_id = Column(String(50), index=True)  # Links to SCADA machine
    parent_asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'))

    # Specifications and documents
    specifications = Column(JSON, default=dict)
    documents = Column(JSON, default=list)  # List of document references

    # Relationships
    asset_class = relationship('AssetClass', back_populates='assets')
    parent_asset = relationship('Asset', remote_side='Asset.id', backref='child_assets')
    meters = relationship('Meter', back_populates='asset', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_asset_status', 'status'),
        Index('ix_asset_class', 'asset_class_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'asset_id': self.asset_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'criticality': self.criticality.value if self.criticality else None,
            'location_id': self.location_id,
            'machine_id': self.machine_id,
            'serial_number': self.serial_number,
            'manufacturer': self.manufacturer,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'installation_date': self.installation_date.isoformat() if self.installation_date else None,
        }


class Meter(AuditedModel):
    """Meter attached to an asset for condition monitoring."""

    __tablename__ = 'meters'

    meter_id = Column(String(50), unique=True, nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    meter_type = Column(SQLEnum(MeterType), default=MeterType.CONTINUOUS)
    unit_of_measure = Column(String(50))

    # Current reading
    last_reading = Column(Float)
    last_reading_date = Column(DateTime)

    # Thresholds for alerts
    warning_threshold = Column(Float)
    critical_threshold = Column(Float)

    # For continuous meters (like runtime)
    rollover_value = Column(Float)  # Value at which meter resets

    # Reading interval
    average_daily_usage = Column(Float)

    # Relationships
    asset = relationship('Asset', back_populates='meters')
    readings = relationship('MeterReading', back_populates='meter', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'meter_id': self.meter_id,
            'asset_id': str(self.asset_id),
            'name': self.name,
            'meter_type': self.meter_type.value if self.meter_type else None,
            'unit_of_measure': self.unit_of_measure,
            'last_reading': self.last_reading,
            'last_reading_date': self.last_reading_date.isoformat() if self.last_reading_date else None,
        }


class MeterReading(BaseModel):
    """Historical meter reading."""

    __tablename__ = 'meter_readings'

    meter_id = Column(UUID(as_uuid=True), ForeignKey('meters.id'), nullable=False)
    reading_date = Column(DateTime, nullable=False, index=True)
    reading_value = Column(Float, nullable=False)
    delta = Column(Float)  # Change from previous reading

    # Source
    source = Column(String(50))  # 'manual', 'automatic', 'import'
    recorded_by = Column(String(50))

    # Relationships
    meter = relationship('Meter', back_populates='readings')

    __table_args__ = (
        Index('ix_meter_reading_date', 'meter_id', 'reading_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'meter_id': str(self.meter_id),
            'reading_date': self.reading_date.isoformat() if self.reading_date else None,
            'reading_value': self.reading_value,
            'delta': self.delta,
            'source': self.source,
        }


class Spare(AuditedModel):
    """Spare part inventory item linked to assets."""

    __tablename__ = 'spares'

    spare_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Stock
    item_id = Column(String(50))  # Links to ERP inventory item
    quantity_on_hand = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    reorder_quantity = Column(Integer, default=1)

    # Cost
    unit_cost = Column(Float)

    # Vendor
    vendor_id = Column(String(50))
    vendor_part_number = Column(String(100))
    lead_time_days = Column(Integer)

    # Location
    bin_location = Column(String(100))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'spare_id': self.spare_id,
            'name': self.name,
            'quantity_on_hand': self.quantity_on_hand,
            'reorder_point': self.reorder_point,
            'unit_cost': self.unit_cost,
        }


class AssetSpare(BaseModel):
    """Association between assets and their spare parts."""

    __tablename__ = 'asset_spares'

    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), primary_key=True)
    spare_id = Column(UUID(as_uuid=True), ForeignKey('spares.id'), primary_key=True)
    quantity_required = Column(Integer, default=1)
    notes = Column(Text)
