#!/usr/bin/env python3
"""
LEGO MCP Alvik AGV Simulator

Simulates Alvik AGVs for testing without hardware.
Emulates micro-ROS topics and behavior including:
- Odometry with realistic motion model
- Battery discharge simulation
- ToF sensor simulation
- Task execution simulation

LEGO MCP Manufacturing System v7.0
"""

import json
import math
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, ColorRGBA, Int32MultiArray
from geometry_msgs.msg import Twist, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, Range, BatteryState


@dataclass
class SimulatedState:
    """Simulated AGV state."""
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    vx: float = 0.0
    vtheta: float = 0.0
    battery: float = 100.0
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    target_theta: Optional[float] = None


class AlvikSimulatorNode(Node):
    """
    Simulates a single Alvik AGV.

    Publishes simulated sensor data and responds to
    velocity commands and task commands.
    """

    def __init__(self, agv_id: str = 'alvik_01'):
        super().__init__(f'alvik_sim_{agv_id}')

        self.agv_id = agv_id

        # Parameters
        self.declare_parameter('agv_id', agv_id)
        self.declare_parameter('initial_x', 0.0)
        self.declare_parameter('initial_y', 0.0)
        self.declare_parameter('initial_theta', 0.0)
        self.declare_parameter('max_linear_vel', 0.3)
        self.declare_parameter('max_angular_vel', 1.5)
        self.declare_parameter('battery_discharge_rate', 0.01)  # % per second while moving
        self.declare_parameter('update_rate', 50.0)  # Hz

        initial_x = self.get_parameter('initial_x').value
        initial_y = self.get_parameter('initial_y').value
        initial_theta = self.get_parameter('initial_theta').value
        self.max_linear = self.get_parameter('max_linear_vel').value
        self.max_angular = self.get_parameter('max_angular_vel').value
        self.discharge_rate = self.get_parameter('battery_discharge_rate').value
        self.update_rate = self.get_parameter('update_rate').value

        # State
        self.state = SimulatedState(
            x=initial_x,
            y=initial_y,
            theta=initial_theta,
        )
        self.cmd_vx = 0.0
        self.cmd_vtheta = 0.0
        self.is_charging = False
        self.led_color = (0.0, 1.0, 0.0)  # Green = idle
        self.current_task: Optional[dict] = None

        # Simulated obstacles (for ToF sensors)
        self.obstacles = [
            {'x': 0.8, 'y': 0.0, 'radius': 0.1},  # Near printer
            {'x': 0.2, 'y': 0.6, 'radius': 0.1},  # Near CNC
        ]

        self.cb_group = ReentrantCallbackGroup()

        # Publishers (simulating micro-ROS outputs)
        self.odom_pub = self.create_publisher(
            Odometry, f'/{agv_id}/odom', 10
        )
        self.imu_pub = self.create_publisher(
            Imu, f'/{agv_id}/imu', 10
        )
        self.tof_front_pub = self.create_publisher(
            Range, f'/{agv_id}/tof_front', 10
        )
        self.tof_left_pub = self.create_publisher(
            Range, f'/{agv_id}/tof_left', 10
        )
        self.tof_right_pub = self.create_publisher(
            Range, f'/{agv_id}/tof_right', 10
        )
        self.line_pub = self.create_publisher(
            Int32MultiArray, f'/{agv_id}/line_sensors', 10
        )
        self.battery_pub = self.create_publisher(
            BatteryState, f'/{agv_id}/battery', 10
        )
        self.status_pub = self.create_publisher(
            String, f'/{agv_id}/status', 10
        )

        # Subscribers (simulating micro-ROS inputs)
        self.create_subscription(
            Twist, f'/{agv_id}/cmd_vel',
            self._on_cmd_vel, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Twist, f'/{agv_id}/cmd_vel_nav',
            self._on_cmd_vel, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            ColorRGBA, f'/{agv_id}/led_cmd',
            self._on_led_cmd, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            String, f'/{agv_id}/task_command',
            self._on_task_command, 10,
            callback_group=self.cb_group
        )

        # Simulation timer
        self.sim_timer = self.create_timer(
            1.0 / self.update_rate, self._update_simulation,
            callback_group=self.cb_group
        )

        # Status publish timer
        self.status_timer = self.create_timer(
            0.5, self._publish_status,
            callback_group=self.cb_group
        )

        self.get_logger().info(f'Alvik simulator started for {agv_id}')

    def _on_cmd_vel(self, msg: Twist):
        """Handle velocity commands."""
        self.cmd_vx = max(-self.max_linear, min(self.max_linear, msg.linear.x))
        self.cmd_vtheta = max(-self.max_angular, min(self.max_angular, msg.angular.z))

    def _on_led_cmd(self, msg: ColorRGBA):
        """Handle LED commands."""
        self.led_color = (msg.r, msg.g, msg.b)

    def _on_task_command(self, msg: String):
        """Handle task commands from fleet manager."""
        try:
            data = json.loads(msg.data)
            command = data.get('command')

            if command == 'execute_task':
                self.current_task = data
                dest = data.get('destination_pose', {})
                self.state.target_x = dest.get('x')
                self.state.target_y = dest.get('y')
                self.state.target_theta = dest.get('yaw', 0)
                self.get_logger().info(
                    f'Task received: {data.get("task_id")} -> ({self.state.target_x}, {self.state.target_y})'
                )

            elif command == 'cancel_task':
                self.current_task = None
                self.state.target_x = None
                self.state.target_y = None
                self.cmd_vx = 0.0
                self.cmd_vtheta = 0.0

            elif command == 'emergency_stop':
                self.cmd_vx = 0.0
                self.cmd_vtheta = 0.0
                self.current_task = None

        except json.JSONDecodeError:
            pass

    def _update_simulation(self):
        """Update simulation state."""
        dt = 1.0 / self.update_rate

        # Simple navigation if we have a target
        if self.state.target_x is not None and self.state.target_y is not None:
            self._navigate_to_target()

        # Update position using differential drive kinematics
        self.state.vx = self.cmd_vx
        self.state.vtheta = self.cmd_vtheta

        # Add noise for realism
        noise_v = random.gauss(0, 0.001)
        noise_theta = random.gauss(0, 0.001)

        self.state.x += (self.state.vx + noise_v) * math.cos(self.state.theta) * dt
        self.state.y += (self.state.vx + noise_v) * math.sin(self.state.theta) * dt
        self.state.theta += (self.state.vtheta + noise_theta) * dt

        # Normalize theta
        while self.state.theta > math.pi:
            self.state.theta -= 2 * math.pi
        while self.state.theta < -math.pi:
            self.state.theta += 2 * math.pi

        # Battery simulation
        if abs(self.state.vx) > 0.01 or abs(self.state.vtheta) > 0.01:
            self.state.battery -= self.discharge_rate * dt
            self.state.battery = max(0, self.state.battery)

        if self.is_charging:
            self.state.battery += 0.1 * dt
            self.state.battery = min(100, self.state.battery)

        # Publish sensor data
        self._publish_odometry()
        self._publish_imu()
        self._publish_tof_sensors()
        self._publish_battery()

    def _navigate_to_target(self):
        """Simple P-controller navigation to target."""
        dx = self.state.target_x - self.state.x
        dy = self.state.target_y - self.state.y
        distance = math.sqrt(dx*dx + dy*dy)

        if distance < 0.05:  # Reached target
            self.cmd_vx = 0.0
            self.cmd_vtheta = 0.0

            # Check if task complete
            if self.current_task:
                self.get_logger().info(f'Task {self.current_task.get("task_id")} completed')
                self.current_task = None
                self.state.target_x = None
                self.state.target_y = None
            return

        # Calculate desired heading
        desired_theta = math.atan2(dy, dx)
        theta_error = desired_theta - self.state.theta

        # Normalize angle error
        while theta_error > math.pi:
            theta_error -= 2 * math.pi
        while theta_error < -math.pi:
            theta_error += 2 * math.pi

        # Control
        if abs(theta_error) > 0.1:
            # Turn first
            self.cmd_vx = 0.0
            self.cmd_vtheta = 1.0 * theta_error
        else:
            # Move forward
            self.cmd_vx = min(0.2, 0.5 * distance)
            self.cmd_vtheta = 0.5 * theta_error

    def _publish_odometry(self):
        """Publish odometry message."""
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = f'{self.agv_id}/odom'
        msg.child_frame_id = f'{self.agv_id}/base_link'

        msg.pose.pose.position.x = self.state.x
        msg.pose.pose.position.y = self.state.y
        msg.pose.pose.position.z = 0.0

        # Convert theta to quaternion
        msg.pose.pose.orientation = self._euler_to_quaternion(0, 0, self.state.theta)

        msg.twist.twist.linear.x = self.state.vx
        msg.twist.twist.angular.z = self.state.vtheta

        self.odom_pub.publish(msg)

    def _publish_imu(self):
        """Publish IMU message."""
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = f'{self.agv_id}/imu_link'

        msg.orientation = self._euler_to_quaternion(0, 0, self.state.theta)
        msg.angular_velocity.z = self.state.vtheta

        # Simulated accelerometer (with noise)
        msg.linear_acceleration.x = random.gauss(0, 0.1)
        msg.linear_acceleration.y = random.gauss(0, 0.1)
        msg.linear_acceleration.z = 9.81 + random.gauss(0, 0.1)

        self.imu_pub.publish(msg)

    def _publish_tof_sensors(self):
        """Publish ToF sensor readings."""
        now = self.get_clock().now().to_msg()

        # Front sensor
        front_range = self._calculate_tof_range(self.state.theta)
        front_msg = Range()
        front_msg.header.stamp = now
        front_msg.header.frame_id = f'{self.agv_id}/tof_front'
        front_msg.radiation_type = Range.INFRARED
        front_msg.field_of_view = 0.44  # ~25 degrees
        front_msg.min_range = 0.02
        front_msg.max_range = 2.0
        front_msg.range = front_range
        self.tof_front_pub.publish(front_msg)

        # Left sensor
        left_range = self._calculate_tof_range(self.state.theta + math.pi/2)
        left_msg = Range()
        left_msg.header.stamp = now
        left_msg.header.frame_id = f'{self.agv_id}/tof_left'
        left_msg.radiation_type = Range.INFRARED
        left_msg.field_of_view = 0.44
        left_msg.min_range = 0.02
        left_msg.max_range = 2.0
        left_msg.range = left_range
        self.tof_left_pub.publish(left_msg)

        # Right sensor
        right_range = self._calculate_tof_range(self.state.theta - math.pi/2)
        right_msg = Range()
        right_msg.header.stamp = now
        right_msg.header.frame_id = f'{self.agv_id}/tof_right'
        right_msg.radiation_type = Range.INFRARED
        right_msg.field_of_view = 0.44
        right_msg.min_range = 0.02
        right_msg.max_range = 2.0
        right_msg.range = right_range
        self.tof_right_pub.publish(right_msg)

    def _calculate_tof_range(self, angle: float) -> float:
        """Calculate ToF range in given direction."""
        max_range = 2.0
        min_dist = max_range

        # Ray cast against obstacles
        for obs in self.obstacles:
            dx = obs['x'] - self.state.x
            dy = obs['y'] - self.state.y
            dist_to_center = math.sqrt(dx*dx + dy*dy)

            # Angle to obstacle center
            angle_to_obs = math.atan2(dy, dx)
            angle_diff = abs(angle - angle_to_obs)

            # Check if obstacle is in sensor FOV
            if angle_diff < 0.3:  # ~17 degrees
                # Approximate distance to obstacle surface
                dist = dist_to_center - obs['radius']
                if dist < min_dist:
                    min_dist = dist

        # Add noise
        min_dist += random.gauss(0, 0.01)
        return max(0.02, min(max_range, min_dist))

    def _publish_battery(self):
        """Publish battery state."""
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = 3.7 * (self.state.battery / 100.0) + 3.0  # 3.0-3.7V range
        msg.percentage = self.state.battery / 100.0
        msg.present = True

        if self.is_charging:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_CHARGING
        elif self.state.battery > 95:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_FULL
        else:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING

        self.battery_pub.publish(msg)

    def _publish_status(self):
        """Publish comprehensive status."""
        # Determine state
        if abs(self.state.vx) > 0.01 or abs(self.state.vtheta) > 0.01:
            state = 'moving'
        elif self.is_charging:
            state = 'charging'
        else:
            state = 'idle'

        # Determine task state
        if self.current_task:
            task_state = 'navigating'
        else:
            task_state = 'none'

        status = {
            'agv_id': self.agv_id,
            'state': state,
            'task_state': task_state,
            'position': {
                'x': self.state.x,
                'y': self.state.y,
                'yaw': self.state.theta,
            },
            'velocity': {
                'linear': self.state.vx,
                'angular': self.state.vtheta,
            },
            'battery': {
                'percentage': self.state.battery,
                'is_charging': self.is_charging,
            },
            'task': {
                'task_id': self.current_task.get('task_id') if self.current_task else None,
            },
            'connectivity': {
                'last_seen': time.time(),
            },
        }

        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def _euler_to_quaternion(self, roll: float, pitch: float, yaw: float) -> Quaternion:
        """Convert Euler angles to quaternion."""
        q = Quaternion()
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        q.w = cr * cp * cy + sr * sp * sy
        q.x = sr * cp * cy - cr * sp * sy
        q.y = cr * sp * cy + sr * cp * sy
        q.z = cr * cp * sy - sr * sp * cy

        return q


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    import sys
    agv_id = 'alvik_01'
    for arg in sys.argv:
        if arg.startswith('agv_id:='):
            agv_id = arg.split(':=')[1]

    node = AlvikSimulatorNode(agv_id=agv_id)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
