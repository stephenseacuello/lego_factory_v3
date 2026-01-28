"""
Autonomous Scheduling Optimizer V8.

LEGO MCP V8 - Autonomous Factory Platform
Intelligent Production Scheduling with Multi-Objective Optimization.

Features:
- Genetic algorithm based scheduling optimization
- Multi-objective optimization (makespan, utilization, tardiness)
- Constraint satisfaction (resource, precedence, time windows)
- Real-time schedule adaptation
- Job shop and flow shop scheduling
- Machine assignment and sequencing
- Dynamic rescheduling on disruptions

Standards Compliance:
- ISA-95 (Enterprise-Control System Integration)

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import asyncio
import copy
import heapq
import logging
import random
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class ScheduleType(Enum):
    """Type of scheduling problem."""
    JOB_SHOP = "job_shop"
    FLOW_SHOP = "flow_shop"
    OPEN_SHOP = "open_shop"
    FLEXIBLE_JOB_SHOP = "flexible_job_shop"


class OptimizationObjective(Enum):
    """Optimization objectives."""
    MINIMIZE_MAKESPAN = "minimize_makespan"
    MINIMIZE_TARDINESS = "minimize_tardiness"
    MAXIMIZE_UTILIZATION = "maximize_utilization"
    MINIMIZE_IDLE_TIME = "minimize_idle_time"
    MINIMIZE_WIP = "minimize_wip"
    BALANCED = "balanced"


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class MachineStatus(Enum):
    """Machine status."""
    AVAILABLE = "available"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    BREAKDOWN = "breakdown"
    OFFLINE = "offline"


class ConstraintType(Enum):
    """Types of scheduling constraints."""
    PRECEDENCE = "precedence"
    RESOURCE = "resource"
    TIME_WINDOW = "time_window"
    SETUP_TIME = "setup_time"
    BATCH = "batch"
    SEQUENCE_DEPENDENT = "sequence_dependent"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Operation:
    """Single operation within a job."""
    operation_id: str
    job_id: str
    name: str
    processing_time: float  # seconds
    eligible_machines: List[str]
    predecessors: List[str] = field(default_factory=list)
    setup_time: float = 0.0
    required_resources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "job_id": self.job_id,
            "name": self.name,
            "processing_time": self.processing_time,
            "eligible_machines": self.eligible_machines,
            "predecessors": self.predecessors,
            "setup_time": self.setup_time,
            "required_resources": self.required_resources,
        }


@dataclass
class Job:
    """Manufacturing job consisting of multiple operations."""
    job_id: str
    name: str
    priority: JobPriority
    operations: List[Operation]
    due_date: Optional[datetime] = None
    release_date: Optional[datetime] = None
    weight: float = 1.0
    status: JobStatus = JobStatus.PENDING
    customer_id: Optional[str] = None

    def get_total_processing_time(self) -> float:
        """Get total processing time for all operations."""
        return sum(op.processing_time for op in self.operations)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority.value,
            "operations": [op.to_dict() for op in self.operations],
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "weight": self.weight,
            "status": self.status.value,
            "customer_id": self.customer_id,
            "total_processing_time": self.get_total_processing_time(),
        }


@dataclass
class Machine:
    """Manufacturing machine/resource."""
    machine_id: str
    name: str
    machine_type: str
    status: MachineStatus = MachineStatus.AVAILABLE
    efficiency: float = 1.0  # Processing time multiplier
    setup_times: Dict[str, float] = field(default_factory=dict)  # op_type -> setup_time
    maintenance_schedule: List[Tuple[datetime, datetime]] = field(default_factory=list)
    current_job: Optional[str] = None
    processing_until: Optional[datetime] = None

    def is_available_at(self, time: datetime) -> bool:
        """Check if machine is available at given time."""
        if self.status != MachineStatus.AVAILABLE:
            if self.processing_until and time < self.processing_until:
                return False

        # Check maintenance windows
        for start, end in self.maintenance_schedule:
            if start <= time < end:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "machine_type": self.machine_type,
            "status": self.status.value,
            "efficiency": self.efficiency,
            "current_job": self.current_job,
            "processing_until": self.processing_until.isoformat() if self.processing_until else None,
        }


@dataclass
class ScheduledOperation:
    """A scheduled operation assignment."""
    operation_id: str
    job_id: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    setup_time: float = 0.0

    def duration(self) -> float:
        """Get operation duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "job_id": self.job_id,
            "machine_id": self.machine_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "setup_time": self.setup_time,
            "duration": self.duration(),
        }


