"""
Model Checker for State Machine Verification

Implements bounded model checking for manufacturing
state machines and control systems.

Reference: TLA+, SPIN, NuSMV, CTL/LTL Temporal Logic
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union
from datetime import datetime
from enum import Enum, auto
from collections import deque
import itertools
import hashlib

logger = logging.getLogger(__name__)


class TemporalOperator(Enum):
    """Temporal logic operators (CTL/LTL)."""
    # Path quantifiers (CTL)
    ALWAYS = "G"           # Globally (on all paths)
    EVENTUALLY = "F"       # Eventually (on all paths)
    NEXT = "X"             # Next state
    UNTIL = "U"            # Until

    # CTL-specific
    EXISTS_ALWAYS = "EG"   # Exists a path where always
    EXISTS_EVENTUALLY = "EF"  # Exists a path where eventually
    ALL_ALWAYS = "AG"      # All paths, always
    ALL_EVENTUALLY = "AF"  # All paths, eventually


class PropertyResult(Enum):
    """Model checking result."""
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class State:
    """
    Immutable state in a state machine.

    Uses frozen dataclass for hashability.
    """
    values: Tuple[Tuple[str, Any], ...]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "State":
        """Create state from dictionary."""
        return cls(tuple(sorted(d.items())))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return dict(self.values)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        d = dict(self.values)
        return d.get(key, default)

    def __str__(self) -> str:
        return str(dict(self.values))


@dataclass
class Transition:
    """State machine transition."""
    name: str
    source: Optional[str] = None  # None means any state
    guard: Optional[Callable[[State], bool]] = None
    action: Optional[Callable[[State], State]] = None

    def is_enabled(self, state: State) -> bool:
        """Check if transition is enabled in state."""
        if self.guard is None:
            return True
        try:
            return self.guard(state)
        except Exception:
            return False

    def execute(self, state: State) -> State:
        """Execute transition from state."""
        if self.action is None:
            return state
        return self.action(state)


@dataclass
class TemporalProperty:
    """
    Temporal logic property specification.

    Supports CTL and LTL properties.

    Examples:
        - AG(safe)           : Always safe in all paths
        - EF(goal)           : Eventually reaches goal
        - AG(request -> AF(response))  : Requests always get responses
    """
    operator: TemporalOperator
    predicate: Callable[[State], bool]
    name: str = ""
    description: str = ""

    # For nested properties
    nested_property: Optional["TemporalProperty"] = None

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.operator.value}({self.predicate.__name__ if hasattr(self.predicate, '__name__') else 'phi'})"


@dataclass
class CounterExample:
    """Counterexample trace for property violation."""
    property_name: str
    trace: List[State]
    loop_start: Optional[int] = None  # For liveness counterexamples

    def __str__(self) -> str:
        lines = [f"Counterexample for: {self.property_name}"]
        for i, state in enumerate(self.trace):
            prefix = "→ " if self.loop_start and i >= self.loop_start else "  "
            lines.append(f"{prefix}State {i}: {state}")
        if self.loop_start is not None:
            lines.append(f"(loop back to state {self.loop_start})")
        return "\n".join(lines)


@dataclass
class ModelCheckResult:
    """Result of model checking."""
    property_name: str
    result: PropertyResult
    states_explored: int = 0
    transitions_explored: int = 0
    counterexample: Optional[CounterExample] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property": self.property_name,
            "result": self.result.value,
            "states_explored": self.states_explored,
            "transitions_explored": self.transitions_explored,
            "has_counterexample": self.counterexample is not None,
            "duration_ms": self.duration_ms
        }


class StateModel:
    """
    State machine model for verification.

    Defines states, transitions, and initial state.

    Usage:
        >>> model = StateModel()
        >>> model.set_initial({"state": "idle", "count": 0})
        >>> model.add_transition("start", guard=lambda s: s.get("state") == "idle",
        ...                      action=lambda s: State.from_dict({**s.to_dict(), "state": "running"}))
        >>> model.add_invariant("count_positive", lambda s: s.get("count", 0) >= 0)
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name
        self.initial_state: Optional[State] = None
        self.transitions: List[Transition] = []
        self.invariants: Dict[str, Callable[[State], bool]] = {}
        self.state_labels: Dict[str, Callable[[State], bool]] = {}

    def set_initial(self, state: Union[State, Dict[str, Any]]) -> None:
        """Set initial state."""
        if isinstance(state, dict):
            state = State.from_dict(state)
        self.initial_state = state

    def add_transition(
        self,
        name: str,
        guard: Optional[Callable[[State], bool]] = None,
        action: Optional[Callable[[State], State]] = None
    ) -> None:
        """Add a transition."""
        self.transitions.append(Transition(name=name, guard=guard, action=action))

    def add_invariant(self, name: str, predicate: Callable[[State], bool]) -> None:
        """Add a state invariant (must always hold)."""
        self.invariants[name] = predicate

    def add_label(self, name: str, predicate: Callable[[State], bool]) -> None:
        """Add a state label for property checking."""
        self.state_labels[name] = predicate

    def get_successors(self, state: State) -> List[Tuple[str, State]]:
        """Get all successor states from current state."""
        successors = []
        for trans in self.transitions:
            if trans.is_enabled(state):
                try:
                    next_state = trans.execute(state)
                    successors.append((trans.name, next_state))
                except Exception as e:
                    logger.warning(f"Transition {trans.name} failed: {e}")
        return successors

    def check_invariants(self, state: State) -> List[str]:
        """Check all invariants, return list of violated ones."""
        violated = []
        for name, pred in self.invariants.items():
            try:
                if not pred(state):
                    violated.append(name)
            except Exception as e:
                logger.warning(f"Invariant {name} raised exception: {e}")
                violated.append(name)
        return violated


