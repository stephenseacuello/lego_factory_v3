"""
LEGO Factory v3 - SPC Service
==============================
Statistical Process Control service with Western Electric rules.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import math
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models.qms import SPCChart, SPCData
from services.websocket import emit_event


# SPC Constants (A2, D3, D4 for X-bar R charts)
SPC_CONSTANTS = {
    2: {'A2': 1.880, 'D3': 0.000, 'D4': 3.267, 'd2': 1.128},
    3: {'A2': 1.023, 'D3': 0.000, 'D4': 2.574, 'd2': 1.693},
    4: {'A2': 0.729, 'D3': 0.000, 'D4': 2.282, 'd2': 2.059},
    5: {'A2': 0.577, 'D3': 0.000, 'D4': 2.114, 'd2': 2.326},
    6: {'A2': 0.483, 'D3': 0.000, 'D4': 2.004, 'd2': 2.534},
    7: {'A2': 0.419, 'D3': 0.076, 'D4': 1.924, 'd2': 2.704},
    8: {'A2': 0.373, 'D3': 0.136, 'D4': 1.864, 'd2': 2.847},
    9: {'A2': 0.337, 'D3': 0.184, 'D4': 1.816, 'd2': 2.970},
    10: {'A2': 0.308, 'D3': 0.223, 'D4': 1.777, 'd2': 3.078},
}


class SPCService:
    """SPC service implementing Western Electric rules."""

    def __init__(self, session: Session):
        self.session = session

    def create_control_chart(
        self,
        chart_id: str,
        name: str,
        characteristic: str,
        chart_type: str = 'xbar_r',
        subgroup_size: int = 5,
        process: str = None,
        unit_of_measure: str = None,
        machine_id: str = None,
        usl: float = None,
        lsl: float = None,
        target: float = None,
        initial_data: List[List[float]] = None,
    ) -> SPCChart:
        """
        Create a new SPC control chart.

        Args:
            chart_id: Unique chart identifier
            name: Chart name
            characteristic: What is being measured
            chart_type: Type of chart (xbar_r, xbar_s, p, c, u, imr)
            subgroup_size: Number of samples per subgroup
            process: Process name
            unit_of_measure: Unit of measurement
            machine_id: Associated machine ID
            usl: Upper specification limit
            lsl: Lower specification limit
            target: Target value
            initial_data: Initial data for calculating control limits

        Returns:
            Created SPCChart
        """
        chart = SPCChart(
            chart_id=chart_id,
            name=name,
            characteristic=characteristic,
            chart_type=chart_type,
            subgroup_size=subgroup_size,
            process=process,
            unit_of_measure=unit_of_measure,
            machine_id=machine_id,
            usl=usl,
            lsl=lsl,
            target=target,
            is_active=True,
        )

        self.session.add(chart)
        self.session.flush()

        # Calculate control limits from initial data if provided
        if initial_data:
            self._calculate_control_limits(chart, initial_data)

        self.session.commit()
        return chart

    def _calculate_control_limits(
        self,
        chart: SPCChart,
        data: List[List[float]],
    ) -> None:
        """Calculate control limits from historical data."""
        if chart.chart_type in ('xbar_r', 'xbar_s'):
            self._calculate_xbar_limits(chart, data)
        elif chart.chart_type == 'imr':
            self._calculate_imr_limits(chart, data)
        elif chart.chart_type == 'p':
            self._calculate_p_limits(chart, data)
        elif chart.chart_type in ('c', 'u'):
            self._calculate_count_limits(chart, data)

    def _calculate_xbar_limits(
        self,
        chart: SPCChart,
        data: List[List[float]],
    ) -> None:
        """Calculate X-bar and R chart limits."""
        n = chart.subgroup_size
        if n < 2 or n > 10:
            n = 5

        constants = SPC_CONSTANTS.get(n, SPC_CONSTANTS[5])

        # Calculate subgroup means and ranges
        means = []
        ranges = []
        for subgroup in data:
            if len(subgroup) >= 2:
                means.append(statistics.mean(subgroup))
                ranges.append(max(subgroup) - min(subgroup))

        if not means or not ranges:
            return

        # Grand mean (X-double-bar)
        x_double_bar = statistics.mean(means)
        # Average range (R-bar)
        r_bar = statistics.mean(ranges)

        # X-bar chart limits
        chart.center_line = x_double_bar
        chart.ucl = x_double_bar + constants['A2'] * r_bar
        chart.lcl = x_double_bar - constants['A2'] * r_bar

        # R chart limits
        chart.center_line_r = r_bar
        chart.ucl_r = constants['D4'] * r_bar
        chart.lcl_r = constants['D3'] * r_bar

    def _calculate_imr_limits(
        self,
        chart: SPCChart,
        data: List[List[float]],
    ) -> None:
        """Calculate Individual-Moving Range chart limits."""
        # Flatten data - each subgroup should be single values
        values = [item for sublist in data for item in sublist]

        if len(values) < 2:
            return

        # Calculate moving ranges
        moving_ranges = [
            abs(values[i] - values[i - 1])
            for i in range(1, len(values))
        ]

        x_bar = statistics.mean(values)
        mr_bar = statistics.mean(moving_ranges)

        # For n=2, d2 = 1.128, E2 = 2.66
        d2 = 1.128
        E2 = 2.66
        D4 = 3.267

        # Individual chart limits
        chart.center_line = x_bar
        chart.ucl = x_bar + E2 * mr_bar
        chart.lcl = x_bar - E2 * mr_bar

        # MR chart limits
        chart.center_line_r = mr_bar
        chart.ucl_r = D4 * mr_bar
        chart.lcl_r = 0

    def _calculate_p_limits(
        self,
        chart: SPCChart,
        data: List[List[float]],
    ) -> None:
        """Calculate p-chart limits (proportion defective)."""
        # data should be [[defectives, sample_size], ...]
        total_defectives = 0
        total_inspected = 0

        for item in data:
            if len(item) >= 2:
                total_defectives += item[0]
                total_inspected += item[1]

        if total_inspected == 0:
            return

        p_bar = total_defectives / total_inspected
        n_bar = total_inspected / len(data)

        chart.center_line = p_bar
        sigma_p = math.sqrt(p_bar * (1 - p_bar) / n_bar)
        chart.ucl = min(1.0, p_bar + 3 * sigma_p)
        chart.lcl = max(0.0, p_bar - 3 * sigma_p)

    def _calculate_count_limits(
        self,
        chart: SPCChart,
        data: List[List[float]],
    ) -> None:
        """Calculate c-chart or u-chart limits."""
        # For c-chart: data should be [count, count, ...]
        counts = [item[0] if isinstance(item, list) else item for item in data]

        if not counts:
            return

        c_bar = statistics.mean(counts)

        chart.center_line = c_bar
        chart.ucl = c_bar + 3 * math.sqrt(c_bar)
        chart.lcl = max(0, c_bar - 3 * math.sqrt(c_bar))

    def add_reading(
        self,
        chart_id: UUID,
        values: List[float],
        operator_id: str = None,
        work_order_id: str = None,
        lot_number: str = None,
        notes: str = None,
        sample_time: datetime = None,
    ) -> Tuple[SPCData, List[str]]:
        """
        Add a reading to an SPC chart and check for rule violations.

        Args:
            chart_id: Chart UUID
            values: Measurement values (subgroup)
            operator_id: Operator who took measurement
            work_order_id: Associated work order
            lot_number: Lot number
            notes: Additional notes
            sample_time: Time of measurement (defaults to now)

        Returns:
            Tuple of (SPCData record, list of rule violations)
        """
        chart = self.session.query(SPCChart).filter_by(id=chart_id).first()
        if not chart:
            raise ValueError(f"Chart {chart_id} not found")

        if sample_time is None:
            sample_time = datetime.utcnow()

        # Calculate statistics
        mean_val = statistics.mean(values) if values else 0
        range_val = max(values) - min(values) if len(values) >= 2 else 0
        std_dev = statistics.stdev(values) if len(values) >= 2 else 0

        # Get subgroup number
        last_data = self.session.query(SPCData).filter_by(
            chart_id=chart_id
        ).order_by(desc(SPCData.subgroup_number)).first()

        subgroup_number = (last_data.subgroup_number + 1) if last_data else 1

        # Check Western Electric rules
        violations = self._check_western_electric_rules(
            chart, mean_val, range_val, values
        )

        # Create data record
        data = SPCData(
            chart_id=chart_id,
            sample_time=sample_time,
            subgroup_number=subgroup_number,
            values=values,
            mean=mean_val,
            range_value=range_val,
            std_dev=std_dev,
            in_control=len(violations) == 0,
            rule_violations=violations,
            operator_id=operator_id,
            work_order_id=work_order_id,
            lot_number=lot_number,
            notes=notes,
        )

        self.session.add(data)
        self.session.commit()

        # Emit WebSocket event
        emit_event('spc_reading', {
            'chart_id': str(chart_id),
            'chart_name': chart.name,
            'mean': mean_val,
            'range': range_val,
            'in_control': data.in_control,
            'violations': violations,
            'sample_time': sample_time.isoformat(),
        }, namespace='/qms')

        return data, violations

    def _check_western_electric_rules(
        self,
        chart: SPCChart,
        current_mean: float,
        current_range: float,
        values: List[float],
    ) -> List[str]:
        """
        Check all 8 Western Electric rules.

        Returns:
            List of violated rule codes
        """
        violations = []

        if chart.ucl is None or chart.lcl is None or chart.center_line is None:
            return violations

        sigma = (chart.ucl - chart.center_line) / 3

        # Get recent readings for pattern rules
        recent_data = self.session.query(SPCData).filter_by(
            chart_id=chart.id
        ).order_by(desc(SPCData.sample_time)).limit(15).all()

        recent_means = [d.mean for d in reversed(recent_data)]
        recent_means.append(current_mean)

        # Rule 1: 1 point beyond 3 sigma
        if self._check_rule1(current_mean, chart.ucl, chart.lcl):
            violations.append('RULE1')

        # Rule 2: 2 out of 3 points beyond 2 sigma (same side)
        if self._check_rule2(recent_means, chart.center_line, sigma):
            violations.append('RULE2')

        # Rule 3: 4 out of 5 points beyond 1 sigma (same side)
        if self._check_rule3(recent_means, chart.center_line, sigma):
            violations.append('RULE3')

        # Rule 4: 8 consecutive points on same side of center line
        if self._check_rule4(recent_means, chart.center_line):
            violations.append('RULE4')

        # Rule 5: 6 consecutive points increasing or decreasing
        if self._check_rule5(recent_means):
            violations.append('RULE5')

        # Rule 6: 14 consecutive points alternating up/down
        if self._check_rule6(recent_means):
            violations.append('RULE6')

        # Rule 7: 15 consecutive points within 1 sigma (stratification)
        if self._check_rule7(recent_means, chart.center_line, sigma):
            violations.append('RULE7')

        # Rule 8: 8 consecutive points beyond 1 sigma on both sides (mixture)
        if self._check_rule8(recent_means, chart.center_line, sigma):
            violations.append('RULE8')

        return violations

    def _check_rule1(
        self,
        value: float,
        ucl: float,
        lcl: float,
    ) -> bool:
        """Rule 1: 1 point beyond 3 sigma."""
        return value > ucl or value < lcl

    def _check_rule2(
        self,
        values: List[float],
        center: float,
        sigma: float,
    ) -> bool:
        """Rule 2: 2 out of 3 consecutive points beyond 2 sigma (same side)."""
        if len(values) < 3:
            return False

        last_3 = values[-3:]
        upper_2sigma = center + 2 * sigma
        lower_2sigma = center - 2 * sigma

        above_count = sum(1 for v in last_3 if v > upper_2sigma)
        below_count = sum(1 for v in last_3 if v < lower_2sigma)

        return above_count >= 2 or below_count >= 2

    def _check_rule3(
        self,
        values: List[float],
        center: float,
        sigma: float,
    ) -> bool:
        """Rule 3: 4 out of 5 consecutive points beyond 1 sigma (same side)."""
        if len(values) < 5:
            return False

        last_5 = values[-5:]
        upper_1sigma = center + sigma
        lower_1sigma = center - sigma

        above_count = sum(1 for v in last_5 if v > upper_1sigma)
        below_count = sum(1 for v in last_5 if v < lower_1sigma)

        return above_count >= 4 or below_count >= 4

    def _check_rule4(
        self,
        values: List[float],
        center: float,
    ) -> bool:
        """Rule 4: 8 consecutive points on same side of center line."""
        if len(values) < 8:
            return False

        last_8 = values[-8:]
        above_center = [v > center for v in last_8]
        below_center = [v < center for v in last_8]

        return all(above_center) or all(below_center)

    def _check_rule5(
        self,
        values: List[float],
    ) -> bool:
        """Rule 5: 6 consecutive points increasing or decreasing."""
        if len(values) < 6:
            return False

        last_6 = values[-6:]
        increasing = all(
            last_6[i] < last_6[i + 1]
            for i in range(5)
        )
        decreasing = all(
            last_6[i] > last_6[i + 1]
            for i in range(5)
        )

        return increasing or decreasing

    def _check_rule6(
        self,
        values: List[float],
    ) -> bool:
        """Rule 6: 14 consecutive points alternating up/down."""
        if len(values) < 14:
            return False

        last_14 = values[-14:]
        alternating = True

        for i in range(12):
            diff1 = last_14[i + 1] - last_14[i]
            diff2 = last_14[i + 2] - last_14[i + 1]
            if (diff1 > 0 and diff2 > 0) or (diff1 < 0 and diff2 < 0):
                alternating = False
                break

        return alternating

    def _check_rule7(
        self,
        values: List[float],
        center: float,
        sigma: float,
    ) -> bool:
        """Rule 7: 15 consecutive points within 1 sigma (stratification)."""
        if len(values) < 15:
            return False

        last_15 = values[-15:]
        upper_1sigma = center + sigma
        lower_1sigma = center - sigma

        return all(
            lower_1sigma <= v <= upper_1sigma
            for v in last_15
        )

    def _check_rule8(
        self,
        values: List[float],
        center: float,
        sigma: float,
    ) -> bool:
        """Rule 8: 8 consecutive points beyond 1 sigma on both sides (mixture)."""
        if len(values) < 8:
            return False

        last_8 = values[-8:]
        upper_1sigma = center + sigma
        lower_1sigma = center - sigma

        all_outside = all(
            v > upper_1sigma or v < lower_1sigma
            for v in last_8
        )

        if not all_outside:
            return False

        # Check both sides are represented
        has_above = any(v > upper_1sigma for v in last_8)
        has_below = any(v < lower_1sigma for v in last_8)

        return has_above and has_below

    def recalculate_limits(
        self,
        chart_id: UUID,
        last_n_readings: int = 25,
    ) -> SPCChart:
        """
        Recalculate control limits from recent stable data.

        Args:
            chart_id: Chart UUID
            last_n_readings: Number of recent readings to use

        Returns:
            Updated SPCChart
        """
        chart = self.session.query(SPCChart).filter_by(id=chart_id).first()
        if not chart:
            raise ValueError(f"Chart {chart_id} not found")

        # Get recent in-control data
        recent_data = self.session.query(SPCData).filter(
            and_(
                SPCData.chart_id == chart_id,
                SPCData.in_control == True,
            )
        ).order_by(desc(SPCData.sample_time)).limit(last_n_readings).all()

        if len(recent_data) < 10:
            raise ValueError("Not enough in-control data for recalculation")

        # Extract values for limit calculation
        data = [d.values for d in recent_data]

        # Recalculate limits
        self._calculate_control_limits(chart, data)

        self.session.commit()
        return chart

    def get_chart_data(
        self,
        chart_id: UUID,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get chart data for visualization.

        Args:
            chart_id: Chart UUID
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of points

        Returns:
            Dict with chart definition and data points
        """
        chart = self.session.query(SPCChart).filter_by(id=chart_id).first()
        if not chart:
            raise ValueError(f"Chart {chart_id} not found")

        query = self.session.query(SPCData).filter_by(chart_id=chart_id)

        if start_time:
            query = query.filter(SPCData.sample_time >= start_time)
        if end_time:
            query = query.filter(SPCData.sample_time <= end_time)

        data = query.order_by(desc(SPCData.sample_time)).limit(limit).all()
        data = list(reversed(data))

        # Calculate warning limits (2 sigma)
        sigma = (chart.ucl - chart.center_line) / 3 if chart.ucl and chart.center_line else None
        warning_ucl = chart.center_line + 2 * sigma if sigma else None
        warning_lcl = chart.center_line - 2 * sigma if sigma else None

        return {
            'chart': chart.to_dict(),
            'limits': {
                'ucl': chart.ucl,
                'lcl': chart.lcl,
                'center_line': chart.center_line,
                'warning_ucl': warning_ucl,
                'warning_lcl': warning_lcl,
                'ucl_r': chart.ucl_r,
                'lcl_r': chart.lcl_r,
                'center_line_r': chart.center_line_r,
                'usl': chart.usl,
                'lsl': chart.lsl,
            },
            'data': [d.to_dict() for d in data],
            'summary': {
                'total_points': len(data),
                'in_control_count': sum(1 for d in data if d.in_control),
                'out_of_control_count': sum(1 for d in data if not d.in_control),
                'cp': self._calculate_cp(chart, data) if data else None,
                'cpk': self._calculate_cpk(chart, data) if data else None,
            },
        }

    def _calculate_cp(
        self,
        chart: SPCChart,
        data: List[SPCData],
    ) -> Optional[float]:
        """Calculate process capability index Cp."""
        if not chart.usl or not chart.lsl:
            return None

        means = [d.mean for d in data if d.mean is not None]
        if len(means) < 2:
            return None

        sigma = statistics.stdev(means)
        if sigma == 0:
            return None

        return (chart.usl - chart.lsl) / (6 * sigma)

    def _calculate_cpk(
        self,
        chart: SPCChart,
        data: List[SPCData],
    ) -> Optional[float]:
        """Calculate process capability index Cpk."""
        if not chart.usl or not chart.lsl:
            return None

        means = [d.mean for d in data if d.mean is not None]
        if len(means) < 2:
            return None

        process_mean = statistics.mean(means)
        sigma = statistics.stdev(means)
        if sigma == 0:
            return None

        cpu = (chart.usl - process_mean) / (3 * sigma)
        cpl = (process_mean - chart.lsl) / (3 * sigma)

        return min(cpu, cpl)

    def get_all_charts(
        self,
        machine_id: str = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all SPC charts."""
        query = self.session.query(SPCChart)

        if machine_id:
            query = query.filter_by(machine_id=machine_id)
        if active_only:
            query = query.filter_by(is_active=True)

        charts = query.all()

        result = []
        for chart in charts:
            # Get recent status
            recent_data = self.session.query(SPCData).filter_by(
                chart_id=chart.id
            ).order_by(desc(SPCData.sample_time)).limit(1).first()

            result.append({
                **chart.to_dict(),
                'last_reading': recent_data.to_dict() if recent_data else None,
                'is_out_of_control': recent_data and not recent_data.in_control if recent_data else False,
            })

        return result


# Export convenience functions
def create_spc_service(session: Session) -> SPCService:
    """Create an SPC service instance."""
    return SPCService(session)
