"""
FMEA Model - Failure Mode and Effects Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 10: FMEA Engine (Dynamic)

Comprehensive FMEA with dynamic RPN:
- Design, Process, Material, Human FMEA types
- Dynamic RPN with real-time factors
- Automated risk responses
- Historical tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class FMEAType(str, Enum):
    """Type of FMEA analysis."""
    DESIGN = "design"  # DFMEA - Design failure modes
    PROCESS = "process"  # PFMEA - Process failure modes
    MATERIAL = "material"  # Material-related failures
    HUMAN = "human"  # Human error modes


class ActionType(str, Enum):
    """Type of risk mitigation action."""
    INSPECTION = "inspection"  # Add inspection step
    SLOW_ROUTING = "slow_routing"  # Use slower/safer routing
    HUMAN_INTERVENTION = "human_intervention"  # Require human oversight
    PRICE_ADJUSTMENT = "price_adjustment"  # Adjust price for risk
    DESIGN_CHANGE = "design_change"  # Modify design
    PROCESS_CONTROL = "process_control"  # Add SPC/controls
    TRAINING = "training"  # Operator training
    PREVENTIVE_MAINTENANCE = "preventive_maintenance"  # Schedule PM


class ActionStatus(str, Enum):
    """Status of a risk action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    CANCELLED = "cancelled"


@dataclass
class FailureMode:
    """A potential failure mode."""
    failure_mode_id: str
    fmea_id: str
    description: str

    # Classic FMEA ratings (1-10 scale)
    severity: int = 5  # Impact if failure occurs
    occurrence: int = 5  # Frequency of failure
    detection: int = 5  # Ability to detect before reaching customer

    # Base RPN
    rpn: int = 125  # S × O × D

    # Dynamic modifiers
    machine_health_factor: float = 1.0  # >1 if machine degraded
    operator_skill_factor: float = 1.0  # >1 if inexperienced operator
    material_quality_factor: float = 1.0  # >1 if material issues
    spc_trend_factor: float = 1.0  # >1 if SPC trends negative

    # Dynamic RPN
    dynamic_rpn: float = 125.0

    # Failure details
    potential_effect: str = ""
    potential_cause: str = ""
    current_controls: str = ""

    # Classification
    is_safety_critical: bool = False
    is_regulatory: bool = False
    is_customer_critical: bool = False

    # Status
    status: str = "active"  # active, mitigated, accepted, closed

    # Actions
    recommended_actions: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.failure_mode_id:
            self.failure_mode_id = str(uuid4())
        self._calculate_rpn()

    def _calculate_rpn(self) -> None:
        """Calculate base and dynamic RPN."""
        self.rpn = self.severity * self.occurrence * self.detection

        # Dynamic RPN includes real-time factors
        self.dynamic_rpn = (
            self.rpn *
            self.machine_health_factor *
            self.operator_skill_factor *
            self.material_quality_factor *
            self.spc_trend_factor
        )

    def update_factors(
        self,
        machine_health: Optional[float] = None,
        operator_skill: Optional[float] = None,
        material_quality: Optional[float] = None,
        spc_trend: Optional[float] = None,
    ) -> None:
        """Update dynamic factors and recalculate RPN."""
        if machine_health is not None:
            self.machine_health_factor = machine_health
        if operator_skill is not None:
            self.operator_skill_factor = operator_skill
        if material_quality is not None:
            self.material_quality_factor = material_quality
        if spc_trend is not None:
            self.spc_trend_factor = spc_trend

        self._calculate_rpn()

    def update_ratings(
        self,
        severity: Optional[int] = None,
        occurrence: Optional[int] = None,
        detection: Optional[int] = None,
    ) -> None:
        """Update SOD ratings and recalculate RPN."""
        if severity is not None:
            self.severity = max(1, min(10, severity))
        if occurrence is not None:
            self.occurrence = max(1, min(10, occurrence))
        if detection is not None:
            self.detection = max(1, min(10, detection))

        self._calculate_rpn()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'failure_mode_id': self.failure_mode_id,
            'fmea_id': self.fmea_id,
            'description': self.description,
            'severity': self.severity,
            'occurrence': self.occurrence,
            'detection': self.detection,
            'rpn': self.rpn,
            'dynamic_rpn': self.dynamic_rpn,
            'machine_health_factor': self.machine_health_factor,
            'operator_skill_factor': self.operator_skill_factor,
            'material_quality_factor': self.material_quality_factor,
            'spc_trend_factor': self.spc_trend_factor,
            'potential_effect': self.potential_effect,
            'potential_cause': self.potential_cause,
            'current_controls': self.current_controls,
            'is_safety_critical': self.is_safety_critical,
            'is_regulatory': self.is_regulatory,
            'status': self.status,
            'recommended_actions': self.recommended_actions,
        }


