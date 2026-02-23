"""
LEGO Quality Service - LEGO-specific quality metrics.

Handles:
- Clutch power testing
- Stud/anti-stud fit testing
- LEGO-specific dimensional checks
- Compatibility testing with official LEGO bricks
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy.orm import Session

from models.quality import QualityInspection, QualityMetric
from lego_specs import LEGO, MANUFACTURING_TOLERANCES

logger = logging.getLogger(__name__)


class FitTestResult(Enum):
    """LEGO fit test results."""
    TOO_TIGHT = "too_tight"      # Excessive force needed
    OPTIMAL = "optimal"          # Perfect clutch power
    TOO_LOOSE = "too_loose"      # Falls off easily
    NO_FIT = "no_fit"            # Won't connect at all


@dataclass
class ClutchPowerResult:
    """Result of clutch power test."""
    force_newtons: float
    rating: FitTestResult
    compatible_with_lego: bool
    notes: str


class LegoQualityService:
    """LEGO-specific quality testing service."""

    # Clutch power specifications (Newtons)
    # Based on LEGO's internal standards for brick connection force
    CLUTCH_POWER_SPECS = {
        'min_force': 0.5,      # Minimum acceptable (N)
        'optimal_min': 1.0,    # Optimal range minimum (N)
        'optimal_max': 3.0,    # Optimal range maximum (N)
        'max_force': 5.0,      # Maximum acceptable (N)
    }

    # Critical LEGO dimensions with tolerances
    CRITICAL_DIMENSIONS = {
        'stud_diameter': {
            'nominal': LEGO.STUD_DIAMETER,
            'tolerance': LEGO.STUD_TOLERANCE
        },
        'stud_height': {
            'nominal': LEGO.STUD_HEIGHT,
            'tolerance': 0.05
        },
        'stud_pitch': {
            'nominal': LEGO.STUD_PITCH,
            'tolerance': 0.02
        },
        'wall_thickness': {
            'nominal': LEGO.WALL_THICKNESS,
            'tolerance': 0.05
        },
        'brick_height': {
            'nominal': LEGO.BRICK_HEIGHT,
            'tolerance': 0.05
        },
        'plate_height': {
            'nominal': LEGO.PLATE_HEIGHT,
            'tolerance': 0.03
        },
        'tube_outer_diameter': {
            'nominal': LEGO.TUBE_OUTER_DIAMETER,
            'tolerance': 0.05
        },
        'tube_inner_diameter': {
            'nominal': LEGO.TUBE_INNER_DIAMETER,
            'tolerance': 0.05
        }
    }

    def __init__(self, session: Session):
        self.session = session

    def test_clutch_power(
        self,
        inspection_id: str,
        force_newtons: float,
        test_type: str = "stud_connection",
        notes: Optional[str] = None
    ) -> ClutchPowerResult:
        """
        Record clutch power (connection force) test result.

        Args:
            inspection_id: Inspection ID
            force_newtons: Measured connection force in Newtons
            test_type: Type of test (stud_connection, tube_connection, technic_pin)
            notes: Test notes

        Returns:
            ClutchPowerResult with rating
        """
        specs = self.CLUTCH_POWER_SPECS

        # Determine rating
        if force_newtons < specs['min_force']:
            rating = FitTestResult.TOO_LOOSE
            compatible = False
        elif force_newtons > specs['max_force']:
            rating = FitTestResult.TOO_TIGHT
            compatible = False
        elif specs['optimal_min'] <= force_newtons <= specs['optimal_max']:
            rating = FitTestResult.OPTIMAL
            compatible = True
        else:
            # In acceptable range but not optimal
            rating = FitTestResult.OPTIMAL  # Still passes
            compatible = True

        # Record metric
        metric = QualityMetric(
            inspection_id=inspection_id,
            metric_name=f"clutch_power_{test_type}",
            target_value=(specs['optimal_min'] + specs['optimal_max']) / 2,
            actual_value=force_newtons,
            tolerance_plus=specs['optimal_max'] - specs['optimal_min'],
            tolerance_minus=specs['optimal_max'] - specs['optimal_min'],
            unit="N",
            passed=compatible,
            notes=f"Rating: {rating.value}. {notes or ''}"
        )

        self.session.add(metric)
        self.session.commit()

        result_notes = f"Force: {force_newtons}N, Rating: {rating.value}"
        if not compatible:
            result_notes += " - NOT COMPATIBLE with official LEGO"

        return ClutchPowerResult(
            force_newtons=force_newtons,
            rating=rating,
            compatible_with_lego=compatible,
            notes=result_notes
        )

    def test_stud_fit(
        self,
        inspection_id: str,
        fit_result: str,
        reference_brick: str = "official_lego",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record stud fit test with reference brick.

        Args:
            inspection_id: Inspection ID
            fit_result: Result (too_tight, optimal, too_loose, no_fit)
            reference_brick: Type of reference brick used
            notes: Test notes

        Returns:
            Test result dict
        """
        fit_enum = FitTestResult(fit_result)
        passed = fit_enum == FitTestResult.OPTIMAL

        metric = QualityMetric(
            inspection_id=inspection_id,
            metric_name="stud_fit_test",
            target_value=1.0,  # 1.0 = optimal
            actual_value=1.0 if passed else 0.0,
            tolerance_plus=0.0,
            tolerance_minus=0.0,
            unit="pass/fail",
            passed=passed,
            notes=f"Reference: {reference_brick}, Result: {fit_result}. {notes or ''}"
        )

        self.session.add(metric)
        self.session.commit()

        return {
            'test': 'stud_fit',
            'result': fit_result,
            'passed': passed,
            'reference_brick': reference_brick,
            'compatible_with_lego': passed
        }

    def measure_critical_dimensions(
        self,
        inspection_id: str,
        measurements: Dict[str, float],
        manufacturing_process: str = "fdm"
    ) -> Dict[str, Any]:
        """
        Measure and record all critical LEGO dimensions.

        Args:
            inspection_id: Inspection ID
            measurements: Dict of dimension_name -> measured_value
            manufacturing_process: Process type for tolerance adjustment

        Returns:
            Summary of all dimension checks
        """
        process_tolerances = MANUFACTURING_TOLERANCES.get(
            manufacturing_process,
            MANUFACTURING_TOLERANCES['fdm']
        )

        results = []
        all_passed = True

        for dim_name, measured in measurements.items():
            if dim_name not in self.CRITICAL_DIMENSIONS:
                continue

            spec = self.CRITICAL_DIMENSIONS[dim_name]
            nominal = spec['nominal']

            # Adjust tolerance based on manufacturing process
            tolerance = max(spec['tolerance'], process_tolerances['general'])

            deviation = measured - nominal
            passed = abs(deviation) <= tolerance

            if not passed:
                all_passed = False

            # Record metric
            metric = QualityMetric(
                inspection_id=inspection_id,
                metric_name=f"lego_{dim_name}",
                target_value=nominal,
                actual_value=measured,
                tolerance_plus=tolerance,
                tolerance_minus=tolerance,
                unit="mm",
                passed=passed,
                notes=f"LEGO spec, Process: {manufacturing_process}"
            )

            self.session.add(metric)

            results.append({
                'dimension': dim_name,
                'nominal': nominal,
                'measured': measured,
                'deviation': round(deviation, 4),
                'tolerance': tolerance,
                'passed': passed
            })

        self.session.commit()

        return {
            'inspection_id': str(inspection_id),
            'manufacturing_process': manufacturing_process,
            'all_passed': all_passed,
            'dimensions_checked': len(results),
            'dimensions_passed': sum(1 for r in results if r['passed']),
            'results': results
        }

    def run_compatibility_suite(
        self,
        inspection_id: str,
        stud_diameter: float,
        stud_height: float,
        wall_thickness: float,
        clutch_force: Optional[float] = None,
        manufacturing_process: str = "fdm"
    ) -> Dict[str, Any]:
        """
        Run full LEGO compatibility test suite.

        Args:
            inspection_id: Inspection ID
            stud_diameter: Measured stud diameter (mm)
            stud_height: Measured stud height (mm)
            wall_thickness: Measured wall thickness (mm)
            clutch_force: Measured clutch power (N) - optional
            manufacturing_process: Manufacturing process used

        Returns:
            Complete compatibility assessment
        """
        # Dimensional checks
        dim_results = self.measure_critical_dimensions(
            inspection_id=inspection_id,
            measurements={
                'stud_diameter': stud_diameter,
                'stud_height': stud_height,
                'wall_thickness': wall_thickness
            },
            manufacturing_process=manufacturing_process
        )

        # Clutch power test if provided
        clutch_result = None
        if clutch_force is not None:
            clutch_result = self.test_clutch_power(
                inspection_id=inspection_id,
                force_newtons=clutch_force
            )

        # Overall compatibility assessment
        dimensional_ok = dim_results['all_passed']
        clutch_ok = clutch_result.compatible_with_lego if clutch_result else True

        compatibility_score = 0
        if dimensional_ok:
            compatibility_score += 60
        if clutch_ok:
            compatibility_score += 40

        # Determine overall grade
        if compatibility_score >= 90:
            grade = "A - Fully LEGO Compatible"
        elif compatibility_score >= 70:
            grade = "B - Compatible with minor deviations"
        elif compatibility_score >= 50:
            grade = "C - Marginally compatible"
        else:
            grade = "F - Not compatible with LEGO"

        return {
            'inspection_id': str(inspection_id),
            'manufacturing_process': manufacturing_process,
            'dimensional_check': {
                'passed': dim_results['all_passed'],
                'details': dim_results['results']
            },
            'clutch_power_check': {
                'tested': clutch_result is not None,
                'passed': clutch_ok,
                'force_newtons': clutch_result.force_newtons if clutch_result else None,
                'rating': clutch_result.rating.value if clutch_result else None
            },
            'overall': {
                'compatibility_score': compatibility_score,
                'grade': grade,
                'lego_compatible': compatibility_score >= 70
            }
        }

    def get_recommended_adjustments(
        self,
        inspection_id: str,
        manufacturing_process: str = "fdm"
    ) -> Dict[str, Any]:
        """
        Get recommended parameter adjustments based on inspection results.

        Returns suggested slicer/machine adjustments to improve compatibility.
        """
        metrics = self.session.query(QualityMetric).filter(
            QualityMetric.inspection_id == inspection_id,
            QualityMetric.metric_name.like('lego_%')
        ).all()

        adjustments = []

        for m in metrics:
            if m.passed:
                continue

            deviation = m.actual_value - m.target_value
            dim_name = m.metric_name.replace('lego_', '')

            if manufacturing_process == 'fdm':
                if dim_name == 'stud_diameter':
                    if deviation > 0:  # Too large
                        adjustments.append({
                            'parameter': 'xy_compensation',
                            'current_deviation': deviation,
                            'recommended_change': -deviation / 2,
                            'unit': 'mm',
                            'notes': 'Reduce XY size compensation to shrink studs'
                        })
                    else:  # Too small
                        adjustments.append({
                            'parameter': 'xy_compensation',
                            'current_deviation': deviation,
                            'recommended_change': -deviation / 2,
                            'unit': 'mm',
                            'notes': 'Increase XY size compensation to enlarge studs'
                        })

                elif dim_name == 'wall_thickness':
                    adjustments.append({
                        'parameter': 'extrusion_multiplier',
                        'current_deviation': deviation,
                        'recommended_change': 1.0 + (m.target_value - m.actual_value) / m.target_value * 0.5,
                        'unit': 'ratio',
                        'notes': 'Adjust extrusion multiplier to correct wall thickness'
                    })

            elif manufacturing_process == 'sla':
                if deviation != 0:
                    adjustments.append({
                        'parameter': 'xy_compensation',
                        'current_deviation': deviation,
                        'recommended_change': -deviation,
                        'unit': 'mm',
                        'notes': 'Apply XY compensation in slicer'
                    })

            elif manufacturing_process == 'cnc':
                adjustments.append({
                    'parameter': 'tool_offset',
                    'current_deviation': deviation,
                    'recommended_change': -deviation,
                    'unit': 'mm',
                    'notes': 'Adjust tool diameter compensation'
                })

        return {
            'inspection_id': str(inspection_id),
            'manufacturing_process': manufacturing_process,
            'adjustments': adjustments,
            'total_adjustments': len(adjustments)
        }
