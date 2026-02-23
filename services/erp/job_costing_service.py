"""
Job Costing Integration Service (MES -> ERP)
=============================================
Calculates actual job costs from production data.
"""
from datetime import datetime
from typing import Dict, Any, List
from decimal import Decimal


class JobCostingService:
    def __init__(self, session):
        self.session = session

    def calculate_job_cost(self, work_order_id: str) -> Dict[str, Any]:
        from models.mes.work_orders import WorkOrder, Job
        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()
        if not wo:
            return {'error': 'Work order not found'}
        jobs = self.session.query(Job).filter(Job.work_order_id == wo.id).all()
        def _job_hours(j):
            if j.actual_start and j.actual_end:
                return (j.actual_end - j.actual_start).total_seconds() / 3600
            if j.scheduled_start and j.scheduled_end:
                return (j.scheduled_end - j.scheduled_start).total_seconds() / 3600
            return 1.0  # default 1 hour
        total_runtime_hours = sum(_job_hours(j) for j in jobs)
        machine_rate = 50.0
        labor_rate = 25.0
        material_cost = Decimal(str(wo.quantity_ordered or 0)) * Decimal('2.50')
        labor_cost = Decimal(str(total_runtime_hours)) * Decimal(str(labor_rate))
        machine_cost = Decimal(str(total_runtime_hours)) * Decimal(str(machine_rate))
        overhead_rate = Decimal('0.15')
        overhead_cost = (labor_cost + machine_cost) * overhead_rate
        total_cost = material_cost + labor_cost + machine_cost + overhead_cost
        return {
            'work_order_id': work_order_id, 'product_id': wo.product_id,
            'quantity': wo.quantity_ordered,
            'cost_breakdown': {
                'material': float(round(material_cost, 2)),
                'labor': float(round(labor_cost, 2)),
                'machine': float(round(machine_cost, 2)),
                'overhead': float(round(overhead_cost, 2)),
            },
            'total_cost': float(round(total_cost, 2)),
            'unit_cost': float(round(total_cost / max(wo.quantity_ordered or 1, 1), 2)),
            'runtime_hours': round(total_runtime_hours, 2),
        }

    def get_job_profitability(self, work_order_id: str, revenue_per_unit: float = 15.0) -> Dict[str, Any]:
        cost = self.calculate_job_cost(work_order_id)
        if 'error' in cost:
            return cost
        revenue = cost['quantity'] * revenue_per_unit
        profit = revenue - cost['total_cost']
        margin = round(profit / max(revenue, 1) * 100, 1)
        return {
            'work_order_id': work_order_id,
            'revenue': round(revenue, 2), 'total_cost': cost['total_cost'],
            'profit': round(profit, 2), 'margin_pct': margin,
            'cost_breakdown': cost['cost_breakdown'],
            'status': 'profitable' if profit > 0 else 'loss',
        }

    def get_profitability_summary(self, period: str = 'month') -> Dict[str, Any]:
        """Get profitability summary across recent work orders."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus
        from datetime import timedelta

        if period == 'week':
            cutoff = datetime.utcnow() - timedelta(days=7)
        elif period == 'quarter':
            cutoff = datetime.utcnow() - timedelta(days=90)
        else:  # month
            cutoff = datetime.utcnow() - timedelta(days=30)

        work_orders = self.session.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.created_at >= cutoff
        ).limit(50).all()

        jobs_summary = []
        total_revenue = 0
        total_cost = 0
        for wo in work_orders:
            prof = self.get_job_profitability(wo.work_order_id)
            if 'error' not in prof:
                jobs_summary.append(prof)
                total_revenue += prof['revenue']
                total_cost += prof['total_cost']

        total_profit = total_revenue - total_cost
        avg_margin = round(total_profit / max(total_revenue, 1) * 100, 1)

        return {
            'period': period,
            'work_order_count': len(jobs_summary),
            'total_revenue': round(total_revenue, 2),
            'total_cost': round(total_cost, 2),
            'total_profit': round(total_profit, 2),
            'average_margin_pct': avg_margin,
            'jobs': jobs_summary[:10],
        }
