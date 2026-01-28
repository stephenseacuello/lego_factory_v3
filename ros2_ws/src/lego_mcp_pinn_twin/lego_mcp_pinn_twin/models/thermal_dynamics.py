"""
Thermal Dynamics Physics-Informed Neural Network

Models heat transfer in manufacturing equipment including:
- 3D printer hotends and heated beds
- CNC spindle thermal expansion
- Robot motor heating
- Injection mold temperature distribution

Governing Equations:
    Heat equation (transient):
        ρ * c_p * ∂T/∂t = k * ∇²T + Q

    where:
        T: Temperature field
        ρ: Density
        c_p: Specific heat capacity
        k: Thermal conductivity
        Q: Heat source term

Boundary Conditions:
    - Convective: -k * ∂T/∂n = h * (T - T_∞)
    - Radiative: -k * ∂T/∂n = ε * σ * (T⁴ - T_∞⁴)
    - Fixed temperature: T = T_boundary
"""

import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass, field

from .base_pinn import BasePINN, PINNConfig, PhysicsLossType


@dataclass
class ThermalProperties:
    """
    Material thermal properties.

    Attributes:
        density: Material density [kg/m³]
        specific_heat: Specific heat capacity [J/(kg·K)]
        thermal_conductivity: Thermal conductivity [W/(m·K)]
        convection_coefficient: Convective heat transfer coefficient [W/(m²·K)]
        emissivity: Surface emissivity for radiation (0-1)
        ambient_temperature: Ambient temperature [K]
    """
    density: float = 2700.0  # Aluminum
    specific_heat: float = 900.0
    thermal_conductivity: float = 205.0
    convection_coefficient: float = 10.0
    emissivity: float = 0.3
    ambient_temperature: float = 293.15  # 20°C


@dataclass
class ThermalPINNConfig(PINNConfig):
    """Extended configuration for thermal PINN."""
    thermal_properties: ThermalProperties = field(default_factory=ThermalProperties)
    include_radiation: bool = False
    include_convection: bool = True
    steady_state: bool = False


