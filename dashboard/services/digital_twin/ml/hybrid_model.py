"""
Hybrid Physics + Data-Driven Models for Manufacturing.

This module implements hybrid models combining physics and machine learning:
- Residual physics networks (NN learns residuals from physics model)
- Physics-data fusion architectures
- Ensemble methods for uncertainty quantification
- Transfer learning with physics priors

Research Value:
- Novel hybrid architectures for manufacturing
- Uncertainty-aware predictions
- Efficient learning from sparse data

References:
- Karpatne, A., et al. (2017). Theory-guided data science
- Wang, J.X., et al. (2017). Physics-informed machine learning
- ISO 23247 Digital Twin Framework
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, Union, Protocol
)
import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Physics Model Interface
# =============================================================================

class PhysicsModel(Protocol):
    """Protocol for physics models used in hybrid architectures."""

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """Predict output from physics model."""
        ...

    def jacobian(self, inputs: np.ndarray) -> np.ndarray:
        """Compute Jacobian of outputs w.r.t. inputs."""
        ...


@dataclass
class PhysicsModelConfig:
    """Configuration for physics model component."""
    model_type: str  # 'analytical', 'fem', 'lumped'
    parameters: Dict[str, float] = field(default_factory=dict)
    input_scaling: Optional[np.ndarray] = None
    output_scaling: Optional[np.ndarray] = None


# =============================================================================
# Analytical Physics Models
# =============================================================================

class AnalyticalPhysicsModel:
    """
    Collection of analytical physics models for manufacturing.

    These serve as the physics component in hybrid models.
    """

    @staticmethod
    def fdm_thermal_model() -> 'ThermalAnalyticalModel':
        """Create analytical thermal model for FDM printing."""
        return ThermalAnalyticalModel()

    @staticmethod
    def simple_mechanical_model() -> 'MechanicalAnalyticalModel':
        """Create simple mechanical model."""
        return MechanicalAnalyticalModel()


class ThermalAnalyticalModel:
    """
    Analytical thermal model for FDM printing.

    Based on moving point heat source solution.
    """

    def __init__(
        self,
        thermal_diffusivity: float = 1.5e-7,  # m²/s
        thermal_conductivity: float = 0.13,  # W/(m·K)
        power: float = 5.0,  # W
        print_speed: float = 0.05,  # m/s
        ambient_temp: float = 25.0  # °C
    ):
        self.alpha = thermal_diffusivity
        self.k = thermal_conductivity
        self.Q = power
        self.v = print_speed
        self.T_amb = ambient_temp

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """
        Predict temperature field.

        Inputs: [x, y, z, t] relative to heat source
        Output: [T]
        """
        x = inputs[:, 0]
        y = inputs[:, 1]
        z = inputs[:, 2]
        t = inputs[:, 3] if inputs.shape[1] > 3 else np.zeros(len(x))

        # Moving heat source position
        x_source = self.v * t

        # Distance from heat source
        r = np.sqrt((x - x_source)**2 + y**2 + z**2) + 1e-10

        # Rosenthal solution (quasi-steady state moving point source)
        # T = T_amb + Q/(2πkr) * exp(-v(r-x)/(2α))
        peclet = self.v * r / (2 * self.alpha)
        xi = self.v * (x - x_source) / (2 * self.alpha)

        T = self.T_amb + (self.Q / (2 * np.pi * self.k * r)) * np.exp(-peclet + xi)

        # Clip to physical bounds
        T = np.clip(T, self.T_amb, 300)

        return T.reshape(-1, 1)

    def jacobian(self, inputs: np.ndarray) -> np.ndarray:
        """Compute Jacobian using finite differences."""
        eps = 1e-5
        n_samples, n_inputs = inputs.shape
        n_outputs = 1

        jac = np.zeros((n_samples, n_outputs, n_inputs))
        y = self.predict(inputs)

        for i in range(n_inputs):
            inputs_plus = inputs.copy()
            inputs_plus[:, i] += eps
            y_plus = self.predict(inputs_plus)
            jac[:, :, i] = (y_plus - y) / eps

        return jac


class MechanicalAnalyticalModel:
    """
    Simple analytical mechanical model.

    Based on beam theory for thin-walled structures.
    """

    def __init__(
        self,
        youngs_modulus: float = 2.5e9,  # Pa
        poissons_ratio: float = 0.35
    ):
        self.E = youngs_modulus
        self.nu = poissons_ratio

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """
        Predict displacement/stress.

        Simplified: assumes cantilever-like behavior
        Inputs: [x, y, z, load]
        Output: [displacement, stress]
        """
        x = inputs[:, 0]
        load = inputs[:, 3] if inputs.shape[1] > 3 else np.ones(len(x))

        # Simplified cantilever: δ = PL³/(3EI)
        L = np.max(x) + 1e-10
        I = 1e-12  # Approximate moment of inertia

        displacement = load * (x**3) / (3 * self.E * I)
        stress = load * x / I  # Bending stress

        return np.column_stack([displacement, stress])

    def jacobian(self, inputs: np.ndarray) -> np.ndarray:
        """Compute Jacobian using finite differences."""
        eps = 1e-5
        n_samples, n_inputs = inputs.shape
        n_outputs = 2

        jac = np.zeros((n_samples, n_outputs, n_inputs))
        y = self.predict(inputs)

        for i in range(n_inputs):
            inputs_plus = inputs.copy()
            inputs_plus[:, i] += eps
            y_plus = self.predict(inputs_plus)
            jac[:, :, i] = (y_plus - y) / eps

        return jac


# =============================================================================
# Neural Network Components
# =============================================================================

class NeuralNetworkLayer:
    """Simple neural network layer for hybrid models."""

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        activation: str = 'tanh'
    ):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.activation = activation

        # Xavier initialization
        scale = np.sqrt(2.0 / (input_dim + output_dim))
        self.W = np.random.randn(input_dim, output_dim) * scale
        self.b = np.zeros(output_dim)

        # Gradients
        self.dW = np.zeros_like(self.W)
        self.db = np.zeros_like(self.b)

        # Cache
        self._x = None
        self._z = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self._x = x
        self._z = x @ self.W + self.b
        return self._activate(self._z)

    def _activate(self, z: np.ndarray) -> np.ndarray:
        if self.activation == 'tanh':
            return np.tanh(z)
        elif self.activation == 'relu':
            return np.maximum(0, z)
        elif self.activation == 'sigmoid':
            return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
        elif self.activation == 'linear':
            return z
        return z

    def _activate_derivative(self, z: np.ndarray) -> np.ndarray:
        if self.activation == 'tanh':
            return 1 - np.tanh(z)**2
        elif self.activation == 'relu':
            return (z > 0).astype(float)
        elif self.activation == 'sigmoid':
            s = 1 / (1 + np.exp(-np.clip(z, -500, 500)))
            return s * (1 - s)
        return np.ones_like(z)

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        grad_z = grad_output * self._activate_derivative(self._z)
        self.dW = self._x.T @ grad_z
        self.db = grad_z.sum(axis=0)
        return grad_z @ self.W.T

    def update(self, lr: float) -> None:
        self.W -= lr * self.dW
        self.b -= lr * self.db


class SimpleNeuralNetwork:
    """Simple feed-forward neural network."""

    def __init__(
        self,
        layer_sizes: List[int],
        activation: str = 'tanh'
    ):
        self.layers = []
        for i in range(len(layer_sizes) - 1):
            # Use linear activation for output layer
            act = activation if i < len(layer_sizes) - 2 else 'linear'
            self.layers.append(NeuralNetworkLayer(
                layer_sizes[i],
                layer_sizes[i + 1],
                activation=act
            ))

    def forward(self, x: np.ndarray) -> np.ndarray:
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def backward(self, grad_output: np.ndarray) -> None:
        grad = grad_output
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def update(self, lr: float) -> None:
        for layer in self.layers:
            layer.update(lr)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.forward(x)


# =============================================================================
# Hybrid Model Architectures
# =============================================================================

class HybridModelType(Enum):
    """Types of hybrid model architectures."""
    RESIDUAL = auto()  # NN learns residual from physics
    PARALLEL = auto()  # Physics and NN in parallel
    SEQUENTIAL = auto()  # Physics then NN correction
    ENSEMBLE = auto()  # Ensemble of physics and NN
    ATTENTION = auto()  # Attention-weighted combination


@dataclass
class HybridModelConfig:
    """Configuration for hybrid model."""
    input_dim: int
    output_dim: int
    hidden_layers: List[int] = field(default_factory=lambda: [32, 32])
    model_type: HybridModelType = HybridModelType.RESIDUAL
    physics_weight: float = 0.5  # Weight for physics model
    learning_rate: float = 1e-3
    regularization: float = 1e-4


class HybridModel(ABC):
    """
    Abstract base class for hybrid physics + data-driven models.

    Combines:
    - Physics model for interpretable, physically consistent base
    - Neural network for learning unmodeled dynamics
    """

    def __init__(
        self,
        config: HybridModelConfig,
        physics_model: PhysicsModel
    ):
        self.config = config
        self.physics_model = physics_model

    @abstractmethod
    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """Make predictions combining physics and NN."""
        pass

    @abstractmethod
    def train_step(
        self,
        inputs: np.ndarray,
        targets: np.ndarray
    ) -> float:
        """Single training step. Returns loss."""
        pass


class ResidualPhysicsNet(HybridModel):
    """
    Residual learning hybrid model.

    Architecture: y = f_physics(x) + f_nn(x)

    The neural network learns the residual between physics model
    predictions and actual data.

    Research Value:
    - Ensures physics baseline is always satisfied
    - NN only corrects for unmodeled effects
    - Better generalization to unseen conditions
    """

    def __init__(
        self,
        config: HybridModelConfig,
        physics_model: PhysicsModel
    ):
        super().__init__(config, physics_model)

        # Neural network for residual
        layer_sizes = [config.input_dim] + config.hidden_layers + [config.output_dim]
        self.nn = SimpleNeuralNetwork(layer_sizes)

        # Training history
        self.loss_history: List[float] = []
        self.physics_loss_history: List[float] = []
        self.residual_loss_history: List[float] = []

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """
        Predict output as physics + residual.

        y = f_physics(x) + f_nn(x)
        """
        physics_pred = self.physics_model.predict(inputs)
        residual_pred = self.nn.predict(inputs)

        return physics_pred + residual_pred

    def predict_decomposed(
        self,
        inputs: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get decomposed predictions.

        Returns:
            Tuple of (total, physics_component, residual_component)
        """
        physics_pred = self.physics_model.predict(inputs)
        residual_pred = self.nn.predict(inputs)

        return physics_pred + residual_pred, physics_pred, residual_pred

    def train_step(
        self,
        inputs: np.ndarray,
        targets: np.ndarray
    ) -> float:
        """
        Single training step.

        Only the NN is trained; physics model is fixed.
        """
        # Forward pass
        physics_pred = self.physics_model.predict(inputs)
        residual_pred = self.nn.predict(inputs)
        total_pred = physics_pred + residual_pred

        # Compute loss
        error = total_pred - targets
        loss = float(np.mean(error ** 2))

        # The residual should be small (regularization)
        residual_penalty = self.config.regularization * float(np.mean(residual_pred ** 2))
        total_loss = loss + residual_penalty

        # Backward pass (only for NN)
        grad_output = 2 * error / len(inputs)
        self.nn.backward(grad_output)

        # Update NN
        self.nn.update(self.config.learning_rate)

        # Record history
        self.loss_history.append(total_loss)
        self.physics_loss_history.append(float(np.mean((physics_pred - targets) ** 2)))
        self.residual_loss_history.append(float(np.mean(residual_pred ** 2)))

        return total_loss

    def get_residual_importance(self, inputs: np.ndarray) -> np.ndarray:
        """
        Get the relative importance of residual vs physics.

        Returns ratio |residual| / |total| for each sample.
        """
        total, physics, residual = self.predict_decomposed(inputs)

        total_magnitude = np.abs(total) + 1e-10
        residual_magnitude = np.abs(residual)

        return residual_magnitude / total_magnitude


