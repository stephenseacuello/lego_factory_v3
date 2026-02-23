"""
Manufacturing Models

ISA-95 Level 3 Manufacturing Operations Management models:
- WorkCenter: Machines and resources
- WorkOrder: Production orders
- WorkOrderOperation: Individual operations
- Routing: Manufacturing process definitions
- MaintenanceRecord: Equipment maintenance
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, Index, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base, IS_SQLITE

# Use JSON for SQLite, JSONB for PostgreSQL
JSON_TYPE = Text if IS_SQLITE else JSONB


class WorkCenterStatus(str, Enum):
    """Work center operational status."""
    AVAILABLE = 'AVAILABLE'
    IN_USE = 'IN_USE'
    MAINTENANCE = 'MAINTENANCE'
    OFFLINE = 'OFFLINE'
    SETUP = 'SETUP'


class WorkOrderStatus(str, Enum):
    """Work order lifecycle status."""
    PLANNED = 'PLANNED'
    RELEASED = 'RELEASED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    ON_HOLD = 'ON_HOLD'


class OperationStatus(str, Enum):
    """Work order operation status."""
    PENDING = 'PENDING'
    SETUP = 'SETUP'
    RUNNING = 'RUNNING'
    COMPLETE = 'COMPLETE'
    HOLD = 'HOLD'
    CANCELLED = 'CANCELLED'


class WorkCenter(Base):
    """
    Work Center - Manufacturing equipment and resources.

    Represents ISA-95 Level 2 equipment:
    - 3D Printers (FDM, SLA)
    - CNC Mills
    - Laser Engravers
    - Inspection Stations
    - Design Workstations
    """
    __tablename__ = 'work_centers'

    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)

    # Equipment details
    manufacturer = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100))

    # Capabilities (JSON: operations, materials, build volume, etc.)
    capabilities = Column(JSON_TYPE)

    # Status
    status = Column(String(50), default=WorkCenterStatus.AVAILABLE.value, index=True)
    location = Column(String(255))

    # Capacity and costing
    capacity_per_hour = Column(Float)
    hourly_rate = Column(Numeric(10, 2), default=0)
    efficiency_percent = Column(Float, default=85.0)  # Expected efficiency (OEE target)

    # Maintenance tracking
    maintenance_interval_hours = Column(Float)
    last_maintenance = Column(DateTime)
    total_runtime_hours = Column(Float, default=0)

    # Connection info (IP, port, protocol for OctoPrint, GRBL, etc.)
    connection_info = Column(JSON_TYPE)

    # Relationships
    operations = relationship('WorkOrderOperation', back_populates='work_center')
    routings = relationship('Routing', back_populates='work_center')
    oee_events = relationship('OEEEvent', back_populates='work_center')
    maintenance_records = relationship('MaintenanceRecord', back_populates='work_center')

    def __repr__(self):
        return f"<WorkCenter({self.code}: {self.name}, status={self.status})>"

    @property
    def next_maintenance(self) -> Optional[datetime]:
        """Calculate next maintenance date based on interval and last maintenance."""
        from datetime import timedelta
        if self.last_maintenance and self.maintenance_interval_hours:
            # Estimate based on 8 hours/day operation
            days = self.maintenance_interval_hours / 8
            return self.last_maintenance + timedelta(days=days)
        return None

    @classmethod
    def get_by_code(cls, session, code: str) -> Optional['WorkCenter']:
        """Find work center by code."""
        return session.query(cls).filter(cls.code == code).first()

    @classmethod
    def get_by_type(cls, session, wc_type: str) -> List['WorkCenter']:
        """Get all work centers of a specific type."""
        return session.query(cls).filter(cls.type == wc_type).all()

    @classmethod
    def get_available(cls, session, wc_type: str = None) -> List['WorkCenter']:
        """Get available work centers, optionally filtered by type."""
        query = session.query(cls).filter(cls.status == WorkCenterStatus.AVAILABLE.value)
        if wc_type:
            query = query.filter(cls.type == wc_type)
        return query.all()

    def is_maintenance_due(self) -> bool:
        """Check if maintenance is due based on runtime hours."""
        if not self.maintenance_interval_hours:
            return False
        hours_since_maintenance = self.total_runtime_hours
        if self.last_maintenance:
            # Would need to track runtime at last maintenance
            pass
        return hours_since_maintenance >= self.maintenance_interval_hours


class Routing(Base):
    """
    Manufacturing Routing - Process definition for producing a part.

    Defines the sequence of operations, work centers, and time standards
    required to manufacture a part.
    """
    __tablename__ = 'routings'

    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id', ondelete='CASCADE'), nullable=False, index=True)
    operation_sequence = Column(Integer, nullable=False)
    operation_code = Column(String(50), nullable=False)

    work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('work_centers.id'), index=True)

    description = Column(Text)

    # Time standards (minutes)
    setup_time_min = Column(Float, default=0)
    run_time_min = Column(Float, default=0)
    machine_time_min = Column(Float, default=0)
    labor_time_min = Column(Float, default=0)

    # Standard cost for this operation
    standard_cost = Column(Numeric(10, 4), default=0)

    # Work instructions and parameters
    instructions = Column(Text)
    tooling_required = Column(JSON_TYPE)
    parameters = Column(JSON_TYPE)  # Machine-specific settings

    is_active = Column(Boolean, default=True)

    # Relationships
    part = relationship('Part', back_populates='routings')
    work_center = relationship('WorkCenter', back_populates='routings')

    __table_args__ = (
        UniqueConstraint('part_id', 'operation_sequence', name='uq_routing_part_seq'),
    )

    def __repr__(self):
        return f"<Routing({self.part_id}, seq={self.operation_sequence}, op={self.operation_code})>"


class WorkOrder(Base):
    """
    Work Order - Production order for manufacturing parts.

    Represents an order to produce a quantity of a specific part.
    Contains one or more operations that must be completed.
    """
    __tablename__ = 'work_orders'

    work_order_number = Column(String(50), unique=True, nullable=False, index=True)

    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id'), nullable=False, index=True)

    # Quantities
    quantity_ordered = Column(Integer, nullable=False)
    quantity_completed = Column(Integer, default=0)
    quantity_scrapped = Column(Integer, default=0)

    # Status and priority
    status = Column(String(50), default=WorkOrderStatus.PLANNED.value, index=True)
    priority = Column(Integer, default=5)  # 1 = highest, 10 = lowest

    # Scheduling
    scheduled_start = Column(DateTime, index=True)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)

    # Hierarchy (for sub-assemblies)
    parent_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                             ForeignKey('work_orders.id'))

    # External references
    sales_order_ref = Column(String(100))
    customer_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                         ForeignKey('customers.id'))

    notes = Column(Text)
    created_by = Column(String(100))

    # Relationships
    part = relationship('Part')
    customer = relationship('Customer')
    parent_order = relationship('WorkOrder', remote_side='WorkOrder.id', backref='child_orders')
    operations = relationship('WorkOrderOperation', back_populates='work_order',
                              cascade='all, delete-orphan', order_by='WorkOrderOperation.operation_sequence')

    def __repr__(self):
        return f"<WorkOrder({self.work_order_number}, status={self.status}, qty={self.quantity_ordered})>"

    @classmethod
    def get_by_number(cls, session, wo_number: str) -> Optional['WorkOrder']:
        """Find work order by number."""
        return session.query(cls).filter(cls.work_order_number == wo_number).first()

    @classmethod
    def get_by_status(cls, session, status: str, limit: int = 100) -> List['WorkOrder']:
        """Get work orders by status."""
        return session.query(cls).filter(cls.status == status).limit(limit).all()

    @classmethod
    def get_queue(cls, session, work_center_id: str = None) -> List['WorkOrder']:
        """Get prioritized work queue."""
        query = session.query(cls).filter(
            cls.status.in_([WorkOrderStatus.RELEASED.value, WorkOrderStatus.IN_PROGRESS.value])
        ).order_by(cls.priority, cls.scheduled_start)

        if work_center_id:
            # Filter by work center through operations
            query = query.join(WorkOrderOperation).filter(
                WorkOrderOperation.work_center_id == work_center_id
            )

        return query.all()

    @property
    def quantity_remaining(self) -> int:
        """Calculate remaining quantity to produce."""
        return self.quantity_ordered - (self.quantity_completed or 0) - (self.quantity_scrapped or 0)

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.quantity_ordered == 0:
            return 100.0
        return (self.quantity_completed or 0) / self.quantity_ordered * 100

    def generate_operations_from_routing(self, session) -> List['WorkOrderOperation']:
        """Generate work order operations from part routing."""
        from .inventory import Part

        part = session.query(Part).filter(Part.id == self.part_id).first()
        if not part:
            return []

        operations = []
        for routing in sorted(part.routings, key=lambda r: r.operation_sequence):
            if not routing.is_active:
                continue

            op = WorkOrderOperation(
                work_order_id=self.id,
                routing_id=routing.id,
                operation_sequence=routing.operation_sequence,
                operation_code=routing.operation_code,
                work_center_id=routing.work_center_id,
                status=OperationStatus.PENDING.value
            )
            operations.append(op)
            session.add(op)

        return operations


class WorkOrderOperation(Base):
    """
    Work Order Operation - Individual production step.

    Tracks the execution of a single operation within a work order,
    including actual times, quantities, and quality results.
    """
    __tablename__ = 'work_order_operations'

    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    routing_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                        ForeignKey('routings.id'))

    operation_sequence = Column(Integer, nullable=False)
    operation_code = Column(String(50), nullable=False)

    work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('work_centers.id'), index=True)

    # Status
    status = Column(String(50), default=OperationStatus.PENDING.value, index=True)

    # Quantities
    quantity_completed = Column(Integer, default=0)
    quantity_scrapped = Column(Integer, default=0)

    # Scheduling
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)

    # Actual times (minutes)
    setup_time_actual_min = Column(Float)
    run_time_actual_min = Column(Float)

    # Execution details
    operator_id = Column(String(100))
    machine_program = Column(Text)  # G-code path, CAM file, etc.
    parameters_used = Column(JSON_TYPE)
    notes = Column(Text)

    # Relationships
    work_order = relationship('WorkOrder', back_populates='operations')
    routing = relationship('Routing')
    work_center = relationship('WorkCenter', back_populates='operations')

    def __repr__(self):
        return f"<WorkOrderOperation({self.work_order_id}, seq={self.operation_sequence}, status={self.status})>"

    def start(self, operator_id: str = None, work_center_id: str = None):
        """Start this operation."""
        self.status = OperationStatus.RUNNING.value
        self.actual_start = datetime.utcnow()
        if operator_id:
            self.operator_id = operator_id
        if work_center_id:
            self.work_center_id = work_center_id

    def complete(self, quantity_completed: int, quantity_scrapped: int = 0):
        """Complete this operation."""
        self.status = OperationStatus.COMPLETE.value
        self.actual_end = datetime.utcnow()
        self.quantity_completed = quantity_completed
        self.quantity_scrapped = quantity_scrapped

        # Calculate actual run time
        if self.actual_start:
            delta = self.actual_end - self.actual_start
            self.run_time_actual_min = delta.total_seconds() / 60

    @property
    def duration_minutes(self) -> Optional[float]:
        """Calculate operation duration in minutes."""
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return delta.total_seconds() / 60
        return None


class MaintenanceRecord(Base):
    """
    Maintenance Record - Equipment maintenance history.

    Tracks preventive, corrective, and predictive maintenance events
    for work centers.
    """
    __tablename__ = 'maintenance_records'

    work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('work_centers.id'), nullable=False, index=True)

    maintenance_type = Column(String(50), nullable=False)  # PREVENTIVE, CORRECTIVE, PREDICTIVE
    status = Column(String(50), default='SCHEDULED', index=True)  # SCHEDULED, IN_PROGRESS, COMPLETED, OVERDUE

    scheduled_date = Column(DateTime, index=True)
    completed_date = Column(DateTime)

    technician_id = Column(String(100))
    description = Column(Text)

    parts_used = Column(JSON_TYPE)
    labor_hours = Column(Float)
    cost = Column(Numeric(10, 2))

    next_maintenance_date = Column(DateTime)
    runtime_at_maintenance = Column(Float)

    notes = Column(Text)

    # Relationships
    work_center = relationship('WorkCenter', back_populates='maintenance_records')

    def __repr__(self):
        return f"<MaintenanceRecord({self.work_center_id}, type={self.maintenance_type}, status={self.status})>"
