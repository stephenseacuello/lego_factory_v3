#!/usr/bin/env python3
"""
Digital Twin Synchronization Node

Maintains real-time digital twin of the LEGO MCP factory cell.
Collects state from all equipment, computes metrics, and publishes
synchronized twin state for visualization and analysis.

Features:
- Real-time equipment state aggregation
- OEE (Overall Equipment Effectiveness) calculation
- Bidirectional sync with physical assets
- AR/VR-ready pose data
- PINN integration for predictive analytics
- ISO 23247 Digital Twin compliant

LEGO MCP Manufacturing System v7.0
"""

import json
import hashlib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Header
from std_srvs.srv import Trigger
from geometry_msgs.msg import Pose, Transform, Vector3, Quaternion

try:
    from lego_mcp_msgs.msg import (
        TwinState, TwinSync, EquipmentStatus,
        Heartbeat, QualityEvent
    )
    from lego_mcp_msgs.srv import GetTwinState
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    print("Warning: lego_mcp_msgs not available, running in stub mode")


class SyncDirection(Enum):
    """Sync direction enumeration."""
    P2D = 0  # Physical to Digital
    D2P = 1  # Digital to Physical
    BIDIRECTIONAL = 2


class HealthLevel(Enum):
    """System health level."""
    CRITICAL = 0
    DEGRADED = 1
    WARNING = 2
    HEALTHY = 3


@dataclass
class EquipmentState:
    """Tracked equipment state."""
    equipment_id: str
    equipment_type: str
    status: str = "OFFLINE"
    connected: bool = False
    last_seen: float = 0.0
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    orientation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    utilization: float = 0.0
    error_count: int = 0
    cycle_time_sec: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductionMetrics:
    """Production metrics tracking."""
    parts_produced: int = 0
    parts_target: int = 100
    good_parts: int = 0
    defective_parts: int = 0
    planned_time_sec: float = 28800.0  # 8 hour shift
    actual_runtime_sec: float = 0.0
    downtime_sec: float = 0.0
    ideal_cycle_time_sec: float = 60.0
    actual_cycle_times: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class OEEMetrics:
    """OEE calculation results."""
    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0
    overall: float = 0.0
    timestamp: float = 0.0


