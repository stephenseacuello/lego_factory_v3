"""
LEGO Factory v3 - Resource Models
==================================
Resource tracking for MESA-11 Resource Allocation & Status function.
Tracks machine status, tool inventory, and material lots.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel, SoftDeleteMixin


class MachineStatus(str, Enum):
    """Machine operational status."""
    IDLE = 'idle'
    RUNNING = 'running'
    DOWN = 'down'
    SETUP = 'setup'
    MAINTENANCE = 'maintenance'
    OFFLINE = 'offline'


class MaterialStatus(str, Enum):
    """Material lot status."""
    AVAILABLE = 'available'
    RESERVED = 'reserved'
    IN_USE = 'in_use'
    QUARANTINE = 'quarantine'
    CONSUMED = 'consumed'
    EXPIRED = 'expired'


class ToolStatus(str, Enum):
    """Tool status."""
    AVAILABLE = 'available'
    IN_USE = 'in_use'
    WORN = 'worn'
    BROKEN = 'broken'
    MAINTENANCE = 'maintenance'


class ResourceStatus(BaseModel):
    """
    Real-time machine resource status.
    One record per machine, updated frequently.
    """

    __tablename__ = 'resource_status'

    # Machine identification
    machine_id = Column(String(50), unique=True, nullable=False, index=True)
    machine_name = Column(String(200))

    # Status
    status = Column(SQLEnum(MachineStatus), default=MachineStatus.OFFLINE, nullable=False)
    previous_status = Column(SQLEnum(MachineStatus))
    status_changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Current work
    current_job_id = Column(String(50), index=True)
    current_work_order_id = Column(String(50))
    current_operation_name = Column(String(200))

    # Material loaded
    current_material_type = Column(String(50))
    current_material_lot = Column(String(50))

    # Utilization tracking
    utilization_1hr = Column(Float, default=0.0)  # % utilization in last hour
    utilization_8hr = Column(Float, default=0.0)  # % utilization in last 8 hours
    utilization_24hr = Column(Float, default=0.0)  # % utilization in last 24 hours

    # Connection status
    is_connected = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime(timezone=True))
    connection_error = Column(Text)

    # Position (for machines with axes)
    position_x = Column(Float)
    position_y = Column(Float)
    position_z = Column(Float)

    # Spindle/extruder state
    spindle_rpm = Column(Float)
    extruder_temp = Column(Float)
    bed_temp = Column(Float)

    # Job progress
    job_progress_pct = Column(Float, default=0.0)
    estimated_completion = Column(DateTime(timezone=True))

    # Error state
    has_alarm = Column(Boolean, default=False)
    alarm_code = Column(String(50))
    alarm_message = Column(Text)

    # Extra data
    extra_data = Column(JSON, default=dict)

    __table_args__ = (
        Index('ix_resource_status_machine_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'machine_name': self.machine_name,
            'status': self.status.value if self.status else None,
            'previous_status': self.previous_status.value if self.previous_status else None,
            'status_changed_at': self.status_changed_at.isoformat() if self.status_changed_at else None,
            'current_job_id': self.current_job_id,
            'current_work_order_id': self.current_work_order_id,
            'current_operation_name': self.current_operation_name,
            'current_material_type': self.current_material_type,
            'current_material_lot': self.current_material_lot,
            'utilization_1hr': self.utilization_1hr,
            'utilization_8hr': self.utilization_8hr,
            'utilization_24hr': self.utilization_24hr,
            'is_connected': self.is_connected,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'position': {
                'x': self.position_x,
                'y': self.position_y,
                'z': self.position_z,
            } if any([self.position_x, self.position_y, self.position_z]) else None,
            'spindle_rpm': self.spindle_rpm,
            'extruder_temp': self.extruder_temp,
            'bed_temp': self.bed_temp,
            'job_progress_pct': self.job_progress_pct,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'has_alarm': self.has_alarm,
            'alarm_code': self.alarm_code,
            'alarm_message': self.alarm_message,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ToolInventory(AuditedModel, SoftDeleteMixin):
    """
    Tool inventory tracking.
    Tracks tool wear, usage, and location.
    """

    __tablename__ = 'tool_inventory'

    # Tool identification
    tool_id = Column(String(50), unique=True, nullable=False, index=True)
    tool_number = Column(Integer)  # Tool slot number
    tool_type = Column(String(100), nullable=False)  # e.g., 'end_mill', 'drill', 'nozzle'
    tool_name = Column(String(200))
    description = Column(Text)

    # Tool specs
    diameter_mm = Column(Float)
    length_mm = Column(Float)
    flute_count = Column(Integer)
    material = Column(String(50))  # e.g., 'carbide', 'hss', 'brass'
    coating = Column(String(50))

    # Location
    machine_id = Column(String(50), index=True)  # Which machine it's on, null if in storage
    magazine_slot = Column(Integer)
    storage_location = Column(String(100))

    # Status
    status = Column(SQLEnum(ToolStatus), default=ToolStatus.AVAILABLE, nullable=False)

    # Wear tracking
    wear_percent = Column(Float, default=0.0)  # 0-100%
    remaining_life_mins = Column(Float)  # Estimated remaining cutting time
    total_cutting_time_mins = Column(Float, default=0.0)
    cut_count = Column(Integer, default=0)

    # Life expectancy
    expected_life_mins = Column(Float)  # Expected total life
    wear_rate_per_min = Column(Float)  # Calculated wear rate

    # Installation tracking
    installed_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))

    # Calibration
    length_offset = Column(Float, default=0.0)
    diameter_offset = Column(Float, default=0.0)
    last_calibrated_at = Column(DateTime(timezone=True))

    # Cost tracking
    purchase_cost = Column(Numeric(10, 2))
    cost_per_minute = Column(Numeric(10, 4))

    # Notes
    notes = Column(Text)
    extra_data = Column(JSON, default=dict)

    __table_args__ = (
        Index('ix_tool_inventory_machine', 'machine_id', 'status'),
        Index('ix_tool_inventory_type', 'tool_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'tool_id': self.tool_id,
            'tool_number': self.tool_number,
            'tool_type': self.tool_type,
            'tool_name': self.tool_name,
            'description': self.description,
            'diameter_mm': self.diameter_mm,
            'length_mm': self.length_mm,
            'machine_id': self.machine_id,
            'magazine_slot': self.magazine_slot,
            'storage_location': self.storage_location,
            'status': self.status.value if self.status else None,
            'wear_percent': self.wear_percent,
            'remaining_life_mins': self.remaining_life_mins,
            'total_cutting_time_mins': self.total_cutting_time_mins,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MaterialLot(AuditedModel, SoftDeleteMixin):
    """
    Material lot tracking for inventory and traceability.
    """

    __tablename__ = 'material_lots'

    # Lot identification
    lot_number = Column(String(50), unique=True, nullable=False, index=True)
    material_type = Column(String(50), nullable=False, index=True)  # e.g., 'PLA', 'ABS', 'ALU-6061'
    material_code = Column(String(50))  # Internal material code
    material_name = Column(String(200))
    description = Column(Text)

    # Material properties
    material_category = Column(String(50))  # 'filament', 'resin', 'metal', 'sheet'
    color = Column(String(50))
    color_hex = Column(String(7))
    grade = Column(String(50))

    # Quantities
    quantity_received = Column(Float, nullable=False)
    quantity_available = Column(Float, nullable=False)
    quantity_reserved = Column(Float, default=0.0)
    quantity_consumed = Column(Float, default=0.0)
    unit_of_measure = Column(String(20), default='g')  # g, kg, mm, m, pcs

    # Location
    location = Column(String(100))
    bin_number = Column(String(50))

    # Status
    status = Column(SQLEnum(MaterialStatus), default=MaterialStatus.AVAILABLE, nullable=False)

    # Supplier info
    supplier = Column(String(200))
    supplier_lot = Column(String(100))
    purchase_order = Column(String(50))

    # Dates
    received_date = Column(DateTime(timezone=True))
    manufacture_date = Column(DateTime(timezone=True))
    expiry_date = Column(DateTime(timezone=True))
    opened_date = Column(DateTime(timezone=True))

    # Quality
    certificate_of_analysis = Column(String(500))  # File path or URL
    inspection_status = Column(String(50))  # 'pending', 'passed', 'failed'
    quality_notes = Column(Text)

    # Cost
    cost_per_unit = Column(Numeric(10, 4))
    total_cost = Column(Numeric(10, 2))

    # Filament specific
    spool_weight_g = Column(Float)  # Spool only weight
    filament_diameter_mm = Column(Float)
    print_temp_min = Column(Float)
    print_temp_max = Column(Float)
    bed_temp_min = Column(Float)
    bed_temp_max = Column(Float)

    # Metal specific
    thickness_mm = Column(Float)
    width_mm = Column(Float)
    length_mm = Column(Float)
    hardness = Column(String(20))

    # Notes
    notes = Column(Text)
    extra_data = Column(JSON, default=dict)

    __table_args__ = (
        Index('ix_material_lots_type_status', 'material_type', 'status'),
        Index('ix_material_lots_location', 'location'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'lot_number': self.lot_number,
            'material_type': self.material_type,
            'material_code': self.material_code,
            'material_name': self.material_name,
            'material_category': self.material_category,
            'color': self.color,
            'quantity_received': self.quantity_received,
            'quantity_available': self.quantity_available,
            'quantity_reserved': self.quantity_reserved,
            'quantity_consumed': self.quantity_consumed,
            'unit_of_measure': self.unit_of_measure,
            'location': self.location,
            'status': self.status.value if self.status else None,
            'supplier': self.supplier,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'cost_per_unit': float(self.cost_per_unit) if self.cost_per_unit else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_low_stock(self) -> bool:
        """Check if lot is low on stock (less than 10% remaining)."""
        if self.quantity_received and self.quantity_received > 0:
            return (self.quantity_available / self.quantity_received) < 0.10
        return False

    @property
    def is_expired(self) -> bool:
        """Check if material has expired."""
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False


class MaterialReservation(BaseModel):
    """
    Material reservation for jobs.
    Links material lots to jobs with reserved quantities.
    """

    __tablename__ = 'material_reservations'

    # References
    lot_id = Column(UUID(as_uuid=True), ForeignKey('material_lots.id'), nullable=False)
    job_id = Column(String(50), nullable=False, index=True)
    work_order_id = Column(String(50), index=True)

    # Quantities
    quantity_reserved = Column(Float, nullable=False)
    quantity_consumed = Column(Float, default=0.0)
    unit_of_measure = Column(String(20))

    # Status
    status = Column(String(20), default='active')  # active, consumed, released

    # Timing
    reserved_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    consumed_at = Column(DateTime(timezone=True))
    released_at = Column(DateTime(timezone=True))

    # Audit
    reserved_by = Column(String(100))
    notes = Column(Text)

    # Relationships
    lot = relationship('MaterialLot', backref='reservations')

    __table_args__ = (
        Index('ix_material_reservations_job', 'job_id'),
        Index('ix_material_reservations_lot', 'lot_id', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'lot_id': str(self.lot_id),
            'lot_number': self.lot.lot_number if self.lot else None,
            'job_id': self.job_id,
            'work_order_id': self.work_order_id,
            'quantity_reserved': self.quantity_reserved,
            'quantity_consumed': self.quantity_consumed,
            'status': self.status,
            'reserved_at': self.reserved_at.isoformat() if self.reserved_at else None,
        }