class ModelChecker:
    """
    Bounded Model Checker for state machine verification.

    Supports:
    - Invariant checking
    - CTL property verification
    - LTL property verification (bounded)
    - Deadlock detection
    - Liveness properties

    Reference: Symbolic Model Checking, SAT-based BMC

    Usage:
        >>> checker = ModelChecker(model, max_depth=100)
        >>> result = checker.check_invariants()
        >>> result = checker.check_property(AG(safe))
    """

    def __init__(
        self,
        model: StateModel,
        max_depth: int = 1000,
        max_states: int = 100000
    ):
        """
        Initialize model checker.

        Args:
            model: State machine model
            max_depth: Maximum exploration depth
            max_states: Maximum states to explore
        """
        self.model = model
        self.max_depth = max_depth
        self.max_states = max_states

        logger.info(f"ModelChecker initialized for model: {model.name}")

    def check_invariants(self) -> List[ModelCheckResult]:
        """Check all model invariants using BFS."""
        import time
        results = []

        for inv_name, inv_pred in self.model.invariants.items():
            start_time = time.time()

            prop = TemporalProperty(
                operator=TemporalOperator.ALL_ALWAYS,
                predicate=inv_pred,
                name=f"invariant_{inv_name}"
            )

            result = self._check_ag(prop)
            result.duration_ms = (time.time() - start_time) * 1000
            results.append(result)

        return results

    def check_property(self, prop: TemporalProperty) -> ModelCheckResult:
        """Check a temporal property."""
        import time
        start_time = time.time()

        if prop.operator == TemporalOperator.ALL_ALWAYS:
            result = self._check_ag(prop)
        elif prop.operator == TemporalOperator.ALL_EVENTUALLY:
            result = self._check_af(prop)
        elif prop.operator == TemporalOperator.EXISTS_EVENTUALLY:
            result = self._check_ef(prop)
        elif prop.operator == TemporalOperator.EXISTS_ALWAYS:
            result = self._check_eg(prop)
        else:
            result = ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.UNKNOWN
            )

        result.duration_ms = (time.time() - start_time) * 1000
        return result

    def check_deadlock_freedom(self) -> ModelCheckResult:
        """Check that no deadlock states exist."""
        import time
        start_time = time.time()

        if self.model.initial_state is None:
            return ModelCheckResult(
                property_name="deadlock_freedom",
                result=PropertyResult.UNKNOWN
            )

        visited: Set[State] = set()
        queue: deque = deque([(self.model.initial_state, [self.model.initial_state])])
        states_explored = 0
        transitions_explored = 0

        while queue and len(visited) < self.max_states:
            current, trace = queue.popleft()

            if current in visited:
                continue
            visited.add(current)
            states_explored += 1

            # Check for deadlock (no enabled transitions)
            successors = self.model.get_successors(current)
            transitions_explored += len(successors)

            if not successors:
                # Deadlock found
                return ModelCheckResult(
                    property_name="deadlock_freedom",
                    result=PropertyResult.VIOLATED,
                    states_explored=states_explored,
                    transitions_explored=transitions_explored,
                    counterexample=CounterExample(
                        property_name="deadlock_freedom",
                        trace=trace
                    ),
                    duration_ms=(time.time() - start_time) * 1000
                )

            for trans_name, next_state in successors:
                if next_state not in visited and len(trace) < self.max_depth:
                    queue.append((next_state, trace + [next_state]))

        return ModelCheckResult(
            property_name="deadlock_freedom",
            result=PropertyResult.SATISFIED,
            states_explored=states_explored,
            transitions_explored=transitions_explored,
            duration_ms=(time.time() - start_time) * 1000
        )

    def _check_ag(self, prop: TemporalProperty) -> ModelCheckResult:
        """Check AG (always globally) property using BFS."""
        if self.model.initial_state is None:
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.UNKNOWN
            )

        visited: Set[State] = set()
        queue: deque = deque([(self.model.initial_state, [self.model.initial_state])])
        states_explored = 0
        transitions_explored = 0

        while queue and len(visited) < self.max_states:
            current, trace = queue.popleft()

            if current in visited:
                continue
            visited.add(current)
            states_explored += 1

            # Check property
            try:
                if not prop.predicate(current):
                    return ModelCheckResult(
                        property_name=prop.name,
                        result=PropertyResult.VIOLATED,
                        states_explored=states_explored,
                        transitions_explored=transitions_explored,
                        counterexample=CounterExample(
                            property_name=prop.name,
                            trace=trace
                        )
                    )
            except Exception as e:
                logger.warning(f"Property check failed: {e}")

            # Explore successors
            for trans_name, next_state in self.model.get_successors(current):
                transitions_explored += 1
                if next_state not in visited and len(trace) < self.max_depth:
                    queue.append((next_state, trace + [next_state]))

        return ModelCheckResult(
            property_name=prop.name,
            result=PropertyResult.SATISFIED,
            states_explored=states_explored,
            transitions_explored=transitions_explored
        )

    def _check_af(self, prop: TemporalProperty) -> ModelCheckResult:
        """Check AF (all paths eventually) property."""
        if self.model.initial_state is None:
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.UNKNOWN
            )

        # Use nested DFS to find paths where phi never holds
        visited: Set[State] = set()
        states_explored = 0

        def dfs(state: State, trace: List[State], depth: int) -> Optional[CounterExample]:
            nonlocal states_explored

            if state in visited:
                # Found cycle - check if phi held on this path
                if not any(prop.predicate(s) for s in trace):
                    loop_idx = trace.index(state) if state in trace else None
                    return CounterExample(
                        property_name=prop.name,
                        trace=trace,
                        loop_start=loop_idx
                    )
                return None

            if depth >= self.max_depth:
                return None

            visited.add(state)
            states_explored += 1

            # Check if property holds here
            try:
                if prop.predicate(state):
                    return None  # Property satisfied on this path
            except Exception:
                pass

            # Explore successors
            successors = self.model.get_successors(state)
            if not successors:
                # Terminal state without satisfaction
                return CounterExample(
                    property_name=prop.name,
                    trace=trace + [state]
                )

            for _, next_state in successors:
                ce = dfs(next_state, trace + [state], depth + 1)
                if ce:
                    return ce

            return None

        ce = dfs(self.model.initial_state, [], 0)

        if ce:
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.VIOLATED,
                states_explored=states_explored,
                counterexample=ce
            )

        return ModelCheckResult(
            property_name=prop.name,
            result=PropertyResult.SATISFIED,
            states_explored=states_explored
        )

    def _check_ef(self, prop: TemporalProperty) -> ModelCheckResult:
        """Check EF (exists path eventually) property."""
        if self.model.initial_state is None:
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.UNKNOWN
            )

        visited: Set[State] = set()
        queue: deque = deque([(self.model.initial_state, [self.model.initial_state])])
        states_explored = 0

        while queue and len(visited) < self.max_states:
            current, trace = queue.popleft()

            if current in visited:
                continue
            visited.add(current)
            states_explored += 1

            # Check property
            try:
                if prop.predicate(current):
                    return ModelCheckResult(
                        property_name=prop.name,
                        result=PropertyResult.SATISFIED,
                        states_explored=states_explored
                    )
            except Exception:
                pass

            for _, next_state in self.model.get_successors(current):
                if next_state not in visited and len(trace) < self.max_depth:
                    queue.append((next_state, trace + [next_state]))

        return ModelCheckResult(
            property_name=prop.name,
            result=PropertyResult.VIOLATED,
            states_explored=states_explored
        )

    def _check_eg(self, prop: TemporalProperty) -> ModelCheckResult:
        """Check EG (exists path where always) property."""
        # Find if there's an infinite path where phi always holds
        if self.model.initial_state is None:
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.UNKNOWN
            )

        # Simplified: Look for cycles where property holds
        visited: Set[State] = set()
        in_stack: Set[State] = set()
        states_explored = 0

        def dfs(state: State, path: List[State]) -> bool:
            nonlocal states_explored

            if state in in_stack:
                # Found cycle - check if property holds in cycle
                cycle_start = path.index(state)
                cycle = path[cycle_start:]
                return all(prop.predicate(s) for s in cycle)

            if state in visited or len(path) >= self.max_depth:
                return False

            visited.add(state)
            in_stack.add(state)
            states_explored += 1

            try:
                if not prop.predicate(state):
                    in_stack.discard(state)
                    return False
            except Exception:
                in_stack.discard(state)
                return False

            for _, next_state in self.model.get_successors(state):
                if dfs(next_state, path + [state]):
                    in_stack.discard(state)
                    return True

            in_stack.discard(state)
            return False

        if dfs(self.model.initial_state, []):
            return ModelCheckResult(
                property_name=prop.name,
                result=PropertyResult.SATISFIED,
                states_explored=states_explored
            )

        return ModelCheckResult(
            property_name=prop.name,
            result=PropertyResult.VIOLATED,
            states_explored=states_explored
        )


# Convenience functions for creating temporal properties
def AG(predicate: Callable[[State], bool], name: str = "") -> TemporalProperty:
    """All paths, always (globally)."""
    return TemporalProperty(TemporalOperator.ALL_ALWAYS, predicate, name)


def AF(predicate: Callable[[State], bool], name: str = "") -> TemporalProperty:
    """All paths, eventually (finally)."""
    return TemporalProperty(TemporalOperator.ALL_EVENTUALLY, predicate, name)


def EF(predicate: Callable[[State], bool], name: str = "") -> TemporalProperty:
    """Exists path, eventually."""
    return TemporalProperty(TemporalOperator.EXISTS_EVENTUALLY, predicate, name)


def EG(predicate: Callable[[State], bool], name: str = "") -> TemporalProperty:
    """Exists path, always."""
    return TemporalProperty(TemporalOperator.EXISTS_ALWAYS, predicate, name)
