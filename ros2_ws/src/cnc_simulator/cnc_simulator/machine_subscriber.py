#!/usr/bin/env python3
"""
CNC Machine Status Subscriber

Subscribes to machine status and:
- Monitors position limits
- Detects state changes
- Calculates statistics
- Logs warnings for anomalies

Subscribes to: /machine/status
               /machine/position
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
import json


class MachineSubscriber(Node):
    """Monitors CNC machine status and logs events."""

    def __init__(self):
        super().__init__('machine_subscriber')

        # Declare parameters for work envelope limits
        self.declare_parameter('x_max', 200.0)
        self.declare_parameter('y_max', 200.0)
        self.declare_parameter('z_max', 100.0)

        self.x_max = self.get_parameter('x_max').value
        self.y_max = self.get_parameter('y_max').value
        self.z_max = self.get_parameter('z_max').value

        # Subscribers
        self.status_sub = self.create_subscription(
            String,
            '/machine/status',
            self.status_callback,
            10
        )

        self.position_sub = self.create_subscription(
            PoseStamped,
            '/machine/position',
            self.position_callback,
            10
        )

        # State tracking
        self.last_state = None
        self.message_count = 0
        self.position_warnings = 0

        self.get_logger().info(
            f'Machine Subscriber started. Work envelope: '
            f'X={self.x_max}, Y={self.y_max}, Z={self.z_max}'
        )

    def status_callback(self, msg: String):
        """Process machine status JSON."""
        try:
            status = json.loads(msg.data)
            self.message_count += 1

            # Detect state changes
            current_state = status.get('state', 'unknown')
            if current_state != self.last_state:
                self.get_logger().info(
                    f"State change: {self.last_state} -> {current_state}"
                )
                self.last_state = current_state

                # Alert on alarm state
                if current_state == 'alarm':
                    self.get_logger().warn('ALARM: Machine entered alarm state!')

            # Log periodic status (every 50 messages)
            if self.message_count % 50 == 0:
                pos = status.get('position', {})
                self.get_logger().info(
                    f"Status #{self.message_count}: "
                    f"State={current_state}, "
                    f"Pos=({pos.get('x', 0):.1f}, {pos.get('y', 0):.1f}, {pos.get('z', 0):.1f}), "
                    f"Feed={status.get('feed_rate', 0):.0f} mm/min"
                )

        except json.JSONDecodeError as e:
            self.get_logger().error(f'Invalid JSON: {e}')

    def position_callback(self, msg: PoseStamped):
        """Check position against work envelope limits."""
        x = msg.pose.position.x
        y = msg.pose.position.y
        z = msg.pose.position.z

        # Check soft limits
        warnings = []
        if abs(x) > self.x_max:
            warnings.append(f'X={x:.1f} exceeds limit {self.x_max}')
        if abs(y) > self.y_max:
            warnings.append(f'Y={y:.1f} exceeds limit {self.y_max}')
        if abs(z) > self.z_max:
            warnings.append(f'Z={z:.1f} exceeds limit {self.z_max}')

        if warnings:
            self.position_warnings += 1
            if self.position_warnings <= 5:  # Don't spam logs
                self.get_logger().warn(f'Soft limit warning: {", ".join(warnings)}')


def main(args=None):
    rclpy.init(args=args)
    node = MachineSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info(
            f'Shutting down. Processed {node.message_count} messages, '
            f'{node.position_warnings} position warnings.'
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
