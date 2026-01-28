"""
LEGO Factory v3 - MES Scheduling Models
=======================================
Shifts, scheduling, and dispatch queue management.
"""

from datetime import datetime, date, time
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date, Time,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class ShiftType(str, Enum):
    """Types of work shifts."""
    DAY = 'day'
    EVENING = 'evening'
    NIGHT = 'night'
    ROTATING = 'rotating'
    FLEXIBLE = 'flexible'


class DispatchPriority(str, Enum):
    """Dispatch queue priorities."""
    CRITICAL = 'critical'
    HIGH = 'high'
    NORMAL = 'normal'
    LOW = 'low'
    HOLD = 'hold'


class DispatchStatus(str, Enum):
    """Dispatch queue item status."""
    QUEUED = 'queued'
    READY = 'ready'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    BLOCKED = 'blocked'
    CANCELLED = 'cancelled'


class Shift(BaseModel):
    """Work shift definition."""

    __tablename__ = 'shifts'

    shift_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    shift_type = Column(SQLEnum(ShiftType), default=ShiftType.DAY)

    # Timing
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    break_duration_mins = Column(Integer, default=30)

    # Schedule pattern
    days_of_week = Column(JSON, default=[1, 2, 3, 4, 5])  # 1=Monday, 7=Sunday
    is_overnight = Column(Boolean, default=False)

    # Capacity
    target_workers = Column(Integer)
    minimum_workers = Column(Integer)

    # Active status
    is_active = Column(Boolean, default=True)

    # Relationships
    assignments = relationship('ShiftAssignment', back_populates='shift')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'shift_code': self.shift_code,
            'name': self.name,
            'shift_type': self.shift_type.value if self.shift_type else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'days_of_week': self.days_of_week,
            'is_active': self.is_active,
        }


class ShiftAssignment(AuditedModel):
    """Worker assignment to shift."""

    __tablename__ = 'shift_assignments'

    worker_id = Column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False, index=True)
    shift_id = Column(UUID(as_uuid=True), ForeignKey('shifts.id'), nullable=False, index=True)

    # Assignment period
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)

    # Work center assignment
    work_center_id = Column(UUID(as_uuid=True), ForeignKey('machines.id'))
    work_area = Column(String(100))

    # Role during shift
    role = Column(String(100))  # lead, operator, assistant

    # Status
    is_active = Column(Boolean, default=True)

    # Notes
    notes = Column(Text)

    # Relationships
    shift = relationship('Shift', back_populates='assignments')

    __table_args__ = (
        Index('ix_shift_assignments_worker_date', 'worker_id', 'effective_date'),
        Index('ix_shift_assignments_shift_date', 'shift_id', 'effective_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'worker_id': str(self.worker_id),
            'shift_id': str(self.shift_id),
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'work_area': self.work_area,
            'role': self.role,
            'is_active': self.is_active,
        }


class DispatchQueue(AuditedModel):
    """
    Production dispatch queue.

    Manages the priority and sequencing of work orders for production.
    """

    __tablename__ = 'dispatch_queue'

    # Work order reference
    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'), nullable=False, index=True)
    operation_id = Column(UUID(as_uuid=True), ForeignKey('operations.id'))

    # Scheduling
    machine_id = Column(UUID(as_uuid=True), ForeignKey('machines.id'), index=True)
    work_center = Column(String(100))

    # Priority and sequencing
    priority = Column(SQLEnum(DispatchPriority), default=DispatchPriority.NORMAL, index=True)
    sequence_number = Column(Integer, index=True)
    priority_score = Column(Float)  # Calculated priority score

    # Timing
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)

    # Status
    status = Column(SQLEnum(DispatchStatus), default=DispatchStatus.QUEUED, index=True)
    hold_reason = Column(Text)

    # Dependencies
    depends_on = Column(JSON, default=list)  # List of prerequisite dispatch IDs
    predecessors_complete = Column(Boolean, default=True)

    # Resource requirements
    required_skills = Column(JSON, default=list)
    required_tools = Column(JSON, default=list)
    material_ready = Column(Boolean, default=False)

    # Assignment
    assigned_worker_id = Column(UUID(as_uuid=True), ForeignKey('workers.id'))

    __table_args__ = (
        Index('ix_dispatch_queue_machine_status', 'machine_id', 'status'),
        Index('ix_dispatch_queue_priority_sequence', 'priority', 'sequence_number'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_order_id': str(self.work_order_id),
            'operation_id': str(self.operation_id) if self.operation_id else None,
            'machine_id': str(self.machine_id) if self.machine_id else None,
            'priority': self.priority.value if self.priority else None,
            'sequence_number': self.sequence_number,
            'status': self.status.value if self.status else None,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'material_ready': self.material_ready,
        }


class MachineAvailabilityType(str, Enum):
    """Types of machine availability windows."""
    OPERATING = 'operating'       # Normal operating hours
    MAINTENANCE = 'maintenance'   # Scheduled maintenance (unavailable)
    DOWNTIME = 'downtime'         # Unplanned downtime (unavailable)
    RESTRICTED = 'restricted'     # Reduced capacity


class MachineAvailability(AuditedModel):
    """
    Machine availability windows for scheduling.

    Tracks operating hours, maintenance windows, and downtime
    for constraint-based scheduling.
    """

    __tablename__ = 'machine_availability'

    machine_id = Column(String(50), nullable=False, index=True)

    # Availability type
    availability_type = Column(SQLEnum(MachineAvailabilityType), nullable=False)

    # Time window
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)

    # Recurring schedule (if applicable)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50))  # 'daily', 'weekly', 'monthly'
    days_of_week = Column(JSON)  # [1,2,3,4,5] for Mon-Fri

    # Capacity (for restricted windows)
    capacity_percent = Column(Integer, default=100)  # 0-100

    # Reason/notes
    reason = Column(String(200))
    notes = Column(Text)

    # Status
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('ix_machine_availability_machine_dates', 'machine_id', 'start_datetime', 'end_datetime'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'availability_type': self.availability_type.value if self.availability_type else None,
            'start_datetime': self.start_datetime.isoformat() if self.start_datetime else None,
            'end_datetime': self.end_datetime.isoformat() if self.end_datetime else None,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'days_of_week': self.days_of_week,
            'capacity_percent': self.capacity_percent,
            'reason': self.reason,
            'is_active': self.is_active,
        }


class ProductionSchedule(AuditedModel):
    """
    Production schedule for a planning period.

    High-level schedule for capacity planning.
    """

    __tablename__ = 'production_schedules'

    schedule_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Status
    status = Column(String(50), default='draft')  # draft, published, frozen, closed

    # Capacity planning
    available_hours = Column(Float)
    planned_hours = Column(Float)
    utilization_percent = Column(Float)

    # Schedule data
    schedule_data = Column(JSON)  # Detailed schedule breakdown

    # Approval
    approved_by = Column(String(100))
    approved_at = Column(DateTime)

    __table_args__ = (
        Index('ix_production_schedules_dates', 'start_date', 'end_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'schedule_id': self.schedule_id,
            'name': self.name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'utilization_percent': self.utilization_percent,
        }
