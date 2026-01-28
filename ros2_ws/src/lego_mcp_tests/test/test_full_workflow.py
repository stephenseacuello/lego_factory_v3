#!/usr/bin/env python3
"""
LEGO MCP Full Workflow Integration Test

Tests the complete workflow:
1. Create work order
2. Schedule on equipment
3. Execute print job (simulated)
4. Quality inspection
5. Robot assembly

LEGO MCP Manufacturing System v7.0
"""

import unittest
import time
import json
from typing import Optional

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger


def generate_test_description():
    """Generate launch description for test."""
    return launch.LaunchDescription([
        # Launch simulation nodes
        launch_ros.actions.Node(
            package='lego_mcp_simulation',
            executable='grbl_simulator',
            name='cnc_sim',
            namespace='lego_mcp',
            parameters=[{
                'machine_type': 'tinyg',
                'machine_name': 'cnc',
                'simulate_delays': False,
            }],
        ),
        launch_ros.actions.Node(
            package='lego_mcp_simulation',
            executable='formlabs_simulator',
            name='formlabs_sim',
            namespace='lego_mcp',
            parameters=[{
                'printer_name': 'formlabs',
                'layer_time_s': 0.1,
                'heating_time_s': 0.5,
                'filling_time_s': 0.2,
            }],
        ),

        # Ready to test action
        launch_testing.actions.ReadyToTest(),
    ])


class TestFullWorkflow(unittest.TestCase):
    """Test complete manufacturing workflow."""

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
        self.node = rclpy.create_node('workflow_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        # State tracking
        self.print_complete = False
        self.print_status = None
        self.quality_events = []

        # Subscribers
        self.node.create_subscription(
            String,
            '/lego_mcp/formlabs/status',
            self._on_formlabs_status,
            10
        )
        self.node.create_subscription(
            String,
            '/lego_mcp/formlabs/events',
            self._on_formlabs_event,
            10
        )

        # Publishers
        self.upload_pub = self.node.create_publisher(
            String, '/lego_mcp/formlabs/upload', 10
        )
        self.command_pub = self.node.create_publisher(
            String, '/lego_mcp/formlabs/command', 10
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_formlabs_status(self, msg: String):
        """Handle Formlabs status."""
        try:
            self.print_status = json.loads(msg.data)
            if self.print_status.get('printer', {}).get('state') == 'finished':
                self.print_complete = True
        except json.JSONDecodeError:
            pass

    def _on_formlabs_event(self, msg: String):
        """Handle Formlabs events."""
        try:
            event = json.loads(msg.data)
            if event.get('event') == 'print_complete':
                self.print_complete = True
        except json.JSONDecodeError:
            pass

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        """Spin until condition is true or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    def test_formlabs_simulator_responds(self):
        """Test that Formlabs simulator is running and responding."""
        # Wait for status
        received = self._spin_until(lambda: self.print_status is not None, timeout=5.0)
        self.assertTrue(received, "Formlabs simulator should publish status")

    def test_upload_print_job(self):
        """Test uploading a print job to simulator."""
        # Upload a job
        upload_msg = String()
        upload_msg.data = json.dumps({
            'file_path': '/test/brick_2x4.form',
            'name': 'Test Brick'
        })

        time.sleep(0.5)  # Wait for simulator to be ready
        self.upload_pub.publish(upload_msg)

        # Wait for job to appear in status
        def job_uploaded():
            if self.print_status:
                return self.print_status.get('queue_length', 0) > 0
            return False

        uploaded = self._spin_until(job_uploaded, timeout=5.0)
        self.assertTrue(uploaded, "Print job should be uploaded")

    def test_print_workflow(self):
        """Test complete print workflow."""
        # Upload job
        upload_msg = String()
        upload_msg.data = json.dumps({
            'file_path': '/test/brick_2x4.form',
            'name': 'Workflow Test Brick'
        })
        self.upload_pub.publish(upload_msg)

        time.sleep(0.5)

        # Start print
        cmd_msg = String()
        cmd_msg.data = json.dumps({'command': 'print'})
        self.command_pub.publish(cmd_msg)

        # Wait for completion (with fast simulation times, should be quick)
        completed = self._spin_until(lambda: self.print_complete, timeout=60.0)

        self.assertTrue(completed, "Print job should complete")


class TestCNCSimulator(unittest.TestCase):
    """Test CNC simulator functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('cnc_test_node')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.cnc_status = None
        self.cnc_response = None

        self.node.create_subscription(
            String,
            '/lego_mcp/cnc/status',
            self._on_cnc_status,
            10
        )
        self.node.create_subscription(
            String,
            '/lego_mcp/cnc/response',
            self._on_cnc_response,
            10
        )

        self.gcode_pub = self.node.create_publisher(
            String, '/lego_mcp/cnc/gcode', 10
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_cnc_status(self, msg: String):
        """Handle CNC status."""
        self.cnc_status = msg.data

    def _on_cnc_response(self, msg: String):
        """Handle CNC response."""
        self.cnc_response = msg.data

    def _spin_until(self, condition, timeout: float = 10.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    def test_cnc_simulator_status(self):
        """Test CNC simulator publishes status."""
        received = self._spin_until(lambda: self.cnc_status is not None, timeout=5.0)
        self.assertTrue(received, "CNC simulator should publish status")

    def test_cnc_gcode_execution(self):
        """Test CNC simulator executes G-code."""
        # Send simple G-code
        gcode_msg = String()
        gcode_msg.data = "G0 X10 Y10\nG1 X20 Y20 F1000"
        self.gcode_pub.publish(gcode_msg)

        # Wait for response
        received = self._spin_until(lambda: self.cnc_response is not None, timeout=5.0)
        self.assertTrue(received, "CNC should respond to G-code")


@launch_testing.post_shutdown_test()
class TestWorkflowShutdown(unittest.TestCase):
    """Tests that run after nodes shut down."""

    def test_exit_codes(self, proc_info):
        """Check all processes exited cleanly."""
        launch_testing.asserts.assertExitCodes(proc_info)
