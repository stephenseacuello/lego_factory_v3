#!/usr/bin/env python3
"""
Work Order Executor - ExecuteWorkOrder Action Server

Provides long-running work order execution with progress feedback.
Coordinates equipment, quality checks, and material handling.

LEGO MCP Manufacturing System v7.0
ISA-95 Compliant Work Order Execution
"""

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String
from std_srvs.srv import Trigger

try:
    from lego_mcp_msgs.action import ExecuteWorkOrder
    from lego_mcp_msgs.msg import EquipmentStatus, QualityEvent
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    print("Warning: lego_mcp_msgs not available, running in stub mode")


class OperationState(Enum):
    """Operation execution state."""
    PENDING = 0
    QUEUED = 1
    WAITING_RESOURCE = 2
    IN_PROGRESS = 3
    QUALITY_HOLD = 4
    COMPLETED = 5
    FAILED = 6
    CANCELLED = 7


@dataclass
class OperationTracker:
    """Track individual operation within work order."""
    operation_id: str
    operation_name: str
    equipment_id: str
    state: OperationState = OperationState.PENDING
    progress_percent: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    quality_passed: bool = True
    defects_found: int = 0
    material_consumed_kg: float = 0.0
    energy_consumed_kwh: float = 0.0
    error_message: str = ""


@dataclass
class WorkOrderExecution:
    """Track work order execution state."""
    work_order_id: str
    job_id: str
    operations: List[OperationTracker] = field(default_factory=list)
    current_operation_index: int = 0

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0

    # Counters
    parts_produced: int = 0
    parts_passed_quality: int = 0
    parts_failed_quality: int = 0
    parts_reworked: int = 0

    # Options
    stop_on_quality_fail: bool = True
    parallel_operations: bool = False
    require_confirmation: bool = False

    # State
    is_cancelled: bool = False
    on_quality_hold: bool = False
    waiting_for_resource: bool = False
    waiting_reason: str = ""


