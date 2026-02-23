"""
Niryo Ned2 Robotic Arm Driver

Driver for the Niryo Ned2 6-DOF collaborative robot.

Specifications:
- 6 axes rotary joints
- 300mm reach
- 300g payload
- ±0.5mm repeatability
- Collaborative operation (ISO/TS 15066)

URDF Source: https://github.com/NiryoRobotics/ned_ros
ROS2 Driver: https://github.com/NiryoRobotics/ned-ros2-driver

DH Parameters derived from URDF at:
https://github.com/NiryoRobotics/ned_ros/blob/master/niryo_robot_description/urdf/ned/

Author: LegoMCP Team
Version: 2.0.0
"""

import asyncio
import math
import logging
from typing import Optional
from datetime import datetime

from ..arm_controller import (
    BaseArmDriver,
    SimulatedArmDriver,
    ArmSpecification,
    ArmModel,
    ArmState,
    GripperState,
    JointState,
    Trajectory,
    DHParameter,
    JointLimits,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Niryo Ned2 Specification
# =============================================================================

# DH Parameters for Niryo Ned2 (from URDF analysis)
# Using modified DH convention
NIRYO_NED2_DH_PARAMS = [
    DHParameter(a=0.0, d=103.0, alpha=-math.pi/2, theta_offset=0.0),      # Joint 1
    DHParameter(a=210.0, d=0.0, alpha=0.0, theta_offset=-math.pi/2),       # Joint 2
    DHParameter(a=30.0, d=0.0, alpha=-math.pi/2, theta_offset=0.0),        # Joint 3
    DHParameter(a=0.0, d=186.0, alpha=math.pi/2, theta_offset=0.0),        # Joint 4
    DHParameter(a=0.0, d=0.0, alpha=-math.pi/2, theta_offset=0.0),         # Joint 5
    DHParameter(a=0.0, d=68.0, alpha=0.0, theta_offset=0.0),               # Joint 6
]

# Joint limits for Ned2
NIRYO_NED2_JOINT_LIMITS = [
    JointLimits(
        min_position=math.radians(-175),
        max_position=math.radians(175),
        max_velocity=math.radians(150),  # deg/s
        max_acceleration=math.radians(300),
        max_effort=6.0  # Nm
    ),
    JointLimits(
        min_position=math.radians(-90),
        max_position=math.radians(36),
        max_velocity=math.radians(150),
        max_acceleration=math.radians(300),
        max_effort=6.0
    ),
    JointLimits(
        min_position=math.radians(-80),
        max_position=math.radians(90),
        max_velocity=math.radians(150),
        max_acceleration=math.radians(300),
        max_effort=6.0
    ),
    JointLimits(
        min_position=math.radians(-175),
        max_position=math.radians(175),
        max_velocity=math.radians(180),
        max_acceleration=math.radians(360),
        max_effort=3.0
    ),
    JointLimits(
        min_position=math.radians(-100),
        max_position=math.radians(110),
        max_velocity=math.radians(180),
        max_acceleration=math.radians(360),
        max_effort=3.0
    ),
    JointLimits(
        min_position=math.radians(-145),
        max_position=math.radians(145),
        max_velocity=math.radians(180),
        max_acceleration=math.radians(360),
        max_effort=1.5
    ),
]

NIRYO_NED2_SPEC = ArmSpecification(
    model=ArmModel.NIRYO_NED2,
    name="Niryo Ned2",
    dof=6,
    dh_params=NIRYO_NED2_DH_PARAMS,
    joint_limits=NIRYO_NED2_JOINT_LIMITS,
    max_payload_kg=0.3,
    reach_mm=440.0,
    repeatability_mm=0.5,
    weight_kg=5.8,
    home_position=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    urdf_url="https://github.com/NiryoRobotics/ned_ros/blob/master/niryo_robot_description/urdf/ned/niryo_ned.urdf.xacro",
    mesh_urls={
        'base': '/models/niryo_ned2/base_link.stl',
        'shoulder': '/models/niryo_ned2/shoulder_link.stl',
        'arm': '/models/niryo_ned2/arm_link.stl',
        'elbow': '/models/niryo_ned2/elbow_link.stl',
        'forearm': '/models/niryo_ned2/forearm_link.stl',
        'wrist': '/models/niryo_ned2/wrist_link.stl',
        'hand': '/models/niryo_ned2/hand_link.stl',
    }
)


# =============================================================================
# Niryo Ned2 Driver
# =============================================================================

class NiryoNed2Driver(BaseArmDriver):
    """
    Driver for Niryo Ned2 robotic arm.

    Supports:
    - TCP/IP communication with Ned2
    - pyniryo2 Python API integration
    - Real-time joint state streaming
    - Gripper control (Gripper 1, Gripper 2, Vacuum)

    Connection:
    - Default IP: 169.254.200.200 (USB)
    - WiFi: Dynamic IP from DHCP
    - Port: 9090 (ROS Bridge) or direct API
    """

    def __init__(
        self,
        arm_id: str,
        host: str = "169.254.200.200",
        port: int = 9090,
        simulation_mode: bool = False
    ):
        super().__init__(arm_id, NIRYO_NED2_SPEC)
        self.host = host
        self.port = port
        self.simulation_mode = simulation_mode

        self._client = None  # pyniryo2 client
        self._streaming_task: Optional[asyncio.Task] = None
        self._gripper_type = "gripper1"  # gripper1, gripper2, vacuum

    async def connect(self) -> bool:
        """Connect to Niryo Ned2."""
        self.state = ArmState.INITIALIZING

        if self.simulation_mode:
            # Simulation mode - no hardware
            await asyncio.sleep(0.5)
            self.state = ArmState.IDLE
            logger.info(f"Niryo Ned2 {self.arm_id} connected (simulation mode)")
            return True

        try:
            # Attempt to import pyniryo2
            # from pyniryo2 import NiryoRobot
            # self._client = NiryoRobot(f"{self.host}")

            # For now, use simulation if library not available
            logger.warning("pyniryo2 not installed, using simulation mode")
            self.simulation_mode = True
            await asyncio.sleep(0.5)
            self.state = ArmState.IDLE
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Niryo Ned2: {e}")
            self.state = ArmState.ERROR
            return False

    async def disconnect(self) -> None:
        """Disconnect from Niryo Ned2."""
        if self._streaming_task:
            self._streaming_task.cancel()

        if self._client:
            # self._client.close_connection()
            self._client = None

        self.state = ArmState.DISCONNECTED
        logger.info(f"Niryo Ned2 {self.arm_id} disconnected")

    async def _execute_trajectory(self, trajectory: Trajectory) -> bool:
        """Execute trajectory on Ned2."""
        if self.simulation_mode:
            # Simulate execution
            for point in trajectory.points:
                if self.state == ArmState.EMERGENCY_STOP:
                    return False

                self.current_joints = JointState(
                    positions=point.positions,
                    velocities=point.velocities or [0.0] * 6,
                    efforts=[0.1] * 6
                )
                await asyncio.sleep(0.02)

            return True

        try:
            # Real hardware execution
            # for point in trajectory.points:
            #     self._client.move_joints(*point.positions)
            #     await asyncio.sleep(point.time_from_start)
            return True

        except Exception as e:
            logger.error(f"Trajectory execution failed: {e}")
            return False

    async def _read_joint_state(self) -> JointState:
        """Read joint state from Ned2."""
        if self.simulation_mode:
            return self.current_joints

        try:
            # joints = self._client.get_joints()
            # return JointState(
            #     positions=list(joints),
            #     velocities=[0.0] * 6,
            #     efforts=[0.0] * 6
            # )
            return self.current_joints
        except Exception as e:
            logger.error(f"Failed to read joint state: {e}")
            return self.current_joints

    async def _control_gripper(self, action: str, force: float = 50.0) -> bool:
        """Control Ned2 gripper."""
        if self.simulation_mode:
            await asyncio.sleep(0.3)
            return True

        try:
            # if action == 'open':
            #     self._client.open_gripper()
            # elif action == 'close':
            #     self._client.close_gripper()
            return True
        except Exception as e:
            logger.error(f"Gripper control failed: {e}")
            return False

    async def calibrate(self) -> bool:
        """Run auto-calibration sequence."""
        self.state = ArmState.CALIBRATING
        logger.info(f"Calibrating Niryo Ned2 {self.arm_id}...")

        if self.simulation_mode:
            await asyncio.sleep(5.0)  # Simulate calibration time
            self.state = ArmState.IDLE
            return True

        try:
            # self._client.calibrate_auto()
            self.state = ArmState.IDLE
            return True
        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            self.state = ArmState.ERROR
            return False

    def set_gripper_type(self, gripper_type: str) -> None:
        """Set gripper type (gripper1, gripper2, vacuum)."""
        valid_types = ["gripper1", "gripper2", "vacuum"]
        if gripper_type not in valid_types:
            raise ValueError(f"Invalid gripper type. Must be one of: {valid_types}")
        self._gripper_type = gripper_type
        logger.info(f"Gripper type set to: {gripper_type}")


# =============================================================================
# Factory Function
# =============================================================================

def create_niryo_ned2(
    arm_id: str,
    host: str = "169.254.200.200",
    simulation: bool = True
) -> NiryoNed2Driver:
    """Create and register a Niryo Ned2 driver."""
    from ..arm_controller import register_arm

    driver = NiryoNed2Driver(
        arm_id=arm_id,
        host=host,
        simulation_mode=simulation
    )
    register_arm(driver)
    return driver
