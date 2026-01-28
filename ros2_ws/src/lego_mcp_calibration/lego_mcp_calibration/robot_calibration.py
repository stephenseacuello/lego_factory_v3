#!/usr/bin/env python3
"""
LEGO MCP Robot Base Calibration Node
Calibrate robot base position relative to world frame.

Uses fiducial markers (ArUco) on the workcell for reference.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import yaml

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from geometry_msgs.msg import Pose, TransformStamped
from sensor_msgs.msg import JointState

try:
    from tf2_ros import Buffer, TransformListener, StaticTransformBroadcaster
    TF2_AVAILABLE = True
except ImportError:
    TF2_AVAILABLE = False


@dataclass
class CalibrationResult:
    """Result of robot calibration."""
    robot_name: str
    base_to_world: Dict[str, List[float]]
    calibrated_at: datetime
    method: str
    error_mm: float = 0.0
    num_samples: int = 0


class RobotCalibrationNode(Node):
    """
    Calibrate robot base position relative to world frame.
    """

    def __init__(self):
        super().__init__('robot_calibration')

        # Parameters
        self.declare_parameter('calibration_method', 'touch_point')
        self.declare_parameter('num_calibration_points', 4)
        self.declare_parameter('calibration_dir', '/tmp/lego_mcp_calibration')

        self._method = self.get_parameter('calibration_method').value
        self._num_points = self.get_parameter('num_calibration_points').value
        self._calibration_dir = self.get_parameter('calibration_dir').value

        # Known marker positions in world frame
        self._marker_positions = {
            0: [0.0, 0.0, 0.0],      # Origin marker
            1: [1.0, 0.0, 0.0],      # X-axis marker
            2: [0.0, 1.0, 0.0],      # Y-axis marker
        }

        # Calibration state
        self._current_robot: str = ''
        self._touch_points: List[Dict[str, Any]] = []
        self._calibration_active = False

        # TF
        if TF2_AVAILABLE:
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self)
            self._static_broadcaster = StaticTransformBroadcaster(self)

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Joint state subscribers for robots
        for robot in ['ned2', 'xarm']:
            self.create_subscription(
                JointState,
                f'/{robot}/joint_states',
                lambda msg, r=robot: self._on_joint_states(r, msg),
                10
            )

        # Command subscriber
        self.create_subscription(
            String,
            '/calibration/command',
            self._on_command,
            10
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/calibration/status',
            10
        )

        self._result_pub = self.create_publisher(
            String,
            '/calibration/result',
            10
        )

        self.get_logger().info("Robot calibration node initialized")

    def _on_joint_states(self, robot_id: str, msg: JointState):
        """Store current joint states for calibration."""
        if self._calibration_active and self._current_robot == robot_id:
            self._current_joint_positions = list(msg.position)

    def _on_command(self, msg: String):
        """Handle calibration commands."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'start_calibration':
                self._start_calibration(data.get('robot', 'ned2'))

            elif command == 'record_point':
                self._record_touch_point(data.get('marker_id', 0))

            elif command == 'finish_calibration':
                self._finish_calibration()

            elif command == 'cancel':
                self._cancel_calibration()

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid command: {msg.data}")

    def _start_calibration(self, robot_name: str):
        """Start calibration process for a robot."""
        self._current_robot = robot_name
        self._touch_points = []
        self._calibration_active = True

        self.get_logger().info(f"Starting calibration for {robot_name}")
        self._publish_status('started', f"Calibrating {robot_name}")

    def _record_touch_point(self, marker_id: int):
        """Record a touch point at a known marker position."""
        if not self._calibration_active:
            return

        # Get current end-effector pose from FK
        ee_pose = self._compute_forward_kinematics()
        if ee_pose is None:
            self._publish_status('error', "Could not compute end-effector pose")
            return

        # Store touch point
        self._touch_points.append({
            'marker_id': marker_id,
            'world_position': self._marker_positions.get(marker_id, [0, 0, 0]),
            'ee_position': ee_pose[:3],
            'joint_positions': self._current_joint_positions.copy(),
            'timestamp': datetime.now().isoformat(),
        })

        self.get_logger().info(f"Recorded touch point {len(self._touch_points)} at marker {marker_id}")
        self._publish_status('point_recorded', f"Point {len(self._touch_points)}/{self._num_points}")

    def _finish_calibration(self):
        """Finish calibration and compute transform."""
        if not self._calibration_active:
            return

        if len(self._touch_points) < 3:
            self._publish_status('error', "Need at least 3 touch points")
            return

        # Compute base transform
        transform = self._compute_base_transform()
        if transform is None:
            self._publish_status('error', "Failed to compute transform")
            return

        # Create calibration result
        result = CalibrationResult(
            robot_name=self._current_robot,
            base_to_world=transform,
            calibrated_at=datetime.now(),
            method=self._method,
            num_samples=len(self._touch_points),
        )

        # Save calibration
        self._save_calibration(result)

        # Broadcast static transform
        if TF2_AVAILABLE:
            self._broadcast_calibration(result)

        # Publish result
        self._publish_result(result)
        self._publish_status('complete', f"Calibration complete for {self._current_robot}")

        # Reset state
        self._calibration_active = False
        self._touch_points = []

    def _cancel_calibration(self):
        """Cancel current calibration."""
        self._calibration_active = False
        self._touch_points = []
        self._publish_status('cancelled', "Calibration cancelled")

    def _compute_forward_kinematics(self) -> Optional[List[float]]:
        """Compute end-effector pose from joint positions."""
        # Simplified - in production would use actual robot kinematics
        # For now, return a placeholder
        if not hasattr(self, '_current_joint_positions'):
            return None

        # This would call the robot's FK solver
        # Placeholder return
        return [0.3, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0]  # x, y, z, qx, qy, qz, qw

    def _compute_base_transform(self) -> Optional[Dict[str, List[float]]]:
        """Compute robot base to world transform from touch points."""
        if len(self._touch_points) < 3:
            return None

        # Use least squares to fit transform
        # Simplified implementation - would use proper SVD in production
        import numpy as np

        world_points = np.array([p['world_position'] for p in self._touch_points])
        ee_points = np.array([p['ee_position'] for p in self._touch_points])

        # Compute centroid
        world_centroid = np.mean(world_points, axis=0)
        ee_centroid = np.mean(ee_points, axis=0)

        # Translation estimate (simplified)
        translation = world_centroid - ee_centroid

        return {
            'translation': translation.tolist(),
            'rotation': [0.0, 0.0, 0.0, 1.0],  # Identity rotation for now
        }

    def _save_calibration(self, result: CalibrationResult):
        """Save calibration to file."""
        import os
        os.makedirs(self._calibration_dir, exist_ok=True)

        filename = f"{self._calibration_dir}/{result.robot_name}_base.yaml"
        data = {
            'robot': result.robot_name,
            'base_to_world': result.base_to_world,
            'calibrated_at': result.calibrated_at.isoformat(),
            'method': result.method,
            'num_samples': result.num_samples,
        }

        with open(filename, 'w') as f:
            yaml.dump(data, f)

        self.get_logger().info(f"Saved calibration to {filename}")

    def _broadcast_calibration(self, result: CalibrationResult):
        """Broadcast static transform for calibrated robot base."""
        if not TF2_AVAILABLE:
            return

        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'world'
        t.child_frame_id = f'{result.robot_name}_base'

        trans = result.base_to_world.get('translation', [0, 0, 0])
        t.transform.translation.x = trans[0]
        t.transform.translation.y = trans[1]
        t.transform.translation.z = trans[2]

        rot = result.base_to_world.get('rotation', [0, 0, 0, 1])
        t.transform.rotation.x = rot[0]
        t.transform.rotation.y = rot[1]
        t.transform.rotation.z = rot[2]
        t.transform.rotation.w = rot[3]

        self._static_broadcaster.sendTransform(t)

    def _publish_status(self, status: str, message: str):
        """Publish calibration status."""
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'message': message,
            'robot': self._current_robot,
            'points_recorded': len(self._touch_points),
            'timestamp': datetime.now().isoformat(),
        })
        self._status_pub.publish(msg)

    def _publish_result(self, result: CalibrationResult):
        """Publish calibration result."""
        msg = String()
        msg.data = json.dumps({
            'robot': result.robot_name,
            'base_to_world': result.base_to_world,
            'method': result.method,
            'num_samples': result.num_samples,
            'calibrated_at': result.calibrated_at.isoformat(),
        })
        self._result_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotCalibrationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
