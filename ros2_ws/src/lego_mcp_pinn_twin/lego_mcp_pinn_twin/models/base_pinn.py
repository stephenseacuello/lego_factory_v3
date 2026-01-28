"""
Base Physics-Informed Neural Network (PINN) Architecture

Provides the foundational architecture for all PINN models in the
LEGO MCP Digital Twin system.

Theory:
    PINNs combine neural network function approximation with physics-based
    constraints. The total loss is:

    L_total = L_data + λ_physics * L_physics + λ_boundary * L_boundary

    where:
    - L_data: Mean squared error on observed data
    - L_physics: Residual of governing PDEs/ODEs
    - L_boundary: Boundary/initial condition satisfaction

References:
    - Raissi et al., "Physics-informed neural networks" (2019)
    - Karniadakis et al., "Physics-informed machine learning" (2021)
"""

import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Union
from enum import Enum


class PhysicsLossType(Enum):
    """Types of physics losses supported."""
    PDE_RESIDUAL = "pde_residual"
    ODE_RESIDUAL = "ode_residual"
    CONSERVATION_LAW = "conservation_law"
    BOUNDARY_CONDITION = "boundary_condition"
    INITIAL_CONDITION = "initial_condition"
    CONSTITUTIVE_RELATION = "constitutive_relation"


@dataclass
class PhysicsLoss:
    """
    Physics-based loss term for PINN training.

    Attributes:
        loss_type: Type of physics constraint
        weight: Weighting factor for this loss term
        residual_fn: Function computing the physics residual
        name: Human-readable name for logging
    """
    loss_type: PhysicsLossType
    weight: float
    residual_fn: Callable
    name: str
    active: bool = True


@dataclass
class PINNConfig:
    """
    Configuration for PINN architecture.

    Attributes:
        input_dim: Number of input features (e.g., x, y, z, t)
        output_dim: Number of output predictions
        hidden_layers: List of hidden layer sizes
        activation: Activation function name
        physics_weights: Dict of physics loss weights
        learning_rate: Initial learning rate
        use_adaptive_weights: Enable loss weighting adaptation
    """
    input_dim: int = 4  # x, y, z, t
    output_dim: int = 1
    hidden_layers: List[int] = field(default_factory=lambda: [64, 64, 64, 64])
    activation: str = "tanh"
    physics_weights: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 1e-3
    use_adaptive_weights: bool = True
    dropout_rate: float = 0.0
    batch_normalization: bool = False


