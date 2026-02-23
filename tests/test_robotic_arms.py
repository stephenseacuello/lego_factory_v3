"""
Robotic Arm Simulation Tests
=============================

Comprehensive tests for the robotic arm simulation system:
- Arm controller and kinematics
- Niryo Ned2 driver
- xArm Lite 6 driver
- Master scheduler with acknowledgments
- OME integration
- Unity visualization

Standards:
- ISO 10218 (Industrial Robot Safety)
- ISO/TS 15066 (Collaborative Robots)

Author: LegoMCP Team
Version: 2.0.0
"""

import pytest
import asyncio
import math
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Import arm controller components
from dashboard.services.robotics.arm_controller import (
    ArmModel,
    ArmState,
    JointState,
    CartesianPose,
    DHParameter,
    ArmSpecification,
    KinematicsEngine,
    TrajectoryPlanner,
    TrajectoryPoint,
    BaseArmDriver,
    SimulatedArmDriver,
)

# Import drivers
from dashboard.services.robotics.drivers import (
    NiryoNed2Driver,
    NIRYO_NED2_SPEC,
    XArmLite6Driver,
    XARM_LITE6_SPEC,
)

# Import master scheduler
from dashboard.services.robotics.master_scheduler import (
    TaskType,
    TaskPriority,
    TaskStatus,
    AcknowledgmentType,
    RobotTask,
    TaskAcknowledgment,
    SynchronizedMotion,
    MasterScheduler,
    get_master_scheduler,
)

# Import OME integration
from dashboard.services.digital_twin.ome_registry import (
    OMEType,
    OMELifecycleState,
    CapabilityType,
    get_ome_registry,
    create_robotic_arm_ome,
    create_niryo_ned2_ome,
    create_xarm_lite6_ome,
    create_end_effector_ome,
)


# ==================== Fixtures ====================

@pytest.fixture
def niryo_spec():
    """Get Niryo Ned2 arm specification."""
    return NIRYO_NED2_SPEC


@pytest.fixture
def xarm_spec():
    """Get xArm Lite 6 arm specification."""
    return XARM_LITE6_SPEC


@pytest.fixture
def niryo_driver():
    """Create Niryo Ned2 driver instance."""
    return NiryoNed2Driver(arm_id="niryo-001")


@pytest.fixture
def xarm_driver():
    """Create xArm Lite 6 driver instance."""
    return XArmLite6Driver(arm_id="xarm-001")


@pytest.fixture
def kinematics_engine(niryo_spec):
    """Create kinematics engine for testing."""
    return KinematicsEngine(niryo_spec)


@pytest.fixture
def trajectory_planner(niryo_spec):
    """Create trajectory planner for testing."""
    return TrajectoryPlanner(niryo_spec)


@pytest.fixture
def master_scheduler():
    """Create fresh master scheduler instance."""
    scheduler = MasterScheduler()
    yield scheduler
    # Cleanup
    scheduler.stop()


@pytest.fixture
def ome_registry():
    """Get fresh OME registry."""
    registry = get_ome_registry()
    # Clear any existing entries for test isolation
    for ome_id in list(registry._omes.keys()):
        registry.delete(ome_id)
    return registry


# ==================== Arm Specification Tests ====================

