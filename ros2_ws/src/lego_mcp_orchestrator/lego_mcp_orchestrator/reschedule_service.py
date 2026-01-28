#!/usr/bin/env python3
"""
LEGO MCP Dynamic Reschedule Service

Provides ROS2 service for dynamic rescheduling after equipment failures.
Integrates with CP-SAT scheduler for optimal reassignment.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from std_srvs.srv import Trigger

# Try to import custom messages
try:
    from lego_mcp_msgs.srv import RescheduleRemaining
    from lego_mcp_msgs.msg import WorkOrder, ScheduleUpdate
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class RescheduleReason(Enum):
    """Reasons for rescheduling."""
    EQUIPMENT_FAILURE = 'equipment_failure'
    QUALITY_REJECT = 'quality_reject'
    PRIORITY_CHANGE = 'priority_change'
    RESOURCE_UNAVAILABLE = 'resource_unavailable'
    MANUAL_REQUEST = 'manual_request'


class SchedulingStrategy(Enum):
    """Available scheduling strategies."""
    CPSAT_OPTIMAL = 'cpsat_optimal'  # Full CP-SAT optimization
    PRIORITY_DISPATCH = 'priority_dispatch'  # Fast heuristic
    EARLIEST_DUE = 'earliest_due'  # Simple due date ordering
    SHORTEST_FIRST = 'shortest_first'  # Shortest job first


@dataclass
class Operation:
    """Manufacturing operation."""
    operation_id: str
    work_order_id: str
    operation_type: str
    equipment_types: List[str]  # Compatible equipment types
    assigned_equipment: Optional[str] = None
    duration_minutes: float = 0.0
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)
    status: str = 'pending'
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Equipment:
    """Equipment resource."""
    equipment_id: str
    equipment_type: str
    available: bool = True
    current_operation: Optional[str] = None
    available_at: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)


@dataclass
class RescheduleResult:
    """Result of rescheduling operation."""
    success: bool
    new_assignments: Dict[str, str]  # operation_id -> equipment_id
    operations_affected: int
    estimated_delay_minutes: float
    strategy_used: SchedulingStrategy
    message: str


class RescheduleServiceNode(Node):
    """
    ROS2 service for dynamic rescheduling after failures.

    Features:
    - Multiple scheduling strategies (CP-SAT, heuristics)
    - Equipment failure handling with reassignment
    - Work order priority management
    - Real-time schedule updates
    """

    def __init__(self):
        super().__init__('reschedule_service')

        # Parameters
        self.declare_parameter('default_strategy', 'priority_dispatch')
        self.declare_parameter('cpsat_timeout_seconds', 30)
        self.declare_parameter('max_operations_for_cpsat', 50)

        self._default_strategy = SchedulingStrategy(
            self.get_parameter('default_strategy').value
        )
        self._cpsat_timeout = self.get_parameter('cpsat_timeout_seconds').value
        self._max_cpsat_ops = self.get_parameter('max_operations_for_cpsat').value

        # State
        self._pending_operations: Dict[str, Operation] = {}
        self._active_operations: Dict[str, Operation] = {}
        self._equipment: Dict[str, Equipment] = {}
        self._schedule: List[str] = []  # Ordered operation IDs

        # Initialize equipment registry
        self._init_equipment()

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Services
        if MSGS_AVAILABLE:
            self._reschedule_srv = self.create_service(
                RescheduleRemaining,
                '/scheduling/reschedule_remaining',
                self._reschedule_callback,
                callback_group=self._cb_group
            )
        else:
            # Fallback using String-based service
            self._reschedule_string_sub = self.create_subscription(
                String,
                '/scheduling/reschedule_request',
                self._on_reschedule_request,
                10
            )

        # Standard trigger service for quick reschedule
        self._quick_reschedule_srv = self.create_service(
            Trigger,
            '/scheduling/reschedule_now',
            self._quick_reschedule_callback,
            callback_group=self._cb_group
        )

        # Subscribers
        self.create_subscription(
            String,
            '/manufacturing/operations',
            self._on_operations_update,
            10
        )

        self.create_subscription(
            String,
            '/manufacturing/failures',
            self._on_failure_event,
            10,
            callback_group=self._cb_group
        )

        self.create_subscription(
            String,
            '/equipment/status',
            self._on_equipment_status,
            10
        )

        # Publishers
        self._schedule_pub = self.create_publisher(
            String,
            '/scheduling/schedule_update',
            10
        )

        self._status_pub = self.create_publisher(
            String,
            '/scheduling/reschedule_status',
            10
        )

        self.get_logger().info("Reschedule service initialized")

    def _init_equipment(self):
        """Initialize equipment registry."""
        # Default equipment configuration
        default_equipment = [
            Equipment('ned2', 'robot_arm', capabilities=['assembly', 'pick_place']),
            Equipment('xarm', 'robot_arm', capabilities=['assembly', 'pick_place']),
            Equipment('formlabs', 'sla_printer', capabilities=['print_sla']),
            Equipment('cnc', 'cnc_machine', capabilities=['mill', 'drill', 'cut']),
            Equipment('laser', 'laser_engraver', capabilities=['engrave', 'cut_thin']),
        ]

        for eq in default_equipment:
            self._equipment[eq.equipment_id] = eq

    def _reschedule_callback(self, request, response):
        """Handle reschedule service request."""
        work_order_id = request.work_order_id if hasattr(request, 'work_order_id') else None
        failed_equipment = request.failed_equipment_id if hasattr(request, 'failed_equipment_id') else None
        urgent = request.urgent if hasattr(request, 'urgent') else False

        result = self._perform_reschedule(
            work_order_id=work_order_id,
            exclude_equipment=failed_equipment,
            urgent=urgent
        )

        response.success = result.success
        response.message = result.message
        response.operations_affected = result.operations_affected

        return response

    def _quick_reschedule_callback(self, request, response):
        """Handle quick reschedule trigger."""
        result = self._perform_reschedule(urgent=True)
        response.success = result.success
        response.message = result.message
        return response

    def _on_reschedule_request(self, msg: String):
        """Handle reschedule request via topic (fallback)."""
        try:
            data = json.loads(msg.data)
            result = self._perform_reschedule(
                work_order_id=data.get('work_order_id'),
                exclude_equipment=data.get('failed_equipment_id'),
                urgent=data.get('urgent', False),
                reason=RescheduleReason(data.get('reason', 'manual_request'))
            )

            # Publish result
            self._publish_result(result)

        except Exception as e:
            self.get_logger().error(f"Reschedule request failed: {e}")

    def _perform_reschedule(
        self,
        work_order_id: Optional[str] = None,
        exclude_equipment: Optional[str] = None,
        urgent: bool = False,
        reason: RescheduleReason = RescheduleReason.MANUAL_REQUEST
    ) -> RescheduleResult:
        """Perform rescheduling operation."""
        self.get_logger().info(
            f"Rescheduling: work_order={work_order_id}, "
            f"exclude={exclude_equipment}, urgent={urgent}"
        )

        # Get operations to reschedule
        operations = self._get_operations_to_reschedule(work_order_id, exclude_equipment)

        if not operations:
            return RescheduleResult(
                success=True,
                new_assignments={},
                operations_affected=0,
                estimated_delay_minutes=0,
                strategy_used=self._default_strategy,
                message="No operations to reschedule"
            )

        # Get available equipment
        available_equipment = self._get_available_equipment(exclude_equipment)

        # Choose strategy
        if urgent or len(operations) > self._max_cpsat_ops:
            strategy = SchedulingStrategy.PRIORITY_DISPATCH
        else:
            strategy = self._default_strategy

        # Perform scheduling
        try:
            if strategy == SchedulingStrategy.CPSAT_OPTIMAL:
                assignments = self._schedule_cpsat(operations, available_equipment)
            elif strategy == SchedulingStrategy.PRIORITY_DISPATCH:
                assignments = self._schedule_priority_dispatch(operations, available_equipment)
            elif strategy == SchedulingStrategy.EARLIEST_DUE:
                assignments = self._schedule_earliest_due(operations, available_equipment)
            else:
                assignments = self._schedule_shortest_first(operations, available_equipment)

            # Apply assignments
            for op_id, eq_id in assignments.items():
                if op_id in self._pending_operations:
                    self._pending_operations[op_id].assigned_equipment = eq_id

            # Publish schedule update
            self._publish_schedule_update(assignments, reason)

            return RescheduleResult(
                success=True,
                new_assignments=assignments,
                operations_affected=len(assignments),
                estimated_delay_minutes=self._estimate_delay(operations, assignments),
                strategy_used=strategy,
                message=f"Rescheduled {len(assignments)} operations using {strategy.value}"
            )

        except Exception as e:
            self.get_logger().error(f"Scheduling failed: {e}")
            return RescheduleResult(
                success=False,
                new_assignments={},
                operations_affected=0,
                estimated_delay_minutes=0,
                strategy_used=strategy,
                message=f"Scheduling failed: {str(e)}"
            )

    def _get_operations_to_reschedule(
        self,
        work_order_id: Optional[str],
        exclude_equipment: Optional[str]
    ) -> List[Operation]:
        """Get list of operations that need rescheduling."""
        operations = []

        for op in self._pending_operations.values():
            # Filter by work order if specified
            if work_order_id and op.work_order_id != work_order_id:
                continue

            # Include if currently assigned to excluded equipment
            if exclude_equipment and op.assigned_equipment == exclude_equipment:
                operations.append(op)
            # Or if not yet assigned
            elif not op.assigned_equipment:
                operations.append(op)

        return operations

    def _get_available_equipment(self, exclude: Optional[str] = None) -> List[Equipment]:
        """Get list of available equipment."""
        available = []

        for eq in self._equipment.values():
            if exclude and eq.equipment_id == exclude:
                continue
            if eq.available:
                available.append(eq)

        return available

    def _schedule_cpsat(
        self,
        operations: List[Operation],
        equipment: List[Equipment]
    ) -> Dict[str, str]:
        """Schedule using CP-SAT optimization."""
        # Try to use ortools if available
        try:
            from ortools.sat.python import cp_model

            model = cp_model.CpModel()

            # Decision variables: operation i assigned to equipment j
            assignments = {}
            for op in operations:
                for eq in equipment:
                    if self._is_compatible(op, eq):
                        var_name = f"op_{op.operation_id}_eq_{eq.equipment_id}"
                        assignments[(op.operation_id, eq.equipment_id)] = model.NewBoolVar(var_name)

            # Constraint: each operation assigned to exactly one equipment
            for op in operations:
                compatible_eqs = [
                    assignments[(op.operation_id, eq.equipment_id)]
                    for eq in equipment
                    if (op.operation_id, eq.equipment_id) in assignments
                ]
                if compatible_eqs:
                    model.Add(sum(compatible_eqs) == 1)

            # Objective: minimize makespan (simplified - just count)
            # In production, would minimize total completion time

            # Solve
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = self._cpsat_timeout
            status = solver.Solve(model)

            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                result = {}
                for (op_id, eq_id), var in assignments.items():
                    if solver.Value(var):
                        result[op_id] = eq_id
                return result
            else:
                # Fall back to heuristic
                return self._schedule_priority_dispatch(operations, equipment)

        except ImportError:
            self.get_logger().warn("ortools not available, using heuristic")
            return self._schedule_priority_dispatch(operations, equipment)

    def _schedule_priority_dispatch(
        self,
        operations: List[Operation],
        equipment: List[Equipment]
    ) -> Dict[str, str]:
        """Fast priority-based dispatch scheduling."""
        # Sort operations by priority (highest first)
        sorted_ops = sorted(operations, key=lambda x: (-x.priority, x.duration_minutes))

        # Track equipment availability times
        eq_available: Dict[str, datetime] = {
            eq.equipment_id: eq.available_at or datetime.now()
            for eq in equipment
        }

        assignments = {}

        for op in sorted_ops:
            # Find compatible equipment with earliest availability
            best_eq = None
            best_time = None

            for eq in equipment:
                if not self._is_compatible(op, eq):
                    continue

                avail_time = eq_available.get(eq.equipment_id, datetime.now())
                if best_time is None or avail_time < best_time:
                    best_time = avail_time
                    best_eq = eq

            if best_eq:
                assignments[op.operation_id] = best_eq.equipment_id
                # Update availability
                eq_available[best_eq.equipment_id] = (
                    best_time + timedelta(minutes=op.duration_minutes)
                )

        return assignments

    def _schedule_earliest_due(
        self,
        operations: List[Operation],
        equipment: List[Equipment]
    ) -> Dict[str, str]:
        """Schedule by earliest due date."""
        # For simplicity, use same as priority dispatch
        # In production, would consider actual due dates
        return self._schedule_priority_dispatch(operations, equipment)

    def _schedule_shortest_first(
        self,
        operations: List[Operation],
        equipment: List[Equipment]
    ) -> Dict[str, str]:
        """Schedule shortest operations first."""
        sorted_ops = sorted(operations, key=lambda x: x.duration_minutes)

        eq_available: Dict[str, datetime] = {
            eq.equipment_id: eq.available_at or datetime.now()
            for eq in equipment
        }

        assignments = {}

        for op in sorted_ops:
            best_eq = None
            best_time = None

            for eq in equipment:
                if not self._is_compatible(op, eq):
                    continue

                avail_time = eq_available.get(eq.equipment_id, datetime.now())
                if best_time is None or avail_time < best_time:
                    best_time = avail_time
                    best_eq = eq

            if best_eq:
                assignments[op.operation_id] = best_eq.equipment_id
                eq_available[best_eq.equipment_id] = (
                    best_time + timedelta(minutes=op.duration_minutes)
                )

        return assignments

    def _is_compatible(self, operation: Operation, equipment: Equipment) -> bool:
        """Check if operation can run on equipment."""
        # Check if equipment type is in operation's compatible types
        if operation.equipment_types and equipment.equipment_type not in operation.equipment_types:
            return False

        # Check capabilities
        if operation.operation_type in equipment.capabilities:
            return True

        # Generic compatibility rules
        compatibility_map = {
            'print_sla': ['sla_printer'],
            'print_fdm': ['fdm_printer'],
            'assembly': ['robot_arm'],
            'pick_place': ['robot_arm'],
            'mill': ['cnc_machine'],
            'engrave': ['laser_engraver', 'cnc_machine'],
        }

        compatible_types = compatibility_map.get(operation.operation_type, [])
        return equipment.equipment_type in compatible_types

    def _estimate_delay(
        self,
        operations: List[Operation],
        assignments: Dict[str, str]
    ) -> float:
        """Estimate delay caused by rescheduling."""
        # Simple estimate: sum of operation durations for reassigned ops
        total_delay = 0.0

        for op in operations:
            if op.operation_id in assignments:
                # Add setup time estimate
                total_delay += 5.0  # 5 min setup per reassignment
                # If assigned to different equipment type, add more
                if op.assigned_equipment and op.assigned_equipment != assignments[op.operation_id]:
                    total_delay += 10.0  # 10 min equipment switch penalty

        return total_delay

    def _on_operations_update(self, msg: String):
        """Handle operations update."""
        try:
            data = json.loads(msg.data)
            for op_data in data.get('operations', []):
                op = Operation(
                    operation_id=op_data['operation_id'],
                    work_order_id=op_data['work_order_id'],
                    operation_type=op_data['operation_type'],
                    equipment_types=op_data.get('equipment_types', []),
                    duration_minutes=op_data.get('duration_minutes', 30),
                    priority=op_data.get('priority', 1),
                    status=op_data.get('status', 'pending'),
                )

                if op.status == 'pending':
                    self._pending_operations[op.operation_id] = op
                elif op.status == 'active':
                    self._active_operations[op.operation_id] = op
                    self._pending_operations.pop(op.operation_id, None)

        except Exception as e:
            self.get_logger().error(f"Operations update failed: {e}")

    def _on_failure_event(self, msg: String):
        """Handle equipment failure event."""
        try:
            data = json.loads(msg.data)
            failed_equipment = data.get('equipment_id')

            if failed_equipment:
                # Mark equipment as unavailable
                if failed_equipment in self._equipment:
                    self._equipment[failed_equipment].available = False

                # Trigger reschedule
                self.get_logger().warn(f"Equipment failure: {failed_equipment}, triggering reschedule")

                result = self._perform_reschedule(
                    exclude_equipment=failed_equipment,
                    urgent=True,
                    reason=RescheduleReason.EQUIPMENT_FAILURE
                )

                self._publish_result(result)

        except Exception as e:
            self.get_logger().error(f"Failure event handling failed: {e}")

    def _on_equipment_status(self, msg: String):
        """Handle equipment status update."""
        try:
            data = json.loads(msg.data)
            eq_id = data.get('equipment_id')

            if eq_id and eq_id in self._equipment:
                self._equipment[eq_id].available = data.get('available', True)
                if data.get('available_at'):
                    self._equipment[eq_id].available_at = datetime.fromisoformat(
                        data['available_at']
                    )

        except Exception as e:
            self.get_logger().debug(f"Equipment status parse error: {e}")

    def _publish_schedule_update(self, assignments: Dict[str, str], reason: RescheduleReason):
        """Publish schedule update."""
        update = {
            'type': 'reschedule',
            'reason': reason.value,
            'assignments': assignments,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(update)
        self._schedule_pub.publish(msg)

    def _publish_result(self, result: RescheduleResult):
        """Publish reschedule result."""
        status = {
            'success': result.success,
            'operations_affected': result.operations_affected,
            'estimated_delay_minutes': result.estimated_delay_minutes,
            'strategy': result.strategy_used.value,
            'message': result.message,
            'timestamp': datetime.now().isoformat(),
        }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RescheduleServiceNode()

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