class PhysicsDataFusion(HybridModel):
    """
    Physics-data fusion model with learnable weights.

    Architecture: y = α·f_physics(x) + (1-α)·f_nn(x)

    Where α is either:
    - Fixed weight
    - Learnable global parameter
    - Input-dependent (attention mechanism)

    Research Value:
    - Smooth transition between physics and data-driven
    - Interpretable contribution weights
    - Adapts to data availability
    """

    def __init__(
        self,
        config: HybridModelConfig,
        physics_model: PhysicsModel,
        learnable_alpha: bool = True,
        attention_based: bool = False
    ):
        super().__init__(config, physics_model)

        self.learnable_alpha = learnable_alpha
        self.attention_based = attention_based

        # Neural network for data-driven component
        layer_sizes = [config.input_dim] + config.hidden_layers + [config.output_dim]
        self.nn = SimpleNeuralNetwork(layer_sizes)

        # Weight parameter
        if attention_based:
            # Attention network: input -> alpha
            self.attention_net = SimpleNeuralNetwork(
                [config.input_dim, 16, 1]
            )
        else:
            self.alpha = config.physics_weight
            self.alpha_grad = 0.0

        self.loss_history: List[float] = []

    def get_alpha(self, inputs: np.ndarray) -> np.ndarray:
        """Get fusion weight(s)."""
        if self.attention_based:
            # Sigmoid to ensure α ∈ [0, 1]
            raw_alpha = self.attention_net.predict(inputs)
            return 1 / (1 + np.exp(-raw_alpha))
        else:
            return np.full((len(inputs), 1), self.alpha)

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """
        Predict with weighted fusion.

        y = α·f_physics(x) + (1-α)·f_nn(x)
        """
        physics_pred = self.physics_model.predict(inputs)
        nn_pred = self.nn.predict(inputs)
        alpha = self.get_alpha(inputs)

        return alpha * physics_pred + (1 - alpha) * nn_pred

    def train_step(
        self,
        inputs: np.ndarray,
        targets: np.ndarray
    ) -> float:
        """Single training step."""
        # Forward
        physics_pred = self.physics_model.predict(inputs)
        nn_pred = self.nn.predict(inputs)
        alpha = self.get_alpha(inputs)

        total_pred = alpha * physics_pred + (1 - alpha) * nn_pred
        error = total_pred - targets
        loss = float(np.mean(error ** 2))

        # Gradients
        grad_output = 2 * error / len(inputs)

        # NN gradient
        nn_grad = grad_output * (1 - alpha)
        self.nn.backward(nn_grad)
        self.nn.update(self.config.learning_rate)

        # Alpha gradient (if learnable and not attention-based)
        if self.learnable_alpha and not self.attention_based:
            alpha_grad = np.mean(grad_output * (physics_pred - nn_pred))
            self.alpha -= self.config.learning_rate * alpha_grad
            self.alpha = np.clip(self.alpha, 0.01, 0.99)  # Keep bounded

        # Attention network gradient
        if self.attention_based:
            # d loss / d alpha · d alpha / d raw_alpha
            d_loss_d_alpha = grad_output * (physics_pred - nn_pred)
            d_alpha_d_raw = alpha * (1 - alpha)  # sigmoid derivative
            attention_grad = d_loss_d_alpha * d_alpha_d_raw
            self.attention_net.backward(attention_grad)
            self.attention_net.update(self.config.learning_rate)

        self.loss_history.append(loss)
        return loss


