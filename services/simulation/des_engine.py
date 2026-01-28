"""
LEGO Factory v3 - Discrete Event Simulation Engine
====================================================
Production-ready DES for schedule validation and algorithm comparison.
"""

import logging
import heapq
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of simulation events."""
    JOB_ARRIVE = 'job_arrive'
    JOB_START = 'job_start'
    JOB_COMPLETE = 'job_complete'
    SETUP_START = 'setup_start'
    SETUP_COMPLETE = 'setup_complete'
    BREAKDOWN = 'breakdown'
    REPAIR_COMPLETE = 'repair_complete'
    QUALITY_DEFECT = 'quality_defect'
    MATERIAL_SHORTAGE = 'material_shortage'
    MATERIAL_ARRIVE = 'material_arrive'
    SHIFT_START = 'shift_start'
    SHIFT_END = 'shift_end'
    MAINTENANCE_START = 'maintenance_start'
    MAINTENANCE_END = 'maintenance_end'


@dataclass
class SimEvent:
    """A discrete event in the simulation."""
    timestamp: datetime
    event_type: EventType
    machine_id: Optional[str] = None
    job_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Lower = higher priority for same timestamp

    def __lt__(self, other):
        if self.timestamp == other.timestamp:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


@dataclass
class SimConfig:
    """Configuration for simulation run."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    duration_hours: float = 168.0  # 1 week default
    enable_breakdowns: bool = True
    enable_quality_defects: bool = True
    enable_material_shortages: bool = True
    enable_setup_variability: bool = True
    enable_process_variability: bool = True
    random_seed: Optional[int] = None

    # Shift configuration
    shift_start_hour: int = 6
    shift_end_hour: int = 22
    enable_shifts: bool = False

    # Callbacks for real-time updates
    on_event: Optional[Callable[[SimEvent], None]] = None
    on_job_update: Optional[Callable[[str, str, datetime], None]] = None


@dataclass
class MachineState:
    """Current state of a machine in simulation."""
    machine_id: str
    status: str = 'idle'  # idle, running, setup, breakdown, maintenance
    current_job_id: Optional[str] = None
    current_material: Optional[str] = None
    time_to_failure: Optional[datetime] = None
    busy_until: Optional[datetime] = None
    total_running_time: float = 0.0
    total_setup_time: float = 0.0
    total_breakdown_time: float = 0.0
    breakdown_count: int = 0
    jobs_completed: int = 0


@dataclass
class JobState:
    """Current state of a job in simulation."""
    job_id: str
    work_order_id: str
    machine_id: Optional[str] = None
    status: str = 'pending'  # pending, queued, running, completed, failed
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    planned_duration_mins: float = 30.0
    actual_duration_mins: float = 0.0
    setup_time_mins: float = 5.0
    material_type: Optional[str] = None
    priority: int = 5
    due_date: Optional[datetime] = None
    defect_count: int = 0
    rework_required: bool = False


@dataclass
class SimResult:
    """Results from a simulation run."""
    sim_id: str
    config: SimConfig
    actual_makespan_mins: float
    planned_makespan_mins: float
    total_tardiness_mins: float
    jobs_completed: int
    jobs_failed: int
    total_breakdowns: int
    total_defects: int
    total_shortages: int
    machine_utilization: Dict[str, float]
    machine_stats: Dict[str, Dict[str, Any]]
    job_results: List[Dict[str, Any]]
    event_log: List[Dict[str, Any]]
    avg_wip: float
    schedule_adherence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sim_id': self.sim_id,
            'actual_makespan_mins': self.actual_makespan_mins,
            'planned_makespan_mins': self.planned_makespan_mins,
            'total_tardiness_mins': self.total_tardiness_mins,
            'jobs_completed': self.jobs_completed,
            'jobs_failed': self.jobs_failed,
            'total_breakdowns': self.total_breakdowns,
            'total_defects': self.total_defects,
            'total_shortages': self.total_shortages,
            'machine_utilization': self.machine_utilization,
            'avg_wip': self.avg_wip,
            'schedule_adherence': self.schedule_adherence,
        }


