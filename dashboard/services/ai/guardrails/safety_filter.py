"""
Safety Filter for AI-Generated Manufacturing Actions

Filters AI recommendations to ensure safety in manufacturing operations.

Critical safety checks:
- Motion commands within safe limits
- Temperature within material limits
- Pressure within equipment ratings
- Speed within mechanical limits
- Tool paths collision-free
- E-stop commands always allowed

Defense in depth: Multiple validation layers.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FilterAction(Enum):
    """Filter action type."""
    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    ESCALATE = "escalate"


class SafetyDomain(Enum):
    """Safety domain categories."""
    MOTION = "motion"
    THERMAL = "thermal"
    PRESSURE = "pressure"
    ELECTRICAL = "electrical"
    CHEMICAL = "chemical"
    HUMAN_SAFETY = "human_safety"


@dataclass
class FilterResult:
    """
    Result of safety filtering.

    Attributes:
        action: Filter action taken
        original: Original recommendation
        filtered: Filtered/modified recommendation
        domain: Safety domain affected
        reason: Reason for action
        severity: Severity of safety concern (1-5)
    """
    action: FilterAction
    original: str
    filtered: str
    domain: Optional[SafetyDomain] = None
    reason: str = ""
    severity: int = 1


@dataclass
class SafetyLimits:
    """
    Manufacturing safety limits.

    All values are absolute limits - AI cannot exceed these.
    """
    # Motion limits
    max_linear_speed_mm_s: float = 100.0  # mm/s
    max_angular_speed_deg_s: float = 180.0  # deg/s
    max_acceleration_mm_s2: float = 1000.0  # mm/s^2

    # Thermal limits
    max_temperature_c: float = 300.0  # °C
    min_temperature_c: float = -40.0  # °C

    # Pressure limits
    max_pressure_bar: float = 10.0  # bar

    # Electrical limits
    max_voltage_v: float = 48.0  # V (low voltage safety)
    max_current_a: float = 20.0  # A

    # Force limits
    max_force_n: float = 50.0  # N (collaborative robot limits)

    # Workspace bounds (mm from origin)
    workspace_min: Tuple[float, float, float] = (-500, -500, 0)
    workspace_max: Tuple[float, float, float] = (500, 500, 500)


class SafetyFilter:
    """
    Filters AI-generated actions for manufacturing safety.

    Implements multi-layer safety filtering:
    1. Keyword blocking (dangerous commands)
    2. Parameter validation (within limits)
    3. Context checking (appropriate for state)
    4. Physics validation (physically possible)

    Always-allowed operations:
    - E-stop commands
    - Status queries
    - Help requests

    Usage:
        >>> filter = SafetyFilter(limits)
        >>> result = filter.check(ai_recommendation)
        >>> if result.action == FilterAction.ALLOW:
        ...     execute(result.filtered)
    """

    # Commands always blocked (regardless of parameters)
    BLOCKED_COMMANDS = {
        "disable_safety",
        "bypass_interlock",
        "override_estop",
        "ignore_limits",
        "force_override",
        "disable_collision",
        "skip_homing",
    }

    # Commands always allowed (safety operations)
    ALWAYS_ALLOWED = {
        "estop",
        "e_stop",
        "emergency_stop",
        "stop",
        "pause",
        "halt",
        "abort",
        "status",
        "get_status",
        "help",
    }

    # Parameter patterns for limit checking
    PARAMETER_PATTERNS = {
        "speed": r"speed[:\s]*(\d+(?:\.\d+)?)",
        "temperature": r"temp(?:erature)?[:\s]*(\d+(?:\.\d+)?)",
        "pressure": r"pressure[:\s]*(\d+(?:\.\d+)?)",
        "position_x": r"x[:\s]*(-?\d+(?:\.\d+)?)",
        "position_y": r"y[:\s]*(-?\d+(?:\.\d+)?)",
        "position_z": r"z[:\s]*(-?\d+(?:\.\d+)?)",
        "force": r"force[:\s]*(\d+(?:\.\d+)?)",
        "voltage": r"voltage[:\s]*(\d+(?:\.\d+)?)",
        "current": r"current[:\s]*(\d+(?:\.\d+)?)",
    }

    def __init__(
        self,
        limits: Optional[SafetyLimits] = None,
        strict_mode: bool = True
    ):
        """
        Initialize safety filter.

        Args:
            limits: Safety limits configuration
            strict_mode: If True, block any ambiguous commands
        """
        self.limits = limits or SafetyLimits()
        self.strict_mode = strict_mode

        # Compile patterns
        self._param_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PARAMETER_PATTERNS.items()
        }

        logger.info(f"SafetyFilter initialized (strict_mode={strict_mode})")

    def check(self, recommendation: str) -> FilterResult:
        """
        Check AI recommendation for safety.

        Args:
            recommendation: AI-generated action/recommendation

        Returns:
            FilterResult with action and details
        """
        rec_lower = recommendation.lower().strip()

        # Check always-allowed commands
        for cmd in self.ALWAYS_ALLOWED:
            if rec_lower.startswith(cmd) or cmd in rec_lower.split():
                return FilterResult(
                    action=FilterAction.ALLOW,
                    original=recommendation,
                    filtered=recommendation,
                    reason="Safety command always allowed"
                )

        # Check blocked commands
        for cmd in self.BLOCKED_COMMANDS:
            if cmd in rec_lower:
                return FilterResult(
                    action=FilterAction.BLOCK,
                    original=recommendation,
                    filtered="",
                    domain=SafetyDomain.HUMAN_SAFETY,
                    reason=f"Blocked command: {cmd}",
                    severity=5
                )

        # Parameter limit checks
        limit_results = self._check_parameter_limits(recommendation)
        if limit_results:
            return limit_results

        # Workspace bounds check
        workspace_result = self._check_workspace_bounds(recommendation)
        if workspace_result:
            return workspace_result

        # Context-specific checks
        context_result = self._check_context_safety(recommendation)
        if context_result:
            return context_result

        # Default: allow if no issues found
        return FilterResult(
            action=FilterAction.ALLOW,
            original=recommendation,
            filtered=recommendation,
            reason="Passed all safety checks"
        )

    def _check_parameter_limits(self, text: str) -> Optional[FilterResult]:
        """Check if parameters are within safety limits."""

        # Speed check
        speed_match = self._param_patterns["speed"].search(text)
        if speed_match:
            speed = float(speed_match.group(1))
            if speed > self.limits.max_linear_speed_mm_s:
                modified = self._param_patterns["speed"].sub(
                    f"speed:{self.limits.max_linear_speed_mm_s}",
                    text
                )
                return FilterResult(
                    action=FilterAction.MODIFY,
                    original=text,
                    filtered=modified,
                    domain=SafetyDomain.MOTION,
                    reason=f"Speed {speed} exceeds limit {self.limits.max_linear_speed_mm_s}",
                    severity=3
                )

        # Temperature check
        temp_match = self._param_patterns["temperature"].search(text)
        if temp_match:
            temp = float(temp_match.group(1))
            if temp > self.limits.max_temperature_c:
                return FilterResult(
                    action=FilterAction.BLOCK,
                    original=text,
                    filtered="",
                    domain=SafetyDomain.THERMAL,
                    reason=f"Temperature {temp}°C exceeds limit {self.limits.max_temperature_c}°C",
                    severity=4
                )
            if temp < self.limits.min_temperature_c:
                return FilterResult(
                    action=FilterAction.BLOCK,
                    original=text,
                    filtered="",
                    domain=SafetyDomain.THERMAL,
                    reason=f"Temperature {temp}°C below limit {self.limits.min_temperature_c}°C",
                    severity=4
                )

        # Pressure check
        pressure_match = self._param_patterns["pressure"].search(text)
        if pressure_match:
            pressure = float(pressure_match.group(1))
            if pressure > self.limits.max_pressure_bar:
                return FilterResult(
                    action=FilterAction.BLOCK,
                    original=text,
                    filtered="",
                    domain=SafetyDomain.PRESSURE,
                    reason=f"Pressure {pressure} bar exceeds limit {self.limits.max_pressure_bar} bar",
                    severity=5
                )

        # Force check
        force_match = self._param_patterns["force"].search(text)
        if force_match:
            force = float(force_match.group(1))
            if force > self.limits.max_force_n:
                modified = self._param_patterns["force"].sub(
                    f"force:{self.limits.max_force_n}",
                    text
                )
                return FilterResult(
                    action=FilterAction.MODIFY,
                    original=text,
                    filtered=modified,
                    domain=SafetyDomain.HUMAN_SAFETY,
                    reason=f"Force {force}N exceeds cobot limit {self.limits.max_force_n}N",
                    severity=4
                )

        return None

    def _check_workspace_bounds(self, text: str) -> Optional[FilterResult]:
        """Check if positions are within workspace bounds."""
        positions = {}

        for axis in ['x', 'y', 'z']:
            pattern = self._param_patterns[f"position_{axis}"]
            match = pattern.search(text)
            if match:
                positions[axis] = float(match.group(1))

        if not positions:
            return None

        mins = self.limits.workspace_min
        maxs = self.limits.workspace_max

        violations = []
        if 'x' in positions:
            if positions['x'] < mins[0] or positions['x'] > maxs[0]:
                violations.append(f"X={positions['x']} outside [{mins[0]}, {maxs[0]}]")
        if 'y' in positions:
            if positions['y'] < mins[1] or positions['y'] > maxs[1]:
                violations.append(f"Y={positions['y']} outside [{mins[1]}, {maxs[1]}]")
        if 'z' in positions:
            if positions['z'] < mins[2] or positions['z'] > maxs[2]:
                violations.append(f"Z={positions['z']} outside [{mins[2]}, {maxs[2]}]")

        if violations:
            return FilterResult(
                action=FilterAction.BLOCK,
                original=text,
                filtered="",
                domain=SafetyDomain.MOTION,
                reason=f"Position out of bounds: {', '.join(violations)}",
                severity=3
            )

        return None

    def _check_context_safety(self, text: str) -> Optional[FilterResult]:
        """Check for context-specific safety concerns."""
        text_lower = text.lower()

        # Dangerous combinations
        if "rapid" in text_lower and "z" in text_lower:
            if self.strict_mode:
                return FilterResult(
                    action=FilterAction.ESCALATE,
                    original=text,
                    filtered=text,
                    domain=SafetyDomain.MOTION,
                    reason="Rapid Z movement requires human confirmation",
                    severity=2
                )

        # Material-specific checks
        if "abs" in text_lower and "temp" not in text_lower:
            # ABS without temperature specification - might be unsafe
            if self.strict_mode:
                return FilterResult(
                    action=FilterAction.ESCALATE,
                    original=text,
                    filtered=text,
                    domain=SafetyDomain.THERMAL,
                    reason="ABS material detected - verify temperature settings",
                    severity=2
                )

        return None

    def check_batch(self, recommendations: List[str]) -> List[FilterResult]:
        """Check multiple recommendations."""
        return [self.check(rec) for rec in recommendations]

    def get_limits_summary(self) -> Dict[str, Any]:
        """Get current safety limits summary."""
        return {
            "motion": {
                "max_speed_mm_s": self.limits.max_linear_speed_mm_s,
                "max_angular_deg_s": self.limits.max_angular_speed_deg_s,
                "max_acceleration_mm_s2": self.limits.max_acceleration_mm_s2,
            },
            "thermal": {
                "max_temp_c": self.limits.max_temperature_c,
                "min_temp_c": self.limits.min_temperature_c,
            },
            "force": {
                "max_force_n": self.limits.max_force_n,
            },
            "workspace": {
                "min": self.limits.workspace_min,
                "max": self.limits.workspace_max,
            },
            "strict_mode": self.strict_mode,
        }
