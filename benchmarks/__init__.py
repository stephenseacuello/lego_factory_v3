"""
Benchmarking Suite for LegoMCP Manufacturing System.

This module provides comprehensive benchmarks for:
- Scheduling algorithms (CP-SAT, NSGA-II, RL, Quantum)
- Quality prediction models
- Digital twin performance
- Sustainability metrics

Research Value:
- Reproducible performance comparison
- Standard manufacturing datasets
- Academic publication support
"""

from .scheduling_benchmark import (
    SchedulingBenchmark,
    SchedulingDataset,
    SchedulingMetrics,
    run_scheduling_benchmark,
)
from .quality_benchmark import (
    QualityBenchmark,
    QualityDataset,
    QualityMetrics,
    run_quality_benchmark,
)

__all__ = [
    'SchedulingBenchmark',
    'SchedulingDataset',
    'SchedulingMetrics',
    'run_scheduling_benchmark',
    'QualityBenchmark',
    'QualityDataset',
    'QualityMetrics',
    'run_quality_benchmark',
]
