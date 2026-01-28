#!/usr/bin/env python3
"""
G-code Validator - Pre-execution validation for CNC programs

Parses and validates G-code before execution to detect:
- Syntax errors
- Out-of-bounds movements
- Dangerous rapids
- Missing tool calls
- Feed rate issues
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from std_msgs.msg import String
from cnc_interfaces.msg import Alarm


@dataclass
class GCodeLine:
    """Parsed G-code line"""
    line_number: int
    raw: str
    g_codes: List[str] = field(default_factory=list)
    m_codes: List[str] = field(default_factory=list)
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[float] = None
    s: Optional[float] = None
    t: Optional[int] = None
    comment: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Complete validation result"""
    valid: bool = True
    total_lines: int = 0
    parsed_lines: int = 0
    error_count: int = 0
    warning_count: int = 0
    errors: List[Tuple[int, str]] = field(default_factory=list)
    warnings: List[Tuple[int, str]] = field(default_factory=list)
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    estimated_time: float = 0.0
    tool_changes: int = 0


class GCodeValidatorNode(Node):
    """G-code validation service"""

    def __init__(self):
        super().__init__('gcode_validator')

        # Parameters
        self.declare_parameter('x_min', 0.0)
        self.declare_parameter('x_max', 300.0)
        self.declare_parameter('y_min', 0.0)
        self.declare_parameter('y_max', 200.0)
        self.declare_parameter('z_min', -100.0)
        self.declare_parameter('z_max', 0.0)
        self.declare_parameter('max_feed_rate', 10000.0)
        self.declare_parameter('max_spindle_speed', 24000.0)
        self.declare_parameter('require_tool_call', True)
        self.declare_parameter('check_rapid_plunge', True)

        # Load limits
        self.limits = {
            'x_min': self.get_parameter('x_min').value,
            'x_max': self.get_parameter('x_max').value,
            'y_min': self.get_parameter('y_min').value,
            'y_max': self.get_parameter('y_max').value,
            'z_min': self.get_parameter('z_min').value,
            'z_max': self.get_parameter('z_max').value,
        }
        self.max_feed = self.get_parameter('max_feed_rate').value
        self.max_spindle = self.get_parameter('max_spindle_speed').value
        self.require_tool = self.get_parameter('require_tool_call').value
        self.check_plunge = self.get_parameter('check_rapid_plunge').value

        # Regex patterns
        self.patterns = {
            'g_code': re.compile(r'G(\d+\.?\d*)'),
            'm_code': re.compile(r'M(\d+)'),
            'x': re.compile(r'X(-?\d+\.?\d*)'),
            'y': re.compile(r'Y(-?\d+\.?\d*)'),
            'z': re.compile(r'Z(-?\d+\.?\d*)'),
            'f': re.compile(r'F(\d+\.?\d*)'),
            's': re.compile(r'S(\d+\.?\d*)'),
            't': re.compile(r'T(\d+)'),
            'comment': re.compile(r'\(.*?\)|;.*$'),
        }

        # Modal state
        self.current_mode = 'G0'  # Rapid
        self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.current_feed = 0.0
        self.tool_called = False

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscriber for validation requests
        self.validate_sub = self.create_subscription(
            String,
            '/gcode/validate',
            self.validate_callback,
            qos
        )

        # Publisher for results
        self.result_pub = self.create_publisher(
            String,
            '/gcode/validation_result',
            qos
        )

        self.alarm_pub = self.create_publisher(
            Alarm,
            '/gcode/validation_alarms',
            qos
        )

        self.get_logger().info('G-code Validator started')

    def validate_callback(self, msg: String):
        """Validate received G-code program"""
        result = self.validate_program(msg.data)

        # Publish result as JSON
        import json
        result_json = json.dumps({
            'valid': result.valid,
            'total_lines': result.total_lines,
            'parsed_lines': result.parsed_lines,
            'error_count': result.error_count,
            'warning_count': result.warning_count,
            'errors': result.errors,
            'warnings': result.warnings,
            'bounds': result.bounds,
            'estimated_time': result.estimated_time,
            'tool_changes': result.tool_changes,
        })

        result_msg = String()
        result_msg.data = result_json
        self.result_pub.publish(result_msg)

        # Publish alarms for errors
        for line_num, error in result.errors:
            alarm = Alarm()
            alarm.header.stamp = self.get_clock().now().to_msg()
            alarm.alarm_code = 6000 + line_num % 1000
            alarm.message = f"Line {line_num}: {error}"
            alarm.severity = 2  # Critical
            self.alarm_pub.publish(alarm)

    def validate_program(self, program: str) -> ValidationResult:
        """Validate complete G-code program"""
        result = ValidationResult()

        # Reset state
        self.current_mode = 'G0'
        self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.current_feed = 0.0
        self.tool_called = False

        # Track bounds
        x_vals, y_vals, z_vals = [], [], []

        lines = program.strip().split('\n')
        result.total_lines = len(lines)

        for i, line in enumerate(lines, 1):
            parsed = self.parse_line(line, i)

            if parsed.errors:
                result.valid = False
                for err in parsed.errors:
                    result.errors.append((i, err))
                    result.error_count += 1

            for warn in parsed.warnings:
                result.warnings.append((i, warn))
                result.warning_count += 1

            # Track positions
            if parsed.x is not None:
                x_vals.append(parsed.x)
                self.current_position['x'] = parsed.x
            if parsed.y is not None:
                y_vals.append(parsed.y)
                self.current_position['y'] = parsed.y
            if parsed.z is not None:
                z_vals.append(parsed.z)
                self.current_position['z'] = parsed.z

            # Track tool calls
            if parsed.t is not None:
                self.tool_called = True
                result.tool_changes += 1

            result.parsed_lines += 1

        # Calculate bounds
        if x_vals:
            result.bounds['x'] = (min(x_vals), max(x_vals))
        if y_vals:
            result.bounds['y'] = (min(y_vals), max(y_vals))
        if z_vals:
            result.bounds['z'] = (min(z_vals), max(z_vals))

        # Check if tool was called (if required)
        if self.require_tool and not self.tool_called:
            result.warnings.append((0, "No tool call (T) found in program"))
            result.warning_count += 1

        return result

    def parse_line(self, line: str, line_number: int) -> GCodeLine:
        """Parse and validate a single G-code line"""
        parsed = GCodeLine(line_number=line_number, raw=line)

        # Skip empty lines and pure comments
        clean_line = line.strip()
        if not clean_line or clean_line.startswith('(') or clean_line.startswith(';'):
            return parsed

        # Extract comment
        comment_match = self.patterns['comment'].search(clean_line)
        if comment_match:
            parsed.comment = comment_match.group()
            clean_line = self.patterns['comment'].sub('', clean_line)

        # Parse G codes
        for match in self.patterns['g_code'].finditer(clean_line):
            g_code = f"G{match.group(1)}"
            parsed.g_codes.append(g_code)

            # Update mode for motion commands
            if g_code in ['G0', 'G00']:
                self.current_mode = 'G0'
            elif g_code in ['G1', 'G01']:
                self.current_mode = 'G1'
            elif g_code in ['G2', 'G02', 'G3', 'G03']:
                self.current_mode = g_code

        # Parse M codes
        for match in self.patterns['m_code'].finditer(clean_line):
            parsed.m_codes.append(f"M{match.group(1)}")

        # Parse coordinates
        x_match = self.patterns['x'].search(clean_line)
        if x_match:
            parsed.x = float(x_match.group(1))
            if not self.limits['x_min'] <= parsed.x <= self.limits['x_max']:
                parsed.errors.append(f"X={parsed.x} out of bounds [{self.limits['x_min']}, {self.limits['x_max']}]")

        y_match = self.patterns['y'].search(clean_line)
        if y_match:
            parsed.y = float(y_match.group(1))
            if not self.limits['y_min'] <= parsed.y <= self.limits['y_max']:
                parsed.errors.append(f"Y={parsed.y} out of bounds [{self.limits['y_min']}, {self.limits['y_max']}]")

        z_match = self.patterns['z'].search(clean_line)
        if z_match:
            parsed.z = float(z_match.group(1))
            if not self.limits['z_min'] <= parsed.z <= self.limits['z_max']:
                parsed.errors.append(f"Z={parsed.z} out of bounds [{self.limits['z_min']}, {self.limits['z_max']}]")

            # Check for rapid plunge
            if self.check_plunge and self.current_mode == 'G0':
                z_change = self.current_position['z'] - parsed.z
                if z_change > 10:  # Rapid descent more than 10mm
                    parsed.warnings.append(f"Rapid Z plunge of {z_change:.1f}mm detected")

        # Parse feed rate
        f_match = self.patterns['f'].search(clean_line)
        if f_match:
            parsed.f = float(f_match.group(1))
            self.current_feed = parsed.f
            if parsed.f > self.max_feed:
                parsed.warnings.append(f"Feed rate {parsed.f} exceeds maximum {self.max_feed}")

        # Check for missing feed in cutting mode
        if self.current_mode == 'G1' and self.current_feed == 0:
            if parsed.x is not None or parsed.y is not None or parsed.z is not None:
                parsed.warnings.append("G1 movement with no feed rate defined")

        # Parse spindle speed
        s_match = self.patterns['s'].search(clean_line)
        if s_match:
            parsed.s = float(s_match.group(1))
            if parsed.s > self.max_spindle:
                parsed.warnings.append(f"Spindle speed {parsed.s} exceeds maximum {self.max_spindle}")

        # Parse tool number
        t_match = self.patterns['t'].search(clean_line)
        if t_match:
            parsed.t = int(t_match.group(1))

        return parsed


def main(args=None):
    rclpy.init(args=args)
    node = GCodeValidatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
