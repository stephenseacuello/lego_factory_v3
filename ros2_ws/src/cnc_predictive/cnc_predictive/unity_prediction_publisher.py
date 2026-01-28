#!/usr/bin/env python3
"""
Unity Prediction Publisher Node
================================
ROS2 node that publishes ML predictions to Unity for visualization.

Subscribes to:
- /predictive/tool_wear (ToolWearPrediction)
- /predictive/maintenance (MaintenanceAlert)
- /predictive/anomaly (AnomalyDetection)
- /predictive/quality (QualityPrediction)

Publishes to:
- /unity/predictions (UnityPredictions)
- MQTT: cnc/{machine_id}/unity/predictions

Features:
- Tool wear indicators with 3D overlay positions
- Maintenance calendar events
- Anomaly markers with severity levels
- Quality score gauges
- AR overlay data for HoloLens/Quest

Author: Flask CNC SCADA System
"""

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# Standard ROS2 messages
from std_msgs.msg import String

# MQTT client
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Position3D:
    """3D position for overlay."""
    x: float
    y: float
    z: float


@dataclass
class ToolWearOverlay:
    """Tool wear visualization data."""
    tool_id: str
    tool_name: str
    wear_percent: float
    remaining_life_minutes: float
    status: str  # good, warning, critical, replace
    position: Position3D
    color: str
    icon: str = "tool"


@dataclass
class MaintenanceEvent:
    """Maintenance event for calendar."""
    event_id: str
    machine_id: str
    component: str
    event_type: str  # scheduled, predicted, overdue
    due_date: str
    priority: int
    description: str
    estimated_duration_hours: float


@dataclass
class AnomalyMarker:
    """Anomaly visualization marker."""
    anomaly_id: str
    machine_id: str
    component: str
    severity: str  # low, medium, high, critical
    position: Position3D
    detection_time: str
    description: str
    confidence: float
    color: str
    pulse: bool = True


@dataclass
class QualityGauge:
    """Quality prediction gauge."""
    machine_id: str
    current_score: float
    predicted_score: float
    trend: str  # improving, stable, declining
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class UnityPredictionsPayload:
    """Complete predictions payload for Unity."""
    timestamp: str
    machine_id: str
    tool_wear: List[ToolWearOverlay] = field(default_factory=list)
    maintenance: List[MaintenanceEvent] = field(default_factory=list)
    anomalies: List[AnomalyMarker] = field(default_factory=list)
    quality: Optional[QualityGauge] = None
    overall_health: float = 100.0


# =============================================================================
# Unity Prediction Publisher Node
# =============================================================================