@dataclass
class RiskAction:
    """An action to mitigate risk."""
    action_id: str
    failure_mode_id: str
    action_type: ActionType
    description: str

    # Trigger
    trigger_threshold: float = 100.0  # Dynamic RPN threshold
    auto_execute: bool = False

    # Impact
    expected_severity_reduction: int = 0
    expected_occurrence_reduction: int = 0
    expected_detection_improvement: int = 0

    # Cost/effort
    estimated_cost: float = 0.0
    estimated_hours: float = 0.0

    # Status
    status: ActionStatus = ActionStatus.PENDING
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None

    # Verification
    verification_method: str = ""
    verified_by: Optional[str] = None
    verified_date: Optional[datetime] = None

    def __post_init__(self):
        if not self.action_id:
            self.action_id = str(uuid4())

    def expected_rpn_reduction(self, current_fm: FailureMode) -> int:
        """Calculate expected RPN after action."""
        new_s = max(1, current_fm.severity - self.expected_severity_reduction)
        new_o = max(1, current_fm.occurrence - self.expected_occurrence_reduction)
        new_d = max(1, current_fm.detection - self.expected_detection_improvement)
        return new_s * new_o * new_d

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'action_id': self.action_id,
            'failure_mode_id': self.failure_mode_id,
            'action_type': self.action_type.value,
            'description': self.description,
            'trigger_threshold': self.trigger_threshold,
            'auto_execute': self.auto_execute,
            'expected_severity_reduction': self.expected_severity_reduction,
            'expected_occurrence_reduction': self.expected_occurrence_reduction,
            'expected_detection_improvement': self.expected_detection_improvement,
            'estimated_cost': self.estimated_cost,
            'status': self.status.value,
            'assigned_to': self.assigned_to,
            'due_date': self.due_date.isoformat() if self.due_date else None,
        }