class ThermalDynamicsPINN(BasePINN):
    """
    Physics-Informed Neural Network for thermal dynamics.

    Models transient and steady-state heat transfer with:
    - Heat diffusion (conduction)
    - Convective boundary conditions
    - Optional radiative heat transfer
    - Heat source terms

    Usage:
        >>> config = ThermalPINNConfig(
        ...     input_dim=4,  # x, y, z, t
        ...     output_dim=1,  # Temperature
        ...     hidden_layers=[64, 64, 64],
        ... )
        >>> model = ThermalDynamicsPINN(config)
        >>> T_pred = model.predict(coordinates)
    """

    def __init__(self, config: ThermalPINNConfig):
        """
        Initialize thermal dynamics PINN.

        Args:
            config: Thermal PINN configuration
        """
        self.thermal_config = config
        self.props = config.thermal_properties

        # Compute thermal diffusivity α = k / (ρ * c_p)
        self.thermal_diffusivity = (
            self.props.thermal_conductivity /
            (self.props.density * self.props.specific_heat)
        )

        super().__init__(config)

    def _define_physics_losses(self) -> None:
        """Define thermal physics constraints."""

        # Heat equation residual
        self.register_physics_loss(
            name="heat_equation",
            loss_type=PhysicsLossType.PDE_RESIDUAL,
            residual_fn=self._heat_equation_residual,
            weight=self.config.physics_weights.get("heat_equation", 1.0)
        )

        # Energy conservation
        self.register_physics_loss(
            name="energy_conservation",
            loss_type=PhysicsLossType.CONSERVATION_LAW,
            residual_fn=self._energy_conservation_residual,
            weight=self.config.physics_weights.get("energy_conservation", 0.1)
        )

        # Temperature positivity (thermodynamic constraint)
        self.register_physics_loss(
            name="temperature_positivity",
            loss_type=PhysicsLossType.CONSTITUTIVE_RELATION,
            residual_fn=self._temperature_positivity_residual,
            weight=self.config.physics_weights.get("temperature_positivity", 10.0)
        )

        if self.thermal_config.include_convection:
            self.register_physics_loss(
                name="convection_bc",
                loss_type=PhysicsLossType.BOUNDARY_CONDITION,
                residual_fn=self._convection_bc_residual,
                weight=self.config.physics_weights.get("convection_bc", 0.5)
            )

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass predicting temperature field.

        Args:
            x: Input array of shape (batch_size, 4) containing [x, y, z, t]

        Returns:
            Temperature predictions of shape (batch_size, 1)
        """
        # Standard forward pass with temperature scaling
        T_normalized = self._forward_pass(x)

        # De-normalize to physical temperature
        # Assume network outputs normalized temperature [0, 1] -> [T_min, T_max]
        T_min = 273.15  # 0°C
        T_max = 573.15  # 300°C
        T = T_normalized * (T_max - T_min) + T_min

        return T

    def compute_physics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Compute thermal physics residuals.

        Args:
            x: Input coordinates [x, y, z, t]
            y_pred: Predicted temperature

        Returns:
            Dictionary of residual arrays
        """
        residuals = {}

        # Heat equation residual
        residuals["heat_equation"] = self._heat_equation_residual(x, y_pred)

        # Energy conservation
        residuals["energy_conservation"] = self._energy_conservation_residual(x, y_pred)

        # Temperature positivity
        residuals["temperature_positivity"] = self._temperature_positivity_residual(x, y_pred)

        # Convection BC if enabled
        if self.thermal_config.include_convection:
            residuals["convection_bc"] = self._convection_bc_residual(x, y_pred)

        return residuals

    def _heat_equation_residual(
        self,
        x: np.ndarray,
        T: np.ndarray
    ) -> np.ndarray:
        """
        Compute heat equation residual.

        Heat equation: ∂T/∂t = α * ∇²T
        Residual should be zero when equation is satisfied.

        Args:
            x: Coordinates [x, y, z, t]
            T: Temperature predictions

        Returns:
            Residual array
        """
        # Compute derivatives
        dT_dt = self.compute_gradients(x, T, 't')
        dT_dx = self.compute_gradients(x, T, 'x')
        dT_dy = self.compute_gradients(x, T, 'y')
        dT_dz = self.compute_gradients(x, T, 'z')

        # Second derivatives (Laplacian)
        d2T_dx2 = self.compute_gradients(x, dT_dx, 'x')
        d2T_dy2 = self.compute_gradients(x, dT_dy, 'y')
        d2T_dz2 = self.compute_gradients(x, dT_dz, 'z')

        laplacian_T = d2T_dx2 + d2T_dy2 + d2T_dz2

        # Heat equation residual
        if self.thermal_config.steady_state:
            # Steady state: ∇²T = 0
            residual = laplacian_T
        else:
            # Transient: ∂T/∂t - α * ∇²T = 0
            residual = dT_dt - self.thermal_diffusivity * laplacian_T

        return residual

    def _energy_conservation_residual(
        self,
        x: np.ndarray,
        T: np.ndarray
    ) -> np.ndarray:
        """
        Compute energy conservation residual.

        Total energy in the system should be conserved (or balance with sources/sinks).
        """
        # Simplified: check that temperature changes are bounded
        dT_dt = self.compute_gradients(x, T, 't')

        # Maximum physically reasonable rate of change
        max_rate = 100.0  # K/s

        residual = np.maximum(0, np.abs(dT_dt) - max_rate)
        return residual

    def _temperature_positivity_residual(
        self,
        x: np.ndarray,
        T: np.ndarray
    ) -> np.ndarray:
        """
        Enforce temperature positivity (T > 0 K).

        Uses soft constraint: penalize negative temperatures.
        """
        # Temperature must be positive (above absolute zero)
        residual = np.maximum(0, -T)  # Penalize if T < 0
        return residual

    def _convection_bc_residual(
        self,
        x: np.ndarray,
        T: np.ndarray
    ) -> np.ndarray:
        """
        Compute convection boundary condition residual.

        Newton's law of cooling: -k * ∂T/∂n = h * (T - T_∞)

        For boundaries, this is applied at domain edges.
        """
        # Compute normal gradient (simplified: use x-direction as example)
        dT_dn = self.compute_gradients(x, T, 'x')

        k = self.props.thermal_conductivity
        h = self.props.convection_coefficient
        T_inf = self.props.ambient_temperature

        # Boundary condition residual
        lhs = -k * dT_dn
        rhs = h * (T - T_inf)

        residual = lhs - rhs
        return residual

    def predict_steady_state(
        self,
        coordinates: np.ndarray,
        boundary_temperatures: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """
        Predict steady-state temperature distribution.

        Args:
            coordinates: Spatial coordinates [x, y, z]
            boundary_temperatures: Optional fixed boundary temperatures

        Returns:
            Steady-state temperature field
        """
        # Add zero time to coordinates
        x = np.column_stack([coordinates, np.zeros(len(coordinates))])
        return self.forward(x)

    def predict_transient(
        self,
        coordinates: np.ndarray,
        times: np.ndarray,
        initial_temperature: float
    ) -> np.ndarray:
        """
        Predict transient temperature evolution.

        Args:
            coordinates: Spatial coordinates [x, y, z]
            times: Time points to predict
            initial_temperature: Initial temperature at t=0

        Returns:
            Temperature field over time (shape: len(coordinates) x len(times))
        """
        results = []
        for t in times:
            x = np.column_stack([coordinates, np.full(len(coordinates), t)])
            T = self.forward(x)
            results.append(T)

        return np.array(results).T

    def compute_heat_flux(
        self,
        coordinates: np.ndarray,
        direction: str = 'x'
    ) -> np.ndarray:
        """
        Compute heat flux in specified direction.

        q = -k * ∂T/∂direction

        Args:
            coordinates: Spatial coordinates with time
            direction: 'x', 'y', or 'z'

        Returns:
            Heat flux values [W/m²]
        """
        T = self.forward(coordinates)
        dT_d = self.compute_gradients(coordinates, T, direction)

        q = -self.props.thermal_conductivity * dT_d
        return q
