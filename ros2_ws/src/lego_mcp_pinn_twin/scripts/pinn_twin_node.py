#!/usr/bin/env python3
"""
PINN Digital Twin ROS2 Node

Main node integrating Physics-Informed Neural Network models
with the ROS2 manufacturing system.

Provides:
- Real-time state estimation
- Predictive maintenance
- Anomaly detection
- Physics-based simulation

ISO 23247 Digital Twin Framework compliant.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Float64MultiArray, String
from sensor_msgs.msg import JointState, Temperature
import numpy as np
import json
from typing import Dict, Optional

from lego_mcp_pinn_twin.models.thermal_dynamics import ThermalDynamicsPINN, ThermalPINNConfig
from lego_mcp_pinn_twin.models.kinematic_chain import KinematicChainPINN, KinematicPINNConfig
from lego_mcp_pinn_twin.models.degradation_model import DegradationPINN, DegradationPINNConfig
from lego_mcp_pinn_twin.inference.realtime_predictor import RealtimePredictor, PredictorConfig
from lego_mcp_pinn_twin.inference.uncertainty_quantifier import UncertaintyQuantifier
from lego_mcp_pinn_twin.inference.anomaly_detector import PhysicsAnomalyDetector


class PINNTwinNode(Node):
    """
    ROS2 node for Physics-Informed Neural Network Digital Twin.

    Subscribes to sensor data and publishes:
    - State estimates
    - Predictions
    - Anomaly alerts
    - Health metrics
    """

    def __init__(self):
        super().__init__('pinn_twin_node')

        # Declare parameters
        self.declare_parameter('update_rate', 10.0)  # Hz
        self.declare_parameter('enable_thermal', True)
        self.declare_parameter('enable_kinematic', True)
        self.declare_parameter('enable_degradation', True)
        self.declare_parameter('anomaly_threshold', 0.1)

        # Load parameters
        self.update_rate = self.get_parameter('update_rate').value
        self.enable_thermal = self.get_parameter('enable_thermal').value
        self.enable_kinematic = self.get_parameter('enable_kinematic').value
        self.enable_degradation = self.get_parameter('enable_degradation').value
        self.anomaly_threshold = self.get_parameter('anomaly_threshold').value

        # QoS profiles
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Initialize PINN models
        self._init_models()

        # Subscribers
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self._joint_state_callback,
            sensor_qos
        )

        self.temperature_sub = self.create_subscription(
            Temperature,
            '/temperature',
            self._temperature_callback,
            sensor_qos
        )

        self.sensor_sub = self.create_subscription(
            Float64MultiArray,
            '/sensor_data',
            self._sensor_callback,
            sensor_qos
        )

        # Publishers
        self.state_pub = self.create_publisher(
            String,
            '~/state_estimate',
            reliable_qos
        )

        self.prediction_pub = self.create_publisher(
            String,
            '~/predictions',
            reliable_qos
        )

        self.anomaly_pub = self.create_publisher(
            String,
            '~/anomalies',
            reliable_qos
        )

        self.health_pub = self.create_publisher(
            String,
            '~/health',
            reliable_qos
        )

        # Timer for periodic updates
        self.update_timer = self.create_timer(
            1.0 / self.update_rate,
            self._update_callback
        )

        # State
        self._current_joint_state: Optional[JointState] = None
        self._current_temperature: float = 293.15  # Default 20°C
        self._sensor_data: Dict = {}

        self.get_logger().info(
            f'PINN Twin Node initialized: '
            f'thermal={self.enable_thermal}, '
            f'kinematic={self.enable_kinematic}, '
            f'degradation={self.enable_degradation}'
        )

    def _init_models(self):
        """Initialize PINN models and inference components."""

        # Thermal model
        if self.enable_thermal:
            thermal_config = ThermalPINNConfig(
                input_dim=4,
                output_dim=1,
                hidden_layers=[32, 32, 32]
            )
            self.thermal_model = ThermalDynamicsPINN(thermal_config)
            self.thermal_predictor = RealtimePredictor(
                self.thermal_model,
                PredictorConfig(max_latency_ms=5.0)
            )
            self.thermal_predictor.warmup()
        else:
            self.thermal_model = None
            self.thermal_predictor = None

        # Kinematic model
        if self.enable_kinematic:
            kinematic_config = KinematicPINNConfig(
                hidden_layers=[64, 64, 64]
            )
            self.kinematic_model = KinematicChainPINN(kinematic_config)
            self.kinematic_predictor = RealtimePredictor(
                self.kinematic_model,
                PredictorConfig(max_latency_ms=5.0)
            )
            self.kinematic_predictor.warmup()
        else:
            self.kinematic_model = None
            self.kinematic_predictor = None

        # Degradation model
        if self.enable_degradation:
            degradation_config = DegradationPINNConfig()
            self.degradation_model = DegradationPINN(degradation_config)
            self.anomaly_detector = PhysicsAnomalyDetector(
                self.degradation_model
            )
        else:
            self.degradation_model = None
            self.anomaly_detector = None

        # Uncertainty quantifier (uses all models)
        models = [m for m in [self.thermal_model, self.kinematic_model] if m]
        if models:
            self.uncertainty_quantifier = UncertaintyQuantifier(models)
        else:
            self.uncertainty_quantifier = None

    def _joint_state_callback(self, msg: JointState):
        """Handle joint state updates."""
        self._current_joint_state = msg

    def _temperature_callback(self, msg: Temperature):
        """Handle temperature updates."""
        self._current_temperature = msg.temperature

    def _sensor_callback(self, msg: Float64MultiArray):
        """Handle generic sensor data."""
        self._sensor_data['raw'] = np.array(msg.data)

    def _update_callback(self):
        """Periodic update callback."""
        try:
            # State estimation
            state_estimate = self._estimate_state()
            if state_estimate:
                self._publish_state(state_estimate)

            # Predictions
            predictions = self._make_predictions()
            if predictions:
                self._publish_predictions(predictions)

            # Anomaly detection
            anomalies = self._detect_anomalies()
            if anomalies:
                self._publish_anomalies(anomalies)

            # Health assessment
            health = self._assess_health()
            if health:
                self._publish_health(health)

        except Exception as e:
            self.get_logger().error(f'Update error: {e}')

    def _estimate_state(self) -> Optional[Dict]:
        """Estimate current system state using PINN models."""
        state = {'timestamp': self.get_clock().now().nanoseconds / 1e9}

        # Thermal state
        if self.thermal_predictor and self._current_temperature:
            x = np.array([[0.0, 0.0, 0.0, 0.0]])  # Position and time
            result = self.thermal_predictor.predict(x)
            state['thermal'] = {
                'temperature_k': self._current_temperature,
                'predicted_k': float(result.value[0, 0]),
                'latency_ms': result.latency_ms
            }

        # Kinematic state
        if self.kinematic_predictor and self._current_joint_state:
            positions = np.array(self._current_joint_state.position)
            velocities = np.array(self._current_joint_state.velocity or [0] * len(positions))
            accelerations = np.zeros_like(positions)

            x = np.concatenate([positions, velocities, accelerations]).reshape(1, -1)
            result = self.kinematic_predictor.predict(x)

            state['kinematic'] = {
                'joint_positions': positions.tolist(),
                'end_effector_pose': result.value[0, :6].tolist() if result.value.shape[1] >= 6 else [],
                'latency_ms': result.latency_ms
            }

        return state

    def _make_predictions(self) -> Optional[Dict]:
        """Make future predictions."""
        predictions = {'timestamp': self.get_clock().now().nanoseconds / 1e9}

        # Temperature prediction
        if self.thermal_predictor:
            future_times = [1.0, 5.0, 10.0]  # seconds ahead
            temp_predictions = []
            for t in future_times:
                x = np.array([[0.0, 0.0, 0.0, t]])
                result = self.thermal_predictor.predict(x)
                temp_predictions.append({
                    'time_s': t,
                    'temperature_k': float(result.value[0, 0])
                })
            predictions['temperature'] = temp_predictions

        # RUL prediction
        if self.degradation_model:
            # Simplified - would use actual operating history
            x = np.array([[1000.0, 100.0, 1000.0, 323.0, 0.5, 0.1]])
            output = self.degradation_model.forward(x)
            predictions['rul'] = {
                'health_index': float(output[0, 0]),
                'rul_hours': float(output[0, 1]),
                'degradation_rate': float(output[0, 2])
            }

        return predictions

    def _detect_anomalies(self) -> Optional[Dict]:
        """Detect physics-based anomalies."""
        if not self.anomaly_detector:
            return None

        # Check for anomalies using current sensor data
        x = np.array([[1000.0, 100.0, 1000.0, 323.0, 0.5, 0.1]])
        anomalies = self.anomaly_detector.check(x)

        if anomalies:
            return {
                'count': len(anomalies),
                'anomalies': [
                    {
                        'type': a.anomaly_type.value,
                        'severity': a.severity.name,
                        'location': a.location,
                        'description': a.description,
                        'confidence': a.confidence
                    }
                    for a in anomalies
                ]
            }
        return None

    def _assess_health(self) -> Dict:
        """Assess overall system health."""
        health = {
            'timestamp': self.get_clock().now().nanoseconds / 1e9,
            'overall_status': 'HEALTHY'
        }

        # Model health
        if self.thermal_predictor:
            stats = self.thermal_predictor.get_stats()
            health['thermal_model'] = {
                'mean_latency_ms': stats['mean_latency_ms'],
                'cache_hit_rate': stats['cache_hit_rate']
            }

        if self.kinematic_predictor:
            stats = self.kinematic_predictor.get_stats()
            health['kinematic_model'] = {
                'mean_latency_ms': stats['mean_latency_ms'],
                'cache_hit_rate': stats['cache_hit_rate']
            }

        # Anomaly summary
        if self.anomaly_detector:
            summary = self.anomaly_detector.get_anomaly_summary()
            health['anomaly_summary'] = summary
            if summary.get('by_severity', {}).get('CRITICAL', 0) > 0:
                health['overall_status'] = 'DEGRADED'
            if summary.get('by_severity', {}).get('EMERGENCY', 0) > 0:
                health['overall_status'] = 'CRITICAL'

        return health

    def _publish_state(self, state: Dict):
        """Publish state estimate."""
        msg = String()
        msg.data = json.dumps(state)
        self.state_pub.publish(msg)

    def _publish_predictions(self, predictions: Dict):
        """Publish predictions."""
        msg = String()
        msg.data = json.dumps(predictions)
        self.prediction_pub.publish(msg)

    def _publish_anomalies(self, anomalies: Dict):
        """Publish anomaly alerts."""
        msg = String()
        msg.data = json.dumps(anomalies)
        self.anomaly_pub.publish(msg)
        self.get_logger().warn(f"Anomalies detected: {anomalies['count']}")

    def _publish_health(self, health: Dict):
        """Publish health status."""
        msg = String()
        msg.data = json.dumps(health)
        self.health_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PINNTwinNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
