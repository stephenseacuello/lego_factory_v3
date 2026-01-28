#!/usr/bin/env python3
"""
Sensor Simulator Node
=====================
Simulates micro-ROS sensor nodes (ESP32/Arduino) for testing without hardware.

Publishes sensor data similar to what an ESP32 with MPU6050 would publish:
- /sensors/imu (sensor_msgs/Imu)
- /sensors/temperature (std_msgs/Float32)

This allows testing ROS 2 sensor processing pipelines without physical hardware.

Usage:
    ros2 run cnc_simulator sensor_simulator

Parameters:
    - publish_rate: Publishing frequency in Hz (default: 50)
    - sensor_id: Sensor frame ID (default: esp32_sim_001)
    - add_noise: Add realistic sensor noise (default: true)
"""

import rclpy
from rclpy.node import Node
import math
import random

from std_msgs.msg import Header, Float32
from sensor_msgs.msg import Imu


class SensorSimulatorNode(Node):
    """Simulates an ESP32 micro-ROS sensor node."""

    def __init__(self):
        super().__init__('sensor_simulator')

        # Parameters
        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('sensor_id', 'esp32_sim_001')
        self.declare_parameter('add_noise', True)

        self.publish_rate = self.get_parameter('publish_rate').value
        self.sensor_id = self.get_parameter('sensor_id').value
        self.add_noise = self.get_parameter('add_noise').value

        # Publishers
        self.imu_pub = self.create_publisher(Imu, '/sensors/imu', 10)
        self.temp_pub = self.create_publisher(Float32, '/sensors/temperature', 10)

        # Timer
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_sensor_data)

        # Simulation state
        self.time = 0.0
        self.machine_running = False  # Simulates spindle on/off

        self.get_logger().info('=' * 50)
        self.get_logger().info('Sensor Simulator Started')
        self.get_logger().info('=' * 50)
        self.get_logger().info(f'  Sensor ID: {self.sensor_id}')
        self.get_logger().info(f'  Rate: {self.publish_rate} Hz')
        self.get_logger().info(f'  Noise: {"enabled" if self.add_noise else "disabled"}')
        self.get_logger().info('=' * 50)
        self.get_logger().info('Publishing to /sensors/imu and /sensors/temperature')

    def publish_sensor_data(self):
        """Generate and publish simulated sensor data."""
        self.time += 1.0 / self.publish_rate
        now = self.get_clock().now()

        # Simulate machine state changes (spindle on/off every 30s)
        if int(self.time) % 60 < 30:
            self.machine_running = True
            vibration_amplitude = 0.5  # Higher vibration when running
        else:
            self.machine_running = False
            vibration_amplitude = 0.05  # Low vibration when idle

        # Generate IMU data
        imu_msg = Imu()
        imu_msg.header = Header()
        imu_msg.header.stamp = now.to_msg()
        imu_msg.header.frame_id = self.sensor_id

        # Accelerometer (m/s^2)
        # Gravity + vibration (simulates spindle vibration)
        vibration_freq = 120.0  # Hz (typical spindle frequency)
        vibration = math.sin(2 * math.pi * vibration_freq * self.time) * vibration_amplitude

        imu_msg.linear_acceleration.x = vibration * 0.8
        imu_msg.linear_acceleration.y = vibration * 0.6
        imu_msg.linear_acceleration.z = 9.81 + vibration * 0.3

        # Gyroscope (rad/s) - small rotational vibration
        imu_msg.angular_velocity.x = vibration * 0.01
        imu_msg.angular_velocity.y = vibration * 0.01
        imu_msg.angular_velocity.z = vibration * 0.005

        # Orientation (quaternion) - identity
        imu_msg.orientation.x = 0.0
        imu_msg.orientation.y = 0.0
        imu_msg.orientation.z = 0.0
        imu_msg.orientation.w = 1.0
        imu_msg.orientation_covariance[0] = -1  # Unknown

        # Add sensor noise
        if self.add_noise:
            noise_scale = 0.01
            imu_msg.linear_acceleration.x += random.gauss(0, noise_scale)
            imu_msg.linear_acceleration.y += random.gauss(0, noise_scale)
            imu_msg.linear_acceleration.z += random.gauss(0, noise_scale)
            imu_msg.angular_velocity.x += random.gauss(0, noise_scale * 0.1)
            imu_msg.angular_velocity.y += random.gauss(0, noise_scale * 0.1)
            imu_msg.angular_velocity.z += random.gauss(0, noise_scale * 0.1)

        # Temperature - gradual heating when running
        temp_msg = Float32()
        base_temp = 25.0
        if self.machine_running:
            # Temperature rises when machine is running
            heat_buildup = min(10.0, (self.time % 30) * 0.3)
            temp_msg.data = base_temp + heat_buildup
        else:
            # Temperature falls when idle
            temp_msg.data = base_temp + max(0, 5.0 - (self.time % 30) * 0.2)

        if self.add_noise:
            temp_msg.data += random.gauss(0, 0.1)

        # Publish
        self.imu_pub.publish(imu_msg)
        self.temp_pub.publish(temp_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SensorSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down sensor simulator...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
