"""
Scheduler Factory - Factory Pattern for Schedulers

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

Provides a unified interface for creating and selecting
the appropriate scheduler based on problem characteristics.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from .constraints import ConstraintSet
from .objectives import ObjectiveSet, ObjectiveWeight, SchedulingObjective

logger = logging.getLogger(__name__)


class SchedulerType(str, Enum):
    """Available scheduler implementations."""
    CP_SAT = "cp_sat"               # OR-Tools Constraint Programming
    MILP = "milp"                   # Mixed-Integer Linear Programming
    GENETIC = "genetic"             # Genetic Algorithm
    NSGA2 = "nsga2"                 # Multi-objective NSGA-II
    NSGA3 = "nsga3"                 # Multi-objective NSGA-III
    SIMULATED_ANNEALING = "sa"      # Simulated Annealing
    TABU_SEARCH = "tabu"            # Tabu Search
    RL_DISPATCH = "rl"              # Reinforcement Learning Dispatcher
    MPC = "mpc"                     # Model Predictive Control
    GREEDY = "greedy"               # Simple greedy heuristic
    PRIORITY_DISPATCH = "priority"  # Priority-based dispatching


class ScheduleStatus(str, Enum):
    """Status of a schedule."""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ScheduledOperation:
    """A scheduled operation with assigned time and resources."""
    operation_id: str
    job_id: str
    machine_id: str
    start_time: float  # Minutes from schedule start
    end_time: float
    setup_time: float = 0.0
    operator_id: Optional[str] = None
    is_locked: bool = False

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation_id': self.operation_id,
            'job_id': self.job_id,
            'machine_id': self.machine_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'setup_time': self.setup_time,
            'duration': self.duration,
            'operator_id': self.operator_id,
            'is_locked': self.is_locked,
        }


@dataclass
class Schedule:
    """
    Complete production schedule.

    Contains all scheduled operations and objective values.
    """
    schedule_id: str
    status: ScheduleStatus
    operations: List[ScheduledOperation] = field(default_factory=list)
    objectives: Optional[ObjectiveSet] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    solver_time_ms: float = 0.0
    solver_type: SchedulerType = SchedulerType.GREEDY
    is_partial: bool = False
    gap: Optional[float] = None  # Optimality gap for MIP solvers

    # Machine timelines for visualization
    machine_timelines: Dict[str, List[ScheduledOperation]] = field(default_factory=dict)

    def add_operation(self, op: ScheduledOperation) -> None:
        """Add an operation to the schedule."""
        self.operations.append(op)
        self.machine_timelines.setdefault(op.machine_id, []).append(op)

    def get_operations_for_machine(self, machine_id: str) -> List[ScheduledOperation]:
        """Get all operations for a specific machine."""
        return self.machine_timelines.get(machine_id, [])

    def get_operations_for_job(self, job_id: str) -> List[ScheduledOperation]:
        """Get all operations for a specific job."""
        return [op for op in self.operations if op.job_id == job_id]

    def get_makespan(self) -> float:
        """Calculate makespan (total schedule duration)."""
        if not self.operations:
            return 0.0
        return max(op.end_time for op in self.operations)

    def get_machine_utilization(self, machine_id: str, horizon: float) -> float:
        """Calculate utilization for a machine."""
        if horizon <= 0:
            return 0.0
        busy_time = sum(op.duration for op in self.get_operations_for_machine(machine_id))
        return busy_time / horizon * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary."""
        return {
            'schedule_id': self.schedule_id,
            'status': self.status.value,
            'operations': [op.to_dict() for op in self.operations],
            'objectives': self.objectives.to_dict() if self.objectives else None,
            'created_at': self.created_at.isoformat(),
            'solver_time_ms': self.solver_time_ms,
            'solver_type': self.solver_type.value,
            'is_partial': self.is_partial,
            'gap': self.gap,
            'makespan': self.get_makespan(),
        }

    def to_gantt_data(self) -> Dict[str, Any]:
        """Convert schedule to Gantt chart format."""
        tasks = []
        for op in self.operations:
            tasks.append({
                'id': op.operation_id,
                'job': op.job_id,
                'machine': op.machine_id,
                'start': op.start_time,
                'end': op.end_time,
                'setup': op.setup_time,
            })

        machines = list(self.machine_timelines.keys())

        return {
            'tasks': tasks,
            'machines': machines,
            'makespan': self.get_makespan(),
        }


