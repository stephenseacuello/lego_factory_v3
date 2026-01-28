"""
Equipment Services - Machine Integration

ISA-95 Level 2 Equipment Controllers for:
- 3D Printers (OctoPrint, Bambu Lab, Prusa Connect, Moonraker/Klipper)
- CNC Mills (GRBL over serial/network)
- Laser Engravers (GRBL laser mode)
- CNC Machines (GRBL, LinuxCNC)
- Conveyor Systems (Modbus TCP, EtherNet/IP)

Each controller provides:
- Connection management
- Real-time status monitoring
- Job submission and control
- OEE data collection
- Safety interlocks (where applicable)
"""

from .base_controller import (
    BaseEquipmentController,
    EquipmentState,
    EquipmentStatus,
    JobStatus,
    JobResult
)
from .printer_controller import PrinterController, PrinterProtocol
from .mill_controller import MillController, GrblState, GrblStatus
from .laser_controller import LaserController, LaserMode, LaserSafetyState
from .cnc_controller import (
    CNCController,
    CNCProtocol,
    GRBLCNCProtocol,
    LinuxCNCProtocol,
    CNCState,
    CNCStatus,
    CNCPosition,
    SpindleState,
    CoolantState,
    CoordinateSystem,
    ToolInfo,
    MachiningOperation,
    create_cnc_controller,
)
from .conveyor_controller import (
    ConveyorController,
    ConveyorProtocol,
    ModbusTCPProtocol,
    EtherNetIPProtocol,
    ConveyorState,
    ConveyorStatus,
    ConveyorDirection,
    ConveyorZone,
    ZoneState,
    TrackedProduct,
    ProductState,
    create_conveyor_controller,
)

__all__ = [
    # Base
    'BaseEquipmentController',
    'EquipmentState',
    'EquipmentStatus',
    'JobStatus',
    'JobResult',
    # Printer
    'PrinterController',
    'PrinterProtocol',
    # Mill
    'MillController',
    'GrblState',
    'GrblStatus',
    # Laser
    'LaserController',
    'LaserMode',
    'LaserSafetyState',
    # CNC
    'CNCController',
    'CNCProtocol',
    'GRBLCNCProtocol',
    'LinuxCNCProtocol',
    'CNCState',
    'CNCStatus',
    'CNCPosition',
    'SpindleState',
    'CoolantState',
    'CoordinateSystem',
    'ToolInfo',
    'MachiningOperation',
    'create_cnc_controller',
    # Conveyor
    'ConveyorController',
    'ConveyorProtocol',
    'ModbusTCPProtocol',
    'EtherNetIPProtocol',
    'ConveyorState',
    'ConveyorStatus',
    'ConveyorDirection',
    'ConveyorZone',
    'ZoneState',
    'TrackedProduct',
    'ProductState',
    'create_conveyor_controller',
]
