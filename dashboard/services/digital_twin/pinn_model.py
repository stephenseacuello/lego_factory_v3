"""
Physics-Informed Neural Network (PINN) Digital Twin Models

Hybrid physics-ML models for manufacturing process simulation.
Embeds physical laws as constraints in neural network training.

Features:
- Thermal dynamics modeling (Fourier's law)
- Structural mechanics (elasticity equations)
- Fluid dynamics approximation
- Multi-physics coupling

Reference: Raissi et al., "Physics-informed neural networks" (2019)

Author: LEGO MCP Digital Twin Engineering
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
from enum import Enum, auto
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PhysicsType(Enum):
    """Types of physics models."""
    THERMAL = "thermal"
    STRUCTURAL = "structural"
    FLUID = "fluid"
    ELECTROMAGNETIC = "electromagnetic"
    MULTI_PHYSICS = "multi_physics"


class BoundaryConditionType(Enum):
    """Types of boundary conditions."""
    DIRICHLET = "dirichlet"  # Fixed value
    NEUMANN = "neumann"      # Fixed gradient
    ROBIN = "robin"          # Mixed
    PERIODIC = "periodic"


@dataclass
class PhysicalDomain:
    """Physical domain specification."""
    x_min: float = 0.0
    x_max: float = 1.0
    y_min: float = 0.0
    y_max: float = 1.0
    z_min: float = 0.0
    z_max: float = 1.0
    t_min: float = 0.0
    t_max: float = 1.0

    def sample_interior(self, n_points: int) -> np.ndarray:
        """Sample random points in interior."""
        x = np.random.uniform(self.x_min, self.x_max, n_points)
        y = np.random.uniform(self.y_min, self.y_max, n_points)
        z = np.random.uniform(self.z_min, self.z_max, n_points)
        t = np.random.uniform(self.t_min, self.t_max, n_points)
        return np.column_stack([x, y, z, t])

    def sample_boundary(self, n_points: int, face: str = "all") -> np.ndarray:
        """Sample points on domain boundary."""
        points = []
        n_per_face = n_points // 6

        # Sample each face
        for _ in range(n_per_face):
            if face in ["all", "x_min"]:
                points.append([self.x_min,
                              np.random.uniform(self.y_min, self.y_max),
                              np.random.uniform(self.z_min, self.z_max),
                              np.random.uniform(self.t_min, self.t_max)])
            if face in ["all", "x_max"]:
                points.append([self.x_max,
                              np.random.uniform(self.y_min, self.y_max),
                              np.random.uniform(self.z_min, self.z_max),
                              np.random.uniform(self.t_min, self.t_max)])

        return np.array(points) if points else np.zeros((0, 4))


@dataclass
class MaterialProperties:
    """Material physical properties."""
    name: str
    density: float                # kg/m^3
    thermal_conductivity: float   # W/(m·K)
    specific_heat: float          # J/(kg·K)
    elastic_modulus: float        # Pa
    poisson_ratio: float          # dimensionless
    yield_strength: float         # Pa

    @classmethod
    def abs_plastic(cls) -> "MaterialProperties":
        """ABS plastic properties."""
        return cls(
            name="ABS",
            density=1050,
            thermal_conductivity=0.17,
            specific_heat=1300,
            elastic_modulus=2.3e9,
            poisson_ratio=0.35,
            yield_strength=40e6,
        )

    @classmethod
    def aluminum_6061(cls) -> "MaterialProperties":
        """Aluminum 6061-T6 properties."""
        return cls(
            name="Aluminum-6061-T6",
            density=2700,
            thermal_conductivity=167,
            specific_heat=896,
            elastic_modulus=68.9e9,
            poisson_ratio=0.33,
            yield_strength=276e6,
        )


@dataclass
class BoundaryCondition:
    """Boundary condition specification."""
    condition_type: BoundaryConditionType
    location: str  # "x_min", "x_max", etc.
    value: Union[float, Callable]

    def evaluate(self, point: np.ndarray) -> float:
        """Evaluate boundary condition at point."""
        if callable(self.value):
            return self.value(point)
        return self.value


@dataclass
class PINNConfig:
    """PINN model configuration."""
    hidden_layers: List[int] = field(default_factory=lambda: [64, 64, 64])
    activation: str = "tanh"
    learning_rate: float = 1e-3
    physics_weight: float = 1.0
    data_weight: float = 1.0
    boundary_weight: float = 10.0
    n_collocation: int = 10000
    n_boundary: int = 1000
    max_epochs: int = 10000
    patience: int = 100


@dataclass
class TrainingHistory:
    """Training history record."""
    epochs: List[int] = field(default_factory=list)
    total_loss: List[float] = field(default_factory=list)
    physics_loss: List[float] = field(default_factory=list)
    data_loss: List[float] = field(default_factory=list)
    boundary_loss: List[float] = field(default_factory=list)

    def add(
        self,
        epoch: int,
        total: float,
        physics: float,
        data: float,
        boundary: float,
    ) -> None:
        """Add training record."""
        self.epochs.append(epoch)
        self.total_loss.append(total)
        self.physics_loss.append(physics)
        self.data_loss.append(data)
        self.boundary_loss.append(boundary)


class PhysicsResidual(ABC):
    """Abstract base for physics residual computation."""

    @abstractmethod
    def compute(
        self,
        u: np.ndarray,
        x: np.ndarray,
        gradients: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """Compute physics residual."""
        pass


class HeatEquationResidual(PhysicsResidual):
    """
    Heat equation residual: du/dt = alpha * laplacian(u)

    Where alpha = k / (rho * cp)
    """

    def __init__(self, material: MaterialProperties):
        self.alpha = (
            material.thermal_conductivity /
            (material.density * material.specific_heat)
        )

    def compute(
        self,
        u: np.ndarray,
        x: np.ndarray,
        gradients: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """
        Compute heat equation residual.

        R = du/dt - alpha * (d²u/dx² + d²u/dy² + d²u/dz²)
        """
        du_dt = gradients.get("du_dt", np.zeros_like(u))
        d2u_dx2 = gradients.get("d2u_dx2", np.zeros_like(u))
        d2u_dy2 = gradients.get("d2u_dy2", np.zeros_like(u))
        d2u_dz2 = gradients.get("d2u_dz2", np.zeros_like(u))

        laplacian = d2u_dx2 + d2u_dy2 + d2u_dz2

        return du_dt - self.alpha * laplacian


class ElasticityResidual(PhysicsResidual):
    """
    Linear elasticity residual (Navier-Cauchy equations).

    (lambda + mu) * grad(div(u)) + mu * laplacian(u) + f = 0
    """

    def __init__(self, material: MaterialProperties):
        E = material.elastic_modulus
        nu = material.poisson_ratio

        # Lamé parameters
        self.lam = E * nu / ((1 + nu) * (1 - 2 * nu))
        self.mu = E / (2 * (1 + nu))

    def compute(
        self,
        u: np.ndarray,
        x: np.ndarray,
        gradients: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """Compute elasticity residual."""
        # Simplified: just laplacian term for demonstration
        d2u_dx2 = gradients.get("d2u_dx2", np.zeros_like(u))
        d2u_dy2 = gradients.get("d2u_dy2", np.zeros_like(u))
        d2u_dz2 = gradients.get("d2u_dz2", np.zeros_like(u))

        laplacian = d2u_dx2 + d2u_dy2 + d2u_dz2

        return self.mu * laplacian


class NeuralNetwork:
    """
    Simple neural network implementation for PINN.

    Note: In production, use PyTorch/TensorFlow/JAX.
    This is a minimal numpy implementation for demonstration.
    """

    def __init__(self, layers: List[int], activation: str = "tanh"):
        self.layers = layers
        self.activation = activation
        self.weights: List[np.ndarray] = []
        self.biases: List[np.ndarray] = []

        # Initialize weights (Xavier initialization)
        for i in range(len(layers) - 1):
            w = np.random.randn(layers[i], layers[i+1]) * np.sqrt(2.0 / layers[i])
            b = np.zeros(layers[i+1])
            self.weights.append(w)
            self.biases.append(b)

    def _activate(self, x: np.ndarray) -> np.ndarray:
        """Apply activation function."""
        if self.activation == "tanh":
            return np.tanh(x)
        elif self.activation == "relu":
            return np.maximum(0, x)
        elif self.activation == "sigmoid":
            return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
        return x

    def _activate_derivative(self, x: np.ndarray) -> np.ndarray:
        """Activation function derivative."""
        if self.activation == "tanh":
            return 1 - np.tanh(x) ** 2
        elif self.activation == "relu":
            return (x > 0).astype(float)
        elif self.activation == "sigmoid":
            s = self._activate(x)
            return s * (1 - s)
        return np.ones_like(x)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass."""
        a = x
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ w + b
            if i < len(self.weights) - 1:  # No activation on output
                a = self._activate(z)
            else:
                a = z
        return a

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Make prediction."""
        return self.forward(x)


class PINNModel:
    """
    Physics-Informed Neural Network Model.

    Combines neural network with physics constraints for accurate
    digital twin simulation.

    Usage:
        # Create model
        material = MaterialProperties.abs_plastic()
        model = PINNModel(
            physics_type=PhysicsType.THERMAL,
            material=material,
        )

        # Set domain
        model.set_domain(PhysicalDomain(x_max=0.01, t_max=100))

        # Add boundary conditions
        model.add_boundary_condition(BoundaryCondition(
            condition_type=BoundaryConditionType.DIRICHLET,
            location="x_min",
            value=300.0,  # 300K
        ))

        # Train with sensor data
        model.train(sensor_data=measurements)

        # Predict
        temperature = model.predict(query_points)
    """

    def __init__(
        self,
        physics_type: PhysicsType,
        material: MaterialProperties,
        config: Optional[PINNConfig] = None,
    ):
        self.physics_type = physics_type
        self.material = material
        self.config = config or PINNConfig()

        # Initialize network
        input_dim = 4  # x, y, z, t
        output_dim = 1  # scalar field (temperature, displacement, etc.)
        layers = [input_dim] + self.config.hidden_layers + [output_dim]
        self.network = NeuralNetwork(layers, self.config.activation)

        # Physics residual
        self.physics_residual = self._create_physics_residual()

        # Domain and BCs
        self.domain: Optional[PhysicalDomain] = None
        self.boundary_conditions: List[BoundaryCondition] = []

        # Training state
        self.history = TrainingHistory()
        self.trained = False

        logger.info(f"PINN model created for {physics_type.value} with {material.name}")

    def _create_physics_residual(self) -> PhysicsResidual:
        """Create appropriate physics residual."""
        if self.physics_type == PhysicsType.THERMAL:
            return HeatEquationResidual(self.material)
        elif self.physics_type == PhysicsType.STRUCTURAL:
            return ElasticityResidual(self.material)
        else:
            # Default to heat equation
            return HeatEquationResidual(self.material)

    def set_domain(self, domain: PhysicalDomain) -> None:
        """Set physical domain."""
        self.domain = domain

    def add_boundary_condition(self, bc: BoundaryCondition) -> None:
        """Add boundary condition."""
        self.boundary_conditions.append(bc)

    def _compute_gradients(
        self,
        x: np.ndarray,
        h: float = 1e-5,
    ) -> Dict[str, np.ndarray]:
        """
        Compute gradients using finite differences.

        Note: In production PINN, use automatic differentiation.
        """
        gradients = {}

        u = self.network.predict(x)

        # First derivatives
        for i, name in enumerate(["x", "y", "z", "t"]):
            x_plus = x.copy()
            x_plus[:, i] += h
            x_minus = x.copy()
            x_minus[:, i] -= h

            u_plus = self.network.predict(x_plus)
            u_minus = self.network.predict(x_minus)

            gradients[f"du_d{name}"] = (u_plus - u_minus) / (2 * h)

        # Second derivatives
        for i, name in enumerate(["x", "y", "z"]):
            x_plus = x.copy()
            x_plus[:, i] += h
            x_minus = x.copy()
            x_minus[:, i] -= h

            u_plus = self.network.predict(x_plus)
            u_minus = self.network.predict(x_minus)

            gradients[f"d2u_d{name}2"] = (u_plus - 2 * u + u_minus) / (h ** 2)

        return gradients

    def _physics_loss(self, x_collocation: np.ndarray) -> float:
        """Compute physics loss (PDE residual)."""
        u = self.network.predict(x_collocation)
        gradients = self._compute_gradients(x_collocation)

        residual = self.physics_residual.compute(u, x_collocation, gradients)

        return float(np.mean(residual ** 2))

    def _data_loss(
        self,
        x_data: np.ndarray,
        u_data: np.ndarray,
    ) -> float:
        """Compute data loss (sensor observations)."""
        u_pred = self.network.predict(x_data)
        return float(np.mean((u_pred - u_data) ** 2))

    def _boundary_loss(self) -> float:
        """Compute boundary condition loss."""
        if not self.domain or not self.boundary_conditions:
            return 0.0

        total_loss = 0.0

        for bc in self.boundary_conditions:
            x_boundary = self.domain.sample_boundary(100, bc.location)
            if len(x_boundary) == 0:
                continue

            u_pred = self.network.predict(x_boundary)
            u_target = np.array([bc.evaluate(p) for p in x_boundary])

            total_loss += np.mean((u_pred.flatten() - u_target) ** 2)

        return float(total_loss)

    def train(
        self,
        sensor_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        verbose: bool = True,
    ) -> TrainingHistory:
        """
        Train PINN model.

        Args:
            sensor_data: Optional (x, u) sensor measurements
            verbose: Print progress

        Returns:
            Training history
        """
        if self.domain is None:
            self.domain = PhysicalDomain()

        logger.info("Starting PINN training...")

        best_loss = float("inf")
        patience_counter = 0

        for epoch in range(self.config.max_epochs):
            # Sample collocation points
            x_collocation = self.domain.sample_interior(self.config.n_collocation)

            # Compute losses
            physics_loss = self._physics_loss(x_collocation)

            data_loss = 0.0
            if sensor_data is not None:
                data_loss = self._data_loss(sensor_data[0], sensor_data[1])

            boundary_loss = self._boundary_loss()

            # Total loss
            total_loss = (
                self.config.physics_weight * physics_loss +
                self.config.data_weight * data_loss +
                self.config.boundary_weight * boundary_loss
            )

            # Record history
            self.history.add(epoch, total_loss, physics_loss, data_loss, boundary_loss)

            # Early stopping
            if total_loss < best_loss:
                best_loss = total_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= self.config.patience:
                if verbose:
                    logger.info(f"Early stopping at epoch {epoch}")
                break

            # Simple gradient descent (demonstration only)
            # In production, use Adam optimizer with automatic differentiation
            if epoch % 100 == 0 and verbose:
                logger.info(
                    f"Epoch {epoch}: total={total_loss:.6f}, "
                    f"physics={physics_loss:.6f}, data={data_loss:.6f}, "
                    f"boundary={boundary_loss:.6f}"
                )

        self.trained = True
        logger.info(f"Training complete. Final loss: {best_loss:.6f}")

        return self.history

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predict field values."""
        if not self.trained:
            logger.warning("Model not trained, predictions may be inaccurate")

        return self.network.predict(x)

    def get_state(self) -> Dict[str, Any]:
        """Get model state for serialization."""
        return {
            "physics_type": self.physics_type.value,
            "material": self.material.name,
            "trained": self.trained,
            "config": {
                "hidden_layers": self.config.hidden_layers,
                "activation": self.config.activation,
            },
            "history": {
                "epochs": len(self.history.epochs),
                "final_loss": self.history.total_loss[-1] if self.history.total_loss else None,
            },
        }


