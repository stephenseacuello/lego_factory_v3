#!/usr/bin/env python3
"""
Collision Detector - Real-time collision detection for CNC machines

Monitors machine position and G-code commands to detect potential collisions
with workpiece, fixtures, and machine limits.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from geometry_msgs.msg import Point, Pose, PoseStamped

from std_msgs.msg import String
from cnc_interfaces.msg import (
    MachineStatus,
    CollisionWarning,
    Alarm,
)


@dataclass
class BoundingBox:
    """Axis-aligned bounding box for collision detection"""
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    min_z: float = 0.0
    max_z: float = 0.0
    name: str = ""
    obstacle_type: str = "obstacle"

    def contains_point(self, x: float, y: float, z: float) -> bool:
        return (self.min_x <= x <= self.max_x and
                self.min_y <= y <= self.max_y and
                self.min_z <= z <= self.max_z)

    def distance_to_point(self, x: float, y: float, z: float) -> float:
        """Calculate minimum distance from point to box"""
        dx = max(self.min_x - x, 0, x - self.max_x)
        dy = max(self.min_y - y, 0, y - self.max_y)
        dz = max(self.min_z - z, 0, z - self.max_z)
        return np.sqrt(dx*dx + dy*dy + dz*dz)


@dataclass
class MachineEnvelope:
    """Machine work envelope and soft limits"""
    machine_id: str
    x_min: float = 0.0
    x_max: float = 300.0
    y_min: float = 0.0
    y_max: float = 200.0
    z_min: float = -100.0
    z_max: float = 0.0

    # Soft limit margins
    warning_margin: float = 5.0
    stop_margin: float = 2.0

    # Obstacles
    obstacles: List[BoundingBox] = field(default_factory=list)

    # Tool parameters
    tool_length: float = 50.0
    tool_diameter: float = 6.0


class CollisionDetectorNode(Node):
    """Real-time collision detection for CNC machines"""

    def __init__(self):
        super().__init__('collision_detector')

        # Parameters
        self.declare_parameter('check_rate', 20.0)  # Hz
        self.declare_parameter('warning_distance', 10.0)  # mm
        self.declare_parameter('stop_distance', 2.0)  # mm
        self.declare_parameter('enable_limit_checking', True)
        self.declare_parameter('enable_obstacle_checking', True)

        self.check_rate = self.get_parameter('check_rate').value
        self.warning_distance = self.get_parameter('warning_distance').value
        self.stop_distance = self.get_parameter('stop_distance').value
        self.check_limits = self.get_parameter('enable_limit_checking').value
        self.check_obstacles = self.get_parameter('enable_obstacle_checking').value

        # Machine envelopes
        self.machines: Dict[str, MachineEnvelope] = {}

        # Current machine states
        self.positions: Dict[str, Tuple[float, float, float]] = {}
        self.last_warnings: Dict[str, float] = {}

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers
        self.status_sub = self.create_subscription(
            MachineStatus,
            '/machine/status',
            self.status_callback,
            qos
        )

        for ctrl in ['tinyg', 'grbl']:
            self.create_subscription(
                MachineStatus, f'/{ctrl}/status',
                self.status_callback, qos
            )

        # Publishers
        self.collision_pub = self.create_publisher(
            CollisionWarning,
            '/motion/collision_warning',
            qos
        )

        self.alarm_pub = self.create_publisher(
            Alarm,
            '/motion/alarms',
            qos
        )

        # Initialize default machine envelope
        self.init_default_envelope()

        self.get_logger().info('Collision Detector started')

    def init_default_envelope(self):
        """Initialize default machine work envelopes"""
        # Default 3-axis mill envelope
        default = MachineEnvelope(
            machine_id='default',
            x_min=0, x_max=300,
            y_min=0, y_max=200,
            z_min=-100, z_max=0
        )

        # Add example fixtures/obstacles
        default.obstacles = [
            BoundingBox(
                min_x=50, max_x=100,
                min_y=50, max_y=100,
                min_z=-20, max_z=0,
                name="vise",
                obstacle_type="fixture"
            ),
        ]

        self.machines['default'] = default

    def get_envelope(self, machine_id: str) -> MachineEnvelope:
        """Get machine envelope, create default if needed"""
        if machine_id not in self.machines:
            envelope = MachineEnvelope(machine_id=machine_id)
            self.machines[machine_id] = envelope
        return self.machines[machine_id]

    def status_callback(self, msg: MachineStatus):
        """Process machine status and check for collisions"""
        machine_id = msg.machine_id
        envelope = self.get_envelope(machine_id)

        # Get current position (work coordinates)
        x, y, z = msg.wpos_x, msg.wpos_y, msg.wpos_z

        # Store position
        prev_pos = self.positions.get(machine_id, (x, y, z))
        self.positions[machine_id] = (x, y, z)

        # Only check during motion
        if msg.state not in [MachineStatus.STATE_RUN, MachineStatus.STATE_JOG]:
            return

        # Check axis limits
        if self.check_limits:
            limit_warning = self.check_axis_limits(machine_id, x, y, z, envelope)
            if limit_warning:
                self.publish_warning(limit_warning)

        # Check obstacle collisions
        if self.check_obstacles:
            obstacle_warning = self.check_obstacle_collisions(
                machine_id, x, y, z, envelope, msg.line_number
            )
            if obstacle_warning:
                self.publish_warning(obstacle_warning)

        # Check rapid motion into workpiece (Z plunge detection)
        if prev_pos[2] > z and (prev_pos[2] - z) > 5:  # Rapid descent
            plunge_warning = self.check_rapid_plunge(
                machine_id, prev_pos, (x, y, z), envelope
            )
            if plunge_warning:
                self.publish_warning(plunge_warning)

    def check_axis_limits(self, machine_id: str, x: float, y: float, z: float,
                          envelope: MachineEnvelope) -> Optional[CollisionWarning]:
        """Check if position is near or beyond axis limits"""
        warnings = []

        # Check each axis
        for axis, val, min_val, max_val in [
            ('X', x, envelope.x_min, envelope.x_max),
            ('Y', y, envelope.y_min, envelope.y_max),
            ('Z', z, envelope.z_min, envelope.z_max),
        ]:
            dist_to_min = val - min_val
            dist_to_max = max_val - val

            min_dist = min(dist_to_min, dist_to_max)

            if min_dist < 0:
                # Beyond limit!
                return self.create_warning(
                    machine_id, x, y, z,
                    CollisionWarning.COLLISION_AXIS_LIMIT,
                    CollisionWarning.SEVERITY_COLLISION,
                    min_dist,
                    f"table_{axis.lower()}_limit",
                    CollisionWarning.ACTION_EMERGENCY_STOP,
                    f"{axis} axis beyond limit by {abs(min_dist):.2f}mm"
                )
            elif min_dist < self.stop_distance:
                return self.create_warning(
                    machine_id, x, y, z,
                    CollisionWarning.COLLISION_AXIS_LIMIT,
                    CollisionWarning.SEVERITY_CRITICAL,
                    min_dist,
                    f"table_{axis.lower()}_limit",
                    CollisionWarning.ACTION_STOP,
                    f"{axis} axis within {min_dist:.2f}mm of limit"
                )
            elif min_dist < self.warning_distance:
                warnings.append((axis, min_dist))

        if warnings:
            axis, dist = warnings[0]
            return self.create_warning(
                machine_id, x, y, z,
                CollisionWarning.COLLISION_AXIS_LIMIT,
                CollisionWarning.SEVERITY_WARNING,
                dist,
                f"table_{axis.lower()}_limit",
                CollisionWarning.ACTION_REDUCE_SPEED,
                f"Approaching {axis} axis limit ({dist:.2f}mm)"
            )

        return None

    def check_obstacle_collisions(self, machine_id: str, x: float, y: float, z: float,
                                   envelope: MachineEnvelope, line_number: int) -> Optional[CollisionWarning]:
        """Check for collisions with defined obstacles"""
        # Adjust for tool tip position
        tool_tip_z = z - envelope.tool_length

        for obstacle in envelope.obstacles:
            # Check if tool tip is inside obstacle
            if obstacle.contains_point(x, y, tool_tip_z):
                return self.create_warning(
                    machine_id, x, y, z,
                    CollisionWarning.COLLISION_TOOL_FIXTURE,
                    CollisionWarning.SEVERITY_COLLISION,
                    0.0,
                    obstacle.obstacle_type,
                    CollisionWarning.ACTION_EMERGENCY_STOP,
                    f"Collision with {obstacle.name}",
                    line_number,
                    obstacle.name
                )

            # Check distance to obstacle
            dist = obstacle.distance_to_point(x, y, tool_tip_z)

            if dist < self.stop_distance:
                return self.create_warning(
                    machine_id, x, y, z,
                    CollisionWarning.COLLISION_TOOL_FIXTURE,
                    CollisionWarning.SEVERITY_CRITICAL,
                    dist,
                    obstacle.obstacle_type,
                    CollisionWarning.ACTION_STOP,
                    f"Critical proximity to {obstacle.name} ({dist:.2f}mm)",
                    line_number,
                    obstacle.name
                )
            elif dist < self.warning_distance:
                return self.create_warning(
                    machine_id, x, y, z,
                    CollisionWarning.COLLISION_TOOL_FIXTURE,
                    CollisionWarning.SEVERITY_WARNING,
                    dist,
                    obstacle.obstacle_type,
                    CollisionWarning.ACTION_REDUCE_SPEED,
                    f"Approaching {obstacle.name} ({dist:.2f}mm)",
                    line_number,
                    obstacle.name
                )

        return None

    def check_rapid_plunge(self, machine_id: str, prev_pos: Tuple,
                           curr_pos: Tuple, envelope: MachineEnvelope) -> Optional[CollisionWarning]:
        """Detect potentially dangerous rapid Z movements"""
        z_change = prev_pos[2] - curr_pos[2]

        # Rapid plunge more than 10mm
        if z_change > 10:
            return self.create_warning(
                machine_id, curr_pos[0], curr_pos[1], curr_pos[2],
                CollisionWarning.COLLISION_TOOL_WORKPIECE,
                CollisionWarning.SEVERITY_WARNING,
                z_change,
                "workpiece",
                CollisionWarning.ACTION_REDUCE_SPEED,
                f"Rapid Z descent detected ({z_change:.1f}mm)"
            )
        return None

    def create_warning(self, machine_id: str, x: float, y: float, z: float,
                       collision_type: int, severity: int, distance: float,
                       obstacle_type: str, action: int, message: str,
                       line_number: int = 0, obstacle_id: str = "") -> CollisionWarning:
        """Create a collision warning message"""
        msg = CollisionWarning()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = machine_id
        msg.collision_type = collision_type
        msg.severity = severity

        msg.current_position = Point(x=x, y=y, z=z)
        msg.min_distance = distance
        msg.warning_distance = self.warning_distance
        msg.stop_distance = self.stop_distance

        msg.obstacle_type = obstacle_type
        msg.obstacle_id = obstacle_id
        msg.gcode_line = line_number

        msg.recommended_action = action
        msg.action_message = message

        # Calculate safe retract position
        msg.safe_retract_position = Point(x=x, y=y, z=0.0)  # Z=0 is safe

        return msg

    def publish_warning(self, warning: CollisionWarning):
        """Publish collision warning and alarm if critical"""
        current_time = self.get_clock().now().nanoseconds / 1e9

        # Rate limit warnings (max 1 per second per machine)
        key = f"{warning.machine_id}_{warning.collision_type}"
        if key in self.last_warnings:
            if current_time - self.last_warnings[key] < 1.0:
                return
        self.last_warnings[key] = current_time

        self.collision_pub.publish(warning)

        # Publish alarm for critical/collision severity
        if warning.severity >= CollisionWarning.SEVERITY_CRITICAL:
            alarm = Alarm()
            alarm.header.stamp = warning.header.stamp
            alarm.machine_id = warning.machine_id
            alarm.alarm_code = 7000 + warning.collision_type
            alarm.message = warning.action_message
            alarm.severity = warning.severity
            self.alarm_pub.publish(alarm)

            self.get_logger().warn(f"Collision warning: {warning.action_message}")


def main(args=None):
    rclpy.init(args=args)
    node = CollisionDetectorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
