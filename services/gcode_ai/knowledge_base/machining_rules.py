"""
Machining Rules for G-code AI

Contains best practices, safety rules, and manufacturing guidelines
for CNC machining operations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class RuleCategory(Enum):
    """Categories of machining rules."""
    SAFETY = "safety"           # Safety-critical rules
    QUALITY = "quality"         # Quality-affecting rules
    EFFICIENCY = "efficiency"   # Optimization rules
    TOOL_LIFE = "tool_life"     # Tool preservation rules
    MACHINE_LIMIT = "machine_limit"  # Machine capability limits
    BEST_PRACTICE = "best_practice"  # General recommendations


class RuleSeverity(Enum):
    """Severity of rule violations."""
    CRITICAL = "critical"   # Must fix, cannot proceed
    WARNING = "warning"     # Should fix
    INFO = "info"          # Suggestion only


@dataclass
class Rule:
    """A machining rule definition."""
    id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    description: str
    check_function: Optional[str] = None  # Name of function to check
    parameters: Dict[str, Any] = field(default_factory=dict)
    fix_suggestion: str = ""
    applicable_operations: List[str] = field(default_factory=list)
    applicable_materials: List[str] = field(default_factory=list)


class MachiningRules:
    """
    Database of machining rules and best practices.

    Used by the G-code analyzer and validator to check
    programs against established guidelines.
    """

    def __init__(self):
        """Initialize rules database."""
        self._rules: Dict[str, Rule] = {}
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default machining rules."""
        # Safety rules
        self._rules["SAFE001"] = Rule(
            id="SAFE001",
            name="Spindle must be on for cutting moves",
            category=RuleCategory.SAFETY,
            severity=RuleSeverity.CRITICAL,
            description="G1/G2/G3 feed moves require spindle to be running (M3/M4)",
            fix_suggestion="Add M3 Sxxxx before cutting moves",
            applicable_operations=["milling", "drilling"],
        )

        self._rules["SAFE002"] = Rule(
            id="SAFE002",
            name="Coolant should be on for metal cutting",
            category=RuleCategory.SAFETY,
            severity=RuleSeverity.WARNING,
            description="Metal cutting operations should use coolant (M8)",
            fix_suggestion="Add M8 before cutting, M9 after",
            applicable_materials=["steel", "stainless", "aluminum", "titanium"],
        )

        self._rules["SAFE003"] = Rule(
            id="SAFE003",
            name="Safe retract before rapid moves",
            category=RuleCategory.SAFETY,
            severity=RuleSeverity.CRITICAL,
            description="Z should be at safe height before XY rapid moves",
            parameters={"safe_z": 0.1},
            fix_suggestion="Add G0 Zsafe before G0 XY moves",
        )

        self._rules["SAFE004"] = Rule(
            id="SAFE004",
            name="Program end requires spindle stop",
            category=RuleCategory.SAFETY,
            severity=RuleSeverity.CRITICAL,
            description="Program should end with M5 (spindle stop) before M30/M2",
            fix_suggestion="Add M5 before M30",
        )

        self._rules["SAFE005"] = Rule(
            id="SAFE005",
            name="Check work envelope limits",
            category=RuleCategory.MACHINE_LIMIT,
            severity=RuleSeverity.CRITICAL,
            description="All moves must be within machine travel limits",
            parameters={
                "x_min": -0.5, "x_max": 12.0,
                "y_min": -0.5, "y_max": 8.0,
                "z_min": -2.0, "z_max": 0.5,
            },
            fix_suggestion="Adjust toolpath to stay within limits or reposition work origin",
        )

        self._rules["SAFE006"] = Rule(
            id="SAFE006",
            name="Maximum spindle speed limit",
            category=RuleCategory.MACHINE_LIMIT,
            severity=RuleSeverity.CRITICAL,
            description="Spindle speed must not exceed machine maximum",
            parameters={"max_rpm": 24000},
            fix_suggestion="Reduce spindle speed to within limits",
        )

        self._rules["SAFE007"] = Rule(
            id="SAFE007",
            name="Maximum feed rate limit",
            category=RuleCategory.MACHINE_LIMIT,
            severity=RuleSeverity.CRITICAL,
            description="Feed rate must not exceed machine maximum",
            parameters={"max_feed": 200.0},  # inches per minute
            fix_suggestion="Reduce feed rate to within limits",
        )

        self._rules["SAFE008"] = Rule(
            id="SAFE008",
            name="Avoid plunge with non-center-cutting tools",
            category=RuleCategory.SAFETY,
            severity=RuleSeverity.CRITICAL,
            description="Standard end mills cannot plunge cut - use ramp or helix entry",
            fix_suggestion="Use ramp entry, helix entry, or pre-drilled start holes",
            applicable_operations=["milling", "pocketing"],
        )

        # Quality rules
        self._rules["QUAL001"] = Rule(
            id="QUAL001",
            name="Use climb milling for finish passes",
            category=RuleCategory.QUALITY,
            severity=RuleSeverity.INFO,
            description="Climb milling produces better surface finish on finishing passes",
            fix_suggestion="Change toolpath direction for climb milling on finish passes",
            applicable_operations=["profiling", "finishing"],
        )

        self._rules["QUAL002"] = Rule(
            id="QUAL002",
            name="Reduce feed for finish passes",
            category=RuleCategory.QUALITY,
            severity=RuleSeverity.INFO,
            description="Finishing passes should use 50-75% of roughing feed rate",
            parameters={"finish_feed_factor": 0.6},
            fix_suggestion="Reduce feed rate for final pass",
            applicable_operations=["finishing"],
        )

        self._rules["QUAL003"] = Rule(
            id="QUAL003",
            name="Maintain consistent chip load",
            category=RuleCategory.QUALITY,
            severity=RuleSeverity.WARNING,
            description="Chip load should remain consistent for good surface finish",
            parameters={"chip_load_variance": 0.20},  # 20% variance allowed
            fix_suggestion="Adjust feed rate to maintain consistent chip load",
        )

        self._rules["QUAL004"] = Rule(
            id="QUAL004",
            name="Corner slowdown for sharp corners",
            category=RuleCategory.QUALITY,
            severity=RuleSeverity.INFO,
            description="Reduce feed rate on sharp corners to maintain accuracy",
            parameters={"corner_angle_threshold": 90, "slowdown_factor": 0.7},
            fix_suggestion="Add feed rate reduction or corner radius",
        )

        self._rules["QUAL005"] = Rule(
            id="QUAL005",
            name="Spring pass for thin walls",
            category=RuleCategory.QUALITY,
            severity=RuleSeverity.INFO,
            description="Thin walls may deflect - consider a spring pass",
            parameters={"wall_thickness_threshold": 0.030},  # 0.030" = thin
            fix_suggestion="Add final spring pass with minimal stock",
        )

        # Efficiency rules
        self._rules["EFFI001"] = Rule(
            id="EFFI001",
            name="Minimize air cutting",
            category=RuleCategory.EFFICIENCY,
            severity=RuleSeverity.INFO,
            description="Reduce non-cutting rapid moves when possible",
            fix_suggestion="Optimize toolpath to reduce air cutting time",
        )

        self._rules["EFFI002"] = Rule(
            id="EFFI002",
            name="Use appropriate depth of cut",
            category=RuleCategory.EFFICIENCY,
            severity=RuleSeverity.INFO,
            description="Depth of cut may be too conservative for roughing",
            parameters={"min_doc_factor": 0.25},  # 25% of tool diameter
            fix_suggestion="Increase depth of cut for roughing operations",
            applicable_operations=["roughing"],
        )

        self._rules["EFFI003"] = Rule(
            id="EFFI003",
            name="Avoid excessive tool changes",
            category=RuleCategory.EFFICIENCY,
            severity=RuleSeverity.INFO,
            description="Minimize tool changes when same tool can complete multiple operations",
            parameters={"max_tool_changes": 10},
            fix_suggestion="Reorganize operations to minimize tool changes",
        )

        self._rules["EFFI004"] = Rule(
            id="EFFI004",
            name="Use rapid moves for non-cutting travel",
            category=RuleCategory.EFFICIENCY,
            severity=RuleSeverity.INFO,
            description="Feed moves (G1) used where rapid (G0) would be faster",
            fix_suggestion="Use G0 for non-cutting moves above the work",
        )

        self._rules["EFFI005"] = Rule(
            id="EFFI005",
            name="Consider high-speed machining strategies",
            category=RuleCategory.EFFICIENCY,
            severity=RuleSeverity.INFO,
            description="Trochoidal or adaptive clearing may be more efficient",
            parameters={"radial_engagement_threshold": 0.5},
            fix_suggestion="Use trochoidal milling for better chip evacuation",
            applicable_operations=["roughing", "slotting"],
        )

        # Tool life rules
        self._rules["TOOL001"] = Rule(
            id="TOOL001",
            name="Check chip load against recommendations",
            category=RuleCategory.TOOL_LIFE,
            severity=RuleSeverity.WARNING,
            description="Chip load too high or too low affects tool life",
            parameters={
                "min_chip_load": 0.001,
                "max_chip_load": 0.010,
            },
            fix_suggestion="Adjust feed rate or spindle speed",
        )

        self._rules["TOOL002"] = Rule(
            id="TOOL002",
            name="Avoid rubbing with low chip load",
            category=RuleCategory.TOOL_LIFE,
            severity=RuleSeverity.WARNING,
            description="Chip load too low causes rubbing and rapid tool wear",
            parameters={"min_chip_load": 0.001},
            fix_suggestion="Increase feed rate or reduce spindle speed",
        )

        self._rules["TOOL003"] = Rule(
            id="TOOL003",
            name="Check surface speed recommendations",
            category=RuleCategory.TOOL_LIFE,
            severity=RuleSeverity.WARNING,
            description="Surface speed should match material and tool coating",
            fix_suggestion="Adjust spindle speed based on material recommendations",
        )

        self._rules["TOOL004"] = Rule(
            id="TOOL004",
            name="Peck drilling for deep holes",
            category=RuleCategory.TOOL_LIFE,
            severity=RuleSeverity.WARNING,
            description="Deep holes (>3x diameter) should use peck drilling",
            parameters={"peck_threshold_factor": 3.0},
            fix_suggestion="Use G83 peck drilling cycle",
            applicable_operations=["drilling"],
        )

        self._rules["TOOL005"] = Rule(
            id="TOOL005",
            name="Reduced parameters for tool entry",
            category=RuleCategory.TOOL_LIFE,
            severity=RuleSeverity.INFO,
            description="Reduce feed/speed during tool entry to reduce shock",
            parameters={"entry_feed_factor": 0.5},
            fix_suggestion="Reduce feed rate during entry moves",
        )

        # Best practices
        self._rules["BEST001"] = Rule(
            id="BEST001",
            name="Include program header comments",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.INFO,
            description="Programs should include header with part info and date",
            fix_suggestion="Add program header with part number, revision, and date",
        )

        self._rules["BEST002"] = Rule(
            id="BEST002",
            name="Use work coordinate system",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.WARNING,
            description="Set work coordinate system (G54-G59) at program start",
            fix_suggestion="Add G54 (or appropriate WCS) at program start",
        )

        self._rules["BEST003"] = Rule(
            id="BEST003",
            name="Include tool length compensation",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.WARNING,
            description="Use tool length compensation (G43 Hxx) after tool change",
            fix_suggestion="Add G43 Hxx after each tool change",
        )

        self._rules["BEST004"] = Rule(
            id="BEST004",
            name="Cancel compensation before tool change",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.WARNING,
            description="Cancel G43/G41/G42 before tool changes",
            fix_suggestion="Add G49 G40 before M6 tool change",
        )

        self._rules["BEST005"] = Rule(
            id="BEST005",
            name="Home position at program end",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.INFO,
            description="Return to home/reference position at program end",
            fix_suggestion="Add G28 or G53 move before M30",
        )

        self._rules["BEST006"] = Rule(
            id="BEST006",
            name="Include dwell after spindle start",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.INFO,
            description="Allow spindle to reach speed before cutting (G4)",
            parameters={"dwell_seconds": 2.0},
            fix_suggestion="Add G4 P2.0 after M3 for spindle to reach speed",
        )

        self._rules["BEST007"] = Rule(
            id="BEST007",
            name="Use incremental mode carefully",
            category=RuleCategory.BEST_PRACTICE,
            severity=RuleSeverity.WARNING,
            description="G91 incremental mode can cause position drift - use sparingly",
            fix_suggestion="Prefer G90 absolute mode, return to G90 after G91 sections",
        )

        logger.info(f"Loaded {len(self._rules)} machining rules")

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID."""
        return self._rules.get(rule_id)

    def get_rules_by_category(self, category: RuleCategory) -> List[Rule]:
        """Get all rules in a category."""
        return [r for r in self._rules.values() if r.category == category]

    def get_rules_by_severity(self, severity: RuleSeverity) -> List[Rule]:
        """Get all rules with a given severity."""
        return [r for r in self._rules.values() if r.severity == severity]

    def get_all_rules(self) -> List[Rule]:
        """Get all rules."""
        return list(self._rules.values())

    def get_applicable_rules(
        self,
        operation: Optional[str] = None,
        material: Optional[str] = None,
    ) -> List[Rule]:
        """
        Get rules applicable to a specific operation and material.

        Args:
            operation: Type of operation (milling, drilling, etc.)
            material: Workpiece material

        Returns:
            List of applicable rules
        """
        applicable = []

        for rule in self._rules.values():
            # Check operation applicability
            if rule.applicable_operations:
                if operation and operation.lower() not in [
                    op.lower() for op in rule.applicable_operations
                ]:
                    continue

            # Check material applicability
            if rule.applicable_materials:
                if material and material.lower() not in [
                    mat.lower() for mat in rule.applicable_materials
                ]:
                    continue

            applicable.append(rule)

        return applicable

    def add_rule(self, rule: Rule):
        """Add a custom rule."""
        self._rules[rule.id] = rule
        logger.info(f"Added rule: {rule.id}")

    def check_spindle_running(
        self,
        gcode_lines: List[str],
    ) -> List[Dict[str, Any]]:
        """Check if spindle is running during feed moves."""
        violations = []
        spindle_on = False
        line_number = 0

        for line in gcode_lines:
            line_number += 1
            line_upper = line.upper().strip()

            # Check for spindle on
            if "M3" in line_upper or "M4" in line_upper:
                spindle_on = True
            elif "M5" in line_upper:
                spindle_on = False

            # Check for feed moves
            if any(g in line_upper for g in ["G1 ", "G2 ", "G3 ", "G01", "G02", "G03"]):
                # Check if it's a cutting move (has F and Z is below surface)
                if "F" in line_upper and not spindle_on:
                    violations.append({
                        "rule_id": "SAFE001",
                        "line_number": line_number,
                        "line": line.strip(),
                        "message": "Feed move without spindle running",
                    })

        return violations

    def check_safe_z_height(
        self,
        gcode_lines: List[str],
        safe_z: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Check if Z is at safe height before rapid XY moves."""
        violations = []
        current_z = 0.0
        line_number = 0

        for line in gcode_lines:
            line_number += 1
            line_upper = line.upper().strip()

            # Track Z position
            if "Z" in line_upper:
                import re
                z_match = re.search(r"Z(-?\d+\.?\d*)", line_upper)
                if z_match:
                    current_z = float(z_match.group(1))

            # Check rapid XY moves
            if "G0 " in line_upper or "G00" in line_upper:
                if ("X" in line_upper or "Y" in line_upper) and "Z" not in line_upper:
                    if current_z < safe_z:
                        violations.append({
                            "rule_id": "SAFE003",
                            "line_number": line_number,
                            "line": line.strip(),
                            "message": f"Rapid XY move with Z={current_z} below safe height {safe_z}",
                            "current_z": current_z,
                            "safe_z": safe_z,
                        })

        return violations

    def check_work_envelope(
        self,
        gcode_lines: List[str],
        limits: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Check if all moves are within work envelope."""
        if limits is None:
            rule = self._rules.get("SAFE005")
            limits = rule.parameters if rule else {
                "x_min": -0.5, "x_max": 12.0,
                "y_min": -0.5, "y_max": 8.0,
                "z_min": -2.0, "z_max": 0.5,
            }

        violations = []
        line_number = 0
        import re

        for line in gcode_lines:
            line_number += 1
            line_upper = line.upper().strip()

            # Skip comments
            if line_upper.startswith("(") or line_upper.startswith(";"):
                continue

            # Check each axis
            for axis in ["X", "Y", "Z"]:
                if axis in line_upper:
                    match = re.search(rf"{axis}(-?\d+\.?\d*)", line_upper)
                    if match:
                        value = float(match.group(1))
                        min_key = f"{axis.lower()}_min"
                        max_key = f"{axis.lower()}_max"

                        if min_key in limits and value < limits[min_key]:
                            violations.append({
                                "rule_id": "SAFE005",
                                "line_number": line_number,
                                "line": line.strip(),
                                "message": f"{axis}={value} below minimum {limits[min_key]}",
                            })
                        elif max_key in limits and value > limits[max_key]:
                            violations.append({
                                "rule_id": "SAFE005",
                                "line_number": line_number,
                                "line": line.strip(),
                                "message": f"{axis}={value} above maximum {limits[max_key]}",
                            })

        return violations

    def get_recommendations(
        self,
        operation: str,
        material: str,
        tool_diameter: float,
    ) -> List[Dict[str, Any]]:
        """
        Get machining recommendations for an operation.

        Args:
            operation: Type of operation
            material: Workpiece material
            tool_diameter: Tool diameter in inches

        Returns:
            List of recommendations
        """
        recommendations = []

        # Get applicable rules
        applicable = self.get_applicable_rules(operation, material)

        for rule in applicable:
            if rule.category == RuleCategory.BEST_PRACTICE:
                recommendations.append({
                    "rule_id": rule.id,
                    "recommendation": rule.description,
                    "suggestion": rule.fix_suggestion,
                })

        # Add material-specific recommendations
        if material.lower() in ["stainless", "titanium"]:
            recommendations.append({
                "rule_id": "CUSTOM",
                "recommendation": f"Work hardening material - maintain constant feed",
                "suggestion": "Never let tool dwell or rub, use constant engagement",
            })

        # Add operation-specific recommendations
        if operation.lower() == "pocketing":
            recommendations.append({
                "rule_id": "CUSTOM",
                "recommendation": "Use ramp or helix entry for pockets",
                "suggestion": f"Ramp angle of 2-3° or helix entry at 5° for {tool_diameter}\" tool",
            })

        return recommendations


# Global instance
machining_rules = MachiningRules()
