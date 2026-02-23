"""
Work Order Service

Manages work order lifecycle:
- Creation from demand or manual entry
- Release for production
- Operation start/complete
- Status transitions
- Completion and closure
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from models import (
    WorkOrder, WorkOrderOperation, Part, WorkCenter,
    InventoryTransaction, InventoryBalance
)
from models.manufacturing import WorkOrderStatus, OperationStatus


class WorkOrderService:
    """
    Work Order Service - Production order management.

    Handles the complete lifecycle of manufacturing work orders
    following ISA-95 manufacturing operations management patterns.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_work_order(
        self,
        part_id: str,
        quantity: int,
        priority: int = 5,
        scheduled_start: datetime = None,
        customer_id: str = None,
        sales_order_ref: str = None,
        notes: str = None,
        created_by: str = None
    ) -> WorkOrder:
        """
        Create a new work order.

        Args:
            part_id: ID of the part to produce
            quantity: Number of parts to produce
            priority: Priority level (1=highest, 10=lowest)
            scheduled_start: Planned start date/time
            customer_id: Optional customer reference
            sales_order_ref: Optional sales order reference
            notes: Additional notes
            created_by: User creating the order

        Returns:
            Created WorkOrder instance
        """
        # Validate part exists
        part = self.session.query(Part).filter(Part.id == part_id).first()
        if not part:
            raise ValueError(f"Part with ID {part_id} not found")

        # Generate work order number
        wo_number = self._generate_wo_number()

        work_order = WorkOrder(
            work_order_number=wo_number,
            part_id=part_id,
            quantity_ordered=quantity,
            priority=priority,
            status=WorkOrderStatus.PLANNED.value,
            scheduled_start=scheduled_start,
            customer_id=customer_id,
            sales_order_ref=sales_order_ref,
            notes=notes,
            created_by=created_by
        )

        self.session.add(work_order)
        self.session.flush()  # Get the ID

        # Generate operations from routing
        work_order.generate_operations_from_routing(self.session)

        self.session.commit()
        return work_order

    def _generate_wo_number(self) -> str:
        """Generate unique work order number."""
        today = datetime.utcnow().strftime('%Y%m%d')
        prefix = f"WO-{today}-"

        # Find highest sequence for today
        from sqlalchemy import func
        last_wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_number.like(f"{prefix}%")
        ).order_by(WorkOrder.work_order_number.desc()).first()

        if last_wo:
            try:
                last_seq = int(last_wo.work_order_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        return f"{prefix}{next_seq:04d}"

    def release_work_order(self, work_order_id: str) -> WorkOrder:
        """
        Release a work order for production.

        Validates:
        - Work order is in PLANNED status
        - Part has active routing
        - Required materials are available

        Args:
            work_order_id: ID of work order to release

        Returns:
            Updated WorkOrder instance
        """
        work_order = self._get_work_order(work_order_id)

        if work_order.status != WorkOrderStatus.PLANNED.value:
            raise ValueError(f"Cannot release work order in status {work_order.status}")

        # Validate routing exists
        if not work_order.operations:
            raise ValueError("Work order has no operations. Check part routing.")

        # Check material availability
        material_available = self._check_material_availability(work_order)
        if not material_available:
            raise ValueError("Insufficient material inventory for work order")

        # Allocate inventory
        self._allocate_inventory(work_order)

        work_order.status = WorkOrderStatus.RELEASED.value
        self.session.commit()

        return work_order

    def start_work_order(self, work_order_id: str) -> WorkOrder:
        """
        Start a work order (first operation begins).

        Args:
            work_order_id: ID of work order to start

        Returns:
            Updated WorkOrder instance
        """
        work_order = self._get_work_order(work_order_id)

        if work_order.status not in [WorkOrderStatus.RELEASED.value, WorkOrderStatus.ON_HOLD.value]:
            raise ValueError(f"Cannot start work order in status {work_order.status}")

        work_order.status = WorkOrderStatus.IN_PROGRESS.value
        work_order.actual_start = datetime.utcnow()
        self.session.commit()

        return work_order

    def complete_work_order(
        self,
        work_order_id: str,
        quantity_completed: int,
        quantity_scrapped: int = 0
    ) -> WorkOrder:
        """
        Complete a work order.

        Args:
            work_order_id: ID of work order
            quantity_completed: Number of good parts produced
            quantity_scrapped: Number of scrapped parts

        Returns:
            Updated WorkOrder instance
        """
        work_order = self._get_work_order(work_order_id)

        if work_order.status != WorkOrderStatus.IN_PROGRESS.value:
            raise ValueError(f"Cannot complete work order in status {work_order.status}")

        # Validate all operations are complete
        incomplete_ops = [
            op for op in work_order.operations
            if op.status != OperationStatus.COMPLETE.value
        ]
        if incomplete_ops:
            raise ValueError(f"Cannot complete: {len(incomplete_ops)} operations still pending")

        work_order.status = WorkOrderStatus.COMPLETED.value
        work_order.actual_end = datetime.utcnow()
        work_order.quantity_completed = quantity_completed
        work_order.quantity_scrapped = quantity_scrapped

        # Record finished goods to inventory
        self._record_finished_goods(work_order, quantity_completed)

        # Record costs to cost ledger
        self._record_costs(work_order)

        self.session.commit()
        return work_order

    def cancel_work_order(self, work_order_id: str, reason: str = None) -> WorkOrder:
        """
        Cancel a work order.

        Args:
            work_order_id: ID of work order
            reason: Cancellation reason

        Returns:
            Updated WorkOrder instance
        """
        work_order = self._get_work_order(work_order_id)

        if work_order.status == WorkOrderStatus.COMPLETED.value:
            raise ValueError("Cannot cancel completed work order")

        work_order.status = WorkOrderStatus.CANCELLED.value
        if reason:
            work_order.notes = f"{work_order.notes or ''}\nCancelled: {reason}".strip()

        # Release allocated inventory
        self._release_allocated_inventory(work_order)

        self.session.commit()
        return work_order

    def hold_work_order(self, work_order_id: str, reason: str = None) -> WorkOrder:
        """
        Place a work order on hold.

        Args:
            work_order_id: ID of work order
            reason: Hold reason

        Returns:
            Updated WorkOrder instance
        """
        work_order = self._get_work_order(work_order_id)

        if work_order.status not in [
            WorkOrderStatus.PLANNED.value,
            WorkOrderStatus.RELEASED.value,
            WorkOrderStatus.IN_PROGRESS.value
        ]:
            raise ValueError(f"Cannot hold work order in status {work_order.status}")

        work_order.status = WorkOrderStatus.ON_HOLD.value
        if reason:
            work_order.notes = f"{work_order.notes or ''}\nHold: {reason}".strip()

        self.session.commit()
        return work_order

    # Operation Management

    def start_operation(
        self,
        operation_id: str,
        work_center_id: str = None,
        operator_id: str = None
    ) -> WorkOrderOperation:
        """
        Start a work order operation.

        Args:
            operation_id: ID of operation to start
            work_center_id: Work center performing the operation
            operator_id: Operator starting the operation

        Returns:
            Updated WorkOrderOperation instance
        """
        operation = self._get_operation(operation_id)

        if operation.status != OperationStatus.PENDING.value:
            raise ValueError(f"Cannot start operation in status {operation.status}")

        # Check previous operations are complete
        previous_ops = [
            op for op in operation.work_order.operations
            if op.operation_sequence < operation.operation_sequence
            and op.status != OperationStatus.COMPLETE.value
        ]
        if previous_ops:
            raise ValueError("Previous operations must be completed first")

        operation.start(operator_id=operator_id, work_center_id=work_center_id)

        # Start work order if not already started
        if operation.work_order.status == WorkOrderStatus.RELEASED.value:
            operation.work_order.status = WorkOrderStatus.IN_PROGRESS.value
            operation.work_order.actual_start = datetime.utcnow()

        # Update work center status
        if work_center_id:
            work_center = self.session.query(WorkCenter).filter(
                WorkCenter.id == work_center_id
            ).first()
            if work_center:
                from models.manufacturing import WorkCenterStatus
                work_center.status = WorkCenterStatus.IN_USE.value

        self.session.commit()
        return operation

    def complete_operation(
        self,
        operation_id: str,
        quantity_completed: int,
        quantity_scrapped: int = 0,
        notes: str = None
    ) -> WorkOrderOperation:
        """
        Complete a work order operation.

        Args:
            operation_id: ID of operation
            quantity_completed: Good parts produced
            quantity_scrapped: Scrapped parts
            notes: Completion notes

        Returns:
            Updated WorkOrderOperation instance
        """
        operation = self._get_operation(operation_id)

        if operation.status != OperationStatus.RUNNING.value:
            raise ValueError(f"Cannot complete operation in status {operation.status}")

        operation.complete(quantity_completed, quantity_scrapped)

        if notes:
            operation.notes = notes

        # Update work center status back to available
        if operation.work_center_id:
            work_center = self.session.query(WorkCenter).filter(
                WorkCenter.id == operation.work_center_id
            ).first()
            if work_center:
                from models.manufacturing import WorkCenterStatus
                work_center.status = WorkCenterStatus.AVAILABLE.value
                # Update runtime hours
                if operation.run_time_actual_min:
                    work_center.total_runtime_hours = (
                        (work_center.total_runtime_hours or 0) +
                        operation.run_time_actual_min / 60
                    )

        # Record OEE event
        self._record_oee_event(operation)

        # Record costs
        self._record_operation_costs(operation)

        self.session.commit()
        return operation

    # Query Methods

    def get_work_queue(
        self,
        work_center_id: str = None,
        status: List[str] = None
    ) -> List[WorkOrder]:
        """
        Get prioritized work queue.

        Args:
            work_center_id: Filter by work center
            status: Filter by status list

        Returns:
            List of work orders sorted by priority and scheduled start
        """
        if status is None:
            status = [WorkOrderStatus.RELEASED.value, WorkOrderStatus.IN_PROGRESS.value]

        return WorkOrder.get_queue(self.session, work_center_id)

    def get_active_operations(self, work_center_id: str = None) -> List[WorkOrderOperation]:
        """Get currently active (running) operations."""
        query = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.status == OperationStatus.RUNNING.value
        )

        if work_center_id:
            query = query.filter(WorkOrderOperation.work_center_id == work_center_id)

        return query.all()

    def _get_work_order(self, work_order_id: str) -> WorkOrder:
        """Get work order by ID or raise error."""
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == work_order_id
        ).first()

        if not work_order:
            raise ValueError(f"Work order {work_order_id} not found")

        return work_order

    def _get_operation(self, operation_id: str) -> WorkOrderOperation:
        """Get operation by ID or raise error."""
        operation = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.id == operation_id
        ).first()

        if not operation:
            raise ValueError(f"Operation {operation_id} not found")

        return operation

    # Inventory Management Methods

    def _check_material_availability(self, work_order: WorkOrder) -> bool:
        """
        Check if required materials are available in inventory.

        Returns True if all materials are available in sufficient quantity.
        """
        if not work_order.part or not work_order.part.bom_items:
            # No BOM defined, assume materials available
            return True

        for bom_item in work_order.part.bom_items:
            required_qty = bom_item.quantity * work_order.quantity_ordered

            # Check inventory balance
            balance = self.session.query(InventoryBalance).filter(
                InventoryBalance.part_id == bom_item.component_id
            ).first()

            available_qty = balance.quantity_on_hand if balance else 0

            if available_qty < required_qty:
                return False

        return True

    def _allocate_inventory(self, work_order: WorkOrder) -> None:
        """
        Allocate inventory for work order materials.

        Creates inventory transactions to reserve materials.
        """
        if not work_order.part or not work_order.part.bom_items:
            return

        for bom_item in work_order.part.bom_items:
            required_qty = bom_item.quantity * work_order.quantity_ordered

            # Create allocation transaction
            transaction = InventoryTransaction(
                part_id=bom_item.component_id,
                transaction_type='allocate',
                quantity=-required_qty,
                reference_type='work_order',
                reference_id=str(work_order.id),
                notes=f"Allocated for WO {work_order.work_order_number}"
            )
            self.session.add(transaction)

            # Update balance
            balance = self.session.query(InventoryBalance).filter(
                InventoryBalance.part_id == bom_item.component_id
            ).first()

            if balance:
                balance.quantity_allocated = (balance.quantity_allocated or 0) + required_qty

    def _release_allocated_inventory(self, work_order: WorkOrder) -> None:
        """
        Release allocated inventory when work order is cancelled.
        """
        if not work_order.part or not work_order.part.bom_items:
            return

        for bom_item in work_order.part.bom_items:
            allocated_qty = bom_item.quantity * work_order.quantity_ordered

            # Create release transaction
            transaction = InventoryTransaction(
                part_id=bom_item.component_id,
                transaction_type='release',
                quantity=allocated_qty,
                reference_type='work_order',
                reference_id=str(work_order.id),
                notes=f"Released from cancelled WO {work_order.work_order_number}"
            )
            self.session.add(transaction)

            # Update balance
            balance = self.session.query(InventoryBalance).filter(
                InventoryBalance.part_id == bom_item.component_id
            ).first()

            if balance:
                balance.quantity_allocated = max(0, (balance.quantity_allocated or 0) - allocated_qty)

    def _record_finished_goods(self, work_order: WorkOrder, quantity: int) -> None:
        """
        Record completed parts to finished goods inventory.
        """
        if not work_order.part_id:
            return

        # Create receipt transaction
        transaction = InventoryTransaction(
            part_id=work_order.part_id,
            transaction_type='receipt',
            quantity=quantity,
            reference_type='work_order',
            reference_id=str(work_order.id),
            notes=f"Completed from WO {work_order.work_order_number}"
        )
        self.session.add(transaction)

        # Update balance
        balance = self.session.query(InventoryBalance).filter(
            InventoryBalance.part_id == work_order.part_id
        ).first()

        if balance:
            balance.quantity_on_hand = (balance.quantity_on_hand or 0) + quantity
        else:
            # Create new balance record
            new_balance = InventoryBalance(
                part_id=work_order.part_id,
                quantity_on_hand=quantity
            )
            self.session.add(new_balance)

    def _record_costs(self, work_order: WorkOrder) -> None:
        """
        Record work order costs to cost ledger.
        """
        total_labor_cost = 0
        total_overhead_cost = 0

        for operation in work_order.operations:
            if operation.run_time_actual_min and operation.work_center:
                hourly_rate = float(operation.work_center.hourly_rate or 0)
                labor_hours = operation.run_time_actual_min / 60
                total_labor_cost += hourly_rate * labor_hours
                # Overhead at 50% of labor
                total_overhead_cost += hourly_rate * labor_hours * 0.5

        # Store costs on work order
        work_order.actual_labor_cost = total_labor_cost
        work_order.actual_overhead_cost = total_overhead_cost

    def _record_oee_event(self, operation: WorkOrderOperation) -> None:
        """
        Record OEE production event for completed operation.
        """
        from models.analytics import OEEEvent

        if not operation.work_center_id:
            return

        # Calculate production time
        run_time_hours = (operation.run_time_actual_min or 0) / 60

        oee_event = OEEEvent(
            work_center_id=operation.work_center_id,
            event_type='production',
            start_time=operation.actual_start,
            end_time=operation.actual_end,
            parts_produced=operation.quantity_completed,
            parts_defective=operation.quantity_scrapped,
            notes=f"Operation {operation.operation_code} completed"
        )
        self.session.add(oee_event)

    def _record_operation_costs(self, operation: WorkOrderOperation) -> None:
        """
        Record individual operation costs.
        """
        if not operation.work_center or not operation.run_time_actual_min:
            return

        hourly_rate = float(operation.work_center.hourly_rate or 0)
        labor_hours = operation.run_time_actual_min / 60

        operation.labor_cost = hourly_rate * labor_hours
        operation.overhead_cost = hourly_rate * labor_hours * 0.5
