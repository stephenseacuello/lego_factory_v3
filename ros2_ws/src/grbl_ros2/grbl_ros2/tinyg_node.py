#!/usr/bin/env python3
"""
TinyG ROS2 Node
ROS2 interface for TinyG-based CNC machines (e.g., Bantam Tools Desktop CNC).
TinyG uses JSON for status reports unlike standard GRBL.

LEGO MCP Manufacturing System v7.0
"""

import asyncio
import json
import threading
from typing import Optional, Dict, Any, List
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

try:
    from lego_mcp_msgs.msg import EquipmentStatus
    from lego_mcp_msgs.action import MachineOperation
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class TinyGState(Enum):
    """TinyG machine states."""
    READY = 0
    ALARM = 1
    PROGRAM_STOP = 2
    PROGRAM_END = 3
    RUN = 4
    HOLD = 5
    PROBE = 6
    CYCLE = 7
    HOMING = 8
    JOG = 9
    INTERLOCK = 10
    SHUTDOWN = 11
    PANIC = 12


@dataclass
class TinyGStatus:
    """TinyG status report from JSON."""
    state: TinyGState = TinyGState.READY
    position: List[float] = None
    velocity: float = 0.0
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    line_number: int = 0
    buffer_available: int = 0

    def __post_init__(self):
        if self.position is None:
            self.position = [0.0, 0.0, 0.0, 0.0]  # X, Y, Z, A


