"""
UFactory xArm Lite 6 Enhanced Controller

Features:
- 6-DOF industrial robot (700mm reach, 5kg payload)
- High-speed motion capability
- Ethernet SDK / ROS2 control
- Collision detection
- Forward kinematics for Unity visualization
- Pick-and-place primitives

The xArm Lite 6 serves as the unloading robot in the factory cell,
responsible for:
- Picking machined parts from the CNC fixture
- Moving parts to inspection station
- Sorting parts to output/reject pallets
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import math
import asyncio
import logging

logger = logging.getLogger(__name__)


class XArmState(Enum):
    """xArm robot states"""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    MOVING = "moving"
    PAUSED = "paused"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class XArmMode(Enum):
    """xArm operation modes"""
    POSITION = 0  # Position control
    SERVO = 1     # Servo motion
    JOINT_TEACH = 2  # Teaching mode


class XArmGripperState(Enum):
    """Gripper states"""
    OPEN = "open"
    CLOSED = "closed"
    HOLDING = "holding"
    MOVING = "moving"


@dataclass
class XArmLite6Configuration:
    """xArm Lite 6 robot configuration"""
    robot_id: str = "xarm-001"
    ip_address: str = "192.168.1.100"
    ros_namespace: str = "/xarm"

    # Denavit-Hartenberg Parameters (mm, degrees)
    dh_params: List[Dict] = field(default_factory=lambda: [
        {"d": 267.0, "a": 0, "alpha": -90, "theta_offset": 0},
        {"d": 0, "a": 289.5, "alpha": 0, "theta_offset": -90},
        {"d": 0, "a": 77.5, "alpha": -90, "theta_offset": 0},
        {"d": 342.5, "a": 0, "alpha": 90, "theta_offset": 0},
        {"d": 0, "a": 0, "alpha": -90, "theta_offset": 0},
        {"d": 97.0, "a": 0, "alpha": 0, "theta_offset": 0},
    ])

    # Joint limits (degrees)
    joint_limits: List[Dict] = field(default_factory=lambda: [
        {"min": -360, "max": 360, "max_velocity": 180, "max_accel": 1000},
        {"min": -118, "max": 120, "max_velocity": 180, "max_accel": 1000},
        {"min": -225, "max": 11, "max_velocity": 180, "max_accel": 1000},
        {"min": -360, "max": 360, "max_velocity": 180, "max_accel": 1000},
        {"min": -97, "max": 180, "max_velocity": 180, "max_accel": 1000},
        {"min": -360, "max": 360, "max_velocity": 180, "max_accel": 1000},
    ])

    # Physical specs
    num_joints: int = 6
    reach_mm: float = 700.0
    payload_kg: float = 5.0
    repeatability_mm: float = 0.1

    # Default speeds (higher than Ned2)
    default_velocity: float = 100.0  # mm/s for linear, deg/s for joint
    default_acceleration: float = 500.0  # mm/s^2 or deg/s^2
    default_velocity_percent: float = 50.0

    # Tool offset (TCP from flange)
    tool_offset: Dict = field(default_factory=lambda: {
        "x": 0, "y": 0, "z": 150, "rx": 0, "ry": 0, "rz": 0
    })

    # Home position (radians)
    home_joints: List[float] = field(default_factory=lambda: [
        0.0, -0.5, 0.0, 0.0, 0.0, 0.0
    ])

    # Pick-and-place defaults
    safe_height_mm: float = 150.0
    approach_height_mm: float = 80.0
    grasp_force: float = 50.0

    # Network settings
    tcp_port: int = 502  # Modbus
    report_port: int = 503


@dataclass
class XArmJointState:
    """Current joint state"""
    positions: List[float]  # radians
    velocities: List[float]  # rad/s
    currents: List[float]  # mA
    temperatures: List[float]  # Celsius


@dataclass
class XArmPose:
    """Cartesian pose"""
    x: float  # mm
    y: float  # mm
    z: float  # mm
    roll: float  # radians
    pitch: float  # radians
    yaw: float  # radians

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z, self.roll, self.pitch, self.yaw]

    def to_mm_deg(self) -> List[float]:
        """Convert to xArm SDK format (mm, degrees)"""
        return [
            self.x, self.y, self.z,
            math.degrees(self.roll),
            math.degrees(self.pitch),
            math.degrees(self.yaw)
        ]

    @classmethod
    def from_list(cls, values: List[float]) -> 'XArmPose':
        return cls(
            x=values[0], y=values[1], z=values[2],
            roll=values[3], pitch=values[4], yaw=values[5]
        )


class XArmLite6Controller:
    """
    Enhanced xArm Lite 6 controller

    Provides high-level primitives for factory automation:
    - pick_from_fixture(): Pick machined part from CNC
    - place_for_inspection(): Place at inspection station
    - place_in_output_pallet(): Store in output pallet
    - place_in_reject_pallet(): Store rejected parts
    """

    def __init__(self, config: XArmLite6Configuration = None):
        self.config = config or XArmLite6Configuration()
        self.state = XArmState.DISCONNECTED
        self.mode = XArmMode.POSITION
        self.gripper_state = XArmGripperState.OPEN

        # Current state
        self.joint_state: Optional[XArmJointState] = None
        self.current_pose: Optional[XArmPose] = None

        # SDK client (set externally)
        self.sdk_client = None
        self.ros_bridge = None

        # Error tracking
        self.error_code: int = 0
        self.warn_code: int = 0

        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_collision: Optional[Callable] = None

        logger.info(f"XArmLite6Controller initialized: {self.config.robot_id}")

    async def connect(self) -> bool:
        """
        Connect to xArm robot

        Attempts connection via:
        1. xArm Python SDK (direct Ethernet)
        2. ROS2 bridge
        3. Simulation mode
        """
        try:
            # Try SDK first
            if self._try_sdk_connect():
                return True

            # Try ROS2
            if self.ros_bridge:
                connected = await self.ros_bridge.connect(
                    self.config.ros_namespace
                )
                if connected:
                    self.state = XArmState.IDLE
                    logger.info(f"Connected to xArm via ROS2: {self.config.robot_id}")
                    return True

            # Simulation mode
            self.state = XArmState.IDLE
            self.joint_state = XArmJointState(
                positions=self.config.home_joints.copy(),
                velocities=[0.0] * 6,
                currents=[0.0] * 6,
                temperatures=[30.0] * 6
            )
            logger.info(f"xArm in simulation mode: {self.config.robot_id}")
            return True

        except Exception as e:
            logger.error(f"xArm connection failed: {e}")
            self.state = XArmState.ERROR
            return False

    def _try_sdk_connect(self) -> bool:
        """Try connecting via xArm SDK"""
        try:
            # Would import xArm SDK here
            # from xarm.wrapper import XArmAPI
            # self.sdk_client = XArmAPI(self.config.ip_address)
            return False
        except ImportError:
            return False

    async def disconnect(self):
        """Disconnect from robot"""
        if self.sdk_client:
            self.sdk_client.disconnect()
        self.state = XArmState.DISCONNECTED
        logger.info(f"xArm disconnected: {self.config.robot_id}")

    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state != XArmState.DISCONNECTED

    # =========================================================================
    # Motion Commands
    # =========================================================================

    async def move_joints(
        self,
        joints: List[float],
        velocity: float = None,
        acceleration: float = None,
        wait: bool = True
    ) -> bool:
        """
        Move to joint positions

        Args:
            joints: Target joint positions in radians (6 values)
            velocity: Speed in deg/s
            acceleration: Acceleration in deg/s^2
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
        acceleration = acceleration or self.config.default_acceleration
        self.state = XArmState.MOVING

        try:
            if self.sdk_client:
                # Convert to degrees for SDK
                joints_deg = [math.degrees(j) for j in joints]
                code = self.sdk_client.set_servo_angle(
                    angle=joints_deg,
                    speed=velocity,
                    mvacc=acceleration,
                    wait=wait
                )
                success = code == 0
            elif self.ros_bridge:
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/move_joint",
                    {"joint": joints, "speed": velocity, "acc": acceleration}
                )
            else:
                # Simulation
                await self._simulate_motion(joints, velocity)
                success = True

            if success and self.joint_state:
                self.joint_state.positions = joints.copy()
                self.current_pose = self.forward_kinematics(joints)

            self.state = XArmState.IDLE
            return success

        except Exception as e:
            logger.error(f"Move joints failed: {e}")
            self.state = XArmState.ERROR
            return False

    async def move_pose(
        self,
        pose: XArmPose,
        velocity: float = None,
        acceleration: float = None,
        linear: bool = True,
        wait: bool = True
    ) -> bool:
        """
        Move to Cartesian pose

        Args:
            pose: Target TCP pose
            velocity: Speed in mm/s
            acceleration: Acceleration in mm/s^2
            linear: Use linear interpolation
            wait: Wait for motion to complete

        Returns:
            True if motion successful
        """
        velocity = velocity or self.config.default_velocity
        acceleration = acceleration or self.config.default_acceleration
        self.state = XArmState.MOVING

        try:
            if self.sdk_client:
                pose_mm_deg = pose.to_mm_deg()
                if linear:
                    code = self.sdk_client.set_position(
                        *pose_mm_deg,
                        speed=velocity,
                        mvacc=acceleration,
                        wait=wait
                    )
                else:
                    code = self.sdk_client.set_position(
                        *pose_mm_deg,
                        speed=velocity,
                        mvacc=acceleration,
                        is_radian=False,
                        wait=wait
                    )
                success = code == 0
            elif self.ros_bridge:
                service = (
                    f"{self.config.ros_namespace}/move_line"
                    if linear else
                    f"{self.config.ros_namespace}/move_pose"
                )
                success = await self.ros_bridge.call_service(
                    service,
                    {
                        "pose": pose.to_list(),
                        "speed": velocity,
                        "acc": acceleration
                    }
                )
            else:
                # Simulation
                await asyncio.sleep(1.5 * (100 - self.config.default_velocity_percent) / 100 + 0.3)
                success = True

            if success:
                self.current_pose = pose

            self.state = XArmState.IDLE
            return success

        except Exception as e:
            logger.error(f"Move pose failed: {e}")
            self.state = XArmState.ERROR
            return False

    async def move_home(self) -> bool:
        """Move to home position"""
        logger.info("Moving xArm to home position")
        return await self.move_joints(self.config.home_joints)

    async def stop(self) -> bool:
        """Emergency stop"""
        self.state = XArmState.EMERGENCY_STOP

        if self.sdk_client:
            self.sdk_client.emergency_stop()
        elif self.ros_bridge:
            await self.ros_bridge.call_service(
                f"{self.config.ros_namespace}/emergency_stop",
                {}
            )

        logger.warning("xArm emergency stop")
        return True

    async def clear_errors(self) -> bool:
        """Clear error state and re-enable motion"""
        try:
            if self.sdk_client:
                self.sdk_client.clean_error()
                self.sdk_client.motion_enable(enable=True)
                self.sdk_client.set_mode(0)
                self.sdk_client.set_state(0)

            self.state = XArmState.IDLE
            self.error_code = 0
            self.warn_code = 0
            logger.info("xArm errors cleared")
            return True

        except Exception as e:
            logger.error(f"Clear errors failed: {e}")
            return False

    # =========================================================================
    # Gripper Control
    # =========================================================================

    async def gripper_grasp(
        self,
        position: float = 0,
        speed: float = 50,
        force: float = None,
        wait: bool = True
    ) -> bool:
        """
        Close gripper to grasp object

        Args:
            position: Target position (0 = fully closed)
            speed: Gripper speed
            force: Grasp force (0-100%)
            wait: Wait for completion

        Returns:
            True if grasp successful
        """
        force = force or self.config.grasp_force
        self.gripper_state = XArmGripperState.MOVING

        try:
            if self.sdk_client:
                code = self.sdk_client.set_gripper_position(
                    pos=position,
                    speed=speed,
                    wait=wait
                )
                success = code == 0
            elif self.ros_bridge:
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/gripper/grasp",
                    {"position": position, "speed": speed, "force": force}
                )
            else:
                await asyncio.sleep(0.5)
                success = True

            self.gripper_state = XArmGripperState.HOLDING if success else XArmGripperState.OPEN
            logger.info(f"xArm gripper grasped at position {position}")
            return success

        except Exception as e:
            logger.error(f"Gripper grasp failed: {e}")
            return False

    async def gripper_release(
        self,
        position: float = 800,
        speed: float = 50,
        wait: bool = True
    ) -> bool:
        """
        Open gripper to release object

        Args:
            position: Target position (800 = fully open for standard gripper)
            speed: Gripper speed
            wait: Wait for completion

        Returns:
            True if release successful
        """
        self.gripper_state = XArmGripperState.MOVING

        try:
            if self.sdk_client:
                code = self.sdk_client.set_gripper_position(
                    pos=position,
                    speed=speed,
                    wait=wait
                )
                success = code == 0
            elif self.ros_bridge:
                success = await self.ros_bridge.call_service(
                    f"{self.config.ros_namespace}/gripper/release",
                    {"position": position, "speed": speed}
                )
            else:
                await asyncio.sleep(0.3)
                success = True

            self.gripper_state = XArmGripperState.OPEN if success else XArmGripperState.CLOSED
            logger.info("xArm gripper released")
            return success

        except Exception as e:
            logger.error(f"Gripper release failed: {e}")
            return False

    # =========================================================================
    # Pick-and-Place Primitives
    # =========================================================================

    async def pick_from_fixture(
        self,
        fixture_position: Tuple[float, float, float],
        approach_height: float = None,
        grasp_force: float = None
    ) -> bool:
        """
        Pick machined part from CNC fixture

        Args:
            fixture_position: (x, y, z) position in mm
            approach_height: Height above for approach
            grasp_force: Gripper force

        Returns:
            True if pick successful
        """
        approach_height = approach_height or self.config.approach_height_mm
        grasp_force = grasp_force or self.config.grasp_force

        x, y, z = fixture_position

        logger.info(f"xArm picking from fixture ({x}, {y}, {z})")

        # 1. Approach from above
        approach_pose = XArmPose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(approach_pose):
            return False

        # 2. Open gripper
        await self.gripper_release()

        # 3. Descend to pick (linear motion)
        pick_pose = XArmPose(
            x=x, y=y, z=z,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(pick_pose, linear=True):
            return False

        # 4. Grasp part
        if not await self.gripper_grasp(force=grasp_force):
            return False

        # Small delay for grip to stabilize
        await asyncio.sleep(0.2)

        # 5. Retract
        if not await self.move_pose(approach_pose, linear=True):
            return False

        logger.info("xArm pick from fixture complete")
        return True

    async def place_for_inspection(
        self,
        inspection_position: Tuple[float, float, float],
        approach_height: float = None
    ) -> bool:
        """
        Place part at inspection station

        Args:
            inspection_position: (x, y, z) position in mm
            approach_height: Height above for approach

        Returns:
            True if place successful
        """
        approach_height = approach_height or self.config.approach_height_mm

        x, y, z = inspection_position

        logger.info(f"xArm placing for inspection ({x}, {y}, {z})")

        # 1. Approach
        approach_pose = XArmPose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(approach_pose):
            return False

        # 2. Descend
        place_pose = XArmPose(
            x=x, y=y, z=z,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(place_pose, linear=True):
            return False

        # 3. Release
        await self.gripper_release()

        # 4. Retract slightly
        if not await self.move_pose(approach_pose, linear=True):
            return False

        logger.info("xArm place for inspection complete")
        return True

    async def pick_after_inspection(
        self,
        inspection_position: Tuple[float, float, float],
        approach_height: float = None
    ) -> bool:
        """
        Pick part after inspection

        Args:
            inspection_position: (x, y, z) position
            approach_height: Height for approach

        Returns:
            True if pick successful
        """
        approach_height = approach_height or self.config.approach_height_mm

        x, y, z = inspection_position

        # Approach
        approach_pose = XArmPose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        await self.move_pose(approach_pose)

        # Descend
        pick_pose = XArmPose(x=x, y=y, z=z, roll=0, pitch=math.pi, yaw=0)
        await self.move_pose(pick_pose, linear=True)

        # Grasp
        await self.gripper_grasp()

        # Retract
        await self.move_pose(approach_pose, linear=True)

        return True

    async def place_in_pallet(
        self,
        slot_position: Tuple[float, float, float],
        approach_height: float = None,
        pallet_type: str = "output"
    ) -> bool:
        """
        Place part in output or reject pallet

        Args:
            slot_position: (x, y, z) slot position
            approach_height: Height for approach
            pallet_type: "output" or "reject"

        Returns:
            True if place successful
        """
        approach_height = approach_height or self.config.approach_height_mm

        x, y, z = slot_position

        logger.info(f"xArm placing in {pallet_type} pallet ({x}, {y}, {z})")

        # Approach
        approach_pose = XArmPose(
            x=x, y=y, z=z + approach_height,
            roll=0, pitch=math.pi, yaw=0
        )
        if not await self.move_pose(approach_pose):
            return False

        # Descend
        place_pose = XArmPose(x=x, y=y, z=z, roll=0, pitch=math.pi, yaw=0)
        if not await self.move_pose(place_pose, linear=True):
            return False

        # Release
        await self.gripper_release()

        # Retract
        if not await self.move_pose(approach_pose, linear=True):
            return False

        logger.info(f"xArm place in {pallet_type} pallet complete")
        return True

    async def safe_retract(self, height: float = None) -> bool:
        """Retract to safe height"""
        height = height or self.config.safe_height_mm

        if self.current_pose:
            safe_pose = XArmPose(
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

    def forward_kinematics(self, joints: List[float]) -> XArmPose:
        """
        Compute TCP pose from joint angles

        Args:
            joints: Joint angles in radians

        Returns:
            TCP pose
        """
        T = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

        for i, (joint, dh) in enumerate(zip(joints, self.config.dh_params)):
            theta = joint + math.radians(dh["theta_offset"])
            d = dh["d"]
            a = dh["a"]
            alpha = math.radians(dh["alpha"])

            ct, st = math.cos(theta), math.sin(theta)
            ca, sa = math.cos(alpha), math.sin(alpha)

            T_i = [
                [ct, -st * ca, st * sa, a * ct],
                [st, ct * ca, -ct * sa, a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1]
            ]

            T = self._matrix_multiply(T, T_i)

        x = T[0][3]
        y = T[1][3]
        z = T[2][3]

        roll = math.atan2(T[2][1], T[2][2])
        pitch = math.atan2(-T[2][0], math.sqrt(T[2][1]**2 + T[2][2]**2))
        yaw = math.atan2(T[1][0], T[0][0])

        return XArmPose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw)

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
            "mode": self.mode.value,
            "connected": self.is_connected(),
            "gripper": {
                "state": self.gripper_state.value
            },
            "joints": {
                "positions": self.joint_state.positions if self.joint_state else [],
                "velocities": self.joint_state.velocities if self.joint_state else [],
                "currents": self.joint_state.currents if self.joint_state else [],
                "temperatures": self.joint_state.temperatures if self.joint_state else []
            },
            "pose": self.current_pose.to_list() if self.current_pose else None,
            "errors": {
                "error_code": self.error_code,
                "warn_code": self.warn_code
            }
        }

    def get_unity_state(self) -> Dict:
        """Get state formatted for Unity visualization"""
        return {
            "robot_id": self.config.robot_id,
            "robot_type": "xarm_lite6",
            "joints": self.joint_state.positions if self.joint_state else [0] * 6,
            "gripper_state": self.gripper_state.value,
            "state": self.state.value,
            "tcp": self.current_pose.to_list() if self.current_pose else [0] * 6
        }

    # =========================================================================
    # Simulation Helpers
    # =========================================================================

    async def _simulate_motion(self, target: List[float], velocity: float):
        """Simulate motion interpolation"""
        if not self.joint_state:
            self.joint_state = XArmJointState(
                positions=[0] * 6,
                velocities=[0] * 6,
                currents=[0] * 6,
                temperatures=[30] * 6
            )

        start = self.joint_state.positions.copy()
        steps = int(30 * (200 - velocity) / 200) + 5

        for i in range(steps + 1):
            t = i / steps
            # Smooth interpolation
            t_smooth = t * t * (3 - 2 * t)  # Smoothstep
            for j in range(6):
                self.joint_state.positions[j] = (
                    start[j] + (target[j] - start[j]) * t_smooth
                )
            await asyncio.sleep(0.02)
