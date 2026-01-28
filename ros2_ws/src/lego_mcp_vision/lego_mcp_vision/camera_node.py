#!/usr/bin/env python3
"""
LEGO MCP Camera/Vision Node
ROS2 node wrapping the existing vision pipeline.

Publishes:
- Defect detections
- Quality events
- Processed images

LEGO MCP Manufacturing System v7.0
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import sys

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from sensor_msgs.msg import Image, CameraInfo

try:
    from cv_bridge import CvBridge
    CV_BRIDGE_AVAILABLE = True
except ImportError:
    CV_BRIDGE_AVAILABLE = False

try:
    from lego_mcp_msgs.msg import DefectDetection, QualityEvent
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False

# Try to import existing vision services
VISION_AVAILABLE = False
try:
    # Add dashboard path for imports
    sys.path.insert(0, '/Users/stepheneacuello/Documents/lego_mcp_fusion360/dashboard')
    from services.vision.pipeline.orchestrator import VisionPipelineOrchestrator
    from services.vision.pipeline.quality_bridge import QualityBridge
    VISION_AVAILABLE = True
except ImportError:
    pass


class VisionNode(Node):
    """
    ROS2 node wrapping the existing vision pipeline.
    Publishes detections and quality events.
    """

    def __init__(self):
        super().__init__('vision_node')

        # Parameters
        self.declare_parameter('camera_topic', '/camera/image_raw')
        self.declare_parameter('publish_processed', True)
        self.declare_parameter('detection_threshold', 0.5)

        self._camera_topic = self.get_parameter('camera_topic').value
        self._publish_processed = self.get_parameter('publish_processed').value
        self._detection_threshold = self.get_parameter('detection_threshold').value

        # CV Bridge
        if CV_BRIDGE_AVAILABLE:
            self._cv_bridge = CvBridge()
        else:
            self._cv_bridge = None

        # Vision pipeline (existing service)
        self._pipeline = None
        self._quality_bridge = None
        if VISION_AVAILABLE:
            try:
                self._pipeline = VisionPipelineOrchestrator()
                self._quality_bridge = QualityBridge()
                # Register quality event handler
                self._quality_bridge.register_handler(self._on_quality_event)
            except Exception as e:
                self.get_logger().warn(f"Could not initialize vision pipeline: {e}")

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.create_subscription(
            Image,
            self._camera_topic,
            self._on_image,
            10,
            callback_group=self._cb_group
        )

        # Publishers
        if MSGS_AVAILABLE:
            self._defect_pub = self.create_publisher(
                DefectDetection,
                '/vision/defects',
                10
            )
            self._quality_pub = self.create_publisher(
                QualityEvent,
                '/quality/events',
                10
            )
        else:
            self._defect_pub = self.create_publisher(
                String,
                '/vision/defects',
                10
            )
            self._quality_pub = self.create_publisher(
                String,
                '/quality/events',
                10
            )

        self._processed_pub = self.create_publisher(
            Image,
            '/vision/processed',
            10
        )

        self._status_pub = self.create_publisher(
            String,
            '/vision/status',
            10
        )

        # Status timer
        self._status_timer = self.create_timer(
            1.0,
            self._publish_status
        )

        self.get_logger().info(f"Vision node initialized (pipeline available: {VISION_AVAILABLE})")

    async def _on_image(self, msg: Image):
        """Process incoming camera image."""
        if not self._pipeline or not self._cv_bridge:
            return

        try:
            # Convert ROS Image to OpenCV
            cv_image = self._cv_bridge.imgmsg_to_cv2(msg, 'bgr8')

            # Run through existing pipeline
            result = await self._pipeline.run({
                'image': cv_image,
                'timestamp': datetime.now(),
            })

            # Process detections
            defects = result.get('defects', [])
            for defect in defects:
                if defect.get('confidence', 0) >= self._detection_threshold:
                    self._publish_defect(defect, msg.header)

            # Publish processed image if enabled
            if self._publish_processed and 'annotated_image' in result:
                processed_msg = self._cv_bridge.cv2_to_imgmsg(
                    result['annotated_image'], 'bgr8'
                )
                processed_msg.header = msg.header
                self._processed_pub.publish(processed_msg)

        except Exception as e:
            self.get_logger().error(f"Image processing error: {e}")

    def _publish_defect(self, defect: Dict[str, Any], header):
        """Publish defect detection."""
        if MSGS_AVAILABLE:
            msg = DefectDetection()
            msg.header = header
            msg.defect_type = defect.get('type', 'unknown')
            msg.confidence = defect.get('confidence', 0.0)
            msg.severity = defect.get('severity', 1)

            bbox = defect.get('bbox', [0, 0, 0, 0])
            msg.bbox = [int(b) for b in bbox]

            if 'position_3d' in defect:
                pos = defect['position_3d']
                msg.position_3d.x = pos[0]
                msg.position_3d.y = pos[1]
                msg.position_3d.z = pos[2]

            msg.layer_number = defect.get('layer', 0)
            self._defect_pub.publish(msg)
        else:
            msg = String()
            msg.data = json.dumps({
                'defect_type': defect.get('type', 'unknown'),
                'confidence': defect.get('confidence', 0.0),
                'severity': defect.get('severity', 1),
                'bbox': defect.get('bbox', [0, 0, 0, 0]),
                'timestamp': datetime.now().isoformat(),
            })
            self._defect_pub.publish(msg)

    def _on_quality_event(self, event):
        """Forward quality events from bridge to ROS2."""
        if MSGS_AVAILABLE:
            msg = QualityEvent()
            msg.event_type = event.event_type if hasattr(event, 'event_type') else 'unknown'
            msg.severity = event.severity.value if hasattr(event, 'severity') else 1
            msg.action = event.action.value if hasattr(event, 'action') else 0
            msg.action_name = event.action.name if hasattr(event, 'action') else 'MONITOR'
            msg.description = event.description if hasattr(event, 'description') else ''
            msg.operation_id = event.operation_id if hasattr(event, 'operation_id') else ''
            msg.work_order_id = event.work_order_id if hasattr(event, 'work_order_id') else ''
            msg.timestamp = self.get_clock().now().to_msg()
            self._quality_pub.publish(msg)
        else:
            msg = String()
            msg.data = json.dumps({
                'event_type': event.event_type if hasattr(event, 'event_type') else 'unknown',
                'severity': event.severity.value if hasattr(event, 'severity') else 1,
                'action': event.action.name if hasattr(event, 'action') else 'MONITOR',
                'description': event.description if hasattr(event, 'description') else '',
                'timestamp': datetime.now().isoformat(),
            })
            self._quality_pub.publish(msg)

    def _publish_status(self):
        """Publish vision system status."""
        msg = String()
        msg.data = json.dumps({
            'vision_available': VISION_AVAILABLE,
            'pipeline_active': self._pipeline is not None,
            'cv_bridge_available': CV_BRIDGE_AVAILABLE,
            'msgs_available': MSGS_AVAILABLE,
            'timestamp': datetime.now().isoformat(),
        })
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = VisionNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
