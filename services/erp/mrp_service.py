"""
LEGO Factory v3 - MRP Service
==============================
Material Requirements Planning.
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class MRPRequirement:
    """Material requirement for MRP planning."""
    item_id: str
    item_name: str
    date_required: date
    gross_requirement: float
    on_hand: float
    on_order: float
    allocated: float
    net_requirement: float
    planned_order_qty: float
    planned_order_date: date
    source: str  # 'sales_order', 'work_order', 'forecast', 'safety_stock'
    source_id: str = None
    level: int = 0
    parent_item: str = None


@dataclass
class MRPPlan:
    """Complete MRP plan."""
    plan_date: date
    horizon_days: int
    requirements: List[MRPRequirement] = field(default_factory=list)
    planned_orders: List[Dict[str, Any]] = field(default_factory=list)
    action_messages: List[str] = field(default_factory=list)


class MRPService:
    """Material Requirements Planning service."""

    def __init__(self, session: Session):
        self.session = session

    def run_mrp(
        self,
        horizon_days: int = 90,
        include_forecasts: bool = True,
        generate_planned_orders: bool = True
    ) -> MRPPlan:
        """
        Run MRP explosion.

        Steps:
        1. Gather gross requirements from sales orders, work orders, forecasts
        2. For each item, calculate net requirements
        3. Explode BOMs for manufactured items
        4. Generate planned orders
        """
        plan = MRPPlan(
            plan_date=date.today(),
            horizon_days=horizon_days,
        )

        end_date = date.today() + timedelta(days=horizon_days)

        # Step 1: Gather gross requirements
        gross_requirements = self._gather_gross_requirements(end_date, include_forecasts)

        # Step 2: Process requirements by date/item
        processed_items = set()
        requirements_by_item = defaultdict(list)

        for req in gross_requirements:
            requirements_by_item[req['item_id']].append(req)

        # Step 3: Calculate net requirements and explode BOMs
        for item_id, reqs in requirements_by_item.items():
            if item_id not in processed_items:
                item_requirements = self._process_item_requirements(
                    item_id, reqs, end_date, level=0
                )
                plan.requirements.extend(item_requirements)
                processed_items.add(item_id)

        # Step 4: Generate planned orders
        if generate_planned_orders:
            plan.planned_orders = self._generate_planned_orders(plan.requirements)

        # Step 5: Generate action messages
        plan.action_messages = self._generate_action_messages(plan)

        logger.info(f"MRP run complete: {len(plan.requirements)} requirements, {len(plan.planned_orders)} planned orders")
        return plan

    def _gather_gross_requirements(
        self,
        end_date: date,
        include_forecasts: bool
    ) -> List[Dict[str, Any]]:
        """Gather all gross requirements."""
        from models.erp.sales import SalesOrder, SalesOrderLine, SalesOrderStatus
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        requirements = []

        # From sales orders
        so_statuses = [SalesOrderStatus.APPROVED, SalesOrderStatus.RELEASED, SalesOrderStatus.PARTIALLY_SHIPPED]
        sales_orders = self.session.query(SalesOrder).filter(
            SalesOrder.status.in_(so_statuses),
            SalesOrder.requested_date <= end_date,
            SalesOrder.is_deleted == False
        ).all()

        for so in sales_orders:
            for line in so.lines:
                open_qty = line.quantity_ordered - line.quantity_shipped
                if open_qty > 0:
                    requirements.append({
                        'item_id': line.item.item_id,
                        'item_name': line.item.name,
                        'date_required': so.requested_date or so.order_date,
                        'quantity': open_qty,
                        'source': 'sales_order',
                        'source_id': so.order_number,
                    })

        # From work orders (component requirements)
        wo_statuses = [WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS]
        work_orders = self.session.query(WorkOrder).filter(
            WorkOrder.status.in_(wo_statuses),
            WorkOrder.planned_start <= end_date,
            WorkOrder.is_deleted == False
        ).all()

        for wo in work_orders:
            # Get BOM for work order product
            from services.erp.item_service import ItemService
            item_service = ItemService(self.session)
            bom = item_service.explode_bom(wo.product_id, wo.quantity_ordered)

            for component in bom:
                requirements.append({
                    'item_id': component['item_id'],
                    'item_name': component['item_name'],
                    'date_required': wo.planned_start.date() if wo.planned_start else date.today(),
                    'quantity': component['quantity'],
                    'source': 'work_order',
                    'source_id': wo.work_order_id,
                })

        # Add safety stock requirements
        requirements.extend(self._get_safety_stock_requirements())

        return requirements

    def _get_safety_stock_requirements(self) -> List[Dict[str, Any]]:
        """Get safety stock replenishment requirements."""
        from models.erp.items import Item
        from models.erp.inventory import InventoryBalance

        requirements = []

        # Find items below safety stock
        items_with_safety = self.session.query(Item).filter(
            Item.safety_stock > 0,
            Item.track_inventory == True,
            Item.is_deleted == False
        ).all()

        for item in items_with_safety:
            total_on_hand = self.session.query(
                func.sum(InventoryBalance.quantity_on_hand)
            ).filter(
                InventoryBalance.item_id == item.id
            ).scalar() or 0

            if total_on_hand < item.safety_stock:
                requirements.append({
                    'item_id': item.item_id,
                    'item_name': item.name,
                    'date_required': date.today(),
                    'quantity': item.safety_stock - total_on_hand,
                    'source': 'safety_stock',
                    'source_id': None,
                })

        return requirements

    def _process_item_requirements(
        self,
        item_id: str,
        requirements: List[Dict[str, Any]],
        end_date: date,
        level: int = 0
    ) -> List[MRPRequirement]:
        """Process requirements for a single item."""
        from models.erp.items import Item
        from models.erp.inventory import InventoryBalance
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return []

        result = []

        # Get current inventory
        on_hand = self.session.query(
            func.sum(InventoryBalance.quantity_available)
        ).filter(
            InventoryBalance.item_id == item.id
        ).scalar() or 0

        # Get open purchase orders
        po_statuses = [PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.SENT, PurchaseOrderStatus.ACKNOWLEDGED]
        on_order = self.session.query(
            func.sum(PurchaseOrderLine.quantity_ordered - PurchaseOrderLine.quantity_received)
        ).join(PurchaseOrder).filter(
            PurchaseOrderLine.item_id == item.id,
            PurchaseOrder.status.in_(po_statuses)
        ).scalar() or 0

        # Get allocated inventory
        allocated = self.session.query(
            func.sum(InventoryBalance.quantity_allocated)
        ).filter(
            InventoryBalance.item_id == item.id
        ).scalar() or 0

        # Group requirements by week for planning
        weekly_reqs = defaultdict(float)
        for req in requirements:
            week_start = req['date_required'] - timedelta(days=req['date_required'].weekday())
            weekly_reqs[week_start] += req['quantity']

        running_balance = on_hand + on_order - allocated

        for week_date in sorted(weekly_reqs.keys()):
            gross_req = weekly_reqs[week_date]
            net_req = max(0, gross_req - running_balance)

            planned_qty = 0
            planned_date = None

            if net_req > 0:
                # Calculate planned order
                planned_qty = max(net_req, item.reorder_quantity or net_req)
                # Round up to order multiple
                if item.order_multiple and item.order_multiple > 0:
                    planned_qty = ((planned_qty + item.order_multiple - 1) // item.order_multiple) * item.order_multiple

                # Calculate order date (subtract lead time)
                planned_date = week_date - timedelta(days=item.lead_time_days or 0)

            mrp_req = MRPRequirement(
                item_id=item_id,
                item_name=item.name,
                date_required=week_date,
                gross_requirement=gross_req,
                on_hand=on_hand,
                on_order=on_order,
                allocated=allocated,
                net_requirement=net_req,
                planned_order_qty=planned_qty,
                planned_order_date=planned_date,
                source=requirements[0]['source'] if requirements else 'unknown',
                source_id=requirements[0].get('source_id'),
                level=level,
            )

            result.append(mrp_req)
            running_balance -= gross_req
            if planned_qty > 0:
                running_balance += planned_qty

        return result

    def _generate_planned_orders(
        self,
        requirements: List[MRPRequirement]
    ) -> List[Dict[str, Any]]:
        """Generate planned purchase/production orders from requirements."""
        from models.erp.items import Item

        planned_orders = []

        # Group by item and planned date
        orders_by_item_date = defaultdict(float)
        for req in requirements:
            if req.planned_order_qty > 0 and req.planned_order_date:
                key = (req.item_id, req.planned_order_date)
                orders_by_item_date[key] += req.planned_order_qty

        for (item_id, order_date), quantity in orders_by_item_date.items():
            item = self.session.query(Item).filter(Item.item_id == item_id).first()
            if not item:
                continue

            order_type = 'production' if item.is_manufactured else 'purchase'

            planned_orders.append({
                'item_id': item_id,
                'item_name': item.name,
                'order_type': order_type,
                'quantity': quantity,
                'order_date': order_date.isoformat(),
                'due_date': (order_date + timedelta(days=item.lead_time_days or 0)).isoformat(),
                'estimated_cost': quantity * (item.standard_cost or 0),
            })

        return planned_orders

    def _generate_action_messages(self, plan: MRPPlan) -> List[str]:
        """Generate action messages for planners."""
        messages = []

        # Past due orders
        for order in plan.planned_orders:
            order_date = date.fromisoformat(order['order_date'])
            if order_date < date.today():
                messages.append(
                    f"EXPEDITE: {order['item_id']} - Order date {order['order_date']} is past due"
                )

        # Large requirements
        for req in plan.requirements:
            if req.net_requirement > 1000:
                messages.append(
                    f"REVIEW: Large requirement for {req.item_id}: {req.net_requirement} units"
                )

        return messages

    def get_item_demand(
        self,
        item_id: str,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """Get demand summary for a specific item."""
        from models.erp.items import Item
        from models.erp.sales import SalesOrderLine
        from models.erp.inventory import InventoryBalance

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return {'error': 'Item not found'}

        end_date = date.today() + timedelta(days=horizon_days)

        # Current inventory
        on_hand = self.session.query(
            func.sum(InventoryBalance.quantity_available)
        ).filter(
            InventoryBalance.item_id == item.id
        ).scalar() or 0

        # Sales order demand
        so_demand = self.session.query(
            func.sum(SalesOrderLine.quantity_ordered - SalesOrderLine.quantity_shipped)
        ).filter(
            SalesOrderLine.item_id == item.id
        ).scalar() or 0

        return {
            'item_id': item_id,
            'item_name': item.name,
            'on_hand': float(on_hand),
            'so_demand': float(so_demand),
            'net_available': float(on_hand - so_demand),
            'safety_stock': item.safety_stock or 0,
            'reorder_point': item.reorder_point or 0,
            'lead_time_days': item.lead_time_days or 0,
            'horizon_days': horizon_days,
        }

    def get_capacity_requirements(
        self,
        horizon_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get capacity requirements from planned production."""
        from models.erp.items import Item, Routing, RoutingOperation
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        end_date = date.today() + timedelta(days=horizon_days)

        # Get planned production
        work_orders = self.session.query(WorkOrder).filter(
            WorkOrder.status.in_([WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS]),
            WorkOrder.planned_start <= end_date,
            WorkOrder.is_deleted == False
        ).all()

        capacity_by_work_center = defaultdict(float)

        for wo in work_orders:
            item = self.session.query(Item).filter(Item.item_id == wo.product_id).first()
            if not item:
                continue

            routing = self.session.query(Routing).filter(
                Routing.item_id == item.id,
                Routing.is_active == True
            ).first()

            if routing:
                for op in routing.operations:
                    run_time = (op.setup_time or 0) + (op.run_time or 0) * wo.quantity_ordered
                    work_center = op.work_center_id or 'unassigned'
                    capacity_by_work_center[work_center] += run_time

        return [
            {'work_center': wc, 'required_hours': round(hours / 60, 2)}
            for wc, hours in capacity_by_work_center.items()
        ]


def get_mrp_service(session: Session = None) -> MRPService:
    """Get MRP service instance."""
    if session:
        return MRPService(session)
    with get_db_session() as session:
        return MRPService(session)
