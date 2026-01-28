#!/usr/bin/env python3
"""
Digital Twin Node - Publish complete machine state for visualization

Aggregates machine status, sensor data, and G-code state into a unified
digital twin representation for Foxglove, RViz2, or custom visualizers.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from typing import Dict
import numpy as np
import json

from std_msgs.msg import String
from geometry_msgs.msg import Pose, Point, PoseStamped, TransformStamped
from visualization_msgs.msg import Marker, MarkerArray
from tf2_ros import TransformBroadcaster

from cnc_interfaces.msg import MachineStatus, DigitalTwinState, SensorReading


class DigitalTwinNode(Node):
    """Publish digital twin state for visualization"""

    def __init__(self):
        super().__init__('digital_twin_node')

        # Parameters
        self.declare_parameter('publish_rate', 30.0)
        self.declare_parameter('machine_model', '3axis_mill')
        self.declare_parameter('show_toolpath', True)
        self.declare_parameter('toolpath_length', 1000)

        self.publish_rate = self.get_parameter('publish_rate').value
        self.machine_model = self.get_parameter('machine_model').value
        self.show_toolpath = self.get_parameter('show_toolpath').value
        self.toolpath_length = self.get_parameter('toolpath_length').value

        # Machine state tracking
        self.machines: Dict[str, MachineStatus] = {}
        self.toolpaths: Dict[str, list] = {}

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # TF broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscribers
        self.status_sub = self.create_subscription(
            MachineStatus, '/machine/status',
            self.status_callback, qos
        )

        for ctrl in ['tinyg', 'grbl']:
            self.create_subscription(
                MachineStatus, f'/{ctrl}/status',
                self.status_callback, qos
            )

        # Publishers
        self.twin_pub = self.create_publisher(
            DigitalTwinState,
            '/visualization/digital_twin',
            qos
        )

        self.marker_pub = self.create_publisher(
            MarkerArray,
            '/visualization/markers',
            qos
        )

        self.toolpath_pub = self.create_publisher(
            Marker,
            '/visualization/toolpath',
            qos
        )

        # Timer for publishing
        self.pub_timer = self.create_timer(
            1.0 / self.publish_rate,
            self.publish_callback
        )

        self.get_logger().info('Digital Twin Node started')

    def status_callback(self, msg: MachineStatus):
        """Update machine state"""
        machine_id = msg.machine_id
        self.machines[machine_id] = msg

        # Track toolpath
        if machine_id not in self.toolpaths:
            self.toolpaths[machine_id] = []

        # Add position to toolpath during cutting
        if msg.state == MachineStatus.STATE_RUN:
            pos = (msg.wpos_x, msg.wpos_y, msg.wpos_z)
            path = self.toolpaths[machine_id]

            # Only add if position changed
            if not path or path[-1] != pos:
                path.append(pos)

                # Limit length
                if len(path) > self.toolpath_length:
                    self.toolpaths[machine_id] = path[-self.toolpath_length:]

    def publish_callback(self):
        """Publish digital twin state and visualization markers"""
        for machine_id, status in self.machines.items():
            # Publish DigitalTwinState
            twin = self.create_twin_state(machine_id, status)
            self.twin_pub.publish(twin)

            # Publish TF transforms
            self.publish_transforms(machine_id, status)

            # Publish markers
            markers = self.create_markers(machine_id, status)
            self.marker_pub.publish(markers)

            # Publish toolpath
            if self.show_toolpath and machine_id in self.toolpaths:
                toolpath = self.create_toolpath_marker(
                    machine_id, self.toolpaths[machine_id]
                )
                self.toolpath_pub.publish(toolpath)

    def create_twin_state(self, machine_id: str, status: MachineStatus) -> DigitalTwinState:
        """Create digital twin state message"""
        twin = DigitalTwinState()
        twin.header.stamp = self.get_clock().now().to_msg()
        twin.header.frame_id = f"{machine_id}_base"

        twin.machine_id = machine_id
        twin.machine_type = self.machine_model
        twin.machine_model = status.controller_type

        # Tool pose
        twin.tool_pose.position.x = status.wpos_x / 1000.0  # Convert mm to m
        twin.tool_pose.position.y = status.wpos_y / 1000.0
        twin.tool_pose.position.z = status.wpos_z / 1000.0

        # Joint positions (X, Y, Z for 3-axis)
        twin.joint_positions = [status.wpos_x, status.wpos_y, status.wpos_z]
        twin.axis_positions = [
            status.wpos_x, status.wpos_y, status.wpos_z,
            status.wpos_a, status.wpos_b, status.wpos_c
        ]

        # Spindle
        twin.spindle_speed = status.spindle_speed
        twin.spindle_running = status.spindle_cw or status.spindle_ccw

        # Coolant
        twin.coolant_flood_active = status.coolant_flood
        twin.coolant_mist_active = status.coolant_mist

        # Visualization settings
        twin.show_toolpath = self.show_toolpath
        twin.show_work_envelope = True
        twin.show_collision_zones = True

        return twin

    def publish_transforms(self, machine_id: str, status: MachineStatus):
        """Publish TF transforms for machine components"""
        stamp = self.get_clock().now().to_msg()

        # Base to table
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = f"{machine_id}_base"
        t.child_frame_id = f"{machine_id}_table"
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.0
        t.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t)

        # Table to spindle (inverted - spindle moves, not table)
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = f"{machine_id}_table"
        t.child_frame_id = f"{machine_id}_spindle"
        t.transform.translation.x = status.wpos_x / 1000.0
        t.transform.translation.y = status.wpos_y / 1000.0
        t.transform.translation.z = status.wpos_z / 1000.0 + 0.1  # Spindle above Z
        t.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t)

        # Spindle to tool tip
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = f"{machine_id}_spindle"
        t.child_frame_id = f"{machine_id}_tool_tip"
        t.transform.translation.z = -0.05  # 50mm tool
        t.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t)

    def create_markers(self, machine_id: str, status: MachineStatus) -> MarkerArray:
        """Create visualization markers for machine components"""
        markers = MarkerArray()
        stamp = self.get_clock().now().to_msg()

        # Work envelope (wireframe box)
        envelope = Marker()
        envelope.header.stamp = stamp
        envelope.header.frame_id = f"{machine_id}_base"
        envelope.ns = f"{machine_id}_envelope"
        envelope.id = 0
        envelope.type = Marker.LINE_LIST
        envelope.action = Marker.ADD
        envelope.scale.x = 0.002  # Line width

        envelope.color.r = 0.5
        envelope.color.g = 0.5
        envelope.color.b = 0.5
        envelope.color.a = 0.5

        # Box corners (300x200x100 mm work envelope)
        corners = [
            (0, 0, 0), (0.3, 0, 0), (0.3, 0.2, 0), (0, 0.2, 0),
            (0, 0, -0.1), (0.3, 0, -0.1), (0.3, 0.2, -0.1), (0, 0.2, -0.1)
        ]

        # Box edges
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom
            (4, 5), (5, 6), (6, 7), (7, 4),  # Top
            (0, 4), (1, 5), (2, 6), (3, 7),  # Verticals
        ]

        for e in edges:
            p1, p2 = corners[e[0]], corners[e[1]]
            envelope.points.append(Point(x=p1[0], y=p1[1], z=p1[2]))
            envelope.points.append(Point(x=p2[0], y=p2[1], z=p2[2]))

        markers.markers.append(envelope)

        # Tool (cylinder)
        tool = Marker()
        tool.header.stamp = stamp
        tool.header.frame_id = f"{machine_id}_tool_tip"
        tool.ns = f"{machine_id}_tool"
        tool.id = 1
        tool.type = Marker.CYLINDER
        tool.action = Marker.ADD
        tool.scale.x = 0.006  # 6mm diameter
        tool.scale.y = 0.006
        tool.scale.z = 0.05   # 50mm length
        tool.pose.position.z = 0.025  # Center of cylinder

        # Color based on state
        if status.state == MachineStatus.STATE_RUN:
            tool.color.r = 0.0
            tool.color.g = 1.0
            tool.color.b = 0.0
        elif status.state == MachineStatus.STATE_ALARM:
            tool.color.r = 1.0
            tool.color.g = 0.0
            tool.color.b = 0.0
        else:
            tool.color.r = 0.5
            tool.color.g = 0.5
            tool.color.b = 0.5
        tool.color.a = 1.0

        markers.markers.append(tool)

        # Current position marker
        pos_marker = Marker()
        pos_marker.header.stamp = stamp
        pos_marker.header.frame_id = f"{machine_id}_base"
        pos_marker.ns = f"{machine_id}_position"
        pos_marker.id = 2
        pos_marker.type = Marker.SPHERE
        pos_marker.action = Marker.ADD
        pos_marker.pose.position.x = status.wpos_x / 1000.0
        pos_marker.pose.position.y = status.wpos_y / 1000.0
        pos_marker.pose.position.z = status.wpos_z / 1000.0
        pos_marker.scale.x = 0.01
        pos_marker.scale.y = 0.01
        pos_marker.scale.z = 0.01
        pos_marker.color.r = 1.0
        pos_marker.color.g = 0.5
        pos_marker.color.b = 0.0
        pos_marker.color.a = 1.0

        markers.markers.append(pos_marker)

        return markers

    def create_toolpath_marker(self, machine_id: str, path: list) -> Marker:
        """Create toolpath line strip marker"""
        marker = Marker()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = f"{machine_id}_base"
        marker.ns = f"{machine_id}_toolpath"
        marker.id = 0
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        marker.scale.x = 0.001  # Line width

        marker.color.r = 0.0
        marker.color.g = 0.5
        marker.color.b = 1.0
        marker.color.a = 0.8

        for pos in path:
            p = Point()
            p.x = pos[0] / 1000.0
            p.y = pos[1] / 1000.0
            p.z = pos[2] / 1000.0
            marker.points.append(p)

        return marker


def main(args=None):
    rclpy.init(args=args)
    node = DigitalTwinNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