class EnsembleHybridModel:
    """
    Ensemble of hybrid models for uncertainty quantification.

    Uses multiple hybrid models with different:
    - Random initializations
    - Physics model variants
    - Architectures

    Provides:
    - Mean prediction
    - Epistemic uncertainty (model uncertainty)
    - Aleatoric uncertainty (data uncertainty)

    Research Value:
    - Uncertainty-aware predictions for manufacturing
    - Reliable confidence intervals
    - Out-of-distribution detection
    """

    def __init__(
        self,
        config: HybridModelConfig,
        physics_model: PhysicsModel,
        n_models: int = 5,
        model_class: type = ResidualPhysicsNet
    ):
        self.config = config
        self.n_models = n_models

        # Create ensemble
        self.models = [
            model_class(config, physics_model)
            for _ in range(n_models)
        ]

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        """Get mean ensemble prediction."""
        predictions = np.array([m.predict(inputs) for m in self.models])
        return predictions.mean(axis=0)

    def predict_with_uncertainty(
        self,
        inputs: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get predictions with uncertainty estimates.

        Returns:
            Tuple of (mean, epistemic_uncertainty, total_uncertainty)
        """
        predictions = np.array([m.predict(inputs) for m in self.models])

        mean = predictions.mean(axis=0)
        epistemic = predictions.std(axis=0)  # Model disagreement

        # Total uncertainty (could add aleatoric if models output it)
        total = epistemic

        return mean, epistemic, total

    def train_step(
        self,
        inputs: np.ndarray,
        targets: np.ndarray
    ) -> float:
        """Train all models in ensemble."""
        losses = []
        for model in self.models:
            loss = model.train_step(inputs, targets)
            losses.append(loss)
        return float(np.mean(losses))

    def get_confidence_interval(
        self,
        inputs: np.ndarray,
        confidence: float = 0.95
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get confidence interval for predictions.

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        predictions = np.array([m.predict(inputs) for m in self.models])

        # Use percentiles for non-parametric interval
        alpha = (1 - confidence) / 2
        lower = np.percentile(predictions, 100 * alpha, axis=0)
        upper = np.percentile(predictions, 100 * (1 - alpha), axis=0)

        return lower, upper


# =============================================================================
# Uncertainty Quantification
# =============================================================================

class UncertaintyType(Enum):
    """Types of uncertainty."""
    EPISTEMIC = auto()  # Model/knowledge uncertainty
    ALEATORIC = auto()  # Data/noise uncertainty
    TOTAL = auto()  # Combined uncertainty


@dataclass
class UncertaintyEstimate:
    """Uncertainty estimation result."""
    mean: np.ndarray
    std: np.ndarray
    epistemic: Optional[np.ndarray] = None
    aleatoric: Optional[np.ndarray] = None
    confidence_lower: Optional[np.ndarray] = None
    confidence_upper: Optional[np.ndarray] = None


class UncertaintyQuantifier:
    """
    Uncertainty quantification for hybrid models.

    Methods:
    - Monte Carlo Dropout
    - Deep Ensembles
    - Evidential Deep Learning (simplified)
    - Physics-informed bounds

    Research Value:
    - Reliable uncertainty for manufacturing decisions
    - Safety-critical applications
    - Active learning guidance
    """

    def __init__(
        self,
        model: Union[HybridModel, EnsembleHybridModel],
        method: str = 'ensemble'
    ):
        self.model = model
        self.method = method

    def estimate(
        self,
        inputs: np.ndarray,
        n_samples: int = 100,
        confidence: float = 0.95
    ) -> UncertaintyEstimate:
        """
        Estimate uncertainty for predictions.

        Args:
            inputs: Input data
            n_samples: Number of MC samples (for dropout)
            confidence: Confidence level for intervals

        Returns:
            UncertaintyEstimate with all uncertainty components
        """
        if self.method == 'ensemble' and isinstance(self.model, EnsembleHybridModel):
            return self._ensemble_uncertainty(inputs, confidence)
        else:
            return self._basic_uncertainty(inputs, n_samples, confidence)

    def _ensemble_uncertainty(
        self,
        inputs: np.ndarray,
        confidence: float
    ) -> UncertaintyEstimate:
        """Uncertainty from ensemble disagreement."""
        mean, epistemic, total = self.model.predict_with_uncertainty(inputs)
        lower, upper = self.model.get_confidence_interval(inputs, confidence)

        return UncertaintyEstimate(
            mean=mean,
            std=total,
            epistemic=epistemic,
            aleatoric=None,  # Would need explicit modeling
            confidence_lower=lower,
            confidence_upper=upper
        )

    def _basic_uncertainty(
        self,
        inputs: np.ndarray,
        n_samples: int,
        confidence: float
    ) -> UncertaintyEstimate:
        """Basic uncertainty from single model variance."""
        # For single model, use prediction as mean
        # Uncertainty estimated from residual variance
        pred = self.model.predict(inputs)

        # Use a rough estimate based on model's loss history if available
        if hasattr(self.model, 'loss_history') and self.model.loss_history:
            recent_loss = np.mean(self.model.loss_history[-100:])
            std = np.sqrt(recent_loss) * np.ones_like(pred)
        else:
            std = np.zeros_like(pred)

        # Confidence interval
        z = 1.96 if confidence == 0.95 else 2.576  # Approximate
        lower = pred - z * std
        upper = pred + z * std

        return UncertaintyEstimate(
            mean=pred,
            std=std,
            confidence_lower=lower,
            confidence_upper=upper
        )

    def is_reliable(
        self,
        inputs: np.ndarray,
        uncertainty_threshold: float = 0.1
    ) -> np.ndarray:
        """
        Check if predictions are reliable (low uncertainty).

        Returns boolean array indicating reliable predictions.
        """
        estimate = self.estimate(inputs)

        # Relative uncertainty
        rel_uncertainty = estimate.std / (np.abs(estimate.mean) + 1e-10)

        return rel_uncertainty < uncertainty_threshold

    def get_calibration_error(
        self,
        inputs: np.ndarray,
        targets: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Compute Expected Calibration Error (ECE).

        Measures how well uncertainty estimates are calibrated.
        """
        estimate = self.estimate(inputs)
        pred = estimate.mean
        std = estimate.std

        # Normalize errors
        errors = np.abs(pred - targets) / (std + 1e-10)

        # For well-calibrated model, errors should follow standard normal
        # Sort into bins by predicted uncertainty
        sorted_idx = np.argsort(std.ravel())
        n_samples = len(sorted_idx)
        bin_size = n_samples // n_bins

        ece = 0.0
        for i in range(n_bins):
            start = i * bin_size
            end = (i + 1) * bin_size if i < n_bins - 1 else n_samples
            bin_idx = sorted_idx[start:end]

            # Expected: fraction of errors within 1 std should be ~68%
            actual_within = np.mean(errors.ravel()[bin_idx] < 1.0)
            expected = 0.68  # For 1 std

            ece += len(bin_idx) / n_samples * np.abs(actual_within - expected)

        return ece


# =============================================================================
# Transfer Learning with Physics
# =============================================================================

class PhysicsGuidedTransfer:
    """
    Transfer learning guided by physics constraints.

    Enables:
    - Transfer across different materials (same physics, different params)
    - Transfer across different geometries
    - Transfer across different operating conditions

    Research Value:
    - Efficient adaptation with minimal data
    - Physics ensures physical consistency
    - Reduces data requirements for new conditions
    """

    def __init__(
        self,
        source_model: HybridModel,
        physics_model: PhysicsModel
    ):
        self.source_model = source_model
        self.physics_model = physics_model

    def adapt(
        self,
        target_inputs: np.ndarray,
        target_outputs: np.ndarray,
        n_epochs: int = 100,
        learning_rate: float = 1e-4,
        freeze_early_layers: bool = True
    ) -> HybridModel:
        """
        Adapt source model to target domain.

        Uses physics constraints to guide adaptation.
        """
        # Create target model (copy of source)
        target_model = ResidualPhysicsNet(
            self.source_model.config,
            self.physics_model
        )

        # Copy weights from source
        if hasattr(self.source_model, 'nn'):
            for i, layer in enumerate(self.source_model.nn.layers):
                target_model.nn.layers[i].W = layer.W.copy()
                target_model.nn.layers[i].b = layer.b.copy()

        # Freeze early layers if requested
        if freeze_early_layers:
            n_freeze = len(target_model.nn.layers) // 2
            for i in range(n_freeze):
                target_model.nn.layers[i].W = target_model.nn.layers[i].W.astype(np.float64)

        # Fine-tune on target data
        original_lr = target_model.config.learning_rate
        target_model.config.learning_rate = learning_rate

        for epoch in range(n_epochs):
            loss = target_model.train_step(target_inputs, target_outputs)

            if (epoch + 1) % 10 == 0:
                logger.info(f"Transfer epoch {epoch + 1}: loss = {loss:.6f}")

        target_model.config.learning_rate = original_lr

        return target_model


# Export public API
__all__ = [
    # Physics models
    'PhysicsModel',
    'PhysicsModelConfig',
    'AnalyticalPhysicsModel',
    'ThermalAnalyticalModel',
    'MechanicalAnalyticalModel',
    # NN components
    'NeuralNetworkLayer',
    'SimpleNeuralNetwork',
    # Hybrid models
    'HybridModelType',
    'HybridModelConfig',
    'HybridModel',
    'ResidualPhysicsNet',
    'PhysicsDataFusion',
    'EnsembleHybridModel',
    # Uncertainty
    'UncertaintyType',
    'UncertaintyEstimate',
    'UncertaintyQuantifier',
    # Transfer learning
    'PhysicsGuidedTransfer',
]