class TinyGConnection:
    """
    Serial connection handler for TinyG devices.
    Handles JSON mode communication.
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
        self._json_mode = True

    def connect(self) -> bool:
        """Establish serial connection and configure TinyG."""
        if not SERIAL_AVAILABLE:
            return False

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            self._connected = True

            # Wake up and configure
            import time
            self._serial.write(b'\n')
            time.sleep(0.5)
            self._serial.flushInput()

            # Enable JSON mode
            self._send_json({'ej': 1})  # Enable JSON mode
            self._send_json({'jv': 4})  # JSON verbosity
            self._send_json({'sv': 1})  # Status report verbosity
            self._send_json({'si': 100})  # Status interval (ms)
            self._send_json({'qv': 2})  # Queue report verbosity

            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to TinyG: {e}")

    def disconnect(self):
        """Close serial connection."""
        if self._serial:
            self._serial.close()
            self._serial = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._serial is not None

    def _send_json(self, data: Dict) -> Dict:
        """Send JSON command and parse response."""
        if not self.is_connected:
            return {}

        cmd = json.dumps(data) + '\n'
        self._serial.write(cmd.encode())
        return self._read_json_response()

    def _read_json_response(self) -> Dict:
        """Read and parse JSON response."""
        try:
            line = self._serial.readline().decode().strip()
            if line and line.startswith('{'):
                return json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return {}

    def send_gcode(self, gcode: str) -> Dict:
        """Send G-code command wrapped in JSON."""
        if not self.is_connected:
            return {}

        with self._lock:
            return self._send_json({'gc': gcode})

    def request_status(self) -> Dict:
        """Request status report."""
        if not self.is_connected:
            return {}

        with self._lock:
            return self._send_json({'sr': None})

    def read_responses(self) -> List[Dict]:
        """Read any pending responses."""
        responses = []
        if self._serial and self._serial.in_waiting:
            with self._lock:
                while self._serial.in_waiting:
                    response = self._read_json_response()
                    if response:
                        responses.append(response)
        return responses


class TinyGNode(Node):
    """
    ROS2 node for TinyG-based CNC machines.
    Uses JSON protocol for communication.
    """

    def __init__(self):
        super().__init__('tinyg_node')

        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('x_max', 150.0)
        self.declare_parameter('y_max', 120.0)
        self.declare_parameter('z_max', 50.0)
        self.declare_parameter('status_rate_hz', 10.0)
        self.declare_parameter('simulate', False)

        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.x_max = self.get_parameter('x_max').value
        self.y_max = self.get_parameter('y_max').value
        self.z_max = self.get_parameter('z_max').value
        self.status_rate = self.get_parameter('status_rate_hz').value
        self.simulate = self.get_parameter('simulate').value

        # Connection
        self._connection: Optional[TinyGConnection] = None
        self._status = TinyGStatus()
        self._is_running = False
        self._queued_commands = 0

        # Callback group
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

        # Action server
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

        # Status timer
        self._status_timer = self.create_timer(
            1.0 / self.status_rate,
            self._poll_status,
            callback_group=self._cb_group
        )

        # Response processing timer
        self._response_timer = self.create_timer(
            0.01,  # 100 Hz
            self._process_responses,
            callback_group=self._cb_group
        )

        # Connect
        if not self.simulate:
            self._connect()
        else:
            self.get_logger().info("Running in simulation mode")

        self.get_logger().info(f"TinyG node initialized")

    def _connect(self):
        """Connect to TinyG device."""
        try:
            self._connection = TinyGConnection(
                self.serial_port,
                self.baud_rate
            )
            self._connection.connect()
            self.get_logger().info(f"Connected to TinyG at {self.serial_port}")
        except Exception as e:
            self.get_logger().error(f"Failed to connect: {e}")
            self._connection = None

    def _poll_status(self):
        """Poll TinyG for status."""
        if self.simulate:
            self._publish_simulated_status()
            return

        if not self._connection or not self._connection.is_connected:
            return

        try:
            response = self._connection.request_status()
            self._parse_status_response(response)
        except Exception as e:
            self.get_logger().warn(f"Status poll failed: {e}")

    def _process_responses(self):
        """Process any pending responses from TinyG."""
        if not self._connection or not self._connection.is_connected:
            return

        responses = self._connection.read_responses()
        for response in responses:
            self._handle_response(response)

    def _handle_response(self, response: Dict):
        """Handle TinyG JSON response."""
        if 'r' in response:
            # Command response
            r = response['r']
            if 'sr' in r:
                self._parse_status_response(r)
            if 'qr' in r:
                self._queued_commands = r['qr']

        if 'sr' in response:
            # Status report
            self._parse_status_response(response)

    def _parse_status_response(self, response: Dict):
        """Parse TinyG status report."""
        sr = response.get('sr', response)

        # State
        if 'stat' in sr:
            try:
                self._status.state = TinyGState(sr['stat'])
            except ValueError:
                pass

        # Position
        if 'posx' in sr:
            self._status.position[0] = sr['posx']
        if 'posy' in sr:
            self._status.position[1] = sr['posy']
        if 'posz' in sr:
            self._status.position[2] = sr['posz']
        if 'posa' in sr:
            self._status.position[3] = sr['posa']

        # Velocity and feed
        if 'vel' in sr:
            self._status.velocity = sr['vel']
        if 'feed' in sr:
            self._status.feed_rate = sr['feed']

        # Line number
        if 'line' in sr:
            self._status.line_number = sr['line']

        # Publish status
        self._publish_status()

    def _publish_status(self):
        """Publish current status."""
        # Position
        pos_msg = Point()
        pos_msg.x = self._status.position[0]
        pos_msg.y = self._status.position[1]
        pos_msg.z = self._status.position[2]
        self.position_pub.publish(pos_msg)

        # State
        state_msg = String()
        state_map = {
            TinyGState.READY: 'Idle',
            TinyGState.RUN: 'Run',
            TinyGState.HOLD: 'Hold',
            TinyGState.ALARM: 'Alarm',
            TinyGState.HOMING: 'Home',
        }
        state_msg.data = state_map.get(self._status.state, 'Unknown')
        self.state_pub.publish(state_msg)

        # Full status
        if MSGS_AVAILABLE:
            status_msg = EquipmentStatus()
            status_msg.header.stamp = self.get_clock().now().to_msg()
            status_msg.equipment_id = self.get_name()
            status_msg.equipment_type = 'cnc'
            status_msg.connected = self._connection is not None and self._connection.is_connected

            state_to_num = {
                TinyGState.READY: 1,
                TinyGState.RUN: 2,
                TinyGState.HOLD: 3,
                TinyGState.ALARM: 4,
            }
            status_msg.state = state_to_num.get(self._status.state, 0)
            status_msg.state_description = self._status.state.name

            status_msg.position = pos_msg
            status_msg.feed_rate = self._status.feed_rate

            self.status_pub.publish(status_msg)

    def _publish_simulated_status(self):
        """Publish simulated status."""
        pos_msg = Point()
        pos_msg.x = self._status.position[0]
        pos_msg.y = self._status.position[1]
        pos_msg.z = self._status.position[2]
        self.position_pub.publish(pos_msg)

        state_msg = String()
        state_msg.data = 'Run' if self._is_running else 'Idle'
        self.state_pub.publish(state_msg)

    def _on_command(self, msg: String):
        """Handle direct G-code command."""
        gcode = msg.data.strip()
        self.get_logger().info(f"Received command: {gcode}")

        if self.simulate:
            self.get_logger().info(f"[SIM] {gcode}")
            return

        if self._connection and self._connection.is_connected:
            response = self._connection.send_gcode(gcode)
            self.get_logger().info(f"Response: {response}")

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().warn("E-STOP activated!")
            self.feedhold()
            self.queue_flush()
            self._is_running = False

    def _goal_callback(self, goal_request):
        """Handle action goal."""
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancel."""
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute G-code program."""
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
                self.get_logger().error(f"Failed to read file: {e}")
                goal_handle.abort()
                result = MachineOperation.Result() if MSGS_AVAILABLE else None
                if result:
                    result.success = False
                    result.message = str(e)
                return result

        lines = [l.strip() for l in gcode.split('\n')
                if l.strip() and not l.strip().startswith(';') and not l.strip().startswith('(')]

        self._is_running = True
        total_lines = len(lines)
        feedback_msg = MachineOperation.Feedback() if MSGS_AVAILABLE else None

        try:
            for i, line in enumerate(lines):
                if goal_handle.is_cancel_requested:
                    self.feedhold()
                    goal_handle.canceled()
                    self._is_running = False
                    result = MachineOperation.Result() if MSGS_AVAILABLE else None
                    if result:
                        result.success = False
                        result.message = "Cancelled"
                    return result

                # Send G-code
                if self.simulate:
                    self.get_logger().debug(f"[SIM] {line}")
                    await asyncio.sleep(0.01)
                else:
                    if self._connection and self._connection.is_connected:
                        # Wait for queue space
                        while self._queued_commands > 24:
                            await asyncio.sleep(0.01)
                            self._process_responses()

                        response = self._connection.send_gcode(line)
                        self._handle_response(response)

                # Feedback
                if feedback_msg:
                    feedback_msg.current_line = i + 1
                    feedback_msg.total_lines = total_lines
                    feedback_msg.current_command = line
                    feedback_msg.progress_percent = (i + 1) / total_lines * 100
                    feedback_msg.position.x = self._status.position[0]
                    feedback_msg.position.y = self._status.position[1]
                    feedback_msg.position.z = self._status.position[2]
                    goal_handle.publish_feedback(feedback_msg)

            # Wait for completion
            if not self.simulate:
                while self._status.state == TinyGState.RUN:
                    await asyncio.sleep(0.1)
                    self._process_responses()

            goal_handle.succeed()
            self._is_running = False

            result = MachineOperation.Result() if MSGS_AVAILABLE else None
            if result:
                result.success = True
                result.message = f"Executed {total_lines} lines"
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
        """Home all axes."""
        if self._connection and self._connection.is_connected:
            self._connection.send_gcode('G28.2 X0 Y0 Z0')

    def feedhold(self):
        """Feedhold (pause)."""
        if self._connection and self._connection.is_connected:
            self._connection._send_json({'!': None})

    def cycle_start(self):
        """Resume from feedhold."""
        if self._connection and self._connection.is_connected:
            self._connection._send_json({'~': None})

    def queue_flush(self):
        """Flush motion queue."""
        if self._connection and self._connection.is_connected:
            self._connection._send_json({'%': None})

    def reset(self):
        """Reset TinyG."""
        if self._connection and self._connection.is_connected:
            self._connection._send_json({'^x': None})

    def destroy_node(self):
        """Cleanup."""
        if self._connection:
            self._connection.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = TinyGNode()

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
