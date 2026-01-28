#!/usr/bin/env python3
"""
CNC Control Client (Enhanced)
=============================
Interactive service client for CNC machine control with:
- Real-time status display via subscription
- Jog command publishing for continuous motion
- Watch mode for live position updates
- Keyboard-driven jog controls

Tutorial 4: Services for Machine Control

Usage:
    ros2 run cnc_control control_client

Commands:
    home [XYZ]       - Home specified axes (default: XYZ)
    jog X Y Z        - Incremental jog by X, Y, Z mm
    goto X Y Z       - Absolute move to X, Y, Z
    jog+ AXIS DIST   - Continuous jog (e.g., jog+ x 10)
    jog-stop         - Stop continuous jog
    estop            - Emergency stop
    reset            - Soft reset
    unlock           - Clear alarm
    status           - Show current position
    watch            - Enter real-time status mode
    help             - Show commands
    quit             - Exit
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
import sys
import threading
import time
from datetime import datetime

from cnc_interfaces.srv import Home, Jog, EmergencyStop
from cnc_interfaces.msg import MachineStatus, GrblStatus
from geometry_msgs.msg import Twist


class EnhancedControlClient(Node):
    """Interactive control client with real-time status and jog publishing."""

    def __init__(self):
        super().__init__('control_client')

        # Callback group for concurrent operations
        self.callback_group = ReentrantCallbackGroup()

        # Machine state tracking
        self.current_status = None
        self.current_grbl_status = None
        self.last_status_time = None
        self.watch_mode = False

        # QoS for status subscription
        qos_best_effort = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Create service clients
        self.home_client = self.create_client(
            Home, 'cnc/home', callback_group=self.callback_group)
        self.jog_client = self.create_client(
            Jog, 'cnc/jog', callback_group=self.callback_group)
        self.estop_client = self.create_client(
            EmergencyStop, 'cnc/emergency_stop', callback_group=self.callback_group)

        # Create jog command publisher (for continuous jog)
        self.jog_pub = self.create_publisher(
            Twist, '/machine/jog_cmd', 10)

        # Subscribe to machine status
        self.status_sub = self.create_subscription(
            MachineStatus,
            '/tinyg/status',
            self._status_callback,
            qos_best_effort,
            callback_group=self.callback_group
        )

        self.grbl_status_sub = self.create_subscription(
            GrblStatus,
            '/grbl/status',
            self._grbl_status_callback,
            qos_best_effort,
            callback_group=self.callback_group
        )

        # Wait for services to be available
        self.get_logger().info('Waiting for CNC services...')
        services_ready = True

        if not self.home_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn('/cnc/home service not available')
            services_ready = False

        if not self.jog_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn('/cnc/jog service not available')
            services_ready = False

        if not self.estop_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn('/cnc/emergency_stop service not available')
            services_ready = False

        if services_ready:
            self.get_logger().info('All services connected!')
        else:
            self.get_logger().warn('Some services unavailable - functionality limited')

        # Track position locally (fallback if no subscription)
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.state = 'unknown'
        self.machine_id = 'unknown'

    def _status_callback(self, msg: MachineStatus):
        """Handle TinyG status updates."""
        self.current_status = msg
        self.last_status_time = datetime.now()
        self.position = {
            'x': msg.mpos_x,
            'y': msg.mpos_y,
            'z': msg.mpos_z
        }
        self.state = msg.state_text
        self.machine_id = msg.machine_id

        if self.watch_mode:
            self._display_status()

    def _grbl_status_callback(self, msg: GrblStatus):
        """Handle GRBL status updates."""
        self.current_grbl_status = msg
        self.last_status_time = datetime.now()
        self.position = {
            'x': msg.mpos_x,
            'y': msg.mpos_y,
            'z': msg.mpos_z
        }
        self.state = msg.state_text
        self.machine_id = msg.machine_id

        if self.watch_mode:
            self._display_status()

    def _display_status(self):
        """Display current status inline (for watch mode)."""
        status = self.current_status or self.current_grbl_status
        if status:
            # Use carriage return for in-place update
            feed = status.feed_rate if hasattr(status, 'feed_rate') else 0
            spindle = status.spindle_speed if hasattr(status, 'spindle_speed') else 0
            print(f'\r[{self.state:8s}] '
                  f'X:{self.position["x"]:8.3f} '
                  f'Y:{self.position["y"]:8.3f} '
                  f'Z:{self.position["z"]:8.3f} '
                  f'F:{feed:6.0f} S:{spindle:5.0f}  ', end='', flush=True)

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

    def publish_jog_command(self, axis, value, feed_rate=1000.0):
        """Publish continuous jog command via Twist message."""
        twist = Twist()

        # Map axis to Twist fields
        if axis.lower() == 'x':
            twist.linear.x = value * feed_rate / 60.0  # Convert to m/s
        elif axis.lower() == 'y':
            twist.linear.y = value * feed_rate / 60.0
        elif axis.lower() == 'z':
            twist.linear.z = value * feed_rate / 60.0
        else:
            self.get_logger().error(f'Invalid axis: {axis}')
            return

        self.jog_pub.publish(twist)
        direction = '+' if value > 0 else '-'
        self.get_logger().info(f'JOG CMD: {axis.upper()}{direction} at F{feed_rate}')

    def stop_jog(self):
        """Stop all jog motion by publishing zero velocity."""
        twist = Twist()
        twist.linear.x = 0.0
        twist.linear.y = 0.0
        twist.linear.z = 0.0
        self.jog_pub.publish(twist)
        self.get_logger().info('JOG STOP: All axes')

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
        """Print current machine status."""
        print(f'\n{"="*50}')
        print(f'Machine Status')
        print(f'{"="*50}')
        print(f'  Machine ID: {self.machine_id}')
        print(f'  State:      {self.state}')
        print(f'  Position:')
        print(f'    X: {self.position["x"]:10.3f} mm')
        print(f'    Y: {self.position["y"]:10.3f} mm')
        print(f'    Z: {self.position["z"]:10.3f} mm')

        status = self.current_status or self.current_grbl_status
        if status:
            print(f'  Feed Rate:    {status.feed_rate:.0f} mm/min')
            print(f'  Spindle:      {status.spindle_speed:.0f} RPM')
            print(f'  Buffer Avail: {status.buffer_available}')

        if self.last_status_time:
            age = (datetime.now() - self.last_status_time).total_seconds()
            print(f'  Last Update:  {age:.1f}s ago')
        else:
            print(f'  Last Update:  No status received')

        print(f'{"="*50}\n')

    def print_help(self):
        """Print help message."""
        print('''
CNC Control Client Commands (Enhanced):
=======================================

BASIC MOTION:
  home [XYZ]       - Home specified axes (default: XYZ)
  jog X Y Z        - Incremental jog by X, Y, Z mm
  goto X Y Z       - Absolute move to X, Y, Z position

CONTINUOUS JOG:
  jog+ AXIS DIST   - Start continuous jog (e.g., jog+ x 1)
  jog- AXIS DIST   - Start continuous jog negative direction
  jog-stop         - Stop all continuous jog motion

MACHINE CONTROL:
  estop            - Emergency stop (halt all motion)
  hold             - Feed hold (controlled stop)
  resume           - Resume from hold
  reset            - Soft reset controller
  unlock           - Clear alarm ($X equivalent)

STATUS & MONITORING:
  status           - Show detailed machine status
  watch            - Enter real-time status display mode
                     (Press Ctrl+C to exit watch mode)

OTHER:
  help             - Show this help
  quit/exit/q      - Exit client

Examples:
  home XY          - Home X and Y axes only
  jog 10 0 0       - Jog +10mm in X direction
  jog 0 0 -5       - Jog -5mm in Z direction
  goto 100 50 -10  - Move to absolute position
  jog+ x 1         - Continuous jog X+ at default feed
  jog-stop         - Stop continuous jog
''')

    def enter_watch_mode(self):
        """Enter real-time status watch mode."""
        print('\n[WATCH MODE] Real-time status display')
        print('Press Ctrl+C to exit watch mode\n')
        self.watch_mode = True

        try:
            while self.watch_mode:
                # Spin to process callbacks
                rclpy.spin_once(self, timeout_sec=0.1)

                # If no status received, show waiting message
                if self.current_status is None and self.current_grbl_status is None:
                    print('\rWaiting for machine status...', end='', flush=True)

        except KeyboardInterrupt:
            pass
        finally:
            self.watch_mode = False
            print('\n\n[WATCH MODE] Exited')

    def run_interactive(self):
        """Run interactive command loop."""
        print('=' * 50)
        print('CNC Control Client - Enhanced Interactive Mode')
        print('=' * 50)
        print('Type "help" for commands, "quit" to exit')
        print()

        while True:
            try:
                # Spin briefly to process any pending callbacks
                rclpy.spin_once(self, timeout_sec=0.01)

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

                elif command == 'watch':
                    self.enter_watch_mode()

                elif command == 'home':
                    axes = parts[1].upper() if len(parts) > 1 else 'XYZ'
                    self.call_home(axes)

                elif command == 'jog':
                    if len(parts) >= 4:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        feed = float(parts[4]) if len(parts) > 4 else 1000.0
                        self.call_jog(x, y, z, jog_type=1, feed_rate=feed)
                    else:
                        print('Usage: jog X Y Z [feed_rate]')
                        print('  Example: jog 10 0 0')
                        print('  Example: jog 10 0 0 500')

                elif command == 'goto':
                    if len(parts) >= 4:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        feed = float(parts[4]) if len(parts) > 4 else 1000.0
                        self.call_jog(x, y, z, jog_type=2, feed_rate=feed)
                    else:
                        print('Usage: goto X Y Z [feed_rate]')

                elif command == 'jog+':
                    if len(parts) >= 3:
                        axis = parts[1]
                        dist = abs(float(parts[2]))
                        feed = float(parts[3]) if len(parts) > 3 else 1000.0
                        self.publish_jog_command(axis, dist, feed)
                    else:
                        print('Usage: jog+ AXIS DISTANCE [feed_rate]')
                        print('  Example: jog+ x 1')

                elif command == 'jog-':
                    if len(parts) >= 3:
                        axis = parts[1]
                        dist = -abs(float(parts[2]))
                        feed = float(parts[3]) if len(parts) > 3 else 1000.0
                        self.publish_jog_command(axis, dist, feed)
                    else:
                        print('Usage: jog- AXIS DISTANCE [feed_rate]')

                elif command == 'jog-stop':
                    self.stop_jog()

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
    node = EnhancedControlClient()

    # Use multi-threaded executor for subscription callbacks
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    # Run executor in background thread
    executor_thread = threading.Thread(target=executor.spin, daemon=True)
    executor_thread.start()

    try:
        node.run_interactive()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
