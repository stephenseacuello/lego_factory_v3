"""
SPC Integration - Vision to SPC Chart Integration

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Vision measurement to SPC
- Control chart updates
- Rule violation detection
- Trend analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import threading
import uuid
import math
import random
from collections import defaultdict


class MeasurementType(Enum):
    """Types of vision measurements."""
    DEFECT_COUNT = "defect_count"
    DEFECT_AREA = "defect_area"
    QUALITY_SCORE = "quality_score"
    LAYER_HEIGHT = "layer_height"
    DIMENSION_X = "dimension_x"
    DIMENSION_Y = "dimension_y"
    DIMENSION_Z = "dimension_z"
    SURFACE_ROUGHNESS = "surface_roughness"
    COLOR_DEVIATION = "color_deviation"


class ChartType(Enum):
    """SPC chart types."""
    XBAR_R = "xbar_r"  # X-bar and Range
    XBAR_S = "xbar_s"  # X-bar and Std Dev
    IMR = "imr"  # Individual and Moving Range
    P_CHART = "p_chart"  # Proportion defective
    NP_CHART = "np_chart"  # Number defective
    C_CHART = "c_chart"  # Count of defects
    U_CHART = "u_chart"  # Defects per unit


class RuleViolation(Enum):
    """Western Electric rules."""
    RULE_1 = "rule_1"  # Point beyond 3 sigma
    RULE_2 = "rule_2"  # 2 of 3 points beyond 2 sigma
    RULE_3 = "rule_3"  # 4 of 5 points beyond 1 sigma
    RULE_4 = "rule_4"  # 8 consecutive points on one side
    RULE_5 = "rule_5"  # 6 points in a row increasing/decreasing
    RULE_6 = "rule_6"  # 14 points alternating up/down
    RULE_7 = "rule_7"  # 15 points within 1 sigma
    RULE_8 = "rule_8"  # 8 points beyond 1 sigma (both sides)


@dataclass
class SPCConfig:
    """SPC integration configuration."""
    sample_size: int = 5
    sigma_limits: float = 3.0
    enable_western_electric_rules: bool = True
    auto_recalculate_limits: bool = False
    min_samples_for_limits: int = 25
    update_interval_seconds: float = 60.0


@dataclass
class VisionMeasurement:
    """Measurement from vision system."""
    measurement_id: str
    measurement_type: MeasurementType
    value: float
    unit: str
    entity_id: str
    source: str  # "vision_pipeline"
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlLimits:
    """Control chart limits."""
    ucl: float  # Upper Control Limit
    cl: float  # Center Line
    lcl: float  # Lower Control Limit
    usl: Optional[float] = None  # Upper Spec Limit
    lsl: Optional[float] = None  # Lower Spec Limit
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    sample_count: int = 0


@dataclass
class ChartPoint:
    """Point on control chart."""
    point_id: str
    value: float
    timestamp: datetime
    subgroup: int
    is_violation: bool = False
    violations: List[RuleViolation] = field(default_factory=list)


@dataclass
class SPCChart:
    """SPC control chart."""
    chart_id: str
    name: str
    chart_type: ChartType
    measurement_type: MeasurementType
    entity_id: str
    limits: ControlLimits
    points: List[ChartPoint] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ViolationAlert:
    """SPC rule violation alert."""
    alert_id: str
    chart_id: str
    rule: RuleViolation
    value: float
    timestamp: datetime
    description: str
    acknowledged: bool = False


class SPCIntegration:
    """
    Integration between Vision Pipeline and SPC system.

    Features:
    - Automatic measurement collection
    - Control chart management
    - Rule violation detection
    - Trend analysis
    """

    def __init__(self, config: Optional[SPCConfig] = None):
        """
        Initialize SPC integration.

        Args:
            config: SPC configuration
        """
        self.config = config or SPCConfig()

        # Charts by entity and measurement type
        self._charts: Dict[str, Dict[str, SPCChart]] = defaultdict(dict)

        # Measurement buffer for subgroups
        self._measurement_buffers: Dict[str, List[VisionMeasurement]] = defaultdict(list)

        # Violation history
        self._violations: List[ViolationAlert] = []

        # Statistics
        self._stats = {
            "measurements_processed": 0,
            "chart_updates": 0,
            "violations_detected": 0,
        }

        # Thread safety
        self._lock = threading.RLock()

    def add_measurement(
        self,
        measurement: VisionMeasurement
    ) -> Optional[ChartPoint]:
        """
        Add a measurement to SPC tracking.

        Args:
            measurement: Vision measurement

        Returns:
            Chart point if added
        """
        with self._lock:
            self._stats["measurements_processed"] += 1

            key = f"{measurement.entity_id}_{measurement.measurement_type.value}"

            # Add to buffer
            self._measurement_buffers[key].append(measurement)

            # Check if we have a complete subgroup
            if len(self._measurement_buffers[key]) >= self.config.sample_size:
                return self._process_subgroup(
                    measurement.entity_id,
                    measurement.measurement_type
                )

            return None

    def add_measurements_from_pipeline(
        self,
        pipeline_result: Dict[str, Any],
        entity_id: str
    ) -> List[ChartPoint]:
        """
        Add measurements from pipeline result.

        Args:
            pipeline_result: Vision pipeline result
            entity_id: Entity identifier

        Returns:
            List of chart points created
        """
        points = []

        # Extract measurements
        measurements = self._extract_measurements(pipeline_result, entity_id)

        for measurement in measurements:
            point = self.add_measurement(measurement)
            if point:
                points.append(point)

        return points

    def create_chart(
        self,
        entity_id: str,
        measurement_type: MeasurementType,
        chart_type: ChartType = ChartType.IMR,
        name: Optional[str] = None,
        spec_limits: Optional[Tuple[float, float]] = None
    ) -> SPCChart:
        """
        Create a new SPC chart.

        Args:
            entity_id: Entity identifier
            measurement_type: Measurement type
            chart_type: Chart type
            name: Chart name
            spec_limits: (LSL, USL) specification limits

        Returns:
            Created chart
        """
        with self._lock:
            chart_id = str(uuid.uuid4())

            # Initial limits (will be calculated from data)
            limits = ControlLimits(
                ucl=0.0,
                cl=0.0,
                lcl=0.0,
                usl=spec_limits[1] if spec_limits else None,
                lsl=spec_limits[0] if spec_limits else None,
            )

            chart = SPCChart(
                chart_id=chart_id,
                name=name or f"{entity_id}_{measurement_type.value}",
                chart_type=chart_type,
                measurement_type=measurement_type,
                entity_id=entity_id,
                limits=limits,
            )

            self._charts[entity_id][measurement_type.value] = chart

            return chart

    def get_chart(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> Optional[SPCChart]:
        """Get a chart."""
        return self._charts.get(entity_id, {}).get(measurement_type.value)

    def get_charts(self, entity_id: str) -> List[SPCChart]:
        """Get all charts for an entity."""
        return list(self._charts.get(entity_id, {}).values())

    def calculate_limits(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> Optional[ControlLimits]:
        """
        Calculate control limits from data.

        Args:
            entity_id: Entity identifier
            measurement_type: Measurement type

        Returns:
            Calculated limits
        """
        chart = self.get_chart(entity_id, measurement_type)
        if chart is None or len(chart.points) < self.config.min_samples_for_limits:
            return None

        values = [p.value for p in chart.points]

        # Calculate statistics
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)

        # Control limits
        sigma = self.config.sigma_limits
        ucl = mean + sigma * std_dev
        lcl = mean - sigma * std_dev

        limits = ControlLimits(
            ucl=ucl,
            cl=mean,
            lcl=lcl,
            usl=chart.limits.usl,
            lsl=chart.limits.lsl,
            sample_count=len(values),
        )

        chart.limits = limits

        return limits

    def check_violations(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> List[ViolationAlert]:
        """
        Check for Western Electric rule violations.

        Args:
            entity_id: Entity identifier
            measurement_type: Measurement type

        Returns:
            List of violations
        """
        chart = self.get_chart(entity_id, measurement_type)
        if chart is None or len(chart.points) < 8:
            return []

        violations = []
        points = chart.points
        limits = chart.limits

        if limits.cl == 0:
            return []

        sigma = (limits.ucl - limits.cl) / self.config.sigma_limits

        # Check each rule
        violations.extend(self._check_rule_1(chart, points, limits, sigma))
        violations.extend(self._check_rule_2(chart, points, limits, sigma))
        violations.extend(self._check_rule_4(chart, points, limits))
        violations.extend(self._check_rule_5(chart, points))

        self._violations.extend(violations)
        self._stats["violations_detected"] += len(violations)

        return violations

    def get_trend_analysis(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> Dict[str, Any]:
        """
        Get trend analysis for a measurement.

        Args:
            entity_id: Entity identifier
            measurement_type: Measurement type

        Returns:
            Trend analysis
        """
        chart = self.get_chart(entity_id, measurement_type)
        if chart is None or len(chart.points) < 10:
            return {"error": "Insufficient data"}

        values = [p.value for p in chart.points]
        timestamps = [p.timestamp for p in chart.points]

        # Simple linear regression
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0

        # Trend direction
        if slope > 0.01:
            trend = "increasing"
        elif slope < -0.01:
            trend = "decreasing"
        else:
            trend = "stable"

        # Capability indices
        cpk = self._calculate_cpk(chart)

        return {
            "entity_id": entity_id,
            "measurement_type": measurement_type.value,
            "trend": trend,
            "slope": slope,
            "mean": y_mean,
            "std_dev": math.sqrt(sum((v - y_mean) ** 2 for v in values) / n),
            "min": min(values),
            "max": max(values),
            "cpk": cpk,
            "samples": n,
            "violations_count": sum(1 for p in chart.points if p.is_violation),
        }

    def get_capability_analysis(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> Dict[str, Any]:
        """
        Get process capability analysis.

        Args:
            entity_id: Entity identifier
            measurement_type: Measurement type

        Returns:
            Capability analysis
        """
        chart = self.get_chart(entity_id, measurement_type)
        if chart is None:
            return {"error": "Chart not found"}

        values = [p.value for p in chart.points]
        if len(values) < 30:
            return {"error": "Insufficient data (need 30+ samples)"}

        mean = sum(values) / len(values)
        std_dev = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))

        limits = chart.limits

        # Calculate capability indices
        cp = None
        cpk = None
        pp = None
        ppk = None

        if limits.usl is not None and limits.lsl is not None:
            spec_range = limits.usl - limits.lsl

            # Cp - Potential capability
            cp = spec_range / (6 * std_dev) if std_dev > 0 else None

            # Cpk - Actual capability
            cpu = (limits.usl - mean) / (3 * std_dev) if std_dev > 0 else None
            cpl = (mean - limits.lsl) / (3 * std_dev) if std_dev > 0 else None
            cpk = min(cpu, cpl) if cpu and cpl else None

        return {
            "entity_id": entity_id,
            "measurement_type": measurement_type.value,
            "mean": mean,
            "std_dev": std_dev,
            "cp": cp,
            "cpk": cpk,
            "usl": limits.usl,
            "lsl": limits.lsl,
            "ucl": limits.ucl,
            "lcl": limits.lcl,
            "samples": len(values),
            "capable": cpk >= 1.33 if cpk else None,
        }

    def get_violations(
        self,
        entity_id: Optional[str] = None,
        unacknowledged_only: bool = True
    ) -> List[ViolationAlert]:
        """Get violation alerts."""
        alerts = self._violations

        if entity_id:
            alerts = [a for a in alerts if self._get_chart_entity(a.chart_id) == entity_id]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return alerts

    def acknowledge_violation(self, alert_id: str) -> bool:
        """Acknowledge a violation."""
        for alert in self._violations:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            **self._stats,
            "charts_count": sum(len(c) for c in self._charts.values()),
            "active_violations": len([v for v in self._violations if not v.acknowledged]),
        }

    def _process_subgroup(
        self,
        entity_id: str,
        measurement_type: MeasurementType
    ) -> Optional[ChartPoint]:
        """Process a complete subgroup."""
        key = f"{entity_id}_{measurement_type.value}"
        buffer = self._measurement_buffers[key]

        if len(buffer) < self.config.sample_size:
            return None

        # Get subgroup data
        subgroup = buffer[:self.config.sample_size]
        self._measurement_buffers[key] = buffer[self.config.sample_size:]

        # Calculate subgroup statistics
        values = [m.value for m in subgroup]
        mean = sum(values) / len(values)

        # Get or create chart
        chart = self.get_chart(entity_id, measurement_type)
        if chart is None:
            chart = self.create_chart(entity_id, measurement_type)

        # Create point
        subgroup_num = len(chart.points) + 1
        point = ChartPoint(
            point_id=str(uuid.uuid4()),
            value=mean,
            timestamp=datetime.utcnow(),
            subgroup=subgroup_num,
        )

        chart.points.append(point)
        chart.updated_at = datetime.utcnow()
        self._stats["chart_updates"] += 1

        # Check violations if limits are set
        if chart.limits.ucl > 0:
            violations = self.check_violations(entity_id, measurement_type)
            if violations:
                point.is_violation = True
                point.violations = [v.rule for v in violations]

        # Recalculate limits if needed
        if (self.config.auto_recalculate_limits and
            len(chart.points) >= self.config.min_samples_for_limits):
            self.calculate_limits(entity_id, measurement_type)

        return point

    def _extract_measurements(
        self,
        pipeline_result: Dict[str, Any],
        entity_id: str
    ) -> List[VisionMeasurement]:
        """Extract measurements from pipeline result."""
        measurements = []

        # Quality score
        if "quality_score" in pipeline_result:
            measurements.append(VisionMeasurement(
                measurement_id=str(uuid.uuid4()),
                measurement_type=MeasurementType.QUALITY_SCORE,
                value=pipeline_result["quality_score"],
                unit="ratio",
                entity_id=entity_id,
                source="vision_pipeline",
                confidence=0.95,
            ))

        # Defect count
        if "defect_count" in pipeline_result:
            measurements.append(VisionMeasurement(
                measurement_id=str(uuid.uuid4()),
                measurement_type=MeasurementType.DEFECT_COUNT,
                value=float(pipeline_result["defect_count"]),
                unit="count",
                entity_id=entity_id,
                source="vision_pipeline",
                confidence=0.95,
            ))

        return measurements

    def _check_rule_1(
        self,
        chart: SPCChart,
        points: List[ChartPoint],
        limits: ControlLimits,
        sigma: float
    ) -> List[ViolationAlert]:
        """Rule 1: Point beyond 3 sigma."""
        violations = []
        point = points[-1]

        if point.value > limits.ucl or point.value < limits.lcl:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_1,
                value=point.value,
                timestamp=datetime.utcnow(),
                description=f"Point {point.value:.3f} beyond control limits",
            ))

        return violations

    def _check_rule_2(
        self,
        chart: SPCChart,
        points: List[ChartPoint],
        limits: ControlLimits,
        sigma: float
    ) -> List[ViolationAlert]:
        """Rule 2: 2 of 3 points beyond 2 sigma."""
        if len(points) < 3:
            return []

        violations = []
        last_3 = points[-3:]

        two_sigma_upper = limits.cl + 2 * sigma
        two_sigma_lower = limits.cl - 2 * sigma

        # Check upper side
        above_2sigma = sum(1 for p in last_3 if p.value > two_sigma_upper)
        if above_2sigma >= 2:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_2,
                value=last_3[-1].value,
                timestamp=datetime.utcnow(),
                description="2 of 3 points beyond 2 sigma (upper)",
            ))

        # Check lower side
        below_2sigma = sum(1 for p in last_3 if p.value < two_sigma_lower)
        if below_2sigma >= 2:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_2,
                value=last_3[-1].value,
                timestamp=datetime.utcnow(),
                description="2 of 3 points beyond 2 sigma (lower)",
            ))

        return violations

    def _check_rule_4(
        self,
        chart: SPCChart,
        points: List[ChartPoint],
        limits: ControlLimits
    ) -> List[ViolationAlert]:
        """Rule 4: 8 consecutive points on one side."""
        if len(points) < 8:
            return []

        violations = []
        last_8 = points[-8:]

        above_cl = sum(1 for p in last_8 if p.value > limits.cl)
        below_cl = sum(1 for p in last_8 if p.value < limits.cl)

        if above_cl == 8:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_4,
                value=last_8[-1].value,
                timestamp=datetime.utcnow(),
                description="8 consecutive points above center line",
            ))

        if below_cl == 8:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_4,
                value=last_8[-1].value,
                timestamp=datetime.utcnow(),
                description="8 consecutive points below center line",
            ))

        return violations

    def _check_rule_5(
        self,
        chart: SPCChart,
        points: List[ChartPoint]
    ) -> List[ViolationAlert]:
        """Rule 5: 6 points in a row increasing/decreasing."""
        if len(points) < 6:
            return []

        violations = []
        last_6 = points[-6:]
        values = [p.value for p in last_6]

        # Check increasing
        increasing = all(values[i] < values[i+1] for i in range(5))
        if increasing:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_5,
                value=last_6[-1].value,
                timestamp=datetime.utcnow(),
                description="6 points in a row increasing",
            ))

        # Check decreasing
        decreasing = all(values[i] > values[i+1] for i in range(5))
        if decreasing:
            violations.append(ViolationAlert(
                alert_id=str(uuid.uuid4()),
                chart_id=chart.chart_id,
                rule=RuleViolation.RULE_5,
                value=last_6[-1].value,
                timestamp=datetime.utcnow(),
                description="6 points in a row decreasing",
            ))

        return violations

    def _calculate_cpk(self, chart: SPCChart) -> Optional[float]:
        """Calculate Cpk for a chart."""
        if not chart.points:
            return None

        limits = chart.limits
        if limits.usl is None or limits.lsl is None:
            return None

        values = [p.value for p in chart.points]
        mean = sum(values) / len(values)
        std_dev = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))

        if std_dev == 0:
            return None

        cpu = (limits.usl - mean) / (3 * std_dev)
        cpl = (mean - limits.lsl) / (3 * std_dev)

        return min(cpu, cpl)

    def _get_chart_entity(self, chart_id: str) -> Optional[str]:
        """Get entity ID for a chart."""
        for entity_id, charts in self._charts.items():
            for chart in charts.values():
                if chart.chart_id == chart_id:
                    return entity_id
        return None


# Singleton instance
_spc_integration: Optional[SPCIntegration] = None


def get_spc_integration() -> SPCIntegration:
    """Get or create the SPC integration instance."""
    global _spc_integration
    if _spc_integration is None:
        _spc_integration = SPCIntegration()
    return _spc_integration
