"""
MES Statistical Process Control (SPC) Service
===============================================
Real-time quality monitoring with control charts and capability analysis.

Features:
- Control charts (X-bar, R, S, p, np, c, u)
- Process capability indices (Cp, Cpk, Pp, Ppk)
- Out-of-control detection (Western Electric rules)
- Trend analysis and alerts
- SPC data collection and storage
"""

import logging
import math
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Control chart types."""
    XBAR_R = 'xbar_r'      # X-bar and Range
    XBAR_S = 'xbar_s'      # X-bar and Standard Deviation
    I_MR = 'i_mr'          # Individual and Moving Range
    P_CHART = 'p'          # Proportion defective
    NP_CHART = 'np'        # Number defective
    C_CHART = 'c'          # Count of defects
    U_CHART = 'u'          # Defects per unit


class AlertLevel(str, Enum):
    """Alert severity level."""
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class ViolationType(str, Enum):
    """Western Electric rule violations."""
    BEYOND_3SIGMA = 'beyond_3sigma'
    TWO_OF_THREE_BEYOND_2SIGMA = 'two_of_three_2sigma'
    FOUR_OF_FIVE_BEYOND_1SIGMA = 'four_of_five_1sigma'
    EIGHT_CONSECUTIVE_ONE_SIDE = 'eight_consecutive'
    SIX_TRENDING = 'six_trending'
    FIFTEEN_WITHIN_1SIGMA = 'fifteen_within_1sigma'
    FOURTEEN_ALTERNATING = 'fourteen_alternating'
    STRATIFICATION = 'stratification'
    MIXTURE = 'mixture'


# Control chart constants (d2, d3, A2, D3, D4) for subgroup sizes 2-25
CHART_CONSTANTS = {
    2: {'d2': 1.128, 'd3': 0.853, 'A2': 1.880, 'D3': 0, 'D4': 3.267, 'c4': 0.7979},
    3: {'d2': 1.693, 'd3': 0.888, 'A2': 1.023, 'D3': 0, 'D4': 2.574, 'c4': 0.8862},
    4: {'d2': 2.059, 'd3': 0.880, 'A2': 0.729, 'D3': 0, 'D4': 2.282, 'c4': 0.9213},
    5: {'d2': 2.326, 'd3': 0.864, 'A2': 0.577, 'D3': 0, 'D4': 2.114, 'c4': 0.9400},
    6: {'d2': 2.534, 'd3': 0.848, 'A2': 0.483, 'D3': 0, 'D4': 2.004, 'c4': 0.9515},
    7: {'d2': 2.704, 'd3': 0.833, 'A2': 0.419, 'D3': 0.076, 'D4': 1.924, 'c4': 0.9594},
    8: {'d2': 2.847, 'd3': 0.820, 'A2': 0.373, 'D3': 0.136, 'D4': 1.864, 'c4': 0.9650},
    9: {'d2': 2.970, 'd3': 0.808, 'A2': 0.337, 'D3': 0.184, 'D4': 1.816, 'c4': 0.9693},
    10: {'d2': 3.078, 'd3': 0.797, 'A2': 0.308, 'D3': 0.223, 'D4': 1.777, 'c4': 0.9727},
}


@dataclass
class SPCDataPoint:
    """Single SPC measurement."""
    point_id: str
    characteristic_id: str
    machine_id: str
    job_id: str = None
    timestamp: datetime = None
    values: List[float] = field(default_factory=list)  # Subgroup values
    mean: float = None
    range_val: float = None
    std_dev: float = None
    sample_size: int = 1
    defects: int = 0
    defectives: int = 0
    units_inspected: int = 1


@dataclass
class ControlLimits:
    """Control chart limits."""
    ucl: float  # Upper control limit
    cl: float   # Center line
    lcl: float  # Lower control limit
    usl: float = None  # Upper spec limit
    target: float = None  # Target value
    lsl: float = None  # Lower spec limit


@dataclass
class CapabilityResult:
    """Process capability analysis result."""
    cp: float = None      # Process capability
    cpk: float = None     # Process capability index
    pp: float = None      # Process performance
    ppk: float = None     # Process performance index
    cpm: float = None     # Taguchi capability index
    sigma_level: float = None
    ppm_defective: float = None
    within_spec_pct: float = None


@dataclass
class ControlChartResult:
    """Control chart analysis result."""
    chart_type: ChartType
    characteristic_id: str
    data_points: List[Dict[str, Any]]
    x_limits: ControlLimits
    r_limits: ControlLimits = None
    s_limits: ControlLimits = None
    violations: List[Dict[str, Any]] = field(default_factory=list)
    is_in_control: bool = True
    capability: CapabilityResult = None


class SPCService:
    """
    Statistical Process Control service.

    Provides:
    - Real-time control chart monitoring
    - Process capability analysis
    - Out-of-control detection
    - SPC alerts and notifications
    - Database persistence for historical analysis
    """

    def __init__(self, session: Session = None, load_from_db: bool = False):
        self.session = session
        self._data: Dict[str, List[SPCDataPoint]] = {}  # characteristic_id -> data points (cache)
        self._limits: Dict[str, ControlLimits] = {}  # characteristic_id -> limits
        self._specs: Dict[str, Dict[str, float]] = {}  # characteristic_id -> {usl, target, lsl}
        self._alert_callbacks: List[callable] = []
        self._chart_cache: Dict[str, Any] = {}  # Cache for chart definitions

        if load_from_db and session:
            self._load_charts_from_db()

    def record_measurement(
        self,
        characteristic_id: str,
        values: List[float],
        machine_id: str,
        job_id: str = None,
        timestamp: datetime = None,
        defects: int = 0,
        defectives: int = 0,
        units_inspected: int = None
    ) -> Dict[str, Any]:
        """
        Record SPC measurement(s).

        Args:
            characteristic_id: Quality characteristic ID
            values: Measured values (subgroup)
            machine_id: Machine ID
            job_id: Associated job
            timestamp: Measurement time
            defects: Count of defects (for c/u charts)
            defectives: Count of defective units (for p/np charts)
            units_inspected: Sample size for attribute charts

        Returns:
            Recorded data point with analysis
        """
        import uuid

        timestamp = timestamp or datetime.utcnow()
        values = [float(v) for v in values]

        point = SPCDataPoint(
            point_id=f"SPC-{uuid.uuid4().hex[:8].upper()}",
            characteristic_id=characteristic_id,
            machine_id=machine_id,
            job_id=job_id,
            timestamp=timestamp,
            values=values,
            mean=statistics.mean(values) if values else None,
            range_val=max(values) - min(values) if len(values) > 1 else None,
            std_dev=statistics.stdev(values) if len(values) > 1 else None,
            sample_size=len(values),
            defects=defects,
            defectives=defectives,
            units_inspected=units_inspected or len(values)
        )

        # Store data
        if characteristic_id not in self._data:
            self._data[characteristic_id] = []
        self._data[characteristic_id].append(point)

        # Keep last 100 points
        if len(self._data[characteristic_id]) > 100:
            self._data[characteristic_id] = self._data[characteristic_id][-100:]

        # Check for violations
        violations = self._check_violations(characteristic_id, point)

        # Emit alerts for violations
        if violations:
            self._emit_alerts(characteristic_id, violations, point)

        # Persist to database
        db_id = None
        if self.session:
            db_id = self._persist_measurement(point, violations)

        return {
            'point_id': point.point_id,
            'db_id': db_id,
            'characteristic_id': characteristic_id,
            'timestamp': timestamp.isoformat(),
            'mean': point.mean,
            'range': point.range_val,
            'violations': violations,
            'is_in_control': len(violations) == 0
        }

    def _persist_measurement(
        self,
        point: SPCDataPoint,
        violations: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Persist SPC measurement to database."""
        try:
            from models.qms.quality import SPCData, SPCChart

            # Find or create chart for this characteristic
            chart = self.session.query(SPCChart).filter(
                SPCChart.chart_id == point.characteristic_id
            ).first()

            if not chart:
                # Create chart definition
                chart = SPCChart(
                    chart_id=point.characteristic_id,
                    name=f"Chart for {point.characteristic_id}",
                    characteristic=point.characteristic_id,
                    chart_type='xbar_r',
                    machine_id=point.machine_id
                )
                self.session.add(chart)
                self.session.flush()

            # Get subgroup number
            last_data = self.session.query(SPCData).filter(
                SPCData.chart_id == chart.id
            ).order_by(SPCData.subgroup_number.desc()).first()

            subgroup_num = (last_data.subgroup_number + 1) if last_data and last_data.subgroup_number else 1

            # Create data record
            spc_data = SPCData(
                chart_id=chart.id,
                sample_time=point.timestamp or datetime.utcnow(),
                subgroup_number=subgroup_num,
                values=point.values,
                mean=point.mean,
                range_value=point.range_val,
                std_dev=point.std_dev,
                in_control=len(violations) == 0,
                rule_violations=[v['rule'] for v in violations] if violations else [],
                work_order_id=point.job_id
            )
            self.session.add(spc_data)
            self.session.flush()

            logger.debug(f"Persisted SPC data: {point.point_id}")
            return str(spc_data.id)

        except Exception as e:
            logger.error(f"Failed to persist SPC data: {e}")
            return None

    def _load_charts_from_db(self):
        """Load chart definitions and recent data from database."""
        try:
            from models.qms.quality import SPCChart, SPCData

            charts = self.session.query(SPCChart).filter(
                SPCChart.is_active == True
            ).all()

            for chart in charts:
                self._chart_cache[chart.chart_id] = chart

                # Load specifications
                if chart.usl or chart.lsl:
                    self._specs[chart.chart_id] = {
                        'usl': chart.usl,
                        'target': chart.target,
                        'lsl': chart.lsl
                    }

                # Load control limits
                if chart.ucl is not None and chart.lcl is not None:
                    self._limits[f"{chart.chart_id}_xbar"] = ControlLimits(
                        ucl=chart.ucl,
                        cl=chart.center_line,
                        lcl=chart.lcl,
                        usl=chart.usl,
                        target=chart.target,
                        lsl=chart.lsl
                    )

                # Load recent data into memory cache
                recent_data = self.session.query(SPCData).filter(
                    SPCData.chart_id == chart.id
                ).order_by(SPCData.sample_time.desc()).limit(100).all()

                self._data[chart.chart_id] = [
                    SPCDataPoint(
                        point_id=str(d.id),
                        characteristic_id=chart.chart_id,
                        machine_id=chart.machine_id or '',
                        job_id=d.work_order_id,
                        timestamp=d.sample_time,
                        values=d.values or [],
                        mean=d.mean,
                        range_val=d.range_value,
                        std_dev=d.std_dev,
                        sample_size=len(d.values) if d.values else 1
                    )
                    for d in reversed(recent_data)
                ]

            logger.info(f"Loaded {len(charts)} SPC charts from database")

        except Exception as e:
            logger.error(f"Failed to load SPC charts from database: {e}")

    def load_historical_data(
        self,
        characteristic_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Load historical SPC data from database.

        Args:
            characteristic_id: Quality characteristic ID
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum records to return

        Returns:
            List of SPC data points
        """
        if not self.session:
            return []

        try:
            from models.qms.quality import SPCChart, SPCData

            chart = self.session.query(SPCChart).filter(
                SPCChart.chart_id == characteristic_id
            ).first()

            if not chart:
                return []

            query = self.session.query(SPCData).filter(
                SPCData.chart_id == chart.id
            )

            if start_time:
                query = query.filter(SPCData.sample_time >= start_time)
            if end_time:
                query = query.filter(SPCData.sample_time <= end_time)

            data = query.order_by(SPCData.sample_time.desc()).limit(limit).all()

            return [
                {
                    'id': str(d.id),
                    'sample_time': d.sample_time.isoformat() if d.sample_time else None,
                    'subgroup_number': d.subgroup_number,
                    'values': d.values,
                    'mean': d.mean,
                    'range_value': d.range_value,
                    'std_dev': d.std_dev,
                    'in_control': d.in_control,
                    'rule_violations': d.rule_violations,
                    'work_order_id': d.work_order_id,
                    'lot_number': d.lot_number
                }
                for d in data
            ]

        except Exception as e:
            logger.error(f"Failed to load historical SPC data: {e}")
            return []

    def get_capability_trend(
        self,
        characteristic_id: str,
        period_days: int = 30,
        group_by: str = 'day'
    ) -> Dict[str, Any]:
        """
        Get process capability trending over time.

        Args:
            characteristic_id: Quality characteristic ID
            period_days: Number of days to analyze
            group_by: Grouping period ('day', 'week', 'shift')

        Returns:
            Capability trend data
        """
        if not self.session:
            return {'error': 'Database session required'}

        try:
            from models.qms.quality import SPCChart, SPCData

            chart = self.session.query(SPCChart).filter(
                SPCChart.chart_id == characteristic_id
            ).first()

            if not chart:
                return {'error': 'Chart not found'}

            specs = self._specs.get(characteristic_id, {})
            usl = specs.get('usl') or chart.usl
            lsl = specs.get('lsl') or chart.lsl

            if not usl or not lsl:
                return {'error': 'Specification limits required'}

            # Load data for period
            start_time = datetime.utcnow() - timedelta(days=period_days)
            data = self.session.query(SPCData).filter(
                SPCData.chart_id == chart.id,
                SPCData.sample_time >= start_time
            ).order_by(SPCData.sample_time).all()

            if len(data) < 30:
                return {'error': f'Insufficient data: {len(data)} points'}

            # Group data by period
            periods = {}
            for d in data:
                if group_by == 'day':
                    key = d.sample_time.date().isoformat()
                elif group_by == 'week':
                    week_start = d.sample_time - timedelta(days=d.sample_time.weekday())
                    key = week_start.date().isoformat()
                else:
                    key = d.sample_time.strftime('%Y-%m-%d %H:00')

                if key not in periods:
                    periods[key] = []
                if d.values:
                    periods[key].extend(d.values)

            # Calculate Cpk for each period
            trend_data = []
            for period, values in sorted(periods.items()):
                if len(values) < 10:
                    continue

                mean = statistics.mean(values)
                stdev = statistics.stdev(values) if len(values) > 1 else 0

                if stdev > 0:
                    cpu = (usl - mean) / (3 * stdev)
                    cpl = (mean - lsl) / (3 * stdev)
                    cpk = min(cpu, cpl)

                    trend_data.append({
                        'period': period,
                        'cpk': round(cpk, 3),
                        'cp': round((usl - lsl) / (6 * stdev), 3),
                        'mean': round(mean, 4),
                        'std_dev': round(stdev, 4),
                        'sample_count': len(values)
                    })

            # Calculate overall trend
            if len(trend_data) >= 2:
                cpk_values = [t['cpk'] for t in trend_data]
                trend_direction = 'improving' if cpk_values[-1] > cpk_values[0] else 'degrading'
                trend_slope = (cpk_values[-1] - cpk_values[0]) / len(cpk_values)
            else:
                trend_direction = 'stable'
                trend_slope = 0

            return {
                'characteristic_id': characteristic_id,
                'period_days': period_days,
                'group_by': group_by,
                'trend_data': trend_data,
                'trend_direction': trend_direction,
                'trend_slope': round(trend_slope, 4),
                'current_cpk': trend_data[-1]['cpk'] if trend_data else None,
                'avg_cpk': round(statistics.mean([t['cpk'] for t in trend_data]), 3) if trend_data else None,
                'specs': {'usl': usl, 'lsl': lsl}
            }

        except Exception as e:
            logger.error(f"Failed to calculate capability trend: {e}")
            return {'error': str(e)}

    def save_control_limits(
        self,
        characteristic_id: str,
        recalculate: bool = False
    ) -> Dict[str, Any]:
        """
        Save calculated control limits to database.

        Args:
            characteristic_id: Quality characteristic ID
            recalculate: Recalculate limits before saving

        Returns:
            Saved limits
        """
        if not self.session:
            return {'error': 'Database session required'}

        try:
            from models.qms.quality import SPCChart

            if recalculate:
                self.calculate_control_limits(characteristic_id, ChartType.XBAR_R)

            limits = self._limits.get(f"{characteristic_id}_xbar")
            r_limits = self._limits.get(f"{characteristic_id}_r")

            if not limits:
                return {'error': 'No control limits calculated'}

            chart = self.session.query(SPCChart).filter(
                SPCChart.chart_id == characteristic_id
            ).first()

            if not chart:
                return {'error': 'Chart not found'}

            # Update chart with limits
            chart.ucl = limits.ucl
            chart.lcl = limits.lcl
            chart.center_line = limits.cl

            if r_limits:
                chart.ucl_r = r_limits.ucl
                chart.lcl_r = r_limits.lcl
                chart.center_line_r = r_limits.cl

            # Save specs if set
            specs = self._specs.get(characteristic_id, {})
            if specs.get('usl'):
                chart.usl = specs['usl']
            if specs.get('lsl'):
                chart.lsl = specs['lsl']
            if specs.get('target'):
                chart.target = specs['target']

            self.session.flush()

            logger.info(f"Saved control limits for {characteristic_id}")

            return {
                'characteristic_id': characteristic_id,
                'x_bar': {
                    'ucl': limits.ucl,
                    'cl': limits.cl,
                    'lcl': limits.lcl
                },
                'range': {
                    'ucl': r_limits.ucl if r_limits else None,
                    'cl': r_limits.cl if r_limits else None,
                    'lcl': r_limits.lcl if r_limits else None
                } if r_limits else None
            }

        except Exception as e:
            logger.error(f"Failed to save control limits: {e}")
            return {'error': str(e)}

    def create_chart(
        self,
        chart_id: str,
        name: str,
        characteristic: str,
        chart_type: str = 'xbar_r',
        machine_id: str = None,
        usl: float = None,
        lsl: float = None,
        target: float = None,
        subgroup_size: int = 5
    ) -> Dict[str, Any]:
        """
        Create a new SPC chart definition.

        Args:
            chart_id: Unique chart identifier
            name: Chart name
            characteristic: Quality characteristic being measured
            chart_type: Type of control chart
            machine_id: Associated machine
            usl: Upper specification limit
            lsl: Lower specification limit
            target: Target value
            subgroup_size: Subgroup sample size

        Returns:
            Created chart definition
        """
        if not self.session:
            return {'error': 'Database session required'}

        try:
            from models.qms.quality import SPCChart

            # Check for existing
            existing = self.session.query(SPCChart).filter(
                SPCChart.chart_id == chart_id
            ).first()

            if existing:
                return {'error': f'Chart {chart_id} already exists'}

            chart = SPCChart(
                chart_id=chart_id,
                name=name,
                characteristic=characteristic,
                chart_type=chart_type,
                machine_id=machine_id,
                usl=usl,
                lsl=lsl,
                target=target,
                subgroup_size=subgroup_size,
                is_active=True
            )
            self.session.add(chart)
            self.session.flush()

            # Update local specs
            if usl or lsl:
                self._specs[chart_id] = {
                    'usl': usl,
                    'target': target,
                    'lsl': lsl
                }

            logger.info(f"Created SPC chart: {chart_id}")

            return chart.to_dict()

        except Exception as e:
            logger.error(f"Failed to create SPC chart: {e}")
            return {'error': str(e)}

    def get_charts(
        self,
        machine_id: str = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all SPC chart definitions.

        Args:
            machine_id: Filter by machine
            active_only: Only return active charts

        Returns:
            List of chart definitions
        """
        if not self.session:
            return []

        try:
            from models.qms.quality import SPCChart

            query = self.session.query(SPCChart)

            if machine_id:
                query = query.filter(SPCChart.machine_id == machine_id)
            if active_only:
                query = query.filter(SPCChart.is_active == True)

            charts = query.all()
            return [c.to_dict() for c in charts]

        except Exception as e:
            logger.error(f"Failed to get SPC charts: {e}")
            return []

    def set_specification_limits(
        self,
        characteristic_id: str,
        usl: float = None,
        target: float = None,
        lsl: float = None
    ) -> Dict[str, Any]:
        """
        Set specification limits for a characteristic.

        Args:
            characteristic_id: Quality characteristic ID
            usl: Upper specification limit
            target: Target value
            lsl: Lower specification limit

        Returns:
            Specification settings
        """
        self._specs[characteristic_id] = {
            'usl': usl,
            'target': target,
            'lsl': lsl
        }

        return {
            'characteristic_id': characteristic_id,
            'usl': usl,
            'target': target,
            'lsl': lsl
        }

    def calculate_control_limits(
        self,
        characteristic_id: str,
        chart_type: ChartType = ChartType.XBAR_R,
        min_points: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate control limits from collected data.

        Args:
            characteristic_id: Quality characteristic
            chart_type: Type of control chart
            min_points: Minimum data points required

        Returns:
            Calculated control limits
        """
        data = self._data.get(characteristic_id, [])
        if len(data) < min_points:
            return {
                'error': f'Insufficient data: {len(data)} points (need {min_points})'
            }

        if chart_type in (ChartType.XBAR_R, ChartType.XBAR_S):
            return self._calc_xbar_limits(data, chart_type)
        elif chart_type == ChartType.I_MR:
            return self._calc_imr_limits(data)
        elif chart_type == ChartType.P_CHART:
            return self._calc_p_limits(data)
        elif chart_type == ChartType.C_CHART:
            return self._calc_c_limits(data)
        else:
            return {'error': f'Unsupported chart type: {chart_type}'}

    def _calc_xbar_limits(
        self,
        data: List[SPCDataPoint],
        chart_type: ChartType
    ) -> Dict[str, Any]:
        """Calculate X-bar R or X-bar S control limits."""
        # Get subgroup means and ranges/stdev
        means = [p.mean for p in data if p.mean is not None]
        ranges = [p.range_val for p in data if p.range_val is not None]
        std_devs = [p.std_dev for p in data if p.std_dev is not None]

        if not means:
            return {'error': 'No valid means in data'}

        # Grand mean
        x_bar_bar = statistics.mean(means)

        # Average range or stdev
        n = data[0].sample_size if data else 5
        n = min(max(n, 2), 10)  # Clamp to available constants

        constants = CHART_CONSTANTS.get(n, CHART_CONSTANTS[5])

        if chart_type == ChartType.XBAR_R and ranges:
            r_bar = statistics.mean(ranges)
            # X-bar limits
            x_ucl = x_bar_bar + constants['A2'] * r_bar
            x_lcl = x_bar_bar - constants['A2'] * r_bar
            # R limits
            r_ucl = constants['D4'] * r_bar
            r_lcl = constants['D3'] * r_bar

            x_limits = ControlLimits(ucl=x_ucl, cl=x_bar_bar, lcl=x_lcl)
            r_limits = ControlLimits(ucl=r_ucl, cl=r_bar, lcl=r_lcl)

            self._limits[f"{data[0].characteristic_id}_xbar"] = x_limits
            self._limits[f"{data[0].characteristic_id}_r"] = r_limits

            return {
                'chart_type': chart_type.value,
                'x_bar': {
                    'ucl': round(x_ucl, 4),
                    'cl': round(x_bar_bar, 4),
                    'lcl': round(x_lcl, 4)
                },
                'range': {
                    'ucl': round(r_ucl, 4),
                    'cl': round(r_bar, 4),
                    'lcl': round(r_lcl, 4)
                },
                'sample_size': n,
                'data_points': len(data)
            }
        else:
            # X-bar S
            s_bar = statistics.mean(std_devs) if std_devs else 0
            sigma = s_bar / constants['c4']

            x_ucl = x_bar_bar + 3 * sigma / math.sqrt(n)
            x_lcl = x_bar_bar - 3 * sigma / math.sqrt(n)

            x_limits = ControlLimits(ucl=x_ucl, cl=x_bar_bar, lcl=x_lcl)
            self._limits[f"{data[0].characteristic_id}_xbar"] = x_limits

            return {
                'chart_type': chart_type.value,
                'x_bar': {
                    'ucl': round(x_ucl, 4),
                    'cl': round(x_bar_bar, 4),
                    'lcl': round(x_lcl, 4)
                },
                'sigma': round(sigma, 4),
                'sample_size': n,
                'data_points': len(data)
            }

    def _calc_imr_limits(self, data: List[SPCDataPoint]) -> Dict[str, Any]:
        """Calculate Individual and Moving Range limits."""
        values = [p.mean or p.values[0] for p in data if p.values]

        if len(values) < 2:
            return {'error': 'Need at least 2 data points'}

        # Individual chart
        x_bar = statistics.mean(values)

        # Moving ranges
        mr = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
        mr_bar = statistics.mean(mr)

        # d2 for n=2 moving range
        d2 = 1.128
        sigma = mr_bar / d2

        x_ucl = x_bar + 3 * sigma
        x_lcl = x_bar - 3 * sigma

        # MR limits
        mr_ucl = 3.267 * mr_bar  # D4 for n=2
        mr_lcl = 0

        x_limits = ControlLimits(ucl=x_ucl, cl=x_bar, lcl=x_lcl)
        mr_limits = ControlLimits(ucl=mr_ucl, cl=mr_bar, lcl=mr_lcl)

        char_id = data[0].characteristic_id
        self._limits[f"{char_id}_i"] = x_limits
        self._limits[f"{char_id}_mr"] = mr_limits

        return {
            'chart_type': 'i_mr',
            'individual': {
                'ucl': round(x_ucl, 4),
                'cl': round(x_bar, 4),
                'lcl': round(x_lcl, 4)
            },
            'moving_range': {
                'ucl': round(mr_ucl, 4),
                'cl': round(mr_bar, 4),
                'lcl': round(mr_lcl, 4)
            },
            'data_points': len(data)
        }

    def _calc_p_limits(self, data: List[SPCDataPoint]) -> Dict[str, Any]:
        """Calculate p-chart limits."""
        proportions = []
        n_values = []

        for point in data:
            if point.units_inspected > 0:
                p = point.defectives / point.units_inspected
                proportions.append(p)
                n_values.append(point.units_inspected)

        if not proportions:
            return {'error': 'No valid proportion data'}

        p_bar = sum(p * n for p, n in zip(proportions, n_values)) / sum(n_values)
        n_avg = statistics.mean(n_values)

        sigma_p = math.sqrt(p_bar * (1 - p_bar) / n_avg)

        ucl = min(1.0, p_bar + 3 * sigma_p)
        lcl = max(0.0, p_bar - 3 * sigma_p)

        limits = ControlLimits(ucl=ucl, cl=p_bar, lcl=lcl)
        self._limits[f"{data[0].characteristic_id}_p"] = limits

        return {
            'chart_type': 'p',
            'p_bar': round(p_bar, 4),
            'ucl': round(ucl, 4),
            'lcl': round(lcl, 4),
            'avg_sample_size': round(n_avg, 1),
            'data_points': len(data)
        }

    def _calc_c_limits(self, data: List[SPCDataPoint]) -> Dict[str, Any]:
        """Calculate c-chart limits."""
        counts = [p.defects for p in data if p.defects is not None]

        if not counts:
            return {'error': 'No defect count data'}

        c_bar = statistics.mean(counts)

        ucl = c_bar + 3 * math.sqrt(c_bar)
        lcl = max(0, c_bar - 3 * math.sqrt(c_bar))

        limits = ControlLimits(ucl=ucl, cl=c_bar, lcl=lcl)
        self._limits[f"{data[0].characteristic_id}_c"] = limits

        return {
            'chart_type': 'c',
            'c_bar': round(c_bar, 2),
            'ucl': round(ucl, 2),
            'lcl': round(lcl, 2),
            'data_points': len(data)
        }

    def calculate_capability(
        self,
        characteristic_id: str,
        min_points: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate process capability indices.

        Args:
            characteristic_id: Quality characteristic
            min_points: Minimum data points required

        Returns:
            Capability analysis results
        """
        data = self._data.get(characteristic_id, [])
        if len(data) < min_points:
            return {'error': f'Insufficient data: {len(data)} points (need {min_points})'}

        specs = self._specs.get(characteristic_id, {})
        usl = specs.get('usl')
        lsl = specs.get('lsl')
        target = specs.get('target')

        if usl is None or lsl is None:
            return {'error': 'Specification limits required for capability analysis'}

        # Collect all individual values
        values = []
        for point in data:
            values.extend(point.values)

        if not values:
            return {'error': 'No measurement values'}

        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0

        if stdev == 0:
            return {'error': 'Zero standard deviation'}

        # Cp: Process capability (assumes centered process)
        cp = (usl - lsl) / (6 * stdev)

        # Cpk: Process capability index (accounts for centering)
        cpu = (usl - mean) / (3 * stdev)
        cpl = (mean - lsl) / (3 * stdev)
        cpk = min(cpu, cpl)

        # Pp and Ppk (using overall variation)
        pp = cp  # Same calculation, different interpretation
        ppk = cpk

        # Cpm (Taguchi index) - if target specified
        cpm = None
        if target is not None:
            tau_sq = stdev ** 2 + (mean - target) ** 2
            cpm = (usl - lsl) / (6 * math.sqrt(tau_sq))

        # Sigma level
        sigma_level = min(cpu, cpl) * 3

        # Estimated PPM defective (assuming normal distribution)
        from_usl = self._normal_probability(usl, mean, stdev)
        from_lsl = self._normal_probability(lsl, mean, stdev)
        ppm = (from_lsl + (1 - from_usl)) * 1_000_000

        # Within spec percentage
        within_spec = (from_usl - from_lsl) * 100

        result = CapabilityResult(
            cp=round(cp, 3),
            cpk=round(cpk, 3),
            pp=round(pp, 3),
            ppk=round(ppk, 3),
            cpm=round(cpm, 3) if cpm else None,
            sigma_level=round(sigma_level, 2),
            ppm_defective=round(ppm, 0),
            within_spec_pct=round(within_spec, 2)
        )

        return {
            'characteristic_id': characteristic_id,
            'sample_size': len(values),
            'mean': round(mean, 4),
            'std_dev': round(stdev, 4),
            'usl': usl,
            'lsl': lsl,
            'target': target,
            'cp': result.cp,
            'cpk': result.cpk,
            'pp': result.pp,
            'ppk': result.ppk,
            'cpm': result.cpm,
            'sigma_level': result.sigma_level,
            'ppm_defective': result.ppm_defective,
            'within_spec_pct': result.within_spec_pct,
            'interpretation': self._interpret_capability(result.cpk)
        }

    def _normal_probability(self, x: float, mean: float, stdev: float) -> float:
        """Calculate cumulative normal probability."""
        z = (x - mean) / stdev
        # Approximation of normal CDF
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def _interpret_capability(self, cpk: float) -> str:
        """Interpret Cpk value."""
        if cpk >= 2.0:
            return "World class (Six Sigma)"
        elif cpk >= 1.67:
            return "Excellent capability"
        elif cpk >= 1.33:
            return "Good capability - meets most requirements"
        elif cpk >= 1.0:
            return "Barely capable - improvement needed"
        elif cpk >= 0.67:
            return "Poor capability - significant improvement needed"
        else:
            return "Incapable - process cannot meet specifications"

    def _check_violations(
        self,
        characteristic_id: str,
        point: SPCDataPoint
    ) -> List[Dict[str, Any]]:
        """Check for control chart violations (Western Electric rules)."""
        violations = []
        data = self._data.get(characteristic_id, [])

        # Get control limits
        limits = self._limits.get(f"{characteristic_id}_xbar") or \
                 self._limits.get(f"{characteristic_id}_i")

        if not limits or point.mean is None:
            return violations

        ucl, cl, lcl = limits.ucl, limits.cl, limits.lcl
        value = point.mean

        # Zone boundaries
        sigma = (ucl - cl) / 3
        zone_a_upper = cl + 2 * sigma
        zone_a_lower = cl - 2 * sigma
        zone_b_upper = cl + sigma
        zone_b_lower = cl - sigma

        # Rule 1: Point beyond 3-sigma
        if value > ucl or value < lcl:
            violations.append({
                'rule': ViolationType.BEYOND_3SIGMA.value,
                'description': 'Point beyond control limits',
                'level': AlertLevel.CRITICAL.value
            })

        # Get recent values for pattern rules
        if len(data) >= 2:
            recent_means = [p.mean for p in data[-10:] if p.mean is not None]

            # Rule 2: 2 of 3 points beyond 2-sigma (same side)
            if len(recent_means) >= 3:
                last_3 = recent_means[-3:]
                above_2sig = sum(1 for v in last_3 if v > zone_a_upper)
                below_2sig = sum(1 for v in last_3 if v < zone_a_lower)
                if above_2sig >= 2 or below_2sig >= 2:
                    violations.append({
                        'rule': ViolationType.TWO_OF_THREE_BEYOND_2SIGMA.value,
                        'description': '2 of 3 points beyond 2-sigma',
                        'level': AlertLevel.WARNING.value
                    })

            # Rule 3: 4 of 5 points beyond 1-sigma (same side)
            if len(recent_means) >= 5:
                last_5 = recent_means[-5:]
                above_1sig = sum(1 for v in last_5 if v > zone_b_upper)
                below_1sig = sum(1 for v in last_5 if v < zone_b_lower)
                if above_1sig >= 4 or below_1sig >= 4:
                    violations.append({
                        'rule': ViolationType.FOUR_OF_FIVE_BEYOND_1SIGMA.value,
                        'description': '4 of 5 points beyond 1-sigma',
                        'level': AlertLevel.WARNING.value
                    })

            # Rule 4: 8 consecutive points on one side
            if len(recent_means) >= 8:
                last_8 = recent_means[-8:]
                all_above = all(v > cl for v in last_8)
                all_below = all(v < cl for v in last_8)
                if all_above or all_below:
                    violations.append({
                        'rule': ViolationType.EIGHT_CONSECUTIVE_ONE_SIDE.value,
                        'description': '8 consecutive points on one side of center',
                        'level': AlertLevel.WARNING.value
                    })

            # Rule 5: 6 points trending (increasing or decreasing)
            if len(recent_means) >= 6:
                last_6 = recent_means[-6:]
                increasing = all(last_6[i] < last_6[i+1] for i in range(5))
                decreasing = all(last_6[i] > last_6[i+1] for i in range(5))
                if increasing or decreasing:
                    violations.append({
                        'rule': ViolationType.SIX_TRENDING.value,
                        'description': '6 consecutive points trending',
                        'level': AlertLevel.WARNING.value
                    })

        return violations

    def _emit_alerts(
        self,
        characteristic_id: str,
        violations: List[Dict[str, Any]],
        point: SPCDataPoint
    ):
        """Emit SPC alerts."""
        for violation in violations:
            try:
                from app import socketio
                socketio.emit('spc_alert', {
                    'characteristic_id': characteristic_id,
                    'machine_id': point.machine_id,
                    'job_id': point.job_id,
                    'timestamp': point.timestamp.isoformat() if point.timestamp else None,
                    'value': point.mean,
                    'violation': violation,
                }, namespace='/dashboard')
            except Exception as e:
                logger.debug(f"WebSocket emit failed: {e}")

        logger.warning(
            f"SPC violations on {characteristic_id}: "
            f"{[v['rule'] for v in violations]}"
        )

    def get_control_chart_data(
        self,
        characteristic_id: str,
        chart_type: ChartType = ChartType.XBAR_R,
        last_n_points: int = 50
    ) -> Dict[str, Any]:
        """
        Get control chart data for visualization.

        Args:
            characteristic_id: Quality characteristic
            chart_type: Type of control chart
            last_n_points: Number of recent points

        Returns:
            Chart data including points, limits, and violations
        """
        data = self._data.get(characteristic_id, [])[-last_n_points:]

        if not data:
            return {'error': 'No data for characteristic', 'characteristic_id': characteristic_id}

        # Get or calculate limits
        limits_key = f"{characteristic_id}_xbar"
        limits = self._limits.get(limits_key)

        if not limits:
            calc_result = self.calculate_control_limits(characteristic_id, chart_type, min_points=10)
            if 'error' in calc_result:
                limits = None
            else:
                limits = self._limits.get(limits_key)

        points = []
        for point in data:
            violations = self._check_violations(characteristic_id, point) if limits else []
            points.append({
                'point_id': point.point_id,
                'timestamp': point.timestamp.isoformat() if point.timestamp else None,
                'mean': point.mean,
                'range': point.range_val,
                'std_dev': point.std_dev,
                'sample_size': point.sample_size,
                'violations': violations,
                'is_in_control': len(violations) == 0
            })

        specs = self._specs.get(characteristic_id, {})

        return {
            'characteristic_id': characteristic_id,
            'chart_type': chart_type.value,
            'points': points,
            'limits': {
                'ucl': limits.ucl if limits else None,
                'cl': limits.cl if limits else None,
                'lcl': limits.lcl if limits else None
            } if limits else None,
            'specs': {
                'usl': specs.get('usl'),
                'target': specs.get('target'),
                'lsl': specs.get('lsl')
            },
            'point_count': len(points),
            'violation_count': sum(len(p['violations']) for p in points)
        }


# Convenience functions
def record_spc_measurement(
    session: Session,
    characteristic_id: str,
    values: List[float],
    machine_id: str,
    **kwargs
) -> Dict[str, Any]:
    """Record SPC measurement."""
    service = SPCService(session)
    return service.record_measurement(characteristic_id, values, machine_id, **kwargs)


def get_capability(
    session: Session,
    characteristic_id: str
) -> Dict[str, Any]:
    """Get process capability."""
    service = SPCService(session)
    return service.calculate_capability(characteristic_id)