class BasePINN(ABC):
    """
    Abstract base class for Physics-Informed Neural Networks.

    This class provides the common infrastructure for all PINN models:
    - Network architecture construction
    - Physics loss registration
    - Training loop with adaptive weighting
    - Gradient computation for physics constraints
    - Uncertainty quantification hooks

    Subclasses must implement:
    - _define_physics_losses(): Define domain-specific physics
    - forward(): Neural network forward pass
    - compute_physics_residual(): Compute PDE/ODE residuals
    """

    def __init__(self, config: PINNConfig):
        """
        Initialize PINN with configuration.

        Args:
            config: PINN configuration
        """
        self.config = config
        self.physics_losses: List[PhysicsLoss] = []
        self._weights: Optional[np.ndarray] = None
        self._biases: Optional[np.ndarray] = None
        self._training_history: List[Dict] = []

        # Build network
        self._build_network()

        # Register physics losses
        self._define_physics_losses()

    def _build_network(self) -> None:
        """
        Build the neural network architecture.

        Uses Xavier/Glorot initialization for weights.
        """
        layers = [self.config.input_dim] + self.config.hidden_layers + [self.config.output_dim]

        self._weights = []
        self._biases = []

        for i in range(len(layers) - 1):
            # Xavier initialization
            std = np.sqrt(2.0 / (layers[i] + layers[i + 1]))
            w = np.random.randn(layers[i], layers[i + 1]) * std
            b = np.zeros((1, layers[i + 1]))

            self._weights.append(w)
            self._biases.append(b)

    @abstractmethod
    def _define_physics_losses(self) -> None:
        """
        Define physics-based loss terms.

        Subclasses implement this to register domain-specific physics.
        Use register_physics_loss() to add each term.
        """
        pass

    @abstractmethod
    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Neural network forward pass.

        Args:
            x: Input array of shape (batch_size, input_dim)

        Returns:
            Output predictions of shape (batch_size, output_dim)
        """
        pass

    @abstractmethod
    def compute_physics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Compute physics residuals for all registered losses.

        Args:
            x: Input coordinates/time
            y_pred: Network predictions

        Returns:
            Dictionary mapping loss names to residual arrays
        """
        pass

    def register_physics_loss(
        self,
        name: str,
        loss_type: PhysicsLossType,
        residual_fn: Callable,
        weight: float = 1.0
    ) -> None:
        """
        Register a physics-based loss term.

        Args:
            name: Unique name for this loss
            loss_type: Type of physics constraint
            residual_fn: Function computing residual (should return 0 when satisfied)
            weight: Weighting factor
        """
        loss = PhysicsLoss(
            loss_type=loss_type,
            weight=weight,
            residual_fn=residual_fn,
            name=name
        )
        self.physics_losses.append(loss)

    def _activation(self, x: np.ndarray) -> np.ndarray:
        """Apply activation function."""
        if self.config.activation == "tanh":
            return np.tanh(x)
        elif self.config.activation == "relu":
            return np.maximum(0, x)
        elif self.config.activation == "swish":
            return x * (1 / (1 + np.exp(-x)))
        elif self.config.activation == "gelu":
            return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))
        else:
            return np.tanh(x)

    def _forward_pass(self, x: np.ndarray) -> np.ndarray:
        """
        Standard forward pass through the network.

        Args:
            x: Input of shape (batch_size, input_dim)

        Returns:
            Output of shape (batch_size, output_dim)
        """
        h = x
        for i, (w, b) in enumerate(zip(self._weights[:-1], self._biases[:-1])):
            h = self._activation(np.dot(h, w) + b)

        # Linear output layer
        output = np.dot(h, self._weights[-1]) + self._biases[-1]
        return output

    def compute_gradients(
        self,
        x: np.ndarray,
        y: np.ndarray,
        variable: str
    ) -> np.ndarray:
        """
        Compute gradients of output with respect to input variable.

        Uses automatic differentiation (numerical approximation for base class).

        Args:
            x: Input coordinates
            y: Output predictions
            variable: Which input variable ('x', 'y', 'z', 't', or index)

        Returns:
            Gradient array
        """
        # Determine variable index
        var_map = {'x': 0, 'y': 1, 'z': 2, 't': 3}
        if isinstance(variable, str):
            var_idx = var_map.get(variable, 0)
        else:
            var_idx = int(variable)

        # Numerical gradient (finite differences)
        eps = 1e-6
        x_plus = x.copy()
        x_minus = x.copy()
        x_plus[:, var_idx] += eps
        x_minus[:, var_idx] -= eps

        y_plus = self._forward_pass(x_plus)
        y_minus = self._forward_pass(x_minus)

        gradient = (y_plus - y_minus) / (2 * eps)
        return gradient

    def compute_total_loss(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_physics: np.ndarray
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute total training loss.

        Args:
            x_data: Observed data inputs
            y_data: Observed data outputs
            x_physics: Collocation points for physics

        Returns:
            Tuple of (total_loss, loss_breakdown_dict)
        """
        # Data loss
        y_pred_data = self._forward_pass(x_data)
        loss_data = np.mean((y_pred_data - y_data) ** 2)

        # Physics losses
        y_pred_physics = self._forward_pass(x_physics)
        residuals = self.compute_physics_residual(x_physics, y_pred_physics)

        loss_breakdown = {"data": loss_data}
        total_loss = loss_data

        for physics_loss in self.physics_losses:
            if physics_loss.active and physics_loss.name in residuals:
                residual = residuals[physics_loss.name]
                loss_value = np.mean(residual ** 2)
                weighted_loss = physics_loss.weight * loss_value
                loss_breakdown[physics_loss.name] = loss_value
                total_loss += weighted_loss

        return total_loss, loss_breakdown

    def predict(
        self,
        x: np.ndarray,
        return_uncertainty: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Make predictions with optional uncertainty quantification.

        Args:
            x: Input coordinates
            return_uncertainty: Whether to return uncertainty estimates

        Returns:
            Predictions, optionally with uncertainty
        """
        y_pred = self._forward_pass(x)

        if return_uncertainty:
            # Monte Carlo dropout approximation
            # (placeholder - real implementation uses ensemble or dropout)
            uncertainty = np.ones_like(y_pred) * 0.1  # Placeholder
            return y_pred, uncertainty

        return y_pred

    def save(self, path: str) -> None:
        """Save model weights to file."""
        np.savez(
            path,
            weights=[w for w in self._weights],
            biases=[b for b in self._biases],
            config=self.config.__dict__
        )

    def load(self, path: str) -> None:
        """Load model weights from file."""
        data = np.load(path, allow_pickle=True)
        self._weights = list(data['weights'])
        self._biases = list(data['biases'])

    @property
    def num_parameters(self) -> int:
        """Total number of trainable parameters."""
        total = 0
        for w, b in zip(self._weights, self._biases):
            total += w.size + b.size
        return total

    def summary(self) -> str:
        """Return model summary string."""
        lines = [
            "=" * 60,
            f"PINN Model: {self.__class__.__name__}",
            "=" * 60,
            f"Input dimension: {self.config.input_dim}",
            f"Output dimension: {self.config.output_dim}",
            f"Hidden layers: {self.config.hidden_layers}",
            f"Activation: {self.config.activation}",
            f"Total parameters: {self.num_parameters:,}",
            "-" * 60,
            "Physics Losses:",
        ]

        for loss in self.physics_losses:
            status = "✓" if loss.active else "✗"
            lines.append(f"  [{status}] {loss.name}: weight={loss.weight:.4f}")

        lines.append("=" * 60)
        return "\n".join(lines)
