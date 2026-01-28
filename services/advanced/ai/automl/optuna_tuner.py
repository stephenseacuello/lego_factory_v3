"""
AutoML Hyperparameter Tuning with Optuna
LegoMCP PhD-Level Manufacturing Platform

Provides automated hyperparameter optimization for:
- Quality prediction models
- Defect detection models
- Scheduling optimization
- Predictive maintenance

Features:
- Bayesian optimization (TPE)
- Pruning for early stopping
- Multi-objective optimization
- Distributed training support
- Integration with MLflow
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib

try:
    import optuna
    from optuna.trial import Trial
    from optuna.pruners import MedianPruner, HyperbandPruner, SuccessiveHalvingPruner
    from optuna.samplers import TPESampler, CmaEsSampler, RandomSampler
    from optuna.integration import MLflowCallback
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

import numpy as np

logger = logging.getLogger(__name__)


class ObjectiveDirection(Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class SamplerType(Enum):
    TPE = "tpe"
    CMAES = "cmaes"
    RANDOM = "random"


class PrunerType(Enum):
    MEDIAN = "median"
    HYPERBAND = "hyperband"
    SUCCESSIVE_HALVING = "successive_halving"
    NONE = "none"


@dataclass
class HyperparameterSpace:
    """Definition of hyperparameter search space."""
    name: str
    param_type: str  # int, float, categorical, loguniform
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[Any]] = None
    step: Optional[float] = None
    log: bool = False

    def suggest(self, trial: "Trial") -> Any:
        """Suggest a value for this hyperparameter."""
        if self.param_type == "int":
            return trial.suggest_int(
                self.name,
                int(self.low),
                int(self.high),
                step=int(self.step) if self.step else 1,
                log=self.log,
            )
        elif self.param_type == "float":
            if self.log:
                return trial.suggest_float(
                    self.name, self.low, self.high, log=True
                )
            else:
                return trial.suggest_float(
                    self.name, self.low, self.high, step=self.step
                )
        elif self.param_type == "categorical":
            return trial.suggest_categorical(self.name, self.choices)
        elif self.param_type == "loguniform":
            return trial.suggest_float(self.name, self.low, self.high, log=True)
        else:
            raise ValueError(f"Unknown param type: {self.param_type}")


@dataclass
class OptimizationResult:
    """Result of hyperparameter optimization."""
    study_name: str
    best_params: Dict[str, Any]
    best_value: float
    best_trial_number: int
    n_trials: int
    optimization_history: List[Dict[str, Any]]
    param_importances: Dict[str, float]
    duration_seconds: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "study_name": self.study_name,
            "best_params": self.best_params,
            "best_value": self.best_value,
            "best_trial_number": self.best_trial_number,
            "n_trials": self.n_trials,
            "optimization_history": self.optimization_history,
            "param_importances": self.param_importances,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
        }


class OptunaTuner:
    """
    AutoML hyperparameter tuning using Optuna.

    Supports:
    - Single and multi-objective optimization
    - Distributed optimization
    - Early stopping with pruning
    - MLflow integration
    - Various samplers (TPE, CMA-ES, Random)
    """

    def __init__(
        self,
        study_name: str = None,
        storage: str = None,
        sampler_type: SamplerType = SamplerType.TPE,
        pruner_type: PrunerType = PrunerType.HYPERBAND,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        directions: List[ObjectiveDirection] = None,
        seed: int = 42,
        mlflow_tracking: bool = True,
    ):
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is required for AutoML. Install with: pip install optuna")

        self.study_name = study_name or f"legomcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.storage = storage or os.environ.get(
            "OPTUNA_STORAGE",
            "sqlite:///optuna.db"
        )
        self.seed = seed
        self.mlflow_tracking = mlflow_tracking and MLFLOW_AVAILABLE

        # Setup sampler
        self.sampler = self._create_sampler(sampler_type, seed)

        # Setup pruner
        self.pruner = self._create_pruner(pruner_type)

        # Direction(s) for optimization
        self.direction = direction
        self.directions = directions
        self.is_multi_objective = directions is not None

        # Study will be created on first use
        self._study = None

    def _create_sampler(self, sampler_type: SamplerType, seed: int):
        """Create the optimization sampler."""
        if sampler_type == SamplerType.TPE:
            return TPESampler(seed=seed, multivariate=True)
        elif sampler_type == SamplerType.CMAES:
            return CmaEsSampler(seed=seed)
        elif sampler_type == SamplerType.RANDOM:
            return RandomSampler(seed=seed)
        else:
            raise ValueError(f"Unknown sampler type: {sampler_type}")

    def _create_pruner(self, pruner_type: PrunerType):
        """Create the pruning strategy."""
        if pruner_type == PrunerType.MEDIAN:
            return MedianPruner(n_startup_trials=5, n_warmup_steps=10)
        elif pruner_type == PrunerType.HYPERBAND:
            return HyperbandPruner(min_resource=1, max_resource=100, reduction_factor=3)
        elif pruner_type == PrunerType.SUCCESSIVE_HALVING:
            return SuccessiveHalvingPruner()
        elif pruner_type == PrunerType.NONE:
            return optuna.pruners.NopPruner()
        else:
            raise ValueError(f"Unknown pruner type: {pruner_type}")

    @property
    def study(self):
        """Get or create the Optuna study."""
        if self._study is None:
            if self.is_multi_objective:
                self._study = optuna.create_study(
                    study_name=self.study_name,
                    storage=self.storage,
                    sampler=self.sampler,
                    directions=[d.value for d in self.directions],
                    load_if_exists=True,
                )
            else:
                self._study = optuna.create_study(
                    study_name=self.study_name,
                    storage=self.storage,
                    sampler=self.sampler,
                    pruner=self.pruner,
                    direction=self.direction.value,
                    load_if_exists=True,
                )
        return self._study

    def optimize(
        self,
        objective: Callable[[Trial], Union[float, Tuple[float, ...]]],
        n_trials: int = 100,
        timeout: int = None,
        n_jobs: int = 1,
        show_progress_bar: bool = True,
        callbacks: List[Callable] = None,
    ) -> OptimizationResult:
        """
        Run hyperparameter optimization.

        Args:
            objective: Objective function that takes a Trial and returns value(s) to optimize
            n_trials: Number of trials to run
            timeout: Maximum time in seconds
            n_jobs: Number of parallel jobs (-1 for all CPUs)
            show_progress_bar: Whether to show progress
            callbacks: List of callback functions

        Returns:
            OptimizationResult with best parameters and history
        """
        start_time = datetime.utcnow()

        # Setup callbacks
        all_callbacks = callbacks or []

        if self.mlflow_tracking:
            mlflow_callback = MLflowCallback(
                tracking_uri=os.environ.get("MLFLOW_TRACKING_URI"),
                metric_name="objective_value",
            )
            all_callbacks.append(mlflow_callback)

        # Run optimization
        self.study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=show_progress_bar,
            callbacks=all_callbacks if all_callbacks else None,
        )

        # Calculate results
        duration = (datetime.utcnow() - start_time).total_seconds()

        if self.is_multi_objective:
            # Multi-objective: return Pareto front
            best_trials = self.study.best_trials
            best_params = best_trials[0].params if best_trials else {}
            best_value = best_trials[0].values[0] if best_trials else float('inf')
            best_trial_number = best_trials[0].number if best_trials else 0
        else:
            best_params = self.study.best_params
            best_value = self.study.best_value
            best_trial_number = self.study.best_trial.number

        # Get optimization history
        history = []
        for trial in self.study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                history.append({
                    "number": trial.number,
                    "value": trial.value if not self.is_multi_objective else trial.values,
                    "params": trial.params,
                    "duration": trial.duration.total_seconds() if trial.duration else 0,
                })

        # Calculate parameter importance
        try:
            if not self.is_multi_objective:
                importances = optuna.importance.get_param_importances(self.study)
            else:
                importances = {}
        except Exception:
            importances = {}

        return OptimizationResult(
            study_name=self.study_name,
            best_params=best_params,
            best_value=best_value,
            best_trial_number=best_trial_number,
            n_trials=len(self.study.trials),
            optimization_history=history,
            param_importances=importances,
            duration_seconds=duration,
        )

    def suggest_params(
        self,
        trial: Trial,
        param_spaces: List[HyperparameterSpace],
    ) -> Dict[str, Any]:
        """
        Suggest hyperparameters for a trial.

        Args:
            trial: Optuna trial object
            param_spaces: List of hyperparameter space definitions

        Returns:
            Dictionary of suggested parameter values
        """
        params = {}
        for space in param_spaces:
            params[space.name] = space.suggest(trial)
        return params

    def get_best_params(self) -> Dict[str, Any]:
        """Get the best parameters found so far."""
        if self.is_multi_objective:
            if self.study.best_trials:
                return self.study.best_trials[0].params
            return {}
        return self.study.best_params

    def get_pareto_front(self) -> List[Dict[str, Any]]:
        """Get Pareto front for multi-objective optimization."""
        if not self.is_multi_objective:
            raise ValueError("Pareto front only available for multi-objective optimization")

        return [
            {"values": trial.values, "params": trial.params}
            for trial in self.study.best_trials
        ]


# =========================================================================
# PREDEFINED SEARCH SPACES FOR MANUFACTURING ML
# =========================================================================

def get_quality_prediction_space() -> List[HyperparameterSpace]:
    """Search space for quality prediction models."""
    return [
        HyperparameterSpace("learning_rate", "loguniform", 1e-5, 1e-1),
        HyperparameterSpace("n_estimators", "int", 50, 500, step=50),
        HyperparameterSpace("max_depth", "int", 3, 15),
        HyperparameterSpace("min_samples_split", "int", 2, 20),
        HyperparameterSpace("min_samples_leaf", "int", 1, 10),
        HyperparameterSpace("subsample", "float", 0.6, 1.0),
        HyperparameterSpace("colsample_bytree", "float", 0.6, 1.0),
        HyperparameterSpace("reg_alpha", "loguniform", 1e-8, 10.0),
        HyperparameterSpace("reg_lambda", "loguniform", 1e-8, 10.0),
    ]


def get_neural_network_space() -> List[HyperparameterSpace]:
    """Search space for neural network models."""
    return [
        HyperparameterSpace("learning_rate", "loguniform", 1e-5, 1e-2),
        HyperparameterSpace("batch_size", "categorical", choices=[16, 32, 64, 128, 256]),
        HyperparameterSpace("n_layers", "int", 1, 5),
        HyperparameterSpace("hidden_dim", "categorical", choices=[32, 64, 128, 256, 512]),
        HyperparameterSpace("dropout", "float", 0.0, 0.5),
        HyperparameterSpace("weight_decay", "loguniform", 1e-6, 1e-2),
        HyperparameterSpace("optimizer", "categorical", choices=["adam", "sgd", "adamw"]),
        HyperparameterSpace("activation", "categorical", choices=["relu", "gelu", "silu"]),
    ]


def get_vision_model_space() -> List[HyperparameterSpace]:
    """Search space for computer vision models (defect detection)."""
    return [
        HyperparameterSpace("learning_rate", "loguniform", 1e-5, 1e-2),
        HyperparameterSpace("batch_size", "categorical", choices=[4, 8, 16, 32]),
        HyperparameterSpace("backbone", "categorical", choices=["resnet50", "efficientnet_b0", "mobilenetv3"]),
        HyperparameterSpace("image_size", "categorical", choices=[224, 320, 416, 512]),
        HyperparameterSpace("augmentation_strength", "float", 0.0, 1.0),
        HyperparameterSpace("confidence_threshold", "float", 0.3, 0.7),
        HyperparameterSpace("iou_threshold", "float", 0.3, 0.7),
        HyperparameterSpace("freeze_backbone", "categorical", choices=[True, False]),
    ]


def get_scheduling_optimizer_space() -> List[HyperparameterSpace]:
    """Search space for scheduling optimization."""
    return [
        HyperparameterSpace("population_size", "int", 50, 500, step=50),
        HyperparameterSpace("crossover_rate", "float", 0.5, 0.95),
        HyperparameterSpace("mutation_rate", "float", 0.01, 0.3),
        HyperparameterSpace("elite_size", "int", 1, 20),
        HyperparameterSpace("tournament_size", "int", 2, 10),
        HyperparameterSpace("generations", "int", 100, 1000, step=100),
        HyperparameterSpace("selection_method", "categorical", choices=["tournament", "roulette", "rank"]),
    ]


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def create_sklearn_objective(
    model_class: type,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    param_spaces: List[HyperparameterSpace],
    metric: str = "accuracy",
) -> Callable[[Trial], float]:
    """
    Create an objective function for scikit-learn models.

    Args:
        model_class: Sklearn model class
        X_train, y_train: Training data
        X_val, y_val: Validation data
        param_spaces: Hyperparameter search space
        metric: Metric to optimize

    Returns:
        Objective function for Optuna
    """
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score, recall_score,
        mean_squared_error, mean_absolute_error, r2_score
    )

    metrics = {
        "accuracy": accuracy_score,
        "f1": lambda y_true, y_pred: f1_score(y_true, y_pred, average="weighted"),
        "precision": lambda y_true, y_pred: precision_score(y_true, y_pred, average="weighted"),
        "recall": lambda y_true, y_pred: recall_score(y_true, y_pred, average="weighted"),
        "mse": mean_squared_error,
        "mae": mean_absolute_error,
        "r2": r2_score,
    }

    def objective(trial: Trial) -> float:
        # Suggest parameters
        params = {}
        for space in param_spaces:
            params[space.name] = space.suggest(trial)

        # Train model
        model = model_class(**params)
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_val)
        score = metrics[metric](y_val, y_pred)

        return score

    return objective