@dataclass
class Job:
    """A job to be scheduled (collection of operations)."""
    job_id: str
    operations: List['Operation'] = field(default_factory=list)
    release_time: float = 0.0  # Earliest start time
    due_date: Optional[float] = None
    priority: int = 1  # Higher = more important
    weight: float = 1.0  # For weighted tardiness
    customer_id: Optional[str] = None
    revenue: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'operations': [op.to_dict() for op in self.operations],
            'release_time': self.release_time,
            'due_date': self.due_date,
            'priority': self.priority,
            'weight': self.weight,
        }


@dataclass
class Operation:
    """An operation within a job."""
    operation_id: str
    job_id: str
    sequence: int  # Order within job
    eligible_machines: List[str] = field(default_factory=list)
    processing_times: Dict[str, int] = field(default_factory=dict)  # Machine -> time
    setup_times: Dict[str, Dict[str, int]] = field(default_factory=dict)  # From -> {To -> time}
    predecessors: List[str] = field(default_factory=list)
    quality_risk: float = 0.0  # From FMEA
    cost: float = 0.0

    def get_processing_time(self, machine_id: str) -> int:
        """Get processing time on specific machine."""
        return self.processing_times.get(machine_id, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation_id': self.operation_id,
            'job_id': self.job_id,
            'sequence': self.sequence,
            'eligible_machines': self.eligible_machines,
            'processing_times': self.processing_times,
            'predecessors': self.predecessors,
        }


@dataclass
class Machine:
    """A machine/resource in the shop."""
    machine_id: str
    name: str
    machine_type: str
    capacity: int = 1
    available_from: float = 0.0
    power_kw: float = 1.0
    hourly_rate: float = 50.0
    skills: List[str] = field(default_factory=list)
    is_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'machine_id': self.machine_id,
            'name': self.name,
            'machine_type': self.machine_type,
            'capacity': self.capacity,
            'available_from': self.available_from,
            'power_kw': self.power_kw,
            'hourly_rate': self.hourly_rate,
            'is_available': self.is_available,
        }


@dataclass
class SchedulingProblem:
    """
    Complete scheduling problem definition.

    Contains all inputs needed for scheduling.
    """
    problem_id: str
    jobs: List[Job] = field(default_factory=list)
    machines: List[Machine] = field(default_factory=list)
    constraints: Optional[ConstraintSet] = None
    objectives: List[ObjectiveWeight] = field(default_factory=list)
    horizon: float = 480.0  # Planning horizon in minutes (8 hours)
    schedule_start: datetime = field(default_factory=datetime.utcnow)

    # Solver parameters
    time_limit_seconds: float = 60.0
    optimality_gap: float = 0.05  # 5% gap acceptable

    def get_all_operations(self) -> List[Operation]:
        """Get all operations from all jobs."""
        operations = []
        for job in self.jobs:
            operations.extend(job.operations)
        return operations

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        """Get machine by ID."""
        for machine in self.machines:
            if machine.machine_id == machine_id:
                return machine
        return None

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'problem_id': self.problem_id,
            'jobs': [j.to_dict() for j in self.jobs],
            'machines': [m.to_dict() for m in self.machines],
            'horizon': self.horizon,
            'schedule_start': self.schedule_start.isoformat(),
            'objectives': [
                {'objective': o.objective.value, 'weight': o.weight}
                for o in self.objectives
            ],
        }


