#!/usr/bin/env python3
"""
Sensor Health Monitor Node
==========================
Specialized node for monitoring sensor data quality, detecting anomalies,
and tracking sensor calibration drift.

Features:
- Real-time noise analysis
- Calibration drift detection
- Anomaly detection using statistical methods
- Sensor timeout monitoring
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node

from cnc_interfaces.msg import SensorReading, Alarm
from diagnostic_msgs.msg import DiagnosticStatus

# Try to import numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class SensorMonitorNode(Node):
    """
    Monitors sensor health and data quality.

    Subscribes to:
        - /sensors/raw: Raw sensor readings

    Publishes:
        - /sensors/health: Sensor health status
        - /system/alarms: Alarm notifications
    """

    def __init__(self):
        super().__init__('sensor_monitor')

        # Parameters
        self.declare_parameter('window_size', 100)
        self.declare_parameter('noise_threshold', 0.5)
        self.declare_parameter('drift_threshold', 2.0)
        self.declare_parameter('timeout_sec', 5.0)
        self.declare_parameter('anomaly_z_score', 3.0)

        self.window_size = self.get_parameter('window_size').value
        self.noise_threshold = self.get_parameter('noise_threshold').value
        self.drift_threshold = self.get_parameter('drift_threshold').value
        self.timeout_sec = self.get_parameter('timeout_sec').value
        self.anomaly_z_score = self.get_parameter('anomaly_z_score').value

        # Data structures
        self.sensor_data: Dict[str, Dict] = {}

        # Subscriptions
        self.sensor_sub = self.create_subscription(
            SensorReading,
            '/sensors/raw',
            self._sensor_callback,
            10
        )

        # Publishers
        self.alarm_pub = self.create_publisher(Alarm, '/system/alarms', 10)

        # Timer for periodic health checks
        self.check_timer = self.create_timer(1.0, self._check_sensors)

        self.get_logger().info('Sensor Monitor Node started')
        self.get_logger().info(f'  Window size: {self.window_size}')
        self.get_logger().info(f'  Noise threshold: {self.noise_threshold}')
        self.get_logger().info(f'  Anomaly Z-score: {self.anomaly_z_score}')

    def _sensor_callback(self, msg: SensorReading):
        """Process incoming sensor reading."""
        sensor_id = msg.sensor_id

        # Initialize tracking for new sensor
        if sensor_id not in self.sensor_data:
            self.sensor_data[sensor_id] = {
                'type': msg.sensor_type,
                'buffer': deque(maxlen=self.window_size),
                'last_seen': datetime.now(),
                'baseline_mean': None,
                'baseline_std': None,
                'anomaly_count': 0
            }

        data = self.sensor_data[sensor_id]
        data['last_seen'] = datetime.now()

        # Store values (flatten multi-axis data)
        if len(msg.values) >= 3:
            # For IMU, compute magnitude
            magnitude = self._compute_magnitude(msg.values[:3])
            data['buffer'].append(magnitude)

            # Check for anomalies
            if len(data['buffer']) >= self.window_size // 2:
                self._check_anomaly(sensor_id, magnitude)

    def _compute_magnitude(self, values: List[float]) -> float:
        """Compute magnitude of 3D vector."""
        if HAS_NUMPY:
            return float(np.linalg.norm(values))
        else:
            return (values[0]**2 + values[1]**2 + values[2]**2) ** 0.5

    def _check_anomaly(self, sensor_id: str, value: float):
        """Check if current value is anomalous."""
        data = self.sensor_data[sensor_id]
        buffer = list(data['buffer'])

        if len(buffer) < 10:
            return

        # Calculate rolling statistics
        if HAS_NUMPY:
            mean = np.mean(buffer[:-1])
            std = np.std(buffer[:-1])
        else:
            n = len(buffer) - 1
            mean = sum(buffer[:-1]) / n
            variance = sum((x - mean) ** 2 for x in buffer[:-1]) / n
            std = variance ** 0.5

        # Update baseline if not set
        if data['baseline_mean'] is None:
            data['baseline_mean'] = mean
            data['baseline_std'] = std

        # Check Z-score for anomaly
        if std > 0:
            z_score = abs(value - mean) / std
            if z_score > self.anomaly_z_score:
                data['anomaly_count'] += 1
                if data['anomaly_count'] >= 3:  # Require multiple consecutive
                    self._publish_alarm(
                        sensor_id,
                        'SENSOR_ANOMALY',
                        Alarm.SEVERITY_WARNING,
                        f'Anomalous reading detected (Z={z_score:.2f})'
                    )
                    data['anomaly_count'] = 0
            else:
                data['anomaly_count'] = 0

        # Check for calibration drift
        if data['baseline_mean'] is not None and data['baseline_std'] is not None:
            drift = abs(mean - data['baseline_mean'])
            if drift > self.drift_threshold * data['baseline_std']:
                self._publish_alarm(
                    sensor_id,
                    'SENSOR_DRIFT',
                    Alarm.SEVERITY_WARNING,
                    f'Calibration drift detected: {drift:.4f}'
                )

    def _check_sensors(self):
        """Periodic check for sensor timeouts and noise levels."""
        now = datetime.now()

        for sensor_id, data in list(self.sensor_data.items()):
            # Check timeout
            elapsed = (now - data['last_seen']).total_seconds()
            if elapsed > self.timeout_sec:
                self._publish_alarm(
                    sensor_id,
                    'SENSOR_TIMEOUT',
                    Alarm.SEVERITY_ERROR,
                    f'No data for {elapsed:.1f}s'
                )
                # Remove stale sensor
                del self.sensor_data[sensor_id]
                continue

            # Check noise level
            if len(data['buffer']) >= self.window_size:
                if HAS_NUMPY:
                    std = np.std(list(data['buffer']))
                else:
                    buffer = list(data['buffer'])
                    mean = sum(buffer) / len(buffer)
                    variance = sum((x - mean) ** 2 for x in buffer) / len(buffer)
                    std = variance ** 0.5

                if std > self.noise_threshold:
                    self._publish_alarm(
                        sensor_id,
                        'SENSOR_NOISE_HIGH',
                        Alarm.SEVERITY_WARNING,
                        f'High noise level: {std:.4f}'
                    )

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
        self.get_logger().warn(f'SENSOR ALARM [{alarm_type}] {source_id}: {message}')


def main(args=None):
    rclpy.init(args=args)
    node = SensorMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down sensor monitor...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
