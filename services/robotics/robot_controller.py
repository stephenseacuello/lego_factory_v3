"""
LEGO Factory v3 - Robot Controllers
====================================
Controllers for Niryo Ned2 and xArm Lite 6 robot arms via ROS2.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Tuple

from .ros2_bridge import ROS2Bridge, get_ros2_bridge, ConnectionState

logger = logging.getLogger(__name__)


class RobotState(Enum):
    DISCONNECTED = 'disconnected'
    IDLE = 'idle'
    MOVING = 'moving'
    GRIPPING = 'gripping'
    ERROR = 'error'
    ESTOPPED = 'estopped'


@dataclass
class Position:
    """Cartesian position"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Orientation:
    """Orientation as quaternion"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


@dataclass
class Pose:
    """6DOF pose"""
    position: Position = field(default_factory=Position)
    orientation: Orientation = field(default_factory=Orientation)


@dataclass
class RobotStatus:
    """Robot arm status"""
    state: RobotState = RobotState.DISCONNECTED
    joint_positions: List[float] = field(default_factory=lambda: [0.0] * 6)
    end_effector_pose: Pose = field(default_factory=Pose)
    gripper_open: bool = True
    gripper_position: float = 1.0  # 0.0 = closed, 1.0 = open
    error_code: str = ""
    error_message: str = ""


class RobotController(ABC):
    """
    Abstract base class for robot arm controllers.
    """
    
    def __init__(self, robot_id: str, config: Dict[str, Any]):
        self.robot_id = robot_id
        self.config = config
        self.status = RobotStatus()
        
        self._bridge: Optional[ROS2Bridge] = None
        self._status_callbacks: List[Callable[[RobotStatus], None]] = []
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._bridge and self._bridge.is_connected
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the robot."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the robot."""
        pass
    
    @abstractmethod
    def home(self) -> bool:
        """Move robot to home position."""
        pass
    
    @abstractmethod
    def move_joints(self, joints: List[float], velocity: float = 0.5) -> bool:
        """Move to joint positions."""
        pass
    
    @abstractmethod
    def move_pose(self, pose: Pose, velocity: float = 0.5) -> bool:
        """Move to cartesian pose."""
        pass
    
    @abstractmethod
    def open_gripper(self) -> bool:
        """Open the gripper."""
        pass
    
    @abstractmethod
    def close_gripper(self) -> bool:
        """Close the gripper."""
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Emergency stop."""
        pass
    
    def pick_and_place(self, pick_pose: Pose, place_pose: Pose, 
                       approach_height: float = 0.05, velocity: float = 0.3) -> bool:
        """Execute a pick and place cycle."""
        try:
            # Approach pick position
            approach_pick = Pose(
                position=Position(pick_pose.position.x, pick_pose.position.y, 
                                  pick_pose.position.z + approach_height),
                orientation=pick_pose.orientation
            )
            
            if not self.open_gripper():
                return False
            if not self.move_pose(approach_pick, velocity):
                return False
            if not self.move_pose(pick_pose, velocity * 0.5):
                return False
            if not self.close_gripper():
                return False
            time.sleep(0.3)  # Wait for grip
            if not self.move_pose(approach_pick, velocity * 0.5):
                return False
            
            # Approach place position
            approach_place = Pose(
                position=Position(place_pose.position.x, place_pose.position.y,
                                  place_pose.position.z + approach_height),
                orientation=place_pose.orientation
            )
            
            if not self.move_pose(approach_place, velocity):
                return False
            if not self.move_pose(place_pose, velocity * 0.5):
                return False
            if not self.open_gripper():
                return False
            time.sleep(0.2)
            if not self.move_pose(approach_place, velocity * 0.5):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Pick and place failed: {e}")
            return False
    
    def on_status_change(self, callback: Callable[[RobotStatus], None]):
        """Register callback for status changes."""
        self._status_callbacks.append(callback)
    
    def _notify_status(self):
        """Notify status change callbacks."""
        for cb in self._status_callbacks:
            try:
                cb(self.status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")


class NiryoController(RobotController):
    """
    Controller for Niryo Ned2 robot arm.
    
    Uses niryo_robot ROS2 packages for communication.
    Topics:
        - /niryo_robot/joint_states
        - /niryo_robot/robot_state
    Services:
        - /niryo_robot_commander/move_joints
        - /niryo_robot_commander/move_pose
        - /niryo_robot_tools/open_gripper
        - /niryo_robot_tools/close_gripper
    """
    
    # Niryo Ned2 joint limits (radians)
    JOINT_LIMITS = [
        (-2.96, 2.96),   # Joint 1
        (-1.92, 0.64),   # Joint 2
        (-1.40, 1.57),   # Joint 3
        (-2.09, 2.09),   # Joint 4
        (-1.92, 1.75),   # Joint 5
        (-2.53, 2.53),   # Joint 6
    ]
    
    HOME_POSITION = [0.0, -0.5, 0.5, 0.0, 0.0, 0.0]
    
    def __init__(self, robot_id: str, config: Dict[str, Any]):
        super().__init__(robot_id, config)
        self._namespace = config.get('ros_namespace', '/niryo_robot')
    
    def connect(self) -> bool:
        """Connect to Niryo Ned2 via ROS2."""
        try:
            ip = self.config.get('connection_config', {}).get('ip', 'localhost')
            port = self.config.get('connection_config', {}).get('port', 9090)
            
            self._bridge = get_ros2_bridge(ip, port)
            
            if not self._bridge.connect():
                logger.error("Failed to connect to rosbridge")
                return False
            
            # Subscribe to robot state
            self._bridge.subscribe(
                f"{self._namespace}/robot_state",
                "niryo_robot_msgs/msg/RobotState",
                self._on_robot_state
            )
            
            # Subscribe to joint states
            self._bridge.subscribe(
                f"{self._namespace}/joint_states",
                "sensor_msgs/msg/JointState",
                self._on_joint_state
            )
            
            self._connected = True
            self.status.state = RobotState.IDLE
            self._notify_status()
            
            logger.info(f"Connected to Niryo Ned2 at {ip}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Niryo: {e}")
            self.status.state = RobotState.ERROR
            self.status.error_message = str(e)
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from Niryo Ned2."""
        if self._bridge:
            self._bridge.unsubscribe(f"{self._namespace}/robot_state")
            self._bridge.unsubscribe(f"{self._namespace}/joint_states")
        
        self._connected = False
        self.status.state = RobotState.DISCONNECTED
        self._notify_status()
        return True
    
    def home(self) -> bool:
        """Move to home position."""
        return self.move_joints(self.HOME_POSITION)
    
    def move_joints(self, joints: List[float], velocity: float = 0.5) -> bool:
        """Move to joint positions."""
        if not self.is_connected:
            return False
        
        # Validate joints
        if len(joints) != 6:
            logger.error("Niryo requires 6 joint values")
            return False
        
        # Check limits
        for i, (j, (lo, hi)) in enumerate(zip(joints, self.JOINT_LIMITS)):
            if j < lo or j > hi:
                logger.error(f"Joint {i+1} value {j} out of limits [{lo}, {hi}]")
                return False
        
        self.status.state = RobotState.MOVING
        self._notify_status()
        
        result = self._bridge.call_service(
            f"{self._namespace}_commander/move_joints",
            "niryo_robot_msgs/srv/MoveJoints",
            {"joints": joints, "velocity_percentage": int(velocity * 100)}
        )
        
        if result and result.get("success"):
            self.status.state = RobotState.IDLE
            self._notify_status()
            return True
        
        self.status.state = RobotState.ERROR
        self.status.error_message = result.get("message", "Move failed") if result else "No response"
        self._notify_status()
        return False
    
    def move_pose(self, pose: Pose, velocity: float = 0.5) -> bool:
        """Move to cartesian pose."""
        if not self.is_connected:
            return False
        
        self.status.state = RobotState.MOVING
        self._notify_status()
        
        result = self._bridge.call_service(
            f"{self._namespace}_commander/move_pose",
            "niryo_robot_msgs/srv/MovePose",
            {
                "x": pose.position.x,
                "y": pose.position.y,
                "z": pose.position.z,
                "roll": 0.0,  # Convert from quaternion if needed
                "pitch": 0.0,
                "yaw": 0.0,
                "velocity_percentage": int(velocity * 100)
            }
        )
        
        if result and result.get("success"):
            self.status.state = RobotState.IDLE
            self._notify_status()
            return True
        
        self.status.state = RobotState.ERROR
        self._notify_status()
        return False
    
    def open_gripper(self) -> bool:
        """Open the gripper."""
        if not self.is_connected:
            return False
        
        result = self._bridge.call_service(
            f"{self._namespace}_tools/open_gripper",
            "niryo_robot_msgs/srv/OpenGripper",
            {"speed": 500}
        )
        
        if result and result.get("success"):
            self.status.gripper_open = True
            self.status.gripper_position = 1.0
            self._notify_status()
            return True
        return False
    
    def close_gripper(self) -> bool:
        """Close the gripper."""
        if not self.is_connected:
            return False
        
        result = self._bridge.call_service(
            f"{self._namespace}_tools/close_gripper",
            "niryo_robot_msgs/srv/CloseGripper",
            {"speed": 500}
        )
        
        if result and result.get("success"):
            self.status.gripper_open = False
            self.status.gripper_position = 0.0
            self._notify_status()
            return True
        return False
    
    def stop(self) -> bool:
        """Emergency stop."""
        if self._bridge:
            self._bridge.call_service(
                f"{self._namespace}_commander/stop_command",
                "std_srvs/srv/Trigger",
                {}
            )
        self.status.state = RobotState.ESTOPPED
        self._notify_status()
        return True
    
    def _on_robot_state(self, msg: Dict):
        """Handle robot state message."""
        state_map = {
            1: RobotState.IDLE,
            2: RobotState.MOVING,
            3: RobotState.ERROR,
        }
        self.status.state = state_map.get(msg.get("robot_state", 0), RobotState.IDLE)
        self._notify_status()
    
    def _on_joint_state(self, msg: Dict):
        """Handle joint state message."""
        positions = msg.get("position", [])
        if len(positions) >= 6:
            self.status.joint_positions = list(positions[:6])
            self._notify_status()


