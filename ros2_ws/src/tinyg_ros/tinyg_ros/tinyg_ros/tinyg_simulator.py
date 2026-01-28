#!/usr/bin/env python3
"""
TinyG Simulator Node
====================
Simulates a TinyG CNC controller for testing without hardware.
Publishes realistic JSON-style status updates.

This node simulates:
- Machine position tracking
- State transitions (idle, run, hold, homing)
- Queue depth reporting
- Motion simulation

Usage:
    ros2 run tinyg_ros tinyg_simulator
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
import math
import time
from dataclasses import dataclass

from std_msgs.msg import Header, Int32
from cnc_interfaces.msg import MachineStatus
from cnc_interfaces.srv import Home, Jog, SendGcode, EmergencyStop

from .tinyg_parser import TinyGState, TINYG_STATE_NAMES, TinyGParser


@dataclass
class SimulatedTinyG:
    """Simulated TinyG machine state."""
    # Position
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0

    # Target
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0

    # State
    state: TinyGState = TinyGState.READY
    homed: bool = False
    alarm: bool = False

    # Motion
    feed_rate: float = 0.0
    velocity: float = 0.0
    spindle_speed: float = 0.0

    # Work envelope (mm)
    max_x: float = 300.0
    max_y: float = 200.0
    max_z: float = 100.0

    # Queue
    queue_depth: int = 28

    # G54 offset
    g54_x: float = 0.0
    g54_y: float = 0.0
    g54_z: float = 0.0


class TinyGSimulatorNode(Node):
    """Simulates a TinyG CNC controller."""

    def __init__(self):
        super().__init__('tinyg_simulator')

        # Parameters
        self.declare_parameter('machine_id', 'tinyg_sim_001')
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('motion_speed', 50.0)

        self.machine_id = self.get_parameter('machine_id').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.motion_speed = self.get_parameter('motion_speed').value

        # Simulated machine
        self.machine = SimulatedTinyG()

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

        # Timers
        self.status_timer = self.create_timer(
            1.0 / self.publish_rate, self.publish_status)
        self.motion_timer = self.create_timer(
            0.02, self.update_motion)

        self.get_logger().info('=' * 60)
        self.get_logger().info('TinyG Simulator Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Machine ID: {self.machine_id}')
        self.get_logger().info(f'  Publish Rate: {self.publish_rate} Hz')
        self.get_logger().info(f'  Work Envelope: {self.machine.max_x}x{self.machine.max_y}x{self.machine.max_z} mm')
        self.get_logger().info('=' * 60)
        self.get_logger().info('Waiting for commands...')

    def update_motion(self):
        """Update simulated motion towards target."""
        if self.machine.state not in [TinyGState.RUN, TinyGState.JOG]:
            return

        dx = self.machine.target_x - self.machine.x
        dy = self.machine.target_y - self.machine.y
        dz = self.machine.target_z - self.machine.z
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        if distance < 0.01:
            self.machine.x = self.machine.target_x
            self.machine.y = self.machine.target_y
            self.machine.z = self.machine.target_z
            self.machine.state = TinyGState.READY
            self.machine.velocity = 0.0
            return

        step = min(self.motion_speed * 0.02, distance)
        ratio = step / distance

        self.machine.x += dx * ratio
        self.machine.y += dy * ratio
        self.machine.z += dz * ratio
        self.machine.velocity = self.motion_speed

    def publish_status(self):
        """Publish TinyG-style status."""
        msg = MachineStatus()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.machine_id

        msg.machine_id = self.machine_id
        msg.controller_type = 'tinyg_simulator'
        msg.firmware_version = '0.97-sim'

        msg.state = TinyGParser.state_to_ros(self.machine.state)
        msg.state_text = TINYG_STATE_NAMES.get(self.machine.state, "Unknown")

        # Position
        msg.mpos_x = self.machine.x
        msg.mpos_y = self.machine.y
        msg.mpos_z = self.machine.z
        msg.mpos_a = self.machine.a

        # Work position
        msg.wpos_x = self.machine.x - self.machine.g54_x
        msg.wpos_y = self.machine.y - self.machine.g54_y
        msg.wpos_z = self.machine.z - self.machine.g54_z

        # Work offset
        msg.wco_x = self.machine.g54_x
        msg.wco_y = self.machine.g54_y
        msg.wco_z = self.machine.g54_z
        msg.coord_system = "G54"

        # Motion
        msg.feed_rate = self.machine.feed_rate
        msg.velocity = self.machine.velocity
        msg.spindle_speed = self.machine.spindle_speed

        # Buffer
        msg.planner_buffer = self.machine.queue_depth

        # Units
        msg.metric = True

        self.status_pub.publish(msg)

        # Queue depth
        queue_msg = Int32()
        queue_msg.data = self.machine.queue_depth
        self.queue_pub.publish(queue_msg)

    def home_callback(self, request, response):
        """Handle homing request."""
        self.get_logger().info(f'HOME request: axes={request.axes}')

        if self.machine.alarm:
            response.success = False
            response.message = 'Cannot home in alarm state'
            return response

        self.machine.state = TinyGState.HOMING
        axes = request.axes.upper()

        start = time.time()
        for axis in axes:
            time.sleep(0.3)
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
        self.machine.state = TinyGState.READY

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

        if request.jog_type == 1:  # Incremental
            self.machine.target_x = self.machine.x + request.x
            self.machine.target_y = self.machine.y + request.y
            self.machine.target_z = self.machine.z + request.z
        else:  # Absolute
            self.machine.target_x = request.x
            self.machine.target_y = request.y
            self.machine.target_z = request.z

        # Clamp to limits
        self.machine.target_x = max(0, min(self.machine.max_x, self.machine.target_x))
        self.machine.target_y = max(0, min(self.machine.max_y, self.machine.target_y))
        self.machine.target_z = max(-self.machine.max_z, min(0, self.machine.target_z))

        self.machine.feed_rate = request.feed_rate
        self.machine.state = TinyGState.JOG

        # Wait for completion
        while self.machine.state == TinyGState.JOG:
            time.sleep(0.05)

        response.success = True
        response.message = 'Jog complete'
        response.motion_complete = True
        response.final_x = self.machine.x
        response.final_y = self.machine.y
        response.final_z = self.machine.z

        return response

    def gcode_callback(self, request, response):
        """Handle G-code request."""
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

            # Basic G-code parsing
            if 'G28' in line:
                self.machine.target_x = 0.0
                self.machine.target_y = 0.0
                self.machine.target_z = 0.0
                self.machine.state = TinyGState.HOMING
            elif line.startswith('G0') or line.startswith('G1'):
                self.machine.state = TinyGState.RUN

            response.lines_ok += 1

        response.success = response.lines_ok == response.lines_sent
        response.message = f'{response.lines_ok}/{response.lines_sent} lines ok'
        response.response = 'ok'

        return response

    def estop_callback(self, request, response):
        """Handle emergency stop."""
        actions = {0: 'ESTOP', 1: 'FEED_HOLD', 2: 'RESET', 3: 'UNLOCK', 4: 'RESUME'}
        self.get_logger().warn(f'ESTOP: {actions.get(request.action)}')

        previous_state = TINYG_STATE_NAMES.get(self.machine.state, "Unknown")

        if request.action == 0:  # ESTOP
            self.machine.state = TinyGState.ALARM
            self.machine.alarm = True
            response.message = 'EMERGENCY STOP activated'
        elif request.action == 1:  # FEED_HOLD
            if self.machine.state in [TinyGState.RUN, TinyGState.JOG]:
                self.machine.state = TinyGState.HOLD
                response.message = 'Feed hold activated'
            else:
                response.message = 'Not in motion'
        elif request.action == 2:  # RESET
            self.machine.state = TinyGState.READY
            self.machine.alarm = False
            self.machine.homed = False
            response.message = 'Soft reset complete'
        elif request.action == 3:  # UNLOCK
            self.machine.alarm = False
            self.machine.state = TinyGState.READY
            response.message = 'Alarm cleared'
        elif request.action == 4:  # RESUME
            if self.machine.state == TinyGState.HOLD:
                self.machine.state = TinyGState.RUN
                response.message = 'Resumed'
            else:
                response.message = 'Not in hold state'

        response.success = True
        response.previous_state = previous_state
        response.new_state = TINYG_STATE_NAMES.get(self.machine.state, "Unknown")

        return response


def main(args=None):
    rclpy.init(args=args)
    node = TinyGSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down TinyG simulator...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
