"""
Measurement Service - Dimensional measurement management.

Handles:
- Dimensional measurements
- Measurement equipment calibration tracking
- Measurement uncertainty
- GD&T (Geometric Dimensioning & Tolerancing)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import math

from sqlalchemy.orm import Session

from models.quality import QualityInspection, QualityMetric

logger = logging.getLogger(__name__)


@dataclass
class MeasurementResult:
    """Result of a measurement with uncertainty."""
    value: float
    uncertainty: float
    unit: str
    in_tolerance: bool
    deviation: float


class MeasurementService:
    """Dimensional measurement management service."""

    # Standard measurement equipment uncertainty (mm)
    EQUIPMENT_UNCERTAINTY = {
        'caliper_digital': 0.02,
        'caliper_dial': 0.05,
        'micrometer': 0.01,
        'cmm': 0.005,
        'optical': 0.01,
        'go_nogo': 0.0,  # Pass/fail only
        '3d_scanner': 0.05,
        'default': 0.05
    }

    def __init__(self, session: Session):
        self.session = session

    def record_dimension(
        self,
        inspection_id: str,
        dimension_name: str,
        nominal: float,
        measured: float,
        tolerance_plus: float,
        tolerance_minus: Optional[float] = None,
        equipment_type: str = 'caliper_digital',
        unit: str = 'mm'
    ) -> MeasurementResult:
        """
        Record a dimensional measurement.

        Args:
            inspection_id: Inspection ID
            dimension_name: Name of dimension (e.g., "stud_diameter", "wall_thickness")
            nominal: Nominal/target value
            measured: Measured value
            tolerance_plus: Upper tolerance
            tolerance_minus: Lower tolerance (defaults to tolerance_plus if not specified)
            equipment_type: Type of measurement equipment
            unit: Unit of measurement

        Returns:
            MeasurementResult with analysis
        """
        tolerance_minus = tolerance_minus or tolerance_plus
        uncertainty = self.EQUIPMENT_UNCERTAINTY.get(
            equipment_type,
            self.EQUIPMENT_UNCERTAINTY['default']
        )

        # Calculate deviation
        deviation = measured - nominal

        # Check tolerance including measurement uncertainty
        upper_limit = nominal + tolerance_plus
        lower_limit = nominal - tolerance_minus
        in_tolerance = (lower_limit - uncertainty) <= measured <= (upper_limit + uncertainty)

        # Record in database
        metric = QualityMetric(
            inspection_id=inspection_id,
            metric_name=dimension_name,
            target_value=nominal,
            actual_value=measured,
            tolerance_plus=tolerance_plus,
            tolerance_minus=tolerance_minus,
            unit=unit,
            passed=in_tolerance,
            notes=f"Equipment: {equipment_type}, Uncertainty: ±{uncertainty}{unit}"
        )

        self.session.add(metric)
        self.session.commit()

        return MeasurementResult(
            value=measured,
            uncertainty=uncertainty,
            unit=unit,
            in_tolerance=in_tolerance,
            deviation=deviation
        )

    def record_batch_measurements(
        self,
        inspection_id: str,
        measurements: List[Dict[str, Any]],
        equipment_type: str = 'caliper_digital'
    ) -> List[MeasurementResult]:
        """
        Record multiple measurements at once.

        Args:
            inspection_id: Inspection ID
            measurements: List of measurement dicts with keys:
                - dimension_name, nominal, measured, tolerance_plus, tolerance_minus (optional)
            equipment_type: Type of measurement equipment

        Returns:
            List of MeasurementResults
        """
        results = []

        for m in measurements:
            result = self.record_dimension(
                inspection_id=inspection_id,
                dimension_name=m['dimension_name'],
                nominal=m['nominal'],
                measured=m['measured'],
                tolerance_plus=m['tolerance_plus'],
                tolerance_minus=m.get('tolerance_minus'),
                equipment_type=equipment_type
            )
            results.append(result)

        return results

    def calculate_cpk(
        self,
        metric_name: str,
        part_id: Optional[str] = None,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate Process Capability Index (Cpk) for a metric.

        Cpk = min((USL - μ) / 3σ, (μ - LSL) / 3σ)

        Args:
            metric_name: Name of metric to analyze
            part_id: Optional part filter
            limit: Number of samples to use

        Returns:
            Dict with Cpk, Cp, mean, std_dev, and interpretation
        """
        query = self.session.query(QualityMetric).filter(
            QualityMetric.metric_name == metric_name,
            QualityMetric.target_value.isnot(None),
            QualityMetric.tolerance_plus.isnot(None)
        )

        if part_id:
            query = query.join(QualityInspection).join(
                __import__('dashboard.models', fromlist=['WorkOrder']).WorkOrder
            ).filter(
                __import__('dashboard.models', fromlist=['WorkOrder']).WorkOrder.part_id == part_id
            )

        metrics = query.order_by(QualityMetric.created_at.desc()).limit(limit).all()

        if len(metrics) < 5:
            return {
                'cpk': None,
                'cp': None,
                'message': 'Insufficient data (minimum 5 samples required)',
                'sample_count': len(metrics)
            }

        # Calculate statistics
        values = [m.actual_value for m in metrics]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 0.001

        # Get specification limits from first metric
        target = metrics[0].target_value
        usl = target + metrics[0].tolerance_plus
        lsl = target - (metrics[0].tolerance_minus or metrics[0].tolerance_plus)

        # Calculate Cp and Cpk
        if std_dev > 0:
            cp = (usl - lsl) / (6 * std_dev)
            cpu = (usl - mean) / (3 * std_dev)
            cpl = (mean - lsl) / (3 * std_dev)
            cpk = min(cpu, cpl)
        else:
            cp = cpk = float('inf')

        # Interpretation
        if cpk >= 1.67:
            interpretation = "Excellent - Six Sigma capable"
        elif cpk >= 1.33:
            interpretation = "Good - Process is capable"
        elif cpk >= 1.0:
            interpretation = "Marginal - Process barely capable"
        else:
            interpretation = "Poor - Process not capable, improvement needed"

        return {
            'metric_name': metric_name,
            'sample_count': len(metrics),
            'mean': round(mean, 4),
            'std_dev': round(std_dev, 4),
            'target': target,
            'usl': usl,
            'lsl': lsl,
            'cp': round(cp, 3) if cp != float('inf') else None,
            'cpk': round(cpk, 3) if cpk != float('inf') else None,
            'interpretation': interpretation
        }

    def get_measurement_trend(
        self,
        metric_name: str,
        inspection_ids: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get measurement trend data for SPC charting.

        Returns data suitable for X-bar and R charts.
        """
        query = self.session.query(QualityMetric).filter(
            QualityMetric.metric_name == metric_name
        )

        if inspection_ids:
            query = query.filter(QualityMetric.inspection_id.in_(inspection_ids))

        metrics = query.order_by(QualityMetric.created_at.desc()).limit(limit).all()

        if not metrics:
            return {'data': [], 'statistics': None}

        values = [m.actual_value for m in metrics]
        mean = sum(values) / len(values)

        target = metrics[0].target_value
        usl = target + metrics[0].tolerance_plus if target and metrics[0].tolerance_plus else None
        lsl = target - (metrics[0].tolerance_minus or metrics[0].tolerance_plus) if target else None

        return {
            'metric_name': metric_name,
            'data': [
                {
                    'timestamp': m.created_at.isoformat() if m.created_at else None,
                    'value': m.actual_value,
                    'passed': m.passed
                }
                for m in reversed(metrics)
            ],
            'statistics': {
                'mean': round(mean, 4),
                'target': target,
                'usl': usl,
                'lsl': lsl,
                'count': len(metrics)
            }
        }

    def generate_inspection_report(
        self,
        inspection_id: str
    ) -> Dict[str, Any]:
        """Generate a dimensional inspection report."""
        inspection = self.session.query(QualityInspection).filter(
            QualityInspection.id == inspection_id
        ).first()

        if not inspection:
            return {'error': 'Inspection not found'}

        metrics = self.session.query(QualityMetric).filter(
            QualityMetric.inspection_id == inspection_id
        ).all()

        total = len(metrics)
        passed = sum(1 for m in metrics if m.passed)
        failed = total - passed

        return {
            'inspection_id': str(inspection_id),
            'work_order': inspection.work_order.work_order_number if inspection.work_order else None,
            'part_number': inspection.work_order.part.part_number if inspection.work_order and inspection.work_order.part else None,
            'inspection_type': inspection.inspection_type,
            'inspection_date': inspection.inspection_date.isoformat() if inspection.inspection_date else None,
            'result': inspection.result,
            'summary': {
                'total_dimensions': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': round(passed / total * 100, 1) if total > 0 else 0
            },
            'measurements': [
                {
                    'dimension': m.metric_name,
                    'nominal': m.target_value,
                    'actual': m.actual_value,
                    'deviation': round(m.actual_value - m.target_value, 4) if m.target_value else None,
                    'tolerance': f"+{m.tolerance_plus}/-{m.tolerance_minus or m.tolerance_plus}" if m.tolerance_plus else None,
                    'unit': m.unit,
                    'result': 'PASS' if m.passed else 'FAIL'
                }
                for m in metrics
            ]
        }
