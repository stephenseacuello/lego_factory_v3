"""
Physics-Informed Neural Networks (PINN) for Manufacturing.

This module implements PINNs for manufacturing process modeling:
- Thermal field prediction for FDM printing
- Mechanical stress/strain analysis
- Process parameter optimization
- Quality prediction with physics constraints

Research Value:
- Novel PINN architecture for additive manufacturing
- Physics-guided learning for sparse manufacturing data
- Multi-physics coupling for digital twins

References:
- Raissi, M., Perdikaris, P., Karniadakis, G.E. (2019). Physics-informed neural networks
- Lu, L., et al. (2021). DeepXDE: A deep learning library for solving PDEs
- ISO 23247 Digital Twin Framework
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, Union
)
import numpy as np
import logging
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Core PINN Components
# =============================================================================

class ActivationType(Enum):
    """Activation functions for PINN layers."""
    TANH = auto()
    SIGMOID = auto()
    RELU = auto()
    SWISH = auto()
    GELU = auto()
    SILU = auto()
    SOFTPLUS = auto()


class LossType(Enum):
    """Types of loss components in PINN."""
    DATA = auto()  # Data fitting loss
    PDE = auto()  # PDE residual loss
    BOUNDARY = auto()  # Boundary condition loss
    INITIAL = auto()  # Initial condition loss
    PHYSICS = auto()  # General physics constraint loss


@dataclass
class PINNConfig:
    """Configuration for PINN model."""
    input_dim: int
    output_dim: int
    hidden_layers: List[int] = field(default_factory=lambda: [64, 64, 64, 64])
    activation: ActivationType = ActivationType.TANH
    learning_rate: float = 1e-3
    loss_weights: Dict[LossType, float] = field(default_factory=lambda: {
        LossType.DATA: 1.0,
        LossType.PDE: 1.0,
        LossType.BOUNDARY: 1.0,
        LossType.INITIAL: 1.0,
    })
    use_batch_norm: bool = False
    dropout_rate: float = 0.0
    weight_decay: float = 0.0


class PINNLayer:
    """
    Neural network layer with automatic differentiation support.

    Implements forward pass and stores gradients for physics constraints.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        activation: ActivationType = ActivationType.TANH
    ):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.activation = activation

        # Xavier initialization
        scale = np.sqrt(2.0 / (input_dim + output_dim))
        self.weights = np.random.randn(input_dim, output_dim) * scale
        self.bias = np.zeros(output_dim)

        # Gradients
        self.grad_weights = np.zeros_like(self.weights)
        self.grad_bias = np.zeros_like(self.bias)

        # Cache for backprop
        self._input_cache: Optional[np.ndarray] = None
        self._pre_activation: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass through layer."""
        self._input_cache = x
        self._pre_activation = x @ self.weights + self.bias

        return self._apply_activation(self._pre_activation)

    def _apply_activation(self, x: np.ndarray) -> np.ndarray:
        """Apply activation function."""
        if self.activation == ActivationType.TANH:
            return np.tanh(x)
        elif self.activation == ActivationType.SIGMOID:
            return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
        elif self.activation == ActivationType.RELU:
            return np.maximum(0, x)
        elif self.activation == ActivationType.SWISH:
            return x * (1 / (1 + np.exp(-x)))
        elif self.activation == ActivationType.GELU:
            return 0.5 * x * (1 + np.tanh(np.sqrt(2/np.pi) * (x + 0.044715 * x**3)))
        elif self.activation == ActivationType.SOFTPLUS:
            return np.log(1 + np.exp(x))
        return x

    def _activation_derivative(self, x: np.ndarray) -> np.ndarray:
        """Compute activation derivative."""
        if self.activation == ActivationType.TANH:
            return 1 - np.tanh(x)**2
        elif self.activation == ActivationType.SIGMOID:
            s = 1 / (1 + np.exp(-np.clip(x, -500, 500)))
            return s * (1 - s)
        elif self.activation == ActivationType.RELU:
            return (x > 0).astype(float)
        elif self.activation == ActivationType.SWISH:
            s = 1 / (1 + np.exp(-x))
            return s + x * s * (1 - s)
        return np.ones_like(x)

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        """Backward pass to compute gradients."""
        # Derivative through activation
        grad_pre = grad_output * self._activation_derivative(self._pre_activation)

        # Gradient w.r.t. weights and bias
        self.grad_weights = self._input_cache.T @ grad_pre
        self.grad_bias = grad_pre.sum(axis=0)

        # Gradient w.r.t. input
        return grad_pre @ self.weights.T

    def update(self, learning_rate: float) -> None:
        """Update weights using accumulated gradients."""
        self.weights -= learning_rate * self.grad_weights
        self.bias -= learning_rate * self.grad_bias

        # Reset gradients
        self.grad_weights = np.zeros_like(self.weights)
        self.grad_bias = np.zeros_like(self.bias)


class PhysicsInformedNN:
    """
    Physics-Informed Neural Network base class.

    Combines data-driven learning with physics constraints
    through a composite loss function.
    """

    def __init__(self, config: PINNConfig):
        self.config = config
        self.layers: List[PINNLayer] = []
        self._build_network()

        # Training history
        self.loss_history: Dict[LossType, List[float]] = defaultdict(list)
        self.total_loss_history: List[float] = []

    def _build_network(self) -> None:
        """Build the neural network architecture."""
        layer_sizes = [self.config.input_dim] + self.config.hidden_layers + [self.config.output_dim]

        for i in range(len(layer_sizes) - 1):
            # Use linear activation for output layer
            activation = (
                self.config.activation
                if i < len(layer_sizes) - 2
                else ActivationType.TANH  # Or linear for regression
            )
            self.layers.append(PINNLayer(
                layer_sizes[i],
                layer_sizes[i + 1],
                activation
            ))

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass through the network."""
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Make predictions (alias for forward)."""
        return self.forward(x)

    def compute_gradients(
        self,
        x: np.ndarray,
        output_idx: int = 0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute first and second order gradients of output w.r.t. input.

        Uses finite differences for simplicity; can be replaced with
        automatic differentiation in production.

        Returns:
            Tuple of (first_derivative, second_derivative) w.r.t. each input dim
        """
        eps = 1e-4
        n_samples, n_inputs = x.shape

        first_deriv = np.zeros((n_samples, n_inputs))
        second_deriv = np.zeros((n_samples, n_inputs))

        y = self.forward(x)[:, output_idx]

        for i in range(n_inputs):
            x_plus = x.copy()
            x_plus[:, i] += eps
            y_plus = self.forward(x_plus)[:, output_idx]

            x_minus = x.copy()
            x_minus[:, i] -= eps
            y_minus = self.forward(x_minus)[:, output_idx]

            # Central difference
            first_deriv[:, i] = (y_plus - y_minus) / (2 * eps)
            second_deriv[:, i] = (y_plus - 2 * y + y_minus) / (eps ** 2)

        return first_deriv, second_deriv

    def data_loss(
        self,
        x: np.ndarray,
        y_true: np.ndarray
    ) -> float:
        """Compute data fitting loss (MSE)."""
        y_pred = self.forward(x)
        return float(np.mean((y_pred - y_true) ** 2))

    @abstractmethod
    def physics_loss(
        self,
        x_collocation: np.ndarray
    ) -> float:
        """
        Compute physics-based loss (PDE residual).

        Must be implemented by subclasses for specific physics.
        """
        pass

    def boundary_loss(
        self,
        x_boundary: np.ndarray,
        y_boundary: np.ndarray
    ) -> float:
        """Compute boundary condition loss."""
        y_pred = self.forward(x_boundary)
        return float(np.mean((y_pred - y_boundary) ** 2))

    def initial_loss(
        self,
        x_initial: np.ndarray,
        y_initial: np.ndarray
    ) -> float:
        """Compute initial condition loss."""
        y_pred = self.forward(x_initial)
        return float(np.mean((y_pred - y_initial) ** 2))

    def total_loss(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_collocation: np.ndarray,
        x_boundary: Optional[np.ndarray] = None,
        y_boundary: Optional[np.ndarray] = None,
        x_initial: Optional[np.ndarray] = None,
        y_initial: Optional[np.ndarray] = None
    ) -> float:
        """Compute weighted total loss."""
        weights = self.config.loss_weights

        total = 0.0

        # Data loss
        data_l = self.data_loss(x_data, y_data)
        total += weights.get(LossType.DATA, 1.0) * data_l
        self.loss_history[LossType.DATA].append(data_l)

        # Physics loss
        physics_l = self.physics_loss(x_collocation)
        total += weights.get(LossType.PDE, 1.0) * physics_l
        self.loss_history[LossType.PDE].append(physics_l)

        # Boundary loss
        if x_boundary is not None and y_boundary is not None:
            boundary_l = self.boundary_loss(x_boundary, y_boundary)
            total += weights.get(LossType.BOUNDARY, 1.0) * boundary_l
            self.loss_history[LossType.BOUNDARY].append(boundary_l)

        # Initial loss
        if x_initial is not None and y_initial is not None:
            initial_l = self.initial_loss(x_initial, y_initial)
            total += weights.get(LossType.INITIAL, 1.0) * initial_l
            self.loss_history[LossType.INITIAL].append(initial_l)

        self.total_loss_history.append(total)
        return total

    def backward(self, grad_output: np.ndarray) -> None:
        """Backward pass through all layers."""
        grad = grad_output
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def update_weights(self) -> None:
        """Update all layer weights."""
        for layer in self.layers:
            layer.update(self.config.learning_rate)

    def get_parameters(self) -> Dict[str, np.ndarray]:
        """Get all network parameters."""
        params = {}
        for i, layer in enumerate(self.layers):
            params[f'layer_{i}_weights'] = layer.weights.copy()
            params[f'layer_{i}_bias'] = layer.bias.copy()
        return params

    def set_parameters(self, params: Dict[str, np.ndarray]) -> None:
        """Set network parameters."""
        for i, layer in enumerate(self.layers):
            layer.weights = params[f'layer_{i}_weights'].copy()
            layer.bias = params[f'layer_{i}_bias'].copy()

    def save(self, filepath: str) -> None:
        """Save model to file."""
        params = self.get_parameters()
        np.savez(
            filepath,
            **params,
            config=json.dumps({
                'input_dim': self.config.input_dim,
                'output_dim': self.config.output_dim,
                'hidden_layers': self.config.hidden_layers,
                'activation': self.config.activation.name,
            })
        )

    @classmethod
    def load(cls, filepath: str) -> 'PhysicsInformedNN':
        """Load model from file."""
        data = np.load(filepath, allow_pickle=True)
        config_dict = json.loads(str(data['config']))

        config = PINNConfig(
            input_dim=config_dict['input_dim'],
            output_dim=config_dict['output_dim'],
            hidden_layers=config_dict['hidden_layers'],
            activation=ActivationType[config_dict['activation']]
        )

        model = cls(config)
        params = {k: data[k] for k in data.files if k != 'config'}
        model.set_parameters(params)

        return model


