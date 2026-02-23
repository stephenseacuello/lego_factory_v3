"""
LEGO Factory v3 - Scheduling Service
====================================
Job scheduling using constraint programming (CP-SAT solver).
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# SETUP TIME MATRIX
# =============================================================================
# Setup time (minutes) to switch between materials/products on the same machine.
# Key: (from_material, to_material) or (from_product_type, to_product_type)
# Value: setup time in minutes

MATERIAL_SETUP_MATRIX = {
    # FDM Material Changes (requires purging and temp changes)
    ('ABS', 'ABS'): 0,      # Same material, no change
    ('ABS', 'PLA'): 15,     # Need to cool bed and nozzle
    ('ABS', 'PETG'): 10,    # Similar temps
    ('ABS', 'TPU'): 20,     # Flexible requires slower speeds
    ('PLA', 'PLA'): 0,
    ('PLA', 'ABS'): 15,     # Need to heat bed and nozzle
    ('PLA', 'PETG'): 8,     # Slight temp increase
    ('PLA', 'TPU'): 15,
    ('PETG', 'PETG'): 0,
    ('PETG', 'ABS'): 10,
    ('PETG', 'PLA'): 8,
    ('PETG', 'TPU'): 15,
    ('TPU', 'TPU'): 0,
    ('TPU', 'ABS'): 20,
    ('TPU', 'PLA'): 15,
    ('TPU', 'PETG'): 15,

    # CNC Material Changes (requires workholding and tool changes)
    ('ALU', 'ALU'): 5,      # May need fixture adjustment
    ('ALU', 'BRS'): 10,     # Different feeds/speeds
    ('ALU', 'SST'): 15,     # Requires coolant, slower speeds
    ('BRS', 'BRS'): 5,
    ('BRS', 'ALU'): 10,
    ('BRS', 'SST'): 15,
    ('SST', 'SST'): 5,
    ('SST', 'ALU'): 15,
    ('SST', 'BRS'): 15,

    # Cross-process defaults (shouldn't happen, but safety fallback)
    ('_default', '_default'): 10,
}

# Machine-specific setup time factors
MACHINE_SETUP_FACTORS = {
    'bambu-ps1': 1.0,         # Fast material changes with AMS
    'creality-cr30': 1.5,     # Manual filament change
    'formlabs-3': 2.0,        # Resin change is slow
    'bantam-explorer': 1.0,   # Standard CNC
    'coastrunner-cr1': 1.2,   # Larger machine
    'longer-ray-laser': 0.5,  # Quick material swap
    'software': 0.0,          # No physical setup
}

# Part type/size setup factors (fixture changes, etc.)
PART_SIZE_SETUP = {
    'small': 0,     # < 4 studs total
    'medium': 2,    # 4-16 studs
    'large': 5,     # > 16 studs
}


@dataclass
class ScheduleJob:
    """Job to be scheduled."""
    job_id: str
    work_order_id: str
    duration_minutes: int
    machine_id: str = None  # Preferred machine
    eligible_machines: List[str] = field(default_factory=list)
    priority: int = 5
    due_date: datetime = None
    dependencies: List[str] = field(default_factory=list)  # Jobs that must complete first
    setup_time: int = 0
    earliest_start: datetime = None
    # Skill-based scheduling constraints
    required_skill: str = None  # Required skill code for this job
    required_skill_level: int = 1  # Minimum skill level (1-5)
    assigned_worker_id: str = None  # Pre-assigned worker (optional)


@dataclass
class Worker:
    """Worker resource with skills."""
    worker_id: str
    name: str
    skills: Dict[str, int] = field(default_factory=dict)  # skill_code -> level (1-5)
    certifications: List[Dict[str, Any]] = field(default_factory=list)
    available_from: datetime = None
    available_until: datetime = None
    shift_id: str = None
    efficiency: float = 1.0  # Worker efficiency factor


@dataclass
class Machine:
    """Machine resource."""
    machine_id: str
    name: str
    capabilities: List[str] = field(default_factory=list)
    available_from: datetime = None
    available_until: datetime = None
    efficiency: float = 1.0  # 0-1 scale


@dataclass
class ScheduledJob:
    """Scheduled job result."""
    job_id: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    setup_time: int = 0
    worker_id: str = None  # Assigned worker (for skill-based scheduling)


@dataclass
class ScheduleResult:
    """Complete schedule result."""
    scheduled_jobs: List[ScheduledJob]
    makespan_minutes: int
    total_setup_time: int
    utilization: Dict[str, float]
    unscheduled_jobs: List[str] = field(default_factory=list)
    solver_status: str = "optimal"


@dataclass
class ScheduleVariance:
    """Variance between planned and actual schedule."""
    job_id: str
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    start_variance_minutes: Optional[float]  # Positive = late start
    end_variance_minutes: Optional[float]  # Positive = late finish
    duration_variance_minutes: Optional[float]  # Positive = took longer
    variance_severity: str  # 'on_time', 'minor', 'major', 'critical'


@dataclass
class WhatIfScenario:
    """What-if scenario definition for schedule simulation."""
    scenario_id: str
    name: str
    description: str
    changes: List[Dict[str, Any]]  # List of changes to apply
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WhatIfResult:
    """Result of a what-if scenario simulation."""
    scenario_id: str
    original_schedule: ScheduleResult
    modified_schedule: ScheduleResult
    makespan_delta: int  # Minutes difference
    utilization_delta: Dict[str, float]
    jobs_affected: List[str]
    recommendations: List[str]


class SchedulingService:
    """
    Job scheduling service using CP-SAT solver.

    Supports:
    - Machine assignment
    - Job sequencing
    - Setup time optimization
    - Due date constraints
    - Priority-based scheduling
    - Skill-based labor constraints
    - Multi-resource operations (machine + worker)
    """

    def __init__(self, session: Session = None):
        self.session = session
        self._worker_cache: Dict[str, Worker] = {}

    def schedule_jobs(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int = 24,
        objective: str = 'makespan',  # 'makespan', 'due_date', 'setup_time'
        workers: List[Worker] = None
    ) -> ScheduleResult:
        """
        Schedule jobs across machines with optional worker constraints.

        Uses Google OR-Tools CP-SAT solver when available,
        falls back to priority-based heuristic otherwise.

        Args:
            jobs: List of jobs to schedule
            machines: Available machines
            horizon_hours: Planning horizon
            objective: Optimization objective
            workers: Optional list of workers for skill-based scheduling
        """
        workers = workers or []

        # For setup_time objective, sort jobs to group similar materials on
        # the same machine then use the heuristic (material grouping is more
        # effective than CP-SAT for changeover minimisation in practice).
        if objective == 'setup_time':
            jobs_sorted = sorted(jobs, key=lambda j: (
                getattr(j, 'material_type', '') or '',
                j.priority,
                j.job_id,
            ))
            return self._schedule_heuristic(jobs_sorted, machines, horizon_hours, workers)

        try:
            return self._schedule_cpsat(jobs, machines, horizon_hours, objective, workers)
        except ImportError:
            logger.warning("OR-Tools not available, using heuristic scheduler")
            return self._schedule_heuristic(jobs, machines, horizon_hours, workers)

    def _get_eligible_workers(
        self,
        workers: List[Worker],
        required_skill: str,
        required_level: int = 1
    ) -> List[Worker]:
        """
        Get workers eligible for a job based on skill requirements.

        Args:
            workers: List of available workers
            required_skill: Skill code required
            required_level: Minimum skill level (1-5)

        Returns:
            List of eligible workers
        """
        eligible = []
        for worker in workers:
            worker_level = worker.skills.get(required_skill, 0)
            if worker_level >= required_level:
                # Check certifications aren't expired
                cert_valid = True
                for cert in worker.certifications:
                    if cert.get('skill') == required_skill:
                        expiry = cert.get('expiry_date')
                        if expiry and datetime.fromisoformat(expiry) < datetime.utcnow():
                            cert_valid = False
                            break
                if cert_valid:
                    eligible.append(worker)
        return eligible

    def get_workers_for_skill(self, skill_code: str, min_level: int = 1) -> List[Dict[str, Any]]:
        """
        Get all workers with a specific skill at or above minimum level.

        Args:
            skill_code: Skill code to search for
            min_level: Minimum skill level required

        Returns:
            List of worker info dicts
        """
        if not self.session:
            return []

        try:
            from models.mes.resources import WorkerResource

            workers = self.session.query(WorkerResource).filter(
                WorkerResource.is_active == True
            ).all()

            result = []
            for worker in workers:
                skills = worker.skills or {}
                level = skills.get(skill_code, 0)
                if level >= min_level:
                    result.append({
                        'worker_id': worker.worker_id,
                        'name': worker.name,
                        'skill_level': level,
                        'shift_id': worker.shift_id,
                        'efficiency': worker.efficiency
                    })
            return result
        except ImportError:
            return []

    def _schedule_cpsat(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int,
        objective: str,
        workers: List[Worker] = None
    ) -> ScheduleResult:
        """Schedule using CP-SAT solver with optional skill-based worker constraints."""
        from ortools.sat.python import cp_model

        workers = workers or []
        model = cp_model.CpModel()
        horizon = horizon_hours * 60  # Convert to minutes

        # Create variables
        job_vars = {}
        machine_assignments = {}
        worker_assignments = {}

        for job in jobs:
            # Start time variable
            start_var = model.NewIntVar(0, horizon - job.duration_minutes, f'start_{job.job_id}')
            end_var = model.NewIntVar(0, horizon, f'end_{job.job_id}')
            job_vars[job.job_id] = {'start': start_var, 'end': end_var, 'worker': None}

            # Duration constraint
            model.Add(end_var == start_var + job.duration_minutes)

            # Machine assignment
            eligible = job.eligible_machines or [m.machine_id for m in machines]
            for m_id in eligible:
                machine_assignments[(job.job_id, m_id)] = model.NewBoolVar(f'assign_{job.job_id}_{m_id}')

            # Must be assigned to exactly one machine
            model.Add(sum(machine_assignments.get((job.job_id, m.machine_id), 0)
                        for m in machines if (job.job_id, m.machine_id) in machine_assignments) == 1)

            # Worker assignment (if job requires skill and workers are provided)
            if job.required_skill and workers:
                eligible_workers = self._get_eligible_workers(
                    workers, job.required_skill, job.required_skill_level
                )

                if eligible_workers:
                    for worker in eligible_workers:
                        worker_assignments[(job.job_id, worker.worker_id)] = model.NewBoolVar(
                            f'worker_{job.job_id}_{worker.worker_id}'
                        )

                    # Must be assigned to exactly one eligible worker
                    model.Add(sum(
                        worker_assignments.get((job.job_id, w.worker_id), 0)
                        for w in eligible_workers
                        if (job.job_id, w.worker_id) in worker_assignments
                    ) == 1)

                    job_vars[job.job_id]['worker'] = True
                else:
                    logger.warning(
                        f"No workers with skill {job.required_skill} level {job.required_skill_level} "
                        f"for job {job.job_id}"
                    )

        # No overlap on same machine
        for machine in machines:
            machine_intervals = []
            for job in jobs:
                if (job.job_id, machine.machine_id) in machine_assignments:
                    is_assigned = machine_assignments[(job.job_id, machine.machine_id)]
                    interval = model.NewOptionalIntervalVar(
                        job_vars[job.job_id]['start'],
                        job.duration_minutes,
                        job_vars[job.job_id]['end'],
                        is_assigned,
                        f'interval_{job.job_id}_{machine.machine_id}'
                    )
                    machine_intervals.append(interval)

            if machine_intervals:
                model.AddNoOverlap(machine_intervals)

        # No overlap on same worker (workers can only do one job at a time)
        for worker in workers:
            worker_intervals = []
            for job in jobs:
                if (job.job_id, worker.worker_id) in worker_assignments:
                    is_assigned = worker_assignments[(job.job_id, worker.worker_id)]
                    interval = model.NewOptionalIntervalVar(
                        job_vars[job.job_id]['start'],
                        job.duration_minutes,
                        job_vars[job.job_id]['end'],
                        is_assigned,
                        f'worker_interval_{job.job_id}_{worker.worker_id}'
                    )
                    worker_intervals.append(interval)

            if worker_intervals:
                model.AddNoOverlap(worker_intervals)

        # Dependencies
        for job in jobs:
            for dep_id in job.dependencies:
                if dep_id in job_vars:
                    model.Add(job_vars[job.job_id]['start'] >= job_vars[dep_id]['end'])

        # Objective
        if objective == 'makespan':
            makespan = model.NewIntVar(0, horizon, 'makespan')
            for job in jobs:
                model.Add(makespan >= job_vars[job.job_id]['end'])
            model.Minimize(makespan)
        elif objective == 'due_date':
            tardiness = []
            for job in jobs:
                if job.due_date:
                    due_minute = int((job.due_date - datetime.utcnow()).total_seconds() / 60)
                    late = model.NewIntVar(0, horizon, f'late_{job.job_id}')
                    model.Add(late >= job_vars[job.job_id]['end'] - due_minute)
                    tardiness.append(late * (10 - job.priority))
            if tardiness:
                model.Minimize(sum(tardiness))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            logger.warning(f"No feasible schedule found, status: {status}")
            return self._schedule_heuristic(jobs, machines, horizon_hours)

        # Extract results
        scheduled = []
        base_time = datetime.utcnow()

        for job in jobs:
            start_min = solver.Value(job_vars[job.job_id]['start'])
            end_min = solver.Value(job_vars[job.job_id]['end'])

            # Find assigned machine
            assigned_machine = None
            for m in machines:
                if (job.job_id, m.machine_id) in machine_assignments:
                    if solver.Value(machine_assignments[(job.job_id, m.machine_id)]):
                        assigned_machine = m.machine_id
                        break

            # Find assigned worker (if applicable)
            assigned_worker = None
            for w in workers:
                if (job.job_id, w.worker_id) in worker_assignments:
                    if solver.Value(worker_assignments[(job.job_id, w.worker_id)]):
                        assigned_worker = w.worker_id
                        break

            if assigned_machine:
                sched_job = ScheduledJob(
                    job_id=job.job_id,
                    machine_id=assigned_machine,
                    start_time=base_time + timedelta(minutes=start_min),
                    end_time=base_time + timedelta(minutes=end_min),
                    setup_time=job.setup_time
                )
                # Store worker assignment in job data
                if assigned_worker:
                    sched_job.worker_id = assigned_worker
                scheduled.append(sched_job)

        # Calculate metrics
        makespan = max((s.end_time - base_time).total_seconds() / 60 for s in scheduled) if scheduled else 0
        utilization = self._calculate_utilization(scheduled, machines, makespan)

        return ScheduleResult(
            scheduled_jobs=scheduled,
            makespan_minutes=int(makespan),
            total_setup_time=sum(j.setup_time for j in scheduled),
            utilization=utilization,
            solver_status='optimal' if status == cp_model.OPTIMAL else 'feasible'
        )

    def _schedule_heuristic(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int,
        workers: List[Worker] = None
    ) -> ScheduleResult:
        """Simple priority-based heuristic scheduler with skill-based worker constraints."""
        workers = workers or []

        # Sort by priority and due date
        sorted_jobs = sorted(jobs, key=lambda j: (j.priority, j.due_date or datetime.max))

        # Track machine and worker availability
        machine_available = {m.machine_id: datetime.utcnow() for m in machines}
        worker_available = {w.worker_id: datetime.utcnow() for w in workers}
        scheduled = []
        unscheduled = []

        # Load WIP limits for capacity-aware scheduling (MESA-1)
        wip_svc = None
        try:
            from services.mes.wip_service import WIPService
            if self.session:
                wip_svc = WIPService(self.session)
        except Exception:
            pass

        for job in sorted_jobs:
            eligible = job.eligible_machines or [m.machine_id for m in machines]
            eligible_available = [(m_id, machine_available[m_id])
                                   for m_id in eligible if m_id in machine_available]

            # Filter out machines at WIP limit
            if wip_svc:
                try:
                    eligible_available = [
                        (m_id, t) for m_id, t in eligible_available
                        if wip_svc.check_wip_limit(m_id).get('can_accept', True)
                    ]
                except Exception:
                    pass

            if not eligible_available:
                unscheduled.append(job.job_id)
                continue

            # Pick earliest available machine
            best_machine, machine_start = min(eligible_available, key=lambda x: x[1])

            # If job requires skill, find earliest available worker with that skill
            assigned_worker = None
            start_time = machine_start

            if job.required_skill and workers:
                eligible_workers = self._get_eligible_workers(
                    workers, job.required_skill, job.required_skill_level
                )
                if eligible_workers:
                    # Find earliest available eligible worker
                    worker_options = [
                        (w.worker_id, worker_available.get(w.worker_id, datetime.utcnow()))
                        for w in eligible_workers
                    ]
                    if worker_options:
                        assigned_worker, worker_start = min(worker_options, key=lambda x: x[1])
                        # Start time is max of machine and worker availability
                        start_time = max(machine_start, worker_start)
                else:
                    # No eligible workers - can't schedule
                    unscheduled.append(job.job_id)
                    continue

            end_time = start_time + timedelta(minutes=job.duration_minutes + job.setup_time)
            machine_available[best_machine] = end_time

            if assigned_worker:
                worker_available[assigned_worker] = end_time

            scheduled.append(ScheduledJob(
                job_id=job.job_id,
                machine_id=best_machine,
                start_time=start_time,
                end_time=end_time,
                setup_time=job.setup_time,
                worker_id=assigned_worker
            ))

        base_time = datetime.utcnow()
        makespan = max((s.end_time - base_time).total_seconds() / 60 for s in scheduled) if scheduled else 0
        utilization = self._calculate_utilization(scheduled, machines, makespan)

        return ScheduleResult(
            scheduled_jobs=scheduled,
            makespan_minutes=int(makespan),
            total_setup_time=sum(j.setup_time for j in scheduled),
            utilization=utilization,
            unscheduled_jobs=unscheduled,
            solver_status='heuristic'
        )

    def _calculate_utilization(
        self,
        scheduled: List[ScheduledJob],
        machines: List[Machine],
        makespan: float
    ) -> Dict[str, float]:
        """Calculate machine utilization."""
        if makespan <= 0:
            return {m.machine_id: 0.0 for m in machines}

        utilization = {}
        for machine in machines:
            machine_jobs = [j for j in scheduled if j.machine_id == machine.machine_id]
            busy_time = sum((j.end_time - j.start_time).total_seconds() / 60 for j in machine_jobs)
            utilization[machine.machine_id] = min(1.0, busy_time / makespan)

        return utilization

    def get_dispatch_queue(self, machine_id: str) -> List[Dict[str, Any]]:
        """Get ordered dispatch queue for a machine."""
        from models.mes.work_orders import Job, JobStatus

        if not self.session:
            return []

        jobs = self.session.query(Job).filter(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
        ).order_by(Job.priority_score.desc(), Job.scheduled_start).all()

        return [j.to_dict() for j in jobs]

    def get_gantt_data(self, hours_back: int = 24, hours_forward: int = 48) -> Dict[str, Any]:
        """
        Get Gantt chart data for scheduled jobs.

        Returns all physical machines and their scheduled jobs for display in a Gantt chart.
        """
        from models.mes.work_orders import Job, JobStatus, WorkOrder
        from sqlalchemy.orm import joinedload

        if not self.session:
            return {'machines': [], 'jobs': [], 'time_range': {}}

        now = datetime.utcnow()
        start_time = now - timedelta(hours=hours_back)
        end_time = now + timedelta(hours=hours_forward)

        # Load all physical machines from config/machines.json
        machines = self._load_physical_machines()

        from models.mes.work_orders import Operation

        # Query all jobs with scheduled times in the time range, eager-load work_order
        jobs = self.session.query(Job).options(
            joinedload(Job.work_order)
        ).filter(
            Job.scheduled_start != None,
            Job.scheduled_end != None,
            Job.scheduled_end >= start_time,
            Job.scheduled_start <= end_time
        ).order_by(Job.scheduled_start).all()

        # Status to color mapping
        status_colors = {
            'pending': '#6c757d',    # gray
            'queued': '#0dcaf0',     # cyan
            'running': '#0d6efd',    # blue
            'paused': '#17a2b8',     # teal
            'completed': '#198754',  # green
            'failed': '#dc3545',     # red
            'cancelled': '#6c757d',  # gray
        }

        # Build dependency map: for each operation, find the previous operation's job
        # Group jobs by (work_order_id, operation_id)
        op_to_job = {}   # operation UUID -> job_id
        job_op_ids = {}  # job_id -> operation UUID
        for job in jobs:
            if job.operation_id and job.job_id:
                op_to_job[str(job.operation_id)] = job.job_id
                job_op_ids[job.job_id] = str(job.operation_id)

        # Get all operations for these jobs to determine sequence ordering
        all_op_ids = [job.operation_id for job in jobs if job.operation_id]
        predecessor_map = {}  # job_id -> predecessor job_id
        if all_op_ids:
            ops = self.session.query(Operation).filter(
                Operation.work_order_id.in_([j.work_order_id for j in jobs])
            ).order_by(Operation.work_order_id, Operation.sequence).all()

            # Group operations by work_order_id
            from collections import defaultdict
            wo_ops = defaultdict(list)
            for op in ops:
                wo_ops[str(op.work_order_id)].append(op)

            # For each WO, link sequential operations
            for wo_id, op_list in wo_ops.items():
                for i in range(1, len(op_list)):
                    curr_op_id = str(op_list[i].id)
                    prev_op_id = str(op_list[i - 1].id)
                    curr_job_id = op_to_job.get(curr_op_id)
                    prev_job_id = op_to_job.get(prev_op_id)
                    if curr_job_id and prev_job_id:
                        predecessor_map[curr_job_id] = prev_job_id

        # Build job list for Gantt chart
        gantt_jobs = []
        for job in jobs:
            if not job.machine_id:
                continue

            # Get work order info for product name
            product_name = 'Unknown Product'
            wo = job.work_order
            if wo:
                op_name = None
                if job.runtime_data:
                    op_name = job.runtime_data.get('operation_name')
                base_name = wo.product_id or wo.description or f"WO-{wo.work_order_id}"
                product_name = f"{op_name} - {base_name}" if op_name else base_name

            status_str = job.status.value if job.status else 'pending'

            eligible_machines = []
            if job.runtime_data:
                eligible_machines = job.runtime_data.get('eligible_machines', [])

            gantt_jobs.append({
                'job_id': job.job_id,
                'machine_id': job.machine_id,
                'work_order_id': wo.work_order_id if wo else str(job.work_order_id),
                'start': job.scheduled_start.isoformat() if job.scheduled_start else None,
                'end': job.scheduled_end.isoformat() if job.scheduled_end else None,
                'status': status_str,
                'product': product_name,
                'color': status_colors.get(status_str, '#6c757d'),
                'quantity': job.quantity_planned,
                'priority': job.priority_score,
                'eligible_machines': eligible_machines,
                'depends_on': predecessor_map.get(job.job_id),
            })

        # Compute critical path: longest chain of dependent jobs by total duration
        critical_path = self._compute_critical_path(gantt_jobs)

        # Fetch maintenance windows for the visible time range
        maintenance_windows = []
        try:
            blackouts = self.get_maintenance_blackouts(
                start_time=start_time, end_time=end_time
            )
            for b in blackouts:
                maintenance_windows.append({
                    'machine_id': b['machine_id'],
                    'start': b['start'].isoformat() if hasattr(b['start'], 'isoformat') else str(b['start']),
                    'end': b['end'].isoformat() if hasattr(b['end'], 'isoformat') else str(b['end']),
                    'type': b.get('type', 'maintenance'),
                    'reason': b.get('reason', 'Maintenance'),
                })
        except Exception:
            pass

        return {
            'machines': machines,
            'jobs': gantt_jobs,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            },
            'critical_path': critical_path,
            'maintenance_windows': maintenance_windows,
        }

    @staticmethod
    def _compute_critical_path(gantt_jobs: list) -> dict:
        """Find the longest chain of sequential jobs (by total duration).

        Traverses ``depends_on`` links and returns the chain with the greatest
        cumulative duration, along with its total minutes.
        """
        # Build adjacency: predecessor -> list of successors
        job_map = {j['job_id']: j for j in gantt_jobs if j.get('job_id')}
        children = {}          # parent_id -> [child_id, ...]
        has_parent = set()
        for j in gantt_jobs:
            dep = j.get('depends_on')
            if dep and dep in job_map:
                children.setdefault(dep, []).append(j['job_id'])
                has_parent.add(j['job_id'])

        def _duration(j):
            s = j.get('start') or j.get('scheduled_start')
            e = j.get('end') or j.get('scheduled_end')
            if not s or not e:
                return 0
            from datetime import datetime as _dt
            try:
                return max(0, (_dt.fromisoformat(e) - _dt.fromisoformat(s)).total_seconds() / 60)
            except Exception:
                return 0

        # DFS from each root (no parent) to find longest path
        best_path = []
        best_dur = 0

        def _dfs(node_id, path, total_dur):
            nonlocal best_path, best_dur
            j = job_map[node_id]
            dur = _duration(j)
            new_total = total_dur + dur
            new_path = path + [node_id]
            if node_id not in children or not children[node_id]:
                if new_total > best_dur:
                    best_dur = new_total
                    best_path = new_path
                return
            for child_id in children[node_id]:
                _dfs(child_id, new_path, new_total)

        roots = [jid for jid in job_map if jid not in has_parent and jid in children]
        # Also consider chains that start mid-graph (orphaned predecessors)
        if not roots:
            roots = [jid for jid in job_map if jid not in has_parent]

        for root_id in roots:
            _dfs(root_id, [], 0)

        return {
            'job_ids': best_path,
            'total_duration_minutes': round(best_dur),
            'jobs_count': len(best_path),
        }

    def _load_physical_machines(self) -> List[Dict[str, Any]]:
        """Load all physical (non-virtual) machines from config/machines.json."""
        import json
        import os

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'machines.json'
        )

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                machines = []
                for m in config.get('machines', []):
                    # Skip virtual machines (software/CAM)
                    if m.get('machine_type') == 'virtual':
                        continue
                    if not m.get('enabled', True):
                        continue
                    machines.append({
                        'id': m['machine_id'],
                        'name': m.get('name', m['machine_id'].replace('-', ' ').title()),
                        'status': 'idle',
                    })
                return machines
        except Exception as e:
            logger.warning(f"Could not load machines config: {e}")
            return []

    def calculate_setup_time(
        self,
        from_material: str,
        to_material: str,
        machine_id: str = None,
        from_part_size: str = None,
        to_part_size: str = None
    ) -> int:
        """
        Calculate setup time in minutes for switching between materials/products.

        Args:
            from_material: Material code of previous job (e.g., 'ABS', 'PLA')
            to_material: Material code of next job
            machine_id: Machine ID for machine-specific factors
            from_part_size: Size category of previous part ('small', 'medium', 'large')
            to_part_size: Size category of next part

        Returns:
            Setup time in minutes
        """
        # Get base setup time from matrix
        base_time = MATERIAL_SETUP_MATRIX.get(
            (from_material, to_material),
            MATERIAL_SETUP_MATRIX.get(('_default', '_default'), 10)
        )

        # Apply machine-specific factor
        machine_factor = MACHINE_SETUP_FACTORS.get(machine_id, 1.0) if machine_id else 1.0

        # Add part size change time
        size_time = 0
        if from_part_size and to_part_size and from_part_size != to_part_size:
            size_time = PART_SIZE_SETUP.get(to_part_size, 0)

        total_time = int(base_time * machine_factor + size_time)
        return max(0, total_time)

    def calculate_setup_time_for_jobs(
        self,
        previous_job_id: str,
        next_job_id: str
    ) -> int:
        """
        Calculate setup time between two specific jobs.

        Args:
            previous_job_id: Job ID of the job that just completed
            next_job_id: Job ID of the job about to start

        Returns:
            Setup time in minutes
        """
        if not self.session:
            return 10  # Default fallback

        from models.mes.work_orders import Job, WorkOrder

        prev_job = self.session.query(Job).filter(Job.job_id == previous_job_id).first()
        next_job = self.session.query(Job).filter(Job.job_id == next_job_id).first()

        if not prev_job or not next_job:
            return 10

        # Get materials from work orders
        from_material = '_default'
        to_material = '_default'
        from_size = 'medium'
        to_size = 'medium'

        if prev_job.work_order and prev_job.work_order.product_id:
            # Extract material from SKU (format: PARTNUM-MATERIAL-COLOR)
            parts = prev_job.work_order.product_id.split('-')
            if len(parts) >= 2:
                from_material = parts[1]

        if next_job.work_order and next_job.work_order.product_id:
            parts = next_job.work_order.product_id.split('-')
            if len(parts) >= 2:
                to_material = parts[1]

        return self.calculate_setup_time(
            from_material=from_material,
            to_material=to_material,
            machine_id=next_job.machine_id,
            from_part_size=from_size,
            to_part_size=to_size
        )

    def update_time_estimates_from_actuals(self, job_id: str) -> Dict[str, Any]:
        """
        Update routing time estimates based on actual job completion times.

        Uses exponential moving average to smooth estimates:
        new_estimate = alpha * actual + (1 - alpha) * old_estimate

        Args:
            job_id: Job ID of the completed job

        Returns:
            Dictionary with update results
        """
        if not self.session:
            return {'success': False, 'error': 'No database session'}

        from models.mes.work_orders import Job, Operation

        # Learning rate for exponential moving average
        ALPHA = 0.2  # Weight given to new data (0.2 = 20% new, 80% historical)

        job = self.session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return {'success': False, 'error': 'Job not found'}

        if not job.actual_start or not job.actual_end:
            return {'success': False, 'error': 'Job has no actual start/end times'}

        actual_duration_min = (job.actual_end - job.actual_start).total_seconds() / 60

        # Find the corresponding operation
        if not job.operation_id:
            # Try to find operation from work order
            operation = self.session.query(Operation).filter(
                Operation.work_order_id == job.work_order_id
            ).first()
        else:
            operation = self.session.query(Operation).filter(
                Operation.id == job.operation_id
            ).first()

        if not operation:
            return {'success': False, 'error': 'No operation found for job'}

        # Update operation's estimated run time using EMA
        old_estimate = operation.run_time or actual_duration_min
        new_estimate = ALPHA * actual_duration_min + (1 - ALPHA) * old_estimate

        # Store in operation metadata for tracking
        metadata = operation.metadata or {}
        if 'time_learning' not in metadata:
            metadata['time_learning'] = {
                'samples': [],
                'estimate_history': []
            }

        metadata['time_learning']['samples'].append({
            'job_id': job_id,
            'actual_minutes': round(actual_duration_min, 1),
            'recorded_at': datetime.utcnow().isoformat()
        })
        # Keep only last 20 samples
        metadata['time_learning']['samples'] = metadata['time_learning']['samples'][-20:]

        metadata['time_learning']['estimate_history'].append({
            'old_estimate': round(old_estimate, 1),
            'new_estimate': round(new_estimate, 1),
            'updated_at': datetime.utcnow().isoformat()
        })
        metadata['time_learning']['estimate_history'] = metadata['time_learning']['estimate_history'][-10:]

        operation.run_time = round(new_estimate, 1)
        operation.metadata = metadata

        self.session.flush()

        logger.info(
            f"Updated operation {operation.operation_id} run_time: "
            f"{old_estimate:.1f} -> {new_estimate:.1f} min "
            f"(actual: {actual_duration_min:.1f} min)"
        )

        return {
            'success': True,
            'operation_id': operation.operation_id,
            'previous_estimate': round(old_estimate, 1),
            'new_estimate': round(new_estimate, 1),
            'actual_duration': round(actual_duration_min, 1),
            'samples_count': len(metadata['time_learning']['samples'])
        }

    def get_setup_time_matrix(self) -> Dict[str, Any]:
        """Return the current setup time matrix configuration."""
        return {
            'material_matrix': {
                f"{k[0]}->{k[1]}": v for k, v in MATERIAL_SETUP_MATRIX.items()
            },
            'machine_factors': MACHINE_SETUP_FACTORS,
            'part_size_setup': PART_SIZE_SETUP,
        }

    def get_machine_availability(
        self,
        machine_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get availability windows for a machine in a time range.

        Args:
            machine_id: Machine ID to check
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of availability windows with type and capacity
        """
        if not self.session:
            # Return default 24/7 availability
            return [{
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'type': 'operating',
                'capacity_percent': 100,
            }]

        from models.mes.scheduling import MachineAvailability, MachineAvailabilityType

        # Query availability windows that overlap with the time range
        windows = self.session.query(MachineAvailability).filter(
            MachineAvailability.machine_id == machine_id,
            MachineAvailability.is_active == True,
            MachineAvailability.start_datetime <= end_time,
            MachineAvailability.end_datetime >= start_time
        ).order_by(MachineAvailability.start_datetime).all()

        if not windows:
            # Default: assume 24/7 availability
            return [{
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'type': 'operating',
                'capacity_percent': 100,
            }]

        return [w.to_dict() for w in windows]

    def is_machine_available(
        self,
        machine_id: str,
        proposed_start: datetime,
        proposed_end: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a machine is available for a proposed time slot.

        Args:
            machine_id: Machine to check
            proposed_start: Proposed job start time
            proposed_end: Proposed job end time

        Returns:
            Tuple of (is_available, reason if not available)
        """
        if not self.session:
            return (True, None)

        from models.mes.scheduling import MachineAvailability, MachineAvailabilityType

        # Check for blocking windows (maintenance, downtime)
        blocking = self.session.query(MachineAvailability).filter(
            MachineAvailability.machine_id == machine_id,
            MachineAvailability.is_active == True,
            MachineAvailability.availability_type.in_([
                MachineAvailabilityType.MAINTENANCE,
                MachineAvailabilityType.DOWNTIME
            ]),
            MachineAvailability.start_datetime < proposed_end,
            MachineAvailability.end_datetime > proposed_start
        ).first()

        if blocking:
            return (
                False,
                f"Machine unavailable due to {blocking.availability_type.value}: {blocking.reason or 'scheduled'}"
            )

        return (True, None)

    def get_next_available_slot(
        self,
        machine_id: str,
        duration_minutes: int,
        after: datetime = None
    ) -> Optional[datetime]:
        """
        Find the next available time slot for a job on a machine.

        Args:
            machine_id: Machine to schedule on
            duration_minutes: Required job duration
            after: Find slot after this time (default: now)

        Returns:
            Start time of next available slot, or None if none found
        """
        if not self.session:
            return after or datetime.utcnow()

        from models.mes.work_orders import Job, JobStatus
        from models.mes.scheduling import MachineAvailability, MachineAvailabilityType

        search_start = after or datetime.utcnow()
        search_end = search_start + timedelta(days=7)  # Look up to 7 days ahead

        # Get existing jobs on this machine
        existing_jobs = self.session.query(Job).filter(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.scheduled_start != None,
            Job.scheduled_end != None,
            Job.scheduled_end >= search_start
        ).order_by(Job.scheduled_start).all()

        # Get maintenance windows
        maintenance = self.session.query(MachineAvailability).filter(
            MachineAvailability.machine_id == machine_id,
            MachineAvailability.is_active == True,
            MachineAvailability.availability_type.in_([
                MachineAvailabilityType.MAINTENANCE,
                MachineAvailabilityType.DOWNTIME
            ]),
            MachineAvailability.end_datetime >= search_start,
            MachineAvailability.start_datetime <= search_end
        ).order_by(MachineAvailability.start_datetime).all()

        # Build list of blocked periods
        blocked = []
        for job in existing_jobs:
            blocked.append((job.scheduled_start, job.scheduled_end))
        for maint in maintenance:
            blocked.append((maint.start_datetime, maint.end_datetime))

        # Sort by start time
        blocked.sort(key=lambda x: x[0])

        # Find first gap that fits
        current = search_start
        job_duration = timedelta(minutes=duration_minutes)

        for block_start, block_end in blocked:
            if current + job_duration <= block_start:
                # Found a gap before this block
                return current
            if block_end > current:
                current = block_end

        # Check if there's room after all blocks
        if current + job_duration <= search_end:
            return current

        return None

    def create_maintenance_window(
        self,
        machine_id: str,
        start_time: datetime,
        end_time: datetime,
        reason: str = None,
        recurrence: str = None
    ) -> Dict[str, Any]:
        """
        Create a maintenance window for a machine.

        Args:
            machine_id: Machine ID
            start_time: Window start
            end_time: Window end
            reason: Reason for maintenance
            recurrence: 'daily', 'weekly', or None for one-time

        Returns:
            Created maintenance window
        """
        if not self.session:
            return {'error': 'No database session'}

        from models.mes.scheduling import MachineAvailability, MachineAvailabilityType

        window = MachineAvailability(
            machine_id=machine_id,
            availability_type=MachineAvailabilityType.MAINTENANCE,
            start_datetime=start_time,
            end_datetime=end_time,
            reason=reason,
            is_recurring=recurrence is not None,
            recurrence_pattern=recurrence,
            capacity_percent=0,
            is_active=True,
        )

        self.session.add(window)
        self.session.flush()

        logger.info(f"Created maintenance window for {machine_id}: {start_time} to {end_time}")
        return window.to_dict()

    # =========================================================================
    # SCHEDULE VARIANCE TRACKING
    # =========================================================================

    def get_schedule_variance(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        machine_id: str = None
    ) -> List[ScheduleVariance]:
        """
        Calculate variance between planned and actual schedule.

        Args:
            start_date: Start of analysis period (default: 24 hours ago)
            end_date: End of analysis period (default: now)
            machine_id: Optional filter by machine

        Returns:
            List of ScheduleVariance for each job
        """
        if not self.session:
            return []

        from models.mes.work_orders import Job, JobStatus

        if not start_date:
            start_date = datetime.utcnow() - timedelta(hours=24)
        if not end_date:
            end_date = datetime.utcnow()

        # Query jobs with both scheduled and actual times
        query = self.session.query(Job).filter(
            Job.scheduled_start != None,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.RUNNING])
        )

        if machine_id:
            query = query.filter(Job.machine_id == machine_id)

        # Filter by scheduled time range
        query = query.filter(
            Job.scheduled_start >= start_date,
            Job.scheduled_start <= end_date
        )

        jobs = query.all()
        variances = []

        for job in jobs:
            start_var = None
            end_var = None
            duration_var = None

            # Calculate start variance
            if job.actual_start:
                start_var = (job.actual_start - job.scheduled_start).total_seconds() / 60

            # Calculate end variance
            if job.actual_end and job.scheduled_end:
                end_var = (job.actual_end - job.scheduled_end).total_seconds() / 60

            # Calculate duration variance
            if job.actual_start and job.actual_end and job.scheduled_start and job.scheduled_end:
                planned_duration = (job.scheduled_end - job.scheduled_start).total_seconds() / 60
                actual_duration = (job.actual_end - job.actual_start).total_seconds() / 60
                duration_var = actual_duration - planned_duration

            # Determine severity
            severity = self._calculate_variance_severity(start_var, end_var, duration_var)

            variances.append(ScheduleVariance(
                job_id=job.job_id,
                planned_start=job.scheduled_start,
                planned_end=job.scheduled_end,
                actual_start=job.actual_start,
                actual_end=job.actual_end,
                start_variance_minutes=round(start_var, 1) if start_var is not None else None,
                end_variance_minutes=round(end_var, 1) if end_var is not None else None,
                duration_variance_minutes=round(duration_var, 1) if duration_var is not None else None,
                variance_severity=severity
            ))

        return variances

    def _calculate_variance_severity(
        self,
        start_var: Optional[float],
        end_var: Optional[float],
        duration_var: Optional[float]
    ) -> str:
        """Calculate variance severity level."""
        # Thresholds in minutes
        MINOR_THRESHOLD = 15
        MAJOR_THRESHOLD = 60
        CRITICAL_THRESHOLD = 120

        max_var = 0
        if start_var is not None:
            max_var = max(max_var, abs(start_var))
        if end_var is not None:
            max_var = max(max_var, abs(end_var))
        if duration_var is not None:
            max_var = max(max_var, abs(duration_var))

        if max_var >= CRITICAL_THRESHOLD:
            return 'critical'
        elif max_var >= MAJOR_THRESHOLD:
            return 'major'
        elif max_var >= MINOR_THRESHOLD:
            return 'minor'
        return 'on_time'

    def get_variance_summary(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for schedule variance.

        Returns:
            Dict with variance metrics and alerts
        """
        variances = self.get_schedule_variance(start_date, end_date)

        if not variances:
            return {
                'total_jobs': 0,
                'variance_counts': {'on_time': 0, 'minor': 0, 'major': 0, 'critical': 0},
                'average_start_variance': 0,
                'average_end_variance': 0,
                'schedule_adherence_percent': 100,
                'alerts': []
            }

        counts = {'on_time': 0, 'minor': 0, 'major': 0, 'critical': 0}
        start_vars = []
        end_vars = []

        for v in variances:
            counts[v.variance_severity] += 1
            if v.start_variance_minutes is not None:
                start_vars.append(v.start_variance_minutes)
            if v.end_variance_minutes is not None:
                end_vars.append(v.end_variance_minutes)

        # Calculate adherence (jobs with minor or no variance)
        on_time_count = counts['on_time'] + counts['minor']
        adherence = (on_time_count / len(variances)) * 100 if variances else 100

        # Generate alerts for critical variances
        alerts = []
        critical_jobs = [v for v in variances if v.variance_severity == 'critical']
        for v in critical_jobs[:5]:  # Top 5 critical
            alerts.append({
                'type': 'critical_variance',
                'job_id': v.job_id,
                'message': f"Job {v.job_id} has critical schedule variance",
                'start_variance': v.start_variance_minutes,
                'end_variance': v.end_variance_minutes
            })

        return {
            'total_jobs': len(variances),
            'variance_counts': counts,
            'average_start_variance': round(sum(start_vars) / len(start_vars), 1) if start_vars else 0,
            'average_end_variance': round(sum(end_vars) / len(end_vars), 1) if end_vars else 0,
            'schedule_adherence_percent': round(adherence, 1),
            'alerts': alerts
        }

    # =========================================================================
    # WHAT-IF SCENARIO SIMULATION
    # =========================================================================

    def simulate_what_if(
        self,
        scenario: WhatIfScenario,
        jobs: List[ScheduleJob] = None,
        machines: List[Machine] = None
    ) -> WhatIfResult:
        """
        Simulate a what-if scenario and compare with current schedule.

        Supported change types:
        - 'add_job': Add a new job to schedule
        - 'remove_job': Remove a job from schedule
        - 'change_priority': Change job priority
        - 'change_machine': Change job's eligible machines
        - 'add_maintenance': Add maintenance window
        - 'change_due_date': Change job due date

        Args:
            scenario: WhatIfScenario with changes to apply
            jobs: Base jobs list (if None, loads from current schedule)
            machines: Available machines

        Returns:
            WhatIfResult comparing original vs modified schedules
        """
        # Get current schedule as baseline
        if jobs is None:
            jobs = self._load_current_jobs()
        if machines is None:
            machines = self._load_machines()

        # Create copy of jobs for modification
        modified_jobs = [
            ScheduleJob(
                job_id=j.job_id,
                work_order_id=j.work_order_id,
                duration_minutes=j.duration_minutes,
                machine_id=j.machine_id,
                eligible_machines=list(j.eligible_machines),
                priority=j.priority,
                due_date=j.due_date,
                dependencies=list(j.dependencies),
                setup_time=j.setup_time,
                earliest_start=j.earliest_start,
                required_skill=j.required_skill,
                required_skill_level=j.required_skill_level,
                assigned_worker_id=j.assigned_worker_id
            )
            for j in jobs
        ]

        # Apply scenario changes
        jobs_affected = []
        for change in scenario.changes:
            change_type = change.get('type')
            affected = self._apply_what_if_change(modified_jobs, machines, change)
            jobs_affected.extend(affected)

        # Generate original schedule
        original_schedule = self.schedule_jobs(jobs, machines)

        # Generate modified schedule
        modified_schedule = self.schedule_jobs(modified_jobs, machines)

        # Compare results
        makespan_delta = modified_schedule.makespan_minutes - original_schedule.makespan_minutes
        utilization_delta = {
            m_id: modified_schedule.utilization.get(m_id, 0) - original_schedule.utilization.get(m_id, 0)
            for m_id in set(list(original_schedule.utilization.keys()) + list(modified_schedule.utilization.keys()))
        }

        # Generate recommendations
        recommendations = self._generate_what_if_recommendations(
            original_schedule, modified_schedule, scenario.changes
        )

        return WhatIfResult(
            scenario_id=scenario.scenario_id,
            original_schedule=original_schedule,
            modified_schedule=modified_schedule,
            makespan_delta=makespan_delta,
            utilization_delta=utilization_delta,
            jobs_affected=list(set(jobs_affected)),
            recommendations=recommendations
        )

    def _apply_what_if_change(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        change: Dict[str, Any]
    ) -> List[str]:
        """Apply a single what-if change and return affected job IDs."""
        change_type = change.get('type')
        affected = []

        if change_type == 'add_job':
            new_job = ScheduleJob(
                job_id=change.get('job_id', f"whatif-{datetime.utcnow().timestamp()}"),
                work_order_id=change.get('work_order_id', 'WHATIF-WO'),
                duration_minutes=change.get('duration_minutes', 30),
                eligible_machines=change.get('eligible_machines', [m.machine_id for m in machines]),
                priority=change.get('priority', 5),
                due_date=change.get('due_date'),
                setup_time=change.get('setup_time', 0)
            )
            jobs.append(new_job)
            affected.append(new_job.job_id)

        elif change_type == 'remove_job':
            job_id = change.get('job_id')
            jobs[:] = [j for j in jobs if j.job_id != job_id]
            affected.append(job_id)

        elif change_type == 'change_priority':
            job_id = change.get('job_id')
            new_priority = change.get('priority')
            for job in jobs:
                if job.job_id == job_id:
                    job.priority = new_priority
                    affected.append(job_id)
                    break

        elif change_type == 'change_machine':
            job_id = change.get('job_id')
            new_machines = change.get('eligible_machines', [])
            for job in jobs:
                if job.job_id == job_id:
                    job.eligible_machines = new_machines
                    affected.append(job_id)
                    break

        elif change_type == 'change_due_date':
            job_id = change.get('job_id')
            new_due = change.get('due_date')
            if isinstance(new_due, str):
                new_due = datetime.fromisoformat(new_due)
            for job in jobs:
                if job.job_id == job_id:
                    job.due_date = new_due
                    affected.append(job_id)
                    break

        elif change_type == 'add_maintenance':
            machine_id = change.get('machine_id')
            start = change.get('start_time')
            end = change.get('end_time')
            # For maintenance, we adjust affected jobs by limiting their windows
            for job in jobs:
                if machine_id in job.eligible_machines or (not job.eligible_machines):
                    affected.append(job.job_id)

        return affected

    def _generate_what_if_recommendations(
        self,
        original: ScheduleResult,
        modified: ScheduleResult,
        changes: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on what-if comparison."""
        recommendations = []

        # Makespan change
        if modified.makespan_minutes > original.makespan_minutes * 1.1:
            recommendations.append(
                f"Warning: Changes increase makespan by {modified.makespan_minutes - original.makespan_minutes} minutes"
            )
        elif modified.makespan_minutes < original.makespan_minutes * 0.9:
            recommendations.append(
                f"Good: Changes reduce makespan by {original.makespan_minutes - modified.makespan_minutes} minutes"
            )

        # Unscheduled jobs
        new_unscheduled = set(modified.unscheduled_jobs) - set(original.unscheduled_jobs)
        if new_unscheduled:
            recommendations.append(
                f"Warning: {len(new_unscheduled)} jobs cannot be scheduled with these changes"
            )

        # Utilization changes
        low_util_machines = [
            m_id for m_id, util in modified.utilization.items()
            if util < 0.5 and original.utilization.get(m_id, 0) >= 0.5
        ]
        if low_util_machines:
            recommendations.append(
                f"Note: Machines {low_util_machines} have significantly reduced utilization"
            )

        return recommendations

    def _load_current_jobs(self) -> List[ScheduleJob]:
        """Load pending/queued jobs from database as ScheduleJob list."""
        if not self.session:
            return []

        from models.mes.work_orders import Job, JobStatus

        jobs = self.session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
        ).all()

        return [
            ScheduleJob(
                job_id=j.job_id,
                work_order_id=str(j.work_order_id),
                duration_minutes=j.runtime_data.get('estimated_duration_mins', 30) if j.runtime_data else 30,
                machine_id=j.machine_id,
                eligible_machines=j.runtime_data.get('eligible_machines', []) if j.runtime_data else [],
                priority=j.priority_score or 5,
                due_date=j.work_order.due_date if j.work_order else None,
                setup_time=j.runtime_data.get('setup_time_mins', 5) if j.runtime_data else 5
            )
            for j in jobs
        ]

    def _load_machines(self) -> List[Machine]:
        """Load machines from config."""
        machine_dicts = self._load_physical_machines()
        return [
            Machine(
                machine_id=m['id'],
                name=m['name'],
                capabilities=m.get('capabilities', []),
                efficiency=m.get('efficiency', 1.0)
            )
            for m in machine_dicts
        ]

    # =========================================================================
    # CMMS MAINTENANCE INTEGRATION
    # =========================================================================

    def get_maintenance_blackouts(
        self,
        machine_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get scheduled maintenance windows from CMMS.

        Args:
            machine_id: Optional filter by machine
            start_time: Start of time range (default: now)
            end_time: End of time range (default: 7 days)

        Returns:
            List of maintenance windows
        """
        if not self.session:
            return []

        if not start_time:
            start_time = datetime.utcnow()
        if not end_time:
            end_time = start_time + timedelta(days=7)

        blackouts = []

        # Check MES availability windows
        try:
            from models.mes.scheduling import MachineAvailability, MachineAvailabilityType

            query = self.session.query(MachineAvailability).filter(
                MachineAvailability.is_active == True,
                MachineAvailability.availability_type.in_([
                    MachineAvailabilityType.MAINTENANCE,
                    MachineAvailabilityType.DOWNTIME
                ]),
                MachineAvailability.start_datetime <= end_time,
                MachineAvailability.end_datetime >= start_time
            )

            if machine_id:
                query = query.filter(MachineAvailability.machine_id == machine_id)

            for window in query.all():
                blackouts.append({
                    'source': 'mes_availability',
                    'machine_id': window.machine_id,
                    'start': window.start_datetime,
                    'end': window.end_datetime,
                    'type': window.availability_type.value,
                    'reason': window.reason
                })
        except ImportError:
            pass

        # Check CMMS work orders
        try:
            from models.cmms.maintenance import MaintenanceWorkOrder, MaintenanceStatus

            query = self.session.query(MaintenanceWorkOrder).filter(
                MaintenanceWorkOrder.status.in_([
                    MaintenanceStatus.SCHEDULED,
                    MaintenanceStatus.IN_PROGRESS
                ]),
                MaintenanceWorkOrder.scheduled_start != None,
                MaintenanceWorkOrder.scheduled_start <= end_time
            )

            if machine_id:
                query = query.filter(MaintenanceWorkOrder.asset_id == machine_id)

            for wo in query.all():
                # Estimate duration if not specified
                duration_hours = wo.estimated_hours or 2
                end = wo.scheduled_start + timedelta(hours=duration_hours)

                if end >= start_time:
                    blackouts.append({
                        'source': 'cmms_work_order',
                        'machine_id': wo.asset_id,
                        'start': wo.scheduled_start,
                        'end': end,
                        'type': 'maintenance',
                        'reason': wo.description or 'Scheduled maintenance',
                        'work_order_id': wo.work_order_number
                    })
        except ImportError:
            pass

        # Add CBM predictive maintenance windows (MESA-5/9: Data Collection + Maintenance)
        try:
            from services.cmms.cbm_service import CBMService
            cbm_svc = CBMService(self.session)

            # Get unique machine IDs from existing blackouts + all known machines
            machine_ids_to_check = set()
            if machine_id:
                machine_ids_to_check.add(machine_id)
            else:
                # Check all machines we know about
                for b in blackouts:
                    machine_ids_to_check.add(b['machine_id'])
                try:
                    import json, os
                    config_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        'config', 'machines.json'
                    )
                    with open(config_path) as f:
                        config = json.load(f)
                        for m in config.get('machines', []):
                            if m.get('enabled', True) and m.get('machine_type') != 'virtual':
                                machine_ids_to_check.add(m['machine_id'])
                except Exception:
                    pass

            for m_id in machine_ids_to_check:
                try:
                    health = cbm_svc.evaluate_conditions(m_id)
                    if health and health.get('needs_maintenance'):
                        rul_days = health.get('remaining_useful_life_days', 7)
                        predicted_start = datetime.utcnow() + timedelta(days=max(rul_days - 1, 0))
                        predicted_end = predicted_start + timedelta(hours=4)
                        if predicted_start <= end_time and predicted_end >= start_time:
                            blackouts.append({
                                'source': 'cbm_prediction',
                                'machine_id': m_id,
                                'start': predicted_start,
                                'end': predicted_end,
                                'type': 'predictive_maintenance',
                                'reason': f"CBM: {health.get('status', 'degraded')} - {(health.get('recommendations', ['maintenance needed'])[:1] or ['maintenance needed'])[0]}"
                            })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"CBM predictive blackout check skipped: {e}")

        return blackouts

    def schedule_with_maintenance(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int = 24,
        objective: str = 'makespan',
        workers: List[Worker] = None
    ) -> ScheduleResult:
        """
        Schedule jobs while respecting maintenance blackouts.

        This is an enhanced version of schedule_jobs that:
        1. Loads maintenance windows from CMMS
        2. Blocks out unavailable time periods
        3. Schedules around maintenance

        Args:
            jobs: Jobs to schedule
            machines: Available machines
            horizon_hours: Planning horizon
            objective: Optimization objective
            workers: Optional workers for skill-based scheduling

        Returns:
            ScheduleResult with maintenance-aware scheduling
        """
        # Get maintenance blackouts for all machines
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=horizon_hours)

        blackouts = self.get_maintenance_blackouts(start_time=start_time, end_time=end_time)

        # Group blackouts by machine
        machine_blackouts: Dict[str, List[Tuple[datetime, datetime]]] = {}
        for blackout in blackouts:
            m_id = blackout['machine_id']
            if m_id not in machine_blackouts:
                machine_blackouts[m_id] = []
            machine_blackouts[m_id].append((blackout['start'], blackout['end']))

        # Update machine availability windows based on blackouts
        adjusted_machines = []
        for machine in machines:
            # If machine has blackouts, reduce availability
            if machine.machine_id in machine_blackouts:
                # For now, mark machine as unavailable during blackouts
                # A more sophisticated approach would split availability windows
                machine_copy = Machine(
                    machine_id=machine.machine_id,
                    name=machine.name,
                    capabilities=machine.capabilities,
                    available_from=machine.available_from,
                    available_until=machine.available_until,
                    efficiency=machine.efficiency
                )
                adjusted_machines.append(machine_copy)
            else:
                adjusted_machines.append(machine)

        # Schedule with adjusted machines
        result = self.schedule_jobs(jobs, adjusted_machines, horizon_hours, objective, workers)

        # Validate results don't conflict with maintenance
        conflicts = []
        for scheduled_job in result.scheduled_jobs:
            m_id = scheduled_job.machine_id
            if m_id in machine_blackouts:
                for blackout_start, blackout_end in machine_blackouts[m_id]:
                    # Check for overlap
                    if (scheduled_job.start_time < blackout_end and
                        scheduled_job.end_time > blackout_start):
                        conflicts.append({
                            'job_id': scheduled_job.job_id,
                            'machine_id': m_id,
                            'blackout_start': blackout_start,
                            'blackout_end': blackout_end
                        })

        if conflicts:
            logger.warning(f"Schedule has {len(conflicts)} conflicts with maintenance windows")
            # Re-schedule conflicting jobs to different machines or later times
            # For now, add them to unscheduled list
            conflict_job_ids = {c['job_id'] for c in conflicts}
            result.scheduled_jobs = [j for j in result.scheduled_jobs if j.job_id not in conflict_job_ids]
            result.unscheduled_jobs.extend(conflict_job_ids)

        return result
