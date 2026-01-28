#!/usr/bin/env python3
"""
LEGO MCP GRBL Simulator Node

Simulates GRBL-based equipment (TinyG CNC, MKS Laser) for testing.
Responds to G-code commands and publishes simulated status.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import asyncio
import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from sensor_msgs.msg import JointState


class MachineState(Enum):
    """GRBL machine states."""
    IDLE = 0
    RUN = 1
    HOLD = 2
    JOG = 3
    ALARM = 4
    DOOR = 5
    CHECK = 6
    HOME = 7
    SLEEP = 8


@dataclass
class SimulatedPosition:
    """Simulated machine position."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0  # Optional 4th axis

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z, self.a]

    def distance_to(self, other: 'SimulatedPosition') -> float:
        return math.sqrt(
            (self.x - other.x)**2 +
            (self.y - other.y)**2 +
            (self.z - other.z)**2
        )


@dataclass
class GCodeCommand:
    """Parsed G-code command."""
    code: str
    params: Dict[str, float] = field(default_factory=dict)
    line_number: Optional[int] = None
    comment: Optional[str] = None


class GRBLSimulatorNode(Node):
    """
    Simulates GRBL/TinyG CNC or Laser for testing.

    Features:
    - Parses and executes G-code commands
    - Simulates motion with configurable feed rates
    - Publishes position feedback at configurable rate
    - Supports TinyG JSON mode
    """

    def __init__(self):
        super().__init__('grbl_simulator')

        # Parameters
        self.declare_parameter('machine_type', 'grbl')  # 'grbl' or 'tinyg'
        self.declare_parameter('machine_name', 'cnc_sim')
        self.declare_parameter('max_feedrate', 5000.0)  # mm/min
        self.declare_parameter('max_travel_x', 300.0)  # mm
        self.declare_parameter('max_travel_y', 200.0)
        self.declare_parameter('max_travel_z', 100.0)
        self.declare_parameter('status_rate', 10.0)  # Hz
        self.declare_parameter('simulate_delays', True)

        self._machine_type = self.get_parameter('machine_type').value
        self._machine_name = self.get_parameter('machine_name').value
        self._max_feedrate = self.get_parameter('max_feedrate').value
        self._max_travel = {
            'x': self.get_parameter('max_travel_x').value,
            'y': self.get_parameter('max_travel_y').value,
            'z': self.get_parameter('max_travel_z').value,
        }
        self._status_rate = self.get_parameter('status_rate').value
        self._simulate_delays = self.get_parameter('simulate_delays').value

        # Machine state
        self._state = MachineState.IDLE
        self._position = SimulatedPosition()
        self._target_position = SimulatedPosition()
        self._feedrate = 1000.0  # mm/min
        self._spindle_speed = 0
        self._spindle_on = False
        self._coolant_on = False
        self._units_mm = True  # G21 = mm, G20 = inches
        self._absolute_mode = True  # G90 = absolute, G91 = incremental
        self._is_moving = False
        self._gcode_queue: List[GCodeCommand] = []
        self._current_line = 0
        self._total_lines = 0

        # Callback group for concurrent operations
        self._cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.create_subscription(
            String,
            f'/{self._machine_name}/gcode',
            self._on_gcode,
            10,
            callback_group=self._cb_group
        )

        self.create_subscription(
            String,
            f'/{self._machine_name}/command',
            self._on_command,
            10,
            callback_group=self._cb_group
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            f'/{self._machine_name}/status',
            10
        )

        self._position_pub = self.create_publisher(
            JointState,
            f'/{self._machine_name}/position',
            10
        )

        self._response_pub = self.create_publisher(
            String,
            f'/{self._machine_name}/response',
            10
        )

        # Status timer
        self._status_timer = self.create_timer(
            1.0 / self._status_rate,
            self._publish_status,
            callback_group=self._cb_group
        )

        # Motion simulation timer
        self._motion_timer = self.create_timer(
            0.01,  # 100Hz motion update
            self._update_motion,
            callback_group=self._cb_group
        )

        self.get_logger().info(
            f"GRBL Simulator initialized: {self._machine_name} ({self._machine_type})"
        )

    def _on_gcode(self, msg: String):
        """Handle incoming G-code."""
        gcode_text = msg.data.strip()

        if not gcode_text:
            return

        # Parse G-code lines
        lines = gcode_text.split('\n')
        self._total_lines = len(lines)
        self._current_line = 0

        for line in lines:
            cmd = self._parse_gcode_line(line.strip())
            if cmd:
                self._gcode_queue.append(cmd)

        # Start processing if idle
        if self._state == MachineState.IDLE and self._gcode_queue:
            self._state = MachineState.RUN
            self._process_next_command()

    def _on_command(self, msg: String):
        """Handle control commands (pause, resume, stop, home)."""
        try:
            data = json.loads(msg.data)
            command = data.get('command', '')

            if command == 'pause' or command == '!':
                self._state = MachineState.HOLD
                self._publish_response('ok', 'Paused')

            elif command == 'resume' or command == '~':
                if self._state == MachineState.HOLD:
                    self._state = MachineState.RUN
                    self._publish_response('ok', 'Resumed')

            elif command == 'stop' or command == '\x18':  # Ctrl-X
                self._gcode_queue.clear()
                self._state = MachineState.IDLE
                self._is_moving = False
                self._publish_response('ok', 'Stopped')

            elif command == 'home' or command == '$H':
                self._start_homing()

            elif command == 'reset' or command == '\x18':
                self._reset_machine()

            elif command == 'status' or command == '?':
                self._publish_status()

        except json.JSONDecodeError:
            # Try as raw GRBL command
            self._handle_raw_command(msg.data)

    def _parse_gcode_line(self, line: str) -> Optional[GCodeCommand]:
        """Parse a single G-code line."""
        if not line or line.startswith(';') or line.startswith('('):
            return None

        # Remove comments
        comment = None
        if ';' in line:
            line, comment = line.split(';', 1)
            comment = comment.strip()
        if '(' in line and ')' in line:
            start = line.index('(')
            end = line.index(')')
            comment = line[start+1:end]
            line = line[:start] + line[end+1:]

        line = line.strip().upper()
        if not line:
            return None

        # Extract line number
        line_number = None
        if line.startswith('N'):
            parts = line.split(maxsplit=1)
            try:
                line_number = int(parts[0][1:])
                line = parts[1] if len(parts) > 1 else ''
            except ValueError:
                pass

        # Parse command and parameters
        params = {}
        code = ''

        tokens = line.split()
        if tokens:
            code = tokens[0]
            for token in tokens[1:]:
                if token and token[0].isalpha():
                    try:
                        params[token[0]] = float(token[1:])
                    except ValueError:
                        pass

        # Also parse inline parameters (e.g., G1X10Y20)
        if not params and len(code) > 2:
            i = 0
            while i < len(line):
                if line[i].isalpha():
                    letter = line[i]
                    i += 1
                    num_str = ''
                    while i < len(line) and (line[i].isdigit() or line[i] in '.-'):
                        num_str += line[i]
                        i += 1
                    if num_str:
                        if letter in ['G', 'M']:
                            code = f"{letter}{num_str}"
                        else:
                            try:
                                params[letter] = float(num_str)
                            except ValueError:
                                pass
                else:
                    i += 1

        return GCodeCommand(code=code, params=params, line_number=line_number, comment=comment)

    def _process_next_command(self):
        """Process the next G-code command in queue."""
        if not self._gcode_queue or self._state != MachineState.RUN:
            if not self._gcode_queue:
                self._state = MachineState.IDLE
            return

        cmd = self._gcode_queue.pop(0)
        self._current_line += 1

        self.get_logger().debug(f"Executing: {cmd.code} {cmd.params}")

        # Process command
        if cmd.code.startswith('G'):
            self._process_g_code(cmd)
        elif cmd.code.startswith('M'):
            self._process_m_code(cmd)
        else:
            self._publish_response('error', f"Unknown command: {cmd.code}")
            self._process_next_command()

    def _process_g_code(self, cmd: GCodeCommand):
        """Process G-code commands."""
        code = cmd.code
        params = cmd.params

        if code in ['G0', 'G00']:  # Rapid move
            self._start_move(params, rapid=True)

        elif code in ['G1', 'G01']:  # Linear move
            feedrate = params.get('F', self._feedrate)
            self._feedrate = min(feedrate, self._max_feedrate)
            self._start_move(params, rapid=False)

        elif code in ['G2', 'G02', 'G3', 'G03']:  # Arc move
            # Simplified: treat as linear move to endpoint
            self._start_move(params, rapid=False)

        elif code in ['G4', 'G04']:  # Dwell
            dwell_time = params.get('P', 0) / 1000.0  # P is in ms
            if params.get('S'):
                dwell_time = params.get('S', 0)  # S is in seconds
            self._start_dwell(dwell_time)

        elif code == 'G20':  # Inches
            self._units_mm = False
            self._publish_response('ok')
            self._process_next_command()

        elif code == 'G21':  # Millimeters
            self._units_mm = True
            self._publish_response('ok')
            self._process_next_command()

        elif code == 'G28':  # Home
            self._start_homing()

        elif code == 'G90':  # Absolute positioning
            self._absolute_mode = True
            self._publish_response('ok')
            self._process_next_command()

        elif code == 'G91':  # Incremental positioning
            self._absolute_mode = False
            self._publish_response('ok')
            self._process_next_command()

        elif code == 'G92':  # Set position
            if 'X' in params:
                self._position.x = params['X']
            if 'Y' in params:
                self._position.y = params['Y']
            if 'Z' in params:
                self._position.z = params['Z']
            self._publish_response('ok')
            self._process_next_command()

        else:
            self._publish_response('ok', f"Ignored: {code}")
            self._process_next_command()

    def _process_m_code(self, cmd: GCodeCommand):
        """Process M-code commands."""
        code = cmd.code
        params = cmd.params

        if code in ['M0', 'M00', 'M1', 'M01']:  # Program pause
            self._state = MachineState.HOLD
            self._publish_response('ok', 'Program paused')

        elif code in ['M2', 'M02', 'M30']:  # Program end
            self._gcode_queue.clear()
            self._state = MachineState.IDLE
            self._spindle_on = False
            self._coolant_on = False
            self._publish_response('ok', 'Program complete')

        elif code in ['M3', 'M03']:  # Spindle on CW
            self._spindle_speed = int(params.get('S', 10000))
            self._spindle_on = True
            self._publish_response('ok', f'Spindle ON: {self._spindle_speed} RPM')
            self._process_next_command()

        elif code in ['M4', 'M04']:  # Spindle on CCW
            self._spindle_speed = int(params.get('S', 10000))
            self._spindle_on = True
            self._publish_response('ok', f'Spindle ON CCW: {self._spindle_speed} RPM')
            self._process_next_command()

        elif code in ['M5', 'M05']:  # Spindle off
            self._spindle_on = False
            self._spindle_speed = 0
            self._publish_response('ok', 'Spindle OFF')
            self._process_next_command()

        elif code in ['M7', 'M07']:  # Mist coolant on
            self._coolant_on = True
            self._publish_response('ok', 'Mist coolant ON')
            self._process_next_command()

        elif code in ['M8', 'M08']:  # Flood coolant on
            self._coolant_on = True
            self._publish_response('ok', 'Flood coolant ON')
            self._process_next_command()

        elif code in ['M9', 'M09']:  # Coolant off
            self._coolant_on = False
            self._publish_response('ok', 'Coolant OFF')
            self._process_next_command()

        elif code == 'M106':  # Fan on (laser power for MKS)
            power = int(params.get('S', 255))
            self._spindle_speed = power
            self._spindle_on = True
            self._publish_response('ok', f'Laser power: {power}')
            self._process_next_command()

        elif code == 'M107':  # Fan off (laser off)
            self._spindle_on = False
            self._spindle_speed = 0
            self._publish_response('ok', 'Laser OFF')
            self._process_next_command()

        else:
            self._publish_response('ok', f"Ignored: {code}")
            self._process_next_command()

    def _start_move(self, params: Dict[str, float], rapid: bool = False):
        """Start a move to target position."""
        # Calculate target position
        target = SimulatedPosition(
            x=self._position.x,
            y=self._position.y,
            z=self._position.z,
            a=self._position.a
        )

        # Unit conversion
        scale = 1.0 if self._units_mm else 25.4

        if self._absolute_mode:
            if 'X' in params:
                target.x = params['X'] * scale
            if 'Y' in params:
                target.y = params['Y'] * scale
            if 'Z' in params:
                target.z = params['Z'] * scale
            if 'A' in params:
                target.a = params['A']
        else:
            if 'X' in params:
                target.x += params['X'] * scale
            if 'Y' in params:
                target.y += params['Y'] * scale
            if 'Z' in params:
                target.z += params['Z'] * scale
            if 'A' in params:
                target.a += params['A']

        # Clamp to travel limits
        target.x = max(0, min(target.x, self._max_travel['x']))
        target.y = max(0, min(target.y, self._max_travel['y']))
        target.z = max(0, min(target.z, self._max_travel['z']))

        self._target_position = target
        self._is_moving = True

        # Use rapid feedrate for G0
        if rapid:
            self._current_feedrate = self._max_feedrate
        else:
            self._current_feedrate = self._feedrate

    def _start_dwell(self, seconds: float):
        """Start a dwell (pause)."""
        if self._simulate_delays:
            self.create_timer(
                seconds,
                self._dwell_complete,
                callback_group=self._cb_group
            )
        else:
            self._dwell_complete()

    def _dwell_complete(self):
        """Dwell completed callback."""
        self._publish_response('ok')
        self._process_next_command()

    def _start_homing(self):
        """Start homing sequence."""
        self._state = MachineState.HOME
        self._target_position = SimulatedPosition(0, 0, 0, 0)
        self._is_moving = True
        self._current_feedrate = self._max_feedrate

    def _reset_machine(self):
        """Reset machine to initial state."""
        self._state = MachineState.IDLE
        self._position = SimulatedPosition()
        self._target_position = SimulatedPosition()
        self._gcode_queue.clear()
        self._is_moving = False
        self._spindle_on = False
        self._coolant_on = False
        self._publish_response('ok', 'Reset complete')

    def _update_motion(self):
        """Update simulated motion (called at 100Hz)."""
        if not self._is_moving or self._state == MachineState.HOLD:
            return

        # Calculate distance to target
        distance = self._position.distance_to(self._target_position)

        if distance < 0.001:  # Reached target
            self._position = SimulatedPosition(
                x=self._target_position.x,
                y=self._target_position.y,
                z=self._target_position.z,
                a=self._target_position.a
            )
            self._is_moving = False

            if self._state == MachineState.HOME:
                self._state = MachineState.IDLE
                self._publish_response('ok', 'Homing complete')
            else:
                self._publish_response('ok')

            self._process_next_command()
            return

        # Calculate step size based on feedrate
        # Feedrate is mm/min, timer is 100Hz (0.01s)
        step_size = (self._current_feedrate / 60.0) * 0.01

        if step_size >= distance:
            # Will reach target this step
            self._position.x = self._target_position.x
            self._position.y = self._target_position.y
            self._position.z = self._target_position.z
            self._position.a = self._target_position.a
        else:
            # Move towards target
            ratio = step_size / distance
            self._position.x += (self._target_position.x - self._position.x) * ratio
            self._position.y += (self._target_position.y - self._position.y) * ratio
            self._position.z += (self._target_position.z - self._position.z) * ratio
            self._position.a += (self._target_position.a - self._position.a) * ratio

    def _handle_raw_command(self, command: str):
        """Handle raw GRBL commands."""
        command = command.strip()

        if command == '?':
            self._publish_status()
        elif command == '!':
            self._state = MachineState.HOLD
        elif command == '~':
            if self._state == MachineState.HOLD:
                self._state = MachineState.RUN
        elif command == '\x18':
            self._reset_machine()
        elif command.startswith('$'):
            self._handle_grbl_setting(command)
        else:
            # Try to parse as G-code
            cmd = self._parse_gcode_line(command)
            if cmd:
                self._gcode_queue.append(cmd)
                if self._state == MachineState.IDLE:
                    self._state = MachineState.RUN
                    self._process_next_command()

    def _handle_grbl_setting(self, command: str):
        """Handle GRBL $ commands."""
        if command == '$$':
            # Return settings
            settings = [
                "$0=10", "$1=25", "$2=0", "$3=0", "$4=0", "$5=0",
                "$6=0", "$10=1", "$11=0.010", "$12=0.002",
                "$13=0", "$20=0", "$21=0", "$22=0", "$23=0",
                f"$100=250", f"$101=250", f"$102=250",
                f"$110={self._max_feedrate}", f"$111={self._max_feedrate}", f"$112={self._max_feedrate}",
                f"$120=10", f"$121=10", f"$122=10",
                f"$130={self._max_travel['x']}", f"$131={self._max_travel['y']}", f"$132={self._max_travel['z']}",
            ]
            for setting in settings:
                self._publish_response('info', setting)
            self._publish_response('ok')
        elif command == '$#':
            # Return offsets
            self._publish_response('info', f"[G54:0.000,0.000,0.000]")
            self._publish_response('info', f"[G92:0.000,0.000,0.000]")
            self._publish_response('ok')
        elif command == '$H':
            self._start_homing()
        else:
            self._publish_response('ok')

    def _publish_status(self):
        """Publish machine status."""
        # GRBL-style status
        state_names = {
            MachineState.IDLE: 'Idle',
            MachineState.RUN: 'Run',
            MachineState.HOLD: 'Hold',
            MachineState.HOME: 'Home',
            MachineState.ALARM: 'Alarm',
        }

        if self._machine_type == 'tinyg':
            # TinyG JSON format
            status = {
                'sr': {
                    'stat': self._state.value,
                    'posx': round(self._position.x, 3),
                    'posy': round(self._position.y, 3),
                    'posz': round(self._position.z, 3),
                    'posa': round(self._position.a, 3),
                    'feed': self._feedrate,
                    'vel': self._current_feedrate if self._is_moving else 0,
                    'unit': 1 if self._units_mm else 0,
                    'coor': 1,
                    'momo': 0 if self._absolute_mode else 1,
                    'dist': 0 if self._absolute_mode else 1,
                    'sps': self._spindle_speed,
                    'spmo': 1 if self._spindle_on else 0,
                }
            }
            msg = String()
            msg.data = json.dumps(status)
        else:
            # GRBL format: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
            status_str = (
                f"<{state_names.get(self._state, 'Unknown')}|"
                f"MPos:{self._position.x:.3f},{self._position.y:.3f},{self._position.z:.3f}|"
                f"FS:{self._feedrate:.0f},{self._spindle_speed}>"
            )
            msg = String()
            msg.data = status_str

        self._status_pub.publish(msg)

        # Also publish position as JointState
        pos_msg = JointState()
        pos_msg.header.stamp = self.get_clock().now().to_msg()
        pos_msg.name = ['x', 'y', 'z', 'a']
        pos_msg.position = [self._position.x, self._position.y, self._position.z, self._position.a]
        pos_msg.velocity = [self._current_feedrate if self._is_moving else 0.0] * 4
        self._position_pub.publish(pos_msg)

    def _publish_response(self, status: str, message: str = ''):
        """Publish response to commands."""
        msg = String()
        if self._machine_type == 'tinyg':
            response = {'r': {'status': status, 'message': message}}
            msg.data = json.dumps(response)
        else:
            if message:
                msg.data = f"{status}: {message}"
            else:
                msg.data = status
        self._response_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = GRBLSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