class SimulationClock:
    """Simulation clock for managing time."""

    def __init__(self, start_time: datetime):
        self.start_time = start_time
        self.current_time = start_time

    def advance_to(self, new_time: datetime):
        """Advance clock to specific time."""
        if new_time < self.current_time:
            raise ValueError("Cannot move clock backwards")
        self.current_time = new_time

    def advance_by(self, delta: timedelta):
        """Advance clock by a time delta."""
        self.current_time += delta

    def elapsed_minutes(self) -> float:
        """Get elapsed time since start in minutes."""
        return (self.current_time - self.start_time).total_seconds() / 60

    def elapsed_hours(self) -> float:
        """Get elapsed time since start in hours."""
        return self.elapsed_minutes() / 60


class EventQueue:
    """Priority queue for simulation events."""

    def __init__(self):
        self._queue: List[SimEvent] = []
        self._counter = 0

    def push(self, event: SimEvent):
        """Add event to queue."""
        heapq.heappush(self._queue, (event.timestamp, self._counter, event))
        self._counter += 1

    def pop(self) -> Optional[SimEvent]:
        """Remove and return next event."""
        if not self._queue:
            return None
        _, _, event = heapq.heappop(self._queue)
        return event

    def peek(self) -> Optional[SimEvent]:
        """Look at next event without removing."""
        if not self._queue:
            return None
        return self._queue[0][2]

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0

    def size(self) -> int:
        """Get number of events in queue."""
        return len(self._queue)

    def clear(self):
        """Clear all events."""
        self._queue.clear()
        self._counter = 0


