#!/usr/bin/env python3
"""
Voice Controller - Voice command processing for CNC machines

Processes voice commands and translates them to machine actions.
Integrates with speech-to-text and NLU services.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import re
from typing import Dict, Optional, Tuple

from std_msgs.msg import String
from geometry_msgs.msg import Twist, Point
from cnc_interfaces.msg import VoiceCommand, Alarm
from cnc_interfaces.srv import ProcessVoice, Jog, Home, EmergencyStop


class VoiceControllerNode(Node):
    """Voice command processing and execution"""

    def __init__(self):
        super().__init__('voice_controller')

        # Parameters
        self.declare_parameter('default_jog_distance', 10.0)
        self.declare_parameter('default_jog_speed', 1000.0)
        self.declare_parameter('require_confirmation_for_dangerous', True)

        self.default_distance = self.get_parameter('default_jog_distance').value
        self.default_speed = self.get_parameter('default_jog_speed').value
        self.require_confirm = self.get_parameter('require_confirmation_for_dangerous').value

        # Command patterns
        self.patterns = {
            'jog': re.compile(r'(?:jog|move)\s+([xyz])\s*(positive|negative|plus|minus|up|down|left|right)?\s*(\d+\.?\d*)?\s*(mm|millimeters|inches)?', re.I),
            'home': re.compile(r'(?:home|zero)\s*(?:all|machine|([xyz]+))?', re.I),
            'stop': re.compile(r'(?:stop|halt|pause)', re.I),
            'estop': re.compile(r'(?:emergency\s*stop|e[\-\s]*stop)', re.I),
            'spindle_on': re.compile(r'(?:spindle|spin)\s*(?:on|start)\s*(?:at\s*)?(\d+)?', re.I),
            'spindle_off': re.compile(r'(?:spindle|spin)\s*(?:off|stop)', re.I),
            'coolant_on': re.compile(r'(?:coolant|flood|mist)\s*(?:on|start)', re.I),
            'coolant_off': re.compile(r'(?:coolant|flood|mist)\s*(?:off|stop)', re.I),
            'go_to': re.compile(r'(?:go\s*to|move\s*to)\s*(?:x\s*)?(-?\d+\.?\d*)\s*(?:y\s*)?(-?\d+\.?\d*)?\s*(?:z\s*)?(-?\d+\.?\d*)?', re.I),
            'status': re.compile(r'(?:status|where|position|what)', re.I),
        }

        # Dangerous commands that need confirmation
        self.dangerous_commands = {'estop', 'home'}

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST, depth=10
        )

        # Subscribers
        self.transcript_sub = self.create_subscription(
            String, '/voice/transcript', self.transcript_callback, qos)

        # Publishers
        self.command_pub = self.create_publisher(VoiceCommand, '/voice/commands', qos)
        self.jog_pub = self.create_publisher(Twist, '/machine/jog_cmd', qos)
        self.gcode_pub = self.create_publisher(String, '/machine/gcode_cmd', qos)
        self.response_pub = self.create_publisher(String, '/voice/response', qos)

        # Service
        self.process_srv = self.create_service(
            ProcessVoice, '/voice/process', self.process_callback)

        # Service clients
        self.jog_client = self.create_client(Jog, '/tinyg/jog')
        self.home_client = self.create_client(Home, '/tinyg/home')
        self.estop_client = self.create_client(EmergencyStop, '/tinyg/emergency_stop')

        self.get_logger().info('Voice Controller started')

    def transcript_callback(self, msg: String):
        """Process incoming voice transcript"""
        command = self.parse_command(msg.data)
        if command:
            self.execute_command(command)

    def process_callback(self, request, response):
        """Process voice command service"""
        transcript = request.transcript

        # Parse command
        command = self.parse_command(transcript)

        if not command:
            response.success = False
            response.message = "Could not understand command"
            response.response_text = "I didn't understand that command. Please try again."
            return response

        # Check for dangerous commands
        if command.command_type in [VoiceCommand.COMMAND_EMERGENCY_STOP, VoiceCommand.COMMAND_HOME]:
            if self.require_confirm:
                response.success = True
                response.requires_confirmation = True
                response.confirmation_prompt = f"Are you sure you want to {self.get_command_name(command.command_type)}?"
                response.parsed_command = command
                return response

        # Execute command
        result = self.execute_command(command)

        response.success = result
        response.message = "Command executed" if result else "Command failed"
        response.parsed_command = command
        response.response_text = self.generate_response(command, result)

        return response

    def parse_command(self, transcript: str) -> Optional[VoiceCommand]:
        """Parse transcript into VoiceCommand"""
        transcript = transcript.strip().lower()

        cmd = VoiceCommand()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.raw_transcript = transcript
        cmd.transcription_confidence = 0.9

        # Try each pattern
        # Jog command
        match = self.patterns['jog'].search(transcript)
        if match:
            cmd.command_type = VoiceCommand.COMMAND_JOG
            cmd.axis = match.group(1).upper()

            direction = match.group(2) or 'positive'
            if direction in ['negative', 'minus', 'down', 'left']:
                cmd.direction = 'negative'
            else:
                cmd.direction = 'positive'

            distance = match.group(3)
            cmd.distance = float(distance) if distance else self.default_distance
            cmd.speed = self.default_speed

            return cmd

        # Home command
        match = self.patterns['home'].search(transcript)
        if match:
            cmd.command_type = VoiceCommand.COMMAND_HOME
            axes = match.group(1)
            cmd.axis = axes.upper() if axes else 'XYZ'
            return cmd

        # E-stop
        if self.patterns['estop'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_EMERGENCY_STOP
            cmd.safety_level = 2
            return cmd

        # Stop
        if self.patterns['stop'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_STOP
            return cmd

        # Spindle on
        match = self.patterns['spindle_on'].search(transcript)
        if match:
            cmd.command_type = VoiceCommand.COMMAND_SPINDLE_ON
            speed = match.group(1)
            cmd.speed = float(speed) if speed else 10000
            return cmd

        # Spindle off
        if self.patterns['spindle_off'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_SPINDLE_OFF
            return cmd

        # Coolant
        if self.patterns['coolant_on'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_COOLANT_ON
            return cmd

        if self.patterns['coolant_off'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_COOLANT_OFF
            return cmd

        # Go to position
        match = self.patterns['go_to'].search(transcript)
        if match:
            cmd.command_type = VoiceCommand.COMMAND_GO_TO
            x = float(match.group(1)) if match.group(1) else 0
            y = float(match.group(2)) if match.group(2) else 0
            z = float(match.group(3)) if match.group(3) else 0
            cmd.target_position = Point(x=x, y=y, z=z)
            return cmd

        # Status request
        if self.patterns['status'].search(transcript):
            cmd.command_type = VoiceCommand.COMMAND_STATUS
            return cmd

        return None

    def execute_command(self, cmd: VoiceCommand) -> bool:
        """Execute parsed voice command"""
        self.command_pub.publish(cmd)

        if cmd.command_type == VoiceCommand.COMMAND_JOG:
            return self.execute_jog(cmd)
        elif cmd.command_type == VoiceCommand.COMMAND_HOME:
            return self.execute_home(cmd)
        elif cmd.command_type == VoiceCommand.COMMAND_EMERGENCY_STOP:
            return self.execute_estop(cmd)
        elif cmd.command_type == VoiceCommand.COMMAND_STOP:
            return self.send_gcode("!")  # Feed hold
        elif cmd.command_type == VoiceCommand.COMMAND_SPINDLE_ON:
            return self.send_gcode(f"M3 S{cmd.speed:.0f}")
        elif cmd.command_type == VoiceCommand.COMMAND_SPINDLE_OFF:
            return self.send_gcode("M5")
        elif cmd.command_type == VoiceCommand.COMMAND_COOLANT_ON:
            return self.send_gcode("M8")  # Flood coolant
        elif cmd.command_type == VoiceCommand.COMMAND_COOLANT_OFF:
            return self.send_gcode("M9")
        elif cmd.command_type == VoiceCommand.COMMAND_GO_TO:
            p = cmd.target_position
            return self.send_gcode(f"G0 X{p.x} Y{p.y} Z{p.z}")

        return False

    def execute_jog(self, cmd: VoiceCommand) -> bool:
        """Execute jog command"""
        twist = Twist()
        distance = cmd.distance if cmd.direction == 'positive' else -cmd.distance

        if cmd.axis == 'X':
            twist.linear.x = distance
        elif cmd.axis == 'Y':
            twist.linear.y = distance
        elif cmd.axis == 'Z':
            twist.linear.z = distance

        self.jog_pub.publish(twist)
        return True

    def execute_home(self, cmd: VoiceCommand) -> bool:
        """Execute home command"""
        if not self.home_client.wait_for_service(timeout_sec=1.0):
            return False

        request = Home.Request()
        request.machine_id = 'tinyg_001'
        future = self.home_client.call_async(request)
        return True  # Async call

    def execute_estop(self, cmd: VoiceCommand) -> bool:
        """Execute emergency stop"""
        if not self.estop_client.wait_for_service(timeout_sec=0.5):
            # Fall back to direct command
            return self.send_gcode("!")

        request = EmergencyStop.Request()
        request.machine_id = 'tinyg_001'
        self.estop_client.call_async(request)
        return True

    def send_gcode(self, gcode: str) -> bool:
        """Send G-code command"""
        msg = String()
        msg.data = gcode
        self.gcode_pub.publish(msg)
        return True

    def get_command_name(self, cmd_type: int) -> str:
        """Get human-readable command name"""
        names = {
            VoiceCommand.COMMAND_JOG: "jog",
            VoiceCommand.COMMAND_HOME: "home the machine",
            VoiceCommand.COMMAND_EMERGENCY_STOP: "emergency stop",
            VoiceCommand.COMMAND_STOP: "stop",
        }
        return names.get(cmd_type, "unknown command")

    def generate_response(self, cmd: VoiceCommand, success: bool) -> str:
        """Generate spoken response"""
        if not success:
            return "Command failed. Please try again."

        responses = {
            VoiceCommand.COMMAND_JOG: f"Jogging {cmd.axis} axis {cmd.distance} millimeters",
            VoiceCommand.COMMAND_HOME: "Homing machine",
            VoiceCommand.COMMAND_EMERGENCY_STOP: "Emergency stop activated",
            VoiceCommand.COMMAND_STOP: "Machine stopped",
            VoiceCommand.COMMAND_SPINDLE_ON: f"Spindle on at {cmd.speed} RPM",
            VoiceCommand.COMMAND_SPINDLE_OFF: "Spindle off",
        }
        return responses.get(cmd.command_type, "Command executed")


def main(args=None):
    rclpy.init(args=args)
    node = VoiceControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