class WorkOrderExecutorNode(Node):
    """
    ROS2 Action Server for executing manufacturing work orders.

    Features:
    - Long-running execution with progress feedback
    - Equipment coordination
    - Quality gate integration
    - Material tracking
    - ISA-95 compliant timing metrics
    """

    def __init__(self):
        super().__init__('work_order_executor')

        # Parameters
        self.declare_parameter('feedback_rate_hz', 2.0)
        self.declare_parameter('operation_timeout_sec', 3600.0)
        self.declare_parameter('quality_gate_enabled', True)
        self.declare_parameter('material_tracking_enabled', True)

        self._feedback_rate = self.get_parameter('feedback_rate_hz').value
        self._operation_timeout = self.get_parameter('operation_timeout_sec').value
        self._quality_gate_enabled = self.get_parameter('quality_gate_enabled').value
        self._material_tracking = self.get_parameter('material_tracking_enabled').value

        # Active executions
        self._executions: Dict[str, WorkOrderExecution] = {}
        self._lock = threading.RLock()

        # Equipment status tracking
        self._equipment_status: Dict[str, Dict] = {}
        self._equipment_available: Dict[str, bool] = {}

        # Callback groups
        self._action_group = ReentrantCallbackGroup()
        self._service_group = MutuallyExclusiveCallbackGroup()

        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Action server
        if MSGS_AVAILABLE:
            self._execute_action_server = ActionServer(
                self,
                ExecuteWorkOrder,
                '/lego_mcp/execute_work_order',
                execute_callback=self._execute_work_order,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._action_group
            )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/lego_mcp/work_order/status',
            reliable_qos
        )

        self._event_pub = self.create_publisher(
            String,
            '/lego_mcp/work_order/events',
            10
        )

        # Subscribers
        self.create_subscription(
            String,
            '/lego_mcp/equipment/registry',
            self._on_equipment_registry,
            reliable_qos
        )

        if MSGS_AVAILABLE:
            self.create_subscription(
                QualityEvent,
                '/quality/events',
                self._on_quality_event,
                10
            )

        # Services
        self._get_status_srv = self.create_service(
            Trigger,
            '/lego_mcp/work_order/get_active',
            self._get_active_work_orders,
            callback_group=self._service_group
        )

        self.get_logger().info(
            f'Work Order Executor started - feedback rate: {self._feedback_rate}Hz'
        )

    def _goal_callback(self, goal_request) -> GoalResponse:
        """Accept or reject incoming work order execution goal."""
        work_order_id = goal_request.work_order_id
        self.get_logger().info(f'Received work order execution request: {work_order_id}')

        # Check if already executing this work order
        with self._lock:
            if work_order_id in self._executions:
                self.get_logger().warning(f'Work order {work_order_id} already executing')
                return GoalResponse.REJECT

        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        """Handle cancellation request."""
        self.get_logger().info('Received cancel request for work order execution')

        # Mark execution as cancelled
        with self._lock:
            for exec_data in self._executions.values():
                if goal_handle in []:  # Would match goal handle
                    exec_data.is_cancelled = True

        return CancelResponse.ACCEPT

    async def _execute_work_order(self, goal_handle: ServerGoalHandle):
        """Execute the work order with progress feedback."""
        request = goal_handle.request
        work_order_id = request.work_order_id
        job_id = request.job_id

        self.get_logger().info(f'Executing work order: {work_order_id}')

        # Initialize execution tracking
        execution = WorkOrderExecution(
            work_order_id=work_order_id,
            job_id=job_id,
            start_time=time.time(),
            stop_on_quality_fail=request.stop_on_quality_fail,
            parallel_operations=request.parallel_operations,
            require_confirmation=request.require_confirmation,
        )

        # Generate operations from work order
        execution.operations = self._load_operations(work_order_id, job_id)

        with self._lock:
            self._executions[work_order_id] = execution

        self._publish_event('work_order_started', {
            'work_order_id': work_order_id,
            'job_id': job_id,
            'operation_count': len(execution.operations),
        })

        # Create result and feedback
        if MSGS_AVAILABLE:
            result = ExecuteWorkOrder.Result()
            feedback = ExecuteWorkOrder.Feedback()
        else:
            result = type('Result', (), {})()
            feedback = type('Feedback', (), {})()

        try:
            # Execute operations sequentially or in parallel
            for i, operation in enumerate(execution.operations):
                if execution.is_cancelled:
                    self.get_logger().info(f'Work order {work_order_id} cancelled')
                    break

                execution.current_operation_index = i

                # Wait for equipment availability
                while not self._is_equipment_available(operation.equipment_id):
                    execution.waiting_for_resource = True
                    execution.waiting_reason = f'Waiting for {operation.equipment_id}'

                    # Send feedback
                    self._update_feedback(feedback, execution, operation)
                    goal_handle.publish_feedback(feedback)

                    await self._async_sleep(1.0 / self._feedback_rate)

                    if execution.is_cancelled:
                        break

                if execution.is_cancelled:
                    break

                execution.waiting_for_resource = False
                execution.waiting_reason = ""

                # Execute operation
                operation.state = OperationState.IN_PROGRESS
                operation.started_at = time.time()

                self.get_logger().info(
                    f'Starting operation {operation.operation_id} on {operation.equipment_id}'
                )

                # Simulate operation execution with progress updates
                success = await self._execute_operation(
                    operation,
                    execution,
                    feedback,
                    goal_handle
                )

                operation.completed_at = time.time()

                if success:
                    operation.state = OperationState.COMPLETED
                    operation.progress_percent = 100.0
                    execution.parts_produced += 1

                    # Quality check
                    if self._quality_gate_enabled:
                        quality_passed = await self._check_quality(operation)
                        operation.quality_passed = quality_passed

                        if quality_passed:
                            execution.parts_passed_quality += 1
                        else:
                            execution.parts_failed_quality += 1
                            operation.defects_found += 1

                            if execution.stop_on_quality_fail:
                                execution.on_quality_hold = True
                                self.get_logger().warning(
                                    f'Quality hold for {operation.operation_id}'
                                )

                                # Wait for quality resolution
                                while execution.on_quality_hold and not execution.is_cancelled:
                                    self._update_feedback(feedback, execution, operation)
                                    goal_handle.publish_feedback(feedback)
                                    await self._async_sleep(1.0 / self._feedback_rate)
                else:
                    operation.state = OperationState.FAILED
                    self.get_logger().error(f'Operation {operation.operation_id} failed')

                    if execution.stop_on_quality_fail:
                        break

        except Exception as e:
            self.get_logger().error(f'Work order execution error: {e}')
            result.success = False
            result.message = str(e)

        finally:
            execution.end_time = time.time()

            with self._lock:
                del self._executions[work_order_id]

        # Compute final metrics
        completed_ops = sum(
            1 for op in execution.operations
            if op.state == OperationState.COMPLETED
        )
        failed_ops = sum(
            1 for op in execution.operations
            if op.state == OperationState.FAILED
        )

        total_duration = execution.end_time - execution.start_time
        productive_time = sum(
            (op.completed_at or 0) - (op.started_at or 0)
            for op in execution.operations
            if op.started_at and op.completed_at
        )

        # Populate result
        if execution.is_cancelled:
            goal_handle.canceled()
            result.success = False
            result.message = "Work order cancelled"
        elif failed_ops == 0:
            goal_handle.succeed()
            result.success = True
            result.message = f"Work order completed: {completed_ops} operations"
        else:
            goal_handle.abort()
            result.success = False
            result.message = f"Work order failed: {failed_ops} operations failed"

        result.operations_completed = completed_ops
        result.operations_failed = failed_ops
        result.parts_produced = execution.parts_produced
        result.parts_passed_quality = execution.parts_passed_quality
        result.parts_failed_quality = execution.parts_failed_quality
        result.parts_reworked = execution.parts_reworked
        result.total_duration_sec = total_duration
        result.productive_time_sec = productive_time
        result.downtime_sec = total_duration - productive_time

        # Quality metrics
        if execution.parts_produced > 0:
            result.first_pass_yield = execution.parts_passed_quality / execution.parts_produced
            result.overall_yield = (
                execution.parts_passed_quality + execution.parts_reworked
            ) / execution.parts_produced
        else:
            result.first_pass_yield = 0.0
            result.overall_yield = 0.0

        # Resource usage
        result.material_consumed_kg = sum(op.material_consumed_kg for op in execution.operations)
        result.energy_consumed_kwh = sum(op.energy_consumed_kwh for op in execution.operations)

        self._publish_event('work_order_completed', {
            'work_order_id': work_order_id,
            'success': result.success,
            'operations_completed': completed_ops,
            'parts_produced': execution.parts_produced,
            'duration_sec': total_duration,
        })

        return result

    def _load_operations(self, work_order_id: str, job_id: str) -> List[OperationTracker]:
        """Load operations from work order definition."""
        # In production, this would query the MES/ERP system
        # For now, generate sample operations
        operations = []

        # Typical LEGO brick manufacturing sequence
        ops_data = [
            ('print', 'Print brick', 'formlabs_sla'),
            ('cure', 'UV curing', 'formlabs_sla'),
            ('wash', 'IPA wash', 'formlabs_sla'),
            ('inspect_dim', 'Dimensional inspection', 'vision_station'),
            ('inspect_surface', 'Surface inspection', 'vision_station'),
            ('package', 'Package part', 'ned2'),
        ]

        for i, (op_type, op_name, equipment) in enumerate(ops_data):
            op = OperationTracker(
                operation_id=f'{work_order_id}-{op_type}-{i+1:03d}',
                operation_name=op_name,
                equipment_id=equipment,
            )
            operations.append(op)

        return operations

    async def _execute_operation(
        self,
        operation: OperationTracker,
        execution: WorkOrderExecution,
        feedback,
        goal_handle: ServerGoalHandle
    ) -> bool:
        """Execute single operation with progress updates."""
        # Simulate operation with progress
        duration = 5.0  # Would come from operation parameters
        steps = 20
        step_time = duration / steps

        for step in range(steps):
            if execution.is_cancelled:
                return False

            operation.progress_percent = (step + 1) / steps * 100.0

            # Update feedback
            self._update_feedback(feedback, execution, operation)
            goal_handle.publish_feedback(feedback)

            await self._async_sleep(step_time)

        # Simulate material consumption
        operation.material_consumed_kg = 0.005  # 5 grams per brick
        operation.energy_consumed_kwh = 0.1

        return True

    async def _check_quality(self, operation: OperationTracker) -> bool:
        """Check quality after operation completion."""
        # In production, would call quality inspection service
        # Simulate 95% pass rate
        import random
        return random.random() < 0.95

    def _update_feedback(
        self,
        feedback,
        execution: WorkOrderExecution,
        current_op: OperationTracker
    ):
        """Update feedback message."""
        feedback.current_operation_id = current_op.operation_id
        feedback.current_operation_name = current_op.operation_name
        feedback.operation_index = execution.current_operation_index
        feedback.total_operations = len(execution.operations)

        # Progress
        completed_progress = sum(
            100.0 for op in execution.operations[:execution.current_operation_index]
            if op.state == OperationState.COMPLETED
        )
        current_progress = current_op.progress_percent
        total_ops = len(execution.operations)

        feedback.overall_progress = (completed_progress + current_progress) / total_ops if total_ops > 0 else 0.0
        feedback.operation_progress = current_op.progress_percent
        feedback.parts_completed = execution.parts_produced

        # Equipment
        feedback.current_equipment_id = current_op.equipment_id
        feedback.equipment_status = current_op.state.name

        # Timing
        feedback.elapsed_time_sec = time.time() - execution.start_time
        remaining_ops = total_ops - execution.current_operation_index - 1
        feedback.estimated_remaining_sec = remaining_ops * 5.0  # Estimate 5s per op

        # Status
        if execution.on_quality_hold:
            feedback.status_message = "On quality hold - awaiting resolution"
            feedback.quality_hold = True
        elif execution.waiting_for_resource:
            feedback.status_message = execution.waiting_reason
            feedback.waiting_for_resource = True
            feedback.waiting_reason = execution.waiting_reason
        else:
            feedback.status_message = f"Executing {current_op.operation_name}"
            feedback.quality_hold = False
            feedback.waiting_for_resource = False

    def _is_equipment_available(self, equipment_id: str) -> bool:
        """Check if equipment is available."""
        return self._equipment_available.get(equipment_id, True)  # Default available

    def _on_equipment_registry(self, msg: String):
        """Handle equipment registry updates."""
        try:
            data = json.loads(msg.data)
            for eq in data.get('equipment', []):
                eq_id = eq.get('equipment_id', '')
                status = eq.get('status', 'OFFLINE')
                self._equipment_available[eq_id] = (status == 'ONLINE')
        except json.JSONDecodeError:
            pass

    def _on_quality_event(self, msg):
        """Handle quality events - can release quality holds."""
        # Would check for RELEASE_HOLD events
        pass

    def _get_active_work_orders(self, request, response):
        """Get active work order executions."""
        with self._lock:
            active = []
            for wo_id, execution in self._executions.items():
                active.append({
                    'work_order_id': wo_id,
                    'job_id': execution.job_id,
                    'progress': (execution.current_operation_index /
                                len(execution.operations) * 100
                                if execution.operations else 0),
                    'parts_produced': execution.parts_produced,
                })

        response.success = True
        response.message = json.dumps({
            'active_count': len(active),
            'work_orders': active,
        })
        return response

    def _publish_event(self, event_type: str, data: dict):
        """Publish work order event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data,
        }
        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)

    async def _async_sleep(self, duration: float):
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(duration)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = WorkOrderExecutorNode()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
