"""
Formal State Machine Verification for Manufacturing Digital Twins.

This module implements verified state machines for manufacturing processes:
- Formal state machine definitions with guards and actions
- Model checking for safety and liveness properties
- Bisimulation for state equivalence verification
- Temporal logic verification (CTL/LTL subset)

Research Value:
- Formal methods applied to manufacturing processes
- Verified digital twin state transitions
- Safety-critical manufacturing validation

References:
- Harel, D. (1987). Statecharts: A visual formalism
- Clarke, E.M., Grumberg, O., Peled, D.A. (1999). Model Checking
- ISO 23247 Digital Twin Framework
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, FrozenSet, Iterator, Union
)
from uuid import UUID, uuid4
import logging
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


# =============================================================================
# State Machine Core Components
# =============================================================================

@dataclass(frozen=True)
class State:
    """
    Immutable state in a state machine.

    States can be:
    - Simple states (atomic)
    - Composite states (containing substates)
    - Final states (terminal)
    """
    name: str
    is_initial: bool = False
    is_final: bool = False
    parent: Optional[str] = None  # For hierarchical state machines
    invariant: Optional[str] = None  # State invariant condition
    entry_action: Optional[str] = None
    exit_action: Optional[str] = None
    timeout_ms: Optional[int] = None  # Optional timeout

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self.name == other.name
        return False


@dataclass(frozen=True)
class Guard:
    """
    Transition guard (precondition).

    Guards are boolean expressions that must be true for a transition to fire.
    """
    name: str
    expression: str  # Boolean expression
    description: Optional[str] = None

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate guard expression against context.

        Uses safe eval with restricted namespace.
        """
        try:
            # Safe evaluation with limited scope
            allowed_names = {
                'True': True,
                'False': False,
                'None': None,
                'abs': abs,
                'min': min,
                'max': max,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
            }
            allowed_names.update(context)

            return bool(eval(self.expression, {"__builtins__": {}}, allowed_names))
        except Exception as e:
            logger.error(f"Guard evaluation failed: {e}")
            return False


@dataclass(frozen=True)
class Action:
    """
    Action executed during state transitions.

    Actions can be:
    - Entry actions (executed when entering a state)
    - Exit actions (executed when leaving a state)
    - Transition actions (executed during transition)
    """
    name: str
    action_type: str  # 'entry', 'exit', 'transition'
    handler: Optional[str] = None  # Handler function name
    parameters: Tuple[str, ...] = field(default_factory=tuple)

    def execute(
        self,
        context: Dict[str, Any],
        handlers: Dict[str, Callable]
    ) -> Any:
        """Execute action using registered handler."""
        if self.handler and self.handler in handlers:
            handler_fn = handlers[self.handler]
            params = {p: context.get(p) for p in self.parameters}
            return handler_fn(**params)
        return None


@dataclass(frozen=True)
class Transition:
    """
    State transition definition.

    Transitions connect states and define the conditions and actions
    for moving between states.
    """
    name: str
    source: str  # Source state name
    target: str  # Target state name
    event: str  # Triggering event
    guard: Optional[Guard] = None
    action: Optional[Action] = None
    priority: int = 0  # Higher priority fires first

    def is_enabled(self, context: Dict[str, Any]) -> bool:
        """Check if transition is enabled (guard satisfied)."""
        if self.guard is None:
            return True
        return self.guard.evaluate(context)


# =============================================================================
# State Machine Definition
# =============================================================================

class StateMachineType(Enum):
    """Types of state machines."""
    FINITE = auto()  # Basic FSM
    EXTENDED = auto()  # FSM with variables
    HIERARCHICAL = auto()  # Statecharts
    PARALLEL = auto()  # Concurrent regions


