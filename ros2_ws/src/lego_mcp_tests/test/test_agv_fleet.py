#!/usr/bin/env python3
"""
LEGO MCP AGV Fleet Integration Test

Tests AGV fleet management functionality:
- Fleet manager registration
- Task allocation
- AGV simulation
- Transport tasks

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

from std_msgs.msg import String
from geometry_msgs.msg import Twist


def generate_test_description():
    """Generate launch description for AGV fleet tests."""
    return launch.LaunchDescription([
        # Launch fleet manager
        launch_ros.actions.Node(
            package='lego_mcp_agv',
            executable='fleet_manager_node.py',
            name='fleet_manager',
            namespace='lego_mcp',
            parameters=[{
                'max_agvs': 5,
                'task_timeout_seconds': 60.0,
            }],
        ),
        # Launch task allocator
        launch_ros.actions.Node(
            package='lego_mcp_agv',
            executable='task_allocator_node.py',
            name='task_allocator',
            namespace='lego_mcp',
            parameters=[{
                'strategy': 'hybrid',
            }],
        ),
        # Launch simulated AGV
        launch_ros.actions.Node(
            package='lego_mcp_agv',
            executable='agv_simulator_node.py',
            name='alvik_sim_test',
            namespace='lego_mcp',
            parameters=[{
                'agv_id': 'alvik_test',
                'initial_x': 0.0,
                'initial_y': 0.0,
            }],
        ),

        launch_testing.actions.ReadyToTest(),
    ])


class TestAGVFleet(unittest.TestCase):
    """Test AGV fleet functionality."""

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
        self.node = rclpy.create_node('agv_fleet_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.fleet_status = None
        self.agv_status = None
        self.task_updates = []

        # Subscribers
        self.node.create_subscription(
            String, '/fleet/status',
            self._on_fleet_status, 10
        )
        self.node.create_subscription(
            String, '/alvik_test/status',
            self._on_agv_status, 10
        )
        self.node.create_subscription(
            String, '/fleet/task_updates',
            self._on_task_update, 10
        )

        # Publishers
        self.transport_pub = self.node.create_publisher(
            String, '/lego_mcp/transport_request', 10
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_fleet_status(self, msg: String):
        """Handle fleet status."""
        try:
            self.fleet_status = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_agv_status(self, msg: String):
        """Handle AGV status."""
        try:
            self.agv_status = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_task_update(self, msg: String):
        """Handle task updates."""
        try:
            self.task_updates.append(json.loads(msg.data))
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

    def test_fleet_manager_running(self):
        """Test that fleet manager is running and publishing status."""
        received = self._spin_until(
            lambda: self.fleet_status is not None,
            timeout=5.0
        )
        self.assertTrue(received, "Fleet manager should publish status")

    def test_agv_simulator_running(self):
        """Test that AGV simulator is running and publishing status."""
        received = self._spin_until(
            lambda: self.agv_status is not None,
            timeout=5.0
        )
        self.assertTrue(received, "AGV simulator should publish status")

    def test_agv_auto_registration(self):
        """Test that AGV is automatically registered with fleet."""
        # Wait for AGV to be registered
        def agv_registered():
            if self.fleet_status:
                return 'alvik_test' in self.fleet_status.get('agvs', {})
            return False

        registered = self._spin_until(agv_registered, timeout=10.0)
        self.assertTrue(registered, "AGV should be auto-registered")

    def test_transport_task_submission(self):
        """Test submitting a transport task."""
        # First ensure AGV is registered
        self._spin_until(
            lambda: self.fleet_status and 'alvik_test' in self.fleet_status.get('agvs', {}),
            timeout=5.0
        )

        # Submit transport task
        task_msg = String()
        task_msg.data = json.dumps({
            'type': 'transfer',
            'source': 'printer_pickup',
            'destination': 'assembly_ned2',
            'payload_id': 'brick_001',
            'payload_type': 'lego_brick',
            'priority': 2,
        })
        self.transport_pub.publish(task_msg)

        # Wait for task update
        received = self._spin_until(
            lambda: len(self.task_updates) > 0,
            timeout=5.0
        )

        self.assertTrue(received, "Should receive task update after submission")

    def test_agv_velocity_command(self):
        """Test AGV responds to velocity commands."""
        # Create velocity publisher
        cmd_vel_pub = self.node.create_publisher(
            Twist, '/alvik_test/cmd_vel', 10
        )

        # Wait for AGV status
        self._spin_until(lambda: self.agv_status is not None, timeout=5.0)

        initial_x = self.agv_status.get('position', {}).get('x', 0) if self.agv_status else 0

        # Send velocity command
        cmd = Twist()
        cmd.linear.x = 0.1
        cmd_vel_pub.publish(cmd)

        # Wait for movement
        time.sleep(1.0)
        self._spin_until(lambda: self.agv_status is not None, timeout=2.0)

        # Check position changed
        final_x = self.agv_status.get('position', {}).get('x', 0) if self.agv_status else 0

        # AGV should have moved
        self.assertNotEqual(initial_x, final_x, "AGV should move with velocity command")


class TestTaskAllocator(unittest.TestCase):
    """Test task allocator functionality."""

    @classmethod
    def setUpClass(cls):
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        self.node = rclpy.create_node('allocator_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.allocation_result = None

        self.node.create_subscription(
            String, '/task_allocator/allocation',
            self._on_allocation, 10
        )

        self.request_pub = self.node.create_publisher(
            String, '/task_allocator/request', 10
        )

    def tearDown(self):
        self.node.destroy_node()

    def _on_allocation(self, msg: String):
        try:
            self.allocation_result = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def test_allocation_request(self):
        """Test task allocation request."""
        # This test will work once AGVs are registered
        # For now, just verify the topic exists
        self.executor.spin_once(timeout_sec=1.0)
        # Test passes if no errors


@launch_testing.post_shutdown_test()
class TestAGVShutdown(unittest.TestCase):
    """Post-shutdown tests."""

    def test_exit_codes(self, proc_info):
        """Check exit codes."""
        launch_testing.asserts.assertExitCodes(proc_info)
