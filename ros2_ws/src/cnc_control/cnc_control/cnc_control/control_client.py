#!/usr/bin/env python3
"""
CNC Control Client
==================
Interactive service client for CNC machine control.
Demonstrates calling ROS 2 services from Python.

Tutorial 4: Services for Machine Control

Usage:
    ros2 run cnc_control control_client

Commands:
    home [XYZ]     - Home specified axes (default: XYZ)
    jog X Y Z      - Incremental jog by X, Y, Z mm
    goto X Y Z     - Absolute move to X, Y, Z
    estop          - Emergency stop
    reset          - Soft reset
    unlock         - Clear alarm
    status         - Show current position
    help           - Show commands
    quit           - Exit
"""

import rclpy
from rclpy.node import Node
import sys

from cnc_interfaces.srv import Home, Jog, EmergencyStop


class ControlClientNode(Node):
    """Interactive service client for CNC control."""

    def __init__(self):
        super().__init__('control_client')

        # Create service clients
        self.home_client = self.create_client(Home, 'cnc/home')
        self.jog_client = self.create_client(Jog, 'cnc/jog')
        self.estop_client = self.create_client(EmergencyStop, 'cnc/emergency_stop')

        # Wait for services to be available
        self.get_logger().info('Waiting for CNC services...')
        services_ready = True

        if not self.home_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('/cnc/home service not available')
            services_ready = False

        if not self.jog_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('/cnc/jog service not available')
            services_ready = False

        if not self.estop_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('/cnc/emergency_stop service not available')
            services_ready = False

        if services_ready:
            self.get_logger().info('All services connected!')
        else:
            self.get_logger().warn('Some services unavailable - functionality limited')

        # Track position locally
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}

    def call_home(self, axes='XYZ'):
        """Call homing service."""
        request = Home.Request()
        request.machine_id = 'tinyg_001'
        request.axes = axes
        request.force = False

        self.get_logger().info(f'Sending HOME request for axes: {axes}')
        future = self.home_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        if future.result() is not None:
            result = future.result()
            if result.success:
                self.position['x'] = result.home_x
                self.position['y'] = result.home_y
                self.position['z'] = result.home_z
                self.get_logger().info(f'HOME SUCCESS: {result.message}')
                self.get_logger().info(f'  Duration: {result.duration:.2f}s')
            else:
                self.get_logger().error(f'HOME FAILED: {result.message}')
            return result.success
        else:
            self.get_logger().error('HOME service call failed')
            return False

    def call_jog(self, x, y, z, jog_type=1, feed_rate=1000.0):
        """Call jog service. jog_type: 1=incremental, 2=absolute"""
        request = Jog.Request()
        request.machine_id = 'tinyg_001'
        request.jog_type = jog_type
        request.x = float(x)
        request.y = float(y)
        request.z = float(z)
        request.feed_rate = feed_rate
        request.rapid = False
        request.check_limits = True

        type_name = 'INCREMENTAL' if jog_type == 1 else 'ABSOLUTE'
        self.get_logger().info(f'Sending JOG ({type_name}): X={x}, Y={y}, Z={z}')

        future = self.jog_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() is not None:
            result = future.result()
            if result.success:
                self.position['x'] = result.final_x
                self.position['y'] = result.final_y
                self.position['z'] = result.final_z
                self.get_logger().info(f'JOG SUCCESS: {result.message}')
            else:
                self.get_logger().error(f'JOG FAILED: {result.message}')
            return result.success
        else:
            self.get_logger().error('JOG service call failed')
            return False

    def call_estop(self, action, reason=''):
        """Call emergency stop service."""
        request = EmergencyStop.Request()
        request.machine_id = 'tinyg_001'
        request.action = action
        request.reason = reason

        actions = {0: 'ESTOP', 1: 'FEED_HOLD', 2: 'RESET', 3: 'UNLOCK', 4: 'RESUME'}
        self.get_logger().warn(f'Sending {actions.get(action, "UNKNOWN")} command')

        future = self.estop_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() is not None:
            result = future.result()
            if result.success:
                self.get_logger().info(f'SUCCESS: {result.message}')
                self.get_logger().info(f'  State: {result.previous_state} -> {result.new_state}')
            else:
                self.get_logger().error(f'FAILED: {result.message}')
            return result.success
        else:
            self.get_logger().error('ESTOP service call failed')
            return False

    def print_status(self):
        """Print current position."""
        print(f'\nCurrent Position:')
        print(f'  X: {self.position["x"]:.3f} mm')
        print(f'  Y: {self.position["y"]:.3f} mm')
        print(f'  Z: {self.position["z"]:.3f} mm')
        print()

    def print_help(self):
        """Print help message."""
        print('''
CNC Control Client Commands:
============================
  home [XYZ]     - Home specified axes (default: XYZ)
  jog X Y Z      - Incremental jog by X, Y, Z mm
  goto X Y Z     - Absolute move to X, Y, Z position
  estop          - Emergency stop (halt all motion)
  hold           - Feed hold (controlled stop)
  resume         - Resume from hold
  reset          - Soft reset controller
  unlock         - Clear alarm ($X equivalent)
  status         - Show current position
  help           - Show this help
  quit/exit      - Exit client

Examples:
  home XY        - Home X and Y axes only
  jog 10 0 0     - Jog +10mm in X direction
  jog 0 0 -5     - Jog -5mm in Z direction
  goto 100 50 -10 - Move to absolute position
''')

    def run_interactive(self):
        """Run interactive command loop."""
        print('=' * 50)
        print('CNC Control Client - Interactive Mode')
        print('=' * 50)
        print('Type "help" for commands, "quit" to exit')
        print()

        while True:
            try:
                cmd = input('cnc> ').strip().lower()
                if not cmd:
                    continue

                parts = cmd.split()
                command = parts[0]

                if command in ('quit', 'exit', 'q'):
                    print('Goodbye!')
                    break

                elif command == 'help':
                    self.print_help()

                elif command == 'status':
                    self.print_status()

                elif command == 'home':
                    axes = parts[1].upper() if len(parts) > 1 else 'XYZ'
                    self.call_home(axes)

                elif command == 'jog':
                    if len(parts) >= 4:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        self.call_jog(x, y, z, jog_type=1)  # Incremental
                    else:
                        print('Usage: jog X Y Z (e.g., jog 10 0 0)')

                elif command == 'goto':
                    if len(parts) >= 4:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        self.call_jog(x, y, z, jog_type=2)  # Absolute
                    else:
                        print('Usage: goto X Y Z (e.g., goto 100 50 -10)')

                elif command == 'estop':
                    self.call_estop(0, 'User initiated emergency stop')

                elif command == 'hold':
                    self.call_estop(1, 'User initiated feed hold')

                elif command == 'resume':
                    self.call_estop(4, 'User initiated resume')

                elif command == 'reset':
                    self.call_estop(2, 'User initiated soft reset')

                elif command == 'unlock':
                    self.call_estop(3, 'User initiated unlock')

                else:
                    print(f'Unknown command: {command}. Type "help" for commands.')

            except ValueError as e:
                print(f'Invalid input: {e}')
            except KeyboardInterrupt:
                print('\nUse "quit" to exit')
            except EOFError:
                print('\nGoodbye!')
                break


def main(args=None):
    rclpy.init(args=args)
    node = ControlClientNode()

    try:
        node.run_interactive()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
