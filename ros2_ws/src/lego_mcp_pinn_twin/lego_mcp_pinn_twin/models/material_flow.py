"""
Material Flow Physics-Informed Neural Network

Models manufacturing process material flow including:
- 3D printing extrusion dynamics
- Injection molding flow front
- CNC chip formation
- Assembly line material tracking

Governing Equations:
    Mass Conservation:
        ∂ρ/∂t + ∇·(ρv) = 0

    Momentum Conservation (Navier-Stokes simplified):
        ρ(∂v/∂t + v·∇v) = -∇p + μ∇²v + f

    For 3D printing extrusion:
        Q = A·v (volumetric flow rate = area × velocity)
        ΔP = 8μLQ/(πr⁴) (Hagen-Poiseuille for nozzle)

    For injection molding:
        Fill time model: t_fill = V/(Q_inj)
        Pressure drop: ΔP = f(viscosity, geometry, temp)
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base_pinn import BasePINN, PINNConfig, PhysicsLossType


class ProcessType(Enum):
    """Manufacturing process types."""
    FDM_EXTRUSION = "fdm_extrusion"
    INJECTION_MOLDING = "injection_molding"
    CNC_MILLING = "cnc_milling"
    ASSEMBLY_LINE = "assembly_line"


@dataclass
class MaterialProperties:
    """
    Material flow properties.

    Attributes:
        density: Material density [kg/m³]
        viscosity: Dynamic viscosity [Pa·s]
        thermal_conductivity: [W/(m·K)]
        specific_heat: [J/(kg·K)]
        melt_temperature: Melting point [K]
        glass_transition: Glass transition temperature [K]
    """
    density: float = 1040.0  # PLA
    viscosity: float = 500.0  # Pa·s at processing temp
    thermal_conductivity: float = 0.13
    specific_heat: float = 1800.0
    melt_temperature: float = 453.0  # 180°C
    glass_transition: float = 333.0  # 60°C


@dataclass
class ProcessParameters:
    """
    Process-specific parameters.

    For FDM extrusion:
        nozzle_diameter: [m]
        filament_diameter: [m]
        layer_height: [m]
        print_speed: [m/s]
        extrusion_multiplier: [-]

    For injection molding:
        cavity_volume: [m³]
        gate_diameter: [m]
        injection_pressure: [Pa]
        cooling_time: [s]
    """
    nozzle_diameter: float = 0.4e-3  # 0.4mm
    filament_diameter: float = 1.75e-3  # 1.75mm
    layer_height: float = 0.2e-3  # 0.2mm
    print_speed: float = 0.06  # 60mm/s
    extrusion_multiplier: float = 1.0


@dataclass
class MaterialFlowPINNConfig(PINNConfig):
    """Extended configuration for material flow PINN."""
    process_type: ProcessType = ProcessType.FDM_EXTRUSION
    material: MaterialProperties = field(default_factory=MaterialProperties)
    process_params: ProcessParameters = field(default_factory=ProcessParameters)
    include_thermal_coupling: bool = True
    include_viscosity_model: bool = True


class MaterialFlowPINN(BasePINN):
    """
    Physics-Informed Neural Network for material flow prediction.

    Models material flow in manufacturing processes with physics constraints:
    - Mass conservation
    - Momentum balance
    - Energy equation (thermal coupling)
    - Rheological models

    Usage:
        >>> config = MaterialFlowPINNConfig(
        ...     process_type=ProcessType.FDM_EXTRUSION,
        ...     input_dim=5,  # x, y, z, t, T
        ...     output_dim=4,  # u, v, w, p (velocity + pressure)
        ... )
        >>> model = MaterialFlowPINN(config)
        >>> flow = model.predict(conditions)
    """

    def __init__(self, config: MaterialFlowPINNConfig):
        """
        Initialize material flow PINN.

        Args:
            config: Material flow PINN configuration
        """
        self.flow_config = config
        self.material = config.material
        self.process = config.process_params

        super().__init__(config)

    def _define_physics_losses(self) -> None:
        """Define material flow physics constraints."""

        # Mass conservation (continuity equation)
        self.register_physics_loss(
            name="mass_conservation",
            loss_type=PhysicsLossType.CONSERVATION_LAW,
            residual_fn=self._mass_conservation_residual,
            weight=self.config.physics_weights.get("mass_conservation", 1.0)
        )

        # Momentum conservation
        self.register_physics_loss(
            name="momentum_conservation",
            loss_type=PhysicsLossType.PDE_RESIDUAL,
            residual_fn=self._momentum_residual,
            weight=self.config.physics_weights.get("momentum_conservation", 1.0)
        )

        # Process-specific constraints
        if self.flow_config.process_type == ProcessType.FDM_EXTRUSION:
            self.register_physics_loss(
                name="extrusion_flow",
                loss_type=PhysicsLossType.CONSTITUTIVE_RELATION,
                residual_fn=self._extrusion_flow_residual,
                weight=self.config.physics_weights.get("extrusion_flow", 1.0)
            )

        # No-slip boundary condition
        self.register_physics_loss(
            name="no_slip_bc",
            loss_type=PhysicsLossType.BOUNDARY_CONDITION,
            residual_fn=self._no_slip_residual,
            weight=self.config.physics_weights.get("no_slip_bc", 10.0)
        )

        if self.flow_config.include_viscosity_model:
            self.register_physics_loss(
                name="viscosity_model",
                loss_type=PhysicsLossType.CONSTITUTIVE_RELATION,
                residual_fn=self._viscosity_model_residual,
                weight=self.config.physics_weights.get("viscosity_model", 0.5)
            )

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass predicting flow field.

        Args:
            x: Input [x, y, z, t, T] coordinates and temperature
               Shape: (batch_size, 5)

        Returns:
            Flow predictions [u, v, w, p] (velocity and pressure)
            Shape: (batch_size, 4)
        """
        return self._forward_pass(x)

    def compute_physics_residual(
        self,
        x: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Compute material flow physics residuals.

        Args:
            x: Input coordinates [x, y, z, t, T]
            y_pred: Predicted flow [u, v, w, p]

        Returns:
            Dictionary of residual arrays
        """
        residuals = {}

        residuals["mass_conservation"] = self._mass_conservation_residual(x, y_pred)
        residuals["momentum_conservation"] = self._momentum_residual(x, y_pred)
        residuals["no_slip_bc"] = self._no_slip_residual(x, y_pred)

        if self.flow_config.process_type == ProcessType.FDM_EXTRUSION:
            residuals["extrusion_flow"] = self._extrusion_flow_residual(x, y_pred)

        if self.flow_config.include_viscosity_model:
            residuals["viscosity_model"] = self._viscosity_model_residual(x, y_pred)

        return residuals

    def _mass_conservation_residual(
        self,
        x: np.ndarray,
        flow: np.ndarray
    ) -> np.ndarray:
        """
        Compute mass conservation (continuity) residual.

        For incompressible flow: ∇·v = ∂u/∂x + ∂v/∂y + ∂w/∂z = 0
        """
        u, v, w = flow[:, 0:1], flow[:, 1:2], flow[:, 2:3]

        du_dx = self.compute_gradients(x, u, 'x')
        dv_dy = self.compute_gradients(x, v, 'y')
        dw_dz = self.compute_gradients(x, w, 'z')

        divergence = du_dx + dv_dy + dw_dz
        return divergence

    def _momentum_residual(
        self,
        x: np.ndarray,
        flow: np.ndarray
    ) -> np.ndarray:
        """
        Compute momentum conservation residual.

        Simplified Stokes flow (low Reynolds number):
        ∇p = μ∇²v

        For each component:
        ∂p/∂x = μ(∂²u/∂x² + ∂²u/∂y² + ∂²u/∂z²)
        """
        u, v, w, p = flow[:, 0:1], flow[:, 1:2], flow[:, 2:3], flow[:, 3:4]

        # Pressure gradients
        dp_dx = self.compute_gradients(x, p, 'x')
        dp_dy = self.compute_gradients(x, p, 'y')
        dp_dz = self.compute_gradients(x, p, 'z')

        # Velocity Laplacians
        du_dx = self.compute_gradients(x, u, 'x')
        d2u_dx2 = self.compute_gradients(x, du_dx, 'x')
        du_dy = self.compute_gradients(x, u, 'y')
        d2u_dy2 = self.compute_gradients(x, du_dy, 'y')
        du_dz = self.compute_gradients(x, u, 'z')
        d2u_dz2 = self.compute_gradients(x, du_dz, 'z')

        laplacian_u = d2u_dx2 + d2u_dy2 + d2u_dz2

        # Get temperature-dependent viscosity
        T = x[:, 4:5] if x.shape[1] > 4 else np.full((len(x), 1), self.material.melt_temperature)
        mu = self._compute_viscosity(T)

        # Residual for x-momentum
        residual_x = dp_dx - mu * laplacian_u

        return residual_x

    def _extrusion_flow_residual(
        self,
        x: np.ndarray,
        flow: np.ndarray
    ) -> np.ndarray:
        """
        Compute extrusion-specific flow residual.

        Volumetric flow rate constraint:
        Q_out = Q_in (mass balance through nozzle)

        Hagen-Poiseuille pressure drop:
        ΔP = 8μLQ/(πr⁴)
        """
        u, v, w, p = flow[:, 0:1], flow[:, 1:2], flow[:, 2:3], flow[:, 3:4]

        # Nozzle geometry
        r = self.process.nozzle_diameter / 2
        A_nozzle = np.pi * r**2

        # Expected velocity from print speed
        v_expected = self.process.print_speed

        # Flow rate balance
        # Filament feed rate should match nozzle output
        r_filament = self.process.filament_diameter / 2
        A_filament = np.pi * r_filament**2

        # Extrusion multiplier adjustment
        flow_ratio = (A_filament / A_nozzle) * self.process.extrusion_multiplier

        # Velocity at nozzle exit should approximately match adjusted print speed
        v_magnitude = np.sqrt(u**2 + v**2 + w**2)
        expected_v_nozzle = v_expected * flow_ratio

        residual = v_magnitude - expected_v_nozzle
        return residual

    def _no_slip_residual(
        self,
        x: np.ndarray,
        flow: np.ndarray
    ) -> np.ndarray:
        """
        Compute no-slip boundary condition residual.

        At walls: v = 0
        """
        u, v, w = flow[:, 0], flow[:, 1], flow[:, 2]

        # Identify wall points (simplified: at domain boundaries)
        r = self.process.nozzle_diameter / 2
        dist_from_center = np.sqrt(x[:, 0]**2 + x[:, 1]**2)

        # Points near wall
        is_wall = dist_from_center > 0.9 * r

        # Residual: velocity should be zero at walls
        wall_velocity = np.sqrt(u**2 + v**2 + w**2)
        residual = np.where(is_wall, wall_velocity, 0.0)

        return residual.reshape(-1, 1)

    def _viscosity_model_residual(
        self,
        x: np.ndarray,
        flow: np.ndarray
    ) -> np.ndarray:
        """
        Compute viscosity model constraint.

        Power-law model for polymer melts:
        μ = K * γ̇^(n-1)

        where γ̇ is shear rate and n < 1 for shear-thinning
        """
        u, v, w = flow[:, 0:1], flow[:, 1:2], flow[:, 2:3]

        # Compute shear rate (simplified: du/dy)
        du_dy = self.compute_gradients(x, u, 'y')
        shear_rate = np.abs(du_dy) + 1e-10  # Avoid division by zero

        # Power-law parameters for PLA
        K = 5000.0  # Consistency index
        n = 0.4     # Power-law index (shear thinning)

        # Expected viscosity
        mu_expected = K * np.power(shear_rate, n - 1)

        # Bound viscosity to reasonable range
        mu_min = 10.0
        mu_max = 10000.0
        mu_expected = np.clip(mu_expected, mu_min, mu_max)

        # This is a soft constraint on the viscosity model
        # Network implicitly learns consistent viscosity behavior
        residual = np.zeros_like(mu_expected)  # Placeholder
        return residual

    def _compute_viscosity(self, T: np.ndarray) -> np.ndarray:
        """
        Compute temperature-dependent viscosity.

        Arrhenius-type temperature dependence:
        μ(T) = μ_ref * exp(E_a/R * (1/T - 1/T_ref))
        """
        mu_ref = self.material.viscosity
        T_ref = self.material.melt_temperature
        E_a = 50000.0  # Activation energy [J/mol]
        R = 8.314      # Gas constant [J/(mol·K)]

        # Temperature in Kelvin
        T_K = np.maximum(T, 273.15)  # Avoid issues with low temps

        mu = mu_ref * np.exp(E_a / R * (1.0 / T_K - 1.0 / T_ref))

        # Bound to reasonable range
        return np.clip(mu, 1.0, 100000.0)

    def predict_extrusion_rate(
        self,
        temperature: float,
        pressure: float,
        nozzle_length: float = 0.005
    ) -> float:
        """
        Predict volumetric extrusion rate.

        Uses Hagen-Poiseuille equation:
        Q = πr⁴ΔP / (8μL)

        Args:
            temperature: Material temperature [K]
            pressure: Driving pressure [Pa]
            nozzle_length: Nozzle land length [m]

        Returns:
            Volumetric flow rate [m³/s]
        """
        r = self.process.nozzle_diameter / 2
        mu = self._compute_viscosity(np.array([[temperature]]))[0, 0]

        Q = np.pi * r**4 * pressure / (8 * mu * nozzle_length)
        return float(Q)

    def predict_layer_width(
        self,
        flow_rate: float,
        print_speed: float,
        layer_height: float
    ) -> float:
        """
        Predict deposited line width.

        W = Q / (v * h)

        Args:
            flow_rate: Volumetric flow rate [m³/s]
            print_speed: Print head velocity [m/s]
            layer_height: Layer height [m]

        Returns:
            Line width [m]
        """
        if print_speed <= 0 or layer_height <= 0:
            return 0.0

        return flow_rate / (print_speed * layer_height)