class TestArmSpecification:
    """Test arm specification data classes."""

    def test_niryo_ned2_spec_values(self, niryo_spec):
        """Test Niryo Ned2 specification values."""
        assert niryo_spec.model == ArmModel.NIRYO_NED2
        assert niryo_spec.dof == 6
        assert niryo_spec.max_reach_mm == 440.0
        assert niryo_spec.max_payload_g == 300.0
        assert niryo_spec.repeatability_mm == 0.5
        assert niryo_spec.is_collaborative is True
        assert len(niryo_spec.dh_parameters) == 6

    def test_xarm_lite6_spec_values(self, xarm_spec):
        """Test xArm Lite 6 specification values."""
        assert xarm_spec.model == ArmModel.XARM_LITE6
        assert xarm_spec.dof == 6
        assert xarm_spec.max_reach_mm == 440.0
        assert xarm_spec.max_payload_g == 500.0  # Higher than Ned2
        assert xarm_spec.repeatability_mm == 0.1  # More precise
        assert xarm_spec.is_collaborative is True

    def test_dh_parameters_structure(self, niryo_spec):
        """Test DH parameters have correct structure."""
        for i, dh in enumerate(niryo_spec.dh_parameters):
            assert isinstance(dh, DHParameter)
            assert isinstance(dh.theta_offset, float)
            assert isinstance(dh.d, float)
            assert isinstance(dh.a, float)
            assert isinstance(dh.alpha, float)

    def test_joint_limits(self, niryo_spec):
        """Test joint limits are properly defined."""
        assert len(niryo_spec.joint_limits_min) == 6
        assert len(niryo_spec.joint_limits_max) == 6

        for i in range(6):
            assert niryo_spec.joint_limits_min[i] < niryo_spec.joint_limits_max[i]

    def test_max_velocities(self, niryo_spec):
        """Test max velocities are positive."""
        assert len(niryo_spec.max_joint_velocities) == 6
        for vel in niryo_spec.max_joint_velocities:
            assert vel > 0


# ==================== Kinematics Tests ====================

class TestKinematicsEngine:
    """Test kinematics calculations."""

    def test_forward_kinematics_home_position(self, kinematics_engine):
        """Test FK at home position (all zeros)."""
        home_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        pose = kinematics_engine.forward_kinematics(home_joints)

        assert isinstance(pose, CartesianPose)
        assert pose.x is not None
        assert pose.y is not None
        assert pose.z is not None

    def test_forward_kinematics_known_positions(self, kinematics_engine):
        """Test FK with known joint configurations."""
        # Test various configurations
        test_configs = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [math.pi/4, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, math.pi/4, 0.0, 0.0, 0.0, 0.0],
        ]

        for config in test_configs:
            pose = kinematics_engine.forward_kinematics(config)
            assert pose is not None
            assert not math.isnan(pose.x)
            assert not math.isnan(pose.y)
            assert not math.isnan(pose.z)

    def test_inverse_kinematics_reachable(self, kinematics_engine):
        """Test IK for reachable positions."""
        # Start with home position FK
        home_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        target_pose = kinematics_engine.forward_kinematics(home_joints)

        # IK should return to home position
        result_joints = kinematics_engine.inverse_kinematics(target_pose)

        if result_joints is not None:
            # Verify FK of result matches target
            result_pose = kinematics_engine.forward_kinematics(result_joints)
            assert abs(result_pose.x - target_pose.x) < 1.0  # 1mm tolerance
            assert abs(result_pose.y - target_pose.y) < 1.0
            assert abs(result_pose.z - target_pose.z) < 1.0

    def test_jacobian_calculation(self, kinematics_engine):
        """Test Jacobian matrix calculation."""
        joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        jacobian = kinematics_engine.calculate_jacobian(joints)

        assert jacobian is not None
        assert jacobian.shape == (6, 6)

    def test_singularity_detection(self, kinematics_engine):
        """Test singularity detection."""
        # Singularity typically occurs when arm is fully extended
        extended_joints = [0.0, math.pi/2, 0.0, 0.0, 0.0, 0.0]
        is_singular = kinematics_engine.check_singularity(extended_joints)

        assert isinstance(is_singular, bool)


# ==================== Trajectory Planning Tests ====================