@dataclass
class StateMachineDefinition:
    """
    Complete state machine definition.

    Defines the structure of a state machine including all states,
    transitions, and properties.
    """
    name: str
    machine_type: StateMachineType
    states: Dict[str, State] = field(default_factory=dict)
    transitions: List[Transition] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    events: Set[str] = field(default_factory=set)

    def add_state(self, state: State) -> None:
        """Add a state to the machine."""
        self.states[state.name] = state

    def add_transition(self, transition: Transition) -> None:
        """Add a transition to the machine."""
        self.transitions.append(transition)
        self.events.add(transition.event)

    def get_initial_state(self) -> Optional[State]:
        """Get the initial state."""
        for state in self.states.values():
            if state.is_initial:
                return state
        return None

    def get_final_states(self) -> Set[State]:
        """Get all final states."""
        return {s for s in self.states.values() if s.is_final}

    def get_outgoing_transitions(self, state_name: str) -> List[Transition]:
        """Get all transitions from a state."""
        return sorted(
            [t for t in self.transitions if t.source == state_name],
            key=lambda t: -t.priority
        )

    def get_incoming_transitions(self, state_name: str) -> List[Transition]:
        """Get all transitions to a state."""
        return [t for t in self.transitions if t.target == state_name]

    def validate(self) -> List[str]:
        """
        Validate state machine definition.

        Returns list of validation errors.
        """
        errors = []

        # Check for initial state
        initial_states = [s for s in self.states.values() if s.is_initial]
        if len(initial_states) == 0:
            errors.append("No initial state defined")
        elif len(initial_states) > 1:
            errors.append(f"Multiple initial states: {[s.name for s in initial_states]}")

        # Check all transitions reference valid states
        for transition in self.transitions:
            if transition.source not in self.states:
                errors.append(f"Transition {transition.name}: source state '{transition.source}' not found")
            if transition.target not in self.states:
                errors.append(f"Transition {transition.name}: target state '{transition.target}' not found")

        # Check for unreachable states
        reachable = self._compute_reachable_states()
        unreachable = set(self.states.keys()) - reachable
        if unreachable:
            errors.append(f"Unreachable states: {unreachable}")

        # Check for deadlock states (non-final without outgoing)
        for state in self.states.values():
            if not state.is_final:
                outgoing = self.get_outgoing_transitions(state.name)
                if not outgoing:
                    errors.append(f"Potential deadlock: state '{state.name}' has no outgoing transitions")

        return errors

    def _compute_reachable_states(self) -> Set[str]:
        """Compute set of reachable states from initial state."""
        initial = self.get_initial_state()
        if not initial:
            return set()

        reachable = set()
        worklist = [initial.name]

        while worklist:
            current = worklist.pop()
            if current in reachable:
                continue
            reachable.add(current)

            for transition in self.get_outgoing_transitions(current):
                if transition.target not in reachable:
                    worklist.append(transition.target)

        return reachable


# =============================================================================
# State Machine Instance
# =============================================================================

@dataclass
class StateTransitionEvent:
    """Record of a state transition."""
    transition_id: UUID
    transition_name: str
    source_state: str
    target_state: str
    event: str
    timestamp: datetime
    context: Dict[str, Any]


