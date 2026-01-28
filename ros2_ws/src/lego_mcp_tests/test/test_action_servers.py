#!/usr/bin/env python3
"""
LEGO MCP Action Servers Integration Test

Tests the v7.0 action servers:
1. ExecuteWorkOrder action
2. PerformInspection action
3. AGVNavigation action
4. Equipment discovery and registry

LEGO MCP Manufacturing System v7.0
"""

import unittest
import time
import json
from typing import Optional, List

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor, MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseStamped, Quaternion

try:
    from lego_mcp_msgs.action import ExecuteWorkOrder, PerformInspection, AGVNavigation
    from lego_mcp_msgs.srv import DispatchAGV, DiscoverEquipment
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


def generate_test_description():
    """Generate launch description for action server tests."""
    return launch.LaunchDescription([
        # Work Order Executor
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='work_order_executor.py',
            name='work_order_executor',
            namespace='lego_mcp',
            parameters=[{
                'feedback_rate_hz': 10.0,
                'operation_timeout_sec': 60.0,
                'quality_gate_enabled': True,
            }],
        ),
        # Inspection Action Server
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='inspection_action_server.py',
            name='inspection_server',
            namespace='lego_mcp',
            parameters=[{
                'feedback_rate_hz': 10.0,
                'enable_ai_detection': True,
            }],
        ),
        # AGV Dispatcher
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='agv_dispatcher.py',
            name='agv_dispatcher',
            namespace='lego_mcp',
            parameters=[{
                'feedback_rate_hz': 20.0,
                'max_velocity_ms': 1.0,  # Faster for testing
            }],
        ),
        # Equipment Registry
        launch_ros.actions.Node(
            package='lego_mcp_discovery',
            executable='equipment_registry_node.py',
            name='equipment_registry',
            namespace='lego_mcp',
            parameters=[{
                'scan_interval_sec': 5.0,
                'offline_threshold_sec': 10.0,
            }],
        ),

        launch_testing.actions.ReadyToTest(),
    ])


