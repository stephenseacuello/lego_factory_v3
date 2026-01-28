#!/usr/bin/env python3
"""
OTP-style Supervisor Node for LEGO MCP ROS2 system.

Implements Erlang/OTP supervision patterns with restart strategies:
- ONE_FOR_ONE: Only restart the failed child
- ONE_FOR_ALL: Restart all children if one fails
- REST_FOR_ONE: Restart the failed child and all children started after it

Features:
- Heartbeat monitoring for child nodes
- Configurable max_restarts and restart_window
- Dependency graph support between nodes
- Lifecycle node integration
- Graceful shutdown handling
"""

import subprocess
import signal
import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger, SetBool
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from lifecycle_msgs.srv import GetState, ChangeState
from lifecycle_msgs.msg import State, Transition


class RestartStrategy(Enum):
    """OTP-style restart strategies."""
    ONE_FOR_ONE = auto()   # Only restart the failed child
    ONE_FOR_ALL = auto()   # Restart all children if one fails
    REST_FOR_ONE = auto()  # Restart failed child and all children started after it


class RestartType(Enum):
    """Child restart behavior specification."""
    PERMANENT = auto()  # Always restart
    TEMPORARY = auto()  # Never restart
    TRANSIENT = auto()  # Restart only on abnormal termination


