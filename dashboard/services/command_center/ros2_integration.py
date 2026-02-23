"""
V8 Command Center ROS2 Integration
===================================

Integrates the Command Center with ROS2 network for:
- Equipment state monitoring and control
- Lifecycle management
- Safety system integration
- Real-time sensor data
- Action execution via ROS2 actions

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import ROS2 bridge
try:
    from services.ros2_bridge import ros2_bridge, ROSLIBPY_AVAILABLE
except ImportError:
    ros2_bridge = None
    ROSLIBPY_AVAILABLE = False


class LifecycleState(Enum):
    """ROS2 lifecycle states"""
    UNKNOWN = "unknown"
    UNCONFIGURED = "unconfigured"
    INACTIVE = "inactive"
    ACTIVE = "active"
    FINALIZED = "finalized"


class EquipmentType(Enum):
    """Types of equipment in the system"""
    CNC_MACHINE = "cnc_machine"
    ROBOT_ARM = "robot_arm"
    CONVEYOR = "conveyor"
    AGV = "agv"
    INSPECTION_STATION = "inspection_station"
    EXTRUDER = "extruder"
    PRINTER_3D = "printer_3d"
    ASSEMBLY_STATION = "assembly_station"


@dataclass
class EquipmentState:
    """Current state of an equipment"""
    equipment_id: str
    equipment_type: EquipmentType
    lifecycle_state: LifecycleState
    operational_mode: str
    is_online: bool
    last_update: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type.value,
            "lifecycle_state": self.lifecycle_state.value,
            "operational_mode": self.operational_mode,
            "is_online": self.is_online,
            "last_update": self.last_update.isoformat(),
            "parameters": self.parameters,
            "alerts": self.alerts
        }


@dataclass
class CommandResult:
    """Result of a ROS2 command"""
    success: bool
    message: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None


class ROS2CommandCenter:
    """
    V8 Command Center ROS2 Integration.

    Provides unified interface for commanding equipment through ROS2:
    - Lifecycle management (configure, activate, deactivate, cleanup)
    - Parameter setting and retrieval
    - Emergency stop coordination
    - Action execution for complex operations
    """

    def __init__(self):
        self._equipment_states: Dict[str, EquipmentState] = {}
        self._subscribers: Dict[str, Any] = {}
        self._state_callbacks: List[Callable[[EquipmentState], None]] = []
        self._lock = threading.RLock()
        self._connected = False

        # ROS2 topic/service names
        self._topics = {
            "equipment_state": "/lego_mcp/equipment_state",
            "system_health": "/lego_mcp/system_health",
            "safety_status": "/lego_mcp/safety_status",
            "command_feedback": "/lego_mcp/command_feedback"
        }

        self._services = {
            "lifecycle_change": "/lego_mcp/lifecycle_manager/change_state",
            "get_state": "/lego_mcp/lifecycle_manager/get_state",
            "emergency_stop": "/lego_mcp/safety/emergency_stop",
            "reset_estop": "/lego_mcp/safety/reset_emergency_stop",
            "set_parameter": "/lego_mcp/param_manager/set_parameter",
            "get_parameter": "/lego_mcp/param_manager/get_parameter"
        }

        self._actions = {
            "execute_job": "/lego_mcp/job_executor",
            "move_robot": "/lego_mcp/robot_controller",
            "run_inspection": "/lego_mcp/quality_inspector"
        }

        logger.info("ROS2CommandCenter initialized")

    @property
    def is_ros2_available(self) -> bool:
        """Check if ROS2 connection is available."""
        return ROSLIBPY_AVAILABLE and ros2_bridge is not None

    async def connect(self) -> bool:
        """Connect to ROS2 network via rosbridge."""
        if not self.is_ros2_available:
            logger.warning("ROS2 bridge not available")
            return False

        try:
            if ros2_bridge.is_connected:
                self._connected = True
                await self._setup_subscribers()
                logger.info("Connected to ROS2 network")
                return True
            else:
                await ros2_bridge.connect_async()
                if ros2_bridge.is_connected:
                    self._connected = True
                    await self._setup_subscribers()
                    return True
        except Exception as e:
            logger.error(f"Failed to connect to ROS2: {e}")
            return False

        return False

    async def _setup_subscribers(self) -> None:
        """Setup ROS2 topic subscribers."""
        if not self._connected or not ros2_bridge:
            return

        try:
            # Subscribe to equipment state
            ros2_bridge.subscribe(
                self._topics["equipment_state"],
                "lego_mcp_msgs/msg/EquipmentState",
                self._on_equipment_state
            )

            # Subscribe to safety status
            ros2_bridge.subscribe(
                self._topics["safety_status"],
                "lego_mcp_msgs/msg/SafetyStatus",
                self._on_safety_status
            )

            logger.info("ROS2 subscribers setup complete")
        except Exception as e:
            logger.error(f"Failed to setup subscribers: {e}")

    def _on_equipment_state(self, msg: Dict[str, Any]) -> None:
        """Handle equipment state update from ROS2."""
        with self._lock:
            equipment_id = msg.get("equipment_id", "unknown")
            state = EquipmentState(
                equipment_id=equipment_id,
                equipment_type=EquipmentType(msg.get("equipment_type", "cnc_machine")),
                lifecycle_state=LifecycleState(msg.get("lifecycle_state", "unknown")),
                operational_mode=msg.get("operational_mode", "unknown"),
                is_online=msg.get("is_online", False),
                last_update=datetime.now(),
                parameters=msg.get("parameters", {}),
                alerts=msg.get("alerts", [])
            )
            self._equipment_states[equipment_id] = state

            # Notify callbacks
            for callback in self._state_callbacks:
                try:
                    callback(state)
                except Exception as e:
                    logger.error(f"State callback error: {e}")

    def _on_safety_status(self, msg: Dict[str, Any]) -> None:
        """Handle safety status update."""
        if msg.get("emergency_stop_active"):
            logger.warning("EMERGENCY STOP ACTIVE")
            # Could trigger alerts here

    # ==========================================
    # Lifecycle Management
    # ==========================================

    async def get_lifecycle_state(self, node_name: str) -> LifecycleState:
        """Get the lifecycle state of a managed node."""
        if not self._connected or not ros2_bridge:
            return LifecycleState.UNKNOWN

        try:
            result = await ros2_bridge.call_service_async(
                self._services["get_state"],
                "lifecycle_msgs/srv/GetState",
                {"node_name": node_name}
            )

            state_id = result.get("current_state", {}).get("id", 0)
            state_map = {
                0: LifecycleState.UNKNOWN,
                1: LifecycleState.UNCONFIGURED,
                2: LifecycleState.INACTIVE,
                3: LifecycleState.ACTIVE,
                4: LifecycleState.FINALIZED
            }
            return state_map.get(state_id, LifecycleState.UNKNOWN)
        except Exception as e:
            logger.error(f"Failed to get lifecycle state: {e}")
            return LifecycleState.UNKNOWN

    async def transition_lifecycle(
        self,
        node_name: str,
        transition: str
    ) -> CommandResult:
        """
        Request a lifecycle transition.

        Args:
            node_name: Name of the managed node
            transition: One of 'configure', 'activate', 'deactivate', 'cleanup'
        """
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        transition_ids = {
            "configure": 1,
            "cleanup": 2,
            "activate": 3,
            "deactivate": 4,
            "shutdown": 5
        }

        if transition not in transition_ids:
            return CommandResult(
                success=False,
                message=f"Invalid transition: {transition}",
                timestamp=datetime.now()
            )

        try:
            result = await ros2_bridge.call_service_async(
                self._services["lifecycle_change"],
                "lifecycle_msgs/srv/ChangeState",
                {
                    "node_name": node_name,
                    "transition": {"id": transition_ids[transition]}
                }
            )

            success = result.get("success", False)
            return CommandResult(
                success=success,
                message=f"Transition {transition} {'succeeded' if success else 'failed'}",
                timestamp=datetime.now(),
                data=result
            )
        except Exception as e:
            logger.error(f"Lifecycle transition failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    async def configure_node(self, node_name: str) -> CommandResult:
        """Configure a managed node."""
        return await self.transition_lifecycle(node_name, "configure")

    async def activate_node(self, node_name: str) -> CommandResult:
        """Activate a managed node."""
        return await self.transition_lifecycle(node_name, "activate")

    async def deactivate_node(self, node_name: str) -> CommandResult:
        """Deactivate a managed node."""
        return await self.transition_lifecycle(node_name, "deactivate")

    async def cleanup_node(self, node_name: str) -> CommandResult:
        """Cleanup a managed node."""
        return await self.transition_lifecycle(node_name, "cleanup")

    # ==========================================
    # Equipment Control
    # ==========================================

    async def get_equipment_state(self, equipment_id: str) -> Optional[EquipmentState]:
        """Get current state of an equipment."""
        with self._lock:
            return self._equipment_states.get(equipment_id)

    def get_all_equipment_states(self) -> Dict[str, EquipmentState]:
        """Get states of all known equipment."""
        with self._lock:
            return self._equipment_states.copy()

    async def set_equipment_parameter(
        self,
        equipment_id: str,
        parameter_name: str,
        value: Any
    ) -> CommandResult:
        """Set a parameter on equipment."""
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        try:
            result = await ros2_bridge.call_service_async(
                self._services["set_parameter"],
                "lego_mcp_msgs/srv/SetParameter",
                {
                    "equipment_id": equipment_id,
                    "parameter_name": parameter_name,
                    "value": str(value)
                }
            )

            return CommandResult(
                success=result.get("success", False),
                message=result.get("message", ""),
                timestamp=datetime.now(),
                data=result
            )
        except Exception as e:
            logger.error(f"Set parameter failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    async def get_equipment_parameter(
        self,
        equipment_id: str,
        parameter_name: str
    ) -> Optional[Any]:
        """Get a parameter from equipment."""
        if not self._connected or not ros2_bridge:
            return None

        try:
            result = await ros2_bridge.call_service_async(
                self._services["get_parameter"],
                "lego_mcp_msgs/srv/GetParameter",
                {
                    "equipment_id": equipment_id,
                    "parameter_name": parameter_name
                }
            )
            return result.get("value")
        except Exception as e:
            logger.error(f"Get parameter failed: {e}")
            return None

    # ==========================================
    # Safety System
    # ==========================================

    async def trigger_emergency_stop(self, reason: str = "") -> CommandResult:
        """Trigger emergency stop on all equipment."""
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        try:
            result = await ros2_bridge.call_service_async(
                self._services["emergency_stop"],
                "std_srvs/srv/Trigger",
                {}
            )

            logger.warning(f"Emergency stop triggered: {reason}")

            return CommandResult(
                success=result.get("success", False),
                message=f"E-Stop: {reason}",
                timestamp=datetime.now(),
                data={"reason": reason}
            )
        except Exception as e:
            logger.error(f"Emergency stop failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    async def reset_emergency_stop(self, authorized_by: str) -> CommandResult:
        """Reset emergency stop (requires authorization)."""
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        try:
            result = await ros2_bridge.call_service_async(
                self._services["reset_estop"],
                "lego_mcp_msgs/srv/ResetEmergencyStop",
                {"authorized_by": authorized_by}
            )

            logger.info(f"Emergency stop reset by: {authorized_by}")

            return CommandResult(
                success=result.get("success", False),
                message=result.get("message", "E-Stop reset"),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"E-Stop reset failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    # ==========================================
    # Action Execution
    # ==========================================

    async def execute_job_action(
        self,
        job_id: str,
        equipment_id: str,
        job_parameters: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict], None]] = None
    ) -> CommandResult:
        """Execute a manufacturing job via ROS2 action."""
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        try:
            goal_handle = await ros2_bridge.send_action_goal(
                self._actions["execute_job"],
                "lego_mcp_msgs/action/ExecuteJob",
                {
                    "job_id": job_id,
                    "equipment_id": equipment_id,
                    "parameters": job_parameters
                },
                feedback_callback=progress_callback
            )

            # Wait for result
            result = await ros2_bridge.wait_for_action_result(goal_handle)

            return CommandResult(
                success=result.get("success", False),
                message=result.get("message", ""),
                timestamp=datetime.now(),
                data=result
            )
        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    async def move_robot(
        self,
        robot_id: str,
        target_pose: Dict[str, float],
        speed: float = 1.0,
        progress_callback: Optional[Callable[[Dict], None]] = None
    ) -> CommandResult:
        """Move robot to target pose via ROS2 action."""
        if not self._connected or not ros2_bridge:
            return CommandResult(
                success=False,
                message="ROS2 not connected",
                timestamp=datetime.now()
            )

        try:
            goal_handle = await ros2_bridge.send_action_goal(
                self._actions["move_robot"],
                "lego_mcp_msgs/action/MoveRobot",
                {
                    "robot_id": robot_id,
                    "target_pose": target_pose,
                    "speed": speed
                },
                feedback_callback=progress_callback
            )

            result = await ros2_bridge.wait_for_action_result(goal_handle)

            return CommandResult(
                success=result.get("success", False),
                message=result.get("message", ""),
                timestamp=datetime.now(),
                data=result
            )
        except Exception as e:
            logger.error(f"Robot move failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                timestamp=datetime.now()
            )

    # ==========================================
    # State Callbacks
    # ==========================================

    def register_state_callback(
        self,
        callback: Callable[[EquipmentState], None]
    ) -> None:
        """Register callback for equipment state changes."""
        self._state_callbacks.append(callback)

    def unregister_state_callback(
        self,
        callback: Callable[[EquipmentState], None]
    ) -> None:
        """Unregister a state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    # ==========================================
    # Dashboard Integration
    # ==========================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data formatted for command center dashboard."""
        with self._lock:
            equipment_list = [
                state.to_dict() for state in self._equipment_states.values()
            ]

            # Count by state
            state_counts = {}
            for state in self._equipment_states.values():
                ls = state.lifecycle_state.value
                state_counts[ls] = state_counts.get(ls, 0) + 1

            # Count online/offline
            online_count = sum(
                1 for s in self._equipment_states.values() if s.is_online
            )

            return {
                "connected": self._connected,
                "equipment": equipment_list,
                "total_equipment": len(self._equipment_states),
                "online_count": online_count,
                "offline_count": len(self._equipment_states) - online_count,
                "state_counts": state_counts,
                "last_update": datetime.now().isoformat()
            }


# Singleton instance
_ros2_command_center: Optional[ROS2CommandCenter] = None


def get_ros2_command_center() -> ROS2CommandCenter:
    """Get singleton ROS2CommandCenter instance."""
    global _ros2_command_center
    if _ros2_command_center is None:
        _ros2_command_center = ROS2CommandCenter()
    return _ros2_command_center
