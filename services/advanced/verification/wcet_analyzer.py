"""
Worst-Case Execution Time (WCET) Analyzer

Provides WCET analysis for safety-critical code paths.
Essential for IEC 61508 SIL 2+ timing verification.

Supports:
- Static WCET estimation
- Dynamic timing measurement
- Statistical analysis (MBTA)
- RapiTime/aiT integration stubs

Reference: IEC 61508-3, WCET analysis best practices

Author: LEGO MCP Safety Engineering
"""

import logging
import time
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from functools import wraps
from enum import Enum, auto
import threading

logger = logging.getLogger(__name__)


class WCETConfidence(Enum):
    """Confidence level of WCET estimate."""
    LOW = 1          # < 90% confidence
    MEDIUM = 2       # 90-99% confidence
    HIGH = 3         # > 99% confidence
    VERIFIED = 4     # Formally verified


class TimingMethod(Enum):
    """WCET analysis method."""
    STATIC = "static"           # Static analysis
    DYNAMIC = "dynamic"         # Measurement-based
    HYBRID = "hybrid"           # Combined approach
    FORMAL = "formal"           # Formal verification


@dataclass
class TimingMeasurement:
    """Single timing measurement."""
    function_name: str
    execution_time_us: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WCETEstimate:
    """WCET estimate for a code path."""
    function_name: str
    wcet_us: float                              # Worst-case in microseconds
    bcet_us: float                              # Best-case
    avg_us: float                               # Average
    std_dev_us: float                           # Standard deviation
    sample_count: int
    confidence: WCETConfidence
    method: TimingMethod
    deadline_us: Optional[float] = None         # Required deadline
    margin_percent: float = 0.0                 # Safety margin
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def meets_deadline(self) -> bool:
        """Check if WCET meets deadline."""
        if self.deadline_us is None:
            return True
        return self.wcet_us <= self.deadline_us

    @property
    def utilization(self) -> Optional[float]:
        """Calculate deadline utilization."""
        if self.deadline_us is None or self.deadline_us == 0:
            return None
        return (self.wcet_us / self.deadline_us) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "wcet_us": self.wcet_us,
            "bcet_us": self.bcet_us,
            "avg_us": self.avg_us,
            "std_dev_us": self.std_dev_us,
            "sample_count": self.sample_count,
            "confidence": self.confidence.name,
            "method": self.method.value,
            "deadline_us": self.deadline_us,
            "margin_percent": self.margin_percent,
            "meets_deadline": self.meets_deadline,
            "utilization": self.utilization,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WCETReport:
    """Complete WCET analysis report."""
    estimates: List[WCETEstimate] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_duration_ms: float = 0.0

    @property
    def all_meet_deadlines(self) -> bool:
        """Check if all estimates meet their deadlines."""
        return all(e.meets_deadline for e in self.estimates if e.deadline_us)

    @property
    def critical_paths(self) -> List[WCETEstimate]:
        """Get estimates that don't meet deadlines."""
        return [e for e in self.estimates if not e.meets_deadline]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimates": [e.to_dict() for e in self.estimates],
            "all_meet_deadlines": self.all_meet_deadlines,
            "critical_paths": [e.to_dict() for e in self.critical_paths],
            "timestamp": self.timestamp.isoformat(),
            "analysis_duration_ms": self.analysis_duration_ms,
        }


