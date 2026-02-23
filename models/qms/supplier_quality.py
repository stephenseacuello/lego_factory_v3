"""
LEGO Factory v3 - Supplier Quality Models
=========================================
Supplier quality management and incoming inspection.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel, VersionedModel


class SupplierGrade(str, Enum):
    """Supplier quality grades."""
    A_PREFERRED = 'A'
    B_APPROVED = 'B'
    C_CONDITIONAL = 'C'
    D_PROBATION = 'D'
    DISQUALIFIED = 'X'


class InspectionType(str, Enum):
    """Types of quality inspections."""
    INCOMING = 'incoming'
    IN_PROCESS = 'in_process'
    FINAL = 'final'
    FIRST_ARTICLE = 'first_article'
    PERIODIC = 'periodic'


class InspectionResult(str, Enum):
    """Inspection disposition results."""
    ACCEPT = 'accept'
    REJECT = 'reject'
    CONDITIONAL = 'conditional'
    HOLD = 'hold'
    REWORK = 'rework'
    USE_AS_IS = 'use_as_is'


class CharacteristicType(str, Enum):
    """Inspection characteristic types."""
    DIMENSIONAL = 'dimensional'
    VISUAL = 'visual'
    FUNCTIONAL = 'functional'
    MATERIAL = 'material'
    DOCUMENTATION = 'documentation'


class SupplierQualityRating(AuditedModel):
    """
    Supplier quality performance tracking.

    Tracks quality metrics for each supplier.
    """

    __tablename__ = 'supplier_quality_ratings'

    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False, index=True)

    # Rating period
    rating_period = Column(String(20), nullable=False)  # e.g., '2024-Q1'
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Quality metrics
    total_lots_received = Column(Integer, default=0)
    lots_rejected = Column(Integer, default=0)
    lots_accepted = Column(Integer, default=0)
    lots_conditional = Column(Integer, default=0)

    total_qty_received = Column(Float, default=0)
    qty_rejected = Column(Float, default=0)
    qty_reworked = Column(Float, default=0)

    # PPM calculations
    defects_per_million = Column(Float)
    reject_rate_percent = Column(Float)

    # Delivery metrics
    on_time_delivery_percent = Column(Float)
    complete_delivery_percent = Column(Float)

    # Score and grade
    quality_score = Column(Float)  # 0-100
    delivery_score = Column(Float)  # 0-100
    overall_score = Column(Float)  # 0-100
    grade = Column(SQLEnum(SupplierGrade), index=True)

    # NCRs issued
    ncr_count = Column(Integer, default=0)
    capa_count = Column(Integer, default=0)

    # Notes
    notes = Column(Text)

    __table_args__ = (
        Index('ix_supplier_ratings_vendor_period', 'vendor_id', 'rating_period'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'vendor_id': str(self.vendor_id),
            'rating_period': self.rating_period,
            'total_lots_received': self.total_lots_received,
            'lots_rejected': self.lots_rejected,
            'defects_per_million': self.defects_per_million,
            'overall_score': self.overall_score,
            'grade': self.grade.value if self.grade else None,
        }


class InspectionPlan(VersionedModel):
    """
    Inspection plan template.

    Defines what characteristics to inspect and how.
    """

    __tablename__ = 'inspection_plans'

    plan_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # What it applies to
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'))
    applies_to = Column(String(50))  # 'item', 'category', 'vendor'

    # Inspection type
    inspection_type = Column(SQLEnum(InspectionType), default=InspectionType.INCOMING)

    # Sampling
    sampling_type = Column(String(50))  # 'none', 'fixed', 'aql', 'skip_lot'
    sample_size = Column(Integer)
    aql_level = Column(String(20))  # AQL level for sampling plans

    # Frequency
    inspection_frequency = Column(String(50))  # 'every_lot', 'skip_lot', 'periodic'
    lots_between_inspection = Column(Integer)

    # Requirements
    requires_coc = Column(Boolean, default=False)  # Certificate of Conformance
    requires_test_report = Column(Boolean, default=False)

    # Active status
    is_active = Column(Boolean, default=True)
    effective_date = Column(Date)
    expiry_date = Column(Date)

    # Relationships
    characteristics = relationship('InspectionCharacteristic', back_populates='plan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'plan_id': self.plan_id,
            'name': self.name,
            'inspection_type': self.inspection_type.value if self.inspection_type else None,
            'sampling_type': self.sampling_type,
            'sample_size': self.sample_size,
            'is_active': self.is_active,
        }


class InspectionCharacteristic(BaseModel):
    """
    Inspection characteristic definition.

    Defines a specific measurement or check to perform.
    """

    __tablename__ = 'inspection_characteristics'

    plan_id = Column(UUID(as_uuid=True), ForeignKey('inspection_plans.id'), nullable=False, index=True)

    # Characteristic definition
    sequence = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    characteristic_type = Column(SQLEnum(CharacteristicType), default=CharacteristicType.DIMENSIONAL)

    # Measurement
    measurement_type = Column(String(50))  # 'variable', 'attribute'
    unit_of_measure = Column(String(50))

    # Specification limits
    nominal_value = Column(Float)
    tolerance_plus = Column(Float)
    tolerance_minus = Column(Float)
    lower_spec_limit = Column(Float)
    upper_spec_limit = Column(Float)

    # For attribute inspections
    attribute_pass_criteria = Column(String(200))

    # Gauging
    gauge_id = Column(String(100))
    gauge_resolution = Column(Float)

    # Criticality
    is_critical = Column(Boolean, default=False)
    is_major = Column(Boolean, default=True)

    # Sampling override
    sample_size_override = Column(Integer)

    # Drawing reference
    drawing_reference = Column(String(200))

    # Instructions
    inspection_method = Column(Text)

    # Relationship
    plan = relationship('InspectionPlan', back_populates='characteristics')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'plan_id': str(self.plan_id),
            'sequence': self.sequence,
            'name': self.name,
            'characteristic_type': self.characteristic_type.value if self.characteristic_type else None,
            'nominal_value': self.nominal_value,
            'tolerance_plus': self.tolerance_plus,
            'tolerance_minus': self.tolerance_minus,
            'is_critical': self.is_critical,
        }


class InspectionRecord(AuditedModel):
    """
    Inspection record / results.

    Records the actual inspection performed.
    """

    __tablename__ = 'inspection_records'

    record_id = Column(String(50), unique=True, nullable=False, index=True)

    # What was inspected
    inspection_type = Column(SQLEnum(InspectionType), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('inspection_plans.id'))
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'))
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))
    receipt_id = Column(UUID(as_uuid=True), ForeignKey('receipts.id'))
    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'))

    # Supplier info
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'))
    po_number = Column(String(100))

    # Lot information
    lot_qty = Column(Float)
    sample_qty = Column(Float)

    # Results
    disposition = Column(SQLEnum(InspectionResult), index=True)
    total_defects = Column(Integer, default=0)
    major_defects = Column(Integer, default=0)
    minor_defects = Column(Integer, default=0)
    critical_defects = Column(Integer, default=0)

    # Inspector
    inspector_id = Column(String(100), index=True)
    inspection_date = Column(DateTime, nullable=False)
    inspection_location = Column(String(100))

    # Documentation
    notes = Column(Text)
    coc_received = Column(Boolean, default=False)
    test_report_received = Column(Boolean, default=False)
    attachments = Column(JSON, default=list)

    # Related NCR if rejected
    ncr_id = Column(UUID(as_uuid=True), ForeignKey('ncrs.id'))

    # Approval
    approved_by = Column(String(100))
    approved_at = Column(DateTime)

    # Relationships
    measurements = relationship('InspectionMeasurement', back_populates='record')

    __table_args__ = (
        Index('ix_inspection_records_date', 'inspection_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'record_id': self.record_id,
            'inspection_type': self.inspection_type.value if self.inspection_type else None,
            'item_id': str(self.item_id) if self.item_id else None,
            'lot_id': str(self.lot_id) if self.lot_id else None,
            'disposition': self.disposition.value if self.disposition else None,
            'total_defects': self.total_defects,
            'inspection_date': self.inspection_date.isoformat() if self.inspection_date else None,
            'inspector_id': self.inspector_id,
        }


class InspectionMeasurement(BaseModel):
    """
    Individual inspection measurement.

    Records each characteristic measurement result.
    """

    __tablename__ = 'inspection_measurements'

    record_id = Column(UUID(as_uuid=True), ForeignKey('inspection_records.id'), nullable=False, index=True)
    characteristic_id = Column(UUID(as_uuid=True), ForeignKey('inspection_characteristics.id'))

    # Measurement details
    sequence = Column(Integer)
    characteristic_name = Column(String(200), nullable=False)
    measurement_type = Column(String(50))

    # Results (for variable data)
    measured_value = Column(Float)
    nominal_value = Column(Float)
    lower_limit = Column(Float)
    upper_limit = Column(Float)
    deviation = Column(Float)

    # Results (for attribute data)
    attribute_result = Column(String(50))  # 'pass', 'fail'
    defects_found = Column(Integer, default=0)

    # Pass/Fail
    is_conforming = Column(Boolean)

    # Notes
    notes = Column(Text)
    gauge_used = Column(String(100))

    # Sample number (for multiple samples)
    sample_number = Column(Integer, default=1)

    # Relationship
    record = relationship('InspectionRecord', back_populates='measurements')

    __table_args__ = (
        Index('ix_inspection_measurements_record', 'record_id', 'sequence'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'record_id': str(self.record_id),
            'characteristic_name': self.characteristic_name,
            'measured_value': self.measured_value,
            'nominal_value': self.nominal_value,
            'is_conforming': self.is_conforming,
            'defects_found': self.defects_found,
        }
