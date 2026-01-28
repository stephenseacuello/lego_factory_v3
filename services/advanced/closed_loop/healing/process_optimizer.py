"""
Process Optimizer - Continuous process optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of process optimization."""
    optimal_parameters: Dict[str, float]
    predicted_quality: float
    confidence: float
    iterations: int
    improvement: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProcessState:
    """Current process state."""
    parameters: Dict[str, float]
    quality_metrics: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ProcessOptimizer:
    """
    Continuous process optimization using Bayesian methods.

    Features:
    - Bayesian optimization
    - Multi-objective optimization
    - Online learning
    - Constraint handling
    """

    def __init__(self,
                 parameter_bounds: Dict[str, Tuple[float, float]],
                 objective: str = "quality"):
        """
        Initialize optimizer.

        Args:
            parameter_bounds: {param: (min, max)}
            objective: Primary objective to optimize
        """
        self.parameter_bounds = parameter_bounds
        self.objective = objective
        self._observations: List[ProcessState] = []
        self._best_params: Optional[Dict[str, float]] = None
        self._best_quality: float = float('-inf')

    def update(self, state: ProcessState) -> None:
        """
        Update optimizer with new observation.

        Args:
            state: Current process state
        """
        self._observations.append(state)

        # Update best
        quality = state.quality_metrics.get(self.objective, 0)
        if quality > self._best_quality:
            self._best_quality = quality
            self._best_params = state.parameters.copy()

        logger.debug(f"Optimizer updated: {len(self._observations)} observations")

    def suggest_parameters(self,
                          n_suggestions: int = 1,
                          exploration: float = 0.1) -> List[Dict[str, float]]:
        """
        Suggest next parameters to try.

        Args:
            n_suggestions: Number of suggestions
            exploration: Exploration vs exploitation trade-off

        Returns:
            List of parameter suggestions
        """
        if len(self._observations) < 5:
            # Not enough data - use random exploration
            return self._random_suggestions(n_suggestions)

        suggestions = []

        for _ in range(n_suggestions):
            if np.random.random() < exploration:
                # Explore
                suggestion = self._random_suggestion()
            else:
                # Exploit - perturb best known
                suggestion = self._perturb_best()

            suggestions.append(suggestion)

        return suggestions

    def _random_suggestions(self, n: int) -> List[Dict[str, float]]:
        """Generate random parameter suggestions."""
        suggestions = []

        for _ in range(n):
            suggestion = self._random_suggestion()
            suggestions.append(suggestion)

        return suggestions

    def _random_suggestion(self) -> Dict[str, float]:
        """Generate single random suggestion."""
        suggestion = {}

        for param, (low, high) in self.parameter_bounds.items():
            suggestion[param] = np.random.uniform(low, high)

        return suggestion

    def _perturb_best(self, noise_scale: float = 0.1) -> Dict[str, float]:
        """Perturb best known parameters."""
        if self._best_params is None:
            return self._random_suggestion()

        suggestion = {}

        for param, (low, high) in self.parameter_bounds.items():
            current = self._best_params.get(param, (low + high) / 2)
            range_size = high - low

            # Add Gaussian noise
            noise = np.random.normal(0, noise_scale * range_size)
            new_value = np.clip(current + noise, low, high)
            suggestion[param] = new_value

        return suggestion

    def optimize(self,
                objective_fn: Optional[Callable] = None,
                max_iterations: int = 50,
                early_stopping: int = 10) -> OptimizationResult:
        """
        Run optimization loop.

        Args:
            objective_fn: Function to evaluate (if not using observations)
            max_iterations: Maximum iterations
            early_stopping: Stop if no improvement for this many iterations

        Returns:
            Optimization result
        """
        best_quality = self._best_quality
        best_params = self._best_params.copy() if self._best_params else None
        no_improvement = 0

        for i in range(max_iterations):
            # Get suggestion
            suggestions = self.suggest_parameters(n_suggestions=1)
            params = suggestions[0]

            # Evaluate
            if objective_fn:
                quality = objective_fn(params)
            else:
                # Use model-based prediction
                quality = self._predict_quality(params)

            # Update
            state = ProcessState(
                parameters=params,
                quality_metrics={self.objective: quality}
            )
            self.update(state)

            # Check for improvement
            if quality > best_quality:
                best_quality = quality
                best_params = params.copy()
                no_improvement = 0
            else:
                no_improvement += 1

            if no_improvement >= early_stopping:
                logger.info(f"Early stopping at iteration {i}")
                break

        improvement = best_quality - self._observations[0].quality_metrics.get(self.objective, 0)

        return OptimizationResult(
            optimal_parameters=best_params or {},
            predicted_quality=best_quality,
            confidence=self._estimate_confidence(),
            iterations=i + 1,
            improvement=improvement
        )

    def _predict_quality(self, params: Dict[str, float]) -> float:
        """Predict quality for given parameters using simple model."""
        if len(self._observations) < 3:
            return 0.5

        # Simple weighted nearest neighbor prediction
        predictions = []
        weights = []

        for obs in self._observations[-20:]:  # Use recent observations
            # Calculate distance
            dist = 0
            for param, value in params.items():
                if param in obs.parameters:
                    obs_val = obs.parameters[param]
                    low, high = self.parameter_bounds.get(param, (0, 1))
                    normalized_diff = (value - obs_val) / (high - low + 1e-10)
                    dist += normalized_diff ** 2
            dist = np.sqrt(dist)

            quality = obs.quality_metrics.get(self.objective, 0)
            weight = 1.0 / (dist + 0.01)

            predictions.append(quality)
            weights.append(weight)

        # Weighted average
        weights = np.array(weights)
        predictions = np.array(predictions)
        return np.average(predictions, weights=weights)

    def _estimate_confidence(self) -> float:
        """Estimate confidence in optimization result."""
        if len(self._observations) < 10:
            return 0.5

        # Based on quality variance
        qualities = [
            obs.quality_metrics.get(self.objective, 0)
            for obs in self._observations[-20:]
        ]

        mean_q = np.mean(qualities)
        std_q = np.std(qualities)

        # Lower variance = higher confidence
        cv = std_q / (mean_q + 1e-10)
        confidence = max(0, 1 - cv)

        return min(confidence, 0.95)

    def get_pareto_front(self,
                        objectives: List[str],
                        maximize: Optional[List[bool]] = None) -> List[ProcessState]:
        """
        Get Pareto-optimal states for multi-objective optimization.

        Args:
            objectives: Objectives to consider
            maximize: Whether to maximize each objective

        Returns:
            Pareto-optimal states
        """
        if not self._observations:
            return []

        if maximize is None:
            maximize = [True] * len(objectives)

        # Extract objective values
        points = []
        for obs in self._observations:
            values = []
            for obj, max_obj in zip(objectives, maximize):
                val = obs.quality_metrics.get(obj, 0)
                if not max_obj:
                    val = -val
                values.append(val)
            points.append(values)

        points = np.array(points)

        # Find Pareto front
        pareto_mask = np.ones(len(points), dtype=bool)

        for i in range(len(points)):
            for j in range(len(points)):
                if i == j:
                    continue
                # Check if j dominates i
                if np.all(points[j] >= points[i]) and np.any(points[j] > points[i]):
                    pareto_mask[i] = False
                    break

        return [self._observations[i] for i in range(len(self._observations)) if pareto_mask[i]]

    def get_best_parameters(self) -> Optional[Dict[str, float]]:
        """Get best known parameters."""
        return self._best_params.copy() if self._best_params else None

    def get_statistics(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        if not self._observations:
            return {'n_observations': 0}

        qualities = [
            obs.quality_metrics.get(self.objective, 0)
            for obs in self._observations
        ]

        return {
            'n_observations': len(self._observations),
            'best_quality': self._best_quality,
            'mean_quality': np.mean(qualities),
            'std_quality': np.std(qualities),
            'best_parameters': self._best_params,
            'improvement_trend': qualities[-1] - qualities[0] if len(qualities) > 1 else 0
        }
