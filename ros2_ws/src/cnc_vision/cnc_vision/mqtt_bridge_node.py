#!/usr/bin/env python3
"""
Vision MQTT Bridge Node

Bridges ROS2 vision topics to MQTT for Flask SCADA integration.
Publishes detections, safety alerts, and status to MQTT broker.
"""

import os
import json
from datetime import datetime

import rclpy
from rclpy.node import Node
import paho.mqtt.client as mqtt

from cnc_interfaces.msg import (
    VisionDetection,
    VisionDetectionArray,
    VisionSafetyAlert,
    VisionStatus,
)


class VisionMQTTBridgeNode(Node):
    """
    Bridges ROS2 vision messages to MQTT.

    Subscribes to:
    - /vision/detections
    - /vision/safety_alerts
    - /vision/status

    Publishes to MQTT topics:
    - cnc/{machine_id}/vision/detections
    - cnc/{machine_id}/vision/safety
    - cnc/{machine_id}/vision/status
    """

    def __init__(self):
        super().__init__('vision_mqtt_bridge')

        # Declare parameters
        self.declare_parameter('mqtt_host', os.getenv('MQTT_BROKER_HOST', 'mosquitto'))
        self.declare_parameter('mqtt_port', int(os.getenv('MQTT_BROKER_PORT', '1883')))
        self.declare_parameter('mqtt_username', os.getenv('MQTT_USERNAME', ''))
        self.declare_parameter('mqtt_password', os.getenv('MQTT_PASSWORD', ''))
        self.declare_parameter('topic_prefix', 'cnc')
        self.declare_parameter('machine_id', 'default')
        self.declare_parameter('qos', 1)
        self.declare_parameter('publish_all_detections', True)

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client(client_id=f'ros2_vision_bridge_{os.getpid()}')

        # Set credentials if provided
        username = self.get_parameter('mqtt_username').value
        password = self.get_parameter('mqtt_password').value
        if username:
            self.mqtt_client.username_pw_set(username, password)

        # Connect callbacks
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect

        # Connect to broker
        host = self.get_parameter('mqtt_host').value
        port = self.get_parameter('mqtt_port').value

        try:
            self.mqtt_client.connect(host, port, keepalive=60)
            self.mqtt_client.loop_start()
            self.get_logger().info(f'Connected to MQTT broker: {host}:{port}')
        except Exception as e:
            self.get_logger().error(f'Failed to connect to MQTT: {e}')

        # ROS2 subscribers
        self.detection_sub = self.create_subscription(
            VisionDetectionArray,
            '/vision/detections',
            self.detection_callback,
            10
        )
        self.safety_sub = self.create_subscription(
            VisionSafetyAlert,
            '/vision/safety_alerts',
            self.safety_alert_callback,
            10
        )
        self.status_sub = self.create_subscription(
            VisionStatus,
            '/vision/status',
            self.status_callback,
            10
        )

        self.get_logger().info('Vision MQTT Bridge initialized')

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self.get_logger().info('MQTT connected successfully')
        else:
            self.get_logger().error(f'MQTT connection failed: {rc}')

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self.get_logger().warn(f'MQTT disconnected: {rc}')

    def _get_topic(self, subtopic: str, machine_id: str = None) -> str:
        """Build MQTT topic."""
        prefix = self.get_parameter('topic_prefix').value
        machine = machine_id or self.get_parameter('machine_id').value
        return f'{prefix}/{machine}/vision/{subtopic}'

    def detection_callback(self, msg: VisionDetectionArray):
        """Handle detection array messages."""
        if not self.get_parameter('publish_all_detections').value:
            return

        qos = self.get_parameter('qos').value

        # Build payload
        payload = {
            'timestamp': datetime.now().isoformat(),
            'frame_id': msg.frame_id,
            'image_width': msg.image_width,
            'image_height': msg.image_height,
            'total_detections': msg.total_detections,
            'inference_time_ms': msg.inference_time_ms,
            'machine_id': msg.machine_id,
            'camera_id': msg.camera_id,
            'detections': []
        }

        for det in msg.detections:
            payload['detections'].append({
                'type': det.detection_type,
                'class': det.class_name,
                'confidence': det.confidence,
                'bbox': {
                    'x_center': det.x_center,
                    'y_center': det.y_center,
                    'width': det.width,
                    'height': det.height,
                }
            })

        topic = self._get_topic('detections', msg.machine_id)
        self.mqtt_client.publish(topic, json.dumps(payload), qos=qos)

        # Also publish by detection type
        detection_types = set(d.detection_type for d in msg.detections)
        for det_type in detection_types:
            type_detections = [d for d in msg.detections if d.detection_type == det_type]
            type_payload = {
                'timestamp': datetime.now().isoformat(),
                'count': len(type_detections),
                'detections': [
                    {'class': d.class_name, 'confidence': d.confidence}
                    for d in type_detections
                ]
            }
            type_topic = self._get_topic(f'{det_type}s', msg.machine_id)
            self.mqtt_client.publish(type_topic, json.dumps(type_payload), qos=qos)

    def safety_alert_callback(self, msg: VisionSafetyAlert):
        """Handle safety alert messages - HIGH PRIORITY."""
        qos = 2  # Use highest QoS for safety alerts

        # Build payload
        payload = {
            'timestamp': datetime.now().isoformat(),
            'machine_id': msg.machine_id,
            'camera_id': msg.camera_id,
            'alert_level': msg.alert_level,
            'alert_level_name': self._level_to_name(msg.alert_level),
            'alert_type': msg.alert_type,
            'object_class': msg.object_class,
            'zone': msg.zone_name,
            'confidence': msg.confidence,
            'position': {
                'x': msg.x_position,
                'y': msg.y_position,
            },
            'requires_estop': msg.requires_estop,
            'requires_pause': msg.requires_pause,
            'recommended_action': msg.recommended_action,
            'snapshot_path': msg.snapshot_path,
        }

        # Publish to safety topic
        topic = self._get_topic('safety', msg.machine_id)
        self.mqtt_client.publish(topic, json.dumps(payload), qos=qos, retain=True)

        # Also publish to alerts topic for general monitoring
        alerts_topic = self._get_topic('alerts', msg.machine_id)
        self.mqtt_client.publish(alerts_topic, json.dumps(payload), qos=qos)

        # If critical/emergency, publish to emergency topic
        if msg.alert_level >= VisionSafetyAlert.LEVEL_CRITICAL:
            emergency_topic = f'{self.get_parameter("topic_prefix").value}/emergency'
            self.mqtt_client.publish(emergency_topic, json.dumps(payload), qos=qos)

        self.get_logger().warn(
            f'SAFETY ALERT published: {msg.alert_type} ({self._level_to_name(msg.alert_level)})'
        )

    def _level_to_name(self, level: int) -> str:
        """Convert alert level to name."""
        levels = {
            VisionSafetyAlert.LEVEL_INFO: 'INFO',
            VisionSafetyAlert.LEVEL_WARNING: 'WARNING',
            VisionSafetyAlert.LEVEL_CRITICAL: 'CRITICAL',
            VisionSafetyAlert.LEVEL_EMERGENCY: 'EMERGENCY',
        }
        return levels.get(level, 'UNKNOWN')

    def status_callback(self, msg: VisionStatus):
        """Handle status messages."""
        qos = self.get_parameter('qos').value

        payload = {
            'timestamp': datetime.now().isoformat(),
            'machine_id': msg.machine_id,
            'camera_connected': msg.camera_connected,
            'camera_device': msg.camera_device,
            'frame_width': msg.frame_width,
            'frame_height': msg.frame_height,
            'fps_actual': msg.fps_actual,
            'inference_running': msg.inference_running,
            'inference_server_url': msg.inference_server_url,
            'active_model': msg.active_model,
            'performance': {
                'avg_inference_ms': msg.avg_inference_time_ms,
                'max_inference_ms': msg.max_inference_time_ms,
                'min_inference_ms': msg.min_inference_time_ms,
                'frames_processed': msg.frames_processed,
                'frames_dropped': msg.frames_dropped,
            },
            'detection_stats': {
                'total': msg.total_detections,
                'defects': msg.defect_detections,
                'safety': msg.safety_detections,
                'tool_wear': msg.tool_wear_detections,
                'parts': msg.part_detections,
            },
            'health': {
                'status': msg.health_status,
                'message': msg.health_message,
                'warnings': list(msg.active_warnings),
            }
        }

        topic = self._get_topic('status', msg.machine_id)
        self.mqtt_client.publish(topic, json.dumps(payload), qos=qos, retain=True)

    def destroy_node(self):
        """Clean up MQTT connection."""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = VisionMQTTBridgeNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
