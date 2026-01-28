#!/usr/bin/env python3
"""
LEGO MCP Alvik AGV Driver

ROS2 driver node for Arduino Alvik robots with ESP32 and micro-ROS.
Handles communication with the micro-ROS agent and provides a standard
ROS2 interface for AGV control.

The Alvik robot features:
- ESP32-S3 microcontroller with WiFi/BLE
- Two DC motors with encoders
- Time-of-Flight distance sensors
- IMU (accelerometer + gyroscope)
- RGB LEDs
- Line-following sensors
- Touch sensors

Micro-ROS Topics (from Alvik):
- /alvik_XX/odom (nav_msgs/Odometry)
- /alvik_XX/imu (sensor_msgs/Imu)
- /alvik_XX/tof_front (sensor_msgs/Range)
- /alvik_XX/tof_left (sensor_msgs/Range)
- /alvik_XX/tof_right (sensor_msgs/Range)
- /alvik_XX/line_sensors (std_msgs/Int32MultiArray)
- /alvik_XX/battery (sensor_msgs/BatteryState)

Micro-ROS Topics (to Alvik):
- /alvik_XX/cmd_vel (geometry_msgs/Twist)
- /alvik_XX/led_cmd (std_msgs/ColorRGBA)

LEGO MCP Manufacturing System v7.0
"""

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, ColorRGBA, Int32MultiArray, Bool
from std_srvs.srv import Trigger, SetBool
from geometry_msgs.msg import Twist, PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry, Path
from sensor_msgs.msg import Imu, Range, BatteryState
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped


class AlvikState(Enum):
    """Alvik operational states."""
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    IDLE = "idle"
    MOVING = "moving"
    CHARGING = "charging"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class TaskState(Enum):
    """Task execution states."""
    NONE = "none"
    PENDING = "pending"
    NAVIGATING = "navigating"
    LOADING = "loading"
    UNLOADING = "unloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AlvikStatus:
    """Complete status of an Alvik AGV."""
    agv_id: str
    state: AlvikState = AlvikState.UNKNOWN
    task_state: TaskState = TaskState.NONE

    # Position and motion
    position_x: float = 0.0
    position_y: float = 0.0
    orientation_yaw: float = 0.0
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0

    # Sensors
    tof_front: float = 0.0
    tof_left: float = 0.0
    tof_right: float = 0.0
    line_sensors: List[int] = field(default_factory=list)

    # Battery
    battery_voltage: float = 0.0
    battery_percentage: float = 0.0
    is_charging: bool = False

    # Task info
    current_task_id: Optional[str] = None
    current_waypoint: Optional[str] = None
    payload: Optional[str] = None

    # Connectivity
    last_seen: float = 0.0
    wifi_rssi: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'agv_id': self.agv_id,
            'state': self.state.value,
            'task_state': self.task_state.value,
            'position': {
                'x': self.position_x,
                'y': self.position_y,
                'yaw': self.orientation_yaw,
            },
            'velocity': {
                'linear': self.linear_velocity,
                'angular': self.angular_velocity,
            },
            'sensors': {
                'tof_front': self.tof_front,
                'tof_left': self.tof_left,
                'tof_right': self.tof_right,
                'line_sensors': self.line_sensors,
            },
            'battery': {
                'voltage': self.battery_voltage,
                'percentage': self.battery_percentage,
                'is_charging': self.is_charging,
            },
            'task': {
                'task_id': self.current_task_id,
                'waypoint': self.current_waypoint,
                'payload': self.payload,
            },
            'connectivity': {
                'last_seen': self.last_seen,
                'last_seen_iso': datetime.fromtimestamp(self.last_seen).isoformat() if self.last_seen else None,
                'wifi_rssi': self.wifi_rssi,
            },
        }


