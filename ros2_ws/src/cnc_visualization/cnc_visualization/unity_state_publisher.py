#!/usr/bin/env python3
"""
Unity State Publisher Node
===========================
ROS2 node that publishes machine state to Unity Digital Twin clients.

Subscribes to:
- /machine/status (MachineStatus)
- /machine/position (JointState)
- /machine/sensors (SensorArray)

Publishes to:
- /unity/state (ISO23247State)
- MQTT: cnc/{machine_id}/unity/state

Features:
- ISO 23247-3 compliant state representation
- 60Hz position updates for smooth animation
- Velocity calculation for client-side interpolation
- Quality scoring based on data freshness
- MQTT bridge for Flask SCADA integration

Author: Flask CNC SCADA System
"""

import json
import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

# Standard ROS2 messages
from std_msgs.msg import Header, String
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Twist, Point

# Try to import custom messages
try:
    from cnc_interfaces.msg import (
        MachineStatus,
        ISO23247State,
        SensorArray,
        DigitalTwinState
    )
    CUSTOM_MSGS_AVAILABLE = True
except ImportError:
    CUSTOM_MSGS_AVAILABLE = False
    MachineStatus = None
    ISO23247State = None

# MQTT client
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Position3D:
    """3D position in millimeters."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    timestamp_us: int = 0


@dataclass
class Velocity3D:
    """3D velocity in mm/s."""
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0


@dataclass
class AxisState:
    """Individual axis state."""
    position: float = 0.0
    velocity: float = 0.0
    load: float = 0.0
    in_position: bool = True
    homed: bool = False


@dataclass
class UnityState:
    """Complete state for Unity rendering."""
    machine_id: str = "default"
    timestamp_us: int = 0

    # Position
    position: Position3D = field(default_factory=Position3D)
    velocity: Velocity3D = field(default_factory=Velocity3D)

    # Axes
    axes: Dict[str, AxisState] = field(default_factory=dict)

    # Spindle
    spindle_rpm: float = 0.0
    spindle_load: float = 0.0
    spindle_direction: str = "OFF"

    # Feed
    feed_rate: float = 0.0
    feed_override: float = 100.0

    # Tool
    tool_number: int = 0
    tool_diameter: float = 6.0
    tool_length: float = 50.0

    # Execution
    execution_state: str = "STOPPED"
    machine_mode: str = "MANUAL"
    active_line: int = 0
    program_progress: float = 0.0

    # Quality
    quality_score: float = 1.0


# =============================================================================
# Unity State Publisher Node
# =============================================================================

class UnityStatePublisher(Node):
    """
    ROS2 node that aggregates machine state and publishes to Unity clients.

    Runs at 60Hz for smooth visualization with velocity-based interpolation.
    """

    def __init__(self):
        super().__init__('unity_state_publisher')

        # Parameters
        self.declare_parameter('machine_id', 'cnc-1')
        self.declare_parameter('publish_rate_hz', 60.0)
        self.declare_parameter('mqtt_enabled', True)
        self.declare_parameter('mqtt_host', 'localhost')
        self.declare_parameter('mqtt_port', 1883)
        self.declare_parameter('quality_timeout_s', 1.0)

        self.machine_id = self.get_parameter('machine_id').value
        self.publish_rate_hz = self.get_parameter('publish_rate_hz').value
        self.mqtt_enabled = self.get_parameter('mqtt_enabled').value
        self.mqtt_host = self.get_parameter('mqtt_host').value
        self.mqtt_port = self.get_parameter('mqtt_port').value
        self.quality_timeout_s = self.get_parameter('quality_timeout_s').value

        # QoS profiles
        self.sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )

        self.reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE
        )

        # Callback group for concurrent processing
        self.callback_group = ReentrantCallbackGroup()

        # Current state
        self.state = UnityState(machine_id=self.machine_id)
        self.state_lock = threading.Lock()
        self.last_position_update = 0.0
        self.position_history = []

        # Initialize axes
        for axis in ['X', 'Y', 'Z', 'A', 'B', 'C']:
            self.state.axes[axis] = AxisState()

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        if self.mqtt_enabled and MQTT_AVAILABLE:
            self._init_mqtt()

        # Publishers
        self.unity_state_pub = self.create_publisher(
            String,  # JSON string for compatibility
            '/unity/state',
            self.reliable_qos
        )

        self.position_pub = self.create_publisher(
            Point,
            f'/unity/{self.machine_id}/position',
            self.sensor_qos
        )

        # Subscribers
        if CUSTOM_MSGS_AVAILABLE:
            self.status_sub = self.create_subscription(
                MachineStatus,
                '/machine/status',
                self._on_machine_status,
                self.reliable_qos,
                callback_group=self.callback_group
            )
        else:
            # Fallback to JSON string
            self.status_sub = self.create_subscription(
                String,
                '/machine/status/json',
                self._on_machine_status_json,
                self.reliable_qos,
                callback_group=self.callback_group
            )

        self.joint_sub = self.create_subscription(
            JointState,
            '/machine/joint_states',
            self._on_joint_state,
            self.sensor_qos,
            callback_group=self.callback_group
        )

        # Timer for publishing at fixed rate
        period = 1.0 / self.publish_rate_hz
        self.publish_timer = self.create_timer(
            period,
            self._publish_state,
            callback_group=self.callback_group
        )

        self.get_logger().info(
            f'Unity State Publisher started for {self.machine_id} at {self.publish_rate_hz}Hz'
        )

    def _init_mqtt(self) -> None:
        """Initialize MQTT client for Flask SCADA integration."""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=f'unity_state_publisher_{self.machine_id}',
                protocol=mqtt.MQTTv5
            )
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port)
            self.mqtt_client.loop_start()
            self.get_logger().info(f'MQTT connecting to {self.mqtt_host}:{self.mqtt_port}')
        except Exception as e:
            self.get_logger().warn(f'MQTT initialization failed: {e}')
            self.mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection."""
        if rc == 0:
            self.get_logger().info('MQTT connected successfully')
        else:
            self.get_logger().warn(f'MQTT connection failed: rc={rc}')

    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        """Handle MQTT disconnection."""
        self.get_logger().warn(f'MQTT disconnected: rc={rc}')

    def _on_machine_status(self, msg: 'MachineStatus') -> None:
        """Handle MachineStatus message from cnc_control node."""
        with self.state_lock:
            now = time.time()

            # Update position
            self.state.position.x = msg.mpos_x
            self.state.position.y = msg.mpos_y
            self.state.position.z = msg.mpos_z
            self.state.position.timestamp_us = int(now * 1_000_000)

            # Calculate velocity from position history
            self._update_velocity(now)

            # Update axes
            self.state.axes['X'].position = msg.mpos_x
            self.state.axes['Y'].position = msg.mpos_y
            self.state.axes['Z'].position = msg.mpos_z

            # Update spindle
            self.state.spindle_rpm = msg.spindle_speed
            self.state.spindle_direction = "CW" if msg.spindle_speed > 0 else "OFF"

            # Update feed
            self.state.feed_rate = msg.feed_rate

            # Update execution state
            self.state.execution_state = self._map_execution_state(msg.machine_state)
            self.state.active_line = msg.active_line

            # Update quality
            self.last_position_update = now
            self.state.quality_score = 1.0

    def _on_machine_status_json(self, msg: String) -> None:
        """Handle JSON machine status (fallback)."""
        try:
            data = json.loads(msg.data)
            with self.state_lock:
                now = time.time()

                if 'mpos' in data:
                    self.state.position.x = data['mpos'].get('x', 0)
                    self.state.position.y = data['mpos'].get('y', 0)
                    self.state.position.z = data['mpos'].get('z', 0)
                    self.state.position.timestamp_us = int(now * 1_000_000)

                self._update_velocity(now)
                self.last_position_update = now
                self.state.quality_score = 1.0

        except json.JSONDecodeError as e:
            self.get_logger().warn(f'Invalid JSON in machine status: {e}')

    def _on_joint_state(self, msg: JointState) -> None:
        """Handle JointState message for axis positions/velocities."""
        with self.state_lock:
            for i, name in enumerate(msg.name):
                axis_name = name.upper()
                if axis_name in self.state.axes:
                    if i < len(msg.position):
                        self.state.axes[axis_name].position = msg.position[i]
                    if i < len(msg.velocity):
                        self.state.axes[axis_name].velocity = msg.velocity[i]
                    if i < len(msg.effort):
                        self.state.axes[axis_name].load = msg.effort[i]

    def _update_velocity(self, now: float) -> None:
        """Calculate velocity from position history."""
        # Add current position to history
        self.position_history.append({
            'x': self.state.position.x,
            'y': self.state.position.y,
            'z': self.state.position.z,
            't': now
        })

        # Keep only last 5 samples
        if len(self.position_history) > 5:
            self.position_history.pop(0)

        # Calculate velocity from last two samples
        if len(self.position_history) >= 2:
            p1 = self.position_history[-2]
            p2 = self.position_history[-1]
            dt = p2['t'] - p1['t']
            if dt > 0:
                self.state.velocity.vx = (p2['x'] - p1['x']) / dt
                self.state.velocity.vy = (p2['y'] - p1['y']) / dt
                self.state.velocity.vz = (p2['z'] - p1['z']) / dt

    def _map_execution_state(self, state: int) -> str:
        """Map TinyG/GRBL state to MTConnect execution state."""
        state_map = {
            0: "UNAVAILABLE",
            1: "READY",       # Idle
            2: "STOPPED",     # Alarm
            3: "ACTIVE",      # Run
            4: "FEED_HOLD",   # Hold
            5: "ACTIVE",      # Jog
            6: "ACTIVE",      # Homing
            7: "STOPPED",     # Shutdown
        }
        return state_map.get(state, "UNAVAILABLE")

    def _publish_state(self) -> None:
        """Publish state to ROS2 and MQTT."""
        with self.state_lock:
            now = time.time()

            # Update quality score based on data age
            age = now - self.last_position_update
            if age < 0.1:
                self.state.quality_score = 1.0
            elif age < 1.0:
                self.state.quality_score = 1.0 - (age - 0.1) * 0.33
            elif age < 5.0:
                self.state.quality_score = 0.7 - (age - 1.0) * 0.125
            else:
                self.state.quality_score = 0.2

            # Update timestamp
            self.state.timestamp_us = int(now * 1_000_000)

            # Create state dict
            state_dict = {
                'machine_id': self.state.machine_id,
                'timestamp_us': self.state.timestamp_us,
                'position': {
                    'x': self.state.position.x,
                    'y': self.state.position.y,
                    'z': self.state.position.z
                },
                'velocity': {
                    'vx': self.state.velocity.vx,
                    'vy': self.state.velocity.vy,
                    'vz': self.state.velocity.vz
                },
                'spindle': {
                    'rpm': self.state.spindle_rpm,
                    'direction': self.state.spindle_direction
                },
                'feed_rate': self.state.feed_rate,
                'execution_state': self.state.execution_state,
                'quality_score': round(self.state.quality_score, 2)
            }

        # Publish to ROS2
        msg = String()
        msg.data = json.dumps(state_dict)
        self.unity_state_pub.publish(msg)

        # Publish position for simple subscribers
        pos_msg = Point()
        pos_msg.x = self.state.position.x
        pos_msg.y = self.state.position.y
        pos_msg.z = self.state.position.z
        self.position_pub.publish(pos_msg)

        # Publish to MQTT
        if self.mqtt_client and self.mqtt_client.is_connected():
            topic = f'cnc/{self.machine_id}/unity/state'
            self.mqtt_client.publish(topic, json.dumps(state_dict), qos=0)

    def destroy_node(self):
        """Clean up on shutdown."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        super().destroy_node()


# =============================================================================
# Main
# =============================================================================

def main(args=None):
    rclpy.init(args=args)

    node = UnityStatePublisher()

    executor = MultiThreadedExecutor(num_threads=4)
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
