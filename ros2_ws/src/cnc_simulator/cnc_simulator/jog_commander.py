#!/usr/bin/env python3
"""
CNC Jog Commander

Publishes jog commands to control machine movement.
Demonstrates ROS 2 publishers with geometry_msgs/Twist.

Publishes to: /machine/jog_cmd
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys


class JogCommander(Node):
    """Sends jog commands to CNC machine."""

    def __init__(self):
        super().__init__('jog_commander')

        self.declare_parameter('feed_rate', 500.0)  # mm/min

        self.publisher = self.create_publisher(Twist, '/machine/jog_cmd', 10)
        self.feed_rate = self.get_parameter('feed_rate').value

        self.get_logger().info(f'Jog Commander ready. Feed rate: {self.feed_rate} mm/min')
        self.get_logger().info('Commands: x+, x-, y+, y-, z+, z-, stop, quit')

        # Create timer for interactive input
        self.timer = self.create_timer(0.1, self.check_input)
        self.pending_command = None

    def check_input(self):
        """Process pending jog command."""
        if self.pending_command:
            self.process_command(self.pending_command)
            self.pending_command = None

    def process_command(self, cmd: str):
        """Convert command string to Twist message."""
        msg = Twist()

        # Convert feed rate from mm/min to mm/s for velocity
        velocity = self.feed_rate / 60.0

        if cmd == 'x+':
            msg.linear.x = velocity
            self.get_logger().info(f'Jog X+ at {velocity:.1f} mm/s')
        elif cmd == 'x-':
            msg.linear.x = -velocity
            self.get_logger().info(f'Jog X- at {velocity:.1f} mm/s')
        elif cmd == 'y+':
            msg.linear.y = velocity
            self.get_logger().info(f'Jog Y+ at {velocity:.1f} mm/s')
        elif cmd == 'y-':
            msg.linear.y = -velocity
            self.get_logger().info(f'Jog Y- at {velocity:.1f} mm/s')
        elif cmd == 'z+':
            msg.linear.z = velocity
            self.get_logger().info(f'Jog Z+ at {velocity:.1f} mm/s')
        elif cmd == 'z-':
            msg.linear.z = -velocity
            self.get_logger().info(f'Jog Z- at {velocity:.1f} mm/s')
        elif cmd == 'stop':
            self.get_logger().info('Stop all movement')
        else:
            self.get_logger().warn(f'Unknown command: {cmd}')
            return

        self.publisher.publish(msg)

    def send_jog(self, direction: str):
        """Queue a jog command."""
        self.pending_command = direction


def main(args=None):
    rclpy.init(args=args)
    node = JogCommander()

    # Simple demo: send a sequence of jog commands
    import time

    node.get_logger().info('Demo: Sending jog sequence...')

    commands = ['x+', 'stop', 'y+', 'stop', 'z-', 'stop']

    for cmd in commands:
        node.send_jog(cmd)
        rclpy.spin_once(node, timeout_sec=0.5)
        time.sleep(1.0)

    node.get_logger().info('Demo complete!')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