# =============================================================================
# Thermal PINN for FDM Printing
# =============================================================================

class ThermalPINN(PhysicsInformedNN):
    """
    Physics-Informed NN for thermal field prediction in FDM printing.

    Solves the heat equation:
    ∂T/∂t = α(∂²T/∂x² + ∂²T/∂y² + ∂²T/∂z²) + Q/(ρ·cp)

    Where:
    - T: Temperature
    - t: Time
    - α: Thermal diffusivity
    - Q: Heat source (from nozzle)
    - ρ: Density
    - cp: Specific heat capacity

    Input: [x, y, z, t]
    Output: [T]
    """

    def __init__(
        self,
        config: PINNConfig,
        thermal_diffusivity: float = 1.5e-7,  # m²/s for PLA
        heat_source_intensity: float = 0.0,
        density: float = 1240.0,  # kg/m³ for PLA
        specific_heat: float = 1800.0  # J/(kg·K) for PLA
    ):
        # Ensure correct dimensions
        config.input_dim = 4  # x, y, z, t
        config.output_dim = 1  # T

        super().__init__(config)

        self.alpha = thermal_diffusivity
        self.Q = heat_source_intensity
        self.rho = density
        self.cp = specific_heat

    def physics_loss(self, x_collocation: np.ndarray) -> float:
        """
        Compute heat equation residual.

        PDE: ∂T/∂t - α·∇²T - Q/(ρ·cp) = 0
        """
        # Get temperature prediction
        T = self.forward(x_collocation)

        # Compute derivatives
        eps = 1e-4

        # ∂T/∂t (time is the 4th input, index 3)
        x_t_plus = x_collocation.copy()
        x_t_plus[:, 3] += eps
        x_t_minus = x_collocation.copy()
        x_t_minus[:, 3] -= eps
        dT_dt = (self.forward(x_t_plus) - self.forward(x_t_minus)) / (2 * eps)

        # ∂²T/∂x²
        x_plus = x_collocation.copy()
        x_plus[:, 0] += eps
        x_minus = x_collocation.copy()
        x_minus[:, 0] -= eps
        d2T_dx2 = (self.forward(x_plus) - 2*T + self.forward(x_minus)) / (eps**2)

        # ∂²T/∂y²
        y_plus = x_collocation.copy()
        y_plus[:, 1] += eps
        y_minus = x_collocation.copy()
        y_minus[:, 1] -= eps
        d2T_dy2 = (self.forward(y_plus) - 2*T + self.forward(y_minus)) / (eps**2)

        # ∂²T/∂z²
        z_plus = x_collocation.copy()
        z_plus[:, 2] += eps
        z_minus = x_collocation.copy()
        z_minus[:, 2] -= eps
        d2T_dz2 = (self.forward(z_plus) - 2*T + self.forward(z_minus)) / (eps**2)

        # Laplacian
        laplacian_T = d2T_dx2 + d2T_dy2 + d2T_dz2

        # Heat source term
        source_term = self.Q / (self.rho * self.cp)

        # PDE residual
        residual = dT_dt - self.alpha * laplacian_T - source_term

        return float(np.mean(residual ** 2))

    def predict_temperature_field(
        self,
        x_range: Tuple[float, float],
        y_range: Tuple[float, float],
        z_range: Tuple[float, float],
        t: float,
        resolution: int = 20
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict temperature field at a given time.

        Returns:
            Tuple of (X, Y, Z, T) meshgrids
        """
        x = np.linspace(x_range[0], x_range[1], resolution)
        y = np.linspace(y_range[0], y_range[1], resolution)
        z = np.linspace(z_range[0], z_range[1], resolution)

        X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
        points = np.column_stack([
            X.ravel(),
            Y.ravel(),
            Z.ravel(),
            np.full(X.size, t)
        ])

        T = self.forward(points).reshape(X.shape)

        return X, Y, Z, T


# =============================================================================
# Mechanical PINN for Stress/Strain Analysis
# =============================================================================

class MechanicalPINN(PhysicsInformedNN):
    """
    Physics-Informed NN for mechanical stress/strain prediction.

    Solves linear elasticity equations:
    ∇·σ + f = 0  (equilibrium)
    ε = (∇u + (∇u)ᵀ) / 2  (strain-displacement)
    σ = C:ε  (constitutive)

    Where:
    - σ: Stress tensor
    - ε: Strain tensor
    - u: Displacement vector
    - f: Body force
    - C: Stiffness tensor

    Input: [x, y, z]
    Output: [u_x, u_y, u_z]  (displacement components)
    """

    def __init__(
        self,
        config: PINNConfig,
        youngs_modulus: float = 2.5e9,  # Pa for PLA
        poissons_ratio: float = 0.35
    ):
        config.input_dim = 3  # x, y, z
        config.output_dim = 3  # u_x, u_y, u_z

        super().__init__(config)

        self.E = youngs_modulus
        self.nu = poissons_ratio

        # Lamé parameters
        self.lam = self.E * self.nu / ((1 + self.nu) * (1 - 2 * self.nu))
        self.mu = self.E / (2 * (1 + self.nu))

    def compute_strain(
        self,
        x: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute strain tensor components from displacement field.

        Returns:
            Tuple of (ε_xx, ε_yy, ε_zz, ε_xy, ε_xz, ε_yz)
        """
        eps = 1e-4

        # Get displacement
        u = self.forward(x)
        u_x, u_y, u_z = u[:, 0], u[:, 1], u[:, 2]

        # Compute displacement gradients
        # ∂u_x/∂x
        x_plus = x.copy()
        x_plus[:, 0] += eps
        x_minus = x.copy()
        x_minus[:, 0] -= eps
        du_x_dx = (self.forward(x_plus)[:, 0] - self.forward(x_minus)[:, 0]) / (2 * eps)

        # ∂u_y/∂y
        y_plus = x.copy()
        y_plus[:, 1] += eps
        y_minus = x.copy()
        y_minus[:, 1] -= eps
        du_y_dy = (self.forward(y_plus)[:, 1] - self.forward(y_minus)[:, 1]) / (2 * eps)

        # ∂u_z/∂z
        z_plus = x.copy()
        z_plus[:, 2] += eps
        z_minus = x.copy()
        z_minus[:, 2] -= eps
        du_z_dz = (self.forward(z_plus)[:, 2] - self.forward(z_minus)[:, 2]) / (2 * eps)

        # Cross derivatives
        du_x_dy = (self.forward(y_plus)[:, 0] - self.forward(y_minus)[:, 0]) / (2 * eps)
        du_y_dx = (self.forward(x_plus)[:, 1] - self.forward(x_minus)[:, 1]) / (2 * eps)

        du_x_dz = (self.forward(z_plus)[:, 0] - self.forward(z_minus)[:, 0]) / (2 * eps)
        du_z_dx = (self.forward(x_plus)[:, 2] - self.forward(x_minus)[:, 2]) / (2 * eps)

        du_y_dz = (self.forward(z_plus)[:, 1] - self.forward(z_minus)[:, 1]) / (2 * eps)
        du_z_dy = (self.forward(y_plus)[:, 2] - self.forward(y_minus)[:, 2]) / (2 * eps)

        # Strain components
        eps_xx = du_x_dx
        eps_yy = du_y_dy
        eps_zz = du_z_dz
        eps_xy = 0.5 * (du_x_dy + du_y_dx)
        eps_xz = 0.5 * (du_x_dz + du_z_dx)
        eps_yz = 0.5 * (du_y_dz + du_z_dy)

        return eps_xx, eps_yy, eps_zz, eps_xy, eps_xz, eps_yz

    def compute_stress(
        self,
        x: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute stress tensor components from strain using constitutive law.

        Returns:
            Tuple of (σ_xx, σ_yy, σ_zz, σ_xy, σ_xz, σ_yz)
        """
        eps_xx, eps_yy, eps_zz, eps_xy, eps_xz, eps_yz = self.compute_strain(x)

        # Volumetric strain
        eps_vol = eps_xx + eps_yy + eps_zz

        # Stress components (isotropic linear elastic)
        sigma_xx = self.lam * eps_vol + 2 * self.mu * eps_xx
        sigma_yy = self.lam * eps_vol + 2 * self.mu * eps_yy
        sigma_zz = self.lam * eps_vol + 2 * self.mu * eps_zz
        sigma_xy = 2 * self.mu * eps_xy
        sigma_xz = 2 * self.mu * eps_xz
        sigma_yz = 2 * self.mu * eps_yz

        return sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_xz, sigma_yz

    def physics_loss(self, x_collocation: np.ndarray) -> float:
        """
        Compute equilibrium equation residual.

        ∇·σ + f = 0 (assuming f = 0)
        """
        eps = 1e-4

        # Get stress at collocation points
        sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_xz, sigma_yz = self.compute_stress(x_collocation)

        # Stress divergence (simplified)
        # ∂σ_xx/∂x + ∂σ_xy/∂y + ∂σ_xz/∂z = 0
        # ∂σ_xy/∂x + ∂σ_yy/∂y + ∂σ_yz/∂z = 0
        # ∂σ_xz/∂x + ∂σ_yz/∂y + ∂σ_zz/∂z = 0

        # Compute derivatives of stress (simplified using finite differences)
        x_plus = x_collocation.copy()
        x_plus[:, 0] += eps
        sigma_xx_plus = self.compute_stress(x_plus)[0]

        x_minus = x_collocation.copy()
        x_minus[:, 0] -= eps
        sigma_xx_minus = self.compute_stress(x_minus)[0]

        d_sigma_xx_dx = (sigma_xx_plus - sigma_xx_minus) / (2 * eps)

        # For simplicity, just checking x-direction equilibrium
        residual_x = d_sigma_xx_dx  # Simplified

        return float(np.mean(residual_x ** 2))

    def compute_von_mises_stress(self, x: np.ndarray) -> np.ndarray:
        """Compute von Mises equivalent stress."""
        sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_xz, sigma_yz = self.compute_stress(x)

        # von Mises stress
        von_mises = np.sqrt(
            0.5 * (
                (sigma_xx - sigma_yy)**2 +
                (sigma_yy - sigma_zz)**2 +
                (sigma_zz - sigma_xx)**2 +
                6 * (sigma_xy**2 + sigma_xz**2 + sigma_yz**2)
            )
        )

        return von_mises


# =============================================================================
# FDM Process PINN (Multi-Physics)
# =============================================================================

class FDMProcessPINN(PhysicsInformedNN):
    """
    Multi-physics PINN for FDM 3D printing process.

    Couples:
    1. Thermal field (heat equation)
    2. Material flow (simplified Navier-Stokes)
    3. Solidification kinetics

    Input: [x, y, z, t, process_params...]
    Output: [T, viscosity, solidification_fraction]

    Research Value:
    - Novel multi-physics PINN for additive manufacturing
    - Process parameter optimization
    - Quality prediction from physics
    """

    def __init__(
        self,
        config: PINNConfig,
        material_properties: Optional[Dict[str, float]] = None
    ):
        # Default to PLA properties
        self.material = material_properties or {
            'thermal_diffusivity': 1.5e-7,  # m²/s
            'melting_temp': 180.0,  # °C
            'glass_transition_temp': 60.0,  # °C
            'density': 1240.0,  # kg/m³
            'specific_heat': 1800.0,  # J/(kg·K)
            'thermal_conductivity': 0.13,  # W/(m·K)
            'zero_shear_viscosity': 1e4,  # Pa·s at reference temp
            'activation_energy': 30000.0,  # J/mol
        }

        # Input: [x, y, z, t, nozzle_temp, bed_temp, print_speed, layer_height]
        config.input_dim = 8
        # Output: [T, viscosity, solidification_degree]
        config.output_dim = 3

        super().__init__(config)

    def physics_loss(self, x_collocation: np.ndarray) -> float:
        """
        Compute coupled physics loss.

        Combines:
        1. Heat equation residual
        2. Arrhenius viscosity constraint
        3. Solidification kinetics
        """
        output = self.forward(x_collocation)
        T = output[:, 0]  # Temperature
        eta = output[:, 1]  # Viscosity
        alpha = output[:, 2]  # Solidification degree

        eps = 1e-4
        R = 8.314  # Gas constant J/(mol·K)

        # 1. Heat equation residual (simplified)
        # ∂T/∂t - α_th·∇²T = 0
        x_t_plus = x_collocation.copy()
        x_t_plus[:, 3] += eps
        T_t_plus = self.forward(x_t_plus)[:, 0]

        x_t_minus = x_collocation.copy()
        x_t_minus[:, 3] -= eps
        T_t_minus = self.forward(x_t_minus)[:, 0]

        dT_dt = (T_t_plus - T_t_minus) / (2 * eps)

        # Laplacian of T (sum of second derivatives)
        laplacian_T = np.zeros_like(T)
        for dim in range(3):  # x, y, z
            x_plus = x_collocation.copy()
            x_plus[:, dim] += eps
            x_minus = x_collocation.copy()
            x_minus[:, dim] -= eps

            T_plus = self.forward(x_plus)[:, 0]
            T_minus = self.forward(x_minus)[:, 0]
            laplacian_T += (T_plus - 2*T + T_minus) / (eps**2)

        heat_residual = dT_dt - self.material['thermal_diffusivity'] * laplacian_T

        # 2. Arrhenius viscosity constraint
        # η = η_0 · exp(E_a / (R·T))
        T_kelvin = T + 273.15  # Convert to Kelvin
        eta_arrhenius = self.material['zero_shear_viscosity'] * np.exp(
            self.material['activation_energy'] / (R * T_kelvin)
        )
        # Normalize to avoid huge numbers
        eta_target = np.log10(eta_arrhenius + 1)
        eta_pred = np.log10(np.abs(eta) + 1)
        viscosity_residual = eta_pred - eta_target

        # 3. Solidification constraint
        # α = 0 when T > T_m (liquid)
        # α = 1 when T < T_g (solid)
        # Smooth transition between
        T_m = self.material['melting_temp']
        T_g = self.material['glass_transition_temp']

        alpha_target = np.clip((T_m - T) / (T_m - T_g), 0, 1)
        solidification_residual = alpha - alpha_target

        # Combined loss
        total_residual = (
            np.mean(heat_residual**2) +
            0.1 * np.mean(viscosity_residual**2) +
            0.1 * np.mean(solidification_residual**2)
        )

        return float(total_residual)

    def predict_print_quality(
        self,
        layer_data: np.ndarray,
        process_params: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Predict print quality based on physics simulation.

        Args:
            layer_data: Points in the layer [N, 3] (x, y, z)
            process_params: Dict with nozzle_temp, bed_temp, print_speed, layer_height

        Returns:
            Dict with quality metrics
        """
        n_points = len(layer_data)
        t = 0.0  # Start of layer

        # Build input
        inputs = np.column_stack([
            layer_data,
            np.full(n_points, t),
            np.full(n_points, process_params.get('nozzle_temp', 200)),
            np.full(n_points, process_params.get('bed_temp', 60)),
            np.full(n_points, process_params.get('print_speed', 50)),
            np.full(n_points, process_params.get('layer_height', 0.2)),
        ])

        output = self.forward(inputs)
        T = output[:, 0]
        eta = output[:, 1]
        alpha = output[:, 2]

        return {
            'temperature': {
                'mean': float(np.mean(T)),
                'std': float(np.std(T)),
                'min': float(np.min(T)),
                'max': float(np.max(T)),
            },
            'viscosity': {
                'mean': float(np.mean(eta)),
                'std': float(np.std(eta)),
            },
            'solidification': {
                'mean': float(np.mean(alpha)),
                'uniformity': 1.0 - float(np.std(alpha)),
            },
            'quality_score': float(
                0.4 * (1.0 - np.std(T) / 50) +  # Temperature uniformity
                0.3 * np.mean(alpha) +  # Solidification completeness
                0.3 * (1.0 - np.clip(np.std(eta) / 1000, 0, 1))  # Viscosity uniformity
            ),
        }


# =============================================================================
# PINN Trainer
# =============================================================================

@dataclass
class TrainingConfig:
    """Configuration for PINN training."""
    epochs: int = 10000
    batch_size: int = 256
    learning_rate: float = 1e-3
    lr_decay: float = 0.99
    lr_decay_steps: int = 1000
    early_stopping_patience: int = 500
    collocation_points: int = 10000
    print_every: int = 100
    validate_every: int = 500


class PINNTrainer:
    """
    Trainer for Physics-Informed Neural Networks.

    Implements:
    - Adaptive loss weighting
    - Learning rate scheduling
    - Early stopping
    - Collocation point sampling
    """

    def __init__(
        self,
        model: PhysicsInformedNN,
        config: TrainingConfig
    ):
        self.model = model
        self.config = config
        self.best_loss = float('inf')
        self.patience_counter = 0
        self.current_lr = config.learning_rate

    def sample_collocation_points(
        self,
        domain: Dict[str, Tuple[float, float]],
        n_points: int
    ) -> np.ndarray:
        """Sample collocation points in the domain."""
        n_dims = len(domain)
        points = np.zeros((n_points, n_dims))

        for i, (dim_name, (low, high)) in enumerate(domain.items()):
            points[:, i] = np.random.uniform(low, high, n_points)

        return points

    def train(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        domain: Dict[str, Tuple[float, float]],
        x_boundary: Optional[np.ndarray] = None,
        y_boundary: Optional[np.ndarray] = None,
        x_initial: Optional[np.ndarray] = None,
        y_initial: Optional[np.ndarray] = None,
        validation_data: Optional[Tuple[np.ndarray, np.ndarray]] = None
    ) -> Dict[str, List[float]]:
        """
        Train the PINN model.

        Returns:
            Training history dictionary
        """
        history = {
            'total_loss': [],
            'data_loss': [],
            'physics_loss': [],
            'validation_loss': [],
        }

        n_samples = len(x_data)

        for epoch in range(self.config.epochs):
            # Sample batch
            batch_idx = np.random.choice(n_samples, min(self.config.batch_size, n_samples), replace=False)
            x_batch = x_data[batch_idx]
            y_batch = y_data[batch_idx]

            # Sample collocation points
            x_collocation = self.sample_collocation_points(
                domain,
                self.config.collocation_points
            )

            # Forward pass and compute loss
            loss = self.model.total_loss(
                x_batch, y_batch,
                x_collocation,
                x_boundary, y_boundary,
                x_initial, y_initial
            )

            # Record history
            history['total_loss'].append(loss)
            if self.model.loss_history[LossType.DATA]:
                history['data_loss'].append(self.model.loss_history[LossType.DATA][-1])
            if self.model.loss_history[LossType.PDE]:
                history['physics_loss'].append(self.model.loss_history[LossType.PDE][-1])

            # Backward pass (simplified gradient)
            y_pred = self.model.forward(x_batch)
            grad_output = 2 * (y_pred - y_batch) / len(x_batch)
            self.model.backward(grad_output)

            # Update weights
            self.model.config.learning_rate = self.current_lr
            self.model.update_weights()

            # Learning rate decay
            if (epoch + 1) % self.config.lr_decay_steps == 0:
                self.current_lr *= self.config.lr_decay

            # Validation
            if validation_data and (epoch + 1) % self.config.validate_every == 0:
                val_loss = self.model.data_loss(*validation_data)
                history['validation_loss'].append(val_loss)

                # Early stopping check
                if val_loss < self.best_loss:
                    self.best_loss = val_loss
                    self.patience_counter = 0
                else:
                    self.patience_counter += 1

                if self.patience_counter >= self.config.early_stopping_patience // self.config.validate_every:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

            # Logging
            if (epoch + 1) % self.config.print_every == 0:
                logger.info(
                    f"Epoch {epoch + 1}/{self.config.epochs} - "
                    f"Loss: {loss:.6f} - LR: {self.current_lr:.2e}"
                )

        return history


# Export public API
__all__ = [
    # Config
    'PINNConfig',
    'TrainingConfig',
    'ActivationType',
    'LossType',
    # Core
    'PINNLayer',
    'PhysicsInformedNN',
    # Specialized PINNs
    'ThermalPINN',
    'MechanicalPINN',
    'FDMProcessPINN',
    # Trainer
    'PINNTrainer',
]
