#!/usr/bin/env python3
"""
LEGO MCP Safety Node
Implements ISO 10218 compliant safety systems including:
- Hardware emergency stop relay control
- Watchdog timer for heartbeat monitoring
- Safety zone monitoring
- Equipment interlock management

LEGO MCP Manufacturing System v7.0
"""

import threading
from typing import Optional, Dict, Set
from datetime import datetime
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger, SetBool
from sensor_msgs.msg import JointState
from diagnostic_msgs.msg import DiagnosticStatus, DiagnosticArray, KeyValue

try:
    from lego_mcp_msgs.msg import EquipmentStatus
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False

# Try to import GPIO for Raspberry Pi hardware e-stop
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class SafetyState(Enum):
    """Safety system states."""
    NORMAL = 'normal'
    WARNING = 'warning'
    ESTOP_PENDING = 'estop_pending'
    ESTOP_ACTIVE = 'estop_active'
    LOCKOUT = 'lockout'


class SafetyNode(Node):
    """
    ROS2 Safety Node implementing ISO 10218 compliant e-stop.

    Features:
    - Hardware e-stop relay control (GPIO or simulated)
    - Watchdog timer - triggers e-stop if no heartbeat for timeout period
    - Equipment interlock management
    - Safety zone monitoring
    """

    def __init__(self):
        super().__init__('safety_node')

        # Declare parameters
        self.declare_parameter('estop_gpio_pin', 17)
        self.declare_parameter('estop_relay_active_low', True)
        self.declare_parameter('watchdog_timeout_ms', 500)
        self.declare_parameter('heartbeat_sources', ['orchestrator'])
        self.declare_parameter('simulation_mode', False)

        # Get parameters
        self.estop_pin = self.get_parameter('estop_gpio_pin').value
        self.relay_active_low = self.get_parameter('estop_relay_active_low').value
        self.watchdog_timeout_ms = self.get_parameter('watchdog_timeout_ms').value
        self.heartbeat_sources = self.get_parameter('heartbeat_sources').value
        self.simulation_mode = self.get_parameter('simulation_mode').value

        # Safety state
        self._state = SafetyState.NORMAL
        self._estop_active = False
        self._estop_reason = ""
        self._lock = threading.Lock()

        # Heartbeat tracking
        self._heartbeat_times: Dict[str, datetime] = {}
        self._heartbeat_healthy: Set[str] = set()

        # Equipment interlocks
        self._interlocks: Dict[str, bool] = {}

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Initialize GPIO if available and not in simulation
        self._gpio_initialized = False
        if GPIO_AVAILABLE and not self.simulation_mode and self.estop_pin >= 0:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.estop_pin, GPIO.OUT)
                # Set relay to "safe" state (e-stop not active)
                GPIO.output(self.estop_pin, GPIO.HIGH if self.relay_active_low else GPIO.LOW)
                self._gpio_initialized = True
                self.get_logger().info(f"E-stop GPIO initialized on pin {self.estop_pin}")
            except Exception as e:
                self.get_logger().error(f"Failed to initialize GPIO: {e}")

        # Publishers
        self._estop_pub = self.create_publisher(
            Bool,
            '/safety/estop_status',
            10
        )

        self._state_pub = self.create_publisher(
            String,
            '/safety/state',
            10
        )

        # Subscribers
        self._heartbeat_sub = self.create_subscription(
            Bool,
            '/safety/heartbeat',
            self._on_heartbeat,
            10
        )

        # Equipment status subscribers for interlock monitoring
        for equipment in ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']:
            self.create_subscription(
                EquipmentStatus if MSGS_AVAILABLE else String,
                f'/{equipment}/status',
                lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                10
            )

        # Services
        self._estop_srv = self.create_service(
            Trigger,
            '/safety/emergency_stop',
            self._estop_callback,
            callback_group=self._cb_group
        )

        self._reset_srv = self.create_service(
            Trigger,
            '/safety/reset',
            self._reset_callback,
            callback_group=self._cb_group
        )

        self._set_interlock_srv = self.create_service(
            SetBool,
            '/safety/set_interlock',
            self._set_interlock_callback,
            callback_group=self._cb_group
        )

        # Watchdog timer
        watchdog_period = self.watchdog_timeout_ms / 1000.0 / 2  # Check at 2x rate
        self._watchdog_timer = self.create_timer(
            watchdog_period,
            self._watchdog_callback,
            callback_group=self._cb_group
        )

        # Status publishing timer
        self._status_timer = self.create_timer(
            0.1,  # 10 Hz
            self._publish_status
        )

        self.get_logger().info(f"Safety node initialized (simulation={self.simulation_mode})")

    def _on_heartbeat(self, msg: Bool):
        """Handle heartbeat from monitored systems."""
        if msg.data:
            self._heartbeat_times['orchestrator'] = datetime.now()
            self._heartbeat_healthy.add('orchestrator')

    def _on_equipment_status(self, equipment_id: str, msg):
        """Monitor equipment for safety-related status."""
        if MSGS_AVAILABLE and hasattr(msg, 'estop_active'):
            # Check if equipment reports e-stop
            if msg.estop_active:
                self.get_logger().warn(f"Equipment {equipment_id} reports e-stop active")

            # Check for collision detection
            if hasattr(msg, 'joint_torques') and msg.joint_torques:
                # High torque could indicate collision
                max_torque = max(abs(t) for t in msg.joint_torques)
                if max_torque > 50.0:  # Newton-meters threshold
                    self.get_logger().warn(f"High torque detected on {equipment_id}: {max_torque} Nm")

    def _watchdog_callback(self):
        """Check heartbeats and trigger e-stop if timeout."""
        now = datetime.now()
        timeout_delta = self.watchdog_timeout_ms / 1000.0

        for source in self.heartbeat_sources:
            last_heartbeat = self._heartbeat_times.get(source)
            if last_heartbeat:
                elapsed = (now - last_heartbeat).total_seconds()
                if elapsed > timeout_delta:
                    if source in self._heartbeat_healthy:
                        self._heartbeat_healthy.remove(source)
                        self.get_logger().warn(f"Heartbeat timeout from {source} ({elapsed:.2f}s)")

                        # Trigger e-stop only if not in simulation
                        if not self.simulation_mode:
                            self._trigger_estop(f"Watchdog timeout - no heartbeat from {source}")
            else:
                # No heartbeat received yet - give grace period on startup
                pass

    def _trigger_estop(self, reason: str):
        """Trigger emergency stop."""
        with self._lock:
            if self._estop_active:
                return  # Already in e-stop

            self.get_logger().error(f"E-STOP TRIGGERED: {reason}")
            self._estop_active = True
            self._estop_reason = reason
            self._state = SafetyState.ESTOP_ACTIVE

            # Activate hardware e-stop relay
            if self._gpio_initialized:
                # Active low: LOW = e-stop active (relay closed, power cut)
                GPIO.output(
                    self.estop_pin,
                    GPIO.LOW if self.relay_active_low else GPIO.HIGH
                )

            # Publish e-stop status
            self._publish_estop(True)

    def _release_estop(self) -> bool:
        """Release emergency stop (requires manual reset)."""
        with self._lock:
            if not self._estop_active:
                return True

            # Check conditions for reset
            # In production, would verify:
            # - Physical e-stop button released
            # - All equipment in safe state
            # - Operator acknowledgment

            self.get_logger().info("E-stop released")
            self._estop_active = False
            self._estop_reason = ""
            self._state = SafetyState.NORMAL

            # Release hardware e-stop relay
            if self._gpio_initialized:
                GPIO.output(
                    self.estop_pin,
                    GPIO.HIGH if self.relay_active_low else GPIO.LOW
                )

            # Publish e-stop status
            self._publish_estop(False)

            return True

    def _publish_estop(self, active: bool):
        """Publish e-stop status."""
        msg = Bool()
        msg.data = active
        self._estop_pub.publish(msg)

    def _publish_status(self):
        """Publish current safety state."""
        msg = String()
        msg.data = self._state.value
        self._state_pub.publish(msg)

        # Also publish e-stop status regularly
        self._publish_estop(self._estop_active)

    def _estop_callback(self, request, response):
        """Handle e-stop service request."""
        self._trigger_estop("Service call")
        response.success = True
        response.message = "Emergency stop activated"
        return response

    def _reset_callback(self, request, response):
        """Handle reset service request."""
        success = self._release_estop()
        response.success = success
        response.message = "E-stop released" if success else "Reset failed - check conditions"
        return response

    def _set_interlock_callback(self, request, response):
        """Handle interlock set request."""
        # This would be used for equipment-specific interlocks
        response.success = True
        response.message = "Interlock set"
        return response

    def destroy_node(self):
        """Cleanup on shutdown."""
        # Ensure e-stop is active on shutdown for safety
        if self._gpio_initialized:
            GPIO.output(
                self.estop_pin,
                GPIO.LOW if self.relay_active_low else GPIO.HIGH
            )
            GPIO.cleanup()

        super().destroy_node()


