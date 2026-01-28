"""
LEGO Factory v3 - Failure Analysis Models
=========================================
Failure codes and root cause analysis.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class FailureType(str, Enum):
    """Types of failures."""
    MECHANICAL = 'mechanical'
    ELECTRICAL = 'electrical'
    PNEUMATIC = 'pneumatic'
    HYDRAULIC = 'hydraulic'
    SOFTWARE = 'software'
    PROCESS = 'process'
    OPERATOR_ERROR = 'operator_error'
    MATERIAL = 'material'
    ENVIRONMENTAL = 'environmental'
    OTHER = 'other'


class FailureSeverity(str, Enum):
    """Failure severity levels."""
    CRITICAL = 'critical'
    MAJOR = 'major'
    MINOR = 'minor'
    INFORMATIONAL = 'informational'


class FailureCode(BaseModel):
    """
    Failure code definition.

    Standard codes for categorizing equipment failures.
    """

    __tablename__ = 'failure_codes'

    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Categorization
    failure_type = Column(SQLEnum(FailureType), nullable=False, index=True)
    category = Column(String(100))
    subcategory = Column(String(100))

    # Severity
    default_severity = Column(SQLEnum(FailureSeverity), default=FailureSeverity.MINOR)

    # Asset class association
    asset_class_id = Column(UUID(as_uuid=True), ForeignKey('asset_classes.id'))
    applies_to = Column(JSON, default=list)  # List of asset types

    # Common causes and solutions
    common_causes = Column(JSON, default=list)
    recommended_actions = Column(JSON, default=list)
    estimated_repair_hours = Column(Float)

    # Active status
    is_active = Column(Boolean, default=True)

    # Relationships
    analyses = relationship('FailureAnalysis', back_populates='failure_code')

    __table_args__ = (
        Index('ix_failure_codes_type_category', 'failure_type', 'category'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'failure_type': self.failure_type.value if self.failure_type else None,
            'category': self.category,
            'default_severity': self.default_severity.value if self.default_severity else None,
            'is_active': self.is_active,
        }


class FailureAnalysis(AuditedModel):
    """
    Failure analysis record.

    Documents the analysis of a specific failure event.
    """

    __tablename__ = 'failure_analyses'

    analysis_id = Column(String(50), unique=True, nullable=False, index=True)

    # What failed
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), nullable=False, index=True)
    failure_code_id = Column(UUID(as_uuid=True), ForeignKey('failure_codes.id'), index=True)
    maintenance_work_order_id = Column(UUID(as_uuid=True), ForeignKey('maintenance_work_orders.id'))
    downtime_event_id = Column(UUID(as_uuid=True), ForeignKey('downtime_events.id'))

    # When it happened
    failure_datetime = Column(DateTime, nullable=False, index=True)
    discovered_datetime = Column(DateTime)
    reported_by = Column(String(100))

    # Severity and impact
    severity = Column(SQLEnum(FailureSeverity), index=True)
    downtime_hours = Column(Float)
    production_loss_units = Column(Float)
    repair_cost = Column(Float)

    # Description
    failure_description = Column(Text, nullable=False)
    symptoms = Column(Text)
    conditions_at_failure = Column(Text)

    # Root cause analysis
    root_cause = Column(Text)
    contributing_factors = Column(JSON, default=list)
    analysis_method = Column(String(100))  # 5-why, fishbone, FMEA, etc.

    # Operating context
    operating_hours_at_failure = Column(Float)
    cycles_at_failure = Column(Integer)
    last_maintenance_date = Column(DateTime)
    days_since_maintenance = Column(Integer)

    # Actions taken
    immediate_actions = Column(Text)
    corrective_actions = Column(JSON, default=list)
    preventive_recommendations = Column(JSON, default=list)

    # Status
    status = Column(String(50), default='open')  # open, in_progress, completed, closed
    analyst = Column(String(100))
    completed_date = Column(DateTime)

    # Related CAPA
    capa_id = Column(UUID(as_uuid=True), ForeignKey('capas.id'))

    # Attachments
    attachments = Column(JSON, default=list)

    # Relationship
    failure_code = relationship('FailureCode', back_populates='analyses')

    __table_args__ = (
        Index('ix_failure_analyses_asset_date', 'asset_id', 'failure_datetime'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'analysis_id': self.analysis_id,
            'asset_id': str(self.asset_id),
            'failure_code_id': str(self.failure_code_id) if self.failure_code_id else None,
            'failure_datetime': self.failure_datetime.isoformat() if self.failure_datetime else None,
            'severity': self.severity.value if self.severity else None,
            'downtime_hours': self.downtime_hours,
            'root_cause': self.root_cause,
            'status': self.status,
        }


class FailureHistory(BaseModel):
    """
    Failure history summary per asset.

    Aggregated failure statistics for reliability analysis.
    """

    __tablename__ = 'failure_history'

    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), nullable=False, index=True)

    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(20))  # 'month', 'quarter', 'year'

    # Counts
    total_failures = Column(Integer, default=0)
    critical_failures = Column(Integer, default=0)
    major_failures = Column(Integer, default=0)
    minor_failures = Column(Integer, default=0)

    # By type
    mechanical_failures = Column(Integer, default=0)
    electrical_failures = Column(Integer, default=0)
    software_failures = Column(Integer, default=0)
    other_failures = Column(Integer, default=0)

    # Time metrics
    total_downtime_hours = Column(Float, default=0)
    mean_time_between_failures = Column(Float)  # MTBF
    mean_time_to_repair = Column(Float)  # MTTR
    availability_percent = Column(Float)

    # Cost
    total_repair_cost = Column(Float, default=0)
    total_production_loss_cost = Column(Float, default=0)

    # Operating context
    operating_hours = Column(Float)
    total_cycles = Column(Integer)

    __table_args__ = (
        Index('ix_failure_history_asset_period', 'asset_id', 'period_start'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'asset_id': str(self.asset_id),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'total_failures': self.total_failures,
            'total_downtime_hours': self.total_downtime_hours,
            'mean_time_between_failures': self.mean_time_between_failures,
            'mean_time_to_repair': self.mean_time_to_repair,
            'availability_percent': self.availability_percent,
        }
