"""
MRP Engine - Material Requirements Planning.

Implements classic MRP logic:
1. Gross requirements from demand/orders
2. Netting against inventory and scheduled receipts
3. Lot sizing
4. Lead time offsetting
5. BOM explosion
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Part, WorkOrder, WorkCenter
from models.manufacturing import WorkOrderStatus
from models.inventory import InventoryBalance, InventoryTransaction
from services.erp import BOMService

logger = logging.getLogger(__name__)


class LotSizingPolicy(Enum):
    """Lot sizing policies for MRP."""
    LOT_FOR_LOT = "lot_for_lot"  # Order exact quantity needed
    FIXED_ORDER_QTY = "fixed_order_qty"  # Fixed order quantity
    EOQ = "eoq"  # Economic Order Quantity
    POQ = "poq"  # Periodic Order Quantity
    MIN_MAX = "min_max"  # Minimum/Maximum


@dataclass
class PlannedOrder:
    """A planned order from MRP."""
    part_id: str
    part_number: str
    part_name: str
    order_type: str  # 'manufacturing' or 'purchase'
    quantity: int
    due_date: datetime
    start_date: datetime
    level: int  # BOM level
    parent_order: Optional[str] = None
    notes: str = ""


@dataclass
class MRPPeriod:
    """MRP data for a single period."""
    period_date: datetime
    gross_requirements: int = 0
    scheduled_receipts: int = 0
    projected_on_hand: int = 0
    net_requirements: int = 0
    planned_order_receipts: int = 0
    planned_order_releases: int = 0


class MRPEngine:
    """Material Requirements Planning engine."""

    def __init__(self, session: Session):
        self.session = session
        self.bom_service = BOMService(session)

    def run_mrp(
        self,
        part_ids: Optional[List[str]] = None,
        horizon_weeks: int = 12,
        lot_sizing: LotSizingPolicy = LotSizingPolicy.LOT_FOR_LOT
    ) -> Dict[str, Any]:
        """
        Run MRP for specified parts or all parts.

        Args:
            part_ids: List of part IDs to plan (None = all)
            horizon_weeks: Planning horizon in weeks
            lot_sizing: Lot sizing policy

        Returns:
            MRP results with planned orders
        """
        now = datetime.utcnow()
        horizon_end = now + timedelta(weeks=horizon_weeks)

        # Get parts to plan
        if part_ids:
            parts = self.session.query(Part).filter(
                Part.id.in_(part_ids)
            ).all()
        else:
            # Plan all parts that have demand or are in BOMs
            parts = self.session.query(Part).all()

        all_planned_orders = []
        mrp_results = {}

        for part in parts:
            # Run MRP for this part
            result = self._run_mrp_for_part(
                part=part,
                start_date=now,
                end_date=horizon_end,
                lot_sizing=lot_sizing
            )

            if result['planned_orders']:
                all_planned_orders.extend(result['planned_orders'])

            mrp_results[str(part.id)] = result

        # Sort planned orders by date
        all_planned_orders.sort(key=lambda x: x.due_date)

        return {
            'run_date': now.isoformat(),
            'horizon_weeks': horizon_weeks,
            'parts_planned': len(parts),
            'total_planned_orders': len(all_planned_orders),
            'planned_orders': [
                {
                    'part_id': po.part_id,
                    'part_number': po.part_number,
                    'order_type': po.order_type,
                    'quantity': po.quantity,
                    'due_date': po.due_date.isoformat(),
                    'start_date': po.start_date.isoformat(),
                    'level': po.level
                }
                for po in all_planned_orders
            ],
            'by_part': {
                pid: {
                    'gross_requirements': r['total_gross'],
                    'net_requirements': r['total_net'],
                    'planned_orders': len(r['planned_orders'])
                }
                for pid, r in mrp_results.items()
            }
        }

    def _run_mrp_for_part(
        self,
        part: Part,
        start_date: datetime,
        end_date: datetime,
        lot_sizing: LotSizingPolicy
    ) -> Dict[str, Any]:
        """Run MRP for a single part."""
        part_id = str(part.id)

        # Get lead time (from routing or default)
        lead_time_days = self._get_lead_time(part)

        # Get current inventory
        on_hand = self._get_on_hand_qty(part_id)

        # Get gross requirements (from work orders, demand forecast)
        gross_reqs = self._get_gross_requirements(part_id, start_date, end_date)

        # Get scheduled receipts (open work orders, purchase orders)
        scheduled = self._get_scheduled_receipts(part_id, start_date, end_date)

        # Generate weekly periods
        periods = self._generate_periods(start_date, end_date)

        # Run MRP netting logic
        planned_orders = []
        projected_oh = on_hand
        total_gross = 0
        total_net = 0

        for period in periods:
            period_start = period.period_date
            period_end = period_start + timedelta(weeks=1)

            # Sum gross requirements for period
            period_gross = sum(
                r['quantity'] for r in gross_reqs
                if period_start <= r['date'] < period_end
            )
            period.gross_requirements = period_gross
            total_gross += period_gross

            # Sum scheduled receipts for period
            period_receipts = sum(
                r['quantity'] for r in scheduled
                if period_start <= r['date'] < period_end
            )
            period.scheduled_receipts = period_receipts

            # Calculate projected on-hand
            projected_oh = projected_oh + period_receipts - period_gross
            period.projected_on_hand = projected_oh

            # Calculate net requirements
            if projected_oh < 0:
                net_req = abs(projected_oh)
                period.net_requirements = net_req
                total_net += net_req

                # Apply lot sizing
                order_qty = self._apply_lot_sizing(net_req, lot_sizing, part)

                # Create planned order
                order_release_date = period_start - timedelta(days=lead_time_days)
                if order_release_date < start_date:
                    order_release_date = start_date

                planned_order = PlannedOrder(
                    part_id=part_id,
                    part_number=part.part_number,
                    part_name=part.name,
                    order_type='manufacturing' if part.part_type in ['standard', 'assembly'] else 'purchase',
                    quantity=order_qty,
                    due_date=period_start,
                    start_date=order_release_date,
                    level=0
                )
                planned_orders.append(planned_order)

                period.planned_order_receipts = order_qty
                projected_oh = projected_oh + order_qty

        return {
            'part_id': part_id,
            'part_number': part.part_number,
            'on_hand': on_hand,
            'lead_time_days': lead_time_days,
            'total_gross': total_gross,
            'total_net': total_net,
            'periods': [
                {
                    'date': p.period_date.isoformat(),
                    'gross': p.gross_requirements,
                    'receipts': p.scheduled_receipts,
                    'oh': p.projected_on_hand,
                    'net': p.net_requirements,
                    'planned': p.planned_order_receipts
                }
                for p in periods
            ],
            'planned_orders': planned_orders
        }

    def _get_lead_time(self, part: Part) -> int:
        """Get lead time for a part (from routing or default)."""
        # Check if part has routing with lead time
        # For now, use part type defaults
        lead_times = {
            'standard': 3,
            'technic': 4,
            'duplo': 3,
            'minifig': 5,
            'assembly': 7,
            'raw_material': 14
        }
        return lead_times.get(part.part_type, 5)

    def _get_on_hand_qty(self, part_id: str) -> int:
        """Get total on-hand quantity for a part."""
        result = self.session.query(
            func.sum(InventoryBalance.quantity_on_hand)
        ).filter(
            InventoryBalance.part_id == part_id
        ).scalar()

        return result or 0

    def _get_gross_requirements(
        self,
        part_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get gross requirements from work orders and demand."""
        requirements = []

        # From work orders (as components)
        # Would need to join through BOM to find where this part is used
        work_orders = self.session.query(WorkOrder).filter(
            WorkOrder.part_id == part_id,
            WorkOrder.status.in_([
                WorkOrderStatus.PLANNED.value,
                WorkOrderStatus.RELEASED.value
            ]),
            WorkOrder.scheduled_start >= start_date,
            WorkOrder.scheduled_start <= end_date
        ).all()

        for wo in work_orders:
            requirements.append({
                'date': wo.scheduled_start or start_date,
                'quantity': wo.quantity_ordered - wo.quantity_completed,
                'source': 'work_order',
                'reference': wo.work_order_number
            })

        return requirements

    def _get_scheduled_receipts(
        self,
        part_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get scheduled receipts from open orders."""
        receipts = []

        # From in-progress work orders
        work_orders = self.session.query(WorkOrder).filter(
            WorkOrder.part_id == part_id,
            WorkOrder.status == WorkOrderStatus.IN_PROGRESS.value,
            WorkOrder.scheduled_end >= start_date,
            WorkOrder.scheduled_end <= end_date
        ).all()

        for wo in work_orders:
            receipts.append({
                'date': wo.scheduled_end or end_date,
                'quantity': wo.quantity_ordered - wo.quantity_completed,
                'source': 'work_order',
                'reference': wo.work_order_number
            })

        return receipts

    def _generate_periods(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[MRPPeriod]:
        """Generate weekly periods for MRP."""
        periods = []
        current = start_date

        # Align to week start (Monday)
        days_since_monday = current.weekday()
        current = current - timedelta(days=days_since_monday)

        while current < end_date:
            periods.append(MRPPeriod(period_date=current))
            current += timedelta(weeks=1)

        return periods

    def _apply_lot_sizing(
        self,
        net_requirement: int,
        policy: LotSizingPolicy,
        part: Part
    ) -> int:
        """Apply lot sizing policy to net requirement."""
        if policy == LotSizingPolicy.LOT_FOR_LOT:
            return net_requirement

        elif policy == LotSizingPolicy.FIXED_ORDER_QTY:
            # Use min order quantity or default
            min_qty = getattr(part, 'min_order_qty', 100)
            return max(net_requirement, min_qty)

        elif policy == LotSizingPolicy.EOQ:
            # Simplified EOQ calculation
            # Would need annual demand, order cost, holding cost
            return max(net_requirement, 50)

        elif policy == LotSizingPolicy.MIN_MAX:
            # Order up to max when below min
            min_level = getattr(part, 'reorder_point', 10)
            max_level = getattr(part, 'max_inventory', 100)
            return max(net_requirement, max_level - min_level)

        return net_requirement

    def explode_planned_orders(
        self,
        planned_orders: List[PlannedOrder]
    ) -> List[PlannedOrder]:
        """
        Explode planned orders through BOM to create component orders.

        This is the core of MRP - turning parent orders into child orders.
        """
        all_orders = list(planned_orders)
        current_level = 0
        max_levels = 10  # Prevent infinite loops

        while current_level < max_levels:
            orders_at_level = [o for o in all_orders if o.level == current_level]

            if not orders_at_level:
                break

            for order in orders_at_level:
                # Get BOM for this part
                bom = self.bom_service.get_bom(order.part_id)

                for component in bom:
                    child_part = self.session.query(Part).filter(
                        Part.id == component['child_part_id']
                    ).first()

                    if not child_part:
                        continue

                    # Calculate component requirement
                    comp_qty = component['quantity'] * order.quantity

                    # Get lead time for child
                    lead_time = self._get_lead_time(child_part)

                    # Calculate dates
                    child_due = order.start_date
                    child_start = child_due - timedelta(days=lead_time)

                    child_order = PlannedOrder(
                        part_id=str(child_part.id),
                        part_number=child_part.part_number,
                        part_name=child_part.name,
                        order_type='manufacturing' if child_part.part_type != 'raw_material' else 'purchase',
                        quantity=comp_qty,
                        due_date=child_due,
                        start_date=child_start,
                        level=current_level + 1,
                        parent_order=order.part_number,
                        notes=f"Component of {order.part_number}"
                    )

                    all_orders.append(child_order)

            current_level += 1

        return all_orders

    def get_action_messages(
        self,
        part_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate MRP action messages (exception messages).

        Types:
        - Release: Order should be released now
        - Reschedule In: Move order earlier
        - Reschedule Out: Move order later
        - Cancel: Order no longer needed
        - Expedite: Order needed sooner
        """
        messages = []
        now = datetime.utcnow()

        query = self.session.query(WorkOrder).filter(
            WorkOrder.status.in_([
                WorkOrderStatus.PLANNED.value,
                WorkOrderStatus.RELEASED.value
            ])
        )

        if part_id:
            query = query.filter(WorkOrder.part_id == part_id)

        work_orders = query.all()

        for wo in work_orders:
            # Check if should be released
            if wo.status == WorkOrderStatus.PLANNED.value:
                lead_time = self._get_lead_time(wo.part) if wo.part else 5
                start_date = wo.scheduled_start or now

                if start_date <= now:
                    messages.append({
                        'type': 'RELEASE',
                        'priority': 'HIGH',
                        'work_order': wo.work_order_number,
                        'part_number': wo.part.part_number if wo.part else None,
                        'message': f"Order should be released - due date approaching",
                        'suggested_action': f"Release WO {wo.work_order_number}"
                    })

            # Check for overdue orders
            if wo.scheduled_end and wo.scheduled_end < now:
                messages.append({
                    'type': 'EXPEDITE',
                    'priority': 'CRITICAL',
                    'work_order': wo.work_order_number,
                    'part_number': wo.part.part_number if wo.part else None,
                    'message': f"Order is past due",
                    'suggested_action': f"Expedite WO {wo.work_order_number}"
                })

        return messages
