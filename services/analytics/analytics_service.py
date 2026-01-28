"""
Advanced Analytics Service.

Provides comprehensive analytics capabilities for:
- Production efficiency metrics (OEE, TEEP)
- Quality metrics and trend analysis
- Predictive maintenance indicators
- Real-time KPI dashboards
- Statistical process control (SPC)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
import math

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of analytics metrics."""
    GAUGE = "gauge"           # Current value
    COUNTER = "counter"       # Cumulative count
    HISTOGRAM = "histogram"   # Distribution
    RATE = "rate"            # Rate per time unit


class TimeGranularity(Enum):
    """Time granularity for aggregation."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class OEEMetrics:
    """Overall Equipment Effectiveness metrics."""
    availability: float  # % of planned time equipment was running
    performance: float   # % of theoretical maximum speed
    quality: float      # % of good parts produced
    oee: float          # Availability * Performance * Quality
    planned_production_time: float  # hours
    actual_running_time: float      # hours
    ideal_cycle_time: float         # seconds per part
    total_count: int
    good_count: int
    downtime_minutes: float = 0
    speed_loss_count: int = 0
    defect_count: int = 0

    @classmethod
    def calculate(
        cls,
        planned_time_hrs: float,
        running_time_hrs: float,
        ideal_cycle_sec: float,
        total_parts: int,
        good_parts: int
    ) -> "OEEMetrics":
        """Calculate OEE from raw data."""
        availability = running_time_hrs / planned_time_hrs if planned_time_hrs > 0 else 0

        # Theoretical parts at ideal cycle time
        theoretical_parts = (running_time_hrs * 3600) / ideal_cycle_sec if ideal_cycle_sec > 0 else 0
        performance = total_parts / theoretical_parts if theoretical_parts > 0 else 0

        quality = good_parts / total_parts if total_parts > 0 else 0

        oee = availability * performance * quality

        return cls(
            availability=round(availability * 100, 2),
            performance=round(performance * 100, 2),
            quality=round(quality * 100, 2),
            oee=round(oee * 100, 2),
            planned_production_time=planned_time_hrs,
            actual_running_time=running_time_hrs,
            ideal_cycle_time=ideal_cycle_sec,
            total_count=total_parts,
            good_count=good_parts,
            downtime_minutes=(planned_time_hrs - running_time_hrs) * 60,
            speed_loss_count=max(0, int(theoretical_parts - total_parts)),
            defect_count=total_parts - good_parts
        )


@dataclass
class SPCData:
    """Statistical Process Control data."""
    values: List[float]
    mean: float
    std_dev: float
    ucl: float  # Upper Control Limit
    lcl: float  # Lower Control Limit
    usl: Optional[float] = None  # Upper Spec Limit
    lsl: Optional[float] = None  # Lower Spec Limit
    cp: Optional[float] = None   # Process Capability
    cpk: Optional[float] = None  # Process Capability Index
    out_of_control: List[int] = field(default_factory=list)
    rule_violations: List[Dict[str, Any]] = field(default_factory=list)


class AnalyticsService:
    """
    Advanced analytics service for manufacturing data.

    Provides:
    - OEE (Overall Equipment Effectiveness) calculation
    - SPC (Statistical Process Control) analysis
    - Trend analysis and forecasting
    - Quality metrics and Pareto analysis
    - Predictive maintenance scoring
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._kpi_cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # seconds

        logger.info("Analytics Service initialized")

    # ==================== OEE Analysis ====================

    def calculate_oee(
        self,
        equipment_id: str,
        start_time: datetime,
        end_time: datetime,
        production_data: Optional[Dict] = None
    ) -> OEEMetrics:
        """
        Calculate OEE for equipment over a time period.

        Args:
            equipment_id: Equipment identifier
            start_time: Period start
            end_time: Period end
            production_data: Optional pre-fetched data

        Returns:
            OEEMetrics dataclass
        """
        # In production, would fetch from database
        # Using example calculation here
        if production_data is None:
            production_data = self._fetch_production_data(
                equipment_id, start_time, end_time
            )

        return OEEMetrics.calculate(
            planned_time_hrs=production_data.get('planned_time', 8.0),
            running_time_hrs=production_data.get('running_time', 7.2),
            ideal_cycle_sec=production_data.get('ideal_cycle', 10.0),
            total_parts=production_data.get('total_parts', 2500),
            good_parts=production_data.get('good_parts', 2400)
        )

    def calculate_line_oee(
        self,
        line_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Calculate OEE for an entire production line.

        Returns aggregate and per-equipment OEE.
        """
        # Get equipment in line
        equipment_list = self._get_line_equipment(line_id)

        equipment_oee = {}
        total_availability = 0
        total_performance = 0
        total_quality = 0

        for equip_id in equipment_list:
            oee = self.calculate_oee(equip_id, start_time, end_time)
            equipment_oee[equip_id] = oee
            total_availability += oee.availability
            total_performance += oee.performance
            total_quality += oee.quality

        n = len(equipment_list) or 1
        avg_availability = total_availability / n
        avg_performance = total_performance / n
        avg_quality = total_quality / n

        return {
            'line_id': line_id,
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'aggregate_oee': {
                'availability': round(avg_availability, 2),
                'performance': round(avg_performance, 2),
                'quality': round(avg_quality, 2),
                'oee': round((avg_availability * avg_performance * avg_quality) / 10000, 2)
            },
            'equipment_oee': {
                k: {
                    'availability': v.availability,
                    'performance': v.performance,
                    'quality': v.quality,
                    'oee': v.oee
                }
                for k, v in equipment_oee.items()
            },
            'bottleneck': min(equipment_oee.items(), key=lambda x: x[1].oee)[0] if equipment_oee else None
        }

    # ==================== SPC Analysis ====================

    def calculate_spc(
        self,
        values: List[float],
        usl: Optional[float] = None,
        lsl: Optional[float] = None,
        sigma_multiplier: float = 3.0
    ) -> SPCData:
        """
        Perform Statistical Process Control analysis.

        Args:
            values: Measurement values
            usl: Upper specification limit
            lsl: Lower specification limit
            sigma_multiplier: Multiplier for control limits (default 3-sigma)

        Returns:
            SPCData with control limits and capability metrics
        """
        if len(values) < 2:
            raise ValueError("Need at least 2 values for SPC analysis")

        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)

        ucl = mean + (sigma_multiplier * std_dev)
        lcl = mean - (sigma_multiplier * std_dev)

        # Find out-of-control points
        out_of_control = [
            i for i, v in enumerate(values)
            if v > ucl or v < lcl
        ]

        # Check Western Electric rules
        rule_violations = self._check_western_electric_rules(values, mean, std_dev)

        # Calculate process capability if spec limits provided
        cp = None
        cpk = None

        if usl is not None and lsl is not None and std_dev > 0:
            cp = (usl - lsl) / (6 * std_dev)
            cpu = (usl - mean) / (3 * std_dev)
            cpl = (mean - lsl) / (3 * std_dev)
            cpk = min(cpu, cpl)

        return SPCData(
            values=values,
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
            ucl=round(ucl, 4),
            lcl=round(lcl, 4),
            usl=usl,
            lsl=lsl,
            cp=round(cp, 4) if cp else None,
            cpk=round(cpk, 4) if cpk else None,
            out_of_control=out_of_control,
            rule_violations=rule_violations
        )

    def _check_western_electric_rules(
        self,
        values: List[float],
        mean: float,
        std_dev: float
    ) -> List[Dict[str, Any]]:
        """Check Western Electric rules for out-of-control conditions."""
        violations = []

        if len(values) < 8:
            return violations

        one_sigma = std_dev
        two_sigma = 2 * std_dev

        # Rule 1: One point beyond 3 sigma (already checked in out_of_control)

        # Rule 2: 2 of 3 consecutive points beyond 2 sigma
        for i in range(2, len(values)):
            window = values[i-2:i+1]
            beyond_2sigma = sum(1 for v in window if abs(v - mean) > two_sigma)
            if beyond_2sigma >= 2:
                violations.append({
                    'rule': 2,
                    'description': '2 of 3 points beyond 2 sigma',
                    'index': i
                })

        # Rule 3: 4 of 5 consecutive points beyond 1 sigma
        for i in range(4, len(values)):
            window = values[i-4:i+1]
            beyond_1sigma = sum(1 for v in window if abs(v - mean) > one_sigma)
            if beyond_1sigma >= 4:
                violations.append({
                    'rule': 3,
                    'description': '4 of 5 points beyond 1 sigma',
                    'index': i
                })

        # Rule 4: 8 consecutive points on same side of center
        for i in range(7, len(values)):
            window = values[i-7:i+1]
            above = all(v > mean for v in window)
            below = all(v < mean for v in window)
            if above or below:
                violations.append({
                    'rule': 4,
                    'description': '8 consecutive points on same side',
                    'index': i
                })

        return violations

    # ==================== Quality Analytics ====================

    def pareto_analysis(
        self,
        defect_data: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Perform Pareto analysis on defect data.

        Args:
            defect_data: Dict of defect_type -> count

        Returns:
            Pareto analysis results
        """
        total = sum(defect_data.values())

        if total == 0:
            return {'categories': [], 'cumulative_percent': [], 'vital_few': []}

        # Sort by count descending
        sorted_defects = sorted(defect_data.items(), key=lambda x: x[1], reverse=True)

        cumulative = 0
        results = []
        vital_few = []

        for defect_type, count in sorted_defects:
            percent = (count / total) * 100
            cumulative += percent

            results.append({
                'defect_type': defect_type,
                'count': count,
                'percent': round(percent, 2),
                'cumulative_percent': round(cumulative, 2)
            })

            # 80/20 rule - vital few
            if cumulative <= 80:
                vital_few.append(defect_type)

        return {
            'total_defects': total,
            'categories': results,
            'vital_few': vital_few,
            'trivial_many': [d[0] for d in sorted_defects if d[0] not in vital_few]
        }

    def calculate_dpmo(
        self,
        defects: int,
        units: int,
        opportunities_per_unit: int
    ) -> Dict[str, float]:
        """
        Calculate Defects Per Million Opportunities.

        Returns DPMO and approximate sigma level.
        """
        if units == 0 or opportunities_per_unit == 0:
            return {'dpmo': 0, 'sigma_level': 6.0, 'yield_percent': 100.0}

        total_opportunities = units * opportunities_per_unit
        dpmo = (defects / total_opportunities) * 1_000_000
        yield_percent = ((total_opportunities - defects) / total_opportunities) * 100

        # Approximate sigma level from DPMO
        sigma_level = self._dpmo_to_sigma(dpmo)

        return {
            'dpmo': round(dpmo, 2),
            'sigma_level': round(sigma_level, 2),
            'yield_percent': round(yield_percent, 4),
            'defects': defects,
            'units': units,
            'opportunities': total_opportunities
        }

    def _dpmo_to_sigma(self, dpmo: float) -> float:
        """Convert DPMO to approximate sigma level."""
        if dpmo <= 0:
            return 6.0
        elif dpmo >= 1_000_000:
            return 0.0

        # Approximate formula
        from math import log10
        return 0.8406 + (29.37 - 2.221 * log10(dpmo)) ** 0.5

    # ==================== Trend Analysis ====================

    def calculate_trend(
        self,
        time_series: List[Tuple[datetime, float]],
        forecast_periods: int = 5
    ) -> Dict[str, Any]:
        """
        Calculate trend and simple forecast.

        Args:
            time_series: List of (timestamp, value) tuples
            forecast_periods: Number of periods to forecast

        Returns:
            Trend analysis and forecast
        """
        if len(time_series) < 3:
            return {'error': 'Need at least 3 data points'}

        values = [v[1] for v in time_series]

        # Calculate moving averages
        ma_3 = self._moving_average(values, 3)
        ma_5 = self._moving_average(values, 5) if len(values) >= 5 else []

        # Linear regression for trend
        x = list(range(len(values)))
        slope, intercept = self._linear_regression(x, values)

        # Determine trend direction
        if slope > 0.01:
            trend_direction = "increasing"
        elif slope < -0.01:
            trend_direction = "decreasing"
        else:
            trend_direction = "stable"

        # Simple linear forecast
        forecast = []
        last_x = len(values)
        for i in range(forecast_periods):
            forecast_x = last_x + i
            forecast_value = intercept + (slope * forecast_x)
            forecast.append({
                'period': i + 1,
                'value': round(forecast_value, 4)
            })

        return {
            'current_value': values[-1],
            'mean': round(statistics.mean(values), 4),
            'std_dev': round(statistics.stdev(values), 4) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values),
            'trend_direction': trend_direction,
            'slope': round(slope, 6),
            'moving_average_3': [round(v, 4) for v in ma_3],
            'moving_average_5': [round(v, 4) for v in ma_5],
            'forecast': forecast
        }

    def _moving_average(self, values: List[float], window: int) -> List[float]:
        """Calculate moving average."""
        if len(values) < window:
            return []

        result = []
        for i in range(len(values) - window + 1):
            avg = sum(values[i:i+window]) / window
            result.append(avg)
        return result

    def _linear_regression(
        self,
        x: List[float],
        y: List[float]
    ) -> Tuple[float, float]:
        """Calculate simple linear regression (slope, intercept)."""
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return 0, sum_y / n if n > 0 else 0

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        return slope, intercept

    # ==================== Predictive Maintenance ====================

    def calculate_health_score(
        self,
        equipment_id: str,
        sensor_readings: Dict[str, float],
        thresholds: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Calculate equipment health score for predictive maintenance.

        Args:
            equipment_id: Equipment identifier
            sensor_readings: Current sensor values
            thresholds: Dict of sensor -> {warning, critical} thresholds

        Returns:
            Health score and recommendations
        """
        warnings = []
        critical_issues = []
        scores = {}

        for sensor, value in sensor_readings.items():
            if sensor not in thresholds:
                scores[sensor] = 100
                continue

            thresh = thresholds[sensor]
            warning_thresh = thresh.get('warning', float('inf'))
            critical_thresh = thresh.get('critical', float('inf'))

            if value >= critical_thresh:
                scores[sensor] = 0
                critical_issues.append({
                    'sensor': sensor,
                    'value': value,
                    'threshold': critical_thresh,
                    'severity': 'critical'
                })
            elif value >= warning_thresh:
                # Linear score between warning and critical
                range_size = critical_thresh - warning_thresh
                score = 100 - (((value - warning_thresh) / range_size) * 100) if range_size > 0 else 50
                scores[sensor] = max(0, score)
                warnings.append({
                    'sensor': sensor,
                    'value': value,
                    'threshold': warning_thresh,
                    'severity': 'warning'
                })
            else:
                # Score based on distance from warning
                if warning_thresh > 0:
                    score = min(100, (1 - (value / warning_thresh)) * 100 + 50)
                else:
                    score = 100
                scores[sensor] = score

        overall_score = sum(scores.values()) / len(scores) if scores else 100

        # Generate recommendations
        recommendations = []
        if critical_issues:
            recommendations.append("Immediate maintenance required")
        if warnings:
            recommendations.append("Schedule preventive maintenance")
        if overall_score < 50:
            recommendations.append("Increase monitoring frequency")

        return {
            'equipment_id': equipment_id,
            'overall_health_score': round(overall_score, 2),
            'sensor_scores': {k: round(v, 2) for k, v in scores.items()},
            'warnings': warnings,
            'critical_issues': critical_issues,
            'recommendations': recommendations,
            'maintenance_priority': 'high' if overall_score < 50 else 'medium' if overall_score < 75 else 'low',
            'timestamp': datetime.utcnow().isoformat()
        }

    # ==================== KPI Dashboard ====================

    def get_production_kpis(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Get key production KPIs for dashboard.
        """
        # In production, would fetch real data
        return {
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'production': {
                'total_units': 15420,
                'good_units': 14890,
                'defect_rate_percent': 3.44,
                'throughput_per_hour': 1285
            },
            'efficiency': {
                'oee': 78.5,
                'availability': 92.3,
                'performance': 88.7,
                'quality': 96.6
            },
            'quality': {
                'first_pass_yield': 96.6,
                'dpmo': 34400,
                'sigma_level': 3.3,
                'open_ncrs': 5,
                'open_capas': 3
            },
            'maintenance': {
                'mtbf_hours': 168.5,
                'mttr_hours': 2.3,
                'planned_downtime_percent': 5.2,
                'unplanned_downtime_percent': 2.5
            }
        }

    # ==================== Helper Methods ====================

    def _fetch_production_data(
        self,
        equipment_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Fetch production data from database."""
        # Placeholder - would query actual database
        return {
            'planned_time': 8.0,
            'running_time': 7.2,
            'ideal_cycle': 10.0,
            'total_parts': 2500,
            'good_parts': 2400
        }

    def _get_line_equipment(self, line_id: str) -> List[str]:
        """Get equipment IDs for a production line."""
        # Placeholder - would query actual database
        return [f"{line_id}_equip_{i}" for i in range(1, 5)]


# Singleton instance
analytics_service = AnalyticsService()