class ChildState(Enum):
    """State of a supervised child process."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    FAILED = auto()
    RESTARTING = auto()


@dataclass
class ChildSpec:
    """
    Specification for a supervised child node.

    Attributes:
        child_id: Unique identifier for the child
        node_name: ROS2 node name
        package: ROS2 package containing the node
        executable: Node executable name
        namespace: Optional ROS2 namespace
        parameters: Node parameters
        arguments: Additional command line arguments
        restart_type: How to handle restarts (PERMANENT, TEMPORARY, TRANSIENT)
        shutdown_timeout: Seconds to wait for graceful shutdown
        dependencies: List of child_ids this node depends on
        lifecycle_managed: Whether this is a lifecycle node
        start_delay: Delay in seconds before starting after dependencies are ready
    """
    child_id: str
    node_name: str
    package: str
    executable: str
    namespace: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    arguments: List[str] = field(default_factory=list)
    restart_type: RestartType = RestartType.PERMANENT
    shutdown_timeout: float = 5.0
    dependencies: List[str] = field(default_factory=list)
    lifecycle_managed: bool = False
    start_delay: float = 0.0


@dataclass
class ChildProcess:
    """Runtime state of a supervised child process."""
    spec: ChildSpec
    state: ChildState = ChildState.STOPPED
    process: Optional[subprocess.Popen] = None
    restart_count: int = 0
    last_restart_time: float = 0.0
    last_heartbeat: float = 0.0
    exit_code: Optional[int] = None
    start_order: int = 0


class SupervisorNode(Node):
    """
    OTP-style supervisor node for ROS2.

    Monitors and manages child nodes with configurable restart strategies,
    dependency management, and lifecycle integration.
    """

    def __init__(
        self,
        node_name: str = "lego_mcp_supervisor",
        strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE,
        max_restarts: int = 3,
        restart_window: float = 60.0,
        heartbeat_timeout: float = 5.0,
        check_interval: float = 1.0,
    ):
        """
        Initialize the supervisor node.

        Args:
            node_name: Name of the supervisor node
            strategy: Restart strategy to use
            max_restarts: Maximum number of restarts within the restart window
            restart_window: Time window in seconds for counting restarts
            heartbeat_timeout: Seconds without heartbeat before considering node dead
            check_interval: Interval between health checks
        """
        super().__init__(node_name)

        self.strategy = strategy
        self.max_restarts = max_restarts
        self.restart_window = restart_window
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval

        # Child management
        self._children: Dict[str, ChildProcess] = {}
        self._start_order: List[str] = []
        self._lock = threading.RLock()
        self._shutdown_requested = False
        self._restart_history: Dict[str, deque] = {}  # child_id -> timestamps

        # Callback groups for concurrent execution
        self._callback_group = ReentrantCallbackGroup()

        # QoS profile for heartbeats
        self._heartbeat_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=10
        )

        # Declare parameters
        self.declare_parameter("strategy", self.strategy.name)
        self.declare_parameter("max_restarts", self.max_restarts)
        self.declare_parameter("restart_window", self.restart_window)
        self.declare_parameter("heartbeat_timeout", self.heartbeat_timeout)
        self.declare_parameter("check_interval", self.check_interval)

        # Load parameters
        self._load_parameters()

        # Subscriptions for heartbeats
        self._heartbeat_sub = self.create_subscription(
            String,
            "~/heartbeats",
            self._heartbeat_callback,
            self._heartbeat_qos,
            callback_group=self._callback_group
        )

        # Publishers
        self._status_pub = self.create_publisher(
            DiagnosticArray,
            "~/status",
            10
        )

        self._event_pub = self.create_publisher(
            String,
            "~/events",
            10
        )

        # Services
        self._start_child_srv = self.create_service(
            Trigger,
            "~/start_all",
            self._start_all_callback,
            callback_group=self._callback_group
        )

        self._stop_child_srv = self.create_service(
            Trigger,
            "~/stop_all",
            self._stop_all_callback,
            callback_group=self._callback_group
        )

        self._restart_child_srv = self.create_service(
            Trigger,
            "~/restart_all",
            self._restart_all_callback,
            callback_group=self._callback_group
        )

        # Health check timer
        self._check_timer = self.create_timer(
            self.check_interval,
            self._health_check_callback,
            callback_group=self._callback_group
        )

        # Status publish timer
        self._status_timer = self.create_timer(
            2.0,
            self._publish_status,
            callback_group=self._callback_group
        )

        self.get_logger().info(
            f"Supervisor initialized with strategy={self.strategy.name}, "
            f"max_restarts={self.max_restarts}, restart_window={self.restart_window}s"
        )

    def _load_parameters(self):
        """Load parameters from ROS2 parameter server."""
        strategy_name = self.get_parameter("strategy").value
        try:
            self.strategy = RestartStrategy[strategy_name]
        except KeyError:
            self.get_logger().warn(f"Unknown strategy '{strategy_name}', using ONE_FOR_ONE")
            self.strategy = RestartStrategy.ONE_FOR_ONE

        self.max_restarts = self.get_parameter("max_restarts").value
        self.restart_window = self.get_parameter("restart_window").value
        self.heartbeat_timeout = self.get_parameter("heartbeat_timeout").value
        self.check_interval = self.get_parameter("check_interval").value

    def add_child(self, spec: ChildSpec) -> bool:
        """
        Add a child specification to the supervisor.

        Args:
            spec: Child specification

        Returns:
            True if added successfully, False if child_id already exists
        """
        with self._lock:
            if spec.child_id in self._children:
                self.get_logger().warn(f"Child '{spec.child_id}' already exists")
                return False

            # Validate dependencies
            for dep in spec.dependencies:
                if dep not in self._children and dep != spec.child_id:
                    self.get_logger().warn(
                        f"Dependency '{dep}' for child '{spec.child_id}' not found"
                    )

            child = ChildProcess(
                spec=spec,
                state=ChildState.STOPPED,
                start_order=len(self._start_order)
            )
            self._children[spec.child_id] = child
            self._start_order.append(spec.child_id)
            self._restart_history[spec.child_id] = deque(maxlen=self.max_restarts + 1)

            self.get_logger().info(f"Added child '{spec.child_id}' to supervision tree")
            return True

    def remove_child(self, child_id: str) -> bool:
        """
        Remove a child from supervision (stops it first if running).

        Args:
            child_id: ID of the child to remove

        Returns:
            True if removed successfully
        """
        with self._lock:
            if child_id not in self._children:
                return False

            # Check if other children depend on this one
            dependents = self._get_dependents(child_id)
            if dependents:
                self.get_logger().warn(
                    f"Cannot remove '{child_id}': depended on by {dependents}"
                )
                return False

            self._stop_child(child_id)
            del self._children[child_id]
            self._start_order.remove(child_id)
            del self._restart_history[child_id]

            self.get_logger().info(f"Removed child '{child_id}' from supervision tree")
            return True

    def start_children(self) -> bool:
        """Start all children in dependency order."""
        with self._lock:
            ordered = self._get_start_order()
            for child_id in ordered:
                if not self._start_child(child_id):
                    self.get_logger().error(
                        f"Failed to start child '{child_id}', aborting start sequence"
                    )
                    return False
            return True

    def stop_children(self):
        """Stop all children in reverse dependency order."""
        with self._lock:
            ordered = self._get_start_order()
            for child_id in reversed(ordered):
                self._stop_child(child_id)

    def _get_start_order(self) -> List[str]:
        """
        Get the order in which children should be started based on dependencies.
        Uses topological sort.
        """
        # Build dependency graph
        visited = set()
        result = []

        def visit(child_id: str, path: Set[str]):
            if child_id in path:
                raise ValueError(f"Circular dependency detected involving '{child_id}'")
            if child_id in visited:
                return

            path.add(child_id)
            child = self._children.get(child_id)
            if child:
                for dep in child.spec.dependencies:
                    if dep in self._children:
                        visit(dep, path.copy())

            visited.add(child_id)
            result.append(child_id)

        for child_id in self._start_order:
            if child_id not in visited:
                visit(child_id, set())

        return result

    def _get_dependents(self, child_id: str) -> List[str]:
        """Get all children that depend on the given child."""
        dependents = []
        for cid, child in self._children.items():
            if child_id in child.spec.dependencies:
                dependents.append(cid)
        return dependents

    def _start_child(self, child_id: str) -> bool:
        """Start a single child process."""
        child = self._children.get(child_id)
        if not child:
            return False

        if child.state in (ChildState.RUNNING, ChildState.STARTING):
            return True

        # Check dependencies
        for dep_id in child.spec.dependencies:
            dep = self._children.get(dep_id)
            if not dep or dep.state != ChildState.RUNNING:
                self.get_logger().warn(
                    f"Cannot start '{child_id}': dependency '{dep_id}' not running"
                )
                return False

        # Apply start delay
        if child.spec.start_delay > 0:
            self.get_logger().debug(
                f"Waiting {child.spec.start_delay}s before starting '{child_id}'"
            )
            time.sleep(child.spec.start_delay)

        child.state = ChildState.STARTING

        try:
            # Build command
            cmd = ["ros2", "run", child.spec.package, child.spec.executable]

            # Add namespace
            if child.spec.namespace:
                cmd.extend(["--ros-args", "-r", f"__ns:={child.spec.namespace}"])

            # Add node name remapping
            cmd.extend(["--ros-args", "-r", f"__node:={child.spec.node_name}"])

            # Add parameters
            for key, value in child.spec.parameters.items():
                cmd.extend(["-p", f"{key}:={value}"])

            # Add additional arguments
            cmd.extend(child.spec.arguments)

            self.get_logger().info(f"Starting child '{child_id}': {' '.join(cmd)}")

            # Start process
            child.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )

            child.state = ChildState.RUNNING
            child.last_heartbeat = time.time()
            child.exit_code = None

            self._publish_event(f"STARTED:{child_id}")

            # Handle lifecycle nodes
            if child.spec.lifecycle_managed:
                self._configure_lifecycle_node(child_id)

            return True

        except Exception as e:
            self.get_logger().error(f"Failed to start '{child_id}': {e}")
            child.state = ChildState.FAILED
            return False

    def _stop_child(self, child_id: str, graceful: bool = True):
        """Stop a single child process."""
        child = self._children.get(child_id)
        if not child or child.state == ChildState.STOPPED:
            return

        child.state = ChildState.STOPPING

        if child.process and child.process.poll() is None:
            try:
                if graceful:
                    # Try SIGTERM first
                    child.process.terminate()
                    try:
                        child.process.wait(timeout=child.spec.shutdown_timeout)
                    except subprocess.TimeoutExpired:
                        self.get_logger().warn(
                            f"Child '{child_id}' did not terminate gracefully, sending SIGKILL"
                        )
                        child.process.kill()
                        child.process.wait(timeout=1.0)
                else:
                    child.process.kill()
                    child.process.wait(timeout=1.0)

            except Exception as e:
                self.get_logger().error(f"Error stopping '{child_id}': {e}")

        child.exit_code = child.process.returncode if child.process else None
        child.state = ChildState.STOPPED
        child.process = None

        self._publish_event(f"STOPPED:{child_id}")
        self.get_logger().info(f"Stopped child '{child_id}'")

    def _restart_child(self, child_id: str) -> bool:
        """Restart a single child process."""
        child = self._children.get(child_id)
        if not child:
            return False

        # Check restart limits
        now = time.time()
        history = self._restart_history[child_id]

        # Clean old restart timestamps
        while history and (now - history[0]) > self.restart_window:
            history.popleft()

        if len(history) >= self.max_restarts:
            self.get_logger().error(
                f"Child '{child_id}' exceeded max_restarts ({self.max_restarts}) "
                f"within {self.restart_window}s window"
            )
            child.state = ChildState.FAILED
            self._publish_event(f"MAX_RESTARTS_EXCEEDED:{child_id}")
            return False

        # Record restart
        history.append(now)
        child.restart_count += 1
        child.last_restart_time = now
        child.state = ChildState.RESTARTING

        self.get_logger().info(
            f"Restarting child '{child_id}' (attempt {child.restart_count})"
        )

        self._stop_child(child_id, graceful=True)

        # Small delay before restart
        time.sleep(0.5)

        return self._start_child(child_id)

    def _handle_child_failure(self, child_id: str):
        """
        Handle a child failure according to the restart strategy.

        Args:
            child_id: ID of the failed child
        """
        child = self._children.get(child_id)
        if not child:
            return

        self._publish_event(f"FAILED:{child_id}")
        self.get_logger().warn(f"Child '{child_id}' failed")

        # Check restart type
        if child.spec.restart_type == RestartType.TEMPORARY:
            self.get_logger().info(
                f"Child '{child_id}' is TEMPORARY, not restarting"
            )
            child.state = ChildState.STOPPED
            return

        if child.spec.restart_type == RestartType.TRANSIENT:
            if child.exit_code == 0:
                self.get_logger().info(
                    f"Child '{child_id}' is TRANSIENT with exit code 0, not restarting"
                )
                child.state = ChildState.STOPPED
                return

        # Apply restart strategy
        if self.strategy == RestartStrategy.ONE_FOR_ONE:
            self._restart_child(child_id)

        elif self.strategy == RestartStrategy.ONE_FOR_ALL:
            # Stop all children in reverse order
            ordered = self._get_start_order()
            for cid in reversed(ordered):
                if self._children[cid].state in (ChildState.RUNNING, ChildState.STARTING):
                    self._stop_child(cid)

            # Restart all children in order
            for cid in ordered:
                if not self._restart_child(cid):
                    self.get_logger().error(
                        f"Failed to restart '{cid}' in ONE_FOR_ALL strategy"
                    )
                    break

        elif self.strategy == RestartStrategy.REST_FOR_ONE:
            # Get children started after the failed one
            ordered = self._get_start_order()
            try:
                failed_index = ordered.index(child_id)
            except ValueError:
                failed_index = 0

            # Stop failed child and all children after it
            for cid in reversed(ordered[failed_index:]):
                if self._children[cid].state in (ChildState.RUNNING, ChildState.STARTING):
                    self._stop_child(cid)

            # Restart them in order
            for cid in ordered[failed_index:]:
                if not self._restart_child(cid):
                    self.get_logger().error(
                        f"Failed to restart '{cid}' in REST_FOR_ONE strategy"
                    )
                    break

    def _configure_lifecycle_node(self, child_id: str):
        """Configure a lifecycle node through its lifecycle services."""
        child = self._children.get(child_id)
        if not child or not child.spec.lifecycle_managed:
            return

        node_name = child.spec.node_name
        namespace = child.spec.namespace or ""

        # Create client for lifecycle state change
        client_name = f"{namespace}/{node_name}/change_state".lstrip("/")

        try:
            client = self.create_client(ChangeState, client_name)
            if not client.wait_for_service(timeout_sec=5.0):
                self.get_logger().warn(
                    f"Lifecycle service for '{child_id}' not available"
                )
                return

            # Configure the node
            req = ChangeState.Request()
            req.transition.id = Transition.TRANSITION_CONFIGURE

            future = client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

            if future.result() and future.result().success:
                self.get_logger().info(f"Configured lifecycle node '{child_id}'")

                # Activate the node
                req.transition.id = Transition.TRANSITION_ACTIVATE
                future = client.call_async(req)
                rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

                if future.result() and future.result().success:
                    self.get_logger().info(f"Activated lifecycle node '{child_id}'")
                else:
                    self.get_logger().warn(
                        f"Failed to activate lifecycle node '{child_id}'"
                    )
            else:
                self.get_logger().warn(
                    f"Failed to configure lifecycle node '{child_id}'"
                )

        except Exception as e:
            self.get_logger().error(
                f"Error managing lifecycle node '{child_id}': {e}"
            )
        finally:
            self.destroy_client(client)

    def _heartbeat_callback(self, msg: String):
        """Handle heartbeat messages from child nodes."""
        child_id = msg.data

        with self._lock:
            if child_id in self._children:
                self._children[child_id].last_heartbeat = time.time()

    def _health_check_callback(self):
        """Periodic health check of all children."""
        if self._shutdown_requested:
            return

        now = time.time()

        with self._lock:
            for child_id, child in list(self._children.items()):
                if child.state != ChildState.RUNNING:
                    continue

                # Check process status
                if child.process and child.process.poll() is not None:
                    child.exit_code = child.process.returncode
                    self.get_logger().warn(
                        f"Child '{child_id}' process exited with code {child.exit_code}"
                    )
                    self._handle_child_failure(child_id)
                    continue

                # Check heartbeat timeout
                if (now - child.last_heartbeat) > self.heartbeat_timeout:
                    self.get_logger().warn(
                        f"Child '{child_id}' heartbeat timeout "
                        f"({now - child.last_heartbeat:.1f}s > {self.heartbeat_timeout}s)"
                    )
                    self._handle_child_failure(child_id)

    def _publish_status(self):
        """Publish diagnostic status of all children."""
        diag_msg = DiagnosticArray()
        diag_msg.header.stamp = self.get_clock().now().to_msg()

        # Overall supervisor status
        supervisor_status = DiagnosticStatus()
        supervisor_status.name = self.get_name()
        supervisor_status.hardware_id = "supervisor"

        running_count = sum(
            1 for c in self._children.values() if c.state == ChildState.RUNNING
        )
        total_count = len(self._children)

        if running_count == total_count and total_count > 0:
            supervisor_status.level = DiagnosticStatus.OK
            supervisor_status.message = f"All {total_count} children running"
        elif running_count > 0:
            supervisor_status.level = DiagnosticStatus.WARN
            supervisor_status.message = f"{running_count}/{total_count} children running"
        else:
            supervisor_status.level = DiagnosticStatus.ERROR
            supervisor_status.message = "No children running"

        supervisor_status.values = [
            KeyValue(key="strategy", value=self.strategy.name),
            KeyValue(key="max_restarts", value=str(self.max_restarts)),
            KeyValue(key="restart_window", value=str(self.restart_window)),
            KeyValue(key="children_running", value=str(running_count)),
            KeyValue(key="children_total", value=str(total_count)),
        ]

        diag_msg.status.append(supervisor_status)

        # Individual child status
        for child_id, child in self._children.items():
            status = DiagnosticStatus()
            status.name = f"{self.get_name()}/{child_id}"
            status.hardware_id = child_id

            if child.state == ChildState.RUNNING:
                status.level = DiagnosticStatus.OK
                status.message = "Running"
            elif child.state in (ChildState.STARTING, ChildState.RESTARTING):
                status.level = DiagnosticStatus.WARN
                status.message = child.state.name
            else:
                status.level = DiagnosticStatus.ERROR
                status.message = child.state.name

            status.values = [
                KeyValue(key="state", value=child.state.name),
                KeyValue(key="restart_count", value=str(child.restart_count)),
                KeyValue(key="restart_type", value=child.spec.restart_type.name),
                KeyValue(key="dependencies", value=",".join(child.spec.dependencies)),
            ]

            diag_msg.status.append(status)

        self._status_pub.publish(diag_msg)

    def _publish_event(self, event: str):
        """Publish a supervisor event."""
        msg = String()
        msg.data = event
        self._event_pub.publish(msg)

    def _start_all_callback(self, request, response):
        """Service callback to start all children."""
        try:
            success = self.start_children()
            response.success = success
            response.message = "All children started" if success else "Failed to start some children"
        except Exception as e:
            response.success = False
            response.message = str(e)
        return response

    def _stop_all_callback(self, request, response):
        """Service callback to stop all children."""
        try:
            self.stop_children()
            response.success = True
            response.message = "All children stopped"
        except Exception as e:
            response.success = False
            response.message = str(e)
        return response

    def _restart_all_callback(self, request, response):
        """Service callback to restart all children."""
        try:
            self.stop_children()
            time.sleep(1.0)
            success = self.start_children()
            response.success = success
            response.message = "All children restarted" if success else "Failed to restart some children"
        except Exception as e:
            response.success = False
            response.message = str(e)
        return response

    def shutdown(self):
        """Gracefully shutdown the supervisor and all children."""
        self._shutdown_requested = True
        self.get_logger().info("Supervisor shutting down...")

        self._check_timer.cancel()
        self._status_timer.cancel()

        self.stop_children()

        self.get_logger().info("Supervisor shutdown complete")

    def get_child_state(self, child_id: str) -> Optional[ChildState]:
        """Get the current state of a child."""
        child = self._children.get(child_id)
        return child.state if child else None

    def get_all_states(self) -> Dict[str, ChildState]:
        """Get states of all children."""
        return {cid: c.state for cid, c in self._children.items()}


def main(args=None):
    """Main entry point for the supervisor node."""
    rclpy.init(args=args)

    supervisor = SupervisorNode()
    executor = MultiThreadedExecutor()
    executor.add_node(supervisor)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.shutdown()
        supervisor.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
