#!/usr/bin/env python3
"""
LEGO MCP Digital Twin Synchronization Node
Synchronizes physical equipment state with digital twin model via ROS2.

Provides:
- Real-time equipment state aggregation
- tf2 transform broadcasting for AR visualization
- Twin state publishing at configurable rate
- PINN prediction comparison

LEGO MCP Manufacturing System v7.0
"""

import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState
from geometry_msgs.msg import TransformStamped, Pose

try:
    from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
    TF2_AVAILABLE = True
except ImportError:
    TF2_AVAILABLE = False

try:
    from lego_mcp_msgs.msg import (
        EquipmentStatus, TwinState, PrintJob
    )
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


@dataclass
class EquipmentTwinState:
    """Twin state for a single piece of equipment."""
    equipment_id: str
    equipment_type: str
    connected: bool = False
    state: str = 'unknown'
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    joint_positions: List[float] = field(default_factory=list)
    temperature: float = 0.0
    progress: float = 0.0
    error_code: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type,
            'connected': self.connected,
            'state': self.state,
            'position': self.position,
            'joint_positions': self.joint_positions,
            'temperature': self.temperature,
            'progress': self.progress,
            'error_code': self.error_code,
            'last_update': self.last_update.isoformat(),
            'metadata': self.metadata,
        }


