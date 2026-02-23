"""
Capacity Planning & Bottleneck Analysis Service
================================================
Calculates load vs capacity and identifies constraint resources.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List

from services.cache.cache_service import cached


class CapacityService:
    def __init__(self, session):
        self.session = session

    def calculate_capacity(self, machine_id: str, period_days: int = 14) -> Dict[str, Any]:
        from models.scada.machines import Machine
        machine = self.session.query(Machine).filter(Machine.machine_id == machine_id).first()
        if not machine:
            return {'error': 'Machine not found'}
        shifts_per_day = 2
        hours_per_shift = 8
        planned_maintenance_hours = period_days * 0.5
        available_hours = (period_days * shifts_per_day * hours_per_shift) - planned_maintenance_hours
        return {
            'machine_id': machine_id, 'name': machine.name,
            'period_days': period_days,
            'available_hours': round(available_hours, 1),
            'shifts_per_day': shifts_per_day,
            'hours_per_shift': hours_per_shift,
            'planned_maintenance_hours': round(planned_maintenance_hours, 1),
        }

    def calculate_load(self, machine_id: str, period_days: int = 14) -> Dict[str, Any]:
        from models.mes.work_orders import Job, JobStatus
        cutoff = datetime.utcnow() + timedelta(days=period_days)
        jobs = self.session.query(Job).filter(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.scheduled_start <= cutoff
        ).all()
        def _job_duration_mins(j):
            if j.scheduled_start and j.scheduled_end:
                return (j.scheduled_end - j.scheduled_start).total_seconds() / 60
            return 60  # default 1 hour
        total_hours = sum(_job_duration_mins(j) / 60 for j in jobs)
        return {
            'machine_id': machine_id,
            'scheduled_hours': round(total_hours, 1),
            'job_count': len(jobs),
            'period_days': period_days,
        }

    @cached(ttl=120, prefix='capacity_forecast')
    def get_utilization_forecast(self, period_days: int = 14, limit: int = 100) -> List[Dict[str, Any]]:
        from models.scada.machines import Machine
        machines = self.session.query(Machine).filter(
            Machine.enabled == True
        ).order_by(Machine.machine_id).limit(limit).all()
        results = []
        for m in machines:
            cap = self.calculate_capacity(m.machine_id, period_days)
            load = self.calculate_load(m.machine_id, period_days)
            avail = cap.get('available_hours', 1) or 1
            util_pct = round(load.get('scheduled_hours', 0) / avail * 100, 1)
            results.append({
                'machine_id': m.machine_id, 'name': m.name,
                'available_hours': cap.get('available_hours', 0),
                'scheduled_hours': load.get('scheduled_hours', 0),
                'utilization_pct': min(util_pct, 999),
                'job_count': load.get('job_count', 0),
                'status': 'overloaded' if util_pct > 100 else 'high' if util_pct > 85 else 'normal' if util_pct > 50 else 'low',
            })
        return sorted(results, key=lambda x: x['utilization_pct'], reverse=True)

    def identify_bottlenecks(self, period_days: int = 14) -> List[Dict[str, Any]]:
        forecast = self.get_utilization_forecast(period_days)
        return [m for m in forecast if m['utilization_pct'] > 85]
