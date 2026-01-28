"""
LEGO Factory v3 - NSGA-II Multi-Objective Scheduler
====================================================
Non-dominated Sorting Genetic Algorithm II for multi-objective job scheduling.

This scheduler provides an alternative to the CP-SAT solver when multiple
competing objectives need to be optimized simultaneously (Pareto optimization).

Supports objectives:
- Makespan minimization
- Tardiness minimization
- Setup time minimization
- Machine utilization balancing
- Priority-weighted completion time
- Energy consumption (optional)
"""

import logging
import random
import copy
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import math

import numpy as np

from services.mes.scheduling_service import (
    ScheduleJob,
    Machine,
    ScheduledJob,
    ScheduleResult
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for NSGA-II
# =============================================================================

@dataclass
class Gene:
    """
    Single gene representing a job assignment.

    Attributes:
        job_id: Identifier of the job
        machine_id: Assigned machine identifier
        position: Position in the job sequence for the machine
    """
    job_id: str
    machine_id: str
    position: int


@dataclass
class Chromosome:
    """
    Chromosome representing a complete schedule solution.

    The chromosome encodes:
    - Job-to-machine assignments
    - Job sequencing on each machine

    Attributes:
        genes: List of Gene objects
        objectives: Dictionary of objective name to value
        rank: Pareto front rank (0 = best)
        crowding_distance: Crowding distance for diversity preservation
        is_feasible: Whether the chromosome satisfies all constraints
        constraint_violations: Count of constraint violations
    """
    genes: List[Gene] = field(default_factory=list)
    objectives: Dict[str, float] = field(default_factory=dict)
    rank: int = 0
    crowding_distance: float = 0.0
    is_feasible: bool = True
    constraint_violations: int = 0

    def __lt__(self, other: 'Chromosome') -> bool:
        """Comparison for sorting: prefer lower rank, then higher crowding distance."""
        if self.rank != other.rank:
            return self.rank < other.rank
        return self.crowding_distance > other.crowding_distance

    def dominates(self, other: 'Chromosome') -> bool:
        """Check if this chromosome dominates another (Pareto dominance)."""
        dominated = False
        for obj_name in self.objectives:
            self_val = self.objectives.get(obj_name, float('inf'))
            other_val = other.objectives.get(obj_name, float('inf'))
            if self_val > other_val:
                return False
            if self_val < other_val:
                dominated = True
        return dominated


@dataclass
class DecodedSchedule:
    """
    Decoded schedule from a chromosome.

    Attributes:
        jobs: List of ScheduledJob objects
        machine_sequences: Dictionary mapping machine_id to ordered list of job_ids
        job_times: Dictionary mapping job_id to (start_time, end_time)
        makespan: Total schedule duration in minutes
    """
    jobs: List[ScheduledJob] = field(default_factory=list)
    machine_sequences: Dict[str, List[str]] = field(default_factory=dict)
    job_times: Dict[str, Tuple[datetime, datetime]] = field(default_factory=dict)
    makespan: float = 0.0


@dataclass
class ObjectiveConfig:
    """Configuration for an optimization objective."""
    name: str
    minimize: bool = True
    weight: float = 1.0
    enabled: bool = True


class ObjectiveType(Enum):
    """Available objective types."""
    MAKESPAN = "makespan"
    TARDINESS = "tardiness"
    SETUP_TIME = "setup_time"
    UTILIZATION = "utilization"
    PRIORITY_COMPLETION = "priority_completion"
    ENERGY = "energy"


# =============================================================================
# NSGA-II Multi-Objective Scheduler
# =============================================================================

class NSGA2Scheduler:
    """
    NSGA-II (Non-dominated Sorting Genetic Algorithm II) Multi-Objective Scheduler.

    This scheduler uses evolutionary computation to find Pareto-optimal schedules
    that balance multiple competing objectives such as makespan, tardiness,
    setup time, and machine utilization.

    The algorithm maintains a population of schedule solutions and evolves them
    through selection, crossover, and mutation, using non-dominated sorting
    and crowding distance to preserve solution diversity.

    Attributes:
        jobs: List of jobs to schedule
        machines: List of available machines
        population: Current population of chromosomes
        pareto_front: List of non-dominated solutions
        objectives: List of objective configurations
        job_lookup: Dictionary for fast job lookups
        machine_lookup: Dictionary for fast machine lookups
        base_time: Reference time for scheduling

    Example:
        >>> scheduler = NSGA2Scheduler()
        >>> result = scheduler.optimize(
        ...     jobs=jobs,
        ...     machines=machines,
        ...     objectives=['makespan', 'tardiness'],
        ...     generations=100,
        ...     pop_size=100
        ... )
        >>> pareto_front = scheduler.get_pareto_front()
        >>> best_schedule = scheduler.get_knee_point()
    """

    def __init__(self):
        """Initialize the NSGA-II scheduler."""
        self.jobs: List[ScheduleJob] = []
        self.machines: List[Machine] = []
        self.population: List[Chromosome] = []
        self.pareto_front: List[Chromosome] = []
        self.objectives: List[ObjectiveConfig] = []
        self.job_lookup: Dict[str, ScheduleJob] = {}
        self.machine_lookup: Dict[str, Machine] = {}
        self.base_time: datetime = datetime.utcnow()

        # Setup time matrix (job_id, prev_job_id) -> setup_time
        self.setup_matrix: Dict[Tuple[str, str], int] = {}

        # Energy consumption per machine (kWh per minute)
        self.energy_rates: Dict[str, float] = {}

        # Random seed for reproducibility
        self._random_state = None

    def set_random_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._random_state = seed
        random.seed(seed)
        np.random.seed(seed)

    def set_setup_matrix(self, matrix: Dict[Tuple[str, str], int]) -> None:
        """
        Set sequence-dependent setup times.

        Args:
            matrix: Dictionary mapping (current_job, previous_job) to setup time in minutes
        """
        self.setup_matrix = matrix

    def set_energy_rates(self, rates: Dict[str, float]) -> None:
        """
        Set energy consumption rates per machine.

        Args:
            rates: Dictionary mapping machine_id to kWh per minute
        """
        self.energy_rates = rates

    # =========================================================================
    # Core NSGA-II Algorithm
    # =========================================================================

    def initialize_population(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        pop_size: int = 100
    ) -> List[Chromosome]:
        """
        Initialize the population with random valid chromosomes.

        Args:
            jobs: List of jobs to schedule
            machines: List of available machines
            pop_size: Population size

        Returns:
            List of initialized chromosomes
        """
        self.jobs = jobs
        self.machines = machines
        self.job_lookup = {j.job_id: j for j in jobs}
        self.machine_lookup = {m.machine_id: m for m in machines}
        self.base_time = datetime.utcnow()

        population = []

        for _ in range(pop_size):
            chromosome = self._create_random_chromosome()

            # Repair if needed to ensure feasibility
            if not self.check_all_constraints(chromosome):
                chromosome = self.repair_chromosome(chromosome)

            population.append(chromosome)

        self.population = population
        logger.info(f"Initialized population with {pop_size} chromosomes")

        return population

    def _create_random_chromosome(self) -> Chromosome:
        """Create a random valid chromosome."""
        genes = []
        machine_positions: Dict[str, int] = {m.machine_id: 0 for m in self.machines}

        # Shuffle jobs for random ordering
        shuffled_jobs = list(self.jobs)
        random.shuffle(shuffled_jobs)

        for job in shuffled_jobs:
            # Get eligible machines
            eligible = job.eligible_machines if job.eligible_machines else [m.machine_id for m in self.machines]

            # Filter by capabilities if needed
            valid_machines = [m_id for m_id in eligible if m_id in self.machine_lookup]

            if not valid_machines:
                valid_machines = [self.machines[0].machine_id]  # Fallback

            # Randomly select machine
            selected_machine = random.choice(valid_machines)

            # Assign position
            position = machine_positions[selected_machine]
            machine_positions[selected_machine] += 1

            genes.append(Gene(
                job_id=job.job_id,
                machine_id=selected_machine,
                position=position
            ))

        return Chromosome(genes=genes)

    def evaluate_objectives(self, chromosome: Chromosome) -> Dict[str, float]:
        """
        Evaluate all objectives for a chromosome.

        Args:
            chromosome: Chromosome to evaluate

        Returns:
            Dictionary mapping objective names to values
        """
        # Decode chromosome to schedule
        schedule = self.decode_chromosome(chromosome)

        objectives = {}

        for obj_config in self.objectives:
            if not obj_config.enabled:
                continue

            if obj_config.name == ObjectiveType.MAKESPAN.value:
                objectives[obj_config.name] = self.objective_makespan(schedule)
            elif obj_config.name == ObjectiveType.TARDINESS.value:
                objectives[obj_config.name] = self.objective_tardiness(schedule)
            elif obj_config.name == ObjectiveType.SETUP_TIME.value:
                objectives[obj_config.name] = self.objective_setup_time(schedule)
            elif obj_config.name == ObjectiveType.UTILIZATION.value:
                objectives[obj_config.name] = self.objective_machine_utilization(schedule)
            elif obj_config.name == ObjectiveType.PRIORITY_COMPLETION.value:
                objectives[obj_config.name] = self.objective_priority_weighted_completion(schedule)
            elif obj_config.name == ObjectiveType.ENERGY.value:
                objectives[obj_config.name] = self.objective_energy_consumption(schedule)

        chromosome.objectives = objectives
        return objectives

    def fast_non_dominated_sort(
        self,
        population: List[Chromosome]
    ) -> List[List[Chromosome]]:
        """
        Perform fast non-dominated sorting on the population.

        This is the core NSGA-II ranking algorithm that sorts solutions
        into Pareto fronts. Front 0 contains non-dominated solutions,
        Front 1 contains solutions dominated only by Front 0, etc.

        Args:
            population: List of chromosomes to sort

        Returns:
            List of fronts, where each front is a list of chromosomes
        """
        n = len(population)

        # domination_count[i] = number of solutions that dominate solution i
        domination_count = [0] * n

        # dominated_solutions[i] = list of solutions that solution i dominates
        dominated_solutions: List[List[int]] = [[] for _ in range(n)]

        fronts: List[List[Chromosome]] = [[]]

        # Calculate domination relationships
        for i in range(n):
            for j in range(i + 1, n):
                if population[i].dominates(population[j]):
                    dominated_solutions[i].append(j)
                    domination_count[j] += 1
                elif population[j].dominates(population[i]):
                    dominated_solutions[j].append(i)
                    domination_count[i] += 1

        # Find first front (non-dominated solutions)
        for i in range(n):
            if domination_count[i] == 0:
                population[i].rank = 0
                fronts[0].append(population[i])

        # Generate subsequent fronts
        current_front = 0
        while fronts[current_front]:
            next_front = []

            for chromosome in fronts[current_front]:
                idx = population.index(chromosome)

                for dominated_idx in dominated_solutions[idx]:
                    domination_count[dominated_idx] -= 1

                    if domination_count[dominated_idx] == 0:
                        population[dominated_idx].rank = current_front + 1
                        next_front.append(population[dominated_idx])

            current_front += 1
            fronts.append(next_front)

        # Remove empty last front
        if not fronts[-1]:
            fronts.pop()

        return fronts

    def calculate_crowding_distance(self, front: List[Chromosome]) -> None:
        """
        Calculate crowding distance for solutions in a front.

        Crowding distance measures how close a solution is to its neighbors
        in objective space. Higher distance means more isolated solution,
        which helps preserve diversity.

        Args:
            front: List of chromosomes in the same Pareto front
        """
        n = len(front)

        if n == 0:
            return

        # Initialize crowding distances
        for chromosome in front:
            chromosome.crowding_distance = 0.0

        if n <= 2:
            # Boundary solutions get infinite distance
            for chromosome in front:
                chromosome.crowding_distance = float('inf')
            return

        # Get objective names
        obj_names = list(front[0].objectives.keys())

        for obj_name in obj_names:
            # Sort by this objective
            front.sort(key=lambda c: c.objectives.get(obj_name, float('inf')))

            # Boundary points get infinite distance
            front[0].crowding_distance = float('inf')
            front[-1].crowding_distance = float('inf')

            # Calculate range for normalization
            obj_min = front[0].objectives.get(obj_name, 0)
            obj_max = front[-1].objectives.get(obj_name, 0)
            obj_range = obj_max - obj_min

            if obj_range == 0:
                continue

            # Calculate crowding distance for intermediate solutions
            for i in range(1, n - 1):
                prev_val = front[i - 1].objectives.get(obj_name, 0)
                next_val = front[i + 1].objectives.get(obj_name, 0)
                front[i].crowding_distance += (next_val - prev_val) / obj_range

    def tournament_selection(
        self,
        population: List[Chromosome],
        tournament_size: int = 2
    ) -> Chromosome:
        """
        Select a chromosome using binary tournament selection.

        Compares random chromosomes and selects the better one based on
        rank (lower is better) and crowding distance (higher is better).

        Args:
            population: Population to select from
            tournament_size: Number of chromosomes in tournament

        Returns:
            Selected chromosome
        """
        candidates = random.sample(population, min(tournament_size, len(population)))

        # Sort by rank, then crowding distance
        candidates.sort()

        return candidates[0]

    def crossover(
        self,
        parent1: Chromosome,
        parent2: Chromosome,
        crossover_rate: float = 0.9
    ) -> Tuple[Chromosome, Chromosome]:
        """
        Perform order crossover (OX) for scheduling chromosomes.

        Order crossover preserves the relative ordering of genes, which is
        important for scheduling problems where job sequence matters.

        Args:
            parent1: First parent chromosome
            parent2: Second parent chromosome
            crossover_rate: Probability of performing crossover

        Returns:
            Tuple of two offspring chromosomes
        """
        if random.random() > crossover_rate:
            # No crossover, return copies
            return (
                Chromosome(genes=copy.deepcopy(parent1.genes)),
                Chromosome(genes=copy.deepcopy(parent2.genes))
            )

        n = len(parent1.genes)

        if n < 2:
            return (
                Chromosome(genes=copy.deepcopy(parent1.genes)),
                Chromosome(genes=copy.deepcopy(parent2.genes))
            )

        # Select two crossover points
        point1 = random.randint(0, n - 2)
        point2 = random.randint(point1 + 1, n - 1)

        # Create offspring
        offspring1_genes = self._order_crossover(parent1.genes, parent2.genes, point1, point2)
        offspring2_genes = self._order_crossover(parent2.genes, parent1.genes, point1, point2)

        return (
            Chromosome(genes=offspring1_genes),
            Chromosome(genes=offspring2_genes)
        )

    def _order_crossover(
        self,
        parent1_genes: List[Gene],
        parent2_genes: List[Gene],
        point1: int,
        point2: int
    ) -> List[Gene]:
        """Perform order crossover to create offspring genes."""
        n = len(parent1_genes)
        offspring_genes = [None] * n

        # Copy segment from parent1
        for i in range(point1, point2 + 1):
            offspring_genes[i] = copy.deepcopy(parent1_genes[i])

        # Get job IDs already in offspring
        used_jobs = {g.job_id for g in offspring_genes if g is not None}

        # Fill remaining from parent2 in order
        parent2_order = [g for g in parent2_genes if g.job_id not in used_jobs]

        idx = 0
        for i in range(n):
            if offspring_genes[i] is None:
                if idx < len(parent2_order):
                    offspring_genes[i] = copy.deepcopy(parent2_order[idx])
                    idx += 1

        # Update positions
        machine_positions: Dict[str, int] = {}
        for gene in offspring_genes:
            if gene is not None:
                m_id = gene.machine_id
                gene.position = machine_positions.get(m_id, 0)
                machine_positions[m_id] = gene.position + 1

        return offspring_genes

    def mutation(
        self,
        chromosome: Chromosome,
        mutation_rate: float = 0.1
    ) -> Chromosome:
        """
        Apply mutation operators to a chromosome.

        Uses three types of mutations:
        1. Swap mutation: Swap two genes
        2. Insert mutation: Move a gene to a different position
        3. Machine mutation: Change job's assigned machine

        Args:
            chromosome: Chromosome to mutate
            mutation_rate: Probability of mutation per gene

        Returns:
            Mutated chromosome
        """
        mutated = Chromosome(genes=copy.deepcopy(chromosome.genes))
        n = len(mutated.genes)

        if n < 2:
            return mutated

        for i in range(n):
            if random.random() < mutation_rate:
                mutation_type = random.choice(['swap', 'insert', 'machine'])

                if mutation_type == 'swap':
                    # Swap with another gene
                    j = random.randint(0, n - 1)
                    if i != j:
                        mutated.genes[i], mutated.genes[j] = mutated.genes[j], mutated.genes[i]

                elif mutation_type == 'insert':
                    # Move gene to different position
                    gene = mutated.genes.pop(i)
                    new_pos = random.randint(0, len(mutated.genes))
                    mutated.genes.insert(new_pos, gene)

                elif mutation_type == 'machine':
                    # Change machine assignment
                    job = self.job_lookup.get(mutated.genes[i].job_id)
                    if job:
                        eligible = job.eligible_machines if job.eligible_machines else [
                            m.machine_id for m in self.machines
                        ]
                        if eligible:
                            mutated.genes[i].machine_id = random.choice(eligible)

        # Update positions after mutation
        machine_positions: Dict[str, int] = {}
        for gene in mutated.genes:
            m_id = gene.machine_id
            gene.position = machine_positions.get(m_id, 0)
            machine_positions[m_id] = gene.position + 1

        return mutated

    def evolve(self, generations: int = 100) -> List[Chromosome]:
        """
        Main evolution loop for NSGA-II.

        Evolves the population through selection, crossover, and mutation
        for the specified number of generations. Uses elitism to preserve
        the best solutions found.

        Args:
            generations: Number of generations to evolve

        Returns:
            Final population
        """
        pop_size = len(self.population)

        logger.info(f"Starting NSGA-II evolution for {generations} generations")

        for gen in range(generations):
            # Evaluate all chromosomes
            for chromosome in self.population:
                if not chromosome.objectives:
                    self.evaluate_objectives(chromosome)

            # Non-dominated sorting
            fronts = self.fast_non_dominated_sort(self.population)

            # Calculate crowding distance for each front
            for front in fronts:
                self.calculate_crowding_distance(front)

            # Create offspring population
            offspring = []

            while len(offspring) < pop_size:
                # Selection
                parent1 = self.tournament_selection(self.population)
                parent2 = self.tournament_selection(self.population)

                # Crossover
                child1, child2 = self.crossover(parent1, parent2)

                # Mutation
                child1 = self.mutation(child1)
                child2 = self.mutation(child2)

                # Repair if needed
                if not self.check_all_constraints(child1):
                    child1 = self.repair_chromosome(child1)
                if not self.check_all_constraints(child2):
                    child2 = self.repair_chromosome(child2)

                offspring.extend([child1, child2])

            # Combine parent and offspring
            combined = self.population + offspring[:pop_size]

            # Evaluate offspring
            for chromosome in offspring:
                self.evaluate_objectives(chromosome)

            # Non-dominated sorting of combined population
            fronts = self.fast_non_dominated_sort(combined)

            # Select next generation
            next_population = []
            front_idx = 0

            while len(next_population) + len(fronts[front_idx]) <= pop_size:
                # Add entire front
                self.calculate_crowding_distance(fronts[front_idx])
                next_population.extend(fronts[front_idx])
                front_idx += 1

                if front_idx >= len(fronts):
                    break

            # Fill remaining with crowding distance selection
            if len(next_population) < pop_size and front_idx < len(fronts):
                remaining = pop_size - len(next_population)
                self.calculate_crowding_distance(fronts[front_idx])
                fronts[front_idx].sort(key=lambda c: c.crowding_distance, reverse=True)
                next_population.extend(fronts[front_idx][:remaining])

            self.population = next_population

            # Log progress
            if (gen + 1) % 10 == 0 or gen == 0:
                best_front = fronts[0] if fronts else []
                logger.info(
                    f"Generation {gen + 1}/{generations}: "
                    f"Pareto front size = {len(best_front)}"
                )

        # Store final Pareto front
        fronts = self.fast_non_dominated_sort(self.population)
        self.pareto_front = fronts[0] if fronts else []

        logger.info(f"Evolution complete. Final Pareto front size: {len(self.pareto_front)}")

        return self.population

    # =========================================================================
    # Multi-Objective Functions
    # =========================================================================

    def objective_makespan(self, schedule: DecodedSchedule) -> float:
        """
        Calculate makespan objective (minimize total completion time).

        Args:
            schedule: Decoded schedule

        Returns:
            Makespan in minutes
        """
        return schedule.makespan

    def objective_tardiness(self, schedule: DecodedSchedule) -> float:
        """
        Calculate total weighted tardiness (minimize late jobs).

        Tardiness is the amount by which a job's completion time
        exceeds its due date. Weighted by job priority.

        Args:
            schedule: Decoded schedule

        Returns:
            Total weighted tardiness in minutes
        """
        total_tardiness = 0.0

        for scheduled_job in schedule.jobs:
            job = self.job_lookup.get(scheduled_job.job_id)

            if job and job.due_date:
                completion_time = scheduled_job.end_time

                if completion_time > job.due_date:
                    tardiness = (completion_time - job.due_date).total_seconds() / 60
                    # Weight by priority (higher priority = higher weight)
                    weight = 11 - job.priority  # Priority 1-10, weight 10-1
                    total_tardiness += tardiness * weight

        return total_tardiness

    def objective_setup_time(self, schedule: DecodedSchedule) -> float:
        """
        Calculate total setup/changeover time (minimize).

        Uses the setup matrix if provided, otherwise uses job setup times.

        Args:
            schedule: Decoded schedule

        Returns:
            Total setup time in minutes
        """
        total_setup = 0.0

        for machine_id, job_sequence in schedule.machine_sequences.items():
            prev_job_id = None

            for job_id in job_sequence:
                if self.setup_matrix and prev_job_id:
                    # Use sequence-dependent setup time
                    setup = self.setup_matrix.get((job_id, prev_job_id), 0)
                else:
                    # Use job's default setup time
                    job = self.job_lookup.get(job_id)
                    setup = job.setup_time if job else 0

                total_setup += setup
                prev_job_id = job_id

        return total_setup

    def objective_machine_utilization(self, schedule: DecodedSchedule) -> float:
        """
        Calculate machine utilization balance objective (minimize imbalance).

        Returns the standard deviation of machine utilizations - lower
        means more balanced workload across machines.

        Args:
            schedule: Decoded schedule

        Returns:
            Standard deviation of utilization (0-1 scale)
        """
        if schedule.makespan <= 0:
            return 0.0

        utilizations = []

        for machine in self.machines:
            machine_jobs = [
                j for j in schedule.jobs
                if j.machine_id == machine.machine_id
            ]

            busy_time = sum(
                (j.end_time - j.start_time).total_seconds() / 60
                for j in machine_jobs
            )

            utilization = busy_time / schedule.makespan
            utilizations.append(utilization)

        if not utilizations:
            return 0.0

        # Return standard deviation as measure of imbalance
        return float(np.std(utilizations))

    def objective_priority_weighted_completion(self, schedule: DecodedSchedule) -> float:
        """
        Calculate priority-weighted completion time (minimize).

        Higher priority jobs should complete earlier. Returns sum of
        completion times weighted by priority.

        Args:
            schedule: Decoded schedule

        Returns:
            Total weighted completion time
        """
        total_weighted = 0.0

        for scheduled_job in schedule.jobs:
            job = self.job_lookup.get(scheduled_job.job_id)

            if job:
                completion_minutes = (
                    scheduled_job.end_time - self.base_time
                ).total_seconds() / 60

                # Weight by priority (higher priority = higher weight)
                weight = 11 - job.priority  # Priority 1-10, weight 10-1
                total_weighted += completion_minutes * weight

        return total_weighted

    def objective_energy_consumption(self, schedule: DecodedSchedule) -> float:
        """
        Calculate total energy consumption (minimize).

        Uses machine energy rates if provided, otherwise estimates
        based on machine efficiency.

        Args:
            schedule: Decoded schedule

        Returns:
            Total energy consumption in kWh
        """
        total_energy = 0.0

        for scheduled_job in schedule.jobs:
            duration_minutes = (
                scheduled_job.end_time - scheduled_job.start_time
            ).total_seconds() / 60

            # Get energy rate for machine
            if self.energy_rates:
                rate = self.energy_rates.get(scheduled_job.machine_id, 0.1)
            else:
                # Estimate based on machine efficiency
                machine = self.machine_lookup.get(scheduled_job.machine_id)
                if machine:
                    # Less efficient machines use more energy
                    rate = 0.1 * (2 - machine.efficiency)
                else:
                    rate = 0.1

            total_energy += duration_minutes * rate

        return total_energy

    # =========================================================================
    # Constraint Handling
    # =========================================================================

    def check_precedence_constraints(self, chromosome: Chromosome) -> bool:
        """
        Check if job dependencies (precedence constraints) are satisfied.

        Args:
            chromosome: Chromosome to check

        Returns:
            True if all precedence constraints are satisfied
        """
        # Build job order index
        job_order = {g.job_id: i for i, g in enumerate(chromosome.genes)}

        for gene in chromosome.genes:
            job = self.job_lookup.get(gene.job_id)

            if job and job.dependencies:
                for dep_id in job.dependencies:
                    if dep_id in job_order:
                        # Dependency must come before this job
                        if job_order[dep_id] >= job_order[gene.job_id]:
                            return False

        return True

    def check_machine_eligibility(self, chromosome: Chromosome) -> bool:
        """
        Check if jobs are assigned to eligible machines.

        Args:
            chromosome: Chromosome to check

        Returns:
            True if all machine assignments are valid
        """
        for gene in chromosome.genes:
            job = self.job_lookup.get(gene.job_id)

            if job and job.eligible_machines:
                if gene.machine_id not in job.eligible_machines:
                    return False

        return True

    def check_resource_availability(self, chromosome: Chromosome) -> bool:
        """
        Check resource availability constraints.

        Currently checks machine availability windows.

        Args:
            chromosome: Chromosome to check

        Returns:
            True if all resource constraints are satisfied
        """
        schedule = self.decode_chromosome(chromosome)

        for scheduled_job in schedule.jobs:
            machine = self.machine_lookup.get(scheduled_job.machine_id)

            if machine:
                # Check availability window
                if machine.available_from and scheduled_job.start_time < machine.available_from:
                    return False
                if machine.available_until and scheduled_job.end_time > machine.available_until:
                    return False

        return True

    def check_all_constraints(self, chromosome: Chromosome) -> bool:
        """
        Check all constraints for a chromosome.

        Args:
            chromosome: Chromosome to check

        Returns:
            True if all constraints are satisfied
        """
        violations = 0

        if not self.check_precedence_constraints(chromosome):
            violations += 1

        if not self.check_machine_eligibility(chromosome):
            violations += 1

        if not self.check_resource_availability(chromosome):
            violations += 1

        chromosome.constraint_violations = violations
        chromosome.is_feasible = (violations == 0)

        return chromosome.is_feasible

    def repair_chromosome(self, chromosome: Chromosome) -> Chromosome:
        """
        Repair a chromosome to satisfy constraints.

        Applies repairs in order:
        1. Fix machine eligibility
        2. Fix precedence constraints

        Args:
            chromosome: Chromosome to repair

        Returns:
            Repaired chromosome
        """
        repaired = Chromosome(genes=copy.deepcopy(chromosome.genes))

        # 1. Fix machine eligibility
        for gene in repaired.genes:
            job = self.job_lookup.get(gene.job_id)

            if job and job.eligible_machines:
                if gene.machine_id not in job.eligible_machines:
                    gene.machine_id = random.choice(job.eligible_machines)

        # 2. Fix precedence constraints using topological sort
        job_order = {g.job_id: i for i, g in enumerate(repaired.genes)}

        # Build dependency graph
        in_degree: Dict[str, int] = {g.job_id: 0 for g in repaired.genes}
        successors: Dict[str, List[str]] = {g.job_id: [] for g in repaired.genes}

        for gene in repaired.genes:
            job = self.job_lookup.get(gene.job_id)
            if job and job.dependencies:
                for dep_id in job.dependencies:
                    if dep_id in in_degree:
                        in_degree[gene.job_id] += 1
                        successors[dep_id].append(gene.job_id)

        # Topological sort
        sorted_jobs = []
        queue = [job_id for job_id, deg in in_degree.items() if deg == 0]

        while queue:
            # Sort by original position to maintain some order
            queue.sort(key=lambda j: job_order.get(j, float('inf')))
            job_id = queue.pop(0)
            sorted_jobs.append(job_id)

            for succ in successors[job_id]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        # Reorder genes according to topological sort
        gene_lookup = {g.job_id: g for g in repaired.genes}
        repaired.genes = [gene_lookup[job_id] for job_id in sorted_jobs]

        # Update positions
        machine_positions: Dict[str, int] = {}
        for gene in repaired.genes:
            m_id = gene.machine_id
            gene.position = machine_positions.get(m_id, 0)
            machine_positions[m_id] = gene.position + 1

        return repaired

    # =========================================================================
    # Solution Representation
    # =========================================================================

    def encode_schedule(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine]
    ) -> Chromosome:
        """
        Encode a job list and machine assignment into a chromosome.

        Creates a chromosome representation of the given job sequence.

        Args:
            jobs: Ordered list of jobs
            machines: Available machines

        Returns:
            Encoded chromosome
        """
        self.jobs = jobs
        self.machines = machines
        self.job_lookup = {j.job_id: j for j in jobs}
        self.machine_lookup = {m.machine_id: m for m in machines}

        genes = []
        machine_positions: Dict[str, int] = {}

        for job in jobs:
            # Use preferred machine or first eligible
            machine_id = job.machine_id

            if not machine_id:
                if job.eligible_machines:
                    machine_id = job.eligible_machines[0]
                elif machines:
                    machine_id = machines[0].machine_id

            position = machine_positions.get(machine_id, 0)
            machine_positions[machine_id] = position + 1

            genes.append(Gene(
                job_id=job.job_id,
                machine_id=machine_id,
                position=position
            ))

        return Chromosome(genes=genes)

    def decode_chromosome(self, chromosome: Chromosome) -> DecodedSchedule:
        """
        Decode a chromosome into a schedule.

        Converts the genetic representation into actual job times
        and machine assignments.

        Args:
            chromosome: Chromosome to decode

        Returns:
            Decoded schedule with job times
        """
        schedule = DecodedSchedule()

        # Group genes by machine
        machine_genes: Dict[str, List[Gene]] = {}
        for gene in chromosome.genes:
            if gene.machine_id not in machine_genes:
                machine_genes[gene.machine_id] = []
            machine_genes[gene.machine_id].append(gene)

        # Sort each machine's jobs by position
        for machine_id in machine_genes:
            machine_genes[machine_id].sort(key=lambda g: g.position)
            schedule.machine_sequences[machine_id] = [
                g.job_id for g in machine_genes[machine_id]
            ]

        # Calculate schedule times
        schedule = self.calculate_schedule_times(schedule, chromosome)

        return schedule

    def calculate_schedule_times(
        self,
        schedule: DecodedSchedule,
        chromosome: Chromosome
    ) -> DecodedSchedule:
        """
        Calculate actual start and end times for jobs in a schedule.

        Handles:
        - Machine availability
        - Job dependencies
        - Setup times

        Args:
            schedule: Decoded schedule with machine sequences
            chromosome: Original chromosome

        Returns:
            Schedule with calculated times
        """
        # Track machine availability
        machine_available: Dict[str, datetime] = {}
        for machine in self.machines:
            machine_available[machine.machine_id] = (
                machine.available_from or self.base_time
            )

        # Track job completion times for dependencies
        job_completion: Dict[str, datetime] = {}

        # Process jobs in chromosome order (respects dependencies)
        gene_lookup = {g.job_id: g for g in chromosome.genes}

        for gene in chromosome.genes:
            job = self.job_lookup.get(gene.job_id)

            if not job:
                continue

            machine_id = gene.machine_id

            # Earliest start based on machine availability
            earliest_start = machine_available.get(machine_id, self.base_time)

            # Check dependencies
            for dep_id in job.dependencies:
                if dep_id in job_completion:
                    earliest_start = max(earliest_start, job_completion[dep_id])

            # Check job's earliest start constraint
            if job.earliest_start:
                earliest_start = max(earliest_start, job.earliest_start)

            # Get setup time
            prev_jobs = schedule.machine_sequences.get(machine_id, [])
            prev_idx = prev_jobs.index(gene.job_id) if gene.job_id in prev_jobs else -1

            setup_time = 0
            if prev_idx > 0:
                prev_job_id = prev_jobs[prev_idx - 1]
                if self.setup_matrix:
                    setup_time = self.setup_matrix.get((gene.job_id, prev_job_id), job.setup_time)
                else:
                    setup_time = job.setup_time
            else:
                setup_time = job.setup_time

            # Calculate times
            start_time = earliest_start + timedelta(minutes=setup_time)

            # Adjust for machine efficiency
            machine = self.machine_lookup.get(machine_id)
            effective_duration = job.duration_minutes
            if machine and machine.efficiency > 0:
                effective_duration = int(job.duration_minutes / machine.efficiency)

            end_time = start_time + timedelta(minutes=effective_duration)

            # Update tracking
            machine_available[machine_id] = end_time
            job_completion[gene.job_id] = end_time
            schedule.job_times[gene.job_id] = (start_time, end_time)

            # Create scheduled job
            scheduled_job = ScheduledJob(
                job_id=gene.job_id,
                machine_id=machine_id,
                start_time=start_time,
                end_time=end_time,
                setup_time=setup_time
            )
            schedule.jobs.append(scheduled_job)

        # Calculate makespan
        if schedule.jobs:
            latest_end = max(j.end_time for j in schedule.jobs)
            schedule.makespan = (latest_end - self.base_time).total_seconds() / 60

        return schedule

    # =========================================================================
    # Decision Support
    # =========================================================================

    def get_pareto_front(self) -> List[Chromosome]:
        """
        Get the current Pareto front (non-dominated solutions).

        Returns:
            List of non-dominated chromosomes
        """
        if not self.pareto_front and self.population:
            fronts = self.fast_non_dominated_sort(self.population)
            self.pareto_front = fronts[0] if fronts else []

        return self.pareto_front

    def get_knee_point(self) -> Optional[Chromosome]:
        """
        Find the knee point of the Pareto front.

        The knee point is the solution that provides the best trade-off
        between all objectives. It's the point where small improvements
        in one objective require large sacrifices in others.

        Uses the angle-based method to find the knee.

        Returns:
            Chromosome at the knee point, or None if no solutions
        """
        front = self.get_pareto_front()

        if not front:
            return None

        if len(front) <= 2:
            return front[0]

        # Normalize objectives
        obj_names = list(front[0].objectives.keys())

        # Find min/max for each objective
        obj_min = {}
        obj_max = {}

        for obj_name in obj_names:
            values = [c.objectives.get(obj_name, 0) for c in front]
            obj_min[obj_name] = min(values)
            obj_max[obj_name] = max(values)

        # Calculate normalized coordinates for each solution
        normalized = []
        for chromosome in front:
            coords = []
            for obj_name in obj_names:
                val = chromosome.objectives.get(obj_name, 0)
                range_val = obj_max[obj_name] - obj_min[obj_name]
                if range_val > 0:
                    norm = (val - obj_min[obj_name]) / range_val
                else:
                    norm = 0
                coords.append(norm)
            normalized.append(coords)

        # Find knee using distance from ideal line
        # Ideal line connects (0,0,...,0) to (1,1,...,1)
        n_obj = len(obj_names)
        ideal_direction = np.array([1.0 / math.sqrt(n_obj)] * n_obj)

        max_distance = -1
        knee_idx = 0

        for i, coords in enumerate(normalized):
            point = np.array(coords)

            # Project point onto ideal line
            projection = np.dot(point, ideal_direction) * ideal_direction

            # Distance from ideal line
            distance = np.linalg.norm(point - projection)

            if distance > max_distance:
                max_distance = distance
                knee_idx = i

        return front[knee_idx]

    def select_by_preference(
        self,
        weights: Dict[str, float]
    ) -> Optional[Chromosome]:
        """
        Select a solution based on user preference weights.

        Calculates a weighted sum of normalized objectives and returns
        the solution with the best (lowest) score.

        Args:
            weights: Dictionary mapping objective names to weights (0-1)

        Returns:
            Best chromosome according to weights, or None
        """
        front = self.get_pareto_front()

        if not front:
            return None

        # Normalize objectives
        obj_names = list(front[0].objectives.keys())
        obj_min = {}
        obj_max = {}

        for obj_name in obj_names:
            values = [c.objectives.get(obj_name, 0) for c in front]
            obj_min[obj_name] = min(values)
            obj_max[obj_name] = max(values)

        # Calculate weighted scores
        best_score = float('inf')
        best_chromosome = front[0]

        for chromosome in front:
            score = 0.0

            for obj_name in obj_names:
                val = chromosome.objectives.get(obj_name, 0)
                range_val = obj_max[obj_name] - obj_min[obj_name]

                if range_val > 0:
                    norm = (val - obj_min[obj_name]) / range_val
                else:
                    norm = 0

                weight = weights.get(obj_name, 1.0)
                score += norm * weight

            if score < best_score:
                best_score = score
                best_chromosome = chromosome

        return best_chromosome

    def compare_schedules(
        self,
        schedule1: DecodedSchedule,
        schedule2: DecodedSchedule
    ) -> Dict[str, Any]:
        """
        Compare two schedules across all objectives.

        Args:
            schedule1: First schedule
            schedule2: Second schedule

        Returns:
            Dictionary with comparison results
        """
        comparison = {
            'objectives': {},
            'winner': None,
            'summary': ''
        }

        schedule1_wins = 0
        schedule2_wins = 0

        # Compare each objective
        obj_funcs = {
            'makespan': self.objective_makespan,
            'tardiness': self.objective_tardiness,
            'setup_time': self.objective_setup_time,
            'utilization': self.objective_machine_utilization,
            'priority_completion': self.objective_priority_weighted_completion,
            'energy': self.objective_energy_consumption
        }

        for obj_name, obj_func in obj_funcs.items():
            val1 = obj_func(schedule1)
            val2 = obj_func(schedule2)

            if val1 < val2:
                winner = 'schedule1'
                schedule1_wins += 1
            elif val2 < val1:
                winner = 'schedule2'
                schedule2_wins += 1
            else:
                winner = 'tie'

            comparison['objectives'][obj_name] = {
                'schedule1': val1,
                'schedule2': val2,
                'difference': val1 - val2,
                'winner': winner
            }

        # Determine overall winner
        if schedule1_wins > schedule2_wins:
            comparison['winner'] = 'schedule1'
            comparison['summary'] = f"Schedule 1 is better on {schedule1_wins} objectives"
        elif schedule2_wins > schedule1_wins:
            comparison['winner'] = 'schedule2'
            comparison['summary'] = f"Schedule 2 is better on {schedule2_wins} objectives"
        else:
            comparison['winner'] = 'tie'
            comparison['summary'] = "Schedules are equally good overall (Pareto-equivalent)"

        return comparison

    # =========================================================================
    # Integration
    # =========================================================================

    def optimize(
        self,
        jobs: List[ScheduleJob],
        machines: List[Machine],
        objectives: List[str] = None,
        generations: int = 100,
        pop_size: int = 100,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1
    ) -> ScheduleResult:
        """
        Main optimization method - run NSGA-II and return best schedule.

        This is the primary entry point for using the scheduler.

        Args:
            jobs: List of jobs to schedule
            machines: List of available machines
            objectives: List of objective names to optimize
                       Options: 'makespan', 'tardiness', 'setup_time',
                               'utilization', 'priority_completion', 'energy'
            generations: Number of generations to evolve
            pop_size: Population size
            crossover_rate: Probability of crossover
            mutation_rate: Probability of mutation per gene

        Returns:
            ScheduleResult with best balanced schedule

        Example:
            >>> scheduler = NSGA2Scheduler()
            >>> result = scheduler.optimize(
            ...     jobs=jobs,
            ...     machines=machines,
            ...     objectives=['makespan', 'tardiness'],
            ...     generations=100
            ... )
        """
        # Set up objectives
        if objectives is None:
            objectives = ['makespan', 'tardiness']

        self.objectives = [
            ObjectiveConfig(name=obj, enabled=True)
            for obj in objectives
        ]

        logger.info(f"Starting NSGA-II optimization with objectives: {objectives}")
        logger.info(f"Jobs: {len(jobs)}, Machines: {len(machines)}")
        logger.info(f"Parameters: generations={generations}, pop_size={pop_size}")

        # Initialize population
        self.initialize_population(jobs, machines, pop_size)

        # Run evolution
        self.evolve(generations)

        # Get best balanced solution (knee point)
        best_chromosome = self.get_knee_point()

        if not best_chromosome:
            logger.warning("No valid solution found")
            return ScheduleResult(
                scheduled_jobs=[],
                makespan_minutes=0,
                total_setup_time=0,
                utilization={m.machine_id: 0.0 for m in machines},
                solver_status='no_solution'
            )

        # Decode best chromosome
        schedule = self.decode_chromosome(best_chromosome)

        # Calculate utilization
        utilization = {}
        for machine in machines:
            machine_jobs = [j for j in schedule.jobs if j.machine_id == machine.machine_id]
            if schedule.makespan > 0:
                busy_time = sum(
                    (j.end_time - j.start_time).total_seconds() / 60
                    for j in machine_jobs
                )
                utilization[machine.machine_id] = min(1.0, busy_time / schedule.makespan)
            else:
                utilization[machine.machine_id] = 0.0

        # Build result
        result = ScheduleResult(
            scheduled_jobs=schedule.jobs,
            makespan_minutes=int(schedule.makespan),
            total_setup_time=sum(j.setup_time for j in schedule.jobs),
            utilization=utilization,
            solver_status='pareto_optimal'
        )

        logger.info(f"Optimization complete. Makespan: {result.makespan_minutes} min")
        logger.info(f"Pareto front size: {len(self.pareto_front)}")

        return result

    def get_schedule_visualization_data(
        self,
        schedule: DecodedSchedule
    ) -> Dict[str, Any]:
        """
        Get schedule data formatted for Gantt chart visualization.

        Args:
            schedule: Decoded schedule to visualize

        Returns:
            Dictionary with visualization data
        """
        gantt_data = {
            'machines': [],
            'jobs': [],
            'time_range': {
                'start': None,
                'end': None
            },
            'summary': {
                'makespan': schedule.makespan,
                'total_jobs': len(schedule.jobs),
                'machines_used': len(schedule.machine_sequences)
            }
        }

        # Machine data
        for machine in self.machines:
            machine_jobs = [
                j for j in schedule.jobs
                if j.machine_id == machine.machine_id
            ]

            gantt_data['machines'].append({
                'id': machine.machine_id,
                'name': machine.name,
                'job_count': len(machine_jobs)
            })

        # Job data for Gantt bars
        for scheduled_job in schedule.jobs:
            job = self.job_lookup.get(scheduled_job.job_id)

            job_data = {
                'id': scheduled_job.job_id,
                'machine_id': scheduled_job.machine_id,
                'start': scheduled_job.start_time.isoformat(),
                'end': scheduled_job.end_time.isoformat(),
                'duration_minutes': (
                    scheduled_job.end_time - scheduled_job.start_time
                ).total_seconds() / 60,
                'setup_time': scheduled_job.setup_time,
                'priority': job.priority if job else 5,
                'is_late': False
            }

            # Check if late
            if job and job.due_date:
                job_data['due_date'] = job.due_date.isoformat()
                job_data['is_late'] = scheduled_job.end_time > job.due_date

            gantt_data['jobs'].append(job_data)

        # Time range
        if schedule.jobs:
            starts = [j.start_time for j in schedule.jobs]
            ends = [j.end_time for j in schedule.jobs]
            gantt_data['time_range']['start'] = min(starts).isoformat()
            gantt_data['time_range']['end'] = max(ends).isoformat()

        return gantt_data

    def get_all_pareto_solutions(self) -> List[Dict[str, Any]]:
        """
        Get all Pareto-optimal solutions with their objectives.

        Returns:
            List of dictionaries containing solution details
        """
        solutions = []

        for i, chromosome in enumerate(self.get_pareto_front()):
            schedule = self.decode_chromosome(chromosome)

            solutions.append({
                'solution_id': i,
                'objectives': dict(chromosome.objectives),
                'makespan': schedule.makespan,
                'job_count': len(schedule.jobs),
                'is_feasible': chromosome.is_feasible,
                'crowding_distance': chromosome.crowding_distance
            })

        return solutions


# =============================================================================
# Convenience Functions
# =============================================================================

def create_nsga2_scheduler() -> NSGA2Scheduler:
    """Factory function to create an NSGA-II scheduler instance."""
    return NSGA2Scheduler()


def schedule_with_nsga2(
    jobs: List[ScheduleJob],
    machines: List[Machine],
    objectives: List[str] = None,
    generations: int = 100,
    pop_size: int = 100
) -> ScheduleResult:
    """
    Convenience function to schedule jobs using NSGA-II.

    Args:
        jobs: List of jobs to schedule
        machines: List of available machines
        objectives: List of objective names
        generations: Number of generations
        pop_size: Population size

    Returns:
        ScheduleResult with optimized schedule
    """
    scheduler = NSGA2Scheduler()
    return scheduler.optimize(
        jobs=jobs,
        machines=machines,
        objectives=objectives,
        generations=generations,
        pop_size=pop_size
    )
