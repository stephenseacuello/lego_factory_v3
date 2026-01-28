"""
LEGO MCP Orchestrator Package
Main coordination node for factory cell operations.

Components:
- orchestrator_node: Main job dispatcher and coordination
- twin_sync: Digital Twin synchronization via ROS2
- ar_publisher: AR/VR visualization markers
- failure_detector: Equipment failure detection
- recovery_engine: Automatic failure recovery
- reschedule_service: Dynamic rescheduling after failures
- moveit_assembly: MoveIt2-based LEGO assembly planning
- equipment_monitor: Unified equipment status monitoring

LEGO MCP Manufacturing System v7.0
"""

__version__ = "7.0.0"

from .orchestrator_node import OrchestratorNode
from .twin_sync import TwinSyncNode
from .ar_publisher import ARPublisherNode
from .failure_detector import FailureDetectorNode
from .recovery_engine import RecoveryEngineNode
from .reschedule_service import RescheduleServiceNode
from .moveit_assembly import MoveItAssemblyPlanner
from .equipment_monitor import EquipmentMonitorNode

__all__ = [
    'OrchestratorNode',
    'TwinSyncNode',
    'ARPublisherNode',
    'FailureDetectorNode',
    'RecoveryEngineNode',
    'RescheduleServiceNode',
    'MoveItAssemblyPlanner',
    'EquipmentMonitorNode',
]
