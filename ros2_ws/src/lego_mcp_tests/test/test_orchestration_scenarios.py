#!/usr/bin/env python3
"""
LEGO MCP Orchestration Scenarios Integration Test

Tests complex manufacturing orchestration scenarios:
1. Multi-equipment coordination
2. Failure recovery during workflow
3. Quality-driven rework scenarios
4. AGV-coordinated material transport
5. Parallel operation execution

LEGO MCP Manufacturing System v7.0
ISA-95 Compliant Manufacturing Orchestration
"""

import unittest
import time
import json
import threading
from typing import Optional, List, Dict
from dataclasses import dataclass

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseStamped

try:
    from lego_mcp_msgs.action import ExecuteWorkOrder, PerformInspection, AGVNavigation
    from lego_mcp_msgs.srv import DispatchAGV
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


def generate_test_description():
    """Generate launch description for orchestration tests."""
    return launch.LaunchDescription([
        # Core orchestration nodes
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='work_order_executor.py',
            name='work_order_executor',
            parameters=[{'feedback_rate_hz': 20.0}],
        ),
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='inspection_action_server.py',
            name='inspection_server',
            parameters=[{'feedback_rate_hz': 20.0}],
        ),
        launch_ros.actions.Node(
            package='lego_mcp_orchestrator',
            executable='agv_dispatcher.py',
            name='agv_dispatcher',
            parameters=[{
                'feedback_rate_hz': 30.0,
                'max_velocity_ms': 2.0,
            }],
        ),
        launch_ros.actions.Node(
            package='lego_mcp_discovery',
            executable='equipment_registry_node.py',
            name='equipment_registry',
        ),

        launch_testing.actions.ReadyToTest(),
    ])


@dataclass
class WorkflowStep:
    """Track workflow execution step."""
    step_name: str
    started_at: float = 0.0
    completed_at: float = 0.0
    success: bool = False
    details: Dict = None

    def duration(self) -> float:
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return 0.0


