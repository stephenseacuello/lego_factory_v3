"""
Physics Constraints for Manufacturing Digital Twins.

This module provides physics constraints for neural network predictions:
- Thermal constraints (heat transfer, energy conservation)
- Mechanical constraints (stress equilibrium, compatibility)
- Fluid constraints (mass conservation, momentum)
- Manufacturing-specific constraints (FDM, molding)

Research Value:
- Novel constraint formulations for manufacturing
- Soft and hard constraint enforcement
- Physics-guided uncertainty quantification

References:
- Raissi, M., Perdikaris, P., Karniadakis, G.E. (2019). Physics-informed neural networks
- Karniadakis, G.E., et al. (2021). Physics-informed machine learning
- ISO 23247 Digital Twin Framework
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, Union
)
import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Physics Constraint Base Classes
# =============================================================================

class ConstraintType(Enum):
    """Types of physics constraints."""
    SOFT = auto()  # Adds penalty to loss
    HARD = auto()  # Enforced exactly through projection
    REGULARIZATION = auto()  # Regularization term


class ConstraintPriority(Enum):
    """Priority levels for constraint enforcement."""
    CRITICAL = 1  # Must be satisfied (e.g., mass conservation)
    HIGH = 2  # Should be satisfied (e.g., equilibrium)
    MEDIUM = 3  # Preferred (e.g., smoothness)
    LOW = 4  # Nice to have (e.g., regularity)


@dataclass
class ConstraintResult:
    """Result of constraint evaluation."""
    name: str
    satisfied: bool
    residual: float
    violation: float
    details: Dict[str, Any] = field(default_factory=dict)


class PhysicsConstraint(ABC):
    """
    Abstract base class for physics constraints.

    Constraints can be evaluated to compute residuals that
    are added to the training loss function.
    """

    def __init__(
        self,
        name: str,
        constraint_type: ConstraintType = ConstraintType.SOFT,
        priority: ConstraintPriority = ConstraintPriority.MEDIUM,
        weight: float = 1.0,
        tolerance: float = 1e-6
    ):
        self.name = name
        self.constraint_type = constraint_type
        self.priority = priority
        self.weight = weight
        self.tolerance = tolerance

    @abstractmethod
    def evaluate(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> ConstraintResult:
        """
        Evaluate the constraint.

        Args:
            predictions: Neural network predictions
            inputs: Input data
            context: Additional context (e.g., derivatives)

        Returns:
            ConstraintResult with residual and violation info
        """
        pass

    def compute_loss(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Compute loss term for this constraint."""
        result = self.evaluate(predictions, inputs, context)
        return self.weight * result.residual

    def project(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Project predictions to satisfy constraint (for hard constraints).

        Default implementation returns predictions unchanged.
        Override for specific projection methods.
        """
        return predictions


# =============================================================================
# Thermal Constraints
# =============================================================================

class ThermalConstraints:
    """Collection of thermal physics constraints."""

    @staticmethod
    def energy_conservation(
        weight: float = 1.0
    ) -> PhysicsConstraint:
        """
        Energy conservation constraint.

        ∂(ρ·cp·T)/∂t = -∇·q + Q
        where q = -k·∇T (Fourier's law)
        """
        class EnergyConservation(PhysicsConstraint):
            def __init__(self, weight: float):
                super().__init__(
                    name="energy_conservation",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.CRITICAL,
                    weight=weight
                )

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}
                eps = 1e-4

                T = predictions[:, 0] if predictions.ndim > 1 else predictions

                # Get derivatives from context or compute
                dT_dt = context.get('dT_dt')
                laplacian_T = context.get('laplacian_T')

                # Material properties
                alpha = context.get('thermal_diffusivity', 1.5e-7)
                Q = context.get('heat_source', 0.0)

                if dT_dt is None or laplacian_T is None:
                    # Cannot evaluate without derivatives
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing derivatives'}
                    )

                # Residual: ∂T/∂t - α·∇²T - Q = 0
                residual = dT_dt - alpha * laplacian_T - Q
                residual_norm = float(np.mean(residual ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual_norm < self.tolerance,
                    residual=residual_norm,
                    violation=float(np.max(np.abs(residual))),
                    details={
                        'mean_residual': float(np.mean(residual)),
                        'max_residual': float(np.max(np.abs(residual)))
                    }
                )

        return EnergyConservation(weight)

    @staticmethod
    def temperature_bounds(
        min_temp: float = 0.0,
        max_temp: float = 300.0,
        weight: float = 10.0
    ) -> PhysicsConstraint:
        """Constraint that temperature stays within physical bounds."""

        class TemperatureBounds(PhysicsConstraint):
            def __init__(self, min_t: float, max_t: float, w: float):
                super().__init__(
                    name="temperature_bounds",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.min_temp = min_t
                self.max_temp = max_t

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                T = predictions[:, 0] if predictions.ndim > 1 else predictions

                # Violation penalties (ReLU-like)
                lower_violation = np.maximum(0, self.min_temp - T)
                upper_violation = np.maximum(0, T - self.max_temp)

                total_violation = lower_violation + upper_violation
                residual = float(np.mean(total_violation ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(total_violation)),
                    details={
                        'n_violations': int(np.sum(total_violation > 0)),
                        'fraction_violations': float(np.mean(total_violation > 0))
                    }
                )

            def project(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> np.ndarray:
                """Project temperature to valid range."""
                result = predictions.copy()
                if predictions.ndim > 1:
                    result[:, 0] = np.clip(predictions[:, 0], self.min_temp, self.max_temp)
                else:
                    result = np.clip(predictions, self.min_temp, self.max_temp)
                return result

        return TemperatureBounds(min_temp, max_temp, weight)

    @staticmethod
    def fourier_law(weight: float = 1.0) -> PhysicsConstraint:
        """
        Fourier's law of heat conduction.

        q = -k·∇T
        """

        class FourierLaw(PhysicsConstraint):
            def __init__(self, w: float):
                super().__init__(
                    name="fourier_law",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Heat flux predictions
                q = context.get('heat_flux')
                # Temperature gradient
                grad_T = context.get('grad_T')
                # Thermal conductivity
                k = context.get('thermal_conductivity', 0.13)

                if q is None or grad_T is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing heat flux or gradient'}
                    )

                # Residual: q + k·∇T = 0
                residual = q + k * grad_T
                residual_norm = float(np.mean(residual ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual_norm < self.tolerance,
                    residual=residual_norm,
                    violation=float(np.max(np.abs(residual)))
                )

        return FourierLaw(weight)


# =============================================================================
# Mechanical Constraints
# =============================================================================

class MechanicalConstraints:
    """Collection of mechanical physics constraints."""

    @staticmethod
    def equilibrium(weight: float = 1.0) -> PhysicsConstraint:
        """
        Static equilibrium constraint.

        ∇·σ + f = 0
        """

        class Equilibrium(PhysicsConstraint):
            def __init__(self, w: float):
                super().__init__(
                    name="equilibrium",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.CRITICAL,
                    weight=w
                )

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Stress divergence
                div_sigma = context.get('div_sigma')
                # Body force
                f = context.get('body_force', np.zeros(3))

                if div_sigma is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing stress divergence'}
                    )

                # Residual: ∇·σ + f = 0
                residual = div_sigma + f
                residual_norm = float(np.mean(np.sum(residual ** 2, axis=-1)))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual_norm < self.tolerance,
                    residual=residual_norm,
                    violation=float(np.max(np.abs(residual)))
                )

        return Equilibrium(weight)

    @staticmethod
    def strain_compatibility(weight: float = 1.0) -> PhysicsConstraint:
        """
        Saint-Venant's strain compatibility equations.

        Ensures strain field is derivable from a displacement field.
        """

        class StrainCompatibility(PhysicsConstraint):
            def __init__(self, w: float):
                super().__init__(
                    name="strain_compatibility",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Strain components and their derivatives
                strain = context.get('strain')
                strain_derivatives = context.get('strain_derivatives')

                if strain is None or strain_derivatives is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing strain data'}
                    )

                # Compatibility: ∂²ε_xx/∂y² + ∂²ε_yy/∂x² = 2·∂²ε_xy/∂x∂y
                # (simplified 2D version)
                eps_xx_yy = strain_derivatives.get('eps_xx_yy', 0)
                eps_yy_xx = strain_derivatives.get('eps_yy_xx', 0)
                eps_xy_xy = strain_derivatives.get('eps_xy_xy', 0)

                residual = eps_xx_yy + eps_yy_xx - 2 * eps_xy_xy
                residual_norm = float(np.mean(residual ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual_norm < self.tolerance,
                    residual=residual_norm,
                    violation=float(np.max(np.abs(residual)))
                )

        return StrainCompatibility(weight)

    @staticmethod
    def von_mises_yield(
        yield_stress: float = 50e6,  # Pa
        weight: float = 10.0
    ) -> PhysicsConstraint:
        """
        Von Mises yield criterion constraint.

        σ_vm ≤ σ_y
        """

        class VonMisesYield(PhysicsConstraint):
            def __init__(self, sigma_y: float, w: float):
                super().__init__(
                    name="von_mises_yield",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.yield_stress = sigma_y

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Von Mises stress
                sigma_vm = context.get('von_mises_stress')

                if sigma_vm is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing von Mises stress'}
                    )

                # Violation: max(0, σ_vm - σ_y)
                violation = np.maximum(0, sigma_vm - self.yield_stress)
                residual = float(np.mean(violation ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(violation)),
                    details={
                        'max_stress': float(np.max(sigma_vm)),
                        'yield_stress': self.yield_stress,
                        'safety_factor': float(self.yield_stress / (np.max(sigma_vm) + 1e-10))
                    }
                )

        return VonMisesYield(yield_stress, weight)

    @staticmethod
    def hookes_law(
        youngs_modulus: float = 2.5e9,
        poissons_ratio: float = 0.35,
        weight: float = 1.0
    ) -> PhysicsConstraint:
        """
        Hooke's law constitutive relation.

        σ = C:ε (isotropic linear elasticity)
        """

        class HookesLaw(PhysicsConstraint):
            def __init__(self, E: float, nu: float, w: float):
                super().__init__(
                    name="hookes_law",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.CRITICAL,
                    weight=w
                )
                self.E = E
                self.nu = nu
                # Lamé parameters
                self.lam = E * nu / ((1 + nu) * (1 - 2 * nu))
                self.mu = E / (2 * (1 + nu))

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                stress = context.get('stress')
                strain = context.get('strain')

                if stress is None or strain is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing stress or strain'}
                    )

                # Compute expected stress from strain
                # σ = λ·tr(ε)·I + 2μ·ε
                trace_strain = strain[:, 0] + strain[:, 1] + strain[:, 2]

                expected_stress = np.zeros_like(stress)
                # Diagonal components
                for i in range(3):
                    expected_stress[:, i] = self.lam * trace_strain + 2 * self.mu * strain[:, i]
                # Shear components
                for i in range(3, 6):
                    expected_stress[:, i] = 2 * self.mu * strain[:, i]

                residual = stress - expected_stress
                residual_norm = float(np.mean(np.sum(residual ** 2, axis=-1)))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual_norm < self.tolerance,
                    residual=residual_norm,
                    violation=float(np.max(np.abs(residual)))
                )

        return HookesLaw(youngs_modulus, poissons_ratio, weight)


# =============================================================================
# Fluid Constraints
# =============================================================================

class FluidConstraints:
    """Collection of fluid mechanics constraints."""

    @staticmethod
    def mass_conservation(weight: float = 1.0) -> PhysicsConstraint:
        """
        Mass conservation (continuity equation).

        ∂ρ/∂t + ∇·(ρv) = 0

        For incompressible flow: ∇·v = 0
        """

        class MassConservation(PhysicsConstraint):
            def __init__(self, w: float):
                super().__init__(
                    name="mass_conservation",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.CRITICAL,
                    weight=w
                )

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Velocity divergence
                div_v = context.get('div_velocity')
                incompressible = context.get('incompressible', True)

                if div_v is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing velocity divergence'}
                    )

                if incompressible:
                    # ∇·v = 0
                    residual = float(np.mean(div_v ** 2))
                else:
                    # Would need density and time derivative
                    drho_dt = context.get('drho_dt', 0)
                    rho = context.get('density', 1000)
                    residual = float(np.mean((drho_dt + rho * div_v) ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(np.abs(div_v)))
                )

        return MassConservation(weight)

    @staticmethod
    def navier_stokes(
        density: float = 1240.0,
        viscosity: float = 1e4,
        weight: float = 1.0
    ) -> PhysicsConstraint:
        """
        Navier-Stokes momentum equation.

        ρ(∂v/∂t + v·∇v) = -∇p + μ∇²v + f
        """

        class NavierStokes(PhysicsConstraint):
            def __init__(self, rho: float, mu: float, w: float):
                super().__init__(
                    name="navier_stokes",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.rho = rho
                self.mu = mu

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Required derivatives
                dv_dt = context.get('dv_dt')
                v_grad_v = context.get('v_grad_v')
                grad_p = context.get('grad_p')
                laplacian_v = context.get('laplacian_v')
                body_force = context.get('body_force', np.zeros(3))

                if any(x is None for x in [dv_dt, v_grad_v, grad_p, laplacian_v]):
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing derivatives'}
                    )

                # Momentum residual
                lhs = self.rho * (dv_dt + v_grad_v)
                rhs = -grad_p + self.mu * laplacian_v + body_force

                residual_vec = lhs - rhs
                residual = float(np.mean(np.sum(residual_vec ** 2, axis=-1)))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(np.abs(residual_vec)))
                )

        return NavierStokes(density, viscosity, weight)


# =============================================================================
# Manufacturing-Specific Constraints
# =============================================================================

class ManufacturingConstraints:
    """Collection of manufacturing-specific constraints."""

    @staticmethod
    def layer_adhesion(
        min_temp: float = 180.0,
        weight: float = 5.0
    ) -> PhysicsConstraint:
        """
        Constraint for FDM layer adhesion.

        Interface temperature must be above minimum for bonding.
        """

        class LayerAdhesion(PhysicsConstraint):
            def __init__(self, t_min: float, w: float):
                super().__init__(
                    name="layer_adhesion",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.min_temp = t_min

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Temperature at layer interfaces
                interface_temp = context.get('interface_temperature')

                if interface_temp is None:
                    # Use predictions if they represent temperature
                    interface_temp = predictions[:, 0] if predictions.ndim > 1 else predictions

                # Violation when T < T_min
                violation = np.maximum(0, self.min_temp - interface_temp)
                residual = float(np.mean(violation ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(violation)),
                    details={
                        'min_interface_temp': float(np.min(interface_temp)),
                        'fraction_below_threshold': float(np.mean(interface_temp < self.min_temp))
                    }
                )

        return LayerAdhesion(min_temp, weight)

    @staticmethod
    def material_extrusion_rate(
        nozzle_diameter: float = 0.4e-3,  # m
        layer_height: float = 0.2e-3,  # m
        print_speed: float = 50e-3,  # m/s
        weight: float = 1.0
    ) -> PhysicsConstraint:
        """
        Constraint for volumetric extrusion rate.

        Ensures material flow rate matches deposition requirements.
        """

        class ExtrusionRate(PhysicsConstraint):
            def __init__(
                self,
                d_nozzle: float,
                h_layer: float,
                v_print: float,
                w: float
            ):
                super().__init__(
                    name="extrusion_rate",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.d_nozzle = d_nozzle
                self.h_layer = h_layer
                self.v_print = v_print

                # Volumetric flow rate = width × height × speed
                # Approximate bead width as 1.2 × nozzle diameter
                self.bead_width = 1.2 * d_nozzle
                self.target_flow = self.bead_width * h_layer * v_print

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Predicted flow rate
                predicted_flow = context.get('extrusion_rate')

                if predicted_flow is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing extrusion rate'}
                    )

                # Relative error
                rel_error = (predicted_flow - self.target_flow) / (self.target_flow + 1e-10)
                residual = float(np.mean(rel_error ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < 0.01,  # 1% tolerance
                    residual=residual,
                    violation=float(np.max(np.abs(rel_error))),
                    details={
                        'target_flow': self.target_flow,
                        'mean_predicted_flow': float(np.mean(predicted_flow))
                    }
                )

        return ExtrusionRate(nozzle_diameter, layer_height, print_speed, weight)

    @staticmethod
    def cooling_rate(
        max_rate: float = 100.0,  # °C/s
        min_rate: float = 0.0,
        weight: float = 2.0
    ) -> PhysicsConstraint:
        """
        Constraint on cooling rate to prevent thermal stress.
        """

        class CoolingRate(PhysicsConstraint):
            def __init__(self, r_max: float, r_min: float, w: float):
                super().__init__(
                    name="cooling_rate",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.MEDIUM,
                    weight=w
                )
                self.max_rate = r_max
                self.min_rate = r_min

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Cooling rate (negative temperature derivative)
                dT_dt = context.get('dT_dt')

                if dT_dt is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing temperature derivative'}
                    )

                cooling_rate = -dT_dt

                # Violation when outside bounds
                upper_violation = np.maximum(0, cooling_rate - self.max_rate)
                lower_violation = np.maximum(0, self.min_rate - cooling_rate)

                total_violation = upper_violation + lower_violation
                residual = float(np.mean(total_violation ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < self.tolerance,
                    residual=residual,
                    violation=float(np.max(total_violation)),
                    details={
                        'max_cooling_rate': float(np.max(cooling_rate)),
                        'mean_cooling_rate': float(np.mean(cooling_rate))
                    }
                )

        return CoolingRate(max_rate, min_rate, weight)

    @staticmethod
    def dimensional_accuracy(
        tolerance: float = 0.1e-3,  # 0.1mm
        weight: float = 5.0
    ) -> PhysicsConstraint:
        """
        Dimensional accuracy constraint.

        Predicted dimensions should match design within tolerance.
        """

        class DimensionalAccuracy(PhysicsConstraint):
            def __init__(self, tol: float, w: float):
                super().__init__(
                    name="dimensional_accuracy",
                    constraint_type=ConstraintType.SOFT,
                    priority=ConstraintPriority.HIGH,
                    weight=w
                )
                self.tolerance = tol

            def evaluate(
                self,
                predictions: np.ndarray,
                inputs: np.ndarray,
                context: Optional[Dict[str, Any]] = None
            ) -> ConstraintResult:
                context = context or {}

                # Design dimensions
                design = context.get('design_dimensions')
                # Predicted dimensions
                predicted = context.get('predicted_dimensions')

                if design is None or predicted is None:
                    return ConstraintResult(
                        name=self.name,
                        satisfied=True,
                        residual=0.0,
                        violation=0.0,
                        details={'note': 'Missing dimensions'}
                    )

                # Dimensional error
                error = np.abs(predicted - design)
                violation = np.maximum(0, error - self.tolerance)
                residual = float(np.mean(violation ** 2))

                return ConstraintResult(
                    name=self.name,
                    satisfied=residual < 1e-10,
                    residual=residual,
                    violation=float(np.max(violation)),
                    details={
                        'max_error': float(np.max(error)),
                        'mean_error': float(np.mean(error)),
                        'within_tolerance': float(np.mean(error <= self.tolerance))
                    }
                )

        return DimensionalAccuracy(tolerance, weight)


# =============================================================================
# Constraint Enforcer
# =============================================================================

class ConstraintEnforcer:
    """
    Manages and enforces multiple physics constraints.

    Provides:
    - Constraint registration and prioritization
    - Combined loss computation
    - Constraint projection for hard constraints
    - Adaptive weight scheduling
    """

    def __init__(self):
        self.constraints: Dict[str, PhysicsConstraint] = {}
        self._adaptive_weights: Dict[str, float] = {}

    def add_constraint(self, constraint: PhysicsConstraint) -> None:
        """Add a constraint to the enforcer."""
        self.constraints[constraint.name] = constraint
        self._adaptive_weights[constraint.name] = constraint.weight

    def remove_constraint(self, name: str) -> None:
        """Remove a constraint by name."""
        self.constraints.pop(name, None)
        self._adaptive_weights.pop(name, None)

    def evaluate_all(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ConstraintResult]:
        """Evaluate all constraints."""
        results = {}
        for name, constraint in self.constraints.items():
            results[name] = constraint.evaluate(predictions, inputs, context)
        return results

    def compute_total_loss(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute total weighted loss from all constraints.

        Returns:
            Tuple of (total_loss, individual_losses)
        """
        individual_losses = {}
        total = 0.0

        for name, constraint in self.constraints.items():
            weight = self._adaptive_weights[name]
            loss = constraint.compute_loss(predictions, inputs, context)
            individual_losses[name] = loss
            total += weight * loss

        return total, individual_losses

    def project_constraints(
        self,
        predictions: np.ndarray,
        inputs: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Project predictions to satisfy hard constraints.

        Applies projections in priority order.
        """
        result = predictions.copy()

        # Sort by priority
        sorted_constraints = sorted(
            self.constraints.values(),
            key=lambda c: c.priority.value
        )

        for constraint in sorted_constraints:
            if constraint.constraint_type == ConstraintType.HARD:
                result = constraint.project(result, inputs, context)

        return result

    def update_adaptive_weights(
        self,
        results: Dict[str, ConstraintResult],
        strategy: str = 'grad_norm'
    ) -> None:
        """
        Update constraint weights adaptively.

        Strategies:
        - 'grad_norm': Balance based on gradient norms
        - 'violation': Weight by violation magnitude
        - 'priority': Fixed weights by priority
        """
        if strategy == 'violation':
            # Weight by violation (more violation = higher weight)
            total_violation = sum(r.violation for r in results.values()) + 1e-10
            for name, result in results.items():
                self._adaptive_weights[name] = (
                    self.constraints[name].weight *
                    (1 + result.violation / total_violation)
                )

        elif strategy == 'priority':
            # Weight by priority (higher priority = higher weight)
            for name, constraint in self.constraints.items():
                priority_weight = 1.0 / constraint.priority.value
                self._adaptive_weights[name] = constraint.weight * priority_weight

    def get_summary(
        self,
        results: Dict[str, ConstraintResult]
    ) -> Dict[str, Any]:
        """Get summary of constraint satisfaction."""
        n_satisfied = sum(1 for r in results.values() if r.satisfied)
        n_total = len(results)

        by_priority = defaultdict(list)
        for name, result in results.items():
            priority = self.constraints[name].priority
            by_priority[priority.name].append((name, result.satisfied))

        return {
            'total_constraints': n_total,
            'satisfied': n_satisfied,
            'satisfaction_rate': n_satisfied / max(n_total, 1),
            'by_priority': {
                p: sum(1 for _, s in items if s) / len(items)
                for p, items in by_priority.items()
            },
            'violated_constraints': [
                name for name, result in results.items()
                if not result.satisfied
            ]
        }


# =============================================================================
# Predefined Constraint Sets
# =============================================================================

def get_fdm_printing_constraints() -> ConstraintEnforcer:
    """Get a predefined set of constraints for FDM 3D printing."""
    enforcer = ConstraintEnforcer()

    # Thermal
    enforcer.add_constraint(ThermalConstraints.energy_conservation(weight=1.0))
    enforcer.add_constraint(ThermalConstraints.temperature_bounds(
        min_temp=20.0, max_temp=250.0, weight=10.0
    ))

    # Manufacturing
    enforcer.add_constraint(ManufacturingConstraints.layer_adhesion(
        min_temp=180.0, weight=5.0
    ))
    enforcer.add_constraint(ManufacturingConstraints.cooling_rate(
        max_rate=100.0, weight=2.0
    ))

    return enforcer


def get_structural_analysis_constraints(
    yield_stress: float = 50e6
) -> ConstraintEnforcer:
    """Get a predefined set of constraints for structural analysis."""
    enforcer = ConstraintEnforcer()

    # Mechanical
    enforcer.add_constraint(MechanicalConstraints.equilibrium(weight=1.0))
    enforcer.add_constraint(MechanicalConstraints.strain_compatibility(weight=1.0))
    enforcer.add_constraint(MechanicalConstraints.von_mises_yield(
        yield_stress=yield_stress, weight=10.0
    ))
    enforcer.add_constraint(MechanicalConstraints.hookes_law(weight=1.0))

    return enforcer


# Export public API
__all__ = [
    # Base classes
    'PhysicsConstraint',
    'ConstraintType',
    'ConstraintPriority',
    'ConstraintResult',
    # Constraint collections
    'ThermalConstraints',
    'MechanicalConstraints',
    'FluidConstraints',
    'ManufacturingConstraints',
    # Enforcer
    'ConstraintEnforcer',
    # Predefined sets
    'get_fdm_printing_constraints',
    'get_structural_analysis_constraints',
]
