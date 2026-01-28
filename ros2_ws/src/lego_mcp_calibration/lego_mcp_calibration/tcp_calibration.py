#!/usr/bin/env python3
"""
LEGO MCP TCP Calibration Node
Calibrate Tool Center Point offset for LEGO gripper.

Uses 4-point method: Touch fixed point from 4 different orientations.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import yaml

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from sensor_msgs.msg import JointState


class TCPCalibrationNode(Node):
    """
    TCP (Tool Center Point) calibration for gripper offset.
    """

    def __init__(self):
        super().__init__('tcp_calibration')

        # Parameters
        self.declare_parameter('num_touch_points', 4)
        self.declare_parameter('calibration_dir', '/tmp/lego_mcp_calibration')

        self._num_points = self.get_parameter('num_touch_points').value
        self._calibration_dir = self.get_parameter('calibration_dir').value

        # Calibration state
        self._calibration_active = False
        self._robot_name = ''
        self._touch_points: List[Dict[str, Any]] = []
        self._current_joint_positions = []

        # Joint state subscribers
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
            '/calibration/tcp/command',
            self._on_command,
            10
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/calibration/tcp/status',
            10
        )

        self._result_pub = self.create_publisher(
            String,
            '/calibration/tcp/result',
            10
        )

        self.get_logger().info("TCP calibration node initialized")

    def _on_joint_states(self, robot_id: str, msg: JointState):
        """Store joint states."""
        if self._calibration_active and self._robot_name == robot_id:
            self._current_joint_positions = list(msg.position)

    def _on_command(self, msg: String):
        """Handle calibration commands."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'start':
                self._start_calibration(data.get('robot', 'ned2'))

            elif command == 'touch':
                self._record_touch()

            elif command == 'compute':
                self._compute_tcp()

            elif command == 'cancel':
                self._cancel_calibration()

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid command: {msg.data}")

    def _start_calibration(self, robot_name: str):
        """Start TCP calibration."""
        self._calibration_active = True
        self._robot_name = robot_name
        self._touch_points = []

        self.get_logger().info(f"Starting TCP calibration for {robot_name}")
        self._publish_status('started', f"Move gripper tip to calibration point (orientation 1/{self._num_points})")

    def _record_touch(self):
        """Record touch point."""
        if not self._calibration_active:
            return

        if not self._current_joint_positions:
            self._publish_status('error', "No joint positions available")
            return

        # Compute flange pose from FK
        flange_pose = self._compute_flange_pose()

        self._touch_points.append({
            'joint_positions': self._current_joint_positions.copy(),
            'flange_pose': flange_pose,
            'timestamp': datetime.now().isoformat(),
        })

        num = len(self._touch_points)
        self.get_logger().info(f"Recorded touch point {num}/{self._num_points}")

        if num < self._num_points:
            self._publish_status('touch_recorded', f"Touch {num}/{self._num_points}. Move to different orientation.")
        else:
            self._publish_status('ready', "All points recorded. Send 'compute' to calculate TCP.")

    def _compute_tcp(self):
        """Compute TCP offset from touch points."""
        if not self._calibration_active:
            return

        if len(self._touch_points) < self._num_points:
            self._publish_status('error', f"Need {self._num_points} touch points")
            return

        # Compute TCP using sphere fit
        tcp_offset = self._sphere_fit()

        if tcp_offset is None:
            self._publish_status('error', "TCP computation failed")
            return

        result = {
            'robot': self._robot_name,
            'tcp_offset': {
                'x': tcp_offset[0],
                'y': tcp_offset[1],
                'z': tcp_offset[2],
            },
            'num_points': len(self._touch_points),
            'calibrated_at': datetime.now().isoformat(),
        }

        self._save_tcp(result)
        self._publish_result(result)
        self._publish_status('complete', f"TCP offset: [{tcp_offset[0]:.4f}, {tcp_offset[1]:.4f}, {tcp_offset[2]:.4f}]")

        self._calibration_active = False

    def _compute_flange_pose(self) -> Dict[str, List[float]]:
        """Compute flange pose from joint positions using FK."""
        # Simplified - would use actual robot FK in production
        import numpy as np

        # DH parameters would be used here for accurate FK
        # Placeholder implementation
        q = self._current_joint_positions

        # Assume some basic FK result
        x = 0.3 + 0.1 * np.sin(q[0] if q else 0)
        y = 0.1 * np.cos(q[0] if q else 0)
        z = 0.3 + 0.05 * (q[1] if len(q) > 1 else 0)

        return {
            'position': [x, y, z],
            'orientation': [0, 0, 0, 1],  # Placeholder quaternion
        }

    def _sphere_fit(self) -> Optional[List[float]]:
        """
        Fit a sphere to the flange positions.
        The center of the sphere is the TCP position.
        """
        import numpy as np

        # Get flange positions
        positions = np.array([p['flange_pose']['position'] for p in self._touch_points])

        if len(positions) < 4:
            return None

        # Solve least squares sphere fit
        # Equation: (x - a)^2 + (y - b)^2 + (z - c)^2 = r^2
        # Linearized: 2ax + 2by + 2cz + (r^2 - a^2 - b^2 - c^2) = x^2 + y^2 + z^2

        A = np.zeros((len(positions), 4))
        b = np.zeros(len(positions))

        for i, p in enumerate(positions):
            A[i] = [2 * p[0], 2 * p[1], 2 * p[2], 1]
            b[i] = p[0]**2 + p[1]**2 + p[2]**2

        # Solve using least squares
        result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

        center = result[:3]

        # TCP offset is the vector from flange origin to sphere center
        # (in flange frame - simplified)
        flange_origin = np.mean(positions, axis=0)
        tcp_offset = center - flange_origin

        return tcp_offset.tolist()

    def _save_tcp(self, result: Dict[str, Any]):
        """Save TCP offset to file."""
        import os
        os.makedirs(self._calibration_dir, exist_ok=True)

        filename = f"{self._calibration_dir}/{self._robot_name}_tcp.yaml"
        with open(filename, 'w') as f:
            yaml.dump(result, f)

        self.get_logger().info(f"Saved TCP to {filename}")

    def _cancel_calibration(self):
        """Cancel calibration."""
        self._calibration_active = False
        self._touch_points = []
        self._publish_status('cancelled', "TCP calibration cancelled")

    def _publish_status(self, status: str, message: str):
        """Publish status."""
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'message': message,
            'robot': self._robot_name,
            'points_recorded': len(self._touch_points),
            'timestamp': datetime.now().isoformat(),
        })
        self._status_pub.publish(msg)

    def _publish_result(self, result: Dict[str, Any]):
        """Publish result."""
        msg = String()
        msg.data = json.dumps(result)
        self._result_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TCPCalibrationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