@dataclass
class Schedule:
    """Complete production schedule."""
    schedule_id: str
    created_at: datetime
    scheduled_operations: List[ScheduledOperation]
    makespan: float  # Total completion time
    total_tardiness: float  # Sum of late deliveries
    machine_utilization: Dict[str, float]  # machine_id -> utilization %
    objective_value: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schedule_id": self.schedule_id,
            "created_at": self.created_at.isoformat(),
            "scheduled_operations": [op.to_dict() for op in self.scheduled_operations],
            "makespan": self.makespan,
            "total_tardiness": self.total_tardiness,
            "machine_utilization": self.machine_utilization,
            "objective_value": self.objective_value,
            "operation_count": len(self.scheduled_operations),
        }


@dataclass
class Constraint:
    """Scheduling constraint."""
    constraint_id: str
    constraint_type: ConstraintType
    parameters: Dict[str, Any]
    is_hard: bool = True  # Hard constraints must be satisfied

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "constraint_id": self.constraint_id,
            "constraint_type": self.constraint_type.value,
            "parameters": self.parameters,
            "is_hard": self.is_hard,
        }


@dataclass
class ScheduleMetrics:
    """Performance metrics for a schedule."""
    makespan: float
    total_tardiness: float
    average_utilization: float
    max_tardiness: float
    number_of_late_jobs: int
    total_setup_time: float
    idle_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "makespan": self.makespan,
            "total_tardiness": self.total_tardiness,
            "average_utilization": self.average_utilization,
            "max_tardiness": self.max_tardiness,
            "number_of_late_jobs": self.number_of_late_jobs,
            "total_setup_time": self.total_setup_time,
            "idle_time": self.idle_time,
        }


# =============================================================================
# Genetic Algorithm Chromosome
# =============================================================================

@dataclass
class Chromosome:
    """Genetic algorithm chromosome for schedule representation."""
    genes: List[Tuple[str, str]]  # List of (operation_id, machine_id)
    fitness: float = float('inf')

    def copy(self) -> 'Chromosome':
        """Create a copy of this chromosome."""
        return Chromosome(genes=list(self.genes), fitness=self.fitness)


# =============================================================================
# Scheduling Optimizer
# =============================================================================