class AlvikDriverNode(Node):
    """
    ROS2 driver node for a single Alvik AGV.

    Bridges micro-ROS topics from the ESP32 to standard ROS2 interfaces
    and provides higher-level control services.
    """

    def __init__(self, agv_id: str = 'alvik_01'):
        super().__init__(f'alvik_driver_{agv_id}')

        self.agv_id = agv_id
        self.status = AlvikStatus(agv_id=agv_id)

        # Parameters
        self.declare_parameter('agv_id', agv_id)
        self.declare_parameter('base_frame', f'{agv_id}/base_link')
        self.declare_parameter('odom_frame', f'{agv_id}/odom')
        self.declare_parameter('max_linear_velocity', 0.3)  # m/s
        self.declare_parameter('max_angular_velocity', 1.5)  # rad/s
        self.declare_parameter('connection_timeout', 5.0)  # seconds
        self.declare_parameter('wheel_base', 0.098)  # meters
        self.declare_parameter('wheel_radius', 0.017)  # meters

        self.base_frame = self.get_parameter('base_frame').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.max_linear_vel = self.get_parameter('max_linear_velocity').value
        self.max_angular_vel = self.get_parameter('max_angular_velocity').value
        self.connection_timeout = self.get_parameter('connection_timeout').value

        # Callback group for concurrent callbacks
        self.cb_group = ReentrantCallbackGroup()

        # QoS profiles
        self.sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # TF broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)

        # === Subscribers from micro-ROS (Alvik) ===
        self.create_subscription(
            Odometry, f'/{agv_id}/odom',
            self._on_odom, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Imu, f'/{agv_id}/imu',
            self._on_imu, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Range, f'/{agv_id}/tof_front',
            self._on_tof_front, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Range, f'/{agv_id}/tof_left',
            self._on_tof_left, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Range, f'/{agv_id}/tof_right',
            self._on_tof_right, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            Int32MultiArray, f'/{agv_id}/line_sensors',
            self._on_line_sensors, self.sensor_qos,
            callback_group=self.cb_group
        )
        self.create_subscription(
            BatteryState, f'/{agv_id}/battery',
            self._on_battery, self.sensor_qos,
            callback_group=self.cb_group
        )

        # === Publishers to micro-ROS (Alvik) ===
        self.cmd_vel_pub = self.create_publisher(
            Twist, f'/{agv_id}/cmd_vel', 10
        )
        self.led_pub = self.create_publisher(
            ColorRGBA, f'/{agv_id}/led_cmd', 10
        )

        # === Publishers for ROS2 ecosystem ===
        self.status_pub = self.create_publisher(
            String, f'/{agv_id}/status', 10
        )
        self.pose_pub = self.create_publisher(
            PoseStamped, f'/{agv_id}/pose', 10
        )

        # === Subscribers from navigation/control ===
        self.create_subscription(
            Twist, f'/{agv_id}/cmd_vel_nav',
            self._on_cmd_vel_nav, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            PoseStamped, f'/{agv_id}/goal_pose',
            self._on_goal_pose, 10,
            callback_group=self.cb_group
        )

        # === Services ===
        self.create_service(
            Trigger, f'/{agv_id}/stop',
            self._srv_stop, callback_group=self.cb_group
        )
        self.create_service(
            SetBool, f'/{agv_id}/enable',
            self._srv_enable, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, f'/{agv_id}/home',
            self._srv_home, callback_group=self.cb_group
        )

        # State
        self.enabled = True
        self.goal_pose: Optional[PoseStamped] = None
        self.current_path: Optional[Path] = None

        # Timers
        self.status_timer = self.create_timer(
            0.5, self._publish_status, callback_group=self.cb_group
        )
        self.connection_timer = self.create_timer(
            1.0, self._check_connection, callback_group=self.cb_group
        )

        self.get_logger().info(f'Alvik driver initialized for {agv_id}')

    # === Sensor Callbacks ===

    def _on_odom(self, msg: Odometry):
        """Handle odometry from micro-ROS."""
        self.status.last_seen = time.time()

        # Update position
        self.status.position_x = msg.pose.pose.position.x
        self.status.position_y = msg.pose.pose.position.y

        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.status.orientation_yaw = math.atan2(siny_cosp, cosy_cosp)

        # Update velocity
        self.status.linear_velocity = msg.twist.twist.linear.x
        self.status.angular_velocity = msg.twist.twist.angular.z

        # Broadcast TF
        self._broadcast_tf(msg)

        # Publish pose
        pose_msg = PoseStamped()
        pose_msg.header = msg.header
        pose_msg.pose = msg.pose.pose
        self.pose_pub.publish(pose_msg)

        # Update state based on motion
        if self.status.state not in [AlvikState.ERROR, AlvikState.EMERGENCY_STOP,
                                      AlvikState.CHARGING, AlvikState.DISCONNECTED]:
            if abs(self.status.linear_velocity) > 0.01 or abs(self.status.angular_velocity) > 0.1:
                self.status.state = AlvikState.MOVING
            else:
                self.status.state = AlvikState.IDLE

    def _on_imu(self, msg: Imu):
        """Handle IMU data from micro-ROS."""
        self.status.last_seen = time.time()
        # IMU data can be used for more accurate orientation estimation
        # or detecting collisions/tips

    def _on_tof_front(self, msg: Range):
        """Handle front ToF sensor."""
        self.status.last_seen = time.time()
        self.status.tof_front = msg.range

        # Collision avoidance
        if msg.range < 0.05 and self.status.state == AlvikState.MOVING:
            self.get_logger().warn(f'{self.agv_id}: Obstacle detected at {msg.range:.3f}m!')
            self._emergency_stop("Front obstacle detected")

    def _on_tof_left(self, msg: Range):
        """Handle left ToF sensor."""
        self.status.last_seen = time.time()
        self.status.tof_left = msg.range

    def _on_tof_right(self, msg: Range):
        """Handle right ToF sensor."""
        self.status.last_seen = time.time()
        self.status.tof_right = msg.range

    def _on_line_sensors(self, msg: Int32MultiArray):
        """Handle line-following sensors."""
        self.status.last_seen = time.time()
        self.status.line_sensors = list(msg.data)

    def _on_battery(self, msg: BatteryState):
        """Handle battery status."""
        self.status.last_seen = time.time()
        self.status.battery_voltage = msg.voltage
        self.status.battery_percentage = msg.percentage * 100
        self.status.is_charging = msg.power_supply_status == BatteryState.POWER_SUPPLY_STATUS_CHARGING

        # Update state if charging
        if self.status.is_charging:
            self.status.state = AlvikState.CHARGING

        # Low battery warning
        if self.status.battery_percentage < 20 and not self.status.is_charging:
            self.get_logger().warn(f'{self.agv_id}: Low battery ({self.status.battery_percentage:.1f}%)')

    # === Control Callbacks ===

    def _on_cmd_vel_nav(self, msg: Twist):
        """Handle velocity commands from navigation stack."""
        if not self.enabled:
            return

        if self.status.state in [AlvikState.ERROR, AlvikState.EMERGENCY_STOP]:
            return

        # Clamp velocities
        cmd = Twist()
        cmd.linear.x = max(-self.max_linear_vel, min(self.max_linear_vel, msg.linear.x))
        cmd.angular.z = max(-self.max_angular_vel, min(self.max_angular_vel, msg.angular.z))

        self.cmd_vel_pub.publish(cmd)

    def _on_goal_pose(self, msg: PoseStamped):
        """Handle goal pose for navigation."""
        self.goal_pose = msg
        self.get_logger().info(
            f'{self.agv_id}: New goal at ({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f})'
        )

    # === Services ===

    def _srv_stop(self, request, response):
        """Emergency stop service."""
        self._emergency_stop("Stop service called")
        response.success = True
        response.message = f"{self.agv_id} stopped"
        return response

    def _srv_enable(self, request, response):
        """Enable/disable AGV."""
        self.enabled = request.data
        if not self.enabled:
            self._send_stop_command()
            self.status.state = AlvikState.IDLE
        response.success = True
        response.message = f"{self.agv_id} {'enabled' if self.enabled else 'disabled'}"
        return response

    def _srv_home(self, request, response):
        """Send AGV to home/charging station."""
        self.get_logger().info(f'{self.agv_id}: Homing requested')

        # Define home position (charging station)
        # This can be configured via parameters in a real deployment
        home_pose = PoseStamped()
        home_pose.header.stamp = self.get_clock().now().to_msg()
        home_pose.header.frame_id = 'map'
        home_pose.pose.position.x = 0.0  # Home X coordinate
        home_pose.pose.position.y = 0.0  # Home Y coordinate
        home_pose.pose.position.z = 0.0
        # Orientation facing charging station (0 degrees = facing +X)
        home_pose.pose.orientation.w = 1.0
        home_pose.pose.orientation.x = 0.0
        home_pose.pose.orientation.y = 0.0
        home_pose.pose.orientation.z = 0.0

        # Calculate simple path to home using current position
        # For a full implementation, this would integrate with Nav2 or a path planner
        self._navigate_to_pose(home_pose)

        response.success = True
        response.message = f"{self.agv_id} homing initiated"
        return response

    def _navigate_to_pose(self, goal: PoseStamped):
        """Navigate to a target pose using simple proportional control."""
        self.goal_pose = goal
        self.status.task_state = TaskState.NAVIGATING
        self.status.current_waypoint = 'home'

        # Start navigation timer if not already running
        if not hasattr(self, '_nav_timer') or self._nav_timer is None:
            self._nav_timer = self.create_timer(
                0.1, self._navigation_step, callback_group=self.cb_group
            )

    def _navigation_step(self):
        """Execute one step of proportional navigation toward goal."""
        if self.goal_pose is None:
            if hasattr(self, '_nav_timer') and self._nav_timer is not None:
                self._nav_timer.cancel()
                self._nav_timer = None
            return

        if not self.enabled or self.status.state in [AlvikState.ERROR, AlvikState.EMERGENCY_STOP]:
            self._send_stop_command()
            return

        # Calculate distance and angle to goal
        dx = self.goal_pose.pose.position.x - self.status.position_x
        dy = self.goal_pose.pose.position.y - self.status.position_y
        distance = math.sqrt(dx * dx + dy * dy)

        # Calculate desired heading
        target_yaw = math.atan2(dy, dx)
        yaw_error = self._normalize_angle(target_yaw - self.status.orientation_yaw)

        # Check if we've reached the goal
        position_tolerance = 0.05  # 5cm
        angle_tolerance = 0.1  # ~6 degrees

        if distance < position_tolerance:
            # At goal position, align with goal orientation
            q = self.goal_pose.pose.orientation
            goal_yaw = math.atan2(2 * (q.w * q.z + q.x * q.y),
                                  1 - 2 * (q.y * q.y + q.z * q.z))
            final_yaw_error = self._normalize_angle(goal_yaw - self.status.orientation_yaw)

            if abs(final_yaw_error) < angle_tolerance:
                # Navigation complete
                self._send_stop_command()
                self.goal_pose = None
                self.status.task_state = TaskState.COMPLETED
                self.status.current_waypoint = None
                self.get_logger().info(f'{self.agv_id}: Reached home position')

                # Set LED to green
                self.set_led_color(0.0, 1.0, 0.0)

                if hasattr(self, '_nav_timer') and self._nav_timer is not None:
                    self._nav_timer.cancel()
                    self._nav_timer = None
                return
            else:
                # Rotate to final orientation
                cmd = Twist()
                cmd.angular.z = max(-self.max_angular_vel,
                                   min(self.max_angular_vel, 1.5 * final_yaw_error))
                self.cmd_vel_pub.publish(cmd)
        else:
            # Navigate toward goal
            cmd = Twist()

            # First rotate toward goal if angle error is large
            if abs(yaw_error) > 0.3:  # ~17 degrees
                cmd.linear.x = 0.0
                cmd.angular.z = max(-self.max_angular_vel,
                                   min(self.max_angular_vel, 1.5 * yaw_error))
            else:
                # Move toward goal with proportional speed
                speed = min(self.max_linear_vel, 0.5 * distance)
                cmd.linear.x = speed
                cmd.angular.z = max(-self.max_angular_vel,
                                   min(self.max_angular_vel, 1.0 * yaw_error))

            self.cmd_vel_pub.publish(cmd)

        # Set LED to blue while navigating
        self.set_led_color(0.0, 0.0, 1.0)

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    # === Helper Methods ===

    def _broadcast_tf(self, odom_msg: Odometry):
        """Broadcast odom -> base_link transform."""
        t = TransformStamped()
        t.header.stamp = odom_msg.header.stamp
        t.header.frame_id = self.odom_frame
        t.child_frame_id = self.base_frame
        t.transform.translation.x = odom_msg.pose.pose.position.x
        t.transform.translation.y = odom_msg.pose.pose.position.y
        t.transform.translation.z = odom_msg.pose.pose.position.z
        t.transform.rotation = odom_msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(t)

    def _emergency_stop(self, reason: str):
        """Execute emergency stop."""
        self.get_logger().error(f'{self.agv_id}: EMERGENCY STOP - {reason}')
        self._send_stop_command()
        self.status.state = AlvikState.EMERGENCY_STOP

        # Set LED to red
        led_msg = ColorRGBA()
        led_msg.r = 1.0
        led_msg.g = 0.0
        led_msg.b = 0.0
        led_msg.a = 1.0
        self.led_pub.publish(led_msg)

    def _send_stop_command(self):
        """Send zero velocity command."""
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        self.cmd_vel_pub.publish(cmd)

    def _check_connection(self):
        """Check if AGV is still connected."""
        if self.status.last_seen == 0:
            return

        elapsed = time.time() - self.status.last_seen
        if elapsed > self.connection_timeout:
            if self.status.state != AlvikState.DISCONNECTED:
                self.get_logger().error(f'{self.agv_id}: Connection lost!')
                self.status.state = AlvikState.DISCONNECTED
        elif self.status.state == AlvikState.DISCONNECTED:
            self.get_logger().info(f'{self.agv_id}: Connection restored')
            self.status.state = AlvikState.IDLE

    def _publish_status(self):
        """Publish AGV status."""
        msg = String()
        msg.data = json.dumps(self.status.to_dict())
        self.status_pub.publish(msg)

    def set_led_color(self, r: float, g: float, b: float):
        """Set LED color (0.0-1.0 for each channel)."""
        led_msg = ColorRGBA()
        led_msg.r = r
        led_msg.g = g
        led_msg.b = b
        led_msg.a = 1.0
        self.led_pub.publish(led_msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    # Get AGV ID from command line or default
    import sys
    agv_id = 'alvik_01'
    for arg in sys.argv:
        if arg.startswith('agv_id:='):
            agv_id = arg.split(':=')[1]

    node = AlvikDriverNode(agv_id=agv_id)

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