class UnityPredictionPublisher(Node):
    """
    ROS2 node that formats and publishes ML predictions for Unity AR overlay.

    Converts internal prediction data to Unity-friendly format with
    3D positions, colors, icons, and animation parameters.
    """

    def __init__(self):
        super().__init__('unity_prediction_publisher')

        # Parameters
        self.declare_parameter('machine_id', 'cnc-1')
        self.declare_parameter('mqtt_enabled', True)
        self.declare_parameter('mqtt_host', 'localhost')
        self.declare_parameter('mqtt_port', 1883)
        self.declare_parameter('publish_rate_hz', 2.0)

        self.machine_id = self.get_parameter('machine_id').value
        self.mqtt_enabled = self.get_parameter('mqtt_enabled').value
        self.mqtt_host = self.get_parameter('mqtt_host').value
        self.mqtt_port = self.get_parameter('mqtt_port').value
        self.publish_rate_hz = self.get_parameter('publish_rate_hz').value

        # QoS
        self.reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # State
        self.predictions = UnityPredictionsPayload(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            machine_id=self.machine_id
        )
        self.state_lock = threading.Lock()

        # Component positions (machine-specific, should be configured)
        self.component_positions = {
            'spindle': Position3D(0, 0, 150),
            'x_axis': Position3D(-100, 0, 50),
            'y_axis': Position3D(0, -100, 50),
            'z_axis': Position3D(0, 0, 100),
            'tool': Position3D(0, 0, 180),
            'coolant': Position3D(50, 50, 100),
            'lubrication': Position3D(-50, 50, 30),
        }

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        if self.mqtt_enabled and MQTT_AVAILABLE:
            self._init_mqtt()

        # Publishers
        self.predictions_pub = self.create_publisher(
            String,
            '/unity/predictions',
            self.reliable_qos
        )

        # Subscribers
        self.tool_wear_sub = self.create_subscription(
            String,
            '/predictive/tool_wear',
            self._on_tool_wear,
            self.reliable_qos
        )

        self.maintenance_sub = self.create_subscription(
            String,
            '/predictive/maintenance',
            self._on_maintenance,
            self.reliable_qos
        )

        self.anomaly_sub = self.create_subscription(
            String,
            '/predictive/anomaly',
            self._on_anomaly,
            self.reliable_qos
        )

        self.quality_sub = self.create_subscription(
            String,
            '/predictive/quality',
            self._on_quality,
            self.reliable_qos
        )

        # Publish timer
        period = 1.0 / self.publish_rate_hz
        self.publish_timer = self.create_timer(period, self._publish_predictions)

        self.get_logger().info(
            f'Unity Prediction Publisher started for {self.machine_id}'
        )

    # -------------------------------------------------------------------------
    # MQTT
    # -------------------------------------------------------------------------

    def _init_mqtt(self) -> None:
        """Initialize MQTT client."""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=f'unity_prediction_pub_{self.machine_id}',
                protocol=mqtt.MQTTv5
            )
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.get_logger().warn(f'MQTT init failed: {e}')
            self.mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection."""
        if rc == 0:
            client.subscribe(f'cnc/{self.machine_id}/predictive/#', qos=1)
            self.get_logger().info('MQTT connected')

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT prediction message."""
        try:
            data = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split('/')

            if len(topic_parts) >= 4:
                prediction_type = topic_parts[3]

                if prediction_type == 'tool_wear':
                    self._process_tool_wear(data)
                elif prediction_type == 'maintenance':
                    self._process_maintenance(data)
                elif prediction_type == 'anomaly':
                    self._process_anomaly(data)
                elif prediction_type == 'quality':
                    self._process_quality(data)

        except Exception as e:
            self.get_logger().error(f'MQTT message error: {e}')

    # -------------------------------------------------------------------------
    # ROS2 Callbacks
    # -------------------------------------------------------------------------

    def _on_tool_wear(self, msg: String) -> None:
        """Handle tool wear prediction."""
        try:
            data = json.loads(msg.data)
            self._process_tool_wear(data)
        except Exception as e:
            self.get_logger().error(f'Tool wear error: {e}')

    def _on_maintenance(self, msg: String) -> None:
        """Handle maintenance prediction."""
        try:
            data = json.loads(msg.data)
            self._process_maintenance(data)
        except Exception as e:
            self.get_logger().error(f'Maintenance error: {e}')

    def _on_anomaly(self, msg: String) -> None:
        """Handle anomaly detection."""
        try:
            data = json.loads(msg.data)
            self._process_anomaly(data)
        except Exception as e:
            self.get_logger().error(f'Anomaly error: {e}')

    def _on_quality(self, msg: String) -> None:
        """Handle quality prediction."""
        try:
            data = json.loads(msg.data)
            self._process_quality(data)
        except Exception as e:
            self.get_logger().error(f'Quality error: {e}')

    # -------------------------------------------------------------------------
    # Prediction Processing
    # -------------------------------------------------------------------------

    def _process_tool_wear(self, data: Dict[str, Any]) -> None:
        """Process tool wear prediction."""
        tool_id = data.get('tool_id', 'T1')
        wear_percent = data.get('wear_percent', 0.0)

        # Determine status and color
        if wear_percent >= 90:
            status = 'replace'
            color = '#F44336'  # Red
        elif wear_percent >= 70:
            status = 'critical'
            color = '#FF5722'  # Deep orange
        elif wear_percent >= 50:
            status = 'warning'
            color = '#FFC107'  # Amber
        else:
            status = 'good'
            color = '#4CAF50'  # Green

        overlay = ToolWearOverlay(
            tool_id=tool_id,
            tool_name=data.get('tool_name', f'Tool {tool_id}'),
            wear_percent=wear_percent,
            remaining_life_minutes=data.get('remaining_life_minutes', 0.0),
            status=status,
            position=self.component_positions.get('tool', Position3D(0, 0, 180)),
            color=color
        )

        with self.state_lock:
            # Update or add tool wear overlay
            found = False
            for i, tw in enumerate(self.predictions.tool_wear):
                if tw.tool_id == tool_id:
                    self.predictions.tool_wear[i] = overlay
                    found = True
                    break
            if not found:
                self.predictions.tool_wear.append(overlay)

    def _process_maintenance(self, data: Dict[str, Any]) -> None:
        """Process maintenance prediction."""
        event = MaintenanceEvent(
            event_id=data.get('event_id', ''),
            machine_id=data.get('machine_id', self.machine_id),
            component=data.get('component', ''),
            event_type=data.get('event_type', 'predicted'),
            due_date=data.get('due_date', ''),
            priority=data.get('priority', 0),
            description=data.get('description', ''),
            estimated_duration_hours=data.get('estimated_duration_hours', 1.0)
        )

        with self.state_lock:
            # Update or add maintenance event
            found = False
            for i, me in enumerate(self.predictions.maintenance):
                if me.event_id == event.event_id:
                    self.predictions.maintenance[i] = event
                    found = True
                    break
            if not found:
                self.predictions.maintenance.append(event)

            # Keep only recent events (last 20)
            self.predictions.maintenance = self.predictions.maintenance[-20:]

    def _process_anomaly(self, data: Dict[str, Any]) -> None:
        """Process anomaly detection."""
        severity = data.get('severity', 'low')

        # Severity to color mapping
        color_map = {
            'low': '#8BC34A',      # Light green
            'medium': '#FFC107',   # Amber
            'high': '#FF5722',     # Deep orange
            'critical': '#F44336'  # Red
        }

        component = data.get('component', 'spindle')
        position = self.component_positions.get(
            component.lower(),
            Position3D(0, 0, 100)
        )

        marker = AnomalyMarker(
            anomaly_id=data.get('anomaly_id', ''),
            machine_id=data.get('machine_id', self.machine_id),
            component=component,
            severity=severity,
            position=position,
            detection_time=data.get('detection_time', datetime.utcnow().isoformat()),
            description=data.get('description', ''),
            confidence=data.get('confidence', 0.0),
            color=color_map.get(severity, '#FFC107'),
            pulse=severity in ['high', 'critical']
        )

        with self.state_lock:
            # Add anomaly (limit to 10 active)
            self.predictions.anomalies.append(marker)
            self.predictions.anomalies = self.predictions.anomalies[-10:]

    def _process_quality(self, data: Dict[str, Any]) -> None:
        """Process quality prediction."""
        current = data.get('current_score', 95.0)
        predicted = data.get('predicted_score', 95.0)

        # Determine trend
        diff = predicted - current
        if diff > 1:
            trend = 'improving'
        elif diff < -1:
            trend = 'declining'
        else:
            trend = 'stable'

        gauge = QualityGauge(
            machine_id=data.get('machine_id', self.machine_id),
            current_score=current,
            predicted_score=predicted,
            trend=trend,
            factors=data.get('factors', {})
        )

        with self.state_lock:
            self.predictions.quality = gauge

    # -------------------------------------------------------------------------
    # Publishing
    # -------------------------------------------------------------------------

    def _publish_predictions(self) -> None:
        """Publish current predictions to Unity."""
        with self.state_lock:
            self.predictions.timestamp = datetime.utcnow().isoformat() + 'Z'

            # Calculate overall health
            health = 100.0

            # Reduce for tool wear
            for tw in self.predictions.tool_wear:
                if tw.status == 'critical':
                    health -= 20
                elif tw.status == 'warning':
                    health -= 10
                elif tw.status == 'replace':
                    health -= 30

            # Reduce for anomalies
            for anomaly in self.predictions.anomalies:
                if anomaly.severity == 'critical':
                    health -= 25
                elif anomaly.severity == 'high':
                    health -= 15
                elif anomaly.severity == 'medium':
                    health -= 5

            # Reduce for overdue maintenance
            for me in self.predictions.maintenance:
                if me.event_type == 'overdue':
                    health -= 10

            self.predictions.overall_health = max(0.0, min(100.0, health))

            # Convert to dict
            payload = self._to_unity_format()

        # Publish to ROS2
        msg = String()
        msg.data = json.dumps(payload)
        self.predictions_pub.publish(msg)

        # Publish to MQTT
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish(
                f'cnc/{self.machine_id}/unity/predictions',
                msg.data,
                qos=0
            )

    def _to_unity_format(self) -> Dict[str, Any]:
        """Convert predictions to Unity-friendly format."""
        return {
            'type': 'predictions',
            'timestamp': self.predictions.timestamp,
            'machine_id': self.predictions.machine_id,
            'overall_health': self.predictions.overall_health,
            'health_color': self._get_health_color(self.predictions.overall_health),

            'tool_wear': [
                {
                    'id': tw.tool_id,
                    'name': tw.tool_name,
                    'wear': tw.wear_percent,
                    'remaining_minutes': tw.remaining_life_minutes,
                    'status': tw.status,
                    'position': asdict(tw.position),
                    'color': tw.color,
                    'icon': tw.icon
                }
                for tw in self.predictions.tool_wear
            ],

            'maintenance': [
                {
                    'id': me.event_id,
                    'component': me.component,
                    'type': me.event_type,
                    'due': me.due_date,
                    'priority': me.priority,
                    'description': me.description,
                    'duration_hours': me.estimated_duration_hours
                }
                for me in self.predictions.maintenance
            ],

            'anomalies': [
                {
                    'id': a.anomaly_id,
                    'component': a.component,
                    'severity': a.severity,
                    'position': asdict(a.position),
                    'time': a.detection_time,
                    'description': a.description,
                    'confidence': a.confidence,
                    'color': a.color,
                    'pulse': a.pulse
                }
                for a in self.predictions.anomalies
            ],

            'quality': {
                'current': self.predictions.quality.current_score,
                'predicted': self.predictions.quality.predicted_score,
                'trend': self.predictions.quality.trend,
                'factors': self.predictions.quality.factors
            } if self.predictions.quality else None,

            'ar_overlays': self._generate_ar_overlays()
        }

    def _get_health_color(self, health: float) -> str:
        """Get color for health score."""
        if health >= 80:
            return '#4CAF50'  # Green
        elif health >= 60:
            return '#FFC107'  # Amber
        elif health >= 40:
            return '#FF5722'  # Deep orange
        else:
            return '#F44336'  # Red

    def _generate_ar_overlays(self) -> List[Dict[str, Any]]:
        """Generate AR overlay data for HoloLens/Quest."""
        overlays = []

        # Tool wear overlays
        for tw in self.predictions.tool_wear:
            overlays.append({
                'type': 'gauge',
                'id': f'tool_{tw.tool_id}',
                'position': asdict(tw.position),
                'rotation': {'x': 0, 'y': 0, 'z': 0},
                'scale': 1.0,
                'value': tw.wear_percent / 100.0,
                'color': tw.color,
                'label': f'{tw.tool_name}: {tw.wear_percent:.0f}%'
            })

        # Anomaly overlays
        for a in self.predictions.anomalies:
            overlays.append({
                'type': 'marker',
                'id': f'anomaly_{a.anomaly_id}',
                'position': asdict(a.position),
                'rotation': {'x': 0, 'y': 0, 'z': 0},
                'scale': 1.5 if a.pulse else 1.0,
                'color': a.color,
                'pulse': a.pulse,
                'label': f'{a.component}: {a.severity}'
            })

        return overlays

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

    node = UnityPredictionPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
