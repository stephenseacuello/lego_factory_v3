"""
Bayesian Optimizer - Gaussian Process Based Optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides sample-efficient optimization using Gaussian Process surrogate models.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from enum import Enum
import random
import math
import logging
import uuid

logger = logging.getLogger(__name__)


class AcquisitionFunction(Enum):
    """Acquisition function type."""
    EXPECTED_IMPROVEMENT = "ei"
    PROBABILITY_OF_IMPROVEMENT = "pi"
    UPPER_CONFIDENCE_BOUND = "ucb"
    THOMPSON_SAMPLING = "ts"


@dataclass
class Observation:
    """An observation (sample) in the optimization process."""
    observation_id: str
    x: List[float]
    y: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "observation_id": self.observation_id,
            "x": self.x,
            "y": self.y,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SurrogateModel:
    """Simple Gaussian Process surrogate model."""
    observations: List[Observation]
    length_scale: float = 1.0
    signal_variance: float = 1.0
    noise_variance: float = 0.01

    def kernel(self, x1: List[float], x2: List[float]) -> float:
        """RBF kernel function."""
        distance_sq = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return self.signal_variance * math.exp(-distance_sq / (2 * self.length_scale ** 2))

    def predict(self, x: List[float]) -> Tuple[float, float]:
        """Predict mean and variance at point x."""
        if not self.observations:
            return 0.0, self.signal_variance

        n = len(self.observations)

        # Compute kernel vectors
        k_star = [self.kernel(x, obs.x) for obs in self.observations]

        # Compute kernel matrix (with noise)
        K = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                K[i][j] = self.kernel(
                    self.observations[i].x,
                    self.observations[j].x
                )
                if i == j:
                    K[i][j] += self.noise_variance

        # Simple matrix inversion (for small matrices)
        try:
            K_inv = self._invert_matrix(K)
        except Exception:
            return 0.0, self.signal_variance

        # Compute mean
        y = [obs.y for obs in self.observations]
        k_K_inv = self._matrix_vector_multiply(k_star, K_inv)
        mean = sum(a * b for a, b in zip(k_K_inv, y))

        # Compute variance
        k_star_star = self.kernel(x, x)
        variance = k_star_star - sum(
            k_K_inv[i] * k_star[i] for i in range(n)
        )
        variance = max(0.0, variance)

        return mean, variance

    def _invert_matrix(self, M: List[List[float]]) -> List[List[float]]:
        """Simple matrix inversion using Gauss-Jordan elimination."""
        n = len(M)
        # Create augmented matrix [M | I]
        aug = [row + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]

        # Forward elimination
        for i in range(n):
            # Find pivot
            max_row = max(range(i, n), key=lambda r: abs(aug[r][i]))
            aug[i], aug[max_row] = aug[max_row], aug[i]

            pivot = aug[i][i]
            if abs(pivot) < 1e-10:
                raise ValueError("Singular matrix")

            # Scale row
            for j in range(2 * n):
                aug[i][j] /= pivot

            # Eliminate column
            for k in range(n):
                if k != i:
                    factor = aug[k][i]
                    for j in range(2 * n):
                        aug[k][j] -= factor * aug[i][j]

        # Extract inverse
        return [row[n:] for row in aug]

    def _matrix_vector_multiply(
        self,
        v: List[float],
        M: List[List[float]],
    ) -> List[float]:
        """Multiply vector by matrix (v @ M)."""
        n = len(M)
        result = [0.0] * n
        for j in range(n):
            for i in range(n):
                result[j] += v[i] * M[i][j]
        return result


class BayesianOptimizer:
    """
    Bayesian Optimizer using Gaussian Process.

    Features:
    - Sample-efficient optimization
    - Multiple acquisition functions
    - Prior knowledge incorporation
    - Uncertainty quantification
    - Hyperparameter tuning
    """

    def __init__(
        self,
        bounds: List[Tuple[float, float]],
        objective_function: Callable[[List[float]], float],
        acquisition: AcquisitionFunction = AcquisitionFunction.EXPECTED_IMPROVEMENT,
        n_initial_points: int = 5,
        exploration_weight: float = 2.0,
    ):
        self.bounds = bounds
        self.objective_function = objective_function
        self.acquisition = acquisition
        self.n_initial_points = n_initial_points
        self.exploration_weight = exploration_weight

        self.observations: List[Observation] = []
        self.surrogate = SurrogateModel(observations=[])
        self.best_observation: Optional[Observation] = None

    def suggest(self) -> List[float]:
        """Suggest next point to evaluate."""
        # Initial random sampling
        if len(self.observations) < self.n_initial_points:
            return self._random_sample()

        # Optimize acquisition function
        best_x = None
        best_acq = float('-inf')

        # Random search for acquisition optimization
        for _ in range(100):
            x = self._random_sample()
            acq = self._acquisition_value(x)

            if acq > best_acq:
                best_acq = acq
                best_x = x

        return best_x if best_x else self._random_sample()

    def _random_sample(self) -> List[float]:
        """Generate random sample within bounds."""
        return [random.uniform(low, high) for low, high in self.bounds]

    def _acquisition_value(self, x: List[float]) -> float:
        """Calculate acquisition function value."""
        mean, variance = self.surrogate.predict(x)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if self.acquisition == AcquisitionFunction.EXPECTED_IMPROVEMENT:
            return self._expected_improvement(mean, std)
        elif self.acquisition == AcquisitionFunction.PROBABILITY_OF_IMPROVEMENT:
            return self._probability_of_improvement(mean, std)
        elif self.acquisition == AcquisitionFunction.UPPER_CONFIDENCE_BOUND:
            return self._upper_confidence_bound(mean, std)
        else:
            return self._thompson_sampling(mean, std)

    def _expected_improvement(self, mean: float, std: float) -> float:
        """Expected Improvement acquisition function."""
        if std < 1e-10:
            return 0.0

        best_y = self.best_observation.y if self.best_observation else 0.0
        z = (mean - best_y) / std

        # Approximate normal CDF and PDF
        cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        pdf = math.exp(-z ** 2 / 2) / math.sqrt(2 * math.pi)

        ei = (mean - best_y) * cdf + std * pdf
        return ei

    def _probability_of_improvement(self, mean: float, std: float) -> float:
        """Probability of Improvement acquisition function."""
        if std < 1e-10:
            return 0.0

        best_y = self.best_observation.y if self.best_observation else 0.0
        z = (mean - best_y) / std

        # Approximate normal CDF
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def _upper_confidence_bound(self, mean: float, std: float) -> float:
        """Upper Confidence Bound acquisition function."""
        return mean + self.exploration_weight * std

    def _thompson_sampling(self, mean: float, std: float) -> float:
        """Thompson Sampling acquisition function."""
        return random.gauss(mean, std)

    def observe(self, x: List[float], y: float, metadata: Optional[Dict[str, Any]] = None):
        """Record an observation."""
        observation = Observation(
            observation_id=str(uuid.uuid4()),
            x=x,
            y=y,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        self.observations.append(observation)
        self.surrogate.observations = self.observations

        # Update best
        if self.best_observation is None or y > self.best_observation.y:
            self.best_observation = observation

        logger.debug(f"Observed y={y:.4f} at x={x}")

    def optimize(
        self,
        n_iterations: int = 20,
        callback: Optional[Callable[[Observation], bool]] = None,
    ) -> Dict[str, Any]:
        """Run Bayesian optimization."""
        logger.info(f"Starting Bayesian optimization with {n_iterations} iterations")

        for i in range(n_iterations):
            # Suggest next point
            x = self.suggest()

            # Evaluate objective
            y = self.objective_function(x)

            # Record observation
            self.observe(x, y, {"iteration": i})

            # Callback for early stopping
            if callback and callback(self.observations[-1]):
                logger.info(f"Early stopping at iteration {i}")
                break

            if i % 5 == 0:
                logger.info(
                    f"Iteration {i}: best_y={self.best_observation.y:.4f}"
                )

        result = {
            "best_x": self.best_observation.x if self.best_observation else None,
            "best_y": self.best_observation.y if self.best_observation else None,
            "n_iterations": len(self.observations),
            "observations": [obs.to_dict() for obs in self.observations],
        }

        logger.info(f"Optimization complete. Best y={result['best_y']:.4f}")
        return result

    def get_posterior(
        self,
        n_points: int = 50,
    ) -> Dict[str, Any]:
        """Get posterior mean and variance across the search space."""
        if len(self.bounds) != 1:
            # Only support 1D for visualization
            return {"error": "Posterior visualization only supports 1D"}

        low, high = self.bounds[0]
        step = (high - low) / (n_points - 1)

        points = []
        means = []
        stds = []

        for i in range(n_points):
            x = [low + i * step]
            mean, variance = self.surrogate.predict(x)
            points.append(x[0])
            means.append(mean)
            stds.append(math.sqrt(max(0, variance)))

        return {
            "points": points,
            "means": means,
            "stds": stds,
            "observations": [(obs.x[0], obs.y) for obs in self.observations],
        }


class HyperparameterTuner:
    """
    Hyperparameter tuning using Bayesian optimization.

    Convenience wrapper for ML model hyperparameter tuning.
    """

    def __init__(
        self,
        param_space: Dict[str, Tuple[float, float]],
        objective_function: Callable[[Dict[str, float]], float],
    ):
        self.param_space = param_space
        self.param_names = list(param_space.keys())
        self.objective_function = objective_function

        # Convert to bounds list
        bounds = [param_space[name] for name in self.param_names]

        # Wrapper function
        def objective_wrapper(x: List[float]) -> float:
            params = dict(zip(self.param_names, x))
            return objective_function(params)

        self.optimizer = BayesianOptimizer(
            bounds=bounds,
            objective_function=objective_wrapper,
            acquisition=AcquisitionFunction.EXPECTED_IMPROVEMENT,
        )

    def tune(self, n_trials: int = 20) -> Dict[str, Any]:
        """Run hyperparameter tuning."""
        result = self.optimizer.optimize(n_iterations=n_trials)

        if result["best_x"]:
            best_params = dict(zip(self.param_names, result["best_x"]))
        else:
            best_params = None

        return {
            "best_params": best_params,
            "best_score": result["best_y"],
            "n_trials": result["n_iterations"],
            "trials": [
                {
                    "params": dict(zip(self.param_names, obs["x"])),
                    "score": obs["y"],
                }
                for obs in result["observations"]
            ],
        }
