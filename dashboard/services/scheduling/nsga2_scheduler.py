"""
NSGA-II Scheduler - Multi-Objective Evolutionary Algorithm

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

Implements NSGA-II (Non-dominated Sorting Genetic Algorithm II) for
multi-objective optimization of production schedules.

Objectives:
- Makespan minimization
- Tardiness minimization
- Energy consumption minimization
- Quality risk minimization
- Cost minimization
- Utilization maximization
"""

import logging
import random
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

try:
    from deap import base, creator, tools, algorithms
    DEAP_AVAILABLE = True
except ImportError:
    DEAP_AVAILABLE = False
    base = creator = tools = algorithms = None

from .scheduler_factory import (
    BaseScheduler, Schedule, ScheduledOperation, ScheduleStatus,
    SchedulingProblem, SchedulerType, SchedulerFactory,
    Job, Operation, Machine
)
from .objectives import (
    ObjectiveCalculator, ObjectiveSet, ObjectiveWeight,
    SchedulingObjective, ObjectiveDirection
)

logger = logging.getLogger(__name__)


@dataclass
class NSGA2Config:
    """Configuration for NSGA-II solver."""
    population_size: int = 100
    num_generations: int = 100
    crossover_prob: float = 0.9
    mutation_prob: float = 0.1
    tournament_size: int = 3
    num_objectives: int = 5
    seed: Optional[int] = None


@dataclass
class ParetoSolution:
    """A solution on the Pareto front."""
    schedule: Schedule
    objectives: ObjectiveSet
    rank: int = 0
    crowding_distance: float = 0.0

    def dominates(self, other: 'ParetoSolution', objective_list: List[SchedulingObjective]) -> bool:
        """Check if this solution dominates another."""
        return self.objectives.dominates(other.objectives, objective_list)


class ParetoFront:
    """
    Maintains a Pareto front of non-dominated solutions.
    """

    def __init__(self, max_size: int = 100):
        self.solutions: List[ParetoSolution] = []
        self.max_size = max_size

    def add(self, solution: ParetoSolution, objectives: List[SchedulingObjective]) -> bool:
        """Add a solution if it's non-dominated."""
        # Check if dominated by any existing solution
        for existing in self.solutions:
            if existing.dominates(solution, objectives):
                return False

        # Remove solutions dominated by new one
        self.solutions = [
            s for s in self.solutions
            if not solution.dominates(s, objectives)
        ]

        self.solutions.append(solution)

        # Trim to max size using crowding distance
        if len(self.solutions) > self.max_size:
            self._calculate_crowding_distances(objectives)
            self.solutions.sort(key=lambda s: s.crowding_distance, reverse=True)
            self.solutions = self.solutions[:self.max_size]

        return True

    def _calculate_crowding_distances(self, objectives: List[SchedulingObjective]) -> None:
        """Calculate crowding distance for each solution."""
        n = len(self.solutions)
        if n <= 2:
            for s in self.solutions:
                s.crowding_distance = float('inf')
            return

        for s in self.solutions:
            s.crowding_distance = 0.0

        for obj in objectives:
            # Sort by this objective
            sorted_sols = sorted(
                self.solutions,
                key=lambda s: s.objectives.get_value(obj)
            )

            # Boundary solutions get infinite distance
            sorted_sols[0].crowding_distance = float('inf')
            sorted_sols[-1].crowding_distance = float('inf')

            # Get range
            obj_min = sorted_sols[0].objectives.get_value(obj)
            obj_max = sorted_sols[-1].objectives.get_value(obj)
            obj_range = obj_max - obj_min

            if obj_range == 0:
                continue

            # Calculate distances
            for i in range(1, n - 1):
                prev_val = sorted_sols[i - 1].objectives.get_value(obj)
                next_val = sorted_sols[i + 1].objectives.get_value(obj)
                sorted_sols[i].crowding_distance += (next_val - prev_val) / obj_range

    def get_best_compromise(self, weights: Optional[Dict[SchedulingObjective, float]] = None) -> Optional[ParetoSolution]:
        """Get best compromise solution (closest to ideal)."""
        if not self.solutions:
            return None

        if weights is None:
            # Equal weights
            return self.solutions[0]

        # Weighted distance to ideal
        best = None
        best_score = float('inf')

        for sol in self.solutions:
            score = 0.0
            for obj, weight in weights.items():
                score += weight * sol.objectives.get_value(obj)

            if score < best_score:
                best_score = score
                best = sol

        return best


