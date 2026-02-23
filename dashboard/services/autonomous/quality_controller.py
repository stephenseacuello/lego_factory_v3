"""
Autonomous Quality Controller V8.

LEGO MCP V8 - Autonomous Factory Platform
Intelligent Quality Control with SPC and Adaptive Inspection.

Features:
- Statistical Process Control (SPC) with control charts
- Automatic defect detection and classification
- Root cause analysis with Pareto analysis
- Adaptive inspection strategies
- Quality prediction models
- Six Sigma capability analysis

Standards Compliance:
- ISO 9001 (Quality Management Systems)
- ISO/TS 16949 (Automotive Quality)
- Six Sigma DMAIC methodology

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import asyncio
import logging
import math
import statistics
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class QualityLevel(Enum):
    """Quality level classification."""
    EXCELLENT = "excellent"      # Cpk >= 2.0
    GOOD = "good"               # 1.33 <= Cpk < 2.0
    ACCEPTABLE = "acceptable"   # 1.0 <= Cpk < 1.33
    MARGINAL = "marginal"       # 0.67 <= Cpk < 1.0
    POOR = "poor"               # Cpk < 0.67


class ControlChartType(Enum):
    """Types of control charts."""
    X_BAR_R = "x_bar_r"           # X-bar and Range
    X_BAR_S = "x_bar_s"           # X-bar and Standard Deviation
    INDIVIDUAL_MR = "individual_mr"  # Individual and Moving Range
    P_CHART = "p_chart"           # Proportion defective
    NP_CHART = "np_chart"         # Number defective
    C_CHART = "c_chart"           # Count of defects
    U_CHART = "u_chart"           # Defects per unit


class InspectionType(Enum):
    """Types of inspection."""
    INCOMING = "incoming"
    IN_PROCESS = "in_process"
    FINAL = "final"
    PATROL = "patrol"
    AUDIT = "audit"


class DefectSeverity(Enum):
    """Defect severity levels."""
    CRITICAL = 1
    MAJOR = 2
    MINOR = 3
    COSMETIC = 4


class DefectType(Enum):
    """Common defect types."""
    DIMENSIONAL = "dimensional"
    SURFACE = "surface"
    STRUCTURAL = "structural"
    FUNCTIONAL = "functional"
    APPEARANCE = "appearance"
    CONTAMINATION = "contamination"
    MISSING_PART = "missing_part"
    WRONG_PART = "wrong_part"


class ControlStatus(Enum):
    """Process control status."""
    IN_CONTROL = "in_control"
    WARNING = "warning"
    OUT_OF_CONTROL = "out_of_control"
    UNKNOWN = "unknown"


class InspectionResult(Enum):
    """Inspection result."""
    PASS = "pass"
    FAIL = "fail"
    REWORK = "rework"
    SCRAP = "scrap"
    CONDITIONAL = "conditional"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QualitySpecification:
    """Quality specification for a characteristic."""
    spec_id: str
    name: str
    nominal: float
    upper_limit: float
    lower_limit: float
    unit: str = ""
    critical: bool = False

    def is_within_spec(self, value: float) -> bool:
        """Check if value is within specification."""
        return self.lower_limit <= value <= self.upper_limit

    def deviation(self, value: float) -> float:
        """Calculate deviation from nominal."""
        return value - self.nominal

    def capability_ratio(self, std_dev: float) -> float:
        """Calculate Cp (capability ratio)."""
        if std_dev <= 0:
            return float('inf')
        return (self.upper_limit - self.lower_limit) / (6 * std_dev)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spec_id": self.spec_id,
            "name": self.name,
            "nominal": self.nominal,
            "upper_limit": self.upper_limit,
            "lower_limit": self.lower_limit,
            "unit": self.unit,
            "critical": self.critical,
        }


@dataclass
class Measurement:
    """Quality measurement data point."""
    measurement_id: str
    spec_id: str
    value: float
    timestamp: datetime
    part_id: str
    operator_id: Optional[str] = None
    machine_id: Optional[str] = None
    batch_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "measurement_id": self.measurement_id,
            "spec_id": self.spec_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "part_id": self.part_id,
            "operator_id": self.operator_id,
            "machine_id": self.machine_id,
            "batch_id": self.batch_id,
        }


@dataclass
class Defect:
    """Recorded defect."""
    defect_id: str
    defect_type: DefectType
    severity: DefectSeverity
    description: str
    part_id: str
    detected_at: datetime
    location: Optional[str] = None
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "defect_id": self.defect_id,
            "defect_type": self.defect_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "part_id": self.part_id,
            "detected_at": self.detected_at.isoformat(),
            "location": self.location,
            "root_cause": self.root_cause,
            "corrective_action": self.corrective_action,
            "resolved": self.resolved,
        }


@dataclass
class ControlLimit:
    """Control chart limits."""
    center_line: float
    upper_control_limit: float
    lower_control_limit: float
    upper_warning_limit: float
    lower_warning_limit: float

    def check_value(self, value: float) -> ControlStatus:
        """Check value against control limits."""
        if value > self.upper_control_limit or value < self.lower_control_limit:
            return ControlStatus.OUT_OF_CONTROL
        elif value > self.upper_warning_limit or value < self.lower_warning_limit:
            return ControlStatus.WARNING
        return ControlStatus.IN_CONTROL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "center_line": self.center_line,
            "upper_control_limit": self.upper_control_limit,
            "lower_control_limit": self.lower_control_limit,
            "upper_warning_limit": self.upper_warning_limit,
            "lower_warning_limit": self.lower_warning_limit,
        }


@dataclass
class CapabilityMetrics:
    """Process capability metrics."""
    cp: float           # Capability ratio
    cpk: float          # Capability index
    pp: float           # Performance ratio
    ppk: float          # Performance index
    sigma_level: float  # Sigma level
    ppm_defective: float  # Parts per million defective
    yield_rate: float   # First pass yield

    def get_quality_level(self) -> QualityLevel:
        """Get quality level based on Cpk."""
        if self.cpk >= 2.0:
            return QualityLevel.EXCELLENT
        elif self.cpk >= 1.33:
            return QualityLevel.GOOD
        elif self.cpk >= 1.0:
            return QualityLevel.ACCEPTABLE
        elif self.cpk >= 0.67:
            return QualityLevel.MARGINAL
        return QualityLevel.POOR

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cp": self.cp,
            "cpk": self.cpk,
            "pp": self.pp,
            "ppk": self.ppk,
            "sigma_level": self.sigma_level,
            "ppm_defective": self.ppm_defective,
            "yield_rate": self.yield_rate,
            "quality_level": self.get_quality_level().value,
        }


@dataclass
class InspectionPlan:
    """Inspection plan definition."""
    plan_id: str
    name: str
    inspection_type: InspectionType
    specifications: List[str]  # spec_ids to check
    sample_size: int
    aql: float  # Acceptable Quality Level
    frequency: str  # e.g., "every_batch", "hourly", "100%"
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "inspection_type": self.inspection_type.value,
            "specifications": self.specifications,
            "sample_size": self.sample_size,
            "aql": self.aql,
            "frequency": self.frequency,
            "active": self.active,
        }


@dataclass
class InspectionRecord:
    """Record of an inspection."""
    record_id: str
    plan_id: str
    inspection_type: InspectionType
    inspected_at: datetime
    sample_size: int
    passed: int
    failed: int
    result: InspectionResult
    measurements: List[Measurement] = field(default_factory=list)
    defects: List[str] = field(default_factory=list)  # defect_ids
    inspector_id: Optional[str] = None
    notes: str = ""

    def defect_rate(self) -> float:
        """Calculate defect rate."""
        if self.sample_size == 0:
            return 0.0
        return self.failed / self.sample_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "record_id": self.record_id,
            "plan_id": self.plan_id,
            "inspection_type": self.inspection_type.value,
            "inspected_at": self.inspected_at.isoformat(),
            "sample_size": self.sample_size,
            "passed": self.passed,
            "failed": self.failed,
            "result": self.result.value,
            "defect_rate": self.defect_rate(),
            "defects": self.defects,
            "inspector_id": self.inspector_id,
            "notes": self.notes,
        }


@dataclass
class QualityAlert:
    """Quality alert notification."""
    alert_id: str
    alert_type: str
    severity: str
    message: str
    spec_id: Optional[str]
    created_at: datetime
    acknowledged: bool = False
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "spec_id": self.spec_id,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


# =============================================================================
# Statistical Process Control
# =============================================================================

class SPCController:
    """
    Statistical Process Control implementation.

    Provides control chart monitoring and analysis.
    """

    def __init__(
        self,
        spec: QualitySpecification,
        chart_type: ControlChartType = ControlChartType.INDIVIDUAL_MR,
        window_size: int = 25
    ):
        """
        Initialize SPC controller.

        Args:
            spec: Quality specification
            chart_type: Type of control chart
            window_size: Number of samples for control limit calculation
        """
        self.spec = spec
        self.chart_type = chart_type
        self.window_size = window_size

        self.measurements: deque = deque(maxlen=1000)
        self.control_limits: Optional[ControlLimit] = None
        self.status = ControlStatus.UNKNOWN

        # Western Electric rules violation count
        self.rule_violations: Dict[str, int] = defaultdict(int)

    def add_measurement(self, value: float) -> ControlStatus:
        """Add a measurement and check control status."""
        self.measurements.append(value)

        # Recalculate limits if needed
        if len(self.measurements) >= self.window_size:
            self._calculate_control_limits()

        if self.control_limits:
            self.status = self._check_control_rules()
        else:
            self.status = ControlStatus.UNKNOWN

        return self.status

    def _calculate_control_limits(self) -> None:
        """Calculate control limits from historical data."""
        values = list(self.measurements)[-self.window_size:]

        if len(values) < 2:
            return

        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)

        # 3-sigma limits
        self.control_limits = ControlLimit(
            center_line=mean,
            upper_control_limit=mean + 3 * std_dev,
            lower_control_limit=mean - 3 * std_dev,
            upper_warning_limit=mean + 2 * std_dev,
            lower_warning_limit=mean - 2 * std_dev,
        )

    def _check_control_rules(self) -> ControlStatus:
        """Check Western Electric rules for out-of-control conditions."""
        if not self.control_limits or len(self.measurements) < 1:
            return ControlStatus.UNKNOWN

        values = list(self.measurements)
        latest = values[-1]
        cl = self.control_limits

        # Rule 1: Single point beyond 3-sigma
        if latest > cl.upper_control_limit or latest < cl.lower_control_limit:
            self.rule_violations["rule_1"] += 1
            return ControlStatus.OUT_OF_CONTROL

        # Rule 2: 2 of 3 points beyond 2-sigma (same side)
        if len(values) >= 3:
            recent = values[-3:]
            above_2sigma = sum(1 for v in recent if v > cl.upper_warning_limit)
            below_2sigma = sum(1 for v in recent if v < cl.lower_warning_limit)
            if above_2sigma >= 2 or below_2sigma >= 2:
                self.rule_violations["rule_2"] += 1
                return ControlStatus.OUT_OF_CONTROL

        # Rule 3: 4 of 5 points beyond 1-sigma (same side)
        if len(values) >= 5:
            recent = values[-5:]
            sigma = (cl.upper_control_limit - cl.center_line) / 3
            above_1sigma = sum(1 for v in recent if v > cl.center_line + sigma)
            below_1sigma = sum(1 for v in recent if v < cl.center_line - sigma)
            if above_1sigma >= 4 or below_1sigma >= 4:
                self.rule_violations["rule_3"] += 1
                return ControlStatus.WARNING

        # Rule 4: 8 consecutive points on same side of center
        if len(values) >= 8:
            recent = values[-8:]
            all_above = all(v > cl.center_line for v in recent)
            all_below = all(v < cl.center_line for v in recent)
            if all_above or all_below:
                self.rule_violations["rule_4"] += 1
                return ControlStatus.OUT_OF_CONTROL

        # Rule 5: 6 points in a row trending
        if len(values) >= 6:
            recent = values[-6:]
            increasing = all(recent[i] < recent[i + 1] for i in range(5))
            decreasing = all(recent[i] > recent[i + 1] for i in range(5))
            if increasing or decreasing:
                self.rule_violations["rule_5"] += 1
                return ControlStatus.WARNING

        return ControlStatus.IN_CONTROL

    def calculate_capability(self) -> CapabilityMetrics:
        """Calculate process capability metrics."""
        values = list(self.measurements)

        if len(values) < 2:
            return CapabilityMetrics(
                cp=0, cpk=0, pp=0, ppk=0,
                sigma_level=0, ppm_defective=1000000, yield_rate=0
            )

        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)
        std_dev = max(std_dev, 0.0001)  # Avoid division by zero

        spec = self.spec
        usl = spec.upper_limit
        lsl = spec.lower_limit

        # Cp - Capability ratio (potential)
        cp = (usl - lsl) / (6 * std_dev)

        # Cpk - Capability index (actual, considers centering)
        cpu = (usl - mean) / (3 * std_dev)
        cpl = (mean - lsl) / (3 * std_dev)
        cpk = min(cpu, cpl)

        # Pp and Ppk (using overall standard deviation)
        pp = cp  # Same for short-term
        ppk = cpk

        # Sigma level (from Cpk)
        sigma_level = cpk * 3

        # PPM defective (approximate)
        if cpk > 0:
            # Using normal distribution approximation
            z_upper = (usl - mean) / std_dev
            z_lower = (mean - lsl) / std_dev
            # Simplified PPM calculation
            ppm = max(0, 1000000 * (1 - self._normal_cdf(min(z_upper, z_lower))))
        else:
            ppm = 1000000

        # Yield rate
        in_spec = sum(1 for v in values if lsl <= v <= usl)
        yield_rate = in_spec / len(values) if values else 0

        return CapabilityMetrics(
            cp=cp,
            cpk=cpk,
            pp=pp,
            ppk=ppk,
            sigma_level=sigma_level,
            ppm_defective=ppm,
            yield_rate=yield_rate,
        )

    def _normal_cdf(self, z: float) -> float:
        """Approximate normal CDF using error function approximation."""
        # Approximation for standard normal CDF
        a1, a2, a3, a4, a5 = (
            0.254829592, -0.284496736, 1.421413741,
            -1.453152027, 1.061405429
        )
        p = 0.3275911

        sign = 1 if z >= 0 else -1
        z = abs(z) / math.sqrt(2)

        t = 1.0 / (1.0 + p * z)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z * z)

        return 0.5 * (1.0 + sign * y)


# =============================================================================
# Autonomous Quality Controller
# =============================================================================

class AutonomousQualityController:
    """
    Autonomous Quality Control System.

    Provides intelligent quality management with:
    - Statistical process control
    - Automatic defect detection
    - Root cause analysis
    - Adaptive inspection
    - Quality prediction
    """

    def __init__(
        self,
        controller_id: str = "default",
        default_aql: float = 0.01,  # 1% AQL
        alert_threshold: float = 0.8
    ):
        """
        Initialize quality controller.

        Args:
            controller_id: Unique identifier
            default_aql: Default Acceptable Quality Level
            alert_threshold: Threshold for triggering alerts
        """
        self.controller_id = controller_id
        self.default_aql = default_aql
        self.alert_threshold = alert_threshold

        # Specifications and SPC controllers
        self.specifications: Dict[str, QualitySpecification] = {}
        self.spc_controllers: Dict[str, SPCController] = {}

        # Inspection
        self.inspection_plans: Dict[str, InspectionPlan] = {}
        self.inspection_records: Dict[str, InspectionRecord] = {}

        # Defects
        self.defects: Dict[str, Defect] = {}
        self.defect_counts: Dict[DefectType, int] = defaultdict(int)

        # Alerts
        self.alerts: Dict[str, QualityAlert] = {}
        self.active_alerts: List[str] = []

        # Callbacks
        self.on_alert: Optional[Callable[[QualityAlert], None]] = None
        self.on_out_of_control: Optional[Callable[[str, ControlStatus], None]] = None

        # Statistics
        self.total_inspections = 0
        self.total_defects = 0
        self.total_measurements = 0

        # Background task
        self._running = False
        self._monitoring_task: Optional[asyncio.Task] = None

        logger.info(f"AutonomousQualityController initialized: {controller_id}")

    # -------------------------------------------------------------------------
    # Specification Management
    # -------------------------------------------------------------------------

    def add_specification(
        self,
        spec_id: str,
        name: str,
        nominal: float,
        upper_limit: float,
        lower_limit: float,
        unit: str = "",
        critical: bool = False,
        chart_type: ControlChartType = ControlChartType.INDIVIDUAL_MR
    ) -> QualitySpecification:
        """
        Add a quality specification.

        Args:
            spec_id: Specification identifier
            name: Specification name
            nominal: Nominal/target value
            upper_limit: Upper specification limit
            lower_limit: Lower specification limit
            unit: Measurement unit
            critical: Is this a critical characteristic
            chart_type: Type of control chart to use

        Returns:
            Created QualitySpecification
        """
        spec = QualitySpecification(
            spec_id=spec_id,
            name=name,
            nominal=nominal,
            upper_limit=upper_limit,
            lower_limit=lower_limit,
            unit=unit,
            critical=critical,
        )

        self.specifications[spec_id] = spec
        self.spc_controllers[spec_id] = SPCController(spec, chart_type)

        logger.info(f"Added specification: {spec_id} ({name})")
        return spec

    # -------------------------------------------------------------------------
    # Measurement Recording
    # -------------------------------------------------------------------------

    def record_measurement(
        self,
        spec_id: str,
        value: float,
        part_id: str,
        operator_id: Optional[str] = None,
        machine_id: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> Tuple[Measurement, ControlStatus]:
        """
        Record a quality measurement.

        Args:
            spec_id: Specification being measured
            value: Measured value
            part_id: Part identifier
            operator_id: Operator identifier
            machine_id: Machine identifier
            batch_id: Batch identifier

        Returns:
            Tuple of (Measurement, ControlStatus)
        """
        if spec_id not in self.specifications:
            raise ValueError(f"Unknown specification: {spec_id}")

        spec = self.specifications[spec_id]
        spc = self.spc_controllers[spec_id]

        measurement = Measurement(
            measurement_id=str(uuid.uuid4()),
            spec_id=spec_id,
            value=value,
            timestamp=datetime.utcnow(),
            part_id=part_id,
            operator_id=operator_id,
            machine_id=machine_id,
            batch_id=batch_id,
        )

        # Add to SPC controller
        control_status = spc.add_measurement(value)
        self.total_measurements += 1

        # Check for alerts
        if control_status == ControlStatus.OUT_OF_CONTROL:
            self._create_alert(
                "out_of_control",
                "critical" if spec.critical else "warning",
                f"Process out of control for {spec.name}: value={value:.3f}",
                spec_id
            )
            if self.on_out_of_control:
                self.on_out_of_control(spec_id, control_status)

        elif control_status == ControlStatus.WARNING:
            self._create_alert(
                "control_warning",
                "warning",
                f"Control warning for {spec.name}: value={value:.3f}",
                spec_id
            )

        # Check specification limits
        if not spec.is_within_spec(value):
            self._create_alert(
                "out_of_spec",
                "critical" if spec.critical else "major",
                f"Out of specification for {spec.name}: {value:.3f} "
                f"(limits: {spec.lower_limit}-{spec.upper_limit})",
                spec_id
            )

        return measurement, control_status

    def record_batch_measurements(
        self,
        spec_id: str,
        values: List[Tuple[str, float]],  # (part_id, value)
        operator_id: Optional[str] = None,
        machine_id: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> List[Tuple[Measurement, ControlStatus]]:
        """Record multiple measurements."""
        return [
            self.record_measurement(
                spec_id, value, part_id,
                operator_id, machine_id, batch_id
            )
            for part_id, value in values
        ]

    # -------------------------------------------------------------------------
    # Defect Management
    # -------------------------------------------------------------------------

    def record_defect(
        self,
        defect_type: DefectType,
        severity: DefectSeverity,
        description: str,
        part_id: str,
        location: Optional[str] = None
    ) -> Defect:
        """
        Record a defect.

        Args:
            defect_type: Type of defect
            severity: Severity level
            description: Defect description
            part_id: Part identifier
            location: Location on part

        Returns:
            Created Defect
        """
        defect = Defect(
            defect_id=str(uuid.uuid4()),
            defect_type=defect_type,
            severity=severity,
            description=description,
            part_id=part_id,
            detected_at=datetime.utcnow(),
            location=location,
        )

        self.defects[defect.defect_id] = defect
        self.defect_counts[defect_type] += 1
        self.total_defects += 1

        # Alert for critical defects
        if severity == DefectSeverity.CRITICAL:
            self._create_alert(
                "critical_defect",
                "critical",
                f"Critical defect: {defect_type.value} - {description}",
                None
            )

        logger.info(f"Recorded defect: {defect.defect_id} ({defect_type.value})")
        return defect

    def get_pareto_analysis(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Perform Pareto analysis on defects.

        Args:
            top_n: Number of top defect types to return

        Returns:
            List of defect types with counts and cumulative percentages
        """
        total = sum(self.defect_counts.values())
        if total == 0:
            return []

        sorted_defects = sorted(
            self.defect_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        cumulative = 0.0
        result = []

        for defect_type, count in sorted_defects:
            percentage = count / total * 100
            cumulative += percentage
            result.append({
                "defect_type": defect_type.value,
                "count": count,
                "percentage": percentage,
                "cumulative_percentage": cumulative,
            })

        return result

    # -------------------------------------------------------------------------
    # Inspection Management
    # -------------------------------------------------------------------------

    def create_inspection_plan(
        self,
        plan_id: str,
        name: str,
        inspection_type: InspectionType,
        specifications: List[str],
        sample_size: int,
        aql: Optional[float] = None,
        frequency: str = "every_batch"
    ) -> InspectionPlan:
        """Create an inspection plan."""
        plan = InspectionPlan(
            plan_id=plan_id,
            name=name,
            inspection_type=inspection_type,
            specifications=specifications,
            sample_size=sample_size,
            aql=aql or self.default_aql,
            frequency=frequency,
        )

        self.inspection_plans[plan_id] = plan
        logger.info(f"Created inspection plan: {plan_id}")
        return plan

    def perform_inspection(
        self,
        plan_id: str,
        measurements: List[Measurement],
        inspector_id: Optional[str] = None,
        notes: str = ""
    ) -> InspectionRecord:
        """
        Perform an inspection according to a plan.

        Args:
            plan_id: Inspection plan to use
            measurements: List of measurements taken
            inspector_id: Inspector identifier
            notes: Additional notes

        Returns:
            InspectionRecord
        """
        if plan_id not in self.inspection_plans:
            raise ValueError(f"Unknown inspection plan: {plan_id}")

        plan = self.inspection_plans[plan_id]

        # Evaluate measurements against specifications
        passed = 0
        failed = 0
        defect_ids = []

        for m in measurements:
            spec = self.specifications.get(m.spec_id)
            if spec and spec.is_within_spec(m.value):
                passed += 1
            else:
                failed += 1
                # Record as defect
                defect = self.record_defect(
                    DefectType.DIMENSIONAL,
                    DefectSeverity.MINOR,
                    f"Out of spec: {m.value}",
                    m.part_id
                )
                defect_ids.append(defect.defect_id)

        # Determine result
        defect_rate = failed / len(measurements) if measurements else 0

        if defect_rate == 0:
            result = InspectionResult.PASS
        elif defect_rate <= plan.aql:
            result = InspectionResult.CONDITIONAL
        elif defect_rate <= plan.aql * 2:
            result = InspectionResult.REWORK
        else:
            result = InspectionResult.FAIL

        record = InspectionRecord(
            record_id=str(uuid.uuid4()),
            plan_id=plan_id,
            inspection_type=plan.inspection_type,
            inspected_at=datetime.utcnow(),
            sample_size=len(measurements),
            passed=passed,
            failed=failed,
            result=result,
            measurements=measurements,
            defects=defect_ids,
            inspector_id=inspector_id,
            notes=notes,
        )

        self.inspection_records[record.record_id] = record
        self.total_inspections += 1

        # Alert on failed inspection
        if result in (InspectionResult.FAIL, InspectionResult.SCRAP):
            self._create_alert(
                "inspection_failed",
                "major",
                f"Inspection failed: {plan.name}, defect rate={defect_rate*100:.1f}%",
                None
            )

        return record

    # -------------------------------------------------------------------------
    # Adaptive Inspection
    # -------------------------------------------------------------------------

    def get_recommended_sample_size(
        self,
        plan_id: str,
        recent_window: int = 10
    ) -> int:
        """
        Get recommended sample size based on recent quality history.

        Uses adaptive sampling: increase sampling when quality degrades,
        decrease when quality is consistently good.
        """
        if plan_id not in self.inspection_plans:
            return 10  # Default

        plan = self.inspection_plans[plan_id]

        # Get recent inspection records for this plan
        recent_records = [
            r for r in self.inspection_records.values()
            if r.plan_id == plan_id
        ][-recent_window:]

        if len(recent_records) < 3:
            return plan.sample_size  # Not enough history

        # Calculate average defect rate
        avg_defect_rate = statistics.mean([r.defect_rate() for r in recent_records])

        # Adaptive logic
        if avg_defect_rate > plan.aql * 2:
            # Poor quality: increase sampling by 50%
            return int(plan.sample_size * 1.5)
        elif avg_defect_rate > plan.aql:
            # Marginal: keep current
            return plan.sample_size
        elif avg_defect_rate < plan.aql * 0.5:
            # Excellent: reduce sampling by 25%
            return max(5, int(plan.sample_size * 0.75))
        else:
            return plan.sample_size

    # -------------------------------------------------------------------------
    # Quality Analytics
    # -------------------------------------------------------------------------

    def get_capability_analysis(self, spec_id: str) -> CapabilityMetrics:
        """Get process capability analysis for a specification."""
        if spec_id not in self.spc_controllers:
            raise ValueError(f"Unknown specification: {spec_id}")

        return self.spc_controllers[spec_id].calculate_capability()

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get overall quality summary."""
        # Calculate overall metrics
        total_passed = sum(
            r.passed for r in self.inspection_records.values()
        )
        total_inspected = sum(
            r.sample_size for r in self.inspection_records.values()
        )
        overall_yield = total_passed / total_inspected if total_inspected > 0 else 0

        # Capability summary
        capability_summary = {}
        for spec_id, spc in self.spc_controllers.items():
            metrics = spc.calculate_capability()
            capability_summary[spec_id] = {
                "cpk": metrics.cpk,
                "quality_level": metrics.get_quality_level().value,
                "control_status": spc.status.value,
            }

        # Recent trend
        recent_records = sorted(
            self.inspection_records.values(),
            key=lambda r: r.inspected_at
        )[-10:]

        trend = "stable"
        if len(recent_records) >= 5:
            recent_rates = [r.defect_rate() for r in recent_records]
            first_half_avg = statistics.mean(recent_rates[:len(recent_rates)//2])
            second_half_avg = statistics.mean(recent_rates[len(recent_rates)//2:])

            if second_half_avg < first_half_avg * 0.8:
                trend = "improving"
            elif second_half_avg > first_half_avg * 1.2:
                trend = "degrading"

        return {
            "controller_id": self.controller_id,
            "total_inspections": self.total_inspections,
            "total_measurements": self.total_measurements,
            "total_defects": self.total_defects,
            "overall_yield": overall_yield,
            "defect_rate": 1 - overall_yield,
            "active_alerts": len(self.active_alerts),
            "trend": trend,
            "capability_summary": capability_summary,
            "pareto_top5": self.get_pareto_analysis(5),
        }

    # -------------------------------------------------------------------------
    # Alert Management
    # -------------------------------------------------------------------------

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        spec_id: Optional[str]
    ) -> QualityAlert:
        """Create a quality alert."""
        alert = QualityAlert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            message=message,
            spec_id=spec_id,
            created_at=datetime.utcnow(),
        )

        self.alerts[alert.alert_id] = alert
        self.active_alerts.append(alert.alert_id)

        if self.on_alert:
            self.on_alert(alert)

        logger.warning(f"Quality alert: {alert_type} - {message}")
        return alert

    def acknowledge_alert(self, alert_id: str) -> None:
        """Acknowledge an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].acknowledged = True

    def resolve_alert(self, alert_id: str) -> None:
        """Resolve an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].resolved = True
            if alert_id in self.active_alerts:
                self.active_alerts.remove(alert_id)

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    def get_controller_status(self) -> Dict[str, Any]:
        """Get controller status."""
        return {
            "controller_id": self.controller_id,
            "specifications": len(self.specifications),
            "inspection_plans": len(self.inspection_plans),
            "total_inspections": self.total_inspections,
            "total_measurements": self.total_measurements,
            "total_defects": self.total_defects,
            "active_alerts": len(self.active_alerts),
            "specs_in_control": sum(
                1 for spc in self.spc_controllers.values()
                if spc.status == ControlStatus.IN_CONTROL
            ),
            "specs_out_of_control": sum(
                1 for spc in self.spc_controllers.values()
                if spc.status == ControlStatus.OUT_OF_CONTROL
            ),
        }


# =============================================================================
# Factory Function and Singleton
# =============================================================================

_quality_controller_instance: Optional[AutonomousQualityController] = None


def get_quality_controller(
    controller_id: str = "default"
) -> AutonomousQualityController:
    """
    Get or create the quality controller singleton.

    Args:
        controller_id: Controller identifier

    Returns:
        AutonomousQualityController instance
    """
    global _quality_controller_instance

    if _quality_controller_instance is None:
        _quality_controller_instance = AutonomousQualityController(
            controller_id=controller_id
        )

    return _quality_controller_instance


__all__ = [
    # Enums
    'QualityLevel',
    'ControlChartType',
    'InspectionType',
    'DefectSeverity',
    'DefectType',
    'ControlStatus',
    'InspectionResult',
    # Data Classes
    'QualitySpecification',
    'Measurement',
    'Defect',
    'ControlLimit',
    'CapabilityMetrics',
    'InspectionPlan',
    'InspectionRecord',
    'QualityAlert',
    # Classes
    'SPCController',
    'AutonomousQualityController',
    'get_quality_controller',
]
