#!/usr/bin/env python3
"""
CNC Diagnostics Aggregator Node
===============================
Aggregates health information from all CNC subsystems and publishes
unified diagnostics to /diagnostics topic (diagnostic_msgs/DiagnosticArray).

Features:
- Machine state monitoring (TinyG, GRBL)
- Sensor variance tracking
- Alarm aggregation and alerting
- Heartbeat monitoring
"""

from collections import deque
from datetime import datetime
from typing import Dict, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from cnc_interfaces.msg import MachineStatus, GrblStatus, SensorReading, Alarm

# Try to import numpy, fall back to pure Python if not available
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class DiagnosticsNode(Node):
    """
    Aggregates health from all CNC subsystems.

    Subscribes to:
        - /tinyg/status: TinyG machine status
        - /grbl/status: GRBL machine status
        - /sensors/raw: Sensor readings

    Publishes:
        - /diagnostics: Aggregated diagnostic messages
        - /system/alarms: Alarm notifications
    """

    def __init__(self):
        super().__init__('cnc_diagnostics')

        # Parameters
        self.declare_parameter('publish_rate', 1.0)  # Hz
        self.declare_parameter('sensor_buffer_size', 100)
        self.declare_parameter('variance_threshold', 10.0)
        self.declare_parameter('heartbeat_timeout', 5.0)  # seconds

        self.publish_rate = self.get_parameter('publish_rate').value
        self.sensor_buffer_size = self.get_parameter('sensor_buffer_size').value
        self.variance_threshold = self.get_parameter('variance_threshold').value
        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout').value

        # State tracking
        self.machine_states: Dict[str, dict] = {}
        self.sensor_buffers: Dict[str, deque] = {}
        self.last_heartbeats: Dict[str, datetime] = {}

        # QoS for reliable diagnostics
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscriptions
        self.tinyg_sub = self.create_subscription(
            MachineStatus,
            '/tinyg/status',
            self._tinyg_callback,
            10
        )

        self.grbl_sub = self.create_subscription(
            GrblStatus,
            '/grbl/status',
            self._grbl_callback,
            10
        )

        self.sensor_sub = self.create_subscription(
            SensorReading,
            '/sensors/raw',
            self._sensor_callback,
            10
        )

        # Publishers
        self.diag_pub = self.create_publisher(
            DiagnosticArray,
            '/diagnostics',
            qos_reliable
        )

        self.alarm_pub = self.create_publisher(
            Alarm,
            '/system/alarms',
            qos_reliable
        )

        # Timer for periodic diagnostics publishing
        period = 1.0 / self.publish_rate
        self.diag_timer = self.create_timer(period, self._publish_diagnostics)

        # Timer for heartbeat checking
        self.heartbeat_timer = self.create_timer(1.0, self._check_heartbeats)

        self.get_logger().info('=' * 60)
        self.get_logger().info('CNC Diagnostics Aggregator Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'Publish rate: {self.publish_rate} Hz')
        self.get_logger().info(f'Variance threshold: {self.variance_threshold}')
        self.get_logger().info('Subscribing to: /tinyg/status, /grbl/status, /sensors/raw')
        self.get_logger().info('Publishing to: /diagnostics, /system/alarms')
        self.get_logger().info('=' * 60)

    def _tinyg_callback(self, msg: MachineStatus):
        """Process TinyG status update."""
        machine_id = msg.machine_id or 'tinyg'
        self.last_heartbeats[machine_id] = datetime.now()

        self.machine_states[machine_id] = {
            'type': 'tinyg',
            'state': msg.state_text,
            'state_code': msg.state,
            'position': {
                'x': msg.mpos_x,
                'y': msg.mpos_y,
                'z': msg.mpos_z
            },
            'feed_rate': msg.feed_rate,
            'spindle_speed': msg.spindle_speed,
            'buffer_available': msg.buffer_available,
            'timestamp': datetime.now()
        }

        # Check for alarm state
        if msg.state == 4:  # ALARM state
            self._publish_alarm(
                machine_id,
                'MACHINE_ALARM',
                Alarm.SEVERITY_ERROR,
                f'TinyG in ALARM state'
            )

    def _grbl_callback(self, msg: GrblStatus):
        """Process GRBL status update."""
        machine_id = msg.machine_id or 'grbl'
        self.last_heartbeats[machine_id] = datetime.now()

        self.machine_states[machine_id] = {
            'type': 'grbl',
            'state': msg.state_text,
            'state_code': msg.state,
            'position': {
                'x': msg.mpos_x,
                'y': msg.mpos_y,
                'z': msg.mpos_z
            },
            'feed_rate': msg.feed_rate,
            'spindle_speed': msg.spindle_speed,
            'buffer_available': msg.buffer_available,
            'timestamp': datetime.now()
        }

        # Check for alarm state
        if msg.state == 4:  # ALARM state
            self._publish_alarm(
                machine_id,
                'MACHINE_ALARM',
                Alarm.SEVERITY_ERROR,
                f'GRBL in ALARM state: {msg.alarm_code}'
            )

    def _sensor_callback(self, msg: SensorReading):
        """Process sensor reading and track variance."""
        sensor_id = msg.sensor_id
        self.last_heartbeats[f'sensor_{sensor_id}'] = datetime.now()

        # Initialize buffer if needed
        if sensor_id not in self.sensor_buffers:
            self.sensor_buffers[sensor_id] = deque(maxlen=self.sensor_buffer_size)

        # Store the reading (use Z-axis acceleration for variance tracking)
        if len(msg.values) >= 3:
            self.sensor_buffers[sensor_id].append(msg.values[2])

            # Check variance when buffer is full
            if len(self.sensor_buffers[sensor_id]) >= self.sensor_buffer_size:
                variance = self._calculate_variance(list(self.sensor_buffers[sensor_id]))
                if variance > self.variance_threshold:
                    self._publish_alarm(
                        sensor_id,
                        'SENSOR_VARIANCE_HIGH',
                        Alarm.SEVERITY_WARNING,
                        f'High sensor variance detected: {variance:.2f} > {self.variance_threshold}'
                    )

    def _calculate_variance(self, data) -> float:
        """Calculate variance of data."""
        if HAS_NUMPY:
            return float(np.var(data))
        else:
            # Pure Python variance calculation
            n = len(data)
            if n < 2:
                return 0.0
            mean = sum(data) / n
            return sum((x - mean) ** 2 for x in data) / n

    def _check_heartbeats(self):
        """Check for missing heartbeats from subsystems."""
        now = datetime.now()
        timeout = self.heartbeat_timeout

        for source_id, last_seen in list(self.last_heartbeats.items()):
            elapsed = (now - last_seen).total_seconds()
            if elapsed > timeout:
                self._publish_alarm(
                    source_id,
                    'HEARTBEAT_TIMEOUT',
                    Alarm.SEVERITY_WARNING,
                    f'No heartbeat from {source_id} for {elapsed:.1f}s'
                )
                # Remove to avoid repeated alarms
                del self.last_heartbeats[source_id]

    def _publish_diagnostics(self):
        """Publish aggregated diagnostics."""
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        # Add machine diagnostics
        for machine_id, state in self.machine_states.items():
            status = DiagnosticStatus()
            status.name = f'CNC/{machine_id}'
            status.hardware_id = machine_id

            # Determine level based on state
            state_code = state.get('state_code', 0)
            if state_code == 4:  # ALARM
                status.level = DiagnosticStatus.ERROR
                status.message = f'Machine in ALARM state: {state.get("state", "unknown")}'
            elif state_code == 3:  # HOLDING
                status.level = DiagnosticStatus.WARN
                status.message = f'Machine holding: {state.get("state", "unknown")}'
            else:
                status.level = DiagnosticStatus.OK
                status.message = f'Machine state: {state.get("state", "unknown")}'

            # Add key-value pairs
            status.values = [
                KeyValue(key='state', value=str(state.get('state', 'unknown'))),
                KeyValue(key='type', value=str(state.get('type', 'unknown'))),
                KeyValue(key='x', value=f'{state.get("position", {}).get("x", 0):.3f}'),
                KeyValue(key='y', value=f'{state.get("position", {}).get("y", 0):.3f}'),
                KeyValue(key='z', value=f'{state.get("position", {}).get("z", 0):.3f}'),
                KeyValue(key='feed_rate', value=f'{state.get("feed_rate", 0):.1f}'),
                KeyValue(key='spindle_speed', value=f'{state.get("spindle_speed", 0):.0f}'),
                KeyValue(key='buffer_available', value=str(state.get('buffer_available', 0))),
            ]

            diag_array.status.append(status)

        # Add sensor diagnostics
        for sensor_id, buffer in self.sensor_buffers.items():
            status = DiagnosticStatus()
            status.name = f'Sensor/{sensor_id}'
            status.hardware_id = sensor_id

            if len(buffer) >= 10:
                variance = self._calculate_variance(list(buffer))
                if variance > self.variance_threshold:
                    status.level = DiagnosticStatus.WARN
                    status.message = f'High variance: {variance:.2f}'
                else:
                    status.level = DiagnosticStatus.OK
                    status.message = f'Variance: {variance:.2f}'

                status.values = [
                    KeyValue(key='variance', value=f'{variance:.4f}'),
                    KeyValue(key='samples', value=str(len(buffer))),
                ]
            else:
                status.level = DiagnosticStatus.STALE
                status.message = 'Insufficient data'
                status.values = [
                    KeyValue(key='samples', value=str(len(buffer))),
                ]

            diag_array.status.append(status)

        # Add system-level status
        system_status = DiagnosticStatus()
        system_status.name = 'CNC/System'
        system_status.hardware_id = 'cnc_system'
        system_status.level = DiagnosticStatus.OK
        system_status.message = f'{len(self.machine_states)} machines, {len(self.sensor_buffers)} sensors active'
        system_status.values = [
            KeyValue(key='machines_active', value=str(len(self.machine_states))),
            KeyValue(key='sensors_active', value=str(len(self.sensor_buffers))),
            KeyValue(key='heartbeats_tracked', value=str(len(self.last_heartbeats))),
        ]
        diag_array.status.append(system_status)

        self.diag_pub.publish(diag_array)

    def _publish_alarm(
        self,
        source_id: str,
        alarm_type: str,
        severity: int,
        message: str
    ):
        """Publish an alarm notification."""
        alarm = Alarm()
        alarm.alarm_id = f'{source_id}_{alarm_type}_{datetime.now().timestamp()}'
        alarm.source = source_id
        alarm.alarm_type = alarm_type
        alarm.severity = severity
        alarm.message = message
        alarm.timestamp = self.get_clock().now().to_msg()
        alarm.acknowledged = False

        self.alarm_pub.publish(alarm)
        self.get_logger().warn(f'ALARM [{alarm_type}] {source_id}: {message}')


def main(args=None):
    rclpy.init(args=args)
    node = DiagnosticsNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down diagnostics node...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