class XArmController(RobotController):
    """
    Controller for UFactory xArm Lite 6 robot arm.
    
    Uses xarm_ros2 packages for communication.
    Topics:
        - /xarm/joint_states
        - /xarm/xarm_states
    Services:
        - /xarm/move_joint
        - /xarm/move_line
        - /xarm/set_gripper_position
    """
    
    # xArm Lite 6 joint limits (degrees, converted to radians internally)
    JOINT_LIMITS_DEG = [
        (-360, 360),  # Joint 1
        (-118, 120),  # Joint 2
        (-225, 11),   # Joint 3
        (-360, 360),  # Joint 4
        (-97, 180),   # Joint 5
        (-360, 360),  # Joint 6
    ]
    
    HOME_POSITION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    def __init__(self, robot_id: str, config: Dict[str, Any]):
        super().__init__(robot_id, config)
        self._namespace = config.get('ros_namespace', '/xarm')
    
    def connect(self) -> bool:
        """Connect to xArm via ROS2."""
        try:
            ip = self.config.get('connection_config', {}).get('ip', 'localhost')
            port = self.config.get('connection_config', {}).get('port', 9090)
            
            self._bridge = get_ros2_bridge(ip, port)
            
            if not self._bridge.connect():
                logger.error("Failed to connect to rosbridge")
                return False
            
            # Subscribe to robot state
            self._bridge.subscribe(
                f"{self._namespace}/xarm_states",
                "xarm_msgs/msg/RobotMsg",
                self._on_robot_state
            )
            
            # Subscribe to joint states
            self._bridge.subscribe(
                f"{self._namespace}/joint_states",
                "sensor_msgs/msg/JointState",
                self._on_joint_state
            )
            
            self._connected = True
            self.status.state = RobotState.IDLE
            self._notify_status()
            
            logger.info(f"Connected to xArm at {ip}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to xArm: {e}")
            self.status.state = RobotState.ERROR
            self.status.error_message = str(e)
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from xArm."""
        if self._bridge:
            self._bridge.unsubscribe(f"{self._namespace}/xarm_states")
            self._bridge.unsubscribe(f"{self._namespace}/joint_states")
        
        self._connected = False
        self.status.state = RobotState.DISCONNECTED
        self._notify_status()
        return True
    
    def home(self) -> bool:
        """Move to home position."""
        return self.move_joints(self.HOME_POSITION)
    
    def move_joints(self, joints: List[float], velocity: float = 0.5) -> bool:
        """Move to joint positions (in radians)."""
        if not self.is_connected:
            return False
        
        if len(joints) != 6:
            logger.error("xArm Lite 6 requires 6 joint values")
            return False
        
        self.status.state = RobotState.MOVING
        self._notify_status()
        
        # xArm uses degrees internally in some interfaces
        import math
        joints_deg = [math.degrees(j) for j in joints]
        
        result = self._bridge.call_service(
            f"{self._namespace}/move_joint",
            "xarm_msgs/srv/MoveJoint",
            {
                "angles": joints_deg,
                "speed": velocity * 180,  # deg/s
                "acc": 500,
                "mvtime": 0
            }
        )
        
        if result and result.get("ret") == 0:
            self.status.state = RobotState.IDLE
            self._notify_status()
            return True
        
        self.status.state = RobotState.ERROR
        self._notify_status()
        return False
    
    def move_pose(self, pose: Pose, velocity: float = 0.5) -> bool:
        """Move to cartesian pose."""
        if not self.is_connected:
            return False
        
        self.status.state = RobotState.MOVING
        self._notify_status()
        
        result = self._bridge.call_service(
            f"{self._namespace}/move_line",
            "xarm_msgs/srv/MoveLine",
            {
                "pose": [
                    pose.position.x * 1000,  # xArm uses mm
                    pose.position.y * 1000,
                    pose.position.z * 1000,
                    0, 0, 0  # Roll, pitch, yaw
                ],
                "speed": velocity * 200,  # mm/s
                "acc": 2000,
                "mvtime": 0
            }
        )
        
        if result and result.get("ret") == 0:
            self.status.state = RobotState.IDLE
            self._notify_status()
            return True
        
        self.status.state = RobotState.ERROR
        self._notify_status()
        return False
    
    def open_gripper(self) -> bool:
        """Open the gripper."""
        if not self.is_connected:
            return False
        
        result = self._bridge.call_service(
            f"{self._namespace}/set_gripper_position",
            "xarm_msgs/srv/GripperMove",
            {"pos": 850, "speed": 3000}  # Max open position
        )
        
        if result and result.get("ret") == 0:
            self.status.gripper_open = True
            self.status.gripper_position = 1.0
            self._notify_status()
            return True
        return False
    
    def close_gripper(self) -> bool:
        """Close the gripper."""
        if not self.is_connected:
            return False
        
        result = self._bridge.call_service(
            f"{self._namespace}/set_gripper_position",
            "xarm_msgs/srv/GripperMove",
            {"pos": 0, "speed": 3000}  # Fully closed
        )
        
        if result and result.get("ret") == 0:
            self.status.gripper_open = False
            self.status.gripper_position = 0.0
            self._notify_status()
            return True
        return False
    
    def stop(self) -> bool:
        """Emergency stop."""
        if self._bridge:
            self._bridge.call_service(
                f"{self._namespace}/emergency_stop",
                "std_srvs/srv/Trigger",
                {}
            )
        self.status.state = RobotState.ESTOPPED
        self._notify_status()
        return True
    
    def _on_robot_state(self, msg: Dict):
        """Handle xArm state message."""
        state = msg.get("state", 0)
        state_map = {
            1: RobotState.IDLE,
            2: RobotState.MOVING,
            3: RobotState.ERROR,
            4: RobotState.ESTOPPED,
        }
        self.status.state = state_map.get(state, RobotState.IDLE)
        
        err = msg.get("err", 0)
        if err != 0:
            self.status.error_code = str(err)
            self.status.state = RobotState.ERROR
        
        self._notify_status()
    
    def _on_joint_state(self, msg: Dict):
        """Handle joint state message."""
        positions = msg.get("position", [])
        if len(positions) >= 6:
            self.status.joint_positions = list(positions[:6])
            self._notify_status()