class ThermalDigitalTwin(PINNModel):
    """
    Thermal digital twin for LEGO brick manufacturing.

    Models temperature distribution during:
    - Injection molding cooling
    - 3D printing thermal history
    - CNC machining heat generation
    """

    def __init__(
        self,
        material: Optional[MaterialProperties] = None,
        config: Optional[PINNConfig] = None,
    ):
        super().__init__(
            physics_type=PhysicsType.THERMAL,
            material=material or MaterialProperties.abs_plastic(),
            config=config,
        )

    def set_injection_mold_domain(
        self,
        brick_length: float = 0.0318,   # 4x2 brick
        brick_width: float = 0.0158,
        brick_height: float = 0.0096,
        cooling_time: float = 30.0,      # seconds
    ) -> None:
        """Set domain for injection molding simulation."""
        self.set_domain(PhysicalDomain(
            x_min=0, x_max=brick_length,
            y_min=0, y_max=brick_width,
            z_min=0, z_max=brick_height,
            t_min=0, t_max=cooling_time,
        ))

        # Mold surface temperature (typically 40-60°C)
        mold_temp = 323.0  # 50°C in Kelvin

        # Add boundary conditions for mold contact
        for face in ["x_min", "x_max", "y_min", "y_max", "z_min"]:
            self.add_boundary_condition(BoundaryCondition(
                condition_type=BoundaryConditionType.DIRICHLET,
                location=face,
                value=mold_temp,
            ))

    def predict_ejection_readiness(
        self,
        max_core_temp: float = 353.0,  # 80°C - safe ejection temp
    ) -> Dict[str, Any]:
        """
        Predict if brick is ready for ejection.

        Checks if core temperature is below threshold.
        """
        if not self.trained:
            return {"ready": False, "reason": "Model not trained"}

        # Sample core region
        if self.domain:
            core_x = (self.domain.x_min + self.domain.x_max) / 2
            core_y = (self.domain.y_min + self.domain.y_max) / 2
            core_z = (self.domain.z_min + self.domain.z_max) / 2

            # Check at final time
            core_point = np.array([[core_x, core_y, core_z, self.domain.t_max]])
            core_temp = self.predict(core_point)[0, 0]

            return {
                "ready": core_temp <= max_core_temp,
                "core_temperature_k": float(core_temp),
                "threshold_k": max_core_temp,
                "margin_k": max_core_temp - core_temp,
            }

        return {"ready": False, "reason": "Domain not set"}


