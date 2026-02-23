"""
Runtime Safety Monitors Package

This package contains runtime monitors generated from TLA+ specifications
and formal verification properties.

Monitors provide real-time validation of safety invariants during system
operation, complementing static model checking with dynamic verification.
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
import logging
import functools

logger = logging.getLogger(__name__)


class MonitorStatus(Enum):
    """Status of a runtime monitor check."""
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    ERROR = "error"
    SKIPPED = "skipped"


class MonitorSeverity(Enum):
    """Severity level of a monitor violation."""
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
    SAFETY_CRITICAL = 5  # IEC 61508 SIL-relevant


@dataclass
class MonitorResult:
    """Result of a single monitor check."""
    monitor_name: str
    property_name: str
    status: MonitorStatus
    severity: MonitorSeverity = MonitorSeverity.ERROR
    message: str = ""
    state_snapshot: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_us: float = 0.0  # Microseconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monitor_name": self.monitor_name,
            "property_name": self.property_name,
            "status": self.status.value,
            "severity": self.severity.name,
            "message": self.message,
            "state_snapshot": self.state_snapshot,
            "timestamp": self.timestamp.isoformat(),
            "duration_us": self.duration_us,
        }


@dataclass
class MonitorReport:
    """Aggregated report from multiple monitor checks."""
    checks_total: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_error: int = 0
    results: List[MonitorResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def all_passed(self) -> bool:
        return self.checks_failed == 0 and self.checks_error == 0

    @property
    def has_safety_critical_failure(self) -> bool:
        return any(
            r.status == MonitorStatus.VIOLATED and
            r.severity == MonitorSeverity.SAFETY_CRITICAL
            for r in self.results
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_error": self.checks_error,
            "all_passed": self.all_passed,
            "has_safety_critical_failure": self.has_safety_critical_failure,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp.isoformat(),
        }


def invariant(
    name: str,
    severity: MonitorSeverity = MonitorSeverity.ERROR,
    description: str = ""
):
    """
    Decorator for marking a method as a runtime invariant check.

    Usage:
        @invariant("TypeInvariant", severity=MonitorSeverity.SAFETY_CRITICAL)
        def check_type_invariant(self, state: Dict) -> bool:
            return state["relay"] in ["OPEN", "CLOSED"]
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Store metadata on the function
        wrapper._is_invariant = True
        wrapper._invariant_name = name
        wrapper._invariant_severity = severity
        wrapper._invariant_description = description
        return wrapper
    return decorator


