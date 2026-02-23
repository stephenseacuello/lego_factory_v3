"""
Extended Routing Model - Alternative Routings

LegoMCP World-Class Manufacturing System v5.0
Phase 9: Alternative Routings & Enhanced BOM

Supports multiple routing alternatives per product:
- Primary and alternative routings
- Routing versioning
- Performance metrics per routing
- FMEA risk scoring
- Automation level tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class RoutingStatus(str, Enum):
    """Routing lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    OBSOLETE = "obsolete"


class OperationType(str, Enum):
    """Type of manufacturing operation."""
    SETUP = "setup"
    PRODUCTION = "production"
    INSPECTION = "inspection"
    TRANSPORT = "transport"
    WAIT = "wait"
    REWORK = "rework"


class SkillLevel(str, Enum):
    """Operator skill level required."""
    NONE = "none"  # Fully automated
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class RoutingOperation:
    """Single operation in a routing."""
    operation_id: str
    sequence: int
    operation_code: str
    description: str
    operation_type: OperationType = OperationType.PRODUCTION

    # Work center
    work_center_id: str = ""
    work_center_name: str = ""
    alternative_work_centers: List[str] = field(default_factory=list)

    # Times (minutes)
    setup_time: float = 0.0
    run_time_per_unit: float = 0.0
    queue_time: float = 0.0
    move_time: float = 0.0

    # Resources
    requires_tooling: bool = False
    tooling_ids: List[str] = field(default_factory=list)
    requires_operator: bool = True
    skill_level_required: SkillLevel = SkillLevel.BASIC

    # Quality
    inspection_required: bool = False
    inspection_type: str = ""
    ctq_parameters: List[str] = field(default_factory=list)

    # Cost
    labor_rate_per_hour: float = 25.0
    machine_rate_per_hour: float = 50.0

    # FMEA
    fmea_risk_score: float = 0.0

    def total_time(self, quantity: int = 1) -> float:
        """Calculate total time for quantity."""
        return self.setup_time + (self.run_time_per_unit * quantity) + self.queue_time + self.move_time

    def standard_cost(self, quantity: int = 1) -> float:
        """Calculate standard cost for quantity."""
        total_hours = self.total_time(quantity) / 60
        labor_cost = total_hours * self.labor_rate_per_hour if self.requires_operator else 0
        machine_cost = total_hours * self.machine_rate_per_hour
        return labor_cost + machine_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'operation_id': self.operation_id,
            'sequence': self.sequence,
            'operation_code': self.operation_code,
            'description': self.description,
            'operation_type': self.operation_type.value,
            'work_center_id': self.work_center_id,
            'alternative_work_centers': self.alternative_work_centers,
            'setup_time': self.setup_time,
            'run_time_per_unit': self.run_time_per_unit,
            'queue_time': self.queue_time,
            'requires_operator': self.requires_operator,
            'skill_level_required': self.skill_level_required.value,
            'inspection_required': self.inspection_required,
            'fmea_risk_score': self.fmea_risk_score,
        }


