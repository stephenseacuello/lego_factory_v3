#!/usr/bin/env python3
"""
CNC Machine Status Publisher

Simulates TinyG machine status including:
- Position (X, Y, Z, A axes)
- Velocity and feed rate
- Machine state (idle, running, holding, alarm)
- Spindle speed

Publishes to: /machine/status (String JSON)
              /machine/position (geometry_msgs/PoseStamped)
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
import json
import math
import random


class MachinePublisher(Node):
    """Simulates a TinyG CNC machine publishing status updates."""

    def __init__(self):
        super().__init__('machine_publisher')

        # Declare parameters
        self.declare_parameter('machine_id', 'tinyg_001')
        self.declare_parameter('publish_rate', 10.0)  # Hz

        self.machine_id = self.get_parameter('machine_id').value
        publish_rate = self.get_parameter('publish_rate').value

        # Publishers
        self.status_pub = self.create_publisher(String, '/machine/status', 10)
        self.position_pub = self.create_publisher(PoseStamped, '/machine/position', 10)

        # Timer
        timer_period = 1.0 / publish_rate
        self.timer = self.create_timer(timer_period, self.timer_callback)

        # Simulated machine state
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}
        self.velocity = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.state = 'idle'  # idle, running, holding, alarm
        self.feed_rate = 0.0
        self.spindle_speed = 0.0
        self.line_number = 0

        # Simulation parameters
        self.sim_time = 0.0
        self.is_running_job = False

        self.get_logger().info(
            f'Machine Publisher started: {self.machine_id} @ {publish_rate} Hz'
        )

    def timer_callback(self):
        """Publish machine status at regular intervals."""
        self.sim_time += 0.1

        # Simulate machine movement (simple sine wave path)
        if self.is_running_job:
            self.position['x'] = 50.0 + 40.0 * math.sin(self.sim_time * 0.5)
            self.position['y'] = 50.0 + 40.0 * math.cos(self.sim_time * 0.5)
            self.position['z'] = -5.0 + 2.0 * math.sin(self.sim_time * 2.0)
            self.velocity['x'] = 20.0 * math.cos(self.sim_time * 0.5)
            self.velocity['y'] = -20.0 * math.sin(self.sim_time * 0.5)
            self.feed_rate = 1200.0
            self.spindle_speed = 12000.0
            self.state = 'running'
            self.line_number += 1
        else:
            self.velocity = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            self.feed_rate = 0.0
            self.state = 'idle'

        # Toggle job state every 30 seconds for demo
        if int(self.sim_time) % 30 == 0 and int(self.sim_time) > 0:
            self.is_running_job = not self.is_running_job
            if self.is_running_job:
                self.get_logger().info('Starting simulated G-code job')
            else:
                self.get_logger().info('Job complete, machine idle')

        # Publish JSON status
        self.publish_status()

        # Publish position as PoseStamped
        self.publish_position()

    def publish_status(self):
        """Publish machine status as JSON string."""
        status = {
            'machine_id': self.machine_id,
            'timestamp': self.get_clock().now().to_msg().sec,
            'state': self.state,
            'position': self.position,
            'velocity': self.velocity,
            'feed_rate': self.feed_rate,
            'spindle_speed': self.spindle_speed,
            'line_number': self.line_number,
            'units': 'mm',
            'coord_system': 'G54'
        }

        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def publish_position(self):
        """Publish position as geometry_msgs/PoseStamped."""
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'machine_base'

        # Position in mm
        msg.pose.position.x = self.position['x']
        msg.pose.position.y = self.position['y']
        msg.pose.position.z = self.position['z']

        # Orientation (no rotation for now)
        msg.pose.orientation.w = 1.0

        self.position_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MachinePublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