class TestTrajectoryPlanner:
    """Test trajectory planning."""

    def test_plan_joint_trajectory(self, trajectory_planner):
        """Test joint-space trajectory planning."""
        start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        end = [0.5, 0.3, -0.2, 0.1, 0.4, -0.1]

        trajectory = trajectory_planner.plan_joint_trajectory(
            start_joints=start,
            end_joints=end,
            duration=2.0,
            num_points=100
        )

        assert len(trajectory) == 100
        assert all(isinstance(p, TrajectoryPoint) for p in trajectory)

        # First point should match start
        assert trajectory[0].positions == pytest.approx(start, abs=0.01)

        # Last point should match end
        assert trajectory[-1].positions == pytest.approx(end, abs=0.01)

    def test_trajectory_velocity_limits(self, trajectory_planner):
        """Test trajectory respects velocity limits."""
        start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        end = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

        trajectory = trajectory_planner.plan_joint_trajectory(
            start_joints=start,
            end_joints=end,
            duration=2.0,
            num_points=100
        )

        # Check velocity limits
        for point in trajectory:
            if point.velocities:
                for vel in point.velocities:
                    assert abs(vel) <= trajectory_planner.spec.max_joint_velocities[0] * 1.1

    def test_quintic_interpolation(self, trajectory_planner):
        """Test quintic polynomial interpolation."""
        start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        end = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]

        trajectory = trajectory_planner.plan_joint_trajectory(
            start_joints=start,
            end_joints=end,
            duration=2.0,
            num_points=50,
            interpolation="quintic"
        )

        # Quintic should have smooth acceleration (zero at endpoints)
        assert trajectory[0].accelerations == pytest.approx([0.0] * 6, abs=0.1)
        assert trajectory[-1].accelerations == pytest.approx([0.0] * 6, abs=0.1)


# ==================== Driver Tests ====================

class TestNiryoNed2Driver:
    """Test Niryo Ned2 driver."""

    def test_driver_initialization(self, niryo_driver):
        """Test driver initializes correctly."""
        assert niryo_driver.arm_id == "niryo-001"
        assert niryo_driver.spec.model == ArmModel.NIRYO_NED2
        assert niryo_driver.state.is_enabled is False

    @pytest.mark.asyncio
    async def test_enable_disable(self, niryo_driver):
        """Test arm enable/disable."""
        await niryo_driver.enable()
        assert niryo_driver.state.is_enabled is True
        assert niryo_driver.state.status == "idle"

        await niryo_driver.disable()
        assert niryo_driver.state.is_enabled is False
        assert niryo_driver.state.status == "disabled"

    @pytest.mark.asyncio
    async def test_home_command(self, niryo_driver):
        """Test home command."""
        await niryo_driver.enable()
        await niryo_driver.home()

        assert niryo_driver.state.joint_positions == pytest.approx([0.0] * 6, abs=0.01)
        assert niryo_driver.state.is_homed is True

    @pytest.mark.asyncio
    async def test_move_joints(self, niryo_driver):
        """Test joint movement."""
        await niryo_driver.enable()

        target = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        await niryo_driver.move_joints(target, velocity_scale=0.5)

        assert niryo_driver.state.joint_positions == pytest.approx(target, abs=0.01)

    @pytest.mark.asyncio
    async def test_joint_limits_enforcement(self, niryo_driver):
        """Test joint limits are enforced."""
        await niryo_driver.enable()

        # Try to move beyond limits
        invalid_target = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]  # Way beyond limits

        with pytest.raises(ValueError, match="joint limits"):
            await niryo_driver.move_joints(invalid_target)

    @pytest.mark.asyncio
    async def test_gripper_control(self, niryo_driver):
        """Test gripper control."""
        await niryo_driver.enable()

        # Open gripper
        await niryo_driver.open_gripper()
        assert niryo_driver.state.gripper_position == pytest.approx(1.0, abs=0.1)

        # Close gripper
        await niryo_driver.close_gripper()
        assert niryo_driver.state.gripper_position == pytest.approx(0.0, abs=0.1)


