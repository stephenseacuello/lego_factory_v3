#!/usr/bin/env python3
"""
GRBL ROS2 Node
ROS2 interface for standard GRBL-based machines (CNC, Laser).
Supports MKS Laser Engraver and other GRBL 1.1 compatible devices.

LEGO MCP Manufacturing System v7.0
"""

import asyncio
import re
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Point

# Import custom messages (will be available after building lego_mcp_msgs)
try:
    from lego_mcp_msgs.msg import EquipmentStatus
    from lego_mcp_msgs.action import MachineOperation
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    EquipmentStatus = None
    MachineOperation = None

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class GRBLState(Enum):
    """GRBL machine states."""
    IDLE = 'Idle'
    RUN = 'Run'
    HOLD = 'Hold'
    JOG = 'Jog'
    ALARM = 'Alarm'
    DOOR = 'Door'
    CHECK = 'Check'
    HOME = 'Home'
    SLEEP = 'Sleep'
    UNKNOWN = 'Unknown'


@dataclass
class GRBLStatus:
    """GRBL status report."""
    state: GRBLState = GRBLState.UNKNOWN
    position: List[float] = None
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    buffer_planner: int = 0
    buffer_rx: int = 0
    laser_power: float = 0.0
    overrides: Dict[str, int] = None

    def __post_init__(self):
        if self.position is None:
            self.position = [0.0, 0.0, 0.0]
        if self.overrides is None:
            self.overrides = {'feed': 100, 'rapid': 100, 'spindle': 100}


