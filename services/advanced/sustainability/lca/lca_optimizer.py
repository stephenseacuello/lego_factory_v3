"""
LCA Optimizer Module.

Multi-objective optimization for life cycle assessment to find
Pareto-optimal manufacturing configurations balancing environmental
impact, cost, and performance.

Research Value:
- Novel multi-objective LCA optimization for manufacturing
- Integration of NSGA-II/III with LCA impact categories
- Carbon-aware production scheduling optimization

References:
- Deb, K. et al. (2002). A Fast and Elitist Multi-objective GA: NSGA-II
- ISO 14040/14044 Life Cycle Assessment standards
- Gutowski, T. et al. (2009). Thermodynamic Analysis of Resources
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum, auto
from abc import ABC, abstractmethod
import random
import math
from datetime import datetime
import json
import copy


class OptimizationObjective(Enum):
    """Optimization objectives for LCA."""
    MINIMIZE_GWP = auto()  # Minimize global warming potential
    MINIMIZE_COST = auto()  # Minimize production cost
    MINIMIZE_ENERGY = auto()  # Minimize energy consumption
    MINIMIZE_WATER = auto()  # Minimize water consumption
    MINIMIZE_WASTE = auto()  # Minimize waste generation
    MAXIMIZE_RECYCLABILITY = auto()  # Maximize material recyclability
    MINIMIZE_TOXICITY = auto()  # Minimize toxicity impacts
    MINIMIZE_RESOURCE_DEPLETION = auto()  # Minimize resource use


@dataclass
class DesignVariable:
    """Design variable for optimization."""

    name: str
    lower_bound: float
    upper_bound: float
    variable_type: str = "continuous"  # continuous, integer, categorical
    categories: List[str] = field(default_factory=list)
    current_value: Optional[float] = None

    def sample_random(self) -> float:
        """Sample random value within bounds."""
        if self.variable_type == "integer":
            return float(random.randint(int(self.lower_bound), int(self.upper_bound)))
        elif self.variable_type == "categorical":
            return float(random.randint(0, len(self.categories) - 1))
        else:
            return random.uniform(self.lower_bound, self.upper_bound)

    def clip(self, value: float) -> float:
        """Clip value to bounds."""
        return max(self.lower_bound, min(self.upper_bound, value))


@dataclass
class OptimizationConstraint:
    """Constraint for optimization."""

    name: str
    constraint_type: str  # "<=", ">=", "=="
    limit: float
    penalty_factor: float = 1000.0

    def evaluate(self, value: float) -> float:
        """Evaluate constraint violation (0 if satisfied)."""
        if self.constraint_type == "<=":
            return max(0, value - self.limit)
        elif self.constraint_type == ">=":
            return max(0, self.limit - value)
        else:  # "=="
            return abs(value - self.limit)


@dataclass
class Solution:
    """Individual solution in optimization."""

    variables: Dict[str, float]
    objectives: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, float] = field(default_factory=dict)
    constraint_violation: float = 0.0
    rank: int = 0
    crowding_distance: float = 0.0
    dominated_by: int = 0
    dominates: List[int] = field(default_factory=list)

    def is_feasible(self) -> bool:
        """Check if solution is feasible."""
        return self.constraint_violation <= 0.0


@dataclass
class ParetoFront:
    """Pareto front of non-dominated solutions."""

    solutions: List[Solution]
    generation: int
    timestamp: datetime = field(default_factory=datetime.now)

    def get_extreme_solutions(self) -> Dict[str, Solution]:
        """Get extreme solutions for each objective."""
        extremes = {}

        if not self.solutions:
            return extremes

        objectives = list(self.solutions[0].objectives.keys())

        for obj in objectives:
            # Find solution with minimum value for this objective
            best_sol = min(self.solutions, key=lambda s: s.objectives.get(obj, float('inf')))
            extremes[f"min_{obj}"] = best_sol

        return extremes

    def get_compromise_solution(
        self,
        weights: Optional[Dict[str, float]] = None
    ) -> Optional[Solution]:
        """Get compromise solution using weighted sum."""
        if not self.solutions:
            return None

        if weights is None:
            # Equal weights
            objectives = list(self.solutions[0].objectives.keys())
            weights = {obj: 1.0 / len(objectives) for obj in objectives}

        # Normalize objectives
        obj_min = {}
        obj_max = {}

        for obj in weights.keys():
            values = [s.objectives.get(obj, 0) for s in self.solutions]
            obj_min[obj] = min(values)
            obj_max[obj] = max(values)

        # Calculate weighted sum for each solution
        best_score = float('inf')
        best_solution = None

        for solution in self.solutions:
            score = 0.0
            for obj, weight in weights.items():
                value = solution.objectives.get(obj, 0)
                range_val = obj_max[obj] - obj_min[obj]
                if range_val > 0:
                    normalized = (value - obj_min[obj]) / range_val
                else:
                    normalized = 0.0
                score += weight * normalized

            if score < best_score:
                best_score = score
                best_solution = solution

        return best_solution


class LCAObjectiveFunction(ABC):
    """Abstract base class for LCA objective functions."""

    @abstractmethod
    def evaluate(
        self,
        variables: Dict[str, float]
    ) -> Dict[str, float]:
        """Evaluate objectives for given variables."""
        pass

    @abstractmethod
    def evaluate_constraints(
        self,
        variables: Dict[str, float]
    ) -> Dict[str, float]:
        """Evaluate constraint values."""
        pass


class ManufacturingLCAObjective(LCAObjectiveFunction):
    """LCA objective function for manufacturing optimization."""

    def __init__(self):
        self.material_impacts = self._initialize_material_impacts()
        self.process_impacts = self._initialize_process_impacts()
        self.electricity_factors = self._initialize_electricity_factors()

    def _initialize_material_impacts(self) -> Dict[str, Dict[str, float]]:
        """Initialize material environmental impacts."""
        return {
            "pla": {
                "gwp": 3.8,  # kg CO2-eq/kg
                "energy": 54.0,  # MJ/kg
                "water": 1.2,  # L/kg
                "cost": 25.0,  # $/kg
                "recyclability": 0.7,
            },
            "abs": {
                "gwp": 4.2,
                "energy": 95.0,
                "water": 1.5,
                "cost": 22.0,
                "recyclability": 0.8,
            },
            "petg": {
                "gwp": 3.5,
                "energy": 62.0,
                "water": 1.0,
                "cost": 28.0,
                "recyclability": 0.75,
            },
            "nylon": {
                "gwp": 8.5,
                "energy": 120.0,
                "water": 3.0,
                "cost": 45.0,
                "recyclability": 0.6,
            },
            "recycled_pla": {
                "gwp": 1.5,
                "energy": 25.0,
                "water": 0.5,
                "cost": 20.0,
                "recyclability": 0.5,
            },
        }

    def _initialize_process_impacts(self) -> Dict[str, Dict[str, float]]:
        """Initialize process environmental impacts."""
        return {
            "fdm": {
                "energy_per_kg": 2.5,  # kWh/kg
                "waste_fraction": 0.05,
                "time_factor": 1.0,
            },
            "sla": {
                "energy_per_kg": 4.0,
                "waste_fraction": 0.08,
                "time_factor": 0.7,
            },
            "sls": {
                "energy_per_kg": 8.0,
                "waste_fraction": 0.03,
                "time_factor": 0.5,
            },
        }

    def _initialize_electricity_factors(self) -> Dict[str, float]:
        """Initialize electricity emission factors."""
        return {
            "grid": 0.45,  # kg CO2/kWh
            "solar": 0.05,
            "wind": 0.02,
            "hydro": 0.02,
            "natural_gas": 0.40,
            "coal": 0.95,
        }

    def evaluate(
        self,
        variables: Dict[str, float]
    ) -> Dict[str, float]:
        """Evaluate LCA objectives."""
        # Extract variables
        material_idx = int(variables.get("material", 0))
        materials = list(self.material_impacts.keys())
        material = materials[material_idx % len(materials)]

        process_idx = int(variables.get("process", 0))
        processes = list(self.process_impacts.keys())
        process = processes[process_idx % len(processes)]

        infill = variables.get("infill", 0.2)
        layer_height = variables.get("layer_height", 0.2)
        print_speed = variables.get("print_speed", 60)
        renewable_fraction = variables.get("renewable_fraction", 0.0)

        # Calculate material usage
        base_material_kg = variables.get("part_volume_cm3", 100) * 0.00125  # PLA density
        actual_material = base_material_kg * (0.3 + 0.7 * infill)

        # Get impact factors
        mat_impact = self.material_impacts[material]
        proc_impact = self.process_impacts[process]

        # Calculate GWP
        material_gwp = actual_material * mat_impact["gwp"]

        # Process energy and emissions
        process_energy_kwh = actual_material * proc_impact["energy_per_kg"]

        # Adjust for layer height (finer = more energy)
        energy_adjustment = 0.2 / layer_height
        process_energy_kwh *= energy_adjustment

        # Calculate electricity emissions
        grid_ef = self.electricity_factors["grid"]
        renewable_ef = self.electricity_factors["solar"]
        effective_ef = (1 - renewable_fraction) * grid_ef + renewable_fraction * renewable_ef
        process_gwp = process_energy_kwh * effective_ef

        total_gwp = material_gwp + process_gwp

        # Calculate energy (MJ)
        material_energy = actual_material * mat_impact["energy"]
        process_energy_mj = process_energy_kwh * 3.6
        total_energy = material_energy + process_energy_mj

        # Calculate water (L)
        total_water = actual_material * mat_impact["water"]

        # Calculate cost ($)
        material_cost = actual_material * mat_impact["cost"]
        energy_cost = process_energy_kwh * 0.12  # $/kWh
        total_cost = material_cost + energy_cost

        # Calculate waste
        waste_kg = actual_material * proc_impact["waste_fraction"]

        # Calculate recyclability score (0-1)
        recyclability = mat_impact["recyclability"]

        return {
            "gwp": total_gwp,
            "energy": total_energy,
            "water": total_water,
            "cost": total_cost,
            "waste": waste_kg,
            "recyclability": 1.0 - recyclability,  # Minimize (1-recyclability)
        }

    def evaluate_constraints(
        self,
        variables: Dict[str, float]
    ) -> Dict[str, float]:
        """Evaluate constraint values."""
        constraints = {}

        # Minimum strength constraint (based on infill)
        infill = variables.get("infill", 0.2)
        min_infill = 0.15
        constraints["min_strength"] = min_infill - infill

        # Maximum print time constraint
        layer_height = variables.get("layer_height", 0.2)
        print_speed = variables.get("print_speed", 60)
        part_height = variables.get("part_height_mm", 50)

        layers = part_height / layer_height
        print_time = layers * 0.5 / (print_speed / 60)  # Simplified time model
        max_print_time = 24  # hours
        constraints["max_time"] = print_time - max_print_time

        # Budget constraint
        objectives = self.evaluate(variables)
        max_cost = variables.get("max_budget", 100)
        constraints["max_cost"] = objectives["cost"] - max_cost

        return constraints


class NSGA2Optimizer:
    """
    NSGA-II optimizer for multi-objective LCA optimization.

    Implements the Non-dominated Sorting Genetic Algorithm II
    for finding Pareto-optimal manufacturing configurations.
    """

    def __init__(
        self,
        objective_function: LCAObjectiveFunction,
        variables: List[DesignVariable],
        constraints: List[OptimizationConstraint],
        population_size: int = 100,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.1,
        seed: Optional[int] = None
    ):
        self.objective_function = objective_function
        self.variables = {v.name: v for v in variables}
        self.constraints = constraints
        self.population_size = population_size
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob

        if seed is not None:
            random.seed(seed)

        self.population: List[Solution] = []
        self.pareto_fronts: List[ParetoFront] = []
        self.generation = 0

    def initialize_population(self):
        """Initialize random population."""
        self.population = []

        for _ in range(self.population_size):
            variables = {}
            for name, var in self.variables.items():
                variables[name] = var.sample_random()

            solution = Solution(variables=variables)
            self._evaluate_solution(solution)
            self.population.append(solution)

    def _evaluate_solution(self, solution: Solution):
        """Evaluate objectives and constraints for solution."""
        # Evaluate objectives
        solution.objectives = self.objective_function.evaluate(solution.variables)

        # Evaluate constraints
        constraint_values = self.objective_function.evaluate_constraints(solution.variables)

        total_violation = 0.0
        for constraint in self.constraints:
            value = constraint_values.get(constraint.name, 0)
            violation = constraint.evaluate(value)
            solution.constraints[constraint.name] = violation
            total_violation += violation * constraint.penalty_factor

        solution.constraint_violation = total_violation

    def non_dominated_sort(self) -> List[List[int]]:
        """Perform non-dominated sorting."""
        n = len(self.population)
        fronts: List[List[int]] = [[]]

        for i in range(n):
            self.population[i].dominated_by = 0
            self.population[i].dominates = []

            for j in range(n):
                if i == j:
                    continue

                if self._dominates(self.population[i], self.population[j]):
                    self.population[i].dominates.append(j)
                elif self._dominates(self.population[j], self.population[i]):
                    self.population[i].dominated_by += 1

            if self.population[i].dominated_by == 0:
                self.population[i].rank = 0
                fronts[0].append(i)

        i = 0
        while fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in self.population[p].dominates:
                    self.population[q].dominated_by -= 1
                    if self.population[q].dominated_by == 0:
                        self.population[q].rank = i + 1
                        next_front.append(q)
            i += 1
            fronts.append(next_front)

        return fronts[:-1]  # Remove empty last front

    def _dominates(self, sol1: Solution, sol2: Solution) -> bool:
        """Check if sol1 dominates sol2."""
        # Handle constraint violations
        if sol1.constraint_violation < sol2.constraint_violation:
            return True
        if sol1.constraint_violation > sol2.constraint_violation:
            return False

        # Both feasible or same violation - compare objectives
        at_least_one_better = False
        for obj in sol1.objectives:
            val1 = sol1.objectives[obj]
            val2 = sol2.objectives[obj]

            if val1 > val2:  # Minimization
                return False
            if val1 < val2:
                at_least_one_better = True

        return at_least_one_better

    def calculate_crowding_distance(self, front: List[int]):
        """Calculate crowding distance for solutions in front."""
        n = len(front)
        if n <= 2:
            for i in front:
                self.population[i].crowding_distance = float('inf')
            return

        # Initialize distances
        for i in front:
            self.population[i].crowding_distance = 0.0

        # Calculate for each objective
        objectives = list(self.population[front[0]].objectives.keys())

        for obj in objectives:
            # Sort by objective
            sorted_front = sorted(front, key=lambda i: self.population[i].objectives[obj])

            # Boundary solutions get infinite distance
            self.population[sorted_front[0]].crowding_distance = float('inf')
            self.population[sorted_front[-1]].crowding_distance = float('inf')

            # Calculate range
            f_min = self.population[sorted_front[0]].objectives[obj]
            f_max = self.population[sorted_front[-1]].objectives[obj]
            range_val = f_max - f_min

            if range_val == 0:
                continue

            # Update intermediate distances
            for i in range(1, n - 1):
                prev_val = self.population[sorted_front[i - 1]].objectives[obj]
                next_val = self.population[sorted_front[i + 1]].objectives[obj]
                self.population[sorted_front[i]].crowding_distance += (next_val - prev_val) / range_val

    def selection(self) -> List[Solution]:
        """Binary tournament selection."""
        selected = []

        for _ in range(self.population_size):
            # Select two random individuals
            i, j = random.sample(range(len(self.population)), 2)
            sol_i = self.population[i]
            sol_j = self.population[j]

            # Crowded comparison
            if sol_i.rank < sol_j.rank:
                selected.append(copy.deepcopy(sol_i))
            elif sol_j.rank < sol_i.rank:
                selected.append(copy.deepcopy(sol_j))
            elif sol_i.crowding_distance > sol_j.crowding_distance:
                selected.append(copy.deepcopy(sol_i))
            else:
                selected.append(copy.deepcopy(sol_j))

        return selected

    def crossover(self, parent1: Solution, parent2: Solution) -> Tuple[Solution, Solution]:
        """Simulated binary crossover (SBX)."""
        if random.random() > self.crossover_prob:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        child1_vars = {}
        child2_vars = {}

        eta = 20  # Distribution index

        for name, var in self.variables.items():
            x1 = parent1.variables[name]
            x2 = parent2.variables[name]

            if var.variable_type == "categorical":
                # Uniform crossover for categorical
                if random.random() < 0.5:
                    child1_vars[name] = x1
                    child2_vars[name] = x2
                else:
                    child1_vars[name] = x2
                    child2_vars[name] = x1
            else:
                # SBX for continuous/integer
                if abs(x1 - x2) > 1e-14:
                    if x1 > x2:
                        x1, x2 = x2, x1

                    xl = var.lower_bound
                    xu = var.upper_bound

                    u = random.random()
                    beta1 = 1.0 + (2.0 * (x1 - xl) / (x2 - x1))
                    beta2 = 1.0 + (2.0 * (xu - x2) / (x2 - x1))

                    alpha1 = 2.0 - pow(beta1, -(eta + 1))
                    alpha2 = 2.0 - pow(beta2, -(eta + 1))

                    if u <= 1.0 / alpha1:
                        betaq1 = pow(u * alpha1, 1.0 / (eta + 1))
                    else:
                        betaq1 = pow(1.0 / (2.0 - u * alpha1), 1.0 / (eta + 1))

                    if u <= 1.0 / alpha2:
                        betaq2 = pow(u * alpha2, 1.0 / (eta + 1))
                    else:
                        betaq2 = pow(1.0 / (2.0 - u * alpha2), 1.0 / (eta + 1))

                    c1 = 0.5 * ((x1 + x2) - betaq1 * (x2 - x1))
                    c2 = 0.5 * ((x1 + x2) + betaq2 * (x2 - x1))

                    child1_vars[name] = var.clip(c1)
                    child2_vars[name] = var.clip(c2)
                else:
                    child1_vars[name] = x1
                    child2_vars[name] = x2

                if var.variable_type == "integer":
                    child1_vars[name] = round(child1_vars[name])
                    child2_vars[name] = round(child2_vars[name])

        return Solution(variables=child1_vars), Solution(variables=child2_vars)

    def mutation(self, solution: Solution):
        """Polynomial mutation."""
        eta = 20  # Distribution index

        for name, var in self.variables.items():
            if random.random() > self.mutation_prob:
                continue

            x = solution.variables[name]

            if var.variable_type == "categorical":
                # Random selection for categorical
                solution.variables[name] = var.sample_random()
            else:
                xl = var.lower_bound
                xu = var.upper_bound
                delta1 = (x - xl) / (xu - xl)
                delta2 = (xu - x) / (xu - xl)

                u = random.random()
                if u < 0.5:
                    deltaq = pow(2.0 * u + (1.0 - 2.0 * u) * pow(1.0 - delta1, eta + 1),
                                 1.0 / (eta + 1)) - 1.0
                else:
                    deltaq = 1.0 - pow(2.0 * (1.0 - u) + 2.0 * (u - 0.5) * pow(1.0 - delta2, eta + 1),
                                       1.0 / (eta + 1))

                x_new = x + deltaq * (xu - xl)
                solution.variables[name] = var.clip(x_new)

                if var.variable_type == "integer":
                    solution.variables[name] = round(solution.variables[name])

    def evolve(self, generations: int = 100) -> ParetoFront:
        """Run optimization for specified generations."""
        if not self.population:
            self.initialize_population()

        for gen in range(generations):
            self.generation = gen

            # Create offspring
            offspring = []
            mating_pool = self.selection()

            for i in range(0, len(mating_pool), 2):
                if i + 1 < len(mating_pool):
                    child1, child2 = self.crossover(mating_pool[i], mating_pool[i + 1])
                    self.mutation(child1)
                    self.mutation(child2)
                    self._evaluate_solution(child1)
                    self._evaluate_solution(child2)
                    offspring.extend([child1, child2])

            # Combine parent and offspring
            combined = self.population + offspring

            # Non-dominated sorting
            self.population = combined
            fronts = self.non_dominated_sort()

            # Calculate crowding distance for each front
            for front in fronts:
                self.calculate_crowding_distance(front)

            # Select next generation
            new_population = []
            front_idx = 0

            while len(new_population) + len(fronts[front_idx]) <= self.population_size:
                for i in fronts[front_idx]:
                    new_population.append(self.population[i])
                front_idx += 1
                if front_idx >= len(fronts):
                    break

            # Fill remaining slots from next front by crowding distance
            if len(new_population) < self.population_size and front_idx < len(fronts):
                remaining = self.population_size - len(new_population)
                front = fronts[front_idx]
                sorted_front = sorted(front,
                                       key=lambda i: self.population[i].crowding_distance,
                                       reverse=True)
                for i in sorted_front[:remaining]:
                    new_population.append(self.population[i])

            self.population = new_population

            # Store Pareto front
            pareto_solutions = [self.population[i] for i in fronts[0] if i < len(self.population)]
            pareto_front = ParetoFront(solutions=pareto_solutions, generation=gen)
            self.pareto_fronts.append(pareto_front)

        # Return final Pareto front
        fronts = self.non_dominated_sort()
        final_solutions = [self.population[i] for i in fronts[0]]
        return ParetoFront(solutions=final_solutions, generation=self.generation)


class LCAOptimizer:
    """
    High-level LCA optimizer for manufacturing.

    Provides simplified interface for optimizing manufacturing
    configurations with respect to environmental impact.

    Research Value:
    - Unified optimization interface for LCA
    - Manufacturing-specific optimization presets
    - Integration with LCA engine
    """

    def __init__(self):
        self.objective_function = ManufacturingLCAObjective()
        self.default_variables = self._create_default_variables()
        self.default_constraints = self._create_default_constraints()

    def _create_default_variables(self) -> List[DesignVariable]:
        """Create default design variables."""
        return [
            DesignVariable(
                name="material",
                lower_bound=0,
                upper_bound=4,
                variable_type="categorical",
                categories=["pla", "abs", "petg", "nylon", "recycled_pla"]
            ),
            DesignVariable(
                name="process",
                lower_bound=0,
                upper_bound=2,
                variable_type="categorical",
                categories=["fdm", "sla", "sls"]
            ),
            DesignVariable(
                name="infill",
                lower_bound=0.1,
                upper_bound=1.0,
                variable_type="continuous"
            ),
            DesignVariable(
                name="layer_height",
                lower_bound=0.1,
                upper_bound=0.4,
                variable_type="continuous"
            ),
            DesignVariable(
                name="print_speed",
                lower_bound=30,
                upper_bound=150,
                variable_type="continuous"
            ),
            DesignVariable(
                name="renewable_fraction",
                lower_bound=0.0,
                upper_bound=1.0,
                variable_type="continuous"
            ),
        ]

    def _create_default_constraints(self) -> List[OptimizationConstraint]:
        """Create default constraints."""
        return [
            OptimizationConstraint(
                name="min_strength",
                constraint_type="<=",
                limit=0.0
            ),
            OptimizationConstraint(
                name="max_time",
                constraint_type="<=",
                limit=0.0
            ),
        ]

    def optimize(
        self,
        part_volume_cm3: float,
        part_height_mm: float,
        max_budget: float = 100.0,
        objectives: List[str] = None,
        population_size: int = 50,
        generations: int = 50,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Optimize manufacturing configuration for given part.

        Args:
            part_volume_cm3: Part volume in cubic centimeters
            part_height_mm: Part height in millimeters
            max_budget: Maximum budget constraint
            objectives: List of objectives to optimize
            population_size: Population size for NSGA-II
            generations: Number of generations
            seed: Random seed for reproducibility

        Returns:
            Optimization results including Pareto front
        """
        if objectives is None:
            objectives = ["gwp", "cost", "waste"]

        # Add part-specific variables
        variables = self.default_variables.copy()
        for var in variables:
            if var.name == "material":
                pass  # Keep as is

        # Create objective function wrapper for selected objectives
        class FilteredObjective(LCAObjectiveFunction):
            def __init__(self, base_function, selected_objectives, volume, height, budget):
                self.base = base_function
                self.selected = selected_objectives
                self.volume = volume
                self.height = height
                self.budget = budget

            def evaluate(self, vars: Dict[str, float]) -> Dict[str, float]:
                vars["part_volume_cm3"] = self.volume
                vars["part_height_mm"] = self.height
                vars["max_budget"] = self.budget
                all_obj = self.base.evaluate(vars)
                return {k: v for k, v in all_obj.items() if k in self.selected}

            def evaluate_constraints(self, vars: Dict[str, float]) -> Dict[str, float]:
                vars["part_volume_cm3"] = self.volume
                vars["part_height_mm"] = self.height
                vars["max_budget"] = self.budget
                return self.base.evaluate_constraints(vars)

        filtered_objective = FilteredObjective(
            self.objective_function,
            objectives,
            part_volume_cm3,
            part_height_mm,
            max_budget
        )

        # Run optimization
        optimizer = NSGA2Optimizer(
            objective_function=filtered_objective,
            variables=variables,
            constraints=self.default_constraints,
            population_size=population_size,
            seed=seed
        )

        pareto_front = optimizer.evolve(generations)

        # Get best solutions
        extremes = pareto_front.get_extreme_solutions()
        compromise = pareto_front.get_compromise_solution()

        # Convert solutions to readable format
        materials = ["pla", "abs", "petg", "nylon", "recycled_pla"]
        processes = ["fdm", "sla", "sls"]

        def format_solution(sol: Optional[Solution]) -> Optional[Dict]:
            if sol is None:
                return None
            return {
                "material": materials[int(sol.variables.get("material", 0)) % len(materials)],
                "process": processes[int(sol.variables.get("process", 0)) % len(processes)],
                "infill": round(sol.variables.get("infill", 0.2), 2),
                "layer_height": round(sol.variables.get("layer_height", 0.2), 2),
                "print_speed": round(sol.variables.get("print_speed", 60)),
                "renewable_fraction": round(sol.variables.get("renewable_fraction", 0), 2),
                "objectives": {k: round(v, 4) for k, v in sol.objectives.items()},
            }

        return {
            "pareto_front": [format_solution(s) for s in pareto_front.solutions],
            "extreme_solutions": {k: format_solution(v) for k, v in extremes.items()},
            "compromise_solution": format_solution(compromise),
            "generations": generations,
            "population_size": population_size,
            "objectives_optimized": objectives,
        }

    def quick_recommendation(
        self,
        part_volume_cm3: float,
        priority: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Get quick recommendation without full optimization.

        Args:
            part_volume_cm3: Part volume
            priority: "eco" (environmental), "cost", or "balanced"

        Returns:
            Recommended configuration
        """
        recommendations = {
            "eco": {
                "material": "recycled_pla",
                "process": "fdm",
                "infill": 0.15,
                "layer_height": 0.3,
                "print_speed": 60,
                "renewable_fraction": 1.0,
                "rationale": "Minimizes carbon footprint using recycled material and renewable energy",
            },
            "cost": {
                "material": "pla",
                "process": "fdm",
                "infill": 0.15,
                "layer_height": 0.3,
                "print_speed": 100,
                "renewable_fraction": 0.0,
                "rationale": "Minimizes cost with standard materials and fast printing",
            },
            "balanced": {
                "material": "pla",
                "process": "fdm",
                "infill": 0.2,
                "layer_height": 0.2,
                "print_speed": 60,
                "renewable_fraction": 0.5,
                "rationale": "Balances environmental impact, cost, and quality",
            },
        }

        config = recommendations.get(priority, recommendations["balanced"])

        # Calculate impacts for recommendation
        variables = {
            "material": ["pla", "abs", "petg", "nylon", "recycled_pla"].index(config["material"]),
            "process": ["fdm", "sla", "sls"].index(config["process"]),
            "infill": config["infill"],
            "layer_height": config["layer_height"],
            "print_speed": config["print_speed"],
            "renewable_fraction": config["renewable_fraction"],
            "part_volume_cm3": part_volume_cm3,
        }

        objectives = self.objective_function.evaluate(variables)

        return {
            "configuration": config,
            "estimated_impacts": {k: round(v, 4) for k, v in objectives.items()},
            "priority": priority,
        }


# Module exports
__all__ = [
    # Enums
    "OptimizationObjective",
    # Data classes
    "DesignVariable",
    "OptimizationConstraint",
    "Solution",
    "ParetoFront",
    # Objective functions
    "LCAObjectiveFunction",
    "ManufacturingLCAObjective",
    # Optimizers
    "NSGA2Optimizer",
    "LCAOptimizer",
]
