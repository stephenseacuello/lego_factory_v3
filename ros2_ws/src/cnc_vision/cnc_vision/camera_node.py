#!/usr/bin/env python3
"""
Camera Node for CNC Vision

Simple camera publisher that wraps USB webcam access.
Publishes images to /camera/image_raw for YOLO inference.
"""

import os
import cv2
import numpy as np
from datetime import datetime

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Header
from cv_bridge import CvBridge


class CameraNode(Node):
    """
    USB camera publisher node.

    Captures frames from USB webcam and publishes to ROS2 topics.
    Use v4l2_camera or usb_cam packages for production - this is a fallback.
    """

    def __init__(self):
        super().__init__('cnc_camera')

        # Declare parameters
        self.declare_parameter('device', '/dev/video0')
        self.declare_parameter('device_id', 0)  # Integer device ID for cv2
        self.declare_parameter('width', 1280)
        self.declare_parameter('height', 720)
        self.declare_parameter('fps', 30.0)
        self.declare_parameter('auto_exposure', True)
        self.declare_parameter('exposure_ms', 10.0)
        self.declare_parameter('frame_id', 'camera')
        self.declare_parameter('use_device_path', False)  # Use /dev/video0 or integer

        # Initialize CV bridge
        self.cv_bridge = CvBridge()

        # Initialize camera
        self._init_camera()

        # Publishers
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        self.camera_info_pub = self.create_publisher(CameraInfo, '/camera/camera_info', 10)

        # Capture timer
        fps = self.get_parameter('fps').value
        self.timer = self.create_timer(1.0 / fps, self.capture_callback)

        self.frame_count = 0
        self.last_log_time = datetime.now()

        self.get_logger().info(
            f'Camera node initialized: {self.get_parameter("width").value}x'
            f'{self.get_parameter("height").value} @ {fps} FPS'
        )

    def _init_camera(self):
        """Initialize camera capture."""
        use_path = self.get_parameter('use_device_path').value

        if use_path:
            device = self.get_parameter('device').value
        else:
            device = self.get_parameter('device_id').value

        self.cap = cv2.VideoCapture(device)

        if not self.cap.isOpened():
            self.get_logger().error(f'Failed to open camera: {device}')
            raise RuntimeError(f'Cannot open camera: {device}')

        # Set resolution
        width = self.get_parameter('width').value
        height = self.get_parameter('height').value
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # Set FPS
        fps = self.get_parameter('fps').value
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        # Set exposure if not auto
        if not self.get_parameter('auto_exposure').value:
            exposure = self.get_parameter('exposure_ms').value
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Manual mode
            self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

        # Verify settings
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        self.get_logger().info(
            f'Camera opened: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS'
        )

    def capture_callback(self):
        """Capture and publish frame."""
        ret, frame = self.cap.read()

        if not ret:
            self.get_logger().warn('Failed to capture frame')
            return

        self.frame_count += 1

        # Create header
        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = self.get_parameter('frame_id').value

        # Convert to ROS Image message
        try:
            img_msg = self.cv_bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            img_msg.header = header
            self.image_pub.publish(img_msg)
        except Exception as e:
            self.get_logger().error(f'Error converting image: {e}')
            return

        # Publish camera info
        camera_info = CameraInfo()
        camera_info.header = header
        camera_info.width = frame.shape[1]
        camera_info.height = frame.shape[0]
        self.camera_info_pub.publish(camera_info)

        # Log FPS periodically
        now = datetime.now()
        if (now - self.last_log_time).total_seconds() >= 10.0:
            elapsed = (now - self.last_log_time).total_seconds()
            fps = self.frame_count / elapsed
            self.get_logger().info(f'Camera publishing at {fps:.1f} FPS')
            self.frame_count = 0
            self.last_log_time = now

    def destroy_node(self):
        """Release camera."""
        if self.cap:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = CameraNode()
        rclpy.spin(node)
    except RuntimeError as e:
        print(f'Camera error: {e}')
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
