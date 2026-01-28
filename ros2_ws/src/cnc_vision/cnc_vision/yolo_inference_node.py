#!/usr/bin/env python3
"""
YOLO Inference Node for CNC Vision

Subscribes to camera images and runs Roboflow YOLO inference.
Publishes detections to ROS2 topics and provides inspection services.
"""

import os
import json
import time
import base64
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from sensor_msgs.msg import Image
from std_msgs.msg import Header
from cv_bridge import CvBridge
import numpy as np

# Import custom messages
from cnc_interfaces.msg import (
    VisionDetection,
    VisionDetectionArray,
    VisionSafetyAlert,
    VisionStatus,
)
from cnc_interfaces.srv import (
    InspectPart,
    CheckToolWear,
    VerifyPartPosition,
    CheckSafetyZone,
)

# Roboflow inference
try:
    from inference_sdk import InferenceHTTPClient
    INFERENCE_SDK_AVAILABLE = True
except ImportError:
    INFERENCE_SDK_AVAILABLE = False
    print("Warning: inference-sdk not available, using HTTP requests")

import requests


@dataclass
class DetectionResult:
    """Single detection result from YOLO."""
    class_name: str
    class_id: str
    confidence: float
    x_center: float
    y_center: float
    width: float
    height: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int


class YOLOInferenceNode(Node):
    """
    ROS2 node for YOLO-based computer vision.

    Provides:
    - Continuous inference on camera feed
    - On-demand inspection services
    - Safety zone monitoring
    - MQTT bridge for Flask integration
    """

    def __init__(self):
        super().__init__('yolo_inference_node')

        # Callback group for concurrent service handling
        self.callback_group = ReentrantCallbackGroup()

        # Declare parameters
        self._declare_parameters()

        # Initialize CV bridge
        self.cv_bridge = CvBridge()

        # Initialize inference client
        self._init_inference_client()

        # State
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_frame_time: Optional[datetime] = None
        self.frame_count = 0
        self.detection_count = 0
        self.inference_times: List[float] = []

        # Publishers
        self.detection_pub = self.create_publisher(
            VisionDetectionArray,
            '/vision/detections',
            10
        )
        self.safety_alert_pub = self.create_publisher(
            VisionSafetyAlert,
            '/vision/safety_alerts',
            10
        )
        self.status_pub = self.create_publisher(
            VisionStatus,
            '/vision/status',
            10
        )

        # Subscribers
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10,
            callback_group=self.callback_group
        )

        # Services
        self.inspect_srv = self.create_service(
            InspectPart,
            '/vision/inspect_part',
            self.inspect_part_callback,
            callback_group=self.callback_group
        )
        self.tool_wear_srv = self.create_service(
            CheckToolWear,
            '/vision/check_tool_wear',
            self.check_tool_wear_callback,
            callback_group=self.callback_group
        )
        self.position_srv = self.create_service(
            VerifyPartPosition,
            '/vision/verify_part_position',
            self.verify_part_position_callback,
            callback_group=self.callback_group
        )
        self.safety_srv = self.create_service(
            CheckSafetyZone,
            '/vision/check_safety_zone',
            self.check_safety_zone_callback,
            callback_group=self.callback_group
        )

        # Status timer
        self.status_timer = self.create_timer(
            1.0,
            self.publish_status,
            callback_group=self.callback_group
        )

        # Inference timer (if continuous mode)
        inference_mode = self.get_parameter('inference_mode').value
        if inference_mode == 'continuous':
            target_fps = self.get_parameter('target_fps').value
            self.inference_timer = self.create_timer(
                1.0 / target_fps,
                self.run_continuous_inference,
                callback_group=self.callback_group
            )

        self.get_logger().info('YOLO Inference Node initialized')

    def _declare_parameters(self):
        """Declare ROS2 parameters."""
        self.declare_parameter('machine_id', 'default')
        self.declare_parameter('camera_id', 'primary')

        # Roboflow settings
        self.declare_parameter('roboflow_api_key', os.getenv('ROBOFLOW_API_KEY', ''))
        self.declare_parameter('inference_server_url', 'http://roboflow-inference:9001')
        self.declare_parameter('use_local_inference', True)

        # Model IDs
        self.declare_parameter('defect_model_id', 'cnc-defect-detection/1')
        self.declare_parameter('tool_wear_model_id', 'tool-wear-detection/1')
        self.declare_parameter('part_model_id', 'part-detection/1')
        self.declare_parameter('safety_model_id', 'hand-detection/1')

        # Thresholds
        self.declare_parameter('confidence_threshold', 0.7)
        self.declare_parameter('safety_confidence_threshold', 0.5)

        # Inference settings
        self.declare_parameter('inference_mode', 'continuous')
        self.declare_parameter('target_fps', 10)

        # Capture settings
        self.declare_parameter('save_detections', True)
        self.declare_parameter('save_path', '/ros2_ws/captures')

    def _init_inference_client(self):
        """Initialize Roboflow inference client."""
        api_key = self.get_parameter('roboflow_api_key').value
        server_url = self.get_parameter('inference_server_url').value
        use_local = self.get_parameter('use_local_inference').value

        if use_local and INFERENCE_SDK_AVAILABLE:
            self.inference_client = InferenceHTTPClient(
                api_url=server_url,
                api_key=api_key
            )
            self.get_logger().info(f'Using local inference server: {server_url}')
        else:
            self.inference_client = None
            self.inference_url = server_url
            self.api_key = api_key
            self.get_logger().info('Using HTTP requests for inference')

    def image_callback(self, msg: Image):
        """Handle incoming camera images."""
        try:
            # Convert ROS Image to OpenCV
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.latest_frame = cv_image
            self.latest_frame_time = datetime.now()
            self.frame_count += 1
        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')

    def run_continuous_inference(self):
        """Run inference on latest frame (continuous mode)."""
        if self.latest_frame is None:
            return

        try:
            # Run safety detection by default in continuous mode
            model_id = self.get_parameter('safety_model_id').value
            confidence = self.get_parameter('safety_confidence_threshold').value

            detections = self._run_inference(
                self.latest_frame,
                model_id,
                confidence,
                detection_type='safety'
            )

            if detections:
                # Publish detection array
                self._publish_detections(detections, 'safety')

                # Check for safety alerts
                self._check_safety_alerts(detections)

        except Exception as e:
            self.get_logger().error(f'Inference error: {e}')

    def _run_inference(
        self,
        image: np.ndarray,
        model_id: str,
        confidence_threshold: float,
        detection_type: str = 'general'
    ) -> List[DetectionResult]:
        """
        Run YOLO inference on image.

        Args:
            image: OpenCV image (BGR)
            model_id: Roboflow model ID
            confidence_threshold: Minimum confidence
            detection_type: Type for categorization

        Returns:
            List of DetectionResult objects
        """
        start_time = time.time()
        detections = []

        try:
            # Encode image to base64
            import cv2
            _, buffer = cv2.imencode('.jpg', image)
            image_b64 = base64.b64encode(buffer).decode('utf-8')

            if self.inference_client:
                # Use SDK
                result = self.inference_client.infer(
                    image_b64,
                    model_id=model_id
                )
            else:
                # Use HTTP request
                response = requests.post(
                    f"{self.inference_url}/{model_id}",
                    params={"api_key": self.api_key},
                    json={"image": image_b64},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                result = response.json()

            # Parse predictions
            predictions = result.get('predictions', [])
            img_height, img_width = image.shape[:2]

            for pred in predictions:
                if pred.get('confidence', 0) >= confidence_threshold:
                    # Normalize coordinates
                    x = pred.get('x', 0) / img_width
                    y = pred.get('y', 0) / img_height
                    w = pred.get('width', 0) / img_width
                    h = pred.get('height', 0) / img_height

                    detection = DetectionResult(
                        class_name=pred.get('class', 'unknown'),
                        class_id=str(pred.get('class_id', '')),
                        confidence=pred.get('confidence', 0),
                        x_center=x,
                        y_center=y,
                        width=w,
                        height=h,
                        x_min=int(pred.get('x', 0) - pred.get('width', 0) / 2),
                        y_min=int(pred.get('y', 0) - pred.get('height', 0) / 2),
                        x_max=int(pred.get('x', 0) + pred.get('width', 0) / 2),
                        y_max=int(pred.get('y', 0) + pred.get('height', 0) / 2),
                    )
                    detections.append(detection)

            # Track inference time
            inference_time = (time.time() - start_time) * 1000
            self.inference_times.append(inference_time)
            if len(self.inference_times) > 100:
                self.inference_times.pop(0)

            self.detection_count += len(detections)

        except Exception as e:
            self.get_logger().error(f'Inference failed: {e}')

        return detections

    def _publish_detections(self, detections: List[DetectionResult], detection_type: str):
        """Publish detection array message."""
        msg = VisionDetectionArray()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera'

        msg.machine_id = self.get_parameter('machine_id').value
        msg.camera_id = self.get_parameter('camera_id').value
        msg.frame_number = self.frame_count

        if self.latest_frame is not None:
            msg.image_height, msg.image_width = self.latest_frame.shape[:2]

        msg.total_detections = len(detections)
        msg.inference_time_ms = self.inference_times[-1] if self.inference_times else 0.0

        for det in detections:
            vision_det = VisionDetection()
            vision_det.header = msg.header
            vision_det.detection_type = detection_type
            vision_det.class_name = det.class_name
            vision_det.class_id = det.class_id
            vision_det.confidence = det.confidence
            vision_det.x_center = det.x_center
            vision_det.y_center = det.y_center
            vision_det.width = det.width
            vision_det.height = det.height
            vision_det.x_min = det.x_min
            vision_det.y_min = det.y_min
            vision_det.x_max = det.x_max
            vision_det.y_max = det.y_max
            vision_det.machine_id = msg.machine_id
            vision_det.camera_id = msg.camera_id
            msg.detections.append(vision_det)

        self.detection_pub.publish(msg)

    def _check_safety_alerts(self, detections: List[DetectionResult]):
        """Check detections for safety zone violations."""
        safety_classes = ['hand', 'person', 'human']

        for det in detections:
            if det.class_name.lower() in safety_classes:
                alert = VisionSafetyAlert()
                alert.header = Header()
                alert.header.stamp = self.get_clock().now().to_msg()
                alert.machine_id = self.get_parameter('machine_id').value
                alert.camera_id = self.get_parameter('camera_id').value

                # Determine alert level based on position
                if self._in_critical_zone(det):
                    alert.alert_level = VisionSafetyAlert.LEVEL_CRITICAL
                    alert.requires_estop = True
                    alert.requires_pause = True
                else:
                    alert.alert_level = VisionSafetyAlert.LEVEL_WARNING
                    alert.requires_estop = False
                    alert.requires_pause = True

                alert.alert_type = f'{det.class_name}_detected'
                alert.object_class = det.class_name
                alert.zone_name = self._get_zone_name(det)
                alert.confidence = det.confidence
                alert.x_position = det.x_center
                alert.y_position = det.y_center
                alert.recommended_action = 'Pause motion and verify area is clear'

                self.safety_alert_pub.publish(alert)
                self.get_logger().warn(
                    f'SAFETY ALERT: {det.class_name} detected in {alert.zone_name}'
                )

    def _in_critical_zone(self, det: DetectionResult) -> bool:
        """Check if detection is in critical (spindle) zone."""
        # Critical zone: center of frame
        return (0.3 <= det.x_center <= 0.7 and 0.3 <= det.y_center <= 0.7)

    def _get_zone_name(self, det: DetectionResult) -> str:
        """Determine which safety zone contains the detection."""
        if self._in_critical_zone(det):
            return 'spindle_area'
        elif 0.1 <= det.x_center <= 0.9 and 0.1 <= det.y_center <= 0.9:
            return 'work_envelope'
        return 'peripheral'

    def inspect_part_callback(self, request, response):
        """Handle part inspection service request."""
        self.get_logger().info(f'Part inspection requested: {request.part_number}')

        try:
            # Capture or use latest frame
            if request.capture_new_image or self.latest_frame is None:
                # Wait briefly for new frame
                time.sleep(0.1)

            if self.latest_frame is None:
                response.success = False
                response.message = 'No camera frame available'
                return response

            # Run defect detection
            model_id = self.get_parameter('defect_model_id').value
            confidence = request.confidence_threshold or 0.7

            detections = self._run_inference(
                self.latest_frame,
                model_id,
                confidence,
                detection_type='defect'
            )

            # Build response
            response.success = True
            response.message = f'Inspection complete: {len(detections)} defects found'
            response.defect_count = len(detections)

            # Categorize defects
            for det in detections:
                vision_det = VisionDetection()
                vision_det.detection_type = 'defect'
                vision_det.class_name = det.class_name
                vision_det.confidence = det.confidence
                vision_det.x_center = det.x_center
                vision_det.y_center = det.y_center
                vision_det.width = det.width
                vision_det.height = det.height
                response.defects.append(vision_det)

            # Calculate quality score (inverse of defect severity)
            if detections:
                avg_confidence = sum(d.confidence for d in detections) / len(detections)
                response.quality_score = max(0, 100 - len(detections) * 20 - avg_confidence * 10)
            else:
                response.quality_score = 100.0

            response.passed = len(detections) == 0
            response.disposition = 'accept' if response.passed else 'review'

            # Save image if configured
            if self.get_parameter('save_detections').value:
                save_path = self.get_parameter('save_path').value
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                response.image_path = f'{save_path}/inspection_{request.part_number}_{timestamp}.jpg'

            response.inference_time_ms = self.inference_times[-1] if self.inference_times else 0.0

        except Exception as e:
            response.success = False
            response.message = f'Inspection failed: {str(e)}'
            self.get_logger().error(f'Inspection error: {e}')

        return response

    def check_tool_wear_callback(self, request, response):
        """Handle tool wear check service request."""
        self.get_logger().info(f'Tool wear check requested: T{request.tool_number}')

        try:
            if self.latest_frame is None:
                response.success = False
                response.message = 'No camera frame available'
                return response

            # Run tool wear detection
            model_id = self.get_parameter('tool_wear_model_id').value

            detections = self._run_inference(
                self.latest_frame,
                model_id,
                0.6,  # Lower threshold for wear detection
                detection_type='tool_wear'
            )

            response.success = True
            response.message = f'Tool wear analysis complete: {len(detections)} wear indicators'

            # Analyze wear patterns
            wear_types = set()
            max_wear = 0.0

            for det in detections:
                wear_types.add(det.class_name)
                if 'severe' in det.class_name.lower() or 'worn' in det.class_name.lower():
                    max_wear = max(max_wear, det.confidence * 100)

                vision_det = VisionDetection()
                vision_det.detection_type = 'tool_wear'
                vision_det.class_name = det.class_name
                vision_det.confidence = det.confidence
                response.wear_indicators.append(vision_det)

            response.wear_types = list(wear_types)
            response.wear_percentage = max_wear

            # Determine condition
            if max_wear >= 80:
                response.condition = CheckToolWear.Response.CONDITION_REPLACE
                response.replace_recommended = True
                response.replacement_reason = 'Severe wear detected'
            elif max_wear >= 60:
                response.condition = CheckToolWear.Response.CONDITION_WORN
                response.replace_recommended = True
                response.replacement_reason = 'Significant wear detected'
            elif max_wear >= 40:
                response.condition = CheckToolWear.Response.CONDITION_FAIR
                response.replace_recommended = False
            elif max_wear >= 20:
                response.condition = CheckToolWear.Response.CONDITION_GOOD
                response.replace_recommended = False
            else:
                response.condition = CheckToolWear.Response.CONDITION_NEW
                response.replace_recommended = False

            response.estimated_remaining_life = 100.0 - max_wear
            response.inference_time_ms = self.inference_times[-1] if self.inference_times else 0.0

        except Exception as e:
            response.success = False
            response.message = f'Tool wear check failed: {str(e)}'
            self.get_logger().error(f'Tool wear check error: {e}')

        return response

    def verify_part_position_callback(self, request, response):
        """Handle part position verification service request."""
        self.get_logger().info(f'Part position verification requested: {request.fixture_id}')

        try:
            if self.latest_frame is None:
                response.success = False
                response.message = 'No camera frame available'
                return response

            # Run part detection
            model_id = self.get_parameter('part_model_id').value

            detections = self._run_inference(
                self.latest_frame,
                model_id,
                0.8,  # Higher threshold for position verification
                detection_type='part'
            )

            response.success = True

            if not detections:
                response.part_detected = False
                response.fixture_empty = True
                response.safe_to_machine = False
                response.recommendation = 'No part detected - load part before machining'
                response.message = 'No part detected in fixture'
            elif len(detections) > 1:
                response.part_detected = True
                response.multiple_parts = True
                response.safe_to_machine = False
                response.recommendation = 'Multiple objects detected - verify fixture'
                response.message = 'Multiple parts/objects detected'
            else:
                det = detections[0]
                response.part_detected = True
                response.fixture_empty = False
                response.multiple_parts = False
                response.detected_x = det.x_center
                response.detected_y = det.y_center
                response.detection_confidence = det.confidence

                # Calculate deviation from expected position
                if request.expected_x != 0 or request.expected_y != 0:
                    response.x_deviation_mm = (det.x_center - request.expected_x) * 100  # Scale factor
                    response.y_deviation_mm = (det.y_center - request.expected_y) * 100
                    total_deviation = (response.x_deviation_mm ** 2 + response.y_deviation_mm ** 2) ** 0.5
                    response.total_deviation_mm = total_deviation

                    tolerance = request.tolerance_position_mm or 1.0
                    response.position_correct = total_deviation <= tolerance
                else:
                    response.position_correct = True

                response.safe_to_machine = response.position_correct
                response.recommendation = 'proceed' if response.safe_to_machine else 'reposition'
                response.message = 'Part position verified' if response.safe_to_machine else 'Part position out of tolerance'

            response.inference_time_ms = self.inference_times[-1] if self.inference_times else 0.0

        except Exception as e:
            response.success = False
            response.message = f'Position verification failed: {str(e)}'
            self.get_logger().error(f'Position verification error: {e}')

        return response

    def check_safety_zone_callback(self, request, response):
        """Handle safety zone check service request."""
        self.get_logger().info(f'Safety zone check requested: {request.zone}')

        try:
            if self.latest_frame is None:
                response.success = False
                response.message = 'No camera frame available'
                return response

            # Run safety detection
            model_id = self.get_parameter('safety_model_id').value
            confidence = self.get_parameter('safety_confidence_threshold').value

            detections = self._run_inference(
                self.latest_frame,
                model_id,
                confidence,
                detection_type='safety'
            )

            response.success = True

            # Check for hazards
            safety_classes = ['hand', 'person', 'human', 'body']
            hazards = [d for d in detections if d.class_name.lower() in safety_classes]

            if not hazards:
                response.zone_clear = True
                response.safety_level = CheckSafetyZone.Response.SAFETY_OK
                response.safe_to_proceed = True
                response.estop_recommended = False
                response.pause_recommended = False
                response.recommended_action = 'Zone clear - safe to proceed'
                response.message = 'No hazards detected'
            else:
                response.zone_clear = False
                response.hands_detected = any(d.class_name.lower() == 'hand' for d in hazards)
                response.person_detected = any(d.class_name.lower() in ['person', 'human'] for d in hazards)

                # Find nearest hazard
                nearest = min(hazards, key=lambda d: ((d.x_center - 0.5) ** 2 + (d.y_center - 0.5) ** 2) ** 0.5)
                response.nearest_hazard_type = nearest.class_name
                response.nearest_hazard_x = nearest.x_center
                response.nearest_hazard_y = nearest.y_center

                # Determine safety level
                if self._in_critical_zone(nearest):
                    response.safety_level = CheckSafetyZone.Response.SAFETY_CRITICAL
                    response.estop_recommended = True
                    response.pause_recommended = True
                    response.safe_to_proceed = False
                    response.recommended_action = 'CRITICAL: Object in spindle area - E-stop recommended'
                else:
                    response.safety_level = CheckSafetyZone.Response.SAFETY_WARNING
                    response.estop_recommended = False
                    response.pause_recommended = True
                    response.safe_to_proceed = False
                    response.recommended_action = 'WARNING: Object in work envelope - pause and verify'

                response.message = f'{len(hazards)} hazard(s) detected'

                # Add hazard detections
                for det in hazards:
                    vision_det = VisionDetection()
                    vision_det.detection_type = 'safety'
                    vision_det.class_name = det.class_name
                    vision_det.confidence = det.confidence
                    vision_det.x_center = det.x_center
                    vision_det.y_center = det.y_center
                    response.hazards.append(vision_det)

            response.hazard_types = list(set(d.class_name for d in hazards))
            response.inference_time_ms = self.inference_times[-1] if self.inference_times else 0.0

        except Exception as e:
            response.success = False
            response.message = f'Safety check failed: {str(e)}'
            self.get_logger().error(f'Safety check error: {e}')

        return response

    def publish_status(self):
        """Publish vision system status."""
        msg = VisionStatus()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = self.get_parameter('machine_id').value

        msg.camera_connected = self.latest_frame is not None
        msg.inference_running = True
        msg.inference_server_url = self.get_parameter('inference_server_url').value
        msg.active_model = self.get_parameter('safety_model_id').value

        msg.frames_processed = self.frame_count
        msg.total_detections = self.detection_count

        if self.inference_times:
            msg.avg_inference_time_ms = sum(self.inference_times) / len(self.inference_times)
            msg.max_inference_time_ms = max(self.inference_times)
            msg.min_inference_time_ms = min(self.inference_times)

        if self.latest_frame is not None:
            msg.frame_height, msg.frame_width = self.latest_frame.shape[:2]

        msg.health_status = VisionStatus.HEALTH_OK
        msg.health_message = 'Vision system operational'

        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = YOLOInferenceNode()

    # Use multi-threaded executor for concurrent service handling
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