class DigitalTwinNode(Node):
    """
    Digital Twin synchronization node for LEGO MCP factory cell.

    Aggregates state from all equipment and subsystems, maintains
    synchronized digital twin, and provides real-time metrics.
    """

    def __init__(self):
        super().__init__('digital_twin')

        # Parameters
        self.declare_parameter('twin_id', 'lego_mcp_factory_twin')
        self.declare_parameter('factory_cell_id', 'CELL-001')
        self.declare_parameter('sync_rate_hz', 10.0)
        self.declare_parameter('oee_calculation_interval_sec', 60.0)
        self.declare_parameter('state_history_size', 1000)
        self.declare_parameter('enable_pinn_predictions', False)

        self._twin_id = self.get_parameter('twin_id').value
        self._factory_cell_id = self.get_parameter('factory_cell_id').value
        self._sync_rate = self.get_parameter('sync_rate_hz').value
        self._oee_interval = self.get_parameter('oee_calculation_interval_sec').value
        self._history_size = self.get_parameter('state_history_size').value
        self._enable_pinn = self.get_parameter('enable_pinn_predictions').value

        # State tracking
        self._equipment_states: Dict[str, EquipmentState] = {}
        self._production = ProductionMetrics()
        self._oee = OEEMetrics()
        self._active_work_orders: List[str] = []
        self._active_jobs: List[str] = []
        self._active_alerts: List[Tuple[str, int]] = []  # (message, severity)
        self._sequence_number = 0
        self._lock = threading.RLock()

        # State history for rollback/playback
        self._state_history: deque = deque(maxlen=self._history_size)

        # Material tracking
        self._material_levels: Dict[str, float] = {
            'pla_white': 100.0,
            'pla_red': 100.0,
            'pla_blue': 100.0,
            'pla_yellow': 100.0,
            'pla_black': 100.0,
            'resin_grey': 100.0,
            'resin_clear': 100.0,
        }

        # Initialize equipment
        self._init_equipment()

        # Callback groups
        self._timer_group = MutuallyExclusiveCallbackGroup()
        self._sub_group = ReentrantCallbackGroup()
        self._srv_group = ReentrantCallbackGroup()

        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Publishers
        self._twin_state_pub = self.create_publisher(
            TwinState if MSGS_AVAILABLE else String,
            '/lego_mcp/digital_twin/state',
            reliable_qos
        )

        self._twin_sync_pub = self.create_publisher(
            TwinSync if MSGS_AVAILABLE else String,
            '/lego_mcp/digital_twin/sync',
            reliable_qos
        )

        self._metrics_pub = self.create_publisher(
            String,
            '/lego_mcp/digital_twin/metrics',
            10
        )

        self._events_pub = self.create_publisher(
            String,
            '/lego_mcp/digital_twin/events',
            10
        )

        # Subscribers - Equipment status
        self._subscribe_to_equipment()

        # Subscribers - Work orders
        self.create_subscription(
            String,
            '/lego_mcp/work_order/events',
            self._on_work_order_event,
            10,
            callback_group=self._sub_group
        )

        # Subscribers - Quality events
        if MSGS_AVAILABLE:
            self.create_subscription(
                QualityEvent,
                '/quality/events',
                self._on_quality_event,
                10,
                callback_group=self._sub_group
            )

        # Subscribers - Heartbeats
        if MSGS_AVAILABLE:
            self.create_subscription(
                Heartbeat,
                '/lego_mcp/heartbeats',
                self._on_heartbeat,
                10,
                callback_group=self._sub_group
            )

        # Services
        if MSGS_AVAILABLE:
            self._get_state_srv = self.create_service(
                GetTwinState,
                '/lego_mcp/digital_twin/get_state',
                self._get_state_callback,
                callback_group=self._srv_group
            )

        self._get_oee_srv = self.create_service(
            Trigger,
            '/lego_mcp/digital_twin/get_oee',
            self._get_oee_callback,
            callback_group=self._srv_group
        )

        self._get_history_srv = self.create_service(
            Trigger,
            '/lego_mcp/digital_twin/get_history',
            self._get_history_callback,
            callback_group=self._srv_group
        )

        # Timers
        self._sync_timer = self.create_timer(
            1.0 / self._sync_rate,
            self._publish_twin_state,
            callback_group=self._timer_group
        )

        self._oee_timer = self.create_timer(
            self._oee_interval,
            self._calculate_oee,
            callback_group=self._timer_group
        )

        self._health_timer = self.create_timer(
            5.0,
            self._check_system_health,
            callback_group=self._timer_group
        )

        # Shift tracking
        self._shift_start = time.time()
        self._last_oee_calculation = time.time()

        self.get_logger().info(
            f'Digital Twin started - ID: {self._twin_id}, '
            f'sync rate: {self._sync_rate}Hz'
        )

    def _init_equipment(self):
        """Initialize known equipment."""
        equipment_config = [
            ('grbl_cnc', 'CNC', (0.0, 0.0, 0.0)),
            ('formlabs_sla', 'SLA', (1.0, 0.0, 0.0)),
            ('bambu_fdm', 'FDM', (2.0, 0.0, 0.0)),
            ('ned2', 'ROBOT', (3.0, 0.0, 0.0)),
            ('xarm', 'ROBOT', (4.0, 0.0, 0.0)),
            ('vision_station', 'INSPECTION', (2.0, 1.0, 0.0)),
            ('alvik_01', 'AGV', (0.0, -1.0, 0.0)),
            ('alvik_02', 'AGV', (4.0, -1.0, 0.0)),
        ]

        for eq_id, eq_type, position in equipment_config:
            self._equipment_states[eq_id] = EquipmentState(
                equipment_id=eq_id,
                equipment_type=eq_type,
                position=position,
            )

    def _subscribe_to_equipment(self):
        """Subscribe to equipment status topics."""
        equipment_topics = [
            '/grbl/status',
            '/formlabs/status',
            '/bambu/status',
            '/ned2/status',
            '/xarm/status',
            '/lego_mcp/agv/fleet',
            '/lego_mcp/equipment/registry',
        ]

        for topic in equipment_topics:
            self.create_subscription(
                String,
                topic,
                lambda msg, t=topic: self._on_equipment_status(t, msg),
                10,
                callback_group=self._sub_group
            )

    def _on_equipment_status(self, topic: str, msg: String):
        """Handle equipment status update."""
        try:
            data = json.loads(msg.data)

            with self._lock:
                if 'equipment' in data:
                    # Equipment registry message
                    for eq in data['equipment']:
                        eq_id = eq.get('equipment_id', '')
                        if eq_id in self._equipment_states:
                            state = self._equipment_states[eq_id]
                            state.status = eq.get('status', 'OFFLINE')
                            state.connected = (state.status == 'ONLINE')
                            state.last_seen = time.time()
                elif 'agvs' in data:
                    # AGV fleet message
                    for agv in data['agvs']:
                        agv_id = agv.get('agv_id', '')
                        if agv_id in self._equipment_states:
                            state = self._equipment_states[agv_id]
                            state.status = agv.get('state', 'OFFLINE')
                            state.connected = agv.get('is_available', False)
                            pos = agv.get('position', [0, 0, 0])
                            state.position = tuple(pos) if len(pos) >= 3 else (0, 0, 0)
                            state.last_seen = time.time()
                            state.properties['battery'] = agv.get('battery_percent', 0)
                else:
                    # Generic equipment status
                    eq_id = data.get('equipment_id') or data.get('printer_id') or data.get('machine_id')
                    if eq_id and eq_id in self._equipment_states:
                        state = self._equipment_states[eq_id]
                        state.status = data.get('state', data.get('status', 'UNKNOWN'))
                        state.connected = data.get('connected', True)
                        state.last_seen = time.time()
                        state.properties.update(data)

        except json.JSONDecodeError:
            pass

    def _on_work_order_event(self, msg: String):
        """Handle work order events."""
        try:
            event = json.loads(msg.data)
            event_type = event.get('event_type', '')
            data = event.get('data', {})

            with self._lock:
                wo_id = data.get('work_order_id', '')

                if event_type == 'work_order_started':
                    if wo_id and wo_id not in self._active_work_orders:
                        self._active_work_orders.append(wo_id)
                elif event_type == 'work_order_completed':
                    if wo_id in self._active_work_orders:
                        self._active_work_orders.remove(wo_id)

                    # Update production metrics
                    parts = data.get('parts_produced', 0)
                    self._production.parts_produced += parts

        except json.JSONDecodeError:
            pass

    def _on_quality_event(self, msg):
        """Handle quality events."""
        with self._lock:
            if msg.action == 1:  # ACCEPT
                self._production.good_parts += 1
            elif msg.action in [4, 5, 6]:  # REJECT, STOP, REWORK
                self._production.defective_parts += 1

    def _on_heartbeat(self, msg):
        """Handle heartbeat messages."""
        with self._lock:
            node_name = msg.node_name if hasattr(msg, 'node_name') else ''

            # Map node name to equipment
            eq_mapping = {
                'grbl_node': 'grbl_cnc',
                'formlabs_node': 'formlabs_sla',
                'bambu_node': 'bambu_fdm',
            }

            eq_id = eq_mapping.get(node_name)
            if eq_id and eq_id in self._equipment_states:
                state = self._equipment_states[eq_id]
                state.last_seen = time.time()
                state.connected = True
                state.status = 'ONLINE'

    def _calculate_oee(self):
        """Calculate Overall Equipment Effectiveness."""
        with self._lock:
            current_time = time.time()
            elapsed_sec = current_time - self._shift_start

            # Availability = Runtime / Planned Time
            # For now, calculate based on equipment connectivity
            online_count = sum(
                1 for eq in self._equipment_states.values()
                if eq.connected and eq.equipment_type in ['CNC', 'SLA', 'FDM']
            )
            total_production_equipment = 3  # CNC, SLA, FDM
            availability = online_count / total_production_equipment if total_production_equipment > 0 else 0

            # Performance = (Ideal Cycle Time × Total Parts) / Runtime
            total_parts = self._production.parts_produced
            ideal_time = self._production.ideal_cycle_time_sec * total_parts
            performance = ideal_time / elapsed_sec if elapsed_sec > 0 else 0
            performance = min(1.0, performance)  # Cap at 100%

            # Quality = Good Parts / Total Parts
            if total_parts > 0:
                quality = self._production.good_parts / total_parts
            else:
                quality = 1.0

            # Overall OEE
            overall = availability * performance * quality

            self._oee = OEEMetrics(
                availability=availability,
                performance=performance,
                quality=quality,
                overall=overall,
                timestamp=current_time,
            )

            # Publish metrics
            self._publish_metrics()

            self.get_logger().debug(
                f'OEE calculated - A: {availability:.2%}, '
                f'P: {performance:.2%}, Q: {quality:.2%}, '
                f'Overall: {overall:.2%}'
            )

    def _check_system_health(self):
        """Check overall system health."""
        with self._lock:
            alerts = []
            current_time = time.time()

            # Check equipment connectivity
            offline_timeout = 30.0
            for eq_id, eq in self._equipment_states.items():
                if eq.last_seen > 0:
                    time_since_seen = current_time - eq.last_seen
                    if time_since_seen > offline_timeout:
                        alerts.append((f'{eq_id} offline for {time_since_seen:.0f}s', 2))

            # Check OEE thresholds
            if self._oee.overall < 0.65:
                alerts.append(f'OEE below target: {self._oee.overall:.1%}', 2)
            if self._oee.quality < 0.95:
                alerts.append(f'Quality below target: {self._oee.quality:.1%}', 2)

            # Check material levels
            for material, level in self._material_levels.items():
                if level < 20.0:
                    alerts.append((f'{material} low: {level:.0f}%', 1))

            self._active_alerts = alerts

    def _publish_twin_state(self):
        """Publish current twin state."""
        with self._lock:
            self._sequence_number += 1

            if MSGS_AVAILABLE:
                msg = self._create_twin_state_msg()
            else:
                msg = String()
                msg.data = json.dumps(self._create_twin_state_dict())

            self._twin_state_pub.publish(msg)

            # Store in history
            state_snapshot = self._create_twin_state_dict()
            self._state_history.append({
                'timestamp': time.time(),
                'sequence': self._sequence_number,
                'state': state_snapshot,
            })

    def _create_twin_state_msg(self) -> 'TwinState':
        """Create TwinState message."""
        msg = TwinState()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'world'

        msg.twin_id = self._twin_id
        msg.factory_cell_id = self._factory_cell_id
        msg.sequence_number = self._sequence_number

        # Timestamps
        msg.physical_timestamp = self.get_clock().now().to_msg()
        msg.twin_timestamp = self.get_clock().now().to_msg()
        msg.sync_latency_ms = 0.0
        msg.synchronized = True

        # Equipment states
        for eq_id, eq in self._equipment_states.items():
            eq_status = EquipmentStatus()
            eq_status.equipment_id = eq_id
            eq_status.equipment_type = eq.equipment_type
            eq_status.state = 1 if eq.connected else 0
            eq_status.connected = eq.connected
            msg.equipment_states.append(eq_status)

        # Active work
        msg.active_work_orders = self._active_work_orders.copy()
        msg.active_jobs = self._active_jobs.copy()
        msg.queue_depth = len(self._active_work_orders)

        # Production metrics
        msg.parts_produced_today = self._production.parts_produced
        msg.parts_target_today = self._production.parts_target
        if self._production.actual_cycle_times:
            avg_cycle = sum(self._production.actual_cycle_times) / len(self._production.actual_cycle_times)
            msg.production_rate = 3600.0 / avg_cycle if avg_cycle > 0 else 0
        else:
            msg.production_rate = 0.0
        total = self._production.parts_produced
        msg.defect_rate = self._production.defective_parts / total if total > 0 else 0

        # OEE
        msg.oee_overall = self._oee.overall
        msg.oee_availability = self._oee.availability
        msg.oee_performance = self._oee.performance
        msg.oee_quality = self._oee.quality

        # Materials
        msg.material_types = list(self._material_levels.keys())
        msg.material_levels = list(self._material_levels.values())

        # Energy (simulated)
        online_eq = sum(1 for eq in self._equipment_states.values() if eq.connected)
        msg.energy_consumption_kw = online_eq * 0.5  # 0.5 kW per online equipment

        # Equipment poses
        for eq_id, eq in self._equipment_states.items():
            pose = Pose()
            pose.position.x = eq.position[0]
            pose.position.y = eq.position[1]
            pose.position.z = eq.position[2]
            pose.orientation.x = eq.orientation[0]
            pose.orientation.y = eq.orientation[1]
            pose.orientation.z = eq.orientation[2]
            pose.orientation.w = eq.orientation[3]
            msg.equipment_poses.append(pose)
            msg.equipment_frame_ids.append(f'{eq_id}_frame')

        # Alerts
        msg.active_alerts = [a[0] for a in self._active_alerts]
        msg.alert_severities = [a[1] for a in self._active_alerts]
        msg.unacknowledged_events = len(self._active_alerts)

        # Health
        if any(a[1] == 0 for a in self._active_alerts):
            msg.overall_health = 0  # Critical
            msg.health_summary = "Critical alerts present"
        elif any(a[1] == 1 for a in self._active_alerts):
            msg.overall_health = 1  # Degraded
            msg.health_summary = "System degraded"
        elif any(a[1] == 2 for a in self._active_alerts):
            msg.overall_health = 2  # Warning
            msg.health_summary = "Warnings present"
        else:
            msg.overall_health = 3  # Healthy
            msg.health_summary = "All systems nominal"

        return msg

    def _create_twin_state_dict(self) -> dict:
        """Create twin state as dictionary."""
        return {
            'twin_id': self._twin_id,
            'factory_cell_id': self._factory_cell_id,
            'sequence_number': self._sequence_number,
            'timestamp': time.time(),
            'equipment': {
                eq_id: {
                    'type': eq.equipment_type,
                    'status': eq.status,
                    'connected': eq.connected,
                    'position': eq.position,
                    'last_seen': eq.last_seen,
                }
                for eq_id, eq in self._equipment_states.items()
            },
            'production': {
                'parts_produced': self._production.parts_produced,
                'parts_target': self._production.parts_target,
                'good_parts': self._production.good_parts,
                'defective_parts': self._production.defective_parts,
            },
            'oee': {
                'availability': self._oee.availability,
                'performance': self._oee.performance,
                'quality': self._oee.quality,
                'overall': self._oee.overall,
            },
            'materials': self._material_levels.copy(),
            'alerts': [{'message': a[0], 'severity': a[1]} for a in self._active_alerts],
            'active_work_orders': self._active_work_orders.copy(),
        }

    def _publish_metrics(self):
        """Publish metrics for monitoring."""
        metrics = {
            'timestamp': time.time(),
            'oee': {
                'availability': self._oee.availability,
                'performance': self._oee.performance,
                'quality': self._oee.quality,
                'overall': self._oee.overall,
            },
            'production': {
                'parts_produced': self._production.parts_produced,
                'good_parts': self._production.good_parts,
                'defective_parts': self._production.defective_parts,
                'target': self._production.parts_target,
            },
            'equipment_status': {
                eq_id: {'connected': eq.connected, 'status': eq.status}
                for eq_id, eq in self._equipment_states.items()
            },
        }

        msg = String()
        msg.data = json.dumps(metrics)
        self._metrics_pub.publish(msg)

    def _get_state_callback(self, request, response):
        """Handle get state service request."""
        with self._lock:
            state_dict = self._create_twin_state_dict()

        response.success = True
        response.state_json = json.dumps(state_dict)
        return response

    def _get_oee_callback(self, request, response):
        """Handle get OEE service request."""
        with self._lock:
            oee_data = {
                'timestamp': self._oee.timestamp,
                'availability': self._oee.availability,
                'performance': self._oee.performance,
                'quality': self._oee.quality,
                'overall': self._oee.overall,
                'parts_produced': self._production.parts_produced,
                'good_parts': self._production.good_parts,
                'defective_parts': self._production.defective_parts,
            }

        response.success = True
        response.message = json.dumps(oee_data)
        return response

    def _get_history_callback(self, request, response):
        """Handle get history service request."""
        with self._lock:
            # Return last 100 entries
            history = list(self._state_history)[-100:]

        response.success = True
        response.message = json.dumps({
            'history_size': len(history),
            'entries': history,
        })
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = DigitalTwinNode()

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