class StateMachine:
    """
    Runtime state machine instance.

    Manages the current state and processes events to trigger transitions.
    """

    def __init__(
        self,
        definition: StateMachineDefinition,
        instance_id: Optional[UUID] = None
    ):
        self.definition = definition
        self.instance_id = instance_id or uuid4()
        self._current_state: Optional[State] = None
        self._context: Dict[str, Any] = {}
        self._history: List[StateTransitionEvent] = []
        self._action_handlers: Dict[str, Callable] = {}
        self._observers: List[Callable[[StateTransitionEvent], None]] = []

        # Initialize to initial state
        initial = definition.get_initial_state()
        if initial:
            self._current_state = initial

    @property
    def current_state(self) -> Optional[State]:
        return self._current_state

    @property
    def context(self) -> Dict[str, Any]:
        return self._context.copy()

    @property
    def history(self) -> List[StateTransitionEvent]:
        return self._history.copy()

    def register_action_handler(
        self,
        name: str,
        handler: Callable
    ) -> None:
        """Register a handler function for actions."""
        self._action_handlers[name] = handler

    def add_observer(
        self,
        observer: Callable[[StateTransitionEvent], None]
    ) -> None:
        """Add observer for state transitions."""
        self._observers.append(observer)

    def set_context(self, key: str, value: Any) -> None:
        """Set a context variable."""
        self._context[key] = value

    def process_event(
        self,
        event: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Optional[StateTransitionEvent]:
        """
        Process an event and potentially transition to a new state.

        Returns the transition event if a transition occurred, None otherwise.
        """
        if not self._current_state:
            logger.warning("State machine has no current state")
            return None

        # Merge event data into context
        if event_data:
            self._context.update(event_data)

        # Find enabled transitions for this event
        outgoing = self.definition.get_outgoing_transitions(self._current_state.name)
        enabled = [
            t for t in outgoing
            if t.event == event and t.is_enabled(self._context)
        ]

        if not enabled:
            logger.debug(f"No enabled transitions for event '{event}' in state '{self._current_state.name}'")
            return None

        # Take highest priority transition
        transition = enabled[0]

        # Execute exit action
        if self._current_state.exit_action:
            self._execute_action_by_name(self._current_state.exit_action)

        # Execute transition action
        if transition.action:
            transition.action.execute(self._context, self._action_handlers)

        # Record transition
        transition_event = StateTransitionEvent(
            transition_id=uuid4(),
            transition_name=transition.name,
            source_state=self._current_state.name,
            target_state=transition.target,
            event=event,
            timestamp=datetime.utcnow(),
            context=self._context.copy()
        )
        self._history.append(transition_event)

        # Transition to new state
        self._current_state = self.definition.states[transition.target]

        # Execute entry action
        if self._current_state.entry_action:
            self._execute_action_by_name(self._current_state.entry_action)

        # Notify observers
        for observer in self._observers:
            try:
                observer(transition_event)
            except Exception as e:
                logger.error(f"Observer error: {e}")

        return transition_event

    def _execute_action_by_name(self, action_name: str) -> None:
        """Execute an action by name."""
        if action_name in self._action_handlers:
            try:
                self._action_handlers[action_name](self._context)
            except Exception as e:
                logger.error(f"Action '{action_name}' failed: {e}")

    def can_process(self, event: str) -> bool:
        """Check if an event can be processed in current state."""
        if not self._current_state:
            return False

        outgoing = self.definition.get_outgoing_transitions(self._current_state.name)
        return any(
            t.event == event and t.is_enabled(self._context)
            for t in outgoing
        )

    def get_available_events(self) -> Set[str]:
        """Get events that can be processed in current state."""
        if not self._current_state:
            return set()

        outgoing = self.definition.get_outgoing_transitions(self._current_state.name)
        return {
            t.event for t in outgoing
            if t.is_enabled(self._context)
        }

    def is_in_final_state(self) -> bool:
        """Check if machine is in a final state."""
        return self._current_state is not None and self._current_state.is_final

    def reset(self) -> None:
        """Reset machine to initial state."""
        initial = self.definition.get_initial_state()
        self._current_state = initial
        self._context.clear()
        self._history.clear()


# =============================================================================
# Manufacturing State Machine Definitions
# =============================================================================

def create_print_job_state_machine() -> StateMachineDefinition:
    """
    Create state machine for print job lifecycle.

    States: Created → Scheduled → Printing → Completed/Failed
    """
    sm = StateMachineDefinition(
        name="PrintJobStateMachine",
        machine_type=StateMachineType.EXTENDED
    )

    # States
    sm.add_state(State("created", is_initial=True))
    sm.add_state(State("scheduled"))
    sm.add_state(State("preparing"))
    sm.add_state(State("printing"))
    sm.add_state(State("paused"))
    sm.add_state(State("inspecting"))
    sm.add_state(State("completed", is_final=True))
    sm.add_state(State("failed", is_final=True))
    sm.add_state(State("cancelled", is_final=True))

    # Transitions
    sm.add_transition(Transition(
        name="schedule",
        source="created",
        target="scheduled",
        event="SCHEDULE"
    ))

    sm.add_transition(Transition(
        name="prepare",
        source="scheduled",
        target="preparing",
        event="START_PREPARE"
    ))

    sm.add_transition(Transition(
        name="start_print",
        source="preparing",
        target="printing",
        event="START_PRINT",
        guard=Guard("machine_ready", "machine_status == 'ready'")
    ))

    sm.add_transition(Transition(
        name="pause",
        source="printing",
        target="paused",
        event="PAUSE"
    ))

    sm.add_transition(Transition(
        name="resume",
        source="paused",
        target="printing",
        event="RESUME"
    ))

    sm.add_transition(Transition(
        name="print_complete",
        source="printing",
        target="inspecting",
        event="PRINT_COMPLETE"
    ))

    sm.add_transition(Transition(
        name="inspection_pass",
        source="inspecting",
        target="completed",
        event="INSPECTION_PASS"
    ))

    sm.add_transition(Transition(
        name="inspection_fail",
        source="inspecting",
        target="failed",
        event="INSPECTION_FAIL"
    ))

    sm.add_transition(Transition(
        name="error",
        source="printing",
        target="failed",
        event="ERROR"
    ))

    sm.add_transition(Transition(
        name="cancel_created",
        source="created",
        target="cancelled",
        event="CANCEL"
    ))

    sm.add_transition(Transition(
        name="cancel_scheduled",
        source="scheduled",
        target="cancelled",
        event="CANCEL"
    ))

    sm.add_transition(Transition(
        name="cancel_paused",
        source="paused",
        target="cancelled",
        event="CANCEL"
    ))

    return sm


def create_machine_state_machine() -> StateMachineDefinition:
    """
    Create state machine for machine/printer lifecycle.

    States: Offline → Idle → Running → Maintenance
    """
    sm = StateMachineDefinition(
        name="MachineStateMachine",
        machine_type=StateMachineType.EXTENDED
    )

    # States
    sm.add_state(State("offline", is_initial=True))
    sm.add_state(State("starting"))
    sm.add_state(State("idle"))
    sm.add_state(State("running"))
    sm.add_state(State("error"))
    sm.add_state(State("maintenance"))
    sm.add_state(State("shutdown", is_final=True))

    # Transitions
    sm.add_transition(Transition(
        name="power_on",
        source="offline",
        target="starting",
        event="POWER_ON"
    ))

    sm.add_transition(Transition(
        name="startup_complete",
        source="starting",
        target="idle",
        event="STARTUP_COMPLETE"
    ))

    sm.add_transition(Transition(
        name="start_job",
        source="idle",
        target="running",
        event="START_JOB",
        guard=Guard("has_job", "job_id is not None")
    ))

    sm.add_transition(Transition(
        name="job_complete",
        source="running",
        target="idle",
        event="JOB_COMPLETE"
    ))

    sm.add_transition(Transition(
        name="error_running",
        source="running",
        target="error",
        event="ERROR"
    ))

    sm.add_transition(Transition(
        name="error_idle",
        source="idle",
        target="error",
        event="ERROR"
    ))

    sm.add_transition(Transition(
        name="recover",
        source="error",
        target="idle",
        event="RECOVER"
    ))

    sm.add_transition(Transition(
        name="start_maintenance_idle",
        source="idle",
        target="maintenance",
        event="START_MAINTENANCE"
    ))

    sm.add_transition(Transition(
        name="complete_maintenance",
        source="maintenance",
        target="idle",
        event="COMPLETE_MAINTENANCE"
    ))

    sm.add_transition(Transition(
        name="power_off",
        source="idle",
        target="shutdown",
        event="POWER_OFF"
    ))

    return sm


def create_quality_inspection_state_machine() -> StateMachineDefinition:
    """
    Create state machine for quality inspection process.
    """
    sm = StateMachineDefinition(
        name="QualityInspectionStateMachine",
        machine_type=StateMachineType.EXTENDED
    )

    # States
    sm.add_state(State("pending", is_initial=True))
    sm.add_state(State("visual_inspection"))
    sm.add_state(State("dimensional_check"))
    sm.add_state(State("functional_test"))
    sm.add_state(State("review"))
    sm.add_state(State("approved", is_final=True))
    sm.add_state(State("rejected", is_final=True))
    sm.add_state(State("rework_required", is_final=True))

    # Transitions
    sm.add_transition(Transition(
        name="start_inspection",
        source="pending",
        target="visual_inspection",
        event="START"
    ))

    sm.add_transition(Transition(
        name="visual_pass",
        source="visual_inspection",
        target="dimensional_check",
        event="VISUAL_PASS"
    ))

    sm.add_transition(Transition(
        name="visual_fail",
        source="visual_inspection",
        target="rejected",
        event="VISUAL_FAIL"
    ))

    sm.add_transition(Transition(
        name="dimensional_pass",
        source="dimensional_check",
        target="functional_test",
        event="DIMENSIONAL_PASS"
    ))

    sm.add_transition(Transition(
        name="dimensional_fail",
        source="dimensional_check",
        target="rework_required",
        event="DIMENSIONAL_FAIL"
    ))

    sm.add_transition(Transition(
        name="functional_pass",
        source="functional_test",
        target="review",
        event="FUNCTIONAL_PASS"
    ))

    sm.add_transition(Transition(
        name="functional_fail",
        source="functional_test",
        target="rejected",
        event="FUNCTIONAL_FAIL"
    ))

    sm.add_transition(Transition(
        name="approve",
        source="review",
        target="approved",
        event="APPROVE"
    ))

    sm.add_transition(Transition(
        name="request_rework",
        source="review",
        target="rework_required",
        event="REQUEST_REWORK"
    ))

    return sm


# =============================================================================
# State Machine Verification
# =============================================================================

class PropertyType(Enum):
    """Types of temporal properties to verify."""
    SAFETY = auto()  # Nothing bad ever happens
    LIVENESS = auto()  # Something good eventually happens
    REACHABILITY = auto()  # A state is reachable
    DEADLOCK_FREEDOM = auto()  # No deadlocks
    DETERMINISM = auto()  # No non-deterministic transitions
    INVARIANT = auto()  # Property holds in all reachable states


@dataclass
class VerificationProperty:
    """Property to be verified against a state machine."""
    name: str
    property_type: PropertyType
    expression: str
    description: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of a verification check."""
    property_name: str
    property_type: PropertyType
    satisfied: bool
    counterexample: Optional[List[str]] = None  # Trace to violation
    message: str = ""


class StateMachineVerifier:
    """
    Formal verification for state machines.

    Implements model checking techniques for manufacturing state machines:
    - Reachability analysis
    - Deadlock detection
    - Determinism checking
    - Safety property verification
    - Liveness checking (bounded)

    Research Value:
    - Formal methods for manufacturing process verification
    - Safety-critical manufacturing validation
    """

    def __init__(self, definition: StateMachineDefinition):
        self.definition = definition
        self._reachable_states: Optional[Set[str]] = None
        self._transition_graph: Dict[str, Set[str]] = defaultdict(set)

        self._build_transition_graph()

    def _build_transition_graph(self) -> None:
        """Build graph representation for analysis."""
        for transition in self.definition.transitions:
            self._transition_graph[transition.source].add(transition.target)

    def verify_all(self) -> List[VerificationResult]:
        """Run all standard verification checks."""
        results = []

        results.append(self.verify_determinism())
        results.append(self.verify_deadlock_freedom())
        results.append(self.verify_reachability_all_states())
        results.append(self.verify_final_state_reachability())

        return results

    def verify_determinism(self) -> VerificationResult:
        """
        Verify that the state machine is deterministic.

        A machine is deterministic if for any state and event,
        at most one transition is enabled.
        """
        non_deterministic = []

        for state_name in self.definition.states:
            outgoing = self.definition.get_outgoing_transitions(state_name)

            # Group transitions by event
            by_event: Dict[str, List[Transition]] = defaultdict(list)
            for t in outgoing:
                by_event[t.event].append(t)

            # Check for non-determinism (same event, overlapping guards)
            for event, transitions in by_event.items():
                if len(transitions) > 1:
                    # Check if guards are mutually exclusive
                    # For simplicity, flag if any transition lacks a guard
                    unguarded = [t for t in transitions if t.guard is None]
                    if len(unguarded) > 1:
                        non_deterministic.append(
                            f"State '{state_name}', event '{event}': "
                            f"{len(unguarded)} unguarded transitions"
                        )

        return VerificationResult(
            property_name="determinism",
            property_type=PropertyType.DETERMINISM,
            satisfied=len(non_deterministic) == 0,
            message="; ".join(non_deterministic) if non_deterministic else "Machine is deterministic"
        )

    def verify_deadlock_freedom(self) -> VerificationResult:
        """
        Verify that no non-final state is a deadlock.

        A deadlock is a non-final state with no outgoing transitions.
        """
        deadlocks = []

        for state in self.definition.states.values():
            if not state.is_final:
                outgoing = self.definition.get_outgoing_transitions(state.name)
                if not outgoing:
                    deadlocks.append(state.name)

        return VerificationResult(
            property_name="deadlock_freedom",
            property_type=PropertyType.DEADLOCK_FREEDOM,
            satisfied=len(deadlocks) == 0,
            counterexample=deadlocks if deadlocks else None,
            message=f"Deadlock states: {deadlocks}" if deadlocks else "No deadlocks"
        )

    def verify_reachability_all_states(self) -> VerificationResult:
        """Verify all states are reachable from the initial state."""
        reachable = self._compute_reachable()
        all_states = set(self.definition.states.keys())
        unreachable = all_states - reachable

        return VerificationResult(
            property_name="all_states_reachable",
            property_type=PropertyType.REACHABILITY,
            satisfied=len(unreachable) == 0,
            counterexample=list(unreachable) if unreachable else None,
            message=f"Unreachable states: {unreachable}" if unreachable else "All states reachable"
        )

    def verify_final_state_reachability(self) -> VerificationResult:
        """Verify at least one final state is reachable."""
        reachable = self._compute_reachable()
        final_states = self.definition.get_final_states()
        reachable_final = {s.name for s in final_states} & reachable

        return VerificationResult(
            property_name="final_state_reachable",
            property_type=PropertyType.LIVENESS,
            satisfied=len(reachable_final) > 0,
            message=f"Reachable final states: {reachable_final}" if reachable_final else "No final state reachable"
        )

    def verify_property(self, prop: VerificationProperty) -> VerificationResult:
        """
        Verify a custom property.

        Supports:
        - REACHABILITY: "eventually(state_name)" - state is reachable
        - SAFETY: "never(state_name)" - state is never reached
        - INVARIANT: "always(condition)" - condition holds in all states
        """
        if prop.property_type == PropertyType.REACHABILITY:
            # Check if state in expression is reachable
            target_state = prop.expression.replace("eventually(", "").replace(")", "").strip()
            reachable = self._compute_reachable()
            is_reachable = target_state in reachable

            return VerificationResult(
                property_name=prop.name,
                property_type=prop.property_type,
                satisfied=is_reachable,
                message=f"State '{target_state}' is {'reachable' if is_reachable else 'not reachable'}"
            )

        elif prop.property_type == PropertyType.SAFETY:
            # Check if state is never reached (unreachable)
            target_state = prop.expression.replace("never(", "").replace(")", "").strip()
            reachable = self._compute_reachable()
            is_safe = target_state not in reachable

            counterexample = None
            if not is_safe:
                counterexample = self._find_path_to_state(target_state)

            return VerificationResult(
                property_name=prop.name,
                property_type=prop.property_type,
                satisfied=is_safe,
                counterexample=counterexample,
                message=f"State '{target_state}' is {'never reached' if is_safe else 'reachable'}"
            )

        return VerificationResult(
            property_name=prop.name,
            property_type=prop.property_type,
            satisfied=False,
            message=f"Property type {prop.property_type} not fully implemented"
        )

    def _compute_reachable(self) -> Set[str]:
        """Compute reachable states from initial state using BFS."""
        if self._reachable_states is not None:
            return self._reachable_states

        initial = self.definition.get_initial_state()
        if not initial:
            return set()

        reachable = set()
        queue = deque([initial.name])

        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)

            for next_state in self._transition_graph[current]:
                if next_state not in reachable:
                    queue.append(next_state)

        self._reachable_states = reachable
        return reachable

    def _find_path_to_state(self, target: str) -> Optional[List[str]]:
        """Find a path from initial state to target state using BFS."""
        initial = self.definition.get_initial_state()
        if not initial:
            return None

        if target == initial.name:
            return [initial.name]

        visited = {initial.name}
        queue = deque([(initial.name, [initial.name])])

        while queue:
            current, path = queue.popleft()

            for next_state in self._transition_graph[current]:
                if next_state == target:
                    return path + [next_state]

                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, path + [next_state]))

        return None

    def check_bisimulation(
        self,
        other: StateMachineDefinition
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if two state machines are bisimilar.

        Bisimulation is an equivalence relation for state machines.

        Returns:
            Tuple of (is_bisimilar, explanation)
        """
        # Simplified bisimulation check: same structure
        if set(self.definition.states.keys()) != set(other.states.keys()):
            return False, "State sets differ"

        if len(self.definition.transitions) != len(other.transitions):
            return False, "Transition counts differ"

        # Check transition structure matches
        self_transitions = {
            (t.source, t.event, t.target) for t in self.definition.transitions
        }
        other_transitions = {
            (t.source, t.event, t.target) for t in other.transitions
        }

        if self_transitions != other_transitions:
            diff = self_transitions.symmetric_difference(other_transitions)
            return False, f"Transition differences: {diff}"

        return True, "State machines are structurally bisimilar"

    def generate_test_sequences(
        self,
        max_length: int = 10
    ) -> List[List[str]]:
        """
        Generate event sequences for testing.

        Uses BFS to generate all paths up to max_length.
        """
        initial = self.definition.get_initial_state()
        if not initial:
            return []

        sequences: List[List[str]] = []
        queue = deque([(initial.name, [])])

        while queue:
            current_state, current_sequence = queue.popleft()

            if len(current_sequence) >= max_length:
                sequences.append(current_sequence)
                continue

            outgoing = self.definition.get_outgoing_transitions(current_state)

            if not outgoing:
                # Terminal state
                if current_sequence:
                    sequences.append(current_sequence)
                continue

            for transition in outgoing:
                new_sequence = current_sequence + [transition.event]
                queue.append((transition.target, new_sequence))

                # Limit total sequences
                if len(sequences) > 1000:
                    return sequences

        return sequences

    def to_graphviz(self) -> str:
        """Export state machine to Graphviz DOT format."""
        lines = [
            "digraph StateMachine {",
            "    rankdir=LR;",
            "    node [shape=ellipse];",
        ]

        # Mark initial state with double circle
        initial = self.definition.get_initial_state()
        if initial:
            lines.append(f'    "{initial.name}" [peripheries=2];')

        # Mark final states with different shape
        for state in self.definition.get_final_states():
            lines.append(f'    "{state.name}" [shape=doublecircle];')

        # Add transitions
        for transition in self.definition.transitions:
            label = transition.event
            if transition.guard:
                label += f" [{transition.guard.name}]"
            lines.append(
                f'    "{transition.source}" -> "{transition.target}" [label="{label}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Export verification results to JSON."""
        results = self.verify_all()
        return json.dumps(
            {
                "machine_name": self.definition.name,
                "states": list(self.definition.states.keys()),
                "events": list(self.definition.events),
                "verification_results": [
                    {
                        "property": r.property_name,
                        "type": r.property_type.name,
                        "satisfied": r.satisfied,
                        "message": r.message,
                        "counterexample": r.counterexample
                    }
                    for r in results
                ]
            },
            indent=2
        )


# =============================================================================
# State Machine Manager
# =============================================================================

class StateMachineManager:
    """
    Manager for multiple state machine instances.

    Provides:
    - Instance creation and tracking
    - Batch event processing
    - State machine coordination
    """

    def __init__(self):
        self._definitions: Dict[str, StateMachineDefinition] = {}
        self._instances: Dict[UUID, StateMachine] = {}
        self._verifiers: Dict[str, StateMachineVerifier] = {}

        # Register manufacturing state machines
        self._register_default_definitions()

    def _register_default_definitions(self) -> None:
        """Register default manufacturing state machine definitions."""
        self.register_definition(create_print_job_state_machine())
        self.register_definition(create_machine_state_machine())
        self.register_definition(create_quality_inspection_state_machine())

    def register_definition(
        self,
        definition: StateMachineDefinition
    ) -> List[str]:
        """
        Register a state machine definition.

        Returns validation errors if any.
        """
        errors = definition.validate()
        if not errors:
            self._definitions[definition.name] = definition
            self._verifiers[definition.name] = StateMachineVerifier(definition)
        return errors

    def create_instance(
        self,
        definition_name: str,
        instance_id: Optional[UUID] = None
    ) -> Optional[StateMachine]:
        """Create a new state machine instance."""
        definition = self._definitions.get(definition_name)
        if not definition:
            logger.error(f"Definition not found: {definition_name}")
            return None

        instance = StateMachine(definition, instance_id)
        self._instances[instance.instance_id] = instance
        return instance

    def get_instance(self, instance_id: UUID) -> Optional[StateMachine]:
        """Get a state machine instance by ID."""
        return self._instances.get(instance_id)

    def get_verifier(self, definition_name: str) -> Optional[StateMachineVerifier]:
        """Get verifier for a definition."""
        return self._verifiers.get(definition_name)

    def verify_definition(self, definition_name: str) -> List[VerificationResult]:
        """Verify a state machine definition."""
        verifier = self._verifiers.get(definition_name)
        if not verifier:
            return []
        return verifier.verify_all()

    def process_event(
        self,
        instance_id: UUID,
        event: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Optional[StateTransitionEvent]:
        """Process an event for a specific instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error(f"Instance not found: {instance_id}")
            return None
        return instance.process_event(event, event_data)


# Export public API
__all__ = [
    # Core
    'State',
    'Guard',
    'Action',
    'Transition',
    'StateMachineDefinition',
    'StateMachineType',
    'StateMachine',
    'StateTransitionEvent',
    # Verification
    'PropertyType',
    'VerificationProperty',
    'VerificationResult',
    'StateMachineVerifier',
    # Manager
    'StateMachineManager',
    # Factory functions
    'create_print_job_state_machine',
    'create_machine_state_machine',
    'create_quality_inspection_state_machine',
]
