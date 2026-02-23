"""
PM Calendar View & Scheduling Integration Service
===================================================
Visual calendar for preventive maintenance with production scheduling integration.

Enhanced Features:
- Production schedule integration (avoid PM during peak production)
- PM clustering to minimize production interruption
- Dynamic interval adjustment based on actual condition
- Resource leveling for maintenance crews
- Compliance tracking and overdue alerts
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from calendar import monthrange
from collections import defaultdict

logger = logging.getLogger(__name__)


class PMPriority(str, Enum):
    """PM task priority levels."""
    CRITICAL = 'critical'  # Safety-related, must not be delayed
    HIGH = 'high'  # Important for reliability
    MEDIUM = 'medium'  # Standard PM
    LOW = 'low'  # Can be deferred if needed


class ComplianceStatus(str, Enum):
    """PM compliance status."""
    ON_TIME = 'on_time'  # Completed within tolerance
    LATE = 'late'  # Completed but overdue
    OVERDUE = 'overdue'  # Not yet completed, past due
    UPCOMING = 'upcoming'  # Scheduled, not yet due


@dataclass
class PMTask:
    """Preventive maintenance task."""
    task_id: str
    machine_id: str
    machine_name: str
    task_type: str
    scheduled_date: datetime
    priority: PMPriority
    estimated_duration_hours: float
    required_skills: List[str] = field(default_factory=list)
    required_parts: List[Dict[str, Any]] = field(default_factory=list)
    assigned_technician: str = None
    status: str = 'scheduled'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'machine_id': self.machine_id,
            'machine_name': self.machine_name,
            'task_type': self.task_type,
            'scheduled_date': self.scheduled_date.isoformat(),
            'priority': self.priority.value,
            'estimated_duration_hours': self.estimated_duration_hours,
            'required_skills': self.required_skills,
            'assigned_technician': self.assigned_technician,
            'status': self.status,
        }


@dataclass
class ResourceCapacity:
    """Maintenance crew resource capacity."""
    date: date
    available_hours: float
    allocated_hours: float
    technician_count: int
    tasks_assigned: int

    @property
    def utilization(self) -> float:
        return self.allocated_hours / self.available_hours if self.available_hours > 0 else 0

    @property
    def remaining_hours(self) -> float:
        return max(0, self.available_hours - self.allocated_hours)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date.isoformat(),
            'available_hours': self.available_hours,
            'allocated_hours': self.allocated_hours,
            'remaining_hours': self.remaining_hours,
            'utilization_pct': round(self.utilization * 100, 1),
            'technician_count': self.technician_count,
            'tasks_assigned': self.tasks_assigned,
        }


class PMCalendarService:
    """
    PM Calendar service with production integration.

    Features:
    - Calendar view of maintenance events
    - Production schedule conflict detection
    - PM clustering for efficiency
    - Resource leveling
    - Compliance tracking
    """

    def __init__(self, session):
        self.session = session
        self._resource_capacity: Dict[date, ResourceCapacity] = {}

    def get_calendar_events(self, year: int = None, month: int = None,
                            machine_id: str = None) -> Dict[str, Any]:
        """Get PM events for a calendar month."""
        from models.scada.machines import Machine

        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
        _, days_in_month = monthrange(year, month)

        machines = self.session.query(Machine).filter(Machine.enabled == True)
        if machine_id:
            machines = machines.filter(Machine.machine_id == machine_id)
        machines = machines.all()

        events = []
        for m in machines:
            if m.next_maintenance:
                maint_date = m.next_maintenance
                if maint_date.year == year and maint_date.month == month:
                    is_overdue = maint_date < now
                    events.append({
                        'machine_id': m.machine_id,
                        'machine_name': m.name,
                        'date': maint_date.isoformat(),
                        'day': maint_date.day,
                        'type': 'preventive',
                        'status': 'overdue' if is_overdue else 'scheduled',
                        'color': 'red' if is_overdue else 'blue',
                    })
        return {
            'year': year, 'month': month,
            'days_in_month': days_in_month,
            'events': sorted(events, key=lambda x: x['day']),
            'total_events': len(events),
            'overdue_count': len([e for e in events if e['status'] == 'overdue']),
        }

    def check_scheduling_conflict(self, machine_id: str, proposed_date: datetime) -> Dict[str, Any]:
        """Check if proposed PM date conflicts with production schedule."""
        from models.mes.work_orders import Job, JobStatus

        window_start = proposed_date - timedelta(hours=4)
        window_end = proposed_date + timedelta(hours=4)

        conflicts = self.session.query(Job).filter(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.scheduled_start <= window_end,
            Job.scheduled_end >= window_start
        ).all()

        return {
            'machine_id': machine_id,
            'proposed_date': proposed_date.isoformat(),
            'has_conflict': len(conflicts) > 0,
            'conflicting_jobs': len(conflicts),
            'recommendation': 'Reschedule PM' if conflicts else 'No conflicts',
        }

    def auto_schedule_pm(self, machine_id: str, preferred_shift: str = 'night') -> Dict[str, Any]:
        """Find the lowest-impact window for PM."""
        from models.mes.work_orders import Job, JobStatus

        best_date = None
        for day_offset in range(1, 15):
            candidate = datetime.utcnow() + timedelta(days=day_offset)
            if preferred_shift == 'night':
                candidate = candidate.replace(hour=22, minute=0)
            else:
                candidate = candidate.replace(hour=6, minute=0)
            conflict = self.check_scheduling_conflict(machine_id, candidate)
            if not conflict['has_conflict']:
                best_date = candidate
                break

        if best_date:
            return {'machine_id': machine_id, 'scheduled_date': best_date.isoformat(), 'status': 'scheduled'}
        return {'machine_id': machine_id, 'status': 'no_available_window', 'message': 'All windows have conflicts'}

    # ==================== Production Integration ====================

    def get_production_load(
        self,
        start_date: date,
        end_date: date,
        machine_id: str = None
    ) -> Dict[str, Any]:
        """
        Get production load for scheduling PM during low-load periods.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            machine_id: Optional machine filter

        Returns:
            Daily production load with recommended PM windows
        """
        from models.mes.work_orders import Job, JobStatus

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = self.session.query(Job).filter(
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.scheduled_start <= end_dt,
            Job.scheduled_end >= start_dt
        )

        if machine_id:
            query = query.filter(Job.machine_id == machine_id)

        jobs = query.all()

        # Calculate daily load
        daily_load = {}
        current = start_date
        while current <= end_date:
            daily_load[current.isoformat()] = {
                'date': current.isoformat(),
                'job_count': 0,
                'scheduled_hours': 0,
                'load_level': 'low',
                'pm_window': True
            }
            current += timedelta(days=1)

        for job in jobs:
            job_date = job.scheduled_start.date().isoformat()
            if job_date in daily_load:
                daily_load[job_date]['job_count'] += 1
                if job.scheduled_end and job.scheduled_start:
                    hours = (job.scheduled_end - job.scheduled_start).total_seconds() / 3600
                    daily_load[job_date]['scheduled_hours'] += hours

        # Determine load levels and PM windows
        for day_data in daily_load.values():
            hours = day_data['scheduled_hours']
            if hours >= 20:  # High load (>20 hours)
                day_data['load_level'] = 'high'
                day_data['pm_window'] = False
            elif hours >= 12:  # Medium load
                day_data['load_level'] = 'medium'
                day_data['pm_window'] = True  # PM possible but not ideal
            else:
                day_data['load_level'] = 'low'
                day_data['pm_window'] = True

        # Find best PM windows
        best_windows = [
            d for d in daily_load.values()
            if d['load_level'] == 'low'
        ]

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'machine_id': machine_id,
            'daily_load': list(daily_load.values()),
            'best_pm_windows': best_windows[:5],  # Top 5 windows
            'summary': {
                'high_load_days': len([d for d in daily_load.values() if d['load_level'] == 'high']),
                'medium_load_days': len([d for d in daily_load.values() if d['load_level'] == 'medium']),
                'low_load_days': len([d for d in daily_load.values() if d['load_level'] == 'low']),
            }
        }

    def schedule_pm_with_production(
        self,
        machine_id: str,
        pm_duration_hours: float = 4,
        priority: PMPriority = PMPriority.MEDIUM,
        within_days: int = 14
    ) -> Dict[str, Any]:
        """
        Schedule PM considering production load.

        Finds the optimal window with minimum production impact.

        Args:
            machine_id: Machine identifier
            pm_duration_hours: Estimated PM duration
            priority: PM priority level
            within_days: Schedule within this many days

        Returns:
            Scheduled PM with production impact analysis
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=within_days)

        # Get production load
        load = self.get_production_load(start_date, end_date, machine_id)

        # Find best window based on priority
        candidates = []
        for day_data in load['daily_load']:
            if priority == PMPriority.CRITICAL:
                # Critical PMs can override production
                candidates.append(day_data)
            elif day_data['pm_window']:
                candidates.append(day_data)

        if not candidates:
            return {
                'machine_id': machine_id,
                'status': 'no_window',
                'message': f'No suitable PM window found within {within_days} days'
            }

        # Sort by load (lowest first for non-critical)
        if priority != PMPriority.CRITICAL:
            candidates.sort(key=lambda x: x['scheduled_hours'])

        best_day = candidates[0]

        # Determine shift (prefer night/weekend for medium+ priority)
        if priority in (PMPriority.HIGH, PMPriority.CRITICAL):
            scheduled_time = datetime.fromisoformat(best_day['date']).replace(hour=6)  # Early morning
        else:
            scheduled_time = datetime.fromisoformat(best_day['date']).replace(hour=22)  # Night shift

        return {
            'machine_id': machine_id,
            'scheduled_date': scheduled_time.isoformat(),
            'priority': priority.value,
            'estimated_duration_hours': pm_duration_hours,
            'production_impact': {
                'day_load_level': best_day['load_level'],
                'scheduled_production_hours': best_day['scheduled_hours'],
                'jobs_affected': best_day['job_count'],
            },
            'status': 'scheduled',
            'alternatives': [c['date'] for c in candidates[1:4]]  # Next 3 alternatives
        }

    # ==================== PM Clustering ====================

    def cluster_pm_tasks(
        self,
        machine_ids: List[str],
        clustering_window_days: int = 3
    ) -> Dict[str, Any]:
        """
        Cluster PM tasks for related machines to minimize disruption.

        Groups PMs for machines in the same area/cell to reduce
        total downtime and travel time.

        Args:
            machine_ids: List of machine identifiers
            clustering_window_days: Group PMs within this window

        Returns:
            Clustered PM schedule
        """
        from models.scada.machines import Machine

        machines = self.session.query(Machine).filter(
            Machine.machine_id.in_(machine_ids),
            Machine.enabled == True
        ).all()

        # Get PM due dates
        pm_dates = []
        for m in machines:
            if m.next_maintenance:
                pm_dates.append({
                    'machine_id': m.machine_id,
                    'machine_name': m.name,
                    'original_date': m.next_maintenance,
                    'location': getattr(m, 'location', 'default'),
                })

        if not pm_dates:
            return {'clusters': [], 'message': 'No PM tasks to cluster'}

        # Sort by date
        pm_dates.sort(key=lambda x: x['original_date'])

        # Create clusters
        clusters = []
        current_cluster = None

        for pm in pm_dates:
            if current_cluster is None:
                current_cluster = {
                    'cluster_id': f"CLU-{len(clusters) + 1:03d}",
                    'cluster_date': pm['original_date'].date(),
                    'machines': [pm],
                    'location': pm['location']
                }
            elif (pm['original_date'].date() - current_cluster['cluster_date']).days <= clustering_window_days:
                current_cluster['machines'].append(pm)
            else:
                clusters.append(current_cluster)
                current_cluster = {
                    'cluster_id': f"CLU-{len(clusters) + 1:03d}",
                    'cluster_date': pm['original_date'].date(),
                    'machines': [pm],
                    'location': pm['location']
                }

        if current_cluster:
            clusters.append(current_cluster)

        # Calculate cluster statistics
        for cluster in clusters:
            cluster['machine_count'] = len(cluster['machines'])
            cluster['cluster_date'] = cluster['cluster_date'].isoformat()
            cluster['machines'] = [
                {
                    'machine_id': m['machine_id'],
                    'machine_name': m['machine_name'],
                    'original_date': m['original_date'].isoformat(),
                }
                for m in cluster['machines']
            ]

        return {
            'total_machines': len(pm_dates),
            'cluster_count': len(clusters),
            'clusters': clusters,
            'efficiency_gain': f"{(1 - len(clusters) / len(pm_dates)) * 100:.1f}%" if pm_dates else "0%"
        }

    # ==================== Resource Leveling ====================

    def get_resource_capacity(
        self,
        start_date: date,
        end_date: date,
        technicians_per_day: int = 3,
        hours_per_technician: float = 8.0
    ) -> Dict[str, Any]:
        """
        Get and manage maintenance crew capacity.

        Args:
            start_date: Start of planning period
            end_date: End of planning period
            technicians_per_day: Available technicians
            hours_per_technician: Hours per technician per day

        Returns:
            Daily resource capacity and allocation
        """
        daily_capacity = []
        current = start_date

        while current <= end_date:
            # Check if weekend (reduced capacity)
            is_weekend = current.weekday() >= 5
            available_techs = 1 if is_weekend else technicians_per_day
            available_hours = available_techs * hours_per_technician

            # Get allocated hours from existing PM tasks in DB
            from models.cmms.maintenance import PMTask as PMTaskModel
            from sqlalchemy import func
            result = self.session.query(
                func.coalesce(func.sum(PMTaskModel.duration_hours), 0),
                func.count(PMTaskModel.id)
            ).filter(PMTaskModel.scheduled_date == current).first()
            allocated = float(result[0])
            tasks_count = int(result[1])

            capacity = ResourceCapacity(
                date=current,
                available_hours=available_hours,
                allocated_hours=allocated,
                technician_count=available_techs,
                tasks_assigned=tasks_count
            )

            self._resource_capacity[current] = capacity
            daily_capacity.append(capacity.to_dict())

            current += timedelta(days=1)

        # Find overloaded days
        overloaded = [d for d in daily_capacity if d['utilization_pct'] > 100]

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'daily_capacity': daily_capacity,
            'overloaded_days': overloaded,
            'summary': {
                'avg_utilization': round(sum(d['utilization_pct'] for d in daily_capacity) / len(daily_capacity), 1),
                'overloaded_count': len(overloaded),
                'total_available_hours': sum(d['available_hours'] for d in daily_capacity),
                'total_allocated_hours': sum(d['allocated_hours'] for d in daily_capacity),
            }
        }

    def level_resources(
        self,
        start_date: date,
        end_date: date,
        max_utilization: float = 0.85
    ) -> Dict[str, Any]:
        """
        Level PM workload across available resources.

        Reschedules PMs to balance workload and avoid overload.

        Args:
            start_date: Start of planning period
            end_date: End of planning period
            max_utilization: Maximum target utilization

        Returns:
            Leveled schedule with changes
        """
        # Get current capacity
        capacity = self.get_resource_capacity(start_date, end_date)

        changes = []
        overloaded_days = [
            d for d in capacity['daily_capacity']
            if d['utilization_pct'] > max_utilization * 100
        ]

        underloaded_days = [
            d for d in capacity['daily_capacity']
            if d['utilization_pct'] < max_utilization * 100 * 0.5  # <50% of target
        ]

        # Move tasks from overloaded to underloaded days
        for overloaded in overloaded_days:
            excess_hours = overloaded['allocated_hours'] - (overloaded['available_hours'] * max_utilization)

            # Find tasks on this day from DB
            from models.cmms.maintenance import PMTask as PMTaskModel
            day_date = date.fromisoformat(overloaded['date'])
            db_tasks = self.session.query(PMTaskModel).filter(
                PMTaskModel.scheduled_date == day_date
            ).all()

            # Convert to dataclass for priority sorting
            priority_order = {
                PMPriority.LOW: 0, 'low': 0,
                PMPriority.MEDIUM: 1, 'medium': 1,
                PMPriority.HIGH: 2, 'high': 2,
                PMPriority.CRITICAL: 3, 'critical': 3,
            }
            day_tasks = []
            for t in db_tasks:
                day_tasks.append(PMTask(
                    task_id=str(t.id),
                    machine_id=t.machine_id,
                    machine_name=t.machine_id,
                    task_type=t.task_name,
                    scheduled_date=datetime.combine(t.scheduled_date, datetime.min.time()),
                    priority=PMPriority(t.priority) if t.priority in [p.value for p in PMPriority] else PMPriority.MEDIUM,
                    estimated_duration_hours=t.duration_hours or 1.0,
                ))
            day_tasks.sort(key=lambda t: priority_order.get(t.priority, 1))

            hours_to_move = excess_hours
            for task in day_tasks:
                if hours_to_move <= 0:
                    break

                if task.priority == PMPriority.CRITICAL:
                    continue  # Don't move critical tasks

                # Find best underloaded day
                for underloaded in underloaded_days:
                    ul_date = date.fromisoformat(underloaded['date'])
                    if underloaded['remaining_hours'] >= task.estimated_duration_hours:
                        # Move task
                        changes.append({
                            'task_id': task.task_id,
                            'machine_id': task.machine_id,
                            'original_date': task.scheduled_date.isoformat(),
                            'new_date': datetime.combine(ul_date, task.scheduled_date.time()).isoformat(),
                            'reason': 'resource_leveling'
                        })
                        hours_to_move -= task.estimated_duration_hours
                        underloaded['allocated_hours'] += task.estimated_duration_hours
                        break

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'changes_made': len(changes),
            'changes': changes,
            'original_overloaded_days': len(overloaded_days),
            'summary': {
                'tasks_rescheduled': len(changes),
                'overloaded_days_resolved': len(overloaded_days) - len([
                    d for d in overloaded_days
                    if d['utilization_pct'] > max_utilization * 100
                ]),
            }
        }

    # ==================== Compliance Tracking ====================

    def get_compliance_status(
        self,
        machine_id: str = None,
        period_days: int = 90
    ) -> Dict[str, Any]:
        """
        Get PM compliance status and metrics.

        Tracks on-time completion rate and identifies overdue PMs.

        Args:
            machine_id: Optional machine filter
            period_days: Analysis period

        Returns:
            Compliance metrics and overdue list
        """
        from models.scada.machines import Machine
        from models.cmms.maintenance import WorkOrder, WorkOrderStatus

        now = datetime.utcnow()
        cutoff = now - timedelta(days=period_days)

        # Get machines
        query = self.session.query(Machine).filter(Machine.enabled == True)
        if machine_id:
            query = query.filter(Machine.machine_id == machine_id)
        machines = query.all()

        # Analyze compliance
        compliance_data = []
        total_scheduled = 0
        on_time = 0
        late = 0
        overdue = []

        for m in machines:
            if not m.next_maintenance:
                continue

            total_scheduled += 1
            pm_date = m.next_maintenance
            days_until_due = (pm_date - now).days

            if days_until_due < 0:
                # Overdue
                status = ComplianceStatus.OVERDUE
                days_overdue = abs(days_until_due)
                overdue.append({
                    'machine_id': m.machine_id,
                    'machine_name': m.name,
                    'due_date': pm_date.isoformat(),
                    'days_overdue': days_overdue,
                    'priority': 'critical' if days_overdue > 30 else 'high' if days_overdue > 14 else 'medium'
                })
            elif days_until_due <= 7:
                status = ComplianceStatus.UPCOMING
            else:
                status = ComplianceStatus.ON_TIME
                on_time += 1

            compliance_data.append({
                'machine_id': m.machine_id,
                'machine_name': m.name,
                'due_date': pm_date.isoformat(),
                'days_until_due': days_until_due,
                'status': status.value,
            })

        # Calculate compliance rate
        compliance_rate = on_time / total_scheduled * 100 if total_scheduled > 0 else 100

        # Sort overdue by severity
        overdue.sort(key=lambda x: x['days_overdue'], reverse=True)

        return {
            'machine_id': machine_id,
            'period_days': period_days,
            'compliance_data': compliance_data,
            'overdue': overdue,
            'metrics': {
                'total_scheduled': total_scheduled,
                'on_time': on_time,
                'overdue_count': len(overdue),
                'compliance_rate': round(compliance_rate, 1),
                'avg_days_overdue': round(sum(o['days_overdue'] for o in overdue) / len(overdue), 1) if overdue else 0,
            },
            'status': 'critical' if compliance_rate < 80 else 'warning' if compliance_rate < 90 else 'good'
        }

    # ==================== Dynamic Interval Adjustment ====================

    def adjust_pm_interval(
        self,
        machine_id: str,
        current_interval_days: int,
        health_score: float = None,
        recent_failures: int = None
    ) -> Dict[str, Any]:
        """
        Dynamically adjust PM interval based on machine condition.

        Uses condition data and failure history to optimize interval.

        Args:
            machine_id: Machine identifier
            current_interval_days: Current PM interval
            health_score: CBM health score (0-100)
            recent_failures: Number of recent failures

        Returns:
            Recommended interval adjustment
        """
        adjustment_factor = 1.0
        reasons = []

        # Adjust based on health score
        if health_score is not None:
            if health_score >= 90:
                adjustment_factor *= 1.2  # Extend interval 20%
                reasons.append(f"Excellent health ({health_score}%): extend interval")
            elif health_score >= 70:
                adjustment_factor *= 1.0  # Keep interval
                reasons.append(f"Good health ({health_score}%): maintain interval")
            elif health_score >= 50:
                adjustment_factor *= 0.8  # Reduce interval 20%
                reasons.append(f"Fair health ({health_score}%): reduce interval")
            else:
                adjustment_factor *= 0.5  # Reduce interval 50%
                reasons.append(f"Poor health ({health_score}%): significantly reduce interval")

        # Adjust based on failure history
        if recent_failures is not None:
            if recent_failures == 0:
                adjustment_factor *= 1.1
                reasons.append("No recent failures: slight extension")
            elif recent_failures <= 2:
                pass  # No change
            elif recent_failures <= 5:
                adjustment_factor *= 0.8
                reasons.append(f"{recent_failures} failures: reduce interval")
            else:
                adjustment_factor *= 0.6
                reasons.append(f"{recent_failures} failures: significantly reduce interval")

        # Calculate new interval
        new_interval = int(current_interval_days * adjustment_factor)

        # Apply bounds (7 days minimum, 180 days maximum)
        new_interval = max(7, min(180, new_interval))

        return {
            'machine_id': machine_id,
            'current_interval_days': current_interval_days,
            'recommended_interval_days': new_interval,
            'adjustment_factor': round(adjustment_factor, 2),
            'change_days': new_interval - current_interval_days,
            'change_percent': round((new_interval - current_interval_days) / current_interval_days * 100, 1),
            'reasons': reasons,
            'recommendation': (
                'extend' if new_interval > current_interval_days else
                'reduce' if new_interval < current_interval_days else
                'maintain'
            )
        }