class GRBLConnection:
    """
    Serial connection handler for GRBL devices.
    Provides async-compatible interface for serial communication.
    """

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        timeout: float = 0.1
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial: Optional['serial.Serial'] = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        """Establish serial connection."""
        if not SERIAL_AVAILABLE:
            return False

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            self._connected = True

            # Wake up GRBL
            self._serial.write(b'\r\n\r\n')
            import time
            time.sleep(2)
            self._serial.flushInput()

            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to GRBL: {e}")

    def disconnect(self):
        """Close serial connection."""
        if self._serial:
            self._serial.close()
            self._serial = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._serial is not None

    def send_command(self, command: str, wait_ok: bool = True) -> str:
        """
        Send command to GRBL and optionally wait for response.

        Args:
            command: G-code or GRBL command
            wait_ok: Wait for 'ok' or 'error' response

        Returns:
            Response string
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to GRBL")

        with self._lock:
            # Send command
            cmd = command.strip() + '\n'
            self._serial.write(cmd.encode())

            if not wait_ok:
                return ''

            # Read response
            responses = []
            while True:
                line = self._serial.readline().decode().strip()
                if not line:
                    continue
                responses.append(line)
                if line == 'ok' or line.startswith('error:'):
                    break

            return '\n'.join(responses)

    def request_status(self) -> str:
        """Request real-time status report."""
        if not self.is_connected:
            return ''

        with self._lock:
            self._serial.write(b'?')
            response = self._serial.readline().decode().strip()
            return response


class GRBLNode(Node):
    """
    ROS2 node for GRBL-based CNC/Laser machines.
    Provides topics for status and action server for G-code execution.
    """

    def __init__(self):
        super().__init__('grbl_node')

        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('machine_type', 'grbl')
        self.declare_parameter('x_max', 300.0)
        self.declare_parameter('y_max', 300.0)
        self.declare_parameter('z_max', 50.0)
        self.declare_parameter('has_laser', True)
        self.declare_parameter('status_rate_hz', 10.0)
        self.declare_parameter('simulate', False)

        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.machine_type = self.get_parameter('machine_type').value
        self.x_max = self.get_parameter('x_max').value
        self.y_max = self.get_parameter('y_max').value
        self.z_max = self.get_parameter('z_max').value
        self.has_laser = self.get_parameter('has_laser').value
        self.status_rate = self.get_parameter('status_rate_hz').value
        self.simulate = self.get_parameter('simulate').value

        # Connection
        self._connection: Optional[GRBLConnection] = None
        self._status = GRBLStatus()
        self._current_gcode: List[str] = []
        self._current_line = 0
        self._is_running = False

        # Callback group for concurrent callbacks
        self._cb_group = ReentrantCallbackGroup()

        # Publishers
        self.status_pub = self.create_publisher(
            EquipmentStatus if MSGS_AVAILABLE else String,
            '~/status',
            10
        )

        self.position_pub = self.create_publisher(
            Point,
            '~/position',
            10
        )

        self.state_pub = self.create_publisher(
            String,
            '~/state',
            10
        )

        # Subscribers
        self.command_sub = self.create_subscription(
            String,
            '~/command',
            self._on_command,
            10,
            callback_group=self._cb_group
        )

        self.estop_sub = self.create_subscription(
            Bool,
            '/safety/estop_status',
            self._on_estop,
            10
        )

        # Action server for G-code execution
        if MSGS_AVAILABLE:
            self._action_server = ActionServer(
                self,
                MachineOperation,
                '~/execute',
                execute_callback=self._execute_callback,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._cb_group
            )

        # Status polling timer
        self._status_timer = self.create_timer(
            1.0 / self.status_rate,
            self._poll_status,
            callback_group=self._cb_group
        )

        # Connect to device
        if not self.simulate:
            self._connect()
        else:
            self.get_logger().info(f"Running in simulation mode")

        self.get_logger().info(f"GRBL node initialized for {self.machine_type}")

    def _connect(self):
        """Connect to GRBL device."""
        try:
            self._connection = GRBLConnection(
                self.serial_port,
                self.baud_rate
            )
            self._connection.connect()
            self.get_logger().info(f"Connected to GRBL at {self.serial_port}")
        except Exception as e:
            self.get_logger().error(f"Failed to connect: {e}")
            self._connection = None

    def _poll_status(self):
        """Poll GRBL for status at regular interval."""
        if self.simulate:
            self._publish_simulated_status()
            return

        if not self._connection or not self._connection.is_connected:
            return

        try:
            response = self._connection.request_status()
            self._parse_status(response)
            self._publish_status()
        except Exception as e:
            self.get_logger().warn(f"Status poll failed: {e}")

    def _parse_status(self, response: str):
        """
        Parse GRBL status response.
        Format: <State|MPos:x,y,z|FS:feed,spindle|...>
        """
        if not response or not response.startswith('<'):
            return

        # Remove < and >
        response = response.strip('<>')
        parts = response.split('|')

        if parts:
            # State
            try:
                state_str = parts[0].split(':')[0]
                self._status.state = GRBLState(state_str)
            except ValueError:
                self._status.state = GRBLState.UNKNOWN

        for part in parts[1:]:
            if part.startswith('MPos:') or part.startswith('WPos:'):
                coords = part.split(':')[1].split(',')
                self._status.position = [float(c) for c in coords[:3]]

            elif part.startswith('FS:'):
                values = part[3:].split(',')
                self._status.feed_rate = float(values[0])
                if len(values) > 1:
                    self._status.spindle_speed = float(values[1])

            elif part.startswith('Bf:'):
                values = part[3:].split(',')
                self._status.buffer_planner = int(values[0])
                self._status.buffer_rx = int(values[1])

            elif part.startswith('Ov:'):
                values = part[3:].split(',')
                self._status.overrides = {
                    'feed': int(values[0]),
                    'rapid': int(values[1]),
                    'spindle': int(values[2])
                }

    def _publish_status(self):
        """Publish current status to ROS2 topics."""
        # Position
        pos_msg = Point()
        pos_msg.x = self._status.position[0]
        pos_msg.y = self._status.position[1]
        pos_msg.z = self._status.position[2] if len(self._status.position) > 2 else 0.0
        self.position_pub.publish(pos_msg)

        # State
        state_msg = String()
        state_msg.data = self._status.state.value
        self.state_pub.publish(state_msg)

        # Full equipment status
        if MSGS_AVAILABLE:
            status_msg = EquipmentStatus()
            status_msg.header.stamp = self.get_clock().now().to_msg()
            status_msg.equipment_id = self.get_name()
            status_msg.equipment_type = 'cnc' if not self.has_laser else 'laser'
            status_msg.connected = self._connection is not None and self._connection.is_connected

            # Map GRBL state to equipment state
            state_map = {
                GRBLState.IDLE: 1,
                GRBLState.RUN: 2,
                GRBLState.HOLD: 3,
                GRBLState.ALARM: 4,
            }
            status_msg.state = state_map.get(self._status.state, 0)
            status_msg.state_description = self._status.state.value

            status_msg.position = pos_msg
            status_msg.feed_rate = self._status.feed_rate
            status_msg.spindle_speed = self._status.spindle_speed
            status_msg.laser_power = self._status.laser_power

            self.status_pub.publish(status_msg)

    def _publish_simulated_status(self):
        """Publish simulated status for testing."""
        pos_msg = Point()
        pos_msg.x = self._status.position[0]
        pos_msg.y = self._status.position[1]
        pos_msg.z = self._status.position[2]
        self.position_pub.publish(pos_msg)

        state_msg = String()
        state_msg.data = 'Idle' if not self._is_running else 'Run'
        self.state_pub.publish(state_msg)

    def _on_command(self, msg: String):
        """Handle direct command input."""
        command = msg.data.strip()
        self.get_logger().info(f"Received command: {command}")

        if self.simulate:
            self.get_logger().info(f"[SIM] Would execute: {command}")
            return

        if self._connection and self._connection.is_connected:
            try:
                response = self._connection.send_command(command)
                self.get_logger().info(f"Response: {response}")
            except Exception as e:
                self.get_logger().error(f"Command failed: {e}")

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().warn("E-STOP activated!")
            if self._connection and self._connection.is_connected:
                # Send GRBL reset
                self._connection.send_command('\x18', wait_ok=False)  # Ctrl+X
                self._is_running = False

    def _goal_callback(self, goal_request):
        """Handle new action goal."""
        self.get_logger().info(f"Received goal request")
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancellation."""
        self.get_logger().info("Received cancel request")
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute G-code action."""
        self.get_logger().info("Executing G-code operation")

        request = goal_handle.request
        gcode = request.gcode if hasattr(request, 'gcode') else ''
        gcode_file = request.gcode_file if hasattr(request, 'gcode_file') else ''

        # Load G-code
        if gcode_file:
            try:
                with open(gcode_file, 'r') as f:
                    gcode = f.read()
            except Exception as e:
                self.get_logger().error(f"Failed to read G-code file: {e}")
                goal_handle.abort()
                result = MachineOperation.Result() if MSGS_AVAILABLE else None
                if result:
                    result.success = False
                    result.message = f"Failed to read G-code file: {e}"
                return result

        # Parse G-code lines
        lines = [line.strip() for line in gcode.split('\n')
                if line.strip() and not line.strip().startswith(';')]

        self._current_gcode = lines
        self._current_line = 0
        self._is_running = True

        total_lines = len(lines)
        feedback_msg = MachineOperation.Feedback() if MSGS_AVAILABLE else None

        try:
            for i, line in enumerate(lines):
                # Check for cancellation
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    self._is_running = False
                    result = MachineOperation.Result() if MSGS_AVAILABLE else None
                    if result:
                        result.success = False
                        result.message = "Operation cancelled"
                    return result

                self._current_line = i

                # Execute command
                if self.simulate:
                    self.get_logger().debug(f"[SIM] {line}")
                    await asyncio.sleep(0.01)  # Simulate execution time
                else:
                    if self._connection and self._connection.is_connected:
                        response = self._connection.send_command(line)
                        if 'error' in response:
                            self.get_logger().warn(f"GRBL error: {response}")

                # Publish feedback
                if feedback_msg:
                    feedback_msg.current_line = i + 1
                    feedback_msg.total_lines = total_lines
                    feedback_msg.current_command = line
                    feedback_msg.progress_percent = (i + 1) / total_lines * 100
                    feedback_msg.state = 2  # Running
                    feedback_msg.state_name = "Running"
                    feedback_msg.position.x = self._status.position[0]
                    feedback_msg.position.y = self._status.position[1]
                    feedback_msg.position.z = self._status.position[2]
                    goal_handle.publish_feedback(feedback_msg)

            # Success
            goal_handle.succeed()
            self._is_running = False

            result = MachineOperation.Result() if MSGS_AVAILABLE else None
            if result:
                result.success = True
                result.message = f"Executed {total_lines} G-code lines"
                result.lines_executed = total_lines
            return result

        except Exception as e:
            self.get_logger().error(f"Execution failed: {e}")
            goal_handle.abort()
            self._is_running = False

            result = MachineOperation.Result() if MSGS_AVAILABLE else None
            if result:
                result.success = False
                result.message = str(e)
            return result

    def home(self):
        """Home the machine."""
        if self._connection and self._connection.is_connected:
            self._connection.send_command('$H')

    def unlock(self):
        """Unlock GRBL after alarm."""
        if self._connection and self._connection.is_connected:
            self._connection.send_command('$X')

    def reset(self):
        """Soft reset GRBL."""
        if self._connection and self._connection.is_connected:
            self._connection.send_command('\x18', wait_ok=False)

    def destroy_node(self):
        """Cleanup on shutdown."""
        if self._connection:
            self._connection.disconnect()
        super().destroy_node()


class GRBLLifecycleNode:
    """
    ROS2 Lifecycle wrapper for GRBL node.

    Provides lifecycle state management for graceful startup/shutdown.
    Implements ISA-95 Level 0 (Field Devices) lifecycle compliance.

    Usage:
        ros2 run grbl_ros2 grbl_lifecycle_node
    """

    def __init__(self):
        from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
        from rclpy.lifecycle import LifecycleState

        self._lifecycle_node = None
        self._grbl_instance: Optional[GRBLNode] = None

    def create_node(self) -> 'LifecycleNode':
        """Create the lifecycle node."""
        from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
        from rclpy.lifecycle import LifecycleState

        class _GRBLLifecycle(LifecycleNode):
            def __init__(node_self):
                super().__init__('grbl_lifecycle_node')
                node_self._grbl: Optional[GRBLNode] = None
                node_self._configured = False

                # Declare parameters (same as GRBLNode)
                node_self.declare_parameter('serial_port', '/dev/ttyUSB0')
                node_self.declare_parameter('baud_rate', 115200)
                node_self.declare_parameter('machine_type', 'grbl')
                node_self.declare_parameter('simulate', False)

                node_self.get_logger().info('GRBL Lifecycle Node created (unconfigured)')

            def on_configure(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().info('Configuring GRBL Lifecycle Node...')
                try:
                    # Store parameters for later use
                    node_self._serial_port = node_self.get_parameter('serial_port').value
                    node_self._baud_rate = node_self.get_parameter('baud_rate').value
                    node_self._simulate = node_self.get_parameter('simulate').value

                    # Create connection but don't connect yet
                    if not node_self._simulate and SERIAL_AVAILABLE:
                        node_self._connection = GRBLConnection(
                            node_self._serial_port,
                            node_self._baud_rate
                        )
                    else:
                        node_self._connection = None

                    node_self._configured = True
                    node_self.get_logger().info('GRBL configured successfully')
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    node_self.get_logger().error(f'Configuration failed: {e}')
                    return TransitionCallbackReturn.FAILURE

            def on_activate(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().info('Activating GRBL Lifecycle Node...')
                try:
                    # Connect to device
                    if node_self._connection and not node_self._simulate:
                        node_self._connection.connect()
                        node_self.get_logger().info(f'Connected to GRBL at {node_self._serial_port}')

                    # Create publishers
                    node_self._state_pub = node_self.create_publisher(
                        String,
                        '~/state',
                        10
                    )

                    node_self._position_pub = node_self.create_publisher(
                        Point,
                        '~/position',
                        10
                    )

                    node_self.get_logger().info('GRBL activated successfully')
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    node_self.get_logger().error(f'Activation failed: {e}')
                    return TransitionCallbackReturn.FAILURE

            def on_deactivate(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().info('Deactivating GRBL Lifecycle Node...')
                try:
                    # Disconnect from device
                    if hasattr(node_self, '_connection') and node_self._connection:
                        node_self._connection.disconnect()

                    node_self.get_logger().info('GRBL deactivated')
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    node_self.get_logger().error(f'Deactivation failed: {e}')
                    return TransitionCallbackReturn.FAILURE

            def on_cleanup(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().info('Cleaning up GRBL Lifecycle Node...')
                node_self._connection = None
                node_self._configured = False
                return TransitionCallbackReturn.SUCCESS

            def on_shutdown(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().info('Shutting down GRBL Lifecycle Node...')
                if hasattr(node_self, '_connection') and node_self._connection:
                    node_self._connection.disconnect()
                return TransitionCallbackReturn.SUCCESS

            def on_error(node_self, state: LifecycleState) -> TransitionCallbackReturn:
                node_self.get_logger().error('GRBL entered error state')
                # Attempt to disconnect safely
                if hasattr(node_self, '_connection') and node_self._connection:
                    try:
                        node_self._connection.disconnect()
                    except:
                        pass
                return TransitionCallbackReturn.SUCCESS

        return _GRBLLifecycle()


def main(args=None):
    rclpy.init(args=args)

    node = GRBLNode()

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
    """Lifecycle node entry point."""
    rclpy.init(args=args)

    wrapper = GRBLLifecycleNode()
    node = wrapper.create_node()

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
