"""
Production Planner - Convert BOMs to Scheduled Work Orders

Converts Bill of Materials into executable production plans
with ROS2 action goals for the orchestrator.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

from .bom_generator import BillOfMaterials, BOMItem, ManufacturingProcess

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of production operations."""
    PRINT_SLA = "print_sla"
    PRINT_FDM = "print_fdm"
    CNC_MILL = "cnc_mill"
    LASER_CUT = "laser_cut"
    INSPECT = "inspect"
    WASH = "wash"
    CURE = "cure"
    ASSEMBLE = "assemble"
    PACK = "pack"


class OperationStatus(Enum):
    """Operation execution status."""
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ON_HOLD = "on_hold"


@dataclass
class Operation:
    """Single production operation."""
    operation_id: str
    operation_type: OperationType
    work_order_id: str
    part_id: str
    equipment_type: str
    duration_minutes: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: OperationStatus = OperationStatus.PLANNED
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    assigned_equipment: str = ""
    priority: int = 2

    def to_ros2_goal(self) -> Dict[str, Any]:
        """Convert to ROS2 action goal format."""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type.value,
            'work_order_id': self.work_order_id,
            'part_id': self.part_id,
            'equipment_type': self.equipment_type,
            'equipment_id': self.assigned_equipment,
            'parameters': self.parameters,
            'priority': self.priority,
        }


@dataclass
class WorkOrder:
    """Production work order."""
    work_order_id: str
    bom_id: str
    model_name: str
    quantity: int
    priority: int
    due_date: Optional[datetime]
    operations: List[Operation]
    status: str = "planned"
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'work_order_id': self.work_order_id,
            'bom_id': self.bom_id,
            'model_name': self.model_name,
            'quantity': self.quantity,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'operation_count': len(self.operations),
            'operations': [
                {
                    'operation_id': op.operation_id,
                    'type': op.operation_type.value,
                    'part_id': op.part_id,
                    'equipment': op.equipment_type,
                    'duration': op.duration_minutes,
                    'status': op.status.value,
                }
                for op in self.operations
            ]
        }


@dataclass
class ProductionPlan:
    """Complete production plan."""
    plan_id: str
    work_orders: List[WorkOrder]
    created_at: datetime
    planned_start: datetime
    planned_end: datetime
    total_operations: int
    total_duration_hours: float
    equipment_utilization: Dict[str, float]