class TestWorkOrderAction(unittest.TestCase):
    """Test ExecuteWorkOrder action server."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('work_order_test')
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.node)

        self.feedback_msgs: List[dict] = []
        self.result = None

        if MSGS_AVAILABLE:
            self._action_client = ActionClient(
                self.node,
                ExecuteWorkOrder,
                '/lego_mcp/execute_work_order'
            )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _feedback_callback(self, feedback_msg):
        """Store feedback messages."""
        self.feedback_msgs.append({
            'operation_id': feedback_msg.feedback.current_operation_id,
            'progress': feedback_msg.feedback.overall_progress,
            'status': feedback_msg.feedback.status_message,
        })

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_action_server_available(self):
        """Test that work order action server is available."""
        available = self._action_client.wait_for_server(timeout_sec=10.0)
        self.assertTrue(available, "Work order action server should be available")

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_execute_work_order(self):
        """Test executing a work order."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        # Create goal
        goal = ExecuteWorkOrder.Goal()
        goal.work_order_id = "WO-TEST-001"
        goal.job_id = "JOB-001"
        goal.auto_schedule = True
        goal.parallel_operations = False
        goal.stop_on_quality_fail = False
        goal.require_confirmation = False

        # Send goal
        future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._feedback_callback
        )

        # Wait for goal acceptance
        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted, "Work order goal should be accepted")

        # Wait for result
        result_future = goal_handle.get_result_async()
        completed = self._spin_until(lambda: result_future.done(), timeout=120.0)

        self.assertTrue(completed, "Work order should complete")

        result = result_future.result().result
        self.assertTrue(result.success, f"Work order should succeed: {result.message}")
        self.assertGreater(result.operations_completed, 0, "Should complete operations")
        self.assertGreater(len(self.feedback_msgs), 0, "Should receive feedback")

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_work_order_cancellation(self):
        """Test cancelling a work order."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        goal = ExecuteWorkOrder.Goal()
        goal.work_order_id = "WO-CANCEL-001"
        goal.stop_on_quality_fail = False

        future = self._action_client.send_goal_async(goal)
        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted)

        # Wait a bit then cancel
        time.sleep(1.0)
        cancel_future = goal_handle.cancel_goal_async()
        self._spin_until(lambda: cancel_future.done(), timeout=10.0)

        # Verify cancelled
        result_future = goal_handle.get_result_async()
        self._spin_until(lambda: result_future.done(), timeout=10.0)


class TestInspectionAction(unittest.TestCase):
    """Test PerformInspection action server."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('inspection_test')
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.node)

        self.feedback_msgs = []

        if MSGS_AVAILABLE:
            self._action_client = ActionClient(
                self.node,
                PerformInspection,
                '/lego_mcp/perform_inspection'
            )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _feedback_callback(self, feedback_msg):
        """Store feedback messages."""
        self.feedback_msgs.append({
            'check': feedback_msg.feedback.current_check,
            'progress': feedback_msg.feedback.progress_percent,
            'defects': feedback_msg.feedback.defects_so_far,
        })

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_inspection_server_available(self):
        """Test that inspection action server is available."""
        available = self._action_client.wait_for_server(timeout_sec=10.0)
        self.assertTrue(available, "Inspection action server should be available")

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_standard_inspection(self):
        """Test standard brick inspection."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        goal = PerformInspection.Goal()
        goal.part_id = "BRICK-2x4"
        goal.serial_number = "SN-TEST-001"
        goal.inspection_plan_id = "LEGO_BRICK_STANDARD"
        goal.inspection_type = 2  # FINAL
        goal.capture_images = False
        goal.generate_report = True
        goal.use_ai_detection = True
        goal.ai_confidence_threshold = 0.8

        future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._feedback_callback
        )

        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted, "Inspection goal should be accepted")

        result_future = goal_handle.get_result_async()
        completed = self._spin_until(lambda: result_future.done(), timeout=60.0)

        self.assertTrue(completed, "Inspection should complete")

        result = result_future.result().result
        self.assertTrue(result.success, "Inspection should succeed")
        self.assertGreater(result.measurements_taken, 0, "Should take measurements")
        self.assertLessEqual(result.defects_found, result.measurements_taken)

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_first_article_inspection(self):
        """Test first article inspection (more thorough)."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        goal = PerformInspection.Goal()
        goal.part_id = "BRICK-2x4"
        goal.serial_number = "SN-FAI-001"
        goal.inspection_plan_id = "LEGO_BRICK_FAI"
        goal.inspection_type = 3  # FIRST_ARTICLE
        goal.use_ai_detection = True
        goal.ai_confidence_threshold = 0.9  # Higher threshold for FAI

        future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._feedback_callback
        )

        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted)

        result_future = goal_handle.get_result_async()
        completed = self._spin_until(lambda: result_future.done(), timeout=90.0)

        self.assertTrue(completed)

        result = result_future.result().result
        # FAI should have more measurements than standard
        self.assertGreaterEqual(result.measurements_taken, 7)


