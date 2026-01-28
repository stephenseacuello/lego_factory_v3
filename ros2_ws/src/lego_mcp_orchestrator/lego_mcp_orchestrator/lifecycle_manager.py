#!/usr/bin/env python3
"""
ROS2 Lifecycle Manager Node

Manages lifecycle state transitions for all supervised nodes in the system.
Provides coordinated startup, shutdown, and state transitions following
ISA-95 layer dependencies.

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import State, Transition
from std_srvs.srv import Trigger
from std_msgs.msg import String
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
import time


class TransitionResult(Enum):
    """Result of a lifecycle transition."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ManagedNode:
    """Represents a node managed by the lifecycle manager."""
    name: str
    namespace: str = "/lego_mcp"
    isa95_layer: int = 2  # Default to supervisory
    dependencies: List[str] = field(default_factory=list)
    current_state: int = State.PRIMARY_STATE_UNKNOWN
    last_transition_time: float = 0.0
    transition_timeout_sec: float = 30.0
    critical: bool = False


class LifecycleManager(Node):
    """
    Lifecycle Manager for coordinated node state management.

    Manages lifecycle transitions for all nodes in the system,
    ensuring proper startup order based on ISA-95 layers and
    dependency relationships.
    """

    def __init__(self):
        super().__init__('lifecycle_manager')

        # Parameters
        self.declare_parameter('managed_nodes', [
            'safety_node',
            'grbl_node',
            'formlabs_node',
            'bambu_node',
            'orchestrator'
        ])
        self.declare_parameter('namespace', '/lego_mcp')
        self.declare_parameter('transition_timeout_sec', 30.0)
        self.declare_parameter('startup_delay_between_layers_sec', 2.0)
        self.declare_parameter('auto_configure', True)
        self.declare_parameter('auto_activate', True)

        # Get parameters
        self._namespace = self.get_parameter('namespace').value
        self._timeout = self.get_parameter('transition_timeout_sec').value
        self._layer_delay = self.get_parameter('startup_delay_between_layers_sec').value
        self._auto_configure = self.get_parameter('auto_configure').value
        self._auto_activate = self.get_parameter('auto_activate').value

        # Internal state
        self._lock = RLock()
        self._managed_nodes: Dict[str, ManagedNode] = {}
        self._change_state_clients: Dict[str, object] = {}
        self._get_state_clients: Dict[str, object] = {}

        # Callback groups
        self._service_cb_group = MutuallyExclusiveCallbackGroup()
        self._client_cb_group = ReentrantCallbackGroup()

        # Initialize managed nodes with ISA-95 layer assignments
        self._initialize_managed_nodes()

        # Create service clients for each managed node
        self._create_lifecycle_clients()

        # Services
        self._configure_all_srv = self.create_service(
            Trigger,
            f'{self._namespace}/lifecycle_manager/configure_all',
            self._handle_configure_all,
            callback_group=self._service_cb_group
        )

        self._activate_all_srv = self.create_service(
            Trigger,
            f'{self._namespace}/lifecycle_manager/activate_all',
            self._handle_activate_all,
            callback_group=self._service_cb_group
        )

        self._deactivate_all_srv = self.create_service(
            Trigger,
            f'{self._namespace}/lifecycle_manager/deactivate_all',
            self._handle_deactivate_all,
            callback_group=self._service_cb_group
        )

        self._shutdown_all_srv = self.create_service(
            Trigger,
            f'{self._namespace}/lifecycle_manager/shutdown_all',
            self._handle_shutdown_all,
            callback_group=self._service_cb_group
        )

        self._get_states_srv = self.create_service(
            Trigger,
            f'{self._namespace}/lifecycle_manager/get_states',
            self._handle_get_states,
            callback_group=self._service_cb_group
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            f'{self._namespace}/lifecycle_manager/status',
            10
        )

        # Status timer
        self._status_timer = self.create_timer(
            5.0,
            self._publish_status
        )

        self.get_logger().info('Lifecycle Manager initialized')

        # Auto-startup if configured
        if self._auto_configure:
            self.create_timer(2.0, self._auto_startup, callback_group=self._service_cb_group)

    def _initialize_managed_nodes(self):
        """Initialize managed node configurations with ISA-95 layers."""
        node_configs = {
            # Layer 1 - Safety (highest priority, starts first)
            'safety_node': ManagedNode(
                name='safety_node',
                namespace=self._namespace,
                isa95_layer=1,
                dependencies=[],
                critical=True,
                transition_timeout_sec=10.0
            ),
            # Layer 0 - Field devices (equipment)
            'grbl_node': ManagedNode(
                name='grbl_node',
                namespace=self._namespace,
                isa95_layer=0,
                dependencies=['safety_node'],
                critical=False,
                transition_timeout_sec=30.0
            ),
            'formlabs_node': ManagedNode(
                name='formlabs_node',
                namespace=self._namespace,
                isa95_layer=0,
                dependencies=['safety_node'],
                critical=False,
                transition_timeout_sec=60.0
            ),
            'bambu_node': ManagedNode(
                name='bambu_node',
                namespace=self._namespace,
                isa95_layer=0,
                dependencies=['safety_node'],
                critical=False,
                transition_timeout_sec=45.0
            ),
            # Layer 2 - Supervisory
            'orchestrator': ManagedNode(
                name='orchestrator',
                namespace=self._namespace,
                isa95_layer=2,
                dependencies=['safety_node', 'grbl_node', 'formlabs_node', 'bambu_node'],
                critical=True,
                transition_timeout_sec=30.0
            ),
        }

        managed_names = self.get_parameter('managed_nodes').value
        for name in managed_names:
            if name in node_configs:
                self._managed_nodes[name] = node_configs[name]
            else:
                # Create default config for unknown nodes
                self._managed_nodes[name] = ManagedNode(
                    name=name,
                    namespace=self._namespace
                )

    def _create_lifecycle_clients(self):
        """Create lifecycle service clients for all managed nodes."""
        for name, node in self._managed_nodes.items():
            full_name = f'{node.namespace}/{name}'

            # Change state client
            self._change_state_clients[name] = self.create_client(
                ChangeState,
                f'{full_name}/change_state',
                callback_group=self._client_cb_group
            )

            # Get state client
            self._get_state_clients[name] = self.create_client(
                GetState,
                f'{full_name}/get_state',
                callback_group=self._client_cb_group
            )

    def _get_nodes_by_layer(self) -> Dict[int, List[str]]:
        """Get nodes grouped by ISA-95 layer."""
        layers: Dict[int, List[str]] = {}
        for name, node in self._managed_nodes.items():
            if node.isa95_layer not in layers:
                layers[node.isa95_layer] = []
            layers[node.isa95_layer].append(name)
        return layers

    def _get_startup_order(self) -> List[str]:
        """Get nodes in ISA-95 compliant startup order."""
        # Layer 1 (Safety) first, then Layer 0 (Field), then Layer 2 (Supervisory)
        order = []
        layers = self._get_nodes_by_layer()

        # Safety first (L1)
        if 1 in layers:
            order.extend(layers[1])
        # Equipment second (L0)
        if 0 in layers:
            order.extend(layers[0])
        # Supervisory last (L2)
        if 2 in layers:
            order.extend(layers[2])
        # Any other layers
        for layer in sorted(layers.keys()):
            if layer not in [0, 1, 2]:
                order.extend(layers[layer])

        return order

    def _get_shutdown_order(self) -> List[str]:
        """Get nodes in reverse ISA-95 order for shutdown."""
        return list(reversed(self._get_startup_order()))

    async def _change_node_state(
        self,
        node_name: str,
        transition_id: int
    ) -> Tuple[TransitionResult, str]:
        """Change a single node's lifecycle state."""
        if node_name not in self._change_state_clients:
            return TransitionResult.FAILURE, f"Unknown node: {node_name}"

        client = self._change_state_clients[node_name]
        node = self._managed_nodes[node_name]

        # Wait for service
        if not client.wait_for_service(timeout_sec=5.0):
            return TransitionResult.TIMEOUT, f"Service not available for {node_name}"

        # Create request
        request = ChangeState.Request()
        request.transition.id = transition_id

        try:
            # Call service
            future = client.call_async(request)

            # Wait with timeout
            start_time = time.time()
            while not future.done():
                if time.time() - start_time > node.transition_timeout_sec:
                    return TransitionResult.TIMEOUT, f"Transition timeout for {node_name}"
                time.sleep(0.1)

            response = future.result()

            if response.success:
                node.last_transition_time = time.time()
                return TransitionResult.SUCCESS, f"Transition successful for {node_name}"
            else:
                return TransitionResult.FAILURE, f"Transition failed for {node_name}"

        except Exception as e:
            return TransitionResult.FAILURE, f"Error transitioning {node_name}: {str(e)}"

    async def _get_node_state(self, node_name: str) -> int:
        """Get current state of a node."""
        if node_name not in self._get_state_clients:
            return State.PRIMARY_STATE_UNKNOWN

        client = self._get_state_clients[node_name]

        if not client.wait_for_service(timeout_sec=2.0):
            return State.PRIMARY_STATE_UNKNOWN

        try:
            request = GetState.Request()
            future = client.call_async(request)

            start_time = time.time()
            while not future.done():
                if time.time() - start_time > 5.0:
                    return State.PRIMARY_STATE_UNKNOWN
                time.sleep(0.1)

            response = future.result()
            return response.current_state.id

        except Exception:
            return State.PRIMARY_STATE_UNKNOWN

    def _auto_startup(self):
        """Auto-configure and activate all nodes on startup."""
        self.get_logger().info('Auto-startup: Configuring all nodes...')

        # This is called once then cancels itself
        if hasattr(self, '_auto_startup_done'):
            return
        self._auto_startup_done = True

        # Configure all
        req = Trigger.Request()
        resp = Trigger.Response()
        self._handle_configure_all(req, resp)

        if self._auto_activate and resp.success:
            time.sleep(self._layer_delay)
            self.get_logger().info('Auto-startup: Activating all nodes...')
            self._handle_activate_all(req, resp)

    def _handle_configure_all(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle configure all nodes request."""
        results = []
        startup_order = self._get_startup_order()
        current_layer = -1

        for node_name in startup_order:
            node = self._managed_nodes[node_name]

            # Add delay between layers
            if node.isa95_layer != current_layer:
                if current_layer != -1:
                    time.sleep(self._layer_delay)
                current_layer = node.isa95_layer
                self.get_logger().info(f'Configuring ISA-95 Layer {current_layer} nodes...')

            # Check dependencies
            deps_met = True
            for dep in node.dependencies:
                if dep in self._managed_nodes:
                    dep_state = State.PRIMARY_STATE_UNKNOWN
                    # In synchronous context, we track last known state
                    if self._managed_nodes[dep].current_state < State.PRIMARY_STATE_INACTIVE:
                        deps_met = False
                        break

            if not deps_met:
                results.append((node_name, TransitionResult.SKIPPED, "Dependencies not met"))
                continue

            # Attempt configure transition
            client = self._change_state_clients.get(node_name)
            if client and client.wait_for_service(timeout_sec=2.0):
                req = ChangeState.Request()
                req.transition.id = Transition.TRANSITION_CONFIGURE

                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=node.transition_timeout_sec)

                    if future.done() and future.result().success:
                        node.current_state = State.PRIMARY_STATE_INACTIVE
                        results.append((node_name, TransitionResult.SUCCESS, "Configured"))
                        self.get_logger().info(f'Configured {node_name}')
                    else:
                        results.append((node_name, TransitionResult.FAILURE, "Configure failed"))
                except Exception as e:
                    results.append((node_name, TransitionResult.FAILURE, str(e)))
            else:
                results.append((node_name, TransitionResult.TIMEOUT, "Service unavailable"))

        # Build response
        successes = sum(1 for _, r, _ in results if r == TransitionResult.SUCCESS)
        response.success = successes == len(results)
        response.message = json.dumps({
            'configured': successes,
            'total': len(results),
            'details': [(n, r.value, m) for n, r, m in results]
        })

        return response

    def _handle_activate_all(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle activate all nodes request."""
        results = []
        startup_order = self._get_startup_order()
        current_layer = -1

        for node_name in startup_order:
            node = self._managed_nodes[node_name]

            # Add delay between layers
            if node.isa95_layer != current_layer:
                if current_layer != -1:
                    time.sleep(self._layer_delay)
                current_layer = node.isa95_layer
                self.get_logger().info(f'Activating ISA-95 Layer {current_layer} nodes...')

            # Attempt activate transition
            client = self._change_state_clients.get(node_name)
            if client and client.wait_for_service(timeout_sec=2.0):
                req = ChangeState.Request()
                req.transition.id = Transition.TRANSITION_ACTIVATE

                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=node.transition_timeout_sec)

                    if future.done() and future.result().success:
                        node.current_state = State.PRIMARY_STATE_ACTIVE
                        results.append((node_name, TransitionResult.SUCCESS, "Activated"))
                        self.get_logger().info(f'Activated {node_name}')
                    else:
                        results.append((node_name, TransitionResult.FAILURE, "Activate failed"))
                except Exception as e:
                    results.append((node_name, TransitionResult.FAILURE, str(e)))
            else:
                results.append((node_name, TransitionResult.TIMEOUT, "Service unavailable"))

        successes = sum(1 for _, r, _ in results if r == TransitionResult.SUCCESS)
        response.success = successes == len(results)
        response.message = json.dumps({
            'activated': successes,
            'total': len(results),
            'details': [(n, r.value, m) for n, r, m in results]
        })

        return response

    def _handle_deactivate_all(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle deactivate all nodes request (reverse order)."""
        results = []
        shutdown_order = self._get_shutdown_order()

        for node_name in shutdown_order:
            node = self._managed_nodes[node_name]

            client = self._change_state_clients.get(node_name)
            if client and client.wait_for_service(timeout_sec=2.0):
                req = ChangeState.Request()
                req.transition.id = Transition.TRANSITION_DEACTIVATE

                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=node.transition_timeout_sec)

                    if future.done() and future.result().success:
                        node.current_state = State.PRIMARY_STATE_INACTIVE
                        results.append((node_name, TransitionResult.SUCCESS, "Deactivated"))
                    else:
                        results.append((node_name, TransitionResult.FAILURE, "Deactivate failed"))
                except Exception as e:
                    results.append((node_name, TransitionResult.FAILURE, str(e)))
            else:
                results.append((node_name, TransitionResult.TIMEOUT, "Service unavailable"))

        successes = sum(1 for _, r, _ in results if r == TransitionResult.SUCCESS)
        response.success = successes == len(results)
        response.message = json.dumps({
            'deactivated': successes,
            'total': len(results),
            'details': [(n, r.value, m) for n, r, m in results]
        })

        return response

    def _handle_shutdown_all(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Handle shutdown all nodes request."""
        # First deactivate
        self._handle_deactivate_all(request, response)

        results = []
        shutdown_order = self._get_shutdown_order()

        for node_name in shutdown_order:
            node = self._managed_nodes[node_name]

            client = self._change_state_clients.get(node_name)
            if client and client.wait_for_service(timeout_sec=2.0):
                # Cleanup first
                req = ChangeState.Request()
                req.transition.id = Transition.TRANSITION_CLEANUP

                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
                except Exception:
                    pass

                # Then shutdown
                req.transition.id = Transition.TRANSITION_UNCONFIGURED_SHUTDOWN
                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

                    if future.done():
                        node.current_state = State.PRIMARY_STATE_FINALIZED
                        results.append((node_name, TransitionResult.SUCCESS, "Shutdown"))
                except Exception as e:
                    results.append((node_name, TransitionResult.FAILURE, str(e)))

        successes = sum(1 for _, r, _ in results if r == TransitionResult.SUCCESS)
        response.success = successes == len(results)
        response.message = json.dumps({
            'shutdown': successes,
            'total': len(results)
        })

        return response

    def _handle_get_states(
        self,
        request: Trigger.Request,
        response: Trigger.Response
    ) -> Trigger.Response:
        """Get states of all managed nodes."""
        states = {}

        for node_name in self._managed_nodes:
            client = self._get_state_clients.get(node_name)
            if client and client.wait_for_service(timeout_sec=1.0):
                req = GetState.Request()
                try:
                    future = client.call_async(req)
                    rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

                    if future.done():
                        result = future.result()
                        states[node_name] = {
                            'state_id': result.current_state.id,
                            'state_label': result.current_state.label
                        }
                    else:
                        states[node_name] = {'state_id': -1, 'state_label': 'timeout'}
                except Exception:
                    states[node_name] = {'state_id': -1, 'state_label': 'error'}
            else:
                states[node_name] = {'state_id': -1, 'state_label': 'unavailable'}

        response.success = True
        response.message = json.dumps(states)
        return response

    def _publish_status(self):
        """Publish current status of all managed nodes."""
        status = {
            'timestamp': self.get_clock().now().nanoseconds / 1e9,
            'nodes': {}
        }

        for name, node in self._managed_nodes.items():
            status['nodes'][name] = {
                'state': node.current_state,
                'layer': node.isa95_layer,
                'critical': node.critical,
                'last_transition': node.last_transition_time
            }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = LifecycleManager()

    executor = MultiThreadedExecutor()
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
