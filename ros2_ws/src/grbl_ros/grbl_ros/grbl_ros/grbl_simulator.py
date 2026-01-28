#!/usr/bin/env python3
"""
GRBL Simulator Node
===================
Simulates a GRBL controller for testing without hardware.
Publishes realistic status updates and responds to service calls.

This is useful for:
- Testing ROS 2 integration without physical hardware
- Developing GUIs and visualization tools
- Running demos and tutorials

Usage:
    ros2 run grbl_ros grbl_simulator
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
import math
import time
from dataclasses import dataclass

from std_msgs.msg import Header
from cnc_interfaces.msg import GrblStatus as GrblStatusMsg, MachineStatus
from cnc_interfaces.srv import Home, Jog, SendGcode, EmergencyStop

from .grbl_parser import GrblState


@dataclass
class SimulatedMachine:
    """Simulated CNC machine state."""
    # Position
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # Target (for motion simulation)
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0

    # State
    state: GrblState = GrblState.IDLE
    homed: bool = False
    alarm: bool = False

    # Motion
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    velocity: float = 0.0

    # Work envelope (mm)
    max_x: float = 300.0
    max_y: float = 200.0
    max_z: float = 100.0

    # Overrides
    feed_override: int = 100
    rapid_override: int = 100
    spindle_override: int = 100


class GrblSimulatorNode(Node):
    """Simulates a GRBL CNC controller."""

    def __init__(self):
        super().__init__('grbl_simulator')

        # Parameters
        self.declare_parameter('machine_id', 'grbl_sim_001')
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('motion_speed', 50.0)  # mm/s for simulation

        self.machine_id = self.get_parameter('machine_id').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.motion_speed = self.get_parameter('motion_speed').value

        # Simulated machine
        self.machine = SimulatedMachine()

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Publishers
        self.grbl_status_pub = self.create_publisher(
            GrblStatusMsg, 'grbl/status', 10)
        self.machine_status_pub = self.create_publisher(
            MachineStatus, 'grbl/machine_status', 10)

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

        # Timers
        self.status_timer = self.create_timer(
            1.0 / self.publish_rate, self.publish_status)
        self.motion_timer = self.create_timer(
            0.02, self.update_motion)  # 50Hz motion update

        self.get_logger().info('=' * 60)
        self.get_logger().info('GRBL Simulator Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Machine ID: {self.machine_id}')
        self.get_logger().info(f'  Publish Rate: {self.publish_rate} Hz')
        self.get_logger().info(f'  Work Envelope: {self.machine.max_x}x{self.machine.max_y}x{self.machine.max_z} mm')
        self.get_logger().info('=' * 60)
        self.get_logger().info('Waiting for commands...')

    def update_motion(self):
        """Update simulated motion towards target."""
        if self.machine.state not in [GrblState.RUN, GrblState.JOG]:
            return

        # Calculate distance to target
        dx = self.machine.target_x - self.machine.x
        dy = self.machine.target_y - self.machine.y
        dz = self.machine.target_z - self.machine.z
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        if distance < 0.01:  # Close enough
            self.machine.x = self.machine.target_x
            self.machine.y = self.machine.target_y
            self.machine.z = self.machine.target_z
            self.machine.state = GrblState.IDLE
            self.machine.velocity = 0.0
            return

        # Move towards target
        step = min(self.motion_speed * 0.02, distance)  # 50Hz * speed
        ratio = step / distance

        self.machine.x += dx * ratio
        self.machine.y += dy * ratio
        self.machine.z += dz * ratio
        self.machine.velocity = self.motion_speed

    def publish_status(self):
        """Publish current machine status."""
        # GRBL-specific status
        grbl_msg = GrblStatusMsg()
        grbl_msg.header = Header()
        grbl_msg.header.stamp = self.get_clock().now().to_msg()
        grbl_msg.header.frame_id = self.machine_id

        grbl_msg.state = self.machine.state.value
        grbl_msg.state_text = self.machine.state.name

        grbl_msg.mpos_x = self.machine.x
        grbl_msg.mpos_y = self.machine.y
        grbl_msg.mpos_z = self.machine.z
        grbl_msg.wpos_x = self.machine.x  # Simplified: WPos = MPos
        grbl_msg.wpos_y = self.machine.y
        grbl_msg.wpos_z = self.machine.z

        grbl_msg.feed_rate = self.machine.feed_rate
        grbl_msg.spindle_speed = self.machine.spindle_speed
        grbl_msg.feed_override = self.machine.feed_override
        grbl_msg.rapid_override = self.machine.rapid_override
        grbl_msg.spindle_override = self.machine.spindle_override

        grbl_msg.planner_buffer = 15
        grbl_msg.rx_buffer = 128

        self.grbl_status_pub.publish(grbl_msg)

        # Generic machine status
        machine_msg = MachineStatus()
        machine_msg.header = grbl_msg.header
        machine_msg.machine_id = self.machine_id
        machine_msg.controller_type = 'grbl_simulator'
        machine_msg.firmware_version = '1.1h-sim'
        machine_msg.state = grbl_msg.state
        machine_msg.state_text = grbl_msg.state_text
        machine_msg.mpos_x = grbl_msg.mpos_x
        machine_msg.mpos_y = grbl_msg.mpos_y
        machine_msg.mpos_z = grbl_msg.mpos_z
        machine_msg.wpos_x = grbl_msg.wpos_x
        machine_msg.wpos_y = grbl_msg.wpos_y
        machine_msg.wpos_z = grbl_msg.wpos_z
        machine_msg.feed_rate = grbl_msg.feed_rate
        machine_msg.velocity = self.machine.velocity

        self.machine_status_pub.publish(machine_msg)

    def home_callback(self, request, response):
        """Handle homing request."""
        self.get_logger().info(f'HOME request: axes={request.axes}')

        if self.machine.alarm:
            response.success = False
            response.message = 'Cannot home while in alarm state'
            return response

        # Simulate homing
        self.machine.state = GrblState.HOME
        axes = request.axes.upper()

        # Simulate homing motion (move to limits then back to 0)
        start = time.time()
        for axis in axes:
            time.sleep(0.3)  # Simulate per-axis homing
            if axis == 'X':
                self.machine.x = 0.0
            elif axis == 'Y':
                self.machine.y = 0.0
            elif axis == 'Z':
                self.machine.z = 0.0
            self.get_logger().info(f'  {axis} axis homed')

        self.machine.target_x = self.machine.x
        self.machine.target_y = self.machine.y
        self.machine.target_z = self.machine.z
        self.machine.homed = True
        self.machine.state = GrblState.IDLE

        response.success = True
        response.message = f'Homing complete: {axes}'
        response.home_x = self.machine.x
        response.home_y = self.machine.y
        response.home_z = self.machine.z
        response.duration = time.time() - start

        return response

    def jog_callback(self, request, response):
        """Handle jog request."""
        jog_types = {0: 'CONTINUOUS', 1: 'INCREMENTAL', 2: 'ABSOLUTE'}
        self.get_logger().info(
            f'JOG {jog_types.get(request.jog_type)}: '
            f'X={request.x:.2f} Y={request.y:.2f} Z={request.z:.2f}'
        )

        if self.machine.alarm:
            response.success = False
            response.message = 'Cannot jog in alarm state'
            response.motion_complete = False
            return response

        if not self.machine.homed:
            response.success = False
            response.message = 'Machine not homed'
            response.motion_complete = False
            return response

        # Calculate target position
        if request.jog_type == 1:  # INCREMENTAL
            self.machine.target_x = self.machine.x + request.x
            self.machine.target_y = self.machine.y + request.y
            self.machine.target_z = self.machine.z + request.z
        else:  # ABSOLUTE
            self.machine.target_x = request.x
            self.machine.target_y = request.y
            self.machine.target_z = request.z

        # Clamp to work envelope
        self.machine.target_x = max(0, min(self.machine.max_x, self.machine.target_x))
        self.machine.target_y = max(0, min(self.machine.max_y, self.machine.target_y))
        self.machine.target_z = max(-self.machine.max_z, min(0, self.machine.target_z))

        self.machine.feed_rate = request.feed_rate
        self.machine.state = GrblState.JOG

        # Wait for motion to complete (simplified)
        while self.machine.state == GrblState.JOG:
            time.sleep(0.05)

        response.success = True
        response.message = 'Jog complete'
        response.motion_complete = True
        response.final_x = self.machine.x
        response.final_y = self.machine.y
        response.final_z = self.machine.z

        return response

    def gcode_callback(self, request, response):
        """Handle G-code request (simplified parsing)."""
        lines = request.gcode.strip().split('\n')
        self.get_logger().info(f'GCODE: {len(lines)} lines')

        response.lines_sent = 0
        response.lines_ok = 0
        response.errors = []

        for line in lines:
            line = line.strip().upper()
            if not line or line.startswith(';') or line.startswith('('):
                continue

            response.lines_sent += 1

            # Very basic G-code parsing
            if 'G28' in line or 'G30' in line:
                # Go home
                self.machine.target_x = 0.0
                self.machine.target_y = 0.0
                self.machine.target_z = 0.0
                self.machine.state = GrblState.RUN
            elif line.startswith('G0') or line.startswith('G1'):
                # Rapid/linear move - extract coordinates
                self.machine.state = GrblState.RUN

            response.lines_ok += 1

        response.success = response.lines_ok == response.lines_sent
        response.message = f'{response.lines_ok}/{response.lines_sent} lines ok'
        response.response = 'ok'

        return response

    def estop_callback(self, request, response):
        """Handle emergency stop request."""
        actions = {0: 'ESTOP', 1: 'FEED_HOLD', 2: 'RESET', 3: 'UNLOCK', 4: 'RESUME'}
        self.get_logger().warn(f'ESTOP: {actions.get(request.action)}')

        previous_state = self.machine.state.name

        if request.action == 0:  # ESTOP
            self.machine.state = GrblState.ALARM
            self.machine.alarm = True
            response.message = 'EMERGENCY STOP activated'
        elif request.action == 1:  # FEED_HOLD
            if self.machine.state in [GrblState.RUN, GrblState.JOG]:
                self.machine.state = GrblState.HOLD
                response.message = 'Feed hold activated'
            else:
                response.message = 'Not in motion'
        elif request.action == 2:  # RESET
            self.machine.state = GrblState.IDLE
            self.machine.alarm = False
            self.machine.homed = False
            response.message = 'Soft reset complete'
        elif request.action == 3:  # UNLOCK
            self.machine.alarm = False
            self.machine.state = GrblState.IDLE
            response.message = 'Alarm cleared'
        elif request.action == 4:  # RESUME
            if self.machine.state == GrblState.HOLD:
                self.machine.state = GrblState.RUN
                response.message = 'Resumed'
            else:
                response.message = 'Not in hold state'

        response.success = True
        response.previous_state = previous_state
        response.new_state = self.machine.state.name

        return response


def main(args=None):
    rclpy.init(args=args)
    node = GrblSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down simulator...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
