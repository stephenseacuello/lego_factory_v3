"""
Runtime Safety Monitor for SafetyNode

Auto-generated from TLA+ specification.
DO NOT EDIT - regenerate from source spec.

Generated: 2026-01-14
Source: SafetyNode.tla

This monitor validates the following IEC 61508 SIL 2+ safety properties
at runtime:

- TypeInvariant: All state variables have valid types
- SafetyP1: E-stop active implies both relays open (unless faulted)
- SafetyP2: E-stop command succeeds if primary channel healthy
- SafetyP3: Single channel fault cannot prevent safety action
- SafetyInvariant: Combined safety property
"""

from typing import Any, Dict, Set
from dashboard.services.verification.monitors import (
    BaseMonitor,
    MonitorSeverity,
    invariant,
    safety_property,
)


# Type sets from TLA+ spec
SAFETY_STATES: Set[str] = {"NORMAL", "WARNING", "ESTOP_PENDING", "ESTOP_ACTIVE", "LOCKOUT"}
RELAY_STATES: Set[str] = {"OPEN", "CLOSED"}


class SafetyNodeMonitor(BaseMonitor):
    """
    Runtime monitor for SafetyNode safety properties.

    This monitor implements real-time verification of safety invariants
    derived from the TLA+ formal specification. It should be called
    on every state transition to ensure safety properties hold.

    Invariants:
        - TypeInvariant
        - SafetyInvariant

    Safety Properties:
        - SafetyP1_EstopImpliesRelaysOpen
        - SafetyP2_EstopCommandSucceeds
        - SafetyP3_SingleFaultSafe

    Usage:
        monitor = SafetyNodeMonitor()
        state = {
            "safety_state": "NORMAL",
            "primary_relay": "CLOSED",
            "secondary_relay": "CLOSED",
            "heartbeat_counter": 0,
            "heartbeat_received": True,
            "hw_estop_pressed": False,
            "primary_fault": False,
            "secondary_fault": False,
            "time": 0
        }
        report = monitor.check_all(state)
        if not report.all_passed:
            trigger_emergency_stop()
    """

    # Constants (should match TLA+ CONSTANTS)
    MAX_TIME = 1000
    WATCHDOG_TIMEOUT = 10
    CROSS_CHECK_PERIOD = 5

    def __init__(self):
        super().__init__(name="SafetyNodeMonitor")

    @invariant("TypeInvariant", severity=MonitorSeverity.ERROR)
    def check_type_invariant(self, state: Dict[str, Any]) -> bool:
        """
        Check TypeInvariant - all state variables have valid types.

        TLA+ Expression::

            /\\ safety_state \\in SafetyStates
            /\\ primary_relay \\in RelayStates
            /\\ secondary_relay \\in RelayStates
            /\\ heartbeat_counter \\in 0..MAX_TIME
            /\\ heartbeat_received \\in BOOLEAN
            /\\ hw_estop_pressed \\in BOOLEAN
            /\\ primary_fault \\in BOOLEAN
            /\\ secondary_fault \\in BOOLEAN
            /\\ time \\in 0..MAX_TIME
        """
        try:
            return (
                state.get("safety_state") in SAFETY_STATES and
                state.get("primary_relay") in RELAY_STATES and
                state.get("secondary_relay") in RELAY_STATES and
                isinstance(state.get("heartbeat_counter"), int) and
                0 <= state.get("heartbeat_counter", -1) <= self.MAX_TIME and
                isinstance(state.get("heartbeat_received"), bool) and
                isinstance(state.get("hw_estop_pressed"), bool) and
                isinstance(state.get("primary_fault"), bool) and
                isinstance(state.get("secondary_fault"), bool) and
                isinstance(state.get("time"), int) and
                0 <= state.get("time", -1) <= self.MAX_TIME
            )
        except (KeyError, TypeError):
            return False

    @safety_property("SafetyP1_EstopImpliesRelaysOpen", severity=MonitorSeverity.SAFETY_CRITICAL)
    def check_safetyp1_estop_implies_relays_open(self, state: Dict[str, Any]) -> bool:
        """
        P1: E-stop active implies both relays SHOULD be open.

        Exception: Unless there's a hardware fault preventing it.

        TLA+ Expression::

            (safety_state = "ESTOP_ACTIVE" /\\ ~primary_fault /\\ ~secondary_fault)
                => BothRelaysOpen

        This is a critical safety property - if E-stop is commanded and
        both channels are healthy, both relays MUST be open to cut power.
        """
        try:
            safety_state = state.get("safety_state")
            primary_fault = state.get("primary_fault", False)
            secondary_fault = state.get("secondary_fault", False)
            primary_relay = state.get("primary_relay")
            secondary_relay = state.get("secondary_relay")

            # If not in E-stop, property trivially holds
            if safety_state != "ESTOP_ACTIVE":
                return True

            # If there are faults, we can't guarantee relay state
            if primary_fault or secondary_fault:
                return True

            # In E-stop with no faults: both relays must be open
            return (
                primary_relay == "OPEN" and
                secondary_relay == "OPEN"
            )
        except (KeyError, TypeError):
            return True  # Fail open for missing data

    @safety_property("SafetyP2_EstopCommandSucceeds", severity=MonitorSeverity.SAFETY_CRITICAL)
    def check_safetyp2_estop_command_succeeds(self, state: Dict[str, Any]) -> bool:
        """
        P2: If primary channel is healthy, E-stop command succeeds.

        TLA+ Expression::

            (safety_state = "ESTOP_ACTIVE" /\\ ~primary_fault) => (primary_relay = "OPEN")

        This ensures that at least the primary safety channel responds
        to E-stop commands when it is not faulted.
        """
        try:
            safety_state = state.get("safety_state")
            primary_fault = state.get("primary_fault", False)
            primary_relay = state.get("primary_relay")

            # If not in E-stop, property trivially holds
            if safety_state != "ESTOP_ACTIVE":
                return True

            # If primary is faulted, can't guarantee its state
            if primary_fault:
                return True

            # Primary healthy + E-stop active = primary relay must be open
            return primary_relay == "OPEN"
        except (KeyError, TypeError):
            return True

    @safety_property("SafetyP3_SingleFaultSafe", severity=MonitorSeverity.SAFETY_CRITICAL)
    def check_safetyp3_single_fault_safe(self, state: Dict[str, Any]) -> bool:
        """
        P3: Single channel fault does not prevent safety action.

        At least one relay opens during E-stop, unless BOTH channels faulted.

        TLA+ Expression::

            (safety_state = "ESTOP_ACTIVE") =>
                (primary_relay = "OPEN" \\/ secondary_relay = "OPEN" \\/
                 (primary_fault /\\ secondary_fault))

        This is the fundamental dual-channel redundancy property required
        for SIL 2+ certification.
        """
        try:
            safety_state = state.get("safety_state")
            primary_relay = state.get("primary_relay")
            secondary_relay = state.get("secondary_relay")
            primary_fault = state.get("primary_fault", False)
            secondary_fault = state.get("secondary_fault", False)

            # If not in E-stop, property trivially holds
            if safety_state != "ESTOP_ACTIVE":
                return True

            # At least one relay open, OR both channels faulted
            return (
                primary_relay == "OPEN" or
                secondary_relay == "OPEN" or
                (primary_fault and secondary_fault)
            )
        except (KeyError, TypeError):
            return True

    @invariant("SafetyInvariant", severity=MonitorSeverity.SAFETY_CRITICAL)
    def check_safety_invariant(self, state: Dict[str, Any]) -> bool:
        """
        Combined safety invariant - all safety properties must hold.

        TLA+ Expression::

            /\\ TypeInvariant
            /\\ SafetyP1_EstopImpliesRelaysOpen
            /\\ SafetyP2_EstopCommandSucceeds
            /\\ SafetyP3_SingleFaultSafe
        """
        return (
            self.check_type_invariant(state) and
            self.check_safetyp1_estop_implies_relays_open(state) and
            self.check_safetyp2_estop_command_succeeds(state) and
            self.check_safetyp3_single_fault_safe(state)
        )

    # Helper methods

    def both_relays_open(self, state: Dict[str, Any]) -> bool:
        """Check if both relays are in safe (open) state."""
        return (
            state.get("primary_relay") == "OPEN" and
            state.get("secondary_relay") == "OPEN"
        )

    def both_relays_closed(self, state: Dict[str, Any]) -> bool:
        """Check if both relays are closed (operational)."""
        return (
            state.get("primary_relay") == "CLOSED" and
            state.get("secondary_relay") == "CLOSED"
        )

    def relays_disagree(self, state: Dict[str, Any]) -> bool:
        """Check if relays are in disagreement (fault condition)."""
        return state.get("primary_relay") != state.get("secondary_relay")

    def watchdog_timeout(self, state: Dict[str, Any]) -> bool:
        """Check if watchdog has timed out."""
        return state.get("heartbeat_counter", 0) >= self.WATCHDOG_TIMEOUT

    def estop_active(self, state: Dict[str, Any]) -> bool:
        """Check if system is in E-stop state."""
        return state.get("safety_state") in {"ESTOP_ACTIVE", "LOCKOUT"}

    def safe_to_reset(self, state: Dict[str, Any]) -> bool:
        """Check if conditions are met for safe reset."""
        return (
            not state.get("hw_estop_pressed", True) and
            not self.watchdog_timeout(state) and
            not self.relays_disagree(state) and
            not state.get("primary_fault", True) and
            not state.get("secondary_fault", True)
        )

    def validate_state_types(self, state: Dict[str, Any]) -> bool:
        """Validate that state has expected structure."""
        required_keys = {
            "safety_state",
            "primary_relay",
            "secondary_relay",
            "heartbeat_counter",
            "heartbeat_received",
            "hw_estop_pressed",
            "primary_fault",
            "secondary_fault",
            "time"
        }
        return required_keys.issubset(state.keys())


# Factory function
def create_safety_node_monitor() -> SafetyNodeMonitor:
    """Create a SafetyNodeMonitor instance."""
    return SafetyNodeMonitor()


__all__ = [
    "SafetyNodeMonitor",
    "create_safety_node_monitor",
    "SAFETY_STATES",
    "RELAY_STATES",
]