@dataclass
class FMEARecord:
    """FMEA record for a part/process."""
    fmea_id: str
    fmea_type: FMEAType
    part_id: str
    part_name: str = ""
    process_id: Optional[str] = None
    revision: str = "1.0"

    # Failure modes
    failure_modes: List[FailureMode] = field(default_factory=list)

    # Actions
    actions: List[RiskAction] = field(default_factory=list)

    # Summary metrics
    highest_rpn: int = 0
    highest_dynamic_rpn: float = 0.0
    total_failure_modes: int = 0
    critical_failure_modes: int = 0
    open_actions: int = 0

    # Status
    status: str = "draft"  # draft, review, approved, active
    approved_by: Optional[str] = None
    approved_date: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_review_date: Optional[datetime] = None

    def __post_init__(self):
        if not self.fmea_id:
            self.fmea_id = str(uuid4())
        self._recalculate_metrics()

    def _recalculate_metrics(self) -> None:
        """Recalculate summary metrics."""
        self.total_failure_modes = len(self.failure_modes)

        if self.failure_modes:
            self.highest_rpn = max(fm.rpn for fm in self.failure_modes)
            self.highest_dynamic_rpn = max(fm.dynamic_rpn for fm in self.failure_modes)
            self.critical_failure_modes = sum(
                1 for fm in self.failure_modes
                if fm.rpn > 100 or fm.is_safety_critical
            )

        self.open_actions = sum(
            1 for action in self.actions
            if action.status in [ActionStatus.PENDING, ActionStatus.IN_PROGRESS]
        )

    def add_failure_mode(self, fm: FailureMode) -> None:
        """Add a failure mode."""
        fm.fmea_id = self.fmea_id
        self.failure_modes.append(fm)
        self._recalculate_metrics()
        self.updated_at = datetime.utcnow()

    def add_action(self, action: RiskAction) -> None:
        """Add a risk action."""
        self.actions.append(action)
        self._recalculate_metrics()
        self.updated_at = datetime.utcnow()

    def get_failure_mode(self, fm_id: str) -> Optional[FailureMode]:
        """Get failure mode by ID."""
        for fm in self.failure_modes:
            if fm.failure_mode_id == fm_id:
                return fm
        return None

    def get_high_risk_modes(self, threshold: float = 100) -> List[FailureMode]:
        """Get failure modes above RPN threshold."""
        return [
            fm for fm in self.failure_modes
            if fm.dynamic_rpn > threshold
        ]

    def get_critical_modes(self) -> List[FailureMode]:
        """Get safety-critical failure modes."""
        return [
            fm for fm in self.failure_modes
            if fm.is_safety_critical or fm.is_regulatory
        ]

    def update_dynamic_factors(
        self,
        machine_health: float = 1.0,
        operator_skill: float = 1.0,
        material_quality: float = 1.0,
        spc_trend: float = 1.0,
    ) -> None:
        """Update dynamic factors for all failure modes."""
        for fm in self.failure_modes:
            fm.update_factors(
                machine_health=machine_health,
                operator_skill=operator_skill,
                material_quality=material_quality,
                spc_trend=spc_trend,
            )
        self._recalculate_metrics()
        self.updated_at = datetime.utcnow()

    def approve(self, approved_by: str) -> None:
        """Approve the FMEA."""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'fmea_id': self.fmea_id,
            'fmea_type': self.fmea_type.value,
            'part_id': self.part_id,
            'part_name': self.part_name,
            'revision': self.revision,
            'failure_modes': [fm.to_dict() for fm in self.failure_modes],
            'actions': [a.to_dict() for a in self.actions],
            'highest_rpn': self.highest_rpn,
            'highest_dynamic_rpn': self.highest_dynamic_rpn,
            'total_failure_modes': self.total_failure_modes,
            'critical_failure_modes': self.critical_failure_modes,
            'open_actions': self.open_actions,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class FMEARepository:
    """Repository for FMEA persistence."""

    def __init__(self):
        self._fmeas: Dict[str, FMEARecord] = {}
        self._by_part: Dict[str, List[str]] = {}

    def save(self, fmea: FMEARecord) -> None:
        """Save or update FMEA."""
        self._fmeas[fmea.fmea_id] = fmea

        if fmea.part_id not in self._by_part:
            self._by_part[fmea.part_id] = []
        if fmea.fmea_id not in self._by_part[fmea.part_id]:
            self._by_part[fmea.part_id].append(fmea.fmea_id)

    def get(self, fmea_id: str) -> Optional[FMEARecord]:
        """Get FMEA by ID."""
        return self._fmeas.get(fmea_id)

    def get_by_part(self, part_id: str) -> List[FMEARecord]:
        """Get all FMEAs for a part."""
        fmea_ids = self._by_part.get(part_id, [])
        return [self._fmeas[fid] for fid in fmea_ids if fid in self._fmeas]

    def get_by_type(self, fmea_type: FMEAType) -> List[FMEARecord]:
        """Get all FMEAs of a type."""
        return [f for f in self._fmeas.values() if f.fmea_type == fmea_type]

    def get_high_risk(self, threshold: float = 100) -> List[FMEARecord]:
        """Get FMEAs with high-risk failure modes."""
        return [
            f for f in self._fmeas.values()
            if f.highest_dynamic_rpn > threshold
        ]

    def delete(self, fmea_id: str) -> bool:
        """Delete FMEA."""
        if fmea_id in self._fmeas:
            fmea = self._fmeas.pop(fmea_id)
            if fmea.part_id in self._by_part:
                if fmea_id in self._by_part[fmea.part_id]:
                    self._by_part[fmea.part_id].remove(fmea_id)
            return True
        return False

    def count(self) -> int:
        """Get total FMEA count."""
        return len(self._fmeas)
