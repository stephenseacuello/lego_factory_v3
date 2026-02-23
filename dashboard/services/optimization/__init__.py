"""
Optimization Service Layer - Multi-Objective Manufacturing Optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Provides genetic algorithms, Pareto optimization, and manufacturing-specific optimizers.
"""

from .genetic_algorithm import GeneticAlgorithm, Individual, Population
from .multi_objective import (
    MultiObjectiveOptimizer,
    ParetoFront,
    ObjectiveFunction,
    OptimizationResult,
)
from .manufacturing_optimizer import (
    ManufacturingOptimizer,
    PrintParameterOptimizer,
    SchedulingOptimizer,
    QualityOptimizer,
)
from .bayesian_optimizer import BayesianOptimizer, AcquisitionFunction

__all__ = [
    # Genetic Algorithm
    'GeneticAlgorithm',
    'Individual',
    'Population',
    # Multi-Objective
    'MultiObjectiveOptimizer',
    'ParetoFront',
    'ObjectiveFunction',
    'OptimizationResult',
    # Manufacturing
    'ManufacturingOptimizer',
    'PrintParameterOptimizer',
    'SchedulingOptimizer',
    'QualityOptimizer',
    # Bayesian
    'BayesianOptimizer',
    'AcquisitionFunction',
]
