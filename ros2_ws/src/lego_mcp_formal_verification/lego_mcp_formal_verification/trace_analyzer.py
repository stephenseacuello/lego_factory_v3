"""
Trace Analyzer for Runtime Verification

Implements 3-valued LTL monitoring for finite traces.

Reference: Bauer et al., "Runtime Verification for LTL and TLTL"
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple
from collections import deque
import logging
import copy

from .property_spec import LTLFormula, LTLOperator, SafetyProperty, LivenessProperty

logger = logging.getLogger(__name__)


class Verdict(Enum):
    """Three-valued verdict for runtime monitoring."""
    TRUE = "true"           # Property definitely satisfied
    FALSE = "false"         # Property definitely violated
    INCONCLUSIVE = "?"      # Cannot determine from finite prefix


@dataclass
class TraceEvent:
    """
    Single event in an execution trace.

    Represents a state snapshot at a point in time.
    """
    event_id: str
    timestamp: datetime
    event_type: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def satisfies(self, proposition: str) -> bool:
        """Check if event satisfies atomic proposition."""
        # Format: "prop=value" or just "prop" (checks truthiness)
        if "=" in proposition:
            key, value = proposition.split("=", 1)
            return str(self.properties.get(key, "")) == value
        return bool(self.properties.get(proposition, False))


@dataclass
class MonitorState:
    """State of a property monitor."""
    property_id: str
    current_verdict: Verdict = Verdict.INCONCLUSIVE
    violation_count: int = 0
    satisfaction_count: int = 0
    last_check_time: Optional[datetime] = None
    counterexample: List[TraceEvent] = field(default_factory=list)


class LTL3Monitor:
    """
    Three-valued LTL monitor for finite traces.

    Implements the LTL3 semantics from:
    Bauer, Leucker, Schallhart: "Runtime Verification for LTL and TLTL"

    Key insight: On finite traces, some formulas are:
    - Definitely TRUE (no extension can falsify)
    - Definitely FALSE (no extension can satisfy)
    - INCONCLUSIVE (depends on future events)
    """

    def evaluate(
        self,
        formula: LTLFormula,
        trace: List[TraceEvent],
        position: int = 0
    ) -> Verdict:
        """
        Evaluate formula at given position in trace.

        Args:
            formula: LTL formula to evaluate
            trace: Execution trace (list of events)
            position: Current position in trace

        Returns:
            Three-valued verdict
        """
        if not trace:
            return Verdict.INCONCLUSIVE

        if position >= len(trace):
            return Verdict.INCONCLUSIVE

        op = formula.operator

        if op == LTLOperator.ATOM:
            # Atomic proposition
            prop = formula.operands[0]
            if trace[position].satisfies(str(prop)):
                return Verdict.TRUE
            return Verdict.FALSE

        elif op == LTLOperator.NOT:
            inner = self.evaluate(formula.operands[0], trace, position)
            if inner == Verdict.TRUE:
                return Verdict.FALSE
            elif inner == Verdict.FALSE:
                return Verdict.TRUE
            return Verdict.INCONCLUSIVE

        elif op == LTLOperator.AND:
            results = [self.evaluate(f, trace, position) for f in formula.operands]
            if Verdict.FALSE in results:
                return Verdict.FALSE
            if all(r == Verdict.TRUE for r in results):
                return Verdict.TRUE
            return Verdict.INCONCLUSIVE

        elif op == LTLOperator.OR:
            results = [self.evaluate(f, trace, position) for f in formula.operands]
            if Verdict.TRUE in results:
                return Verdict.TRUE
            if all(r == Verdict.FALSE for r in results):
                return Verdict.FALSE
            return Verdict.INCONCLUSIVE

        elif op == LTLOperator.IMPLIES:
            left = self.evaluate(formula.operands[0], trace, position)
            right = self.evaluate(formula.operands[1], trace, position)
            # p -> q ≡ !p || q
            if left == Verdict.FALSE:
                return Verdict.TRUE
            if left == Verdict.TRUE and right == Verdict.TRUE:
                return Verdict.TRUE
            if left == Verdict.TRUE and right == Verdict.FALSE:
                return Verdict.FALSE
            return Verdict.INCONCLUSIVE

        elif op == LTLOperator.NEXT:
            # X(phi): evaluate phi at next position
            if position + 1 >= len(trace):
                return Verdict.INCONCLUSIVE
            return self.evaluate(formula.operands[0], trace, position + 1)

        elif op == LTLOperator.ALWAYS:
            # G(phi): phi must hold at all positions from now
            # FALSE if phi is false at any position
            # INCONCLUSIVE otherwise (trace might extend)
            for i in range(position, len(trace)):
                result = self.evaluate(formula.operands[0], trace, i)
                if result == Verdict.FALSE:
                    return Verdict.FALSE
            return Verdict.INCONCLUSIVE  # Can't prove G on finite trace

        elif op == LTLOperator.EVENTUALLY:
            # F(phi): phi must hold at some position
            # TRUE if phi is true at any position
            # INCONCLUSIVE otherwise
            for i in range(position, len(trace)):
                result = self.evaluate(formula.operands[0], trace, i)
                if result == Verdict.TRUE:
                    return Verdict.TRUE
            return Verdict.INCONCLUSIVE

        elif op == LTLOperator.UNTIL:
            # p U q: p holds until q becomes true
            # TRUE if q is true at some position and p holds until then
            # FALSE if p becomes false before q is true
            for i in range(position, len(trace)):
                q_result = self.evaluate(formula.operands[1], trace, i)
                if q_result == Verdict.TRUE:
                    return Verdict.TRUE
                p_result = self.evaluate(formula.operands[0], trace, i)
                if p_result == Verdict.FALSE:
                    return Verdict.FALSE
            return Verdict.INCONCLUSIVE

        return Verdict.INCONCLUSIVE


class TraceAnalyzer:
    """
    Trace analyzer for runtime verification.

    Maintains a sliding window of events and monitors properties.
    """

    def __init__(
        self,
        max_trace_length: int = 10000,
        properties: Optional[List[SafetyProperty]] = None
    ):
        self.max_trace_length = max_trace_length
        self.trace: Deque[TraceEvent] = deque(maxlen=max_trace_length)
        self.properties: Dict[str, SafetyProperty] = {}
        self.monitor_states: Dict[str, MonitorState] = {}
        self.ltl3_monitor = LTL3Monitor()

        if properties:
            for prop in properties:
                self.add_property(prop)

    def add_property(self, prop: SafetyProperty) -> None:
        """Add a property to monitor."""
        self.properties[prop.id] = prop
        self.monitor_states[prop.id] = MonitorState(property_id=prop.id)

    def add_event(self, event: TraceEvent) -> List[Tuple[str, Verdict]]:
        """
        Add event to trace and check properties.

        Returns list of (property_id, verdict) for any that changed.
        """
        self.trace.append(event)

        results = []
        for prop_id, prop in self.properties.items():
            state = self.monitor_states[prop_id]
            old_verdict = state.current_verdict

            # Evaluate property on current trace
            new_verdict = self.ltl3_monitor.evaluate(
                prop.formula,
                list(self.trace),
                0
            )

            state.current_verdict = new_verdict
            state.last_check_time = event.timestamp

            if new_verdict != old_verdict:
                results.append((prop_id, new_verdict))

            if new_verdict == Verdict.FALSE:
                state.violation_count += 1
                # Store counterexample (last few events)
                state.counterexample = list(self.trace)[-10:]
                logger.error(
                    f"Property {prop_id} violated: {prop.description}"
                )

        return results

    def check_all(self) -> Dict[str, Verdict]:
        """Check all properties on current trace."""
        results = {}
        for prop_id, prop in self.properties.items():
            verdict = self.ltl3_monitor.evaluate(
                prop.formula,
                list(self.trace),
                0
            )
            results[prop_id] = verdict
            self.monitor_states[prop_id].current_verdict = verdict
        return results

    def get_violations(self) -> List[Tuple[SafetyProperty, MonitorState]]:
        """Get all currently violated properties."""
        violations = []
        for prop_id, state in self.monitor_states.items():
            if state.current_verdict == Verdict.FALSE:
                violations.append((self.properties[prop_id], state))
        return violations

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "trace_length": len(self.trace),
            "properties_monitored": len(self.properties),
            "total_violations": sum(
                s.violation_count for s in self.monitor_states.values()
            ),
            "current_violations": len(self.get_violations()),
            "verdicts": {
                pid: state.current_verdict.value
                for pid, state in self.monitor_states.items()
            }
        }

    def clear_trace(self) -> None:
        """Clear trace while keeping properties."""
        self.trace.clear()
        for state in self.monitor_states.values():
            state.current_verdict = Verdict.INCONCLUSIVE
            state.counterexample = []


class BoundedLTLMonitor:
    """
    Bounded LTL monitor with time constraints.

    For properties like "eventually within T time units".
    """

    def __init__(self, formula: LTLFormula, time_bound_ms: float):
        self.formula = formula
        self.time_bound_ms = time_bound_ms
        self.pending_obligations: List[Tuple[datetime, LTLFormula]] = []

    def add_event(self, event: TraceEvent) -> Verdict:
        """Process event and check bounded obligations."""
        current_time = event.timestamp

        # Check expired obligations
        expired_violations = []
        remaining = []

        for deadline, obligation in self.pending_obligations:
            elapsed = (current_time - deadline).total_seconds() * 1000

            if elapsed > 0:  # Past deadline
                expired_violations.append(obligation)
            else:
                remaining.append((deadline, obligation))

        self.pending_obligations = remaining

        if expired_violations:
            return Verdict.FALSE

        return Verdict.INCONCLUSIVE


class PatternMonitor:
    """
    Pattern-based monitor for common temporal patterns.

    Implements Dwyer et al. "Patterns in Property Specifications"
    """

    @staticmethod
    def absence(p: str) -> LTLFormula:
        """Pattern: P is never true (absence)."""
        return LTLFormula.always(LTLFormula.not_(LTLFormula.atom(p)))

    @staticmethod
    def existence(p: str) -> LTLFormula:
        """Pattern: P is true at least once (existence)."""
        return LTLFormula.eventually(LTLFormula.atom(p))

    @staticmethod
    def universality(p: str) -> LTLFormula:
        """Pattern: P is always true (universality)."""
        return LTLFormula.always(LTLFormula.atom(p))

    @staticmethod
    def response(p: str, q: str) -> LTLFormula:
        """Pattern: P is followed by Q (response)."""
        return LTLFormula.always(
            LTLFormula.implies(
                LTLFormula.atom(p),
                LTLFormula.eventually(LTLFormula.atom(q))
            )
        )

    @staticmethod
    def precedence(p: str, q: str) -> LTLFormula:
        """Pattern: Q is preceded by P (precedence)."""
        return LTLFormula.until(
            LTLFormula.not_(LTLFormula.atom(q)),
            LTLFormula.atom(p)
        )

    @staticmethod
    def chain_response(p: str, q: str, r: str) -> LTLFormula:
        """Pattern: P followed by Q followed by R."""
        return LTLFormula.always(
            LTLFormula.implies(
                LTLFormula.atom(p),
                LTLFormula.eventually(
                    LTLFormula.and_(
                        LTLFormula.atom(q),
                        LTLFormula.eventually(LTLFormula.atom(r))
                    )
                )
            )
        )
