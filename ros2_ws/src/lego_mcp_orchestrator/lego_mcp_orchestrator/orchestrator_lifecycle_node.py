#!/usr/bin/env python3
"""
LEGO MCP Orchestrator Lifecycle Node
Main coordination node with ROS2 Lifecycle management for deterministic startup/shutdown.

States: unconfigured → inactive → active → finalized

LEGO MCP Manufacturing System v7.0 - Industry 4.0/5.0 Architecture
"""

import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import rclpy
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Bool

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
    PRINT_FDM = 'print_fdm'
    PRINT_SLA = 'print_sla'
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


class OrchestratorLifecycleNode(LifecycleNode):
    """
    Lifecycle-managed orchestration node.

    Lifecycle States:
        - unconfigured: Node created, no resources allocated
        - inactive: Resources allocated but not processing
        - active: Fully operational, dispatching jobs
        - finalized: Cleaned up, ready for destruction

    Transitions:
        - configure: Allocate resources, connect to equipment
        - activate: Start processing jobs
        - deactivate: Stop processing, graceful shutdown
        - cleanup: Release resources
        - shutdown: Destroy node
    """

    def __init__(self, node_name: str = 'lego_mcp_orchestrator'):
        super().__init__(node_name)

        # State tracking (allocated in on_configure)
        self._work_orders: Dict[str, WorkOrder] = {}
        self._operations: Dict[str, Operation] = {}
        self._active_operations: Dict[str, Operation] = {}
        self._equipment_status: Dict[str, Dict] = {}
        self._equipment_available: Dict[str, bool] = {}

        # Clients (created in on_configure)
        self._bambu_client: Optional[ActionClient] = None
        self._ned2_client: Optional[ActionClient] = None
        self._xarm_client: Optional[ActionClient] = None
        self._cnc_client: Optional[ActionClient] = None
        self._laser_client: Optional[ActionClient] = None

        # Timers (created in on_activate)
        self._heartbeat_timer = None
        self._dispatch_timer = None

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        self.get_logger().info("Orchestrator lifecycle node created (unconfigured)")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        """
        Configure callback - allocate resources.

        Called when transitioning from unconfigured to inactive.
        Creates action clients, services, publishers, subscribers.
        """
        self.get_logger().info("Configuring orchestrator...")

        try:
            # Initialize state tracking
            self._work_orders = {}
            self._operations = {}
            self._active_operations = {}
            self._equipment_status = {}
            self._equipment_available = {
                'ned2': False,
                'xarm': False,
                'bambu': False,  # Bambu Lab A1
                'cnc': False,
                'laser': False,
            }

            # Declare parameters
            self.declare_parameter('equipment_config', '')
            self.declare_parameter('auto_start_dispatch', True)
            self.declare_parameter('heartbeat_rate_hz', 10.0)
            self.declare_parameter('dispatch_rate_hz', 1.0)

            # Create action clients
            if MSGS_AVAILABLE:
                self._bambu_client = ActionClient(
                    self, PrintBrick, '/bambu/print',
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

            # Create services
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

            # Create publishers
            self._status_pub = self.create_publisher(String, '~/status', 10)
            self._job_complete_pub = self.create_publisher(
                String, '/lego_mcp/job_complete', 10
            )
            self._heartbeat_pub = self.create_publisher(
                Bool, '/safety/heartbeat', 10
            )
            self._lifecycle_state_pub = self.create_publisher(
                String, '~/lifecycle_state', 10
            )

            # Create subscribers
            for equipment in ['ned2', 'xarm', 'bambu', 'cnc', 'laser']:
                self.create_subscription(
                    EquipmentStatus if MSGS_AVAILABLE else String,
                    f'/{equipment}/status',
                    lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                    10
                )

            self.create_subscription(
                Bool, '/safety/estop_status', self._on_estop, 10
            )

            if MSGS_AVAILABLE:
                self.create_subscription(
                    QualityEvent, '/quality/events',
                    self._on_quality_event, 10,
                    callback_group=self._cb_group
                )
                self.create_subscription(
                    FailureEvent, '/manufacturing/failures',
                    self._on_failure_event, 10,
                    callback_group=self._cb_group
                )

            self._publish_lifecycle_state("inactive")
            self.get_logger().info("Orchestrator configured successfully")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Configuration failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        """
        Activate callback - start processing.

        Called when transitioning from inactive to active.
        Starts heartbeat and dispatch timers, begins job processing.
        """
        self.get_logger().info("Activating orchestrator...")

        try:
            # Wait for equipment to be available
            if not self._wait_for_equipment(timeout=10.0):
                self.get_logger().warn(
                    "Not all equipment available, continuing anyway"
                )

            # Start heartbeat timer
            heartbeat_rate = self.get_parameter('heartbeat_rate_hz').value
            self._heartbeat_timer = self.create_timer(
                1.0 / heartbeat_rate, self._send_heartbeat
            )

            # Start dispatch timer
            dispatch_rate = self.get_parameter('dispatch_rate_hz').value
            self._dispatch_timer = self.create_timer(
                1.0 / dispatch_rate,
                self._dispatch_pending_operations,
                callback_group=self._cb_group
            )

            self._publish_lifecycle_state("active")
            self.get_logger().info("Orchestrator activated - now dispatching jobs")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Activation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        """
        Deactivate callback - stop processing gracefully.

        Called when transitioning from active to inactive.
        Stops timers, waits for active operations to complete.
        """
        self.get_logger().info("Deactivating orchestrator...")

        try:
            # Stop dispatch timer
            if self._dispatch_timer:
                self.destroy_timer(self._dispatch_timer)
                self._dispatch_timer = None

            # Stop heartbeat timer
            if self._heartbeat_timer:
                self.destroy_timer(self._heartbeat_timer)
                self._heartbeat_timer = None

            # Wait for active operations to complete (with timeout)
            if self._active_operations:
                self.get_logger().info(
                    f"Waiting for {len(self._active_operations)} operations to complete..."
                )
                # In production, implement proper graceful shutdown
                # For now, just mark them as cancelled
                for op_id, op in self._active_operations.items():
                    op.status = OperationStatus.CANCELLED
                    self.get_logger().warn(f"Cancelled operation: {op_id}")
                self._active_operations.clear()

            self._publish_lifecycle_state("inactive")
            self.get_logger().info("Orchestrator deactivated")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Deactivation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        """
        Cleanup callback - release resources.

        Called when transitioning from inactive to unconfigured.
        Releases action clients and clears state.
        """
        self.get_logger().info("Cleaning up orchestrator...")

        try:
            # Clear action clients
            self._bambu_client = None
            self._ned2_client = None
            self._xarm_client = None
            self._cnc_client = None
            self._laser_client = None

            # Clear state
            self._work_orders.clear()
            self._operations.clear()
            self._active_operations.clear()
            self._equipment_status.clear()
            self._equipment_available.clear()

            self._publish_lifecycle_state("unconfigured")
            self.get_logger().info("Orchestrator cleaned up")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            self.get_logger().error(f"Cleanup failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        """
        Shutdown callback - final cleanup before destruction.

        Called when transitioning to finalized state.
        """
        self.get_logger().info("Shutting down orchestrator...")
        self._publish_lifecycle_state("finalized")
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state: State) -> TransitionCallbackReturn:
        """
        Error callback - handle errors and attempt recovery.

        Called when an error occurs during transitions.
        Returns SUCCESS to allow recovery, FAILURE to trigger shutdown.
        """
        self.get_logger().error(f"Orchestrator error in state: {state.label}")
        self._publish_lifecycle_state("error")

        # Attempt recovery by cleaning up and going to unconfigured
        try:
            if self._heartbeat_timer:
                self.destroy_timer(self._heartbeat_timer)
            if self._dispatch_timer:
                self.destroy_timer(self._dispatch_timer)

            self._active_operations.clear()
            return TransitionCallbackReturn.SUCCESS  # Allow recovery

        except Exception:
            return TransitionCallbackReturn.FAILURE  # Force shutdown

    def _wait_for_equipment(self, timeout: float) -> bool:
        """Wait for equipment to become available."""
        # In a real implementation, wait for action servers
        # For now, check if any equipment is available
        return any(self._equipment_available.values())

    def _publish_lifecycle_state(self, state: str):
        """Publish current lifecycle state."""
        msg = String()
        msg.data = state
        self._lifecycle_state_pub.publish(msg)

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
            self._equipment_available[equipment_id] = (
                msg.connected and
                msg.state == 1 and  # Idle
                not msg.estop_active
            )

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().error("E-STOP ACTIVATED - Stopping all operations")
            for eq in self._equipment_available:
                self._equipment_available[eq] = False

    def _on_quality_event(self, msg):
        """Handle quality events from vision system."""
        self.get_logger().info(f"Quality event: {msg.event_type}")

    def _on_failure_event(self, msg):
        """Handle failure events."""
        self.get_logger().error(f"Failure: {msg.failure_type_name}")

    async def _schedule_job_callback(self, request, response):
        """Handle schedule job service request."""
        self.get_logger().info(f"Scheduling job: {request.work_order_id}")

        work_order = self._work_orders.get(request.work_order_id)
        if not work_order:
            response.success = False
            response.message = "Work order not found"
            return response

        available = [eq for eq, avail in self._equipment_available.items() if avail]

        for op in work_order.operations:
            if op.status != OperationStatus.PENDING:
                continue
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
        self.get_logger().info(f"Creating WO: {request.part_id} x {request.quantity}")

        work_order_id = f"WO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        operations = self._generate_operations(
            work_order_id, request.part_id, request.quantity
        )

        work_order = WorkOrder(
            work_order_id=work_order_id,
            part_id=request.part_id,
            quantity=request.quantity,
            priority=request.priority,
            operations=operations,
        )
        self._work_orders[work_order_id] = work_order

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
        self, work_order_id: str, part_id: str, quantity: int
    ) -> List[Operation]:
        """Generate operations for a part."""
        operations = []
        op_count = 0

        for i in range(quantity):
            # Print operation (FDM for Bambu Lab)
            op_count += 1
            print_op = Operation(
                operation_id=f"{work_order_id}-OP{op_count:03d}",
                work_order_id=work_order_id,
                operation_type=OperationType.PRINT_FDM,
                parameters={'part_id': part_id, 'instance': i + 1},
            )
            operations.append(print_op)

            # Inspect operation
            op_count += 1
            inspect_op = Operation(
                operation_id=f"{work_order_id}-OP{op_count:03d}",
                work_order_id=work_order_id,
                operation_type=OperationType.INSPECT,
                parameters={'part_id': part_id, 'instance': i + 1},
                dependencies=[print_op.operation_id],
            )
            operations.append(inspect_op)

        return operations

    def _match_equipment(
        self, operation_type: OperationType, available: List[str]
    ) -> Optional[str]:
        """Match operation type to available equipment."""
        equipment_map = {
            OperationType.PRINT_FDM: ['bambu'],
            OperationType.PRINT_SLA: ['sla_printer'],
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

            deps_met = all(
                self._operations.get(dep_id, Operation('', '', OperationType.INSPECT)).status == OperationStatus.COMPLETED
                for dep_id in op.dependencies
            )
            if not deps_met:
                continue

            if not self._equipment_available.get(op.equipment_id, False):
                continue

            self.get_logger().info(f"Dispatching {op.operation_id} to {op.equipment_id}")
            op.status = OperationStatus.IN_PROGRESS
            op.started_at = datetime.now()
            self._active_operations[op_id] = op
            self._equipment_available[op.equipment_id] = False

            asyncio.create_task(self._execute_operation(op))

    async def _execute_operation(self, op: Operation):
        """Execute a single operation."""
        try:
            if op.operation_type == OperationType.PRINT_FDM:
                await self._execute_print_fdm(op)
            elif op.operation_type in [OperationType.CNC_MILL, OperationType.LASER_CUT]:
                await self._execute_machine_operation(op)
            elif op.operation_type == OperationType.ROBOT_ASSEMBLE:
                await self._execute_assembly(op)
            elif op.operation_type == OperationType.INSPECT:
                await self._execute_inspection(op)
            else:
                op.status = OperationStatus.FAILED
        except Exception as e:
            self.get_logger().error(f"Operation {op.operation_id} failed: {e}")
            op.status = OperationStatus.FAILED
            op.result = {'error': str(e)}
        finally:
            op.completed_at = datetime.now()
            self._equipment_available[op.equipment_id] = True
            if op.operation_id in self._active_operations:
                del self._active_operations[op.operation_id]

            msg = String()
            msg.data = f"{op.operation_id}:{op.status.value}"
            self._job_complete_pub.publish(msg)

    async def _execute_print_fdm(self, op: Operation):
        """Execute FDM print operation on Bambu Lab."""
        if not self._bambu_client or not self._bambu_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("Bambu action server not available")

        goal = PrintBrick.Goal()
        goal.brick_id = op.parameters.get('part_id', '')
        goal.printer_id = op.equipment_id

        goal_handle = await self._bambu_client.send_goal_async(goal)
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
        if not client or not client.wait_for_server(timeout_sec=5.0):
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

    async def _execute_assembly(self, op: Operation):
        """Execute robot assembly operation."""
        robot = op.equipment_id
        client = self._ned2_client if robot == 'ned2' else self._xarm_client
        if not client or not client.wait_for_server(timeout_sec=5.0):
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

    async def _execute_inspection(self, op: Operation):
        """Execute inspection operation."""
        await asyncio.sleep(0.5)
        op.status = OperationStatus.COMPLETED
        op.result = {'quality_score': 0.95, 'passed': True}


def main(args=None):
    rclpy.init(args=args)

    node = OrchestratorLifecycleNode()

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