class ProductionPlanner:
    """
    Converts BOMs to scheduled production plans.

    Features:
    - BOM explosion to operations
    - Dependency tracking
    - Equipment assignment
    - Schedule optimization via CP-SAT
    """

    def __init__(self):
        self._equipment_capabilities = self._load_equipment_capabilities()
        self._process_routes = self._load_process_routes()

    def _load_equipment_capabilities(self) -> Dict[str, List[str]]:
        """Load equipment capabilities."""
        return {
            'formlabs': ['print_sla', 'cure'],
            'coastrunner': ['print_fdm'],
            'cnc': ['cnc_mill'],
            'laser': ['laser_cut', 'laser_engrave'],
            'ned2': ['assemble', 'pick_place', 'inspect'],
            'xarm': ['assemble', 'pick_place', 'inspect'],
            'wash_station': ['wash'],
            'vision': ['inspect'],
        }

    def _load_process_routes(self) -> Dict[str, List[OperationType]]:
        """Load standard process routes."""
        return {
            'sla_print': [
                OperationType.PRINT_SLA,
                OperationType.WASH,
                OperationType.CURE,
                OperationType.INSPECT,
            ],
            'fdm_print': [
                OperationType.PRINT_FDM,
                OperationType.INSPECT,
            ],
            'cnc_part': [
                OperationType.CNC_MILL,
                OperationType.INSPECT,
            ],
            'assembly': [
                OperationType.ASSEMBLE,
                OperationType.INSPECT,
                OperationType.PACK,
            ],
        }

    def create_work_order(
        self,
        bom: BillOfMaterials,
        quantity: int = 1,
        priority: int = 2,
        due_date: Optional[datetime] = None,
    ) -> WorkOrder:
        """
        Create a work order from a BOM.

        Args:
            bom: Bill of Materials
            quantity: Number of assemblies to produce
            priority: Priority (1=highest, 5=lowest)
            due_date: Due date for completion

        Returns:
            Work order with all operations
        """
        work_order_id = f"WO-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        operations = self._generate_operations(bom, work_order_id, quantity)

        work_order = WorkOrder(
            work_order_id=work_order_id,
            bom_id=bom.bom_id,
            model_name=bom.model_name,
            quantity=quantity,
            priority=priority,
            due_date=due_date,
            operations=operations,
        )

        logger.info(f"Created work order {work_order_id} with {len(operations)} operations")
        return work_order

    def _generate_operations(
        self,
        bom: BillOfMaterials,
        work_order_id: str,
        quantity: int
    ) -> List[Operation]:
        """Generate operations from BOM items."""
        operations = []
        op_count = 0
        part_operations: Dict[str, List[str]] = {}  # Track ops per part

        # Generate operations for each part
        for item in bom.items:
            for instance in range(item.part_spec.quantity * quantity):
                part_ops = self._generate_part_operations(
                    item,
                    work_order_id,
                    op_count,
                    instance,
                )

                for op in part_ops:
                    operations.append(op)
                    op_count += 1

                    # Track for dependency resolution
                    part_key = f"{item.part_spec.part_id}_{instance}"
                    if part_key not in part_operations:
                        part_operations[part_key] = []
                    part_operations[part_key].append(op.operation_id)

        # Add assembly operations if multi-part
        if len(bom.items) > 1:
            # Get final inspect operations as dependencies
            inspect_ops = [
                op.operation_id for op in operations
                if op.operation_type == OperationType.INSPECT
            ]

            for instance in range(quantity):
                op_count += 1
                assembly_op = Operation(
                    operation_id=f"{work_order_id}-{op_count:04d}",
                    operation_type=OperationType.ASSEMBLE,
                    work_order_id=work_order_id,
                    part_id=bom.model_name,
                    equipment_type='robot',
                    duration_minutes=self._estimate_assembly_time(bom),
                    parameters={
                        'assembly_id': f"{bom.bom_id}_{instance}",
                        'total_parts': len(bom.items),
                    },
                    dependencies=inspect_ops[:len(bom.items)],  # Depend on inspects
                )
                operations.append(assembly_op)

                # Final inspection
                op_count += 1
                final_inspect = Operation(
                    operation_id=f"{work_order_id}-{op_count:04d}",
                    operation_type=OperationType.INSPECT,
                    work_order_id=work_order_id,
                    part_id=bom.model_name,
                    equipment_type='vision',
                    duration_minutes=2.0,
                    parameters={'inspection_type': 'final_assembly'},
                    dependencies=[assembly_op.operation_id],
                )
                operations.append(final_inspect)

        return operations

    def _generate_part_operations(
        self,
        item: BOMItem,
        work_order_id: str,
        start_op_num: int,
        instance: int,
    ) -> List[Operation]:
        """Generate operations for a single part."""
        operations = []
        op_num = start_op_num

        # Determine process route
        process = item.part_spec.manufacturing_process
        if process == ManufacturingProcess.SLA_PRINT:
            route = self._process_routes['sla_print']
        elif process == ManufacturingProcess.FDM_PRINT:
            route = self._process_routes['fdm_print']
        elif process == ManufacturingProcess.CNC_MILL:
            route = self._process_routes['cnc_part']
        else:
            route = [OperationType.INSPECT]  # Purchased parts just need inspection

        prev_op_id = None
        for op_type in route:
            op_num += 1
            op_id = f"{work_order_id}-{op_num:04d}"

            # Determine equipment and duration
            equipment = self._get_equipment_for_operation(op_type)
            duration = self._get_operation_duration(op_type, item)

            # Build parameters
            params = {
                'part_id': item.part_spec.part_id,
                'color': item.part_spec.color,
                'material': item.part_spec.material,
                'instance': instance,
            }

            if op_type == OperationType.PRINT_SLA:
                params['layer_thickness'] = 0.05  # mm
                params['exposure_time'] = 8.0  # seconds
            elif op_type == OperationType.PRINT_FDM:
                params['layer_height'] = 0.2  # mm
                params['infill'] = 20  # percent
            elif op_type == OperationType.INSPECT:
                params['critical_dimensions'] = item.part_spec.critical_dimensions

            op = Operation(
                operation_id=op_id,
                operation_type=op_type,
                work_order_id=work_order_id,
                part_id=item.part_spec.part_id,
                equipment_type=equipment,
                duration_minutes=duration,
                parameters=params,
                dependencies=[prev_op_id] if prev_op_id else [],
            )
            operations.append(op)
            prev_op_id = op_id

        return operations

    def _get_equipment_for_operation(self, op_type: OperationType) -> str:
        """Get equipment type for operation."""
        equipment_map = {
            OperationType.PRINT_SLA: 'sla_printer',
            OperationType.PRINT_FDM: 'fdm_printer',
            OperationType.CNC_MILL: 'cnc',
            OperationType.LASER_CUT: 'laser',
            OperationType.INSPECT: 'vision',
            OperationType.WASH: 'wash_station',
            OperationType.CURE: 'cure_station',
            OperationType.ASSEMBLE: 'robot',
            OperationType.PACK: 'pack_station',
        }
        return equipment_map.get(op_type, 'manual')

    def _get_operation_duration(
        self,
        op_type: OperationType,
        item: BOMItem
    ) -> float:
        """Get operation duration in minutes."""
        if op_type == OperationType.PRINT_SLA:
            return item.part_spec.print_time_minutes
        elif op_type == OperationType.PRINT_FDM:
            return item.part_spec.print_time_minutes * 1.5  # FDM typically slower
        elif op_type == OperationType.CNC_MILL:
            return item.part_spec.print_time_minutes * 0.5
        elif op_type == OperationType.INSPECT:
            return 1.0  # 1 minute per inspection
        elif op_type == OperationType.WASH:
            return 10.0  # 10 minutes wash cycle
        elif op_type == OperationType.CURE:
            return 30.0  # 30 minutes UV cure
        elif op_type == OperationType.ASSEMBLE:
            return 0.5  # 30 seconds per part placement
        else:
            return 1.0

    def _estimate_assembly_time(self, bom: BillOfMaterials) -> float:
        """Estimate assembly time for a complete model."""
        # Base time + time per part
        return 2.0 + len(bom.items) * 0.5

    def schedule_work_order(
        self,
        work_order: WorkOrder,
        start_time: Optional[datetime] = None,
        available_equipment: Optional[Dict[str, List[str]]] = None,
    ) -> WorkOrder:
        """
        Schedule operations in a work order.

        Args:
            work_order: Work order to schedule
            start_time: Earliest start time (default: now)
            available_equipment: Available equipment by type

        Returns:
            Scheduled work order
        """
        if start_time is None:
            start_time = datetime.now()

        if available_equipment is None:
            available_equipment = {
                'sla_printer': ['formlabs'],
                'fdm_printer': ['coastrunner'],
                'cnc': ['cnc'],
                'laser': ['laser'],
                'robot': ['ned2', 'xarm'],
                'vision': ['vision'],
                'wash_station': ['wash_station'],
                'cure_station': ['cure_station'],
            }

        # Simple forward scheduling (for production, use CP-SAT scheduler)
        equipment_end_times: Dict[str, datetime] = {}
        scheduled_ops: Dict[str, datetime] = {}

        for op in work_order.operations:
            # Get earliest start based on dependencies
            earliest_start = start_time
            for dep_id in op.dependencies:
                if dep_id in scheduled_ops:
                    dep_end = scheduled_ops[dep_id]
                    if dep_end > earliest_start:
                        earliest_start = dep_end

            # Get available equipment
            equipment_options = available_equipment.get(op.equipment_type, ['manual'])
            if not equipment_options:
                equipment_options = ['manual']

            # Find earliest available equipment
            best_equipment = equipment_options[0]
            best_start = earliest_start

            for eq in equipment_options:
                eq_available = equipment_end_times.get(eq, start_time)
                candidate_start = max(earliest_start, eq_available)
                if candidate_start < best_start:
                    best_start = candidate_start
                    best_equipment = eq

            # Schedule operation
            op.assigned_equipment = best_equipment
            op.scheduled_start = best_start
            op.scheduled_end = best_start + timedelta(minutes=op.duration_minutes)
            op.status = OperationStatus.SCHEDULED

            # Update tracking
            equipment_end_times[best_equipment] = op.scheduled_end
            scheduled_ops[op.operation_id] = op.scheduled_end

        # Update work order
        work_order.status = "scheduled"
        work_order.scheduled_start = min(op.scheduled_start for op in work_order.operations)
        work_order.scheduled_end = max(op.scheduled_end for op in work_order.operations)

        logger.info(f"Scheduled {work_order.work_order_id}: {work_order.scheduled_start} - {work_order.scheduled_end}")
        return work_order

    def create_production_plan(
        self,
        work_orders: List[WorkOrder],
    ) -> ProductionPlan:
        """
        Create a production plan from multiple work orders.

        Args:
            work_orders: List of work orders to plan

        Returns:
            Complete production plan
        """
        plan_id = f"PLAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Sort by priority and due date
        sorted_orders = sorted(
            work_orders,
            key=lambda wo: (wo.priority, wo.due_date or datetime.max)
        )

        # Schedule each work order
        current_time = datetime.now()
        for wo in sorted_orders:
            if wo.status != "scheduled":
                self.schedule_work_order(wo, current_time)
            if wo.scheduled_end:
                current_time = wo.scheduled_end

        # Calculate totals
        total_ops = sum(len(wo.operations) for wo in sorted_orders)
        total_duration = sum(
            (wo.scheduled_end - wo.scheduled_start).total_seconds() / 3600
            for wo in sorted_orders
            if wo.scheduled_start and wo.scheduled_end
        )

        # Calculate equipment utilization
        equipment_busy: Dict[str, float] = {}
        for wo in sorted_orders:
            for op in wo.operations:
                eq = op.assigned_equipment
                if eq:
                    equipment_busy[eq] = equipment_busy.get(eq, 0) + op.duration_minutes

        plan_duration = (sorted_orders[-1].scheduled_end - sorted_orders[0].scheduled_start).total_seconds() / 60 if sorted_orders else 1
        utilization = {
            eq: (busy / plan_duration) * 100
            for eq, busy in equipment_busy.items()
        }

        return ProductionPlan(
            plan_id=plan_id,
            work_orders=sorted_orders,
            created_at=datetime.now(),
            planned_start=sorted_orders[0].scheduled_start if sorted_orders else datetime.now(),
            planned_end=sorted_orders[-1].scheduled_end if sorted_orders else datetime.now(),
            total_operations=total_ops,
            total_duration_hours=total_duration,
            equipment_utilization=utilization,
        )

    def get_ros2_action_goals(self, work_order: WorkOrder) -> List[Dict[str, Any]]:
        """
        Get ROS2 action goals for all operations in a work order.

        Returns list of goals to send to orchestrator node.
        """
        return [op.to_ros2_goal() for op in work_order.operations]


# Singleton instance
_production_planner: Optional[ProductionPlanner] = None


def get_production_planner() -> ProductionPlanner:
    """Get production planner singleton."""
    global _production_planner
    if _production_planner is None:
        _production_planner = ProductionPlanner()
    return _production_planner
