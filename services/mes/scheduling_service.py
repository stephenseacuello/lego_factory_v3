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


@dataclass
class ScheduleResult:
    """Complete schedule result."""
    scheduled_jobs: List[ScheduledJob]
    makespan_minutes: int
    total_setup_time: int
    utilization: Dict[str, float]
    unscheduled_jobs: List[str] = field(default_factory=list)
    solver_status: str = "optimal"


class SchedulingService:
    """
    Job scheduling service using CP-SAT solver.

    Supports:
    - Machine assignment
    - Job sequencing
    - Setup time optimization
    - Due date constraints
    - Priority-based scheduling
    """

    def __init__(self, session: Session = None):
        self.session = session

    def schedule_jobs(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int = 24,
        objective: str = 'makespan'  # 'makespan', 'due_date', 'setup_time'
    ) -> ScheduleResult:
        """
        Schedule jobs across machines.

        Uses Google OR-Tools CP-SAT solver when available,
        falls back to priority-based heuristic otherwise.
        """
        try:
            return self._schedule_cpsat(jobs, machines, horizon_hours, objective)
        except ImportError:
            logger.warning("OR-Tools not available, using heuristic scheduler")
            return self._schedule_heuristic(jobs, machines, horizon_hours)

    def _schedule_cpsat(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        horizon_hours: int,
        objective: str
    ) -> ScheduleResult:
        """Schedule using CP-SAT solver."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        horizon = horizon_hours * 60  # Convert to minutes

        # Create variables
        job_vars = {}
        machine_assignments = {}

        for job in jobs:
            # Start time variable
            start_var = model.NewIntVar(0, horizon - job.duration_minutes, f'start_{job.job_id}')
            end_var = model.NewIntVar(0, horizon, f'end_{job.job_id}')
            job_vars[job.job_id] = {'start': start_var, 'end': end_var}

            # Duration constraint
            model.Add(end_var == start_var + job.duration_minutes)

            # Machine assignment
            eligible = job.eligible_machines or [m.machine_id for m in machines]
            for m_id in eligible:
                machine_assignments[(job.job_id, m_id)] = model.NewBoolVar(f'assign_{job.job_id}_{m_id}')

            # Must be assigned to exactly one machine
            model.Add(sum(machine_assignments.get((job.job_id, m.machine_id), 0)
                        for m in machines if (job.job_id, m.machine_id) in machine_assignments) == 1)

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

            if assigned_machine:
                scheduled.append(ScheduledJob(
                    job_id=job.job_id,
                    machine_id=assigned_machine,
                    start_time=base_time + timedelta(minutes=start_min),
                    end_time=base_time + timedelta(minutes=end_min),
                    setup_time=job.setup_time
                ))

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
        horizon_hours: int
    ) -> ScheduleResult:
        """Simple priority-based heuristic scheduler."""
        # Sort by priority and due date
        sorted_jobs = sorted(jobs, key=lambda j: (j.priority, j.due_date or datetime.max))

        # Track machine availability
        machine_available = {m.machine_id: datetime.utcnow() for m in machines}
        scheduled = []
        unscheduled = []

        for job in sorted_jobs:
            eligible = job.eligible_machines or [m.machine_id for m in machines]
            eligible_available = [(m_id, machine_available[m_id])
                                   for m_id in eligible if m_id in machine_available]

            if not eligible_available:
                unscheduled.append(job.job_id)
                continue

            # Pick earliest available machine
            best_machine, start_time = min(eligible_available, key=lambda x: x[1])

            end_time = start_time + timedelta(minutes=job.duration_minutes + job.setup_time)
            machine_available[best_machine] = end_time

            scheduled.append(ScheduledJob(
                job_id=job.job_id,
                machine_id=best_machine,
                start_time=start_time,
                end_time=end_time,
                setup_time=job.setup_time
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
            'queued': '#ffc107',     # yellow
            'running': '#007bff',    # blue
            'paused': '#17a2b8',     # teal
            'completed': '#28a745',  # green
            'failed': '#dc3545',     # red
            'cancelled': '#6c757d',  # gray
        }

        # Build job list for Gantt chart
        gantt_jobs = []
        for job in jobs:
            if not job.machine_id:
                continue

            # Get work order info for product name
            product_name = 'Unknown Product'
            wo = job.work_order
            if wo:
                # Include operation name if available
                op_name = None
                if job.runtime_data:
                    op_name = job.runtime_data.get('operation_name')
                base_name = wo.product_id or wo.description or f"WO-{wo.work_order_id}"
                product_name = f"{op_name} - {base_name}" if op_name else base_name

            status_str = job.status.value if job.status else 'pending'

            # Get eligible_machines from runtime_data
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
            })

        return {
            'machines': machines,
            'jobs': gantt_jobs,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            }
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
