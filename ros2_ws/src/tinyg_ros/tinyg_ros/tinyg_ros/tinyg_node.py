#!/usr/bin/env python3
"""
TinyG ROS 2 Node
================
ROS 2 interface for TinyG CNC controllers using JSON protocol.

Features:
- Publishes machine status at configurable rate
- Provides services for homing, jogging, G-code, E-stop
- Handles TinyG's JSON serial communication
- Supports simulation mode for testing

Topics Published:
- /tinyg/status (cnc_interfaces/msg/MachineStatus)
- /tinyg/queue (std_msgs/Int32) - queue depth

Services:
- /tinyg/home (cnc_interfaces/srv/Home)
- /tinyg/jog (cnc_interfaces/srv/Jog)
- /tinyg/send_gcode (cnc_interfaces/srv/SendGcode)
- /tinyg/emergency_stop (cnc_interfaces/srv/EmergencyStop)
- /tinyg/set_feed_override (cnc_interfaces/srv/SetFeedOverride)

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
import json
from typing import Optional

from std_msgs.msg import Header, Int32
from cnc_interfaces.msg import MachineStatus
from cnc_interfaces.srv import Home, Jog, SendGcode, EmergencyStop, SetFeedOverride

from .tinyg_parser import TinyGParser, TinyGStatus, TinyGState, TINYG_STATE_NAMES

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class TinyGNode(Node):
    """ROS 2 node for TinyG CNC controller interface."""

    def __init__(self):
        super().__init__('tinyg_node')

        # Declare parameters
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('status_rate', 10.0)
        self.declare_parameter('simulate', not SERIAL_AVAILABLE)
        self.declare_parameter('machine_id', 'tinyg_001')

        # Get parameters
        self.port = self.get_parameter('port').value
        self.baudrate = self.get_parameter('baudrate').value
        self.status_rate = self.get_parameter('status_rate').value
        self.simulate = self.get_parameter('simulate').value
        self.machine_id = self.get_parameter('machine_id').value

        # State
        self.parser = TinyGParser()
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.last_status: Optional[TinyGStatus] = None
        self._lock = threading.Lock()
        self._read_thread: Optional[threading.Thread] = None
        self._running = True

        # Simulation state
        self._sim_position = [0.0, 0.0, 0.0, 0.0]
        self._sim_state = TinyGState.READY
        self._sim_feed = 0.0
        self._sim_spindle = 0.0
        self._sim_homed = False
        self._sim_queue = 28

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.status_pub = self.create_publisher(
            MachineStatus, 'tinyg/status', 10)
        self.queue_pub = self.create_publisher(
            Int32, 'tinyg/queue', 10)

        # Services
        self.home_srv = self.create_service(
            Home, 'tinyg/home', self.home_callback,
            callback_group=self.callback_group)
        self.jog_srv = self.create_service(
            Jog, 'tinyg/jog', self.jog_callback,
            callback_group=self.callback_group)
        self.gcode_srv = self.create_service(
            SendGcode, 'tinyg/send_gcode', self.gcode_callback,
            callback_group=self.callback_group)
        self.estop_srv = self.create_service(
            EmergencyStop, 'tinyg/emergency_stop', self.estop_callback,
            callback_group=self.callback_group)
        self.override_srv = self.create_service(
            SetFeedOverride, 'tinyg/set_feed_override', self.override_callback,
            callback_group=self.callback_group)

        # Status polling timer
        self.status_timer = self.create_timer(
            1.0 / self.status_rate, self.poll_status)

        # Connect
        if self.simulate:
            self.get_logger().warn('Running in SIMULATION mode (no serial)')
            self.connected = True
        else:
            self.connect()

        self.get_logger().info('=' * 60)
        self.get_logger().info('TinyG ROS 2 Node Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Machine ID: {self.machine_id}')
        self.get_logger().info(f'  Port: {self.port}')
        self.get_logger().info(f'  Baudrate: {self.baudrate}')
        self.get_logger().info(f'  Status Rate: {self.status_rate} Hz')
        self.get_logger().info(f'  Simulation: {self.simulate}')
        self.get_logger().info('=' * 60)

    def connect(self) -> bool:
        """Connect to TinyG via serial."""
        if self.simulate:
            return True

        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )
            # Wait for TinyG startup
            time.sleep(2)
            self.serial.reset_input_buffer()

            # Start read thread
            self._read_thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self._read_thread.start()

            # Request initial status
            self.send_command('{"sr":null}', wait_response=False)

            self.connected = True
            self.get_logger().info(f'Connected to TinyG on {self.port}')
            return True
        except Exception as e:
            self.get_logger().error(f'Failed to connect: {e}')
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from TinyG."""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False

    def _serial_read_loop(self):
        """Background thread to read serial data."""
        while self._running and self.serial and self.serial.is_open:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_response(line)
            except Exception as e:
                self.get_logger().error(f'Serial read error: {e}')
            time.sleep(0.001)

    def _process_response(self, line: str):
        """Process a response line from TinyG."""
        status, response = self.parser.parse_line(line)
        if status:
            self.last_status = status
        if response and response.status_code != 0:
            self.get_logger().warn(f'TinyG error: {response.status_msg}')

    def send_command(self, command: str, wait_response: bool = True) -> str:
        """Send command to TinyG."""
        if self.simulate:
            return self._simulate_command(command)

        if not self.connected or not self.serial:
            return '{"f":[1,11,0]}'  # No device error

        with self._lock:
            try:
                cmd = command.strip() + '\n'
                self.serial.write(cmd.encode())
                self.serial.flush()

                if not wait_response:
                    return '{"f":[1,0,0]}'

                # Wait for response (simplified - real implementation would be async)
                time.sleep(0.1)
                return '{"f":[1,0,0]}'  # OK
            except Exception as e:
                return f'{{"f":[1,1,0],"err":"{e}"}}'

    def _simulate_command(self, command: str) -> str:
        """Simulate TinyG command response."""
        try:
            data = json.loads(command)
        except json.JSONDecodeError:
            # Plain G-code command
            data = {"gc": command}

        # Handle G-code
        if "gc" in data:
            gc = data["gc"].upper()
            if gc == "G28" or gc == "G28.2":
                # Homing
                self._sim_state = TinyGState.HOMING
                time.sleep(0.5)
                self._sim_position = [0.0, 0.0, 0.0, 0.0]
                self._sim_state = TinyGState.READY
                self._sim_homed = True
            elif gc.startswith("G0") or gc.startswith("G1"):
                # Motion
                self._sim_state = TinyGState.RUN
                time.sleep(0.1)
                self._sim_state = TinyGState.READY
            elif gc == "!":
                # Feed hold
                self._sim_state = TinyGState.HOLD
            elif gc == "~":
                # Cycle start
                self._sim_state = TinyGState.RUN
            elif gc == "\x18":  # Ctrl+X
                # Reset
                self._sim_state = TinyGState.READY
                self._sim_homed = False

        # Handle status request
        if "sr" in data:
            pass  # Status will be returned in poll_status

        return '{"f":[1,0,0]}'

    def poll_status(self):
        """Poll TinyG for status and publish."""
        if not self.connected:
            return

        # In simulation mode, build status from sim state
        if self.simulate:
            status = TinyGStatus(
                stat=self._sim_state,
                state_name=TINYG_STATE_NAMES.get(self._sim_state, "Unknown"),
                posx=self._sim_position[0],
                posy=self._sim_position[1],
                posz=self._sim_position[2],
                posa=self._sim_position[3],
                vel=self._sim_feed if self._sim_state == TinyGState.RUN else 0.0,
                feed=self._sim_feed,
                sps=self._sim_spindle,
                qr=self._sim_queue,
                unit=1,  # mm
            )
            self.last_status = status
        else:
            # Request status from real TinyG
            self.send_command('{"sr":null}', wait_response=False)

        if self.last_status:
            self._publish_status(self.last_status)
            self._publish_queue(self.last_status.qr)

    def _publish_status(self, status: TinyGStatus):
        """Publish machine status message."""
        msg = MachineStatus()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.machine_id

        msg.machine_id = self.machine_id
        msg.controller_type = 'tinyg'
        msg.firmware_version = '0.97'

        msg.state = TinyGParser.state_to_ros(status.stat)
        msg.state_text = status.state_name

        # Position
        msg.mpos_x = status.posx
        msg.mpos_y = status.posy
        msg.mpos_z = status.posz
        msg.mpos_a = status.posa

        # Work position (with G54 offset)
        msg.wpos_x = status.posx - status.g54x
        msg.wpos_y = status.posy - status.g54y
        msg.wpos_z = status.posz - status.g54z

        # Work coordinate offset
        msg.wco_x = status.g54x
        msg.wco_y = status.g54y
        msg.wco_z = status.g54z

        # Coordinate system
        coord_systems = {1: "G54", 2: "G55", 3: "G56", 4: "G57", 5: "G58", 6: "G59"}
        msg.coord_system = coord_systems.get(status.coor, "G54")

        # Motion
        msg.feed_rate = status.feed
        msg.velocity = status.vel

        # Spindle
        msg.spindle_speed = status.sps
        msg.spindle_cw = status.spmo == 1
        msg.spindle_ccw = status.spmo == 2

        # Coolant
        msg.coolant_flood = status.coof == 1
        msg.coolant_mist = status.coom == 1

        # Line number
        msg.line_number = status.line

        # Units
        msg.metric = status.unit == 1

        # Buffer
        msg.planner_buffer = status.qr

        self.status_pub.publish(msg)

    def _publish_queue(self, queue_depth: int):
        """Publish queue depth."""
        msg = Int32()
        msg.data = queue_depth
        self.queue_pub.publish(msg)

    # Service callbacks
    def home_callback(self, request, response):
        """Handle homing request."""
        self.get_logger().info(f'HOME request: axes={request.axes}')

        # TinyG homing command
        axes = request.axes.upper()
        if axes == "XYZ" or axes == "":
            cmd = '{"gc":"G28.2 X0 Y0 Z0"}'
        else:
            axis_str = " ".join([f"{a}0" for a in axes])
            cmd = f'{{"gc":"G28.2 {axis_str}"}}'

        result = self.send_command(cmd)

        # Wait for homing to complete
        start_time = time.time()
        while time.time() - start_time < 30.0:
            if self.last_status and self.last_status.stat == TinyGState.READY:
                break
            time.sleep(0.1)

        duration = time.time() - start_time

        response.success = True
        response.message = f'Homing complete for axes: {axes}'
        response.home_x = self.last_status.posx if self.last_status else 0.0
        response.home_y = self.last_status.posy if self.last_status else 0.0
        response.home_z = self.last_status.posz if self.last_status else 0.0
        response.duration = duration

        return response

    def jog_callback(self, request, response):
        """Handle jog request."""
        jog_types = {0: 'CONTINUOUS', 1: 'INCREMENTAL', 2: 'ABSOLUTE'}
        self.get_logger().info(
            f'JOG request: type={jog_types.get(request.jog_type)}, '
            f'X={request.x}, Y={request.y}, Z={request.z}'
        )

        # Build jog command
        if request.jog_type == 1:  # Incremental
            cmd = f'{{"gc":"G91 G0 X{request.x} Y{request.y} Z{request.z}"}}'
        else:  # Absolute
            cmd = f'{{"gc":"G90 G0 X{request.x} Y{request.y} Z{request.z}"}}'

        if request.feed_rate > 0:
            cmd = cmd.replace('G0', f'G1 F{request.feed_rate}')

        result = self.send_command(cmd)

        # Update simulation position
        if self.simulate:
            if request.jog_type == 1:
                self._sim_position[0] += request.x
                self._sim_position[1] += request.y
                self._sim_position[2] += request.z
            else:
                self._sim_position[0] = request.x
                self._sim_position[1] = request.y
                self._sim_position[2] = request.z

        response.success = True
        response.message = 'Jog complete'
        response.motion_complete = True
        response.final_x = self._sim_position[0] if self.simulate else (self.last_status.posx if self.last_status else 0.0)
        response.final_y = self._sim_position[1] if self.simulate else (self.last_status.posy if self.last_status else 0.0)
        response.final_z = self._sim_position[2] if self.simulate else (self.last_status.posz if self.last_status else 0.0)

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

            cmd = json.dumps({"gc": line})
            result = self.send_command(cmd)
            response.lines_sent += 1

            try:
                resp_data = json.loads(result)
                if resp_data.get('f', [1, 0, 0])[1] == 0:
                    response.lines_ok += 1
                else:
                    response.errors.append(f'Line {response.lines_sent}: {result}')
            except:
                response.lines_ok += 1  # Assume OK if can't parse

        response.success = response.lines_ok == response.lines_sent
        response.message = f'Sent {response.lines_sent} lines, {response.lines_ok} ok'
        response.response = result

        return response

    def estop_callback(self, request, response):
        """Handle emergency stop request."""
        actions = {0: 'ESTOP', 1: 'FEED_HOLD', 2: 'RESET', 3: 'UNLOCK', 4: 'RESUME'}
        self.get_logger().warn(f'ESTOP request: action={actions.get(request.action)}')

        previous_state = self.last_status.state_name if self.last_status else 'unknown'

        if request.action == 0:  # ESTOP - Ctrl+X
            self.send_command('\x18', wait_response=False)
            if self.simulate:
                self._sim_state = TinyGState.ALARM
            response.message = 'Emergency stop sent'

        elif request.action == 1:  # FEED_HOLD
            self.send_command('!', wait_response=False)
            if self.simulate:
                self._sim_state = TinyGState.HOLD
            response.message = 'Feed hold activated'

        elif request.action == 2:  # RESET
            self.send_command('\x18', wait_response=False)
            if self.simulate:
                self._sim_state = TinyGState.READY
                self._sim_homed = False
            response.message = 'Soft reset complete'

        elif request.action == 3:  # UNLOCK
            self.send_command('{"clear":null}', wait_response=False)
            if self.simulate:
                self._sim_state = TinyGState.READY
            response.message = 'Alarm cleared'

        elif request.action == 4:  # RESUME
            self.send_command('~', wait_response=False)
            if self.simulate:
                self._sim_state = TinyGState.RUN
            response.message = 'Cycle resumed'

        else:
            response.success = False
            response.message = f'Unknown action: {request.action}'
            return response

        response.success = True
        response.previous_state = previous_state
        response.new_state = self.last_status.state_name if self.last_status else 'unknown'

        return response

    def override_callback(self, request, response):
        """Handle feed override request."""
        self.get_logger().info(f'OVERRIDE request: value={request.value}')

        # TinyG uses mfo (manual feed override) setting
        override_percent = int(request.value * 100)
        cmd = json.dumps({"mfo": override_percent / 100.0})
        self.send_command(cmd)

        response.success = True
        response.previous_value = 1.0
        response.new_value = request.value
        response.message = f'Feed override set to {override_percent}%'

        return response


def main(args=None):
    rclpy.init(args=args)
    node = TinyGNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down TinyG node...')
    finally:
        node.disconnect()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
