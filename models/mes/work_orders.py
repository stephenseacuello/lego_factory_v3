"""
LEGO Factory v3 - Work Order Models
===================================
Work orders, operations, and jobs for manufacturing execution.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel, SoftDeleteMixin


class WorkOrderStatus(str, Enum):
    """Work order status lifecycle."""
    DRAFT = 'draft'
    PLANNED = 'planned'
    RELEASED = 'released'
    IN_PROGRESS = 'in_progress'
    ON_HOLD = 'on_hold'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = 'pending'
    QUEUED = 'queued'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class OperationType(str, Enum):
    """Types of manufacturing operations."""
    DESIGN = 'design'
    PRINTING_FDM = 'printing_fdm'
    PRINTING_SLA = 'printing_sla'
    CNC_MILLING = 'cnc_milling'
    ASSEMBLY = 'assembly'
    INSPECTION = 'inspection'
    PACKAGING = 'packaging'
    CUSTOM = 'custom'


class WorkOrder(AuditedModel, SoftDeleteMixin):
    """Manufacturing work order."""

    __tablename__ = 'work_orders'

    work_order_id = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)

    # Product/Recipe reference
    product_id = Column(String(50), index=True)
    recipe_id = Column(String(50))  # Recipe reference (FK removed - recipes can have versions)
    quantity_ordered = Column(Integer, default=1)
    quantity_completed = Column(Integer, default=0)

    # Status and priority
    status = Column(SQLEnum(WorkOrderStatus), default=WorkOrderStatus.DRAFT, index=True)
    priority = Column(Integer, default=5)  # 1=highest, 10=lowest

    # Scheduling
    planned_start = Column(DateTime)
    planned_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    due_date = Column(DateTime, index=True)

    # Customer reference
    customer_id = Column(String(50))
    sales_order_id = Column(String(50))

    # Additional data
    notes = Column(Text)
    extra_data = Column(JSON, default=dict)  # renamed from 'metadata' (reserved in SQLAlchemy)

    # Relationships
    operations = relationship('Operation', back_populates='work_order', order_by='Operation.sequence')
    jobs = relationship('Job', back_populates='work_order')

    __table_args__ = (
        Index('ix_work_orders_status_due', 'status', 'due_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': self.work_order_id,
            'description': self.description,
            'product_id': self.product_id,
            'recipe_id': self.recipe_id,
            'quantity_ordered': self.quantity_ordered,
            'quantity_completed': self.quantity_completed,
            'status': self.status.value if self.status else None,
            'priority': self.priority,
            'planned_start': self.planned_start.isoformat() if self.planned_start else None,
            'planned_end': self.planned_end.isoformat() if self.planned_end else None,
            'actual_start': self.actual_start.isoformat() if self.actual_start else None,
            'actual_end': self.actual_end.isoformat() if self.actual_end else None,
            'due_date': self.due_date.isoformat() if self.due_date and hasattr(self.due_date, 'isoformat') else str(self.due_date) if self.due_date else None,
            'customer_id': self.customer_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Operation(BaseModel, SoftDeleteMixin):
    """Operation within a work order (routing step)."""

    __tablename__ = 'operations'

    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'), nullable=False)
    operation_id = Column(String(50), nullable=False)
    sequence = Column(Integer, default=10)

    # Operation details
    operation_type = Column(SQLEnum(OperationType), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Work center assignment
    work_center_id = Column(String(50))
    machine_id = Column(String(50))
    eligible_machines = Column(JSON, default=list)  # List of machine_ids that can perform this operation

    # Time estimates (minutes)
    setup_time = Column(Float, default=0)
    run_time = Column(Float, default=0)
    teardown_time = Column(Float, default=0)

    # Actual times
    actual_setup_time = Column(Float)
    actual_run_time = Column(Float)

    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Parameters
    parameters = Column(JSON, default=dict)

    # Relationships
    work_order = relationship('WorkOrder', back_populates='operations')

    __table_args__ = (
        Index('ix_operations_wo_seq', 'work_order_id', 'sequence'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': str(self.work_order_id),
            'operation_id': self.operation_id,
            'sequence': self.sequence,
            'operation_type': self.operation_type.value if self.operation_type else None,
            'name': self.name,
            'work_center_id': self.work_center_id,
            'machine_id': self.machine_id,
            'eligible_machines': self.eligible_machines or [],
            'setup_time': self.setup_time,
            'run_time': self.run_time,
            'status': self.status.value if self.status else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class Job(AuditedModel, SoftDeleteMixin):
    """Scheduled job instance (actual execution unit)."""

    __tablename__ = 'jobs'

    job_id = Column(String(50), unique=True, nullable=False, index=True)

    # References
    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'), nullable=False)
    operation_id = Column(UUID(as_uuid=True), ForeignKey('operations.id'))
    machine_id = Column(String(50), index=True)

    # Scheduling
    scheduled_start = Column(DateTime, index=True)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)

    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    priority_score = Column(Float, default=0)

    # Execution
    quantity_planned = Column(Integer, default=1)
    quantity_completed = Column(Integer, default=0)
    quantity_rejected = Column(Integer, default=0)

    # Worker assignment
    assigned_worker_id = Column(String(50))

    # G-code reference
    gcode_file = Column(String(500))
    gcode_hash = Column(String(64))

    # Runtime data
    runtime_data = Column(JSON, default=dict)

    # Relationships
    work_order = relationship('WorkOrder', back_populates='jobs')

    __table_args__ = (
        Index('ix_jobs_machine_status', 'machine_id', 'status'),
        Index('ix_jobs_scheduled', 'scheduled_start', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'id': str(self.id),
            'job_id': self.job_id,
            'work_order_id': str(self.work_order_id),
            'operation_id': str(self.operation_id) if self.operation_id else None,
            'machine_id': self.machine_id,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'actual_start': self.actual_start.isoformat() if self.actual_start else None,
            'actual_end': self.actual_end.isoformat() if self.actual_end else None,
            'status': self.status.value if self.status else None,
            'priority_score': self.priority_score,
            'quantity_planned': self.quantity_planned,
            'quantity_completed': self.quantity_completed,
            'quantity_rejected': self.quantity_rejected,
            'assigned_worker_id': self.assigned_worker_id,
        }
        # Include runtime_data fields (eligible_machines, operation info)
        if self.runtime_data:
            result['eligible_machines'] = self.runtime_data.get('eligible_machines', [])
            result['operation_name'] = self.runtime_data.get('operation_name')
            result['operation_type'] = self.runtime_data.get('operation_type')
        return result
