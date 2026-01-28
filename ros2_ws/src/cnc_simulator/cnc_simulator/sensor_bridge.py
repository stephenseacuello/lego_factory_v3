"""
Sensor Bridge Node for micro-ROS Integration.

Converts generic sensor_msgs/Imu messages from micro-ROS ESP32 to
cnc_interfaces/SensorReading messages for unified sensor handling.

This allows the ESP32 to publish standard ROS messages while the rest of
the system works with cnc_interfaces custom messages.

Topics Subscribed:
- /sensors/imu (sensor_msgs/Imu) - From micro-ROS ESP32
- /sensors/temperature (std_msgs/Float32) - From micro-ROS ESP32

Topics Published:
- /sensors/raw (cnc_interfaces/SensorReading) - Unified sensor output
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from sensor_msgs.msg import Imu
from std_msgs.msg import Float32

from cnc_interfaces.msg import SensorReading


class SensorBridgeNode(Node):
    """Converts sensor_msgs to cnc_interfaces/SensorReading."""

    def __init__(self):
        super().__init__('sensor_bridge')

        # Declare parameters
        self.declare_parameter('publish_rate', 50.0)  # Hz
        self.declare_parameter('imu_topic', '/sensors/imu')
        self.declare_parameter('temp_topic', '/sensors/temperature')
        self.declare_parameter('output_topic', '/sensors/raw')

        # Get parameters
        self.imu_topic = self.get_parameter('imu_topic').value
        self.temp_topic = self.get_parameter('temp_topic').value
        self.output_topic = self.get_parameter('output_topic').value

        # QoS profile - best effort for high-frequency sensor data
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Reliable QoS for output
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribe to micro-ROS IMU topic
        self.imu_sub = self.create_subscription(
            Imu,
            self.imu_topic,
            self._imu_callback,
            sensor_qos
        )

        # Subscribe to micro-ROS temperature topic
        self.temp_sub = self.create_subscription(
            Float32,
            self.temp_topic,
            self._temp_callback,
            sensor_qos
        )

        # Publisher for unified SensorReading
        self.sensor_pub = self.create_publisher(
            SensorReading,
            self.output_topic,
            reliable_qos
        )

        # Cache latest temperature for combining with IMU data
        self.latest_temp = 25.0  # Default temperature

        # Statistics
        self.imu_count = 0
        self.temp_count = 0

        # Status timer
        self.create_timer(10.0, self._log_stats)

        self.get_logger().info(
            f'Sensor Bridge initialized. '
            f'IMU: {self.imu_topic}, Temp: {self.temp_topic} -> {self.output_topic}'
        )

    def _imu_callback(self, msg: Imu):
        """Convert IMU message to SensorReading and publish."""
        reading = SensorReading()

        # Use frame_id as sensor_id, or default
        reading.sensor_id = msg.header.frame_id if msg.header.frame_id else 'esp32_imu'
        reading.sensor_type = 'imu'

        # Pack IMU data into values array:
        # [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z]
        reading.values = [
            msg.linear_acceleration.x,
            msg.linear_acceleration.y,
            msg.linear_acceleration.z,
            msg.angular_velocity.x,
            msg.angular_velocity.y,
            msg.angular_velocity.z,
        ]

        reading.unit = 'm/s^2, rad/s'
        reading.header.stamp = msg.header.stamp
        reading.header.frame_id = reading.sensor_id

        self.sensor_pub.publish(reading)
        self.imu_count += 1

    def _temp_callback(self, msg: Float32):
        """Convert temperature message to SensorReading and publish."""
        self.latest_temp = msg.data

        reading = SensorReading()
        reading.sensor_id = 'esp32_temp'
        reading.sensor_type = 'temperature'
        reading.values = [msg.data]
        reading.unit = 'celsius'
        reading.header.stamp = self.get_clock().now().to_msg()
        reading.header.frame_id = reading.sensor_id

        self.sensor_pub.publish(reading)
        self.temp_count += 1

    def _log_stats(self):
        """Log statistics periodically."""
        self.get_logger().info(
            f'Sensor Bridge stats - IMU msgs: {self.imu_count}, '
            f'Temp msgs: {self.temp_count}'
        )


def main(args=None):
    """Entry point for sensor_bridge node."""
    rclpy.init(args=args)

    node = SensorBridgeNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
