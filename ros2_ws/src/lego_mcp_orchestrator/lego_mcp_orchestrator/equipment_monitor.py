#!/usr/bin/env python3
"""
LEGO MCP Equipment Status Monitor

Aggregates status from all manufacturing equipment into a unified
monitoring interface with health tracking and alerting.

Equipment monitored:
- Niryo Ned2 robot arm
- xArm 6 Lite robot arm
- TinyG CNC (GRBL)
- MKS Laser Engraver (GRBL)
- Formlabs SLA printer
- Coastrunner CR-1

LEGO MCP Manufacturing System v7.0
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState


class EquipmentType(Enum):
    """Types of manufacturing equipment."""
    ROBOT_ARM = "robot_arm"
    CNC = "cnc"
    LASER = "laser"
    SLA_PRINTER = "sla_printer"
    FDM_PRINTER = "fdm_printer"


class EquipmentState(Enum):
    """Equipment operational states."""
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    EMERGENCY_STOP = "emergency_stop"


class HealthLevel(Enum):
    """Equipment health levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class EquipmentStatus:
    """Status data for a piece of equipment."""
    equipment_id: str
    equipment_type: EquipmentType
    state: EquipmentState = EquipmentState.UNKNOWN
    health: HealthLevel = HealthLevel.UNKNOWN
    last_seen: float = 0.0
    uptime_seconds: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    current_job: Optional[str] = None
    job_progress: float = 0.0
    position: Optional[Dict] = None
    temperature: Optional[Dict] = None
    metrics: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type.value,
            'state': self.state.value,
            'health': self.health.value,
            'last_seen': self.last_seen,
            'last_seen_iso': datetime.fromtimestamp(self.last_seen).isoformat() if self.last_seen else None,
            'uptime_seconds': self.uptime_seconds,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'current_job': self.current_job,
            'job_progress': self.job_progress,
            'position': self.position,
            'temperature': self.temperature,
            'metrics': self.metrics,
        }


@dataclass
class Alert:
    """Equipment alert."""
    alert_id: str
    equipment_id: str
    severity: str  # info, warning, error, critical
    message: str
    timestamp: float
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return {
            'alert_id': self.alert_id,
            'equipment_id': self.equipment_id,
            'severity': self.severity,
            'message': self.message,
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'acknowledged': self.acknowledged,
        }


