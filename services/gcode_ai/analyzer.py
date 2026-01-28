"""
G-code Analyzer for AI-powered toolpath analysis.

Uses Claude AI to provide intelligent analysis of G-code programs,
identifying issues, inefficiencies, and improvement opportunities.
"""

import logging
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for toolpath issues."""
    CRITICAL = "critical"   # Must fix before running
    WARNING = "warning"     # Should fix
    INFO = "info"          # Suggestion


class IssueCategory(Enum):
    """Categories of toolpath issues."""
    SAFETY = "safety"
    EFFICIENCY = "efficiency"
    QUALITY = "quality"
    TOOL_LIFE = "tool_life"
    SYNTAX = "syntax"
    MACHINE_LIMIT = "machine_limit"


@dataclass
class ToolpathIssue:
    """A detected issue in the toolpath."""
    id: str
    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    line_number: Optional[int] = None
    line_content: Optional[str] = None
    suggestion: str = ""
    affected_lines: List[int] = field(default_factory=list)


@dataclass
class ToolpathMetrics:
    """Metrics extracted from toolpath analysis."""
    total_lines: int = 0
    motion_lines: int = 0
    rapid_moves: int = 0
    feed_moves: int = 0
    arc_moves: int = 0
    tool_changes: int = 0

    # Distance metrics
    total_rapid_distance: float = 0.0
    total_cut_distance: float = 0.0

    # Time estimates (based on feed rates)
    estimated_cut_time_minutes: float = 0.0
    estimated_rapid_time_minutes: float = 0.0
    estimated_total_time_minutes: float = 0.0

    # Axis ranges
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0
    z_min: float = 0.0
    z_max: float = 0.0

    # Feed rates
    min_feed_rate: float = float("inf")
    max_feed_rate: float = 0.0
    avg_feed_rate: float = 0.0

    # Spindle
    spindle_speeds: List[int] = field(default_factory=list)

    # Tools used
    tools_used: List[int] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    success: bool
    program_name: str
    analysis_time: datetime
    metrics: ToolpathMetrics
    issues: List[ToolpathIssue]
    summary: str
    recommendations: List[str]
    gcode_preview: List[str]  # First/last lines
    ai_interpretation: str = ""  # Claude's interpretation


class GCodeAnalyzer:
    """
    Analyzes G-code programs for issues, inefficiencies, and improvements.

    Uses both rule-based analysis and Claude AI for intelligent interpretation.
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """
        Initialize analyzer.

        Args:
            flask_url: URL of Flask backend for API calls
        """
        self.flask_url = flask_url
        self._rapid_rate = 100.0  # Assumed rapid rate (ipm)

        # G-code patterns
        self._motion_pattern = re.compile(
            r"^[GN\d]*\s*G?([0123])\s*",
            re.IGNORECASE
        )
        self._axis_pattern = re.compile(
            r"([XYZIJKR])(-?\d+\.?\d*)",
            re.IGNORECASE
        )
        self._feed_pattern = re.compile(r"F(\d+\.?\d*)", re.IGNORECASE)
        self._speed_pattern = re.compile(r"S(\d+)", re.IGNORECASE)
        self._tool_pattern = re.compile(r"T(\d+)", re.IGNORECASE)

    def analyze(
        self,
        gcode: str,
        program_name: str = "Unknown",
        material: str = "aluminum",
        tool_diameter: float = 0.25,
    ) -> AnalysisResult:
        """
        Analyze a G-code program.

        Args:
            gcode: G-code program text
            program_name: Name of the program
            material: Workpiece material
            tool_diameter: Current tool diameter in inches

        Returns:
            AnalysisResult with metrics, issues, and recommendations
        """
        lines = gcode.strip().split("\n")
        issues: List[ToolpathIssue] = []

        # Parse and extract metrics
        metrics = self._extract_metrics(lines)

        # Run rule-based checks
        issues.extend(self._check_safety_rules(lines))
        issues.extend(self._check_efficiency_rules(lines, metrics))
        issues.extend(self._check_quality_rules(lines, tool_diameter))
        issues.extend(self._check_syntax(lines))

        # Generate summary
        summary = self._generate_summary(metrics, issues)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            issues, metrics, material, tool_diameter
        )

        # Create preview
        preview_lines = 10
        gcode_preview = (
            lines[:preview_lines] +
            ["...", f"({len(lines) - preview_lines * 2} lines omitted)", "..."] +
            lines[-preview_lines:]
            if len(lines) > preview_lines * 2
            else lines
        )

        return AnalysisResult(
            success=True,
            program_name=program_name,
            analysis_time=datetime.now(),
            metrics=metrics,
            issues=issues,
            summary=summary,
            recommendations=recommendations,
            gcode_preview=gcode_preview,
        )

    def _extract_metrics(self, lines: List[str]) -> ToolpathMetrics:
        """Extract metrics from G-code lines."""
        metrics = ToolpathMetrics()
        metrics.total_lines = len(lines)

        current_pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        current_feed = 0.0
        is_first_x = is_first_y = is_first_z = True
        feed_rates = []

        for line in lines:
            line = line.strip().upper()

            # Skip comments and empty lines
            if not line or line.startswith("(") or line.startswith(";"):
                continue

            # Check for tool changes
            tool_match = self._tool_pattern.search(line)
            if tool_match:
                tool_num = int(tool_match.group(1))
                if tool_num not in metrics.tools_used:
                    metrics.tools_used.append(tool_num)
                if "M6" in line or "M06" in line:
                    metrics.tool_changes += 1

            # Check for spindle speeds
            speed_match = self._speed_pattern.search(line)
            if speed_match:
                speed = int(speed_match.group(1))
                if speed not in metrics.spindle_speeds:
                    metrics.spindle_speeds.append(speed)

            # Check for feed rate
            feed_match = self._feed_pattern.search(line)
            if feed_match:
                current_feed = float(feed_match.group(1))
                feed_rates.append(current_feed)

            # Check motion commands
            motion_match = self._motion_pattern.search(line)
            if motion_match or any(axis in line for axis in "XYZ"):
                metrics.motion_lines += 1

                # Extract new position
                new_pos = current_pos.copy()
                for match in self._axis_pattern.finditer(line):
                    axis = match.group(1).upper()
                    value = float(match.group(2))
                    if axis in "XYZ":
                        new_pos[axis] = value

                # Update min/max
                if "X" in line:
                    if is_first_x:
                        metrics.x_min = metrics.x_max = new_pos["X"]
                        is_first_x = False
                    else:
                        metrics.x_min = min(metrics.x_min, new_pos["X"])
                        metrics.x_max = max(metrics.x_max, new_pos["X"])

                if "Y" in line:
                    if is_first_y:
                        metrics.y_min = metrics.y_max = new_pos["Y"]
                        is_first_y = False
                    else:
                        metrics.y_min = min(metrics.y_min, new_pos["Y"])
                        metrics.y_max = max(metrics.y_max, new_pos["Y"])

                if "Z" in line:
                    if is_first_z:
                        metrics.z_min = metrics.z_max = new_pos["Z"]
                        is_first_z = False
                    else:
                        metrics.z_min = min(metrics.z_min, new_pos["Z"])
                        metrics.z_max = max(metrics.z_max, new_pos["Z"])

                # Calculate distance
                dx = new_pos["X"] - current_pos["X"]
                dy = new_pos["Y"] - current_pos["Y"]
                dz = new_pos["Z"] - current_pos["Z"]
                distance = math.sqrt(dx**2 + dy**2 + dz**2)

                # Categorize move type
                if "G0" in line or "G00" in line:
                    metrics.rapid_moves += 1
                    metrics.total_rapid_distance += distance
                    if self._rapid_rate > 0:
                        metrics.estimated_rapid_time_minutes += distance / self._rapid_rate
                elif "G1" in line or "G01" in line:
                    metrics.feed_moves += 1
                    metrics.total_cut_distance += distance
                    if current_feed > 0:
                        metrics.estimated_cut_time_minutes += distance / current_feed
                elif "G2" in line or "G02" in line or "G3" in line or "G03" in line:
                    metrics.arc_moves += 1
                    # Arc distance is approximate
                    metrics.total_cut_distance += distance * 1.5
                    if current_feed > 0:
                        metrics.estimated_cut_time_minutes += (distance * 1.5) / current_feed

                current_pos = new_pos

        # Calculate feed rate stats
        if feed_rates:
            metrics.min_feed_rate = min(feed_rates)
            metrics.max_feed_rate = max(feed_rates)
            metrics.avg_feed_rate = sum(feed_rates) / len(feed_rates)

        # Total time
        metrics.estimated_total_time_minutes = (
            metrics.estimated_cut_time_minutes +
            metrics.estimated_rapid_time_minutes +
            (metrics.tool_changes * 0.5)  # 30 sec per tool change
        )

        return metrics

    def _check_safety_rules(self, lines: List[str]) -> List[ToolpathIssue]:
        """Check safety-related rules."""
        issues = []
        spindle_on = False
        coolant_on = False
        current_z = 0.0
        safe_z = 0.1

        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()

            # Skip comments
            if not line_upper or line_upper.startswith("(") or line_upper.startswith(";"):
                continue

            # Track spindle state
            if "M3" in line_upper or "M4" in line_upper:
                spindle_on = True
            elif "M5" in line_upper:
                spindle_on = False

            # Track coolant state
            if "M8" in line_upper or "M7" in line_upper:
                coolant_on = True
            elif "M9" in line_upper:
                coolant_on = False

            # Track Z position
            z_match = re.search(r"Z(-?\d+\.?\d*)", line_upper)
            if z_match:
                current_z = float(z_match.group(1))

            # Check: Feed move without spindle
            if any(g in line_upper for g in ["G1 ", "G01", "G2 ", "G02", "G3 ", "G03"]):
                if "F" in line_upper and current_z < 0 and not spindle_on:
                    issues.append(ToolpathIssue(
                        id=f"SAFE001-{i}",
                        category=IssueCategory.SAFETY,
                        severity=IssueSeverity.CRITICAL,
                        title="Feed move without spindle running",
                        description=f"Line {i} has a cutting move but spindle is not on",
                        line_number=i,
                        line_content=line.strip(),
                        suggestion="Add M3 Sxxxx before this line to start spindle",
                    ))

            # Check: Rapid XY without safe Z
            if "G0" in line_upper or "G00" in line_upper:
                if ("X" in line_upper or "Y" in line_upper) and "Z" not in line_upper:
                    if current_z < safe_z:
                        issues.append(ToolpathIssue(
                            id=f"SAFE003-{i}",
                            category=IssueCategory.SAFETY,
                            severity=IssueSeverity.CRITICAL,
                            title="Rapid XY move with tool below safe height",
                            description=f"Line {i}: Rapid move at Z={current_z} may cause collision",
                            line_number=i,
                            line_content=line.strip(),
                            suggestion=f"Retract to Z{safe_z} or higher before XY rapid moves",
                        ))

        # Check: Program end without spindle stop
        last_lines = "\n".join(lines[-10:]).upper()
        if ("M30" in last_lines or "M2" in last_lines) and "M5" not in last_lines:
            issues.append(ToolpathIssue(
                id="SAFE004",
                category=IssueCategory.SAFETY,
                severity=IssueSeverity.WARNING,
                title="Program ends without spindle stop",
                description="M5 (spindle stop) should appear before M30/M2",
                suggestion="Add M5 before M30 at program end",
            ))

        return issues

    def _check_efficiency_rules(
        self,
        lines: List[str],
        metrics: ToolpathMetrics,
    ) -> List[ToolpathIssue]:
        """Check efficiency-related rules."""
        issues = []

        # Check: Excessive rapid distance (air cutting)
        if metrics.total_rapid_distance > 0:
            rapid_ratio = metrics.total_rapid_distance / (
                metrics.total_cut_distance + metrics.total_rapid_distance + 0.001
            )
            if rapid_ratio > 0.4:  # More than 40% is rapid
                issues.append(ToolpathIssue(
                    id="EFFI001",
                    category=IssueCategory.EFFICIENCY,
                    severity=IssueSeverity.INFO,
                    title="High proportion of rapid (non-cutting) moves",
                    description=f"{rapid_ratio*100:.0f}% of travel is rapid moves (air cutting)",
                    suggestion="Consider optimizing toolpath to reduce air cutting time",
                ))

        # Check: Many tool changes
        if metrics.tool_changes > 8:
            issues.append(ToolpathIssue(
                id="EFFI003",
                category=IssueCategory.EFFICIENCY,
                severity=IssueSeverity.INFO,
                title="High number of tool changes",
                description=f"{metrics.tool_changes} tool changes in program",
                suggestion="Consider reorganizing operations to minimize tool changes",
            ))

        # Check: Feed moves used for travel
        for i, line in enumerate(lines, 1):
            line_upper = line.strip().upper()
            if ("G1 " in line_upper or "G01" in line_upper) and "Z" not in line_upper:
                # Feed move without Z change at high position might be unnecessary
                z_match = re.search(r"Z(-?\d+\.?\d*)", "\n".join(lines[max(0, i-5):i]).upper())
                if z_match and float(z_match.group(1)) > 0.1:
                    # Check if there's a significant XY move
                    xy_move = re.search(r"[XY](-?\d+\.?\d*)", line_upper)
                    if xy_move:
                        issues.append(ToolpathIssue(
                            id=f"EFFI004-{i}",
                            category=IssueCategory.EFFICIENCY,
                            severity=IssueSeverity.INFO,
                            title="Feed move used for non-cutting travel",
                            description=f"Line {i}: G1 used where G0 would be faster",
                            line_number=i,
                            line_content=line.strip(),
                            suggestion="Use G0 for rapid positioning above the work",
                        ))
                        break  # Only report once

        return issues

    def _check_quality_rules(
        self,
        lines: List[str],
        tool_diameter: float,
    ) -> List[ToolpathIssue]:
        """Check quality-related rules."""
        issues = []

        # Track feed rate changes for consistency
        feed_rates = []
        for line in lines:
            match = self._feed_pattern.search(line)
            if match:
                feed_rates.append(float(match.group(1)))

        if len(feed_rates) >= 2:
            # Check for large feed rate variations
            avg_feed = sum(feed_rates) / len(feed_rates)
            max_variation = max(abs(f - avg_feed) / avg_feed for f in feed_rates)
            if max_variation > 0.5:  # More than 50% variation
                issues.append(ToolpathIssue(
                    id="QUAL003",
                    category=IssueCategory.QUALITY,
                    severity=IssueSeverity.INFO,
                    title="Large feed rate variation",
                    description=f"Feed rate varies by {max_variation*100:.0f}% from average",
                    suggestion="Consider using more consistent feed rates for better finish",
                ))

        return issues

    def _check_syntax(self, lines: List[str]) -> List[ToolpathIssue]:
        """Check for syntax issues."""
        issues = []

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("(") or line.startswith(";"):
                continue

            # Check for unbalanced parentheses
            if line.count("(") != line.count(")"):
                issues.append(ToolpathIssue(
                    id=f"SYN001-{i}",
                    category=IssueCategory.SYNTAX,
                    severity=IssueSeverity.WARNING,
                    title="Unbalanced parentheses",
                    description=f"Line {i} has mismatched parentheses",
                    line_number=i,
                    line_content=line,
                    suggestion="Check and balance parentheses",
                ))

            # Check for mixed G codes on same line
            g_codes = re.findall(r"G(\d+)", line.upper())
            motion_gcodes = [g for g in g_codes if g in ["0", "00", "1", "01", "2", "02", "3", "03"]]
            if len(motion_gcodes) > 1:
                issues.append(ToolpathIssue(
                    id=f"SYN002-{i}",
                    category=IssueCategory.SYNTAX,
                    severity=IssueSeverity.WARNING,
                    title="Multiple motion G-codes on same line",
                    description=f"Line {i} has multiple motion commands",
                    line_number=i,
                    line_content=line,
                    suggestion="Put each motion command on its own line",
                ))

        return issues

    def _generate_summary(
        self,
        metrics: ToolpathMetrics,
        issues: List[ToolpathIssue],
    ) -> str:
        """Generate a human-readable summary."""
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == IssueSeverity.INFO)

        summary_lines = [
            f"## Program Analysis Summary",
            "",
            f"**Lines:** {metrics.total_lines} total, {metrics.motion_lines} motion commands",
            f"**Moves:** {metrics.rapid_moves} rapid, {metrics.feed_moves} feed, {metrics.arc_moves} arc",
            f"**Tools:** {len(metrics.tools_used)} tools, {metrics.tool_changes} changes",
            "",
            f"**Work Envelope:**",
            f"- X: {metrics.x_min:.3f} to {metrics.x_max:.3f}",
            f"- Y: {metrics.y_min:.3f} to {metrics.y_max:.3f}",
            f"- Z: {metrics.z_min:.3f} to {metrics.z_max:.3f}",
            "",
            f"**Distances:**",
            f"- Cutting: {metrics.total_cut_distance:.2f} inches",
            f"- Rapid: {metrics.total_rapid_distance:.2f} inches",
            "",
            f"**Estimated Time:** {metrics.estimated_total_time_minutes:.1f} minutes",
            "",
            f"**Issues Found:**",
            f"- Critical: {critical_count}",
            f"- Warnings: {warning_count}",
            f"- Suggestions: {info_count}",
        ]

        return "\n".join(summary_lines)

    def _generate_recommendations(
        self,
        issues: List[ToolpathIssue],
        metrics: ToolpathMetrics,
        material: str,
        tool_diameter: float,
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Safety recommendations first
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            recommendations.append(
                f"⛔ FIX {len(critical_issues)} CRITICAL issues before running this program"
            )

        # Material-specific recommendations
        if material.lower() in ["stainless", "titanium"]:
            recommendations.append(
                "🛡️ Work-hardening material: Ensure constant engagement, never let tool dwell"
            )

        if material.lower() in ["aluminum", "plastic"]:
            if metrics.max_feed_rate > 0 and metrics.max_feed_rate < 20:
                recommendations.append(
                    f"⚡ Feed rate may be conservative for {material}. Consider increasing."
                )

        # Efficiency recommendations
        if metrics.tool_changes > 5:
            recommendations.append(
                "🔧 Consider grouping operations to reduce tool changes"
            )

        if metrics.total_rapid_distance > metrics.total_cut_distance * 0.5:
            recommendations.append(
                "✈️ High air cutting time. Consider optimizing toolpath order."
            )

        # General best practices
        if not metrics.spindle_speeds:
            recommendations.append(
                "⚠️ No spindle speed found. Ensure S command is present."
            )

        return recommendations

    async def analyze_with_claude(
        self,
        gcode: str,
        program_name: str = "Unknown",
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        Analyze G-code with Claude AI for intelligent interpretation.

        Args:
            gcode: G-code program text
            program_name: Name of the program
            context: Additional context (material, machine, etc.)

        Returns:
            AnalysisResult with AI interpretation
        """
        # First run standard analysis
        result = self.analyze(
            gcode,
            program_name,
            context.get("material", "aluminum") if context else "aluminum",
            context.get("tool_diameter", 0.25) if context else 0.25,
        )

        # Use Claude for interpretation
        try:
            import anthropic

            client = anthropic.Anthropic()

            # Build prompt
            prompt = f"""Analyze this CNC G-code program and provide insights:

## Program: {program_name}

## Metrics
{result.summary}

## First 20 lines:
```gcode
{chr(10).join(result.gcode_preview[:20])}
```

## Issues Found:
{chr(10).join(f"- [{i.severity.value}] {i.title}: {i.description}" for i in result.issues[:10])}

## Context:
Material: {context.get('material', 'unknown') if context else 'unknown'}
Machine: {context.get('machine', 'CNC router') if context else 'CNC router'}

Please provide:
1. A brief description of what this program appears to do
2. Any additional concerns not captured by the automated analysis
3. Optimization suggestions specific to this toolpath
4. Estimated complexity (simple/moderate/complex)

Keep your response concise and actionable."""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            result.ai_interpretation = response.content[0].text

        except Exception as e:
            logger.warning(f"Claude analysis failed: {e}")
            result.ai_interpretation = f"AI analysis unavailable: {str(e)}"

        return result


# Convenience function
def analyze_gcode(
    gcode: str,
    program_name: str = "Unknown",
    material: str = "aluminum",
) -> AnalysisResult:
    """Quick analysis of G-code."""
    analyzer = GCodeAnalyzer()
    return analyzer.analyze(gcode, program_name, material)