def safety_property(
    name: str,
    severity: MonitorSeverity = MonitorSeverity.SAFETY_CRITICAL,
    sil_level: int = 2
):
    """
    Decorator for marking a method as a SIL-rated safety property.

    These properties correspond to IEC 61508 safety requirements.

    Usage:
        @safety_property("P1_EstopImpliesRelaysOpen", sil_level=2)
        def check_estop_relays(self, state: Dict) -> bool:
            if state["safety_state"] == "ESTOP_ACTIVE":
                return state["primary_relay"] == "OPEN"
            return True
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._is_safety_property = True
        wrapper._property_name = name
        wrapper._property_severity = severity
        wrapper._sil_level = sil_level
        return wrapper
    return decorator


class BaseMonitor:
    """
    Base class for runtime safety monitors.

    Monitors check safety invariants at runtime, providing dynamic
    verification complementary to static model checking.

    Subclasses should define invariant methods decorated with @invariant
    or @safety_property decorators.
    """

    def __init__(self, name: str = "BaseMonitor"):
        self.name = name
        self._invariants: Dict[str, Callable] = {}
        self._safety_properties: Dict[str, Callable] = {}
        self._check_count = 0
        self._violation_count = 0
        self._last_report: Optional[MonitorReport] = None

        # Auto-discover decorated methods
        self._discover_checks()

    def _discover_checks(self):
        """Discover all invariant and safety property methods."""
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if callable(attr):
                if getattr(attr, '_is_invariant', False):
                    self._invariants[attr._invariant_name] = attr
                elif getattr(attr, '_is_safety_property', False):
                    self._safety_properties[attr._property_name] = attr

    def check_all(self, state: Dict[str, Any]) -> MonitorReport:
        """
        Run all invariants and safety properties against given state.

        Args:
            state: Current system state as dictionary

        Returns:
            MonitorReport with all check results
        """
        import time
        report = MonitorReport()

        # Check invariants
        for name, check_fn in self._invariants.items():
            start = time.perf_counter()
            try:
                result = check_fn(state)
                duration_us = (time.perf_counter() - start) * 1_000_000

                status = MonitorStatus.SATISFIED if result else MonitorStatus.VIOLATED
                severity = getattr(check_fn, '_invariant_severity', MonitorSeverity.ERROR)

                report.results.append(MonitorResult(
                    monitor_name=self.name,
                    property_name=name,
                    status=status,
                    severity=severity,
                    message="" if result else f"Invariant {name} violated",
                    state_snapshot=state.copy() if not result else None,
                    duration_us=duration_us,
                ))

                report.checks_total += 1
                if result:
                    report.checks_passed += 1
                else:
                    report.checks_failed += 1
                    self._violation_count += 1
                    logger.warning(f"Monitor {self.name}: Invariant {name} VIOLATED")

            except Exception as e:
                duration_us = (time.perf_counter() - start) * 1_000_000
                report.results.append(MonitorResult(
                    monitor_name=self.name,
                    property_name=name,
                    status=MonitorStatus.ERROR,
                    severity=MonitorSeverity.ERROR,
                    message=str(e),
                    duration_us=duration_us,
                ))
                report.checks_total += 1
                report.checks_error += 1
                logger.error(f"Monitor {self.name}: Invariant {name} ERROR: {e}")

        # Check safety properties
        for name, check_fn in self._safety_properties.items():
            start = time.perf_counter()
            try:
                result = check_fn(state)
                duration_us = (time.perf_counter() - start) * 1_000_000

                status = MonitorStatus.SATISFIED if result else MonitorStatus.VIOLATED
                severity = getattr(check_fn, '_property_severity', MonitorSeverity.SAFETY_CRITICAL)

                report.results.append(MonitorResult(
                    monitor_name=self.name,
                    property_name=name,
                    status=status,
                    severity=severity,
                    message="" if result else f"Safety property {name} violated",
                    state_snapshot=state.copy() if not result else None,
                    duration_us=duration_us,
                ))

                report.checks_total += 1
                if result:
                    report.checks_passed += 1
                else:
                    report.checks_failed += 1
                    self._violation_count += 1
                    logger.critical(f"Monitor {self.name}: Safety property {name} VIOLATED")

            except Exception as e:
                duration_us = (time.perf_counter() - start) * 1_000_000
                report.results.append(MonitorResult(
                    monitor_name=self.name,
                    property_name=name,
                    status=MonitorStatus.ERROR,
                    severity=MonitorSeverity.SAFETY_CRITICAL,
                    message=str(e),
                    duration_us=duration_us,
                ))
                report.checks_total += 1
                report.checks_error += 1
                logger.error(f"Monitor {self.name}: Safety property {name} ERROR: {e}")

        self._check_count += 1
        self._last_report = report
        return report

    def check_invariant(self, name: str, state: Dict[str, Any]) -> MonitorResult:
        """Check a single invariant by name."""
        if name not in self._invariants:
            return MonitorResult(
                monitor_name=self.name,
                property_name=name,
                status=MonitorStatus.ERROR,
                message=f"Unknown invariant: {name}",
            )

        import time
        start = time.perf_counter()
        check_fn = self._invariants[name]

        try:
            result = check_fn(state)
            duration_us = (time.perf_counter() - start) * 1_000_000
            return MonitorResult(
                monitor_name=self.name,
                property_name=name,
                status=MonitorStatus.SATISFIED if result else MonitorStatus.VIOLATED,
                severity=getattr(check_fn, '_invariant_severity', MonitorSeverity.ERROR),
                message="" if result else f"Invariant {name} violated",
                state_snapshot=state.copy() if not result else None,
                duration_us=duration_us,
            )
        except Exception as e:
            duration_us = (time.perf_counter() - start) * 1_000_000
            return MonitorResult(
                monitor_name=self.name,
                property_name=name,
                status=MonitorStatus.ERROR,
                message=str(e),
                duration_us=duration_us,
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            "name": self.name,
            "invariant_count": len(self._invariants),
            "safety_property_count": len(self._safety_properties),
            "total_checks": self._check_count,
            "total_violations": self._violation_count,
            "invariant_names": list(self._invariants.keys()),
            "safety_property_names": list(self._safety_properties.keys()),
        }


__all__ = [
    "MonitorStatus",
    "MonitorSeverity",
    "MonitorResult",
    "MonitorReport",
    "BaseMonitor",
    "invariant",
    "safety_property",
]
