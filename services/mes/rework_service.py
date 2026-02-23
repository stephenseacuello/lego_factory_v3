"""
Rework Routing & Scrap Tracking Service
========================================
Manages rework orders and tracks scrap costs.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session


class ReworkService:
    def __init__(self, session: Session):
        self.session = session

    def create_rework_order(self, original_wo_id: str, ncr_id: str = None,
                            rework_operations: List[str] = None, cost: float = 0) -> Dict[str, Any]:
        from models.mes.operations import ReworkOrder, ReworkStatus

        count = self.session.query(func.count(ReworkOrder.id)).scalar() or 0
        rework_id = f'RW-{count + 1:04d}'

        order = ReworkOrder(
            rework_id=rework_id,
            original_wo_id=original_wo_id,
            ncr_id=ncr_id,
            rework_operations=rework_operations or [],
            cost=cost,
            status=ReworkStatus.OPEN,
        )
        self.session.add(order)
        self.session.flush()

        return order.to_dict()

    def record_scrap(self, job_id: str, quantity: int, reason: str,
                     unit_cost: float = 0, dispositioned_by: str = None) -> Dict[str, Any]:
        from models.mes.operations import ScrapEvent

        total_cost = round(quantity * unit_cost, 2)

        event = ScrapEvent(
            job_id=job_id,
            quantity=quantity,
            reason=reason,
            unit_cost=unit_cost,
            total_cost=total_cost,
            dispositioned_by=dispositioned_by,
        )
        self.session.add(event)
        self.session.flush()

        return {'status': 'recorded', 'event': event.to_dict()}

    def get_rework_rate(self, period_days: int = 30) -> Dict[str, Any]:
        from models.mes.operations import ReworkOrder

        cutoff = datetime.utcnow() - timedelta(days=period_days)
        reworks = (
            self.session.query(ReworkOrder)
            .filter(ReworkOrder.created_at >= cutoff)
            .all()
        )
        return {
            'period_days': period_days,
            'rework_count': len(reworks),
            'total_rework_cost': round(sum(r.cost or 0 for r in reworks), 2),
        }

    def get_scrap_cost(self, period_days: int = 30) -> Dict[str, Any]:
        from models.mes.operations import ScrapEvent

        cutoff = datetime.utcnow() - timedelta(days=period_days)
        events = (
            self.session.query(ScrapEvent)
            .filter(ScrapEvent.created_at >= cutoff)
            .all()
        )

        total_cost = sum(e.total_cost or 0 for e in events)
        total_qty = sum(e.quantity or 0 for e in events)

        by_reason = defaultdict(lambda: {'qty': 0, 'cost': 0})
        for e in events:
            r = e.reason or 'unknown'
            by_reason[r]['qty'] += e.quantity or 0
            by_reason[r]['cost'] += e.total_cost or 0

        pareto = sorted(by_reason.items(), key=lambda x: x[1]['cost'], reverse=True)

        return {
            'period_days': period_days,
            'total_scrap_cost': round(total_cost, 2),
            'total_scrap_qty': total_qty,
            'event_count': len(events),
            'by_reason': [{'reason': r, **d} for r, d in pareto],
        }