class BaseScheduler(ABC):
    """
    Abstract base class for all schedulers.

    Provides common interface and utilities.
    """

    scheduler_type: SchedulerType = SchedulerType.GREEDY

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def solve(self, problem: SchedulingProblem) -> Schedule:
        """
        Solve the scheduling problem.

        Args:
            problem: The scheduling problem to solve

        Returns:
            A Schedule object with the solution
        """
        pass

    def validate_problem(self, problem: SchedulingProblem) -> List[str]:
        """Validate problem inputs."""
        errors = []

        if not problem.jobs:
            errors.append("No jobs to schedule")

        if not problem.machines:
            errors.append("No machines available")

        # Check all operations have valid machines
        machine_ids = {m.machine_id for m in problem.machines}
        for job in problem.jobs:
            for op in job.operations:
                if not op.eligible_machines:
                    errors.append(f"Operation {op.operation_id} has no eligible machines")
                for m_id in op.eligible_machines:
                    if m_id not in machine_ids:
                        errors.append(f"Operation {op.operation_id} references unknown machine {m_id}")

        # Validate constraints if present
        if problem.constraints:
            errors.extend(problem.constraints.validate())

        return errors

    def create_empty_schedule(
        self,
        problem: SchedulingProblem,
        status: ScheduleStatus = ScheduleStatus.INFEASIBLE
    ) -> Schedule:
        """Create an empty schedule with given status."""
        from uuid import uuid4
        return Schedule(
            schedule_id=str(uuid4()),
            status=status,
            solver_type=self.scheduler_type,
        )


