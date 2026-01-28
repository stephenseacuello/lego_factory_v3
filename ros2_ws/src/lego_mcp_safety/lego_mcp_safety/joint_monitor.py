#!/usr/bin/env python3
"""
LEGO MCP Joint Monitor Node

Monitors robot joint states for safety violations:
- Position limits
- Velocity limits
- Acceleration limits
- Torque/effort anomalies (collision detection)

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from std_msgs.msg import Bool, String
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger


class ViolationType(Enum):
    """Types of joint limit violations."""
    POSITION_SOFT = 'position_soft'
    POSITION_HARD = 'position_hard'
    VELOCITY = 'velocity'
    ACCELERATION = 'acceleration'
    TORQUE = 'torque'
    COLLISION = 'collision'


@dataclass
class JointLimits:
    """Joint limit configuration."""
    name: str
    position_min: float
    position_max: float
    velocity_max: float
    acceleration_max: float = 10.0
    torque_max: float = 50.0
    soft_limit_margin: float = 0.05  # radians from hard limit


@dataclass
class JointViolation:
    """Record of a joint limit violation."""
    robot: str
    joint: str
    violation_type: ViolationType
    current_value: float
    limit_value: float
    timestamp: datetime = field(default_factory=datetime.now)


class JointMonitorNode(Node):
    """
    Monitors joint states for safety limit violations.

    Subscribes to joint states from all robots and triggers
    safety stops when limits are exceeded.
    """

    def __init__(self):
        super().__init__('joint_monitor')

        # Parameters
        self.declare_parameter('check_rate_hz', 100.0)
        self.declare_parameter('soft_limit_warning', True)
        self.declare_parameter('collision_detection_enabled', True)
        self.declare_parameter('torque_threshold', 50.0)
        self.declare_parameter('velocity_filter_samples', 5)

        self._check_rate = self.get_parameter('check_rate_hz').value
        self._soft_limit_warning = self.get_parameter('soft_limit_warning').value
        self._collision_detection = self.get_parameter('collision_detection_enabled').value
        self._torque_threshold = self.get_parameter('torque_threshold').value
        self._filter_samples = self.get_parameter('velocity_filter_samples').value

        # Define joint limits for each robot
        self._joint_limits: Dict[str, Dict[str, JointLimits]] = {
            'ned2': self._create_ned2_limits(),
            'xarm': self._create_xarm_limits(),
        }

        # State tracking
        self._last_joint_states: Dict[str, JointState] = {}
        self._last_timestamps: Dict[str, datetime] = {}
        self._velocity_history: Dict[str, List[float]] = {}
        self._violations: List[JointViolation] = []
        self._safety_stop_triggered = False

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # QoS for reliable joint state reception
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribe to joint states for each robot
        self.create_subscription(
            JointState,
            '/ned2/joint_states',
            lambda msg: self._on_joint_states('ned2', msg),
            qos_reliable,
            callback_group=self._cb_group
        )

        self.create_subscription(
            JointState,
            '/xarm/joint_states',
            lambda msg: self._on_joint_states('xarm', msg),
            qos_reliable,
            callback_group=self._cb_group
        )

        # E-stop status subscription
        self.create_subscription(
            Bool,
            '/safety/estop_status',
            self._on_estop_status,
            10
        )

        # Publishers
        self._violation_pub = self.create_publisher(
            String,
            '/safety/joint_violations',
            10
        )

        self._safety_stop_pub = self.create_publisher(
            Bool,
            '/safety/joint_monitor/stop',
            10
        )

        self._status_pub = self.create_publisher(
            String,
            '/safety/joint_monitor/status',
            10
        )

        # Service to call safety e-stop
        self._estop_client = self.create_client(
            Trigger,
            '/safety/emergency_stop'
        )

        # Status timer
        self._status_timer = self.create_timer(
            1.0,
            self._publish_status
        )

        self.get_logger().info("Joint monitor initialized")

    def _create_ned2_limits(self) -> Dict[str, JointLimits]:
        """Create joint limits for Niryo Ned2."""
        return {
            'ned2_joint_1': JointLimits(
                name='ned2_joint_1',
                position_min=-2.9, position_max=2.9,
                velocity_max=1.0, acceleration_max=2.0, torque_max=10.0
            ),
            'ned2_joint_2': JointLimits(
                name='ned2_joint_2',
                position_min=-1.8, position_max=0.6,
                velocity_max=1.0, acceleration_max=2.0, torque_max=10.0
            ),
            'ned2_joint_3': JointLimits(
                name='ned2_joint_3',
                position_min=-1.3, position_max=1.6,
                velocity_max=1.0, acceleration_max=2.0, torque_max=10.0
            ),
            'ned2_joint_4': JointLimits(
                name='ned2_joint_4',
                position_min=-2.1, position_max=2.1,
                velocity_max=1.0, acceleration_max=3.0, torque_max=5.0
            ),
            'ned2_joint_5': JointLimits(
                name='ned2_joint_5',
                position_min=-1.9, position_max=1.9,
                velocity_max=1.0, acceleration_max=3.0, torque_max=5.0
            ),
            'ned2_joint_6': JointLimits(
                name='ned2_joint_6',
                position_min=-2.5, position_max=2.5,
                velocity_max=1.5, acceleration_max=3.0, torque_max=5.0
            ),
        }

    def _create_xarm_limits(self) -> Dict[str, JointLimits]:
        """Create joint limits for xArm 6 Lite."""
        return {
            'xarm_joint1': JointLimits(
                name='xarm_joint1',
                position_min=-6.28, position_max=6.28,
                velocity_max=1.5, acceleration_max=5.0, torque_max=20.0
            ),
            'xarm_joint2': JointLimits(
                name='xarm_joint2',
                position_min=-2.0, position_max=2.0,
                velocity_max=1.5, acceleration_max=5.0, torque_max=20.0
            ),
            'xarm_joint3': JointLimits(
                name='xarm_joint3',
                position_min=-4.0, position_max=0.2,
                velocity_max=1.5, acceleration_max=5.0, torque_max=10.0
            ),
            'xarm_joint4': JointLimits(
                name='xarm_joint4',
                position_min=-6.28, position_max=6.28,
                velocity_max=1.5, acceleration_max=8.0, torque_max=10.0
            ),
            'xarm_joint5': JointLimits(
                name='xarm_joint5',
                position_min=-2.2, position_max=2.2,
                velocity_max=1.5, acceleration_max=8.0, torque_max=10.0
            ),
            'xarm_joint6': JointLimits(
                name='xarm_joint6',
                position_min=-6.28, position_max=6.28,
                velocity_max=1.5, acceleration_max=8.0, torque_max=10.0
            ),
        }

    def _on_joint_states(self, robot_id: str, msg: JointState):
        """Process joint state message."""
        now = datetime.now()
        violations = []

        # Get limits for this robot
        limits = self._joint_limits.get(robot_id, {})

        # Check each joint
        for i, joint_name in enumerate(msg.name):
            # Find matching limits
            joint_limits = limits.get(joint_name)
            if not joint_limits:
                continue

            # Get current values
            position = msg.position[i] if i < len(msg.position) else None
            velocity = msg.velocity[i] if msg.velocity and i < len(msg.velocity) else None
            effort = msg.effort[i] if msg.effort and i < len(msg.effort) else None

            # Check position limits
            if position is not None:
                violations.extend(self._check_position_limits(
                    robot_id, joint_name, position, joint_limits
                ))

            # Check velocity limits
            if velocity is not None:
                violations.extend(self._check_velocity_limits(
                    robot_id, joint_name, velocity, joint_limits
                ))

            # Calculate and check acceleration
            if velocity is not None:
                accel = self._calculate_acceleration(robot_id, joint_name, velocity, now)
                if accel is not None:
                    violations.extend(self._check_acceleration_limits(
                        robot_id, joint_name, accel, joint_limits
                    ))

            # Check effort/torque for collision detection
            if effort is not None and self._collision_detection:
                violations.extend(self._check_torque_limits(
                    robot_id, joint_name, effort, joint_limits
                ))

        # Store state for next iteration
        self._last_joint_states[robot_id] = msg
        self._last_timestamps[robot_id] = now

        # Process violations
        for violation in violations:
            self._handle_violation(violation)

    def _check_position_limits(
        self, robot: str, joint: str, position: float, limits: JointLimits
    ) -> List[JointViolation]:
        """Check position against limits."""
        violations = []

        # Hard limits
        if position < limits.position_min:
            violations.append(JointViolation(
                robot=robot, joint=joint,
                violation_type=ViolationType.POSITION_HARD,
                current_value=position,
                limit_value=limits.position_min
            ))
        elif position > limits.position_max:
            violations.append(JointViolation(
                robot=robot, joint=joint,
                violation_type=ViolationType.POSITION_HARD,
                current_value=position,
                limit_value=limits.position_max
            ))

        # Soft limits (warning zone)
        elif self._soft_limit_warning:
            if position < limits.position_min + limits.soft_limit_margin:
                violations.append(JointViolation(
                    robot=robot, joint=joint,
                    violation_type=ViolationType.POSITION_SOFT,
                    current_value=position,
                    limit_value=limits.position_min + limits.soft_limit_margin
                ))
            elif position > limits.position_max - limits.soft_limit_margin:
                violations.append(JointViolation(
                    robot=robot, joint=joint,
                    violation_type=ViolationType.POSITION_SOFT,
                    current_value=position,
                    limit_value=limits.position_max - limits.soft_limit_margin
                ))

        return violations

    def _check_velocity_limits(
        self, robot: str, joint: str, velocity: float, limits: JointLimits
    ) -> List[JointViolation]:
        """Check velocity against limits."""
        violations = []

        if abs(velocity) > limits.velocity_max:
            violations.append(JointViolation(
                robot=robot, joint=joint,
                violation_type=ViolationType.VELOCITY,
                current_value=abs(velocity),
                limit_value=limits.velocity_max
            ))

        return violations

    def _calculate_acceleration(
        self, robot: str, joint: str, velocity: float, now: datetime
    ) -> Optional[float]:
        """Calculate acceleration from velocity change."""
        key = f"{robot}_{joint}"

        # Initialize history if needed
        if key not in self._velocity_history:
            self._velocity_history[key] = []

        # Add current velocity
        self._velocity_history[key].append((now, velocity))

        # Keep only recent samples
        cutoff = now.timestamp() - 0.1  # 100ms window
        self._velocity_history[key] = [
            (t, v) for t, v in self._velocity_history[key]
            if t.timestamp() > cutoff
        ]

        # Need at least 2 samples
        if len(self._velocity_history[key]) < 2:
            return None

        # Calculate acceleration from oldest to newest
        t1, v1 = self._velocity_history[key][0]
        t2, v2 = self._velocity_history[key][-1]

        dt = (t2 - t1).total_seconds()
        if dt < 0.001:
            return None

        return (v2 - v1) / dt

    def _check_acceleration_limits(
        self, robot: str, joint: str, acceleration: float, limits: JointLimits
    ) -> List[JointViolation]:
        """Check acceleration against limits."""
        violations = []

        if abs(acceleration) > limits.acceleration_max:
            violations.append(JointViolation(
                robot=robot, joint=joint,
                violation_type=ViolationType.ACCELERATION,
                current_value=abs(acceleration),
                limit_value=limits.acceleration_max
            ))

        return violations

    def _check_torque_limits(
        self, robot: str, joint: str, torque: float, limits: JointLimits
    ) -> List[JointViolation]:
        """Check torque/effort for potential collisions."""
        violations = []

        if abs(torque) > limits.torque_max:
            # High torque might indicate collision
            violations.append(JointViolation(
                robot=robot, joint=joint,
                violation_type=ViolationType.COLLISION,
                current_value=abs(torque),
                limit_value=limits.torque_max
            ))

        return violations

    def _handle_violation(self, violation: JointViolation):
        """Handle a detected violation."""
        self._violations.append(violation)

        # Log violation
        if violation.violation_type == ViolationType.POSITION_SOFT:
            self.get_logger().warn(
                f"Soft limit warning: {violation.robot}/{violation.joint} "
                f"position={violation.current_value:.3f} near limit={violation.limit_value:.3f}"
            )
        else:
            self.get_logger().error(
                f"VIOLATION: {violation.robot}/{violation.joint} "
                f"{violation.violation_type.value} "
                f"value={violation.current_value:.3f} limit={violation.limit_value:.3f}"
            )

        # Publish violation
        msg = String()
        msg.data = json.dumps({
            'robot': violation.robot,
            'joint': violation.joint,
            'type': violation.violation_type.value,
            'value': violation.current_value,
            'limit': violation.limit_value,
            'timestamp': violation.timestamp.isoformat(),
        })
        self._violation_pub.publish(msg)

        # Trigger safety stop for hard violations
        if violation.violation_type in [
            ViolationType.POSITION_HARD,
            ViolationType.VELOCITY,
            ViolationType.COLLISION
        ]:
            self._trigger_safety_stop(violation)

    def _trigger_safety_stop(self, violation: JointViolation):
        """Trigger safety stop via e-stop service."""
        if self._safety_stop_triggered:
            return

        self.get_logger().error(
            f"SAFETY STOP: {violation.violation_type.value} on {violation.robot}/{violation.joint}"
        )

        self._safety_stop_triggered = True

        # Publish stop command
        stop_msg = Bool()
        stop_msg.data = True
        self._safety_stop_pub.publish(stop_msg)

        # Call e-stop service
        if self._estop_client.service_is_ready():
            request = Trigger.Request()
            future = self._estop_client.call_async(request)
            future.add_done_callback(self._estop_response_callback)
        else:
            self.get_logger().warn("E-stop service not available")

    def _estop_response_callback(self, future):
        """Handle e-stop service response."""
        try:
            response = future.result()
            if response.success:
                self.get_logger().info("E-stop triggered successfully")
            else:
                self.get_logger().error(f"E-stop failed: {response.message}")
        except Exception as e:
            self.get_logger().error(f"E-stop call failed: {e}")

    def _on_estop_status(self, msg: Bool):
        """Handle e-stop status updates."""
        if not msg.data:
            # E-stop released - allow new safety stops
            self._safety_stop_triggered = False

    def _publish_status(self):
        """Publish monitoring status."""
        status = {
            'monitoring': True,
            'robots_tracked': list(self._last_joint_states.keys()),
            'recent_violations': len([
                v for v in self._violations
                if (datetime.now() - v.timestamp).total_seconds() < 60
            ]),
            'safety_stop_active': self._safety_stop_triggered,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = JointMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