@dataclass
class AlternativeRouting:
    """Alternative manufacturing routing for a part."""
    routing_id: str
    part_id: str
    routing_version: str = "1.0"
    routing_name: str = ""
    description: str = ""

    # Status
    status: RoutingStatus = RoutingStatus.DRAFT
    is_primary: bool = False
    is_active: bool = True

    # Operations
    operations: List[RoutingOperation] = field(default_factory=list)

    # Performance metrics
    total_time_minutes: float = 0.0
    total_cost: float = 0.0
    expected_yield_percent: float = 99.0
    throughput_per_hour: float = 0.0

    # Energy
    energy_kwh: float = 0.0
    carbon_kg: float = 0.0

    # Risk
    fmea_risk_score: float = 0.0
    quality_capability_ppk: float = 1.33

    # Automation
    automation_percent: float = 0.0
    requires_human: bool = True
    skill_level_required: SkillLevel = SkillLevel.BASIC

    # Selection criteria
    selection_score: float = 0.0
    preferred_for: List[str] = field(default_factory=list)  # e.g., ["rush", "high_quality"]

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    def __post_init__(self):
        if not self.routing_id:
            self.routing_id = str(uuid4())
        self._recalculate_metrics()

    def _recalculate_metrics(self) -> None:
        """Recalculate aggregated metrics from operations."""
        if not self.operations:
            return

        self.total_time_minutes = sum(op.total_time(1) for op in self.operations)
        self.total_cost = sum(op.standard_cost(1) for op in self.operations)

        # Throughput (units per hour)
        if self.total_time_minutes > 0:
            self.throughput_per_hour = 60 / self.total_time_minutes

        # Automation percentage
        automated_ops = sum(1 for op in self.operations if not op.requires_operator)
        self.automation_percent = (automated_ops / len(self.operations)) * 100

        self.requires_human = any(op.requires_operator for op in self.operations)

        # Max skill level required
        skill_order = [SkillLevel.NONE, SkillLevel.BASIC, SkillLevel.INTERMEDIATE,
                       SkillLevel.ADVANCED, SkillLevel.EXPERT]
        max_skill = SkillLevel.NONE
        for op in self.operations:
            if skill_order.index(op.skill_level_required) > skill_order.index(max_skill):
                max_skill = op.skill_level_required
        self.skill_level_required = max_skill

        # Aggregate FMEA risk
        self.fmea_risk_score = max(
            (op.fmea_risk_score for op in self.operations), default=0
        )

    def add_operation(self, operation: RoutingOperation) -> None:
        """Add an operation to the routing."""
        self.operations.append(operation)
        self.operations.sort(key=lambda x: x.sequence)
        self._recalculate_metrics()

    def remove_operation(self, operation_id: str) -> bool:
        """Remove an operation from the routing."""
        for i, op in enumerate(self.operations):
            if op.operation_id == operation_id:
                self.operations.pop(i)
                self._recalculate_metrics()
                return True
        return False

    def get_operation(self, sequence: int) -> Optional[RoutingOperation]:
        """Get operation by sequence number."""
        for op in self.operations:
            if op.sequence == sequence:
                return op
        return None

    def calculate_for_quantity(self, quantity: int) -> Dict[str, float]:
        """Calculate metrics for a specific quantity."""
        total_time = sum(op.total_time(quantity) for op in self.operations)
        total_cost = sum(op.standard_cost(quantity) for op in self.operations)

        return {
            'quantity': quantity,
            'total_time_minutes': total_time,
            'total_time_hours': total_time / 60,
            'total_cost': total_cost,
            'cost_per_unit': total_cost / quantity if quantity > 0 else 0,
            'expected_good_units': int(quantity * self.expected_yield_percent / 100),
        }

    def approve(self, approved_by: str) -> None:
        """Approve the routing."""
        self.status = RoutingStatus.APPROVED
        self.approved_at = datetime.utcnow()
        self.approved_by = approved_by

    def activate(self) -> None:
        """Activate the routing."""
        if self.status == RoutingStatus.APPROVED:
            self.status = RoutingStatus.ACTIVE
            self.is_active = True

    def deprecate(self) -> None:
        """Deprecate the routing."""
        self.status = RoutingStatus.DEPRECATED
        self.is_active = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'routing_id': self.routing_id,
            'part_id': self.part_id,
            'routing_version': self.routing_version,
            'routing_name': self.routing_name,
            'description': self.description,
            'status': self.status.value,
            'is_primary': self.is_primary,
            'is_active': self.is_active,
            'operations': [op.to_dict() for op in self.operations],
            'total_time_minutes': self.total_time_minutes,
            'total_cost': self.total_cost,
            'expected_yield_percent': self.expected_yield_percent,
            'throughput_per_hour': self.throughput_per_hour,
            'energy_kwh': self.energy_kwh,
            'automation_percent': self.automation_percent,
            'requires_human': self.requires_human,
            'skill_level_required': self.skill_level_required.value,
            'fmea_risk_score': self.fmea_risk_score,
            'quality_capability_ppk': self.quality_capability_ppk,
            'created_at': self.created_at.isoformat(),
        }


class RoutingRepository:
    """Repository for routing persistence."""

    def __init__(self):
        self._routings: Dict[str, AlternativeRouting] = {}
        self._by_part: Dict[str, List[str]] = {}  # part_id -> [routing_ids]

    def save(self, routing: AlternativeRouting) -> None:
        """Save or update a routing."""
        self._routings[routing.routing_id] = routing

        if routing.part_id not in self._by_part:
            self._by_part[routing.part_id] = []
        if routing.routing_id not in self._by_part[routing.part_id]:
            self._by_part[routing.part_id].append(routing.routing_id)

    def get(self, routing_id: str) -> Optional[AlternativeRouting]:
        """Get routing by ID."""
        return self._routings.get(routing_id)

    def get_by_part(self, part_id: str) -> List[AlternativeRouting]:
        """Get all routings for a part."""
        routing_ids = self._by_part.get(part_id, [])
        return [self._routings[rid] for rid in routing_ids if rid in self._routings]

    def get_primary(self, part_id: str) -> Optional[AlternativeRouting]:
        """Get primary routing for a part."""
        for routing in self.get_by_part(part_id):
            if routing.is_primary and routing.is_active:
                return routing
        return None

    def get_active(self, part_id: str) -> List[AlternativeRouting]:
        """Get all active routings for a part."""
        return [r for r in self.get_by_part(part_id) if r.is_active]

    def set_primary(self, routing_id: str) -> bool:
        """Set a routing as primary (unsets others)."""
        routing = self._routings.get(routing_id)
        if not routing:
            return False

        # Unset other primaries for this part
        for r in self.get_by_part(routing.part_id):
            r.is_primary = False

        routing.is_primary = True
        return True

    def delete(self, routing_id: str) -> bool:
        """Delete a routing."""
        if routing_id in self._routings:
            routing = self._routings.pop(routing_id)
            if routing.part_id in self._by_part:
                if routing_id in self._by_part[routing.part_id]:
                    self._by_part[routing.part_id].remove(routing_id)
            return True
        return False

    def count(self) -> int:
        """Get total routing count."""
        return len(self._routings)