class TestXArmLite6Driver:
    """Test xArm Lite 6 driver."""

    def test_driver_initialization(self, xarm_driver):
        """Test driver initializes correctly."""
        assert xarm_driver.arm_id == "xarm-001"
        assert xarm_driver.spec.model == ArmModel.XARM_LITE6
        assert xarm_driver.state.is_enabled is False

    @pytest.mark.asyncio
    async def test_enable_disable(self, xarm_driver):
        """Test arm enable/disable."""
        await xarm_driver.enable()
        assert xarm_driver.state.is_enabled is True

        await xarm_driver.disable()
        assert xarm_driver.state.is_enabled is False

    @pytest.mark.asyncio
    async def test_linear_move(self, xarm_driver):
        """Test linear (Cartesian) movement."""
        await xarm_driver.enable()
        await xarm_driver.home()

        target_pose = CartesianPose(x=200.0, y=100.0, z=150.0, rx=0.0, ry=0.0, rz=0.0)
        await xarm_driver.move_linear(target_pose, velocity_scale=0.3)

        # Verify end position via FK
        current_pose = xarm_driver.get_tcp_pose()
        assert abs(current_pose.x - target_pose.x) < 5.0  # 5mm tolerance
        assert abs(current_pose.y - target_pose.y) < 5.0
        assert abs(current_pose.z - target_pose.z) < 5.0

    @pytest.mark.asyncio
    async def test_emergency_stop(self, xarm_driver):
        """Test emergency stop."""
        await xarm_driver.enable()

        # Start a movement in background (would be a longer movement)
        await xarm_driver.emergency_stop()

        assert xarm_driver.state.status == "stopped"
        assert xarm_driver.state.is_enabled is False


# ==================== Master Scheduler Tests ====================

