#!/usr/bin/env python3
"""
CNC Machine Service Server
==========================
Demonstrates ROS 2 services for CNC machine control.
Handles: Home, Jog, EmergencyStop services using cnc_interfaces.

Tutorial 4: Services for Machine Control
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
import time

from cnc_interfaces.srv import Home, Jog, EmergencyStop


class MachineServiceNode(Node):
    """Service server for CNC machine control operations."""

    def __init__(self):
        super().__init__('machine_service')

        # Machine state simulation
        self.machine_id = 'tinyg_001'
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.state = 'idle'
        self.homed = False
        self.alarm_active = False

        # Use reentrant callback group for concurrent service calls
        self.callback_group = ReentrantCallbackGroup()

        # Create services
        self.home_srv = self.create_service(
            Home,
            'cnc/home',
            self.home_callback,
            callback_group=self.callback_group
        )

        self.jog_srv = self.create_service(
            Jog,
            'cnc/jog',
            self.jog_callback,
            callback_group=self.callback_group
        )

        self.estop_srv = self.create_service(
            EmergencyStop,
            'cnc/emergency_stop',
            self.estop_callback,
            callback_group=self.callback_group
        )

        self.get_logger().info('=' * 50)
        self.get_logger().info('CNC Machine Service Server Started')
        self.get_logger().info('=' * 50)
        self.get_logger().info('Available services:')
        self.get_logger().info('  - /cnc/home (Home.srv)')
        self.get_logger().info('  - /cnc/jog (Jog.srv)')
        self.get_logger().info('  - /cnc/emergency_stop (EmergencyStop.srv)')
        self.get_logger().info('=' * 50)

    def home_callback(self, request, response):
        """Handle homing cycle request."""
        self.get_logger().info(f'HOME request: machine={request.machine_id}, axes={request.axes}')

        if self.alarm_active:
            response.success = False
            response.message = 'Cannot home while alarm is active. Clear alarm first.'
            return response

        # Simulate homing cycle
        self.state = 'homing'
        start_time = time.time()

        axes = request.axes.upper()
        self.get_logger().info(f'Homing axes: {axes}...')

        # Simulate homing each axis (0.5s per axis)
        for axis in axes:
            time.sleep(0.5)  # Simulate motion
            if axis == 'X':
                self.position['x'] = 0.0
            elif axis == 'Y':
                self.position['y'] = 0.0
            elif axis == 'Z':
                self.position['z'] = 0.0
            self.get_logger().info(f'  {axis} axis homed')

        duration = time.time() - start_time
        self.homed = True
        self.state = 'idle'

        response.success = True
        response.message = f'Homing complete for axes: {axes}'
        response.home_x = self.position['x']
        response.home_y = self.position['y']
        response.home_z = self.position['z']
        response.duration = duration

        self.get_logger().info(f'HOME complete in {duration:.2f}s')
        return response

    def jog_callback(self, request, response):
        """Handle jog movement request."""
        jog_types = {0: 'CONTINUOUS', 1: 'INCREMENTAL', 2: 'ABSOLUTE'}
        jog_type_name = jog_types.get(request.jog_type, 'UNKNOWN')

        self.get_logger().info(
            f'JOG request: type={jog_type_name}, '
            f'X={request.x:.3f}, Y={request.y:.3f}, Z={request.z:.3f}, '
            f'feed={request.feed_rate}'
        )

        if self.alarm_active:
            response.success = False
            response.message = 'Cannot jog while alarm is active'
            response.motion_complete = False
            return response

        if not self.homed and request.check_limits:
            response.success = False
            response.message = 'Machine not homed. Home first or disable limit check.'
            response.motion_complete = False
            return response

        self.state = 'jog'

        # Simulate jog motion based on type
        if request.jog_type == 1:  # INCREMENTAL
            # Move relative to current position
            self.position['x'] += request.x
            self.position['y'] += request.y
            self.position['z'] += request.z
        elif request.jog_type == 2:  # ABSOLUTE
            # Move to absolute position
            self.position['x'] = request.x
            self.position['y'] = request.y
            self.position['z'] = request.z

        # Check soft limits (simulated work envelope: 300x200x100mm)
        limits_ok = True
        if request.check_limits:
            if not (0 <= self.position['x'] <= 300):
                limits_ok = False
                self.position['x'] = max(0, min(300, self.position['x']))
            if not (0 <= self.position['y'] <= 200):
                limits_ok = False
                self.position['y'] = max(0, min(200, self.position['y']))
            if not (-100 <= self.position['z'] <= 0):
                limits_ok = False
                self.position['z'] = max(-100, min(0, self.position['z']))

        # Simulate motion time
        time.sleep(0.2)
        self.state = 'idle'

        response.success = True
        response.motion_complete = True
        response.final_x = self.position['x']
        response.final_y = self.position['y']
        response.final_z = self.position['z']

        if limits_ok:
            response.message = f'Jog complete. Position: X={self.position["x"]:.3f}, Y={self.position["y"]:.3f}, Z={self.position["z"]:.3f}'
        else:
            response.message = f'Jog clamped to soft limits. Position: X={self.position["x"]:.3f}, Y={self.position["y"]:.3f}, Z={self.position["z"]:.3f}'

        self.get_logger().info(f'JOG complete: {response.message}')
        return response

    def estop_callback(self, request, response):
        """Handle emergency stop / reset request."""
        actions = {
            0: 'ESTOP',
            1: 'FEED_HOLD',
            2: 'RESET',
            3: 'UNLOCK',
            4: 'RESUME'
        }
        action_name = actions.get(request.action, 'UNKNOWN')

        self.get_logger().warn(
            f'EMERGENCY STOP request: action={action_name}, reason="{request.reason}"'
        )

        previous_state = self.state

        if request.action == 0:  # ESTOP
            self.state = 'alarm'
            self.alarm_active = True
            response.success = True
            response.message = 'EMERGENCY STOP activated! All motion halted.'

        elif request.action == 1:  # FEED_HOLD
            if self.state == 'run' or self.state == 'jog':
                self.state = 'hold'
                response.success = True
                response.message = 'Feed hold activated. Motion paused.'
            else:
                response.success = False
                response.message = f'Cannot feed hold from state: {self.state}'

        elif request.action == 2:  # RESET
            self.state = 'idle'
            self.alarm_active = False
            self.homed = False
            self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            response.success = True
            response.message = 'Soft reset complete. Machine requires re-homing.'

        elif request.action == 3:  # UNLOCK
            if self.alarm_active:
                self.alarm_active = False
                self.state = 'idle'
                response.success = True
                response.message = 'Alarm cleared. Machine unlocked.'
            else:
                response.success = False
                response.message = 'No alarm to clear.'

        elif request.action == 4:  # RESUME
            if self.state == 'hold':
                self.state = 'run'
                response.success = True
                response.message = 'Cycle resumed.'
            else:
                response.success = False
                response.message = f'Cannot resume from state: {self.state}'

        else:
            response.success = False
            response.message = f'Unknown action: {request.action}'

        response.previous_state = previous_state
        response.new_state = self.state

        self.get_logger().info(
            f'State transition: {previous_state} -> {self.state}'
        )
        return response


def main(args=None):
    rclpy.init(args=args)
    node = MachineServiceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down machine service...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
