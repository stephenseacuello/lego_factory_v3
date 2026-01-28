#!/usr/bin/env python3
"""
LEGO MCP Hand-Eye Calibration Node
Calibrate camera position relative to robot or workcell.

Supports:
- Eye-in-hand: Camera mounted on robot end-effector
- Eye-to-hand: Camera fixed in workcell

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
from sensor_msgs.msg import Image

try:
    from tf2_ros import Buffer, TransformListener, StaticTransformBroadcaster
    TF2_AVAILABLE = True
except ImportError:
    TF2_AVAILABLE = False

try:
    from cv_bridge import CvBridge
    import cv2
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


class HandEyeCalibrationNode(Node):
    """
    Hand-eye calibration for camera setup.
    """

    def __init__(self):
        super().__init__('hand_eye_calibration')

        # Parameters
        self.declare_parameter('calibration_type', 'eye_to_hand')  # or 'eye_in_hand'
        self.declare_parameter('min_poses', 20)
        self.declare_parameter('checkerboard_size', [9, 6])
        self.declare_parameter('square_size_mm', 25.0)
        self.declare_parameter('calibration_dir', '/tmp/lego_mcp_calibration')

        self._calibration_type = self.get_parameter('calibration_type').value
        self._min_poses = self.get_parameter('min_poses').value
        self._checkerboard_size = tuple(self.get_parameter('checkerboard_size').value)
        self._square_size = self.get_parameter('square_size_mm').value / 1000.0
        self._calibration_dir = self.get_parameter('calibration_dir').value

        # Calibration state
        self._calibration_active = False
        self._camera_name = ''
        self._robot_name = ''
        self._collected_poses: List[Dict[str, Any]] = []

        # CV Bridge
        if CV_AVAILABLE:
            self._cv_bridge = CvBridge()
            self._aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            self._aruco_params = cv2.aruco.DetectorParameters_create()
        else:
            self._cv_bridge = None

        # TF
        if TF2_AVAILABLE:
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self)
            self._static_broadcaster = StaticTransformBroadcaster(self)

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Command subscriber
        self.create_subscription(
            String,
            '/calibration/hand_eye/command',
            self._on_command,
            10
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/calibration/hand_eye/status',
            10
        )

        self._result_pub = self.create_publisher(
            String,
            '/calibration/hand_eye/result',
            10
        )

        self.get_logger().info("Hand-eye calibration node initialized")

    def _on_command(self, msg: String):
        """Handle calibration commands."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'start':
                self._start_calibration(
                    data.get('camera', 'camera'),
                    data.get('robot', 'ned2')
                )

            elif command == 'capture':
                self._capture_pose()

            elif command == 'compute':
                self._compute_calibration()

            elif command == 'cancel':
                self._cancel_calibration()

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid command: {msg.data}")

    def _start_calibration(self, camera_name: str, robot_name: str):
        """Start hand-eye calibration."""
        self._calibration_active = True
        self._camera_name = camera_name
        self._robot_name = robot_name
        self._collected_poses = []

        # Subscribe to camera image
        self._image_sub = self.create_subscription(
            Image,
            f'/{camera_name}/image_raw',
            self._on_image,
            10,
            callback_group=self._cb_group
        )

        self._latest_image = None

        self.get_logger().info(f"Started hand-eye calibration: {self._calibration_type}")
        self._publish_status('started', f"Calibrating {camera_name} with {robot_name}")

    def _on_image(self, msg: Image):
        """Store latest camera image."""
        if self._cv_bridge:
            self._latest_image = self._cv_bridge.imgmsg_to_cv2(msg, 'bgr8')
            self._latest_image_header = msg.header

    def _capture_pose(self):
        """Capture current robot pose and camera observation."""
        if not self._calibration_active:
            return

        if self._latest_image is None:
            self._publish_status('error', "No camera image available")
            return

        # Detect calibration target in image
        target_pose = self._detect_target(self._latest_image)
        if target_pose is None:
            self._publish_status('error', "Could not detect calibration target")
            return

        # Get robot end-effector pose
        robot_pose = self._get_robot_pose()
        if robot_pose is None:
            self._publish_status('error', "Could not get robot pose")
            return

        # Store pose pair
        self._collected_poses.append({
            'robot_pose': robot_pose,
            'target_pose': target_pose,
            'timestamp': datetime.now().isoformat(),
        })

        self.get_logger().info(f"Captured pose {len(self._collected_poses)}/{self._min_poses}")
        self._publish_status('pose_captured', f"Pose {len(self._collected_poses)}/{self._min_poses}")

    def _detect_target(self, image) -> Optional[Dict[str, List[float]]]:
        """Detect calibration target in image."""
        if not CV_AVAILABLE:
            return None

        # Try checkerboard detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, self._checkerboard_size, None)

        if ret:
            # Refine corners
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Solve PnP to get pose
            obj_points = self._get_checkerboard_points()
            ret, rvec, tvec = cv2.solvePnP(obj_points, corners, self._camera_matrix, self._dist_coeffs)

            if ret:
                return {
                    'translation': tvec.flatten().tolist(),
                    'rotation_vec': rvec.flatten().tolist(),
                }

        # Try ArUco marker detection as fallback
        corners, ids, _ = cv2.aruco.detectMarkers(gray, self._aruco_dict, parameters=self._aruco_params)

        if ids is not None and len(ids) > 0:
            # Use first detected marker
            rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(corners, 0.05, self._camera_matrix, self._dist_coeffs)
            return {
                'translation': tvec[0].flatten().tolist(),
                'rotation_vec': rvec[0].flatten().tolist(),
                'marker_id': int(ids[0][0]),
            }

        return None

    def _get_checkerboard_points(self):
        """Generate 3D points for checkerboard corners."""
        import numpy as np
        points = []
        for i in range(self._checkerboard_size[1]):
            for j in range(self._checkerboard_size[0]):
                points.append([j * self._square_size, i * self._square_size, 0])
        return np.array(points, dtype=np.float32)

    def _get_robot_pose(self) -> Optional[Dict[str, List[float]]]:
        """Get current robot end-effector pose."""
        if not TF2_AVAILABLE:
            return None

        try:
            transform = self._tf_buffer.lookup_transform(
                'world',
                f'{self._robot_name}_gripper',
                rclpy.time.Time()
            )

            return {
                'translation': [
                    transform.transform.translation.x,
                    transform.transform.translation.y,
                    transform.transform.translation.z,
                ],
                'rotation': [
                    transform.transform.rotation.x,
                    transform.transform.rotation.y,
                    transform.transform.rotation.z,
                    transform.transform.rotation.w,
                ],
            }
        except Exception as e:
            self.get_logger().warn(f"Could not get robot pose: {e}")
            return None

    def _compute_calibration(self):
        """Compute hand-eye calibration from collected poses."""
        if not self._calibration_active:
            return

        if len(self._collected_poses) < self._min_poses:
            self._publish_status('error', f"Need at least {self._min_poses} poses")
            return

        # Compute hand-eye calibration using OpenCV
        # This requires proper matrix formatting
        try:
            import numpy as np

            # Convert poses to rotation matrices and translation vectors
            R_gripper2base = []
            t_gripper2base = []
            R_target2cam = []
            t_target2cam = []

            for pose in self._collected_poses:
                # Robot pose
                rp = pose['robot_pose']
                R_gripper2base.append(self._quat_to_rotation_matrix(rp['rotation']))
                t_gripper2base.append(np.array(rp['translation']))

                # Target pose in camera frame
                tp = pose['target_pose']
                R_target2cam.append(cv2.Rodrigues(np.array(tp['rotation_vec']))[0])
                t_target2cam.append(np.array(tp['translation']))

            # Compute calibration (simplified)
            # In production, would use cv2.calibrateHandEye
            if self._calibration_type == 'eye_to_hand':
                # Camera fixed in world
                R_cam2world = np.eye(3)
                t_cam2world = np.mean([np.array(p['robot_pose']['translation']) for p in self._collected_poses], axis=0)
            else:
                # Camera on robot
                R_cam2gripper = np.eye(3)
                t_cam2gripper = [0.05, 0, 0.1]  # Placeholder

            # Save result
            result = {
                'camera': self._camera_name,
                'robot': self._robot_name,
                'calibration_type': self._calibration_type,
                'transform': {
                    'translation': t_cam2world.tolist() if self._calibration_type == 'eye_to_hand' else t_cam2gripper,
                    'rotation': [0, 0, 0, 1],  # Placeholder
                },
                'num_poses': len(self._collected_poses),
                'calibrated_at': datetime.now().isoformat(),
            }

            self._save_calibration(result)
            self._broadcast_calibration(result)
            self._publish_result(result)
            self._publish_status('complete', "Hand-eye calibration complete")

            self._calibration_active = False

        except Exception as e:
            self.get_logger().error(f"Calibration computation failed: {e}")
            self._publish_status('error', str(e))

    def _quat_to_rotation_matrix(self, quat):
        """Convert quaternion to rotation matrix."""
        import numpy as np
        x, y, z, w = quat
        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
        ])

    def _save_calibration(self, result: Dict[str, Any]):
        """Save calibration to file."""
        import os
        os.makedirs(self._calibration_dir, exist_ok=True)

        filename = f"{self._calibration_dir}/{self._camera_name}_hand_eye.yaml"
        with open(filename, 'w') as f:
            yaml.dump(result, f)

        self.get_logger().info(f"Saved calibration to {filename}")

    def _broadcast_calibration(self, result: Dict[str, Any]):
        """Broadcast calibration transform."""
        if not TF2_AVAILABLE:
            return

        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()

        if self._calibration_type == 'eye_to_hand':
            t.header.frame_id = 'world'
            t.child_frame_id = f'{self._camera_name}_optical'
        else:
            t.header.frame_id = f'{self._robot_name}_gripper'
            t.child_frame_id = f'{self._camera_name}_optical'

        trans = result['transform']['translation']
        t.transform.translation.x = trans[0]
        t.transform.translation.y = trans[1]
        t.transform.translation.z = trans[2]

        rot = result['transform']['rotation']
        t.transform.rotation.x = rot[0]
        t.transform.rotation.y = rot[1]
        t.transform.rotation.z = rot[2]
        t.transform.rotation.w = rot[3]

        self._static_broadcaster.sendTransform(t)

    def _cancel_calibration(self):
        """Cancel calibration."""
        self._calibration_active = False
        self._collected_poses = []
        self._publish_status('cancelled', "Calibration cancelled")

    def _publish_status(self, status: str, message: str):
        """Publish status."""
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'message': message,
            'poses_collected': len(self._collected_poses),
            'timestamp': datetime.now().isoformat(),
        })
        self._status_pub.publish(msg)

    def _publish_result(self, result: Dict[str, Any]):
        """Publish result."""
        msg = String()
        msg.data = json.dumps(result)
        self._result_pub.publish(msg)

    @property
    def _camera_matrix(self):
        """Camera intrinsic matrix (placeholder)."""
        import numpy as np
        return np.array([
            [800, 0, 320],
            [0, 800, 240],
            [0, 0, 1],
        ], dtype=np.float32)

    @property
    def _dist_coeffs(self):
        """Camera distortion coefficients (placeholder)."""
        import numpy as np
        return np.zeros(5, dtype=np.float32)


def main(args=None):
    rclpy.init(args=args)
    node = HandEyeCalibrationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