class TwinSyncNode(Node):
    """
    Digital Twin synchronization via ROS2.

    Subscribes to all equipment topics and publishes unified twin state.
    Broadcasts tf2 transforms for AR visualization.
    """

    def __init__(self):
        super().__init__('twin_sync')

        # Parameters
        self.declare_parameter('publish_rate', 10.0)  # Hz
        self.declare_parameter('tf_rate', 30.0)  # Hz
        self.declare_parameter('stale_timeout', 5.0)  # seconds

        self._publish_rate = self.get_parameter('publish_rate').value
        self._tf_rate = self.get_parameter('tf_rate').value
        self._stale_timeout = self.get_parameter('stale_timeout').value

        # Equipment state storage
        self._equipment_states: Dict[str, EquipmentTwinState] = {}
        self._lock = threading.Lock()

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Initialize equipment states
        self._init_equipment_states()

        # TF broadcasters
        if TF2_AVAILABLE:
            self._tf_broadcaster = TransformBroadcaster(self)
            self._static_tf_broadcaster = StaticTransformBroadcaster(self)
            # Broadcast static transforms for equipment bases
            self._broadcast_static_transforms()

        # Twin state publisher
        if MSGS_AVAILABLE:
            self._twin_pub = self.create_publisher(
                TwinState,
                '/lego_mcp/twin_state',
                10
            )
        else:
            self._twin_pub = self.create_publisher(
                String,
                '/lego_mcp/twin_state',
                10
            )

        # JSON state publisher (for web dashboard)
        self._json_pub = self.create_publisher(
            String,
            '/lego_mcp/twin_state_json',
            10
        )

        # Subscribe to equipment status topics
        self._setup_equipment_subscriptions()

        # Timers
        self._publish_timer = self.create_timer(
            1.0 / self._publish_rate,
            self._publish_twin_state
        )

        if TF2_AVAILABLE:
            self._tf_timer = self.create_timer(
                1.0 / self._tf_rate,
                self._broadcast_transforms
            )

        self.get_logger().info("Twin sync node initialized")

    def _init_equipment_states(self):
        """Initialize equipment states."""
        equipment_config = [
            ('ned2', 'robot_arm'),
            ('xarm', 'robot_arm'),
            ('formlabs', 'sla_printer'),
            ('cnc', 'cnc_mill'),
            ('laser', 'laser_engraver'),
            ('coastrunner', 'fdm_printer'),
        ]

        for eq_id, eq_type in equipment_config:
            self._equipment_states[eq_id] = EquipmentTwinState(
                equipment_id=eq_id,
                equipment_type=eq_type,
            )

    def _setup_equipment_subscriptions(self):
        """Set up subscriptions to equipment topics."""
        # Robot joint states
        for robot in ['ned2', 'xarm']:
            self.create_subscription(
                JointState,
                f'/{robot}/joint_states',
                lambda msg, r=robot: self._on_joint_states(r, msg),
                10
            )

        # Equipment status
        for equipment in ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']:
            self.create_subscription(
                EquipmentStatus if MSGS_AVAILABLE else String,
                f'/{equipment}/status',
                lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                10
            )

        # Print job status
        if MSGS_AVAILABLE:
            self.create_subscription(
                PrintJob,
                '/formlabs/job_status',
                self._on_print_job_status,
                10
            )

    def _on_joint_states(self, robot_id: str, msg: JointState):
        """Handle robot joint state update."""
        with self._lock:
            if robot_id in self._equipment_states:
                state = self._equipment_states[robot_id]
                state.joint_positions = list(msg.position)
                state.last_update = datetime.now()

                # Compute end-effector position (simplified)
                if len(msg.position) >= 6:
                    # This would use forward kinematics in production
                    state.metadata['joint_names'] = list(msg.name)
                    state.metadata['joint_velocities'] = list(msg.velocity) if msg.velocity else []

    def _on_equipment_status(self, equipment_id: str, msg):
        """Handle equipment status update."""
        with self._lock:
            if equipment_id not in self._equipment_states:
                return

            state = self._equipment_states[equipment_id]

            if MSGS_AVAILABLE and hasattr(msg, 'state'):
                state.connected = msg.connected
                state.state = self._state_to_string(msg.state)
                state.error_code = msg.error_code if hasattr(msg, 'error_code') else 0
                if hasattr(msg, 'temperature'):
                    state.temperature = msg.temperature
            else:
                # Parse string message
                try:
                    data = json.loads(msg.data)
                    state.connected = data.get('connected', False)
                    state.state = data.get('state', 'unknown')
                except (json.JSONDecodeError, AttributeError):
                    pass

            state.last_update = datetime.now()

    def _on_print_job_status(self, msg):
        """Handle print job status update."""
        with self._lock:
            state = self._equipment_states.get('formlabs')
            if state:
                state.progress = msg.progress if hasattr(msg, 'progress') else 0.0
                state.metadata['job_id'] = msg.job_id if hasattr(msg, 'job_id') else ''
                state.metadata['layer'] = msg.current_layer if hasattr(msg, 'current_layer') else 0
                state.last_update = datetime.now()

    def _state_to_string(self, state_code: int) -> str:
        """Convert state code to string."""
        state_map = {
            0: 'disconnected',
            1: 'idle',
            2: 'busy',
            3: 'error',
            4: 'estop',
            5: 'homing',
            6: 'paused',
        }
        return state_map.get(state_code, 'unknown')

    def _publish_twin_state(self):
        """Publish aggregated twin state."""
        with self._lock:
            now = datetime.now()

            # Check for stale states
            for eq_id, state in self._equipment_states.items():
                age = (now - state.last_update).total_seconds()
                if age > self._stale_timeout:
                    state.connected = False
                    state.state = 'stale'

            # Build state message
            if MSGS_AVAILABLE:
                msg = TwinState()
                msg.timestamp = self.get_clock().now().to_msg()
                msg.equipment_count = len(self._equipment_states)

                # Equipment IDs and states
                msg.equipment_ids = list(self._equipment_states.keys())
                msg.equipment_states = [s.state for s in self._equipment_states.values()]
                msg.equipment_connected = [s.connected for s in self._equipment_states.values()]

                self._twin_pub.publish(msg)
            else:
                msg = String()
                msg.data = json.dumps({
                    'timestamp': now.isoformat(),
                    'equipment': {
                        eq_id: state.to_dict()
                        for eq_id, state in self._equipment_states.items()
                    }
                })
                self._twin_pub.publish(msg)

            # Also publish JSON version for web dashboard
            json_msg = String()
            json_msg.data = json.dumps({
                'timestamp': now.isoformat(),
                'equipment': {
                    eq_id: state.to_dict()
                    for eq_id, state in self._equipment_states.items()
                }
            })
            self._json_pub.publish(json_msg)

    def _broadcast_static_transforms(self):
        """Broadcast static transforms for equipment bases."""
        if not TF2_AVAILABLE:
            return

        transforms = []

        # Equipment base positions in world frame
        equipment_positions = {
            'ned2': [0.0, 0.0, 0.0],
            'xarm': [0.5, 0.0, 0.0],
            'formlabs': [0.8, -0.3, 0.0],
            'cnc': [-0.3, 0.4, 0.0],
            'laser': [-0.3, -0.4, 0.0],
        }

        for eq_id, pos in equipment_positions.items():
            t = TransformStamped()
            t.header.stamp = self.get_clock().now().to_msg()
            t.header.frame_id = 'world'
            t.child_frame_id = f'{eq_id}_base'
            t.transform.translation.x = pos[0]
            t.transform.translation.y = pos[1]
            t.transform.translation.z = pos[2]
            t.transform.rotation.w = 1.0
            transforms.append(t)

        self._static_tf_broadcaster.sendTransform(transforms)

    def _broadcast_transforms(self):
        """Broadcast dynamic transforms for equipment."""
        if not TF2_AVAILABLE:
            return

        transforms = []

        with self._lock:
            for eq_id, state in self._equipment_states.items():
                if state.equipment_type == 'robot_arm' and state.joint_positions:
                    # Broadcast end-effector transform (simplified)
                    t = TransformStamped()
                    t.header.stamp = self.get_clock().now().to_msg()
                    t.header.frame_id = f'{eq_id}_base'
                    t.child_frame_id = f'{eq_id}_gripper'

                    # Simplified FK - in production would use actual kinematics
                    t.transform.translation.x = state.position[0] if state.position else 0.3
                    t.transform.translation.y = state.position[1] if len(state.position) > 1 else 0.0
                    t.transform.translation.z = state.position[2] if len(state.position) > 2 else 0.2
                    t.transform.rotation.w = 1.0

                    transforms.append(t)

        if transforms:
            self._tf_broadcaster.sendTransform(transforms)

    def get_equipment_state(self, equipment_id: str) -> Optional[Dict[str, Any]]:
        """Get state of specific equipment."""
        with self._lock:
            state = self._equipment_states.get(equipment_id)
            if state:
                return state.to_dict()
        return None

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all equipment states."""
        with self._lock:
            return {
                eq_id: state.to_dict()
                for eq_id, state in self._equipment_states.items()
            }


def main(args=None):
    rclpy.init(args=args)

    node = TwinSyncNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
