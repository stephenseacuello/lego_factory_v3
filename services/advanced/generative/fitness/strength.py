"""
Strength Evaluator - FEA-based strength evaluation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class LoadType(Enum):
    """Types of mechanical loads."""
    TENSION = "tension"
    COMPRESSION = "compression"
    BENDING = "bending"
    TORSION = "torsion"
    SHEAR = "shear"
    COMBINED = "combined"


class FailureMode(Enum):
    """Failure modes."""
    YIELD = "yield"
    FRACTURE = "fracture"
    FATIGUE = "fatigue"
    BUCKLING = "buckling"
    DELAMINATION = "delamination"


@dataclass
class StrengthResult:
    """Strength evaluation result."""
    max_stress: float
    max_strain: float
    safety_factor: float
    failure_mode: Optional[FailureMode]
    failure_location: Optional[Tuple[float, float, float]]
    stiffness: float
    weight: float
    strength_to_weight: float
    fitness_score: float  # 0-1 normalized
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class StrengthEvaluator:
    """
    FEA-based strength evaluation for generative designs.

    Features:
    - Multiple load case analysis
    - Safety factor calculation
    - Failure mode prediction
    - LEGO-specific structural requirements
    """

    def __init__(self):
        self._materials: Dict[str, Dict] = {}
        self._lego_requirements: Dict[str, float] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default materials and requirements."""
        self._materials = {
            'PLA': {
                'density': 1.24e-6,  # kg/mm³
                'elastic_modulus': 2500,  # MPa
                'poisson_ratio': 0.35,
                'yield_strength': 60,  # MPa
                'ultimate_strength': 65,  # MPa
                'fatigue_limit': 30  # MPa (for cyclic loading)
            },
            'ABS': {
                'density': 1.05e-6,
                'elastic_modulus': 2000,
                'poisson_ratio': 0.35,
                'yield_strength': 45,
                'ultimate_strength': 50,
                'fatigue_limit': 22
            },
            'PETG': {
                'density': 1.27e-6,
                'elastic_modulus': 2100,
                'poisson_ratio': 0.37,
                'yield_strength': 50,
                'ultimate_strength': 55,
                'fatigue_limit': 25
            }
        }

        # LEGO-specific structural requirements
        self._lego_requirements = {
            'stud_shear_force': 50.0,  # N minimum before failure
            'clutch_force_max': 3.0,  # N (don't want too stiff)
            'wall_thickness_min': 1.2,  # mm
            'drop_test_height': 1.0,  # m
            'cycle_life': 1000  # connection/disconnection cycles
        }

    def evaluate(self,
                geometry: np.ndarray,
                loads: List[Dict[str, Any]],
                material: str = 'PLA',
                target_safety_factor: float = 2.0) -> StrengthResult:
        """
        Evaluate strength of design.

        Args:
            geometry: 3D density field (0-1)
            loads: List of load definitions
            material: Material name
            target_safety_factor: Target safety factor

        Returns:
            Strength evaluation result
        """
        mat = self._materials.get(material, self._materials['PLA'])

        # Calculate volume and weight
        volume = np.sum(geometry)  # mm³
        weight = volume * mat['density']  # kg

        # Simplified FEA analysis
        stress_field = self._simplified_fea(geometry, loads, mat)

        max_stress = float(np.max(np.abs(stress_field)))
        max_strain = max_stress / mat['elastic_modulus']

        # Find failure location
        failure_idx = np.unravel_index(np.argmax(np.abs(stress_field)), stress_field.shape)
        failure_location = tuple(float(i) for i in failure_idx)

        # Calculate safety factor
        yield_strength = mat['yield_strength']
        safety_factor = yield_strength / max_stress if max_stress > 0 else float('inf')

        # Determine failure mode
        failure_mode = self._predict_failure_mode(
            stress_field, geometry, mat, loads
        )

        # Calculate stiffness (simplified)
        stiffness = self._estimate_stiffness(geometry, mat)

        # Strength to weight ratio
        strength_to_weight = (yield_strength * volume) / (weight * 1e6) if weight > 0 else 0

        # Calculate fitness score (0-1)
        fitness = self._calculate_fitness(
            safety_factor, target_safety_factor, weight, stiffness
        )

        passed = safety_factor >= target_safety_factor

        return StrengthResult(
            max_stress=max_stress,
            max_strain=max_strain,
            safety_factor=safety_factor,
            failure_mode=failure_mode if safety_factor < 1.5 else None,
            failure_location=failure_location if safety_factor < 1.5 else None,
            stiffness=stiffness,
            weight=weight * 1e6,  # Convert to grams
            strength_to_weight=strength_to_weight,
            fitness_score=fitness,
            passed=passed,
            details={
                'material': material,
                'volume_mm3': volume,
                'target_sf': target_safety_factor
            }
        )

    def _simplified_fea(self,
                       geometry: np.ndarray,
                       loads: List[Dict],
                       material: Dict) -> np.ndarray:
        """Simplified FEA stress calculation."""
        E = material['elastic_modulus']
        stress = np.zeros_like(geometry, dtype=float)

        for load in loads:
            load_type = load.get('type', LoadType.COMPRESSION)
            magnitude = load.get('magnitude', 0)
            location = load.get('location', (0, 0, 0))

            # Apply load
            loc = tuple(min(int(l), s-1) for l, s in zip(location, geometry.shape))

            if load_type == LoadType.COMPRESSION or load_type == LoadType.TENSION:
                # Stress = Force / Area
                # Simplified: spread stress from load point
                for i in range(geometry.shape[0]):
                    for j in range(geometry.shape[1]):
                        for k in range(geometry.shape[2]):
                            if geometry[i, j, k] > 0.5:
                                dist = np.sqrt((i-loc[0])**2 + (j-loc[1])**2 + (k-loc[2])**2)
                                stress[i, j, k] += magnitude / (1 + dist * 0.1)

            elif load_type == LoadType.BENDING:
                # Bending stress increases with distance from neutral axis
                center = np.array(geometry.shape) / 2
                for i in range(geometry.shape[0]):
                    for j in range(geometry.shape[1]):
                        for k in range(geometry.shape[2]):
                            if geometry[i, j, k] > 0.5:
                                dist_from_center = abs(i - center[0])
                                stress[i, j, k] += magnitude * dist_from_center / center[0]

        return stress

    def _predict_failure_mode(self,
                             stress_field: np.ndarray,
                             geometry: np.ndarray,
                             material: Dict,
                             loads: List[Dict]) -> FailureMode:
        """Predict likely failure mode."""
        max_stress = np.max(np.abs(stress_field))
        yield_strength = material['yield_strength']

        # Check for different failure modes
        if max_stress > material['ultimate_strength']:
            return FailureMode.FRACTURE
        elif max_stress > yield_strength:
            return FailureMode.YIELD

        # Check for buckling (thin sections under compression)
        thin_sections = geometry < 0.3
        if np.any(thin_sections):
            compressive_loads = [l for l in loads if l.get('type') == LoadType.COMPRESSION]
            if compressive_loads:
                return FailureMode.BUCKLING

        # For FDM parts, check for delamination risk
        # (high stress perpendicular to layer direction)
        layer_direction = 2  # Assuming Z is layer direction
        gradient = np.gradient(stress_field, axis=layer_direction)
        if np.max(np.abs(gradient)) > yield_strength * 0.3:
            return FailureMode.DELAMINATION

        return FailureMode.YIELD  # Default

    def _estimate_stiffness(self, geometry: np.ndarray, material: Dict) -> float:
        """Estimate structural stiffness."""
        E = material['elastic_modulus']
        volume_fraction = np.mean(geometry)

        # Simplified stiffness based on volume fraction
        # Uses rule of mixtures approximation
        return E * volume_fraction

    def _calculate_fitness(self,
                          safety_factor: float,
                          target_sf: float,
                          weight: float,
                          stiffness: float) -> float:
        """Calculate overall fitness score."""
        # Safety factor component (0-1)
        sf_score = min(1.0, safety_factor / (target_sf * 1.5))

        # Weight penalty (lower is better, normalized)
        weight_score = 1.0 / (1 + weight * 10)  # Penalize heavier designs

        # Stiffness bonus
        stiffness_score = min(1.0, stiffness / 2000)

        # Combined fitness
        fitness = 0.5 * sf_score + 0.3 * weight_score + 0.2 * stiffness_score

        return max(0, min(1, fitness))

    def evaluate_lego_requirements(self,
                                   geometry: np.ndarray,
                                   material: str = 'PLA') -> Dict[str, Any]:
        """
        Evaluate LEGO-specific structural requirements.

        Returns:
            Dictionary of requirement check results
        """
        mat = self._materials.get(material, self._materials['PLA'])
        results = {}

        # Stud shear resistance
        stud_loads = [{'type': LoadType.SHEAR, 'magnitude': self._lego_requirements['stud_shear_force'], 'location': (5, 5, 10)}]
        stud_result = self.evaluate(geometry, stud_loads, material)
        results['stud_shear'] = {
            'passed': stud_result.safety_factor >= 1.5,
            'safety_factor': stud_result.safety_factor
        }

        # Wall thickness check
        # Count connected voxels for minimum feature size
        min_thickness = self._estimate_min_thickness(geometry)
        results['wall_thickness'] = {
            'passed': min_thickness >= self._lego_requirements['wall_thickness_min'],
            'measured': min_thickness,
            'required': self._lego_requirements['wall_thickness_min']
        }

        # Fatigue life estimation
        fatigue_limit = mat['fatigue_limit']
        stud_stress = self._lego_requirements['stud_shear_force'] / 10  # Simplified
        fatigue_sf = fatigue_limit / stud_stress if stud_stress > 0 else float('inf')
        results['fatigue_life'] = {
            'passed': fatigue_sf >= 2.0,
            'estimated_cycles': int(self._lego_requirements['cycle_life'] * fatigue_sf)
        }

        # Overall pass
        results['overall_passed'] = all(r.get('passed', False) for r in results.values())

        return results

    def _estimate_min_thickness(self, geometry: np.ndarray) -> float:
        """Estimate minimum feature thickness."""
        # Simplified: find smallest solid dimension
        solid_mask = geometry > 0.5

        # Check each direction
        min_thickness = float('inf')

        for axis in range(3):
            for i in range(geometry.shape[axis]):
                if axis == 0:
                    slice_mask = solid_mask[i, :, :]
                elif axis == 1:
                    slice_mask = solid_mask[:, i, :]
                else:
                    slice_mask = solid_mask[:, :, i]

                if np.any(slice_mask):
                    # Count consecutive True values
                    runs = []
                    current_run = 0
                    for row in slice_mask:
                        for val in row:
                            if val:
                                current_run += 1
                            elif current_run > 0:
                                runs.append(current_run)
                                current_run = 0
                    if current_run > 0:
                        runs.append(current_run)
                    if runs:
                        min_thickness = min(min_thickness, min(runs))

        return min_thickness * 0.5  # Convert to approximate mm

    def get_material_properties(self, material: str) -> Dict[str, float]:
        """Get material properties."""
        return self._materials.get(material, {})
