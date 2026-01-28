#!/usr/bin/env python3
"""
Heartbeat utilities for LEGO MCP supervised nodes.

This module provides:
- HeartbeatMixin: A mixin class to add heartbeat functionality to ROS2 nodes
- HeartbeatMonitor: A utility class to monitor heartbeats from multiple nodes

Nodes using the HeartbeatMixin will automatically send periodic heartbeat
messages to their supervisor, allowing the supervisor to detect unresponsive
nodes and take appropriate action based on the configured restart strategy.
"""

import time
import threading
from typing import Callable, Dict, Optional, Set
from dataclasses import dataclass, field

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String, Bool


@dataclass
class HeartbeatStatus:
    """Status information for a monitored heartbeat source."""
    node_id: str
    last_heartbeat: float = 0.0
    heartbeat_count: int = 0
    is_alive: bool = False
    missed_count: int = 0
    latency_ms: float = 0.0


class HeartbeatMixin:
    """
    Mixin class providing heartbeat functionality for supervised ROS2 nodes.

    This mixin should be used with ROS2 nodes that are managed by the
    SupervisorNode. It automatically publishes heartbeat messages at
    configurable intervals.

    Usage:
        class MyNode(Node, HeartbeatMixin):
            def __init__(self):
                super().__init__('my_node')
                self.init_heartbeat()

            def on_heartbeat(self):
                # Optional: Custom logic executed on each heartbeat
                pass
    """

    # Default heartbeat configuration
    _heartbeat_interval: float = 1.0  # seconds
    _heartbeat_topic: str = "~/heartbeats"
    _heartbeat_node_id: Optional[str] = None
    _heartbeat_timer = None
    _heartbeat_publisher = None
    _heartbeat_callback_group = None
    _heartbeat_enabled: bool = True
    _heartbeat_count: int = 0
    _heartbeat_custom_callback: Optional[Callable] = None

    def init_heartbeat(
        self,
        interval: float = 1.0,
        topic: str = "/lego_mcp_supervisor/heartbeats",
        node_id: Optional[str] = None,
        enabled: bool = True,
        callback: Optional[Callable] = None,
    ):
        """
        Initialize the heartbeat publisher and timer.

        Args:
            interval: Time between heartbeats in seconds
            topic: Topic to publish heartbeats to
            node_id: Unique identifier for this node (defaults to node name)
            enabled: Whether heartbeats are initially enabled
            callback: Optional callback to execute on each heartbeat
        """
        self._heartbeat_interval = interval
        self._heartbeat_topic = topic
        self._heartbeat_node_id = node_id or self.get_name()
        self._heartbeat_enabled = enabled
        self._heartbeat_custom_callback = callback
        self._heartbeat_count = 0

        # Create callback group for heartbeat operations
        self._heartbeat_callback_group = ReentrantCallbackGroup()

        # QoS profile for reliable heartbeat delivery
        heartbeat_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=10
        )

        # Create publisher
        self._heartbeat_publisher = self.create_publisher(
            String,
            self._heartbeat_topic,
            heartbeat_qos
        )

        # Create timer for periodic heartbeats
        self._heartbeat_timer = self.create_timer(
            self._heartbeat_interval,
            self._send_heartbeat,
            callback_group=self._heartbeat_callback_group
        )

        # Declare parameters if the node supports them
        if hasattr(self, 'declare_parameter'):
            try:
                self.declare_parameter('heartbeat.interval', self._heartbeat_interval)
                self.declare_parameter('heartbeat.enabled', self._heartbeat_enabled)
                self.declare_parameter('heartbeat.node_id', self._heartbeat_node_id)
            except Exception:
                pass  # Parameters may already be declared

        self.get_logger().debug(
            f"Heartbeat initialized: id={self._heartbeat_node_id}, "
            f"interval={self._heartbeat_interval}s, topic={self._heartbeat_topic}"
        )

    def _send_heartbeat(self):
        """Send a heartbeat message to the supervisor."""
        if not self._heartbeat_enabled:
            return

        try:
            msg = String()
            msg.data = self._heartbeat_node_id

            self._heartbeat_publisher.publish(msg)
            self._heartbeat_count += 1

            # Execute custom callback if provided
            if self._heartbeat_custom_callback:
                try:
                    self._heartbeat_custom_callback()
                except Exception as e:
                    self.get_logger().warn(f"Heartbeat callback error: {e}")

            # Call overridable hook
            self.on_heartbeat()

        except Exception as e:
            self.get_logger().error(f"Failed to send heartbeat: {e}")

    def on_heartbeat(self):
        """
        Hook called on each heartbeat. Override in subclass for custom behavior.

        This method can be used to perform periodic health checks or
        maintenance tasks that should run at the heartbeat interval.
        """
        pass

    def enable_heartbeat(self):
        """Enable heartbeat publishing."""
        self._heartbeat_enabled = True
        self.get_logger().debug("Heartbeat enabled")

    def disable_heartbeat(self):
        """Disable heartbeat publishing."""
        self._heartbeat_enabled = False
        self.get_logger().debug("Heartbeat disabled")

    def set_heartbeat_interval(self, interval: float):
        """
        Change the heartbeat interval.

        Args:
            interval: New interval in seconds
        """
        if interval <= 0:
            self.get_logger().warn("Invalid heartbeat interval, must be positive")
            return

        self._heartbeat_interval = interval

        # Recreate timer with new interval
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()

        self._heartbeat_timer = self.create_timer(
            self._heartbeat_interval,
            self._send_heartbeat,
            callback_group=self._heartbeat_callback_group
        )

        self.get_logger().debug(f"Heartbeat interval changed to {interval}s")

    def get_heartbeat_count(self) -> int:
        """Get the total number of heartbeats sent."""
        return self._heartbeat_count

    def is_heartbeat_enabled(self) -> bool:
        """Check if heartbeat is currently enabled."""
        return self._heartbeat_enabled

    def shutdown_heartbeat(self):
        """Clean up heartbeat resources."""
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

        if self._heartbeat_publisher:
            self.destroy_publisher(self._heartbeat_publisher)
            self._heartbeat_publisher = None


