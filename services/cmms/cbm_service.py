"""
Condition-Based Maintenance Service
====================================
Advanced CBM with predictive degradation modeling, RUL estimation,
and health scoring for proactive maintenance management.

Features:
- Threshold-based condition monitoring
- Trend analysis and degradation prediction
- Remaining Useful Life (RUL) estimation
- Multi-parameter health scoring (sensor fusion)
- Maintenance recommendations with confidence
- Spare parts integration for proactive ordering
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import math

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Machine health status levels."""
    EXCELLENT = 'excellent'  # 90-100%
    GOOD = 'good'            # 70-89%
    FAIR = 'fair'            # 50-69%
    POOR = 'poor'            # 30-49%
    CRITICAL = 'critical'    # 0-29%


class DegradationTrend(str, Enum):
    """Degradation trend direction."""
    IMPROVING = 'improving'
    STABLE = 'stable'
    DEGRADING = 'degrading'
    RAPID_DEGRADATION = 'rapid_degradation'


@dataclass
class SensorReading:
    """Sensor reading with metadata."""
    parameter: str
    value: float
    unit: str
    timestamp: datetime
    threshold_max: Optional[float] = None
    threshold_min: Optional[float] = None


@dataclass
class HealthScore:
    """Multi-parameter health score."""
    overall_score: float  # 0-100
    status: HealthStatus
    parameter_scores: Dict[str, float]
    trend: DegradationTrend
    confidence: float  # 0-1


@dataclass
class RULEstimate:
    """Remaining Useful Life estimate."""
    estimated_days: float
    confidence: float  # 0-1
    lower_bound_days: float
    upper_bound_days: float
    failure_mode: str
    methodology: str


@dataclass
class MaintenanceRecommendation:
    """Maintenance recommendation with priority."""
    action: str
    priority: str  # 'immediate', 'scheduled', 'monitor'
    reason: str
    confidence: float
    estimated_cost: Optional[float] = None
    spare_parts_needed: List[str] = field(default_factory=list)
    recommended_date: Optional[datetime] = None


