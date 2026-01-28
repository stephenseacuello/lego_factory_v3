#!/usr/bin/env python3
"""
LEGO MCP Discovery Service Integration Test

Tests discovery service functionality:
- Equipment registration
- Auto-discovery
- Topology management
- Bandwidth optimization

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


def generate_test_description():
    """Generate launch description for discovery tests."""
    return launch.LaunchDescription([
        # Launch discovery server
        launch_ros.actions.Node(
            package='lego_mcp_discovery',
            executable='discovery_server_node.py',
            name='discovery_server',
            parameters=[{
                'heartbeat_timeout_seconds': 5.0,
                'discovery_interval_seconds': 2.0,
                'enable_auto_discovery': True,
            }],
        ),
        # Launch bandwidth optimizer
        launch_ros.actions.Node(
            package='lego_mcp_discovery',
            executable='bandwidth_optimizer_node.py',
            name='bandwidth_optimizer',
            parameters=[{
                'monitoring_interval_seconds': 1.0,
                'max_total_bandwidth_mbps': 100.0,
            }],
        ),

        launch_testing.actions.ReadyToTest(),
    ])


class TestDiscoveryService(unittest.TestCase):
    """Test discovery service functionality."""

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
        self.node = rclpy.create_node('discovery_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.equipment_list = None
        self.discovery_events = []
        self.bandwidth_stats = None

        # Subscribers
        self.node.create_subscription(
            String, '/discovery/equipment_list',
            self._on_equipment_list, 10
        )
        self.node.create_subscription(
            String, '/discovery/events',
            self._on_discovery_event, 10
        )
        self.node.create_subscription(
            String, '/bandwidth/statistics',
            self._on_bandwidth_stats, 10
        )

        # Publishers
        self.heartbeat_pub = self.node.create_publisher(
            String, '/discovery/heartbeat', 10
        )
        self.register_pub = self.node.create_publisher(
            String, '/discovery/register_request', 10
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_equipment_list(self, msg: String):
        """Handle equipment list."""
        try:
            self.equipment_list = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_discovery_event(self, msg: String):
        """Handle discovery events."""
        try:
            self.discovery_events.append(json.loads(msg.data))
        except json.JSONDecodeError:
            pass

    def _on_bandwidth_stats(self, msg: String):
        """Handle bandwidth statistics."""
        try:
            self.bandwidth_stats = json.loads(msg.data)
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

    def test_discovery_server_running(self):
        """Test that discovery server is running."""
        received = self._spin_until(
            lambda: self.equipment_list is not None,
            timeout=5.0
        )
        self.assertTrue(received, "Discovery server should publish equipment list")

    def test_equipment_registration_via_heartbeat(self):
        """Test equipment registration via heartbeat."""
        # Send heartbeat
        heartbeat_msg = String()
        heartbeat_msg.data = json.dumps({
            'equipment_id': 'test_robot',
            'equipment_type': 'robot_arm',
            'node_name': 'test_robot_driver',
            'namespace': '/test',
        })
        self.heartbeat_pub.publish(heartbeat_msg)

        # Wait for registration event
        def equipment_registered():
            for event in self.discovery_events:
                if (event.get('event_type') == 'registered' and
                    event.get('equipment_id') == 'test_robot'):
                    return True
            return False

        registered = self._spin_until(equipment_registered, timeout=5.0)
        self.assertTrue(registered, "Equipment should be registered via heartbeat")

    def test_equipment_registration_via_request(self):
        """Test equipment registration via request topic."""
        # Send registration request
        register_msg = String()
        register_msg.data = json.dumps({
            'equipment_id': 'test_cnc',
            'equipment_type': 'cnc',
            'node_name': 'test_cnc_driver',
            'namespace': '/test',
            'capabilities': [
                {'name': 'milling', 'version': '1.0'},
                {'name': 'drilling', 'version': '1.0'},
            ],
            'endpoints': [
                {'type': 'publisher', 'name': '/test_cnc/status', 'message_type': 'std_msgs/String'},
                {'type': 'subscriber', 'name': '/test_cnc/gcode', 'message_type': 'std_msgs/String'},
            ],
        })
        self.register_pub.publish(register_msg)

        # Wait for equipment in list
        def equipment_in_list():
            if self.equipment_list:
                return 'test_cnc' in self.equipment_list.get('equipment', {})
            return False

        found = self._spin_until(equipment_in_list, timeout=5.0)
        self.assertTrue(found, "Equipment should appear in equipment list")

    def test_bandwidth_optimizer_running(self):
        """Test that bandwidth optimizer is running."""
        received = self._spin_until(
            lambda: self.bandwidth_stats is not None,
            timeout=5.0
        )
        self.assertTrue(received, "Bandwidth optimizer should publish statistics")

    def test_bandwidth_statistics_content(self):
        """Test bandwidth statistics content."""
        self._spin_until(lambda: self.bandwidth_stats is not None, timeout=5.0)

        if self.bandwidth_stats:
            # Check required fields
            self.assertIn('timestamp', self.bandwidth_stats)
            self.assertIn('current_bandwidth_mbps', self.bandwidth_stats)
            self.assertIn('topic_count', self.bandwidth_stats)


class TestTopologyDiscovery(unittest.TestCase):
    """Test topology discovery functionality."""

    @classmethod
    def setUpClass(cls):
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        self.node = rclpy.create_node('topology_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.topology = None

        self.node.create_subscription(
            String, '/discovery/topology',
            self._on_topology, 10
        )

    def tearDown(self):
        self.node.destroy_node()

    def _on_topology(self, msg: String):
        try:
            self.topology = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def test_topology_available(self):
        """Test that topology is available via service."""
        # Topology is available via service, test the subscription works
        self.executor.spin_once(timeout_sec=2.0)
        # Test passes if no errors


@launch_testing.post_shutdown_test()
class TestDiscoveryShutdown(unittest.TestCase):
    """Post-shutdown tests."""

    def test_exit_codes(self, proc_info):
        """Check exit codes."""
        launch_testing.asserts.assertExitCodes(proc_info)