class DiscreteEventSimulator:
    """
    Main discrete event simulation engine.

    Handles job scheduling simulation with stochastic events
    like breakdowns, quality defects, and material shortages.
    """

    def __init__(self, config: Optional[SimConfig] = None):
        self.config = config or SimConfig()
        self.clock = SimulationClock(self.config.start_time)
        self.event_queue = EventQueue()

        self.machines: Dict[str, MachineState] = {}
        self.jobs: Dict[str, JobState] = {}
        self.job_queues: Dict[str, List[str]] = {}  # machine_id -> [job_ids]

        self.event_log: List[Dict[str, Any]] = []
        self.wip_samples: List[int] = []

        # Initialize stochastic models
        self._init_stochastic_models()

        # Statistics
        self.total_breakdowns = 0
        self.total_defects = 0
        self.total_shortages = 0

    def _init_stochastic_models(self):
        """Initialize stochastic models for random events."""
        import numpy as np

        seed = self.config.random_seed
        self.rng = np.random.default_rng(seed)

        # Load simulation parameters
        try:
            from services.simulation.stochastic_models import (
                BreakdownModel, QualityModel, MaterialShortageModel,
                SetupVariabilityModel, ProcessTimeModel
            )
            self.breakdown_model = BreakdownModel(rng=self.rng)
            self.quality_model = QualityModel(rng=self.rng)
            self.shortage_model = MaterialShortageModel(rng=self.rng)
            self.setup_model = SetupVariabilityModel(rng=self.rng)
            self.process_model = ProcessTimeModel(rng=self.rng)
        except ImportError:
            logger.warning("Stochastic models not available, using defaults")
            self.breakdown_model = None
            self.quality_model = None
            self.shortage_model = None
            self.setup_model = None
            self.process_model = None

    def run(
        self,
        schedule: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
        duration_hours: Optional[float] = None
    ) -> SimResult:
        """
        Run simulation with given schedule.

        Args:
            schedule: List of job assignments [{job_id, machine_id, start, end, ...}]
            machines: List of machine definitions [{machine_id, ...}]
            duration_hours: Override config duration

        Returns:
            SimResult with simulation outcomes
        """
        sim_id = str(uuid.uuid4())[:8]
        duration = duration_hours or self.config.duration_hours
        end_time = self.config.start_time + timedelta(hours=duration)

        logger.info(f"Starting simulation {sim_id} for {duration} hours")

        # Initialize state
        self._initialize_machines(machines)
        self._initialize_jobs(schedule)
        self._schedule_initial_events(schedule)

        # Schedule breakdown events if enabled
        if self.config.enable_breakdowns:
            self._schedule_breakdown_events()

        # Main event loop
        events_processed = 0
        while not self.event_queue.is_empty():
            event = self.event_queue.pop()

            # Stop if past end time
            if event.timestamp > end_time:
                break

            # Advance clock
            self.clock.advance_to(event.timestamp)

            # Process event
            self._process_event(event)
            events_processed += 1

            # Sample WIP periodically
            if events_processed % 10 == 0:
                self.wip_samples.append(self._count_wip())

            # Callback for real-time updates
            if self.config.on_event:
                self.config.on_event(event)

        logger.info(f"Simulation {sim_id} complete: {events_processed} events processed")

        # Calculate results
        return self._calculate_results(sim_id, schedule)

    def _initialize_machines(self, machines: List[Dict[str, Any]]):
        """Initialize machine states."""
        self.machines.clear()
        self.job_queues.clear()

        for m in machines:
            machine_id = m.get('machine_id') or m.get('id')
            self.machines[machine_id] = MachineState(machine_id=machine_id)
            self.job_queues[machine_id] = []

    def _initialize_jobs(self, schedule: List[Dict[str, Any]]):
        """Initialize job states from schedule."""
        self.jobs.clear()

        for item in schedule:
            job_id = item.get('job_id')
            if not job_id:
                continue

            # Parse times
            planned_start = item.get('start')
            if isinstance(planned_start, str):
                planned_start = datetime.fromisoformat(planned_start.replace('Z', '+00:00'))
            elif isinstance(planned_start, (int, float)):
                planned_start = self.config.start_time + timedelta(minutes=planned_start)

            planned_end = item.get('end')
            if isinstance(planned_end, str):
                planned_end = datetime.fromisoformat(planned_end.replace('Z', '+00:00'))
            elif isinstance(planned_end, (int, float)):
                planned_end = self.config.start_time + timedelta(minutes=planned_end)

            duration = 30.0
            if planned_start and planned_end:
                duration = (planned_end - planned_start).total_seconds() / 60

            due_date = item.get('due_date')
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))

            self.jobs[job_id] = JobState(
                job_id=job_id,
                work_order_id=item.get('work_order_id', ''),
                machine_id=item.get('machine_id'),
                planned_start=planned_start,
                planned_end=planned_end,
                planned_duration_mins=duration,
                setup_time_mins=item.get('setup_time_mins', 5.0),
                material_type=item.get('material_type'),
                priority=item.get('priority', 5),
                due_date=due_date,
            )

    def _schedule_initial_events(self, schedule: List[Dict[str, Any]]):
        """Schedule initial job arrival events."""
        for item in schedule:
            job_id = item.get('job_id')
            if not job_id or job_id not in self.jobs:
                continue

            job = self.jobs[job_id]
            if job.planned_start:
                self.event_queue.push(SimEvent(
                    timestamp=job.planned_start,
                    event_type=EventType.JOB_ARRIVE,
                    machine_id=job.machine_id,
                    job_id=job_id,
                ))

    def _schedule_breakdown_events(self):
        """Schedule initial breakdown events for each machine."""
        if not self.breakdown_model:
            return

        for machine_id, machine in self.machines.items():
            # Get machine-specific parameters
            params = self.breakdown_model.get_machine_params(machine_id)
            ttf = self.breakdown_model.time_to_failure(params)

            breakdown_time = self.config.start_time + timedelta(hours=ttf)
            machine.time_to_failure = breakdown_time

            self.event_queue.push(SimEvent(
                timestamp=breakdown_time,
                event_type=EventType.BREAKDOWN,
                machine_id=machine_id,
            ))

    def _process_event(self, event: SimEvent):
        """Process a single simulation event."""
        # Log event
        self._log_event(event)

        handlers = {
            EventType.JOB_ARRIVE: self._handle_job_arrive,
            EventType.JOB_START: self._handle_job_start,
            EventType.JOB_COMPLETE: self._handle_job_complete,
            EventType.SETUP_START: self._handle_setup_start,
            EventType.SETUP_COMPLETE: self._handle_setup_complete,
            EventType.BREAKDOWN: self._handle_breakdown,
            EventType.REPAIR_COMPLETE: self._handle_repair_complete,
            EventType.QUALITY_DEFECT: self._handle_quality_defect,
            EventType.MATERIAL_SHORTAGE: self._handle_material_shortage,
            EventType.MATERIAL_ARRIVE: self._handle_material_arrive,
        }

        handler = handlers.get(event.event_type)
        if handler:
            handler(event)

    def _handle_job_arrive(self, event: SimEvent):
        """Handle job arrival at machine."""
        job = self.jobs.get(event.job_id)
        if not job:
            return

        machine_id = event.machine_id or job.machine_id
        if not machine_id:
            return

        machine = self.machines.get(machine_id)
        if not machine:
            return

        # Check for material shortage
        if self.config.enable_material_shortages and self.shortage_model:
            if self.shortage_model.check_shortage():
                self.total_shortages += 1
                delay_hours = self.shortage_model.delay()

                # Schedule material arrival and re-queue job
                self.event_queue.push(SimEvent(
                    timestamp=self.clock.current_time + timedelta(hours=delay_hours),
                    event_type=EventType.MATERIAL_ARRIVE,
                    machine_id=machine_id,
                    job_id=event.job_id,
                ))
                job.status = 'waiting_material'
                return

        # If machine is available, start setup/job
        if machine.status == 'idle':
            self._start_job_or_setup(machine, job)
        else:
            # Queue the job
            job.status = 'queued'
            self.job_queues[machine_id].append(event.job_id)

    def _start_job_or_setup(self, machine: MachineState, job: JobState):
        """Start setup or job on machine."""
        # Check if setup needed
        needs_setup = (
            machine.current_material != job.material_type and
            job.material_type is not None
        )

        if needs_setup:
            # Start setup
            setup_time = job.setup_time_mins
            if self.config.enable_setup_variability and self.setup_model:
                setup_time = self.setup_model.actual_setup(setup_time)

            machine.status = 'setup'
            machine.current_job_id = job.job_id

            self.event_queue.push(SimEvent(
                timestamp=self.clock.current_time + timedelta(minutes=setup_time),
                event_type=EventType.SETUP_COMPLETE,
                machine_id=machine.machine_id,
                job_id=job.job_id,
                data={'setup_time': setup_time},
            ))
        else:
            # Start job directly
            self._start_job(machine, job)

    def _start_job(self, machine: MachineState, job: JobState):
        """Start job execution on machine."""
        job.status = 'running'
        job.actual_start = self.clock.current_time
        machine.status = 'running'
        machine.current_job_id = job.job_id
        machine.current_material = job.material_type

        # Calculate actual processing time
        duration = job.planned_duration_mins
        if self.config.enable_process_variability and self.process_model:
            duration = self.process_model.actual_time(duration)

        job.actual_duration_mins = duration

        # Schedule completion
        self.event_queue.push(SimEvent(
            timestamp=self.clock.current_time + timedelta(minutes=duration),
            event_type=EventType.JOB_COMPLETE,
            machine_id=machine.machine_id,
            job_id=job.job_id,
        ))

        # Callback
        if self.config.on_job_update:
            self.config.on_job_update(job.job_id, 'running', self.clock.current_time)

    def _handle_job_start(self, event: SimEvent):
        """Handle explicit job start event."""
        job = self.jobs.get(event.job_id)
        machine = self.machines.get(event.machine_id)
        if job and machine:
            self._start_job(machine, job)

    def _handle_job_complete(self, event: SimEvent):
        """Handle job completion."""
        job = self.jobs.get(event.job_id)
        machine = self.machines.get(event.machine_id)
        if not job or not machine:
            return

        # Check for quality defect
        if self.config.enable_quality_defects and self.quality_model:
            params = self.quality_model.get_machine_params(event.machine_id)
            if self.quality_model.check_quality(params):
                self.total_defects += 1
                job.defect_count += 1

                # For simplicity, mark as rework needed but complete
                job.rework_required = True

        # Complete job
        job.status = 'completed'
        job.actual_end = self.clock.current_time

        # Update machine stats
        machine.status = 'idle'
        machine.current_job_id = None
        machine.jobs_completed += 1
        machine.total_running_time += job.actual_duration_mins

        # Callback
        if self.config.on_job_update:
            self.config.on_job_update(job.job_id, 'completed', self.clock.current_time)

        # Start next queued job if any
        self._dispatch_next_job(machine)

    def _handle_setup_start(self, event: SimEvent):
        """Handle setup start."""
        machine = self.machines.get(event.machine_id)
        if machine:
            machine.status = 'setup'

    def _handle_setup_complete(self, event: SimEvent):
        """Handle setup completion."""
        job = self.jobs.get(event.job_id)
        machine = self.machines.get(event.machine_id)
        if not job or not machine:
            return

        # Record setup time
        setup_time = event.data.get('setup_time', 0)
        machine.total_setup_time += setup_time

        # Start the job
        self._start_job(machine, job)

    def _handle_breakdown(self, event: SimEvent):
        """Handle machine breakdown."""
        machine = self.machines.get(event.machine_id)
        if not machine:
            return

        self.total_breakdowns += 1
        machine.breakdown_count += 1

        # If running a job, pause it
        if machine.current_job_id:
            job = self.jobs.get(machine.current_job_id)
            if job and job.status == 'running':
                job.status = 'paused'

        machine.status = 'breakdown'

        # Schedule repair
        if self.breakdown_model:
            params = self.breakdown_model.get_machine_params(event.machine_id)
            repair_time = self.breakdown_model.repair_duration(params)
        else:
            repair_time = 1.0  # Default 1 hour

        self.event_queue.push(SimEvent(
            timestamp=self.clock.current_time + timedelta(hours=repair_time),
            event_type=EventType.REPAIR_COMPLETE,
            machine_id=event.machine_id,
            data={'repair_time': repair_time},
        ))

    def _handle_repair_complete(self, event: SimEvent):
        """Handle repair completion."""
        machine = self.machines.get(event.machine_id)
        if not machine:
            return

        repair_time = event.data.get('repair_time', 0)
        machine.total_breakdown_time += repair_time * 60  # Convert to minutes

        # Resume paused job or go idle
        if machine.current_job_id:
            job = self.jobs.get(machine.current_job_id)
            if job and job.status == 'paused':
                self._start_job(machine, job)
            else:
                machine.status = 'idle'
                self._dispatch_next_job(machine)
        else:
            machine.status = 'idle'
            self._dispatch_next_job(machine)

        # Schedule next breakdown
        if self.config.enable_breakdowns and self.breakdown_model:
            params = self.breakdown_model.get_machine_params(event.machine_id)
            ttf = self.breakdown_model.time_to_failure(params)

            self.event_queue.push(SimEvent(
                timestamp=self.clock.current_time + timedelta(hours=ttf),
                event_type=EventType.BREAKDOWN,
                machine_id=event.machine_id,
            ))

    def _handle_quality_defect(self, event: SimEvent):
        """Handle quality defect event."""
        job = self.jobs.get(event.job_id)
        if job:
            job.defect_count += 1
            self.total_defects += 1

    def _handle_material_shortage(self, event: SimEvent):
        """Handle material shortage event."""
        self.total_shortages += 1

    def _handle_material_arrive(self, event: SimEvent):
        """Handle material arrival after shortage."""
        job = self.jobs.get(event.job_id)
        machine = self.machines.get(event.machine_id)
        if not job or not machine:
            return

        job.status = 'pending'

        # Re-queue job arrival
        self.event_queue.push(SimEvent(
            timestamp=self.clock.current_time,
            event_type=EventType.JOB_ARRIVE,
            machine_id=event.machine_id,
            job_id=event.job_id,
            priority=1,  # Higher priority after wait
        ))

    def _dispatch_next_job(self, machine: MachineState):
        """Dispatch next job from queue to machine."""
        queue = self.job_queues.get(machine.machine_id, [])
        if not queue:
            return

        # Get next job
        job_id = queue.pop(0)
        job = self.jobs.get(job_id)
        if job:
            self._start_job_or_setup(machine, job)

    def _count_wip(self) -> int:
        """Count work-in-progress jobs."""
        return sum(1 for j in self.jobs.values()
                   if j.status in ('running', 'queued', 'setup', 'waiting_material'))

    def _log_event(self, event: SimEvent):
        """Log event for reporting."""
        self.event_log.append({
            'timestamp': event.timestamp.isoformat(),
            'event_type': event.event_type.value,
            'machine_id': event.machine_id,
            'job_id': event.job_id,
            'data': event.data,
        })

    def _calculate_results(self, sim_id: str, schedule: List[Dict[str, Any]]) -> SimResult:
        """Calculate simulation results."""
        # Calculate makespan
        completed_jobs = [j for j in self.jobs.values() if j.status == 'completed']

        if completed_jobs:
            actual_makespan = max(
                (j.actual_end - self.config.start_time).total_seconds() / 60
                for j in completed_jobs
            )
        else:
            actual_makespan = 0.0

        planned_makespan = 0.0
        if schedule:
            for item in schedule:
                end = item.get('end')
                if isinstance(end, datetime):
                    mins = (end - self.config.start_time).total_seconds() / 60
                elif isinstance(end, (int, float)):
                    mins = end
                else:
                    continue
                planned_makespan = max(planned_makespan, mins)

        # Calculate tardiness
        total_tardiness = 0.0
        for job in completed_jobs:
            if job.due_date and job.actual_end:
                if job.actual_end > job.due_date:
                    tardiness = (job.actual_end - job.due_date).total_seconds() / 60
                    total_tardiness += tardiness

        # Calculate utilization
        duration_mins = self.clock.elapsed_minutes()
        machine_utilization = {}
        machine_stats = {}

        for machine_id, machine in self.machines.items():
            if duration_mins > 0:
                utilization = machine.total_running_time / duration_mins
            else:
                utilization = 0.0
            machine_utilization[machine_id] = min(1.0, utilization)

            machine_stats[machine_id] = {
                'running_time_mins': machine.total_running_time,
                'setup_time_mins': machine.total_setup_time,
                'breakdown_time_mins': machine.total_breakdown_time,
                'breakdown_count': machine.breakdown_count,
                'jobs_completed': machine.jobs_completed,
                'utilization': machine_utilization[machine_id],
            }

        # Calculate schedule adherence
        adherent_jobs = 0
        for job in completed_jobs:
            if job.planned_start and job.actual_start:
                deviation = abs((job.actual_start - job.planned_start).total_seconds() / 60)
                if deviation <= 15:  # Within 15 minutes
                    adherent_jobs += 1

        schedule_adherence = adherent_jobs / len(completed_jobs) if completed_jobs else 0.0

        # Build job results
        job_results = []
        for job in self.jobs.values():
            job_results.append({
                'job_id': job.job_id,
                'work_order_id': job.work_order_id,
                'machine_id': job.machine_id,
                'status': job.status,
                'planned_start': job.planned_start.isoformat() if job.planned_start else None,
                'planned_end': job.planned_end.isoformat() if job.planned_end else None,
                'actual_start': job.actual_start.isoformat() if job.actual_start else None,
                'actual_end': job.actual_end.isoformat() if job.actual_end else None,
                'planned_duration_mins': job.planned_duration_mins,
                'actual_duration_mins': job.actual_duration_mins,
                'defect_count': job.defect_count,
                'rework_required': job.rework_required,
            })

        # Average WIP
        avg_wip = sum(self.wip_samples) / len(self.wip_samples) if self.wip_samples else 0.0

        return SimResult(
            sim_id=sim_id,
            config=self.config,
            actual_makespan_mins=actual_makespan,
            planned_makespan_mins=planned_makespan,
            total_tardiness_mins=total_tardiness,
            jobs_completed=len(completed_jobs),
            jobs_failed=sum(1 for j in self.jobs.values() if j.status == 'failed'),
            total_breakdowns=self.total_breakdowns,
            total_defects=self.total_defects,
            total_shortages=self.total_shortages,
            machine_utilization=machine_utilization,
            machine_stats=machine_stats,
            job_results=job_results,
            event_log=self.event_log,
            avg_wip=avg_wip,
            schedule_adherence=schedule_adherence,
        )
