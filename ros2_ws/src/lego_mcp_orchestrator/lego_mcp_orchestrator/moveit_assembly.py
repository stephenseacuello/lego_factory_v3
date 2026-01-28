#!/usr/bin/env python3
"""
LEGO MCP MoveIt2 Assembly Planner

Provides motion planning for LEGO brick assembly using MoveIt2.
Handles pick-and-place operations with collision avoidance.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from geometry_msgs.msg import Pose, PoseStamped, Point, Quaternion
from sensor_msgs.msg import JointState

# Try to import MoveIt2 interfaces
try:
    from moveit_msgs.msg import (
        RobotState, RobotTrajectory,
        PlanningScene, CollisionObject,
        AttachedCollisionObject,
        Constraints, OrientationConstraint, PositionConstraint,
    )
    from moveit_msgs.srv import GetPlanningScene, GetCartesianPath
    from moveit_msgs.action import MoveGroup, ExecuteTrajectory
    from shape_msgs.msg import SolidPrimitive
    MOVEIT_AVAILABLE = True
except ImportError:
    MOVEIT_AVAILABLE = False


class AssemblyPhase(Enum):
    """Phases of a pick-and-place operation."""
    IDLE = 'idle'
    APPROACH_PICK = 'approach_pick'
    PICK = 'pick'
    RETREAT_PICK = 'retreat_pick'
    APPROACH_PLACE = 'approach_place'
    PLACE = 'place'
    RETREAT_PLACE = 'retreat_place'
    COMPLETE = 'complete'
    FAILED = 'failed'


@dataclass
class BrickPose:
    """LEGO brick pose with approach vectors."""
    brick_id: str
    position: Tuple[float, float, float]
    orientation: Tuple[float, float, float, float]  # quaternion xyzw
    approach_distance: float = 0.05  # meters
    grasp_depth: float = 0.01  # how far into brick to grasp


@dataclass
class AssemblyStep:
    """Single assembly step."""
    step_id: str
    brick_id: str
    pick_pose: BrickPose
    place_pose: BrickPose
    assigned_robot: str = 'ned2'
    status: AssemblyPhase = AssemblyPhase.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MoveItAssemblyPlanner(Node):
    """
    MoveIt2-based assembly planner for LEGO brick operations.

    Features:
    - Pick-and-place motion planning
    - Collision-aware trajectory planning
    - Multi-robot coordination
    - Gripper control integration
    - Path constraints for safe motion
    """

    def __init__(self):
        super().__init__('moveit_assembly_planner')

        # Parameters
        self.declare_parameter('planning_group_ned2', 'ned2_arm')
        self.declare_parameter('planning_group_xarm', 'xarm_arm')
        self.declare_parameter('planning_time', 5.0)
        self.declare_parameter('max_velocity_scaling', 0.5)
        self.declare_parameter('max_acceleration_scaling', 0.5)
        self.declare_parameter('cartesian_step_size', 0.005)
        self.declare_parameter('cartesian_jump_threshold', 0.0)

        self._planning_group_ned2 = self.get_parameter('planning_group_ned2').value
        self._planning_group_xarm = self.get_parameter('planning_group_xarm').value
        self._planning_time = self.get_parameter('planning_time').value
        self._vel_scaling = self.get_parameter('max_velocity_scaling').value
        self._accel_scaling = self.get_parameter('max_acceleration_scaling').value
        self._cartesian_step = self.get_parameter('cartesian_step_size').value
        self._cartesian_jump = self.get_parameter('cartesian_jump_threshold').value

        # State
        self._current_step: Optional[AssemblyStep] = None
        self._attached_object: Optional[str] = None
        self._joint_states: Dict[str, JointState] = {}

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Action clients for MoveIt
        if MOVEIT_AVAILABLE:
            self._move_group_ned2 = ActionClient(
                self, MoveGroup, '/ned2/move_action',
                callback_group=self._cb_group
            )
            self._move_group_xarm = ActionClient(
                self, MoveGroup, '/xarm/move_action',
                callback_group=self._cb_group
            )
            self._execute_ned2 = ActionClient(
                self, ExecuteTrajectory, '/ned2/execute_trajectory',
                callback_group=self._cb_group
            )
            self._execute_xarm = ActionClient(
                self, ExecuteTrajectory, '/xarm/execute_trajectory',
                callback_group=self._cb_group
            )

        # Service clients
        if MOVEIT_AVAILABLE:
            self._get_scene_ned2 = self.create_client(
                GetPlanningScene, '/ned2/get_planning_scene'
            )
            self._get_scene_xarm = self.create_client(
                GetPlanningScene, '/xarm/get_planning_scene'
            )

        # Subscribers
        self.create_subscription(
            JointState,
            '/ned2/joint_states',
            lambda msg: self._on_joint_states('ned2', msg),
            10
        )
        self.create_subscription(
            JointState,
            '/xarm/joint_states',
            lambda msg: self._on_joint_states('xarm', msg),
            10
        )

        self.create_subscription(
            String,
            '/assembly/command',
            self._on_assembly_command,
            10,
            callback_group=self._cb_group
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/assembly/status',
            10
        )

        self._trajectory_pub = self.create_publisher(
            String,
            '/assembly/trajectory',
            10
        )

        if MOVEIT_AVAILABLE:
            self._scene_pub = self.create_publisher(
                PlanningScene,
                '/planning_scene',
                10
            )

        self.get_logger().info(
            f"MoveIt Assembly Planner initialized (MoveIt available: {MOVEIT_AVAILABLE})"
        )

    def _on_joint_states(self, robot: str, msg: JointState):
        """Store joint states."""
        self._joint_states[robot] = msg

    def _on_assembly_command(self, msg: String):
        """Handle assembly command."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'pick_place':
                step = self._parse_assembly_step(data)
                self._execute_pick_place(step)

            elif command == 'move_to_pose':
                robot = data.get('robot', 'ned2')
                pose = self._parse_pose(data.get('pose', {}))
                self._move_to_pose(robot, pose)

            elif command == 'move_to_named':
                robot = data.get('robot', 'ned2')
                name = data.get('named_pose', 'home')
                self._move_to_named(robot, name)

            elif command == 'gripper':
                robot = data.get('robot', 'ned2')
                action = data.get('action', 'close')
                self._control_gripper(robot, action)

        except Exception as e:
            self.get_logger().error(f"Assembly command failed: {e}")
            self._publish_status('error', str(e))

    def _parse_assembly_step(self, data: Dict) -> AssemblyStep:
        """Parse assembly step from JSON data."""
        return AssemblyStep(
            step_id=data.get('step_id', f"step_{datetime.now().timestamp()}"),
            brick_id=data.get('brick_id', 'brick_2x4'),
            pick_pose=BrickPose(
                brick_id=data.get('brick_id', 'brick_2x4'),
                position=tuple(data.get('pick_position', [0.3, 0.4, 0.78])),
                orientation=tuple(data.get('pick_orientation', [0, 0, 0, 1])),
            ),
            place_pose=BrickPose(
                brick_id=data.get('brick_id', 'brick_2x4'),
                position=tuple(data.get('place_position', [0.6, 0.4, 0.78])),
                orientation=tuple(data.get('place_orientation', [0, 0, 0, 1])),
            ),
            assigned_robot=data.get('robot', 'ned2'),
        )

    def _parse_pose(self, data: Dict) -> Pose:
        """Parse pose from JSON data."""
        pose = Pose()
        pos = data.get('position', [0, 0, 0])
        pose.position.x = pos[0]
        pose.position.y = pos[1]
        pose.position.z = pos[2]

        ori = data.get('orientation', [0, 0, 0, 1])
        pose.orientation.x = ori[0]
        pose.orientation.y = ori[1]
        pose.orientation.z = ori[2]
        pose.orientation.w = ori[3]

        return pose

    async def _execute_pick_place(self, step: AssemblyStep):
        """Execute a complete pick-and-place operation."""
        self._current_step = step
        step.started_at = datetime.now()
        step.status = AssemblyPhase.APPROACH_PICK

        robot = step.assigned_robot
        self._publish_status('started', f"Starting pick-place for {step.brick_id}")

        try:
            # 1. Approach pick position
            approach_pose = self._compute_approach_pose(step.pick_pose)
            success = await self._execute_cartesian_path(robot, [approach_pose])
            if not success:
                raise Exception("Failed to approach pick position")
            step.status = AssemblyPhase.PICK

            # 2. Move down to pick
            pick_pose = self._brick_pose_to_ros(step.pick_pose)
            success = await self._execute_cartesian_path(robot, [pick_pose])
            if not success:
                raise Exception("Failed to reach pick position")

            # 3. Close gripper
            self._control_gripper(robot, 'close')
            await self._wait_for_gripper(robot)

            # 4. Attach object to robot
            self._attach_brick(robot, step.brick_id, step.pick_pose)
            step.status = AssemblyPhase.RETREAT_PICK

            # 5. Retreat from pick
            success = await self._execute_cartesian_path(robot, [approach_pose])
            if not success:
                raise Exception("Failed to retreat from pick")
            step.status = AssemblyPhase.APPROACH_PLACE

            # 6. Approach place position
            place_approach = self._compute_approach_pose(step.place_pose)
            success = await self._move_to_pose_async(robot, place_approach)
            if not success:
                raise Exception("Failed to approach place position")
            step.status = AssemblyPhase.PLACE

            # 7. Move down to place
            place_pose = self._brick_pose_to_ros(step.place_pose)
            success = await self._execute_cartesian_path(robot, [place_pose])
            if not success:
                raise Exception("Failed to reach place position")

            # 8. Open gripper
            self._control_gripper(robot, 'open')
            await self._wait_for_gripper(robot)

            # 9. Detach object
            self._detach_brick(robot)
            step.status = AssemblyPhase.RETREAT_PLACE

            # 10. Retreat from place
            success = await self._execute_cartesian_path(robot, [place_approach])
            if not success:
                raise Exception("Failed to retreat from place")

            # Success
            step.status = AssemblyPhase.COMPLETE
            step.completed_at = datetime.now()
            self._publish_status('complete', f"Completed pick-place for {step.brick_id}")

        except Exception as e:
            step.status = AssemblyPhase.FAILED
            self.get_logger().error(f"Pick-place failed: {e}")
            self._publish_status('failed', str(e))

        finally:
            self._current_step = None

    def _compute_approach_pose(self, brick_pose: BrickPose) -> Pose:
        """Compute approach pose above the brick."""
        pose = Pose()
        pose.position.x = brick_pose.position[0]
        pose.position.y = brick_pose.position[1]
        pose.position.z = brick_pose.position[2] + brick_pose.approach_distance
        pose.orientation.x = brick_pose.orientation[0]
        pose.orientation.y = brick_pose.orientation[1]
        pose.orientation.z = brick_pose.orientation[2]
        pose.orientation.w = brick_pose.orientation[3]
        return pose

    def _brick_pose_to_ros(self, brick_pose: BrickPose) -> Pose:
        """Convert BrickPose to ROS Pose."""
        pose = Pose()
        pose.position.x = brick_pose.position[0]
        pose.position.y = brick_pose.position[1]
        pose.position.z = brick_pose.position[2]
        pose.orientation.x = brick_pose.orientation[0]
        pose.orientation.y = brick_pose.orientation[1]
        pose.orientation.z = brick_pose.orientation[2]
        pose.orientation.w = brick_pose.orientation[3]
        return pose

    async def _move_to_pose_async(self, robot: str, pose: Pose) -> bool:
        """Move robot to target pose using MoveIt."""
        if not MOVEIT_AVAILABLE:
            self.get_logger().warn("MoveIt not available, simulating motion")
            await self._simulate_motion(robot, pose)
            return True

        planning_group = (
            self._planning_group_ned2 if robot == 'ned2'
            else self._planning_group_xarm
        )

        # Create goal
        goal = MoveGroup.Goal()
        goal.request.group_name = planning_group
        goal.request.allowed_planning_time = self._planning_time
        goal.request.max_velocity_scaling_factor = self._vel_scaling
        goal.request.max_acceleration_scaling_factor = self._accel_scaling

        # Set target pose
        goal.request.goal_constraints.append(
            self._create_pose_constraint(planning_group, pose)
        )

        # Send goal
        action_client = (
            self._move_group_ned2 if robot == 'ned2'
            else self._move_group_xarm
        )

        if not action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error(f"MoveGroup action server not available for {robot}")
            return False

        future = action_client.send_goal_async(goal)
        result = await future
        return result.accepted

    async def _execute_cartesian_path(self, robot: str, waypoints: List[Pose]) -> bool:
        """Execute Cartesian path through waypoints."""
        if not MOVEIT_AVAILABLE:
            self.get_logger().warn("MoveIt not available, simulating Cartesian path")
            for wp in waypoints:
                await self._simulate_motion(robot, wp)
            return True

        # In production, would use GetCartesianPath service
        # For now, execute each waypoint as pose goal
        for waypoint in waypoints:
            success = await self._move_to_pose_async(robot, waypoint)
            if not success:
                return False

        return True

    def _create_pose_constraint(self, group: str, pose: Pose) -> Constraints:
        """Create pose constraint for MoveIt planning."""
        if not MOVEIT_AVAILABLE:
            return None

        constraints = Constraints()

        # Position constraint
        pos_constraint = PositionConstraint()
        pos_constraint.header.frame_id = 'world'
        pos_constraint.link_name = f"{group.split('_')[0]}_tool0"
        pos_constraint.target_point_offset.x = 0
        pos_constraint.target_point_offset.y = 0
        pos_constraint.target_point_offset.z = 0

        # Bounding box around target
        primitive = SolidPrimitive()
        primitive.type = SolidPrimitive.BOX
        primitive.dimensions = [0.01, 0.01, 0.01]  # 1cm tolerance

        pos_constraint.constraint_region.primitives.append(primitive)

        region_pose = Pose()
        region_pose.position = pose.position
        region_pose.orientation.w = 1.0
        pos_constraint.constraint_region.primitive_poses.append(region_pose)

        constraints.position_constraints.append(pos_constraint)

        # Orientation constraint
        ori_constraint = OrientationConstraint()
        ori_constraint.header.frame_id = 'world'
        ori_constraint.link_name = f"{group.split('_')[0]}_tool0"
        ori_constraint.orientation = pose.orientation
        ori_constraint.absolute_x_axis_tolerance = 0.1
        ori_constraint.absolute_y_axis_tolerance = 0.1
        ori_constraint.absolute_z_axis_tolerance = 0.1
        ori_constraint.weight = 1.0

        constraints.orientation_constraints.append(ori_constraint)

        return constraints

    def _move_to_pose(self, robot: str, pose: Pose):
        """Synchronous wrapper for pose motion."""
        import asyncio
        asyncio.create_task(self._move_to_pose_async(robot, pose))

    def _move_to_named(self, robot: str, named_pose: str):
        """Move robot to named pose."""
        # Named poses are defined in SRDF
        self.get_logger().info(f"Moving {robot} to {named_pose}")

        # Publish trajectory command (actual motion handled by robot controller)
        trajectory = {
            'robot': robot,
            'type': 'named_pose',
            'pose': named_pose,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(trajectory)
        self._trajectory_pub.publish(msg)

    def _control_gripper(self, robot: str, action: str):
        """Control gripper open/close."""
        self.get_logger().info(f"Gripper {robot}: {action}")

        # Publish gripper command
        gripper_cmd = {
            'robot': robot,
            'action': action,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps({'gripper': gripper_cmd})
        self._trajectory_pub.publish(msg)

    async def _wait_for_gripper(self, robot: str, timeout: float = 2.0):
        """Wait for gripper action to complete."""
        import asyncio
        await asyncio.sleep(0.5)  # Simulated gripper delay

    def _attach_brick(self, robot: str, brick_id: str, pose: BrickPose):
        """Attach brick collision object to robot gripper."""
        if not MOVEIT_AVAILABLE:
            self._attached_object = brick_id
            return

        # Create attached collision object
        attached_obj = AttachedCollisionObject()
        attached_obj.link_name = f"{robot}_gripper"
        attached_obj.object.id = brick_id
        attached_obj.object.header.frame_id = f"{robot}_gripper"

        # LEGO 2x4 brick dimensions
        primitive = SolidPrimitive()
        primitive.type = SolidPrimitive.BOX
        primitive.dimensions = [0.032, 0.016, 0.0096]  # LEGO 2x4 size

        attached_obj.object.primitives.append(primitive)

        brick_pose = Pose()
        brick_pose.position.z = 0.005  # Offset below gripper
        brick_pose.orientation.w = 1.0
        attached_obj.object.primitive_poses.append(brick_pose)

        attached_obj.object.operation = CollisionObject.ADD

        # Publish to planning scene
        scene_msg = PlanningScene()
        scene_msg.robot_state.attached_collision_objects.append(attached_obj)
        scene_msg.is_diff = True
        self._scene_pub.publish(scene_msg)

        self._attached_object = brick_id

    def _detach_brick(self, robot: str):
        """Detach brick from robot gripper."""
        if not self._attached_object:
            return

        if MOVEIT_AVAILABLE:
            # Remove attached object
            attached_obj = AttachedCollisionObject()
            attached_obj.link_name = f"{robot}_gripper"
            attached_obj.object.id = self._attached_object
            attached_obj.object.operation = CollisionObject.REMOVE

            scene_msg = PlanningScene()
            scene_msg.robot_state.attached_collision_objects.append(attached_obj)
            scene_msg.is_diff = True
            self._scene_pub.publish(scene_msg)

        self._attached_object = None

    async def _simulate_motion(self, robot: str, target: Pose):
        """Simulate motion when MoveIt is not available."""
        import asyncio
        self.get_logger().debug(
            f"Simulating motion: {robot} -> "
            f"({target.position.x:.3f}, {target.position.y:.3f}, {target.position.z:.3f})"
        )
        await asyncio.sleep(0.5)  # Simulated motion time

    def _publish_status(self, status: str, message: str = ''):
        """Publish assembly status."""
        status_msg = {
            'status': status,
            'message': message,
            'current_step': self._current_step.step_id if self._current_step else None,
            'phase': self._current_step.status.value if self._current_step else 'idle',
            'attached_object': self._attached_object,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(status_msg)
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MoveItAssemblyPlanner()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
