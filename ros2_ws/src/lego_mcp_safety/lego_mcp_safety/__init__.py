"""
LEGO MCP Safety Package

Safety systems including:
- Emergency stop management (ISO 10218 compliant)
- Joint limit monitoring
- Collision detection
- Watchdog timers for system health

LEGO MCP Manufacturing System v7.0
"""

from .safety_node import SafetyNode, SafetyState
from .joint_monitor import JointMonitorNode, JointLimits, ViolationType

__version__ = "7.0.0"

__all__ = [
    'SafetyNode',
    'SafetyState',
    'JointMonitorNode',
    'JointLimits',
    'ViolationType',
]
