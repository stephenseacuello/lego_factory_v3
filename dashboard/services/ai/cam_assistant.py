"""
CAM Assistant - AI-Powered CAM Parameter Optimization

LEGO MCP World-Class Manufacturing System v6.0
Phase 18: AI CAM Copilot

Multi-mode AI assistant for CAM operations:
- AUTONOMOUS: AI decides and executes without user intervention
- COPILOT: AI suggests parameters, user approves before execution
- ADVISORY: AI explains options, user makes all decisions

Integrates with:
- Quality defect history for learning
- Material database for optimal parameters
- Machine profiles for capability matching
- MCP tools for Fusion 360 execution
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json
import hashlib

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

logger = logging.getLogger(__name__)


class CAMMode(str, Enum):
    """Operating modes for AI CAM assistance."""
    AUTONOMOUS = "autonomous"  # AI decides and executes
    COPILOT = "copilot"       # AI suggests, user approves
    ADVISORY = "advisory"      # AI explains, user configures


class MaterialType(str, Enum):
    """Supported material types."""
    PLA = "pla"
    ABS = "abs"
    PETG = "petg"
    TPU = "tpu"
    NYLON = "nylon"
    PC = "polycarbonate"
    ASA = "asa"
    # CNC Materials
    ALUMINUM_6061 = "aluminum_6061"
    ALUMINUM_7075 = "aluminum_7075"
    STEEL_1018 = "steel_1018"
    BRASS = "brass"
    DELRIN = "delrin"
    HDPE = "hdpe"


class OperationType(str, Enum):
    """CAM operation types."""
    FACING = "facing"
    POCKET = "pocket"
    CONTOUR = "contour"
    DRILLING = "drilling"
    ADAPTIVE = "adaptive"
    SLOT = "slot"
    CHAMFER = "chamfer"
    # 3D Printing
    PRINT = "print"
    SUPPORT = "support"


@dataclass
class ToolRecommendation:
    """Recommended cutting tool configuration."""
    tool_type: str
    tool_diameter_mm: float
    flute_count: int
    material: str  # Tool material (HSS, Carbide, etc.)
    coating: Optional[str] = None
    rationale: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FeedSpeedRecommendation:
    """Recommended feed and speed parameters."""
    spindle_rpm: int
    feed_rate_mm_min: float
    plunge_rate_mm_min: float
    depth_of_cut_mm: float
    stepover_percent: float

    # Calculated values
    surface_speed_m_min: float = 0.0
    chip_load_mm: float = 0.0
    mrr_cm3_min: float = 0.0  # Material removal rate

    rationale: str = ""
    safety_margin: float = 0.8  # Operating at 80% of max


@dataclass
class ToolpathStrategy:
    """Recommended toolpath strategy."""
    strategy_type: str
    direction: str  # climb, conventional, or both
    lead_in_type: str
    lead_out_type: str
    smoothing_tolerance_mm: float

    # Advanced options
    high_speed_machining: bool = False
    rest_machining: bool = False

    rationale: str = ""


@dataclass
class CAMRecommendation:
    """Complete CAM recommendation from AI."""
    recommendation_id: str
    timestamp: datetime
    mode: CAMMode

    # Component info
    component_name: str
    brick_type: str
    dimensions: Dict[str, float]
    material: MaterialType
    machine_id: str

    # Recommendations
    tool: ToolRecommendation
    feeds_speeds: FeedSpeedRecommendation
    toolpath: ToolpathStrategy
    operations: List[Dict[str, Any]]

    # AI metadata
    confidence: float
    rationale: str
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Quality feedback integration
    defect_adjustments: Dict[str, Any] = field(default_factory=dict)
    learning_applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'recommendation_id': self.recommendation_id,
            'timestamp': self.timestamp.isoformat(),
            'mode': self.mode.value,
            'component': {
                'name': self.component_name,
                'brick_type': self.brick_type,
                'dimensions': self.dimensions,
                'material': self.material.value,
            },
            'machine_id': self.machine_id,
            'tool': {
                'type': self.tool.tool_type,
                'diameter_mm': self.tool.tool_diameter_mm,
                'flutes': self.tool.flute_count,
                'material': self.tool.material,
                'coating': self.tool.coating,
                'rationale': self.tool.rationale,
            },
            'feeds_speeds': {
                'spindle_rpm': self.feeds_speeds.spindle_rpm,
                'feed_rate_mm_min': self.feeds_speeds.feed_rate_mm_min,
                'plunge_rate_mm_min': self.feeds_speeds.plunge_rate_mm_min,
                'depth_of_cut_mm': self.feeds_speeds.depth_of_cut_mm,
                'stepover_percent': self.feeds_speeds.stepover_percent,
                'surface_speed_m_min': self.feeds_speeds.surface_speed_m_min,
                'chip_load_mm': self.feeds_speeds.chip_load_mm,
                'mrr_cm3_min': self.feeds_speeds.mrr_cm3_min,
                'rationale': self.feeds_speeds.rationale,
            },
            'toolpath': {
                'strategy': self.toolpath.strategy_type,
                'direction': self.toolpath.direction,
                'lead_in': self.toolpath.lead_in_type,
                'lead_out': self.toolpath.lead_out_type,
                'hsm_enabled': self.toolpath.high_speed_machining,
                'rationale': self.toolpath.rationale,
            },
            'operations': self.operations,
            'confidence': self.confidence,
            'rationale': self.rationale,
            'alternatives': self.alternatives,
            'warnings': self.warnings,
            'learning': {
                'defect_adjustments': self.defect_adjustments,
                'learning_applied': self.learning_applied,
            }
        }


@dataclass
class CAMExecutionResult:
    """Result of CAM execution."""
    success: bool
    recommendation_id: str
    execution_time_ms: float

    # Results
    gcode_file: Optional[str] = None
    estimated_time_min: float = 0.0
    tool_changes: int = 0

    # Errors/warnings
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'recommendation_id': self.recommendation_id,
            'execution_time_ms': self.execution_time_ms,
            'gcode_file': self.gcode_file,
            'estimated_time_min': self.estimated_time_min,
            'tool_changes': self.tool_changes,
            'error': self.error_message,
            'warnings': self.warnings,
        }


class MaterialDatabase:
    """Database of material cutting properties."""

    MATERIALS = {
        MaterialType.ALUMINUM_6061: {
            'name': 'Aluminum 6061-T6',
            'surface_speed_range': (150, 300),  # m/min
            'chip_load_range': (0.05, 0.15),    # mm/tooth
            'max_doc_factor': 1.0,              # Relative to tool diameter
            'coolant': 'flood',
            'hardness_bhn': 95,
        },
        MaterialType.ALUMINUM_7075: {
            'name': 'Aluminum 7075-T6',
            'surface_speed_range': (120, 250),
            'chip_load_range': (0.04, 0.12),
            'max_doc_factor': 0.8,
            'coolant': 'flood',
            'hardness_bhn': 150,
        },
        MaterialType.BRASS: {
            'name': 'Brass (C360)',
            'surface_speed_range': (100, 200),
            'chip_load_range': (0.05, 0.15),
            'max_doc_factor': 1.0,
            'coolant': 'optional',
            'hardness_bhn': 78,
        },
        MaterialType.DELRIN: {
            'name': 'Delrin (Acetal)',
            'surface_speed_range': (200, 400),
            'chip_load_range': (0.1, 0.25),
            'max_doc_factor': 1.5,
            'coolant': 'air_blast',
            'hardness_bhn': 20,
        },
        MaterialType.HDPE: {
            'name': 'HDPE',
            'surface_speed_range': (250, 500),
            'chip_load_range': (0.1, 0.3),
            'max_doc_factor': 2.0,
            'coolant': 'none',
            'hardness_bhn': 10,
        },
    }

    @classmethod
    def get_properties(cls, material: MaterialType) -> Dict[str, Any]:
        return cls.MATERIALS.get(material, cls.MATERIALS[MaterialType.ALUMINUM_6061])


class MachineProfiles:
    """Machine capability profiles."""

    PROFILES = {
        'bantam-desktop-cnc': {
            'name': 'Bantam Tools Desktop CNC',
            'type': 'cnc_mill',
            'max_rpm': 26000,
            'min_rpm': 2000,
            'max_feed_rate': 2500,  # mm/min
            'max_z_rate': 1500,
            'work_envelope': {'x': 140, 'y': 114, 'z': 41},  # mm
            'spindle_power_w': 150,
            'tool_change': 'manual',
            'coolant': 'none',  # Air blast available
            'precision_mm': 0.003,
        },
        'prusa-mk4': {
            'name': 'Prusa MK4',
            'type': 'fdm_printer',
            'max_print_speed': 200,  # mm/s
            'max_volumetric_speed': 25,  # mm³/s
            'work_envelope': {'x': 250, 'y': 210, 'z': 220},
            'heated_bed': True,
            'max_bed_temp': 120,
            'max_hotend_temp': 300,
            'precision_mm': 0.1,
        },
        'bambu-x1c': {
            'name': 'Bambu Lab X1 Carbon',
            'type': 'fdm_printer',
            'max_print_speed': 500,
            'max_volumetric_speed': 32,
            'work_envelope': {'x': 256, 'y': 256, 'z': 256},
            'heated_bed': True,
            'max_bed_temp': 120,
            'max_hotend_temp': 300,
            'precision_mm': 0.05,
            'ams': True,
        },
    }

    @classmethod
    def get_profile(cls, machine_id: str) -> Dict[str, Any]:
        return cls.PROFILES.get(machine_id, cls.PROFILES['bantam-desktop-cnc'])


class DefectCAMMapping:
    """Maps defect types to CAM parameter adjustments."""

    MAPPINGS = {
        'undersized_stud': {
            'description': 'Stud diameter too small',
            'adjustments': {
                'stepover_percent': -5,  # Decrease stepover
                'feed_rate_factor': 0.95,
            },
            'root_cause': 'Tool deflection or excessive stepover',
        },
        'oversized_stud': {
            'description': 'Stud diameter too large',
            'adjustments': {
                'stepover_percent': +3,
                'depth_of_cut_factor': 0.9,
            },
            'root_cause': 'Tool rubbing or insufficient stepover',
        },
        'rough_surface': {
            'description': 'Surface finish below spec',
            'adjustments': {
                'stepover_percent': -10,
                'feed_rate_factor': 0.85,
                'spindle_rpm_factor': 1.1,
            },
            'root_cause': 'High feed rate or tool wear',
        },
        'chatter_marks': {
            'description': 'Vibration-induced surface marks',
            'adjustments': {
                'depth_of_cut_factor': 0.7,
                'spindle_rpm_factor': 0.9,
            },
            'root_cause': 'Resonance at current parameters',
        },
        'burrs': {
            'description': 'Excessive burr formation',
            'adjustments': {
                'chip_load_factor': 1.1,
                'direction': 'climb',
            },
            'root_cause': 'Low feed or conventional milling',
        },
        'dimensional_error': {
            'description': 'Part out of tolerance',
            'adjustments': {
                'stepover_percent': -5,
                'finishing_pass': True,
            },
            'root_cause': 'Tool deflection or thermal expansion',
        },
    }

    @classmethod
    def get_adjustments(cls, defect_type: str) -> Dict[str, Any]:
        return cls.MAPPINGS.get(defect_type, {})


@dataclass
class CAMAssistantConfig:
    """Configuration for the CAM Assistant."""
    api_key: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.2  # Low temp for precise recommendations
    default_mode: CAMMode = CAMMode.COPILOT
    auto_approve_threshold: float = 0.95
    apply_defect_learning: bool = True
    safety_margin: float = 0.8


class CAMAssistant:
    """
    AI-Powered CAM Parameter Optimizer.

    Provides intelligent CAM parameter recommendations with three operating modes:
    - AUTONOMOUS: Full automation for trusted operations
    - COPILOT: Suggestions with human approval
    - ADVISORY: Explanations for manual configuration
    """

    def __init__(self, config: Optional[CAMAssistantConfig] = None):
        self.config = config or CAMAssistantConfig()
        self.client = None

        if ANTHROPIC_AVAILABLE and self.config.api_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.config.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

        # Defect history for learning
        self._defect_history: List[Dict[str, Any]] = []

        logger.info(f"CAMAssistant initialized in {self.config.default_mode.value} mode")

    def _generate_recommendation_id(self, component_name: str, material: str) -> str:
        """Generate unique recommendation ID."""
        data = f"{component_name}{material}{datetime.utcnow().isoformat()}"
        return f"cam-{hashlib.sha256(data.encode()).hexdigest()[:12]}"

    async def recommend_cam_parameters(
        self,
        brick_type: str,
        dimensions: Dict[str, float],
        material: MaterialType,
        machine_id: str,
        operation_type: OperationType = OperationType.POCKET,
        mode: Optional[CAMMode] = None,
        quality_history: Optional[List[Dict[str, Any]]] = None,
        custom_constraints: Optional[Dict[str, Any]] = None,
    ) -> CAMRecommendation:
        """
        Generate AI-recommended CAM parameters.

        Args:
            brick_type: Type of LEGO brick (e.g., '2x4', '1x2')
            dimensions: Part dimensions in mm
            material: Material type
            machine_id: Target machine identifier
            operation_type: Type of machining operation
            mode: Operating mode (overrides default)
            quality_history: Past quality issues for learning
            custom_constraints: User-specified constraints

        Returns:
            Complete CAM recommendation
        """
        current_mode = mode or self.config.default_mode
        machine_profile = MachineProfiles.get_profile(machine_id)
        material_props = MaterialDatabase.get_properties(material)

        # Apply defect-based learning
        defect_adjustments = {}
        if self.config.apply_defect_learning and quality_history:
            defect_adjustments = self._analyze_defect_history(quality_history)

        # Calculate base parameters
        tool = self._select_tool(dimensions, material, machine_profile)
        feeds_speeds = self._calculate_feeds_speeds(
            tool, material_props, machine_profile, defect_adjustments
        )
        toolpath = self._select_toolpath_strategy(
            operation_type, material, dimensions, defect_adjustments
        )

        # Generate operations sequence
        operations = self._generate_operations(
            brick_type, dimensions, operation_type, tool
        )

        # Build rationale
        rationale = self._build_rationale(
            current_mode, material, machine_profile, defect_adjustments
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            material_props, machine_profile, defect_adjustments
        )

        # Generate warnings
        warnings = self._generate_warnings(
            dimensions, machine_profile, feeds_speeds
        )

        recommendation = CAMRecommendation(
            recommendation_id=self._generate_recommendation_id(
                f"LEGO-{brick_type}", material.value
            ),
            timestamp=datetime.utcnow(),
            mode=current_mode,
            component_name=f"LEGO-{brick_type}-Brick",
            brick_type=brick_type,
            dimensions=dimensions,
            material=material,
            machine_id=machine_id,
            tool=tool,
            feeds_speeds=feeds_speeds,
            toolpath=toolpath,
            operations=operations,
            confidence=confidence,
            rationale=rationale,
            alternatives=self._generate_alternatives(tool, feeds_speeds),
            warnings=warnings,
            defect_adjustments=defect_adjustments,
            learning_applied=bool(defect_adjustments),
        )

        logger.info(
            f"Generated CAM recommendation {recommendation.recommendation_id} "
            f"with {confidence:.1%} confidence"
        )

        return recommendation

    def _select_tool(
        self,
        dimensions: Dict[str, float],
        material: MaterialType,
        machine_profile: Dict[str, Any]
    ) -> ToolRecommendation:
        """Select optimal cutting tool."""
        # Determine tool diameter based on smallest feature
        min_feature = min(dimensions.values())

        # Tool should be ~1/3 of smallest feature for good detail
        ideal_diameter = min(min_feature / 3, 6.35)  # Max 1/4"

        # Round to standard sizes
        standard_sizes = [1.0, 1.5, 2.0, 3.0, 3.175, 4.0, 6.0, 6.35]
        tool_diameter = min(standard_sizes, key=lambda x: abs(x - ideal_diameter))

        # Select tool material based on workpiece
        is_metal = material in [
            MaterialType.ALUMINUM_6061, MaterialType.ALUMINUM_7075,
            MaterialType.BRASS, MaterialType.STEEL_1018
        ]
        tool_material = "Carbide" if is_metal else "HSS"
        coating = "TiAlN" if is_metal else None

        # Flute count
        flute_count = 2 if material in [MaterialType.ALUMINUM_6061, MaterialType.ALUMINUM_7075] else 3

        return ToolRecommendation(
            tool_type="Flat End Mill",
            tool_diameter_mm=tool_diameter,
            flute_count=flute_count,
            material=tool_material,
            coating=coating,
            rationale=f"{tool_diameter}mm {flute_count}-flute {tool_material} end mill selected "
                      f"for {material.value} based on feature size {min_feature:.1f}mm",
            alternatives=[
                {'diameter_mm': s, 'reason': 'Alternative standard size'}
                for s in standard_sizes if abs(s - tool_diameter) < 2
            ]
        )

    def _calculate_feeds_speeds(
        self,
        tool: ToolRecommendation,
        material_props: Dict[str, Any],
        machine_profile: Dict[str, Any],
        defect_adjustments: Dict[str, Any]
    ) -> FeedSpeedRecommendation:
        """Calculate optimal feeds and speeds."""
        import math

        # Get material ranges
        sfm_min, sfm_max = material_props['surface_speed_range']
        cl_min, cl_max = material_props['chip_load_range']

        # Start with conservative middle values
        target_sfm = (sfm_min + sfm_max) / 2 * self.config.safety_margin
        target_chip_load = (cl_min + cl_max) / 2 * self.config.safety_margin

        # Apply defect adjustments
        if 'spindle_rpm_factor' in defect_adjustments:
            target_sfm *= defect_adjustments['spindle_rpm_factor']
        if 'chip_load_factor' in defect_adjustments:
            target_chip_load *= defect_adjustments['chip_load_factor']

        # Calculate RPM from surface speed
        rpm = (target_sfm * 1000) / (math.pi * tool.tool_diameter_mm)
        rpm = min(rpm, machine_profile['max_rpm'])
        rpm = max(rpm, machine_profile.get('min_rpm', 1000))
        rpm = round(rpm / 100) * 100  # Round to nearest 100

        # Calculate feed rate
        feed_rate = rpm * tool.flute_count * target_chip_load
        feed_rate = min(feed_rate, machine_profile['max_feed_rate'])

        # Apply feed rate adjustment
        if 'feed_rate_factor' in defect_adjustments:
            feed_rate *= defect_adjustments['feed_rate_factor']

        # Depth of cut
        max_doc = tool.tool_diameter_mm * material_props['max_doc_factor']
        doc = max_doc * self.config.safety_margin
        if 'depth_of_cut_factor' in defect_adjustments:
            doc *= defect_adjustments['depth_of_cut_factor']

        # Stepover
        base_stepover = 40  # 40% for roughing
        if 'stepover_percent' in defect_adjustments:
            base_stepover += defect_adjustments['stepover_percent']

        # Calculate actual values
        actual_sfm = (rpm * math.pi * tool.tool_diameter_mm) / 1000
        actual_chip_load = feed_rate / (rpm * tool.flute_count)
        mrr = (tool.tool_diameter_mm * (base_stepover/100) * doc * feed_rate) / 1000000

        return FeedSpeedRecommendation(
            spindle_rpm=int(rpm),
            feed_rate_mm_min=round(feed_rate, 1),
            plunge_rate_mm_min=round(feed_rate * 0.3, 1),
            depth_of_cut_mm=round(doc, 2),
            stepover_percent=base_stepover,
            surface_speed_m_min=round(actual_sfm, 1),
            chip_load_mm=round(actual_chip_load, 4),
            mrr_cm3_min=round(mrr, 3),
            rationale=f"RPM {int(rpm)} ({actual_sfm:.0f}m/min SFM), "
                      f"Feed {feed_rate:.0f}mm/min ({actual_chip_load:.3f}mm chip load), "
                      f"DOC {doc:.2f}mm, {base_stepover}% stepover",
            safety_margin=self.config.safety_margin
        )

    def _select_toolpath_strategy(
        self,
        operation_type: OperationType,
        material: MaterialType,
        dimensions: Dict[str, float],
        defect_adjustments: Dict[str, Any]
    ) -> ToolpathStrategy:
        """Select optimal toolpath strategy."""
        # Default to climb milling for better finish
        direction = defect_adjustments.get('direction', 'climb')

        # Strategy based on operation
        strategies = {
            OperationType.POCKET: 'adaptive',
            OperationType.CONTOUR: 'profile',
            OperationType.FACING: 'spiral',
            OperationType.ADAPTIVE: 'adaptive',
            OperationType.SLOT: 'trochoidal',
        }
        strategy = strategies.get(operation_type, 'adaptive')

        # HSM for aluminum
        hsm = material in [MaterialType.ALUMINUM_6061, MaterialType.ALUMINUM_7075]

        return ToolpathStrategy(
            strategy_type=strategy,
            direction=direction,
            lead_in_type='arc',
            lead_out_type='arc',
            smoothing_tolerance_mm=0.01,
            high_speed_machining=hsm,
            rest_machining=False,
            rationale=f"{strategy.title()} strategy with {direction} milling, "
                      f"HSM {'enabled' if hsm else 'disabled'}"
        )

    def _generate_operations(
        self,
        brick_type: str,
        dimensions: Dict[str, float],
        operation_type: OperationType,
        tool: ToolRecommendation
    ) -> List[Dict[str, Any]]:
        """Generate machining operations sequence."""
        operations = []

        # Facing operation
        if operation_type in [OperationType.FACING, OperationType.POCKET]:
            operations.append({
                'sequence': 1,
                'name': 'Face Top Surface',
                'type': 'facing',
                'tool': tool.tool_type,
                'depth': 0.5,
            })

        # Main pocket for brick cavity
        operations.append({
            'sequence': 2,
            'name': 'Rough Pocket - Brick Cavity',
            'type': 'adaptive_pocket',
            'tool': tool.tool_type,
            'depth': dimensions.get('z', 10) - 2,
            'stock_to_leave': 0.2,
        })

        # Finishing pass
        operations.append({
            'sequence': 3,
            'name': 'Finish Pocket Walls',
            'type': 'contour',
            'tool': tool.tool_type,
            'stock_to_leave': 0.0,
        })

        # Stud pockets
        stud_count = self._parse_brick_studs(brick_type)
        if stud_count > 0:
            operations.append({
                'sequence': 4,
                'name': f'Drill Stud Pockets ({stud_count}x)',
                'type': 'circular_pocket',
                'tool': tool.tool_type,
                'count': stud_count,
                'diameter': 4.8,  # LEGO stud inner diameter
            })

        return operations

    def _parse_brick_studs(self, brick_type: str) -> int:
        """Parse brick type to get stud count."""
        try:
            parts = brick_type.lower().replace('x', ' ').split()
            if len(parts) >= 2:
                return int(parts[0]) * int(parts[1])
        except:
            pass
        return 0

    def _analyze_defect_history(
        self,
        quality_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze defect history and return parameter adjustments."""
        adjustments = {}

        for defect in quality_history:
            defect_type = defect.get('type', '').lower().replace(' ', '_')
            mapping = DefectCAMMapping.get_adjustments(defect_type)

            if mapping and 'adjustments' in mapping:
                for key, value in mapping['adjustments'].items():
                    if key in adjustments:
                        # Accumulate adjustments
                        if isinstance(value, (int, float)):
                            adjustments[key] = (adjustments[key] + value) / 2
                    else:
                        adjustments[key] = value

        if adjustments:
            logger.info(f"Applied defect learning adjustments: {adjustments}")

        return adjustments

    def _build_rationale(
        self,
        mode: CAMMode,
        material: MaterialType,
        machine_profile: Dict[str, Any],
        defect_adjustments: Dict[str, Any]
    ) -> str:
        """Build human-readable rationale for recommendations."""
        parts = [
            f"Parameters optimized for {material.value} on {machine_profile['name']}.",
        ]

        if defect_adjustments:
            parts.append(
                f"Adjusted based on {len(defect_adjustments)} defect-learned parameters."
            )

        mode_descriptions = {
            CAMMode.AUTONOMOUS: "Operating in autonomous mode - will execute without confirmation.",
            CAMMode.COPILOT: "Operating in copilot mode - review and approve before execution.",
            CAMMode.ADVISORY: "Operating in advisory mode - parameters provided for manual setup.",
        }
        parts.append(mode_descriptions[mode])

        return " ".join(parts)

    def _calculate_confidence(
        self,
        material_props: Dict[str, Any],
        machine_profile: Dict[str, Any],
        defect_adjustments: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for recommendation."""
        base_confidence = 0.85

        # Boost for common materials
        if material_props.get('hardness_bhn', 100) < 100:
            base_confidence += 0.05

        # Boost for defect learning
        if defect_adjustments:
            base_confidence += 0.05

        # Penalty for high-power requirements
        if machine_profile.get('spindle_power_w', 500) < 200:
            base_confidence -= 0.05

        return min(0.98, max(0.5, base_confidence))

    def _generate_warnings(
        self,
        dimensions: Dict[str, float],
        machine_profile: Dict[str, Any],
        feeds_speeds: FeedSpeedRecommendation
    ) -> List[str]:
        """Generate safety and capability warnings."""
        warnings = []

        # Check work envelope
        envelope = machine_profile.get('work_envelope', {})
        for axis, size in dimensions.items():
            if axis in envelope and size > envelope[axis]:
                warnings.append(
                    f"Part {axis.upper()} dimension ({size}mm) exceeds "
                    f"machine capability ({envelope[axis]}mm)"
                )

        # Check spindle speed
        if feeds_speeds.spindle_rpm >= machine_profile.get('max_rpm', 30000) * 0.95:
            warnings.append("Operating near maximum spindle speed")

        return warnings

    def _generate_alternatives(
        self,
        tool: ToolRecommendation,
        feeds_speeds: FeedSpeedRecommendation
    ) -> List[Dict[str, Any]]:
        """Generate alternative parameter sets."""
        return [
            {
                'name': 'Conservative',
                'description': 'Lower speeds for safer operation',
                'rpm': int(feeds_speeds.spindle_rpm * 0.8),
                'feed_rate': round(feeds_speeds.feed_rate_mm_min * 0.8, 1),
                'doc': round(feeds_speeds.depth_of_cut_mm * 0.7, 2),
            },
            {
                'name': 'Aggressive',
                'description': 'Higher speeds for faster machining',
                'rpm': int(min(feeds_speeds.spindle_rpm * 1.2, 26000)),
                'feed_rate': round(feeds_speeds.feed_rate_mm_min * 1.2, 1),
                'doc': round(feeds_speeds.depth_of_cut_mm * 1.1, 2),
            },
        ]

    async def execute_autonomous(
        self,
        recommendation: CAMRecommendation,
        mcp_bridge: Optional[Any] = None,
    ) -> CAMExecutionResult:
        """
        Execute CAM recommendation autonomously.

        Only available in AUTONOMOUS mode or with explicit approval.
        """
        start_time = datetime.utcnow()

        if recommendation.mode != CAMMode.AUTONOMOUS:
            return CAMExecutionResult(
                success=False,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=0,
                error_message="Autonomous execution requires AUTONOMOUS mode",
            )

        if recommendation.confidence < self.config.auto_approve_threshold:
            return CAMExecutionResult(
                success=False,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=0,
                error_message=f"Confidence {recommendation.confidence:.1%} below "
                              f"threshold {self.config.auto_approve_threshold:.1%}",
            )

        try:
            # In a real implementation, this would call MCP tools
            logger.info(f"Executing autonomous CAM: {recommendation.recommendation_id}")

            # Simulate execution
            await asyncio.sleep(0.1)

            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            return CAMExecutionResult(
                success=True,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=elapsed,
                gcode_file=f"/output/{recommendation.component_name}.nc",
                estimated_time_min=15.5,
                tool_changes=1,
                warnings=recommendation.warnings,
            )

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CAMExecutionResult(
                success=False,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=elapsed,
                error_message=str(e),
            )

    async def execute_with_approval(
        self,
        recommendation: CAMRecommendation,
        user_approved: bool,
        mcp_bridge: Optional[Any] = None,
    ) -> CAMExecutionResult:
        """
        Execute CAM recommendation with user approval (COPILOT mode).
        """
        if not user_approved:
            return CAMExecutionResult(
                success=False,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=0,
                error_message="User did not approve execution",
            )

        # Proceed with execution
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"Executing approved CAM: {recommendation.recommendation_id}"
            )

            # Simulate execution
            await asyncio.sleep(0.1)

            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            return CAMExecutionResult(
                success=True,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=elapsed,
                gcode_file=f"/output/{recommendation.component_name}.nc",
                estimated_time_min=15.5,
                tool_changes=1,
            )

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CAMExecutionResult(
                success=False,
                recommendation_id=recommendation.recommendation_id,
                execution_time_ms=elapsed,
                error_message=str(e),
            )

    def record_quality_feedback(
        self,
        recommendation_id: str,
        defect_type: str,
        severity: str,
        notes: Optional[str] = None
    ) -> None:
        """Record quality feedback for learning."""
        feedback = {
            'recommendation_id': recommendation_id,
            'defect_type': defect_type,
            'severity': severity,
            'notes': notes,
            'timestamp': datetime.utcnow().isoformat(),
        }
        self._defect_history.append(feedback)
        logger.info(f"Recorded quality feedback: {defect_type} ({severity})")

    def get_mode_description(self, mode: CAMMode) -> Dict[str, Any]:
        """Get description of operating mode."""
        descriptions = {
            CAMMode.AUTONOMOUS: {
                'name': 'Autonomous',
                'description': 'AI makes all decisions and executes without user intervention',
                'user_interaction': 'None - fully automated',
                'best_for': 'Repetitive, well-understood operations',
                'risks': 'Errors execute automatically',
                'confidence_threshold': self.config.auto_approve_threshold,
            },
            CAMMode.COPILOT: {
                'name': 'Copilot',
                'description': 'AI recommends parameters, user reviews and approves',
                'user_interaction': 'Review and approve/reject',
                'best_for': 'Most operations - balances efficiency with oversight',
                'risks': 'Low - human verification required',
                'confidence_threshold': 0.0,  # Any confidence allows suggestion
            },
            CAMMode.ADVISORY: {
                'name': 'Advisory',
                'description': 'AI explains options, user makes all configuration decisions',
                'user_interaction': 'Manual configuration with AI guidance',
                'best_for': 'New materials, learning, or critical operations',
                'risks': 'Lowest - full user control',
                'confidence_threshold': 0.0,
            },
        }
        return descriptions.get(mode, descriptions[CAMMode.COPILOT])


# Factory function
def create_cam_assistant(
    mode: CAMMode = CAMMode.COPILOT,
    api_key: Optional[str] = None
) -> CAMAssistant:
    """Create a CAM Assistant with specified mode."""
    import os
    config = CAMAssistantConfig(
        api_key=api_key or os.environ.get('ANTHROPIC_API_KEY'),
        default_mode=mode,
    )
    return CAMAssistant(config)
