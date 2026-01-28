#!/usr/bin/env python3
"""
Anomaly Detector - Real-time anomaly detection for CNC machines

Uses statistical methods and optional ML models to detect anomalies in:
- Vibration patterns
- Temperature trends
- Power consumption
- Motion profiles
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np
from scipy import stats

from std_msgs.msg import String
from cnc_interfaces.msg import (
    SensorReading,
    MachineStatus,
    Alarm,
    PredictiveMaintenance,
)


@dataclass
class AnomalyProfile:
    """Statistical profile for anomaly detection"""
    sensor_id: str
    sensor_type: str

    # Rolling statistics
    values: deque = field(default_factory=lambda: deque(maxlen=500))

    # Baseline statistics (calculated during normal operation)
    baseline_mean: float = 0.0
    baseline_std: float = 1.0
    baseline_samples: int = 0
    baseline_established: bool = False

    # Detection thresholds
    z_threshold: float = 3.0  # Standard deviations
    iqr_multiplier: float = 1.5

    # Anomaly tracking
    anomaly_count: int = 0
    consecutive_anomalies: int = 0
    last_anomaly_time: float = 0.0

    def add_value(self, value: float):
        self.values.append(value)

    def establish_baseline(self, min_samples: int = 100):
        """Calculate baseline from collected data"""
        if len(self.values) >= min_samples:
            arr = np.array(self.values)
            self.baseline_mean = np.mean(arr)
            self.baseline_std = max(np.std(arr), 0.001)  # Avoid zero
            self.baseline_samples = len(arr)
            self.baseline_established = True
            return True
        return False

    def detect_anomaly(self, value: float) -> Tuple[bool, float, str]:
        """
        Detect if value is anomalous
        Returns: (is_anomaly, anomaly_score, detection_method)
        """
        if not self.baseline_established:
            return False, 0.0, "baseline_not_established"

        # Z-score method
        z_score = abs(value - self.baseline_mean) / self.baseline_std
        if z_score > self.z_threshold:
            return True, z_score, "z_score"

        # IQR method (robust to outliers)
        arr = np.array(self.values)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr

        if value < lower or value > upper:
            deviation = max(abs(value - lower), abs(value - upper)) / max(iqr, 0.001)
            return True, deviation, "iqr"

        return False, z_score, "normal"


class AnomalyDetectorNode(Node):
    """Real-time anomaly detection for CNC machines"""

    def __init__(self):
        super().__init__('anomaly_detector')

        # Parameters
        self.declare_parameter('z_threshold', 3.0)
        self.declare_parameter('baseline_samples', 100)
        self.declare_parameter('publish_rate', 2.0)
        self.declare_parameter('alarm_consecutive_threshold', 5)

        self.z_threshold = self.get_parameter('z_threshold').value
        self.baseline_samples = self.get_parameter('baseline_samples').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.alarm_threshold = self.get_parameter('alarm_consecutive_threshold').value

        # Sensor profiles
        self.profiles: Dict[str, AnomalyProfile] = {}

        # Recent anomalies for reporting
        self.recent_anomalies: deque = deque(maxlen=100)

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers
        self.sensor_sub = self.create_subscription(
            SensorReading,
            '/sensors/raw',
            self.sensor_callback,
            qos
        )

        # Publishers
        self.alarm_pub = self.create_publisher(
            Alarm,
            '/anomaly/alarms',
            qos
        )

        self.prediction_pub = self.create_publisher(
            PredictiveMaintenance,
            '/anomaly/predictions',
            qos
        )

        # Timer for baseline updates
        self.baseline_timer = self.create_timer(
            10.0,  # Every 10 seconds
            self.update_baselines
        )

        self.get_logger().info('Anomaly Detector started')

    def get_or_create_profile(self, sensor_id: str, sensor_type: str) -> AnomalyProfile:
        """Get or create anomaly profile for sensor"""
        key = f"{sensor_id}_{sensor_type}"
        if key not in self.profiles:
            self.profiles[key] = AnomalyProfile(
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                z_threshold=self.z_threshold
            )
        return self.profiles[key]

    def sensor_callback(self, msg: SensorReading):
        """Process sensor reading for anomaly detection"""
        if not msg.valid:
            return

        profile = self.get_or_create_profile(msg.sensor_id, msg.sensor_type)
        current_time = self.get_clock().now().nanoseconds / 1e9

        # Add value to profile
        profile.add_value(msg.value)

        # Check for anomaly
        is_anomaly, score, method = profile.detect_anomaly(msg.value)

        if is_anomaly:
            profile.anomaly_count += 1
            profile.consecutive_anomalies += 1
            profile.last_anomaly_time = current_time

            # Record anomaly
            anomaly_record = {
                'time': current_time,
                'sensor_id': msg.sensor_id,
                'sensor_type': msg.sensor_type,
                'value': msg.value,
                'score': score,
                'method': method,
                'baseline_mean': profile.baseline_mean,
                'baseline_std': profile.baseline_std,
            }
            self.recent_anomalies.append(anomaly_record)

            # Publish alarm if consecutive threshold exceeded
            if profile.consecutive_anomalies >= self.alarm_threshold:
                self.publish_anomaly_alarm(msg, profile, score)

        else:
            profile.consecutive_anomalies = 0

        # Multi-axis anomaly detection
        if len(msg.values) >= 3:
            self.detect_multiaxis_anomaly(msg, current_time)

    def detect_multiaxis_anomaly(self, msg: SensorReading, current_time: float):
        """Detect anomalies in multi-axis sensor data (e.g., accelerometer)"""
        values = np.array(msg.values[:3])

        # Calculate magnitude
        magnitude = np.linalg.norm(values)

        # Create profile for magnitude
        mag_profile = self.get_or_create_profile(
            f"{msg.sensor_id}_magnitude",
            msg.sensor_type
        )
        mag_profile.add_value(magnitude)

        is_anomaly, score, method = mag_profile.detect_anomaly(magnitude)

        if is_anomaly and mag_profile.consecutive_anomalies >= self.alarm_threshold:
            self.publish_anomaly_alarm(msg, mag_profile, score, is_magnitude=True)

    def publish_anomaly_alarm(self, msg: SensorReading, profile: AnomalyProfile,
                              score: float, is_magnitude: bool = False):
        """Publish alarm for detected anomaly"""
        alarm = Alarm()
        alarm.header.stamp = self.get_clock().now().to_msg()
        alarm.machine_id = msg.sensor_id.split('_')[0] if '_' in msg.sensor_id else 'unknown'
        alarm.alarm_code = 8000 + hash(msg.sensor_type) % 1000

        alarm.message = (
            f"Anomaly detected: {msg.sensor_type} "
            f"{'magnitude ' if is_magnitude else ''}"
            f"value={msg.value:.3f} "
            f"(baseline={profile.baseline_mean:.3f}±{profile.baseline_std:.3f}, "
            f"score={score:.2f})"
        )

        # Severity based on score
        if score > 5:
            alarm.severity = 2  # Critical
        elif score > 4:
            alarm.severity = 1  # Warning
        else:
            alarm.severity = 0  # Info

        self.alarm_pub.publish(alarm)

        # Also publish as predictive maintenance message
        pm = PredictiveMaintenance()
        pm.header.stamp = alarm.header.stamp
        pm.machine_id = alarm.machine_id
        pm.component_id = msg.sensor_id
        pm.prediction_type = PredictiveMaintenance.PREDICTION_VIBRATION_ANOMALY
        pm.health_score = max(0.1, 1.0 - (score / 10.0))
        pm.confidence = min(0.9, profile.baseline_samples / 500.0)
        pm.severity = alarm.severity
        pm.recommended_actions = [
            f"Investigate {msg.sensor_type} anomaly on {msg.sensor_id}",
            "Check for mechanical looseness or wear"
        ]

        self.prediction_pub.publish(pm)

        self.get_logger().warn(f"Anomaly alarm: {alarm.message}")

    def update_baselines(self):
        """Periodically update baselines for all profiles"""
        for key, profile in self.profiles.items():
            if not profile.baseline_established:
                if profile.establish_baseline(self.baseline_samples):
                    self.get_logger().info(
                        f"Baseline established for {key}: "
                        f"mean={profile.baseline_mean:.3f}, "
                        f"std={profile.baseline_std:.3f}"
                    )


def main(args=None):
    rclpy.init(args=args)
    node = AnomalyDetectorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
