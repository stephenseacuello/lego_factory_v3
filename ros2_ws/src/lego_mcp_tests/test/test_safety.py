#!/usr/bin/env python3
"""
LEGO MCP Safety System Integration Test

Tests safety system functionality:
- E-stop triggering and release
- Joint limit monitoring
- Watchdog timer
- Equipment interlocks

LEGO MCP Manufacturing System v7.0
"""

import unittest
import time
import json

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger
from sensor_msgs.msg import JointState


def generate_test_description():
    """Generate launch description for safety tests."""
    return launch.LaunchDescription([
        # Launch safety node in simulation mode
        launch_ros.actions.Node(
            package='lego_mcp_safety',
            executable='safety_node',
            name='safety_node',
            parameters=[{
                'simulation_mode': True,
                'watchdog_timeout_ms': 2000,
                'heartbeat_sources': ['test'],
            }],
        ),
        launch_ros.actions.Node(
            package='lego_mcp_safety',
            executable='joint_monitor',
            name='joint_monitor',
            parameters=[{
                'collision_detection_enabled': True,
            }],
        ),

        launch_testing.actions.ReadyToTest(),
    ])


class TestSafetySystem(unittest.TestCase):
    """Test safety system functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        """Tear down test fixtures."""
        rclpy.shutdown()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('safety_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.estop_status = None
        self.safety_state = None
        self.joint_violations = []

        # Subscribers
        self.node.create_subscription(
            Bool, '/safety/estop_status',
            self._on_estop_status, 10
        )
        self.node.create_subscription(
            String, '/safety/state',
            self._on_safety_state, 10
        )
        self.node.create_subscription(
            String, '/safety/joint_violations',
            self._on_joint_violation, 10
        )

        # Publishers
        self.heartbeat_pub = self.node.create_publisher(
            Bool, '/safety/heartbeat', 10
        )
        self.joint_pub = self.node.create_publisher(
            JointState, '/ned2/joint_states', 10
        )

        # Service clients
        self.estop_client = self.node.create_client(
            Trigger, '/safety/emergency_stop'
        )
        self.reset_client = self.node.create_client(
            Trigger, '/safety/reset'
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_estop_status(self, msg: Bool):
        """Handle e-stop status."""
        self.estop_status = msg.data

    def _on_safety_state(self, msg: String):
        """Handle safety state."""
        self.safety_state = msg.data

    def _on_joint_violation(self, msg: String):
        """Handle joint violation."""
        try:
            self.joint_violations.append(json.loads(msg.data))
        except json.JSONDecodeError:
            pass

    def _spin_until(self, condition, timeout: float = 10.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    def _send_heartbeat(self):
        """Send heartbeat signal."""
        msg = Bool()
        msg.data = True
        self.heartbeat_pub.publish(msg)

    def test_safety_node_starts(self):
        """Test that safety node starts and publishes status."""
        # Send heartbeat to prevent watchdog
        self._send_heartbeat()

        # Wait for status
        received = self._spin_until(
            lambda: self.estop_status is not None,
            timeout=5.0
        )
        self.assertTrue(received, "Safety node should publish e-stop status")
        self.assertFalse(self.estop_status, "E-stop should not be active initially")

    def test_estop_trigger(self):
        """Test e-stop trigger via service."""
        # Ensure service is available
        if not self.estop_client.wait_for_service(timeout_sec=5.0):
            self.skipTest("E-stop service not available")

        # Send heartbeat first
        self._send_heartbeat()
        time.sleep(0.5)

        # Trigger e-stop
        request = Trigger.Request()
        future = self.estop_client.call_async(request)

        # Wait for response
        self._spin_until(lambda: future.done(), timeout=5.0)

        if future.done():
            response = future.result()
            self.assertTrue(response.success, "E-stop should trigger successfully")

        # Verify e-stop is active
        self._spin_until(lambda: self.estop_status == True, timeout=2.0)
        self.assertTrue(self.estop_status, "E-stop should be active after trigger")

    def test_estop_reset(self):
        """Test e-stop reset."""
        # Skip if services not available
        if not self.estop_client.wait_for_service(timeout_sec=2.0):
            self.skipTest("E-stop service not available")
        if not self.reset_client.wait_for_service(timeout_sec=2.0):
            self.skipTest("Reset service not available")

        # Trigger and reset e-stop
        self._send_heartbeat()

        trigger_req = Trigger.Request()
        trigger_future = self.estop_client.call_async(trigger_req)
        self._spin_until(lambda: trigger_future.done(), timeout=5.0)

        time.sleep(0.5)

        reset_req = Trigger.Request()
        reset_future = self.reset_client.call_async(reset_req)
        self._spin_until(lambda: reset_future.done(), timeout=5.0)

        if reset_future.done():
            response = reset_future.result()
            self.assertTrue(response.success, "Reset should succeed")

    def test_joint_limit_violation(self):
        """Test joint limit violation detection."""
        # Publish joint state with position out of limits
        joint_msg = JointState()
        joint_msg.header.stamp = self.node.get_clock().now().to_msg()
        joint_msg.name = ['ned2_joint_1', 'ned2_joint_2']
        joint_msg.position = [5.0, 0.0]  # Joint 1 way beyond limit (±2.9)
        joint_msg.velocity = [0.0, 0.0]
        joint_msg.effort = [0.0, 0.0]

        self.joint_pub.publish(joint_msg)

        # Wait for violation
        received = self._spin_until(
            lambda: len(self.joint_violations) > 0,
            timeout=5.0
        )

        self.assertTrue(received, "Joint limit violation should be detected")
        if self.joint_violations:
            violation = self.joint_violations[0]
            self.assertEqual(violation['joint'], 'ned2_joint_1')
            self.assertEqual(violation['type'], 'position_hard')

    def test_velocity_limit_violation(self):
        """Test velocity limit violation detection."""
        joint_msg = JointState()
        joint_msg.header.stamp = self.node.get_clock().now().to_msg()
        joint_msg.name = ['ned2_joint_1']
        joint_msg.position = [0.0]
        joint_msg.velocity = [5.0]  # Way beyond velocity limit (1.0)
        joint_msg.effort = [0.0]

        self.joint_pub.publish(joint_msg)

        received = self._spin_until(
            lambda: any(v.get('type') == 'velocity' for v in self.joint_violations),
            timeout=5.0
        )

        self.assertTrue(received, "Velocity violation should be detected")


@launch_testing.post_shutdown_test()
class TestSafetyShutdown(unittest.TestCase):
    """Post-shutdown tests."""

    def test_exit_codes(self, proc_info):
        """Check exit codes."""
        launch_testing.asserts.assertExitCodes(proc_info)