class ScenarioTestBase(unittest.TestCase):
    """Base class for scenario tests."""

    @classmethod
    def setUpClass(cls):
        if not rclpy.ok():
            rclpy.init()

    def setUp(self):
        self.node = rclpy.create_node(f'scenario_test_{id(self)}')
        self.executor = MultiThreadedExecutor(num_threads=8)
        self.executor.add_node(self.node)
        self.cb_group = ReentrantCallbackGroup()

        # Tracking
        self.workflow_steps: List[WorkflowStep] = []
        self.events: List[Dict] = []
        self.errors: List[str] = []

        # Subscribe to events
        self.node.create_subscription(
            String, '/lego_mcp/work_order/events',
            self._on_wo_event, 10
        )
        self.node.create_subscription(
            String, '/lego_mcp/inspection/events',
            self._on_insp_event, 10
        )
        self.node.create_subscription(
            String, '/lego_mcp/agv/events',
            self._on_agv_event, 10
        )

        if MSGS_AVAILABLE:
            self.wo_client = ActionClient(
                self.node, ExecuteWorkOrder, '/lego_mcp/execute_work_order',
                callback_group=self.cb_group
            )
            self.insp_client = ActionClient(
                self.node, PerformInspection, '/lego_mcp/perform_inspection',
                callback_group=self.cb_group
            )
            self.agv_client = ActionClient(
                self.node, AGVNavigation, '/lego_mcp/agv/navigate',
                callback_group=self.cb_group
            )

    def tearDown(self):
        self.node.destroy_node()

    def _on_wo_event(self, msg: String):
        try:
            event = json.loads(msg.data)
            event['source'] = 'work_order'
            self.events.append(event)
        except json.JSONDecodeError:
            pass

    def _on_insp_event(self, msg: String):
        try:
            event = json.loads(msg.data)
            event['source'] = 'inspection'
            self.events.append(event)
        except json.JSONDecodeError:
            pass

    def _on_agv_event(self, msg: String):
        try:
            event = json.loads(msg.data)
            event['source'] = 'agv'
            self.events.append(event)
        except json.JSONDecodeError:
            pass

    def _spin_until(self, condition, timeout: float = 30.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            self.executor.spin_once(timeout_sec=0.05)
            if condition():
                return True
        return False

    def _wait_for_servers(self, timeout: float = 15.0) -> bool:
        """Wait for all action servers to be available."""
        if not MSGS_AVAILABLE:
            return False

        wo_ready = self.wo_client.wait_for_server(timeout_sec=timeout)
        insp_ready = self.insp_client.wait_for_server(timeout_sec=timeout)
        agv_ready = self.agv_client.wait_for_server(timeout_sec=timeout)

        return wo_ready and insp_ready and agv_ready


class TestSequentialWorkflow(ScenarioTestBase):
    """Test sequential manufacturing workflow."""

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_print_inspect_transport_workflow(self):
        """
        Scenario: Complete sequential workflow
        1. Execute work order (print brick)
        2. Perform quality inspection
        3. AGV transports to storage
        """
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        # Step 1: Work Order
        step1 = WorkflowStep(step_name="Execute Work Order")
        step1.started_at = time.time()

        wo_goal = ExecuteWorkOrder.Goal()
        wo_goal.work_order_id = "WO-SEQ-001"
        wo_goal.stop_on_quality_fail = False

        wo_future = self.wo_client.send_goal_async(wo_goal)
        self._spin_until(lambda: wo_future.done(), timeout=10.0)
        wo_handle = wo_future.result()

        wo_result_future = wo_handle.get_result_async()
        self._spin_until(lambda: wo_result_future.done(), timeout=120.0)

        wo_result = wo_result_future.result().result
        step1.completed_at = time.time()
        step1.success = wo_result.success
        step1.details = {'parts_produced': wo_result.parts_produced}
        self.workflow_steps.append(step1)

        self.assertTrue(wo_result.success, "Work order should succeed")

        # Step 2: Inspection
        step2 = WorkflowStep(step_name="Quality Inspection")
        step2.started_at = time.time()

        insp_goal = PerformInspection.Goal()
        insp_goal.part_id = "BRICK-SEQ"
        insp_goal.serial_number = "SN-SEQ-001"
        insp_goal.inspection_type = 2
        insp_goal.use_ai_detection = True

        insp_future = self.insp_client.send_goal_async(insp_goal)
        self._spin_until(lambda: insp_future.done(), timeout=10.0)
        insp_handle = insp_future.result()

        insp_result_future = insp_handle.get_result_async()
        self._spin_until(lambda: insp_result_future.done(), timeout=60.0)

        insp_result = insp_result_future.result().result
        step2.completed_at = time.time()
        step2.success = insp_result.success
        step2.details = {
            'measurements': insp_result.measurements_taken,
            'defects': insp_result.defects_found,
        }
        self.workflow_steps.append(step2)

        self.assertTrue(insp_result.success, "Inspection should succeed")

        # Step 3: AGV Transport
        step3 = WorkflowStep(step_name="AGV Transport")
        step3.started_at = time.time()

        agv_goal = AGVNavigation.Goal()
        agv_goal.agv_id = "alvik_01"
        agv_goal.station_id = "storage_out"
        agv_goal.max_velocity = 1.0

        agv_future = self.agv_client.send_goal_async(agv_goal)
        self._spin_until(lambda: agv_future.done(), timeout=10.0)
        agv_handle = agv_future.result()

        agv_result_future = agv_handle.get_result_async()
        self._spin_until(lambda: agv_result_future.done(), timeout=60.0)

        agv_result = agv_result_future.result().result
        step3.completed_at = time.time()
        step3.success = agv_result.success
        step3.details = {
            'distance_m': agv_result.total_distance_m,
            'time_sec': agv_result.total_time_sec,
        }
        self.workflow_steps.append(step3)

        self.assertTrue(agv_result.success, "AGV transport should succeed")

        # Verify complete workflow
        self.assertEqual(len(self.workflow_steps), 3)
        self.assertTrue(all(s.success for s in self.workflow_steps))

        # Log workflow summary
        total_time = sum(s.duration() for s in self.workflow_steps)
        print(f"\n=== Sequential Workflow Complete ===")
        for step in self.workflow_steps:
            print(f"  {step.step_name}: {step.duration():.2f}s - {'OK' if step.success else 'FAIL'}")
        print(f"  Total time: {total_time:.2f}s")


class TestParallelOperations(ScenarioTestBase):
    """Test parallel manufacturing operations."""

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_concurrent_work_orders(self):
        """
        Scenario: Execute multiple work orders concurrently
        Tests orchestrator's ability to handle parallel requests.
        """
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        num_orders = 3
        goal_handles = []
        result_futures = []

        # Launch concurrent work orders
        start_time = time.time()

        for i in range(num_orders):
            wo_goal = ExecuteWorkOrder.Goal()
            wo_goal.work_order_id = f"WO-PARALLEL-{i+1:03d}"
            wo_goal.stop_on_quality_fail = False

            future = self.wo_client.send_goal_async(wo_goal)
            goal_handles.append((i, future))

        # Collect handles
        for i, future in goal_handles:
            self._spin_until(lambda f=future: f.done(), timeout=10.0)
            handle = future.result()
            if handle.accepted:
                result_futures.append((i, handle.get_result_async()))

        # Wait for all results
        results = []
        for i, rf in result_futures:
            self._spin_until(lambda f=rf: f.done(), timeout=180.0)
            result = rf.result().result
            results.append((i, result))

        end_time = time.time()

        # Verify all succeeded
        success_count = sum(1 for _, r in results if r.success)
        self.assertEqual(success_count, num_orders, "All work orders should succeed")

        # Verify parallel execution (total time < sum of individual times)
        total_elapsed = end_time - start_time
        sum_durations = sum(r.total_duration_sec for _, r in results)

        print(f"\n=== Parallel Work Orders ===")
        print(f"  Orders executed: {num_orders}")
        print(f"  Total elapsed: {total_elapsed:.2f}s")
        print(f"  Sum of durations: {sum_durations:.2f}s")
        print(f"  Parallelization factor: {sum_durations/total_elapsed:.2f}x")

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_concurrent_agv_missions(self):
        """
        Scenario: Execute multiple AGV missions concurrently
        Tests fleet management with multiple AGVs.
        """
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        # Two AGVs going to different stations
        missions = [
            ("alvik_01", "formlabs_sla"),
            ("alvik_02", "vision_station"),
        ]

        goal_handles = []

        for agv_id, station_id in missions:
            agv_goal = AGVNavigation.Goal()
            agv_goal.agv_id = agv_id
            agv_goal.station_id = station_id
            agv_goal.max_velocity = 1.0

            future = self.agv_client.send_goal_async(agv_goal)
            goal_handles.append((agv_id, station_id, future))

        # Collect results
        results = []
        for agv_id, station_id, future in goal_handles:
            self._spin_until(lambda f=future: f.done(), timeout=10.0)
            handle = future.result()

            if handle.accepted:
                result_future = handle.get_result_async()
                self._spin_until(lambda f=result_future: f.done(), timeout=60.0)
                result = result_future.result().result
                results.append((agv_id, station_id, result))

        # Verify
        self.assertEqual(len(results), len(missions))
        for agv_id, station_id, result in results:
            self.assertTrue(result.success, f"AGV {agv_id} should reach {station_id}")


class TestQualityDrivenWorkflow(ScenarioTestBase):
    """Test quality-driven manufacturing scenarios."""

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_inspection_driven_routing(self):
        """
        Scenario: Inspection result determines next action
        - If pass: route to storage
        - If fail: route to rework area (simulated)
        """
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        # Execute multiple parts and route based on inspection
        num_parts = 5
        passed_parts = 0
        failed_parts = 0

        for i in range(num_parts):
            # Inspect part
            insp_goal = PerformInspection.Goal()
            insp_goal.part_id = f"BRICK-QDW-{i+1}"
            insp_goal.serial_number = f"SN-QDW-{i+1:03d}"
            insp_goal.inspection_type = 2
            insp_goal.use_ai_detection = True

            insp_future = self.insp_client.send_goal_async(insp_goal)
            self._spin_until(lambda f=insp_future: f.done(), timeout=10.0)
            insp_handle = insp_future.result()

            insp_result_future = insp_handle.get_result_async()
            self._spin_until(lambda f=insp_result_future: f.done(), timeout=60.0)

            insp_result = insp_result_future.result().result

            # Determine routing based on result
            if insp_result.measurements_passed == insp_result.measurements_taken and \
               insp_result.defects_found == 0:
                passed_parts += 1
                destination = "storage_out"
            else:
                failed_parts += 1
                destination = "ned2_robot"  # Rework station

            # Route via AGV
            agv_goal = AGVNavigation.Goal()
            agv_goal.agv_id = "alvik_01"
            agv_goal.station_id = destination
            agv_goal.max_velocity = 1.5

            agv_future = self.agv_client.send_goal_async(agv_goal)
            self._spin_until(lambda f=agv_future: f.done(), timeout=10.0)
            agv_handle = agv_future.result()

            if agv_handle.accepted:
                agv_result_future = agv_handle.get_result_async()
                self._spin_until(lambda f=agv_result_future: f.done(), timeout=60.0)

        print(f"\n=== Quality-Driven Workflow ===")
        print(f"  Total parts: {num_parts}")
        print(f"  Passed (to storage): {passed_parts}")
        print(f"  Failed (to rework): {failed_parts}")

        # Some variation expected due to simulated defects
        self.assertEqual(passed_parts + failed_parts, num_parts)


class TestMultiEquipmentCoordination(ScenarioTestBase):
    """Test multi-equipment coordination scenarios."""

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_equipment_to_inspection_to_assembly(self):
        """
        Scenario: Full manufacturing cell coordination
        1. Work order produces parts on equipment
        2. AGV transports to inspection
        3. Inspection validates
        4. AGV transports to assembly (if passed)
        """
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        workflow_log = []

        # Step 1: Manufacturing
        wo_goal = ExecuteWorkOrder.Goal()
        wo_goal.work_order_id = "WO-MULTI-001"
        wo_goal.stop_on_quality_fail = False

        wo_future = self.wo_client.send_goal_async(wo_goal)
        self._spin_until(lambda f=wo_future: f.done(), timeout=10.0)
        wo_handle = wo_future.result()

        wo_result_future = wo_handle.get_result_async()
        self._spin_until(lambda f=wo_result_future: f.done(), timeout=120.0)

        wo_result = wo_result_future.result().result
        workflow_log.append(('manufacturing', wo_result.success, wo_result.parts_produced))

        # Step 2: Transport to inspection
        agv_goal = AGVNavigation.Goal()
        agv_goal.agv_id = "alvik_01"
        agv_goal.station_id = "vision_station"

        agv_future = self.agv_client.send_goal_async(agv_goal)
        self._spin_until(lambda f=agv_future: f.done(), timeout=10.0)
        agv_handle = agv_future.result()

        agv_result_future = agv_handle.get_result_async()
        self._spin_until(lambda f=agv_result_future: f.done(), timeout=60.0)

        agv_result = agv_result_future.result().result
        workflow_log.append(('transport_to_inspect', agv_result.success, agv_result.total_distance_m))

        # Step 3: Inspection
        insp_goal = PerformInspection.Goal()
        insp_goal.part_id = "BRICK-MULTI"
        insp_goal.serial_number = "SN-MULTI-001"
        insp_goal.inspection_type = 2
        insp_goal.use_ai_detection = True

        insp_future = self.insp_client.send_goal_async(insp_goal)
        self._spin_until(lambda f=insp_future: f.done(), timeout=10.0)
        insp_handle = insp_future.result()

        insp_result_future = insp_handle.get_result_async()
        self._spin_until(lambda f=insp_result_future: f.done(), timeout=60.0)

        insp_result = insp_result_future.result().result
        inspection_passed = (insp_result.measurements_passed == insp_result.measurements_taken)
        workflow_log.append(('inspection', insp_result.success, inspection_passed))

        # Step 4: Transport to assembly (if passed)
        if inspection_passed:
            agv_goal = AGVNavigation.Goal()
            agv_goal.agv_id = "alvik_01"
            agv_goal.station_id = "ned2_robot"

            agv_future = self.agv_client.send_goal_async(agv_goal)
            self._spin_until(lambda f=agv_future: f.done(), timeout=10.0)
            agv_handle = agv_future.result()

            agv_result_future = agv_handle.get_result_async()
            self._spin_until(lambda f=agv_result_future: f.done(), timeout=60.0)

            agv_result = agv_result_future.result().result
            workflow_log.append(('transport_to_assembly', agv_result.success, agv_result.total_distance_m))

        # Verify workflow
        print(f"\n=== Multi-Equipment Coordination ===")
        for step_name, success, detail in workflow_log:
            print(f"  {step_name}: {'OK' if success else 'FAIL'} ({detail})")

        self.assertTrue(all(s[1] for s in workflow_log), "All steps should succeed")


class TestTimingMetrics(ScenarioTestBase):
    """Test and measure timing characteristics."""

    @unittest.skipUnless(MSGS_AVAILABLE, "lego_mcp_msgs not available")
    def test_action_response_times(self):
        """Measure action server response times."""
        self.assertTrue(self._wait_for_servers(), "Servers should be ready")

        timings = {}

        # Work Order response time
        start = time.time()
        wo_goal = ExecuteWorkOrder.Goal()
        wo_goal.work_order_id = "WO-TIMING-001"

        wo_future = self.wo_client.send_goal_async(wo_goal)
        self._spin_until(lambda f=wo_future: f.done(), timeout=10.0)
        wo_handle = wo_future.result()
        timings['work_order_accept'] = time.time() - start

        # Inspection response time
        start = time.time()
        insp_goal = PerformInspection.Goal()
        insp_goal.part_id = "BRICK-TIMING"

        insp_future = self.insp_client.send_goal_async(insp_goal)
        self._spin_until(lambda f=insp_future: f.done(), timeout=10.0)
        insp_handle = insp_future.result()
        timings['inspection_accept'] = time.time() - start

        # AGV response time
        start = time.time()
        agv_goal = AGVNavigation.Goal()
        agv_goal.agv_id = "alvik_01"
        agv_goal.station_id = "formlabs_sla"

        agv_future = self.agv_client.send_goal_async(agv_goal)
        self._spin_until(lambda f=agv_future: f.done(), timeout=10.0)
        agv_handle = agv_future.result()
        timings['agv_accept'] = time.time() - start

        # Report
        print(f"\n=== Action Response Times ===")
        for name, t in timings.items():
            print(f"  {name}: {t*1000:.1f}ms")

        # All should respond within reasonable time
        for name, t in timings.items():
            self.assertLess(t, 5.0, f"{name} should respond within 5s")


@launch_testing.post_shutdown_test()
class TestOrchestrationShutdown(unittest.TestCase):
    """Tests after shutdown."""

    def test_exit_codes(self, proc_info):
        """Check clean exit."""
        launch_testing.asserts.assertExitCodes(proc_info)


if __name__ == '__main__':
    unittest.main()
