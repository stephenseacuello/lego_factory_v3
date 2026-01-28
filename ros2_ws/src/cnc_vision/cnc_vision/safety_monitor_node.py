#!/usr/bin/env python3
"""
Safety Monitor Node

Dedicated safety monitoring with integration to machine E-stop.
Monitors camera feed for hands, people, and obstructions.
Can trigger emergency stop via ROS2 services.
"""

import os
from datetime import datetime
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from cnc_interfaces.msg import (
    VisionDetection,
    VisionDetectionArray,
    VisionSafetyAlert,
    SafetyState,
)
from cnc_interfaces.srv import EmergencyStop


class SafetyMonitorNode(Node):
    """
    Safety monitoring node.

    Subscribes to vision detections and monitors for safety hazards.
    Can trigger E-stop when critical violations detected.
    """

    def __init__(self):
        super().__init__('vision_safety_monitor')

        self.callback_group = ReentrantCallbackGroup()

        # Parameters
        self.declare_parameter('machine_id', 'default')
        self.declare_parameter('enable_estop_on_intrusion', True)
        self.declare_parameter('warning_zone_threshold', 0.8)  # Normalized distance
        self.declare_parameter('critical_zone_threshold', 0.5)
        self.declare_parameter('consecutive_frames_for_alert', 3)
        self.declare_parameter('cooldown_seconds', 5.0)
        self.declare_parameter('safety_classes', ['hand', 'person', 'human', 'body'])

        # State tracking
        self.detection_history = []  # Last N frames
        self.last_alert_time: Optional[datetime] = None
        self.alert_count = 0
        self.estop_triggered = False

        # Publishers
        self.alert_pub = self.create_publisher(
            VisionSafetyAlert,
            '/vision/safety_alerts',
            10
        )
        self.safety_state_pub = self.create_publisher(
            SafetyState,
            '/safety/state',
            10
        )

        # Subscribers
        self.detection_sub = self.create_subscription(
            VisionDetectionArray,
            '/vision/detections',
            self.detection_callback,
            10,
            callback_group=self.callback_group
        )

        # E-stop service client
        self.estop_client = self.create_client(
            EmergencyStop,
            '/machine/emergency_stop',
            callback_group=self.callback_group
        )

        # Status timer
        self.status_timer = self.create_timer(
            1.0,
            self.publish_safety_state,
            callback_group=self.callback_group
        )

        self.get_logger().info('Safety Monitor initialized')

    def detection_callback(self, msg: VisionDetectionArray):
        """Process detections for safety violations."""
        safety_classes = self.get_parameter('safety_classes').value
        machine_id = self.get_parameter('machine_id').value

        # Filter for safety-relevant detections
        safety_detections = [
            det for det in msg.detections
            if det.class_name.lower() in [c.lower() for c in safety_classes]
        ]

        # Update history
        self.detection_history.append({
            'timestamp': datetime.now(),
            'detections': safety_detections,
            'frame_number': msg.frame_number
        })

        # Keep only last N frames
        max_history = self.get_parameter('consecutive_frames_for_alert').value * 2
        if len(self.detection_history) > max_history:
            self.detection_history = self.detection_history[-max_history:]

        if not safety_detections:
            return

        # Check for persistent detections
        consecutive = self._count_consecutive_detections()
        threshold = self.get_parameter('consecutive_frames_for_alert').value

        if consecutive >= threshold:
            self._handle_safety_violation(safety_detections, msg, consecutive)

    def _count_consecutive_detections(self) -> int:
        """Count consecutive frames with safety detections."""
        count = 0
        for entry in reversed(self.detection_history):
            if entry['detections']:
                count += 1
            else:
                break
        return count

    def _handle_safety_violation(
        self,
        detections: list,
        msg: VisionDetectionArray,
        consecutive_frames: int
    ):
        """Handle confirmed safety violation."""
        # Check cooldown
        cooldown = self.get_parameter('cooldown_seconds').value
        if self.last_alert_time:
            elapsed = (datetime.now() - self.last_alert_time).total_seconds()
            if elapsed < cooldown:
                return

        # Determine severity
        critical_threshold = self.get_parameter('critical_zone_threshold').value
        warning_threshold = self.get_parameter('warning_zone_threshold').value

        # Find most critical detection
        most_critical = None
        highest_severity = 0

        for det in detections:
            # Calculate distance from center (spindle area)
            distance = ((det.x_center - 0.5) ** 2 + (det.y_center - 0.5) ** 2) ** 0.5

            if distance < critical_threshold:
                severity = 3  # Emergency
            elif distance < warning_threshold:
                severity = 2  # Critical
            else:
                severity = 1  # Warning

            if severity > highest_severity:
                highest_severity = severity
                most_critical = det

        if not most_critical:
            return

        # Create alert
        alert = VisionSafetyAlert()
        alert.header.stamp = self.get_clock().now().to_msg()
        alert.machine_id = self.get_parameter('machine_id').value
        alert.camera_id = msg.camera_id

        if highest_severity >= 3:
            alert.alert_level = VisionSafetyAlert.LEVEL_EMERGENCY
            alert.requires_estop = True
            alert.requires_pause = True
        elif highest_severity >= 2:
            alert.alert_level = VisionSafetyAlert.LEVEL_CRITICAL
            alert.requires_estop = self.get_parameter('enable_estop_on_intrusion').value
            alert.requires_pause = True
        else:
            alert.alert_level = VisionSafetyAlert.LEVEL_WARNING
            alert.requires_estop = False
            alert.requires_pause = True

        alert.alert_type = f'{most_critical.class_name}_detected'
        alert.object_class = most_critical.class_name
        alert.zone_name = self._get_zone_name(most_critical)
        alert.confidence = most_critical.confidence
        alert.x_position = most_critical.x_center
        alert.y_position = most_critical.y_center
        alert.consecutive_frames = consecutive_frames
        alert.recommended_action = self._get_recommended_action(alert)

        # Publish alert
        self.alert_pub.publish(alert)
        self.alert_count += 1
        self.last_alert_time = datetime.now()

        self.get_logger().warn(
            f'SAFETY ALERT: {alert.alert_type} in {alert.zone_name} '
            f'(level: {alert.alert_level}, frames: {consecutive_frames})'
        )

        # Trigger E-stop if required
        if alert.requires_estop and self.get_parameter('enable_estop_on_intrusion').value:
            self._trigger_estop(alert)

    def _get_zone_name(self, det) -> str:
        """Determine zone based on position."""
        distance = ((det.x_center - 0.5) ** 2 + (det.y_center - 0.5) ** 2) ** 0.5

        if distance < 0.2:
            return 'spindle_area'
        elif distance < 0.4:
            return 'fixture_zone'
        elif distance < 0.6:
            return 'work_envelope'
        else:
            return 'peripheral'

    def _get_recommended_action(self, alert: VisionSafetyAlert) -> str:
        """Generate recommended action based on alert."""
        if alert.alert_level == VisionSafetyAlert.LEVEL_EMERGENCY:
            return 'EMERGENCY STOP - Clear area immediately before reset'
        elif alert.alert_level == VisionSafetyAlert.LEVEL_CRITICAL:
            return 'Machine paused - Remove obstruction and verify area is clear'
        else:
            return 'Warning - Object detected near work area'

    def _trigger_estop(self, alert: VisionSafetyAlert):
        """Trigger emergency stop."""
        if self.estop_triggered:
            return

        if not self.estop_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().error('E-stop service not available')
            return

        request = EmergencyStop.Request()
        request.reason = f'Vision safety: {alert.alert_type}'

        future = self.estop_client.call_async(request)
        future.add_done_callback(self._estop_callback)

        self.estop_triggered = True
        self.get_logger().error(f'E-STOP TRIGGERED: {alert.alert_type}')

    def _estop_callback(self, future):
        """Handle E-stop response."""
        try:
            response = future.result()
            if response.success:
                self.get_logger().info('E-stop executed successfully')
            else:
                self.get_logger().error(f'E-stop failed: {response.message}')
        except Exception as e:
            self.get_logger().error(f'E-stop call failed: {e}')

    def publish_safety_state(self):
        """Publish current safety state."""
        msg = SafetyState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = self.get_parameter('machine_id').value

        # Determine current safety level
        recent_alerts = [
            entry for entry in self.detection_history[-5:]
            if entry['detections']
        ]

        if self.estop_triggered:
            msg.safety_level = SafetyState.SAFETY_EMERGENCY
            msg.reset_required = True
        elif len(recent_alerts) >= 3:
            msg.safety_level = SafetyState.SAFETY_CRITICAL
        elif recent_alerts:
            msg.safety_level = SafetyState.SAFETY_WARNING
        else:
            msg.safety_level = SafetyState.SAFETY_OK

        msg.light_curtain_clear = msg.safety_level == SafetyState.SAFETY_OK

        self.safety_state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = SafetyMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