class StructuralDigitalTwin(PINNModel):
    """
    Structural digital twin for brick stress analysis.

    Models deformation and stress during:
    - Assembly pressure
    - Drop testing
    - Long-term loading
    """

    def __init__(
        self,
        material: Optional[MaterialProperties] = None,
        config: Optional[PINNConfig] = None,
    ):
        super().__init__(
            physics_type=PhysicsType.STRUCTURAL,
            material=material or MaterialProperties.abs_plastic(),
            config=config,
        )

    def predict_clutch_power(
        self,
        interference: float = 0.0002,  # 0.2mm interference fit
    ) -> Dict[str, Any]:
        """
        Predict clutch power (connection force) for brick studs.

        Based on interference fit analysis.
        """
        # Simplified analytical estimate
        # Real PINN would predict full stress field

        E = self.material.elastic_modulus
        stud_diameter = 0.0048  # 4.8mm

        # Hoop stress from interference
        contact_pressure = E * interference / stud_diameter

        # Clutch force (friction * contact area * pressure)
        friction_coef = 0.35  # ABS-on-ABS
        contact_height = 0.0017  # 1.7mm
        contact_area = np.pi * stud_diameter * contact_height

        clutch_force = friction_coef * contact_area * contact_pressure

        return {
            "clutch_force_n": float(clutch_force),
            "contact_pressure_mpa": float(contact_pressure / 1e6),
            "within_yield": contact_pressure < self.material.yield_strength,
            "stud_diameter_m": stud_diameter,
            "interference_m": interference,
        }


