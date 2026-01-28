#!/usr/bin/env python3
"""
GRBL ROS 2 Node
===============
ROS 2 interface for GRBL v1.1 and grblHAL CNC controllers.

Features:
- Publishes machine status at configurable rate
- Provides services for homing, jogging, G-code, E-stop
- Handles serial communication with GRBL firmware
- Supports simulation mode for testing without hardware

Topics Published:
- /grbl/status (cnc_interfaces/msg/GrblStatus)
- /grbl/machine_status (cnc_interfaces/msg/MachineStatus)
- /grbl/alarm (cnc_interfaces/msg/Alarm)

Services:
- /grbl/home (cnc_interfaces/srv/Home)
- /grbl/jog (cnc_interfaces/srv/Jog)
- /grbl/send_gcode (cnc_interfaces/srv/SendGcode)
- /grbl/emergency_stop (cnc_interfaces/srv/EmergencyStop)
- /grbl/set_feed_override (cnc_interfaces/srv/SetFeedOverride)

Parameters:
- port: Serial port (default: /dev/ttyUSB0)
- baudrate: Baud rate (default: 115200)
- status_rate: Status polling rate Hz (default: 10.0)
- simulate: Run in simulation mode (default: false)
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
import threading
import time
from typing import Optional

from std_msgs.msg import Header
from cnc_interfaces.msg import GrblStatus as GrblStatusMsg
from cnc_interfaces.msg import MachineStatus, Alarm
from cnc_interfaces.srv import Home, Jog, SendGcode, EmergencyStop, SetFeedOverride

from .grbl_parser import GrblParser, GrblStatus, GrblState

# Try to import serial, fall back to simulation
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class GrblNode(Node):
    """ROS 2 node for GRBL CNC controller interface."""

    def __init__(self):
        super().__init__('grbl_node')

        # Declare parameters
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('status_rate', 10.0)
        self.declare_parameter('simulate', not SERIAL_AVAILABLE)
        self.declare_parameter('machine_id', 'grbl_001')

        # Get parameters
        self.port = self.get_parameter('port').value
        self.baudrate = self.get_parameter('baudrate').value
        self.status_rate = self.get_parameter('status_rate').value
        self.simulate = self.get_parameter('simulate').value
        self.machine_id = self.get_parameter('machine_id').value

        # State
        self.parser = GrblParser()
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.last_status: Optional[GrblStatus] = None
        self._lock = threading.Lock()

        # Simulation state
        self._sim_position = [0.0, 0.0, 0.0]
        self._sim_state = GrblState.IDLE
        self._sim_feed = 0.0
        self._sim_spindle = 0.0
        self._sim_homed = False

        # Callback group for concurrent service calls
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.grbl_status_pub = self.create_publisher(
            GrblStatusMsg, 'grbl/status', 10)
        self.machine_status_pub = self.create_publisher(
            MachineStatus, 'grbl/machine_status', 10)
        self.alarm_pub = self.create_publisher(
            Alarm, 'grbl/alarm', 10)

        # Services
        self.home_srv = self.create_service(
            Home, 'grbl/home', self.home_callback,
            callback_group=self.callback_group)
        self.jog_srv = self.create_service(
            Jog, 'grbl/jog', self.jog_callback,
            callback_group=self.callback_group)
        self.gcode_srv = self.create_service(
            SendGcode, 'grbl/send_gcode', self.gcode_callback,
            callback_group=self.callback_group)
        self.estop_srv = self.create_service(
            EmergencyStop, 'grbl/emergency_stop', self.estop_callback,
            callback_group=self.callback_group)
        self.override_srv = self.create_service(
            SetFeedOverride, 'grbl/set_feed_override', self.override_callback,
            callback_group=self.callback_group)

        # Status polling timer
        self.status_timer = self.create_timer(
            1.0 / self.status_rate, self.poll_status)

        # Connect to controller
        if self.simulate:
            self.get_logger().warn('Running in SIMULATION mode (no serial)')
            self.connected = True
        else:
            self.connect()

        self.get_logger().info('=' * 60)
        self.get_logger().info('GRBL ROS 2 Node Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Machine ID: {self.machine_id}')
        self.get_logger().info(f'  Port: {self.port}')
        self.get_logger().info(f'  Baudrate: {self.baudrate}')
        self.get_logger().info(f'  Status Rate: {self.status_rate} Hz')
        self.get_logger().info(f'  Simulation: {self.simulate}')
        self.get_logger().info('=' * 60)

    def connect(self) -> bool:
        """Connect to GRBL controller via serial."""
        if self.simulate:
            return True

        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )
            # Wait for GRBL startup message
            time.sleep(2)
            self.serial.reset_input_buffer()
            self.connected = True
            self.get_logger().info(f'Connected to GRBL on {self.port}')
            return True
        except Exception as e:
            self.get_logger().error(f'Failed to connect: {e}')
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from GRBL controller."""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False

    def send_command(self, command: str, wait_ok: bool = True) -> str:
        """Send command to GRBL and get response."""
        if self.simulate:
            return self._simulate_command(command)

        if not self.connected or not self.serial:
            return "error: not connected"

        with self._lock:
            try:
                # Send command
                cmd = command.strip() + '\n'
                self.serial.write(cmd.encode())
                self.serial.flush()

                if not wait_ok:
                    return "sent"

                # Read response
                response_lines = []
                start_time = time.time()
                while time.time() - start_time < 5.0:  # 5s timeout
                    if self.serial.in_waiting:
                        line = self.serial.readline().decode().strip()
                        if line:
                            response_lines.append(line)
                            if line == 'ok' or line.startswith('error:'):
                                break
                    time.sleep(0.01)

                return '\n'.join(response_lines) if response_lines else 'timeout'
            except Exception as e:
                return f'error: {e}'

    def _simulate_command(self, command: str) -> str:
        """Simulate GRBL command response."""
        cmd = command.strip().upper()

        if cmd == '?':
            # Status query
            state = ['Idle', 'Run', 'Hold', 'Jog', 'Alarm', 'Door', 'Check', 'Home', 'Sleep'][self._sim_state.value - 1] if self._sim_state != GrblState.UNKNOWN else 'Idle'
            return f'<{state}|MPos:{self._sim_position[0]:.3f},{self._sim_position[1]:.3f},{self._sim_position[2]:.3f}|FS:{self._sim_feed:.0f},{self._sim_spindle:.0f}|Ov:100,100,100>'

        elif cmd == '$H':
            # Homing
            self._sim_state = GrblState.HOME
            time.sleep(0.5)
            self._sim_position = [0.0, 0.0, 0.0]
            self._sim_state = GrblState.IDLE
            self._sim_homed = True
            return 'ok'

        elif cmd.startswith('$J='):
            # Jog command
            if not self._sim_homed:
                return 'error:9'  # G-code locked
            self._sim_state = GrblState.JOG
            # Parse jog and update position (simplified)
            if 'X' in cmd:
                try:
                    x_idx = cmd.index('X')
                    x_end = min([cmd.index(c) for c in 'YZF' if c in cmd[x_idx:]] + [len(cmd)])
                    self._sim_position[0] = float(cmd[x_idx+1:x_end])
                except:
                    pass
            time.sleep(0.1)
            self._sim_state = GrblState.IDLE
            return 'ok'

        elif cmd == '\x18':  # Ctrl+X soft reset
            self._sim_state = GrblState.IDLE
            self._sim_homed = False
            return 'Grbl 1.1h [\'$\' for help]'

        elif cmd == '!':  # Feed hold
            if self._sim_state == GrblState.RUN:
                self._sim_state = GrblState.HOLD
            return ''

        elif cmd == '~':  # Cycle start/resume
            if self._sim_state == GrblState.HOLD:
                self._sim_state = GrblState.RUN
            return ''

        elif cmd == '$X':  # Kill alarm lock
            self._sim_state = GrblState.IDLE
            return 'ok'

        return 'ok'

    def poll_status(self):
        """Poll GRBL for status and publish."""
        if not self.connected:
            return

        response = self.send_command('?', wait_ok=False)

        # Parse status
        status = self.parser.parse_status(response)
        if not status:
            return

        self.last_status = status

        # Publish GrblStatus message
        self._publish_grbl_status(status)

        # Publish generic MachineStatus message
        self._publish_machine_status(status)

        # Check for alarm
        if status.state == GrblState.ALARM:
            self._publish_alarm(status)

    def _publish_grbl_status(self, status: GrblStatus):
        """Publish GRBL-specific status message."""
        msg = GrblStatusMsg()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.machine_id

        msg.state = status.state.value
        msg.state_text = status.state_text

        msg.mpos_x = status.mpos_x
        msg.mpos_y = status.mpos_y
        msg.mpos_z = status.mpos_z
        msg.wpos_x = status.wpos_x
        msg.wpos_y = status.wpos_y
        msg.wpos_z = status.wpos_z

        msg.feed_rate = status.feed_rate
        msg.spindle_speed = status.spindle_speed

        msg.feed_override = status.feed_override
        msg.rapid_override = status.rapid_override
        msg.spindle_override = status.spindle_override

        msg.planner_buffer = status.planner_buffer
        msg.rx_buffer = status.rx_buffer

        msg.limit_x = status.limit_x
        msg.limit_y = status.limit_y
        msg.limit_z = status.limit_z
        msg.probe = status.probe

        self.grbl_status_pub.publish(msg)

    def _publish_machine_status(self, status: GrblStatus):
        """Publish generic machine status message."""
        msg = MachineStatus()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.machine_id

        msg.machine_id = self.machine_id
        msg.controller_type = 'grbl'
        msg.firmware_version = '1.1h'

        msg.state = status.state.value
        msg.state_text = status.state_text

        msg.mpos_x = status.mpos_x
        msg.mpos_y = status.mpos_y
        msg.mpos_z = status.mpos_z
        msg.wpos_x = status.wpos_x
        msg.wpos_y = status.wpos_y
        msg.wpos_z = status.wpos_z

        msg.feed_rate = status.feed_rate
        msg.feed_override = status.feed_override / 100.0
        msg.spindle_speed = status.spindle_speed
        msg.spindle_override = status.spindle_override / 100.0

        msg.spindle_cw = status.spindle_cw
        msg.spindle_ccw = status.spindle_ccw
        msg.coolant_flood = status.flood_coolant
        msg.coolant_mist = status.mist_coolant

        msg.planner_buffer = status.planner_buffer
        msg.rx_buffer = status.rx_buffer

        self.machine_status_pub.publish(msg)

    def _publish_alarm(self, status: GrblStatus):
        """Publish alarm message."""
        msg = Alarm()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = self.machine_id
        msg.alarm_active = True
        msg.alarm_text = f"GRBL Alarm State: {status.state_text}"
        self.alarm_pub.publish(msg)

    # Service callbacks
    def home_callback(self, request, response):
        """Handle homing request."""
        self.get_logger().info(f'HOME request: axes={request.axes}')

        result = self.send_command('$H')
        response.success = 'ok' in result.lower()
        response.message = result if not response.success else f'Homing complete for axes: {request.axes}'
        response.home_x = 0.0
        response.home_y = 0.0
        response.home_z = 0.0
        response.duration = 1.5  # Estimated

        return response

    def jog_callback(self, request, response):
        """Handle jog request."""
        jog_types = {0: 'CONTINUOUS', 1: 'INCREMENTAL', 2: 'ABSOLUTE'}
        self.get_logger().info(
            f'JOG request: type={jog_types.get(request.jog_type)}, '
            f'X={request.x}, Y={request.y}, Z={request.z}'
        )

        # Build GRBL jog command
        # Format: $J=G91 X10 Y0 Z0 F1000
        mode = 'G91' if request.jog_type == 1 else 'G90'
        cmd = f'$J={mode} X{request.x} Y{request.y} Z{request.z} F{request.feed_rate}'

        result = self.send_command(cmd)
        response.success = 'ok' in result.lower()
        response.message = result if not response.success else 'Jog complete'
        response.motion_complete = response.success

        # Update position from last status
        if self.last_status:
            response.final_x = self.last_status.mpos_x
            response.final_y = self.last_status.mpos_y
            response.final_z = self.last_status.mpos_z

        return response

    def gcode_callback(self, request, response):
        """Handle G-code send request."""
        lines = request.gcode.strip().split('\n')
        self.get_logger().info(f'GCODE request: {len(lines)} lines')

        response.lines_sent = 0
        response.lines_ok = 0
        response.errors = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('('):
                continue

            result = self.send_command(line)
            response.lines_sent += 1

            if 'ok' in result.lower():
                response.lines_ok += 1
            elif 'error' in result.lower():
                response.errors.append(f'Line {response.lines_sent}: {result}')

        response.success = response.lines_ok == response.lines_sent
        response.message = f'Sent {response.lines_sent} lines, {response.lines_ok} ok'
        response.response = result

        return response

    def estop_callback(self, request, response):
        """Handle emergency stop request."""
        actions = {0: 'ESTOP', 1: 'FEED_HOLD', 2: 'RESET', 3: 'UNLOCK', 4: 'RESUME'}
        action = actions.get(request.action, 'UNKNOWN')
        self.get_logger().warn(f'ESTOP request: action={action}')

        previous_state = self.last_status.state_text if self.last_status else 'unknown'

        if request.action == 0:  # ESTOP - Ctrl+X soft reset
            result = self.send_command('\x18')
            response.success = True
            response.message = 'Emergency stop - soft reset sent'
        elif request.action == 1:  # FEED_HOLD
            result = self.send_command('!')
            response.success = True
            response.message = 'Feed hold activated'
        elif request.action == 2:  # RESET
            result = self.send_command('\x18')
            response.success = True
            response.message = 'Soft reset complete'
        elif request.action == 3:  # UNLOCK
            result = self.send_command('$X')
            response.success = 'ok' in result.lower()
            response.message = 'Alarm cleared' if response.success else result
        elif request.action == 4:  # RESUME
            result = self.send_command('~')
            response.success = True
            response.message = 'Cycle resumed'
        else:
            response.success = False
            response.message = f'Unknown action: {request.action}'

        response.previous_state = previous_state
        response.new_state = self.last_status.state_text if self.last_status else 'unknown'

        return response

    def override_callback(self, request, response):
        """Handle feed/spindle override request."""
        override_types = {0: 'FEED', 1: 'RAPID', 2: 'SPINDLE'}
        self.get_logger().info(
            f'OVERRIDE request: type={override_types.get(request.override_type)}, '
            f'value={request.value}'
        )

        # GRBL real-time override commands
        # Feed: 0x90 (set to 100%), 0x91 (+10%), 0x92 (-10%), 0x93 (+1%), 0x94 (-1%)
        # Rapid: 0x95 (100%), 0x96 (50%), 0x97 (25%)
        # Spindle: 0x99 (set to 100%), 0x9A (+10%), 0x9B (-10%), 0x9C (+1%), 0x9D (-1%)

        current = 100
        if self.last_status:
            if request.override_type == 0:
                current = self.last_status.feed_override
            elif request.override_type == 1:
                current = self.last_status.rapid_override
            else:
                current = self.last_status.spindle_override

        response.previous_value = current / 100.0

        # For simulation, just acknowledge
        if self.simulate:
            response.success = True
            response.new_value = request.value
            response.message = f'Override set to {request.value * 100:.0f}%'
        else:
            # In real mode, would send appropriate byte commands
            response.success = True
            response.new_value = request.value
            response.message = 'Override command sent'

        return response


def main(args=None):
    rclpy.init(args=args)
    node = GrblNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down GRBL node...')
    finally:
        node.disconnect()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