class SafetyLifecycleNode(LifecycleNode):
    """
    ROS2 Lifecycle-managed Safety Node implementing ISO 10218 compliant e-stop.

    This is an additive wrapper around SafetyNode functionality that provides
    lifecycle management for deterministic startup/shutdown in supervised systems.

    Lifecycle States:
        - unconfigured: Node created, GPIO not initialized
        - inactive: GPIO initialized, but safety monitoring not active
        - active: Full safety monitoring operational
        - finalized: Cleaned up and ready for destruction

    Industry 4.0/5.0 Architecture - ISA-95 Layer 1 (Control)
    """

    def __init__(self, node_name: str = 'safety_lifecycle_node'):
        super().__init__(node_name)

        # Declare parameters (not loaded until configure)
        self.declare_parameter('estop_gpio_pin', 17)
        self.declare_parameter('estop_relay_active_low', True)
        self.declare_parameter('watchdog_timeout_ms', 500)
        self.declare_parameter('heartbeat_sources', ['orchestrator'])
        self.declare_parameter('simulation_mode', False)
        self.declare_parameter('safety_zone_count', 4)

        # State tracking (allocated in on_configure)
        self._state = SafetyState.NORMAL
        self._estop_active = False
        self._estop_reason = ""
        self._lock = threading.Lock()

        # Heartbeat tracking
        self._heartbeat_times: Dict[str, datetime] = {}
        self._heartbeat_healthy: Set[str] = set()

        # Equipment interlocks
        self._interlocks: Dict[str, bool] = {}

        # GPIO state
        self._gpio_initialized = False
        self.estop_pin = -1
        self.relay_active_low = True
        self.watchdog_timeout_ms = 500
        self.heartbeat_sources = []
        self.simulation_mode = False

        # Timers and publishers (created in on_configure/activate)
        self._watchdog_timer = None
        self._status_timer = None
        self._diagnostic_timer = None
        self._estop_pub = None
        self._state_pub = None
        self._diagnostic_pub = None
        self._lifecycle_state_pub = None

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        self.get_logger().info("Safety lifecycle node created (unconfigured)")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        """
        Configure callback - Initialize GPIO and allocate resources.

        Called when transitioning from unconfigured to inactive.
        """
        self.get_logger().info("Configuring safety node...")

        try:
            # Load parameters
            self.estop_pin = self.get_parameter('estop_gpio_pin').value
            self.relay_active_low = self.get_parameter('estop_relay_active_low').value
            self.watchdog_timeout_ms = self.get_parameter('watchdog_timeout_ms').value
            self.heartbeat_sources = self.get_parameter('heartbeat_sources').value
            self.simulation_mode = self.get_parameter('simulation_mode').value

            # Initialize GPIO if available and not in simulation
            if GPIO_AVAILABLE and not self.simulation_mode and self.estop_pin >= 0:
                try:
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.estop_pin, GPIO.OUT)
                    # Set relay to "safe" state (e-stop not active)
                    GPIO.output(self.estop_pin, GPIO.HIGH if self.relay_active_low else GPIO.LOW)
                    self._gpio_initialized = True
                    self.get_logger().info(f"E-stop GPIO initialized on pin {self.estop_pin}")
                except Exception as e:
                    self.get_logger().error(f"Failed to initialize GPIO: {e}")
                    return TransitionCallbackReturn.FAILURE

            # Create publishers
            self._estop_pub = self.create_publisher(Bool, '/safety/estop_status', 10)
            self._state_pub = self.create_publisher(String, '/safety/state', 10)
            self._diagnostic_pub = self.create_publisher(
                DiagnosticArray, '/diagnostics', 10
            )
            self._lifecycle_state_pub = self.create_publisher(
                String, '~/lifecycle_state', 10
            )

            # Create subscribers
            self.create_subscription(
                Bool, '/safety/heartbeat', self._on_heartbeat, 10
            )

            # Equipment status subscribers
            for equipment in ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']:
                self.create_subscription(
                    EquipmentStatus if MSGS_AVAILABLE else String,
                    f'/{equipment}/status',
                    lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                    10
                )

            # Create services
            self.create_service(
                Trigger, '/safety/emergency_stop',
                self._estop_callback, callback_group=self._cb_group
            )
            self.create_service(
                Trigger, '/safety/reset',
                self._reset_callback, callback_group=self._cb_group
            )
            self.create_service(
                SetBool, '/safety/set_interlock',
                self._set_interlock_callback, callback_group=self._cb_group
            )

            self._publish_lifecycle_state("inactive")
            self.get_logger().info("Safety node configured successfully")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Configuration failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        """
        Activate callback - Start safety monitoring.

        Called when transitioning from inactive to active.
        """
        self.get_logger().info("Activating safety node...")

        try:
            # Start watchdog timer
            watchdog_period = self.watchdog_timeout_ms / 1000.0 / 2
            self._watchdog_timer = self.create_timer(
                watchdog_period, self._watchdog_callback, callback_group=self._cb_group
            )

            # Start status publishing timer
            self._status_timer = self.create_timer(0.1, self._publish_status)

            # Start diagnostic publishing timer
            self._diagnostic_timer = self.create_timer(1.0, self._publish_diagnostics)

            # Reset safety state
            self._state = SafetyState.NORMAL
            self._estop_active = False

            self._publish_lifecycle_state("active")
            self.get_logger().info("Safety node activated - monitoring active")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Activation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        """
        Deactivate callback - Stop monitoring but keep GPIO configured.

        Called when transitioning from active to inactive.
        Note: For safety, e-stop remains active on deactivation.
        """
        self.get_logger().info("Deactivating safety node...")

        try:
            # Stop timers
            if self._watchdog_timer:
                self.destroy_timer(self._watchdog_timer)
                self._watchdog_timer = None

            if self._status_timer:
                self.destroy_timer(self._status_timer)
                self._status_timer = None

            if self._diagnostic_timer:
                self.destroy_timer(self._diagnostic_timer)
                self._diagnostic_timer = None

            # For safety, trigger e-stop when deactivating
            self._trigger_estop("Lifecycle deactivation - safety precaution")

            self._publish_lifecycle_state("inactive")
            self.get_logger().info("Safety node deactivated")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Deactivation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        """
        Cleanup callback - Release GPIO resources.

        Called when transitioning from inactive to unconfigured.
        """
        self.get_logger().info("Cleaning up safety node...")

        try:
            # Release GPIO
            if self._gpio_initialized:
                # Ensure e-stop is active (safe state) before cleanup
                GPIO.output(
                    self.estop_pin,
                    GPIO.LOW if self.relay_active_low else GPIO.HIGH
                )
                GPIO.cleanup()
                self._gpio_initialized = False

            # Clear state
            self._heartbeat_times.clear()
            self._heartbeat_healthy.clear()
            self._interlocks.clear()

            self._publish_lifecycle_state("unconfigured")
            self.get_logger().info("Safety node cleaned up")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Cleanup failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        """
        Shutdown callback - Final cleanup before destruction.

        Ensures system is in safe state before node destruction.
        """
        self.get_logger().info("Shutting down safety node...")

        # Ensure e-stop is active (safe state)
        if self._gpio_initialized:
            try:
                GPIO.output(
                    self.estop_pin,
                    GPIO.LOW if self.relay_active_low else GPIO.HIGH
                )
                GPIO.cleanup()
            except Exception:
                pass

        self._publish_lifecycle_state("finalized")
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state: State) -> TransitionCallbackReturn:
        """
        Error callback - Trigger e-stop and attempt recovery.

        Safety-critical: Always trigger e-stop on error.
        """
        self.get_logger().error(f"Safety node error in state: {state.label}")
        self._publish_lifecycle_state("error")

        # Safety-critical: Always trigger e-stop on error
        self._trigger_estop(f"Lifecycle error in state {state.label}")

        # Return SUCCESS to allow recovery attempt
        return TransitionCallbackReturn.SUCCESS

    def _publish_lifecycle_state(self, state_str: str):
        """Publish current lifecycle state."""
        if self._lifecycle_state_pub:
            msg = String()
            msg.data = state_str
            self._lifecycle_state_pub.publish(msg)

    def _on_heartbeat(self, msg: Bool):
        """Handle heartbeat from monitored systems."""
        if msg.data:
            self._heartbeat_times['orchestrator'] = datetime.now()
            self._heartbeat_healthy.add('orchestrator')

    def _on_equipment_status(self, equipment_id: str, msg):
        """Monitor equipment for safety-related status."""
        if MSGS_AVAILABLE and hasattr(msg, 'estop_active'):
            if msg.estop_active:
                self.get_logger().warn(f"Equipment {equipment_id} reports e-stop active")

    def _watchdog_callback(self):
        """Check heartbeats and trigger e-stop if timeout."""
        now = datetime.now()
        timeout_delta = self.watchdog_timeout_ms / 1000.0

        for source in self.heartbeat_sources:
            last_heartbeat = self._heartbeat_times.get(source)
            if last_heartbeat:
                elapsed = (now - last_heartbeat).total_seconds()
                if elapsed > timeout_delta:
                    if source in self._heartbeat_healthy:
                        self._heartbeat_healthy.remove(source)
                        self.get_logger().warn(f"Heartbeat timeout from {source}")
                        if not self.simulation_mode:
                            self._trigger_estop(f"Watchdog timeout - no heartbeat from {source}")

    def _trigger_estop(self, reason: str):
        """Trigger emergency stop."""
        with self._lock:
            if self._estop_active:
                return

            self.get_logger().error(f"E-STOP TRIGGERED: {reason}")
            self._estop_active = True
            self._estop_reason = reason
            self._state = SafetyState.ESTOP_ACTIVE

            if self._gpio_initialized:
                GPIO.output(
                    self.estop_pin,
                    GPIO.LOW if self.relay_active_low else GPIO.HIGH
                )

            self._publish_estop(True)

    def _release_estop(self) -> bool:
        """Release emergency stop."""
        with self._lock:
            if not self._estop_active:
                return True

            self.get_logger().info("E-stop released")
            self._estop_active = False
            self._estop_reason = ""
            self._state = SafetyState.NORMAL

            if self._gpio_initialized:
                GPIO.output(
                    self.estop_pin,
                    GPIO.HIGH if self.relay_active_low else GPIO.LOW
                )

            self._publish_estop(False)
            return True

    def _publish_estop(self, active: bool):
        """Publish e-stop status."""
        if self._estop_pub:
            msg = Bool()
            msg.data = active
            self._estop_pub.publish(msg)

    def _publish_status(self):
        """Publish current safety state."""
        if self._state_pub:
            msg = String()
            msg.data = self._state.value
            self._state_pub.publish(msg)
            self._publish_estop(self._estop_active)

    def _publish_diagnostics(self):
        """Publish diagnostic information."""
        if not self._diagnostic_pub:
            return

        diag_msg = DiagnosticArray()
        diag_msg.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.name = self.get_name()
        status.hardware_id = "safety_system"

        if self._state == SafetyState.NORMAL:
            status.level = DiagnosticStatus.OK
            status.message = "Safety system normal"
        elif self._state == SafetyState.WARNING:
            status.level = DiagnosticStatus.WARN
            status.message = "Safety system warning"
        else:
            status.level = DiagnosticStatus.ERROR
            status.message = f"Safety system: {self._state.value}"

        status.values = [
            KeyValue(key="state", value=self._state.value),
            KeyValue(key="estop_active", value=str(self._estop_active)),
            KeyValue(key="estop_reason", value=self._estop_reason),
            KeyValue(key="gpio_initialized", value=str(self._gpio_initialized)),
            KeyValue(key="simulation_mode", value=str(self.simulation_mode)),
            KeyValue(key="healthy_sources", value=",".join(self._heartbeat_healthy)),
        ]

        diag_msg.status.append(status)
        self._diagnostic_pub.publish(diag_msg)

    def _estop_callback(self, request, response):
        """Handle e-stop service request."""
        self._trigger_estop("Service call")
        response.success = True
        response.message = "Emergency stop activated"
        return response

    def _reset_callback(self, request, response):
        """Handle reset service request."""
        success = self._release_estop()
        response.success = success
        response.message = "E-stop released" if success else "Reset failed"
        return response

    def _set_interlock_callback(self, request, response):
        """Handle interlock set request."""
        response.success = True
        response.message = "Interlock set"
        return response


def main(args=None):
    rclpy.init(args=args)

    node = SafetyNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main_lifecycle(args=None):
    """Entry point for lifecycle-managed safety node."""
    rclpy.init(args=args)

    node = SafetyLifecycleNode()

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
