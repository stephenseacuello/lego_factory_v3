"""
Research Platform - Experiment Tracking & Analysis.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure

MLflow-style experiment tracking for manufacturing research:
- Experiment tracking with parameters and metrics
- Model versioning and registry
- Statistical hypothesis testing
- Reproducibility tools
"""

from .experiment_tracker import ExperimentTracker, Experiment, Run, Metric
from .model_registry import ModelRegistry, RegisteredModel, ModelVersion
from .artifact_store import ArtifactStore, Artifact
from .comparison_engine import ComparisonEngine, ExperimentComparison

__all__ = [
    # Experiment Tracking
    'ExperimentTracker',
    'Experiment',
    'Run',
    'Metric',
    # Model Registry
    'ModelRegistry',
    'RegisteredModel',
    'ModelVersion',
    # Artifacts
    'ArtifactStore',
    'Artifact',
    # Comparison
    'ComparisonEngine',
    'ExperimentComparison',
]
