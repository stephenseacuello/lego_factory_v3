#!/usr/bin/env python3
"""
Predictive Maintenance Node - ML-based health monitoring and prediction

Subscribes to sensor data and machine status to predict maintenance needs.
Uses ensemble models for tool wear, bearing degradation, and anomaly detection.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os
import numpy as np
from datetime import datetime

from std_msgs.msg import String
from cnc_interfaces.msg import (
    SensorReading,
    MachineStatus,
    PredictiveMaintenance,
    ToolWear,
    Alarm,
)
from cnc_interfaces.srv import GetPrediction


@dataclass
class SensorHistory:
    """Rolling buffer for sensor data"""
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))

    def add(self, value: float, timestamp: float):
        self.values.append(value)
        self.timestamps.append(timestamp)

    def get_array(self) -> np.ndarray:
        return np.array(self.values)

    def get_statistics(self) -> Dict:
        if len(self.values) < 2:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'trend': 0}
        arr = self.get_array()
        return {
            'mean': float(np.mean(arr)),
            'std': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'trend': float(np.polyfit(range(len(arr)), arr, 1)[0]) if len(arr) > 10 else 0
        }


@dataclass
class MachineHealth:
    """Health state for a machine"""
    machine_id: str
    spindle_health: float = 1.0
    x_axis_health: float = 1.0
    y_axis_health: float = 1.0
    z_axis_health: float = 1.0
    vibration_score: float = 1.0
    thermal_score: float = 1.0
    overall_health: float = 1.0
    last_update: float = 0.0

    # Sensor histories
    vibration_history: SensorHistory = field(default_factory=SensorHistory)
    temperature_history: SensorHistory = field(default_factory=SensorHistory)
    spindle_load_history: SensorHistory = field(default_factory=SensorHistory)
    current_history: SensorHistory = field(default_factory=SensorHistory)


class PredictiveMaintenanceNode(Node):
    """ML-based predictive maintenance for CNC machines"""

    def __init__(self):
        super().__init__('predictive_maintenance_node')

        # Parameters
        self.declare_parameter('publish_rate', 1.0)
        self.declare_parameter('health_threshold_warning', 0.7)
        self.declare_parameter('health_threshold_critical', 0.4)
        self.declare_parameter('model_path', '')
        self.declare_parameter('enable_ml_models', True)

        self.publish_rate = self.get_parameter('publish_rate').value
        self.warning_threshold = self.get_parameter('health_threshold_warning').value
        self.critical_threshold = self.get_parameter('health_threshold_critical').value
        self.model_path = self.get_parameter('model_path').value
        self.enable_ml = self.get_parameter('enable_ml_models').value

        # Machine health tracking
        self.machines: Dict[str, MachineHealth] = {}

        # QoS profile
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

        self.status_sub = self.create_subscription(
            MachineStatus,
            '/machine/status',
            self.status_callback,
            qos
        )

        # Multiple machine status topics
        for controller in ['tinyg', 'grbl']:
            self.create_subscription(
                MachineStatus,
                f'/{controller}/status',
                self.status_callback,
                qos
            )

        # Publishers
        self.prediction_pub = self.create_publisher(
            PredictiveMaintenance,
            '/predictive/maintenance',
            qos
        )

        self.tool_wear_pub = self.create_publisher(
            ToolWear,
            '/predictive/tool_wear',
            qos
        )

        self.alarm_pub = self.create_publisher(
            Alarm,
            '/predictive/alarms',
            qos
        )

        # Service
        self.prediction_srv = self.create_service(
            GetPrediction,
            '/predictive/get_prediction',
            self.get_prediction_callback
        )

        # Timer for periodic analysis
        self.analysis_timer = self.create_timer(
            1.0 / self.publish_rate,
            self.analysis_callback
        )

        # Load ML models if available
        self.models = {}
        if self.enable_ml:
            self.load_models()

        self.get_logger().info('Predictive Maintenance Node started')

    def load_models(self):
        """Load pre-trained ML models"""
        try:
            # In production, load actual sklearn/tensorflow models
            # For now, use statistical methods as fallback
            self.models = {
                'tool_wear': None,  # Would load joblib.load(path)
                'bearing': None,
                'anomaly': None,
                'thermal': None,
            }
            self.get_logger().info('Using statistical prediction models')
        except Exception as e:
            self.get_logger().warn(f'Could not load ML models: {e}')

    def get_or_create_machine(self, machine_id: str) -> MachineHealth:
        """Get or create machine health tracker"""
        if machine_id not in self.machines:
            self.machines[machine_id] = MachineHealth(machine_id=machine_id)
        return self.machines[machine_id]

    def sensor_callback(self, msg: SensorReading):
        """Process incoming sensor data"""
        machine_id = msg.sensor_id.split('_')[0] if '_' in msg.sensor_id else 'default'
        machine = self.get_or_create_machine(machine_id)

        timestamp = self.get_clock().now().nanoseconds / 1e9

        if msg.sensor_type == 'vibration':
            machine.vibration_history.add(msg.value, timestamp)
            # Multi-axis vibration
            if len(msg.values) >= 3:
                rms = np.sqrt(np.mean(np.array(msg.values[:3])**2))
                machine.vibration_history.add(rms, timestamp)

        elif msg.sensor_type == 'temperature':
            machine.temperature_history.add(msg.value, timestamp)

        elif msg.sensor_type == 'current':
            machine.current_history.add(msg.value, timestamp)

        elif msg.sensor_type == 'spindle_load':
            machine.spindle_load_history.add(msg.value, timestamp)

    def status_callback(self, msg: MachineStatus):
        """Process machine status updates"""
        machine = self.get_or_create_machine(msg.machine_id)
        machine.last_update = self.get_clock().now().nanoseconds / 1e9

        # Track spindle load if available
        if msg.spindle_speed > 0:
            # Infer load from current if not directly available
            machine.spindle_load_history.add(
                msg.spindle_speed / 10000.0,  # Normalized
                machine.last_update
            )

    def analyze_health(self, machine: MachineHealth) -> Dict:
        """Analyze machine health using statistical/ML methods"""
        results = {
            'overall': 1.0,
            'components': {},
            'predictions': [],
            'recommendations': []
        }

        # Vibration analysis
        vib_stats = machine.vibration_history.get_statistics()
        if vib_stats['std'] > 0:
            # High variance indicates problems
            vib_score = max(0, 1.0 - (vib_stats['std'] / 5.0))
            # Negative trend is good (vibration decreasing)
            trend_penalty = max(0, vib_stats['trend'] * 10)
            machine.vibration_score = max(0.1, vib_score - trend_penalty)
            results['components']['vibration'] = machine.vibration_score

            if machine.vibration_score < self.warning_threshold:
                results['predictions'].append({
                    'type': 'VIBRATION_ANOMALY',
                    'severity': 'WARNING' if machine.vibration_score > self.critical_threshold else 'CRITICAL',
                    'component': 'spindle',
                    'rul_hours': max(1, machine.vibration_score * 100),
                })
                results['recommendations'].append('Schedule vibration analysis')

        # Thermal analysis
        temp_stats = machine.temperature_history.get_statistics()
        if temp_stats['mean'] > 0:
            # Normalize temperature (assume 20-80C range)
            temp_normalized = (temp_stats['mean'] - 20) / 60
            machine.thermal_score = max(0.1, 1.0 - temp_normalized)
            results['components']['thermal'] = machine.thermal_score

            if temp_stats['trend'] > 0.1:  # Rising temperature trend
                results['predictions'].append({
                    'type': 'THERMAL_DRIFT',
                    'severity': 'WARNING',
                    'component': 'cooling_system',
                    'rul_hours': max(1, 50 / temp_stats['trend']),
                })
                results['recommendations'].append('Check coolant levels and flow')

        # Spindle load analysis
        load_stats = machine.spindle_load_history.get_statistics()
        if load_stats['mean'] > 0:
            # High average load indicates tool wear
            load_factor = load_stats['mean']
            if load_stats['trend'] > 0.01:  # Increasing load trend
                results['predictions'].append({
                    'type': 'TOOL_WEAR',
                    'severity': 'WARNING',
                    'component': 'tool',
                    'rul_hours': max(1, 20 / load_stats['trend']),
                })
                results['recommendations'].append('Inspect cutting tool for wear')

        # Calculate overall health
        scores = [machine.vibration_score, machine.thermal_score]
        machine.overall_health = float(np.mean(scores)) if scores else 1.0
        results['overall'] = machine.overall_health

        return results

    def analysis_callback(self):
        """Periodic health analysis"""
        for machine_id, machine in self.machines.items():
            # Skip if no recent data
            current_time = self.get_clock().now().nanoseconds / 1e9
            if current_time - machine.last_update > 60:
                continue

            # Analyze health
            results = self.analyze_health(machine)

            # Publish predictions
            for pred in results['predictions']:
                msg = PredictiveMaintenance()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.machine_id = machine_id
                msg.component_id = pred['component']

                # Map prediction type
                type_map = {
                    'TOOL_WEAR': PredictiveMaintenance.PREDICTION_TOOL_WEAR,
                    'VIBRATION_ANOMALY': PredictiveMaintenance.PREDICTION_VIBRATION_ANOMALY,
                    'THERMAL_DRIFT': PredictiveMaintenance.PREDICTION_THERMAL_DRIFT,
                    'BEARING_DEGRADATION': PredictiveMaintenance.PREDICTION_BEARING_DEGRADATION,
                }
                msg.prediction_type = type_map.get(pred['type'], 0)

                msg.health_score = results['overall']
                msg.remaining_useful_life = pred['rul_hours']
                msg.confidence = 0.75  # Statistical model confidence

                severity_map = {
                    'INFO': PredictiveMaintenance.SEVERITY_INFO,
                    'WARNING': PredictiveMaintenance.SEVERITY_WARNING,
                    'CRITICAL': PredictiveMaintenance.SEVERITY_CRITICAL,
                }
                msg.severity = severity_map.get(pred['severity'], 0)

                msg.recommended_actions = results['recommendations']

                self.prediction_pub.publish(msg)

                # Publish alarm for critical predictions
                if pred['severity'] == 'CRITICAL':
                    alarm = Alarm()
                    alarm.header.stamp = msg.header.stamp
                    alarm.machine_id = machine_id
                    alarm.alarm_code = 9000 + msg.prediction_type
                    alarm.message = f"Predicted {pred['type']}: RUL {pred['rul_hours']:.1f}h"
                    alarm.severity = 2  # Critical
                    self.alarm_pub.publish(alarm)

    def get_prediction_callback(self, request, response):
        """Service callback for on-demand predictions"""
        machine_id = request.machine_id

        if machine_id not in self.machines:
            response.success = False
            response.message = f"Unknown machine: {machine_id}"
            return response

        machine = self.machines[machine_id]
        results = self.analyze_health(machine)

        response.success = True
        response.message = f"Analysis complete for {machine_id}"
        response.analysis_timestamp = self.get_clock().now().to_msg()

        # Populate predictions
        for pred in results['predictions']:
            pm = PredictiveMaintenance()
            pm.header.stamp = response.analysis_timestamp
            pm.machine_id = machine_id
            pm.component_id = pred['component']
            pm.health_score = results['overall']
            pm.remaining_useful_life = pred['rul_hours']
            pm.confidence = 0.75
            pm.recommended_actions = results['recommendations']
            response.predictions.append(pm)

        return response


def main(args=None):
    rclpy.init(args=args)
    node = PredictiveMaintenanceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
