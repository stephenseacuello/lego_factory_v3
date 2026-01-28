"""
Algorithm Registry for Flask CNC SCADA Scheduling
=================================================
Registry of all available scheduling algorithms with metadata.

Provides:
- Algorithm registration and discovery
- Algorithm metadata and descriptions
- Best-use-case recommendations
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlgorithmCategory(Enum):
    """Categories of scheduling algorithms."""
    DISPATCHING = "dispatching"      # Simple priority rules
    OPTIMIZATION = "optimization"    # Exact methods (OR-Tools)
    METAHEURISTIC = "metaheuristic"  # Genetic, SA, etc.


@dataclass
class AlgorithmInfo:
    """Information about a scheduling algorithm."""
    id: str
    name: str
    category: AlgorithmCategory
    description: str
    best_for: str
    complexity: str  # O(n), O(n^2), etc.
    typical_runtime: str  # "< 1 sec", "1-60 sec", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    supports_setup_times: bool = True
    supports_due_dates: bool = True
    supports_priorities: bool = True
    supports_multi_machine: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "best_for": self.best_for,
            "complexity": self.complexity,
            "typical_runtime": self.typical_runtime,
            "parameters": self.parameters,
            "supports": {
                "setup_times": self.supports_setup_times,
                "due_dates": self.supports_due_dates,
                "priorities": self.supports_priorities,
                "multi_machine": self.supports_multi_machine,
            },
        }


# Define all algorithms
ALGORITHMS = {
    "FIFO": AlgorithmInfo(
        id="FIFO",
        name="First In First Out",
        category=AlgorithmCategory.DISPATCHING,
        description="Schedules jobs in the order they were received. Simple and fair.",
        best_for="Simple queue management, fairness requirements",
        complexity="O(n)",
        typical_runtime="< 1 sec",
    ),
    "EDD": AlgorithmInfo(
        id="EDD",
        name="Earliest Due Date",
        category=AlgorithmCategory.DISPATCHING,
        description="Prioritizes jobs with earliest due dates. Minimizes maximum lateness.",
        best_for="Meeting delivery deadlines, customer commitments",
        complexity="O(n log n)",
        typical_runtime="< 1 sec",
    ),
    "SPT": AlgorithmInfo(
        id="SPT",
        name="Shortest Processing Time",
        category=AlgorithmCategory.DISPATCHING,
        description="Shortest jobs first. Minimizes average flow time and WIP.",
        best_for="Reducing work-in-progress, quick turnaround for small jobs",
        complexity="O(n log n)",
        typical_runtime="< 1 sec",
    ),
    "CR": AlgorithmInfo(
        id="CR",
        name="Critical Ratio",
        category=AlgorithmCategory.DISPATCHING,
        description="Ratio of time remaining to work remaining. Balances urgency and workload.",
        best_for="Dynamic environments with changing priorities",
        complexity="O(n log n)",
        typical_runtime="< 1 sec",
    ),
    "WSPT": AlgorithmInfo(
        id="WSPT",
        name="Weighted Shortest Processing Time",
        category=AlgorithmCategory.DISPATCHING,
        description="Combines processing time and priority weights. Minimizes weighted completion time.",
        best_for="High-priority jobs with varying sizes, cost optimization",
        complexity="O(n log n)",
        typical_runtime="< 1 sec",
        parameters={
            "weight_source": {
                "description": "Source of job weights",
                "options": ["priority", "custom"],
                "default": "priority",
            },
        },
    ),
    "SETUP_MIN": AlgorithmInfo(
        id="SETUP_MIN",
        name="Setup Time Minimization",
        category=AlgorithmCategory.DISPATCHING,
        description="Groups similar jobs to minimize changeover/setup times.",
        best_for="High setup costs, batch production, family scheduling",
        complexity="O(n^2)",
        typical_runtime="< 5 sec",
        parameters={
            "similarity_threshold": {
                "description": "Threshold for considering jobs similar",
                "type": "float",
                "default": 0.8,
            },
        },
    ),
    "GENETIC": AlgorithmInfo(
        id="GENETIC",
        name="Genetic Algorithm",
        category=AlgorithmCategory.METAHEURISTIC,
        description="Evolutionary optimization inspired by natural selection. Good for complex multi-objective problems.",
        best_for="Multi-objective optimization, complex constraints, large problem instances",
        complexity="O(g * p * n)",  # generations * population * jobs
        typical_runtime="10-120 sec",
        parameters={
            "population_size": {
                "description": "Number of solutions in population",
                "type": "int",
                "default": 50,
            },
            "generations": {
                "description": "Number of generations to evolve",
                "type": "int",
                "default": 100,
            },
            "mutation_rate": {
                "description": "Probability of mutation",
                "type": "float",
                "default": 0.1,
            },
            "crossover_rate": {
                "description": "Probability of crossover",
                "type": "float",
                "default": 0.8,
            },
        },
    ),
    "SA": AlgorithmInfo(
        id="SA",
        name="Simulated Annealing",
        category=AlgorithmCategory.METAHEURISTIC,
        description="Probabilistic optimization that can escape local minima. Good for large search spaces.",
        best_for="Large problem instances, avoiding local optima",
        complexity="O(i * n)",  # iterations * jobs
        typical_runtime="5-60 sec",
        parameters={
            "initial_temp": {
                "description": "Starting temperature",
                "type": "float",
                "default": 1000.0,
            },
            "cooling_rate": {
                "description": "Temperature reduction rate",
                "type": "float",
                "default": 0.995,
            },
            "min_temp": {
                "description": "Stopping temperature",
                "type": "float",
                "default": 0.1,
            },
        },
    ),
    "ORTOOLS": AlgorithmInfo(
        id="ORTOOLS",
        name="OR-Tools CP-SAT",
        category=AlgorithmCategory.OPTIMIZATION,
        description="Google's constraint programming solver. Finds optimal or near-optimal solutions.",
        best_for="Finding optimal solutions, proving optimality, complex constraints",
        complexity="Exponential (but practical for typical sizes)",
        typical_runtime="1-300 sec",
        parameters={
            "time_limit_sec": {
                "description": "Maximum solve time in seconds",
                "type": "float",
                "default": 60.0,
            },
            "objective": {
                "description": "Optimization objective",
                "options": ["makespan", "tardiness", "weighted_tardiness", "flow_time"],
                "default": "makespan",
            },
        },
    ),
}


class AlgorithmRegistry:
    """
    Registry for scheduling algorithms.

    Provides algorithm discovery, metadata, and recommendations.
    """

    def __init__(self):
        """Initialize registry with default algorithms."""
        self._algorithms: Dict[str, AlgorithmInfo] = dict(ALGORITHMS)
        logger.info(f"AlgorithmRegistry initialized with {len(self._algorithms)} algorithms")

    def get(self, algorithm_id: str) -> Optional[AlgorithmInfo]:
        """Get algorithm by ID."""
        return self._algorithms.get(algorithm_id.upper())

    def list_all(self) -> List[AlgorithmInfo]:
        """Get all registered algorithms."""
        return list(self._algorithms.values())

    def list_by_category(self, category: AlgorithmCategory) -> List[AlgorithmInfo]:
        """Get algorithms by category."""
        return [a for a in self._algorithms.values() if a.category == category]

    def get_dispatching_rules(self) -> List[AlgorithmInfo]:
        """Get all dispatching rules."""
        return self.list_by_category(AlgorithmCategory.DISPATCHING)

    def get_metaheuristics(self) -> List[AlgorithmInfo]:
        """Get all metaheuristic algorithms."""
        return self.list_by_category(AlgorithmCategory.METAHEURISTIC)

    def get_optimization(self) -> List[AlgorithmInfo]:
        """Get all exact optimization algorithms."""
        return self.list_by_category(AlgorithmCategory.OPTIMIZATION)

    def recommend(
        self,
        job_count: int,
        machine_count: int,
        has_due_dates: bool = True,
        has_priorities: bool = True,
        has_setup_times: bool = False,
        time_limit_sec: float = 60.0,
    ) -> List[AlgorithmInfo]:
        """
        Recommend algorithms based on problem characteristics.

        Args:
            job_count: Number of jobs to schedule
            machine_count: Number of machines
            has_due_dates: Whether jobs have due dates
            has_priorities: Whether jobs have priorities
            has_setup_times: Whether operations have setup times
            time_limit_sec: Available computation time

        Returns:
            List of recommended algorithms (best first)
        """
        recommendations = []

        # Small problems (<= 20 jobs) - use OR-Tools
        if job_count <= 20 and time_limit_sec >= 30:
            recommendations.append(self._algorithms["ORTOOLS"])

        # Medium problems with due dates - use EDD or CR
        if has_due_dates:
            recommendations.append(self._algorithms["EDD"])
            recommendations.append(self._algorithms["CR"])

        # Problems with priorities - use WSPT
        if has_priorities:
            recommendations.append(self._algorithms["WSPT"])

        # Problems with setup times - use SETUP_MIN
        if has_setup_times:
            recommendations.append(self._algorithms["SETUP_MIN"])

        # Large problems with time - use metaheuristics
        if job_count > 50 and time_limit_sec >= 30:
            recommendations.append(self._algorithms["GENETIC"])
            recommendations.append(self._algorithms["SA"])

        # Always include fast heuristics as fallback
        if self._algorithms["SPT"] not in recommendations:
            recommendations.append(self._algorithms["SPT"])
        if self._algorithms["FIFO"] not in recommendations:
            recommendations.append(self._algorithms["FIFO"])

        return recommendations[:5]  # Return top 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary."""
        return {
            "algorithms": {
                aid: algo.to_dict() for aid, algo in self._algorithms.items()
            },
            "categories": [c.value for c in AlgorithmCategory],
            "count": len(self._algorithms),
        }


# Global registry instance
_registry: Optional[AlgorithmRegistry] = None


def get_algorithm_registry() -> AlgorithmRegistry:
    """Get global algorithm registry instance."""
    global _registry
    if _registry is None:
        _registry = AlgorithmRegistry()
    return _registry