class SchedulerFactory:
    """
    Factory for creating schedulers.

    Selects the appropriate scheduler based on problem
    characteristics or explicit selection.
    """

    _schedulers: Dict[SchedulerType, Type[BaseScheduler]] = {}

    @classmethod
    def register(cls, scheduler_type: SchedulerType):
        """Decorator to register a scheduler implementation."""
        def decorator(scheduler_class: Type[BaseScheduler]):
            cls._schedulers[scheduler_type] = scheduler_class
            return scheduler_class
        return decorator

    @classmethod
    def create(
        cls,
        scheduler_type: SchedulerType,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseScheduler:
        """Create a scheduler of the specified type."""
        if scheduler_type not in cls._schedulers:
            available = list(cls._schedulers.keys())
            raise ValueError(
                f"Unknown scheduler type: {scheduler_type}. "
                f"Available: {available}"
            )

        scheduler_class = cls._schedulers[scheduler_type]
        return scheduler_class(config)

    @classmethod
    def auto_select(
        cls,
        problem: SchedulingProblem
    ) -> SchedulerType:
        """
        Automatically select the best scheduler for a problem.

        Selection criteria:
        - Small problems (<10 jobs): CP-SAT for optimality
        - Multi-objective: NSGA-II/III
        - Real-time dispatching: RL or Priority
        - Large problems: Genetic or Simulated Annealing
        """
        num_jobs = len(problem.jobs)
        num_ops = sum(len(j.operations) for j in problem.jobs)
        num_objectives = len(problem.objectives)

        # Multi-objective problems
        if num_objectives > 1:
            if num_objectives <= 3:
                return SchedulerType.NSGA2
            else:
                return SchedulerType.NSGA3

        # Small problems - use exact solver
        if num_ops <= 50:
            return SchedulerType.CP_SAT

        # Medium problems
        if num_ops <= 200:
            return SchedulerType.GENETIC

        # Large problems - use fast heuristics
        if problem.time_limit_seconds < 5:
            return SchedulerType.PRIORITY_DISPATCH

        return SchedulerType.SIMULATED_ANNEALING

    @classmethod
    def solve(
        cls,
        problem: SchedulingProblem,
        scheduler_type: Optional[SchedulerType] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Schedule:
        """
        Solve a scheduling problem.

        If scheduler_type is not specified, auto-selects based on problem.
        """
        if scheduler_type is None:
            scheduler_type = cls.auto_select(problem)
            logger.info(f"Auto-selected scheduler: {scheduler_type}")

        scheduler = cls.create(scheduler_type, config)

        # Validate problem
        errors = scheduler.validate_problem(problem)
        if errors:
            logger.error(f"Problem validation failed: {errors}")
            schedule = scheduler.create_empty_schedule(problem)
            return schedule

        # Solve
        import time
        start = time.time()
        schedule = scheduler.solve(problem)
        schedule.solver_time_ms = (time.time() - start) * 1000

        logger.info(
            f"Scheduling complete: status={schedule.status}, "
            f"makespan={schedule.get_makespan():.1f}, "
            f"time={schedule.solver_time_ms:.0f}ms"
        )

        return schedule

    @classmethod
    def available_schedulers(cls) -> List[SchedulerType]:
        """Get list of available scheduler types."""
        return list(cls._schedulers.keys())


# Register a simple greedy scheduler as fallback
@SchedulerFactory.register(SchedulerType.GREEDY)
class GreedyScheduler(BaseScheduler):
    """
    Simple greedy scheduler using priority dispatching.

    Uses SPT (Shortest Processing Time) or EDD (Earliest Due Date).
    """

    scheduler_type = SchedulerType.GREEDY

    def solve(self, problem: SchedulingProblem) -> Schedule:
        from uuid import uuid4

        schedule = Schedule(
            schedule_id=str(uuid4()),
            status=ScheduleStatus.FEASIBLE,
            solver_type=self.scheduler_type,
        )

        # Track machine availability
        machine_available: Dict[str, float] = {
            m.machine_id: m.available_from for m in problem.machines
        }

        # Track job completion for precedence
        op_completion: Dict[str, float] = {}

        # Sort operations by job priority and sequence
        all_ops = []
        for job in sorted(problem.jobs, key=lambda j: -j.priority):
            for op in sorted(job.operations, key=lambda o: o.sequence):
                all_ops.append((job, op))

        # Schedule each operation
        for job, op in all_ops:
            # Find earliest start considering precedence
            earliest = job.release_time
            for pred_id in op.predecessors:
                if pred_id in op_completion:
                    earliest = max(earliest, op_completion[pred_id])

            # Find best machine (earliest available, shortest processing time)
            best_machine = None
            best_start = float('inf')
            best_proc_time = float('inf')

            for m_id in op.eligible_machines:
                proc_time = op.get_processing_time(m_id)
                avail = machine_available.get(m_id, 0)
                start = max(earliest, avail)

                if start < best_start or (start == best_start and proc_time < best_proc_time):
                    best_machine = m_id
                    best_start = start
                    best_proc_time = proc_time

            if best_machine is None:
                self.logger.error(f"No machine available for operation {op.operation_id}")
                schedule.status = ScheduleStatus.INFEASIBLE
                return schedule

            # Schedule the operation
            end_time = best_start + best_proc_time
            scheduled_op = ScheduledOperation(
                operation_id=op.operation_id,
                job_id=job.job_id,
                machine_id=best_machine,
                start_time=best_start,
                end_time=end_time,
            )

            schedule.add_operation(scheduled_op)
            machine_available[best_machine] = end_time
            op_completion[op.operation_id] = end_time

        # Calculate objectives
        from .objectives import ObjectiveCalculator
        calculator = ObjectiveCalculator()

        job_dicts = [j.to_dict() for j in problem.jobs]
        op_dicts = [op.to_dict() for op in schedule.operations]
        machine_dicts = {m.machine_id: m.to_dict() for m in problem.machines}

        schedule.objectives = calculator.calculate_full_objectives(
            job_dicts, op_dicts, machine_dicts
        )

        return schedule


@SchedulerFactory.register(SchedulerType.PRIORITY_DISPATCH)
class PriorityDispatcher(BaseScheduler):
    """
    Priority-based dispatcher with multiple dispatch rules.

    Supports: SPT, LPT, EDD, SLACK, FIFO, CR (Critical Ratio).
    """

    scheduler_type = SchedulerType.PRIORITY_DISPATCH

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.rule = config.get('rule', 'EDD') if config else 'EDD'

    def solve(self, problem: SchedulingProblem) -> Schedule:
        from uuid import uuid4

        schedule = Schedule(
            schedule_id=str(uuid4()),
            status=ScheduleStatus.FEASIBLE,
            solver_type=self.scheduler_type,
        )

        # Build operation queue with priority values
        queue = []
        for job in problem.jobs:
            for op in job.operations:
                priority = self._calculate_priority(job, op, problem)
                queue.append((priority, job, op))

        # Sort by priority
        queue.sort(key=lambda x: x[0])

        # Track machine availability
        machine_available: Dict[str, float] = {
            m.machine_id: m.available_from for m in problem.machines
        }
        op_completion: Dict[str, float] = {}

        # Schedule operations
        scheduled_ops = set()
        while queue:
            # Find next schedulable operation
            scheduled_any = False
            for i, (priority, job, op) in enumerate(queue):
                if op.operation_id in scheduled_ops:
                    continue

                # Check predecessors complete
                ready = all(
                    pred_id in op_completion
                    for pred_id in op.predecessors
                )
                if not ready:
                    continue

                # Find best machine
                earliest = job.release_time
                for pred_id in op.predecessors:
                    earliest = max(earliest, op_completion.get(pred_id, 0))

                best_machine = None
                best_start = float('inf')

                for m_id in op.eligible_machines:
                    avail = machine_available.get(m_id, 0)
                    start = max(earliest, avail)
                    if start < best_start:
                        best_machine = m_id
                        best_start = start

                if best_machine:
                    proc_time = op.get_processing_time(best_machine)
                    end_time = best_start + proc_time

                    scheduled_op = ScheduledOperation(
                        operation_id=op.operation_id,
                        job_id=job.job_id,
                        machine_id=best_machine,
                        start_time=best_start,
                        end_time=end_time,
                    )

                    schedule.add_operation(scheduled_op)
                    machine_available[best_machine] = end_time
                    op_completion[op.operation_id] = end_time
                    scheduled_ops.add(op.operation_id)
                    queue.pop(i)
                    scheduled_any = True
                    break

            if not scheduled_any:
                break

        # Check if all operations were scheduled
        total_ops = sum(len(j.operations) for j in problem.jobs)
        if len(scheduled_ops) < total_ops:
            schedule.status = ScheduleStatus.INFEASIBLE

        return schedule

    def _calculate_priority(self, job: Job, op: Operation, problem: SchedulingProblem) -> float:
        """Calculate priority value based on dispatch rule."""
        if self.rule == 'SPT':
            # Shortest Processing Time
            return min(op.processing_times.values()) if op.processing_times else 0

        elif self.rule == 'LPT':
            # Longest Processing Time
            return -max(op.processing_times.values()) if op.processing_times else 0

        elif self.rule == 'EDD':
            # Earliest Due Date
            return job.due_date if job.due_date else float('inf')

        elif self.rule == 'SLACK':
            # Minimum Slack = Due Date - Remaining Processing Time
            remaining = sum(
                min(o.processing_times.values()) if o.processing_times else 0
                for o in job.operations
            )
            if job.due_date:
                return job.due_date - remaining
            return float('inf')

        elif self.rule == 'CR':
            # Critical Ratio = (Due Date - Now) / Remaining Work
            remaining = sum(
                min(o.processing_times.values()) if o.processing_times else 0
                for o in job.operations
            )
            if job.due_date and remaining > 0:
                return (job.due_date - job.release_time) / remaining
            return float('inf')

        elif self.rule == 'FIFO':
            # First In First Out (by release time)
            return job.release_time

        else:
            # Default to job priority
            return -job.priority
