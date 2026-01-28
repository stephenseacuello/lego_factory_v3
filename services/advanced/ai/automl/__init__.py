"""
AutoML Module for LEGO MCP Manufacturing

Provides automated machine learning capabilities including:
- Hyperparameter optimization with Optuna
- Neural architecture search
- Automated model selection

Author: LEGO MCP AI Engineering
"""

from .optuna_tuner import (
    OptunaTuner,
    ObjectiveDirection,
    SamplerType,
    PrunerType,
    HyperparameterSpace,
    OptimizationResult,
    get_quality_prediction_space,
    get_neural_network_space,
    get_vision_model_space,
    get_scheduling_optimizer_space,
    create_sklearn_objective,
)

__all__ = [
    "OptunaTuner",
    "ObjectiveDirection",
    "SamplerType",
    "PrunerType",
    "HyperparameterSpace",
    "OptimizationResult",
    "get_quality_prediction_space",
    "get_neural_network_space",
    "get_vision_model_space",
    "get_scheduling_optimizer_space",
    "create_sklearn_objective",
]
