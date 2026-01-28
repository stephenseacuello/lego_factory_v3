"""
LEGO Factory v3 - Machine Models
=================================
Machine and controller models for SCADA system.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, ForeignKey, Index, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import BaseModel, AuditedModel


class MachineType(PyEnum):
    """Types of machines supported."""
    CNC_MILL = "cnc_mill"
    CNC_LATHE = "cnc_lathe"
    PRINTER_3D = "printer_3d"
    LASER_CUTTER = "laser_cutter"
    ROBOT_ARM = "robot_arm"
    CONVEYOR = "conveyor"
    ASSEMBLY_STATION = "assembly_station"


class ControllerType(PyEnum):
    """Types of machine controllers."""
    TINYG = "tinyg"
    GRBL = "grbl"
    MARLIN = "marlin"
    LINUXCNC = "linuxcnc"
    MACH3 = "mach3"
    FANUC = "fanuc"
    SIEMENS = "siemens"
    ROS2 = "ros2"
    BAMBU = "bambu"
    SIMULATION = "simulation"


class MachineState(PyEnum):
    """Machine operational states."""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    HOLD = "hold"
    HOMING = "homing"
    ALARM = "alarm"
    ERROR = "error"
    ESTOP = "estop"
    MAINTENANCE = "maintenance"


class ConnectionType(PyEnum):
    """Connection types for machine controllers."""
    SERIAL = "serial"
    ETHERNET = "ethernet"
    USB = "usb"
    MQTT = "mqtt"
    ROS2 = "ros2"
    SIMULATION = "simulation"


class Machine(AuditedModel):
    """
    Machine definition.

    Represents a physical or virtual machine in the factory.
    """
    __tablename__ = 'machines'

    # Identification
    machine_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    machine_type: Mapped[MachineType] = mapped_column(Enum(MachineType), nullable=False)
    controller_type: Mapped[ControllerType] = mapped_column(Enum(ControllerType), nullable=False)

    # Location (index defined in __table_args__)
    area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cell: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # x, y, z coordinates

    # Connection
    connection_type: Mapped[ConnectionType] = mapped_column(Enum(ConnectionType), nullable=False)
    connection_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # port, baud, ip, etc.

    # Capabilities
    axes: Mapped[int] = mapped_column(Integer, default=3)
    has_spindle: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tool_changer: Mapped[bool] = mapped_column(Boolean, default=False)
    has_coolant: Mapped[bool] = mapped_column(Boolean, default=False)
    max_feed_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_spindle_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Work envelope
    work_envelope_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    work_envelope_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    work_envelope_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Current state
    current_state: Mapped[MachineState] = mapped_column(Enum(MachineState), default=MachineState.DISCONNECTED)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Position
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)
    position_z: Mapped[float] = mapped_column(Float, default=0.0)
    position_a: Mapped[float] = mapped_column(Float, default=0.0)
    position_b: Mapped[float] = mapped_column(Float, default=0.0)
    position_c: Mapped[float] = mapped_column(Float, default=0.0)

    # Spindle
    spindle_rpm: Mapped[float] = mapped_column(Float, default=0.0)
    spindle_load: Mapped[float] = mapped_column(Float, default=0.0)

    # Feed
    feed_rate: Mapped[float] = mapped_column(Float, default=0.0)
    feed_override: Mapped[float] = mapped_column(Float, default=100.0)
    spindle_override: Mapped[float] = mapped_column(Float, default=100.0)

    # Program
    current_program: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    current_line: Mapped[int] = mapped_column(Integer, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Tool
    current_tool: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    coolant_on: Mapped[bool] = mapped_column(Boolean, default=False)
    mist_on: Mapped[bool] = mapped_column(Boolean, default=False)

    # Error info
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statistics
    total_runtime_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_parts_produced: Mapped[int] = mapped_column(Integer, default=0)

    # Maintenance
    next_maintenance: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    maintenance_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enable/disable
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index('ix_machines_type', 'machine_type'),
        Index('ix_machines_state', 'current_state'),
        Index('ix_machines_area', 'area'),
    )

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'name': self.name,
            'description': self.description,
            'machine_type': self.machine_type.value,
            'controller_type': self.controller_type.value,
            'current_state': self.current_state.value,
            'is_connected': self.is_connected,
            'position': {
                'x': self.position_x,
                'y': self.position_y,
                'z': self.position_z,
                'a': self.position_a,
                'b': self.position_b,
                'c': self.position_c,
            },
            'spindle_rpm': self.spindle_rpm,
            'feed_rate': self.feed_rate,
            'current_program': self.current_program,
            'progress_pct': self.progress_pct,
            'enabled': self.enabled,
        }


class MachineEvent(BaseModel):
    """Log of machine events and state changes."""
    __tablename__ = 'machine_events'

    machine_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('machines.id'), nullable=False)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # connect, disconnect, start, stop, alarm, etc.
    previous_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_state: Mapped[str] = mapped_column(String(50), nullable=False)

    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    operator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_machine_events_machine', 'machine_id'),
        Index('ix_machine_events_type', 'event_type'),
    )