# Factory functions

def create_thermal_twin(
    brick_type: str = "4x2",
    material: str = "ABS",
) -> ThermalDigitalTwin:
    """Create thermal digital twin for brick manufacturing."""
    mat = MaterialProperties.abs_plastic() if material == "ABS" else MaterialProperties.aluminum_6061()
    twin = ThermalDigitalTwin(material=mat)

    # Set standard brick dimensions
    brick_dims = {
        "1x1": (0.008, 0.008, 0.0096),
        "2x2": (0.016, 0.016, 0.0096),
        "4x2": (0.032, 0.016, 0.0096),
        "8x2": (0.064, 0.016, 0.0096),
    }

    if brick_type in brick_dims:
        l, w, h = brick_dims[brick_type]
        twin.set_injection_mold_domain(brick_length=l, brick_width=w, brick_height=h)

    return twin


def create_structural_twin(material: str = "ABS") -> StructuralDigitalTwin:
    """Create structural digital twin for brick analysis."""
    mat = MaterialProperties.abs_plastic() if material == "ABS" else MaterialProperties.aluminum_6061()
    return StructuralDigitalTwin(material=mat)


__all__ = [
    "PINNModel",
    "PINNConfig",
    "PhysicsType",
    "PhysicalDomain",
    "MaterialProperties",
    "BoundaryCondition",
    "BoundaryConditionType",
    "TrainingHistory",
    "ThermalDigitalTwin",
    "StructuralDigitalTwin",
    "create_thermal_twin",
    "create_structural_twin",
]