class WCETAnalyzer:
    """
    Worst-Case Execution Time Analyzer.

    Provides both measurement-based and static analysis capabilities
    for timing verification of safety-critical code.

    Usage:
        analyzer = WCETAnalyzer()

        # Register function with deadline
        analyzer.register("safety_check", deadline_us=10000)

        # Measure execution
        with analyzer.measure("safety_check"):
            result = safety_check()

        # Or use decorator
        @analyzer.timed("control_loop", deadline_us=1000)
        def control_loop():
            ...

        # Get WCET estimate
        estimate = analyzer.get_estimate("safety_check")
        print(f"WCET: {estimate.wcet_us}us")
    """

    # Safety margin for WCET (percentage above measured max)
    DEFAULT_SAFETY_MARGIN = 20.0

    # Minimum samples for confident estimate
    MIN_SAMPLES = 100

    # High confidence sample count
    HIGH_CONFIDENCE_SAMPLES = 1000

    def __init__(self, safety_margin: float = DEFAULT_SAFETY_MARGIN):
        self.safety_margin = safety_margin
        self._measurements: Dict[str, List[TimingMeasurement]] = {}
        self._deadlines: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._static_estimates: Dict[str, float] = {}

        logger.info(f"WCET Analyzer initialized (margin={safety_margin}%)")

    def register(
        self,
        function_name: str,
        deadline_us: Optional[float] = None,
        static_wcet_us: Optional[float] = None,
    ) -> None:
        """Register a function for WCET analysis."""
        with self._lock:
            if function_name not in self._measurements:
                self._measurements[function_name] = []

            if deadline_us is not None:
                self._deadlines[function_name] = deadline_us

            if static_wcet_us is not None:
                self._static_estimates[function_name] = static_wcet_us

        logger.debug(f"Registered WCET tracking for: {function_name}")

    def measure(self, function_name: str, context: Optional[Dict] = None):
        """Context manager for timing measurement."""
        return _TimingContext(self, function_name, context or {})

    def timed(
        self,
        function_name: Optional[str] = None,
        deadline_us: Optional[float] = None,
    ):
        """Decorator for automatic timing measurement."""
        def decorator(func: Callable) -> Callable:
            name = function_name or func.__name__

            # Register the function
            self.register(name, deadline_us)

            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.measure(name):
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def record_measurement(
        self,
        function_name: str,
        execution_time_us: float,
        context: Dict[str, Any],
    ) -> None:
        """Record a timing measurement."""
        measurement = TimingMeasurement(
            function_name=function_name,
            execution_time_us=execution_time_us,
            timestamp=datetime.now(timezone.utc),
            context=context,
        )

        with self._lock:
            if function_name not in self._measurements:
                self._measurements[function_name] = []

            self._measurements[function_name].append(measurement)

            # Check for deadline violation
            deadline = self._deadlines.get(function_name)
            if deadline and execution_time_us > deadline:
                logger.warning(
                    f"WCET: {function_name} exceeded deadline! "
                    f"{execution_time_us:.1f}us > {deadline:.1f}us"
                )

    def get_estimate(
        self,
        function_name: str,
        method: TimingMethod = TimingMethod.DYNAMIC,
    ) -> Optional[WCETEstimate]:
        """Get WCET estimate for a function."""
        with self._lock:
            measurements = self._measurements.get(function_name, [])

        if not measurements:
            # Check for static estimate
            if function_name in self._static_estimates:
                return WCETEstimate(
                    function_name=function_name,
                    wcet_us=self._static_estimates[function_name],
                    bcet_us=0,
                    avg_us=0,
                    std_dev_us=0,
                    sample_count=0,
                    confidence=WCETConfidence.LOW,
                    method=TimingMethod.STATIC,
                    deadline_us=self._deadlines.get(function_name),
                )
            return None

        times = [m.execution_time_us for m in measurements]

        # Calculate statistics
        min_time = min(times)
        max_time = max(times)
        avg_time = statistics.mean(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0

        # Apply safety margin
        wcet = max_time * (1 + self.safety_margin / 100)

        # Determine confidence
        sample_count = len(times)
        if sample_count >= self.HIGH_CONFIDENCE_SAMPLES:
            confidence = WCETConfidence.HIGH
        elif sample_count >= self.MIN_SAMPLES:
            confidence = WCETConfidence.MEDIUM
        else:
            confidence = WCETConfidence.LOW

        return WCETEstimate(
            function_name=function_name,
            wcet_us=wcet,
            bcet_us=min_time,
            avg_us=avg_time,
            std_dev_us=std_dev,
            sample_count=sample_count,
            confidence=confidence,
            method=method,
            deadline_us=self._deadlines.get(function_name),
            margin_percent=self.safety_margin,
        )

    def get_all_estimates(self) -> List[WCETEstimate]:
        """Get estimates for all tracked functions."""
        estimates = []
        with self._lock:
            function_names = list(self._measurements.keys())

        for name in function_names:
            estimate = self.get_estimate(name)
            if estimate:
                estimates.append(estimate)

        return estimates

    def generate_report(self) -> WCETReport:
        """Generate comprehensive WCET report."""
        start = time.perf_counter()

        report = WCETReport()
        report.estimates = self.get_all_estimates()
        report.analysis_duration_ms = (time.perf_counter() - start) * 1000

        return report

    def clear_measurements(self, function_name: Optional[str] = None) -> None:
        """Clear stored measurements."""
        with self._lock:
            if function_name:
                self._measurements[function_name] = []
            else:
                self._measurements.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        with self._lock:
            total_measurements = sum(
                len(m) for m in self._measurements.values()
            )

        return {
            "tracked_functions": len(self._measurements),
            "total_measurements": total_measurements,
            "functions_with_deadlines": len(self._deadlines),
            "static_estimates": len(self._static_estimates),
            "safety_margin_percent": self.safety_margin,
        }


class _TimingContext:
    """Context manager for timing measurements."""

    def __init__(
        self,
        analyzer: WCETAnalyzer,
        function_name: str,
        context: Dict[str, Any],
    ):
        self.analyzer = analyzer
        self.function_name = function_name
        self.context = context
        self.start_time: float = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        execution_time_us = (end_time - self.start_time) * 1_000_000

        self.analyzer.record_measurement(
            self.function_name,
            execution_time_us,
            self.context,
        )

        return False  # Don't suppress exceptions


# Integration stubs for commercial tools

class RapiTimeIntegration:
    """
    Integration stub for RapiTime WCET analyzer.

    RapiTime by Rapita Systems provides:
    - Measurement-based timing analysis
    - Structural coverage
    - DO-178C/IEC 61508 certification support

    Note: Requires RapiTime license for actual use.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        logger.info("RapiTime integration initialized (stub)")

    def analyze(self, executable: str) -> Dict[str, float]:
        """Run RapiTime analysis (stub)."""
        logger.warning("RapiTime analysis is a stub - requires actual RapiTime installation")
        return {}

    def generate_report(self, output_path: str) -> str:
        """Generate RapiTime report (stub)."""
        return output_path


class AiTIntegration:
    """
    Integration stub for AbsInt aiT WCET analyzer.

    aiT by AbsInt provides:
    - Static WCET analysis
    - Value analysis
    - Cache/pipeline analysis
    - IEC 61508 certification support

    Note: Requires aiT license for actual use.
    """

    def __init__(self, target_architecture: str = "arm"):
        self.target_architecture = target_architecture
        logger.info(f"aiT integration initialized for {target_architecture} (stub)")

    def analyze(self, executable: str, entry_point: str) -> Dict[str, float]:
        """Run aiT analysis (stub)."""
        logger.warning("aiT analysis is a stub - requires actual aiT installation")
        return {}


# Factory function
def create_wcet_analyzer(
    safety_margin: float = 20.0,
    safety_functions: Optional[Dict[str, float]] = None,
) -> WCETAnalyzer:
    """
    Create and configure a WCET analyzer for LEGO MCP.

    Args:
        safety_margin: Percentage margin above measured max
        safety_functions: Dict of function names to deadline (us)

    Returns:
        Configured WCETAnalyzer
    """
    analyzer = WCETAnalyzer(safety_margin=safety_margin)

    # Register default safety-critical functions
    default_deadlines = {
        "estop_handler": 10_000,         # 10ms E-stop response
        "safety_check": 1_000,           # 1ms safety check
        "heartbeat_handler": 100_000,    # 100ms heartbeat
        "relay_control": 5_000,          # 5ms relay control
        "watchdog_kick": 1_000,          # 1ms watchdog
    }

    if safety_functions:
        default_deadlines.update(safety_functions)

    for func_name, deadline in default_deadlines.items():
        analyzer.register(func_name, deadline_us=deadline)

    return analyzer


__all__ = [
    "WCETAnalyzer",
    "WCETEstimate",
    "WCETReport",
    "WCETConfidence",
    "TimingMethod",
    "TimingMeasurement",
    "RapiTimeIntegration",
    "AiTIntegration",
    "create_wcet_analyzer",
]
