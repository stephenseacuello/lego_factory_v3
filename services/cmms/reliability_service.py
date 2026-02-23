"""
MTBF/MTTR Reliability Service
==============================
Calculates Mean Time Between Failures and Mean Time To Repair.

Enhanced Features:
- Weibull distribution analysis for failure prediction
- Failure Mode and Effects Analysis (FMEA) integration
- Reliability growth tracking (Duane/AMSAA models)
- Maintenance strategy optimization (PM interval tuning)
- Cost-benefit analysis for maintenance decisions
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

logger = logging.getLogger(__name__)


class FMEASeverity(Enum):
    """FMEA Severity ratings (1-10 scale)."""
    NONE = 1
    VERY_MINOR = 2
    MINOR = 3
    VERY_LOW = 4
    LOW = 5
    MODERATE = 6
    HIGH = 7
    VERY_HIGH = 8
    HAZARDOUS_WARNING = 9
    HAZARDOUS_NO_WARNING = 10


class FMEAOccurrence(Enum):
    """FMEA Occurrence ratings (1-10 scale)."""
    ALMOST_NEVER = 1
    REMOTE = 2
    VERY_SLIGHT = 3
    SLIGHT = 4
    LOW = 5
    MEDIUM = 6
    MODERATELY_HIGH = 7
    HIGH = 8
    VERY_HIGH = 9
    ALMOST_CERTAIN = 10


class FMEADetection(Enum):
    """FMEA Detection ratings (1-10 scale)."""
    ALMOST_CERTAIN = 1
    VERY_HIGH = 2
    HIGH = 3
    MODERATELY_HIGH = 4
    MEDIUM = 5
    LOW = 6
    VERY_LOW = 7
    REMOTE = 8
    VERY_REMOTE = 9
    ABSOLUTE_UNCERTAINTY = 10


@dataclass
class WeibullParameters:
    """Weibull distribution parameters."""
    beta: float  # Shape parameter (slope)
    eta: float   # Scale parameter (characteristic life)
    gamma: float = 0.0  # Location parameter (failure-free period)
    r_squared: float = 0.0  # Goodness of fit

    def reliability_at_time(self, t: float) -> float:
        """Calculate reliability R(t) at time t."""
        if t <= self.gamma:
            return 1.0
        return math.exp(-((t - self.gamma) / self.eta) ** self.beta)

    def failure_rate_at_time(self, t: float) -> float:
        """Calculate instantaneous failure rate h(t) at time t."""
        if t <= self.gamma:
            return 0.0
        return (self.beta / self.eta) * ((t - self.gamma) / self.eta) ** (self.beta - 1)

    def mean_life(self) -> float:
        """Calculate mean time to failure (MTTF)."""
        return self.gamma + self.eta * math.gamma(1 + 1 / self.beta)

    def b_life(self, percentile: float = 10) -> float:
        """Calculate B-life (time by which percentile% have failed)."""
        p = percentile / 100
        return self.gamma + self.eta * (-math.log(1 - p)) ** (1 / self.beta)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'beta': round(self.beta, 3),
            'eta': round(self.eta, 1),
            'gamma': round(self.gamma, 1),
            'r_squared': round(self.r_squared, 4),
            'interpretation': self._interpret_beta(),
            'mean_life': round(self.mean_life(), 1),
            'b10_life': round(self.b_life(10), 1),
        }

    def _interpret_beta(self) -> str:
        if self.beta < 1:
            return "Infant mortality (early failures)"
        elif self.beta == 1:
            return "Random failures (constant failure rate)"
        else:
            return "Wear-out failures (increasing failure rate)"


@dataclass
class FMEAItem:
    """FMEA (Failure Mode and Effects Analysis) item."""
    item_id: str
    machine_id: str
    component: str
    failure_mode: str
    failure_effect: str
    severity: int
    occurrence: int
    detection: int
    rpn: int = 0  # Risk Priority Number
    current_controls: str = ""
    recommended_actions: str = ""
    responsibility: str = ""
    target_date: datetime = None
    action_taken: str = ""
    new_severity: int = None
    new_occurrence: int = None
    new_detection: int = None
    new_rpn: int = None

    def __post_init__(self):
        self.rpn = self.severity * self.occurrence * self.detection
        if self.new_severity and self.new_occurrence and self.new_detection:
            self.new_rpn = self.new_severity * self.new_occurrence * self.new_detection

    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'machine_id': self.machine_id,
            'component': self.component,
            'failure_mode': self.failure_mode,
            'failure_effect': self.failure_effect,
            'severity': self.severity,
            'occurrence': self.occurrence,
            'detection': self.detection,
            'rpn': self.rpn,
            'rpn_category': self._categorize_rpn(),
            'current_controls': self.current_controls,
            'recommended_actions': self.recommended_actions,
            'new_rpn': self.new_rpn,
        }

    def _categorize_rpn(self) -> str:
        if self.rpn >= 200:
            return "critical"
        elif self.rpn >= 120:
            return "high"
        elif self.rpn >= 80:
            return "medium"
        else:
            return "low"


@dataclass
class MaintenanceCostBenefit:
    """Cost-benefit analysis for maintenance strategy."""
    machine_id: str
    strategy: str  # 'reactive', 'preventive', 'predictive'
    analysis_period_months: int

    # Costs
    preventive_cost: float = 0.0
    corrective_cost: float = 0.0
    downtime_cost: float = 0.0
    spare_parts_cost: float = 0.0
    labor_cost: float = 0.0
    total_cost: float = 0.0

    # Benefits/Savings
    downtime_savings: float = 0.0
    failure_prevention_savings: float = 0.0
    extended_life_value: float = 0.0
    total_benefit: float = 0.0

    # Metrics
    roi: float = 0.0
    payback_months: float = 0.0

    def calculate_totals(self):
        self.total_cost = (self.preventive_cost + self.corrective_cost +
                          self.downtime_cost + self.spare_parts_cost + self.labor_cost)
        self.total_benefit = (self.downtime_savings + self.failure_prevention_savings +
                             self.extended_life_value)
        if self.total_cost > 0:
            self.roi = (self.total_benefit - self.total_cost) / self.total_cost * 100
            if self.total_benefit > self.total_cost:
                monthly_benefit = (self.total_benefit - self.total_cost) / self.analysis_period_months
                self.payback_months = self.total_cost / monthly_benefit if monthly_benefit > 0 else float('inf')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'machine_id': self.machine_id,
            'strategy': self.strategy,
            'analysis_period_months': self.analysis_period_months,
            'costs': {
                'preventive': self.preventive_cost,
                'corrective': self.corrective_cost,
                'downtime': self.downtime_cost,
                'spare_parts': self.spare_parts_cost,
                'labor': self.labor_cost,
                'total': self.total_cost,
            },
            'benefits': {
                'downtime_savings': self.downtime_savings,
                'failure_prevention': self.failure_prevention_savings,
                'extended_life': self.extended_life_value,
                'total': self.total_benefit,
            },
            'metrics': {
                'roi_percent': round(self.roi, 1),
                'payback_months': round(self.payback_months, 1) if self.payback_months != float('inf') else None,
                'net_benefit': round(self.total_benefit - self.total_cost, 2),
            }
        }


class ReliabilityService:
    """Calculates reliability metrics for assets and machines."""

    def __init__(self, session):
        self.session = session

    def calculate_mtbf(self, machine_id: str, period_days: int = 90) -> Dict[str, Any]:
        """Calculate Mean Time Between Failures."""
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=period_days)
        failures = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type.in_(['alarm', 'downtime']),
            MachineEvent.created_at >= cutoff
        ).order_by(MachineEvent.created_at).all()

        breakdown_events = [f for f in failures if (f.details or {}).get('category') == 'breakdown' or f.event_type == 'alarm']

        if len(breakdown_events) < 2:
            total_hours = period_days * 24
            return {
                'machine_id': machine_id,
                'mtbf_hours': total_hours,
                'failure_count': len(breakdown_events),
                'period_days': period_days,
                'status': 'excellent',
            }

        intervals = []
        for i in range(1, len(breakdown_events)):
            interval = (breakdown_events[i].created_at - breakdown_events[i - 1].created_at).total_seconds() / 3600
            intervals.append(interval)

        mtbf = sum(intervals) / len(intervals)

        return {
            'machine_id': machine_id,
            'mtbf_hours': round(mtbf, 1),
            'failure_count': len(breakdown_events),
            'period_days': period_days,
            'status': 'good' if mtbf > 168 else 'warning' if mtbf > 48 else 'critical',
        }

    def calculate_mttr(self, machine_id: str, period_days: int = 90) -> Dict[str, Any]:
        """Calculate Mean Time To Repair from maintenance work orders."""
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=period_days)
        repair_events = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type == 'downtime',
            MachineEvent.created_at >= cutoff
        ).all()

        repair_durations = []
        for event in repair_events:
            details = event.details or {}
            duration = details.get('duration_minutes')
            if duration and details.get('category') in ('breakdown', 'planned_maintenance'):
                repair_durations.append(duration)

        if not repair_durations:
            return {
                'machine_id': machine_id,
                'mttr_hours': 0,
                'repair_count': 0,
                'period_days': period_days,
                'status': 'excellent',
            }

        mttr = sum(repair_durations) / len(repair_durations) / 60

        return {
            'machine_id': machine_id,
            'mttr_hours': round(mttr, 1),
            'repair_count': len(repair_durations),
            'period_days': period_days,
            'status': 'good' if mttr < 2 else 'warning' if mttr < 8 else 'critical',
        }

    def reliability_trend(self, machine_id: str, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly MTBF/MTTR trend."""
        trend = []
        for i in range(months - 1, -1, -1):
            month_end = datetime.utcnow() - timedelta(days=i * 30)
            mtbf = self.calculate_mtbf(machine_id, 30)
            mttr = self.calculate_mttr(machine_id, 30)
            trend.append({
                'month': month_end.strftime('%Y-%m'),
                'mtbf_hours': mtbf.get('mtbf_hours', 0),
                'mttr_hours': mttr.get('mttr_hours', 0),
            })
        return trend

    def get_worst_performers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get machines ranked by worst MTBF."""
        from models.scada.machines import Machine

        machines = self.session.query(Machine).filter(Machine.enabled == True).all()
        results = []
        for m in machines:
            mtbf = self.calculate_mtbf(m.machine_id, 90)
            mttr = self.calculate_mttr(m.machine_id, 90)
            results.append({
                'machine_id': m.machine_id,
                'name': m.name,
                'mtbf_hours': mtbf.get('mtbf_hours', 0),
                'mttr_hours': mttr.get('mttr_hours', 0),
                'failure_count': mtbf.get('failure_count', 0),
                'status': mtbf.get('status', 'unknown'),
            })
        return sorted(results, key=lambda x: x['mtbf_hours'])[:limit]

    # ==================== Weibull Analysis ====================

    def weibull_analysis(
        self,
        machine_id: str,
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Perform Weibull distribution analysis for failure prediction.

        Args:
            machine_id: Machine identifier
            period_days: Analysis period in days

        Returns:
            Weibull parameters and reliability predictions
        """
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=period_days)
        failures = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type.in_(['alarm', 'downtime']),
            MachineEvent.created_at >= cutoff
        ).order_by(MachineEvent.created_at).all()

        breakdown_events = [
            f for f in failures
            if (f.details or {}).get('category') == 'breakdown' or f.event_type == 'alarm'
        ]

        if len(breakdown_events) < 3:
            return {
                'error': f'Insufficient failures for Weibull analysis ({len(breakdown_events)} < 3)',
                'machine_id': machine_id
            }

        # Calculate time between failures (in hours)
        ttf_list = []
        for i in range(1, len(breakdown_events)):
            ttf = (breakdown_events[i].created_at - breakdown_events[i - 1].created_at).total_seconds() / 3600
            if ttf > 0:
                ttf_list.append(ttf)

        if len(ttf_list) < 2:
            return {'error': 'Insufficient time-to-failure data', 'machine_id': machine_id}

        # Fit Weibull distribution using least squares (median rank regression)
        params = self._fit_weibull(ttf_list)

        # Calculate predictions
        current_age = 0  # Hours since last failure
        if breakdown_events:
            current_age = (datetime.utcnow() - breakdown_events[-1].created_at).total_seconds() / 3600

        predictions = {
            'reliability_now': params.reliability_at_time(current_age),
            'reliability_24h': params.reliability_at_time(current_age + 24),
            'reliability_7d': params.reliability_at_time(current_age + 168),
            'reliability_30d': params.reliability_at_time(current_age + 720),
            'failure_rate_now': params.failure_rate_at_time(current_age),
            'recommended_pm_interval': params.b_life(10),  # B10 life
        }

        return {
            'machine_id': machine_id,
            'period_days': period_days,
            'failure_count': len(breakdown_events),
            'weibull_parameters': params.to_dict(),
            'predictions': {k: round(v, 4) for k, v in predictions.items()},
            'current_age_hours': round(current_age, 1),
            'recommendations': self._weibull_recommendations(params, current_age)
        }

    def _fit_weibull(self, ttf_list: List[float]) -> WeibullParameters:
        """Fit Weibull distribution using median rank regression."""
        n = len(ttf_list)
        sorted_ttf = sorted(ttf_list)

        # Calculate median ranks (Bernard's approximation)
        ranks = [(i - 0.3) / (n + 0.4) for i in range(1, n + 1)]

        # Linearize: Y = ln(ln(1/(1-F))), X = ln(t)
        x = [math.log(t) for t in sorted_ttf]
        y = [math.log(-math.log(1 - r)) for r in ranks]

        # Linear regression
        n_points = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        beta = (n_points * sum_xy - sum_x * sum_y) / (n_points * sum_x2 - sum_x ** 2)
        intercept = (sum_y - beta * sum_x) / n_points
        eta = math.exp(-intercept / beta)

        # Calculate R-squared
        y_mean = sum_y / n_points
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        y_pred = [beta * xi + intercept for xi in x]
        ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return WeibullParameters(
            beta=max(0.1, beta),  # Ensure positive
            eta=max(1, eta),
            gamma=0,
            r_squared=r_squared
        )

    def _weibull_recommendations(
        self,
        params: WeibullParameters,
        current_age: float
    ) -> List[str]:
        """Generate maintenance recommendations based on Weibull analysis."""
        recommendations = []

        # Based on beta (shape parameter)
        if params.beta < 1:
            recommendations.append(
                "Beta < 1 indicates infant mortality. Investigate quality issues, "
                "installation problems, or burn-in requirements."
            )
        elif params.beta > 3:
            recommendations.append(
                "Beta > 3 indicates strong wear-out pattern. Consider age-based "
                "preventive replacement before B10 life."
            )

        # Based on current reliability
        reliability_now = params.reliability_at_time(current_age)
        if reliability_now < 0.5:
            recommendations.append(
                f"Current reliability ({reliability_now:.1%}) is below 50%. "
                "Schedule preventive maintenance immediately."
            )
        elif reliability_now < 0.8:
            recommendations.append(
                f"Current reliability ({reliability_now:.1%}) is degraded. "
                "Plan maintenance within next week."
            )

        # PM interval recommendation
        b10 = params.b_life(10)
        recommendations.append(
            f"Recommended PM interval: {b10:.0f} hours (B10 life). "
            "This ensures 90% reliability between maintenance."
        )

        return recommendations

    # ==================== FMEA Integration ====================

    def create_fmea_item(
        self,
        machine_id: str,
        component: str,
        failure_mode: str,
        failure_effect: str,
        severity: int,
        occurrence: int,
        detection: int,
        current_controls: str = "",
        recommended_actions: str = ""
    ) -> FMEAItem:
        """
        Create an FMEA item for a machine component.

        Args:
            machine_id: Machine identifier
            component: Component name
            failure_mode: How the component can fail
            failure_effect: Effect of the failure
            severity: Severity rating (1-10)
            occurrence: Occurrence rating (1-10)
            detection: Detection rating (1-10)
            current_controls: Current detection/prevention controls
            recommended_actions: Recommended actions to reduce RPN

        Returns:
            FMEAItem with calculated RPN
        """
        import uuid

        item = FMEAItem(
            item_id=f"FMEA-{uuid.uuid4().hex[:8].upper()}",
            machine_id=machine_id,
            component=component,
            failure_mode=failure_mode,
            failure_effect=failure_effect,
            severity=min(10, max(1, severity)),
            occurrence=min(10, max(1, occurrence)),
            detection=min(10, max(1, detection)),
            current_controls=current_controls,
            recommended_actions=recommended_actions
        )

        logger.info(f"Created FMEA item {item.item_id} with RPN {item.rpn}")
        return item

    def get_fmea_analysis(
        self,
        machine_id: str,
        failure_history_days: int = 180
    ) -> Dict[str, Any]:
        """
        Generate FMEA analysis based on actual failure history.

        Args:
            machine_id: Machine identifier
            failure_history_days: Days of history to analyze

        Returns:
            FMEA analysis with auto-generated items from failure data
        """
        from models.scada.machines import Machine, MachineEvent
        from collections import Counter

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=failure_history_days)
        failures = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type.in_(['alarm', 'downtime']),
            MachineEvent.created_at >= cutoff
        ).all()

        # Analyze failure patterns
        failure_modes = Counter()
        severity_by_mode = {}
        duration_by_mode = {}

        for f in failures:
            details = f.details or {}
            mode = details.get('reason', details.get('category', 'unknown'))
            failure_modes[mode] += 1

            # Track severity based on duration
            duration = details.get('duration_minutes', 0)
            if mode not in duration_by_mode:
                duration_by_mode[mode] = []
            duration_by_mode[mode].append(duration)

        # Generate FMEA items from patterns
        fmea_items = []
        total_failures = sum(failure_modes.values())

        for mode, count in failure_modes.most_common():
            # Calculate occurrence based on frequency
            occurrence_rate = count / failure_history_days * 30  # Monthly rate
            if occurrence_rate >= 4:
                occurrence = 9
            elif occurrence_rate >= 2:
                occurrence = 7
            elif occurrence_rate >= 1:
                occurrence = 5
            elif occurrence_rate >= 0.5:
                occurrence = 3
            else:
                occurrence = 2

            # Calculate severity based on average duration
            avg_duration = sum(duration_by_mode.get(mode, [0])) / max(1, count)
            if avg_duration >= 480:  # 8+ hours
                severity = 9
            elif avg_duration >= 120:  # 2+ hours
                severity = 7
            elif avg_duration >= 30:
                severity = 5
            else:
                severity = 3

            # Default detection (can be improved with CBM)
            detection = 6  # Medium - some controls but not fully predictive

            item = FMEAItem(
                item_id=f"FMEA-{machine_id}-{mode[:8].upper()}",
                machine_id=machine_id,
                component=mode,
                failure_mode=f"{mode} failure",
                failure_effect=f"Downtime due to {mode}",
                severity=severity,
                occurrence=occurrence,
                detection=detection,
                current_controls="Standard monitoring"
            )
            fmea_items.append(item)

        # Sort by RPN (highest first)
        fmea_items.sort(key=lambda x: x.rpn, reverse=True)

        return {
            'machine_id': machine_id,
            'analysis_period_days': failure_history_days,
            'total_failures': total_failures,
            'fmea_items': [item.to_dict() for item in fmea_items],
            'high_rpn_items': [item.to_dict() for item in fmea_items if item.rpn >= 120],
            'critical_items': [item.to_dict() for item in fmea_items if item.rpn >= 200],
            'summary': {
                'total_items': len(fmea_items),
                'critical_count': len([i for i in fmea_items if i.rpn >= 200]),
                'high_count': len([i for i in fmea_items if 120 <= i.rpn < 200]),
                'avg_rpn': round(sum(i.rpn for i in fmea_items) / len(fmea_items), 1) if fmea_items else 0
            }
        }

    # ==================== Reliability Growth ====================

    def reliability_growth_analysis(
        self,
        machine_id: str,
        period_months: int = 12
    ) -> Dict[str, Any]:
        """
        Analyze reliability growth using Duane model.

        The Duane model tracks MTBF improvement over time as corrective
        actions are implemented.

        Args:
            machine_id: Machine identifier
            period_months: Analysis period in months

        Returns:
            Reliability growth analysis
        """
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        # Get monthly MTBF data
        monthly_data = []
        for i in range(period_months - 1, -1, -1):
            month_start = datetime.utcnow() - timedelta(days=(i + 1) * 30)
            month_end = datetime.utcnow() - timedelta(days=i * 30)

            failures = self.session.query(MachineEvent).filter(
                MachineEvent.machine_id == machine.id,
                MachineEvent.event_type.in_(['alarm', 'downtime']),
                MachineEvent.created_at >= month_start,
                MachineEvent.created_at < month_end
            ).all()

            breakdown_count = len([
                f for f in failures
                if (f.details or {}).get('category') == 'breakdown' or f.event_type == 'alarm'
            ])

            operating_hours = 30 * 24  # Assume 24/7 operation
            mtbf = operating_hours / breakdown_count if breakdown_count > 0 else operating_hours

            monthly_data.append({
                'month': month_end.strftime('%Y-%m'),
                'cumulative_time': (period_months - i) * operating_hours,
                'cumulative_failures': sum(d.get('failures', 0) for d in monthly_data) + breakdown_count,
                'mtbf': mtbf,
                'failures': breakdown_count
            })

        # Calculate Duane growth rate (alpha)
        if len(monthly_data) >= 3:
            # Use log-linear regression on cumulative MTBF vs time
            cum_times = [d['cumulative_time'] for d in monthly_data if d['cumulative_failures'] > 0]
            cum_mtbfs = [
                d['cumulative_time'] / d['cumulative_failures']
                for d in monthly_data if d['cumulative_failures'] > 0
            ]

            if len(cum_times) >= 2 and all(t > 0 for t in cum_times) and all(m > 0 for m in cum_mtbfs):
                # Log transform
                log_times = [math.log(t) for t in cum_times]
                log_mtbfs = [math.log(m) for m in cum_mtbfs]

                # Linear regression
                n = len(log_times)
                sum_x = sum(log_times)
                sum_y = sum(log_mtbfs)
                sum_xy = sum(x * y for x, y in zip(log_times, log_mtbfs))
                sum_x2 = sum(x ** 2 for x in log_times)

                alpha = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
            else:
                alpha = 0
        else:
            alpha = 0

        # Interpret growth rate
        if alpha > 0.3:
            growth_status = "excellent"
            interpretation = "Strong reliability improvement observed"
        elif alpha > 0.1:
            growth_status = "good"
            interpretation = "Positive reliability trend"
        elif alpha > 0:
            growth_status = "marginal"
            interpretation = "Slight improvement, consider more corrective actions"
        else:
            growth_status = "declining"
            interpretation = "Reliability is degrading, urgent action needed"

        # Project future MTBF
        current_mtbf = monthly_data[-1]['mtbf'] if monthly_data else 0
        projected_mtbf_6m = current_mtbf * (1 + alpha) ** 6 if alpha > 0 else current_mtbf

        return {
            'machine_id': machine_id,
            'period_months': period_months,
            'monthly_data': monthly_data,
            'growth_rate_alpha': round(alpha, 4),
            'growth_status': growth_status,
            'interpretation': interpretation,
            'current_mtbf': round(current_mtbf, 1),
            'projected_mtbf_6m': round(projected_mtbf_6m, 1),
            'improvement_actions_needed': alpha < 0.1
        }

    # ==================== PM Interval Optimization ====================

    def optimize_pm_interval(
        self,
        machine_id: str,
        current_pm_interval_hours: float,
        pm_cost: float,
        failure_cost: float,
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Optimize preventive maintenance interval based on cost analysis.

        Uses Weibull analysis to find the optimal PM interval that minimizes
        total maintenance cost.

        Args:
            machine_id: Machine identifier
            current_pm_interval_hours: Current PM interval
            pm_cost: Cost of preventive maintenance
            failure_cost: Cost of corrective maintenance (including downtime)
            period_days: Analysis period

        Returns:
            Optimal PM interval and cost comparison
        """
        # Get Weibull parameters
        weibull_result = self.weibull_analysis(machine_id, period_days)

        if 'error' in weibull_result:
            return weibull_result

        params = WeibullParameters(
            beta=weibull_result['weibull_parameters']['beta'],
            eta=weibull_result['weibull_parameters']['eta'],
            gamma=0
        )

        # Calculate optimal interval using cost minimization
        # Total cost = (PM cost / interval) + (failure cost * failure rate)
        intervals_to_test = [i for i in range(24, int(params.eta * 2), 24)]  # Test intervals

        best_interval = current_pm_interval_hours
        best_cost = float('inf')
        cost_data = []

        for interval in intervals_to_test:
            reliability = params.reliability_at_time(interval)
            failure_prob = 1 - reliability

            # Expected annual PM events
            pm_events_per_year = 8760 / interval

            # Expected failures per year (simplified model)
            expected_failures = pm_events_per_year * failure_prob

            # Annual cost
            pm_annual_cost = pm_events_per_year * pm_cost
            failure_annual_cost = expected_failures * failure_cost
            total_annual_cost = pm_annual_cost + failure_annual_cost

            cost_data.append({
                'interval_hours': interval,
                'reliability': round(reliability, 4),
                'pm_cost': round(pm_annual_cost, 2),
                'failure_cost': round(failure_annual_cost, 2),
                'total_cost': round(total_annual_cost, 2)
            })

            if total_annual_cost < best_cost:
                best_cost = total_annual_cost
                best_interval = interval

        # Calculate current vs optimal comparison
        current_idx = min(range(len(cost_data)),
                         key=lambda i: abs(cost_data[i]['interval_hours'] - current_pm_interval_hours))
        current_cost = cost_data[current_idx]['total_cost']

        return {
            'machine_id': machine_id,
            'current_interval_hours': current_pm_interval_hours,
            'optimal_interval_hours': best_interval,
            'weibull_beta': params.beta,
            'weibull_eta': params.eta,
            'cost_comparison': {
                'current_annual_cost': current_cost,
                'optimal_annual_cost': best_cost,
                'potential_savings': round(current_cost - best_cost, 2),
                'savings_percent': round((current_cost - best_cost) / current_cost * 100, 1) if current_cost > 0 else 0
            },
            'recommendation': (
                f"Change PM interval from {current_pm_interval_hours}h to {best_interval}h "
                f"for ${current_cost - best_cost:.2f} annual savings"
                if best_interval != current_pm_interval_hours else
                "Current PM interval is optimal"
            ),
            'cost_curve': cost_data[:20]  # First 20 data points
        }

    # ==================== Cost-Benefit Analysis ====================

    def maintenance_cost_benefit(
        self,
        machine_id: str,
        analysis_months: int = 12,
        pm_cost_per_event: float = 500,
        cm_cost_per_event: float = 2000,
        downtime_cost_per_hour: float = 500,
        hourly_production_value: float = 200
    ) -> Dict[str, Any]:
        """
        Perform cost-benefit analysis comparing maintenance strategies.

        Compares reactive, preventive, and predictive maintenance strategies.

        Args:
            machine_id: Machine identifier
            analysis_months: Analysis period in months
            pm_cost_per_event: Cost of preventive maintenance event
            cm_cost_per_event: Cost of corrective/reactive maintenance
            downtime_cost_per_hour: Cost of unplanned downtime per hour
            hourly_production_value: Value of production per hour

        Returns:
            Cost-benefit analysis for different strategies
        """
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()
        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=analysis_months * 30)
        events = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type.in_(['alarm', 'downtime', 'maintenance']),
            MachineEvent.created_at >= cutoff
        ).all()

        # Count events by type
        breakdown_count = 0
        pm_count = 0
        total_downtime_hours = 0

        for e in events:
            details = e.details or {}
            if details.get('category') == 'breakdown' or e.event_type == 'alarm':
                breakdown_count += 1
                total_downtime_hours += details.get('duration_minutes', 60) / 60
            elif details.get('category') == 'planned_maintenance':
                pm_count += 1

        # === Reactive Strategy ===
        reactive = MaintenanceCostBenefit(
            machine_id=machine_id,
            strategy='reactive',
            analysis_period_months=analysis_months
        )
        reactive.corrective_cost = breakdown_count * cm_cost_per_event
        reactive.downtime_cost = total_downtime_hours * downtime_cost_per_hour
        reactive.labor_cost = breakdown_count * 4 * 50  # 4 hours @ $50/hr
        reactive.calculate_totals()

        # === Preventive Strategy ===
        # Assume PM reduces breakdowns by 60%
        preventive = MaintenanceCostBenefit(
            machine_id=machine_id,
            strategy='preventive',
            analysis_period_months=analysis_months
        )
        pm_events_needed = analysis_months  # Monthly PM
        reduced_breakdowns = int(breakdown_count * 0.4)
        reduced_downtime = total_downtime_hours * 0.4

        preventive.preventive_cost = pm_events_needed * pm_cost_per_event
        preventive.corrective_cost = reduced_breakdowns * cm_cost_per_event
        preventive.downtime_cost = reduced_downtime * downtime_cost_per_hour
        preventive.labor_cost = (pm_events_needed * 2 + reduced_breakdowns * 4) * 50

        preventive.downtime_savings = (total_downtime_hours - reduced_downtime) * hourly_production_value
        preventive.failure_prevention_savings = (breakdown_count - reduced_breakdowns) * cm_cost_per_event
        preventive.calculate_totals()

        # === Predictive Strategy ===
        # Assume predictive reduces breakdowns by 85%
        predictive = MaintenanceCostBenefit(
            machine_id=machine_id,
            strategy='predictive',
            analysis_period_months=analysis_months
        )
        cbm_events = int(analysis_months * 0.5)  # Less frequent, condition-based
        predicted_breakdowns = int(breakdown_count * 0.15)
        predicted_downtime = total_downtime_hours * 0.15

        predictive.preventive_cost = cbm_events * pm_cost_per_event * 1.2  # Slightly higher due to sensors
        predictive.corrective_cost = predicted_breakdowns * cm_cost_per_event
        predictive.downtime_cost = predicted_downtime * downtime_cost_per_hour
        predictive.spare_parts_cost = 500  # Sensor/monitoring costs
        predictive.labor_cost = (cbm_events * 1.5 + predicted_breakdowns * 4) * 50

        predictive.downtime_savings = (total_downtime_hours - predicted_downtime) * hourly_production_value
        predictive.failure_prevention_savings = (breakdown_count - predicted_breakdowns) * cm_cost_per_event
        predictive.extended_life_value = analysis_months * 100  # Extended equipment life value
        predictive.calculate_totals()

        # Find best strategy
        strategies = [reactive, preventive, predictive]
        best = min(strategies, key=lambda s: s.total_cost)

        return {
            'machine_id': machine_id,
            'analysis_period_months': analysis_months,
            'historical_data': {
                'breakdown_count': breakdown_count,
                'pm_count': pm_count,
                'total_downtime_hours': round(total_downtime_hours, 1)
            },
            'strategies': {
                'reactive': reactive.to_dict(),
                'preventive': preventive.to_dict(),
                'predictive': predictive.to_dict()
            },
            'recommendation': {
                'best_strategy': best.strategy,
                'annual_cost': round(best.total_cost, 2),
                'vs_reactive_savings': round(reactive.total_cost - best.total_cost, 2),
                'roi': round(best.roi, 1)
            }
        }
