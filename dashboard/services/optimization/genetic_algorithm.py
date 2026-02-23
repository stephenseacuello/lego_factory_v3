"""
Genetic Algorithm - Evolutionary Optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System

Provides genetic algorithm optimization for manufacturing problems.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from enum import Enum
import random
import logging
import uuid
import math

logger = logging.getLogger(__name__)


class SelectionMethod(Enum):
    """Selection method for genetic algorithm."""
    TOURNAMENT = "tournament"
    ROULETTE = "roulette"
    RANK = "rank"
    ELITIST = "elitist"


class CrossoverMethod(Enum):
    """Crossover method for genetic algorithm."""
    SINGLE_POINT = "single_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    BLEND = "blend"


class MutationMethod(Enum):
    """Mutation method for genetic algorithm."""
    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    BOUNDARY = "boundary"
    POLYNOMIAL = "polynomial"


@dataclass
class Individual:
    """An individual in the population."""
    individual_id: str
    genes: List[float]
    fitness: float = 0.0
    objectives: List[float] = field(default_factory=list)
    constraints_violated: int = 0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "individual_id": self.individual_id,
            "genes": self.genes,
            "fitness": self.fitness,
            "objectives": self.objectives,
            "constraints_violated": self.constraints_violated,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
        }

    def copy(self) -> 'Individual':
        """Create a copy of this individual."""
        return Individual(
            individual_id=str(uuid.uuid4()),
            genes=self.genes.copy(),
            fitness=self.fitness,
            objectives=self.objectives.copy(),
            constraints_violated=self.constraints_violated,
            generation=self.generation,
            parent_ids=self.parent_ids.copy(),
        )


@dataclass
class Population:
    """A population of individuals."""
    individuals: List[Individual]
    generation: int = 0
    best_fitness: float = 0.0
    average_fitness: float = 0.0
    diversity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "size": len(self.individuals),
            "generation": self.generation,
            "best_fitness": self.best_fitness,
            "average_fitness": self.average_fitness,
            "diversity": self.diversity,
            "individuals": [i.to_dict() for i in self.individuals[:10]],  # Top 10
        }


@dataclass
class GAConfig:
    """Genetic algorithm configuration."""
    population_size: int = 100
    max_generations: int = 100
    chromosome_length: int = 10
    gene_bounds: List[Tuple[float, float]] = field(default_factory=list)
    selection_method: SelectionMethod = SelectionMethod.TOURNAMENT
    crossover_method: CrossoverMethod = CrossoverMethod.UNIFORM
    mutation_method: MutationMethod = MutationMethod.GAUSSIAN
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    elitism_count: int = 2
    tournament_size: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "chromosome_length": self.chromosome_length,
            "gene_bounds": self.gene_bounds,
            "selection_method": self.selection_method.value,
            "crossover_method": self.crossover_method.value,
            "mutation_method": self.mutation_method.value,
            "crossover_rate": self.crossover_rate,
            "mutation_rate": self.mutation_rate,
            "elitism_count": self.elitism_count,
            "tournament_size": self.tournament_size,
        }


class GeneticAlgorithm:
    """
    Genetic Algorithm optimizer for manufacturing problems.

    Features:
    - Multiple selection methods (tournament, roulette, rank, elitist)
    - Multiple crossover methods (single-point, two-point, uniform, blend)
    - Multiple mutation methods (Gaussian, uniform, boundary, polynomial)
    - Constraint handling
    - Diversity maintenance
    - Convergence detection
    """

    def __init__(
        self,
        config: GAConfig,
        fitness_function: Callable[[List[float]], float],
        constraint_functions: Optional[List[Callable[[List[float]], float]]] = None,
    ):
        self.config = config
        self.fitness_function = fitness_function
        self.constraint_functions = constraint_functions or []
        self.population: Optional[Population] = None
        self.history: List[Dict[str, Any]] = []
        self.best_individual: Optional[Individual] = None

        # Set default bounds if not provided
        if not self.config.gene_bounds:
            self.config.gene_bounds = [(0.0, 1.0)] * self.config.chromosome_length

    def initialize_population(self) -> Population:
        """Initialize a random population."""
        individuals = []

        for _ in range(self.config.population_size):
            genes = [
                random.uniform(low, high)
                for low, high in self.config.gene_bounds
            ]
            individual = Individual(
                individual_id=str(uuid.uuid4()),
                genes=genes,
                generation=0,
            )
            individuals.append(individual)

        population = Population(individuals=individuals, generation=0)
        self._evaluate_population(population)
        self.population = population

        logger.info(f"Initialized population with {len(individuals)} individuals")
        return population

    def _evaluate_population(self, population: Population):
        """Evaluate fitness for all individuals."""
        total_fitness = 0.0
        best_fitness = float('-inf')

        for individual in population.individuals:
            # Evaluate fitness
            individual.fitness = self.fitness_function(individual.genes)

            # Check constraints
            individual.constraints_violated = 0
            for constraint_fn in self.constraint_functions:
                if constraint_fn(individual.genes) < 0:
                    individual.constraints_violated += 1

            # Penalize constraint violations
            if individual.constraints_violated > 0:
                individual.fitness -= individual.constraints_violated * 1000

            total_fitness += individual.fitness
            if individual.fitness > best_fitness:
                best_fitness = individual.fitness

        population.best_fitness = best_fitness
        population.average_fitness = total_fitness / len(population.individuals)
        population.diversity = self._calculate_diversity(population)

        # Update best individual
        best = max(population.individuals, key=lambda i: i.fitness)
        if self.best_individual is None or best.fitness > self.best_individual.fitness:
            self.best_individual = best.copy()

    def _calculate_diversity(self, population: Population) -> float:
        """Calculate population diversity."""
        if len(population.individuals) < 2:
            return 0.0

        total_distance = 0.0
        count = 0

        for i, ind1 in enumerate(population.individuals):
            for ind2 in population.individuals[i+1:]:
                distance = sum(
                    (g1 - g2) ** 2
                    for g1, g2 in zip(ind1.genes, ind2.genes)
                ) ** 0.5
                total_distance += distance
                count += 1

        return total_distance / count if count > 0 else 0.0

    def select(self, population: Population) -> List[Individual]:
        """Select individuals for reproduction."""
        if self.config.selection_method == SelectionMethod.TOURNAMENT:
            return self._tournament_selection(population)
        elif self.config.selection_method == SelectionMethod.ROULETTE:
            return self._roulette_selection(population)
        elif self.config.selection_method == SelectionMethod.RANK:
            return self._rank_selection(population)
        else:
            return self._elitist_selection(population)

    def _tournament_selection(self, population: Population) -> List[Individual]:
        """Tournament selection."""
        selected = []
        for _ in range(self.config.population_size):
            tournament = random.sample(
                population.individuals,
                self.config.tournament_size
            )
            winner = max(tournament, key=lambda i: i.fitness)
            selected.append(winner.copy())
        return selected

    def _roulette_selection(self, population: Population) -> List[Individual]:
        """Roulette wheel selection."""
        min_fitness = min(i.fitness for i in population.individuals)
        adjusted = [i.fitness - min_fitness + 1 for i in population.individuals]
        total = sum(adjusted)

        selected = []
        for _ in range(self.config.population_size):
            r = random.uniform(0, total)
            cumulative = 0
            for i, fitness in enumerate(adjusted):
                cumulative += fitness
                if cumulative >= r:
                    selected.append(population.individuals[i].copy())
                    break
        return selected

    def _rank_selection(self, population: Population) -> List[Individual]:
        """Rank-based selection."""
        sorted_pop = sorted(population.individuals, key=lambda i: i.fitness)
        ranks = list(range(1, len(sorted_pop) + 1))
        total = sum(ranks)

        selected = []
        for _ in range(self.config.population_size):
            r = random.uniform(0, total)
            cumulative = 0
            for i, rank in enumerate(ranks):
                cumulative += rank
                if cumulative >= r:
                    selected.append(sorted_pop[i].copy())
                    break
        return selected

    def _elitist_selection(self, population: Population) -> List[Individual]:
        """Elitist selection."""
        sorted_pop = sorted(
            population.individuals,
            key=lambda i: i.fitness,
            reverse=True
        )
        return [i.copy() for i in sorted_pop[:self.config.population_size]]

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Perform crossover between two parents."""
        if random.random() > self.config.crossover_rate:
            return parent1.copy(), parent2.copy()

        if self.config.crossover_method == CrossoverMethod.SINGLE_POINT:
            return self._single_point_crossover(parent1, parent2)
        elif self.config.crossover_method == CrossoverMethod.TWO_POINT:
            return self._two_point_crossover(parent1, parent2)
        elif self.config.crossover_method == CrossoverMethod.BLEND:
            return self._blend_crossover(parent1, parent2)
        else:
            return self._uniform_crossover(parent1, parent2)

    def _single_point_crossover(
        self,
        p1: Individual,
        p2: Individual,
    ) -> Tuple[Individual, Individual]:
        """Single-point crossover."""
        point = random.randint(1, len(p1.genes) - 1)

        child1 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=p1.genes[:point] + p2.genes[point:],
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        child2 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=p2.genes[:point] + p1.genes[point:],
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        return child1, child2

    def _two_point_crossover(
        self,
        p1: Individual,
        p2: Individual,
    ) -> Tuple[Individual, Individual]:
        """Two-point crossover."""
        points = sorted(random.sample(range(1, len(p1.genes)), 2))

        child1_genes = (
            p1.genes[:points[0]] +
            p2.genes[points[0]:points[1]] +
            p1.genes[points[1]:]
        )
        child2_genes = (
            p2.genes[:points[0]] +
            p1.genes[points[0]:points[1]] +
            p2.genes[points[1]:]
        )

        child1 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child1_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        child2 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child2_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        return child1, child2

    def _uniform_crossover(
        self,
        p1: Individual,
        p2: Individual,
    ) -> Tuple[Individual, Individual]:
        """Uniform crossover."""
        child1_genes = []
        child2_genes = []

        for g1, g2 in zip(p1.genes, p2.genes):
            if random.random() < 0.5:
                child1_genes.append(g1)
                child2_genes.append(g2)
            else:
                child1_genes.append(g2)
                child2_genes.append(g1)

        child1 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child1_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        child2 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child2_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        return child1, child2

    def _blend_crossover(
        self,
        p1: Individual,
        p2: Individual,
        alpha: float = 0.5,
    ) -> Tuple[Individual, Individual]:
        """BLX-alpha crossover."""
        child1_genes = []
        child2_genes = []

        for i, (g1, g2) in enumerate(zip(p1.genes, p2.genes)):
            low, high = self.config.gene_bounds[i]
            d = abs(g2 - g1)
            min_val = max(low, min(g1, g2) - alpha * d)
            max_val = min(high, max(g1, g2) + alpha * d)

            child1_genes.append(random.uniform(min_val, max_val))
            child2_genes.append(random.uniform(min_val, max_val))

        child1 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child1_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        child2 = Individual(
            individual_id=str(uuid.uuid4()),
            genes=child2_genes,
            parent_ids=[p1.individual_id, p2.individual_id],
        )
        return child1, child2

    def mutate(self, individual: Individual) -> Individual:
        """Apply mutation to an individual."""
        if self.config.mutation_method == MutationMethod.GAUSSIAN:
            return self._gaussian_mutation(individual)
        elif self.config.mutation_method == MutationMethod.BOUNDARY:
            return self._boundary_mutation(individual)
        elif self.config.mutation_method == MutationMethod.POLYNOMIAL:
            return self._polynomial_mutation(individual)
        else:
            return self._uniform_mutation(individual)

    def _gaussian_mutation(self, individual: Individual) -> Individual:
        """Gaussian mutation."""
        for i in range(len(individual.genes)):
            if random.random() < self.config.mutation_rate:
                low, high = self.config.gene_bounds[i]
                sigma = (high - low) * 0.1
                individual.genes[i] += random.gauss(0, sigma)
                individual.genes[i] = max(low, min(high, individual.genes[i]))
        return individual

    def _uniform_mutation(self, individual: Individual) -> Individual:
        """Uniform mutation."""
        for i in range(len(individual.genes)):
            if random.random() < self.config.mutation_rate:
                low, high = self.config.gene_bounds[i]
                individual.genes[i] = random.uniform(low, high)
        return individual

    def _boundary_mutation(self, individual: Individual) -> Individual:
        """Boundary mutation."""
        for i in range(len(individual.genes)):
            if random.random() < self.config.mutation_rate:
                low, high = self.config.gene_bounds[i]
                individual.genes[i] = low if random.random() < 0.5 else high
        return individual

    def _polynomial_mutation(self, individual: Individual, eta: float = 20) -> Individual:
        """Polynomial mutation."""
        for i in range(len(individual.genes)):
            if random.random() < self.config.mutation_rate:
                low, high = self.config.gene_bounds[i]
                y = individual.genes[i]
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
                individual.genes[i] = max(low, min(high, y))
        return individual

    def evolve(self) -> Population:
        """Evolve the population for one generation."""
        if self.population is None:
            self.initialize_population()

        # Selection
        selected = self.select(self.population)

        # Elitism - keep best individuals
        sorted_pop = sorted(
            self.population.individuals,
            key=lambda i: i.fitness,
            reverse=True
        )
        elite = [i.copy() for i in sorted_pop[:self.config.elitism_count]]

        # Crossover and mutation
        new_individuals = elite.copy()
        while len(new_individuals) < self.config.population_size:
            parent1, parent2 = random.sample(selected, 2)
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)
            new_individuals.extend([child1, child2])

        new_individuals = new_individuals[:self.config.population_size]

        # Update generation
        new_generation = self.population.generation + 1
        for ind in new_individuals:
            ind.generation = new_generation

        self.population = Population(
            individuals=new_individuals,
            generation=new_generation,
        )
        self._evaluate_population(self.population)

        # Record history
        self.history.append({
            "generation": new_generation,
            "best_fitness": self.population.best_fitness,
            "average_fitness": self.population.average_fitness,
            "diversity": self.population.diversity,
        })

        return self.population

    def run(self, callback: Optional[Callable[[Population], bool]] = None) -> Individual:
        """Run the genetic algorithm to completion."""
        if self.population is None:
            self.initialize_population()

        logger.info(f"Starting GA with {self.config.max_generations} generations")

        for gen in range(self.config.max_generations):
            self.evolve()

            # Check callback for early stopping
            if callback and callback(self.population):
                logger.info(f"Early stopping at generation {gen}")
                break

            if gen % 10 == 0:
                logger.info(
                    f"Generation {gen}: best={self.population.best_fitness:.4f}, "
                    f"avg={self.population.average_fitness:.4f}"
                )

        logger.info(f"GA completed. Best fitness: {self.best_individual.fitness:.4f}")
        return self.best_individual

    def get_results(self) -> Dict[str, Any]:
        """Get optimization results."""
        return {
            "best_individual": self.best_individual.to_dict() if self.best_individual else None,
            "final_population": self.population.to_dict() if self.population else None,
            "generations_run": len(self.history),
            "history": self.history,
            "config": self.config.to_dict(),
        }