class HeartbeatMonitor:
    """
    Utility class to monitor heartbeats from multiple nodes.

    This can be used independently of the SupervisorNode for custom
    monitoring scenarios.

    Usage:
        monitor = HeartbeatMonitor(node, timeout=5.0)
        monitor.add_node("node1")
        monitor.add_node("node2")
        monitor.start()

        # Later...
        status = monitor.get_status("node1")
        if not status.is_alive:
            handle_dead_node("node1")
    """

    def __init__(
        self,
        ros_node: Node,
        topic: str = "/lego_mcp_supervisor/heartbeats",
        timeout: float = 5.0,
        check_interval: float = 1.0,
        on_timeout: Optional[Callable[[str], None]] = None,
        on_recovery: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the heartbeat monitor.

        Args:
            ros_node: The ROS2 node to attach to
            topic: Topic to subscribe to for heartbeats
            timeout: Seconds without heartbeat before considering node dead
            check_interval: Interval between health checks
            on_timeout: Callback when a node times out
            on_recovery: Callback when a timed-out node recovers
        """
        self._node = ros_node
        self._topic = topic
        self._timeout = timeout
        self._check_interval = check_interval
        self._on_timeout = on_timeout
        self._on_recovery = on_recovery

        self._monitored_nodes: Dict[str, HeartbeatStatus] = {}
        self._lock = threading.RLock()
        self._running = False

        self._callback_group = ReentrantCallbackGroup()
        self._subscription = None
        self._check_timer = None

    def add_node(self, node_id: str):
        """
        Add a node to monitor.

        Args:
            node_id: Unique identifier of the node to monitor
        """
        with self._lock:
            if node_id not in self._monitored_nodes:
                self._monitored_nodes[node_id] = HeartbeatStatus(
                    node_id=node_id,
                    last_heartbeat=time.time(),
                    is_alive=True
                )
                self._node.get_logger().debug(f"Added node '{node_id}' to heartbeat monitor")

    def remove_node(self, node_id: str):
        """
        Remove a node from monitoring.

        Args:
            node_id: Unique identifier of the node to remove
        """
        with self._lock:
            if node_id in self._monitored_nodes:
                del self._monitored_nodes[node_id]
                self._node.get_logger().debug(f"Removed node '{node_id}' from heartbeat monitor")

    def start(self):
        """Start monitoring heartbeats."""
        if self._running:
            return

        # QoS profile for heartbeat subscription
        heartbeat_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=10
        )

        # Create subscription
        self._subscription = self._node.create_subscription(
            String,
            self._topic,
            self._heartbeat_callback,
            heartbeat_qos,
            callback_group=self._callback_group
        )

        # Create health check timer
        self._check_timer = self._node.create_timer(
            self._check_interval,
            self._check_health,
            callback_group=self._callback_group
        )

        self._running = True
        self._node.get_logger().info(
            f"Heartbeat monitor started: topic={self._topic}, timeout={self._timeout}s"
        )

    def stop(self):
        """Stop monitoring heartbeats."""
        if not self._running:
            return

        if self._subscription:
            self._node.destroy_subscription(self._subscription)
            self._subscription = None

        if self._check_timer:
            self._check_timer.cancel()
            self._check_timer = None

        self._running = False
        self._node.get_logger().info("Heartbeat monitor stopped")

    def _heartbeat_callback(self, msg: String):
        """Handle incoming heartbeat messages."""
        node_id = msg.data
        now = time.time()

        with self._lock:
            if node_id in self._monitored_nodes:
                status = self._monitored_nodes[node_id]
                was_dead = not status.is_alive

                # Calculate latency (rough estimate)
                if status.last_heartbeat > 0:
                    expected_interval = self._check_interval
                    actual_interval = now - status.last_heartbeat
                    status.latency_ms = max(0, (actual_interval - expected_interval) * 1000)

                status.last_heartbeat = now
                status.heartbeat_count += 1
                status.is_alive = True
                status.missed_count = 0

                # Fire recovery callback
                if was_dead and self._on_recovery:
                    try:
                        self._on_recovery(node_id)
                    except Exception as e:
                        self._node.get_logger().error(f"Recovery callback error: {e}")

    def _check_health(self):
        """Check health of all monitored nodes."""
        now = time.time()

        with self._lock:
            for node_id, status in self._monitored_nodes.items():
                time_since_heartbeat = now - status.last_heartbeat

                if time_since_heartbeat > self._timeout:
                    was_alive = status.is_alive
                    status.is_alive = False
                    status.missed_count += 1

                    # Fire timeout callback
                    if was_alive and self._on_timeout:
                        try:
                            self._on_timeout(node_id)
                        except Exception as e:
                            self._node.get_logger().error(f"Timeout callback error: {e}")

    def get_status(self, node_id: str) -> Optional[HeartbeatStatus]:
        """
        Get the status of a monitored node.

        Args:
            node_id: Node identifier

        Returns:
            HeartbeatStatus or None if not monitored
        """
        with self._lock:
            return self._monitored_nodes.get(node_id)

    def get_all_statuses(self) -> Dict[str, HeartbeatStatus]:
        """Get status of all monitored nodes."""
        with self._lock:
            return dict(self._monitored_nodes)

    def get_alive_nodes(self) -> Set[str]:
        """Get set of currently alive node IDs."""
        with self._lock:
            return {nid for nid, s in self._monitored_nodes.items() if s.is_alive}

    def get_dead_nodes(self) -> Set[str]:
        """Get set of currently dead node IDs."""
        with self._lock:
            return {nid for nid, s in self._monitored_nodes.items() if not s.is_alive}

    def is_node_alive(self, node_id: str) -> bool:
        """
        Check if a specific node is alive.

        Args:
            node_id: Node identifier

        Returns:
            True if alive, False if dead or not monitored
        """
        status = self.get_status(node_id)
        return status.is_alive if status else False

    def set_timeout(self, timeout: float):
        """
        Change the heartbeat timeout.

        Args:
            timeout: New timeout in seconds
        """
        if timeout <= 0:
            self._node.get_logger().warn("Invalid timeout, must be positive")
            return
        self._timeout = timeout

    @property
    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._running

    @property
    def monitored_count(self) -> int:
        """Get the number of nodes being monitored."""
        with self._lock:
            return len(self._monitored_nodes)


class HealthyNodeMixin(HeartbeatMixin):
    """
    Extended mixin that includes self-health checking capabilities.

    Nodes using this mixin can register health check functions that are
    evaluated on each heartbeat. If any health check fails, the heartbeat
    is suppressed, allowing the supervisor to detect the unhealthy state.

    Usage:
        class MyNode(Node, HealthyNodeMixin):
            def __init__(self):
                super().__init__('my_node')
                self.init_heartbeat()
                self.add_health_check("database", self.check_database)
                self.add_health_check("sensor", self.check_sensor)

            def check_database(self) -> bool:
                return self.db_connection.is_connected()

            def check_sensor(self) -> bool:
                return self.sensor.is_responding()
    """

    _health_checks: Dict[str, Callable[[], bool]] = {}
    _health_status: Dict[str, bool] = {}
    _suppress_heartbeat_on_unhealthy: bool = True

    def init_healthy_node(
        self,
        suppress_on_unhealthy: bool = True,
        **heartbeat_kwargs
    ):
        """
        Initialize the healthy node with heartbeat and health checking.

        Args:
            suppress_on_unhealthy: If True, suppress heartbeats when unhealthy
            **heartbeat_kwargs: Arguments passed to init_heartbeat()
        """
        self._health_checks = {}
        self._health_status = {}
        self._suppress_heartbeat_on_unhealthy = suppress_on_unhealthy
        self.init_heartbeat(**heartbeat_kwargs)

    def add_health_check(self, name: str, check_func: Callable[[], bool]):
        """
        Add a health check function.

        Args:
            name: Unique name for the health check
            check_func: Function that returns True if healthy, False otherwise
        """
        self._health_checks[name] = check_func
        self._health_status[name] = True
        self.get_logger().debug(f"Added health check: {name}")

    def remove_health_check(self, name: str):
        """Remove a health check function."""
        self._health_checks.pop(name, None)
        self._health_status.pop(name, None)

    def on_heartbeat(self):
        """Override to perform health checks before heartbeat."""
        all_healthy = True

        for name, check_func in self._health_checks.items():
            try:
                is_healthy = check_func()
                was_healthy = self._health_status.get(name, True)

                self._health_status[name] = is_healthy

                if is_healthy and not was_healthy:
                    self.get_logger().info(f"Health check '{name}' recovered")
                    self.on_health_recovered(name)
                elif not is_healthy and was_healthy:
                    self.get_logger().warn(f"Health check '{name}' failed")
                    self.on_health_degraded(name)

                if not is_healthy:
                    all_healthy = False

            except Exception as e:
                self.get_logger().error(f"Health check '{name}' raised exception: {e}")
                self._health_status[name] = False
                all_healthy = False

        # Suppress heartbeat if unhealthy
        if self._suppress_heartbeat_on_unhealthy and not all_healthy:
            self._heartbeat_enabled = False
        else:
            self._heartbeat_enabled = True

    def on_health_degraded(self, check_name: str):
        """
        Hook called when a health check transitions from healthy to unhealthy.
        Override in subclass for custom behavior.
        """
        pass

    def on_health_recovered(self, check_name: str):
        """
        Hook called when a health check transitions from unhealthy to healthy.
        Override in subclass for custom behavior.
        """
        pass

    def is_healthy(self) -> bool:
        """Check if all health checks are passing."""
        return all(self._health_status.values())

    def get_health_status(self) -> Dict[str, bool]:
        """Get the current health status of all checks."""
        return dict(self._health_status)

    def get_failed_checks(self) -> Set[str]:
        """Get the names of failing health checks."""
        return {name for name, healthy in self._health_status.items() if not healthy}
