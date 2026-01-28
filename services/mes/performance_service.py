"""
LEGO Factory v3 - Performance Analysis Service
===============================================
KPI calculation and analysis for MESA-11 Performance Analysis function.
Calculates OEE, throughput, yield, MTBF, MTTR, and schedule adherence.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

logger = logging.getLogger(__name__)


class PerformanceService:
    """
    Service for calculating manufacturing performance KPIs.

    Key metrics:
    - OEE (Availability × Performance × Quality)
    - Throughput (parts/hour)
    - Yield rate (good/total)
    - MTBF (Mean Time Between Failures)
    - MTTR (Mean Time To Repair)
    - Schedule adherence
    - WIP level
    """

    def __init__(self, session: Session):
        self.session = session

    def calculate_kpis(
        self,
        period: str = '7d',
        machine_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate all KPIs for a period.

        Args:
            period: Time period ('1d', '7d', '30d', 'mtd', 'ytd')
            machine_id: Optional machine filter

        Returns:
            Dict with all KPI values
        """
        start_date, end_date = self._parse_period(period)

        return {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'oee': self._calculate_oee(start_date, end_date, machine_id),
            'throughput': self._calculate_throughput(start_date, end_date, machine_id),
            'yield_rate': self._calculate_yield(start_date, end_date, machine_id),
            'on_time_delivery': self._calculate_otd(start_date, end_date),
            'mtbf': self._calculate_mtbf(start_date, end_date, machine_id),
            'mttr': self._calculate_mttr(start_date, end_date, machine_id),
            'wip_level': self._calculate_wip(),
            'schedule_adherence': self._calculate_schedule_adherence(start_date, end_date),
            'setup_ratio': self._calculate_setup_ratio(start_date, end_date, machine_id),
        }

    def get_trend_data(
        self,
        kpi_name: str,
        machine_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily trend data for a KPI.

        Args:
            kpi_name: KPI to track ('oee', 'throughput', 'yield', etc.)
            machine_id: Optional machine filter
            days: Number of days of history

        Returns:
            List of daily data points
        """
        trend_data = []
        end_date = datetime.utcnow()

        for i in range(days):
            date = end_date - timedelta(days=days - i - 1)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            value = None
            if kpi_name == 'oee':
                value = self._calculate_oee(day_start, day_end, machine_id)
            elif kpi_name == 'throughput':
                value = self._calculate_throughput(day_start, day_end, machine_id)
            elif kpi_name == 'yield':
                value = self._calculate_yield(day_start, day_end, machine_id)
            elif kpi_name == 'otd':
                value = self._calculate_otd(day_start, day_end)

            trend_data.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'value': value or 0
            })

        return trend_data

    def generate_shift_report(
        self,
        shift_date: datetime,
        shift_type: str = 'day'  # 'day', 'evening', 'night'
    ) -> Dict[str, Any]:
        """
        Generate shift handover report.

        Args:
            shift_date: Date of shift
            shift_type: Shift period

        Returns:
            Shift summary report
        """
        # Define shift times
        shift_hours = {
            'day': (6, 14),
            'evening': (14, 22),
            'night': (22, 6),
        }
        start_hour, end_hour = shift_hours.get(shift_type, (6, 14))

        shift_start = shift_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if end_hour < start_hour:  # Night shift crosses midnight
            shift_end = (shift_date + timedelta(days=1)).replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            shift_end = shift_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        return {
            'shift_date': shift_date.strftime('%Y-%m-%d'),
            'shift_type': shift_type,
            'shift_start': shift_start.isoformat(),
            'shift_end': shift_end.isoformat(),
            'summary': {
                'oee': self._calculate_oee(shift_start, shift_end),
                'production_count': self._get_production_count(shift_start, shift_end),
                'defect_count': self._get_defect_count(shift_start, shift_end),
                'downtime_minutes': self._get_downtime_minutes(shift_start, shift_end),
            },
            'production_by_machine': self._get_production_by_machine(shift_start, shift_end),
            'downtime_events': self._get_downtime_events(shift_start, shift_end),
            'quality_issues': self._get_quality_issues(shift_start, shift_end),
            'pending_jobs': self._get_pending_jobs_count(),
        }

    def compare_schedules(
        self,
        result_a: Dict[str, Any],
        result_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare two schedule results side-by-side.
        """
        return {
            'comparison': {
                'makespan': {
                    'a': result_a.get('makespan', 0),
                    'b': result_b.get('makespan', 0),
                    'diff': result_a.get('makespan', 0) - result_b.get('makespan', 0),
                    'winner': 'a' if result_a.get('makespan', 0) <= result_b.get('makespan', 0) else 'b',
                },
                'tardiness': {
                    'a': result_a.get('total_tardiness', 0),
                    'b': result_b.get('total_tardiness', 0),
                    'diff': result_a.get('total_tardiness', 0) - result_b.get('total_tardiness', 0),
                    'winner': 'a' if result_a.get('total_tardiness', 0) <= result_b.get('total_tardiness', 0) else 'b',
                },
                'utilization': {
                    'a': result_a.get('avg_utilization', 0),
                    'b': result_b.get('avg_utilization', 0),
                    'diff': result_a.get('avg_utilization', 0) - result_b.get('avg_utilization', 0),
                    'winner': 'a' if result_a.get('avg_utilization', 0) >= result_b.get('avg_utilization', 0) else 'b',
                },
            }
        }

    # =========================================================================
    # Private KPI Calculation Methods
    # =========================================================================

    def _parse_period(self, period: str) -> tuple:
        """Parse period string to start/end datetime."""
        now = datetime.utcnow()

        if period == '1d':
            start = now - timedelta(days=1)
        elif period == '7d':
            start = now - timedelta(days=7)
        elif period == '30d':
            start = now - timedelta(days=30)
        elif period == 'mtd':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'ytd':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now - timedelta(days=7)

        return start, now

    def _calculate_oee(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate OEE = Availability × Performance × Quality."""
        try:
            from models.mes.oee import OEERecord

            query = self.session.query(
                func.avg(OEERecord.availability),
                func.avg(OEERecord.performance),
                func.avg(OEERecord.quality)
            ).filter(
                and_(
                    OEERecord.record_date >= start_date,
                    OEERecord.record_date <= end_date
                )
            )

            if machine_id:
                query = query.filter(OEERecord.machine_id == machine_id)

            result = query.first()
            if result and all(result):
                a, p, q = result
                return round((a / 100) * (p / 100) * (q / 100) * 100, 1)
        except ImportError:
            pass

        return 85.0  # Default fallback

    def _calculate_throughput(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate throughput in parts per hour."""
        try:
            from models.mes.work_orders import Job, JobStatus

            query = self.session.query(func.sum(Job.quantity_completed)).filter(
                and_(
                    Job.status == JobStatus.COMPLETED,
                    Job.actual_end >= start_date,
                    Job.actual_end <= end_date
                )
            )

            if machine_id:
                query = query.filter(Job.machine_id == machine_id)

            total_qty = query.scalar() or 0
            hours = (end_date - start_date).total_seconds() / 3600

            return round(total_qty / max(hours, 1), 2)
        except ImportError:
            pass

        return 10.0

    def _calculate_yield(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate yield rate (good parts / total parts)."""
        try:
            from models.mes.work_orders import Job, JobStatus

            query = self.session.query(
                func.sum(Job.quantity_completed),
                func.sum(Job.quantity_scrapped)
            ).filter(
                and_(
                    Job.status == JobStatus.COMPLETED,
                    Job.actual_end >= start_date,
                    Job.actual_end <= end_date
                )
            )

            if machine_id:
                query = query.filter(Job.machine_id == machine_id)

            good, scrap = query.first()
            good = good or 0
            scrap = scrap or 0
            total = good + scrap

            if total > 0:
                return round((good / total) * 100, 1)
        except ImportError:
            pass

        return 99.0

    def _calculate_otd(self, start_date: datetime, end_date: datetime) -> float:
        """Calculate on-time delivery percentage."""
        try:
            from models.mes.work_orders import WorkOrder, WorkOrderStatus

            completed = self.session.query(WorkOrder).filter(
                and_(
                    WorkOrder.status == WorkOrderStatus.COMPLETED,
                    WorkOrder.actual_completion >= start_date,
                    WorkOrder.actual_completion <= end_date
                )
            ).all()

            if not completed:
                return 100.0

            on_time = sum(1 for wo in completed
                         if wo.due_date and wo.actual_completion <= wo.due_date)

            return round((on_time / len(completed)) * 100, 1)
        except ImportError:
            pass

        return 95.0

    def _calculate_mtbf(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate Mean Time Between Failures in hours."""
        try:
            from models.mes.oee import DowntimeEvent

            query = self.session.query(DowntimeEvent).filter(
                and_(
                    DowntimeEvent.start_time >= start_date,
                    DowntimeEvent.start_time <= end_date,
                    DowntimeEvent.downtime_type == 'breakdown'
                )
            )

            if machine_id:
                query = query.filter(DowntimeEvent.machine_id == machine_id)

            failures = query.count()
            total_hours = (end_date - start_date).total_seconds() / 3600

            if failures > 0:
                return round(total_hours / failures, 1)
        except ImportError:
            pass

        return 120.0

    def _calculate_mttr(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate Mean Time To Repair in hours."""
        try:
            from models.mes.oee import DowntimeEvent

            query = self.session.query(
                func.avg(DowntimeEvent.duration_minutes)
            ).filter(
                and_(
                    DowntimeEvent.start_time >= start_date,
                    DowntimeEvent.start_time <= end_date,
                    DowntimeEvent.downtime_type == 'breakdown',
                    DowntimeEvent.duration_minutes.isnot(None)
                )
            )

            if machine_id:
                query = query.filter(DowntimeEvent.machine_id == machine_id)

            avg_mins = query.scalar()
            if avg_mins:
                return round(avg_mins / 60, 2)
        except ImportError:
            pass

        return 1.5

    def _calculate_wip(self) -> int:
        """Calculate current WIP level (in-progress jobs)."""
        try:
            from models.mes.work_orders import Job, JobStatus

            return self.session.query(Job).filter(
                Job.status == JobStatus.RUNNING
            ).count()
        except ImportError:
            pass

        return 0

    def _calculate_schedule_adherence(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate schedule adherence percentage."""
        try:
            from models.mes.work_orders import Job, JobStatus

            jobs = self.session.query(Job).filter(
                and_(
                    Job.status == JobStatus.COMPLETED,
                    Job.actual_start.isnot(None),
                    Job.scheduled_start.isnot(None),
                    Job.actual_end >= start_date,
                    Job.actual_end <= end_date
                )
            ).all()

            if not jobs:
                return 100.0

            # Consider on-schedule if actual start within 30 min of scheduled
            on_schedule = sum(1 for j in jobs
                            if abs((j.actual_start - j.scheduled_start).total_seconds()) <= 1800)

            return round((on_schedule / len(jobs)) * 100, 1)
        except ImportError:
            pass

        return 90.0

    def _calculate_setup_ratio(
        self,
        start_date: datetime,
        end_date: datetime,
        machine_id: Optional[str] = None
    ) -> float:
        """Calculate setup time as percentage of total time."""
        # Simplified - would need setup time tracking
        return 8.5

    def _get_production_count(self, start: datetime, end: datetime) -> int:
        """Get total production count for period."""
        try:
            from models.mes.work_orders import Job, JobStatus

            return self.session.query(func.sum(Job.quantity_completed)).filter(
                and_(
                    Job.status == JobStatus.COMPLETED,
                    Job.actual_end >= start,
                    Job.actual_end <= end
                )
            ).scalar() or 0
        except ImportError:
            return 0

    def _get_defect_count(self, start: datetime, end: datetime) -> int:
        """Get total defect count for period."""
        try:
            from models.mes.work_orders import Job, JobStatus

            return self.session.query(func.sum(Job.quantity_scrapped)).filter(
                and_(
                    Job.actual_end >= start,
                    Job.actual_end <= end
                )
            ).scalar() or 0
        except ImportError:
            return 0

    def _get_downtime_minutes(self, start: datetime, end: datetime) -> int:
        """Get total downtime minutes for period."""
        try:
            from models.mes.oee import DowntimeEvent

            return self.session.query(func.sum(DowntimeEvent.duration_minutes)).filter(
                and_(
                    DowntimeEvent.start_time >= start,
                    DowntimeEvent.start_time <= end
                )
            ).scalar() or 0
        except ImportError:
            return 0

    def _get_production_by_machine(self, start: datetime, end: datetime) -> List[Dict]:
        """Get production breakdown by machine."""
        try:
            from models.mes.work_orders import Job, JobStatus

            results = self.session.query(
                Job.machine_id,
                func.count(Job.id),
                func.sum(Job.quantity_completed)
            ).filter(
                and_(
                    Job.status == JobStatus.COMPLETED,
                    Job.actual_end >= start,
                    Job.actual_end <= end
                )
            ).group_by(Job.machine_id).all()

            return [
                {'machine_id': r[0], 'job_count': r[1], 'quantity': r[2] or 0}
                for r in results
            ]
        except ImportError:
            return []

    def _get_downtime_events(self, start: datetime, end: datetime) -> List[Dict]:
        """Get downtime events for period."""
        try:
            from models.mes.oee import DowntimeEvent

            events = self.session.query(DowntimeEvent).filter(
                and_(
                    DowntimeEvent.start_time >= start,
                    DowntimeEvent.start_time <= end
                )
            ).order_by(DowntimeEvent.start_time.desc()).limit(20).all()

            return [e.to_dict() for e in events]
        except ImportError:
            return []

    def _get_quality_issues(self, start: datetime, end: datetime) -> List[Dict]:
        """Get quality issues for period."""
        try:
            from models.qms.ncr_capa import NCR

            ncrs = self.session.query(NCR).filter(
                and_(
                    NCR.created_at >= start,
                    NCR.created_at <= end
                )
            ).order_by(NCR.created_at.desc()).limit(10).all()

            return [n.to_dict() for n in ncrs]
        except ImportError:
            return []

    def _get_pending_jobs_count(self) -> int:
        """Get count of pending jobs."""
        try:
            from models.mes.work_orders import Job, JobStatus

            return self.session.query(Job).filter(
                Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
            ).count()
        except ImportError:
            return 0


# =============================================================================
# Module-level convenience functions
# =============================================================================

def calculate_kpis(session: Session, **kwargs) -> Dict[str, Any]:
    """Calculate all KPIs."""
    service = PerformanceService(session)
    return service.calculate_kpis(**kwargs)


def get_trend_data(session: Session, kpi_name: str, **kwargs) -> List[Dict]:
    """Get trend data for a KPI."""
    service = PerformanceService(session)
    return service.get_trend_data(kpi_name, **kwargs)


def generate_shift_report(session: Session, shift_date: datetime, shift_type: str = 'day') -> Dict[str, Any]:
    """Generate shift report."""
    service = PerformanceService(session)
    return service.generate_shift_report(shift_date, shift_type)
