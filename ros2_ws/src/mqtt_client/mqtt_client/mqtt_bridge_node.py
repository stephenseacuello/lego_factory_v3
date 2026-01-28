"""
MQTT-ROS 2 Bridge Node for CNC SCADA Integration.

Provides bidirectional communication between Flask SCADA (via MQTT) and ROS 2.

ROS 2 → MQTT:
- /tinyg/status → cnc/{machine_id}/tinyg/status
- /grbl/status → cnc/{machine_id}/grbl/status
- /sensors/raw → cnc/{machine_id}/sensors/{sensor_type}/data

MQTT → ROS 2:
- cnc/+/commands/jog → /machine/jog_cmd
- cnc/+/commands/gcode → /machine/gcode_cmd
- cnc/+/alarms → /system/alarms
"""
import json
import threading
from typing import Callable, Dict, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import paho.mqtt.client as mqtt

from cnc_interfaces.msg import MachineStatus, SensorReading, Alarm, GrblStatus
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from .message_converters import (
    machine_status_to_json,
    grbl_status_to_json,
    sensor_reading_to_json,
    alarm_to_json,
    json_to_alarm,
    json_to_dict,
)


class MqttBridgeNode(Node):
    """Bidirectional MQTT ↔ ROS 2 bridge for CNC SCADA integration."""

    def __init__(self):
        super().__init__('mqtt_bridge')

        # Declare parameters
        self.declare_parameter('broker_host', 'localhost')
        self.declare_parameter('broker_port', 1883)
        self.declare_parameter('client_id', 'ros2_mqtt_bridge')
        self.declare_parameter('username', '')
        self.declare_parameter('password', '')
        self.declare_parameter('use_tls', False)
        self.declare_parameter('reconnect_delay', 5.0)
        self.declare_parameter('keepalive', 60)

        # Get parameters
        self.broker_host = self.get_parameter('broker_host').value
        self.broker_port = self.get_parameter('broker_port').value
        self.client_id = self.get_parameter('client_id').value
        self.username = self.get_parameter('username').value
        self.password = self.get_parameter('password').value
        self.use_tls = self.get_parameter('use_tls').value
        self.reconnect_delay = self.get_parameter('reconnect_delay').value
        self.keepalive = self.get_parameter('keepalive').value

        # QoS profile for reliable communication
        self.qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client(client_id=self.client_id)
        self._setup_mqtt_callbacks()

        # Track connection state
        self.mqtt_connected = False

        # =====================================================================
        # ROS 2 → MQTT: Subscribe to ROS topics and publish to MQTT
        # =====================================================================

        # TinyG status
        self.tinyg_status_sub = self.create_subscription(
            MachineStatus,
            '/tinyg/status',
            self._tinyg_status_callback,
            self.qos
        )

        # GRBL status
        self.grbl_status_sub = self.create_subscription(
            GrblStatus,
            '/grbl/status',
            self._grbl_status_callback,
            self.qos
        )

        # Sensor readings
        self.sensor_sub = self.create_subscription(
            SensorReading,
            '/sensors/raw',
            self._sensor_callback,
            self.qos
        )

        # Alarms (ROS → MQTT)
        self.alarm_ros_sub = self.create_subscription(
            Alarm,
            '/system/alarms',
            self._alarm_to_mqtt_callback,
            self.qos
        )

        # =====================================================================
        # MQTT → ROS 2: Publish ROS messages from MQTT subscriptions
        # =====================================================================

        # Jog commands from MQTT
        self.jog_pub = self.create_publisher(
            Twist,
            '/machine/jog_cmd',
            self.qos
        )

        # G-code commands from MQTT
        self.gcode_pub = self.create_publisher(
            String,
            '/machine/gcode_cmd',
            self.qos
        )

        # Alarms from MQTT
        self.alarm_pub = self.create_publisher(
            Alarm,
            '/mqtt/alarms',
            self.qos
        )

        # Generic command passthrough
        self.command_pub = self.create_publisher(
            String,
            '/mqtt/commands',
            self.qos
        )

        # Connect to MQTT broker
        self._connect_mqtt()

        # Reconnection timer
        self.reconnect_timer = self.create_timer(
            self.reconnect_delay,
            self._check_mqtt_connection
        )

        self.get_logger().info(
            f'MQTT Bridge initialized. Broker: {self.broker_host}:{self.broker_port}'
        )

    def _setup_mqtt_callbacks(self):
        """Configure MQTT client callbacks."""
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message

        # Set credentials if provided
        if self.username:
            self.mqtt_client.username_pw_set(self.username, self.password)

        # TLS if enabled
        if self.use_tls:
            self.mqtt_client.tls_set()

    def _connect_mqtt(self):
        """Connect to MQTT broker."""
        try:
            self.get_logger().info(
                f'Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...'
            )
            self.mqtt_client.connect_async(
                self.broker_host,
                self.broker_port,
                self.keepalive
            )
            self.mqtt_client.loop_start()
        except Exception as e:
            self.get_logger().error(f'Failed to connect to MQTT broker: {e}')

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT connection is established."""
        if rc == 0:
            self.mqtt_connected = True
            self.get_logger().info('Connected to MQTT broker')

            # Subscribe to MQTT topics
            self._subscribe_mqtt_topics()
        else:
            self.get_logger().error(f'MQTT connection failed with code: {rc}')

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when MQTT connection is lost."""
        self.mqtt_connected = False
        if rc != 0:
            self.get_logger().warn(f'Unexpected MQTT disconnection (rc={rc}). Reconnecting...')

    def _subscribe_mqtt_topics(self):
        """Subscribe to MQTT topics for MQTT → ROS bridging."""
        topics = [
            ('cnc/+/commands/jog', 1),
            ('cnc/+/commands/gcode', 1),
            ('cnc/+/commands/+', 1),
            ('cnc/+/alarms', 1),
            ('cnc/commands/#', 1),
        ]

        for topic, qos in topics:
            self.mqtt_client.subscribe(topic, qos)
            self.get_logger().info(f'Subscribed to MQTT topic: {topic}')

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages and bridge to ROS."""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')

        self.get_logger().debug(f'MQTT message received: {topic}')

        try:
            # Route message based on topic pattern
            if '/commands/jog' in topic:
                self._handle_jog_command(topic, payload)
            elif '/commands/gcode' in topic:
                self._handle_gcode_command(topic, payload)
            elif '/alarms' in topic:
                self._handle_alarm_message(topic, payload)
            else:
                # Generic command passthrough
                self._handle_generic_command(topic, payload)

        except Exception as e:
            self.get_logger().error(f'Error processing MQTT message: {e}')

    def _handle_jog_command(self, topic: str, payload: str):
        """Convert MQTT jog command to ROS Twist message."""
        try:
            data = json.loads(payload)
            twist = Twist()

            # Support both axis-specific and vector-based jog commands
            if 'axis' in data:
                # Axis-specific: {"axis": "x", "distance": 10.0, "feed_rate": 1000}
                axis = data.get('axis', '').lower()
                distance = float(data.get('distance', 0.0))
                feed_rate = float(data.get('feed_rate', 1000.0))

                # Encode distance in linear velocity, feed_rate in angular.z
                if axis == 'x':
                    twist.linear.x = distance
                elif axis == 'y':
                    twist.linear.y = distance
                elif axis == 'z':
                    twist.linear.z = distance

                twist.angular.z = feed_rate  # Store feed rate

            else:
                # Vector-based: {"x": 10.0, "y": 5.0, "z": -2.0, "feed_rate": 1000}
                twist.linear.x = float(data.get('x', 0.0))
                twist.linear.y = float(data.get('y', 0.0))
                twist.linear.z = float(data.get('z', 0.0))
                twist.angular.z = float(data.get('feed_rate', 1000.0))

            self.jog_pub.publish(twist)
            self.get_logger().debug(f'Published jog command: {data}')

        except json.JSONDecodeError as e:
            self.get_logger().error(f'Invalid JSON in jog command: {e}')

    def _handle_gcode_command(self, topic: str, payload: str):
        """Forward G-code command to ROS."""
        msg = String()
        msg.data = payload
        self.gcode_pub.publish(msg)
        self.get_logger().debug(f'Published G-code command: {payload[:50]}...')

    def _handle_alarm_message(self, topic: str, payload: str):
        """Convert MQTT alarm to ROS Alarm message."""
        try:
            alarm_msg = json_to_alarm(payload, Alarm)
            self.alarm_pub.publish(alarm_msg)
            self.get_logger().info(f'Published alarm: {alarm_msg.message}')
        except Exception as e:
            self.get_logger().error(f'Error parsing alarm message: {e}')

    def _handle_generic_command(self, topic: str, payload: str):
        """Passthrough for unrecognized commands."""
        msg = String()
        msg.data = json.dumps({'topic': topic, 'payload': payload})
        self.command_pub.publish(msg)

    # =========================================================================
    # ROS → MQTT Callbacks
    # =========================================================================

    def _tinyg_status_callback(self, msg: MachineStatus):
        """Forward TinyG status to MQTT."""
        if not self.mqtt_connected:
            return

        topic = f'cnc/{msg.machine_id}/tinyg/status'
        payload = machine_status_to_json(msg)
        self.mqtt_client.publish(topic, payload, qos=1)

    def _grbl_status_callback(self, msg: GrblStatus):
        """Forward GRBL status to MQTT."""
        if not self.mqtt_connected:
            return

        topic = f'cnc/{msg.machine_id}/grbl/status'
        payload = grbl_status_to_json(msg)
        self.mqtt_client.publish(topic, payload, qos=1)

    def _sensor_callback(self, msg: SensorReading):
        """Forward sensor readings to MQTT."""
        if not self.mqtt_connected:
            return

        topic = f'cnc/sensors/{msg.sensor_id}/{msg.sensor_type}/data'
        payload = sensor_reading_to_json(msg)
        self.mqtt_client.publish(topic, payload, qos=0)  # QoS 0 for high-frequency data

    def _alarm_to_mqtt_callback(self, msg: Alarm):
        """Forward ROS alarms to MQTT."""
        if not self.mqtt_connected:
            return

        topic = f'cnc/{msg.machine_id}/alarms'
        payload = alarm_to_json(msg)
        self.mqtt_client.publish(topic, payload, qos=2)  # QoS 2 for alarms

    def _check_mqtt_connection(self):
        """Periodic check for MQTT connection and reconnect if needed."""
        if not self.mqtt_connected:
            self.get_logger().info('Attempting MQTT reconnection...')
            try:
                self.mqtt_client.reconnect()
            except Exception as e:
                self.get_logger().warn(f'MQTT reconnection failed: {e}')

    def destroy_node(self):
        """Clean up MQTT client on shutdown."""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        super().destroy_node()


def main(args=None):
    """Entry point for mqtt_bridge node."""
    rclpy.init(args=args)

    node = MqttBridgeNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
