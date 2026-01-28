"""
G-code Safety Validator for pre-execution verification.

Performs comprehensive safety checks on G-code programs before
allowing execution on the machine.
"""

import logging
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Safety check levels."""
    CRITICAL = "critical"   # Cannot run
    WARNING = "warning"     # Should review
    CAUTION = "caution"     # Minor concern
    PASSED = "passed"       # All checks passed


@dataclass
class SafetyIssue:
    """A safety issue found during validation."""
    code: str
    level: SafetyLevel
    title: str
    description: str
    line_number: Optional[int] = None
    line_content: Optional[str] = None
    recommendation: str = ""


@dataclass
class MachineEnvelope:
    """Machine work envelope definition."""
    x_min: float = -0.5
    x_max: float = 12.0
    y_min: float = -0.5
    y_max: float = 8.0
    z_min: float = -3.0
    z_max: float = 1.0
    max_spindle_rpm: int = 24000
    min_spindle_rpm: int = 1000
    max_feed_rate: float = 200.0
    max_rapid_rate: float = 400.0


@dataclass
class ValidationResult:
    """Complete validation result."""
    safe_to_run: bool
    overall_level: SafetyLevel
    issues: List[SafetyIssue]
    summary: str
    checks_performed: List[str]
    machine_envelope: MachineEnvelope
    estimated_bounds: Dict[str, Tuple[float, float]]


class SafetyValidator:
    """
    Validates G-code for safety before machine execution.

    Performs comprehensive checks including:
    - Machine envelope limits
    - Spindle safety
    - Feed rate limits
    - Collision detection
    - Proper sequencing
    """

    def __init__(
        self,
        machine_envelope: Optional[MachineEnvelope] = None,
        flask_url: str = "http://localhost:5000",
    ):
        """
        Initialize validator.

        Args:
            machine_envelope: Machine limits (uses defaults if not provided)
            flask_url: URL of Flask backend
        """
        self.envelope = machine_envelope or MachineEnvelope()
        self.flask_url = flask_url

        # Pattern definitions
        self._axis_pattern = re.compile(
            r"([XYZIJKR])(-?\d+\.?\d*)", re.IGNORECASE
        )
        self._g_pattern = re.compile(r"G(\d+)", re.IGNORECASE)
        self._m_pattern = re.compile(r"M(\d+)", re.IGNORECASE)
        self._f_pattern = re.compile(r"F(\d+\.?\d*)", re.IGNORECASE)
        self._s_pattern = re.compile(r"S(\d+)", re.IGNORECASE)

    def validate(
        self,
        gcode: str,
        strict_mode: bool = False,
    ) -> ValidationResult:
        """
        Validate G-code program for safety.

        Args:
            gcode: G-code program text
            strict_mode: If True, treat warnings as critical

        Returns:
            ValidationResult with safety assessment
        """
        lines = gcode.strip().split("\n")
        issues: List[SafetyIssue] = []
        checks_performed = []

        # Track estimated bounds
        bounds = {
            "X": (0.0, 0.0),
            "Y": (0.0, 0.0),
            "Z": (0.0, 0.0),
        }

        # Run all checks
        issues.extend(self._check_envelope_limits(lines, bounds))
        checks_performed.append("Machine envelope limits")

        issues.extend(self._check_spindle_safety(lines))
        checks_performed.append("Spindle safety")

        issues.extend(self._check_feed_rates(lines))
        checks_performed.append("Feed rate limits")

        issues.extend(self._check_coolant_safety(lines))
        checks_performed.append("Coolant safety")

        issues.extend(self._check_rapid_safety(lines))
        checks_performed.append("Rapid move safety")

        issues.extend(self._check_program_structure(lines))
        checks_performed.append("Program structure")

        issues.extend(self._check_dangerous_gcodes(lines))
        checks_performed.append("Dangerous G-codes")

        # Determine overall safety level
        has_critical = any(i.level == SafetyLevel.CRITICAL for i in issues)
        has_warning = any(i.level == SafetyLevel.WARNING for i in issues)

        if has_critical:
            overall_level = SafetyLevel.CRITICAL
            safe_to_run = False
        elif has_warning:
            overall_level = SafetyLevel.WARNING
            safe_to_run = not strict_mode
        elif issues:
            overall_level = SafetyLevel.CAUTION
            safe_to_run = True
        else:
            overall_level = SafetyLevel.PASSED
            safe_to_run = True

        # Generate summary
        summary = self._generate_summary(issues, overall_level, len(lines))

        return ValidationResult(
            safe_to_run=safe_to_run,
            overall_level=overall_level,
            issues=issues,
            summary=summary,
            checks_performed=checks_performed,
            machine_envelope=self.envelope,
            estimated_bounds=bounds,
        )

    def _check_envelope_limits(
        self,
        lines: List[str],
        bounds: Dict[str, Tuple[float, float]],
    ) -> List[SafetyIssue]:
        """Check if all moves are within machine envelope."""
        issues = []
        current_pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            # Skip comments
            if not line_upper or line_upper.startswith("(") or line_upper.startswith(";"):
                continue

            # Extract axis values
            for match in self._axis_pattern.finditer(line_upper):
                axis = match.group(1).upper()
                if axis in "XYZ":
                    value = float(match.group(2))
                    current_pos[axis] = value

                    # Check limits
                    if axis == "X":
                        if value < self.envelope.x_min:
                            issues.append(SafetyIssue(
                                code="ENV001",
                                level=SafetyLevel.CRITICAL,
                                title="X below minimum travel",
                                description=f"X{value} is below machine minimum X{self.envelope.x_min}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Adjust work origin or modify toolpath",
                            ))
                        elif value > self.envelope.x_max:
                            issues.append(SafetyIssue(
                                code="ENV002",
                                level=SafetyLevel.CRITICAL,
                                title="X above maximum travel",
                                description=f"X{value} is above machine maximum X{self.envelope.x_max}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Adjust work origin or modify toolpath",
                            ))
                        bounds["X"] = (
                            min(bounds["X"][0], value),
                            max(bounds["X"][1], value),
                        )

                    elif axis == "Y":
                        if value < self.envelope.y_min:
                            issues.append(SafetyIssue(
                                code="ENV003",
                                level=SafetyLevel.CRITICAL,
                                title="Y below minimum travel",
                                description=f"Y{value} is below machine minimum Y{self.envelope.y_min}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Adjust work origin or modify toolpath",
                            ))
                        elif value > self.envelope.y_max:
                            issues.append(SafetyIssue(
                                code="ENV004",
                                level=SafetyLevel.CRITICAL,
                                title="Y above maximum travel",
                                description=f"Y{value} is above machine maximum Y{self.envelope.y_max}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Adjust work origin or modify toolpath",
                            ))
                        bounds["Y"] = (
                            min(bounds["Y"][0], value),
                            max(bounds["Y"][1], value),
                        )

                    elif axis == "Z":
                        if value < self.envelope.z_min:
                            issues.append(SafetyIssue(
                                code="ENV005",
                                level=SafetyLevel.CRITICAL,
                                title="Z below minimum travel",
                                description=f"Z{value} is below machine minimum Z{self.envelope.z_min}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Check depth of cut and work holding",
                            ))
                        elif value > self.envelope.z_max:
                            issues.append(SafetyIssue(
                                code="ENV006",
                                level=SafetyLevel.CRITICAL,
                                title="Z above maximum travel",
                                description=f"Z{value} is above machine maximum Z{self.envelope.z_max}",
                                line_number=i,
                                line_content=line.strip(),
                                recommendation="Check tool length and clearance",
                            ))
                        bounds["Z"] = (
                            min(bounds["Z"][0], value),
                            max(bounds["Z"][1], value),
                        )

        return issues

    def _check_spindle_safety(self, lines: List[str]) -> List[SafetyIssue]:
        """Check spindle-related safety issues."""
        issues = []
        spindle_on = False
        has_spindle_start = False
        has_spindle_stop = False
        current_z = 0.0

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            # Track Z
            z_match = re.search(r"Z(-?\d+\.?\d*)", line_upper)
            if z_match:
                current_z = float(z_match.group(1))

            # Check for spindle start
            if "M3" in line_upper or "M4" in line_upper:
                spindle_on = True
                has_spindle_start = True

                # Check for spindle speed
                s_match = self._s_pattern.search(line_upper)
                if s_match:
                    speed = int(s_match.group(1))
                    if speed > self.envelope.max_spindle_rpm:
                        issues.append(SafetyIssue(
                            code="SPD001",
                            level=SafetyLevel.CRITICAL,
                            title="Spindle speed exceeds maximum",
                            description=f"S{speed} exceeds machine max {self.envelope.max_spindle_rpm} RPM",
                            line_number=i,
                            line_content=line.strip(),
                            recommendation=f"Reduce spindle speed to {self.envelope.max_spindle_rpm} or below",
                        ))
                    elif speed < self.envelope.min_spindle_rpm and speed > 0:
                        issues.append(SafetyIssue(
                            code="SPD002",
                            level=SafetyLevel.WARNING,
                            title="Spindle speed below minimum",
                            description=f"S{speed} is below minimum {self.envelope.min_spindle_rpm} RPM",
                            line_number=i,
                            line_content=line.strip(),
                            recommendation="Increase spindle speed for proper operation",
                        ))

            # Check for spindle stop
            if "M5" in line_upper:
                spindle_on = False
                has_spindle_stop = True

            # Check for cutting move without spindle
            if any(g in line_upper for g in ["G1 ", "G01", "G2 ", "G02", "G3 ", "G03"]):
                if "F" in line_upper and current_z < 0 and not spindle_on:
                    issues.append(SafetyIssue(
                        code="SPD003",
                        level=SafetyLevel.CRITICAL,
                        title="Cutting move without spindle",
                        description="Feed move below surface with spindle off",
                        line_number=i,
                        line_content=line.strip(),
                        recommendation="Add M3 Sxxxx before this line",
                    ))

        # Check for missing spindle commands
        if not has_spindle_start:
            issues.append(SafetyIssue(
                code="SPD004",
                level=SafetyLevel.CRITICAL,
                title="No spindle start command",
                description="Program has no M3/M4 spindle start command",
                recommendation="Add M3 Sxxxx at program start",
            ))

        if has_spindle_start and not has_spindle_stop:
            issues.append(SafetyIssue(
                code="SPD005",
                level=SafetyLevel.WARNING,
                title="No spindle stop command",
                description="Program has no M5 spindle stop command",
                recommendation="Add M5 before program end (M30)",
            ))

        return issues

    def _check_feed_rates(self, lines: List[str]) -> List[SafetyIssue]:
        """Check feed rate safety."""
        issues = []
        has_feed_rate = False

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            f_match = self._f_pattern.search(line_upper)
            if f_match:
                has_feed_rate = True
                feed = float(f_match.group(1))

                if feed > self.envelope.max_feed_rate:
                    issues.append(SafetyIssue(
                        code="FED001",
                        level=SafetyLevel.CRITICAL,
                        title="Feed rate exceeds maximum",
                        description=f"F{feed} exceeds machine max {self.envelope.max_feed_rate}",
                        line_number=i,
                        line_content=line.strip(),
                        recommendation=f"Reduce feed rate to {self.envelope.max_feed_rate} or below",
                    ))
                elif feed < 0.1:
                    issues.append(SafetyIssue(
                        code="FED002",
                        level=SafetyLevel.WARNING,
                        title="Very low feed rate",
                        description=f"F{feed} is very low and may cause tool rubbing",
                        line_number=i,
                        line_content=line.strip(),
                        recommendation="Increase feed rate to prevent tool wear",
                    ))

            # Check for feed move without feed rate
            if ("G1 " in line_upper or "G01" in line_upper) and "F" not in line_upper:
                if not has_feed_rate:
                    issues.append(SafetyIssue(
                        code="FED003",
                        level=SafetyLevel.WARNING,
                        title="Feed move without feed rate",
                        description="G1 move has no F value and no prior F specified",
                        line_number=i,
                        line_content=line.strip(),
                        recommendation="Add F value to specify feed rate",
                    ))

        return issues

    def _check_coolant_safety(self, lines: List[str]) -> List[SafetyIssue]:
        """Check coolant-related safety."""
        issues = []
        coolant_on = False
        has_coolant_off = False

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            if "M8" in line_upper or "M7" in line_upper:
                coolant_on = True
            if "M9" in line_upper:
                coolant_on = False
                has_coolant_off = True

        # Check if coolant was started but never stopped
        if coolant_on and not has_coolant_off:
            issues.append(SafetyIssue(
                code="CLN001",
                level=SafetyLevel.CAUTION,
                title="Coolant not turned off",
                description="M8/M7 coolant on found but no M9 off command",
                recommendation="Add M9 before program end",
            ))

        return issues

    def _check_rapid_safety(self, lines: List[str]) -> List[SafetyIssue]:
        """Check rapid move safety."""
        issues = []
        current_z = 0.0
        safe_z = 0.1

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            # Track Z position
            z_match = re.search(r"Z(-?\d+\.?\d*)", line_upper)
            if z_match:
                current_z = float(z_match.group(1))

            # Check rapid XY moves at unsafe Z
            if "G0" in line_upper or "G00" in line_upper:
                if ("X" in line_upper or "Y" in line_upper) and "Z" not in line_upper:
                    if current_z < safe_z:
                        issues.append(SafetyIssue(
                            code="RAP001",
                            level=SafetyLevel.CRITICAL,
                            title="Rapid XY below safe height",
                            description=f"Rapid XY move at Z{current_z} may cause collision",
                            line_number=i,
                            line_content=line.strip(),
                            recommendation=f"Retract to Z{safe_z} or higher before XY rapids",
                        ))

        return issues

    def _check_program_structure(self, lines: List[str]) -> List[SafetyIssue]:
        """Check program structure and sequencing."""
        issues = []
        full_text = "\n".join(lines).upper()

        # Check for program end
        if "M30" not in full_text and "M2" not in full_text and "M00" not in full_text:
            issues.append(SafetyIssue(
                code="STR001",
                level=SafetyLevel.WARNING,
                title="No program end command",
                description="Program has no M30, M2, or M00 end command",
                recommendation="Add M30 at program end",
            ))

        # Check for work coordinate system
        if not any(f"G5{n}" in full_text for n in range(4, 10)):
            issues.append(SafetyIssue(
                code="STR002",
                level=SafetyLevel.CAUTION,
                title="No work coordinate system",
                description="No G54-G59 work coordinate specified",
                recommendation="Add G54 (or appropriate WCS) at program start",
            ))

        # Check for tool length compensation
        if "T" in full_text and "M6" in full_text:
            if "G43" not in full_text:
                issues.append(SafetyIssue(
                    code="STR003",
                    level=SafetyLevel.WARNING,
                    title="No tool length compensation",
                    description="Tool change found but no G43 Hxx",
                    recommendation="Add G43 Hxx after each tool change",
                ))

        return issues

    def _check_dangerous_gcodes(self, lines: List[str]) -> List[SafetyIssue]:
        """Check for potentially dangerous G-codes."""
        issues = []

        dangerous_codes = {
            "G28": "Return to reference position - verify safe path",
            "G30": "Return to secondary reference - verify safe path",
            "G53": "Machine coordinate move - verify safe limits",
            "G92": "Coordinate system offset - verify values",
        }

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            for code, warning in dangerous_codes.items():
                if code in line_upper:
                    issues.append(SafetyIssue(
                        code=f"DNG{code[1:]}",
                        level=SafetyLevel.CAUTION,
                        title=f"{code} command detected",
                        description=warning,
                        line_number=i,
                        line_content=line.strip(),
                        recommendation="Review this line carefully before running",
                    ))

        return issues

    def _generate_summary(
        self,
        issues: List[SafetyIssue],
        overall_level: SafetyLevel,
        line_count: int,
    ) -> str:
        """Generate validation summary."""
        critical = sum(1 for i in issues if i.level == SafetyLevel.CRITICAL)
        warnings = sum(1 for i in issues if i.level == SafetyLevel.WARNING)
        cautions = sum(1 for i in issues if i.level == SafetyLevel.CAUTION)

        if overall_level == SafetyLevel.PASSED:
            emoji = "✅"
            status = "PASSED - Safe to run"
        elif overall_level == SafetyLevel.CAUTION:
            emoji = "⚠️"
            status = "PASSED with cautions"
        elif overall_level == SafetyLevel.WARNING:
            emoji = "⚠️"
            status = "WARNINGS - Review before running"
        else:
            emoji = "🛑"
            status = "FAILED - Do not run"

        lines = [
            f"## {emoji} Safety Validation: {status}",
            "",
            f"**Lines Analyzed:** {line_count}",
            f"**Issues Found:**",
            f"- Critical: {critical}",
            f"- Warnings: {warnings}",
            f"- Cautions: {cautions}",
        ]

        if issues:
            lines.append("")
            lines.append("### Issues:")
            for issue in issues[:5]:  # Show first 5
                level_emoji = {
                    SafetyLevel.CRITICAL: "🛑",
                    SafetyLevel.WARNING: "⚠️",
                    SafetyLevel.CAUTION: "ℹ️",
                }[issue.level]
                lines.append(f"- {level_emoji} **{issue.title}**: {issue.description}")

            if len(issues) > 5:
                lines.append(f"- ... and {len(issues) - 5} more issues")

        return "\n".join(lines)

    def quick_check(self, gcode: str) -> Tuple[bool, str]:
        """
        Quick pass/fail safety check.

        Args:
            gcode: G-code program text

        Returns:
            Tuple of (safe_to_run, summary_message)
        """
        result = self.validate(gcode)
        return result.safe_to_run, result.summary


# Convenience function
def validate_gcode(gcode: str, strict: bool = False) -> ValidationResult:
    """Quick G-code validation."""
    validator = SafetyValidator()
    return validator.validate(gcode, strict_mode=strict)


def is_safe_to_run(gcode: str) -> Tuple[bool, str]:
    """Quick check if G-code is safe to run."""
    validator = SafetyValidator()
    return validator.quick_check(gcode)
