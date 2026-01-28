"""
Equipment Degradation Physics-Informed Neural Network

Models equipment wear and degradation for predictive maintenance:
- Bearing wear and fatigue
- Tool wear in CNC machining
- Nozzle wear in 3D printing
- Motor degradation
- Belt/pulley wear

Governing Equations:
    Paris Law (Fatigue Crack Growth):
        da/dN = C * (ΔK)^m

    Archard Wear Law:
        V = K * F * s / H

    where:
        a: Crack length
        N: Number of cycles
        ΔK: Stress intensity factor range
        V: Wear volume
        K: Wear coefficient
        F: Normal force
        s: Sliding distance
        H: Hardness

    Remaining Useful Life (RUL):
        RUL = f(degradation_state, operating_conditions, historical_data)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_pinn import BasePINN, PINNConfig, PhysicsLossType


class DegradationMode(Enum):
    """Types of degradation mechanisms."""
    WEAR = "wear"
    FATIGUE = "fatigue"
    CORROSION = "corrosion"
    THERMAL = "thermal"
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"


class ComponentType(Enum):
    """Equipment component types."""
    BEARING = "bearing"
    MOTOR = "motor"
    TOOL = "tool"
    NOZZLE = "nozzle"
    BELT = "belt"
    GEARBOX = "gearbox"
    LINEAR_GUIDE = "linear_guide"


@dataclass
class ComponentProperties:
    """
    Component material and design properties.

    Attributes:
        component_type: Type of component
        material_hardness: Vickers hardness [HV]
        fatigue_limit: Fatigue limit stress [Pa]
        design_life: Design life [hours or cycles]
        failure_threshold: Degradation level at failure (0-1)
    """
    component_type: ComponentType = ComponentType.BEARING
    material_hardness: float = 700.0  # HV
    fatigue_limit: float = 300e6  # Pa
    design_life: float = 20000.0  # hours
    failure_threshold: float = 0.8


@dataclass
class OperatingConditions:
    """
    Operating conditions affecting degradation.

    Attributes:
        load: Applied load [N]
        speed: Operating speed [rpm or m/s]
        temperature: Operating temperature [K]
        humidity: Relative humidity (0-1)
        contamination_level: Contamination (0-1)
    """
    load: float = 100.0
    speed: float = 1000.0
    temperature: float = 323.15  # 50°C
    humidity: float = 0.5
    contamination_level: float = 0.1


@dataclass
class DegradationPINNConfig(PINNConfig):
    """Extended configuration for degradation PINN."""
    component: ComponentProperties = field(default_factory=ComponentProperties)
    degradation_modes: List[DegradationMode] = field(
        default_factory=lambda: [DegradationMode.WEAR, DegradationMode.FATIGUE]
    )
    include_uncertainty: bool = True
    ensemble_size: int = 5


class DegradationPINN(BasePINN):
    """
    Physics-Informed Neural Network for equipment degradation prediction.

    Combines physics-based degradation models with learned corrections:
    - Wear progression based on Archard's law
    - Fatigue accumulation based on Miner's rule
    - Thermal degradation effects
    - Operating condition impacts

    Outputs:
    - Current health index (0=new, 1=failed)
    - Remaining useful life (RUL) prediction
    - Degradation rate
    - Uncertainty quantification

    Usage:
        >>> config = DegradationPINNConfig(
        ...     component=ComponentProperties(component_type=ComponentType.BEARING),
        ... )
        >>> model = DegradationPINN(config)
        >>> health, rul = model.predict_health(operating_history)
    """

    def __init__(self, config: DegradationPINNConfig):
        """
        Initialize degradation PINN.

        Args:
            config: Degradation PINN configuration
        """
        self.deg_config = config
        self.component = config.component

        # Input: time, load, speed, temp, humidity, contamination
        config.input_dim = 6
        # Output: health_index, rul, degradation_rate, uncertainty
        config.output_dim = 4

        # Create ensemble for uncertainty
        self._ensemble: List[BasePINN] = []

        super().__init__(config)

    def _define_physics_losses(self) -> None:
        """Define degradation physics constraints."""

        # Wear law constraint
        if DegradationMode.WEAR in self.deg_config.degradation_modes:
            self.register_physics_loss(
                name="archard_wear",
                loss_type=PhysicsLossType.ODE_RESIDUAL,
                residual_fn=self._archard_wear_residual,
                weight=self.config.physics_weights.get("archard_wear", 1.0)
            )

        # Fatigue accumulation constraint
        if DegradationMode.FATIGUE in self.deg_config.degradation_modes:
            self.register_physics_loss(
                name="fatigue_accumulation",
                loss_type=PhysicsLossType.ODE_RESIDUAL,
                residual_fn=self._fatigue_residual,
                weight=self.config.physics_weights.get("fatigue_accumulation", 1.0)
            )

        # Monotonicity constraint (degradation only increases)
        self.register_physics_loss(
            name="monotonicity",
            loss_type=PhysicsLossType.CONSTITUTIVE_RELATION,
            residual_fn=self._monotonicity_residual,
            weight=self.config.physics_weights.get("monotonicity", 10.0)
        )

        # Health index bounds
        self.register_physics_loss(
            name="health_bounds",
            loss_type=PhysicsLossType.BOUNDARY_CONDITION,
            residual_fn=self._health_bounds_residual,
            weight=self.config.physics_weights.get("health_bounds", 10.0)
        )

        # RUL positivity
        self.register_physics_loss(
            name="rul_positivity",
            loss_type=PhysicsLossType.BOUNDARY_CONDITION,
            residual_fn=self._rul_positivity_residual,
            weight=self.config.physics_weights.get("rul_positivity", 10.0)
        )

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass predicting degradation state.

        Args:
            x: Input [time, load, speed, temp, humidity, contamination]
               Shape: (batch_size, 6)

        Returns:
            Predictions [health_index, rul, degradation_rate, uncertainty]
            Shape: (batch_size, 4)
        """
        output = self._forward_pass(x)

        # Apply constraints to output
        health = self._sigmoid(output[:, 0:1])  # Bound to [0, 1]
        rul = np.maximum(0, output[:, 1:2])     # Non-negative
        rate = np.maximum(0, output[:, 2:3])    # Non-negative
        uncertainty = np.abs(output[:, 3:4])    # Non-negative

        return np.concatenate([health, rul, rate, uncertainty], axis=1)

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        """Sigmoid activation for bounded output."""
        return 1.0 / (1.0 + np.exp(-x))

    def compute_physics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Compute degradation physics residuals.

        Args:
            x: Input conditions
            y_pred: Predicted [health, rul, rate, uncertainty]

        Returns:
            Dictionary of residual arrays
        """
        residuals = {}

        if DegradationMode.WEAR in self.deg_config.degradation_modes:
            residuals["archard_wear"] = self._archard_wear_residual(x, y_pred)

        if DegradationMode.FATIGUE in self.deg_config.degradation_modes:
            residuals["fatigue_accumulation"] = self._fatigue_residual(x, y_pred)

        residuals["monotonicity"] = self._monotonicity_residual(x, y_pred)
        residuals["health_bounds"] = self._health_bounds_residual(x, y_pred)
        residuals["rul_positivity"] = self._rul_positivity_residual(x, y_pred)

        return residuals

    def _archard_wear_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute Archard wear law residual.

        dV/dt = K * F * v / H

        where:
            V: Wear volume (related to health degradation)
            K: Wear coefficient
            F: Load
            v: Sliding velocity
            H: Hardness
        """
        time = x[:, 0:1]
        load = x[:, 1:2]
        speed = x[:, 2:3]

        health = y_pred[:, 0:1]
        rate = y_pred[:, 2:3]

        # Wear coefficient (typical values 1e-4 to 1e-6)
        K = 1e-5

        # Expected wear rate from Archard's law
        # Convert speed from rpm to m/s for bearing (assume 0.01m radius)
        v = speed * 2 * np.pi * 0.01 / 60.0
        H = self.component.material_hardness * 9.81e6  # Convert HV to Pa

        expected_rate = K * load * v / H

        # Scale to health index degradation rate
        # Assume failure threshold corresponds to certain wear volume
        health_rate = expected_rate / self.component.failure_threshold

        # Residual
        residual = rate - health_rate
        return residual

    def _fatigue_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Compute fatigue accumulation residual.

        Miner's rule: D = Σ(n_i / N_i)

        where:
            D: Damage accumulation (failure at D = 1)
            n_i: Cycles at stress level i
            N_i: Cycles to failure at stress level i
        """
        time = x[:, 0:1]
        load = x[:, 1:2]
        speed = x[:, 2:3]

        health = y_pred[:, 0:1]

        # Cycles per unit time
        cycles_per_second = speed / 60.0

        # S-N curve parameters (Basquin's equation)
        # N = C * S^(-b)
        C = 1e12
        b = 5.0

        # Stress from load (simplified)
        stress = load * 1e6  # Scale to Pa

        # Cycles to failure at this stress
        if self.component.fatigue_limit > 0:
            # Below fatigue limit: infinite life
            N_f = np.where(
                stress < self.component.fatigue_limit,
                np.inf,
                C * np.power(stress, -b)
            )
        else:
            N_f = C * np.power(stress + 1e-10, -b)

        # Damage rate
        damage_rate = cycles_per_second / N_f

        # Compare to actual degradation rate
        actual_rate = self.compute_gradients(x, health, 't')

        residual = actual_rate - damage_rate
        return residual

    def _monotonicity_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Enforce monotonic degradation (health only decreases).

        dH/dt <= 0 (or equivalently, degradation rate >= 0)
        """
        health = y_pred[:, 0:1]

        # Compute time derivative
        dH_dt = self.compute_gradients(x, health, 't')

        # Penalize positive derivatives (health increase)
        residual = np.maximum(0, dH_dt)
        return residual

    def _health_bounds_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Enforce health index bounds [0, 1].
        """
        health = y_pred[:, 0:1]

        below = np.maximum(0, -health)
        above = np.maximum(0, health - 1.0)

        return below + above

    def _rul_positivity_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> np.ndarray:
        """
        Enforce non-negative RUL.
        """
        rul = y_pred[:, 1:2]
        return np.maximum(0, -rul)

    def predict_health(
        self,
        operating_conditions: OperatingConditions,
        operating_hours: float
    ) -> Tuple[float, float, float]:
        """
        Predict current health state.

        Args:
            operating_conditions: Current operating conditions
            operating_hours: Total operating hours

        Returns:
            Tuple of (health_index, rul_hours, degradation_rate)
        """
        x = np.array([[
            operating_hours,
            operating_conditions.load,
            operating_conditions.speed,
            operating_conditions.temperature,
            operating_conditions.humidity,
            operating_conditions.contamination_level
        ]])

        output = self.forward(x)

        health_index = float(output[0, 0])
        rul = float(output[0, 1])
        rate = float(output[0, 2])

        return health_index, rul, rate

    def predict_rul(
        self,
        operating_history: np.ndarray,
        future_conditions: OperatingConditions
    ) -> Tuple[float, float]:
        """
        Predict remaining useful life.

        Args:
            operating_history: Historical operating data
                Shape: (num_timesteps, 6)
            future_conditions: Expected future operating conditions

        Returns:
            Tuple of (rul_mean, rul_std)
        """
        # Get current state from history
        current_state = self.forward(operating_history[-1:])
        current_health = current_state[0, 0]

        # Predict future degradation
        # Use current rate to extrapolate
        rate = current_state[0, 2]

        # RUL = (failure_threshold - current_health) / rate
        if rate > 1e-10:
            rul_mean = (self.component.failure_threshold - current_health) / rate
        else:
            rul_mean = self.component.design_life

        # Uncertainty from network
        uncertainty = current_state[0, 3]
        rul_std = rul_mean * uncertainty

        return max(0, rul_mean), rul_std

    def compute_survival_probability(
        self,
        health_index: float,
        time_horizon: float
    ) -> float:
        """
        Compute probability of surviving to time horizon.

        Uses Weibull distribution assumption:
        R(t) = exp(-(t/η)^β)

        Args:
            health_index: Current health state
            time_horizon: Future time to evaluate

        Returns:
            Survival probability (0-1)
        """
        # Weibull parameters (can be learned or calibrated)
        beta = 2.0  # Shape parameter
        eta = self.component.design_life  # Scale parameter

        # Adjust for current health
        effective_age = health_index * eta

        # Survival probability
        R = np.exp(-((effective_age + time_horizon) / eta) ** beta)

        return float(np.clip(R, 0, 1))
