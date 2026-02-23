"""
Capacity Planner - Finite capacity planning and scheduling.

Handles:
- Capacity analysis by work center
- Load leveling
- Finite capacity scheduling
- Bottleneck identification
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Part, WorkOrder, WorkCenter, WorkOrderOperation
from models.manufacturing import WorkCenterStatus, WorkOrderStatus
from services.manufacturing import RoutingService

logger = logging.getLogger(__name__)


class SchedulingDirection(Enum):
    """Scheduling direction."""
    FORWARD = "forward"   # Schedule from start date
    BACKWARD = "backward"  # Schedule from due date


@dataclass
class CapacityBucket:
    """Capacity data for a time period."""
    period_start: datetime
    period_end: datetime
    available_hours: float
    scheduled_hours: float
    remaining_hours: float
    utilization_percent: float


@dataclass
class ScheduledOperation:
    """A scheduled operation."""
    operation_id: str
    work_order_number: str
    operation_code: str
    work_center_id: str
    work_center_code: str
    scheduled_start: datetime
    scheduled_end: datetime
    setup_hours: float
    run_hours: float
    total_hours: float


class CapacityPlanner:
    """Finite capacity planning service."""

    def __init__(self, session: Session):
        self.session = session
        self.routing_service = RoutingService(session)

    def get_capacity_overview(
        self,
        work_center_id: Optional[str] = None,
        horizon_weeks: int = 4,
        period_type: str = 'day'
    ) -> Dict[str, Any]:
        """
        Get capacity overview for work centers.

        Args:
            work_center_id: Filter by work center (None = all)
            horizon_weeks: Planning horizon
            period_type: 'day' or 'week'

        Returns:
            Capacity overview with utilization by period
        """
        now = datetime.utcnow()
        horizon_end = now + timedelta(weeks=horizon_weeks)

        # Get work centers
        if work_center_id:
            work_centers = [self.session.query(WorkCenter).filter(
                WorkCenter.id == work_center_id
            ).first()]
        else:
            work_centers = self.session.query(WorkCenter).filter(
                WorkCenter.status != WorkCenterStatus.OFFLINE.value
            ).all()

        overview = {}

        for wc in work_centers:
            if not wc:
                continue

            buckets = self._calculate_capacity_buckets(
                work_center=wc,
                start_date=now,
                end_date=horizon_end,
                period_type=period_type
            )

            avg_utilization = sum(b.utilization_percent for b in buckets) / len(buckets) if buckets else 0

            overview[str(wc.id)] = {
                'work_center_code': wc.code,
                'work_center_name': wc.name,
                'average_utilization': round(avg_utilization, 1),
                'periods': [
                    {
                        'start': b.period_start.isoformat(),
                        'end': b.period_end.isoformat(),
                        'available_hours': round(b.available_hours, 1),
                        'scheduled_hours': round(b.scheduled_hours, 1),
                        'remaining_hours': round(b.remaining_hours, 1),
                        'utilization': round(b.utilization_percent, 1)
                    }
                    for b in buckets
                ]
            }

        return {
            'generated_at': now.isoformat(),
            'horizon_weeks': horizon_weeks,
            'period_type': period_type,
            'work_centers': overview
        }

    def _calculate_capacity_buckets(
        self,
        work_center: WorkCenter,
        start_date: datetime,
        end_date: datetime,
        period_type: str = 'day'
    ) -> List[CapacityBucket]:
        """Calculate capacity buckets for a work center."""
        buckets = []

        # Hours per day (assuming 8-hour shifts)
        hours_per_day = 8

        # Get scheduled operations
        scheduled_ops = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.work_center_id == work_center.id,
            WorkOrderOperation.status.in_(['pending', 'in_progress']),
            WorkOrderOperation.scheduled_start >= start_date,
            WorkOrderOperation.scheduled_start < end_date
        ).all()

        # Generate periods
        if period_type == 'week':
            delta = timedelta(weeks=1)
            hours_per_period = hours_per_day * 5  # 5-day week
        else:
            delta = timedelta(days=1)
            hours_per_period = hours_per_day

        current = start_date
        while current < end_date:
            period_end = current + delta

            # Calculate available hours (considering efficiency)
            efficiency = (work_center.efficiency_percent or 85) / 100
            available = hours_per_period * efficiency

            # Sum scheduled hours for this period
            scheduled = 0
            for op in scheduled_ops:
                if op.scheduled_start and op.scheduled_end:
                    # Check overlap with this period
                    op_start = max(op.scheduled_start, current)
                    op_end = min(op.scheduled_end, period_end)

                    if op_start < op_end:
                        overlap_hours = (op_end - op_start).total_seconds() / 3600
                        scheduled += overlap_hours

            remaining = max(0, available - scheduled)
            utilization = (scheduled / available * 100) if available > 0 else 0

            buckets.append(CapacityBucket(
                period_start=current,
                period_end=period_end,
                available_hours=available,
                scheduled_hours=scheduled,
                remaining_hours=remaining,
                utilization_percent=utilization
            ))

            current = period_end

        return buckets

    def identify_bottlenecks(
        self,
        horizon_weeks: int = 4,
        threshold_percent: float = 90
    ) -> List[Dict[str, Any]]:
        """
        Identify capacity bottlenecks.

        Args:
            horizon_weeks: Planning horizon
            threshold_percent: Utilization threshold for bottleneck

        Returns:
            List of bottleneck periods
        """
        overview = self.get_capacity_overview(
            horizon_weeks=horizon_weeks,
            period_type='day'
        )

        bottlenecks = []

        for wc_id, wc_data in overview['work_centers'].items():
            for period in wc_data['periods']:
                if period['utilization'] >= threshold_percent:
                    bottlenecks.append({
                        'work_center_id': wc_id,
                        'work_center_code': wc_data['work_center_code'],
                        'work_center_name': wc_data['work_center_name'],
                        'period_start': period['start'],
                        'period_end': period['end'],
                        'utilization': period['utilization'],
                        'overload_hours': max(0, period['scheduled_hours'] - period['available_hours']),
                        'severity': 'CRITICAL' if period['utilization'] > 100 else 'WARNING'
                    })

        # Sort by severity and date
        bottlenecks.sort(
            key=lambda x: (x['severity'] != 'CRITICAL', x['period_start'])
        )

        return bottlenecks

    def schedule_work_order(
        self,
        work_order_id: str,
        direction: SchedulingDirection = SchedulingDirection.BACKWARD
    ) -> List[ScheduledOperation]:
        """
        Schedule a work order using finite capacity.

        Args:
            work_order_id: Work order to schedule
            direction: FORWARD from start date or BACKWARD from due date

        Returns:
            List of scheduled operations
        """
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == work_order_id
        ).first()

        if not work_order:
            raise ValueError(f"Work order {work_order_id} not found")

        # Get routing
        if not work_order.part:
            raise ValueError("Work order has no part")

        routings = self.routing_service.get_routing(str(work_order.part_id))

        if not routings:
            # Auto-generate routing
            routings = self.routing_service.auto_generate_routing(
                str(work_order.part_id),
                work_order.part.part_type
            )

        # Get or create operations
        operations = list(work_order.operations)
        if not operations:
            # Create operations from routing
            for r in routings:
                op = WorkOrderOperation(
                    work_order_id=work_order_id,
                    routing_id=r.id,
                    operation_sequence=r.operation_sequence,
                    operation_code=r.operation_code,
                    work_center_id=r.work_center_id,
                    quantity_scheduled=work_order.quantity_ordered,
                    setup_time_planned=r.setup_time_min,
                    run_time_planned=r.run_time_min * work_order.quantity_ordered,
                    status='pending'
                )
                self.session.add(op)
                operations.append(op)

            self.session.flush()

        # Sort operations
        operations.sort(key=lambda x: x.operation_sequence)

        if direction == SchedulingDirection.BACKWARD:
            operations = list(reversed(operations))

        scheduled = []
        current_date = (
            work_order.scheduled_end or datetime.utcnow() + timedelta(weeks=1)
        ) if direction == SchedulingDirection.BACKWARD else (
            work_order.scheduled_start or datetime.utcnow()
        )

        for op in operations:
            # Calculate duration
            setup_hours = (op.setup_time_planned or 0) / 60
            run_hours = (op.run_time_planned or 0) / 60
            total_hours = setup_hours + run_hours

            # Find available slot
            work_center = self.session.query(WorkCenter).filter(
                WorkCenter.id == op.work_center_id
            ).first()

            if not work_center:
                continue

            # Simple scheduling - find next available slot
            slot = self._find_available_slot(
                work_center=work_center,
                required_hours=total_hours,
                target_date=current_date,
                direction=direction
            )

            if slot:
                op.scheduled_start = slot['start']
                op.scheduled_end = slot['end']

                scheduled.append(ScheduledOperation(
                    operation_id=str(op.id),
                    work_order_number=work_order.work_order_number,
                    operation_code=op.operation_code,
                    work_center_id=str(work_center.id),
                    work_center_code=work_center.code,
                    scheduled_start=slot['start'],
                    scheduled_end=slot['end'],
                    setup_hours=setup_hours,
                    run_hours=run_hours,
                    total_hours=total_hours
                ))

                # Update current date for next operation
                if direction == SchedulingDirection.BACKWARD:
                    current_date = slot['start']
                else:
                    current_date = slot['end']

        self.session.commit()

        # Return in sequence order
        scheduled.sort(key=lambda x: x.scheduled_start)
        return scheduled

    def _find_available_slot(
        self,
        work_center: WorkCenter,
        required_hours: float,
        target_date: datetime,
        direction: SchedulingDirection
    ) -> Optional[Dict[str, datetime]]:
        """Find available capacity slot on a work center."""
        hours_per_day = 8
        efficiency = (work_center.efficiency_percent or 85) / 100
        available_per_day = hours_per_day * efficiency

        # Get existing scheduled operations
        if direction == SchedulingDirection.BACKWARD:
            search_start = target_date - timedelta(days=30)
            search_end = target_date
        else:
            search_start = target_date
            search_end = target_date + timedelta(days=30)

        existing_ops = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.work_center_id == work_center.id,
            WorkOrderOperation.scheduled_start >= search_start,
            WorkOrderOperation.scheduled_end <= search_end,
            WorkOrderOperation.status != 'complete'
        ).all()

        # Build capacity calendar
        current = search_start if direction == SchedulingDirection.FORWARD else search_end

        for _ in range(60):  # Search up to 60 days
            # Calculate available hours for this day
            day_start = current.replace(hour=8, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(hours=hours_per_day)

            # Sum already scheduled hours
            scheduled_hours = 0
            for op in existing_ops:
                if op.scheduled_start and op.scheduled_end:
                    if op.scheduled_start.date() == day_start.date():
                        op_hours = (op.scheduled_end - op.scheduled_start).total_seconds() / 3600
                        scheduled_hours += op_hours

            remaining = available_per_day - scheduled_hours

            if remaining >= required_hours:
                # Found a slot
                if direction == SchedulingDirection.BACKWARD:
                    slot_end = day_end
                    slot_start = slot_end - timedelta(hours=required_hours)
                else:
                    slot_start = day_start + timedelta(hours=scheduled_hours)
                    slot_end = slot_start + timedelta(hours=required_hours)

                return {
                    'start': slot_start,
                    'end': slot_end
                }

            # Move to next/previous day
            if direction == SchedulingDirection.BACKWARD:
                current -= timedelta(days=1)
            else:
                current += timedelta(days=1)

        return None

    def get_schedule_gantt(
        self,
        work_center_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get schedule data formatted for Gantt chart display.

        Returns operations organized by work center and time.
        """
        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(weeks=2)

        query = self.session.query(WorkOrderOperation).filter(
            WorkOrderOperation.status.in_(['pending', 'in_progress']),
            WorkOrderOperation.scheduled_start >= start_date,
            WorkOrderOperation.scheduled_start < end_date
        )

        if work_center_id:
            query = query.filter(WorkOrderOperation.work_center_id == work_center_id)

        operations = query.all()

        # Group by work center
        by_work_center = {}
        for op in operations:
            wc_id = str(op.work_center_id) if op.work_center_id else 'unassigned'

            if wc_id not in by_work_center:
                wc = self.session.query(WorkCenter).filter(
                    WorkCenter.id == op.work_center_id
                ).first() if op.work_center_id else None

                by_work_center[wc_id] = {
                    'work_center_code': wc.code if wc else 'Unassigned',
                    'work_center_name': wc.name if wc else 'Unassigned',
                    'operations': []
                }

            by_work_center[wc_id]['operations'].append({
                'id': str(op.id),
                'work_order': op.work_order.work_order_number if op.work_order else None,
                'operation': op.operation_code,
                'start': op.scheduled_start.isoformat() if op.scheduled_start else None,
                'end': op.scheduled_end.isoformat() if op.scheduled_end else None,
                'status': op.status,
                'progress': (
                    (op.quantity_completed / op.quantity_scheduled * 100)
                    if op.quantity_scheduled else 0
                )
            })

        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'work_centers': list(by_work_center.values())
        }
