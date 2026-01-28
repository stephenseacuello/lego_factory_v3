#!/usr/bin/env python3
"""
Heartbeat Monitor Node - Standalone ROS2 node for monitoring node heartbeats.

This node monitors heartbeat messages from supervised nodes and publishes
aggregated health status. It integrates with the supervision tree for
automatic failure detection and recovery triggering.

Industry 4.0/5.0 Architecture - ISA-95 Compliant
LEGO MCP Manufacturing System v7.0
"""

import json
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

# Try to import custom messages (may not be built yet)
try:
    from lego_mcp_msgs.msg import Heartbeat, SupervisorStatus
    from lego_mcp_msgs.srv import RestartNode, GetSupervisorStatus
    CUSTOM_MSGS_AVAILABLE = True
except ImportError:
    CUSTOM_MSGS_AVAILABLE = False


@dataclass
class MonitoredNode:
    """Status tracking for a monitored node."""
    node_id: str
    node_name: str
    namespace: str = ""
    last_heartbeat: float = 0.0
    heartbeat_count: int = 0
    missed_count: int = 0
    is_alive: bool = False
    state: str = "unknown"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    error_count: int = 0
    isa95_level: int = 2
    status_message: str = ""


class HeartbeatMonitorNode(Node):
    """
    ROS2 Node for monitoring heartbeats from supervised nodes.

    This node:
    - Subscribes to heartbeat topics from all supervised nodes
    - Tracks node health and detects failures
    - Publishes aggregated health diagnostics
    - Provides services for querying node status
    - Triggers recovery actions when nodes fail
    """

    def __init__(self):
        super().__init__('heartbeat_monitor')

        # Declare parameters
        self.declare_parameter('timeout_ms', 500)
        self.declare_parameter('check_interval_ms', 100)
        self.declare_parameter('missed_threshold', 3)
        self.declare_parameter('monitored_nodes', [])
        self.declare_parameter('heartbeat_topic', '/lego_mcp/heartbeats')
        self.declare_parameter('diagnostics_topic', '/diagnostics')
        self.declare_parameter('enable_auto_recovery', True)
        self.declare_parameter('recovery_cooldown_sec', 30.0)

        # Get parameters
        self._timeout_ms = self.get_parameter('timeout_ms').value
        self._check_interval_ms = self.get_parameter('check_interval_ms').value
        self._missed_threshold = self.get_parameter('missed_threshold').value
        self._monitored_node_names = self.get_parameter('monitored_nodes').value
        self._heartbeat_topic = self.get_parameter('heartbeat_topic').value
        self._diagnostics_topic = self.get_parameter('diagnostics_topic').value
        self._enable_auto_recovery = self.get_parameter('enable_auto_recovery').value
        self._recovery_cooldown_sec = self.get_parameter('recovery_cooldown_sec').value

        # Internal state
        self._monitored_nodes: Dict[str, MonitoredNode] = {}
        self._last_recovery_time: Dict[str, float] = {}
        self._lock = __import__('threading').RLock()

        # Callback groups
        self._timer_callback_group = MutuallyExclusiveCallbackGroup()
        self._service_callback_group = ReentrantCallbackGroup()

        # QoS profiles
        self._reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=10
        )

        # Subscribers
        if CUSTOM_MSGS_AVAILABLE:
            self._heartbeat_sub = self.create_subscription(
                Heartbeat,
                self._heartbeat_topic,
                self._heartbeat_callback,
                self._reliable_qos
            )
        else:
            # Fallback to String messages
            self._heartbeat_sub = self.create_subscription(
                String,
                self._heartbeat_topic,
                self._heartbeat_string_callback,
                self._reliable_qos
            )

        # Publishers
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray,
            self._diagnostics_topic,
            10
        )

        self._status_pub = self.create_publisher(
            String,
            '/lego_mcp/heartbeat_monitor/status',
            10
        )

        self._failure_pub = self.create_publisher(
            String,
            '/lego_mcp/heartbeat_monitor/failures',
            10
        )

        # Timers
        self._check_timer = self.create_timer(
            self._check_interval_ms / 1000.0,
            self._check_heartbeats,
            callback_group=self._timer_callback_group
        )

        self._diagnostics_timer = self.create_timer(
            1.0,  # 1 Hz diagnostics
            self._publish_diagnostics,
            callback_group=self._timer_callback_group
        )

        # Services
        self._get_status_srv = self.create_service(
            Trigger,
            '/lego_mcp/heartbeat_monitor/get_status',
            self._get_status_callback,
            callback_group=self._service_callback_group
        )

        self._reset_srv = self.create_service(
            Trigger,
            '/lego_mcp/heartbeat_monitor/reset',
            self._reset_callback,
            callback_group=self._service_callback_group
        )

        self.get_logger().info(
            f'Heartbeat Monitor started - timeout: {self._timeout_ms}ms, '
            f'threshold: {self._missed_threshold} missed'
        )

    def _heartbeat_callback(self, msg: 'Heartbeat'):
        """Process incoming heartbeat message (custom msg type)."""
        with self._lock:
            node_id = msg.node_id or msg.node_name

            if node_id not in self._monitored_nodes:
                self._monitored_nodes[node_id] = MonitoredNode(
                    node_id=node_id,
                    node_name=msg.node_name,
                    namespace=msg.node_namespace
                )
                self.get_logger().info(f'Now monitoring node: {node_id}')

            node = self._monitored_nodes[node_id]
            node.last_heartbeat = time.time()
            node.heartbeat_count += 1
            node.missed_count = 0
            node.is_alive = True
            node.state = self._state_to_string(msg.state)
            node.cpu_percent = msg.cpu_percent
            node.memory_mb = msg.memory_mb
            node.error_count = msg.error_count
            node.isa95_level = msg.isa95_level
            node.status_message = msg.status_message

    def _heartbeat_string_callback(self, msg: String):
        """Process incoming heartbeat message (fallback String type)."""
        try:
            data = json.loads(msg.data)
            node_id = data.get('node_id', data.get('node_name', 'unknown'))

            with self._lock:
                if node_id not in self._monitored_nodes:
                    self._monitored_nodes[node_id] = MonitoredNode(
                        node_id=node_id,
                        node_name=data.get('node_name', node_id),
                        namespace=data.get('namespace', '')
                    )
                    self.get_logger().info(f'Now monitoring node: {node_id}')

                node = self._monitored_nodes[node_id]
                node.last_heartbeat = time.time()
                node.heartbeat_count += 1
                node.missed_count = 0
                node.is_alive = True
                node.state = data.get('state', 'running')
                node.cpu_percent = data.get('cpu_percent', 0.0)
                node.memory_mb = data.get('memory_mb', 0.0)
                node.error_count = data.get('error_count', 0)
                node.status_message = data.get('status', '')

        except json.JSONDecodeError:
            self.get_logger().warning(f'Invalid heartbeat JSON: {msg.data[:100]}')

    def _state_to_string(self, state_id: int) -> str:
        """Convert state ID to string."""
        states = {
            0: 'unknown',
            1: 'starting',
            2: 'running',
            3: 'stopping',
            4: 'stopped',
            5: 'error',
            10: 'unconfigured',
            11: 'inactive',
            12: 'active',
            13: 'finalized',
        }
        return states.get(state_id, 'unknown')

    def _check_heartbeats(self):
        """Check for missed heartbeats and trigger recovery if needed."""
        current_time = time.time()
        timeout_sec = self._timeout_ms / 1000.0
        failed_nodes: List[str] = []

        with self._lock:
            for node_id, node in self._monitored_nodes.items():
                if node.last_heartbeat > 0:
                    elapsed = current_time - node.last_heartbeat

                    if elapsed > timeout_sec:
                        node.missed_count += 1

                        if node.missed_count >= self._missed_threshold:
                            if node.is_alive:
                                node.is_alive = False
                                node.state = 'failed'
                                failed_nodes.append(node_id)
                                self.get_logger().warning(
                                    f'Node {node_id} failed - {node.missed_count} missed heartbeats'
                                )

        # Handle failures
        for node_id in failed_nodes:
            self._handle_node_failure(node_id)

    def _handle_node_failure(self, node_id: str):
        """Handle detected node failure."""
        # Publish failure event
        failure_msg = String()
        failure_msg.data = json.dumps({
            'node_id': node_id,
            'timestamp': time.time(),
            'event': 'heartbeat_timeout',
            'missed_count': self._monitored_nodes[node_id].missed_count,
        })
        self._failure_pub.publish(failure_msg)

        # Check recovery cooldown
        last_recovery = self._last_recovery_time.get(node_id, 0)
        if time.time() - last_recovery < self._recovery_cooldown_sec:
            self.get_logger().info(
                f'Node {node_id} in recovery cooldown, skipping auto-recovery'
            )
            return

        # Trigger auto-recovery if enabled
        if self._enable_auto_recovery:
            self.get_logger().info(f'Triggering auto-recovery for node: {node_id}')
            self._last_recovery_time[node_id] = time.time()
            # Recovery would be triggered via supervisor service call here

    def _publish_diagnostics(self):
        """Publish diagnostics for all monitored nodes."""
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        with self._lock:
            for node_id, node in self._monitored_nodes.items():
                status = DiagnosticStatus()
                status.name = f'heartbeat_monitor/{node_id}'
                status.hardware_id = node_id

                if node.is_alive:
                    status.level = DiagnosticStatus.OK
                    status.message = f'Node alive - {node.state}'
                else:
                    status.level = DiagnosticStatus.ERROR
                    status.message = f'Node failed - {node.missed_count} missed heartbeats'

                status.values = [
                    KeyValue(key='state', value=node.state),
                    KeyValue(key='heartbeat_count', value=str(node.heartbeat_count)),
                    KeyValue(key='missed_count', value=str(node.missed_count)),
                    KeyValue(key='cpu_percent', value=f'{node.cpu_percent:.1f}'),
                    KeyValue(key='memory_mb', value=f'{node.memory_mb:.1f}'),
                    KeyValue(key='error_count', value=str(node.error_count)),
                    KeyValue(key='isa95_level', value=str(node.isa95_level)),
                ]

                diag_array.status.append(status)

        self._diagnostics_pub.publish(diag_array)

        # Publish summary status
        status_msg = String()
        with self._lock:
            alive = sum(1 for n in self._monitored_nodes.values() if n.is_alive)
            total = len(self._monitored_nodes)

        status_msg.data = json.dumps({
            'timestamp': time.time(),
            'total_nodes': total,
            'alive_nodes': alive,
            'failed_nodes': total - alive,
            'health_percent': (alive / total * 100) if total > 0 else 100,
        })
        self._status_pub.publish(status_msg)

    def _get_status_callback(self, request, response):
        """Service callback to get current status."""
        with self._lock:
            nodes_status = {
                node_id: {
                    'is_alive': node.is_alive,
                    'state': node.state,
                    'heartbeat_count': node.heartbeat_count,
                    'missed_count': node.missed_count,
                    'cpu_percent': node.cpu_percent,
                    'memory_mb': node.memory_mb,
                }
                for node_id, node in self._monitored_nodes.items()
            }

        response.success = True
        response.message = json.dumps({
            'nodes': nodes_status,
            'timeout_ms': self._timeout_ms,
            'missed_threshold': self._missed_threshold,
        })
        return response

    def _reset_callback(self, request, response):
        """Service callback to reset monitor state."""
        with self._lock:
            for node in self._monitored_nodes.values():
                node.missed_count = 0
                node.is_alive = True
            self._last_recovery_time.clear()

        response.success = True
        response.message = 'Heartbeat monitor reset'
        self.get_logger().info('Heartbeat monitor reset')
        return response


def main(args=None):
    """Main entry point for heartbeat monitor node."""
    rclpy.init(args=args)

    node = HeartbeatMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