class CBMService:
    """
    Condition-Based Maintenance Service with predictive capabilities.

    Provides:
    - Real-time condition monitoring against thresholds
    - Trend analysis for early degradation detection
    - RUL estimation using multiple methodologies
    - Health scoring with sensor fusion
    - Maintenance recommendations with confidence levels
    """

    def __init__(self, session: Session):
        self.session = session
        self._thresholds = self._load_thresholds()
        self._degradation_history: Dict[str, List[Dict]] = {}  # Cache for trend analysis

    def _load_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load CBM thresholds from configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'cbm_thresholds.json'
        )
        try:
            with open(config_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._get_default_thresholds()

    def _get_default_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get default thresholds by machine type."""
        return {
            'default': {
                'nozzle_temp_max': 280,
                'nozzle_temp_min': 180,
                'vibration_rms_max': 2.5,
                'power_draw_max': 350,
                'temperature_max': 85,
                'spindle_load_max': 80,
            },
            'fdm': {
                'nozzle_temp_max': 300,
                'bed_temp_max': 110,
                'ambient_temp_max': 35,
                'filament_tension_max': 5.0,
                'extruder_current_max': 2.0,
            },
            'cnc': {
                'spindle_vibration_max': 3.0,
                'spindle_temp_max': 70,
                'coolant_level_min': 20,
                'spindle_load_max': 85,
                'tool_wear_max': 80,  # Percentage
            }
        }

    # =========================================================================
    # BASIC CONDITION MONITORING
    # =========================================================================

    def evaluate_conditions(self, machine_id: str) -> Dict[str, Any]:
        """
        Evaluate current machine conditions against thresholds.

        Returns:
            Dict with readings, violations, health score, and recommendations
        """
        from models.scada.machines import Machine

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'error': f'Machine {machine_id} not found'}

        # Get appropriate thresholds
        machine_type = self._get_machine_type(machine_id)
        thresholds = self._thresholds.get(machine_id,
                     self._thresholds.get(machine_type,
                     self._thresholds.get('default', {})))

        # Get current readings
        readings = self._get_current_readings(machine)

        # Check for threshold violations
        violations = self._check_threshold_violations(readings, thresholds)

        # Calculate health score
        health = self._calculate_health_score(readings, thresholds, machine_id)

        # Get RUL estimate
        rul = self.estimate_rul(machine_id)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            machine_id, violations, health, rul
        )

        return {
            'machine_id': machine_id,
            'machine_type': machine_type,
            'timestamp': datetime.utcnow().isoformat(),
            'readings': {r.parameter: {'value': r.value, 'unit': r.unit} for r in readings},
            'violations': violations,
            'health': {
                'score': health.overall_score,
                'status': health.status.value,
                'trend': health.trend.value,
                'confidence': health.confidence
            },
            'rul_days': rul.estimated_days if rul else None,
            'needs_maintenance': len(violations) > 0 or health.status in [HealthStatus.POOR, HealthStatus.CRITICAL],
            'recommendations': [
                {
                    'action': r.action,
                    'priority': r.priority,
                    'reason': r.reason,
                    'confidence': r.confidence,
                    'spare_parts': r.spare_parts_needed
                }
                for r in recommendations
            ]
        }

    def _get_current_readings(self, machine) -> List[SensorReading]:
        """Get current sensor readings for a machine."""
        readings = []
        now = datetime.utcnow()

        # Common machine attributes
        if hasattr(machine, 'spindle_load') and machine.spindle_load is not None:
            readings.append(SensorReading('spindle_load', machine.spindle_load, '%', now))
        if hasattr(machine, 'spindle_rpm') and machine.spindle_rpm is not None:
            readings.append(SensorReading('spindle_rpm', machine.spindle_rpm, 'rpm', now))
        if hasattr(machine, 'feed_rate') and machine.feed_rate is not None:
            readings.append(SensorReading('feed_rate', machine.feed_rate, 'mm/min', now))
        if hasattr(machine, 'temperature') and machine.temperature is not None:
            readings.append(SensorReading('temperature', machine.temperature, '°C', now))
        if hasattr(machine, 'vibration_rms') and machine.vibration_rms is not None:
            readings.append(SensorReading('vibration_rms', machine.vibration_rms, 'g', now))
        if hasattr(machine, 'power_consumption') and machine.power_consumption is not None:
            readings.append(SensorReading('power_draw', machine.power_consumption, 'W', now))

        # FDM-specific
        if hasattr(machine, 'nozzle_temp') and machine.nozzle_temp is not None:
            readings.append(SensorReading('nozzle_temp', machine.nozzle_temp, '°C', now))
        if hasattr(machine, 'bed_temp') and machine.bed_temp is not None:
            readings.append(SensorReading('bed_temp', machine.bed_temp, '°C', now))

        return readings

    def _check_threshold_violations(
        self,
        readings: List[SensorReading],
        thresholds: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Check readings against thresholds and return violations."""
        violations = []

        for reading in readings:
            max_key = f'{reading.parameter}_max'
            min_key = f'{reading.parameter}_min'

            if max_key in thresholds and reading.value > thresholds[max_key]:
                deviation_pct = ((reading.value - thresholds[max_key]) /
                                thresholds[max_key] * 100)
                violations.append({
                    'parameter': reading.parameter,
                    'current_value': reading.value,
                    'threshold': thresholds[max_key],
                    'threshold_type': 'max',
                    'deviation_pct': round(deviation_pct, 1),
                    'severity': 'critical' if deviation_pct > 20 else 'warning'
                })

            if min_key in thresholds and reading.value < thresholds[min_key]:
                deviation_pct = ((thresholds[min_key] - reading.value) /
                                thresholds[min_key] * 100)
                violations.append({
                    'parameter': reading.parameter,
                    'current_value': reading.value,
                    'threshold': thresholds[min_key],
                    'threshold_type': 'min',
                    'deviation_pct': round(deviation_pct, 1),
                    'severity': 'critical' if deviation_pct > 20 else 'warning'
                })

        return violations

    # =========================================================================
    # HEALTH SCORING (SENSOR FUSION)
    # =========================================================================

    def _calculate_health_score(
        self,
        readings: List[SensorReading],
        thresholds: Dict[str, float],
        machine_id: str
    ) -> HealthScore:
        """
        Calculate overall health score using sensor fusion.

        Combines multiple sensor readings into a single health metric
        with weighted importance based on parameter criticality.
        """
        # Parameter weights (criticality)
        weights = {
            'vibration_rms': 0.25,
            'spindle_load': 0.20,
            'temperature': 0.15,
            'power_draw': 0.15,
            'nozzle_temp': 0.10,
            'spindle_rpm': 0.10,
            'feed_rate': 0.05,
        }

        parameter_scores = {}
        weighted_sum = 0
        total_weight = 0

        for reading in readings:
            max_key = f'{reading.parameter}_max'
            if max_key in thresholds:
                max_val = thresholds[max_key]
                # Score: 100 at 0% of max, 0 at 100%+ of max
                normalized = min(reading.value / max_val, 1.5)  # Cap at 150%
                score = max(0, 100 * (1 - normalized))

                parameter_scores[reading.parameter] = round(score, 1)

                weight = weights.get(reading.parameter, 0.1)
                weighted_sum += score * weight
                total_weight += weight

        # Calculate overall score
        overall = (weighted_sum / total_weight) if total_weight > 0 else 100

        # Determine status
        if overall >= 90:
            status = HealthStatus.EXCELLENT
        elif overall >= 70:
            status = HealthStatus.GOOD
        elif overall >= 50:
            status = HealthStatus.FAIR
        elif overall >= 30:
            status = HealthStatus.POOR
        else:
            status = HealthStatus.CRITICAL

        # Determine trend from history
        trend = self._analyze_trend(machine_id, overall)

        # Confidence based on number of readings
        confidence = min(len(readings) / 5, 1.0)  # Max confidence with 5+ readings

        return HealthScore(
            overall_score=round(overall, 1),
            status=status,
            parameter_scores=parameter_scores,
            trend=trend,
            confidence=confidence
        )

    def _analyze_trend(self, machine_id: str, current_score: float) -> DegradationTrend:
        """Analyze degradation trend from historical data."""
        # Get or initialize history
        if machine_id not in self._degradation_history:
            self._degradation_history[machine_id] = []

        history = self._degradation_history[machine_id]

        # Add current reading
        history.append({
            'score': current_score,
            'timestamp': datetime.utcnow()
        })

        # Keep only last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        history[:] = [h for h in history if h['timestamp'] > cutoff]

        if len(history) < 3:
            return DegradationTrend.STABLE

        # Calculate trend (linear regression slope)
        scores = [h['score'] for h in history[-10:]]  # Last 10 readings
        n = len(scores)

        if n < 2:
            return DegradationTrend.STABLE

        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n

        numerator = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0

        # Interpret slope
        if slope > 2:  # Score increasing (improving)
            return DegradationTrend.IMPROVING
        elif slope < -5:  # Rapid decrease
            return DegradationTrend.RAPID_DEGRADATION
        elif slope < -1:  # Gradual decrease
            return DegradationTrend.DEGRADING
        else:
            return DegradationTrend.STABLE

    # =========================================================================
    # REMAINING USEFUL LIFE (RUL) ESTIMATION
    # =========================================================================

    def estimate_rul(self, machine_id: str) -> Optional[RULEstimate]:
        """
        Estimate Remaining Useful Life for a machine.

        Uses multiple methodologies:
        1. Linear extrapolation of degradation trend
        2. Operating hours since last maintenance
        3. Historical failure data (if available)

        Returns RUL with confidence interval.
        """
        # Method 1: Trend-based estimation
        trend_rul = self._estimate_rul_from_trend(machine_id)

        # Method 2: Operating hours based
        hours_rul = self._estimate_rul_from_hours(machine_id)

        # Method 3: Historical MTBF
        mtbf_rul = self._estimate_rul_from_mtbf(machine_id)

        # Combine estimates with weighted average
        estimates = []
        weights = []

        if trend_rul:
            estimates.append(trend_rul[0])
            weights.append(0.4)  # Trend gets highest weight
        if hours_rul:
            estimates.append(hours_rul[0])
            weights.append(0.35)
        if mtbf_rul:
            estimates.append(mtbf_rul[0])
            weights.append(0.25)

        if not estimates:
            return None

        # Weighted average
        total_weight = sum(weights)
        combined_estimate = sum(e * w for e, w in zip(estimates, weights)) / total_weight

        # Confidence based on consistency of estimates
        if len(estimates) > 1:
            variance = sum((e - combined_estimate) ** 2 for e in estimates) / len(estimates)
            std_dev = math.sqrt(variance)
            confidence = max(0.3, 1 - (std_dev / combined_estimate)) if combined_estimate > 0 else 0.3
        else:
            confidence = 0.5

        # Confidence interval (±30% at low confidence, ±10% at high)
        interval_factor = 0.1 + (1 - confidence) * 0.2
        lower_bound = combined_estimate * (1 - interval_factor)
        upper_bound = combined_estimate * (1 + interval_factor)

        return RULEstimate(
            estimated_days=round(combined_estimate, 1),
            confidence=round(confidence, 2),
            lower_bound_days=round(lower_bound, 1),
            upper_bound_days=round(upper_bound, 1),
            failure_mode='general_wear',
            methodology='ensemble'
        )

    def _estimate_rul_from_trend(self, machine_id: str) -> Optional[Tuple[float, float]]:
        """Estimate RUL from degradation trend."""
        if machine_id not in self._degradation_history:
            return None

        history = self._degradation_history[machine_id]
        if len(history) < 5:
            return None

        scores = [h['score'] for h in history[-20:]]
        timestamps = [h['timestamp'] for h in history[-20:]]

        # Calculate degradation rate (points per day)
        if len(scores) < 2:
            return None

        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 86400  # Days
        if time_span < 0.1:
            return None

        score_change = scores[0] - scores[-1]  # Positive if degrading
        daily_rate = score_change / time_span

        if daily_rate <= 0:
            # Not degrading, estimate high RUL
            return (365, 0.3)  # 1 year with low confidence

        # Project to failure threshold (score = 30)
        current_score = scores[-1]
        failure_threshold = 30

        if current_score <= failure_threshold:
            return (0, 0.9)  # Already at failure

        days_to_failure = (current_score - failure_threshold) / daily_rate
        confidence = min(0.8, 0.3 + (len(history) / 50))  # More data = more confidence

        return (days_to_failure, confidence)

    def _estimate_rul_from_hours(self, machine_id: str) -> Optional[Tuple[float, float]]:
        """Estimate RUL from operating hours since last maintenance."""
        try:
            from models.cmms.maintenance import MaintenanceWorkOrder, MaintenanceStatus

            # Find last completed maintenance
            last_maintenance = self.session.query(MaintenanceWorkOrder).filter(
                MaintenanceWorkOrder.asset_id == machine_id,
                MaintenanceWorkOrder.status == MaintenanceStatus.CLOSED
            ).order_by(MaintenanceWorkOrder.completed_at.desc()).first()

            if not last_maintenance or not last_maintenance.completed_at:
                return None

            days_since_maintenance = (datetime.utcnow() - last_maintenance.completed_at).days

            # Typical maintenance interval (could be configurable per machine)
            typical_interval = 90  # 90 days default

            remaining = max(0, typical_interval - days_since_maintenance)
            confidence = 0.6  # Medium confidence for time-based

            return (remaining, confidence)

        except ImportError:
            return None

    def _estimate_rul_from_mtbf(self, machine_id: str) -> Optional[Tuple[float, float]]:
        """Estimate RUL from historical Mean Time Between Failures."""
        try:
            from models.cmms.maintenance import MaintenanceWorkOrder, MaintenanceType, MaintenanceStatus

            # Get corrective maintenance history (failures)
            failures = self.session.query(MaintenanceWorkOrder).filter(
                MaintenanceWorkOrder.asset_id == machine_id,
                MaintenanceWorkOrder.maintenance_type == MaintenanceType.CORRECTIVE,
                MaintenanceWorkOrder.status == MaintenanceStatus.CLOSED
            ).order_by(MaintenanceWorkOrder.completed_at).all()

            if len(failures) < 2:
                return None

            # Calculate MTBF
            intervals = []
            for i in range(1, len(failures)):
                if failures[i].created_at and failures[i-1].created_at:
                    interval = (failures[i].created_at - failures[i-1].created_at).days
                    intervals.append(interval)

            if not intervals:
                return None

            mtbf = sum(intervals) / len(intervals)

            # Days since last failure
            last_failure = failures[-1].created_at
            days_since_failure = (datetime.utcnow() - last_failure).days if last_failure else 0

            remaining = max(0, mtbf - days_since_failure)
            confidence = min(0.7, 0.4 + (len(failures) / 20))  # More history = more confidence

            return (remaining, confidence)

        except ImportError:
            return None

    # =========================================================================
    # MAINTENANCE RECOMMENDATIONS
    # =========================================================================

    def _generate_recommendations(
        self,
        machine_id: str,
        violations: List[Dict],
        health: HealthScore,
        rul: Optional[RULEstimate]
    ) -> List[MaintenanceRecommendation]:
        """Generate maintenance recommendations based on conditions."""
        recommendations = []

        # Critical violations require immediate action
        critical_violations = [v for v in violations if v['severity'] == 'critical']
        if critical_violations:
            for v in critical_violations:
                recommendations.append(MaintenanceRecommendation(
                    action=f"Inspect and address {v['parameter']} issue",
                    priority='immediate',
                    reason=f"{v['parameter']} exceeds threshold by {v['deviation_pct']}%",
                    confidence=0.9,
                    spare_parts_needed=self._get_spare_parts_for_parameter(v['parameter'])
                ))

        # Poor/Critical health requires scheduled maintenance
        if health.status in [HealthStatus.POOR, HealthStatus.CRITICAL]:
            recommendations.append(MaintenanceRecommendation(
                action="Perform comprehensive maintenance inspection",
                priority='immediate' if health.status == HealthStatus.CRITICAL else 'scheduled',
                reason=f"Machine health score: {health.overall_score}% ({health.status.value})",
                confidence=health.confidence
            ))

        # Rapid degradation trend
        if health.trend == DegradationTrend.RAPID_DEGRADATION:
            recommendations.append(MaintenanceRecommendation(
                action="Investigate cause of rapid condition deterioration",
                priority='scheduled',
                reason="Rapid degradation trend detected",
                confidence=0.7
            ))

        # Low RUL
        if rul and rul.estimated_days < 14:
            recommendations.append(MaintenanceRecommendation(
                action="Plan preventive maintenance",
                priority='immediate' if rul.estimated_days < 3 else 'scheduled',
                reason=f"Estimated {rul.estimated_days:.0f} days until maintenance required",
                confidence=rul.confidence,
                recommended_date=datetime.utcnow() + timedelta(days=max(1, rul.estimated_days - 2))
            ))
        elif rul and rul.estimated_days < 30:
            recommendations.append(MaintenanceRecommendation(
                action="Schedule preventive maintenance",
                priority='scheduled',
                reason=f"Estimated {rul.estimated_days:.0f} days until maintenance required",
                confidence=rul.confidence,
                recommended_date=datetime.utcnow() + timedelta(days=rul.estimated_days * 0.7)
            ))

        # Warning violations for monitoring
        warning_violations = [v for v in violations if v['severity'] == 'warning']
        if warning_violations and not critical_violations:
            recommendations.append(MaintenanceRecommendation(
                action="Continue monitoring - early warning indicators",
                priority='monitor',
                reason=f"{len(warning_violations)} parameter(s) approaching threshold",
                confidence=0.6
            ))

        # If no issues, recommend standard PM
        if not recommendations:
            recommendations.append(MaintenanceRecommendation(
                action="Continue normal operation",
                priority='monitor',
                reason="All parameters within acceptable range",
                confidence=0.8
            ))

        return recommendations

    def _get_spare_parts_for_parameter(self, parameter: str) -> List[str]:
        """Get spare parts typically needed for a parameter issue."""
        parts_map = {
            'nozzle_temp': ['nozzle', 'heater_cartridge', 'thermistor'],
            'spindle_load': ['spindle_bearing', 'drive_belt'],
            'vibration_rms': ['bearing', 'mounting_hardware'],
            'temperature': ['cooling_fan', 'thermal_paste'],
            'power_draw': ['power_supply', 'motor_driver'],
        }
        return parts_map.get(parameter, [])

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def evaluate_all_machines(self) -> List[Dict[str, Any]]:
        """Evaluate CBM conditions for all enabled machines."""
        from models.scada.machines import Machine

        machines = self.session.query(Machine).filter(
            Machine.enabled == True
        ).all()

        results = []
        for machine in machines:
            result = self.evaluate_conditions(machine.machine_id)
            results.append(result)

        # Sort by health score (worst first)
        results.sort(key=lambda x: x.get('health', {}).get('score', 100))

        return results

    def get_maintenance_queue(self) -> List[Dict[str, Any]]:
        """Get prioritized maintenance queue based on CBM analysis."""
        evaluations = self.evaluate_all_machines()

        queue = []
        for eval_result in evaluations:
            if eval_result.get('needs_maintenance'):
                queue.append({
                    'machine_id': eval_result['machine_id'],
                    'health_score': eval_result.get('health', {}).get('score'),
                    'status': eval_result.get('health', {}).get('status'),
                    'rul_days': eval_result.get('rul_days'),
                    'violations_count': len(eval_result.get('violations', [])),
                    'recommendations': eval_result.get('recommendations', [])
                })

        return queue

    def _get_machine_type(self, machine_id: str) -> str:
        """Determine machine type from ID."""
        machine_lower = machine_id.lower()
        if 'bambu' in machine_lower or 'creality' in machine_lower or 'fdm' in machine_lower:
            return 'fdm'
        elif 'cnc' in machine_lower or 'bantam' in machine_lower:
            return 'cnc'
        elif 'laser' in machine_lower:
            return 'laser'
        return 'default'


# Convenience functions for Celery tasks
def evaluate_all_cbm(session: Session) -> List[Dict[str, Any]]:
    """Evaluate CBM for all machines (for scheduled tasks)."""
    service = CBMService(session)
    return service.evaluate_all_machines()


def get_machine_health(session: Session, machine_id: str) -> Dict[str, Any]:
    """Get health status for a specific machine."""
    service = CBMService(session)
    return service.evaluate_conditions(machine_id)
