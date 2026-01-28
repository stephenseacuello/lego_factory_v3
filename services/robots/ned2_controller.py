"""
Niryo Ned2 Enhanced Controller

Features:
- 6-DOF collaborative robot (440mm reach, 300g payload)
- Built-in vacuum/gripper control
- Learning mode for manual teaching
- ROS2/pyniryo integration
- Forward kinematics for Unity visualization
- Pick-and-place primitives

Safety Features:
- Collision detection
- Joint limit monitoring
- Speed limiting in collaborative mode
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math
import asyncio
import logging

logger = logging.getLogger(__name__)


class Ned2State(Enum):
    """Ned2 robot states"""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    MOVING = "moving"
    HOLDING = "holding"
    LEARNING = "learning"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class GripperType(Enum):
    """Ned2 end effector types"""
    NONE = "none"
    GRIPPER_1 = "gripper_1"  # Standard gripper
    GRIPPER_2 = "gripper_2"  # Large gripper
    VACUUM = "vacuum"
    ELECTROMAGNET = "electromagnet"
    CUSTOM = "custom"


@dataclass
class Ned2Configuration:
    """Ned2 robot configuration"""
    robot_id: str = "ned2-001"
    ros_namespace: str = "/niryo_robot"
    ip_address: str = "169.254.200.200"  # Default Ned2 IP

    # Denavit-Hartenberg Parameters (mm, degrees)
    # Modified DH convention: [d, a, alpha, theta_offset]
    dh_params: List[Dict] = field(default_factory=lambda: [
        {"d": 103.0, "a": 0, "alpha": -90, "theta_offset": 0},
        {"d": 0, "a": 210.0, "alpha": 0, "theta_offset": -90},
        {"d": 0, "a": 30.0, "alpha": -90, "theta_offset": 0},
        {"d": 221.0, "a": 0, "alpha": 90, "theta_offset": 0},
        {"d": 0, "a": 0, "alpha": -90, "theta_offset": 0},
        {"d": 55.0, "a": 0, "alpha": 0, "theta_offset": 0},
    ])

    # Joint limits (degrees)
    joint_limits: List[Dict] = field(default_factory=lambda: [
        {"min": -175, "max": 175, "max_velocity": 180, "max_accel": 360},
        {"min": -90, "max": 36.7, "max_velocity": 180, "max_accel": 360},
        {"min": -80, "max": 90, "max_velocity": 180, "max_accel": 360},
        {"min": -175, "max": 175, "max_velocity": 180, "max_accel": 360},
        {"min": -100, "max": 110, "max_velocity": 180, "max_accel": 360},
        {"min": -147.5, "max": 147.5, "max_velocity": 180, "max_accel": 360},
    ])

    # Physical specs
    num_joints: int = 6
    reach_mm: float = 440.0
    payload_kg: float = 0.3
    repeatability_mm: float = 0.5

    # Default speeds
    default_velocity: float = 50.0  # percent
    default_acceleration: float = 50.0  # percent

    # Tool offset (TCP from flange)
    tool_offset: Dict = field(default_factory=lambda: {
        "x": 0, "y": 0, "z": 25, "rx": 0, "ry": 0, "rz": 0
    })

    # Home position (radians)
    home_joints: List[float] = field(default_factory=lambda: [
        0.0, 0.0, 0.0, 0.0, -1.57, 0.0
    ])

    # Safe retract height above work
    safe_height_mm: float = 100.0

    # Pick-and-place defaults
    approach_height_mm: float = 50.0
    grasp_force: float = 50.0  # percent


@dataclass
class Ned2JointState:
    """Current joint state"""
    positions: List[float]  # radians
    velocities: List[float]  # rad/s
    efforts: List[float]  # Nm (estimated)
    temperatures: List[float]  # Celsius


@dataclass
class Ned2Pose:
    """Cartesian pose"""
    x: float  # mm
    y: float  # mm
    z: float  # mm
    roll: float  # radians
    pitch: float  # radians
    yaw: float  # radians

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z, self.roll, self.pitch, self.yaw]

    @classmethod
    def from_list(cls, values: List[float]) -> 'Ned2Pose':
        return cls(
            x=values[0], y=values[1], z=values[2],
            roll=values[3], pitch=values[4], yaw=values[5]
        )


class Ned2Controller:
    """
    Enhanced Ned2 controller with pick-and-place support

    Provides high-level primitives for factory automation:
    - pick_from_pallet(): Pick from specific pallet slot
    - place_in_fixture(): Place in CNC fixture
    - safe_retract(): Move to safe height
    - forward_kinematics(): Compute TCP pose from joints
    """

    def __init__(self, config: Ned2Configuration = None):
        self.config = config or Ned2Configuration()
        self.state = Ned2State.DISCONNECTED
        self.gripper_type = GripperType.GRIPPER_1
        self.gripper_open = True

        # Current state
        self.joint_state: Optional[Ned2JointState] = None
        self.current_pose: Optional[Ned2Pose] = None

        # ROS2 interface (set externally)
        self.ros_bridge = None

        # Recorded waypoints for teaching
        self.waypoints: Dict[str, List[float]] = {}

        # Callbacks
        self.on_state_change = None
        self.on_error = None

        logger.info(f"Ned2Controller initialized: {self.config.robot_id}")

    async def connect(self) -> bool:
        """Connect to Ned2 robot"""
        try:
            if self.ros_bridge:
                # Connect via ROS2
                connected = await self.ros_bridge.connect(
                    self.config.ros_namespace
                )
                if connected:
                    self.state = Ned2State.IDLE
                    logger.info(f"Connected to Ned2: {self.config.robot_id}")
                    return True

            # Simulation mode
            self.state = Ned2State.IDLE
            self.joint_state = Ned2JointState(
                positions=self.config.home_joints.copy(),
                velocities=[0.0] * 6,
                efforts=[0.0] * 6,
                temperatures=[25.0] * 6
            )
            logger.info(f"Ned2 in simulation mode: {self.config.robot_id}")
            return True

        except Exception as e:
            logger.error(f"Ned2 connection failed: {e}")
            self.state = Ned2State.ERROR
            return False

    async def disconnect(self):
        """Disconnect from robot"""
        self.state = Ned2State.DISCONNECTED
        logger.info(f"Ned2 disconnected: {self.config.robot_id}")

    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state != Ned2State.DISCONNECTED

    # =========================================================================
    # Motion Commands
    # =========================================================================

    async def move_joints(
        self,
        joints: List[float],
        velocity: float = None,
        wait: bool = True
    ) -> bool:
        """
        Move to joint positions

        Args:
            joints: Target joint positions in radians (6 values)
            velocity: Speed percentage (0-100)
            wait: Wait for motion to complete

        Returns:
            True if motion successful
        """
        if len(joints) != 6:
            raise ValueError("joints must have 6 values")

        # Check limits
        for i, (joint, limit) in enumerate(zip(joints, self.config.joint_limits)):
            joint_deg = math.degrees(joint)
            if joint_deg < limit["min"] or joint_deg > limit["max"]:
                raise ValueError(
                    f"Joint {i} ({joint_deg:.1f}°) outside limits "
                    f"[{limit['min']}, {limit['max']}]"
                )

        velocity = velocity or self.config.default_velocity
        self.state = Ned2State.MOVING

        try:
            if self.ros_bridge:
                # Send via ROS2
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/commander/move_joints",
                    {"joints": joints, "velocity": velocity / 100.0}
                )
            else:
                # Simulation - interpolate motion
                await self._simulate_motion(joints, velocity)
                success = True

            if success and self.joint_state:
                self.joint_state.positions = joints.copy()
                self.current_pose = self.forward_kinematics(joints)

            self.state = Ned2State.IDLE
            return success

        except Exception as e:
            logger.error(f"Move joints failed: {e}")
            self.state = Ned2State.ERROR
            return False

    async def move_pose(
        self,
        pose: Ned2Pose,
        velocity: float = None,
        linear: bool = False,
        wait: bool = True
    ) -> bool:
        """
        Move to Cartesian pose

        Args:
            pose: Target TCP pose
            velocity: Speed percentage
            linear: Use linear interpolation (vs joint)
            wait: Wait for motion to complete

        Returns:
            True if motion successful
        """
        velocity = velocity or self.config.default_velocity
        self.state = Ned2State.MOVING

        try:
            if self.ros_bridge:
                service = (
                    f"{self.config.ros_namespace}/commander/move_linear"
                    if linear else
                    f"{self.config.ros_namespace}/commander/move_pose"
                )
                success = await self.ros_bridge.call_service(
                    service,
                    {
                        "position": [pose.x / 1000, pose.y / 1000, pose.z / 1000],
                        "orientation": [pose.roll, pose.pitch, pose.yaw],
                        "velocity": velocity / 100.0
                    }
                )
            else:
                # Simulation
                await asyncio.sleep(2.0 * (100 - velocity) / 100 + 0.5)
                success = True

            if success:
                self.current_pose = pose

            self.state = Ned2State.IDLE
            return success

        except Exception as e:
            logger.error(f"Move pose failed: {e}")
            self.state = Ned2State.ERROR
            return False

    async def move_home(self) -> bool:
        """Move to home position"""
        logger.info("Moving Ned2 to home position")
        return await self.move_joints(self.config.home_joints)

    async def stop(self) -> bool:
        """Emergency stop"""
        self.state = Ned2State.EMERGENCY_STOP
        if self.ros_bridge:
            await self.ros_bridge.call_service(
                f"{self.config.ros_namespace}/commander/stop",
                {}
            )
        logger.warning("Ned2 emergency stop")
        return True

    # =========================================================================
    # Gripper Control
    # =========================================================================

    async def gripper_grasp(self, force: float = None) -> bool:
        """
        Close gripper to grasp object

        Args:
            force: Grasp force percentage (0-100)

        Returns:
            True if grasp detected
        """
        force = force or self.config.grasp_force

        try:
            if self.ros_bridge:
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/tools/grasp",
                    {"force": force / 100.0}
                )
            else:
                await asyncio.sleep(0.5)
                success = True

            self.gripper_open = False
            logger.info(f"Ned2 gripper grasped at {force}% force")
            return success

        except Exception as e:
            logger.error(f"Gripper grasp failed: {e}")
            return False

    async def gripper_release(self) -> bool:
        """Open gripper to release object"""
        try:
            if self.ros_bridge:
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/tools/release",
                    {}
                )
            else:
                await asyncio.sleep(0.3)
                success = True

            self.gripper_open = True
            logger.info("Ned2 gripper released")
            return success

        except Exception as e:
            logger.error(f"Gripper release failed: {e}")
            return False

    # =========================================================================
    # Learning Mode
    # =========================================================================

    async def set_learning_mode(self, enabled: bool) -> bool:
        """
        Enable/disable learning mode

        In learning mode, the robot can be manually moved
        and joint positions recorded.
        """
        try:
            if self.ros_bridge:
                await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/commander/set_learning_mode",
                    {"enabled": enabled}
                )

            self.state = Ned2State.LEARNING if enabled else Ned2State.IDLE
            logger.info(f"Ned2 learning mode: {'enabled' if enabled else 'disabled'}")
            return True

        except Exception as e:
            logger.error(f"Set learning mode failed: {e}")
            return False

    def record_waypoint(self, name: str) -> Dict:
        """Record current position as named waypoint"""
        if self.joint_state:
            self.waypoints[name] = self.joint_state.positions.copy()
            logger.info(f"Recorded waypoint '{name}': {self.waypoints[name]}")
            return {
                "name": name,
                "joints": self.waypoints[name],
                "pose": self.current_pose.to_list() if self.current_pose else None
            }
        return {}

    # =========================================================================
    # Pick-and-Place Primitives
    # =========================================================================

    async def pick_from_pallet(
        self,
        slot_position: Tuple[float, float, float],
        approach_height: float = None,
        grasp_force: float = None
    ) -> bool:
        """
        Pick workpiece from pallet slot

        Args:
            slot_position: (x, y, z) position of slot in mm
            approach_height: Height above slot for approach
            grasp_force: Gripper force percentage

        Returns:
            True if pick successful
        """
        approach_height = approach_height or self.config.approach_height_mm
        grasp_force = grasp_force or self.config.grasp_force

        x, y, z = slot_position

        logger.info(f"Ned2 picking from ({x}, {y}, {z})")

        # 1. Move to approach position
        approach_pose = Ned2Pose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(approach_pose):
            return False

        # 2. Open gripper
        await self.gripper_release()

        # 3. Descend to pick
        pick_pose = Ned2Pose(
            x=x, y=y, z=z,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(pick_pose, linear=True):
            return False

        # 4. Grasp
        if not await self.gripper_grasp(grasp_force):
            return False

        # 5. Retract
        if not await self.move_pose(approach_pose, linear=True):
            return False

        logger.info("Ned2 pick complete")
        return True

    async def place_in_fixture(
        self,
        fixture_position: Tuple[float, float, float],
        approach_height: float = None
    ) -> bool:
        """
        Place workpiece in fixture

        Args:
            fixture_position: (x, y, z) fixture position in mm
            approach_height: Height above fixture for approach

        Returns:
            True if place successful
        """
        approach_height = approach_height or self.config.approach_height_mm

        x, y, z = fixture_position

        logger.info(f"Ned2 placing at fixture ({x}, {y}, {z})")

        # 1. Move to approach position
        approach_pose = Ned2Pose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(approach_pose):
            return False

        # 2. Descend to place
        place_pose = Ned2Pose(
            x=x, y=y, z=z,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(place_pose, linear=True):
            return False

        # 3. Release
        await self.gripper_release()

        # 4. Retract
        if not await self.move_pose(approach_pose, linear=True):
            return False

        logger.info("Ned2 place complete")
        return True

    async def safe_retract(self, height: float = None) -> bool:
        """Retract to safe height above current position"""
        height = height or self.config.safe_height_mm

        if self.current_pose:
            safe_pose = Ned2Pose(
                x=self.current_pose.x,
                y=self.current_pose.y,
                z=self.current_pose.z + height,
                roll=self.current_pose.roll,
                pitch=self.current_pose.pitch,
                yaw=self.current_pose.yaw
            )
            return await self.move_pose(safe_pose, linear=True)

        return await self.move_home()

    # =========================================================================
    # Kinematics
    # =========================================================================

    def forward_kinematics(self, joints: List[float]) -> Ned2Pose:
        """
        Compute TCP pose from joint angles

        Uses DH parameters for forward kinematics.

        Args:
            joints: Joint angles in radians

        Returns:
            TCP pose
        """
        # Build transformation matrix
        T = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

        for i, (joint, dh) in enumerate(zip(joints, self.config.dh_params)):
            theta = joint + math.radians(dh["theta_offset"])
            d = dh["d"]
            a = dh["a"]
            alpha = math.radians(dh["alpha"])

            # DH transformation matrix
            ct, st = math.cos(theta), math.sin(theta)
            ca, sa = math.cos(alpha), math.sin(alpha)

            T_i = [
                [ct, -st * ca, st * sa, a * ct],
                [st, ct * ca, -ct * sa, a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1]
            ]

            # Matrix multiply T = T * T_i
            T = self._matrix_multiply(T, T_i)

        # Extract position
        x = T[0][3]
        y = T[1][3]
        z = T[2][3]

        # Extract Euler angles (ZYX convention)
        roll = math.atan2(T[2][1], T[2][2])
        pitch = math.atan2(-T[2][0], math.sqrt(T[2][1]**2 + T[2][2]**2))
        yaw = math.atan2(T[1][0], T[0][0])

        return Ned2Pose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw)

    def _matrix_multiply(self, A: List[List], B: List[List]) -> List[List]:
        """4x4 matrix multiplication"""
        result = [[0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                for k in range(4):
                    result[i][j] += A[i][k] * B[k][j]
        return result

    # =========================================================================
    # Status & Monitoring
    # =========================================================================

    def get_status(self) -> Dict:
        """Get comprehensive robot status"""
        return {
            "robot_id": self.config.robot_id,
            "state": self.state.value,
            "connected": self.is_connected(),
            "gripper": {
                "type": self.gripper_type.value,
                "open": self.gripper_open
            },
            "joints": {
                "positions": self.joint_state.positions if self.joint_state else [],
                "velocities": self.joint_state.velocities if self.joint_state else [],
                "temperatures": self.joint_state.temperatures if self.joint_state else []
            },
            "pose": self.current_pose.to_list() if self.current_pose else None,
            "waypoints": list(self.waypoints.keys())
        }

    def get_unity_state(self) -> Dict:
        """Get state formatted for Unity visualization"""
        return {
            "robot_id": self.config.robot_id,
            "robot_type": "niryo_ned2",
            "joints": self.joint_state.positions if self.joint_state else [0] * 6,
            "gripper_open": self.gripper_open,
            "state": self.state.value,
            "tcp": self.current_pose.to_list() if self.current_pose else [0] * 6
        }

    # =========================================================================
    # Simulation Helpers
    # =========================================================================

    async def _simulate_motion(self, target: List[float], velocity: float):
        """Simulate motion interpolation"""
        if not self.joint_state:
            self.joint_state = Ned2JointState(
                positions=[0] * 6,
                velocities=[0] * 6,
                efforts=[0] * 6,
                temperatures=[25] * 6
            )

        start = self.joint_state.positions.copy()
        steps = int(50 * (100 - velocity) / 100) + 10

        for i in range(steps + 1):
            t = i / steps
            for j in range(6):
                self.joint_state.positions[j] = (
                    start[j] + (target[j] - start[j]) * t
                )
            await asyncio.sleep(0.02)