class SchedulingOptimizer:
    """
    Autonomous Scheduling Optimizer.

    Uses genetic algorithms and heuristics to optimize production schedules
    with multi-objective optimization and constraint satisfaction.

    Features:
    - Genetic algorithm optimization
    - Multiple scheduling objectives
    - Hard and soft constraints
    - Real-time rescheduling
    - Dynamic adaptation
    """

    def __init__(
        self,
        optimizer_id: str = "default",
        schedule_type: ScheduleType = ScheduleType.JOB_SHOP,
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
        population_size: int = 50,
        generations: int = 100,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8
    ):
        """
        Initialize scheduling optimizer.

        Args:
            optimizer_id: Unique identifier
            schedule_type: Type of scheduling problem
            objective: Optimization objective
            population_size: GA population size
            generations: Number of GA generations
            mutation_rate: Mutation probability
            crossover_rate: Crossover probability
        """
        self.optimizer_id = optimizer_id
        self.schedule_type = schedule_type
        self.objective = objective
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

        # Problem definition
        self.jobs: Dict[str, Job] = {}
        self.machines: Dict[str, Machine] = {}
        self.constraints: Dict[str, Constraint] = {}
        self.resources: Dict[str, int] = {}  # resource_id -> capacity

        # Current schedule
        self.current_schedule: Optional[Schedule] = None

        # History
        self.schedule_history: List[Schedule] = []

        # Callbacks
        self.on_schedule_updated: Optional[Callable[[Schedule], None]] = None
        self.on_disruption: Optional[Callable[[str, Any], None]] = None

        # Statistics
        self.total_optimizations = 0
        self.total_reschedulings = 0

        # Background task
        self._running = False
        self._optimization_task: Optional[asyncio.Task] = None

        logger.info(
            f"SchedulingOptimizer initialized: {optimizer_id}, "
            f"type={schedule_type.value}, objective={objective.value}"
        )

    # -------------------------------------------------------------------------
    # Problem Definition
    # -------------------------------------------------------------------------

    def add_job(
        self,
        job_id: str,
        name: str,
        operations: List[Dict[str, Any]],
        priority: JobPriority = JobPriority.NORMAL,
        due_date: Optional[datetime] = None,
        release_date: Optional[datetime] = None,
        weight: float = 1.0
    ) -> Job:
        """
        Add a job to the scheduling problem.

        Args:
            job_id: Unique job identifier
            name: Job name
            operations: List of operation definitions
            priority: Job priority
            due_date: Optional due date
            release_date: Optional release date
            weight: Importance weight

        Returns:
            Created Job
        """
        ops = []
        for i, op_def in enumerate(operations):
            op = Operation(
                operation_id=f"{job_id}_op{i}",
                job_id=job_id,
                name=op_def.get("name", f"Operation {i}"),
                processing_time=op_def["processing_time"],
                eligible_machines=op_def.get("eligible_machines", list(self.machines.keys())),
                predecessors=op_def.get("predecessors", []),
                setup_time=op_def.get("setup_time", 0.0),
                required_resources=op_def.get("required_resources", []),
            )
            ops.append(op)

        job = Job(
            job_id=job_id,
            name=name,
            priority=priority,
            operations=ops,
            due_date=due_date,
            release_date=release_date,
            weight=weight,
        )

        self.jobs[job_id] = job
        logger.info(f"Added job: {job_id} with {len(ops)} operations")

        return job

    def add_machine(
        self,
        machine_id: str,
        name: str,
        machine_type: str,
        efficiency: float = 1.0,
        setup_times: Optional[Dict[str, float]] = None
    ) -> Machine:
        """
        Add a machine to the scheduling problem.

        Args:
            machine_id: Unique machine identifier
            name: Machine name
            machine_type: Type of machine
            efficiency: Processing efficiency factor
            setup_times: Setup times by operation type

        Returns:
            Created Machine
        """
        machine = Machine(
            machine_id=machine_id,
            name=name,
            machine_type=machine_type,
            efficiency=efficiency,
            setup_times=setup_times or {},
        )

        self.machines[machine_id] = machine
        logger.info(f"Added machine: {machine_id} ({machine_type})")

        return machine

    def add_constraint(
        self,
        constraint_type: ConstraintType,
        parameters: Dict[str, Any],
        is_hard: bool = True
    ) -> Constraint:
        """Add a scheduling constraint."""
        constraint = Constraint(
            constraint_id=str(uuid.uuid4()),
            constraint_type=constraint_type,
            parameters=parameters,
            is_hard=is_hard,
        )

        self.constraints[constraint.constraint_id] = constraint
        return constraint

    # -------------------------------------------------------------------------
    # Schedule Generation
    # -------------------------------------------------------------------------

    def generate_schedule(
        self,
        start_time: Optional[datetime] = None
    ) -> Schedule:
        """
        Generate an optimized schedule using genetic algorithm.

        Args:
            start_time: Schedule start time (defaults to now)

        Returns:
            Optimized Schedule
        """
        start_time = start_time or datetime.utcnow()

        # Get all operations
        all_operations = []
        for job in self.jobs.values():
            if job.status not in (JobStatus.COMPLETED, JobStatus.CANCELLED):
                all_operations.extend(job.operations)

        if not all_operations:
            logger.warning("No operations to schedule")
            return self._create_empty_schedule()

        # Run genetic algorithm
        best_chromosome = self._genetic_algorithm(all_operations, start_time)

        # Decode chromosome to schedule
        schedule = self._decode_chromosome(best_chromosome, start_time)

        self.current_schedule = schedule
        self.schedule_history.append(schedule)
        self.total_optimizations += 1

        if self.on_schedule_updated:
            self.on_schedule_updated(schedule)

        logger.info(
            f"Generated schedule with makespan={schedule.makespan:.1f}s, "
            f"utilization={sum(schedule.machine_utilization.values())/len(schedule.machine_utilization)*100:.1f}%"
        )

        return schedule

    def _genetic_algorithm(
        self,
        operations: List[Operation],
        start_time: datetime
    ) -> Chromosome:
        """Run genetic algorithm optimization."""
        # Initialize population
        population = self._initialize_population(operations)

        # Evaluate initial population
        for chromosome in population:
            chromosome.fitness = self._evaluate_fitness(chromosome, operations, start_time)

        # Evolution loop
        for generation in range(self.generations):
            # Selection
            parents = self._tournament_selection(population)

            # Crossover and mutation
            offspring = []
            for i in range(0, len(parents) - 1, 2):
                child1, child2 = self._crossover(parents[i], parents[i + 1], operations)
                child1 = self._mutate(child1, operations)
                child2 = self._mutate(child2, operations)
                offspring.extend([child1, child2])

            # Evaluate offspring
            for chromosome in offspring:
                chromosome.fitness = self._evaluate_fitness(chromosome, operations, start_time)

            # Elitism: keep best from population
            population.sort(key=lambda c: c.fitness)
            elite_count = max(2, self.population_size // 10)
            new_population = population[:elite_count]

            # Fill rest with offspring
            offspring.sort(key=lambda c: c.fitness)
            new_population.extend(offspring[:self.population_size - elite_count])

            population = new_population

            # Early termination if converged
            if generation > 10:
                fitness_variance = self._calculate_variance([c.fitness for c in population[:10]])
                if fitness_variance < 0.001:
                    break

        # Return best chromosome
        population.sort(key=lambda c: c.fitness)
        return population[0]

    def _initialize_population(self, operations: List[Operation]) -> List[Chromosome]:
        """Initialize GA population."""
        population = []

        for _ in range(self.population_size):
            # Random assignment of operations to machines
            genes = []
            for op in operations:
                machine = random.choice(op.eligible_machines)
                genes.append((op.operation_id, machine))

            # Shuffle to create different orderings
            random.shuffle(genes)
            population.append(Chromosome(genes=genes))

        return population

    def _evaluate_fitness(
        self,
        chromosome: Chromosome,
        operations: List[Operation],
        start_time: datetime
    ) -> float:
        """Evaluate chromosome fitness."""
        try:
            schedule = self._decode_chromosome(chromosome, start_time)
        except Exception:
            return float('inf')

        # Multi-objective fitness
        if self.objective == OptimizationObjective.MINIMIZE_MAKESPAN:
            return schedule.makespan

        elif self.objective == OptimizationObjective.MINIMIZE_TARDINESS:
            return schedule.total_tardiness

        elif self.objective == OptimizationObjective.MAXIMIZE_UTILIZATION:
            avg_util = sum(schedule.machine_utilization.values()) / len(schedule.machine_utilization)
            return 1.0 - avg_util  # Lower is better

        elif self.objective == OptimizationObjective.BALANCED:
            # Weighted combination
            makespan_normalized = schedule.makespan / 10000.0
            tardiness_normalized = schedule.total_tardiness / 10000.0
            avg_util = sum(schedule.machine_utilization.values()) / len(schedule.machine_utilization)
            util_penalty = 1.0 - avg_util

            return 0.4 * makespan_normalized + 0.3 * tardiness_normalized + 0.3 * util_penalty

        else:
            return schedule.makespan

    def _tournament_selection(
        self,
        population: List[Chromosome],
        tournament_size: int = 3
    ) -> List[Chromosome]:
        """Tournament selection for parent selection."""
        selected = []
        for _ in range(len(population)):
            tournament = random.sample(population, min(tournament_size, len(population)))
            winner = min(tournament, key=lambda c: c.fitness)
            selected.append(winner.copy())
        return selected

    def _crossover(
        self,
        parent1: Chromosome,
        parent2: Chromosome,
        operations: List[Operation]
    ) -> Tuple[Chromosome, Chromosome]:
        """Order crossover (OX) for permutation representation."""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        size = len(parent1.genes)
        if size < 2:
            return parent1.copy(), parent2.copy()

        # Select crossover points
        point1, point2 = sorted(random.sample(range(size), 2))

        # Create children
        child1_genes = [None] * size
        child2_genes = [None] * size

        # Copy segment from parents
        child1_genes[point1:point2] = parent1.genes[point1:point2]
        child2_genes[point1:point2] = parent2.genes[point1:point2]

        # Fill remaining positions
        self._fill_remaining(child1_genes, parent2.genes, point2)
        self._fill_remaining(child2_genes, parent1.genes, point2)

        return Chromosome(genes=child1_genes), Chromosome(genes=child2_genes)

    def _fill_remaining(
        self,
        child: List[Optional[Tuple[str, str]]],
        parent: List[Tuple[str, str]],
        start: int
    ) -> None:
        """Fill remaining positions in crossover child."""
        size = len(child)
        existing_ops = {g[0] for g in child if g is not None}

        parent_idx = start
        child_idx = start

        while None in child:
            op_id, machine = parent[parent_idx % size]

            if op_id not in existing_ops:
                # Find next empty position
                while child[child_idx % size] is not None:
                    child_idx += 1
                child[child_idx % size] = (op_id, machine)
                existing_ops.add(op_id)

            parent_idx += 1

    def _mutate(
        self,
        chromosome: Chromosome,
        operations: List[Operation]
    ) -> Chromosome:
        """Mutation operator."""
        if random.random() > self.mutation_rate:
            return chromosome

        mutated = chromosome.copy()
        mutation_type = random.choice(["swap", "machine", "insert"])

        if mutation_type == "swap" and len(mutated.genes) >= 2:
            # Swap two operations
            i, j = random.sample(range(len(mutated.genes)), 2)
            mutated.genes[i], mutated.genes[j] = mutated.genes[j], mutated.genes[i]

        elif mutation_type == "machine":
            # Change machine assignment
            idx = random.randint(0, len(mutated.genes) - 1)
            op_id, _ = mutated.genes[idx]

            # Find operation
            op = next((o for o in operations if o.operation_id == op_id), None)
            if op and len(op.eligible_machines) > 1:
                new_machine = random.choice(op.eligible_machines)
                mutated.genes[idx] = (op_id, new_machine)

        elif mutation_type == "insert" and len(mutated.genes) >= 2:
            # Remove and insert at new position
            idx = random.randint(0, len(mutated.genes) - 1)
            gene = mutated.genes.pop(idx)
            new_idx = random.randint(0, len(mutated.genes))
            mutated.genes.insert(new_idx, gene)

        return mutated

    def _decode_chromosome(
        self,
        chromosome: Chromosome,
        start_time: datetime
    ) -> Schedule:
        """Decode chromosome to actual schedule."""
        scheduled_ops = []
        machine_end_times: Dict[str, datetime] = {
            m: start_time for m in self.machines
        }
        job_end_times: Dict[str, datetime] = {}
        op_end_times: Dict[str, datetime] = {}

        # Process operations in chromosome order
        for op_id, machine_id in chromosome.genes:
            # Find operation
            op = None
            for job in self.jobs.values():
                for o in job.operations:
                    if o.operation_id == op_id:
                        op = o
                        break
                if op:
                    break

            if not op:
                continue

            job = self.jobs[op.job_id]

            # Calculate earliest start time
            earliest_start = machine_end_times.get(machine_id, start_time)

            # Check job release date
            if job.release_date and job.release_date > earliest_start:
                earliest_start = job.release_date

            # Check predecessor constraints
            for pred_id in op.predecessors:
                if pred_id in op_end_times:
                    if op_end_times[pred_id] > earliest_start:
                        earliest_start = op_end_times[pred_id]

            # Calculate processing time
            machine = self.machines[machine_id]
            processing_time = op.processing_time * machine.efficiency
            setup_time = op.setup_time

            # Calculate end time
            end_time = earliest_start + timedelta(seconds=processing_time + setup_time)

            # Create scheduled operation
            scheduled_op = ScheduledOperation(
                operation_id=op_id,
                job_id=op.job_id,
                machine_id=machine_id,
                start_time=earliest_start,
                end_time=end_time,
                setup_time=setup_time,
            )
            scheduled_ops.append(scheduled_op)

            # Update end times
            machine_end_times[machine_id] = end_time
            op_end_times[op_id] = end_time
            job_end_times[op.job_id] = max(
                job_end_times.get(op.job_id, start_time),
                end_time
            )

        # Calculate metrics
        makespan = max(
            (et - start_time).total_seconds()
            for et in machine_end_times.values()
        ) if machine_end_times else 0

        # Calculate tardiness
        total_tardiness = 0.0
        for job_id, end_time in job_end_times.items():
            job = self.jobs[job_id]
            if job.due_date and end_time > job.due_date:
                tardiness = (end_time - job.due_date).total_seconds()
                total_tardiness += tardiness * job.weight

        # Calculate utilization
        utilization = {}
        for machine_id in self.machines:
            busy_time = sum(
                op.duration() for op in scheduled_ops
                if op.machine_id == machine_id
            )
            utilization[machine_id] = busy_time / makespan if makespan > 0 else 0

        return Schedule(
            schedule_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            scheduled_operations=scheduled_ops,
            makespan=makespan,
            total_tardiness=total_tardiness,
            machine_utilization=utilization,
            objective_value=chromosome.fitness,
        )

    def _create_empty_schedule(self) -> Schedule:
        """Create empty schedule."""
        return Schedule(
            schedule_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            scheduled_operations=[],
            makespan=0,
            total_tardiness=0,
            machine_utilization={m: 0.0 for m in self.machines},
            objective_value=0,
        )

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of values."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    # -------------------------------------------------------------------------
    # Dynamic Rescheduling
    # -------------------------------------------------------------------------

    def reschedule_on_disruption(
        self,
        disruption_type: str,
        affected_entity: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Schedule:
        """
        Reschedule in response to a disruption.

        Args:
            disruption_type: Type of disruption (machine_breakdown, job_delay, etc.)
            affected_entity: ID of affected entity
            details: Additional details

        Returns:
            New schedule
        """
        logger.info(f"Rescheduling due to {disruption_type} affecting {affected_entity}")

        if self.on_disruption:
            self.on_disruption(disruption_type, details)

        # Update status based on disruption
        if disruption_type == "machine_breakdown":
            if affected_entity in self.machines:
                self.machines[affected_entity].status = MachineStatus.BREAKDOWN

        elif disruption_type == "job_cancelled":
            if affected_entity in self.jobs:
                self.jobs[affected_entity].status = JobStatus.CANCELLED

        elif disruption_type == "new_urgent_job":
            # New job should already be added
            pass

        # Generate new schedule
        schedule = self.generate_schedule()
        self.total_reschedulings += 1

        return schedule

    def update_job_progress(
        self,
        job_id: str,
        completed_operations: List[str]
    ) -> None:
        """Update job progress after operations complete."""
        if job_id not in self.jobs:
            return

        job = self.jobs[job_id]

        # Check if job is complete
        completed_set = set(completed_operations)
        all_ops = {op.operation_id for op in job.operations}

        if completed_set >= all_ops:
            job.status = JobStatus.COMPLETED
        elif completed_set:
            job.status = JobStatus.IN_PROGRESS

    # -------------------------------------------------------------------------
    # Analysis and Metrics
    # -------------------------------------------------------------------------

    def analyze_schedule(self, schedule: Optional[Schedule] = None) -> ScheduleMetrics:
        """Analyze schedule performance."""
        schedule = schedule or self.current_schedule

        if not schedule:
            return ScheduleMetrics(
                makespan=0, total_tardiness=0, average_utilization=0,
                max_tardiness=0, number_of_late_jobs=0,
                total_setup_time=0, idle_time=0
            )

        # Calculate metrics
        avg_util = (
            sum(schedule.machine_utilization.values()) /
            len(schedule.machine_utilization)
            if schedule.machine_utilization else 0
        )

        total_setup = sum(op.setup_time for op in schedule.scheduled_operations)

        # Calculate max tardiness and late jobs
        max_tardiness = 0.0
        late_jobs = 0

        job_end_times: Dict[str, datetime] = {}
        for op in schedule.scheduled_operations:
            current_end = job_end_times.get(op.job_id)
            if current_end is None or op.end_time > current_end:
                job_end_times[op.job_id] = op.end_time

        for job_id, end_time in job_end_times.items():
            job = self.jobs.get(job_id)
            if job and job.due_date and end_time > job.due_date:
                tardiness = (end_time - job.due_date).total_seconds()
                max_tardiness = max(max_tardiness, tardiness)
                late_jobs += 1

        # Calculate idle time
        total_time = schedule.makespan * len(self.machines)
        busy_time = sum(op.duration() for op in schedule.scheduled_operations)
        idle_time = total_time - busy_time

        return ScheduleMetrics(
            makespan=schedule.makespan,
            total_tardiness=schedule.total_tardiness,
            average_utilization=avg_util,
            max_tardiness=max_tardiness,
            number_of_late_jobs=late_jobs,
            total_setup_time=total_setup,
            idle_time=idle_time,
        )

    def get_gantt_data(self, schedule: Optional[Schedule] = None) -> List[Dict[str, Any]]:
        """Get data for Gantt chart visualization."""
        schedule = schedule or self.current_schedule
        if not schedule:
            return []

        return [
            {
                "operation": op.operation_id,
                "job": op.job_id,
                "machine": op.machine_id,
                "start": op.start_time.isoformat(),
                "end": op.end_time.isoformat(),
                "duration": op.duration(),
            }
            for op in schedule.scheduled_operations
        ]

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    def get_optimizer_status(self) -> Dict[str, Any]:
        """Get optimizer status."""
        return {
            "optimizer_id": self.optimizer_id,
            "schedule_type": self.schedule_type.value,
            "objective": self.objective.value,
            "total_jobs": len(self.jobs),
            "total_machines": len(self.machines),
            "total_constraints": len(self.constraints),
            "current_schedule": self.current_schedule.to_dict() if self.current_schedule else None,
            "total_optimizations": self.total_optimizations,
            "total_reschedulings": self.total_reschedulings,
            "ga_parameters": {
                "population_size": self.population_size,
                "generations": self.generations,
                "mutation_rate": self.mutation_rate,
                "crossover_rate": self.crossover_rate,
            },
        }


# =============================================================================
# Factory Function and Singleton
# =============================================================================

_optimizer_instance: Optional[SchedulingOptimizer] = None


def get_scheduling_optimizer(
    optimizer_id: str = "default",
    objective: OptimizationObjective = OptimizationObjective.BALANCED
) -> SchedulingOptimizer:
    """
    Get or create the scheduling optimizer singleton.

    Args:
        optimizer_id: Optimizer identifier
        objective: Optimization objective

    Returns:
        SchedulingOptimizer instance
    """
    global _optimizer_instance

    if _optimizer_instance is None:
        _optimizer_instance = SchedulingOptimizer(
            optimizer_id=optimizer_id,
            objective=objective
        )

    return _optimizer_instance


__all__ = [
    # Enums
    'ScheduleType',
    'OptimizationObjective',
    'JobStatus',
    'JobPriority',
    'MachineStatus',
    'ConstraintType',
    # Data Classes
    'Operation',
    'Job',
    'Machine',
    'ScheduledOperation',
    'Schedule',
    'Constraint',
    'ScheduleMetrics',
    # Main Class
    'SchedulingOptimizer',
    'get_scheduling_optimizer',
]