class EquipmentMonitorNode(Node):
    """
    ROS2 node that monitors all manufacturing equipment.

    Subscribes to:
    - /ned2/joint_states, /ned2/status
    - /xarm/joint_states, /xarm/status
    - /grbl_cnc/status
    - /grbl_laser/status
    - /formlabs/status
    - /safety/estop_status

    Publishes:
    - /lego_mcp/equipment/status - Aggregated equipment status
    - /lego_mcp/equipment/alerts - Equipment alerts
    - /lego_mcp/equipment/health_summary - Overall health summary
    """

    def __init__(self):
        super().__init__('equipment_monitor')

        # Parameters
        self.declare_parameter('status_publish_rate', 1.0)  # Hz
        self.declare_parameter('offline_timeout_seconds', 10.0)
        self.declare_parameter('warning_timeout_seconds', 5.0)

        self.status_rate = self.get_parameter('status_publish_rate').value
        self.offline_timeout = self.get_parameter('offline_timeout_seconds').value
        self.warning_timeout = self.get_parameter('warning_timeout_seconds').value

        # Equipment registry
        self.equipment: Dict[str, EquipmentStatus] = {}
        self.equipment_start_times: Dict[str, float] = {}
        self.alerts: List[Alert] = []
        self.alert_counter = 0

        # E-stop state
        self.estop_active = False

        # Initialize equipment entries
        self._initialize_equipment()

        # QoS profile for reliable communication
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers for robot arms
        self.create_subscription(
            JointState, '/ned2/joint_states',
            self._on_ned2_joints, 10
        )
        self.create_subscription(
            String, '/ned2/status',
            self._on_ned2_status, 10
        )
        self.create_subscription(
            JointState, '/xarm/joint_states',
            self._on_xarm_joints, 10
        )
        self.create_subscription(
            String, '/xarm/status',
            self._on_xarm_status, 10
        )

        # Subscribers for CNC/laser equipment
        self.create_subscription(
            String, '/lego_mcp/cnc/status',
            self._on_cnc_status, 10
        )
        self.create_subscription(
            String, '/lego_mcp/laser/status',
            self._on_laser_status, 10
        )

        # Subscribers for printers
        self.create_subscription(
            String, '/lego_mcp/formlabs/status',
            self._on_formlabs_status, 10
        )
        self.create_subscription(
            String, '/lego_mcp/coastrunner/status',
            self._on_coastrunner_status, 10
        )

        # Safety e-stop subscriber
        self.create_subscription(
            Bool, '/safety/estop_status',
            self._on_estop_status, qos_reliable
        )

        # Publishers
        self.status_pub = self.create_publisher(
            String, '/lego_mcp/equipment/status', 10
        )
        self.alert_pub = self.create_publisher(
            String, '/lego_mcp/equipment/alerts', 10
        )
        self.health_pub = self.create_publisher(
            String, '/lego_mcp/equipment/health_summary', 10
        )

        # Status update timer
        self.timer = self.create_timer(
            1.0 / self.status_rate, self._publish_status
        )

        # Health check timer (less frequent)
        self.health_timer = self.create_timer(
            2.0, self._check_equipment_health
        )

        self.get_logger().info('Equipment Monitor initialized')

    def _initialize_equipment(self):
        """Initialize equipment registry with known equipment."""
        equipment_config = [
            ('ned2', EquipmentType.ROBOT_ARM),
            ('xarm', EquipmentType.ROBOT_ARM),
            ('tinyg_cnc', EquipmentType.CNC),
            ('mks_laser', EquipmentType.LASER),
            ('formlabs', EquipmentType.SLA_PRINTER),
            ('coastrunner', EquipmentType.FDM_PRINTER),
        ]

        now = time.time()
        for eq_id, eq_type in equipment_config:
            self.equipment[eq_id] = EquipmentStatus(
                equipment_id=eq_id,
                equipment_type=eq_type,
                state=EquipmentState.UNKNOWN,
                health=HealthLevel.UNKNOWN,
                last_seen=0.0,
            )
            self.equipment_start_times[eq_id] = now

    def _update_equipment(self, eq_id: str, **kwargs):
        """Update equipment status fields."""
        if eq_id not in self.equipment:
            self.get_logger().warn(f'Unknown equipment: {eq_id}')
            return

        eq = self.equipment[eq_id]
        now = time.time()

        # Track state transitions for alerts
        old_state = eq.state

        # Update fields
        for key, value in kwargs.items():
            if hasattr(eq, key):
                setattr(eq, key, value)

        # Update last seen
        eq.last_seen = now

        # Calculate uptime
        eq.uptime_seconds = now - self.equipment_start_times.get(eq_id, now)

        # Generate alerts on state transitions
        if 'state' in kwargs and old_state != kwargs['state']:
            self._handle_state_transition(eq_id, old_state, kwargs['state'])

    def _handle_state_transition(self, eq_id: str, old_state: EquipmentState,
                                  new_state: EquipmentState):
        """Handle equipment state transitions and generate alerts."""
        if new_state == EquipmentState.ERROR:
            self._create_alert(
                eq_id, 'error',
                f'Equipment {eq_id} entered ERROR state'
            )
        elif new_state == EquipmentState.EMERGENCY_STOP:
            self._create_alert(
                eq_id, 'critical',
                f'Equipment {eq_id} in EMERGENCY STOP'
            )
        elif old_state == EquipmentState.ERROR and new_state == EquipmentState.IDLE:
            self._create_alert(
                eq_id, 'info',
                f'Equipment {eq_id} recovered from error'
            )
        elif old_state == EquipmentState.OFFLINE and new_state != EquipmentState.OFFLINE:
            self._create_alert(
                eq_id, 'info',
                f'Equipment {eq_id} came online'
            )

    def _create_alert(self, eq_id: str, severity: str, message: str):
        """Create and publish an alert."""
        self.alert_counter += 1
        alert = Alert(
            alert_id=f'alert_{self.alert_counter}',
            equipment_id=eq_id,
            severity=severity,
            message=message,
            timestamp=time.time(),
        )
        self.alerts.append(alert)

        # Keep only recent alerts (last 100)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        # Publish alert
        msg = String()
        msg.data = json.dumps(alert.to_dict())
        self.alert_pub.publish(msg)

        # Log based on severity
        if severity == 'critical':
            self.get_logger().error(f'ALERT: {message}')
        elif severity == 'error':
            self.get_logger().error(f'Alert: {message}')
        elif severity == 'warning':
            self.get_logger().warn(f'Alert: {message}')
        else:
            self.get_logger().info(f'Alert: {message}')

    # Equipment-specific status handlers
    def _on_ned2_joints(self, msg: JointState):
        """Handle Ned2 joint state updates."""
        position = {}
        velocity = {}
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                position[name] = msg.position[i]
            if i < len(msg.velocity):
                velocity[name] = msg.velocity[i]

        self._update_equipment(
            'ned2',
            state=EquipmentState.IDLE if not self.estop_active else EquipmentState.EMERGENCY_STOP,
            position={'joints': position, 'velocities': velocity},
        )

    def _on_ned2_status(self, msg: String):
        """Handle Ned2 status updates."""
        try:
            data = json.loads(msg.data)
            state = self._parse_robot_state(data.get('state', 'unknown'))
            self._update_equipment(
                'ned2',
                state=state,
                error_code=data.get('error_code'),
                error_message=data.get('error_message'),
                current_job=data.get('current_job'),
                metrics=data.get('metrics', {}),
            )
        except json.JSONDecodeError:
            pass

    def _on_xarm_joints(self, msg: JointState):
        """Handle xArm joint state updates."""
        position = {}
        velocity = {}
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                position[name] = msg.position[i]
            if i < len(msg.velocity):
                velocity[name] = msg.velocity[i]

        self._update_equipment(
            'xarm',
            state=EquipmentState.IDLE if not self.estop_active else EquipmentState.EMERGENCY_STOP,
            position={'joints': position, 'velocities': velocity},
        )

    def _on_xarm_status(self, msg: String):
        """Handle xArm status updates."""
        try:
            data = json.loads(msg.data)
            state = self._parse_robot_state(data.get('state', 'unknown'))
            self._update_equipment(
                'xarm',
                state=state,
                error_code=data.get('error_code'),
                error_message=data.get('error_message'),
                current_job=data.get('current_job'),
                metrics=data.get('metrics', {}),
            )
        except json.JSONDecodeError:
            pass

    def _on_cnc_status(self, msg: String):
        """Handle CNC status updates."""
        try:
            data = json.loads(msg.data)
            state = self._parse_grbl_state(data.get('machine_state', 'unknown'))

            position = None
            if 'position' in data:
                position = {
                    'x': data['position'].get('x', 0),
                    'y': data['position'].get('y', 0),
                    'z': data['position'].get('z', 0),
                }

            self._update_equipment(
                'tinyg_cnc',
                state=state,
                position=position,
                current_job=data.get('current_file'),
                job_progress=data.get('progress', 0.0),
                metrics={
                    'feed_rate': data.get('feed_rate', 0),
                    'spindle_speed': data.get('spindle_speed', 0),
                },
            )
        except json.JSONDecodeError:
            pass

    def _on_laser_status(self, msg: String):
        """Handle laser engraver status updates."""
        try:
            data = json.loads(msg.data)
            state = self._parse_grbl_state(data.get('machine_state', 'unknown'))

            position = None
            if 'position' in data:
                position = {
                    'x': data['position'].get('x', 0),
                    'y': data['position'].get('y', 0),
                }

            self._update_equipment(
                'mks_laser',
                state=state,
                position=position,
                current_job=data.get('current_file'),
                job_progress=data.get('progress', 0.0),
                metrics={
                    'laser_power': data.get('laser_power', 0),
                    'feed_rate': data.get('feed_rate', 0),
                },
            )
        except json.JSONDecodeError:
            pass

    def _on_formlabs_status(self, msg: String):
        """Handle Formlabs printer status updates."""
        try:
            data = json.loads(msg.data)
            printer_data = data.get('printer', {})
            state = self._parse_printer_state(printer_data.get('state', 'unknown'))

            temperature = None
            if 'temperature' in printer_data:
                temperature = {
                    'resin': printer_data['temperature'].get('resin', 0),
                    'chamber': printer_data['temperature'].get('chamber', 0),
                }

            self._update_equipment(
                'formlabs',
                state=state,
                current_job=data.get('current_job', {}).get('name'),
                job_progress=data.get('current_job', {}).get('progress', 0.0),
                temperature=temperature,
                metrics={
                    'current_layer': data.get('current_job', {}).get('current_layer', 0),
                    'total_layers': data.get('current_job', {}).get('total_layers', 0),
                    'resin_ml_used': printer_data.get('resin_ml_used', 0),
                    'tank_hours': printer_data.get('tank_hours', 0),
                },
            )
        except json.JSONDecodeError:
            pass

    def _on_coastrunner_status(self, msg: String):
        """Handle Coastrunner CR-1 status updates."""
        try:
            data = json.loads(msg.data)
            state = self._parse_printer_state(data.get('state', 'unknown'))

            temperature = None
            if 'temperature' in data:
                temperature = {
                    'hotend': data['temperature'].get('hotend', 0),
                    'bed': data['temperature'].get('bed', 0),
                }

            self._update_equipment(
                'coastrunner',
                state=state,
                position=data.get('position'),
                current_job=data.get('current_file'),
                job_progress=data.get('progress', 0.0),
                temperature=temperature,
                metrics={
                    'current_layer': data.get('current_layer', 0),
                    'total_layers': data.get('total_layers', 0),
                    'filament_used_mm': data.get('filament_used_mm', 0),
                },
            )
        except json.JSONDecodeError:
            pass

    def _on_estop_status(self, msg: Bool):
        """Handle e-stop status updates."""
        was_active = self.estop_active
        self.estop_active = msg.data

        if self.estop_active and not was_active:
            self._create_alert(
                'system', 'critical',
                'EMERGENCY STOP ACTIVATED - All equipment halted'
            )
            # Set all equipment to e-stop state
            for eq_id in self.equipment:
                self._update_equipment(eq_id, state=EquipmentState.EMERGENCY_STOP)
        elif not self.estop_active and was_active:
            self._create_alert(
                'system', 'info',
                'Emergency stop released'
            )

    # State parsing helpers
    def _parse_robot_state(self, state_str: str) -> EquipmentState:
        """Parse robot state string to EquipmentState."""
        state_map = {
            'idle': EquipmentState.IDLE,
            'moving': EquipmentState.BUSY,
            'busy': EquipmentState.BUSY,
            'error': EquipmentState.ERROR,
            'fault': EquipmentState.ERROR,
            'initializing': EquipmentState.INITIALIZING,
            'emergency_stop': EquipmentState.EMERGENCY_STOP,
            'estop': EquipmentState.EMERGENCY_STOP,
        }
        return state_map.get(state_str.lower(), EquipmentState.UNKNOWN)

    def _parse_grbl_state(self, state_str: str) -> EquipmentState:
        """Parse GRBL state string to EquipmentState."""
        state_map = {
            'idle': EquipmentState.IDLE,
            'run': EquipmentState.BUSY,
            'hold': EquipmentState.BUSY,
            'jog': EquipmentState.BUSY,
            'alarm': EquipmentState.ERROR,
            'door': EquipmentState.ERROR,
            'check': EquipmentState.INITIALIZING,
            'home': EquipmentState.INITIALIZING,
            'sleep': EquipmentState.IDLE,
        }
        return state_map.get(state_str.lower(), EquipmentState.UNKNOWN)

    def _parse_printer_state(self, state_str: str) -> EquipmentState:
        """Parse printer state string to EquipmentState."""
        state_map = {
            'idle': EquipmentState.IDLE,
            'ready': EquipmentState.IDLE,
            'printing': EquipmentState.BUSY,
            'heating': EquipmentState.BUSY,
            'filling': EquipmentState.BUSY,
            'separating': EquipmentState.BUSY,
            'finished': EquipmentState.IDLE,
            'error': EquipmentState.ERROR,
            'paused': EquipmentState.BUSY,
            'offline': EquipmentState.OFFLINE,
        }
        return state_map.get(state_str.lower(), EquipmentState.UNKNOWN)

    def _check_equipment_health(self):
        """Check equipment health based on last seen time and state."""
        now = time.time()

        for eq_id, eq in self.equipment.items():
            old_health = eq.health

            # Check if equipment is responding
            if eq.last_seen == 0:
                eq.health = HealthLevel.UNKNOWN
            elif now - eq.last_seen > self.offline_timeout:
                if eq.state != EquipmentState.OFFLINE:
                    self._update_equipment(eq_id, state=EquipmentState.OFFLINE)
                eq.health = HealthLevel.CRITICAL
            elif now - eq.last_seen > self.warning_timeout:
                eq.health = HealthLevel.WARNING
            elif eq.state == EquipmentState.ERROR:
                eq.health = HealthLevel.CRITICAL
            elif eq.state == EquipmentState.EMERGENCY_STOP:
                eq.health = HealthLevel.CRITICAL
            else:
                eq.health = HealthLevel.HEALTHY

            # Alert on health changes
            if old_health != eq.health:
                if eq.health == HealthLevel.CRITICAL:
                    self._create_alert(
                        eq_id, 'critical',
                        f'Equipment {eq_id} health is CRITICAL'
                    )
                elif eq.health == HealthLevel.WARNING:
                    self._create_alert(
                        eq_id, 'warning',
                        f'Equipment {eq_id} health degraded to WARNING'
                    )

    def _publish_status(self):
        """Publish aggregated equipment status."""
        # Build status message
        status_data = {
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            'estop_active': self.estop_active,
            'equipment': {
                eq_id: eq.to_dict()
                for eq_id, eq in self.equipment.items()
            },
        }

        msg = String()
        msg.data = json.dumps(status_data)
        self.status_pub.publish(msg)

        # Publish health summary
        self._publish_health_summary()

    def _publish_health_summary(self):
        """Publish overall health summary."""
        health_counts = {level.value: 0 for level in HealthLevel}
        state_counts = {state.value: 0 for state in EquipmentState}

        for eq in self.equipment.values():
            health_counts[eq.health.value] += 1
            state_counts[eq.state.value] += 1

        # Determine overall health
        if health_counts[HealthLevel.CRITICAL.value] > 0:
            overall_health = HealthLevel.CRITICAL.value
        elif health_counts[HealthLevel.WARNING.value] > 0:
            overall_health = HealthLevel.WARNING.value
        elif health_counts[HealthLevel.UNKNOWN.value] == len(self.equipment):
            overall_health = HealthLevel.UNKNOWN.value
        else:
            overall_health = HealthLevel.HEALTHY.value

        summary = {
            'timestamp': time.time(),
            'overall_health': overall_health,
            'estop_active': self.estop_active,
            'equipment_count': len(self.equipment),
            'health_breakdown': health_counts,
            'state_breakdown': state_counts,
            'active_alerts': len([a for a in self.alerts if not a.acknowledged]),
            'recent_alerts': [a.to_dict() for a in self.alerts[-5:]],
        }

        msg = String()
        msg.data = json.dumps(summary)
        self.health_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = EquipmentMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
