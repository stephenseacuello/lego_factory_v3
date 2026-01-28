#!/usr/bin/env python3
"""
ROS2 Lifecycle Monitor Node

Monitors lifecycle state transitions for all managed nodes and publishes
diagnostics. Provides real-time visibility into system health.

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from lifecycle_msgs.srv import GetState
from lifecycle_msgs.msg import State, TransitionEvent
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from std_msgs.msg import String
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
import time


@dataclass
class NodeStateRecord:
    """Record of a node's lifecycle state."""
    name: str
    namespace: str
    current_state: int = State.PRIMARY_STATE_UNKNOWN
    state_label: str = "unknown"
    last_update: float = 0.0
    transition_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    state_history: List[Dict] = field(default_factory=list)


class LifecycleMonitor(Node):
    """
    Lifecycle Monitor Node.

    Monitors lifecycle state of all managed nodes and publishes
    comprehensive diagnostics for system health visibility.
    """

    def __init__(self):
        super().__init__('lifecycle_monitor')

        # Parameters
        self.declare_parameter('monitored_nodes', [
            'safety_node',
            'grbl_node',
            'formlabs_node',
            'bambu_node',
            'orchestrator'
        ])
        self.declare_parameter('namespace', '/lego_mcp')
        self.declare_parameter('poll_rate_hz', 1.0)
        self.declare_parameter('history_size', 100)

        # Get parameters
        self._namespace = self.get_parameter('namespace').value
        self._poll_rate = self.get_parameter('poll_rate_hz').value
        self._history_size = self.get_parameter('history_size').value
        self._monitored_names = self.get_parameter('monitored_nodes').value

        # State tracking
        self._lock = RLock()
        self._node_states: Dict[str, NodeStateRecord] = {}
        self._get_state_clients: Dict[str, object] = {}

        # Callback group for async operations
        self._cb_group = ReentrantCallbackGroup()

        # Initialize state records
        for name in self._monitored_names:
            self._node_states[name] = NodeStateRecord(
                name=name,
                namespace=self._namespace
            )

        # Create service clients
        self._create_state_clients()

        # Subscribe to transition events
        self._create_transition_subscribers()

        # Publishers
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray,
            '/diagnostics',
            10
        )

        self._status_pub = self.create_publisher(
            String,
            f'{self._namespace}/lifecycle_monitor/status',
            10
        )

        self._state_summary_pub = self.create_publisher(
            String,
            f'{self._namespace}/lifecycle_monitor/state_summary',
            10
        )

        # Polling timer
        poll_period = 1.0 / self._poll_rate
        self._poll_timer = self.create_timer(
            poll_period,
            self._poll_node_states,
            callback_group=self._cb_group
        )

        # Diagnostics timer (slower rate)
        self._diag_timer = self.create_timer(
            2.0,
            self._publish_diagnostics
        )

        self.get_logger().info(
            f'Lifecycle Monitor initialized, monitoring {len(self._monitored_names)} nodes'
        )

    def _create_state_clients(self):
        """Create GetState service clients for all monitored nodes."""
        for name in self._monitored_names:
            full_name = f'{self._namespace}/{name}'
            self._get_state_clients[name] = self.create_client(
                GetState,
                f'{full_name}/get_state',
                callback_group=self._cb_group
            )

    def _create_transition_subscribers(self):
        """Subscribe to lifecycle transition events for all nodes."""
        for name in self._monitored_names:
            full_name = f'{self._namespace}/{name}'
            self.create_subscription(
                TransitionEvent,
                f'{full_name}/transition_event',
                lambda msg, n=name: self._on_transition_event(n, msg),
                10,
                callback_group=self._cb_group
            )

    def _on_transition_event(self, node_name: str, event: TransitionEvent):
        """Handle lifecycle transition event from a node."""
        with self._lock:
            if node_name not in self._node_states:
                return

            record = self._node_states[node_name]

            # Update state
            record.current_state = event.goal_state.id
            record.state_label = event.goal_state.label
            record.last_update = time.time()
            record.transition_count += 1

            # Check for error transitions
            if event.goal_state.id == State.PRIMARY_STATE_UNCONFIGURED:
                if event.transition.id in [
                    State.TRANSITION_STATE_ERRORPROCESSING,
                ]:
                    record.error_count += 1
                    record.last_error = f"Error transition at {datetime.now().isoformat()}"

            # Add to history
            history_entry = {
                'timestamp': time.time(),
                'from_state': event.start_state.label,
                'to_state': event.goal_state.label,
                'transition': event.transition.label
            }
            record.state_history.append(history_entry)

            # Trim history
            if len(record.state_history) > self._history_size:
                record.state_history = record.state_history[-self._history_size:]

            self.get_logger().debug(
                f'{node_name}: {event.start_state.label} -> {event.goal_state.label}'
            )

    def _poll_node_states(self):
        """Poll current state of all monitored nodes."""
        for name in self._monitored_names:
            self._poll_single_node(name)

        # Publish summary after polling
        self._publish_state_summary()

    def _poll_single_node(self, node_name: str):
        """Poll state of a single node."""
        client = self._get_state_clients.get(node_name)
        if not client:
            return

        if not client.wait_for_service(timeout_sec=0.5):
            with self._lock:
                if node_name in self._node_states:
                    self._node_states[node_name].current_state = State.PRIMARY_STATE_UNKNOWN
                    self._node_states[node_name].state_label = "unavailable"
            return

        request = GetState.Request()
        future = client.call_async(request)

        # Non-blocking wait
        future.add_done_callback(
            lambda f, n=node_name: self._on_state_response(n, f)
        )

    def _on_state_response(self, node_name: str, future):
        """Handle GetState response."""
        try:
            result = future.result()
            with self._lock:
                if node_name in self._node_states:
                    record = self._node_states[node_name]
                    record.current_state = result.current_state.id
                    record.state_label = result.current_state.label
                    record.last_update = time.time()
        except Exception as e:
            self.get_logger().debug(f'Failed to get state for {node_name}: {e}')
            with self._lock:
                if node_name in self._node_states:
                    self._node_states[node_name].state_label = "error"

    def _publish_state_summary(self):
        """Publish summary of all node states."""
        with self._lock:
            summary = {
                'timestamp': time.time(),
                'nodes': {}
            }

            active_count = 0
            inactive_count = 0
            error_count = 0
            unknown_count = 0

            for name, record in self._node_states.items():
                summary['nodes'][name] = {
                    'state': record.state_label,
                    'state_id': record.current_state,
                    'transitions': record.transition_count,
                    'errors': record.error_count,
                    'last_update': record.last_update
                }

                if record.current_state == State.PRIMARY_STATE_ACTIVE:
                    active_count += 1
                elif record.current_state == State.PRIMARY_STATE_INACTIVE:
                    inactive_count += 1
                elif record.current_state == State.PRIMARY_STATE_UNKNOWN:
                    unknown_count += 1
                elif record.state_label in ['error', 'unavailable']:
                    error_count += 1

            summary['summary'] = {
                'active': active_count,
                'inactive': inactive_count,
                'error': error_count,
                'unknown': unknown_count,
                'total': len(self._node_states)
            }

        msg = String()
        msg.data = json.dumps(summary)
        self._state_summary_pub.publish(msg)

    def _publish_diagnostics(self):
        """Publish diagnostic information."""
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        with self._lock:
            for name, record in self._node_states.items():
                status = DiagnosticStatus()
                status.name = f'lifecycle/{name}'
                status.hardware_id = f'{self._namespace}/{name}'

                # Determine status level
                if record.current_state == State.PRIMARY_STATE_ACTIVE:
                    status.level = DiagnosticStatus.OK
                    status.message = 'Node active'
                elif record.current_state == State.PRIMARY_STATE_INACTIVE:
                    status.level = DiagnosticStatus.OK
                    status.message = 'Node inactive (configured)'
                elif record.current_state == State.PRIMARY_STATE_UNCONFIGURED:
                    status.level = DiagnosticStatus.WARN
                    status.message = 'Node unconfigured'
                elif record.state_label in ['unavailable', 'error']:
                    status.level = DiagnosticStatus.ERROR
                    status.message = f'Node {record.state_label}'
                else:
                    status.level = DiagnosticStatus.STALE
                    status.message = 'Unknown state'

                # Add key-value pairs
                status.values = [
                    KeyValue(key='state', value=record.state_label),
                    KeyValue(key='state_id', value=str(record.current_state)),
                    KeyValue(key='transitions', value=str(record.transition_count)),
                    KeyValue(key='errors', value=str(record.error_count)),
                    KeyValue(key='last_update', value=str(record.last_update)),
                ]

                if record.last_error:
                    status.values.append(
                        KeyValue(key='last_error', value=record.last_error)
                    )

                diag_array.status.append(status)

        self._diagnostics_pub.publish(diag_array)

    def get_node_state(self, node_name: str) -> Optional[NodeStateRecord]:
        """Get current state record for a node."""
        with self._lock:
            return self._node_states.get(node_name)

    def get_all_states(self) -> Dict[str, NodeStateRecord]:
        """Get all node state records."""
        with self._lock:
            return dict(self._node_states)

    def get_state_history(self, node_name: str) -> List[Dict]:
        """Get state transition history for a node."""
        with self._lock:
            if node_name in self._node_states:
                return list(self._node_states[node_name].state_history)
            return []


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = LifecycleMonitor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
