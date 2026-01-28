"""
LEGO Factory v3 - QMS Quality Models
=====================================
Audits, Training, Calibration, and SPC.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


# ============== Audit Models ==============

class AuditType(str, Enum):
    """Audit types."""
    INTERNAL = 'internal'
    EXTERNAL = 'external'
    SUPPLIER = 'supplier'
    CUSTOMER = 'customer'
    REGULATORY = 'regulatory'
    PROCESS = 'process'


class AuditStatus(str, Enum):
    """Audit lifecycle status."""
    PLANNED = 'planned'
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    REPORT_DRAFT = 'report_draft'
    REPORT_REVIEW = 'report_review'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class FindingSeverity(str, Enum):
    """Audit finding severity."""
    CRITICAL = 'critical'
    MAJOR = 'major'
    MINOR = 'minor'
    OBSERVATION = 'observation'
    OPPORTUNITY = 'opportunity'


class Audit(AuditedModel):
    """Quality audit record."""

    __tablename__ = 'audits'

    audit_number = Column(String(50), unique=True, nullable=False, index=True)

    # Classification
    audit_type = Column(SQLEnum(AuditType), nullable=False)
    status = Column(SQLEnum(AuditStatus), default=AuditStatus.PLANNED)

    # Description
    title = Column(String(500), nullable=False)
    scope = Column(Text)
    objectives = Column(JSON, default=list)
    criteria = Column(JSON, default=list)  # Standards, procedures being audited

    # Auditee
    department = Column(String(100))
    process = Column(String(200))
    auditee_contact = Column(String(50))

    # Audit team
    lead_auditor = Column(String(50), nullable=False)
    audit_team = Column(JSON, default=list)

    # Dates
    planned_start = Column(Date)
    planned_end = Column(Date)
    actual_start = Column(Date)
    actual_end = Column(Date)

    # Schedule
    audit_schedule = Column(JSON, default=list)  # Day-by-day schedule

    # Results
    summary = Column(Text)
    conclusion = Column(Text)
    findings_count = Column(JSON, default=dict)  # Count by severity

    # Report
    report_date = Column(Date)
    report_approved_by = Column(String(50))
    report_approved_date = Column(DateTime)

    # Follow-up
    follow_up_date = Column(Date)

    # Documents
    attachments = Column(JSON, default=list)

    # Relationships
    findings = relationship('AuditFinding', back_populates='audit', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_audit_status', 'status'),
        Index('ix_audit_type', 'audit_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'audit_number': self.audit_number,
            'audit_type': self.audit_type.value if self.audit_type else None,
            'status': self.status.value if self.status else None,
            'title': self.title,
            'lead_auditor': self.lead_auditor,
            'planned_start': self.planned_start.isoformat() if self.planned_start else None,
            'findings_count': self.findings_count,
        }


class AuditFinding(AuditedModel):
    """Finding from an audit."""

    __tablename__ = 'audit_findings'

    audit_id = Column(UUID(as_uuid=True), ForeignKey('audits.id'), nullable=False)
    finding_number = Column(String(50), nullable=False)

    # Classification
    severity = Column(SQLEnum(FindingSeverity), nullable=False)
    category = Column(String(100))  # e.g., 'Documentation', 'Training', 'Equipment'

    # Details
    reference = Column(String(200))  # Clause, procedure reference
    description = Column(Text, nullable=False)
    objective_evidence = Column(Text)
    risk_assessment = Column(Text)

    # Response
    auditee_response = Column(Text)
    response_date = Column(Date)

    # CAPA linkage
    capa_required = Column(Boolean, default=False)
    capa_id = Column(UUID(as_uuid=True), ForeignKey('capas.id'))

    # Closure
    is_closed = Column(Boolean, default=False)
    closure_date = Column(Date)
    closure_evidence = Column(Text)
    closed_by = Column(String(50))

    # Relationships
    audit = relationship('Audit', back_populates='findings')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'audit_id': str(self.audit_id),
            'finding_number': self.finding_number,
            'severity': self.severity.value if self.severity else None,
            'description': self.description,
            'capa_required': self.capa_required,
            'is_closed': self.is_closed,
        }


# ============== Training Models ==============

class TrainingStatus(str, Enum):
    """Training record status."""
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    EXPIRED = 'expired'
    WAIVED = 'waived'


class TrainingCourse(AuditedModel):
    """Training course definition."""

    __tablename__ = 'training_courses'

    course_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Classification
    category = Column(String(100))
    course_type = Column(String(50))  # 'classroom', 'online', 'ojt', 'self_study'

    # Content
    duration_hours = Column(Float)
    materials = Column(JSON, default=list)
    assessment_required = Column(Boolean, default=False)
    passing_score = Column(Float)

    # Requirements
    prerequisites = Column(JSON, default=list)
    required_for_roles = Column(JSON, default=list)

    # Recertification
    validity_months = Column(Integer)  # How long certification is valid

    # Documents
    document_ids = Column(JSON, default=list)

    is_active = Column(Boolean, default=True)

    # Relationships
    records = relationship('TrainingRecord', back_populates='course')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'course_id': self.course_id,
            'title': self.title,
            'category': self.category,
            'duration_hours': self.duration_hours,
            'validity_months': self.validity_months,
            'is_active': self.is_active,
        }


class TrainingRecord(AuditedModel):
    """Individual training record."""

    __tablename__ = 'training_records'

    course_id = Column(UUID(as_uuid=True), ForeignKey('training_courses.id'), nullable=False)
    trainee_id = Column(String(50), nullable=False, index=True)
    trainee_name = Column(String(200))

    # Status
    status = Column(SQLEnum(TrainingStatus), default=TrainingStatus.SCHEDULED)

    # Dates
    scheduled_date = Column(Date)
    completion_date = Column(Date)
    expiry_date = Column(Date)

    # Instructor
    instructor_id = Column(String(50))
    instructor_name = Column(String(200))

    # Assessment
    assessment_score = Column(Float)
    assessment_passed = Column(Boolean)
    assessment_date = Column(Date)

    # Certification
    certificate_number = Column(String(100))

    # Notes
    notes = Column(Text)

    # E-signature for completion
    signed_by_trainee = Column(Boolean, default=False)
    trainee_signature_date = Column(DateTime)
    signed_by_instructor = Column(Boolean, default=False)
    instructor_signature_date = Column(DateTime)

    # Relationships
    course = relationship('TrainingCourse', back_populates='records')

    __table_args__ = (
        Index('ix_training_trainee', 'trainee_id'),
        Index('ix_training_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'course_id': str(self.course_id),
            'trainee_id': self.trainee_id,
            'status': self.status.value if self.status else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'assessment_passed': self.assessment_passed,
        }


# ============== Calibration Models ==============

class CalibrationStatus(str, Enum):
    """Calibration status."""
    CURRENT = 'current'
    DUE = 'due'
    OVERDUE = 'overdue'
    OUT_OF_SERVICE = 'out_of_service'
    RETIRED = 'retired'


class CalibratedEquipment(AuditedModel):
    """Equipment requiring calibration."""

    __tablename__ = 'calibrated_equipment'

    equipment_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Classification
    equipment_type = Column(String(100))
    category = Column(String(100))

    # Identification
    manufacturer = Column(String(200))
    model = Column(String(100))
    serial_number = Column(String(100))
    asset_id = Column(String(50))  # Link to CMMS asset

    # Location
    location = Column(String(200))
    custodian = Column(String(50))

    # Calibration
    calibration_procedure = Column(String(200))
    calibration_interval_days = Column(Integer, default=365)
    last_calibration_date = Column(Date)
    next_calibration_due = Column(Date)
    status = Column(SQLEnum(CalibrationStatus), default=CalibrationStatus.CURRENT)

    # Specifications
    range_min = Column(Float)
    range_max = Column(Float)
    resolution = Column(Float)
    accuracy = Column(String(100))
    unit_of_measure = Column(String(50))

    # Traceability
    traceable_to = Column(String(200))  # e.g., NIST

    # Documents
    certificate_ids = Column(JSON, default=list)

    is_active = Column(Boolean, default=True)

    # Relationships
    records = relationship('CalibrationRecord', back_populates='equipment', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'equipment_id': self.equipment_id,
            'name': self.name,
            'serial_number': self.serial_number,
            'status': self.status.value if self.status else None,
            'last_calibration_date': self.last_calibration_date.isoformat() if self.last_calibration_date else None,
            'next_calibration_due': self.next_calibration_due.isoformat() if self.next_calibration_due else None,
        }


class CalibrationRecord(AuditedModel):
    """Calibration record."""

    __tablename__ = 'calibration_records'

    equipment_id = Column(UUID(as_uuid=True), ForeignKey('calibrated_equipment.id'), nullable=False)
    calibration_number = Column(String(50), unique=True, nullable=False)

    # Dates
    calibration_date = Column(Date, nullable=False)
    next_due_date = Column(Date)

    # Who performed
    performed_by = Column(String(50), nullable=False)
    performed_by_company = Column(String(200))  # If external

    # Results
    result = Column(String(50), nullable=False)  # 'pass', 'fail', 'adjusted', 'limited_use'
    as_found_data = Column(JSON, default=dict)
    as_left_data = Column(JSON, default=dict)
    adjustments_made = Column(Text)
    out_of_tolerance_action = Column(Text)

    # Standards used
    standards_used = Column(JSON, default=list)

    # Environment
    temperature = Column(Float)
    humidity = Column(Float)

    # Certificate
    certificate_number = Column(String(100))
    certificate_file = Column(String(500))

    # Approval
    reviewed_by = Column(String(50))
    reviewed_date = Column(DateTime)

    # Relationships
    equipment = relationship('CalibratedEquipment', back_populates='records')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'equipment_id': str(self.equipment_id),
            'calibration_number': self.calibration_number,
            'calibration_date': self.calibration_date.isoformat() if self.calibration_date else None,
            'result': self.result,
            'performed_by': self.performed_by,
        }


# ============== SPC Models ==============

class SPCChart(AuditedModel):
    """Statistical Process Control chart definition."""

    __tablename__ = 'spc_charts'

    chart_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # What is being measured
    process = Column(String(200))
    characteristic = Column(String(200), nullable=False)
    unit_of_measure = Column(String(50))

    # Chart type
    chart_type = Column(String(50), nullable=False)  # 'xbar_r', 'xbar_s', 'p', 'np', 'c', 'u', 'imr'
    subgroup_size = Column(Integer, default=5)

    # Specification limits
    usl = Column(Float)  # Upper Spec Limit
    lsl = Column(Float)  # Lower Spec Limit
    target = Column(Float)

    # Control limits (calculated or fixed)
    ucl = Column(Float)  # Upper Control Limit
    lcl = Column(Float)  # Lower Control Limit
    center_line = Column(Float)

    # For range/sigma charts
    ucl_r = Column(Float)
    lcl_r = Column(Float)
    center_line_r = Column(Float)

    # Data collection
    machine_id = Column(String(50))
    tag_id = Column(String(50))  # SCADA tag for automatic data

    # Active
    is_active = Column(Boolean, default=True)

    # Relationships
    data = relationship('SPCData', back_populates='chart', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'chart_id': self.chart_id,
            'name': self.name,
            'chart_type': self.chart_type,
            'characteristic': self.characteristic,
            'usl': self.usl,
            'lsl': self.lsl,
            'ucl': self.ucl,
            'lcl': self.lcl,
        }


class SPCData(AuditedModel):
    """SPC measurement data."""

    __tablename__ = 'spc_data'

    chart_id = Column(UUID(as_uuid=True), ForeignKey('spc_charts.id'), nullable=False)

    # Timing
    sample_time = Column(DateTime, nullable=False, index=True)
    subgroup_number = Column(Integer)

    # Measurements
    values = Column(JSON, nullable=False)  # List of measurements in subgroup
    mean = Column(Float)
    range_value = Column(Float)
    std_dev = Column(Float)

    # Status
    in_control = Column(Boolean, default=True)
    rule_violations = Column(JSON, default=list)  # Western Electric rules violated

    # Source
    operator_id = Column(String(50))
    work_order_id = Column(String(50))
    lot_number = Column(String(50))

    notes = Column(Text)

    # Relationships
    chart = relationship('SPCChart', back_populates='data')

    __table_args__ = (
        Index('ix_spc_data_time', 'chart_id', 'sample_time'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'chart_id': str(self.chart_id),
            'sample_time': self.sample_time.isoformat() if self.sample_time else None,
            'mean': self.mean,
            'range_value': self.range_value,
            'in_control': self.in_control,
            'rule_violations': self.rule_violations,
        }