class TestAGVAction(unittest.TestCase):
    """Test AGVNavigation action server."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('agv_test')
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.node)

        self.feedback_msgs = []
        self.fleet_status = None

        # Subscribe to fleet status
        self.node.create_subscription(
            String,
            '/lego_mcp/agv/fleet',
            self._on_fleet_status,
            10
        )

        if MSGS_AVAILABLE:
            self._action_client = ActionClient(
                self.node,
                AGVNavigation,
                '/lego_mcp/agv/navigate'
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

    def _feedback_callback(self, feedback_msg):
        """Store feedback messages."""
        self.feedback_msgs.append({
            'progress': feedback_msg.feedback.progress_percent,
            'distance_remaining': feedback_msg.feedback.distance_remaining_m,
            'status': feedback_msg.feedback.status_message,
        })

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_agv_action_available(self):
        """Test that AGV action server is available."""
        available = self._action_client.wait_for_server(timeout_sec=10.0)
        self.assertTrue(available, "AGV action server should be available")

    def test_fleet_status_published(self):
        """Test that fleet status is published."""
        received = self._spin_until(lambda: self.fleet_status is not None, timeout=5.0)
        self.assertTrue(received, "Fleet status should be published")

        self.assertIn('agv_count', self.fleet_status)
        self.assertGreater(self.fleet_status['agv_count'], 0)

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_navigate_to_station(self):
        """Test AGV navigation to station."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        # Wait for fleet status to know AGV ID
        self._spin_until(lambda: self.fleet_status is not None, timeout=5.0)
        agv_id = self.fleet_status['agvs'][0]['agv_id']

        goal = AGVNavigation.Goal()
        goal.agv_id = agv_id
        goal.station_id = "formlabs_sla"
        goal.max_velocity = 0.5
        goal.precise_docking = True
        goal.position_tolerance = 0.05
        goal.orientation_tolerance = 0.1
        goal.allow_replanning = True

        future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._feedback_callback
        )

        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted, "Navigation goal should be accepted")

        result_future = goal_handle.get_result_async()
        completed = self._spin_until(lambda: result_future.done(), timeout=60.0)

        self.assertTrue(completed, "Navigation should complete")

        result = result_future.result().result
        self.assertTrue(result.success, f"Navigation should succeed: {result.message}")
        self.assertLess(result.position_error, 0.1, "Position error should be small")
        self.assertGreater(len(self.feedback_msgs), 0, "Should receive feedback")

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_navigate_to_pose(self):
        """Test AGV navigation to arbitrary pose."""
        self._action_client.wait_for_server(timeout_sec=10.0)

        self._spin_until(lambda: self.fleet_status is not None, timeout=5.0)
        agv_id = self.fleet_status['agvs'][0]['agv_id']

        goal = AGVNavigation.Goal()
        goal.agv_id = agv_id
        goal.goal_pose = PoseStamped()
        goal.goal_pose.pose.position.x = 3.0
        goal.goal_pose.pose.position.y = 1.0
        goal.goal_pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
        goal.max_velocity = 0.5

        future = self._action_client.send_goal_async(goal)
        self._spin_until(lambda: future.done(), timeout=10.0)
        goal_handle = future.result()

        self.assertTrue(goal_handle.accepted)

        result_future = goal_handle.get_result_async()
        completed = self._spin_until(lambda: result_future.done(), timeout=60.0)

        self.assertTrue(completed)
        result = result_future.result().result
        self.assertTrue(result.success)


