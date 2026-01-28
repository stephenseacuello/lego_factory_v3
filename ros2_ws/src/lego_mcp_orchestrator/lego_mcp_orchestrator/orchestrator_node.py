#!/usr/bin/env python3
"""
LEGO MCP Orchestrator Node
Main coordination node for factory cell operations.
Dispatches jobs to equipment, monitors progress, handles failures.

LEGO MCP Manufacturing System v7.0
"""

import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Bool
from geometry_msgs.msg import Pose

try:
    from lego_mcp_msgs.msg import (
        EquipmentStatus, PrintJob, AssemblyStep,
        QualityEvent, FailureEvent, TwinState
    )
    from lego_mcp_msgs.srv import (
        ScheduleJob, CreateWorkOrder, RescheduleRemaining
    )
    from lego_mcp_msgs.action import (
        PrintBrick, AssembleLego, MachineOperation
    )
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class OperationType(Enum):
    """Types of manufacturing operations."""
    PRINT_SLA = 'print_sla'
    PRINT_FDM = 'print_fdm'
    CNC_MILL = 'cnc_mill'
    LASER_CUT = 'laser_cut'
    LASER_ENGRAVE = 'laser_engrave'
    ROBOT_PICK = 'robot_pick'
    ROBOT_PLACE = 'robot_place'
    ROBOT_ASSEMBLE = 'robot_assemble'
    INSPECT = 'inspect'


class OperationStatus(Enum):
    """Status of an operation."""
    PENDING = 'pending'
    QUEUED = 'queued'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class Operation:
    """Single manufacturing operation."""
    operation_id: str
    work_order_id: str
    operation_type: OperationType
    equipment_id: str = ''
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: OperationStatus = OperationStatus.PENDING
    priority: int = 2
    dependencies: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkOrder:
    """Manufacturing work order."""
    work_order_id: str
    part_id: str
    quantity: int
    priority: int = 2
    operations: List[Operation] = field(default_factory=list)
    status: str = 'planned'
    created_at: datetime = field(default_factory=datetime.now)


