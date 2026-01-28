"""
Clutch Optimizer - Optimize LEGO stud geometry for clutch power.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClutchParameters:
    """Parameters affecting clutch power."""
    stud_diameter: float = 4.8  # mm
    stud_height: float = 1.7  # mm
    tube_inner_diameter: float = 4.8  # mm
    tube_outer_diameter: float = 6.51  # mm
    wall_thickness: float = 1.5  # mm
    material_modulus: float = 2400  # MPa (PLA)


@dataclass
class ClutchResult:
    """Result of clutch optimization."""
    optimal_stud_diameter: float
    predicted_clutch_force: float
    interference_fit: float
    stress_ratio: float
    parameters: ClutchParameters


class ClutchOptimizer:
    """
    Optimize LEGO stud and tube geometry for optimal clutch power.

    Target clutch force: 1.0 - 3.0 N (per stud)

    Factors affecting clutch:
    - Interference fit (stud diameter vs tube ID)
    - Material stiffness
    - Wall thickness
    - Surface friction
    """

    def __init__(self,
                 target_force_min: float = 1.0,
                 target_force_max: float = 3.0,
                 friction_coefficient: float = 0.3):
        self.target_force_min = target_force_min
        self.target_force_max = target_force_max
        self.friction_coefficient = friction_coefficient

        # LEGO specifications
        self.lego_stud_diameter = 4.8
        self.lego_tube_id = 4.8

    def optimize(self,
                 material_modulus: float = 2400,
                 manufacturing_process: str = "fdm",
                 process_tolerance: float = 0.05) -> ClutchResult:
        """
        Find optimal stud diameter for target clutch power.

        Args:
            material_modulus: Material Young's modulus (MPa)
            manufacturing_process: "fdm", "sla", or "injection"
            process_tolerance: Expected manufacturing tolerance (mm)

        Returns:
            ClutchResult with optimal parameters
        """
        logger.info(f"Optimizing clutch for {manufacturing_process} with E={material_modulus}MPa")

        # Target interference for optimal clutch
        target_interference = self._calculate_target_interference(
            material_modulus,
            manufacturing_process
        )

        # Compensate for process variation
        if manufacturing_process == "fdm":
            # FDM typically produces slightly larger studs
            compensation = -0.02
        elif manufacturing_process == "sla":
            compensation = -0.01
        else:
            compensation = 0

        optimal_diameter = self.lego_stud_diameter + target_interference + compensation

        # Calculate predicted clutch force
        params = ClutchParameters(
            stud_diameter=optimal_diameter,
            material_modulus=material_modulus
        )
        predicted_force = self._calculate_clutch_force(params)

        # Calculate stress ratio (actual/yield)
        stress_ratio = self._calculate_stress_ratio(params)

        result = ClutchResult(
            optimal_stud_diameter=round(optimal_diameter, 3),
            predicted_clutch_force=round(predicted_force, 2),
            interference_fit=round(target_interference, 3),
            stress_ratio=round(stress_ratio, 2),
            parameters=params
        )

        logger.info(f"Optimal diameter: {result.optimal_stud_diameter}mm, "
                   f"predicted force: {result.predicted_clutch_force}N")
        return result

    def _calculate_target_interference(self,
                                       modulus: float,
                                       process: str) -> float:
        """Calculate target interference fit for optimal clutch."""
        # Higher modulus materials need less interference
        base_interference = 0.05  # mm

        # Scale by material stiffness (relative to ABS at 2400 MPa)
        stiffness_factor = 2400 / modulus

        # Process-specific adjustment
        process_factors = {
            'fdm': 1.1,  # FDM parts slightly less stiff due to layer lines
            'sla': 1.0,
            'injection': 0.95
        }
        process_factor = process_factors.get(process, 1.0)

        return base_interference * stiffness_factor * process_factor

    def _calculate_clutch_force(self, params: ClutchParameters) -> float:
        """
        Calculate clutch force using press-fit interference model.

        Simplified Lame equations for thick-walled cylinder.
        """
        # Interference
        delta = params.stud_diameter - params.tube_inner_diameter

        if delta <= 0:
            return 0.0  # No interference, no clutch

        # Geometric parameters
        r_i = params.tube_inner_diameter / 2  # Inner radius
        r_o = params.tube_outer_diameter / 2  # Outer radius

        # Contact pressure (simplified)
        E = params.material_modulus
        contact_pressure = (E * delta) / (2 * r_i * ((r_o**2 + r_i**2) / (r_o**2 - r_i**2) + 0.3))

        # Contact area (stud height * circumference)
        contact_area = params.stud_height * np.pi * params.stud_diameter

        # Normal force
        normal_force = contact_pressure * contact_area

        # Friction force = clutch force
        clutch_force = self.friction_coefficient * normal_force

        return clutch_force

    def _calculate_stress_ratio(self, params: ClutchParameters) -> float:
        """Calculate ratio of actual stress to yield stress."""
        # Simplified stress calculation
        delta = params.stud_diameter - params.tube_inner_diameter
        if delta <= 0:
            return 0.0

        r_i = params.tube_inner_diameter / 2
        r_o = params.tube_outer_diameter / 2

        E = params.material_modulus
        contact_pressure = (E * delta) / (2 * r_i * ((r_o**2 + r_i**2) / (r_o**2 - r_i**2) + 0.3))

        # Hoop stress at inner surface
        hoop_stress = contact_pressure * (r_o**2 + r_i**2) / (r_o**2 - r_i**2)

        # Typical yield strength for PLA/ABS (MPa)
        yield_strength = 40

        return hoop_stress / yield_strength

    def sensitivity_analysis(self,
                            params: ClutchParameters,
                            parameter: str,
                            range_pct: float = 10) -> List[Tuple[float, float]]:
        """
        Analyze sensitivity of clutch force to parameter variations.

        Returns list of (parameter_value, clutch_force) tuples.
        """
        base_value = getattr(params, parameter)
        min_val = base_value * (1 - range_pct / 100)
        max_val = base_value * (1 + range_pct / 100)

        results = []
        for val in np.linspace(min_val, max_val, 11):
            test_params = ClutchParameters(
                stud_diameter=params.stud_diameter,
                stud_height=params.stud_height,
                tube_inner_diameter=params.tube_inner_diameter,
                tube_outer_diameter=params.tube_outer_diameter,
                wall_thickness=params.wall_thickness,
                material_modulus=params.material_modulus
            )
            setattr(test_params, parameter, val)
            force = self._calculate_clutch_force(test_params)
            results.append((val, force))

        return results

    def validate_compatibility(self,
                              params: ClutchParameters) -> Dict[str, Any]:
        """
        Validate parameters against LEGO compatibility requirements.
        """
        report = {
            'compatible': True,
            'issues': [],
            'warnings': []
        }

        # Check stud diameter tolerance
        diameter_deviation = abs(params.stud_diameter - self.lego_stud_diameter)
        if diameter_deviation > 0.1:
            report['compatible'] = False
            report['issues'].append(
                f"Stud diameter {params.stud_diameter}mm exceeds LEGO tolerance "
                f"(nominal {self.lego_stud_diameter}mm +/- 0.1mm)"
            )
        elif diameter_deviation > 0.05:
            report['warnings'].append(
                f"Stud diameter {params.stud_diameter}mm at edge of tolerance"
            )

        # Check clutch force
        force = self._calculate_clutch_force(params)
        if force < self.target_force_min:
            report['warnings'].append(
                f"Predicted clutch force {force:.2f}N below minimum {self.target_force_min}N"
            )
        elif force > self.target_force_max:
            report['warnings'].append(
                f"Predicted clutch force {force:.2f}N above maximum {self.target_force_max}N"
            )

        # Check stress ratio
        stress_ratio = self._calculate_stress_ratio(params)
        if stress_ratio > 0.8:
            report['warnings'].append(
                f"High stress ratio {stress_ratio:.2f} may cause fatigue"
            )

        return report
