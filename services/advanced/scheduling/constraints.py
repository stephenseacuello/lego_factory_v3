"""
Scheduling Constraints - Constraint Definitions

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

Defines constraint types for scheduling:
- Resource capacity constraints
- Precedence constraints
- Time window constraints
- Setup time constraints
- Alternative machine constraints
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ConstraintType(str, Enum):
    """Types of scheduling constraints."""
    PRECEDENCE = "precedence"           # Operation A must finish before B starts
    RESOURCE_CAPACITY = "resource_capacity"  # Limited resource availability
    TIME_WINDOW = "time_window"         # Start/end time bounds
    SETUP_TIME = "setup_time"           # Sequence-dependent setups
    NO_OVERLAP = "no_overlap"           # Operations can't overlap on machine
    ALTERNATIVE_MACHINE = "alternative_machine"  # Can run on multiple machines
    MAINTENANCE = "maintenance"         # Maintenance windows
    SKILL_REQUIREMENT = "skill_requirement"  # Operator skills required
    BATCH_SIZE = "batch_size"           # Minimum/maximum batch constraints
    CALENDAR = "calendar"               # Work calendar (shifts, holidays)


class ConstraintPriority(str, Enum):
    """Priority levels for soft constraints."""
    MANDATORY = "mandatory"   # Hard constraint, must be satisfied
    HIGH = "high"             # Soft, high penalty
    MEDIUM = "medium"         # Soft, medium penalty
    LOW = "low"               # Soft, low penalty


@dataclass
class SchedulingConstraint:
    """Base constraint definition."""
    constraint_id: str
    constraint_type: ConstraintType
    priority: ConstraintPriority = ConstraintPriority.MANDATORY
    description: str = ""
    penalty_weight: float = 1000.0  # For soft constraints

    def is_hard(self) -> bool:
        """Check if this is a hard (mandatory) constraint."""
        return self.priority == ConstraintPriority.MANDATORY


@dataclass
class PrecedenceConstraint(SchedulingConstraint):
    """Operation A must complete before operation B starts."""
    predecessor_op_id: str = ""
    successor_op_id: str = ""
    min_delay: int = 0  # Minimum time between end of A and start of B
    max_delay: Optional[int] = None  # Maximum time between (for flow constraints)

    def __post_init__(self):
        self.constraint_type = ConstraintType.PRECEDENCE


@dataclass
class ResourceCapacityConstraint(SchedulingConstraint):
    """Resource has limited capacity."""
    resource_id: str = ""
    resource_type: str = "machine"  # machine, operator, tool, material
    capacity: int = 1  # Number of concurrent operations
    time_periods: Optional[List[Tuple[datetime, datetime, int]]] = None  # Variable capacity

    def __post_init__(self):
        self.constraint_type = ConstraintType.RESOURCE_CAPACITY

    def get_capacity_at(self, time: datetime) -> int:
        """Get capacity at a specific time."""
        if not self.time_periods:
            return self.capacity

        for start, end, cap in self.time_periods:
            if start <= time < end:
                return cap
        return self.capacity


@dataclass
class TimeWindowConstraint(SchedulingConstraint):
    """Operation must start/end within time bounds."""
    operation_id: str = ""
    earliest_start: Optional[datetime] = None
    latest_start: Optional[datetime] = None
    earliest_end: Optional[datetime] = None
    latest_end: Optional[datetime] = None  # Due date

    def __post_init__(self):
        self.constraint_type = ConstraintType.TIME_WINDOW


@dataclass
class SetupTimeConstraint(SchedulingConstraint):
    """Sequence-dependent setup times between operations."""
    machine_id: str = ""
    from_product_type: str = ""
    to_product_type: str = ""
    setup_time_minutes: int = 0
    requires_operator: bool = False

    def __post_init__(self):
        self.constraint_type = ConstraintType.SETUP_TIME


@dataclass
class SetupTimeMatrix:
    """Matrix of sequence-dependent setup times."""
    machine_id: str
    product_types: List[str]
    setup_times: List[List[int]]  # setup_times[from][to] in minutes

    def get_setup_time(self, from_type: str, to_type: str) -> int:
        """Get setup time between two product types."""
        try:
            from_idx = self.product_types.index(from_type)
            to_idx = self.product_types.index(to_type)
            return self.setup_times[from_idx][to_idx]
        except (ValueError, IndexError):
            return 0


@dataclass
class AlternativeMachineConstraint(SchedulingConstraint):
    """Operation can run on multiple machines with different times."""
    operation_id: str = ""
    machine_options: List[str] = field(default_factory=list)  # Machine IDs
    processing_times: Dict[str, int] = field(default_factory=dict)  # Machine -> time
    preferences: Dict[str, float] = field(default_factory=dict)  # Machine -> preference score

    def __post_init__(self):
        self.constraint_type = ConstraintType.ALTERNATIVE_MACHINE

    def get_processing_time(self, machine_id: str) -> Optional[int]:
        """Get processing time on specific machine."""
        return self.processing_times.get(machine_id)

    def get_best_machine(self) -> Optional[str]:
        """Get machine with highest preference score."""
        if not self.preferences:
            return self.machine_options[0] if self.machine_options else None
        return max(self.preferences.keys(), key=lambda m: self.preferences[m])


@dataclass
class MaintenanceWindowConstraint(SchedulingConstraint):
    """Machine is unavailable during maintenance."""
    machine_id: str = ""
    maintenance_windows: List[Tuple[datetime, datetime]] = field(default_factory=list)
    is_flexible: bool = False  # Can maintenance be moved?

    def __post_init__(self):
        self.constraint_type = ConstraintType.MAINTENANCE

    def is_available_at(self, time: datetime) -> bool:
        """Check if machine is available at specific time."""
        for start, end in self.maintenance_windows:
            if start <= time < end:
                return False
        return True

    def get_next_available(self, after: datetime) -> datetime:
        """Get next available time after given time."""
        for start, end in sorted(self.maintenance_windows):
            if start <= after < end:
                return end
        return after


@dataclass
class SkillRequirementConstraint(SchedulingConstraint):
    """Operation requires specific operator skills."""
    operation_id: str = ""
    required_skills: List[str] = field(default_factory=list)
    minimum_skill_level: int = 1  # 1-5 scale
    preferred_operators: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.constraint_type = ConstraintType.SKILL_REQUIREMENT


@dataclass
class CalendarConstraint(SchedulingConstraint):
    """Work calendar with shifts and holidays."""
    work_center_id: str = ""
    shifts: List[Dict[str, Any]] = field(default_factory=list)  # [{day, start, end}]
    holidays: List[datetime] = field(default_factory=list)
    overtime_allowed: bool = True
    overtime_penalty: float = 1.5  # Cost multiplier

    def __post_init__(self):
        self.constraint_type = ConstraintType.CALENDAR

    def is_work_time(self, time: datetime) -> bool:
        """Check if given time is within work hours."""
        # Check holidays first
        if time.date() in [h.date() for h in self.holidays]:
            return False

        # Check shifts
        day_of_week = time.strftime('%A').lower()
        time_of_day = time.time()

        for shift in self.shifts:
            if shift.get('day', '').lower() == day_of_week:
                shift_start = shift.get('start')
                shift_end = shift.get('end')
                if shift_start and shift_end:
                    if shift_start <= time_of_day <= shift_end:
                        return True

        return False


@dataclass
class BatchConstraint(SchedulingConstraint):
    """Batch size constraints for operations."""
    operation_id: str = ""
    min_batch_size: int = 1
    max_batch_size: int = 1000
    batch_multiples: Optional[int] = None  # Must be multiple of this

    def __post_init__(self):
        self.constraint_type = ConstraintType.BATCH_SIZE

    def is_valid_batch_size(self, size: int) -> bool:
        """Check if batch size is valid."""
        if size < self.min_batch_size or size > self.max_batch_size:
            return False
        if self.batch_multiples and size % self.batch_multiples != 0:
            return False
        return True


class ConstraintSet:
    """
    Collection of scheduling constraints.

    Manages all constraints for a scheduling problem
    and provides validation methods.
    """

    def __init__(self):
        self.constraints: Dict[str, SchedulingConstraint] = {}
        self._by_type: Dict[ConstraintType, List[str]] = {t: [] for t in ConstraintType}
        self._by_resource: Dict[str, List[str]] = {}
        self._by_operation: Dict[str, List[str]] = {}

    def add(self, constraint: SchedulingConstraint) -> None:
        """Add a constraint to the set."""
        self.constraints[constraint.constraint_id] = constraint
        self._by_type[constraint.constraint_type].append(constraint.constraint_id)

        # Index by resource
        if hasattr(constraint, 'machine_id') and constraint.machine_id:
            self._by_resource.setdefault(constraint.machine_id, []).append(
                constraint.constraint_id
            )
        if hasattr(constraint, 'resource_id') and constraint.resource_id:
            self._by_resource.setdefault(constraint.resource_id, []).append(
                constraint.constraint_id
            )

        # Index by operation
        if hasattr(constraint, 'operation_id') and constraint.operation_id:
            self._by_operation.setdefault(constraint.operation_id, []).append(
                constraint.constraint_id
            )

    def remove(self, constraint_id: str) -> None:
        """Remove a constraint from the set."""
        if constraint_id in self.constraints:
            constraint = self.constraints[constraint_id]
            self._by_type[constraint.constraint_type].remove(constraint_id)
            del self.constraints[constraint_id]

    def get(self, constraint_id: str) -> Optional[SchedulingConstraint]:
        """Get a constraint by ID."""
        return self.constraints.get(constraint_id)

    def get_by_type(self, constraint_type: ConstraintType) -> List[SchedulingConstraint]:
        """Get all constraints of a given type."""
        return [
            self.constraints[cid]
            for cid in self._by_type.get(constraint_type, [])
        ]

    def get_for_resource(self, resource_id: str) -> List[SchedulingConstraint]:
        """Get all constraints for a resource."""
        return [
            self.constraints[cid]
            for cid in self._by_resource.get(resource_id, [])
        ]

    def get_for_operation(self, operation_id: str) -> List[SchedulingConstraint]:
        """Get all constraints for an operation."""
        return [
            self.constraints[cid]
            for cid in self._by_operation.get(operation_id, [])
        ]

    def get_hard_constraints(self) -> List[SchedulingConstraint]:
        """Get all mandatory (hard) constraints."""
        return [c for c in self.constraints.values() if c.is_hard()]

    def get_soft_constraints(self) -> List[SchedulingConstraint]:
        """Get all soft constraints."""
        return [c for c in self.constraints.values() if not c.is_hard()]

    def get_precedence_graph(self) -> Dict[str, List[str]]:
        """Build precedence graph from constraints."""
        graph: Dict[str, List[str]] = {}
        for constraint in self.get_by_type(ConstraintType.PRECEDENCE):
            if isinstance(constraint, PrecedenceConstraint):
                graph.setdefault(constraint.predecessor_op_id, []).append(
                    constraint.successor_op_id
                )
        return graph

    def get_setup_matrix(self, machine_id: str) -> Optional[SetupTimeMatrix]:
        """Get setup time matrix for a machine."""
        setups = {}
        product_types = set()

        for constraint in self.get_for_resource(machine_id):
            if isinstance(constraint, SetupTimeConstraint):
                product_types.add(constraint.from_product_type)
                product_types.add(constraint.to_product_type)
                setups[(constraint.from_product_type, constraint.to_product_type)] = \
                    constraint.setup_time_minutes

        if not product_types:
            return None

        types_list = sorted(product_types)
        n = len(types_list)
        matrix = [[0] * n for _ in range(n)]

        for i, from_type in enumerate(types_list):
            for j, to_type in enumerate(types_list):
                matrix[i][j] = setups.get((from_type, to_type), 0)

        return SetupTimeMatrix(
            machine_id=machine_id,
            product_types=types_list,
            setup_times=matrix
        )

    def validate(self) -> List[str]:
        """Validate constraint consistency."""
        errors = []

        # Check for circular precedences
        graph = self.get_precedence_graph()
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    errors.append("Circular precedence detected in constraints")
                    break

        # Check for conflicting time windows
        by_op: Dict[str, List[TimeWindowConstraint]] = {}
        for constraint in self.get_by_type(ConstraintType.TIME_WINDOW):
            if isinstance(constraint, TimeWindowConstraint):
                by_op.setdefault(constraint.operation_id, []).append(constraint)

        for op_id, windows in by_op.items():
            if len(windows) > 1:
                # Check for conflicts
                earliest_latest_start = min(
                    (w.latest_start for w in windows if w.latest_start),
                    default=None
                )
                latest_earliest_start = max(
                    (w.earliest_start for w in windows if w.earliest_start),
                    default=None
                )
                if (earliest_latest_start and latest_earliest_start and
                    earliest_latest_start < latest_earliest_start):
                    errors.append(
                        f"Conflicting time windows for operation {op_id}"
                    )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert constraint set to dictionary."""
        return {
            'constraints': [
                {
                    'id': c.constraint_id,
                    'type': c.constraint_type.value,
                    'priority': c.priority.value,
                    'description': c.description,
                }
                for c in self.constraints.values()
            ],
            'stats': {
                'total': len(self.constraints),
                'hard': len(self.get_hard_constraints()),
                'soft': len(self.get_soft_constraints()),
                'by_type': {t.value: len(ids) for t, ids in self._by_type.items()},
            }
        }


