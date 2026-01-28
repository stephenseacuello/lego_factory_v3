"""
LEGO MCP AGV Package

Fleet management and control for Alvik AGVs with ESP32 and micro-ROS
for material transport in the LEGO manufacturing factory cell.

Components:
- alvik_driver: ROS2 driver for individual Alvik AGVs
- fleet_manager: Coordinates multiple AGVs
- task_allocator: Intelligent task assignment
- agv_simulator: Simulation for testing

LEGO MCP Manufacturing System v7.0
"""

__version__ = "7.0.0"

from .alvik_driver import AlvikDriverNode, AlvikState, AlvikStatus
from .fleet_manager import FleetManagerNode, TaskType, TaskPriority, TransportTask
from .task_allocator import TaskAllocatorNode, AllocationStrategy
from .agv_simulator import AlvikSimulatorNode

__all__ = [
    'AlvikDriverNode',
    'AlvikState',
    'AlvikStatus',
    'FleetManagerNode',
    'TaskType',
    'TaskPriority',
    'TransportTask',
    'TaskAllocatorNode',
    'AllocationStrategy',
    'AlvikSimulatorNode',
]