class TestEquipmentDiscovery(unittest.TestCase):
    """Test equipment discovery and registry."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('discovery_test')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        self.registry_data = None
        self.equipment_events = []

        self.node.create_subscription(
            String,
            '/lego_mcp/equipment/registry',
            self._on_registry,
            10
        )
        self.node.create_subscription(
            String,
            '/lego_mcp/equipment/events',
            self._on_event,
            10
        )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _on_registry(self, msg: String):
        """Handle registry update."""
        try:
            self.registry_data = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_event(self, msg: String):
        """Handle equipment event."""
        try:
            event = json.loads(msg.data)
            self.equipment_events.append(event)
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

    def test_registry_published(self):
        """Test that equipment registry is published."""
        received = self._spin_until(lambda: self.registry_data is not None, timeout=10.0)
        self.assertTrue(received, "Equipment registry should be published")

        self.assertIn('equipment_count', self.registry_data)
        self.assertIn('equipment', self.registry_data)

    def test_known_equipment_registered(self):
        """Test that known equipment is pre-registered."""
        self._spin_until(lambda: self.registry_data is not None, timeout=10.0)

        equipment_ids = [eq['equipment_id'] for eq in self.registry_data['equipment']]

        # Known equipment from equipment_registry_node.py
        expected_equipment = ['grbl_cnc', 'formlabs_sla', 'bambu_fdm']

        for eq_id in expected_equipment:
            self.assertIn(eq_id, equipment_ids, f"{eq_id} should be registered")

    def test_equipment_capabilities(self):
        """Test that equipment has capabilities listed."""
        self._spin_until(lambda: self.registry_data is not None, timeout=10.0)

        for equipment in self.registry_data['equipment']:
            self.assertIn('capabilities', equipment)
            self.assertIsInstance(equipment['capabilities'], list)

    def test_equipment_protocols(self):
        """Test that equipment has protocols listed."""
        self._spin_until(lambda: self.registry_data is not None, timeout=10.0)

        for equipment in self.registry_data['equipment']:
            self.assertIn('supported_protocols', equipment)
            self.assertIn('ros2', equipment['supported_protocols'],
                         "ROS2 should be a supported protocol")


class TestIntegrationWorkflow(unittest.TestCase):
    """Integration test for complete manufacturing workflow with actions."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        """Set up each test."""
        self.node = rclpy.create_node('integration_test')
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.node)

        if MSGS_AVAILABLE:
            self._wo_client = ActionClient(
                self.node, ExecuteWorkOrder, '/lego_mcp/execute_work_order'
            )
            self._insp_client = ActionClient(
                self.node, PerformInspection, '/lego_mcp/perform_inspection'
            )
            self._agv_client = ActionClient(
                self.node, AGVNavigation, '/lego_mcp/agv/navigate'
            )

    def tearDown(self):
        """Tear down each test."""
        self.node.destroy_node()

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        """Spin until condition or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.1)
            if condition():
                return True
        return False

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_manufacturing_to_inspection_workflow(self):
        """Test complete workflow: execute work order -> inspect result."""
        # Wait for servers
        wo_ready = self._wo_client.wait_for_server(timeout_sec=10.0)
        insp_ready = self._insp_client.wait_for_server(timeout_sec=10.0)

        self.assertTrue(wo_ready and insp_ready, "Action servers should be ready")

        # Step 1: Execute work order
        wo_goal = ExecuteWorkOrder.Goal()
        wo_goal.work_order_id = "WO-INTEGRATION-001"
        wo_goal.stop_on_quality_fail = False

        wo_future = self._wo_client.send_goal_async(wo_goal)
        self._spin_until(lambda: wo_future.done(), timeout=10.0)
        wo_handle = wo_future.result()

        self.assertTrue(wo_handle.accepted)

        wo_result_future = wo_handle.get_result_async()
        self._spin_until(lambda: wo_result_future.done(), timeout=120.0)

        wo_result = wo_result_future.result().result
        self.assertTrue(wo_result.success, "Work order should succeed")

        # Step 2: Perform final inspection
        insp_goal = PerformInspection.Goal()
        insp_goal.part_id = "BRICK-2x4"
        insp_goal.serial_number = "SN-INTEGRATION-001"
        insp_goal.inspection_type = 2  # FINAL
        insp_goal.use_ai_detection = True

        insp_future = self._insp_client.send_goal_async(insp_goal)
        self._spin_until(lambda: insp_future.done(), timeout=10.0)
        insp_handle = insp_future.result()

        self.assertTrue(insp_handle.accepted)

        insp_result_future = insp_handle.get_result_async()
        self._spin_until(lambda: insp_result_future.done(), timeout=60.0)

        insp_result = insp_result_future.result().result
        self.assertTrue(insp_result.success, "Inspection should succeed")

        # Verify complete workflow metrics
        self.assertGreater(wo_result.parts_produced, 0)
        self.assertGreater(insp_result.measurements_taken, 0)


@launch_testing.post_shutdown_test()
class TestActionServersShutdown(unittest.TestCase):
    """Tests that run after nodes shut down."""

    def test_exit_codes(self, proc_info):
        """Check all processes exited cleanly."""
        launch_testing.asserts.assertExitCodes(proc_info)


if __name__ == '__main__':
    unittest.main()