class ConstraintBuilder:
    """
    Fluent builder for creating constraints.

    Example:
        constraint = (ConstraintBuilder()
            .precedence()
            .predecessor("op1")
            .successor("op2")
            .min_delay(5)
            .mandatory()
            .build())
    """

    def __init__(self):
        self._type: Optional[ConstraintType] = None
        self._id: str = ""
        self._priority: ConstraintPriority = ConstraintPriority.MANDATORY
        self._description: str = ""
        self._penalty: float = 1000.0
        self._params: Dict[str, Any] = {}

    def id(self, constraint_id: str) -> 'ConstraintBuilder':
        self._id = constraint_id
        return self

    def precedence(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.PRECEDENCE
        return self

    def resource_capacity(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.RESOURCE_CAPACITY
        return self

    def time_window(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.TIME_WINDOW
        return self

    def setup_time(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.SETUP_TIME
        return self

    def alternative_machine(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.ALTERNATIVE_MACHINE
        return self

    def maintenance(self) -> 'ConstraintBuilder':
        self._type = ConstraintType.MAINTENANCE
        return self

    def mandatory(self) -> 'ConstraintBuilder':
        self._priority = ConstraintPriority.MANDATORY
        return self

    def soft(self, priority: ConstraintPriority = ConstraintPriority.MEDIUM) -> 'ConstraintBuilder':
        self._priority = priority
        return self

    def penalty(self, weight: float) -> 'ConstraintBuilder':
        self._penalty = weight
        return self

    def description(self, desc: str) -> 'ConstraintBuilder':
        self._description = desc
        return self

    # Precedence-specific
    def predecessor(self, op_id: str) -> 'ConstraintBuilder':
        self._params['predecessor_op_id'] = op_id
        return self

    def successor(self, op_id: str) -> 'ConstraintBuilder':
        self._params['successor_op_id'] = op_id
        return self

    def min_delay(self, minutes: int) -> 'ConstraintBuilder':
        self._params['min_delay'] = minutes
        return self

    def max_delay(self, minutes: int) -> 'ConstraintBuilder':
        self._params['max_delay'] = minutes
        return self

    # Resource-specific
    def resource(self, resource_id: str) -> 'ConstraintBuilder':
        self._params['resource_id'] = resource_id
        return self

    def capacity(self, cap: int) -> 'ConstraintBuilder':
        self._params['capacity'] = cap
        return self

    # Time window-specific
    def operation(self, op_id: str) -> 'ConstraintBuilder':
        self._params['operation_id'] = op_id
        return self

    def earliest_start(self, time: datetime) -> 'ConstraintBuilder':
        self._params['earliest_start'] = time
        return self

    def latest_end(self, time: datetime) -> 'ConstraintBuilder':
        self._params['latest_end'] = time
        return self

    # Alternative machine-specific
    def machines(self, machine_ids: List[str]) -> 'ConstraintBuilder':
        self._params['machine_options'] = machine_ids
        return self

    def processing_times(self, times: Dict[str, int]) -> 'ConstraintBuilder':
        self._params['processing_times'] = times
        return self

    # Machine-specific
    def machine(self, machine_id: str) -> 'ConstraintBuilder':
        self._params['machine_id'] = machine_id
        return self

    def build(self) -> SchedulingConstraint:
        """Build the constraint."""
        if not self._id:
            from uuid import uuid4
            self._id = str(uuid4())

        base_params = {
            'constraint_id': self._id,
            'priority': self._priority,
            'description': self._description,
            'penalty_weight': self._penalty,
        }

        if self._type == ConstraintType.PRECEDENCE:
            return PrecedenceConstraint(**base_params, **self._params)
        elif self._type == ConstraintType.RESOURCE_CAPACITY:
            return ResourceCapacityConstraint(**base_params, **self._params)
        elif self._type == ConstraintType.TIME_WINDOW:
            return TimeWindowConstraint(**base_params, **self._params)
        elif self._type == ConstraintType.SETUP_TIME:
            return SetupTimeConstraint(**base_params, **self._params)
        elif self._type == ConstraintType.ALTERNATIVE_MACHINE:
            return AlternativeMachineConstraint(**base_params, **self._params)
        elif self._type == ConstraintType.MAINTENANCE:
            return MaintenanceWindowConstraint(**base_params, **self._params)
        else:
            return SchedulingConstraint(
                constraint_id=self._id,
                constraint_type=self._type or ConstraintType.PRECEDENCE,
                **{k: v for k, v in base_params.items() if k != 'constraint_id'}
            )
