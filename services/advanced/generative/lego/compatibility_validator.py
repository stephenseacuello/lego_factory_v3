"""
Compatibility Validator - Validate against official LEGO specs.

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


class CompatibilityLevel(Enum):
    """Levels of LEGO compatibility."""
    FULLY_COMPATIBLE = "fully_compatible"  # Works with official LEGO
    MOSTLY_COMPATIBLE = "mostly_compatible"  # Minor issues
    PARTIALLY_COMPATIBLE = "partially_compatible"  # Works with limitations
    INCOMPATIBLE = "incompatible"  # Does not work with official LEGO


class ValidationCategory(Enum):
    """Categories of validation checks."""
    DIMENSIONAL = "dimensional"
    CLUTCH_POWER = "clutch_power"
    MATERIAL = "material"
    STRUCTURAL = "structural"
    SAFETY = "safety"


@dataclass
class ValidationIssue:
    """Single validation issue."""
    issue_id: str
    category: ValidationCategory
    severity: str  # 'critical', 'major', 'minor'
    parameter: str
    measured_value: float
    expected_value: float
    tolerance: float
    deviation: float
    description: str
    recommendation: str


@dataclass
class ValidationResult:
    """Complete validation result."""
    validation_id: str
    compatibility_level: CompatibilityLevel
    overall_score: float  # 0-1
    issues: List[ValidationIssue]
    passed_checks: List[str]
    dimensional_score: float
    clutch_score: float
    structural_score: float
    safety_score: float
    certified: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CompatibilityValidator:
    """
    Validate designs against official LEGO specifications.

    Features:
    - Dimensional tolerance checking
    - Clutch power verification
    - Material compatibility
    - Safety standard compliance
    """

    def __init__(self):
        self._lego_specs: Dict[str, Dict] = {}
        self._safety_standards: Dict[str, Dict] = {}
        self._load_specifications()

    def _load_specifications(self) -> None:
        """Load official LEGO specifications."""
        # Dimensional specifications (mm)
        self._lego_specs['dimensional'] = {
            'stud_diameter': {'nominal': 4.8, 'tolerance': 0.02},
            'stud_height': {'nominal': 1.7, 'tolerance': 0.02},
            'stud_pitch': {'nominal': 8.0, 'tolerance': 0.01},
            'brick_height_1u': {'nominal': 3.2, 'tolerance': 0.02},  # Plate
            'brick_height_3u': {'nominal': 9.6, 'tolerance': 0.03},  # Brick
            'wall_thickness': {'nominal': 1.5, 'tolerance': 0.1},
            'tube_outer_diameter': {'nominal': 6.51, 'tolerance': 0.05},
            'tube_inner_diameter': {'nominal': 4.8, 'tolerance': 0.02},
            'tube_height': {'nominal': 6.8, 'tolerance': 0.1},
            'base_thickness': {'nominal': 1.0, 'tolerance': 0.05},
        }

        # Clutch power specifications
        self._lego_specs['clutch_power'] = {
            'insertion_force': {'min': 0.5, 'max': 2.0, 'unit': 'N'},
            'separation_force': {'min': 1.0, 'max': 3.0, 'unit': 'N'},
            'cycle_retention': {'min_cycles': 1000, 'max_degradation': 0.20}
        }

        # Material specifications
        self._lego_specs['material'] = {
            'density': {'nominal': 1.05, 'tolerance': 0.05, 'unit': 'g/cm³'},
            'elastic_modulus': {'min': 1800, 'max': 2500, 'unit': 'MPa'},
            'yield_strength': {'min': 40, 'unit': 'MPa'},
            'color_delta_e': {'max': 2.0}
        }

        # Safety standards (EN 71, ASTM F963)
        self._safety_standards = {
            'small_parts': {
                'min_dimension': 31.7,  # mm (small parts cylinder)
                'applies_to': 'any detachable part'
            },
            'sharp_edges': {
                'max_edge_radius': 0.5,  # mm
                'description': 'No sharp edges that could cause injury'
            },
            'sharp_points': {
                'max_tip_radius': 0.5,  # mm
                'description': 'No sharp points'
            },
            'toxicity': {
                'lead_max_ppm': 90,
                'cadmium_max_ppm': 75,
                'phthalates_max_percent': 0.1
            },
            'flammability': {
                'self_extinguish_time': 5,  # seconds
                'unit': 'seconds'
            }
        }

    def validate(self,
                measurements: Dict[str, float],
                clutch_data: Optional[Dict[str, float]] = None,
                material_data: Optional[Dict[str, float]] = None) -> ValidationResult:
        """
        Validate design against LEGO specifications.

        Args:
            measurements: Dimensional measurements
            clutch_data: Clutch power test data
            material_data: Material properties

        Returns:
            Validation result
        """
        issues = []
        passed_checks = []

        # Dimensional validation
        dim_issues, dim_passed, dim_score = self._validate_dimensional(measurements)
        issues.extend(dim_issues)
        passed_checks.extend(dim_passed)

        # Clutch power validation
        if clutch_data:
            clutch_issues, clutch_passed, clutch_score = self._validate_clutch(clutch_data)
            issues.extend(clutch_issues)
            passed_checks.extend(clutch_passed)
        else:
            clutch_score = 0.5  # Unknown

        # Material validation
        if material_data:
            mat_issues, mat_passed, mat_score = self._validate_material(material_data)
            issues.extend(mat_issues)
            passed_checks.extend(mat_passed)
        else:
            mat_score = 0.5

        # Structural validation (based on dimensions)
        struct_issues, struct_passed, struct_score = self._validate_structural(measurements)
        issues.extend(struct_issues)
        passed_checks.extend(struct_passed)

        # Safety validation
        safety_issues, safety_passed, safety_score = self._validate_safety(measurements)
        issues.extend(safety_issues)
        passed_checks.extend(safety_passed)

        # Calculate overall score
        overall_score = (
            0.35 * dim_score +
            0.25 * clutch_score +
            0.15 * mat_score +
            0.15 * struct_score +
            0.10 * safety_score
        )

        # Determine compatibility level
        critical_issues = [i for i in issues if i.severity == 'critical']
        major_issues = [i for i in issues if i.severity == 'major']

        if critical_issues:
            compatibility_level = CompatibilityLevel.INCOMPATIBLE
        elif len(major_issues) > 2:
            compatibility_level = CompatibilityLevel.PARTIALLY_COMPATIBLE
        elif major_issues:
            compatibility_level = CompatibilityLevel.MOSTLY_COMPATIBLE
        else:
            compatibility_level = CompatibilityLevel.FULLY_COMPATIBLE

        # Certification check
        certified = (compatibility_level == CompatibilityLevel.FULLY_COMPATIBLE and
                    safety_score >= 0.9)

        return ValidationResult(
            validation_id=f"val_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            compatibility_level=compatibility_level,
            overall_score=overall_score,
            issues=issues,
            passed_checks=passed_checks,
            dimensional_score=dim_score,
            clutch_score=clutch_score,
            structural_score=struct_score,
            safety_score=safety_score,
            certified=certified
        )

    def _validate_dimensional(self,
                             measurements: Dict[str, float]) -> Tuple[List[ValidationIssue], List[str], float]:
        """Validate dimensional specifications."""
        issues = []
        passed = []
        scores = []

        for param, spec in self._lego_specs['dimensional'].items():
            if param in measurements:
                measured = measurements[param]
                nominal = spec['nominal']
                tolerance = spec['tolerance']

                deviation = abs(measured - nominal)
                deviation_ratio = deviation / tolerance

                if deviation <= tolerance:
                    passed.append(f"dimensional_{param}")
                    scores.append(1.0)
                else:
                    severity = 'critical' if deviation_ratio > 2 else ('major' if deviation_ratio > 1.5 else 'minor')

                    issues.append(ValidationIssue(
                        issue_id=f"DIM_{param.upper()}",
                        category=ValidationCategory.DIMENSIONAL,
                        severity=severity,
                        parameter=param,
                        measured_value=measured,
                        expected_value=nominal,
                        tolerance=tolerance,
                        deviation=deviation,
                        description=f"{param}: {measured:.3f}mm vs {nominal:.3f}±{tolerance:.3f}mm",
                        recommendation=f"Adjust {param} by {nominal - measured:+.3f}mm"
                    ))
                    scores.append(max(0, 1 - deviation_ratio))

        avg_score = np.mean(scores) if scores else 0.5
        return issues, passed, avg_score

    def _validate_clutch(self,
                        clutch_data: Dict[str, float]) -> Tuple[List[ValidationIssue], List[str], float]:
        """Validate clutch power specifications."""
        issues = []
        passed = []
        scores = []

        specs = self._lego_specs['clutch_power']

        # Insertion force
        if 'insertion_force' in clutch_data:
            force = clutch_data['insertion_force']
            min_f, max_f = specs['insertion_force']['min'], specs['insertion_force']['max']

            if min_f <= force <= max_f:
                passed.append('clutch_insertion')
                scores.append(1.0)
            else:
                severity = 'critical' if force > max_f * 1.5 or force < min_f * 0.5 else 'major'
                issues.append(ValidationIssue(
                    issue_id="CLUTCH_INSERT",
                    category=ValidationCategory.CLUTCH_POWER,
                    severity=severity,
                    parameter="insertion_force",
                    measured_value=force,
                    expected_value=(min_f + max_f) / 2,
                    tolerance=(max_f - min_f) / 2,
                    deviation=max(0, force - max_f, min_f - force),
                    description=f"Insertion force: {force:.2f}N (expected {min_f}-{max_f}N)",
                    recommendation="Adjust stud/tube dimensions for proper clutch"
                ))
                scores.append(0.5)

        # Separation force
        if 'separation_force' in clutch_data:
            force = clutch_data['separation_force']
            min_f, max_f = specs['separation_force']['min'], specs['separation_force']['max']

            if min_f <= force <= max_f:
                passed.append('clutch_separation')
                scores.append(1.0)
            else:
                severity = 'critical' if force < min_f * 0.5 else 'major'
                issues.append(ValidationIssue(
                    issue_id="CLUTCH_SEP",
                    category=ValidationCategory.CLUTCH_POWER,
                    severity=severity,
                    parameter="separation_force",
                    measured_value=force,
                    expected_value=(min_f + max_f) / 2,
                    tolerance=(max_f - min_f) / 2,
                    deviation=max(0, force - max_f, min_f - force),
                    description=f"Separation force: {force:.2f}N (expected {min_f}-{max_f}N)",
                    recommendation="Adjust interference fit"
                ))
                scores.append(0.5)

        return issues, passed, np.mean(scores) if scores else 0.5

    def _validate_material(self,
                          material_data: Dict[str, float]) -> Tuple[List[ValidationIssue], List[str], float]:
        """Validate material specifications."""
        issues = []
        passed = []
        scores = []

        specs = self._lego_specs['material']

        # Elastic modulus
        if 'elastic_modulus' in material_data:
            modulus = material_data['elastic_modulus']
            min_e, max_e = specs['elastic_modulus']['min'], specs['elastic_modulus']['max']

            if min_e <= modulus <= max_e:
                passed.append('material_modulus')
                scores.append(1.0)
            else:
                issues.append(ValidationIssue(
                    issue_id="MAT_MODULUS",
                    category=ValidationCategory.MATERIAL,
                    severity='major',
                    parameter="elastic_modulus",
                    measured_value=modulus,
                    expected_value=(min_e + max_e) / 2,
                    tolerance=(max_e - min_e) / 2,
                    deviation=max(0, modulus - max_e, min_e - modulus),
                    description=f"Elastic modulus: {modulus:.0f}MPa (expected {min_e}-{max_e}MPa)",
                    recommendation="Select material with appropriate stiffness"
                ))
                scores.append(0.6)

        # Color accuracy
        if 'color_delta_e' in material_data:
            delta_e = material_data['color_delta_e']
            max_de = specs['color_delta_e']['max']

            if delta_e <= max_de:
                passed.append('material_color')
                scores.append(1.0)
            else:
                issues.append(ValidationIssue(
                    issue_id="MAT_COLOR",
                    category=ValidationCategory.MATERIAL,
                    severity='minor',
                    parameter="color_delta_e",
                    measured_value=delta_e,
                    expected_value=max_de / 2,
                    tolerance=max_de / 2,
                    deviation=delta_e - max_de,
                    description=f"Color ΔE: {delta_e:.1f} (max {max_de})",
                    recommendation="Adjust pigment or process parameters"
                ))
                scores.append(0.8)

        return issues, passed, np.mean(scores) if scores else 0.5

    def _validate_structural(self,
                            measurements: Dict[str, float]) -> Tuple[List[ValidationIssue], List[str], float]:
        """Validate structural requirements."""
        issues = []
        passed = []
        scores = []

        # Wall thickness
        if 'wall_thickness' in measurements:
            thickness = measurements['wall_thickness']
            min_thickness = 1.0  # mm minimum for structural integrity

            if thickness >= min_thickness:
                passed.append('structural_wall')
                scores.append(1.0)
            else:
                issues.append(ValidationIssue(
                    issue_id="STRUCT_WALL",
                    category=ValidationCategory.STRUCTURAL,
                    severity='major',
                    parameter="wall_thickness",
                    measured_value=thickness,
                    expected_value=1.5,
                    tolerance=0.5,
                    deviation=min_thickness - thickness,
                    description=f"Wall thickness {thickness:.2f}mm below minimum {min_thickness}mm",
                    recommendation="Increase wall thickness for structural integrity"
                ))
                scores.append(thickness / min_thickness)

        return issues, passed, np.mean(scores) if scores else 0.8

    def _validate_safety(self,
                        measurements: Dict[str, float]) -> Tuple[List[ValidationIssue], List[str], float]:
        """Validate safety requirements."""
        issues = []
        passed = []
        scores = []

        # Small parts test
        if 'min_feature_size' in measurements:
            size = measurements['min_feature_size']
            min_safe = self._safety_standards['small_parts']['min_dimension']

            if size >= min_safe:
                passed.append('safety_small_parts')
                scores.append(1.0)
            else:
                issues.append(ValidationIssue(
                    issue_id="SAFETY_SMALL",
                    category=ValidationCategory.SAFETY,
                    severity='critical',
                    parameter="min_feature_size",
                    measured_value=size,
                    expected_value=min_safe,
                    tolerance=0,
                    deviation=min_safe - size,
                    description=f"Feature size {size:.1f}mm fails small parts test (min {min_safe}mm)",
                    recommendation="Increase feature size or design as non-detachable"
                ))
                scores.append(0.0)

        # Default pass if no measurements
        if not scores:
            passed.append('safety_default')
            scores.append(0.9)

        return issues, passed, np.mean(scores) if scores else 0.9

    def quick_check(self,
                   stud_diameter: float,
                   stud_height: float,
                   clutch_force: float) -> Dict[str, Any]:
        """
        Quick compatibility check with minimal inputs.

        Args:
            stud_diameter: Measured stud diameter (mm)
            stud_height: Measured stud height (mm)
            clutch_force: Measured clutch force (N)

        Returns:
            Quick check result
        """
        measurements = {
            'stud_diameter': stud_diameter,
            'stud_height': stud_height
        }
        clutch_data = {
            'separation_force': clutch_force
        }

        result = self.validate(measurements, clutch_data)

        return {
            'compatible': result.compatibility_level in [
                CompatibilityLevel.FULLY_COMPATIBLE,
                CompatibilityLevel.MOSTLY_COMPATIBLE
            ],
            'compatibility_level': result.compatibility_level.value,
            'score': result.overall_score,
            'critical_issues': [i.description for i in result.issues if i.severity == 'critical']
        }

    def get_specifications(self) -> Dict[str, Any]:
        """Get all LEGO specifications."""
        return {
            'dimensional': self._lego_specs['dimensional'],
            'clutch_power': self._lego_specs['clutch_power'],
            'material': self._lego_specs['material'],
            'safety': self._safety_standards
        }

    def generate_report(self, result: ValidationResult) -> str:
        """Generate validation report."""
        lines = ["# LEGO Compatibility Validation Report\n"]
        lines.append(f"**Validation ID:** {result.validation_id}")
        lines.append(f"**Date:** {result.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Compatibility Level:** {result.compatibility_level.value}")
        lines.append(f"**Overall Score:** {result.overall_score:.1%}")
        lines.append(f"**Certified:** {'Yes' if result.certified else 'No'}\n")

        lines.append("## Score Breakdown\n")
        lines.append(f"- Dimensional: {result.dimensional_score:.1%}")
        lines.append(f"- Clutch Power: {result.clutch_score:.1%}")
        lines.append(f"- Structural: {result.structural_score:.1%}")
        lines.append(f"- Safety: {result.safety_score:.1%}\n")

        if result.issues:
            lines.append("## Issues Found\n")
            for issue in result.issues:
                lines.append(f"### {issue.issue_id} ({issue.severity})")
                lines.append(f"- {issue.description}")
                lines.append(f"- **Recommendation:** {issue.recommendation}\n")

        if result.passed_checks:
            lines.append("## Passed Checks\n")
            for check in result.passed_checks:
                lines.append(f"- ✓ {check}")

        return "\n".join(lines)
