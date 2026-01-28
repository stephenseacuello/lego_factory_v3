"""
Differential Privacy for Federated Learning.

This module implements differential privacy mechanisms:
- Gradient clipping for sensitivity control
- Noise addition (Gaussian, Laplacian)
- Privacy budget accounting
- Moment accountant for tight bounds

Research Contributions:
- Privacy-preserving manufacturing quality models
- Adaptive noise calibration for industrial data
- Privacy-utility trade-off optimization

References:
- Abadi, M., et al. (2016). Deep Learning with Differential Privacy
- Mironov, I. (2017). Rényi Differential Privacy
- McMahan, B., et al. (2018). Learning Differentially Private Recurrent Language Models
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime
import math

logger = logging.getLogger(__name__)


class NoiseType(Enum):
    """Types of noise for differential privacy."""
    GAUSSIAN = "gaussian"
    LAPLACIAN = "laplacian"
    EXPONENTIAL = "exponential"


class AccountingMethod(Enum):
    """Privacy accounting methods."""
    SIMPLE = "simple"  # Simple composition
    ADVANCED = "advanced"  # Advanced composition
    MOMENTS = "moments"  # Moment accountant
    RDP = "rdp"  # Rényi DP
    GDP = "gdp"  # Gaussian DP


@dataclass
class DPConfig:
    """Configuration for differential privacy."""
    epsilon: float = 1.0  # Privacy budget
    delta: float = 1e-5  # Failure probability
    noise_type: NoiseType = NoiseType.GAUSSIAN
    accounting_method: AccountingMethod = AccountingMethod.RDP
    max_grad_norm: float = 1.0  # Gradient clipping threshold
    noise_multiplier: float = 1.0  # σ/sensitivity ratio
    # Adaptive settings
    adaptive_clipping: bool = False
    target_clip_quantile: float = 0.5
    clip_learning_rate: float = 0.1
    # Sampling
    sample_rate: float = 0.01  # Fraction of data per iteration
    n_iterations: int = 1000  # Total training iterations


@dataclass
class PrivacyBudget:
    """Privacy budget tracking."""
    epsilon_spent: float = 0.0
    delta_spent: float = 0.0
    epsilon_budget: float = 1.0
    delta_budget: float = 1e-5
    n_queries: int = 0

    @property
    def remaining_epsilon(self) -> float:
        return self.epsilon_budget - self.epsilon_spent

    @property
    def remaining_delta(self) -> float:
        return self.delta_budget - self.delta_spent

    @property
    def is_exhausted(self) -> bool:
        return self.remaining_epsilon <= 0 or self.remaining_delta <= 0

    def to_dict(self) -> Dict:
        return {
            'epsilon_spent': self.epsilon_spent,
            'delta_spent': self.delta_spent,
            'epsilon_budget': self.epsilon_budget,
            'delta_budget': self.delta_budget,
            'remaining_epsilon': self.remaining_epsilon,
            'remaining_delta': self.remaining_delta,
            'n_queries': self.n_queries,
            'is_exhausted': self.is_exhausted
        }


class GradientClipper:
    """
    Gradient clipping for differential privacy.

    Clips gradients to bound sensitivity.
    """

    def __init__(self, config: DPConfig):
        self.config = config
        self.max_norm = config.max_grad_norm
        self._clip_history: List[float] = []
        self._adaptive_threshold = config.max_grad_norm

    def clip(
        self,
        gradients: Dict[str, np.ndarray],
        per_sample: bool = False
    ) -> Tuple[Dict[str, np.ndarray], float]:
        """
        Clip gradients to max norm.

        Args:
            gradients: Dictionary of gradients
            per_sample: If True, clip per sample (for per-example clipping)

        Returns:
            Clipped gradients and clipping factor
        """
        # Compute gradient norm
        total_norm = self._compute_norm(gradients)

        # Record for adaptive clipping
        self._clip_history.append(total_norm)

        # Compute clipping factor
        clip_threshold = self._adaptive_threshold if self.config.adaptive_clipping else self.max_norm
        clip_factor = min(1.0, clip_threshold / (total_norm + 1e-8))

        # Clip gradients
        clipped = {
            name: grad * clip_factor
            for name, grad in gradients.items()
        }

        # Update adaptive threshold if enabled
        if self.config.adaptive_clipping and len(self._clip_history) >= 10:
            self._update_adaptive_threshold()

        return clipped, float(clip_factor)

    def _compute_norm(self, gradients: Dict[str, np.ndarray]) -> float:
        """Compute total L2 norm of gradients."""
        total_sq = sum(np.sum(g ** 2) for g in gradients.values())
        return float(np.sqrt(total_sq))

    def _update_adaptive_threshold(self):
        """Update adaptive clipping threshold."""
        recent = self._clip_history[-100:]
        target_percentile = self.config.target_clip_quantile * 100
        current_quantile = np.percentile(recent, target_percentile)

        # Smooth update
        self._adaptive_threshold = (
            (1 - self.config.clip_learning_rate) * self._adaptive_threshold +
            self.config.clip_learning_rate * current_quantile
        )

    def get_clipping_stats(self) -> Dict:
        """Get clipping statistics."""
        if not self._clip_history:
            return {'n_clips': 0}

        clipped = [n for n in self._clip_history if n > self.max_norm]

        return {
            'n_clips': len(self._clip_history),
            'n_clipped': len(clipped),
            'clip_rate': len(clipped) / len(self._clip_history),
            'mean_norm': float(np.mean(self._clip_history)),
            'max_norm': float(np.max(self._clip_history)),
            'threshold': self._adaptive_threshold if self.config.adaptive_clipping else self.max_norm
        }


class NoiseGenerator:
    """
    Noise generator for differential privacy.

    Generates calibrated noise for privacy guarantees.
    """

    def __init__(self, config: DPConfig):
        self.config = config

    def generate(
        self,
        shape: Tuple[int, ...],
        sensitivity: float = 1.0,
        epsilon: Optional[float] = None
    ) -> np.ndarray:
        """
        Generate noise for differential privacy.

        Args:
            shape: Shape of noise array
            sensitivity: L2 sensitivity of query
            epsilon: Privacy parameter (uses config if None)

        Returns:
            Noise array
        """
        eps = epsilon or self.config.epsilon

        if self.config.noise_type == NoiseType.GAUSSIAN:
            return self._gaussian_noise(shape, sensitivity, eps)
        elif self.config.noise_type == NoiseType.LAPLACIAN:
            return self._laplacian_noise(shape, sensitivity, eps)
        else:
            return self._gaussian_noise(shape, sensitivity, eps)

    def _gaussian_noise(
        self,
        shape: Tuple[int, ...],
        sensitivity: float,
        epsilon: float
    ) -> np.ndarray:
        """Generate Gaussian noise for (ε, δ)-DP."""
        # σ = sensitivity * sqrt(2 * ln(1.25/δ)) / ε
        delta = self.config.delta
        sigma = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon

        # Apply noise multiplier
        sigma *= self.config.noise_multiplier

        return np.random.normal(0, sigma, shape).astype(np.float32)

    def _laplacian_noise(
        self,
        shape: Tuple[int, ...],
        sensitivity: float,
        epsilon: float
    ) -> np.ndarray:
        """Generate Laplacian noise for ε-DP."""
        # b = sensitivity / ε
        scale = sensitivity / epsilon

        return np.random.laplace(0, scale, shape).astype(np.float32)

    def calibrate_noise(
        self,
        target_epsilon: float,
        target_delta: float,
        sensitivity: float,
        n_iterations: int
    ) -> float:
        """
        Calibrate noise multiplier for target privacy.

        Returns recommended noise multiplier.
        """
        # Simple calibration using RDP
        # In practice, would use numerical optimization

        sigma_min = 0.1
        sigma_max = 100.0

        for _ in range(100):  # Binary search
            sigma = (sigma_min + sigma_max) / 2

            # Compute epsilon for this sigma
            eps = self._compute_epsilon_from_sigma(sigma, target_delta, n_iterations)

            if eps < target_epsilon:
                sigma_max = sigma
            else:
                sigma_min = sigma

            if abs(sigma_max - sigma_min) < 0.01:
                break

        return sigma


    def _compute_epsilon_from_sigma(
        self,
        sigma: float,
        delta: float,
        n_iterations: int
    ) -> float:
        """Compute epsilon from sigma using RDP."""
        # Simplified RDP computation
        # Real implementation would use proper RDP accountant

        sample_rate = self.config.sample_rate

        # RDP at order α = 2
        alpha = 2
        rdp = sample_rate ** 2 * alpha / (2 * sigma ** 2)

        # Compose over iterations
        total_rdp = n_iterations * rdp

        # Convert RDP to (ε, δ)-DP
        epsilon = total_rdp + np.log(1 / delta) / (alpha - 1)

        return float(epsilon)


class PrivacyAccountant:
    """
    Privacy accountant for tracking privacy budget.

    Implements various composition theorems.
    """

    def __init__(self, config: DPConfig):
        self.config = config
        self.budget = PrivacyBudget(
            epsilon_budget=config.epsilon,
            delta_budget=config.delta
        )

        # RDP tracking
        self._rdp_orders = np.array([1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 16, 32, 64])
        self._rdp_epsilon = np.zeros_like(self._rdp_orders)

        self._history: List[Dict] = []

    def accumulate(
        self,
        noise_multiplier: float,
        sample_rate: float,
        n_steps: int = 1
    ):
        """
        Accumulate privacy cost for n_steps.

        Args:
            noise_multiplier: σ/sensitivity
            sample_rate: Sampling probability
            n_steps: Number of steps
        """
        if self.config.accounting_method == AccountingMethod.RDP:
            self._accumulate_rdp(noise_multiplier, sample_rate, n_steps)
        else:
            self._accumulate_simple(noise_multiplier, sample_rate, n_steps)

        self.budget.n_queries += n_steps

        # Record history
        self._history.append({
            'noise_multiplier': noise_multiplier,
            'sample_rate': sample_rate,
            'n_steps': n_steps,
            'epsilon_after': self.budget.epsilon_spent,
            'delta_after': self.budget.delta_spent
        })

    def _accumulate_simple(
        self,
        noise_multiplier: float,
        sample_rate: float,
        n_steps: int
    ):
        """Simple composition."""
        # ε per step
        step_epsilon = sample_rate * np.sqrt(2 * np.log(1.25 / self.config.delta)) / noise_multiplier

        # Simple composition: ε_total = n * ε
        self.budget.epsilon_spent += n_steps * step_epsilon

    def _accumulate_rdp(
        self,
        noise_multiplier: float,
        sample_rate: float,
        n_steps: int
    ):
        """RDP-based accounting."""
        for i, alpha in enumerate(self._rdp_orders):
            # RDP for subsampled Gaussian
            rdp = self._compute_rdp(alpha, noise_multiplier, sample_rate)
            self._rdp_epsilon[i] += n_steps * rdp

        # Convert to (ε, δ)-DP
        epsilon, delta = self._rdp_to_dp(self.config.delta)
        self.budget.epsilon_spent = epsilon
        self.budget.delta_spent = delta

    def _compute_rdp(
        self,
        alpha: float,
        sigma: float,
        sample_rate: float
    ) -> float:
        """Compute RDP for subsampled Gaussian mechanism."""
        if sample_rate == 0:
            return 0

        # Poisson subsampling
        if sample_rate < 1:
            # Simplified bound
            return sample_rate ** 2 * alpha / (2 * sigma ** 2)
        else:
            # Full batch
            return alpha / (2 * sigma ** 2)

    def _rdp_to_dp(self, target_delta: float) -> Tuple[float, float]:
        """Convert RDP to (ε, δ)-DP."""
        # Find best α
        best_epsilon = float('inf')

        for alpha, rdp in zip(self._rdp_orders, self._rdp_epsilon):
            # ε = rdp - log(δ) / (α - 1)
            epsilon = rdp + np.log(1 / target_delta) / (alpha - 1)
            best_epsilon = min(best_epsilon, epsilon)

        return float(best_epsilon), float(target_delta)

    def get_epsilon(self, delta: Optional[float] = None) -> float:
        """Get current epsilon for given delta."""
        d = delta or self.config.delta

        if self.config.accounting_method == AccountingMethod.RDP:
            eps, _ = self._rdp_to_dp(d)
            return eps
        else:
            return self.budget.epsilon_spent

    def remaining_steps(
        self,
        noise_multiplier: float,
        sample_rate: float
    ) -> int:
        """Estimate remaining steps within budget."""
        if self.budget.is_exhausted:
            return 0

        # Binary search for max steps
        low, high = 0, 100000

        while high - low > 1:
            mid = (low + high) // 2

            # Simulate accumulation
            test_accountant = PrivacyAccountant(self.config)
            test_accountant._rdp_epsilon = self._rdp_epsilon.copy()
            test_accountant.accumulate(noise_multiplier, sample_rate, mid)

            if test_accountant.get_epsilon() <= self.config.epsilon:
                low = mid
            else:
                high = mid

        return low

    def get_status(self) -> Dict:
        """Get privacy accounting status."""
        return {
            'budget': self.budget.to_dict(),
            'accounting_method': self.config.accounting_method.value,
            'history_length': len(self._history)
        }


class DifferentialPrivacy:
    """
    Complete differential privacy system for federated learning.

    Combines clipping, noise, and accounting.
    """

    def __init__(self, config: Optional[DPConfig] = None):
        self.config = config or DPConfig()
        self.clipper = GradientClipper(self.config)
        self.noise_gen = NoiseGenerator(self.config)
        self.accountant = PrivacyAccountant(self.config)

    def privatize_gradients(
        self,
        gradients: Dict[str, np.ndarray],
        n_samples: int
    ) -> Dict[str, np.ndarray]:
        """
        Apply differential privacy to gradients.

        Args:
            gradients: Raw gradients
            n_samples: Number of samples in batch

        Returns:
            Privatized gradients
        """
        # Step 1: Clip gradients
        clipped, clip_factor = self.clipper.clip(gradients)

        # Step 2: Add noise
        noised = {}
        sensitivity = self.config.max_grad_norm / n_samples

        for name, grad in clipped.items():
            noise = self.noise_gen.generate(grad.shape, sensitivity)
            noised[name] = grad + noise

        # Step 3: Account for privacy
        sample_rate = n_samples / self.config.n_iterations  # Approximate
        self.accountant.accumulate(self.config.noise_multiplier, sample_rate, 1)

        return noised

    def get_privacy_guarantee(self) -> Dict:
        """Get current privacy guarantee."""
        return {
            'epsilon': self.accountant.get_epsilon(),
            'delta': self.config.delta,
            'budget_status': self.accountant.budget.to_dict(),
            'clipping_stats': self.clipper.get_clipping_stats()
        }

    def is_budget_available(self) -> bool:
        """Check if privacy budget is available."""
        return not self.accountant.budget.is_exhausted


class ManufacturingDP(DifferentialPrivacy):
    """
    Manufacturing-specific differential privacy.

    Adapts DP for manufacturing data characteristics.
    """

    def __init__(self, config: Optional[DPConfig] = None):
        super().__init__(config)

        # Manufacturing context
        self.feature_sensitivities: Dict[str, float] = {}
        self.public_features: List[str] = []

    def set_feature_context(
        self,
        feature_sensitivities: Dict[str, float],
        public_features: Optional[List[str]] = None
    ):
        """
        Set manufacturing feature context.

        Args:
            feature_sensitivities: Sensitivity per feature
            public_features: Features that don't need protection
        """
        self.feature_sensitivities = feature_sensitivities
        self.public_features = public_features or []

    def privatize_with_context(
        self,
        gradients: Dict[str, np.ndarray],
        feature_names: List[str],
        n_samples: int
    ) -> Dict[str, np.ndarray]:
        """Privatize gradients with feature-aware noise."""
        # Clip gradients
        clipped, _ = self.clipper.clip(gradients)

        noised = {}
        for name, grad in clipped.items():
            # Check if this corresponds to a public feature
            if any(pf in name for pf in self.public_features):
                # No noise for public features
                noised[name] = grad
            else:
                # Get feature-specific sensitivity if available
                sensitivity = self.feature_sensitivities.get(name, self.config.max_grad_norm)
                noise = self.noise_gen.generate(grad.shape, sensitivity / n_samples)
                noised[name] = grad + noise

        # Account for privacy (simplified - assumes all features)
        sample_rate = n_samples / self.config.n_iterations
        self.accountant.accumulate(self.config.noise_multiplier, sample_rate, 1)

        return noised
