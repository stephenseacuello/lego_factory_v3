"""
SPC Service - Statistical Process Control.

Handles:
- Control charts (X-bar, R, S charts)
- Process capability analysis
- Control limits calculation
- Out-of-control detection
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import math

from sqlalchemy.orm import Session

from models.quality import QualityMetric, QualityInspection

logger = logging.getLogger(__name__)


@dataclass
class ControlLimits:
    """Control chart limits."""
    ucl: float  # Upper Control Limit
    lcl: float  # Lower Control Limit
    center_line: float
    usl: Optional[float] = None  # Upper Spec Limit
    lsl: Optional[float] = None  # Lower Spec Limit


class SPCService:
    """Statistical Process Control service."""

    # Control chart constants
    # A2 factors for X-bar chart (subgroup sizes 2-10)
    A2_FACTORS = {
        2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577,
        6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308
    }

    # D3/D4 factors for R chart (subgroup sizes 2-10)
    D3_FACTORS = {
        2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223
    }
    D4_FACTORS = {
        2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114,
        6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777
    }

    def __init__(self, session: Session):
        self.session = session

    def calculate_control_limits(
        self,
        metric_name: str,
        subgroup_size: int = 5,
        num_subgroups: int = 25
    ) -> Dict[str, ControlLimits]:
        """
        Calculate control limits for X-bar and R charts.

        Args:
            metric_name: Name of metric to analyze
            subgroup_size: Size of each subgroup (default 5)
            num_subgroups: Number of subgroups to use (default 25)

        Returns:
            Dict with x_bar and range control limits
        """
        # Get recent measurements
        metrics = self.session.query(QualityMetric).filter(
            QualityMetric.metric_name == metric_name
        ).order_by(QualityMetric.created_at.desc()).limit(
            subgroup_size * num_subgroups
        ).all()

        if len(metrics) < subgroup_size * 2:
            raise ValueError(f"Insufficient data: need at least {subgroup_size * 2} samples")

        values = [m.actual_value for m in reversed(metrics)]

        # Create subgroups
        subgroups = []
        for i in range(0, len(values), subgroup_size):
            group = values[i:i + subgroup_size]
            if len(group) == subgroup_size:
                subgroups.append(group)

        if not subgroups:
            raise ValueError("Could not create subgroups")

        # Calculate subgroup statistics
        x_bars = [sum(g) / len(g) for g in subgroups]
        ranges = [max(g) - min(g) for g in subgroups]

        # Grand averages
        x_double_bar = sum(x_bars) / len(x_bars)
        r_bar = sum(ranges) / len(ranges)

        # Get factors
        a2 = self.A2_FACTORS.get(subgroup_size, 0.577)
        d3 = self.D3_FACTORS.get(subgroup_size, 0)
        d4 = self.D4_FACTORS.get(subgroup_size, 2.114)

        # X-bar chart limits
        x_bar_limits = ControlLimits(
            ucl=x_double_bar + a2 * r_bar,
            lcl=x_double_bar - a2 * r_bar,
            center_line=x_double_bar
        )

        # Get spec limits if available
        if metrics and metrics[0].target_value and metrics[0].tolerance_plus:
            x_bar_limits.usl = metrics[0].target_value + metrics[0].tolerance_plus
            x_bar_limits.lsl = metrics[0].target_value - (
                metrics[0].tolerance_minus or metrics[0].tolerance_plus
            )

        # R chart limits
        range_limits = ControlLimits(
            ucl=d4 * r_bar,
            lcl=d3 * r_bar,
            center_line=r_bar
        )

        return {
            'x_bar': x_bar_limits,
            'range': range_limits,
            'subgroup_size': subgroup_size,
            'num_subgroups': len(subgroups)
        }

    def get_control_chart_data(
        self,
        metric_name: str,
        subgroup_size: int = 5,
        num_points: int = 25
    ) -> Dict[str, Any]:
        """
        Get data for control charts.

        Returns subgrouped data with control limits for charting.
        """
        try:
            limits = self.calculate_control_limits(
                metric_name, subgroup_size, num_points
            )
        except ValueError as e:
            return {'error': str(e)}

        # Get data points
        metrics = self.session.query(QualityMetric).filter(
            QualityMetric.metric_name == metric_name
        ).order_by(QualityMetric.created_at.desc()).limit(
            subgroup_size * num_points
        ).all()

        values = [m.actual_value for m in reversed(metrics)]
        timestamps = [m.created_at for m in reversed(metrics)]

        # Create subgroups
        subgroups = []
        for i in range(0, len(values), subgroup_size):
            group_values = values[i:i + subgroup_size]
            group_times = timestamps[i:i + subgroup_size]

            if len(group_values) == subgroup_size:
                x_bar = sum(group_values) / len(group_values)
                r = max(group_values) - min(group_values)

                subgroups.append({
                    'timestamp': group_times[-1].isoformat() if group_times[-1] else None,
                    'x_bar': round(x_bar, 4),
                    'range': round(r, 4),
                    'values': [round(v, 4) for v in group_values],
                    'x_bar_in_control': limits['x_bar'].lcl <= x_bar <= limits['x_bar'].ucl,
                    'range_in_control': limits['range'].lcl <= r <= limits['range'].ucl
                })

        return {
            'metric_name': metric_name,
            'subgroup_size': subgroup_size,
            'x_bar_chart': {
                'ucl': round(limits['x_bar'].ucl, 4),
                'center_line': round(limits['x_bar'].center_line, 4),
                'lcl': round(limits['x_bar'].lcl, 4),
                'usl': round(limits['x_bar'].usl, 4) if limits['x_bar'].usl else None,
                'lsl': round(limits['x_bar'].lsl, 4) if limits['x_bar'].lsl else None
            },
            'range_chart': {
                'ucl': round(limits['range'].ucl, 4),
                'center_line': round(limits['range'].center_line, 4),
                'lcl': round(limits['range'].lcl, 4)
            },
            'data': subgroups
        }

    def check_out_of_control(
        self,
        metric_name: str,
        subgroup_size: int = 5
    ) -> Dict[str, Any]:
        """
        Check for out-of-control conditions using Western Electric rules.

        Rules checked:
        1. One point beyond 3 sigma
        2. Two of three consecutive points beyond 2 sigma
        3. Four of five consecutive points beyond 1 sigma
        4. Eight consecutive points on one side of center line
        """
        chart_data = self.get_control_chart_data(metric_name, subgroup_size)

        if 'error' in chart_data:
            return chart_data

        x_bar_limits = chart_data['x_bar_chart']
        data = chart_data['data']

        if len(data) < 8:
            return {'error': 'Need at least 8 subgroups for OOC analysis'}

        center = x_bar_limits['center_line']
        ucl = x_bar_limits['ucl']
        lcl = x_bar_limits['lcl']

        sigma = (ucl - center) / 3

        violations = []

        for i, point in enumerate(data):
            x_bar = point['x_bar']

            # Rule 1: Beyond 3 sigma
            if x_bar > ucl or x_bar < lcl:
                violations.append({
                    'rule': 1,
                    'description': 'Point beyond 3 sigma',
                    'index': i,
                    'value': x_bar
                })

            # Rule 2: Two of three beyond 2 sigma
            if i >= 2:
                recent = [data[i - j]['x_bar'] for j in range(3)]
                above_2sigma = sum(1 for v in recent if v > center + 2 * sigma)
                below_2sigma = sum(1 for v in recent if v < center - 2 * sigma)

                if above_2sigma >= 2 or below_2sigma >= 2:
                    violations.append({
                        'rule': 2,
                        'description': 'Two of three points beyond 2 sigma',
                        'index': i,
                        'value': x_bar
                    })

            # Rule 3: Four of five beyond 1 sigma
            if i >= 4:
                recent = [data[i - j]['x_bar'] for j in range(5)]
                above_1sigma = sum(1 for v in recent if v > center + sigma)
                below_1sigma = sum(1 for v in recent if v < center - sigma)

                if above_1sigma >= 4 or below_1sigma >= 4:
                    violations.append({
                        'rule': 3,
                        'description': 'Four of five points beyond 1 sigma',
                        'index': i,
                        'value': x_bar
                    })

            # Rule 4: Eight consecutive on one side
            if i >= 7:
                recent = [data[i - j]['x_bar'] for j in range(8)]
                all_above = all(v > center for v in recent)
                all_below = all(v < center for v in recent)

                if all_above or all_below:
                    violations.append({
                        'rule': 4,
                        'description': 'Eight consecutive points on one side',
                        'index': i,
                        'value': x_bar
                    })

        # Deduplicate violations by index
        seen_indices = set()
        unique_violations = []
        for v in violations:
            if v['index'] not in seen_indices:
                unique_violations.append(v)
                seen_indices.add(v['index'])

        return {
            'metric_name': metric_name,
            'in_control': len(unique_violations) == 0,
            'violations': unique_violations,
            'total_subgroups': len(data),
            'recommendation': self._get_ooc_recommendation(unique_violations)
        }

    def _get_ooc_recommendation(self, violations: List[Dict]) -> str:
        """Get recommendation based on OOC violations."""
        if not violations:
            return "Process is in statistical control. Continue monitoring."

        rules_violated = set(v['rule'] for v in violations)

        if 1 in rules_violated:
            return "STOP: Special cause detected (beyond 3 sigma). Investigate immediately."
        elif 4 in rules_violated:
            return "Process shift detected. Check for changed conditions or settings."
        elif 2 in rules_violated or 3 in rules_violated:
            return "Trend or pattern detected. Investigate potential drift in process."

        return "Out of control conditions detected. Review process parameters."

    def calculate_process_performance(
        self,
        metric_name: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Calculate Pp and Ppk (process performance indices).

        Unlike Cp/Cpk, these use all data (not just within-subgroup variation).
        """
        metrics = self.session.query(QualityMetric).filter(
            QualityMetric.metric_name == metric_name,
            QualityMetric.target_value.isnot(None),
            QualityMetric.tolerance_plus.isnot(None)
        ).order_by(QualityMetric.created_at.desc()).limit(limit).all()

        if len(metrics) < 10:
            return {
                'error': 'Insufficient data',
                'sample_count': len(metrics)
            }

        values = [m.actual_value for m in metrics]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        std_dev = math.sqrt(variance)

        target = metrics[0].target_value
        usl = target + metrics[0].tolerance_plus
        lsl = target - (metrics[0].tolerance_minus or metrics[0].tolerance_plus)

        if std_dev == 0:
            return {'error': 'Zero variation in data'}

        # Pp = (USL - LSL) / (6 * std_dev)
        pp = (usl - lsl) / (6 * std_dev)

        # Ppk = min((USL - mean) / (3 * std_dev), (mean - LSL) / (3 * std_dev))
        ppu = (usl - mean) / (3 * std_dev)
        ppl = (mean - lsl) / (3 * std_dev)
        ppk = min(ppu, ppl)

        # Calculate expected defect rate (approximate)
        # Assuming normal distribution
        z_upper = (usl - mean) / std_dev
        z_lower = (mean - lsl) / std_dev

        # Sigma level approximation
        sigma_level = min(z_upper, z_lower)

        return {
            'metric_name': metric_name,
            'sample_count': len(metrics),
            'mean': round(mean, 4),
            'std_dev': round(std_dev, 4),
            'target': target,
            'usl': usl,
            'lsl': lsl,
            'pp': round(pp, 3),
            'ppk': round(ppk, 3),
            'sigma_level': round(sigma_level, 2),
            'interpretation': self._interpret_ppk(ppk)
        }

    def _interpret_ppk(self, ppk: float) -> str:
        """Interpret Ppk value."""
        if ppk >= 2.0:
            return "World class (6 sigma)"
        elif ppk >= 1.67:
            return "Excellent (5 sigma)"
        elif ppk >= 1.33:
            return "Good (4 sigma)"
        elif ppk >= 1.0:
            return "Minimum acceptable (3 sigma)"
        elif ppk >= 0.67:
            return "Poor (2 sigma)"
        else:
            return "Very poor - process not capable"
