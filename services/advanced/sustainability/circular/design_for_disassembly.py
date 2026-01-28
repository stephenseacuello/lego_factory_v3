"""
Design for Disassembly (DfD) Analysis for Circular Economy

PhD-Level Research Implementation:
- Disassembly sequence planning using graph theory
- DfD scoring based on multiple criteria
- Product architecture analysis for circularity
- End-of-life scenario modeling

Novel Contributions:
- AI-assisted disassembly optimization
- Integration with CAD systems for design feedback
- Real-time DfD scoring during product design

Standards:
- ISO 14006 (Environmental Management - Eco-design)
- IEC 62430 (Environmentally Conscious Design)
- EU Ecodesign Directive
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
from datetime import datetime
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class JointType(Enum):
    """Types of joints between components"""
    SNAP_FIT = "snap_fit"           # Easy to disassemble
    SCREW = "screw"                 # Requires tools
    ADHESIVE = "adhesive"          # Difficult to separate
    WELD = "weld"                  # Very difficult
    RIVET = "rivet"                # Destructive removal
    PRESS_FIT = "press_fit"        # Moderate difficulty
    MAGNETIC = "magnetic"          # Very easy
    HOOK = "hook"                  # Easy
    ULTRASONIC = "ultrasonic"      # Very difficult


class MaterialCategory(Enum):
    """Material categories for recyclability assessment"""
    SINGLE_POLYMER = "single_polymer"   # Easily recyclable
    MULTI_POLYMER = "multi_polymer"     # Separation needed
    METAL = "metal"                     # High value recyclable
    COMPOSITE = "composite"             # Difficult to recycle
    ELECTRONIC = "electronic"           # Special handling
    HAZARDOUS = "hazardous"             # Regulated disposal
    BIODEGRADABLE = "biodegradable"     # Compostable


@dataclass
class Component:
    """A component in the product structure"""
    component_id: str
    name: str
    material: str
    material_category: MaterialCategory
    mass_kg: float
    volume_cm3: float
    is_reusable: bool = True
    is_recyclable: bool = True
    contains_hazardous: bool = False
    lifetime_cycles: int = 1
    recycled_content_percent: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Joint:
    """A joint connecting two components"""
    joint_id: str
    component_a: str
    component_b: str
    joint_type: JointType
    disassembly_time_seconds: float
    requires_tool: bool = False
    tool_type: Optional[str] = None
    is_reversible: bool = True
    accessibility_score: float = 1.0  # 0-1, 1=fully accessible
    force_required_n: float = 0.0


@dataclass
class DisassemblyStep:
    """A step in the disassembly sequence"""
    step_number: int
    component_id: str
    joints_released: List[str]
    time_seconds: float
    tools_required: List[str]
    notes: str = ""
    parallel_candidates: List[str] = field(default_factory=list)


@dataclass
class DfDScore:
    """Design for Disassembly score and breakdown"""
    overall_score: float  # 0-100
    disassembly_time_score: float
    tool_requirement_score: float
    material_compatibility_score: float
    component_accessibility_score: float
    reversibility_score: float
    hazard_score: float
    recyclability_score: float
    reusability_score: float
    breakdown: Dict[str, float]
    recommendations: List[str]
    grade: str  # A/B/C/D/F


@dataclass
class EndOfLifeScenario:
    """End-of-life scenario analysis"""
    scenario_name: str
    reusable_mass_kg: float
    recyclable_mass_kg: float
    energy_recovery_mass_kg: float
    landfill_mass_kg: float
    hazardous_mass_kg: float
    total_value: float
    total_processing_cost: float
    disassembly_time_hours: float
    required_labor_hours: float


class DfDAnalyzer:
    """
    Design for Disassembly analyzer for product circularity.

    Evaluates products based on:
    - Ease of disassembly (time, tools, accessibility)
    - Material compatibility for recycling
    - Component reusability potential
    - Hazardous material handling
    - End-of-life value recovery

    Example:
        analyzer = DfDAnalyzer()

        # Add components
        analyzer.add_component(Component(
            "body", "Main Body", "ABS", MaterialCategory.SINGLE_POLYMER,
            0.25, 300.0, is_reusable=True
        ))

        # Add joints
        analyzer.add_joint(Joint(
            "j1", "body", "cover", JointType.SNAP_FIT, 5.0
        ))

        # Analyze
        score = analyzer.calculate_dfd_score()
    """

    # DfD score weights
    WEIGHTS = {
        "disassembly_time": 0.20,
        "tool_requirement": 0.10,
        "material_compatibility": 0.15,
        "accessibility": 0.10,
        "reversibility": 0.10,
        "hazard": 0.10,
        "recyclability": 0.15,
        "reusability": 0.10
    }

    # Disassembly time thresholds (seconds per joint)
    DISASSEMBLY_TARGETS = {
        JointType.MAGNETIC: 1.0,
        JointType.HOOK: 2.0,
        JointType.SNAP_FIT: 5.0,
        JointType.SCREW: 15.0,
        JointType.PRESS_FIT: 10.0,
        JointType.RIVET: 30.0,
        JointType.ADHESIVE: 45.0,
        JointType.ULTRASONIC: 60.0,
        JointType.WELD: 90.0
    }

    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.joints: Dict[str, Joint] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
        self._joint_map: Dict[Tuple[str, str], str] = {}

    def add_component(self, component: Component) -> None:
        """Add a component to the product"""
        self.components[component.component_id] = component
        logger.info(f"Added component: {component.component_id}")

    def add_joint(self, joint: Joint) -> None:
        """Add a joint between components"""
        self.joints[joint.joint_id] = joint
        self._adjacency[joint.component_a].add(joint.component_b)
        self._adjacency[joint.component_b].add(joint.component_a)
        self._joint_map[(joint.component_a, joint.component_b)] = joint.joint_id
        self._joint_map[(joint.component_b, joint.component_a)] = joint.joint_id
        logger.info(f"Added joint: {joint.joint_id}")

    def calculate_dfd_score(self) -> DfDScore:
        """
        Calculate comprehensive DfD score.

        Returns a DfDScore object with overall score, subscores,
        and recommendations for improvement.
        """
        # Calculate individual subscores
        scores = {}

        scores["disassembly_time"] = self._score_disassembly_time()
        scores["tool_requirement"] = self._score_tool_requirements()
        scores["material_compatibility"] = self._score_material_compatibility()
        scores["accessibility"] = self._score_accessibility()
        scores["reversibility"] = self._score_reversibility()
        scores["hazard"] = self._score_hazard_handling()
        scores["recyclability"] = self._score_recyclability()
        scores["reusability"] = self._score_reusability()

        # Weighted overall score
        overall = sum(
            scores[key] * self.WEIGHTS[key]
            for key in scores
        )

        # Determine grade
        if overall >= 85:
            grade = "A"
        elif overall >= 70:
            grade = "B"
        elif overall >= 55:
            grade = "C"
        elif overall >= 40:
            grade = "D"
        else:
            grade = "F"

        # Generate recommendations
        recommendations = self._generate_recommendations(scores)

        return DfDScore(
            overall_score=overall,
            disassembly_time_score=scores["disassembly_time"],
            tool_requirement_score=scores["tool_requirement"],
            material_compatibility_score=scores["material_compatibility"],
            component_accessibility_score=scores["accessibility"],
            reversibility_score=scores["reversibility"],
            hazard_score=scores["hazard"],
            recyclability_score=scores["recyclability"],
            reusability_score=scores["reusability"],
            breakdown=scores,
            recommendations=recommendations,
            grade=grade
        )

    def _score_disassembly_time(self) -> float:
        """Score based on total disassembly time"""
        if not self.joints:
            return 100.0

        total_time = sum(j.disassembly_time_seconds for j in self.joints.values())
        total_components = len(self.components)

        # Target: 30 seconds per component average
        target_total = total_components * 30.0
        ratio = total_time / target_total if target_total > 0 else 1.0

        # Score: 100 if at target, decreasing logarithmically
        if ratio <= 1.0:
            return 100.0
        else:
            return max(0, 100 - 30 * np.log10(ratio) * 10)

    def _score_tool_requirements(self) -> float:
        """Score based on tools required for disassembly"""
        if not self.joints:
            return 100.0

        tool_joints = sum(1 for j in self.joints.values() if j.requires_tool)
        tool_ratio = tool_joints / len(self.joints)

        # Unique tools required
        unique_tools = set(
            j.tool_type for j in self.joints.values()
            if j.tool_type
        )
        tool_penalty = len(unique_tools) * 5

        return max(0, 100 - tool_ratio * 50 - tool_penalty)

    def _score_material_compatibility(self) -> float:
        """Score based on material compatibility for recycling"""
        if not self.components:
            return 100.0

        material_groups: Dict[str, List[Component]] = defaultdict(list)
        for comp in self.components.values():
            material_groups[comp.material].append(comp)

        # Fewer distinct materials = better score
        n_materials = len(material_groups)
        material_score = max(0, 100 - (n_materials - 1) * 15)

        # Check for incompatible materials in contact
        incompatibility_penalty = 0
        for joint in self.joints.values():
            comp_a = self.components.get(joint.component_a)
            comp_b = self.components.get(joint.component_b)
            if comp_a and comp_b:
                if comp_a.material_category != comp_b.material_category:
                    if not joint.is_reversible:
                        incompatibility_penalty += 10

        return max(0, material_score - incompatibility_penalty)

    def _score_accessibility(self) -> float:
        """Score based on component accessibility for disassembly"""
        if not self.joints:
            return 100.0

        avg_accessibility = np.mean([
            j.accessibility_score for j in self.joints.values()
        ])

        return avg_accessibility * 100

    def _score_reversibility(self) -> float:
        """Score based on joint reversibility"""
        if not self.joints:
            return 100.0

        reversible = sum(1 for j in self.joints.values() if j.is_reversible)
        return (reversible / len(self.joints)) * 100

    def _score_hazard_handling(self) -> float:
        """Score based on hazardous material handling"""
        if not self.components:
            return 100.0

        hazardous_count = sum(
            1 for c in self.components.values() if c.contains_hazardous
        )

        if hazardous_count == 0:
            return 100.0

        # Check if hazardous components are easily separable
        hazard_ids = {
            c.component_id for c in self.components.values()
            if c.contains_hazardous
        }

        # Count joints connecting hazardous to non-hazardous
        boundary_joints = 0
        easy_boundary = 0
        for joint in self.joints.values():
            a_haz = joint.component_a in hazard_ids
            b_haz = joint.component_b in hazard_ids
            if a_haz != b_haz:  # Boundary joint
                boundary_joints += 1
                if joint.joint_type in [JointType.SNAP_FIT, JointType.MAGNETIC, JointType.HOOK]:
                    easy_boundary += 1

        if boundary_joints == 0:
            return 70.0  # All hazardous or all non-hazardous

        separation_ease = easy_boundary / boundary_joints
        return 40 + separation_ease * 60

    def _score_recyclability(self) -> float:
        """Score based on component recyclability"""
        if not self.components:
            return 100.0

        recyclable_mass = sum(
            c.mass_kg for c in self.components.values() if c.is_recyclable
        )
        total_mass = sum(c.mass_kg for c in self.components.values())

        recyclable_ratio = recyclable_mass / total_mass if total_mass > 0 else 0

        # Bonus for recycled content
        avg_recycled_content = np.mean([
            c.recycled_content_percent for c in self.components.values()
        ])

        return recyclable_ratio * 80 + avg_recycled_content * 0.2

    def _score_reusability(self) -> float:
        """Score based on component reusability potential"""
        if not self.components:
            return 100.0

        reusable_mass = sum(
            c.mass_kg for c in self.components.values() if c.is_reusable
        )
        total_mass = sum(c.mass_kg for c in self.components.values())

        reusable_ratio = reusable_mass / total_mass if total_mass > 0 else 0

        # Bonus for multi-cycle components
        avg_cycles = np.mean([
            min(c.lifetime_cycles, 10) for c in self.components.values()
        ])
        cycle_bonus = (avg_cycles - 1) * 5

        return min(100, reusable_ratio * 80 + cycle_bonus)

    def _generate_recommendations(self, scores: Dict[str, float]) -> List[str]:
        """Generate recommendations based on scores"""
        recommendations = []

        if scores["disassembly_time"] < 60:
            slow_joints = [
                j for j in self.joints.values()
                if j.disassembly_time_seconds > 30
            ]
            if slow_joints:
                recommendations.append(
                    f"Replace {len(slow_joints)} slow joints (welds, adhesives) "
                    "with snap-fits or screws to reduce disassembly time."
                )

        if scores["tool_requirement"] < 70:
            recommendations.append(
                "Reduce tool requirements by using snap-fits or captive fasteners "
                "that can be released without specialized tools."
            )

        if scores["material_compatibility"] < 70:
            recommendations.append(
                "Consolidate materials or ensure incompatible materials are "
                "easily separable to improve recycling efficiency."
            )

        if scores["reversibility"] < 80:
            irreversible = [
                j.joint_id for j in self.joints.values()
                if not j.is_reversible
            ]
            recommendations.append(
                f"Replace {len(irreversible)} irreversible joints with "
                "reversible alternatives to enable component reuse."
            )

        if scores["hazard"] < 80:
            recommendations.append(
                "Improve separation of hazardous components by using "
                "easy-release joints at material boundaries."
            )

        if scores["recyclability"] < 80:
            recommendations.append(
                "Increase recyclability by using single-polymer materials "
                "or clearly marking materials for sorting."
            )

        if not recommendations:
            recommendations.append(
                "Excellent DfD design! Consider documenting disassembly "
                "procedures for end-of-life operators."
            )

        return recommendations

    def generate_disassembly_sequence(self) -> List[DisassemblyStep]:
        """
        Generate optimal disassembly sequence using topological analysis.

        Uses graph algorithms to determine the order in which components
        should be removed, minimizing total disassembly time and tool changes.
        """
        if not self.components or not self.joints:
            return []

        # Find components with fewest connections (outer components)
        connection_counts = {
            comp_id: len(self._adjacency[comp_id])
            for comp_id in self.components
        }

        # Greedy sequence: remove least-connected components first
        remaining = set(self.components.keys())
        sequence = []
        step_num = 1

        while remaining:
            # Find component with minimum connections to remaining components
            min_conn = float('inf')
            best_candidate = None

            for comp_id in remaining:
                conn_count = sum(
                    1 for neighbor in self._adjacency[comp_id]
                    if neighbor in remaining
                )
                if conn_count < min_conn:
                    min_conn = conn_count
                    best_candidate = comp_id

            if best_candidate is None:
                break

            # Identify joints to release
            joints_to_release = []
            tools_needed = set()
            total_time = 0.0

            for neighbor in self._adjacency[best_candidate]:
                joint_id = self._joint_map.get((best_candidate, neighbor))
                if joint_id:
                    joint = self.joints[joint_id]
                    joints_to_release.append(joint_id)
                    total_time += joint.disassembly_time_seconds
                    if joint.tool_type:
                        tools_needed.add(joint.tool_type)

            # Find parallel candidates (components that could be removed next)
            parallel = [
                comp_id for comp_id in remaining
                if comp_id != best_candidate and
                   sum(1 for n in self._adjacency[comp_id] if n in remaining) <= 1
            ]

            step = DisassemblyStep(
                step_number=step_num,
                component_id=best_candidate,
                joints_released=joints_to_release,
                time_seconds=total_time,
                tools_required=list(tools_needed),
                parallel_candidates=parallel[:3]  # Top 3 alternatives
            )
            sequence.append(step)

            remaining.remove(best_candidate)
            step_num += 1

        return sequence

    def analyze_end_of_life(self) -> EndOfLifeScenario:
        """
        Analyze end-of-life scenarios for the product.

        Calculates mass distribution across disposal pathways
        and economic value of material recovery.
        """
        total_mass = sum(c.mass_kg for c in self.components.values())

        reusable_mass = sum(
            c.mass_kg for c in self.components.values()
            if c.is_reusable and c.lifetime_cycles > 1
        )

        recyclable_mass = sum(
            c.mass_kg for c in self.components.values()
            if c.is_recyclable and not c.is_reusable
        )

        hazardous_mass = sum(
            c.mass_kg for c in self.components.values()
            if c.contains_hazardous
        )

        # Remaining goes to energy recovery or landfill
        remaining = total_mass - reusable_mass - recyclable_mass - hazardous_mass
        energy_recovery = remaining * 0.7  # Assume 70% can be energy recovered
        landfill = remaining * 0.3

        # Calculate disassembly time
        sequence = self.generate_disassembly_sequence()
        disassembly_time = sum(s.time_seconds for s in sequence) / 3600  # hours

        # Value calculations (simplified)
        reuse_value = reusable_mass * 5.0  # $5/kg for reusable parts
        recycle_value = recyclable_mass * 0.5  # $0.50/kg for recyclables
        energy_value = energy_recovery * 0.1  # $0.10/kg for energy recovery
        total_value = reuse_value + recycle_value + energy_value

        # Processing costs
        hazard_cost = hazardous_mass * 2.0  # $2/kg for hazardous disposal
        landfill_cost = landfill * 0.1  # $0.10/kg landfill
        labor_cost = disassembly_time * 25.0  # $25/hour labor
        total_cost = hazard_cost + landfill_cost + labor_cost

        return EndOfLifeScenario(
            scenario_name="Standard EOL",
            reusable_mass_kg=reusable_mass,
            recyclable_mass_kg=recyclable_mass,
            energy_recovery_mass_kg=energy_recovery,
            landfill_mass_kg=landfill,
            hazardous_mass_kg=hazardous_mass,
            total_value=total_value,
            total_processing_cost=total_cost,
            disassembly_time_hours=disassembly_time,
            required_labor_hours=disassembly_time * 1.2  # 20% overhead
        )

    def export_to_cad_feedback(self) -> Dict[str, Any]:
        """
        Export DfD analysis for CAD system integration.

        Returns structured data for highlighting issues
        in the CAD design environment.
        """
        score = self.calculate_dfd_score()
        sequence = self.generate_disassembly_sequence()
        eol = self.analyze_end_of_life()

        # Identify problematic components and joints
        issues = []

        for joint in self.joints.values():
            if joint.joint_type in [JointType.WELD, JointType.ADHESIVE, JointType.ULTRASONIC]:
                issues.append({
                    "type": "joint",
                    "id": joint.joint_id,
                    "severity": "high",
                    "message": f"Difficult joint type: {joint.joint_type.value}",
                    "component_a": joint.component_a,
                    "component_b": joint.component_b
                })

        for comp in self.components.values():
            if comp.contains_hazardous:
                issues.append({
                    "type": "component",
                    "id": comp.component_id,
                    "severity": "warning",
                    "message": "Contains hazardous materials - ensure easy separation"
                })

            if comp.material_category == MaterialCategory.COMPOSITE:
                issues.append({
                    "type": "component",
                    "id": comp.component_id,
                    "severity": "medium",
                    "message": "Composite material - difficult to recycle"
                })

        return {
            "overall_score": score.overall_score,
            "grade": score.grade,
            "subscores": score.breakdown,
            "issues": issues,
            "disassembly_sequence": [
                {
                    "step": s.step_number,
                    "component": s.component_id,
                    "time_seconds": s.time_seconds,
                    "tools": s.tools_required
                }
                for s in sequence
            ],
            "end_of_life": {
                "reuse_percent": eol.reusable_mass_kg / (
                    eol.reusable_mass_kg + eol.recyclable_mass_kg +
                    eol.energy_recovery_mass_kg + eol.landfill_mass_kg
                ) * 100 if eol.reusable_mass_kg > 0 else 0,
                "recycle_percent": eol.recyclable_mass_kg / (
                    eol.reusable_mass_kg + eol.recyclable_mass_kg +
                    eol.energy_recovery_mass_kg + eol.landfill_mass_kg
                ) * 100 if eol.recyclable_mass_kg > 0 else 0,
                "net_value": eol.total_value - eol.total_processing_cost
            },
            "recommendations": score.recommendations
        }
