"""
LEGO Factory v3 - NCR/CAPA Models
==================================
Non-Conformance Reports and Corrective/Preventive Actions.
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


class NCRStatus(str, Enum):
    """NCR lifecycle status."""
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_INVESTIGATION = 'under_investigation'
    PENDING_DISPOSITION = 'pending_disposition'
    DISPOSITION_APPROVED = 'disposition_approved'
    IN_PROGRESS = 'in_progress'
    PENDING_VERIFICATION = 'pending_verification'
    VERIFIED = 'verified'
    CLOSED = 'closed'
    VOIDED = 'voided'


class NCRType(str, Enum):
    """Type of non-conformance."""
    PRODUCT = 'product'
    PROCESS = 'process'
    SUPPLIER = 'supplier'
    CUSTOMER_COMPLAINT = 'customer_complaint'
    AUDIT_FINDING = 'audit_finding'
    INTERNAL = 'internal'


class DispositionType(str, Enum):
    """NCR disposition types."""
    USE_AS_IS = 'use_as_is'
    REWORK = 'rework'
    REPAIR = 'repair'
    SCRAP = 'scrap'
    RETURN_TO_SUPPLIER = 'return_to_supplier'
    SORT_AND_INSPECT = 'sort_and_inspect'
    ENGINEERING_CONCESSION = 'engineering_concession'


class Severity(str, Enum):
    """Issue severity levels."""
    CRITICAL = 'critical'
    MAJOR = 'major'
    MINOR = 'minor'
    OBSERVATION = 'observation'


class CAPAType(str, Enum):
    """CAPA type."""
    CORRECTIVE = 'corrective'
    PREVENTIVE = 'preventive'
    IMPROVEMENT = 'improvement'


class CAPAStatus(str, Enum):
    """CAPA lifecycle status."""
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    ROOT_CAUSE_ANALYSIS = 'root_cause_analysis'
    ACTION_PLANNING = 'action_planning'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    IN_IMPLEMENTATION = 'in_implementation'
    PENDING_VERIFICATION = 'pending_verification'
    EFFECTIVENESS_CHECK = 'effectiveness_check'
    CLOSED = 'closed'
    VOIDED = 'voided'


class NonConformanceReport(AuditedModel):
    """Non-Conformance Report (NCR)."""

    __tablename__ = 'ncrs'

    ncr_number = Column(String(50), unique=True, nullable=False, index=True)

    # Classification
    ncr_type = Column(SQLEnum(NCRType), nullable=False)
    severity = Column(SQLEnum(Severity), default=Severity.MINOR)
    status = Column(SQLEnum(NCRStatus), default=NCRStatus.DRAFT)

    # Description
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    detected_date = Column(Date, nullable=False, default=date.today)
    detected_by = Column(String(50), nullable=False)
    detection_location = Column(String(200))
    detection_stage = Column(String(100))  # 'incoming', 'in_process', 'final', 'customer'

    # Product/Process affected
    item_id = Column(String(50))
    lot_number = Column(String(50))
    serial_numbers = Column(JSON, default=list)
    work_order_id = Column(String(50))
    operation_id = Column(String(50))
    quantity_affected = Column(Float)
    quantity_inspected = Column(Float)

    # Supplier (if supplier NCR)
    vendor_id = Column(String(50))
    purchase_order_id = Column(String(50))

    # Customer (if customer complaint)
    customer_id = Column(String(50))
    sales_order_id = Column(String(50))
    customer_complaint_date = Column(Date)

    # Containment
    containment_action = Column(Text)
    containment_date = Column(DateTime)
    containment_by = Column(String(50))

    # Investigation
    investigation_lead = Column(String(50))
    root_cause = Column(Text)
    root_cause_category = Column(String(100))  # '5Why', 'Fishbone', etc.

    # Disposition
    disposition = Column(SQLEnum(DispositionType))
    disposition_reason = Column(Text)
    disposition_approved_by = Column(String(50))
    disposition_date = Column(DateTime)

    # Cost
    estimated_cost = Column(Float)
    actual_cost = Column(Float)

    # Due dates
    target_close_date = Column(Date)
    actual_close_date = Column(Date)

    # CAPA linkage
    capa_required = Column(Boolean, default=False)

    # Documents
    attachments = Column(JSON, default=list)

    # Relationships
    capa_records = relationship('CAPA', back_populates='ncr')

    __table_args__ = (
        Index('ix_ncr_status', 'status'),
        Index('ix_ncr_type', 'ncr_type'),
        Index('ix_ncr_severity', 'severity'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'ncr_number': self.ncr_number,
            'ncr_type': self.ncr_type.value if self.ncr_type else None,
            'severity': self.severity.value if self.severity else None,
            'status': self.status.value if self.status else None,
            'title': self.title,
            'detected_date': self.detected_date.isoformat() if self.detected_date else None,
            'detected_by': self.detected_by,
            'disposition': self.disposition.value if self.disposition else None,
            'capa_required': self.capa_required,
        }


class CAPA(AuditedModel):
    """Corrective and Preventive Action."""

    __tablename__ = 'capas'

    capa_number = Column(String(50), unique=True, nullable=False, index=True)

    # Classification
    capa_type = Column(SQLEnum(CAPAType), nullable=False)
    status = Column(SQLEnum(CAPAStatus), default=CAPAStatus.DRAFT)
    priority = Column(String(20), default='medium')  # low, medium, high, critical

    # Source
    ncr_id = Column(UUID(as_uuid=True), ForeignKey('ncrs.id'))
    audit_finding_id = Column(UUID(as_uuid=True))
    source_type = Column(String(50))  # 'ncr', 'audit', 'customer_complaint', 'management_review'
    source_reference = Column(String(200))

    # Description
    title = Column(String(500), nullable=False)
    problem_statement = Column(Text, nullable=False)
    scope = Column(Text)

    # Ownership
    owner_id = Column(String(50), nullable=False)
    owner_department = Column(String(100))

    # Root Cause Analysis
    root_cause_method = Column(String(100))  # '5Why', 'Fishbone', 'FTA', 'RCA'
    root_cause = Column(Text)
    contributing_factors = Column(JSON, default=list)

    # Risk Assessment
    risk_before = Column(Integer)  # 1-25 scale
    risk_after = Column(Integer)

    # Due dates
    initiation_date = Column(Date, default=date.today)
    target_completion_date = Column(Date)
    actual_completion_date = Column(Date)
    effectiveness_check_date = Column(Date)

    # Verification
    verification_method = Column(Text)
    verification_criteria = Column(Text)
    verification_result = Column(Text)
    verified_by = Column(String(50))
    verified_date = Column(DateTime)

    # Effectiveness
    effectiveness_criteria = Column(Text)
    effectiveness_result = Column(Text)
    is_effective = Column(Boolean)
    effectiveness_reviewed_by = Column(String(50))
    effectiveness_review_date = Column(DateTime)

    # Cost
    estimated_cost = Column(Float)
    actual_cost = Column(Float)

    # Documents
    attachments = Column(JSON, default=list)

    # Extension tracking
    extension_count = Column(Integer, default=0)
    extension_reasons = Column(JSON, default=list)

    # Relationships
    ncr = relationship('NonConformanceReport', back_populates='capa_records')
    actions = relationship('CAPAAction', back_populates='capa', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_capa_status', 'status'),
        Index('ix_capa_type', 'capa_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'capa_number': self.capa_number,
            'capa_type': self.capa_type.value if self.capa_type else None,
            'status': self.status.value if self.status else None,
            'title': self.title,
            'owner_id': self.owner_id,
            'target_completion_date': self.target_completion_date.isoformat() if self.target_completion_date else None,
            'is_effective': self.is_effective,
        }


class CAPAAction(AuditedModel):
    """Individual action within a CAPA."""

    __tablename__ = 'capa_actions'

    capa_id = Column(UUID(as_uuid=True), ForeignKey('capas.id'), nullable=False)
    action_number = Column(Integer, nullable=False)

    # Action details
    action_type = Column(String(50))  # 'immediate', 'short_term', 'long_term', 'systemic'
    description = Column(Text, nullable=False)

    # Assignment
    assigned_to = Column(String(50), nullable=False)
    assigned_department = Column(String(100))

    # Dates
    target_date = Column(Date)
    completed_date = Column(Date)

    # Status
    status = Column(String(50), default='open')  # open, in_progress, completed, verified, cancelled

    # Completion
    completion_notes = Column(Text)
    evidence = Column(JSON, default=list)

    # Verification
    verification_required = Column(Boolean, default=True)
    verified_by = Column(String(50))
    verified_date = Column(DateTime)
    verification_notes = Column(Text)

    # Relationships
    capa = relationship('CAPA', back_populates='actions')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'capa_id': str(self.capa_id),
            'action_number': self.action_number,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'status': self.status,
        }