class OrchestratorNode(Node):
    """
    Main orchestration node coordinating all equipment via ROS2 actions.
    """

    def __init__(self):
        super().__init__('lego_mcp_orchestrator')

        # Work order and operation tracking
        self._work_orders: Dict[str, WorkOrder] = {}
        self._operations: Dict[str, Operation] = {}
        self._active_operations: Dict[str, Operation] = {}

        # Equipment status tracking
        self._equipment_status: Dict[str, Dict] = {}
        self._equipment_available: Dict[str, bool] = {
            'ned2': True,
            'xarm': True,
            'formlabs': True,
            'cnc': True,
            'laser': True,
        }

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Action clients
        if MSGS_AVAILABLE:
            self._formlabs_client = ActionClient(
                self, PrintBrick, '/formlabs/print',
                callback_group=self._cb_group
            )
            self._ned2_client = ActionClient(
                self, AssembleLego, '/ned2/assemble',
                callback_group=self._cb_group
            )
            self._xarm_client = ActionClient(
                self, AssembleLego, '/xarm/assemble',
                callback_group=self._cb_group
            )
            self._cnc_client = ActionClient(
                self, MachineOperation, '/cnc/execute',
                callback_group=self._cb_group
            )
            self._laser_client = ActionClient(
                self, MachineOperation, '/laser/execute',
                callback_group=self._cb_group
            )

        # Services
        if MSGS_AVAILABLE:
            self._schedule_srv = self.create_service(
                ScheduleJob,
                '~/schedule_job',
                self._schedule_job_callback,
                callback_group=self._cb_group
            )

            self._create_wo_srv = self.create_service(
                CreateWorkOrder,
                '~/create_work_order',
                self._create_work_order_callback,
                callback_group=self._cb_group
            )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '~/status',
            10
        )

        self._job_complete_pub = self.create_publisher(
            String,
            '/lego_mcp/job_complete',
            10
        )

        # Subscribers - Equipment status
        for equipment in ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']:
            self.create_subscription(
                EquipmentStatus if MSGS_AVAILABLE else String,
                f'/{equipment}/status',
                lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                10
            )

        # E-stop subscriber
        self.create_subscription(
            Bool,
            '/safety/estop_status',
            self._on_estop,
            10
        )

        # Quality event subscriber
        if MSGS_AVAILABLE:
            self.create_subscription(
                QualityEvent,
                '/quality/events',
                self._on_quality_event,
                10,
                callback_group=self._cb_group
            )

        # Failure event subscriber
        if MSGS_AVAILABLE:
            self.create_subscription(
                FailureEvent,
                '/manufacturing/failures',
                self._on_failure_event,
                10,
                callback_group=self._cb_group
            )

        # Heartbeat timer for safety
        self._heartbeat_pub = self.create_publisher(
            Bool,
            '/safety/heartbeat',
            10
        )
        self._heartbeat_timer = self.create_timer(
            0.1,  # 10 Hz
            self._send_heartbeat
        )

        # Dispatch timer
        self._dispatch_timer = self.create_timer(
            1.0,
            self._dispatch_pending_operations,
            callback_group=self._cb_group
        )

        self.get_logger().info("Orchestrator node initialized")

    def _send_heartbeat(self):
        """Send heartbeat to safety system."""
        msg = Bool()
        msg.data = True
        self._heartbeat_pub.publish(msg)

    def _on_equipment_status(self, equipment_id: str, msg):
        """Handle equipment status update."""
        if MSGS_AVAILABLE and hasattr(msg, 'state'):
            self._equipment_status[equipment_id] = {
                'state': msg.state,
                'connected': msg.connected,
                'estop_active': msg.estop_active,
            }
            # Update availability
            self._equipment_available[equipment_id] = (
                msg.connected and
                msg.state == 1 and  # Idle
                not msg.estop_active
            )

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().error("E-STOP ACTIVATED - Stopping all operations")
            # Mark all equipment as unavailable
            for eq in self._equipment_available:
                self._equipment_available[eq] = False
            # Cancel active operations would happen here

    def _on_quality_event(self, msg):
        """Handle quality events from vision system."""
        self.get_logger().info(f"Quality event: {msg.event_type} - {msg.action_name}")

        if msg.action == 5:  # STOP
            self.get_logger().warn(f"Quality STOP for operation {msg.operation_id}")
            # Stop operation and trigger rescheduling

        elif msg.action == 6:  # REWORK
            self.get_logger().warn(f"Quality REWORK for {msg.work_order_id}")
            # Schedule rework operation

    def _on_failure_event(self, msg):
        """Handle failure events."""
        self.get_logger().error(f"Failure event: {msg.failure_type_name} on {msg.equipment_id}")
        # Recovery handling delegated to recovery_engine_node

    async def _schedule_job_callback(self, request, response):
        """Handle schedule job service request."""
        self.get_logger().info(f"Scheduling job for work order: {request.work_order_id}")

        # Find work order
        work_order = self._work_orders.get(request.work_order_id)
        if not work_order:
            response.success = False
            response.message = "Work order not found"
            return response

        # Get available equipment
        available = [eq for eq, avail in self._equipment_available.items() if avail]

        # Simple scheduling - assign operations to available equipment
        for op in work_order.operations:
            if op.status != OperationStatus.PENDING:
                continue

            # Match operation type to equipment
            equipment = self._match_equipment(op.operation_type, available)
            if equipment:
                op.equipment_id = equipment
                op.status = OperationStatus.QUEUED
                self._operations[op.operation_id] = op

        response.success = True
        response.message = "Job scheduled"
        response.schedule_id = f"SCH-{datetime.now().strftime('%H%M%S')}"

        return response

    async def _create_work_order_callback(self, request, response):
        """Handle create work order service request."""
        self.get_logger().info(f"Creating work order for {request.part_id} x {request.quantity}")

        work_order_id = f"WO-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create operations based on part requirements
        operations = self._generate_operations(
            work_order_id,
            request.part_id,
            request.quantity
        )

        work_order = WorkOrder(
            work_order_id=work_order_id,
            part_id=request.part_id,
            quantity=request.quantity,
            priority=request.priority,
            operations=operations,
        )

        self._work_orders[work_order_id] = work_order

        # Auto-schedule if requested
        if request.auto_schedule:
            schedule_request = ScheduleJob.Request()
            schedule_request.work_order_id = work_order_id
            await self._schedule_job_callback(schedule_request, ScheduleJob.Response())

        response.success = True
        response.message = "Work order created"
        response.work_order_id = work_order_id
        response.operation_ids = [op.operation_id for op in operations]

        return response

    def _generate_operations(
        self,
        work_order_id: str,
        part_id: str,
        quantity: int
    ) -> List[Operation]:
        """Generate operations for a part."""
        operations = []
        op_count = 0

        # For LEGO bricks, typical operations are:
        # 1. Print (SLA or FDM)
        # 2. Inspect
        # 3. (Optional) Assembly

        for i in range(quantity):
            # Print operation
            op_count += 1
            print_op = Operation(
                operation_id=f"{work_order_id}-OP{op_count:03d}",
                work_order_id=work_order_id,
                operation_type=OperationType.PRINT_SLA,
                parameters={
                    'part_id': part_id,
                    'instance': i + 1,
                },
            )
            operations.append(print_op)

            # Inspect operation
            op_count += 1
            inspect_op = Operation(
                operation_id=f"{work_order_id}-OP{op_count:03d}",
                work_order_id=work_order_id,
                operation_type=OperationType.INSPECT,
                parameters={
                    'part_id': part_id,
                    'instance': i + 1,
                },
                dependencies=[print_op.operation_id],
            )
            operations.append(inspect_op)

        return operations

    def _match_equipment(
        self,
        operation_type: OperationType,
        available: List[str]
    ) -> Optional[str]:
        """Match operation type to available equipment."""
        equipment_map = {
            OperationType.PRINT_SLA: ['formlabs'],
            OperationType.PRINT_FDM: ['coastrunner'],
            OperationType.CNC_MILL: ['cnc'],
            OperationType.LASER_CUT: ['laser'],
            OperationType.LASER_ENGRAVE: ['laser'],
            OperationType.ROBOT_PICK: ['ned2', 'xarm'],
            OperationType.ROBOT_PLACE: ['ned2', 'xarm'],
            OperationType.ROBOT_ASSEMBLE: ['ned2', 'xarm'],
            OperationType.INSPECT: ['vision'],
        }

        candidates = equipment_map.get(operation_type, [])
        for eq in candidates:
            if eq in available:
                return eq

        return None

    def _dispatch_pending_operations(self):
        """Dispatch pending operations to equipment."""
        for op_id, op in list(self._operations.items()):
            if op.status != OperationStatus.QUEUED:
                continue

            # Check dependencies
            deps_met = all(
                self._operations.get(dep_id, Operation('', '', OperationType.INSPECT)).status == OperationStatus.COMPLETED
                for dep_id in op.dependencies
            )

            if not deps_met:
                continue

            # Check equipment availability
            if not self._equipment_available.get(op.equipment_id, False):
                continue

            # Dispatch operation
            self.get_logger().info(f"Dispatching {op.operation_id} to {op.equipment_id}")
            op.status = OperationStatus.IN_PROGRESS
            op.started_at = datetime.now()
            self._active_operations[op_id] = op

            # Mark equipment as busy
            self._equipment_available[op.equipment_id] = False

            # Start async execution
            asyncio.create_task(self._execute_operation(op))

    async def _execute_operation(self, op: Operation):
        """Execute a single operation."""
        try:
            if op.operation_type == OperationType.PRINT_SLA:
                await self._execute_print_sla(op)
            elif op.operation_type in [OperationType.CNC_MILL, OperationType.LASER_CUT]:
                await self._execute_machine_operation(op)
            elif op.operation_type == OperationType.ROBOT_ASSEMBLE:
                await self._execute_assembly(op)
            elif op.operation_type == OperationType.INSPECT:
                await self._execute_inspection(op)
            else:
                self.get_logger().warn(f"Unknown operation type: {op.operation_type}")
                op.status = OperationStatus.FAILED

        except Exception as e:
            self.get_logger().error(f"Operation {op.operation_id} failed: {e}")
            op.status = OperationStatus.FAILED
            op.result = {'error': str(e)}

        finally:
            op.completed_at = datetime.now()
            self._equipment_available[op.equipment_id] = True
            del self._active_operations[op.operation_id]

            # Publish completion
            msg = String()
            msg.data = f"{op.operation_id}:{op.status.value}"
            self._job_complete_pub.publish(msg)

    async def _execute_print_sla(self, op: Operation):
        """Execute SLA print operation."""
        if not self._formlabs_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("Formlabs action server not available")

        goal = PrintBrick.Goal()
        goal.brick_id = op.parameters.get('part_id', '')
        goal.printer_id = op.equipment_id

        goal_handle = await self._formlabs_client.send_goal_async(goal)
        if not goal_handle.accepted:
            raise RuntimeError("Print goal rejected")

        result = await goal_handle.get_result_async()
        if result.result.success:
            op.status = OperationStatus.COMPLETED
            op.result = {'message': result.result.message}
        else:
            op.status = OperationStatus.FAILED
            op.result = {'error': result.result.message}

    async def _execute_machine_operation(self, op: Operation):
        """Execute CNC/Laser operation."""
        client = self._cnc_client if 'cnc' in op.equipment_id else self._laser_client

        if not client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("Machine action server not available")

        goal = MachineOperation.Goal()
        goal.operation_id = op.operation_id
        goal.machine_id = op.equipment_id
        goal.gcode = op.parameters.get('gcode', '')

        goal_handle = await client.send_goal_async(goal)
        if not goal_handle.accepted:
            raise RuntimeError("Machine goal rejected")

        result = await goal_handle.get_result_async()
        if result.result.success:
            op.status = OperationStatus.COMPLETED
        else:
            op.status = OperationStatus.FAILED
            op.result = {'error': result.result.message}

    async def _execute_assembly(self, op: Operation):
        """Execute robot assembly operation."""
        robot = op.equipment_id
        client = self._ned2_client if robot == 'ned2' else self._xarm_client

        if not client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("Robot action server not available")

        goal = AssembleLego.Goal()
        goal.assembly_id = op.parameters.get('assembly_id', '')
        goal.robot_id = robot

        goal_handle = await client.send_goal_async(goal)
        if not goal_handle.accepted:
            raise RuntimeError("Assembly goal rejected")

        result = await goal_handle.get_result_async()
        if result.result.success:
            op.status = OperationStatus.COMPLETED
        else:
            op.status = OperationStatus.FAILED
            op.result = {'error': result.result.message}

    async def _execute_inspection(self, op: Operation):
        """Execute inspection operation (via vision system)."""
        # Vision system inspection - would call vision node
        # For now, simulate success
        await asyncio.sleep(0.5)
        op.status = OperationStatus.COMPLETED
        op.result = {'quality_score': 0.95, 'passed': True}


def main(args=None):
    rclpy.init(args=args)

    node = OrchestratorNode()

    executor = MultiThreadedExecutor()
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
