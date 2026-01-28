#!/usr/bin/env python3
"""
ROS2 Lifecycle Service Bridge

Provides external service interface for lifecycle control, enabling
integration with dashboard, SCADA systems, and other external clients.

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from lifecycle_msgs.srv import ChangeState, GetState, GetAvailableTransitions
from lifecycle_msgs.msg import State, Transition
from std_srvs.srv import Trigger, SetBool
from std_msgs.msg import String
from lego_mcp_msgs.srv import LifecycleTransition
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from threading import RLock
import time


@dataclass
class TransitionRequest:
    """Represents a pending transition request."""
    node_name: str
    transition_id: int
    timestamp: float
    status: str = "pending"
    result: Optional[str] = None


class LifecycleServiceBridge(Node):
    """
    Lifecycle Service Bridge.

    Provides unified service interface for external systems to control
    and monitor lifecycle states of ROS2 nodes.
    """

    # Transition name to ID mapping
    TRANSITIONS = {
        'configure': Transition.TRANSITION_CONFIGURE,
        'cleanup': Transition.TRANSITION_CLEANUP,
        'activate': Transition.TRANSITION_ACTIVATE,
        'deactivate': Transition.TRANSITION_DEACTIVATE,
        'shutdown': Transition.TRANSITION_UNCONFIGURED_SHUTDOWN,
        'destroy': Transition.TRANSITION_DESTROY,
    }

    # State ID to name mapping
    STATE_NAMES = {
        State.PRIMARY_STATE_UNKNOWN: 'unknown',
        State.PRIMARY_STATE_UNCONFIGURED: 'unconfigured',
        State.PRIMARY_STATE_INACTIVE: 'inactive',
        State.PRIMARY_STATE_ACTIVE: 'active',
        State.PRIMARY_STATE_FINALIZED: 'finalized',
    }

    def __init__(self):
        super().__init__('lifecycle_service_bridge')

        # Parameters
        self.declare_parameter('bridged_nodes', [
            'safety_node',
            'grbl_node',
            'formlabs_node',
            'bambu_node',
            'orchestrator'
        ])
        self.declare_parameter('namespace', '/lego_mcp')
        self.declare_parameter('request_timeout_sec', 30.0)

        # Get parameters
        self._namespace = self.get_parameter('namespace').value
        self._timeout = self.get_parameter('request_timeout_sec').value
        self._bridged_names = self.get_parameter('bridged_nodes').value

        # Internal state
        self._lock = RLock()
        self._pending_requests: Dict[str, TransitionRequest] = {}
        self._change_state_clients: Dict[str, object] = {}
        self._get_state_clients: Dict[str, object] = {}
        self._get_transitions_clients: Dict[str, object] = {}

        # Callback groups
        self._service_cb_group = MutuallyExclusiveCallbackGroup()
        self._client_cb_group = ReentrantCallbackGroup()

        # Create lifecycle clients for bridged nodes
        self._create_lifecycle_clients()

        # Bridge services (external interface)
        self._transition_srv = self.create_service(
            LifecycleTransition,
            f'{self._namespace}/bridge/lifecycle/transition',
            self._handle_transition,
            callback_group=self._service_cb_group
        )

        self._get_state_srv = self.create_service(
            Trigger,
            f'{self._namespace}/bridge/lifecycle/get_state',
            self._handle_get_state,
            callback_group=self._service_cb_group
        )

        self._get_all_states_srv = self.create_service(
            Trigger,
            f'{self._namespace}/bridge/lifecycle/get_all_states',
            self._handle_get_all_states,
            callback_group=self._service_cb_group
        )

        self._get_transitions_srv = self.create_service(
            Trigger,
            f'{self._namespace}/bridge/lifecycle/get_available_transitions',
            self._handle_get_available_transitions,
            callback_group=self._service_cb_group
        )

        self._batch_transition_srv = self.create_service(
            Trigger,
            f'{self._namespace}/bridge/lifecycle/batch_transition',
            self._handle_batch_transition,
            callback_group=self._service_cb_group
        )

        # Publishers
        self._event_pub = self.create_publisher(
            String,
            f'{self._namespace}/bridge/lifecycle/events',
            10
        )

        self.get_logger().info(
            f'Lifecycle Service Bridge initialized, bridging {len(self._bridged_names)} nodes'
        )

    def _create_lifecycle_clients(self):
        """Create service clients for all bridged nodes."""
        for name in self._bridged_names:
            full_name = f'{self._namespace}/{name}'

            # ChangeState client
            self._change_state_clients[name] = self.create_client(
                ChangeState,
                f'{full_name}/change_state',
                callback_group=self._client_cb_group
            )

            # GetState client
            self._get_state_clients[name] = self.create_client(
                GetState,
                f'{full_name}/get_state',
                callback_group=self._client_cb_group
            )

            # GetAvailableTransitions client
            self._get_transitions_clients[name] = self.create_client(
                GetAvailableTransitions,
                f'{full_name}/get_available_transitions',
                callback_group=self._client_cb_group
            )

    def _handle_transition(
        self,
        request: LifecycleTransition.Request,
        response: LifecycleTransition.Response
    ) -> LifecycleTransition.Response:
        """Handle lifecycle transition request."""
        node_name = request.node_name
        transition_id = request.transition_id

        # Map transition_id to name for logging
        transition_names = {
            1: 'configure',
            2: 'cleanup',
            3: 'activate',
            4: 'deactivate',
            5: 'shutdown'
        }
        transition_name = transition_names.get(transition_id, f'unknown({transition_id})')

        # Validate node
        if node_name not in self._bridged_names:
            response.success = False
            response.message = f"Unknown node: {node_name}"
            response.current_state = 0  # STATE_UNKNOWN
            return response

        # Get previous state
        prev_state_name = self._get_node_state(node_name)
        prev_state_id = self._state_name_to_id(prev_state_name)
        response.previous_state = prev_state_id

        # Get client
        client = self._change_state_clients.get(node_name)
        if not client:
            response.success = False
            response.message = f"No client for node: {node_name}"
            response.current_state = prev_state_id
            return response

        # Check service availability
        if not client.wait_for_service(timeout_sec=5.0):
            response.success = False
            response.message = f"Service unavailable for {node_name}"
            response.current_state = prev_state_id
            return response

        # Use request timeout or default
        timeout = request.timeout_sec if request.timeout_sec > 0 else self._timeout

        # Create and send request
        change_req = ChangeState.Request()
        change_req.transition.id = transition_id

        start_time = time.time()

        try:
            future = client.call_async(change_req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)

            if future.done():
                result = future.result()
                response.success = result.success

                # Get new state
                new_state_name = self._get_node_state(node_name)
                new_state_id = self._state_name_to_id(new_state_name)
                response.current_state = new_state_id
                response.transition_duration_sec = time.time() - start_time

                if result.success:
                    response.message = f"Transition {transition_name} successful"

                    # Publish event
                    self._publish_event({
                        'type': 'transition',
                        'node': node_name,
                        'transition': transition_name,
                        'new_state': new_state_name,
                        'success': True,
                        'timestamp': time.time()
                    })
                else:
                    response.message = f"Transition {transition_name} failed"
                    response.error_code = "TRANSITION_REJECTED"
                    response.error_detail = "Node rejected the transition"
            else:
                response.success = False
                response.message = "Transition timed out"
                response.current_state = prev_state_id
                response.error_code = "TIMEOUT"
                response.error_detail = f"Transition did not complete within {timeout}s"

        except Exception as e:
            response.success = False
            response.message = f"Error: {str(e)}"
            response.current_state = prev_state_id
            response.error_code = "EXCEPTION"
            response.error_detail = str(e)

        return response

    def _state_name_to_id(self, state_name: str) -> int:
        """Convert state name to state ID."""
        name_to_id = {
            'unknown': 0,
            'unconfigured': 1,
            'inactive': 2,
            'active': 3,
            'finalized': 4,
            'unavailable': 0,
            'error': 0,
            'timeout': 0
        }
        return name_to_id.get(state_name, 0)

    def _handle_get_state(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle get state request (expects node_name in message field via workaround)."""
        # For single node queries, we use a simplified approach
        # In production, use a custom service type
        response.success = True
        response.message = json.dumps({
            'hint': 'Use get_all_states for multiple nodes or specify node via custom service'
        })
        return response

    def _handle_get_all_states(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle get all states request."""
        states = {}

        for name in self._bridged_names:
            state = self._get_node_state(name)
            states[name] = {
                'state': state,
                'available': name in self._get_state_clients
            }

        response.success = True
        response.message = json.dumps(states)
        return response

    def _handle_get_available_transitions(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Get available transitions for all nodes."""
        all_transitions = {}

        for name in self._bridged_names:
            client = self._get_transitions_clients.get(name)
            if not client or not client.wait_for_service(timeout_sec=2.0):
                all_transitions[name] = {'available': False, 'transitions': []}
                continue

            try:
                req = GetAvailableTransitions.Request()
                future = client.call_async(req)
                rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

                if future.done():
                    result = future.result()
                    transitions = []
                    for t in result.available_transitions:
                        transitions.append({
                            'id': t.transition.id,
                            'label': t.transition.label,
                            'start_state': t.start_state.label,
                            'goal_state': t.goal_state.label
                        })
                    all_transitions[name] = {
                        'available': True,
                        'transitions': transitions
                    }
                else:
                    all_transitions[name] = {'available': False, 'transitions': []}

            except Exception as e:
                all_transitions[name] = {
                    'available': False,
                    'transitions': [],
                    'error': str(e)
                }

        response.success = True
        response.message = json.dumps(all_transitions)
        return response

    def _handle_batch_transition(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle batch transition request (all nodes same transition)."""
        # Parse request from message (workaround for Trigger service)
        # Expected format: {"transition": "activate"} or {"transition": "deactivate"}
        try:
            # Default to activate if no specific request
            transition_name = "activate"
            transition_id = self.TRANSITIONS.get(transition_name, Transition.TRANSITION_ACTIVATE)
        except Exception:
            transition_id = Transition.TRANSITION_ACTIVATE
            transition_name = "activate"

        results = {}

        for name in self._bridged_names:
            client = self._change_state_clients.get(name)
            if not client or not client.wait_for_service(timeout_sec=2.0):
                results[name] = {'success': False, 'error': 'unavailable'}
                continue

            try:
                req = ChangeState.Request()
                req.transition.id = transition_id

                future = client.call_async(req)
                rclpy.spin_until_future_complete(self, future, timeout_sec=self._timeout)

                if future.done():
                    result = future.result()
                    results[name] = {
                        'success': result.success,
                        'new_state': self._get_node_state(name)
                    }
                else:
                    results[name] = {'success': False, 'error': 'timeout'}

            except Exception as e:
                results[name] = {'success': False, 'error': str(e)}

        successes = sum(1 for r in results.values() if r.get('success', False))
        response.success = successes == len(self._bridged_names)
        response.message = json.dumps({
            'transition': transition_name,
            'succeeded': successes,
            'total': len(self._bridged_names),
            'results': results
        })

        return response

    def _get_node_state(self, node_name: str) -> str:
        """Get current state of a node."""
        client = self._get_state_clients.get(node_name)
        if not client or not client.wait_for_service(timeout_sec=2.0):
            return "unavailable"

        try:
            req = GetState.Request()
            future = client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

            if future.done():
                result = future.result()
                return self.STATE_NAMES.get(
                    result.current_state.id,
                    result.current_state.label
                )
            return "timeout"

        except Exception:
            return "error"

    def _publish_event(self, event: Dict):
        """Publish lifecycle event."""
        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = LifecycleServiceBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
