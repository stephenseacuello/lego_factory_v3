"""
Multi-Objective Optimization - NSGA-II Implementation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System

Provides Pareto-based multi-objective optimization.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from enum import Enum
import random
import logging
import uuid
import math

logger = logging.getLogger(__name__)


class ObjectiveDirection(Enum):
    """Direction of optimization."""
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass
class ObjectiveFunction:
    """An objective function definition."""
    name: str
    function: Callable[[List[float]], float]
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE
    weight: float = 1.0

    def evaluate(self, genes: List[float]) -> float:
        """Evaluate the objective."""
        value = self.function(genes)
        # Convert to minimization problem
        if self.direction == ObjectiveDirection.MAXIMIZE:
            return -value
        return value


@dataclass
class Solution:
    """A solution in multi-objective space."""
    solution_id: str
    genes: List[float]
    objectives: List[float]
    rank: int = 0
    crowding_distance: float = 0.0
    dominated_by: List[str] = field(default_factory=list)
    dominates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "solution_id": self.solution_id,
            "genes": self.genes,
            "objectives": self.objectives,
            "rank": self.rank,
            "crowding_distance": self.crowding_distance,
        }


@dataclass
class ParetoFront:
    """A Pareto front of non-dominated solutions."""
    solutions: List[Solution]
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rank": self.rank,
            "size": len(self.solutions),
            "solutions": [s.to_dict() for s in self.solutions],
        }


@dataclass
class OptimizationResult:
    """Result of multi-objective optimization."""
    pareto_front: ParetoFront
    all_solutions: List[Solution]
    generations: int
    objective_names: List[str]
    hypervolume: float
    spread: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pareto_front": self.pareto_front.to_dict(),
            "total_solutions": len(self.all_solutions),
            "generations": self.generations,
            "objective_names": self.objective_names,
            "hypervolume": self.hypervolume,
            "spread": self.spread,
        }


class MultiObjectiveOptimizer:
    """
    NSGA-II Multi-Objective Optimizer.

    Features:
    - Non-dominated sorting
    - Crowding distance assignment
    - Pareto front extraction
    - Hypervolume indicator
    - Reference point handling
    """

    def __init__(
        self,
        objectives: List[ObjectiveFunction],
        gene_bounds: List[Tuple[float, float]],
        population_size: int = 100,
        max_generations: int = 100,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1,
    ):
        self.objectives = objectives
        self.gene_bounds = gene_bounds
        self.population_size = population_size
        self.max_generations = max_generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate

        self.population: List[Solution] = []
        self.fronts: List[ParetoFront] = []
        self.generation = 0

    def initialize_population(self) -> List[Solution]:
        """Initialize random population."""
        population = []

        for _ in range(self.population_size):
            genes = [
                random.uniform(low, high)
                for low, high in self.gene_bounds
            ]
            solution = Solution(
                solution_id=str(uuid.uuid4()),
                genes=genes,
                objectives=[obj.evaluate(genes) for obj in self.objectives],
            )
            population.append(solution)

        self.population = population
        return population

    def dominates(self, s1: Solution, s2: Solution) -> bool:
        """Check if s1 dominates s2."""
        at_least_one_better = False

        for o1, o2 in zip(s1.objectives, s2.objectives):
            if o1 > o2:  # Worse on at least one objective
                return False
            if o1 < o2:  # Better on at least one
                at_least_one_better = True

        return at_least_one_better

    def fast_non_dominated_sort(self, population: List[Solution]) -> List[ParetoFront]:
        """Perform fast non-dominated sorting."""
        fronts: List[ParetoFront] = []

        # Reset dominance info
        for s in population:
            s.dominated_by = []
            s.dominates = []
            s.rank = 0

        # Calculate dominance
        for i, s1 in enumerate(population):
            for j, s2 in enumerate(population):
                if i == j:
                    continue
                if self.dominates(s1, s2):
                    s1.dominates.append(s2.solution_id)
                elif self.dominates(s2, s1):
                    s1.dominated_by.append(s2.solution_id)

        # Build first front
        first_front = [s for s in population if len(s.dominated_by) == 0]
        for s in first_front:
            s.rank = 0

        fronts.append(ParetoFront(solutions=first_front, rank=0))

        # Build subsequent fronts
        current_front = first_front
        rank = 1

        while len(current_front) > 0:
            next_front = []

            for s1 in current_front:
                for s2_id in s1.dominates:
                    s2 = next((s for s in population if s.solution_id == s2_id), None)
                    if s2:
                        s2.dominated_by = [
                            d for d in s2.dominated_by
                            if d != s1.solution_id
                        ]
                        if len(s2.dominated_by) == 0 and s2.rank == 0:
                            s2.rank = rank
                            next_front.append(s2)

            if next_front:
                fronts.append(ParetoFront(solutions=next_front, rank=rank))
            current_front = next_front
            rank += 1

        self.fronts = fronts
        return fronts

    def calculate_crowding_distance(self, front: ParetoFront):
        """Calculate crowding distance for solutions in a front."""
        n = len(front.solutions)
        if n <= 2:
            for s in front.solutions:
                s.crowding_distance = float('inf')
            return

        for s in front.solutions:
            s.crowding_distance = 0.0

        for m in range(len(self.objectives)):
            # Sort by objective m
            front.solutions.sort(key=lambda s: s.objectives[m])

            # Boundary solutions get infinite distance
            front.solutions[0].crowding_distance = float('inf')
            front.solutions[-1].crowding_distance = float('inf')

            # Calculate range
            obj_min = front.solutions[0].objectives[m]
            obj_max = front.solutions[-1].objectives[m]
            obj_range = obj_max - obj_min

            if obj_range == 0:
                continue

            # Calculate crowding distance for intermediate solutions
            for i in range(1, n - 1):
                diff = (
                    front.solutions[i + 1].objectives[m] -
                    front.solutions[i - 1].objectives[m]
                )
                front.solutions[i].crowding_distance += diff / obj_range

    def tournament_selection(self, population: List[Solution]) -> Solution:
        """Binary tournament selection based on rank and crowding distance."""
        candidates = random.sample(population, 2)

        if candidates[0].rank < candidates[1].rank:
            return candidates[0]
        elif candidates[0].rank > candidates[1].rank:
            return candidates[1]
        else:
            # Same rank - choose by crowding distance
            if candidates[0].crowding_distance > candidates[1].crowding_distance:
                return candidates[0]
            else:
                return candidates[1]

    def crossover(self, parent1: Solution, parent2: Solution) -> Tuple[Solution, Solution]:
        """SBX crossover."""
        if random.random() > self.crossover_rate:
            return parent1, parent2

        eta = 20  # Distribution index
        child1_genes = []
        child2_genes = []

        for i, (g1, g2) in enumerate(zip(parent1.genes, parent2.genes)):
            low, high = self.gene_bounds[i]

            if random.random() < 0.5:
                if abs(g1 - g2) > 1e-14:
                    if g1 < g2:
                        y1, y2 = g1, g2
                    else:
                        y1, y2 = g2, g1

                    beta = 1.0 + (2.0 * (y1 - low) / (y2 - y1))
                    alpha = 2.0 - beta ** (-(eta + 1))
                    rand = random.random()

                    if rand <= (1.0 / alpha):
                        betaq = (rand * alpha) ** (1.0 / (eta + 1))
                    else:
                        betaq = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta + 1))

                    c1 = 0.5 * ((y1 + y2) - betaq * (y2 - y1))
                    c2 = 0.5 * ((y1 + y2) + betaq * (y2 - y1))

                    c1 = max(low, min(high, c1))
                    c2 = max(low, min(high, c2))

                    if random.random() < 0.5:
                        child1_genes.append(c2)
                        child2_genes.append(c1)
                    else:
                        child1_genes.append(c1)
                        child2_genes.append(c2)
                else:
                    child1_genes.append(g1)
                    child2_genes.append(g2)
            else:
                child1_genes.append(g1)
                child2_genes.append(g2)

        child1 = Solution(
            solution_id=str(uuid.uuid4()),
            genes=child1_genes,
            objectives=[obj.evaluate(child1_genes) for obj in self.objectives],
        )
        child2 = Solution(
            solution_id=str(uuid.uuid4()),
            genes=child2_genes,
            objectives=[obj.evaluate(child2_genes) for obj in self.objectives],
        )

        return child1, child2

    def mutate(self, solution: Solution) -> Solution:
        """Polynomial mutation."""
        eta = 20

        for i in range(len(solution.genes)):
            if random.random() < self.mutation_rate:
                low, high = self.gene_bounds[i]
                y = solution.genes[i]

                delta1 = (y - low) / (high - low)
                delta2 = (high - y) / (high - low)

                r = random.random()
                if r < 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * r + (1.0 - 2.0 * r) * (xy ** (eta + 1))
                    deltaq = val ** (1.0 / (eta + 1)) - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - r) + 2.0 * (r - 0.5) * (xy ** (eta + 1))
                    deltaq = 1.0 - val ** (1.0 / (eta + 1))

                y = y + deltaq * (high - low)
                solution.genes[i] = max(low, min(high, y))

        # Re-evaluate objectives
        solution.objectives = [obj.evaluate(solution.genes) for obj in self.objectives]
        return solution

    def evolve(self) -> List[ParetoFront]:
        """Evolve population for one generation."""
        # Create offspring
        offspring = []
        while len(offspring) < self.population_size:
            parent1 = self.tournament_selection(self.population)
            parent2 = self.tournament_selection(self.population)
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)
            offspring.extend([child1, child2])

        # Combine parent and offspring
        combined = self.population + offspring[:self.population_size]

        # Non-dominated sorting
        fronts = self.fast_non_dominated_sort(combined)

        # Calculate crowding distance for each front
        for front in fronts:
            self.calculate_crowding_distance(front)

        # Select next generation
        new_population = []
        front_idx = 0

        while len(new_population) + len(fronts[front_idx].solutions) <= self.population_size:
            new_population.extend(fronts[front_idx].solutions)
            front_idx += 1
            if front_idx >= len(fronts):
                break

        # Fill remaining slots with solutions from next front by crowding distance
        if len(new_population) < self.population_size and front_idx < len(fronts):
            remaining = self.population_size - len(new_population)
            last_front = sorted(
                fronts[front_idx].solutions,
                key=lambda s: s.crowding_distance,
                reverse=True
            )
            new_population.extend(last_front[:remaining])

        self.population = new_population
        self.generation += 1

        # Update fronts
        self.fronts = self.fast_non_dominated_sort(self.population)
        for front in self.fronts:
            self.calculate_crowding_distance(front)

        return self.fronts

    def run(self) -> OptimizationResult:
        """Run the optimization."""
        logger.info(f"Starting NSGA-II with {self.max_generations} generations")

        if not self.population:
            self.initialize_population()

        for gen in range(self.max_generations):
            self.evolve()

            if gen % 10 == 0:
                logger.info(
                    f"Generation {gen}: Pareto front size = {len(self.fronts[0].solutions)}"
                )

        # Calculate metrics
        hypervolume = self._calculate_hypervolume(self.fronts[0])
        spread = self._calculate_spread(self.fronts[0])

        result = OptimizationResult(
            pareto_front=self.fronts[0],
            all_solutions=self.population,
            generations=self.generation,
            objective_names=[obj.name for obj in self.objectives],
            hypervolume=hypervolume,
            spread=spread,
        )

        logger.info(f"Optimization complete. Pareto front: {len(self.fronts[0].solutions)} solutions")
        return result

    def _calculate_hypervolume(self, front: ParetoFront) -> float:
        """Calculate hypervolume indicator (simplified 2D)."""
        if len(self.objectives) != 2 or len(front.solutions) == 0:
            return 0.0

        # Reference point
        ref_point = [max(s.objectives[i] for s in front.solutions) * 1.1 for i in range(2)]

        # Sort by first objective
        sorted_solutions = sorted(front.solutions, key=lambda s: s.objectives[0])

        hypervolume = 0.0
        prev_y = ref_point[1]

        for sol in sorted_solutions:
            hypervolume += (ref_point[0] - sol.objectives[0]) * (prev_y - sol.objectives[1])
            prev_y = sol.objectives[1]

        return hypervolume

    def _calculate_spread(self, front: ParetoFront) -> float:
        """Calculate spread metric."""
        if len(front.solutions) < 2:
            return 0.0

        distances = []
        for i, s1 in enumerate(front.solutions):
            min_dist = float('inf')
            for j, s2 in enumerate(front.solutions):
                if i != j:
                    dist = sum(
                        (o1 - o2) ** 2
                        for o1, o2 in zip(s1.objectives, s2.objectives)
                    ) ** 0.5
                    min_dist = min(min_dist, dist)
            distances.append(min_dist)

        mean_dist = sum(distances) / len(distances)
        if mean_dist == 0:
            return 0.0

        spread = sum(abs(d - mean_dist) for d in distances) / (len(distances) * mean_dist)
        return spread
