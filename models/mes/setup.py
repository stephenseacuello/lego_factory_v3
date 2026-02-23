"""
LEGO Factory v3 - Setup/Changeover Models
==========================================
Setup events, procedures, benchmarks, and SMED improvement tracking.
"""

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import (
    Column, String, Float, DateTime, Text, Integer,
    ForeignKey, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID

from models.base import AuditedModel


class SetupEvent(AuditedModel):
    """Recorded setup/changeover event."""

    __tablename__ = 'setup_events'

    setup_id = Column(String(50), unique=True, nullable=False, index=True)
    machine_id = Column(String(100), nullable=False, index=True)
    job_id = Column(String(100))
    from_product = Column(String(100))
    to_product = Column(String(100))
    operator_id = Column(String(100))
    setup_type = Column(String(50), default='internal')  # internal / external
    duration_minutes = Column(Float, nullable=False)
    total_duration_minutes = Column(Float)
    pause_minutes = Column(Float, default=0)
    step_times = Column(JSON, default=dict)
    notes = Column(Text)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index('ix_setup_events_machine_completed', 'machine_id', 'completed_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'setup_id': self.setup_id,
            'machine_id': self.machine_id,
            'job_id': self.job_id,
            'from_product': self.from_product,
            'to_product': self.to_product,
            'operator_id': self.operator_id,
            'setup_type': self.setup_type,
            'duration_minutes': self.duration_minutes,
            'total_duration_minutes': self.total_duration_minutes,
            'pause_minutes': self.pause_minutes,
            'step_times': self.step_times,
            'notes': self.notes,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
        }


class SetupProcedure(AuditedModel):
    """Standardized setup procedure checklist."""

    __tablename__ = 'setup_procedures'

    procedure_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    machine_id = Column(String(100), nullable=False, index=True)
    from_product = Column(String(100))
    to_product = Column(String(100))
    steps = Column(JSON, default=list)  # List of step dicts
    total_estimated_minutes = Column(Float, default=0)
    version = Column(Integer, default=1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'procedure_id': self.procedure_id,
            'name': self.name,
            'machine_id': self.machine_id,
            'from_product': self.from_product,
            'to_product': self.to_product,
            'steps': self.steps,
            'total_estimated_minutes': self.total_estimated_minutes,
            'version': self.version,
        }


class SetupBenchmark(AuditedModel):
    """Benchmark statistics for setup times."""

    __tablename__ = 'setup_benchmarks'

    machine_id = Column(String(100), nullable=False)
    product_transition = Column(String(200), nullable=False)
    best_time_minutes = Column(Float)
    avg_time_minutes = Column(Float)
    worst_time_minutes = Column(Float)
    std_dev_minutes = Column(Float, default=0)
    sample_count = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_setup_benchmarks_machine_transition', 'machine_id', 'product_transition', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'product_transition': self.product_transition,
            'best_time_minutes': self.best_time_minutes,
            'avg_time_minutes': self.avg_time_minutes,
            'worst_time_minutes': self.worst_time_minutes,
            'std_dev_minutes': self.std_dev_minutes,
            'sample_count': self.sample_count,
        }


class SMEDProject(AuditedModel):
    """SMED improvement project tracking."""

    __tablename__ = 'smed_projects'

    project_id = Column(String(50), unique=True, nullable=False, index=True)
    machine_id = Column(String(100), nullable=False)
    product_transition = Column(String(200))
    baseline_minutes = Column(Float)
    current_minutes = Column(Float)
    target_minutes = Column(Float)
    improvement_pct = Column(Float, default=0)
    internal_converted_to_external = Column(JSON, default=list)
    streamlined_steps = Column(JSON, default=list)
    status = Column(String(50), default='active')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'project_id': self.project_id,
            'machine_id': self.machine_id,
            'product_transition': self.product_transition,
            'baseline_minutes': self.baseline_minutes,
            'current_minutes': self.current_minutes,
            'target_minutes': self.target_minutes,
            'improvement_pct': self.improvement_pct,
            'status': self.status,
        }
