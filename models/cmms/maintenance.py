"""
LEGO Factory v3 - CMMS Maintenance Models
==========================================
Maintenance work orders, PM schedules, and task templates.
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


class WorkOrderType(str, Enum):
    """Maintenance work order type."""
    PREVENTIVE = 'preventive'
    CORRECTIVE = 'corrective'
    PREDICTIVE = 'predictive'
    EMERGENCY = 'emergency'
    PROJECT = 'project'
    INSPECTION = 'inspection'
    CALIBRATION = 'calibration'


class WorkOrderStatus(str, Enum):
    """Maintenance work order status."""
    DRAFT = 'draft'
    APPROVED = 'approved'
    WAITING_PARTS = 'waiting_parts'
    WAITING_SCHEDULE = 'waiting_schedule'
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    ON_HOLD = 'on_hold'
    COMPLETED = 'completed'
    CLOSED = 'closed'
    CANCELLED = 'cancelled'


class WorkOrderPriority(str, Enum):
    """Maintenance work order priority."""
    EMERGENCY = 'emergency'
    URGENT = 'urgent'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class PMTriggerType(str, Enum):
    """PM schedule trigger type."""
    CALENDAR = 'calendar'       # Time-based (every X days)
    METER = 'meter'             # Usage-based (every X hours)
    CONDITION = 'condition'     # Condition-based


class TaskTemplate(AuditedModel):
    """Reusable maintenance task template."""

    __tablename__ = 'task_templates'

    template_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Task details
    instructions = Column(Text)
    estimated_hours = Column(Float)
    skill_required = Column(String(100))

    # Safety
    safety_requirements = Column(JSON, default=list)
    lockout_required = Column(Boolean, default=False)

    # Tools and materials
    tools_required = Column(JSON, default=list)
    materials_required = Column(JSON, default=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'instructions': self.instructions,
            'estimated_hours': self.estimated_hours,
            'skill_required': self.skill_required,
            'lockout_required': self.lockout_required,
        }


class PMSchedule(AuditedModel):
    """Preventive Maintenance schedule."""

    __tablename__ = 'pm_schedules'

    pm_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Asset linkage
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), nullable=False)
    asset_class_id = Column(UUID(as_uuid=True), ForeignKey('asset_classes.id'))

    # Status
    is_active = Column(Boolean, default=True)

    # Trigger configuration
    trigger_type = Column(SQLEnum(PMTriggerType), default=PMTriggerType.CALENDAR)

    # Calendar-based triggers
    frequency_days = Column(Integer)  # Every N days
    day_of_week = Column(Integer)     # 0=Mon, 6=Sun
    day_of_month = Column(Integer)    # 1-31
    month_of_year = Column(Integer)   # 1-12

    # Meter-based triggers
    meter_id = Column(UUID(as_uuid=True), ForeignKey('meters.id'))
    meter_interval = Column(Float)    # Trigger every X units

    # Condition-based triggers (links to alarm or tag)
    condition_tag_id = Column(String(50))
    condition_threshold = Column(Float)

    # Lead time and window
    lead_time_days = Column(Integer, default=7)  # Days before due to generate WO
    work_window_days = Column(Integer, default=7)  # Days after due still acceptable

    # Schedule tracking
    last_completed = Column(DateTime)
    last_meter_reading = Column(Float)
    next_due_date = Column(Date)
    next_due_meter = Column(Float)

    # Work order generation
    priority = Column(SQLEnum(WorkOrderPriority), default=WorkOrderPriority.MEDIUM)
    estimated_hours = Column(Float)
    estimated_cost = Column(Float)
    work_center_id = Column(String(50))

    # Task template
    task_template_id = Column(UUID(as_uuid=True), ForeignKey('task_templates.id'))

    # Instructions
    instructions = Column(Text)
    checklist = Column(JSON, default=list)

    # Spares required
    spares_required = Column(JSON, default=list)

    # Relationships
    asset = relationship('Asset')
    meter = relationship('Meter')
    task_template = relationship('TaskTemplate')
    work_orders = relationship('MaintenanceWorkOrder', back_populates='pm_schedule')

    __table_args__ = (
        Index('ix_pm_asset', 'asset_id'),
        Index('ix_pm_next_due', 'next_due_date'),
    )

    def calculate_next_due(self) -> Optional[date]:
        """Calculate next due date based on trigger type."""
        if self.trigger_type == PMTriggerType.CALENDAR:
            if self.last_completed and self.frequency_days:
                base = self.last_completed.date() if isinstance(self.last_completed, datetime) else self.last_completed
                return base + timedelta(days=self.frequency_days)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'pm_id': self.pm_id,
            'name': self.name,
            'asset_id': str(self.asset_id),
            'is_active': self.is_active,
            'trigger_type': self.trigger_type.value if self.trigger_type else None,
            'frequency_days': self.frequency_days,
            'meter_interval': self.meter_interval,
            'next_due_date': self.next_due_date.isoformat() if self.next_due_date else None,
            'last_completed': self.last_completed.isoformat() if self.last_completed else None,
            'priority': self.priority.value if self.priority else None,
            'estimated_hours': self.estimated_hours,
        }


class MaintenanceWorkOrder(AuditedModel):
    """Maintenance Work Order."""

    __tablename__ = 'maintenance_work_orders'

    wo_number = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Classification
    wo_type = Column(SQLEnum(WorkOrderType), default=WorkOrderType.CORRECTIVE)
    status = Column(SQLEnum(WorkOrderStatus), default=WorkOrderStatus.DRAFT)
    priority = Column(SQLEnum(WorkOrderPriority), default=WorkOrderPriority.MEDIUM)

    # Asset
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id'), nullable=False)

    # PM linkage (if generated from PM schedule)
    pm_schedule_id = Column(UUID(as_uuid=True), ForeignKey('pm_schedules.id'))

    # Problem description (for corrective maintenance)
    problem_code = Column(String(50))
    problem_description = Column(Text)
    failure_code = Column(String(50))

    # Dates
    reported_date = Column(DateTime, default=datetime.utcnow)
    target_start = Column(DateTime)
    target_completion = Column(DateTime)
    actual_start = Column(DateTime)
    actual_completion = Column(DateTime)

    # Assignment
    assigned_to = Column(String(50))
    work_center_id = Column(String(50))

    # Estimates vs Actuals
    estimated_hours = Column(Float)
    actual_hours = Column(Float, default=0)
    estimated_cost = Column(Float)
    actual_labor_cost = Column(Float, default=0)
    actual_material_cost = Column(Float, default=0)

    # Downtime
    downtime_start = Column(DateTime)
    downtime_end = Column(DateTime)
    downtime_hours = Column(Float)

    # Instructions and completion
    instructions = Column(Text)
    completion_notes = Column(Text)
    root_cause = Column(Text)
    corrective_action = Column(Text)

    # Approval workflow
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(String(50))
    approved_date = Column(DateTime)

    # Relationships
    asset = relationship('Asset')
    pm_schedule = relationship('PMSchedule', back_populates='work_orders')
    tasks = relationship('WorkOrderTask', back_populates='work_order', cascade='all, delete-orphan')
    labor = relationship('WorkOrderLabor', back_populates='work_order', cascade='all, delete-orphan')
    materials = relationship('WorkOrderMaterial', back_populates='work_order', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_mwo_status', 'status'),
        Index('ix_mwo_asset', 'asset_id'),
        Index('ix_mwo_assigned', 'assigned_to'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'wo_number': self.wo_number,
            'description': self.description,
            'wo_type': self.wo_type.value if self.wo_type else None,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'asset_id': str(self.asset_id),
            'assigned_to': self.assigned_to,
            'target_start': self.target_start.isoformat() if self.target_start else None,
            'target_completion': self.target_completion.isoformat() if self.target_completion else None,
            'actual_start': self.actual_start.isoformat() if self.actual_start else None,
            'actual_completion': self.actual_completion.isoformat() if self.actual_completion else None,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
        }


class WorkOrderTask(AuditedModel):
    """Individual task within a work order."""

    __tablename__ = 'work_order_tasks'

    work_order_id = Column(UUID(as_uuid=True), ForeignKey('maintenance_work_orders.id'), nullable=False)
    sequence = Column(Integer, default=10)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    instructions = Column(Text)

    # Status
    is_completed = Column(Boolean, default=False)
    completed_by = Column(String(50))
    completed_date = Column(DateTime)

    # Time
    estimated_minutes = Column(Integer)
    actual_minutes = Column(Integer)

    # Safety
    lockout_required = Column(Boolean, default=False)

    # Relationships
    work_order = relationship('MaintenanceWorkOrder', back_populates='tasks')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': str(self.work_order_id),
            'sequence': self.sequence,
            'name': self.name,
            'is_completed': self.is_completed,
            'estimated_minutes': self.estimated_minutes,
            'actual_minutes': self.actual_minutes,
        }


class WorkOrderLabor(AuditedModel):
    """Labor entry for a work order."""

    __tablename__ = 'work_order_labor'

    work_order_id = Column(UUID(as_uuid=True), ForeignKey('maintenance_work_orders.id'), nullable=False)
    worker_id = Column(String(50), nullable=False)
    craft = Column(String(100))

    # Time
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)

    # Cost
    hourly_rate = Column(Float)
    total_cost = Column(Float)

    notes = Column(Text)

    # Relationships
    work_order = relationship('MaintenanceWorkOrder', back_populates='labor')

    def calculate_cost(self):
        """Calculate total labor cost."""
        if self.hourly_rate:
            self.total_cost = (self.regular_hours or 0) * self.hourly_rate + \
                              (self.overtime_hours or 0) * self.hourly_rate * 1.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': str(self.work_order_id),
            'worker_id': self.worker_id,
            'regular_hours': self.regular_hours,
            'overtime_hours': self.overtime_hours,
            'total_cost': self.total_cost,
        }


class WorkOrderMaterial(AuditedModel):
    """Material/part used on a work order."""

    __tablename__ = 'work_order_materials'

    work_order_id = Column(UUID(as_uuid=True), ForeignKey('maintenance_work_orders.id'), nullable=False)
    spare_id = Column(UUID(as_uuid=True), ForeignKey('spares.id'))
    item_id = Column(String(50))  # ERP item reference
    description = Column(String(200), nullable=False)

    # Quantities
    quantity_required = Column(Float, default=1)
    quantity_used = Column(Float, default=0)

    # Cost
    unit_cost = Column(Float)
    total_cost = Column(Float)

    # Relationships
    work_order = relationship('MaintenanceWorkOrder', back_populates='materials')

    def calculate_cost(self):
        """Calculate total material cost."""
        if self.unit_cost and self.quantity_used:
            self.total_cost = self.unit_cost * self.quantity_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': str(self.work_order_id),
            'description': self.description,
            'quantity_required': self.quantity_required,
            'quantity_used': self.quantity_used,
            'total_cost': self.total_cost,
        }
