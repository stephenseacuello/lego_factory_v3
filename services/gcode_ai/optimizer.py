"""
G-code Optimizer for AI-powered feed/speed optimization.

Analyzes G-code and suggests optimizations for better performance,
tool life, and surface finish based on material and tooling.
"""

import logging
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations."""
    FEED_RATE = "feed_rate"
    SPINDLE_SPEED = "spindle_speed"
    DEPTH_OF_CUT = "depth_of_cut"
    TOOLPATH = "toolpath"
    ENTRY_EXIT = "entry_exit"
    RAPID_MOVES = "rapid_moves"


class OptimizationGoal(Enum):
    """Optimization goals."""
    CYCLE_TIME = "cycle_time"      # Minimize time
    SURFACE_FINISH = "surface_finish"  # Best finish
    TOOL_LIFE = "tool_life"        # Maximize tool life
    BALANCED = "balanced"          # Balance all factors


@dataclass
class OptimizationSuggestion:
    """A suggested optimization."""
    type: OptimizationType
    priority: int  # 1 = highest priority
    title: str
    description: str
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    affected_lines: List[int] = field(default_factory=list)
    estimated_improvement: str = ""
    risk_level: str = "low"  # low, medium, high


@dataclass
class OptimizationResult:
    """Complete optimization result."""
    success: bool
    original_gcode: str
    optimized_gcode: Optional[str]
    suggestions: List[OptimizationSuggestion]
    summary: str
    estimated_time_savings: float  # minutes
    parameters_changed: Dict[str, Any]


class GCodeOptimizer:
    """
    Optimizes G-code programs for better performance.

    Analyzes feed rates, spindle speeds, and toolpath efficiency
    to suggest improvements based on material and tooling.
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """
        Initialize optimizer.

        Args:
            flask_url: URL of Flask backend for API calls
        """
        self.flask_url = flask_url

        # Import knowledge base
        from .knowledge_base.materials import material_db
        from .knowledge_base.tooling import tool_catalog
        self.material_db = material_db
        self.tool_catalog = tool_catalog

    def optimize(
        self,
        gcode: str,
        material: str = "aluminum",
        tool_diameter: float = 0.25,
        tool_number: int = 1,
        goal: OptimizationGoal = OptimizationGoal.BALANCED,
        apply_changes: bool = False,
    ) -> OptimizationResult:
        """
        Optimize G-code program.

        Args:
            gcode: G-code program text
            material: Workpiece material
            tool_diameter: Tool diameter in inches
            tool_number: Tool number for lookup
            goal: Optimization goal
            apply_changes: If True, return modified G-code

        Returns:
            OptimizationResult with suggestions and optionally modified code
        """
        lines = gcode.strip().split("\n")
        suggestions: List[OptimizationSuggestion] = []

        # Get material recommendations
        material_recs = self.material_db.get_cutting_recommendations(
            material, "milling", tool_diameter
        )

        # Get tool info
        tool = self.tool_catalog.get_tool(tool_number)

        # Analyze feed rates
        suggestions.extend(
            self._analyze_feed_rates(lines, material_recs, goal)
        )

        # Analyze spindle speeds
        suggestions.extend(
            self._analyze_spindle_speeds(lines, material_recs, tool_diameter)
        )

        # Analyze depth of cut
        suggestions.extend(
            self._analyze_depth_of_cut(lines, tool_diameter, material)
        )

        # Analyze toolpath efficiency
        suggestions.extend(
            self._analyze_toolpath_efficiency(lines)
        )

        # Analyze entry/exit moves
        suggestions.extend(
            self._analyze_entry_exit(lines, tool)
        )

        # Sort by priority
        suggestions.sort(key=lambda s: s.priority)

        # Calculate estimated savings
        time_savings = sum(
            self._estimate_time_saving(s) for s in suggestions
        )

        # Optionally apply changes
        optimized_gcode = None
        parameters_changed = {}

        if apply_changes:
            optimized_gcode, parameters_changed = self._apply_optimizations(
                lines, suggestions, material_recs
            )

        # Generate summary
        summary = self._generate_summary(suggestions, time_savings, goal)

        return OptimizationResult(
            success=True,
            original_gcode=gcode,
            optimized_gcode=optimized_gcode,
            suggestions=suggestions,
            summary=summary,
            estimated_time_savings=time_savings,
            parameters_changed=parameters_changed,
        )

    def _analyze_feed_rates(
        self,
        lines: List[str],
        material_recs: Dict[str, Any],
        goal: OptimizationGoal,
    ) -> List[OptimizationSuggestion]:
        """Analyze and suggest feed rate optimizations."""
        suggestions = []

        if "error" in material_recs:
            return suggestions

        recommended_feed = material_recs.get("recommended_parameters", {}).get(
            "feed_rate_ipm", 20
        )

        # Adjust based on goal
        if goal == OptimizationGoal.CYCLE_TIME:
            recommended_feed *= 1.2  # 20% faster
        elif goal == OptimizationGoal.SURFACE_FINISH:
            recommended_feed *= 0.7  # 30% slower
        elif goal == OptimizationGoal.TOOL_LIFE:
            recommended_feed *= 0.8  # 20% slower

        feed_pattern = re.compile(r"F(\d+\.?\d*)", re.IGNORECASE)
        feed_lines = []

        for i, line in enumerate(lines, 1):
            match = feed_pattern.search(line)
            if match:
                current_feed = float(match.group(1))
                feed_lines.append((i, current_feed))

        if feed_lines:
            avg_feed = sum(f[1] for f in feed_lines) / len(feed_lines)

            # Check if feed is too low
            if avg_feed < recommended_feed * 0.6:
                suggestions.append(OptimizationSuggestion(
                    type=OptimizationType.FEED_RATE,
                    priority=1,
                    title="Feed rate may be too conservative",
                    description=f"Average feed rate ({avg_feed:.1f} ipm) is significantly "
                               f"below recommended ({recommended_feed:.1f} ipm) for this material",
                    current_value=f"{avg_feed:.1f} ipm",
                    suggested_value=f"{recommended_feed:.1f} ipm",
                    affected_lines=[l[0] for l in feed_lines],
                    estimated_improvement="10-30% cycle time reduction",
                    risk_level="low",
                ))

            # Check if feed is too high
            elif avg_feed > recommended_feed * 1.5:
                suggestions.append(OptimizationSuggestion(
                    type=OptimizationType.FEED_RATE,
                    priority=1,
                    title="Feed rate may be too aggressive",
                    description=f"Average feed rate ({avg_feed:.1f} ipm) is above "
                               f"recommended ({recommended_feed:.1f} ipm) for this material",
                    current_value=f"{avg_feed:.1f} ipm",
                    suggested_value=f"{recommended_feed:.1f} ipm",
                    affected_lines=[l[0] for l in feed_lines],
                    estimated_improvement="Improved tool life, better finish",
                    risk_level="medium",
                ))

            # Check for inconsistent feed rates
            if len(feed_lines) > 1:
                min_feed = min(f[1] for f in feed_lines)
                max_feed = max(f[1] for f in feed_lines)
                if max_feed > min_feed * 2:
                    suggestions.append(OptimizationSuggestion(
                        type=OptimizationType.FEED_RATE,
                        priority=3,
                        title="Large feed rate variation detected",
                        description=f"Feed rate varies from {min_feed:.1f} to {max_feed:.1f} ipm",
                        estimated_improvement="More consistent surface finish",
                        risk_level="low",
                    ))

        return suggestions

    def _analyze_spindle_speeds(
        self,
        lines: List[str],
        material_recs: Dict[str, Any],
        tool_diameter: float,
    ) -> List[OptimizationSuggestion]:
        """Analyze and suggest spindle speed optimizations."""
        suggestions = []

        if "error" in material_recs:
            return suggestions

        recommended_rpm = material_recs.get("recommended_parameters", {}).get(
            "spindle_rpm", 10000
        )

        speed_pattern = re.compile(r"S(\d+)", re.IGNORECASE)
        speeds = []

        for i, line in enumerate(lines, 1):
            match = speed_pattern.search(line)
            if match:
                speeds.append((i, int(match.group(1))))

        if speeds:
            primary_speed = speeds[0][1]

            # Check if speed is appropriate
            if primary_speed < recommended_rpm * 0.5:
                suggestions.append(OptimizationSuggestion(
                    type=OptimizationType.SPINDLE_SPEED,
                    priority=2,
                    title="Spindle speed may be too low",
                    description=f"Current speed ({primary_speed} RPM) is below "
                               f"recommended ({recommended_rpm} RPM) for this tool/material",
                    current_value=f"{primary_speed} RPM",
                    suggested_value=f"{recommended_rpm} RPM",
                    affected_lines=[s[0] for s in speeds],
                    estimated_improvement="Better chip formation, improved finish",
                    risk_level="low",
                ))

            elif primary_speed > recommended_rpm * 1.5:
                suggestions.append(OptimizationSuggestion(
                    type=OptimizationType.SPINDLE_SPEED,
                    priority=2,
                    title="Spindle speed may be too high",
                    description=f"Current speed ({primary_speed} RPM) exceeds "
                               f"recommended ({recommended_rpm} RPM) for this tool/material",
                    current_value=f"{primary_speed} RPM",
                    suggested_value=f"{recommended_rpm} RPM",
                    affected_lines=[s[0] for s in speeds],
                    estimated_improvement="Reduced tool wear, safer operation",
                    risk_level="medium",
                ))

        return suggestions

    def _analyze_depth_of_cut(
        self,
        lines: List[str],
        tool_diameter: float,
        material: str,
    ) -> List[OptimizationSuggestion]:
        """Analyze depth of cut for optimization opportunities."""
        suggestions = []

        # Track Z moves to find depth of cut
        z_moves = []
        z_pattern = re.compile(r"Z(-?\d+\.?\d*)", re.IGNORECASE)

        for i, line in enumerate(lines, 1):
            match = z_pattern.search(line)
            if match:
                z = float(match.group(1))
                if z < 0:  # Below surface
                    z_moves.append((i, z))

        if len(z_moves) >= 2:
            # Calculate step down
            z_values = sorted(set(z[1] for z in z_moves), reverse=True)
            if len(z_values) >= 2:
                step_downs = [
                    abs(z_values[i] - z_values[i+1])
                    for i in range(len(z_values) - 1)
                ]
                avg_step = sum(step_downs) / len(step_downs)

                # Recommended step down is typically 0.5x tool diameter for roughing
                recommended_step = tool_diameter * 0.5

                if avg_step < recommended_step * 0.3:
                    suggestions.append(OptimizationSuggestion(
                        type=OptimizationType.DEPTH_OF_CUT,
                        priority=2,
                        title="Depth of cut appears conservative",
                        description=f"Average step down ({avg_step:.4f}\") is less than "
                                   f"30% of tool diameter. Consider increasing for faster roughing.",
                        current_value=f"{avg_step:.4f}\" step",
                        suggested_value=f"{recommended_step:.4f}\" step",
                        estimated_improvement="Fewer passes, faster cycle time",
                        risk_level="medium" if "steel" in material.lower() else "low",
                    ))

        return suggestions

    def _analyze_toolpath_efficiency(
        self,
        lines: List[str],
    ) -> List[OptimizationSuggestion]:
        """Analyze toolpath for efficiency improvements."""
        suggestions = []

        rapid_count = 0
        feed_count = 0
        total_rapid_distance = 0.0
        total_cut_distance = 0.0

        current_pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        axis_pattern = re.compile(r"([XYZ])(-?\d+\.?\d*)", re.IGNORECASE)

        for line in lines:
            line_upper = line.upper()

            # Extract position changes
            new_pos = current_pos.copy()
            for match in axis_pattern.finditer(line_upper):
                axis = match.group(1).upper()
                new_pos[axis] = float(match.group(2))

            # Calculate distance
            dx = new_pos["X"] - current_pos["X"]
            dy = new_pos["Y"] - current_pos["Y"]
            dz = new_pos["Z"] - current_pos["Z"]
            distance = math.sqrt(dx**2 + dy**2 + dz**2)

            if "G0" in line_upper or "G00" in line_upper:
                rapid_count += 1
                total_rapid_distance += distance
            elif any(g in line_upper for g in ["G1", "G01", "G2", "G02", "G3", "G03"]):
                feed_count += 1
                total_cut_distance += distance

            current_pos = new_pos

        if rapid_count + feed_count > 0:
            rapid_ratio = total_rapid_distance / (
                total_rapid_distance + total_cut_distance + 0.001
            )

            if rapid_ratio > 0.4:
                suggestions.append(OptimizationSuggestion(
                    type=OptimizationType.RAPID_MOVES,
                    priority=3,
                    title="High proportion of non-cutting moves",
                    description=f"{rapid_ratio*100:.0f}% of travel is rapid positioning. "
                               f"Consider optimizing toolpath order.",
                    estimated_improvement="5-15% cycle time reduction",
                    risk_level="low",
                ))

        # Check for unnecessary retracts
        retract_count = 0
        for i, line in enumerate(lines):
            if "G0" in line.upper() and "Z" in line.upper():
                z_match = re.search(r"Z(\d+\.?\d*)", line, re.IGNORECASE)
                if z_match and float(z_match.group(1)) > 0.1:
                    # Check if next XY move is nearby
                    retract_count += 1

        if retract_count > 20:
            suggestions.append(OptimizationSuggestion(
                type=OptimizationType.RAPID_MOVES,
                priority=4,
                title="Frequent retracts detected",
                description=f"{retract_count} retract moves found. Some may be unnecessary.",
                estimated_improvement="Reduced cycle time",
                risk_level="low",
            ))

        return suggestions

    def _analyze_entry_exit(
        self,
        lines: List[str],
        tool: Optional[Any],
    ) -> List[OptimizationSuggestion]:
        """Analyze entry and exit moves."""
        suggestions = []

        # Check for plunge moves (vertical entry)
        plunge_count = 0
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if "G1" in line_upper or "G01" in line_upper:
                # Check if only Z is moving (plunge)
                if "Z" in line_upper and "X" not in line_upper and "Y" not in line_upper:
                    z_match = re.search(r"Z(-\d+\.?\d*)", line_upper)
                    if z_match:
                        plunge_count += 1

        if plunge_count > 3:
            suggestions.append(OptimizationSuggestion(
                type=OptimizationType.ENTRY_EXIT,
                priority=2,
                title="Multiple plunge entry moves detected",
                description=f"{plunge_count} vertical plunge moves found. "
                           f"Consider ramp or helix entry for better tool life.",
                estimated_improvement="Reduced tool wear, safer entry",
                risk_level="medium",
            ))

        return suggestions

    def _estimate_time_saving(self, suggestion: OptimizationSuggestion) -> float:
        """Estimate time saving for a suggestion."""
        # Rough estimates based on suggestion type
        time_map = {
            OptimizationType.FEED_RATE: 2.0,
            OptimizationType.SPINDLE_SPEED: 0.5,
            OptimizationType.DEPTH_OF_CUT: 3.0,
            OptimizationType.TOOLPATH: 1.5,
            OptimizationType.ENTRY_EXIT: 0.5,
            OptimizationType.RAPID_MOVES: 1.0,
        }
        return time_map.get(suggestion.type, 0.5)

    def _apply_optimizations(
        self,
        lines: List[str],
        suggestions: List[OptimizationSuggestion],
        material_recs: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Apply suggested optimizations to G-code."""
        modified_lines = lines.copy()
        parameters_changed = {}

        for suggestion in suggestions:
            if suggestion.type == OptimizationType.FEED_RATE:
                if suggestion.suggested_value and suggestion.affected_lines:
                    # Extract numeric value
                    new_feed_match = re.search(r"(\d+\.?\d*)", suggestion.suggested_value)
                    if new_feed_match:
                        new_feed = new_feed_match.group(1)
                        for line_num in suggestion.affected_lines:
                            idx = line_num - 1
                            if idx < len(modified_lines):
                                modified_lines[idx] = re.sub(
                                    r"F\d+\.?\d*",
                                    f"F{new_feed}",
                                    modified_lines[idx],
                                    flags=re.IGNORECASE,
                                )
                        parameters_changed["feed_rate"] = float(new_feed)

            elif suggestion.type == OptimizationType.SPINDLE_SPEED:
                if suggestion.suggested_value and suggestion.affected_lines:
                    new_speed_match = re.search(r"(\d+)", suggestion.suggested_value)
                    if new_speed_match:
                        new_speed = new_speed_match.group(1)
                        for line_num in suggestion.affected_lines:
                            idx = line_num - 1
                            if idx < len(modified_lines):
                                modified_lines[idx] = re.sub(
                                    r"S\d+",
                                    f"S{new_speed}",
                                    modified_lines[idx],
                                    flags=re.IGNORECASE,
                                )
                        parameters_changed["spindle_speed"] = int(new_speed)

        # Add optimization comment at top
        header = [
            "( OPTIMIZED BY G-CODE AI )",
            f"( Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Changes: {', '.join(parameters_changed.keys()) or 'None'} )",
            "",
        ]

        return "\n".join(header + modified_lines), parameters_changed

    def _generate_summary(
        self,
        suggestions: List[OptimizationSuggestion],
        time_savings: float,
        goal: OptimizationGoal,
    ) -> str:
        """Generate optimization summary."""
        if not suggestions:
            return "No optimizations suggested - program appears well-optimized."

        priority_1 = [s for s in suggestions if s.priority == 1]
        priority_2 = [s for s in suggestions if s.priority == 2]
        priority_3 = [s for s in suggestions if s.priority >= 3]

        lines = [
            f"## Optimization Summary",
            f"",
            f"**Optimization Goal:** {goal.value.replace('_', ' ').title()}",
            f"**Suggestions Found:** {len(suggestions)}",
            f"**Estimated Time Savings:** {time_savings:.1f} minutes",
            "",
        ]

        if priority_1:
            lines.append("### High Priority")
            for s in priority_1:
                lines.append(f"- {s.title}")
            lines.append("")

        if priority_2:
            lines.append("### Medium Priority")
            for s in priority_2:
                lines.append(f"- {s.title}")
            lines.append("")

        if priority_3:
            lines.append("### Low Priority")
            for s in priority_3:
                lines.append(f"- {s.title}")

        return "\n".join(lines)

    def get_feed_speed_recommendations(
        self,
        material: str,
        tool_diameter: float,
        operation: str = "milling",
    ) -> Dict[str, Any]:
        """
        Get feed and speed recommendations for a material/tool combination.

        Args:
            material: Workpiece material
            tool_diameter: Tool diameter in inches
            operation: Type of operation

        Returns:
            Dictionary with recommended parameters
        """
        return self.material_db.get_cutting_recommendations(
            material, operation, tool_diameter
        )


# Convenience function
def optimize_gcode(
    gcode: str,
    material: str = "aluminum",
    tool_diameter: float = 0.25,
    goal: OptimizationGoal = OptimizationGoal.BALANCED,
) -> OptimizationResult:
    """Quick G-code optimization."""
    optimizer = GCodeOptimizer()
    return optimizer.optimize(gcode, material, tool_diameter, goal=goal)