class TestMasterScheduler:
    """Test master scheduler with acknowledgments."""

    def test_scheduler_initialization(self, master_scheduler):
        """Test scheduler initializes correctly."""
        assert len(master_scheduler.registered_arms) == 0
        assert master_scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_register_arm(self, master_scheduler, niryo_driver):
        """Test arm registration."""
        master_scheduler.register_arm("niryo-001", niryo_driver)

        assert "niryo-001" in master_scheduler.registered_arms
        assert master_scheduler.registered_arms["niryo-001"] == niryo_driver

    @pytest.mark.asyncio
    async def test_schedule_task(self, master_scheduler, niryo_driver):
        """Test task scheduling."""
        master_scheduler.register_arm("niryo-001", niryo_driver)

        task = RobotTask(
            task_id="task-001",
            arm_id="niryo-001",
            task_type=TaskType.MOVE_JOINT,
            priority=TaskPriority.NORMAL,
            parameters={'target': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
        )

        task_id = await master_scheduler.schedule_task(task)
        assert task_id == "task-001"
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_task_acknowledgment_flow(self, master_scheduler, niryo_driver):
        """Test acknowledgment flow: received -> started -> completed."""
        master_scheduler.register_arm("niryo-001", niryo_driver)
        await niryo_driver.enable()

        acks_received = []

        def ack_callback(ack: TaskAcknowledgment):
            acks_received.append(ack)

        task = RobotTask(
            task_id="task-002",
            arm_id="niryo-001",
            task_type=TaskType.HOME,
            priority=TaskPriority.HIGH,
            ack_callback=ack_callback
        )

        await master_scheduler.schedule_task(task)
        await master_scheduler.execute_next()

        # Should have received acknowledgments
        ack_types = [ack.ack_type for ack in acks_received]
        assert AcknowledgmentType.RECEIVED in ack_types
        assert AcknowledgmentType.STARTED in ack_types
        assert AcknowledgmentType.COMPLETED in ack_types

    @pytest.mark.asyncio
    async def test_task_priority_ordering(self, master_scheduler, niryo_driver):
        """Test high priority tasks execute first."""
        master_scheduler.register_arm("niryo-001", niryo_driver)

        # Schedule low priority first
        task_low = RobotTask(
            task_id="low-priority",
            arm_id="niryo-001",
            task_type=TaskType.HOME,
            priority=TaskPriority.LOW
        )

        # Then high priority
        task_high = RobotTask(
            task_id="high-priority",
            arm_id="niryo-001",
            task_type=TaskType.HOME,
            priority=TaskPriority.CRITICAL
        )

        await master_scheduler.schedule_task(task_low)
        await master_scheduler.schedule_task(task_high)

        # High priority should be first
        next_task = master_scheduler.peek_next_task("niryo-001")
        assert next_task.task_id == "high-priority"

    @pytest.mark.asyncio
    async def test_synchronized_motion(self, master_scheduler, niryo_driver, xarm_driver):
        """Test synchronized multi-arm motion."""
        master_scheduler.register_arm("niryo-001", niryo_driver)
        master_scheduler.register_arm("xarm-001", xarm_driver)

        await niryo_driver.enable()
        await xarm_driver.enable()

        sync_motion = SynchronizedMotion(
            motion_id="sync-001",
            arm_ids=["niryo-001", "xarm-001"],
            tasks={
                "niryo-001": RobotTask(
                    task_id="sync-task-1",
                    arm_id="niryo-001",
                    task_type=TaskType.MOVE_JOINT,
                    parameters={'target': [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]}
                ),
                "xarm-001": RobotTask(
                    task_id="sync-task-2",
                    arm_id="xarm-001",
                    task_type=TaskType.MOVE_JOINT,
                    parameters={'target': [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]}
                )
            }
        )

        await master_scheduler.schedule_synchronized_motion(sync_motion)

        # Both tasks should be pending
        assert sync_motion.tasks["niryo-001"].status == TaskStatus.PENDING
        assert sync_motion.tasks["xarm-001"].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_task_failure_handling(self, master_scheduler, niryo_driver):
        """Test failed task handling with acknowledgment."""
        master_scheduler.register_arm("niryo-001", niryo_driver)

        acks_received = []

        def ack_callback(ack: TaskAcknowledgment):
            acks_received.append(ack)

        # Schedule task with invalid parameters to cause failure
        task = RobotTask(
            task_id="fail-task",
            arm_id="niryo-001",
            task_type=TaskType.MOVE_JOINT,
            parameters={'target': [99.0] * 6},  # Invalid - beyond limits
            ack_callback=ack_callback
        )

        await master_scheduler.schedule_task(task)

        try:
            await master_scheduler.execute_next()
        except Exception:
            pass

        # Should have FAILED acknowledgment
        ack_types = [ack.ack_type for ack in acks_received]
        assert AcknowledgmentType.FAILED in ack_types or task.status == TaskStatus.FAILED


# ==================== OME Integration Tests ====================

class TestRoboticArmOME:
    """Test OME integration for robotic arms."""

    def test_create_robotic_arm_ome(self, ome_registry):
        """Test creating generic robotic arm OME."""
        arm_ome = create_robotic_arm_ome(
            name="Test Arm",
            manufacturer="TestCo",
            model="Test-6",
            dof=6,
            reach_mm=400.0,
            payload_g=250.0
        )

        assert arm_ome.ome_type == OMEType.ROBOTIC_ARM
        assert arm_ome.name == "Test Arm"
        assert CapabilityType.PICK_AND_PLACE in arm_ome.static_attributes.capabilities
        assert CapabilityType.MANIPULATION in arm_ome.static_attributes.capabilities

    def test_create_niryo_ned2_ome(self, ome_registry):
        """Test creating Niryo Ned2 OME."""
        arm_ome = create_niryo_ned2_ome(
            name="Production Ned2",
            position={'x': 100, 'y': 200, 'z': 0}
        )

        assert arm_ome.ome_type == OMEType.ROBOTIC_ARM
        assert "Niryo" in arm_ome.description
        assert "Ned2" in arm_ome.description
        assert arm_ome.custom_attributes['payload_g'] == 300.0
        assert arm_ome.custom_attributes['is_collaborative'] is True
        assert "niryo_ned2" in arm_ome.tags

    def test_create_xarm_lite6_ome(self, ome_registry):
        """Test creating xArm Lite 6 OME."""
        arm_ome = create_xarm_lite6_ome(
            name="Assembly xArm",
            position={'x': 500, 'y': 200, 'z': 0}
        )

        assert arm_ome.ome_type == OMEType.ROBOTIC_ARM
        assert "UFactory" in arm_ome.description
        assert arm_ome.custom_attributes['payload_g'] == 500.0
        assert arm_ome.custom_attributes['repeatability_mm'] == 0.1
        assert "xarm_lite6" in arm_ome.tags

    def test_create_end_effector_ome(self, ome_registry):
        """Test creating end effector attached to arm."""
        # First create parent arm
        arm_ome = create_niryo_ned2_ome(name="Parent Arm")
        ome_registry.register(arm_ome)

        # Create gripper attached to arm
        gripper_ome = create_end_effector_ome(
            name="Standard Gripper",
            effector_type="gripper",
            parent_arm_id=arm_ome.id,
            grip_force_n=15.0,
            stroke_mm=35.0
        )

        assert gripper_ome.ome_type == OMEType.END_EFFECTOR
        assert gripper_ome.parent_id == arm_ome.id
        assert gripper_ome.custom_attributes['grip_force_n'] == 15.0

    def test_ome_lifecycle_transitions(self, ome_registry):
        """Test OME lifecycle for arm."""
        arm_ome = create_niryo_ned2_ome(name="Lifecycle Test Arm")
        ome_registry.register(arm_ome)

        # Should start in DESIGN
        assert arm_ome.lifecycle_state == OMELifecycleState.DESIGN

        # Transition to COMMISSIONING
        ome_registry.transition_lifecycle(
            arm_ome.id,
            OMELifecycleState.COMMISSIONING,
            reason="Installation complete"
        )
        assert arm_ome.lifecycle_state == OMELifecycleState.COMMISSIONING

        # Transition to ACTIVE
        ome_registry.transition_lifecycle(
            arm_ome.id,
            OMELifecycleState.ACTIVE,
            reason="Calibration passed"
        )
        assert arm_ome.lifecycle_state == OMELifecycleState.ACTIVE

        # Verify history
        assert len(arm_ome.lifecycle_history) == 2

    def test_ome_dynamic_attributes_update(self, ome_registry):
        """Test updating dynamic attributes for arm."""
        arm_ome = create_niryo_ned2_ome(name="Dynamic Test Arm")
        ome_registry.register(arm_ome)

        # Update joint positions
        ome_registry.update_dynamic_attributes(arm_ome.id, {
            'status': 'moving',
            'positions': {
                'j1': 0.5, 'j2': 0.3, 'j3': -0.2,
                'j4': 0.1, 'j5': 0.4, 'j6': -0.1
            },
            'health_score': 95.5
        })

        assert arm_ome.dynamic_attributes.status == 'moving'
        assert arm_ome.dynamic_attributes.positions['j1'] == 0.5
        assert arm_ome.dynamic_attributes.health_score == 95.5

    def test_ome_to_unity_dict(self, ome_registry):
        """Test OME conversion to Unity-compatible format."""
        arm_ome = create_xarm_lite6_ome(
            name="Unity Arm",
            position={'x': 300, 'y': 100, 'z': 50}
        )

        unity_dict = arm_ome.to_unity_dict()

        assert 'id' in unity_dict
        assert unity_dict['name'] == "Unity Arm"
        assert unity_dict['type'] == 'robotic_arm'
        assert 'geometry' in unity_dict
        assert unity_dict['geometry']['position']['x'] == 300

    def test_query_arms_by_type(self, ome_registry):
        """Test querying arms by OME type."""
        # Create multiple arms
        arm1 = create_niryo_ned2_ome(name="Arm 1")
        arm2 = create_xarm_lite6_ome(name="Arm 2")

        ome_registry.register(arm1)
        ome_registry.register(arm2)

        # Query by type
        arms = ome_registry.get_by_type(OMEType.ROBOTIC_ARM)

        assert len(arms) == 2
        arm_names = [a.name for a in arms]
        assert "Arm 1" in arm_names
        assert "Arm 2" in arm_names


# ==================== Integration Tests ====================

class TestFullIntegration:
    """Full integration tests combining all components."""

    @pytest.mark.asyncio
    async def test_full_pick_and_place_workflow(self, master_scheduler, niryo_driver, ome_registry):
        """Test complete pick-and-place workflow."""
        # 1. Create OME
        arm_ome = create_niryo_ned2_ome(name="Pick-Place Arm")
        ome_registry.register(arm_ome)

        # 2. Transition to active
        ome_registry.transition_lifecycle(arm_ome.id, OMELifecycleState.COMMISSIONING)
        ome_registry.transition_lifecycle(arm_ome.id, OMELifecycleState.ACTIVE)

        # 3. Register driver with scheduler
        master_scheduler.register_arm(arm_ome.id, niryo_driver)

        # 4. Enable arm
        await niryo_driver.enable()

        # 5. Schedule pick sequence
        pick_task = RobotTask(
            task_id="pick-001",
            arm_id=arm_ome.id,
            task_type=TaskType.PICK,
            parameters={
                'position': [0.2, 0.1, 0.15, 0.0, 0.0, 0.0],
                'approach_height': 50.0
            }
        )

        await master_scheduler.schedule_task(pick_task)

        # 6. Execute and verify
        await master_scheduler.execute_next()

        # Update OME with arm state
        ome_registry.update_dynamic_attributes(arm_ome.id, {
            'status': niryo_driver.state.status,
            'positions': {f'j{i+1}': p for i, p in enumerate(niryo_driver.state.joint_positions)}
        })

        assert arm_ome.dynamic_attributes.status in ['idle', 'completed']

    @pytest.mark.asyncio
    async def test_multi_arm_coordination(self, ome_registry):
        """Test coordinating multiple arms."""
        scheduler = MasterScheduler()

        # Create two arms
        niryo = NiryoNed2Driver(arm_id="niryo-coord")
        xarm = XArmLite6Driver(arm_id="xarm-coord")

        niryo_ome = create_niryo_ned2_ome(name="Niryo Coord", position={'x': 0, 'y': 0, 'z': 0})
        xarm_ome = create_xarm_lite6_ome(name="xArm Coord", position={'x': 500, 'y': 0, 'z': 0})

        ome_registry.register(niryo_ome)
        ome_registry.register(xarm_ome)

        scheduler.register_arm(niryo_ome.id, niryo)
        scheduler.register_arm(xarm_ome.id, xarm)

        await niryo.enable()
        await xarm.enable()

        # Schedule synchronized motion
        sync = SynchronizedMotion(
            motion_id="coord-001",
            arm_ids=[niryo_ome.id, xarm_ome.id],
            tasks={
                niryo_ome.id: RobotTask(
                    task_id="niryo-move",
                    arm_id=niryo_ome.id,
                    task_type=TaskType.HOME
                ),
                xarm_ome.id: RobotTask(
                    task_id="xarm-move",
                    arm_id=xarm_ome.id,
                    task_type=TaskType.HOME
                )
            }
        )

        await scheduler.schedule_synchronized_motion(sync)

        # Verify both registered
        assert len(scheduler.registered_arms) == 2

        # Cleanup
        scheduler.stop()


# ==================== Performance Tests ====================

class TestPerformance:
    """Performance benchmarks."""

    def test_forward_kinematics_speed(self, kinematics_engine):
        """Benchmark FK calculation speed."""
        import time

        joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            kinematics_engine.forward_kinematics(joints)
        elapsed = time.time() - start

        # Should complete 1000 FK calculations in under 1 second
        assert elapsed < 1.0
        fk_per_second = iterations / elapsed
        print(f"\nFK calculations per second: {fk_per_second:.0f}")

    def test_trajectory_planning_speed(self, trajectory_planner):
        """Benchmark trajectory planning speed."""
        import time

        start_pos = [0.0] * 6
        end_pos = [0.5] * 6
        iterations = 100

        start = time.time()
        for _ in range(iterations):
            trajectory_planner.plan_joint_trajectory(
                start_joints=start_pos,
                end_joints=end_pos,
                duration=2.0,
                num_points=100
            )
        elapsed = time.time() - start

        # Should plan 100 trajectories in under 5 seconds
        assert elapsed < 5.0
        plans_per_second = iterations / elapsed
        print(f"\nTrajectory plans per second: {plans_per_second:.1f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