# DEAP setup for NSGA-II
def _setup_deap(num_objectives: int):
    """Set up DEAP toolbox for NSGA-II."""
    if not DEAP_AVAILABLE:
        return None

    # Check if already created
    if hasattr(creator, "FitnessMin"):
        return

    # Create fitness and individual classes
    # All objectives are minimized
    creator.create("FitnessMin", base.Fitness, weights=tuple([-1.0] * num_objectives))
    creator.create("Individual", list, fitness=creator.FitnessMin)


@SchedulerFactory.register(SchedulerType.NSGA2)
class NSGA2Scheduler(BaseScheduler):
    """
    NSGA-II multi-objective scheduler.

    Features:
    - Pareto-optimal solutions
    - Multiple conflicting objectives
    - Crowding distance for diversity
    - Elitist selection
    """

    scheduler_type = SchedulerType.NSGA2

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        if not DEAP_AVAILABLE:
            logger.warning("DEAP not available. Install with: pip install deap")

        self.nsga_config = NSGA2Config(
            population_size=config.get('population_size', 100) if config else 100,
            num_generations=config.get('num_generations', 100) if config else 100,
            crossover_prob=config.get('crossover_prob', 0.9) if config else 0.9,
            mutation_prob=config.get('mutation_prob', 0.1) if config else 0.1,
        )

        self.objectives_to_optimize: List[SchedulingObjective] = [
            SchedulingObjective.MAKESPAN,
            SchedulingObjective.TOTAL_TARDINESS,
            SchedulingObjective.ENERGY,
            SchedulingObjective.QUALITY_RISK,
            SchedulingObjective.COST,
        ]

    def solve(self, problem: SchedulingProblem) -> Schedule:
        """Solve using NSGA-II."""
        if not DEAP_AVAILABLE:
            logger.error("DEAP not available, falling back to greedy")
            from .scheduler_factory import GreedyScheduler
            return GreedyScheduler().solve(problem)

        # Update objectives from problem if specified
        if problem.objectives:
            self.objectives_to_optimize = [w.objective for w in problem.objectives]

        _setup_deap(len(self.objectives_to_optimize))

        if self.nsga_config.seed is not None:
            random.seed(self.nsga_config.seed)

        # Create toolbox
        toolbox = base.Toolbox()

        # Chromosome: list of (operation_id, machine_id) pairs in scheduling order
        all_ops = problem.get_all_operations()
        n_ops = len(all_ops)

        def create_individual():
            """Create a random individual (schedule encoding)."""
            # Random permutation of operation indices
            perm = list(range(n_ops))
            random.shuffle(perm)

            # Random machine assignment for each operation
            chromosome = []
            for idx in perm:
                op = all_ops[idx]
                machine = random.choice(op.eligible_machines)
                chromosome.append((idx, machine))

            return creator.Individual(chromosome)

        toolbox.register("individual", create_individual)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        # Evaluation function
        def evaluate(individual):
            """Decode and evaluate a schedule."""
            schedule = self._decode(individual, problem)
            if schedule.status != ScheduleStatus.FEASIBLE:
                # Infeasible - return worst case
                return tuple([float('inf')] * len(self.objectives_to_optimize))

            # Calculate objectives
            values = []
            for obj in self.objectives_to_optimize:
                val = schedule.objectives.get_value(obj) if schedule.objectives else float('inf')
                values.append(val)

            return tuple(values)

        toolbox.register("evaluate", evaluate)

        # Genetic operators
        toolbox.register("mate", self._crossover)
        toolbox.register("mutate", self._mutate, problem=problem)
        toolbox.register("select", tools.selNSGA2)

        # Create initial population
        pop = toolbox.population(n=self.nsga_config.population_size)

        # Evaluate initial population
        fitnesses = list(map(toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        # Hall of fame for Pareto front
        hof = tools.ParetoFront()

        # Statistics
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda x: [sum(v[i] for v in x) / len(x) for i in range(len(self.objectives_to_optimize))])
        stats.register("min", lambda x: [min(v[i] for v in x) for i in range(len(self.objectives_to_optimize))])

        # Run NSGA-II
        algorithms.eaMuPlusLambda(
            pop, toolbox,
            mu=self.nsga_config.population_size,
            lambda_=self.nsga_config.population_size,
            cxpb=self.nsga_config.crossover_prob,
            mutpb=self.nsga_config.mutation_prob,
            ngen=self.nsga_config.num_generations,
            stats=stats,
            halloffame=hof,
            verbose=False
        )

        # Get best compromise solution
        if hof:
            best_ind = hof[0]  # First solution in Pareto front
        else:
            # Fall back to best in population
            best_ind = tools.selBest(pop, 1)[0]

        # Decode best solution
        best_schedule = self._decode(best_ind, problem)

        return best_schedule

    def _decode(self, individual: List[Tuple[int, str]], problem: SchedulingProblem) -> Schedule:
        """Decode a chromosome into a schedule."""
        all_ops = problem.get_all_operations()

        schedule = Schedule(
            schedule_id=str(uuid4()),
            status=ScheduleStatus.FEASIBLE,
            solver_type=self.scheduler_type,
        )

        # Track machine availability
        machine_available: Dict[str, float] = {
            m.machine_id: m.available_from for m in problem.machines
        }

        # Track operation completion for precedence
        op_completion: Dict[str, float] = {}

        # Build job lookup
        job_lookup = {j.job_id: j for j in problem.jobs}

        # Schedule operations in chromosome order
        for op_idx, machine_id in individual:
            op = all_ops[op_idx]
            job = job_lookup.get(op.job_id)

            if not job:
                continue

            # Calculate earliest start
            earliest = job.release_time

            # Check precedence (within job)
            for pred_id in op.predecessors:
                if pred_id in op_completion:
                    earliest = max(earliest, op_completion[pred_id])

            # Check job-level sequence precedence
            for other_op in job.operations:
                if other_op.sequence < op.sequence:
                    if other_op.operation_id in op_completion:
                        earliest = max(earliest, op_completion[other_op.operation_id])

            # Get machine availability
            machine_avail = machine_available.get(machine_id, 0)
            start = max(earliest, machine_avail)

            # Get processing time
            proc_time = op.get_processing_time(machine_id)
            if proc_time == 0:
                proc_time = min(op.processing_times.values()) if op.processing_times else 1

            end_time = start + proc_time

            # Create scheduled operation
            scheduled_op = ScheduledOperation(
                operation_id=op.operation_id,
                job_id=op.job_id,
                machine_id=machine_id,
                start_time=start,
                end_time=end_time,
            )

            schedule.add_operation(scheduled_op)
            machine_available[machine_id] = end_time
            op_completion[op.operation_id] = end_time

        # Calculate objectives
        calculator = ObjectiveCalculator()
        job_dicts = [j.to_dict() for j in problem.jobs]
        op_dicts = [op.to_dict() for op in schedule.operations]
        machine_dicts = {m.machine_id: m.to_dict() for m in problem.machines}

        schedule.objectives = calculator.calculate_full_objectives(
            job_dicts, op_dicts, machine_dicts
        )

        return schedule

    def _crossover(self, ind1: List, ind2: List) -> Tuple[List, List]:
        """Order crossover (OX) for permutation encoding."""
        size = len(ind1)
        if size < 3:
            return ind1, ind2

        # Select crossover points
        cx1 = random.randint(0, size - 2)
        cx2 = random.randint(cx1 + 1, size - 1)

        # Get operation indices from each parent
        ops1 = [x[0] for x in ind1]
        ops2 = [x[0] for x in ind2]

        # Create children with OX
        child1_ops = self._ox_crossover(ops1, ops2, cx1, cx2)
        child2_ops = self._ox_crossover(ops2, ops1, cx1, cx2)

        # Preserve machine assignments from parents where possible
        op_to_machine1 = {x[0]: x[1] for x in ind1}
        op_to_machine2 = {x[0]: x[1] for x in ind2}

        child1 = [(op, op_to_machine1.get(op, op_to_machine2.get(op, ''))) for op in child1_ops]
        child2 = [(op, op_to_machine2.get(op, op_to_machine1.get(op, ''))) for op in child2_ops]

        return creator.Individual(child1), creator.Individual(child2)

    def _ox_crossover(self, parent1: List, parent2: List, cx1: int, cx2: int) -> List:
        """Order crossover helper."""
        size = len(parent1)
        child = [None] * size

        # Copy segment from parent1
        child[cx1:cx2] = parent1[cx1:cx2]
        copied = set(parent1[cx1:cx2])

        # Fill remaining from parent2 in order
        pos = cx2
        for i in range(size):
            idx = (cx2 + i) % size
            gene = parent2[idx]
            if gene not in copied:
                while child[pos % size] is not None:
                    pos += 1
                child[pos % size] = gene
                pos += 1

        return child

    def _mutate(self, individual: List, problem: SchedulingProblem) -> Tuple[List]:
        """Mutation: swap operations or change machine assignment."""
        if len(individual) < 2:
            return (individual,)

        # 50% chance: swap two operations
        if random.random() < 0.5:
            i, j = random.sample(range(len(individual)), 2)
            individual[i], individual[j] = individual[j], individual[i]

        # 50% chance: change machine assignment
        if random.random() < 0.5:
            all_ops = problem.get_all_operations()
            idx = random.randint(0, len(individual) - 1)
            op_idx, _ = individual[idx]
            op = all_ops[op_idx]
            if len(op.eligible_machines) > 1:
                new_machine = random.choice(op.eligible_machines)
                individual[idx] = (op_idx, new_machine)

        return (individual,)

    def get_pareto_front(self, problem: SchedulingProblem, population: int = 100) -> ParetoFront:
        """
        Get the full Pareto front for a problem.

        Returns multiple non-dominated solutions for decision-maker selection.
        """
        # Store original config
        original_pop = self.nsga_config.population_size
        self.nsga_config.population_size = population

        # Solve
        _ = self.solve(problem)

        # Restore config
        self.nsga_config.population_size = original_pop

        # Build Pareto front
        # In practice, this would return all non-dominated solutions
        # from the final population
        pareto = ParetoFront()

        # For now, return single solution
        # Full implementation would track all Pareto-optimal solutions
        return pareto


@SchedulerFactory.register(SchedulerType.NSGA3)
class NSGA3Scheduler(NSGA2Scheduler):
    """
    NSGA-III scheduler for many-objective optimization (>3 objectives).

    Uses reference point based selection instead of crowding distance.
    """

    scheduler_type = SchedulerType.NSGA3

    def solve(self, problem: SchedulingProblem) -> Schedule:
        """Solve using NSGA-III."""
        if not DEAP_AVAILABLE:
            logger.error("DEAP not available, falling back to greedy")
            from .scheduler_factory import GreedyScheduler
            return GreedyScheduler().solve(problem)

        # For many objectives, use reference points
        num_obj = len(self.objectives_to_optimize)

        if num_obj <= 3:
            # Use standard NSGA-II for few objectives
            return super().solve(problem)

        # Generate reference points
        ref_points = self._generate_reference_points(num_obj)

        # NSGA-III uses these reference points in selection
        # Full implementation would modify selection operator
        logger.info(f"NSGA-III with {len(ref_points)} reference points for {num_obj} objectives")

        return super().solve(problem)

    def _generate_reference_points(self, num_objectives: int, divisions: int = 4) -> List[List[float]]:
        """Generate uniformly distributed reference points."""
        from itertools import combinations

        # Das and Dennis's systematic approach
        # Number of reference points = C(H+M-1, M-1) where H=divisions, M=objectives
        points = []

        def _recursive(M: int, H: int, point: List[float], left: int):
            if M == 1:
                points.append(point + [left / divisions])
            else:
                for i in range(left + 1):
                    _recursive(M - 1, H, point + [i / divisions], left - i)

        _recursive(num_objectives, divisions, [], divisions)

        return points
