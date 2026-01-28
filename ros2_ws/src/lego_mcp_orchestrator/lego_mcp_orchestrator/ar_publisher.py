#!/usr/bin/env python3
"""
LEGO MCP AR Publisher Node
Publishes AR guidance data via ROS2 topics for HoloLens/Quest/WebXR.

Provides:
- Visual markers for AR overlay
- Assembly step instructions
- Robot intent visualization
- Next brick placement guidance

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, ColorRGBA
from geometry_msgs.msg import Pose, Point, Quaternion, Vector3
from visualization_msgs.msg import Marker, MarkerArray

try:
    from lego_mcp_msgs.msg import AssemblyStep
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


@dataclass
class BrickMarker:
    """AR marker for a LEGO brick."""
    brick_id: str
    brick_type: str  # 2x4, 2x2, 1x4, etc.
    color: str
    position: List[float]  # x, y, z
    orientation: List[float]  # qx, qy, qz, qw
    alpha: float = 1.0  # Transparency
    highlight: bool = False
    state: str = 'placed'  # placed, ghost, highlight


class ARPublisherNode(Node):
    """
    Publishes AR guidance data via ROS2 topics.

    AR headsets can subscribe directly via rosbridge for real-time
    robot visualization and assembly guidance.
    """

    def __init__(self):
        super().__init__('ar_publisher')

        # Parameters
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('mesh_resource_prefix', 'package://lego_meshes/')

        self._publish_rate = self.get_parameter('publish_rate').value
        self._mesh_prefix = self.get_parameter('mesh_resource_prefix').value

        # Current assembly state
        self._current_step: int = 0
        self._total_steps: int = 0
        self._current_assembly_id: str = ''
        self._brick_markers: Dict[str, BrickMarker] = {}
        self._next_brick: Optional[BrickMarker] = None
        self._placed_bricks: List[str] = []

        # Robot path visualization
        self._robot_path: List[Pose] = []
        self._show_robot_intent: bool = True

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Publishers
        self._marker_pub = self.create_publisher(
            MarkerArray,
            '/lego_mcp/ar_markers',
            10
        )

        if MSGS_AVAILABLE:
            self._step_pub = self.create_publisher(
                AssemblyStep,
                '/lego_mcp/current_step',
                10
            )
        else:
            self._step_pub = self.create_publisher(
                String,
                '/lego_mcp/current_step',
                10
            )

        self._instructions_pub = self.create_publisher(
            String,
            '/lego_mcp/ar_instructions',
            10
        )

        # JSON markers for WebXR fallback
        self._json_markers_pub = self.create_publisher(
            String,
            '/lego_mcp/ar_markers_json',
            10
        )

        # Subscribers
        self.create_subscription(
            String,
            '/lego_mcp/assembly_start',
            self._on_assembly_start,
            10
        )

        self.create_subscription(
            String,
            '/lego_mcp/step_complete',
            self._on_step_complete,
            10
        )

        self.create_subscription(
            String,
            '/lego_mcp/user_confirm',
            self._on_user_confirm,
            10
        )

        # Timer for periodic updates
        self._publish_timer = self.create_timer(
            1.0 / self._publish_rate,
            self._publish_markers
        )

        self.get_logger().info("AR publisher node initialized")

    def _on_assembly_start(self, msg: String):
        """Handle new assembly sequence start."""
        try:
            data = json.loads(msg.data)
            self._current_assembly_id = data.get('assembly_id', '')
            self._total_steps = data.get('total_steps', 0)
            self._current_step = 0
            self._placed_bricks = []
            self._brick_markers = {}

            # Load assembly sequence
            steps = data.get('steps', [])
            for step in steps:
                brick = BrickMarker(
                    brick_id=step.get('brick_id', ''),
                    brick_type=step.get('brick_type', '2x4'),
                    color=step.get('color', 'red'),
                    position=step.get('position', [0, 0, 0]),
                    orientation=step.get('orientation', [0, 0, 0, 1]),
                    state='pending',
                    alpha=0.3,
                )
                self._brick_markers[brick.brick_id] = brick

            self.get_logger().info(f"Started assembly {self._current_assembly_id} with {self._total_steps} steps")

            # Set first brick as next
            if self._brick_markers:
                first_brick = list(self._brick_markers.values())[0]
                self._set_next_brick(first_brick.brick_id)

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid assembly start message: {msg.data}")

    def _on_step_complete(self, msg: String):
        """Handle step completion."""
        try:
            data = json.loads(msg.data)
            brick_id = data.get('brick_id', '')

            if brick_id in self._brick_markers:
                self._brick_markers[brick_id].state = 'placed'
                self._brick_markers[brick_id].alpha = 1.0
                self._placed_bricks.append(brick_id)
                self._current_step += 1

                # Set next brick
                remaining = [b for b in self._brick_markers.values() if b.state == 'pending']
                if remaining:
                    self._set_next_brick(remaining[0].brick_id)
                else:
                    self._next_brick = None
                    self.get_logger().info("Assembly complete!")

        except json.JSONDecodeError:
            pass

    def _on_user_confirm(self, msg: String):
        """Handle user confirmation of step."""
        # Move to next step when user confirms
        if self._next_brick:
            self._next_brick.state = 'placed'
            self._on_step_complete(String(data=json.dumps({'brick_id': self._next_brick.brick_id})))

    def _set_next_brick(self, brick_id: str):
        """Set the next brick to place."""
        if brick_id in self._brick_markers:
            # Reset previous next brick
            if self._next_brick:
                self._next_brick.highlight = False

            self._next_brick = self._brick_markers[brick_id]
            self._next_brick.state = 'ghost'
            self._next_brick.alpha = 0.7
            self._next_brick.highlight = True

    def _publish_markers(self):
        """Publish AR visualization markers."""
        marker_array = MarkerArray()
        marker_id = 0

        # Clear previous markers
        clear_marker = Marker()
        clear_marker.header.frame_id = 'world'
        clear_marker.header.stamp = self.get_clock().now().to_msg()
        clear_marker.ns = 'lego_bricks'
        clear_marker.action = Marker.DELETEALL
        marker_array.markers.append(clear_marker)
        marker_id += 1

        # Publish brick markers
        for brick in self._brick_markers.values():
            marker = self._create_brick_marker(brick, marker_id)
            marker_array.markers.append(marker)
            marker_id += 1

            # Add highlight ring for next brick
            if brick.highlight and brick == self._next_brick:
                ring = self._create_highlight_ring(brick, marker_id)
                marker_array.markers.append(ring)
                marker_id += 1

        # Publish robot path markers if enabled
        if self._show_robot_intent and self._robot_path:
            path_markers = self._create_path_markers(marker_id)
            marker_array.markers.extend(path_markers)

        self._marker_pub.publish(marker_array)

        # Publish JSON version for WebXR
        self._publish_json_markers()

        # Publish current step
        self._publish_current_step()

    def _create_brick_marker(self, brick: BrickMarker, marker_id: int) -> Marker:
        """Create a visualization marker for a brick."""
        marker = Marker()
        marker.header.frame_id = 'world'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'lego_bricks'
        marker.id = marker_id
        marker.type = Marker.CUBE  # Or MESH_RESOURCE for actual brick mesh

        if brick.state == 'ghost':
            marker.action = Marker.ADD
        else:
            marker.action = Marker.ADD

        # Position
        marker.pose.position.x = brick.position[0]
        marker.pose.position.y = brick.position[1]
        marker.pose.position.z = brick.position[2]

        # Orientation
        marker.pose.orientation.x = brick.orientation[0]
        marker.pose.orientation.y = brick.orientation[1]
        marker.pose.orientation.z = brick.orientation[2]
        marker.pose.orientation.w = brick.orientation[3]

        # Scale based on brick type
        scale = self._get_brick_scale(brick.brick_type)
        marker.scale.x = scale[0]
        marker.scale.y = scale[1]
        marker.scale.z = scale[2]

        # Color
        color = self._get_brick_color(brick.color)
        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        marker.color.a = brick.alpha

        marker.lifetime.sec = 0  # Never expire

        return marker

    def _create_highlight_ring(self, brick: BrickMarker, marker_id: int) -> Marker:
        """Create a highlight ring around the next brick."""
        marker = Marker()
        marker.header.frame_id = 'world'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = 'highlights'
        marker.id = marker_id
        marker.type = Marker.CYLINDER

        marker.pose.position.x = brick.position[0]
        marker.pose.position.y = brick.position[1]
        marker.pose.position.z = brick.position[2] - 0.005  # Slightly below

        marker.scale.x = 0.05  # Diameter
        marker.scale.y = 0.05
        marker.scale.z = 0.002  # Thin ring

        # Pulsing green highlight
        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.0
        marker.color.a = 0.8

        return marker

    def _create_path_markers(self, start_id: int) -> List[Marker]:
        """Create markers showing robot planned path."""
        markers = []

        # Line strip for path
        line = Marker()
        line.header.frame_id = 'world'
        line.header.stamp = self.get_clock().now().to_msg()
        line.ns = 'robot_path'
        line.id = start_id
        line.type = Marker.LINE_STRIP

        line.scale.x = 0.005  # Line width

        line.color.r = 0.0
        line.color.g = 0.5
        line.color.b = 1.0
        line.color.a = 0.6

        for pose in self._robot_path:
            line.points.append(pose.position)

        if line.points:
            markers.append(line)

        return markers

    def _get_brick_scale(self, brick_type: str) -> List[float]:
        """Get brick dimensions in meters."""
        # LEGO stud pitch is 8mm
        # Brick height is 9.6mm (plate is 3.2mm)
        scales = {
            '2x4': [0.032, 0.016, 0.0096],
            '2x2': [0.016, 0.016, 0.0096],
            '1x4': [0.032, 0.008, 0.0096],
            '1x2': [0.016, 0.008, 0.0096],
            '1x1': [0.008, 0.008, 0.0096],
            '2x6': [0.048, 0.016, 0.0096],
            '2x8': [0.064, 0.016, 0.0096],
        }
        return scales.get(brick_type, [0.032, 0.016, 0.0096])

    def _get_brick_color(self, color_name: str) -> List[float]:
        """Get LEGO color as RGB."""
        colors = {
            'red': [0.8, 0.0, 0.0],
            'blue': [0.0, 0.0, 0.8],
            'yellow': [1.0, 0.8, 0.0],
            'green': [0.0, 0.6, 0.0],
            'white': [0.95, 0.95, 0.95],
            'black': [0.1, 0.1, 0.1],
            'orange': [1.0, 0.5, 0.0],
            'gray': [0.6, 0.6, 0.6],
            'brown': [0.4, 0.2, 0.0],
        }
        return colors.get(color_name.lower(), [0.5, 0.5, 0.5])

    def _publish_json_markers(self):
        """Publish markers as JSON for WebXR fallback."""
        markers_data = []

        for brick in self._brick_markers.values():
            markers_data.append({
                'brick_id': brick.brick_id,
                'brick_type': brick.brick_type,
                'color': brick.color,
                'position': brick.position,
                'orientation': brick.orientation,
                'alpha': brick.alpha,
                'state': brick.state,
                'highlight': brick.highlight,
            })

        msg = String()
        msg.data = json.dumps({
            'timestamp': datetime.now().isoformat(),
            'assembly_id': self._current_assembly_id,
            'current_step': self._current_step,
            'total_steps': self._total_steps,
            'markers': markers_data,
            'next_brick': self._next_brick.brick_id if self._next_brick else None,
        })
        self._json_markers_pub.publish(msg)

    def _publish_current_step(self):
        """Publish current assembly step."""
        if MSGS_AVAILABLE:
            msg = AssemblyStep()
            msg.assembly_id = self._current_assembly_id
            msg.step_number = self._current_step
            msg.total_steps = self._total_steps
            if self._next_brick:
                msg.brick_id = self._next_brick.brick_id
                msg.brick_type = self._next_brick.brick_type
                msg.instruction = f"Place {self._next_brick.color} {self._next_brick.brick_type} brick"
            self._step_pub.publish(msg)
        else:
            msg = String()
            msg.data = json.dumps({
                'assembly_id': self._current_assembly_id,
                'step_number': self._current_step,
                'total_steps': self._total_steps,
                'next_brick': self._next_brick.brick_id if self._next_brick else None,
                'instruction': f"Place {self._next_brick.color} {self._next_brick.brick_type} brick" if self._next_brick else "Assembly complete",
            })
            self._step_pub.publish(msg)

    def set_robot_path(self, path: List[Pose]):
        """Set robot planned path for visualization."""
        self._robot_path = path

    def add_brick(self, brick: BrickMarker):
        """Add a brick to the assembly."""
        self._brick_markers[brick.brick_id] = brick


def main(args=None):
    rclpy.init(args=args)

    node = ARPublisherNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
