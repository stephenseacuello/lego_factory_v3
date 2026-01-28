"""
Manufacturing Optimizer - Domain-Specific Optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System

Provides manufacturing-specific optimization for 3D printing and LEGO production.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import logging
import random
import math

from .multi_objective import (
    MultiObjectiveOptimizer,
    ObjectiveFunction,
    ObjectiveDirection,
    OptimizationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PrintParameters:
    """3D print parameters."""
    layer_height: float = 0.2  # mm
    nozzle_temperature: float = 200.0  # °C
    bed_temperature: float = 60.0  # °C
    print_speed: float = 50.0  # mm/s
    infill_percentage: float = 20.0  # %
    wall_count: int = 2
    fan_speed: float = 100.0  # %
    retraction_distance: float = 6.0  # mm
    retraction_speed: float = 25.0  # mm/s

    def to_genes(self) -> List[float]:
        """Convert to gene representation."""
        return [
            self.layer_height,
            self.nozzle_temperature,
            self.bed_temperature,
            self.print_speed,
            self.infill_percentage,
            float(self.wall_count),
            self.fan_speed,
            self.retraction_distance,
            self.retraction_speed,
        ]

    @classmethod
    def from_genes(cls, genes: List[float]) -> 'PrintParameters':
        """Create from gene representation."""
        return cls(
            layer_height=genes[0],
            nozzle_temperature=genes[1],
            bed_temperature=genes[2],
            print_speed=genes[3],
            infill_percentage=genes[4],
            wall_count=int(round(genes[5])),
            fan_speed=genes[6],
            retraction_distance=genes[7],
            retraction_speed=genes[8],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer_height": self.layer_height,
            "nozzle_temperature": self.nozzle_temperature,
            "bed_temperature": self.bed_temperature,
            "print_speed": self.print_speed,
            "infill_percentage": self.infill_percentage,
            "wall_count": self.wall_count,
            "fan_speed": self.fan_speed,
            "retraction_distance": self.retraction_distance,
            "retraction_speed": self.retraction_speed,
        }


class PrintParameterOptimizer:
    """
    Optimizer for 3D print parameters.

    Optimizes for:
    - Print quality (surface finish, dimensional accuracy)
    - Print time
    - Material usage
    - Structural strength
    """

    # Parameter bounds for PLA
    BOUNDS = [
        (0.08, 0.32),      # layer_height (mm)
        (190.0, 230.0),    # nozzle_temperature (°C)
        (50.0, 70.0),      # bed_temperature (°C)
        (30.0, 100.0),     # print_speed (mm/s)
        (10.0, 100.0),     # infill_percentage (%)
        (1.0, 4.0),        # wall_count
        (50.0, 100.0),     # fan_speed (%)
        (0.5, 10.0),       # retraction_distance (mm)
        (15.0, 50.0),      # retraction_speed (mm/s)
    ]

    def __init__(
        self,
        target_quality: str = "balanced",  # "draft", "balanced", "high_quality"
        material: str = "PLA",
        printer_type: str = "generic_fdm",
    ):
        self.target_quality = target_quality
        self.material = material
        self.printer_type = printer_type

    def _quality_score(self, genes: List[float]) -> float:
        """Calculate quality score (higher is better)."""
        params = PrintParameters.from_genes(genes)

        # Layer height affects quality (lower = better quality)
        layer_score = 1.0 - (params.layer_height - 0.08) / 0.24

        # Temperature affects quality (optimal range)
        temp_optimal = 210.0
        temp_score = 1.0 - abs(params.nozzle_temperature - temp_optimal) / 40.0

        # Speed affects quality (slower = better)
        speed_score = 1.0 - (params.print_speed - 30.0) / 70.0

        # Wall count affects quality (more = better)
        wall_score = (params.wall_count - 1.0) / 3.0

        return (layer_score * 0.35 + temp_score * 0.25 +
                speed_score * 0.25 + wall_score * 0.15)

    def _time_score(self, genes: List[float]) -> float:
        """Calculate time efficiency score (higher is faster)."""
        params = PrintParameters.from_genes(genes)

        # Higher layer height = faster
        layer_score = (params.layer_height - 0.08) / 0.24

        # Higher speed = faster
        speed_score = (params.print_speed - 30.0) / 70.0

        # Lower infill = faster
        infill_score = 1.0 - (params.infill_percentage - 10.0) / 90.0

        # Fewer walls = faster
        wall_score = 1.0 - (params.wall_count - 1.0) / 3.0

        return (layer_score * 0.35 + speed_score * 0.35 +
                infill_score * 0.2 + wall_score * 0.1)

    def _strength_score(self, genes: List[float]) -> float:
        """Calculate structural strength score."""
        params = PrintParameters.from_genes(genes)

        # Higher infill = stronger
        infill_score = (params.infill_percentage - 10.0) / 90.0

        # More walls = stronger
        wall_score = (params.wall_count - 1.0) / 3.0

        # Lower layer height = stronger
        layer_score = 1.0 - (params.layer_height - 0.08) / 0.24

        # Optimal temperature = stronger layer adhesion
        temp_optimal = 215.0
        temp_score = 1.0 - abs(params.nozzle_temperature - temp_optimal) / 35.0

        return (infill_score * 0.35 + wall_score * 0.25 +
                layer_score * 0.2 + temp_score * 0.2)

    def _material_score(self, genes: List[float]) -> float:
        """Calculate material efficiency score (higher = less material)."""
        params = PrintParameters.from_genes(genes)

        # Lower infill = less material
        infill_score = 1.0 - (params.infill_percentage - 10.0) / 90.0

        # Fewer walls = less material
        wall_score = 1.0 - (params.wall_count - 1.0) / 3.0

        return infill_score * 0.7 + wall_score * 0.3

    def optimize(
        self,
        objectives: Optional[List[str]] = None,
        generations: int = 50,
        population_size: int = 50,
    ) -> Dict[str, Any]:
        """Run optimization."""
        objectives = objectives or ["quality", "time"]

        objective_functions = []
        for obj in objectives:
            if obj == "quality":
                objective_functions.append(ObjectiveFunction(
                    name="quality",
                    function=self._quality_score,
                    direction=ObjectiveDirection.MAXIMIZE,
                ))
            elif obj == "time":
                objective_functions.append(ObjectiveFunction(
                    name="time",
                    function=self._time_score,
                    direction=ObjectiveDirection.MAXIMIZE,
                ))
            elif obj == "strength":
                objective_functions.append(ObjectiveFunction(
                    name="strength",
                    function=self._strength_score,
                    direction=ObjectiveDirection.MAXIMIZE,
                ))
            elif obj == "material":
                objective_functions.append(ObjectiveFunction(
                    name="material",
                    function=self._material_score,
                    direction=ObjectiveDirection.MAXIMIZE,
                ))

        optimizer = MultiObjectiveOptimizer(
            objectives=objective_functions,
            gene_bounds=self.BOUNDS,
            population_size=population_size,
            max_generations=generations,
        )

        result = optimizer.run()

        # Convert Pareto front to parameters
        pareto_params = []
        for sol in result.pareto_front.solutions:
            params = PrintParameters.from_genes(sol.genes)
            pareto_params.append({
                "parameters": params.to_dict(),
                "objectives": dict(zip(objectives, sol.objectives)),
            })

        # Select recommended based on target quality
        recommended = self._select_recommended(result, objectives)

        return {
            "recommended": recommended.to_dict() if recommended else None,
            "pareto_front": pareto_params,
            "generations": result.generations,
            "objectives": objectives,
        }

    def _select_recommended(
        self,
        result: OptimizationResult,
        objectives: List[str],
    ) -> Optional[PrintParameters]:
        """Select recommended parameters based on target quality."""
        if not result.pareto_front.solutions:
            return None

        solutions = result.pareto_front.solutions

        if self.target_quality == "draft":
            # Prioritize time
            if "time" in objectives:
                idx = objectives.index("time")
                best = min(solutions, key=lambda s: s.objectives[idx])
            else:
                best = solutions[0]
        elif self.target_quality == "high_quality":
            # Prioritize quality
            if "quality" in objectives:
                idx = objectives.index("quality")
                best = min(solutions, key=lambda s: s.objectives[idx])
            else:
                best = solutions[0]
        else:
            # Balanced - middle of Pareto front
            mid_idx = len(solutions) // 2
            best = solutions[mid_idx]

        return PrintParameters.from_genes(best.genes)


class SchedulingOptimizer:
    """
    Optimizer for job shop scheduling.

    Optimizes for:
    - Makespan minimization
    - Machine utilization
    - Due date adherence
    - Energy efficiency
    """

    def __init__(
        self,
        jobs: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
    ):
        self.jobs = jobs
        self.machines = machines
        self.n_jobs = len(jobs)
        self.n_machines = len(machines)

    def optimize(
        self,
        generations: int = 100,
        population_size: int = 50,
    ) -> Dict[str, Any]:
        """Run scheduling optimization."""
        # Simple GA-based scheduling optimization

        # Generate initial schedule
        best_schedule = list(range(self.n_jobs))
        random.shuffle(best_schedule)
        best_makespan = self._evaluate_makespan(best_schedule)

        for gen in range(generations):
            # Generate variations
            for _ in range(population_size):
                schedule = best_schedule.copy()

                # Apply mutation (swap two jobs)
                i, j = random.sample(range(self.n_jobs), 2)
                schedule[i], schedule[j] = schedule[j], schedule[i]

                makespan = self._evaluate_makespan(schedule)

                if makespan < best_makespan:
                    best_makespan = makespan
                    best_schedule = schedule

        # Build result
        scheduled_jobs = []
        current_time = 0
        for job_idx in best_schedule:
            job = self.jobs[job_idx]
            scheduled_jobs.append({
                "job_id": job.get("id", f"job_{job_idx}"),
                "start_time": current_time,
                "end_time": current_time + job.get("duration", 1),
                "machine": job_idx % self.n_machines,
            })
            current_time += job.get("duration", 1)

        return {
            "schedule": scheduled_jobs,
            "makespan": best_makespan,
            "utilization": self._calculate_utilization(best_schedule),
            "generations": generations,
        }

    def _evaluate_makespan(self, schedule: List[int]) -> float:
        """Calculate makespan for a schedule."""
        machine_times = [0.0] * self.n_machines

        for job_idx in schedule:
            job = self.jobs[job_idx]
            duration = job.get("duration", 1.0)
            machine = job_idx % self.n_machines

            machine_times[machine] += duration

        return max(machine_times)

    def _calculate_utilization(self, schedule: List[int]) -> float:
        """Calculate machine utilization."""
        machine_times = [0.0] * self.n_machines

        for job_idx in schedule:
            job = self.jobs[job_idx]
            duration = job.get("duration", 1.0)
            machine = job_idx % self.n_machines
            machine_times[machine] += duration

        makespan = max(machine_times)
        if makespan == 0:
            return 0.0

        total_busy = sum(machine_times)
        total_available = makespan * self.n_machines

        return total_busy / total_available


class QualityOptimizer:
    """
    Optimizer for quality prediction model parameters.

    Optimizes inspection thresholds and model hyperparameters.
    """

    def __init__(
        self,
        defect_costs: Dict[str, float],
        inspection_costs: float,
        false_positive_cost: float,
        false_negative_cost: float,
    ):
        self.defect_costs = defect_costs
        self.inspection_costs = inspection_costs
        self.false_positive_cost = false_positive_cost
        self.false_negative_cost = false_negative_cost

    def optimize_threshold(
        self,
        precision_recall_curve: List[Tuple[float, float, float]],
    ) -> Dict[str, Any]:
        """
        Optimize classification threshold based on cost.

        Args:
            precision_recall_curve: List of (threshold, precision, recall) tuples
        """
        best_threshold = 0.5
        best_cost = float('inf')

        for threshold, precision, recall in precision_recall_curve:
            # Calculate expected cost
            # Higher precision = fewer false positives
            # Higher recall = fewer false negatives
            fp_rate = 1.0 - precision if precision > 0 else 1.0
            fn_rate = 1.0 - recall

            cost = (
                fp_rate * self.false_positive_cost +
                fn_rate * self.false_negative_cost +
                self.inspection_costs
            )

            if cost < best_cost:
                best_cost = cost
                best_threshold = threshold

        return {
            "optimal_threshold": best_threshold,
            "expected_cost": best_cost,
            "recommendation": self._get_threshold_recommendation(best_threshold),
        }

    def _get_threshold_recommendation(self, threshold: float) -> str:
        """Get recommendation based on threshold."""
        if threshold < 0.3:
            return "Very sensitive detection - may increase false positives"
        elif threshold < 0.5:
            return "Sensitive detection - balanced approach"
        elif threshold < 0.7:
            return "Moderate detection - some defects may be missed"
        else:
            return "Conservative detection - only high-confidence defects"


class ManufacturingOptimizer:
    """
    Unified manufacturing optimization interface.

    Combines print parameter, scheduling, and quality optimization.
    """

    def __init__(self):
        self.print_optimizer: Optional[PrintParameterOptimizer] = None
        self.scheduling_optimizer: Optional[SchedulingOptimizer] = None
        self.quality_optimizer: Optional[QualityOptimizer] = None

    def optimize_print_parameters(
        self,
        target_quality: str = "balanced",
        material: str = "PLA",
        objectives: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Optimize 3D print parameters."""
        self.print_optimizer = PrintParameterOptimizer(
            target_quality=target_quality,
            material=material,
        )
        return self.print_optimizer.optimize(objectives=objectives)

    def optimize_schedule(
        self,
        jobs: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Optimize production schedule."""
        self.scheduling_optimizer = SchedulingOptimizer(jobs, machines)
        return self.scheduling_optimizer.optimize()

    def optimize_quality_threshold(
        self,
        precision_recall_curve: List[Tuple[float, float, float]],
        defect_costs: Dict[str, float],
        inspection_costs: float = 1.0,
        fp_cost: float = 10.0,
        fn_cost: float = 100.0,
    ) -> Dict[str, Any]:
        """Optimize quality inspection threshold."""
        self.quality_optimizer = QualityOptimizer(
            defect_costs=defect_costs,
            inspection_costs=inspection_costs,
            false_positive_cost=fp_cost,
            false_negative_cost=fn_cost,
        )
        return self.quality_optimizer.optimize_threshold(precision_recall_curve)
