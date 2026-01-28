"""
Physics Loss Functions for PINN Training

Implements physics-based loss terms for training.
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from enum import Enum


class LossType(Enum):
    """Types of loss functions."""
    MSE = "mse"
    MAE = "mae"
    HUBER = "huber"
    LOG_COSH = "log_cosh"


@dataclass
class LossWeight:
    """Adaptive loss weight with scheduling."""
    initial: float = 1.0
    final: float = 1.0
    schedule: str = "constant"  # constant, linear, exponential
    warmup_steps: int = 0


class PhysicsLossFunction:
    """
    Physics-constrained loss function for PINN training.

    Combines:
    - Data fitting loss (MSE on observations)
    - Physics residual loss (PDE/ODE satisfaction)
    - Boundary condition loss
    - Regularization terms

    Total Loss = λ_data * L_data + λ_physics * L_physics + λ_bc * L_bc

    Features:
    - Adaptive loss weighting (gradient normalization)
    - Multi-task learning balancing
    - Curriculum learning for physics
    """

    def __init__(
        self,
        loss_type: LossType = LossType.MSE,
        weights: Optional[Dict[str, LossWeight]] = None
    ):
        """
        Initialize physics loss function.

        Args:
            loss_type: Base loss type
            weights: Loss term weights
        """
        self.loss_type = loss_type
        self.weights = weights or {}
        self.step = 0

        # Default weights
        self._default_weights = {
            "data": LossWeight(initial=1.0),
            "physics": LossWeight(initial=0.1, final=1.0, schedule="linear", warmup_steps=1000),
            "boundary": LossWeight(initial=1.0),
            "initial": LossWeight(initial=10.0),
            "regularization": LossWeight(initial=0.01)
        }

    def compute(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        physics_residuals: Dict[str, np.ndarray],
        bc_residuals: Optional[Dict[str, np.ndarray]] = None
    ) -> Dict[str, float]:
        """
        Compute total loss with breakdown.

        Args:
            y_pred: Predicted values
            y_true: True values
            physics_residuals: Dictionary of physics residuals
            bc_residuals: Optional boundary condition residuals

        Returns:
            Dictionary with loss values
        """
        losses = {}

        # Data loss
        data_weight = self._get_weight("data")
        losses["data"] = data_weight * self._base_loss(y_pred, y_true)

        # Physics losses
        physics_weight = self._get_weight("physics")
        for name, residual in physics_residuals.items():
            residual_loss = float(np.mean(residual ** 2))
            losses[f"physics_{name}"] = physics_weight * residual_loss

        # Boundary condition losses
        if bc_residuals:
            bc_weight = self._get_weight("boundary")
            for name, residual in bc_residuals.items():
                bc_loss = float(np.mean(residual ** 2))
                losses[f"bc_{name}"] = bc_weight * bc_loss

        # Total
        losses["total"] = sum(losses.values())

        self.step += 1
        return losses

    def _base_loss(self, y_pred: np.ndarray, y_true: np.ndarray) -> float:
        """Compute base loss between predictions and targets."""
        if self.loss_type == LossType.MSE:
            return float(np.mean((y_pred - y_true) ** 2))
        elif self.loss_type == LossType.MAE:
            return float(np.mean(np.abs(y_pred - y_true)))
        elif self.loss_type == LossType.HUBER:
            delta = 1.0
            error = np.abs(y_pred - y_true)
            quadratic = np.minimum(error, delta)
            linear = error - quadratic
            return float(np.mean(0.5 * quadratic ** 2 + delta * linear))
        elif self.loss_type == LossType.LOG_COSH:
            return float(np.mean(np.log(np.cosh(y_pred - y_true))))
        else:
            return float(np.mean((y_pred - y_true) ** 2))

    def _get_weight(self, name: str) -> float:
        """Get current weight value with scheduling."""
        if name in self.weights:
            weight_config = self.weights[name]
        elif name in self._default_weights:
            weight_config = self._default_weights[name]
        else:
            return 1.0

        if weight_config.schedule == "constant":
            return weight_config.initial
        elif weight_config.schedule == "linear":
            progress = min(1.0, self.step / max(1, weight_config.warmup_steps))
            return weight_config.initial + progress * (weight_config.final - weight_config.initial)
        elif weight_config.schedule == "exponential":
            progress = min(1.0, self.step / max(1, weight_config.warmup_steps))
            return weight_config.initial * (weight_config.final / weight_config.initial) ** progress
        else:
            return weight_config.initial
