"""
Parameter Adjuster - LEGO-Specific Automatic Parameter Optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning

This module provides intelligent parameter adjustment for 3D printed LEGO bricks
with domain-specific rules for:
- Material-specific temperature, speed, and flow profiles
- Brick feature-based adjustments (studs, tubes, walls, ribs)
- Defect-specific correction rules
- Clutch power optimization (0.08-0.15mm interference)
- Dimensional accuracy targeting LEGO specs (4.8mm studs, 6.51mm tubes)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


# === LEGO-Specific Enums ===

class LEGOMaterial(Enum):
    """Supported materials for LEGO brick printing."""
    PLA = "pla"
    PETG = "petg"
    ABS = "abs"
    ASA = "asa"
    TPU = "tpu"  # For flexible parts


class LEGOBrickType(Enum):
    """Types of LEGO brick features requiring different parameters."""
    STANDARD = "standard"
    PLATE = "plate"
    TILE = "tile"
    TECHNIC = "technic"
    SLOPE = "slope"
    BASEPLATE = "baseplate"
    DUPLO = "duplo"


class LEGOFeature(Enum):
    """Specific features within a LEGO brick."""
    STUD = "stud"
    TUBE = "tube"
    WALL = "wall"
    RIB = "rib"
    TOP_SURFACE = "top_surface"
    BOTTOM_SURFACE = "bottom_surface"
    TECHNIC_HOLE = "technic_hole"
    SLOPE_SURFACE = "slope_surface"


class LEGODefectType(Enum):
    """LEGO-specific defect types."""
    STUD_FIT_LOOSE = "stud_fit_loose"
    STUD_FIT_TIGHT = "stud_fit_tight"
    CLUTCH_WEAK = "clutch_weak"
    CLUTCH_STRONG = "clutch_strong"
    DIMENSIONAL_ERROR = "dimensional_error"
    WARPING = "warping"
    STRINGING = "stringing"
    LAYER_ADHESION = "layer_adhesion"
    UNDER_EXTRUSION = "under_extrusion"
    OVER_EXTRUSION = "over_extrusion"
    SURFACE_ROUGH = "surface_rough"
    LAYER_LINES = "layer_lines"
    ELEPHANT_FOOT = "elephant_foot"
    Z_BANDING = "z_banding"


class PrintPhase(Enum):
    """Phases of the print with different parameter requirements."""
    FIRST_LAYER = "first_layer"
    BOTTOM_LAYERS = "bottom_layers"
    STRUCTURAL = "structural"
    DECORATIVE = "decorative"
    TOP_LAYERS = "top_layers"
    STUDS = "studs"
    TUBES = "tubes"


class AdjustmentPriority(Enum):
    """Priority levels for adjustments."""
    CRITICAL = 1  # Safety or major quality issue
    HIGH = 2      # Significant quality improvement
    MEDIUM = 3    # Moderate improvement
    LOW = 4       # Minor optimization


# === LEGO Specifications Constants ===

class LEGOSpecs:
    """LEGO dimensional specifications for parameter targeting."""
    # Core dimensions (mm)
    STUD_DIAMETER = 4.8
    STUD_HEIGHT = 1.7
    STUD_PITCH = 8.0
    TUBE_OUTER_DIAMETER = 6.51
    TUBE_INNER_DIAMETER = 4.8
    WALL_THICKNESS = 1.6
    BRICK_HEIGHT = 9.6
    PLATE_HEIGHT = 3.2
    TOP_THICKNESS = 1.0

    # Tolerances
    STUD_TOLERANCE = 0.02  # Critical for clutch power
    TUBE_TOLERANCE = 0.03
    GENERAL_TOLERANCE = 0.10

    # Clutch power interference range (mm)
    CLUTCH_INTERFERENCE_MIN = 0.08
    CLUTCH_INTERFERENCE_MAX = 0.15
    CLUTCH_INTERFERENCE_OPTIMAL = 0.12


# === Material Profiles ===

@dataclass
class MaterialProfile:
    """Material-specific printing parameters for LEGO bricks."""
    material: LEGOMaterial
    name: str

    # Temperature settings (°C)
    nozzle_temp_min: float
    nozzle_temp_max: float
    nozzle_temp_default: float
    bed_temp_min: float
    bed_temp_max: float
    bed_temp_default: float

    # Speed settings (mm/s)
    print_speed_min: float
    print_speed_max: float
    print_speed_default: float
    stud_speed_factor: float = 0.5  # Slower for studs (50%)

    # Flow settings (%)
    flow_rate_min: float = 90.0
    flow_rate_max: float = 110.0
    flow_rate_default: float = 100.0

    # Cooling (%)
    fan_speed_min: float = 0.0
    fan_speed_max: float = 100.0
    fan_speed_default: float = 100.0
    fan_first_layer: float = 0.0  # Off for first layer

    # Retraction
    retraction_distance: float = 0.8
    retraction_speed: float = 45.0

    # Material properties
    shrinkage_factor: float = 1.0  # Multiply dimensions
    density: float = 1.0  # g/cm³

    # Recommended for LEGO
    lego_suitability: float = 0.8  # 0-1 score


# Default material profiles optimized for LEGO brick printing
MATERIAL_PROFILES: Dict[LEGOMaterial, MaterialProfile] = {
    LEGOMaterial.PLA: MaterialProfile(
        material=LEGOMaterial.PLA,
        name="PLA (Standard LEGO)",
        nozzle_temp_min=190.0, nozzle_temp_max=230.0, nozzle_temp_default=210.0,
        bed_temp_min=50.0, bed_temp_max=70.0, bed_temp_default=60.0,
        print_speed_min=30.0, print_speed_max=100.0, print_speed_default=50.0,
        stud_speed_factor=0.5,
        flow_rate_min=95.0, flow_rate_max=105.0, flow_rate_default=100.0,
        fan_speed_default=100.0, fan_first_layer=0.0,
        retraction_distance=0.8, retraction_speed=45.0,
        shrinkage_factor=1.002, density=1.24,
        lego_suitability=0.85
    ),
    LEGOMaterial.PETG: MaterialProfile(
        material=LEGOMaterial.PETG,
        name="PETG (Best for LEGO clutch)",
        nozzle_temp_min=220.0, nozzle_temp_max=260.0, nozzle_temp_default=240.0,
        bed_temp_min=70.0, bed_temp_max=90.0, bed_temp_default=80.0,
        print_speed_min=25.0, print_speed_max=80.0, print_speed_default=40.0,
        stud_speed_factor=0.4,  # Even slower for studs
        flow_rate_min=92.0, flow_rate_max=108.0, flow_rate_default=98.0,
        fan_speed_default=50.0, fan_first_layer=0.0,  # Less cooling
        retraction_distance=1.0, retraction_speed=35.0,  # Slower retraction
        shrinkage_factor=1.003, density=1.27,
        lego_suitability=0.95  # Best for LEGO
    ),
    LEGOMaterial.ABS: MaterialProfile(
        material=LEGOMaterial.ABS,
        name="ABS (Original LEGO material)",
        nozzle_temp_min=220.0, nozzle_temp_max=270.0, nozzle_temp_default=245.0,
        bed_temp_min=90.0, bed_temp_max=110.0, bed_temp_default=100.0,
        print_speed_min=30.0, print_speed_max=80.0, print_speed_default=45.0,
        stud_speed_factor=0.5,
        flow_rate_min=95.0, flow_rate_max=110.0, flow_rate_default=102.0,
        fan_speed_default=30.0, fan_first_layer=0.0,  # Minimal cooling
        retraction_distance=0.6, retraction_speed=40.0,
        shrinkage_factor=1.005, density=1.05,
        lego_suitability=0.90  # Requires enclosure
    ),
    LEGOMaterial.ASA: MaterialProfile(
        material=LEGOMaterial.ASA,
        name="ASA (UV resistant outdoor)",
        nozzle_temp_min=235.0, nozzle_temp_max=280.0, nozzle_temp_default=260.0,
        bed_temp_min=95.0, bed_temp_max=115.0, bed_temp_default=105.0,
        print_speed_min=25.0, print_speed_max=70.0, print_speed_default=40.0,
        stud_speed_factor=0.45,
        flow_rate_min=95.0, flow_rate_max=110.0, flow_rate_default=100.0,
        fan_speed_default=20.0, fan_first_layer=0.0,
        retraction_distance=0.6, retraction_speed=40.0,
        shrinkage_factor=1.005, density=1.07,
        lego_suitability=0.88
    ),
    LEGOMaterial.TPU: MaterialProfile(
        material=LEGOMaterial.TPU,
        name="TPU (Flexible LEGO parts)",
        nozzle_temp_min=210.0, nozzle_temp_max=250.0, nozzle_temp_default=230.0,
        bed_temp_min=40.0, bed_temp_max=60.0, bed_temp_default=50.0,
        print_speed_min=15.0, print_speed_max=40.0, print_speed_default=25.0,
        stud_speed_factor=0.6,
        flow_rate_min=100.0, flow_rate_max=115.0, flow_rate_default=105.0,
        fan_speed_default=50.0, fan_first_layer=0.0,
        retraction_distance=0.0, retraction_speed=25.0,  # Direct drive only
        shrinkage_factor=1.001, density=1.21,
        lego_suitability=0.60  # Limited clutch power
    ),
}


# === Defect Correction Rules ===

@dataclass
class DefectCorrectionRule:
    """Rule for correcting a specific defect type."""
    defect_type: LEGODefectType
    description: str
    parameter_adjustments: Dict[str, Tuple[str, float]]  # param -> (direction, amount)
    priority: AdjustmentPriority = AdjustmentPriority.MEDIUM
    requires_cooldown: bool = False  # Wait between applications
    max_applications: int = 5  # Maximum times to apply


# LEGO-specific defect correction rules based on manufacturing expertise
DEFECT_CORRECTION_RULES: Dict[LEGODefectType, DefectCorrectionRule] = {
    LEGODefectType.STUD_FIT_LOOSE: DefectCorrectionRule(
        defect_type=LEGODefectType.STUD_FIT_LOOSE,
        description="Studs too small - bricks don't grip",
        parameter_adjustments={
            "flow_rate": ("increase", 2.0),
            "nozzle_temperature": ("increase", 5.0),
            "print_speed": ("decrease", 5.0),
        },
        priority=AdjustmentPriority.HIGH,
        max_applications=3
    ),
    LEGODefectType.STUD_FIT_TIGHT: DefectCorrectionRule(
        defect_type=LEGODefectType.STUD_FIT_TIGHT,
        description="Studs too large - difficult to connect",
        parameter_adjustments={
            "flow_rate": ("decrease", 2.0),
            "nozzle_temperature": ("decrease", 5.0),
            "xy_compensation": ("increase", 0.02),
        },
        priority=AdjustmentPriority.HIGH,
        max_applications=3
    ),
    LEGODefectType.CLUTCH_WEAK: DefectCorrectionRule(
        defect_type=LEGODefectType.CLUTCH_WEAK,
        description="Bricks don't hold together firmly",
        parameter_adjustments={
            "flow_rate": ("increase", 2.0),
            "nozzle_temperature": ("increase", 3.0),
            "print_speed": ("decrease", 10.0),  # More time for material flow
            "z_offset": ("decrease", 0.02),  # Closer first layer
        },
        priority=AdjustmentPriority.CRITICAL,
        max_applications=4
    ),
    LEGODefectType.CLUTCH_STRONG: DefectCorrectionRule(
        defect_type=LEGODefectType.CLUTCH_STRONG,
        description="Bricks too tight - hard to separate",
        parameter_adjustments={
            "flow_rate": ("decrease", 2.0),
            "xy_compensation": ("increase", 0.03),
        },
        priority=AdjustmentPriority.HIGH,
        max_applications=3
    ),
    LEGODefectType.DIMENSIONAL_ERROR: DefectCorrectionRule(
        defect_type=LEGODefectType.DIMENSIONAL_ERROR,
        description="Overall dimensions incorrect",
        parameter_adjustments={
            "flow_rate": ("adjust", 0.0),  # Calculated based on error
            "xy_compensation": ("adjust", 0.0),  # Calculated based on error
        },
        priority=AdjustmentPriority.HIGH,
        max_applications=5
    ),
    LEGODefectType.WARPING: DefectCorrectionRule(
        defect_type=LEGODefectType.WARPING,
        description="Part warping or lifting from bed",
        parameter_adjustments={
            "bed_temperature": ("increase", 5.0),
            "nozzle_temperature": ("decrease", 5.0),  # Less residual stress
            "fan_speed": ("decrease", 20.0),  # Slower cooling
            "print_speed": ("decrease", 10.0),
        },
        priority=AdjustmentPriority.CRITICAL,
        requires_cooldown=True,
        max_applications=4
    ),
    LEGODefectType.STRINGING: DefectCorrectionRule(
        defect_type=LEGODefectType.STRINGING,
        description="Fine strings between features (studs)",
        parameter_adjustments={
            "retraction_distance": ("increase", 0.2),
            "retraction_speed": ("increase", 5.0),
            "nozzle_temperature": ("decrease", 5.0),
            "travel_speed": ("increase", 20.0),
        },
        priority=AdjustmentPriority.MEDIUM,
        max_applications=4
    ),
    LEGODefectType.LAYER_ADHESION: DefectCorrectionRule(
        defect_type=LEGODefectType.LAYER_ADHESION,
        description="Layers separating or weak bonds",
        parameter_adjustments={
            "nozzle_temperature": ("increase", 10.0),
            "print_speed": ("decrease", 10.0),
            "fan_speed": ("decrease", 20.0),
            "layer_height": ("decrease", 0.02),
        },
        priority=AdjustmentPriority.CRITICAL,
        max_applications=3
    ),
    LEGODefectType.UNDER_EXTRUSION: DefectCorrectionRule(
        defect_type=LEGODefectType.UNDER_EXTRUSION,
        description="Not enough material being extruded",
        parameter_adjustments={
            "flow_rate": ("increase", 5.0),
            "nozzle_temperature": ("increase", 10.0),
            "print_speed": ("decrease", 15.0),
        },
        priority=AdjustmentPriority.HIGH,
        max_applications=3
    ),
    LEGODefectType.OVER_EXTRUSION: DefectCorrectionRule(
        defect_type=LEGODefectType.OVER_EXTRUSION,
        description="Too much material being extruded",
        parameter_adjustments={
            "flow_rate": ("decrease", 5.0),
            "nozzle_temperature": ("decrease", 5.0),
        },
        priority=AdjustmentPriority.MEDIUM,
        max_applications=3
    ),
    LEGODefectType.SURFACE_ROUGH: DefectCorrectionRule(
        defect_type=LEGODefectType.SURFACE_ROUGH,
        description="Rough surface finish on brick",
        parameter_adjustments={
            "print_speed": ("decrease", 10.0),
            "layer_height": ("decrease", 0.04),
            "nozzle_temperature": ("increase", 5.0),
        },
        priority=AdjustmentPriority.LOW,
        max_applications=3
    ),
    LEGODefectType.LAYER_LINES: DefectCorrectionRule(
        defect_type=LEGODefectType.LAYER_LINES,
        description="Visible layer lines on surface",
        parameter_adjustments={
            "layer_height": ("decrease", 0.04),
            "print_speed": ("decrease", 5.0),
        },
        priority=AdjustmentPriority.LOW,
        max_applications=2
    ),
    LEGODefectType.ELEPHANT_FOOT: DefectCorrectionRule(
        defect_type=LEGODefectType.ELEPHANT_FOOT,
        description="First layer bulges outward",
        parameter_adjustments={
            "z_offset": ("increase", 0.02),
            "bed_temperature": ("decrease", 5.0),
            "initial_layer_flow": ("decrease", 5.0),
        },
        priority=AdjustmentPriority.MEDIUM,
        max_applications=4
    ),
    LEGODefectType.Z_BANDING: DefectCorrectionRule(
        defect_type=LEGODefectType.Z_BANDING,
        description="Horizontal lines/inconsistent layers",
        parameter_adjustments={
            "print_speed": ("decrease", 10.0),
            "acceleration": ("decrease", 500.0),
            "jerk": ("decrease", 5.0),
        },
        priority=AdjustmentPriority.MEDIUM,
        max_applications=3
    ),
}


# === Feature-Specific Parameters ===

@dataclass
class FeatureParameters:
    """Parameters optimized for specific LEGO features."""
    feature: LEGOFeature
    speed_factor: float = 1.0  # Multiply base speed
    flow_factor: float = 1.0  # Multiply base flow
    temp_offset: float = 0.0  # Add to base temperature
    cooling_factor: float = 1.0  # Multiply base cooling
    extra_perimeters: int = 0  # Additional perimeters for strength


# Feature-specific parameter modifiers for LEGO printing
FEATURE_PARAMETERS: Dict[LEGOFeature, FeatureParameters] = {
    LEGOFeature.STUD: FeatureParameters(
        feature=LEGOFeature.STUD,
        speed_factor=0.5,  # Studs need slow, precise printing
        flow_factor=1.02,  # Slight over-extrusion for strength
        temp_offset=5.0,  # Slightly higher temp for adhesion
        cooling_factor=0.8,  # Less cooling for layer bonding
        extra_perimeters=1,  # Extra wall for strength
    ),
    LEGOFeature.TUBE: FeatureParameters(
        feature=LEGOFeature.TUBE,
        speed_factor=0.6,
        flow_factor=1.01,
        temp_offset=3.0,
        cooling_factor=0.7,
        extra_perimeters=1,
    ),
    LEGOFeature.WALL: FeatureParameters(
        feature=LEGOFeature.WALL,
        speed_factor=0.8,
        flow_factor=1.0,
        temp_offset=0.0,
        cooling_factor=1.0,
        extra_perimeters=0,
    ),
    LEGOFeature.RIB: FeatureParameters(
        feature=LEGOFeature.RIB,
        speed_factor=0.7,
        flow_factor=1.01,
        temp_offset=2.0,
        cooling_factor=0.9,
        extra_perimeters=0,
    ),
    LEGOFeature.TOP_SURFACE: FeatureParameters(
        feature=LEGOFeature.TOP_SURFACE,
        speed_factor=0.7,  # Nice top finish
        flow_factor=0.98,
        temp_offset=-3.0,  # Cooler for crisp surface
        cooling_factor=1.2,  # More cooling
        extra_perimeters=0,
    ),
    LEGOFeature.BOTTOM_SURFACE: FeatureParameters(
        feature=LEGOFeature.BOTTOM_SURFACE,
        speed_factor=0.3,  # Slow first layer
        flow_factor=1.05,  # Good bed adhesion
        temp_offset=5.0,
        cooling_factor=0.0,  # No cooling for first layer
        extra_perimeters=0,
    ),
    LEGOFeature.TECHNIC_HOLE: FeatureParameters(
        feature=LEGOFeature.TECHNIC_HOLE,
        speed_factor=0.4,  # Very precise
        flow_factor=0.98,  # Slightly less for accuracy
        temp_offset=0.0,
        cooling_factor=1.0,
        extra_perimeters=1,
    ),
    LEGOFeature.SLOPE_SURFACE: FeatureParameters(
        feature=LEGOFeature.SLOPE_SURFACE,
        speed_factor=0.6,
        flow_factor=1.0,
        temp_offset=0.0,
        cooling_factor=1.0,
        extra_perimeters=0,
    ),
}


# === Core Data Classes ===

@dataclass
class ParameterBounds:
    """Bounds for a parameter with LEGO-specific context."""
    name: str
    min_value: float
    max_value: float
    step_size: float = 1.0
    current_value: float = 0.0
    unit: str = ""
    lego_critical: bool = False  # Critical for LEGO compatibility
    description: str = ""


@dataclass
class Adjustment:
    """Parameter adjustment with full context."""
    parameter: str
    old_value: float
    new_value: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    applied: bool = False
    priority: AdjustmentPriority = AdjustmentPriority.MEDIUM
    defect_type: Optional[LEGODefectType] = None
    feature: Optional[LEGOFeature] = None
    rollback_possible: bool = True


@dataclass
class ClutchPowerAnalysis:
    """Analysis of LEGO clutch power based on dimensions."""
    stud_diameter: float
    tube_inner_diameter: float
    interference_mm: float
    assessment: str  # "optimal", "too_loose", "too_tight"
    in_range: bool
    adjustments_needed: List[Tuple[str, float]]  # (parameter, delta)


@dataclass
class DimensionalAnalysis:
    """Analysis of LEGO brick dimensions vs specifications."""
    dimension_name: str
    measured_value: float
    target_value: float
    tolerance: float
    error_mm: float
    error_percent: float
    in_tolerance: bool
    suggested_flow_adjustment: float
    suggested_xy_compensation: float


class LEGOParameterAdjuster:
    """
    LEGO-Specific Automatic Parameter Adjustment for Manufacturing.

    This is the primary parameter adjuster for LEGO brick 3D printing with
    comprehensive domain knowledge including:

    - Material-specific temperature, speed, and flow profiles
    - Brick feature-based adjustments (studs, tubes, walls)
    - Defect-specific correction rules based on Six Sigma methodology
    - Clutch power optimization (0.08-0.15mm interference fit)
    - Dimensional accuracy targeting LEGO specs
    - Color-specific shrinkage compensation

    Features:
    - Rule-based adjustments with LEGO domain expertise
    - Closed-loop feedback from quality inspection
    - Statistical process control integration
    - Multi-parameter optimization for clutch power
    - Gradient descent for continuous improvement
    """

    def __init__(self, material: LEGOMaterial = LEGOMaterial.PLA):
        self._material = material
        self._profile = MATERIAL_PROFILES.get(material, MATERIAL_PROFILES[LEGOMaterial.PLA])
        self._bounds: Dict[str, ParameterBounds] = {}
        self._current_values: Dict[str, float] = {}
        self._adjustment_history: List[Adjustment] = []
        self._defect_application_counts: Dict[LEGODefectType, int] = {}
        self._executor: Optional[Any] = None
        self._brick_type: LEGOBrickType = LEGOBrickType.STANDARD
        self._current_feature: Optional[LEGOFeature] = None

        # Statistical tracking
        self._adjustment_effectiveness: Dict[str, List[float]] = {}  # param -> [effectiveness_scores]

        self._load_default_bounds()
        self._apply_material_profile()

    def _load_default_bounds(self) -> None:
        """Load default parameter bounds optimized for LEGO printing."""
        # Temperature parameters
        self._bounds["nozzle_temperature"] = ParameterBounds(
            name="nozzle_temperature",
            min_value=180.0,
            max_value=280.0,
            step_size=5.0,
            current_value=210.0,
            unit="°C",
            lego_critical=True,
            description="Nozzle temperature affects layer adhesion and material flow"
        )

        self._bounds["bed_temperature"] = ParameterBounds(
            name="bed_temperature",
            min_value=20.0,
            max_value=120.0,
            step_size=5.0,
            current_value=60.0,
            unit="°C",
            lego_critical=True,
            description="Bed temperature prevents warping and elephant foot"
        )

        # Speed parameters
        self._bounds["print_speed"] = ParameterBounds(
            name="print_speed",
            min_value=15.0,
            max_value=150.0,
            step_size=5.0,
            current_value=50.0,
            unit="mm/s",
            lego_critical=True,
            description="Print speed affects dimensional accuracy and layer adhesion"
        )

        self._bounds["travel_speed"] = ParameterBounds(
            name="travel_speed",
            min_value=50.0,
            max_value=250.0,
            step_size=10.0,
            current_value=150.0,
            unit="mm/s",
            lego_critical=False,
            description="Travel speed affects stringing and print time"
        )

        self._bounds["first_layer_speed"] = ParameterBounds(
            name="first_layer_speed",
            min_value=10.0,
            max_value=50.0,
            step_size=5.0,
            current_value=20.0,
            unit="mm/s",
            lego_critical=True,
            description="First layer speed critical for bed adhesion"
        )

        # Flow parameters
        self._bounds["flow_rate"] = ParameterBounds(
            name="flow_rate",
            min_value=85.0,
            max_value=120.0,
            step_size=1.0,
            current_value=100.0,
            unit="%",
            lego_critical=True,
            description="Flow rate directly affects stud diameter and clutch power"
        )

        self._bounds["initial_layer_flow"] = ParameterBounds(
            name="initial_layer_flow",
            min_value=90.0,
            max_value=120.0,
            step_size=2.0,
            current_value=105.0,
            unit="%",
            lego_critical=True,
            description="First layer flow affects bottom surface and elephant foot"
        )

        # Z and compensation parameters
        self._bounds["z_offset"] = ParameterBounds(
            name="z_offset",
            min_value=-0.5,
            max_value=0.5,
            step_size=0.01,
            current_value=0.0,
            unit="mm",
            lego_critical=True,
            description="Z offset affects first layer adhesion and bottom dimensions"
        )

        self._bounds["xy_compensation"] = ParameterBounds(
            name="xy_compensation",
            min_value=-0.3,
            max_value=0.3,
            step_size=0.01,
            current_value=0.0,
            unit="mm",
            lego_critical=True,
            description="XY compensation affects stud/tube diameter accuracy"
        )

        # Cooling parameters
        self._bounds["fan_speed"] = ParameterBounds(
            name="fan_speed",
            min_value=0.0,
            max_value=100.0,
            step_size=5.0,
            current_value=100.0,
            unit="%",
            lego_critical=False,
            description="Fan speed affects layer cooling and overhang quality"
        )

        # Retraction parameters
        self._bounds["retraction_distance"] = ParameterBounds(
            name="retraction_distance",
            min_value=0.0,
            max_value=6.0,
            step_size=0.2,
            current_value=0.8,
            unit="mm",
            lego_critical=False,
            description="Retraction distance affects stringing between studs"
        )

        self._bounds["retraction_speed"] = ParameterBounds(
            name="retraction_speed",
            min_value=10.0,
            max_value=70.0,
            step_size=5.0,
            current_value=45.0,
            unit="mm/s",
            lego_critical=False,
            description="Retraction speed affects stringing and print time"
        )

        # Layer parameters
        self._bounds["layer_height"] = ParameterBounds(
            name="layer_height",
            min_value=0.08,
            max_value=0.32,
            step_size=0.04,
            current_value=0.20,
            unit="mm",
            lego_critical=True,
            description="Layer height affects Z accuracy and surface finish"
        )

        self._bounds["first_layer_height"] = ParameterBounds(
            name="first_layer_height",
            min_value=0.15,
            max_value=0.35,
            step_size=0.05,
            current_value=0.25,
            unit="mm",
            lego_critical=True,
            description="First layer height affects bed adhesion"
        )

        # Motion parameters
        self._bounds["acceleration"] = ParameterBounds(
            name="acceleration",
            min_value=500.0,
            max_value=5000.0,
            step_size=100.0,
            current_value=1500.0,
            unit="mm/s²",
            lego_critical=False,
            description="Acceleration affects print quality and ringing"
        )

        self._bounds["jerk"] = ParameterBounds(
            name="jerk",
            min_value=1.0,
            max_value=20.0,
            step_size=1.0,
            current_value=8.0,
            unit="mm/s",
            lego_critical=False,
            description="Jerk affects corner quality and ringing"
        )

        # Initialize current values
        for name, bounds in self._bounds.items():
            self._current_values[name] = bounds.current_value

    def _apply_material_profile(self) -> None:
        """Apply material-specific parameters from profile."""
        profile = self._profile

        # Update bounds and current values from material profile
        if "nozzle_temperature" in self._bounds:
            self._bounds["nozzle_temperature"].min_value = profile.nozzle_temp_min
            self._bounds["nozzle_temperature"].max_value = profile.nozzle_temp_max
            self._current_values["nozzle_temperature"] = profile.nozzle_temp_default

        if "bed_temperature" in self._bounds:
            self._bounds["bed_temperature"].min_value = profile.bed_temp_min
            self._bounds["bed_temperature"].max_value = profile.bed_temp_max
            self._current_values["bed_temperature"] = profile.bed_temp_default

        if "print_speed" in self._bounds:
            self._bounds["print_speed"].min_value = profile.print_speed_min
            self._bounds["print_speed"].max_value = profile.print_speed_max
            self._current_values["print_speed"] = profile.print_speed_default

        if "flow_rate" in self._bounds:
            self._bounds["flow_rate"].min_value = profile.flow_rate_min
            self._bounds["flow_rate"].max_value = profile.flow_rate_max
            self._current_values["flow_rate"] = profile.flow_rate_default

        if "fan_speed" in self._bounds:
            self._current_values["fan_speed"] = profile.fan_speed_default

        if "retraction_distance" in self._bounds:
            self._current_values["retraction_distance"] = profile.retraction_distance

        if "retraction_speed" in self._bounds:
            self._current_values["retraction_speed"] = profile.retraction_speed

        logger.info(f"Applied material profile: {profile.name}")

    def set_executor(self, executor: Any) -> None:
        """Set action executor for applying adjustments."""
        self._executor = executor

    def set_material(self, material: LEGOMaterial) -> None:
        """Change the material profile."""
        self._material = material
        self._profile = MATERIAL_PROFILES.get(material, MATERIAL_PROFILES[LEGOMaterial.PLA])
        self._apply_material_profile()

    def set_brick_type(self, brick_type: LEGOBrickType) -> None:
        """Set current brick type for context-aware adjustments."""
        self._brick_type = brick_type

    def set_current_feature(self, feature: Optional[LEGOFeature]) -> None:
        """Set current feature being printed for feature-specific adjustments."""
        self._current_feature = feature

    def set_bounds(self, parameter: str, min_val: float, max_val: float,
                   step: float = 1.0, unit: str = "", lego_critical: bool = False) -> None:
        """Set bounds for parameter with LEGO context."""
        current = self._current_values.get(parameter, (min_val + max_val) / 2)
        self._bounds[parameter] = ParameterBounds(
            name=parameter,
            min_value=min_val,
            max_value=max_val,
            step_size=step,
            current_value=current,
            unit=unit,
            lego_critical=lego_critical
        )

    def adjust(self,
              parameter: str,
              target_value: Optional[float] = None,
              delta: Optional[float] = None,
              reason: str = "",
              priority: AdjustmentPriority = AdjustmentPriority.MEDIUM,
              defect_type: Optional[LEGODefectType] = None,
              feature: Optional[LEGOFeature] = None) -> Adjustment:
        """
        Adjust a parameter with full LEGO context.

        Args:
            parameter: Parameter to adjust
            target_value: Target value (if specified)
            delta: Change amount (if target not specified)
            reason: Reason for adjustment
            priority: Priority level of adjustment
            defect_type: Associated defect type if any
            feature: Associated LEGO feature if any

        Returns:
            Adjustment record
        """
        if parameter not in self._bounds:
            raise ValueError(f"Unknown parameter: {parameter}")

        bounds = self._bounds[parameter]
        old_value = self._current_values.get(parameter, bounds.current_value)

        if target_value is not None:
            new_value = target_value
        elif delta is not None:
            new_value = old_value + delta
        else:
            raise ValueError("Must specify target_value or delta")

        # Enforce bounds
        new_value = max(bounds.min_value, min(bounds.max_value, new_value))

        # Round to step size
        steps = round((new_value - bounds.min_value) / bounds.step_size)
        new_value = bounds.min_value + steps * bounds.step_size

        adjustment = Adjustment(
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            priority=priority,
            defect_type=defect_type,
            feature=feature or self._current_feature
        )

        # Apply adjustment
        self._current_values[parameter] = new_value
        self._bounds[parameter].current_value = new_value
        adjustment.applied = True

        self._adjustment_history.append(adjustment)
        logger.info(f"Adjusted {parameter}: {old_value:.3f} -> {new_value:.3f} ({reason})")

        return adjustment

    # === LEGO-Specific Adjustment Methods ===

    def analyze_clutch_power(self,
                            stud_diameter: float,
                            tube_inner_diameter: Optional[float] = None) -> ClutchPowerAnalysis:
        """
        Analyze LEGO clutch power based on measured dimensions.

        Clutch power is the interference fit between studs and tubes that
        makes LEGO bricks snap together. Optimal range: 0.08-0.15mm.

        Args:
            stud_diameter: Measured stud diameter (mm)
            tube_inner_diameter: Measured tube inner diameter (mm), defaults to spec

        Returns:
            ClutchPowerAnalysis with assessment and recommended adjustments
        """
        tube_id = tube_inner_diameter or LEGOSpecs.TUBE_INNER_DIAMETER

        # Calculate interference (how much stud compresses tube)
        # Interference = stud_diameter - (tube_id - wall_gap)
        # For LEGO, the effective gap is tube_id that stud fits into
        interference = stud_diameter - tube_id

        # Determine assessment
        if interference < LEGOSpecs.CLUTCH_INTERFERENCE_MIN:
            assessment = "too_loose"
            in_range = False
        elif interference > LEGOSpecs.CLUTCH_INTERFERENCE_MAX:
            assessment = "too_tight"
            in_range = False
        else:
            assessment = "optimal"
            in_range = True

        # Calculate needed adjustments
        adjustments_needed: List[Tuple[str, float]] = []

        if not in_range:
            target_interference = LEGOSpecs.CLUTCH_INTERFERENCE_OPTIMAL
            diameter_error = (target_interference - interference)

            if assessment == "too_loose":
                # Need larger studs: increase flow, decrease XY compensation
                flow_delta = diameter_error * 10  # ~1% flow per 0.1mm
                adjustments_needed.append(("flow_rate", flow_delta))
                adjustments_needed.append(("xy_compensation", -diameter_error / 2))
            else:  # too_tight
                # Need smaller studs: decrease flow, increase XY compensation
                flow_delta = diameter_error * 10
                adjustments_needed.append(("flow_rate", flow_delta))
                adjustments_needed.append(("xy_compensation", -diameter_error / 2))

        return ClutchPowerAnalysis(
            stud_diameter=stud_diameter,
            tube_inner_diameter=tube_id,
            interference_mm=round(interference, 4),
            assessment=assessment,
            in_range=in_range,
            adjustments_needed=adjustments_needed
        )

    def adjust_for_clutch_power(self,
                               stud_diameter: float,
                               tube_inner_diameter: Optional[float] = None) -> List[Adjustment]:
        """
        Automatically adjust parameters to achieve optimal clutch power.

        Args:
            stud_diameter: Measured stud diameter
            tube_inner_diameter: Measured tube inner diameter (optional)

        Returns:
            List of adjustments made
        """
        analysis = self.analyze_clutch_power(stud_diameter, tube_inner_diameter)

        if analysis.in_range:
            logger.info(f"Clutch power optimal: {analysis.interference_mm}mm interference")
            return []

        adjustments = []
        for param, delta in analysis.adjustments_needed:
            if param in self._bounds:
                adj = self.adjust(
                    parameter=param,
                    delta=delta,
                    reason=f"Clutch power correction: {analysis.assessment}",
                    priority=AdjustmentPriority.HIGH,
                    defect_type=(LEGODefectType.CLUTCH_WEAK if analysis.assessment == "too_loose"
                                else LEGODefectType.CLUTCH_STRONG)
                )
                adjustments.append(adj)

        return adjustments

    def analyze_dimension(self,
                         dimension_name: str,
                         measured_value: float,
                         target_value: Optional[float] = None,
                         tolerance: Optional[float] = None) -> DimensionalAnalysis:
        """
        Analyze a LEGO dimension against specification.

        Args:
            dimension_name: Name of dimension (e.g., "stud_diameter")
            measured_value: Measured value in mm
            target_value: Target value (uses LEGO spec if not provided)
            tolerance: Tolerance (uses default if not provided)

        Returns:
            DimensionalAnalysis with error and suggested corrections
        """
        # Get target and tolerance from LEGO specs if not provided
        spec_map = {
            "stud_diameter": (LEGOSpecs.STUD_DIAMETER, LEGOSpecs.STUD_TOLERANCE),
            "stud_height": (LEGOSpecs.STUD_HEIGHT, 0.05),
            "tube_outer_diameter": (LEGOSpecs.TUBE_OUTER_DIAMETER, LEGOSpecs.TUBE_TOLERANCE),
            "tube_inner_diameter": (LEGOSpecs.TUBE_INNER_DIAMETER, LEGOSpecs.TUBE_TOLERANCE),
            "wall_thickness": (LEGOSpecs.WALL_THICKNESS, 0.05),
            "brick_height": (LEGOSpecs.BRICK_HEIGHT, LEGOSpecs.GENERAL_TOLERANCE),
            "plate_height": (LEGOSpecs.PLATE_HEIGHT, LEGOSpecs.GENERAL_TOLERANCE),
            "stud_pitch": (LEGOSpecs.STUD_PITCH, LEGOSpecs.GENERAL_TOLERANCE),
        }

        if target_value is None:
            target_value, default_tolerance = spec_map.get(
                dimension_name,
                (measured_value, LEGOSpecs.GENERAL_TOLERANCE)
            )
            tolerance = tolerance or default_tolerance
        else:
            tolerance = tolerance or LEGOSpecs.GENERAL_TOLERANCE

        error_mm = measured_value - target_value
        error_percent = (error_mm / target_value) * 100 if target_value != 0 else 0
        in_tolerance = abs(error_mm) <= tolerance

        # Calculate suggested adjustments
        # Flow rate affects extrusion width/height proportionally
        suggested_flow = -error_percent  # If too big, reduce flow

        # XY compensation directly affects XY dimensions
        suggested_xy = -error_mm if dimension_name in [
            "stud_diameter", "tube_outer_diameter", "tube_inner_diameter"
        ] else 0

        return DimensionalAnalysis(
            dimension_name=dimension_name,
            measured_value=measured_value,
            target_value=target_value,
            tolerance=tolerance,
            error_mm=round(error_mm, 4),
            error_percent=round(error_percent, 2),
            in_tolerance=in_tolerance,
            suggested_flow_adjustment=round(suggested_flow, 2),
            suggested_xy_compensation=round(suggested_xy, 4)
        )

    def adjust_for_dimension(self,
                            dimension_name: str,
                            measured_value: float,
                            target_value: Optional[float] = None) -> List[Adjustment]:
        """
        Automatically adjust parameters to correct dimensional error.

        Args:
            dimension_name: Name of dimension
            measured_value: Measured value in mm
            target_value: Target value (uses LEGO spec if not provided)

        Returns:
            List of adjustments made
        """
        analysis = self.analyze_dimension(dimension_name, measured_value, target_value)

        if analysis.in_tolerance:
            logger.info(f"{dimension_name} in tolerance: {analysis.error_mm}mm error")
            return []

        adjustments = []

        # Apply flow adjustment
        if abs(analysis.suggested_flow_adjustment) > 0.5:
            adj = self.adjust(
                parameter="flow_rate",
                delta=analysis.suggested_flow_adjustment,
                reason=f"Dimensional correction for {dimension_name}",
                priority=AdjustmentPriority.HIGH,
                defect_type=LEGODefectType.DIMENSIONAL_ERROR
            )
            adjustments.append(adj)

        # Apply XY compensation for cylindrical features
        if abs(analysis.suggested_xy_compensation) > 0.005:
            adj = self.adjust(
                parameter="xy_compensation",
                delta=analysis.suggested_xy_compensation,
                reason=f"XY correction for {dimension_name}",
                priority=AdjustmentPriority.HIGH,
                defect_type=LEGODefectType.DIMENSIONAL_ERROR
            )
            adjustments.append(adj)

        return adjustments

    def correct_defect(self, defect_type: LEGODefectType,
                      severity: float = 1.0) -> List[Adjustment]:
        """
        Apply correction rules for a specific defect type.

        Args:
            defect_type: Type of defect detected
            severity: Severity multiplier (0.5 = mild, 1.0 = normal, 2.0 = severe)

        Returns:
            List of adjustments made
        """
        if defect_type not in DEFECT_CORRECTION_RULES:
            logger.warning(f"No correction rule for defect: {defect_type}")
            return []

        rule = DEFECT_CORRECTION_RULES[defect_type]

        # Check if we've exceeded max applications
        count = self._defect_application_counts.get(defect_type, 0)
        if count >= rule.max_applications:
            logger.warning(
                f"Max corrections reached for {defect_type.value} "
                f"({count}/{rule.max_applications})"
            )
            return []

        adjustments = []

        for param, (direction, amount) in rule.parameter_adjustments.items():
            if param not in self._bounds:
                continue

            # Calculate delta based on direction and severity
            if direction == "increase":
                delta = amount * severity
            elif direction == "decrease":
                delta = -amount * severity
            elif direction == "adjust":
                # For 'adjust', amount is calculated elsewhere (e.g., dimensional)
                continue
            else:
                continue

            adj = self.adjust(
                parameter=param,
                delta=delta,
                reason=f"Defect correction: {rule.description}",
                priority=rule.priority,
                defect_type=defect_type
            )
            adjustments.append(adj)

        # Track application count
        self._defect_application_counts[defect_type] = count + 1

        logger.info(
            f"Applied {len(adjustments)} corrections for {defect_type.value} "
            f"(application {count + 1}/{rule.max_applications})"
        )

        return adjustments

    def get_feature_parameters(self, feature: LEGOFeature) -> Dict[str, float]:
        """
        Get optimized parameters for a specific LEGO feature.

        Args:
            feature: LEGO feature type (stud, tube, wall, etc.)

        Returns:
            Dict of parameter name to value optimized for this feature
        """
        base_params = self.get_current_values()

        if feature not in FEATURE_PARAMETERS:
            return base_params

        fp = FEATURE_PARAMETERS[feature]

        # Apply feature-specific modifiers
        optimized = base_params.copy()

        if "print_speed" in optimized:
            optimized["print_speed"] = base_params["print_speed"] * fp.speed_factor

        if "flow_rate" in optimized:
            optimized["flow_rate"] = base_params["flow_rate"] * fp.flow_factor

        if "nozzle_temperature" in optimized:
            optimized["nozzle_temperature"] = base_params["nozzle_temperature"] + fp.temp_offset

        if "fan_speed" in optimized:
            optimized["fan_speed"] = base_params["fan_speed"] * fp.cooling_factor

        return optimized

    def optimize_for_brick(self,
                          studs_x: int,
                          studs_y: int,
                          brick_type: LEGOBrickType = LEGOBrickType.STANDARD) -> Dict[str, float]:
        """
        Get optimized parameters for a specific brick configuration.

        Larger bricks need different parameters (warping prevention, etc.)

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            brick_type: Type of brick

        Returns:
            Dict of optimized parameters
        """
        self.set_brick_type(brick_type)
        params = self.get_current_values()

        # Calculate brick footprint
        footprint = studs_x * studs_y

        # Large bricks (>8 studs) need warping prevention
        if footprint > 8:
            # Lower first layer speed
            if "first_layer_speed" in params:
                params["first_layer_speed"] *= 0.8
            # Slightly higher bed temp
            if "bed_temperature" in params:
                params["bed_temperature"] = min(
                    params["bed_temperature"] + 5,
                    self._bounds["bed_temperature"].max_value
                )
            # Less cooling on first layers
            if "fan_speed" in params:
                params["fan_speed"] *= 0.8

        # Very large bricks (baseplates) need extra care
        if footprint > 32:
            if "first_layer_speed" in params:
                params["first_layer_speed"] *= 0.7
            if "bed_temperature" in params:
                params["bed_temperature"] = min(
                    params["bed_temperature"] + 10,
                    self._bounds["bed_temperature"].max_value
                )

        # Plates need slightly different handling
        if brick_type == LEGOBrickType.PLATE:
            # Thinner parts can use slightly higher speeds
            if "print_speed" in params:
                params["print_speed"] *= 1.1

        # Technic bricks need precision for holes
        if brick_type == LEGOBrickType.TECHNIC:
            if "print_speed" in params:
                params["print_speed"] *= 0.8
            if "flow_rate" in params:
                params["flow_rate"] *= 0.98  # Slight under-extrusion for holes

        return params

    def apply_color_compensation(self, material: str, color: str) -> List[Adjustment]:
        """
        Apply shrinkage compensation based on material color.

        Different colors and materials have different shrinkage rates.

        Args:
            material: Material type (pla, petg, abs, asa)
            color: Color name

        Returns:
            List of adjustments made
        """
        # Color-specific shrinkage factors (from lego_specs.py pattern)
        shrinkage_factors = {
            "pla_white": 1.002,
            "pla_black": 1.001,
            "pla_trans": 1.003,
            "petg_white": 1.004,
            "petg_black": 1.003,
            "abs_white": 1.004,
            "abs_black": 1.005,
            "abs_dark_brown": 1.006,
            "asa_any": 1.005,
        }

        key = f"{material.lower()}_{color.lower()}"
        factor = shrinkage_factors.get(key, shrinkage_factors.get(f"{material.lower()}_any", 1.0))

        adjustments = []

        if factor != 1.0:
            # Adjust XY compensation to account for shrinkage
            # If part shrinks by 0.5%, we need to print 0.5% larger
            xy_comp = (factor - 1.0) * LEGOSpecs.STUD_DIAMETER  # Scale by stud size

            adj = self.adjust(
                parameter="xy_compensation",
                delta=xy_comp,
                reason=f"Color shrinkage compensation: {material} {color}",
                priority=AdjustmentPriority.MEDIUM
            )
            adjustments.append(adj)

        return adjustments

    def adjust_for_quality(self,
                          quality_metric: float,
                          target_metric: float,
                          parameters: Optional[List[str]] = None) -> List[Adjustment]:
        """
        Adjust parameters to improve quality metric using LEGO-aware optimization.

        Args:
            quality_metric: Current quality value (0-1, higher is better)
            target_metric: Target quality value
            parameters: Parameters to adjust (defaults to LEGO-critical params)

        Returns:
            List of adjustments made
        """
        if parameters is None:
            # Default to LEGO-critical parameters
            parameters = [name for name, bounds in self._bounds.items() if bounds.lego_critical]

        adjustments = []
        error = target_metric - quality_metric

        if abs(error) < 0.01:
            return adjustments  # Within tolerance

        # Proportional-integral adjustment with LEGO domain knowledge
        # Use different gains for different parameter types
        param_gains = {
            "nozzle_temperature": 10.0,  # °C per quality unit
            "bed_temperature": 5.0,
            "print_speed": -5.0,  # Negative: lower speed = higher quality
            "flow_rate": 2.0,
            "z_offset": 0.02,
            "xy_compensation": 0.01,
            "fan_speed": -10.0,
            "layer_height": -0.02,
        }

        for param in parameters:
            if param not in self._bounds or param not in param_gains:
                continue

            gain = param_gains[param]
            delta = gain * error

            # Limit delta to prevent wild swings
            bounds = self._bounds[param]
            max_delta = (bounds.max_value - bounds.min_value) * 0.1
            delta = max(-max_delta, min(max_delta, delta))

            if abs(delta) < bounds.step_size:
                continue

            adj = self.adjust(
                parameter=param,
                delta=delta,
                reason=f"Quality optimization: {quality_metric:.3f} -> {target_metric:.3f}",
                priority=AdjustmentPriority.MEDIUM
            )
            adjustments.append(adj)

        return adjustments

    def run_spc_analysis(self,
                        measurements: List[float],
                        parameter: str) -> Dict[str, Any]:
        """
        Run Statistical Process Control analysis on measurements.

        Args:
            measurements: List of recent measurements
            parameter: Parameter name for context

        Returns:
            SPC analysis results with control limits and recommendations
        """
        if len(measurements) < 5:
            return {"error": "Need at least 5 measurements for SPC"}

        # Calculate statistics
        mean = sum(measurements) / len(measurements)
        variance = sum((x - mean) ** 2 for x in measurements) / len(measurements)
        std_dev = math.sqrt(variance)

        # Control limits (3-sigma)
        ucl = mean + 3 * std_dev
        lcl = mean - 3 * std_dev

        # Warning limits (2-sigma)
        uwl = mean + 2 * std_dev
        lwl = mean - 2 * std_dev

        # Check for out-of-control conditions
        out_of_control = []
        for i, m in enumerate(measurements):
            if m > ucl or m < lcl:
                out_of_control.append({"index": i, "value": m, "type": "beyond_3sigma"})
            elif m > uwl or m < lwl:
                out_of_control.append({"index": i, "value": m, "type": "beyond_2sigma"})

        # Check for trends (7 consecutive points trending)
        trending_up = all(measurements[i] < measurements[i+1]
                         for i in range(min(6, len(measurements)-1)))
        trending_down = all(measurements[i] > measurements[i+1]
                           for i in range(min(6, len(measurements)-1)))

        # Process capability (Cp, Cpk) for LEGO dimensions
        cp = cpk = None
        if parameter in ["stud_diameter", "tube_inner_diameter"]:
            # Use LEGO tolerances
            usl = LEGOSpecs.STUD_DIAMETER + LEGOSpecs.STUD_TOLERANCE
            lsl = LEGOSpecs.STUD_DIAMETER - LEGOSpecs.STUD_TOLERANCE
            if std_dev > 0:
                cp = (usl - lsl) / (6 * std_dev)
                cpu = (usl - mean) / (3 * std_dev)
                cpl = (mean - lsl) / (3 * std_dev)
                cpk = min(cpu, cpl)

        return {
            "mean": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "ucl": round(ucl, 4),
            "lcl": round(lcl, 4),
            "uwl": round(uwl, 4),
            "lwl": round(lwl, 4),
            "out_of_control": out_of_control,
            "trending_up": trending_up,
            "trending_down": trending_down,
            "cp": round(cp, 3) if cp else None,
            "cpk": round(cpk, 3) if cpk else None,
            "process_capable": cpk >= 1.33 if cpk else None,
            "recommendations": self._generate_spc_recommendations(
                mean, std_dev, out_of_control, trending_up, trending_down, cp, cpk, parameter
            )
        }

    def _generate_spc_recommendations(self,
                                     mean: float,
                                     std_dev: float,
                                     out_of_control: List[Dict],
                                     trending_up: bool,
                                     trending_down: bool,
                                     cp: Optional[float],
                                     cpk: Optional[float],
                                     parameter: str) -> List[str]:
        """Generate SPC-based recommendations."""
        recommendations = []

        if out_of_control:
            recommendations.append(
                f"Found {len(out_of_control)} out-of-control points - investigate root cause"
            )

        if trending_up:
            recommendations.append("Upward trend detected - check for tool wear or drift")
        if trending_down:
            recommendations.append("Downward trend detected - check for environmental changes")

        if cpk is not None:
            if cpk < 1.0:
                recommendations.append(f"Cpk={cpk:.2f} - process not capable, reduce variation")
            elif cpk < 1.33:
                recommendations.append(f"Cpk={cpk:.2f} - marginally capable, improve centering")
            else:
                recommendations.append(f"Cpk={cpk:.2f} - process capable")

        if std_dev > 0.05:  # High variation for LEGO dimensions
            recommendations.append("High variation - check printer calibration and environment")

        return recommendations

    def adjust_for_temperature(self,
                              current_temp: float,
                              target_temp: float,
                              parameter: str = "nozzle_temperature") -> Optional[Adjustment]:
        """
        Adjust temperature parameter for LEGO printing.

        Args:
            current_temp: Current temperature in °C
            target_temp: Target temperature in °C
            parameter: Temperature parameter to adjust

        Returns:
            Adjustment if made, None if within tolerance
        """
        error = target_temp - current_temp

        if abs(error) < 2.0:
            return None  # Within tolerance

        return self.adjust(
            parameter=parameter,
            target_value=target_temp,
            reason=f"Temperature correction: {current_temp:.1f}°C -> {target_temp:.1f}°C",
            priority=AdjustmentPriority.HIGH
        )

    def adjust_for_layer(self, layer_number: int, total_layers: int) -> Dict[str, float]:
        """
        Get layer-specific parameter adjustments.

        Different layers need different parameters:
        - First layer: slow, high flow, no fan
        - Bottom layers: gradual ramp up
        - Middle layers: normal
        - Top layers: good surface finish

        Args:
            layer_number: Current layer (1-indexed)
            total_layers: Total number of layers

        Returns:
            Dict of adjusted parameters for this layer
        """
        params = self.get_current_values()

        # Calculate layer percentages
        layer_percent = layer_number / total_layers if total_layers > 0 else 0

        if layer_number == 1:
            # First layer - critical for adhesion
            params["print_speed"] = self._current_values.get("first_layer_speed", 20)
            params["flow_rate"] = self._current_values.get("initial_layer_flow", 105)
            params["fan_speed"] = self._profile.fan_first_layer
            self._current_feature = LEGOFeature.BOTTOM_SURFACE

        elif layer_number <= 3:
            # Bottom layers - gradual transition
            ramp = layer_number / 3
            base_speed = self._current_values.get("print_speed", 50)
            first_layer_speed = self._current_values.get("first_layer_speed", 20)
            params["print_speed"] = first_layer_speed + (base_speed - first_layer_speed) * ramp
            params["fan_speed"] = self._current_values.get("fan_speed", 100) * ramp

        elif layer_percent > 0.9:
            # Top layers - good surface finish
            fp = FEATURE_PARAMETERS.get(LEGOFeature.TOP_SURFACE)
            if fp:
                params["print_speed"] *= fp.speed_factor
                params["flow_rate"] *= fp.flow_factor
                params["fan_speed"] *= fp.cooling_factor
            self._current_feature = LEGOFeature.TOP_SURFACE

        return params

    def get_adjustment_suggestions(self,
                                  metrics: Dict[str, float],
                                  targets: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Get LEGO-specific parameter adjustment suggestions based on quality metrics.

        Args:
            metrics: Current metric values (defect_rate, dimensional_accuracy,
                    clutch_power, surface_quality, etc.)
            targets: Target metric values

        Returns:
            List of suggested adjustments with LEGO context
        """
        suggestions = []

        # LEGO-specific metric handling
        lego_metric_rules = {
            "defect_rate": {
                "direction": "minimize",
                "adjustments": [
                    {"parameter": "print_speed", "action": "decrease", "factor": 5.0},
                    {"parameter": "nozzle_temperature", "action": "increase", "factor": 2.0},
                    {"parameter": "flow_rate", "action": "adjust", "factor": 1.0},
                ]
            },
            "dimensional_accuracy": {
                "direction": "maximize",
                "adjustments": [
                    {"parameter": "flow_rate", "action": "tune", "factor": 2.0},
                    {"parameter": "xy_compensation", "action": "tune", "factor": 0.02},
                    {"parameter": "print_speed", "action": "decrease", "factor": 3.0},
                ]
            },
            "clutch_power": {
                "direction": "target",  # Specific target range
                "target_range": (0.08, 0.15),
                "adjustments": [
                    {"parameter": "flow_rate", "action": "tune", "factor": 2.0},
                    {"parameter": "xy_compensation", "action": "tune", "factor": 0.03},
                    {"parameter": "nozzle_temperature", "action": "tune", "factor": 5.0},
                ]
            },
            "surface_quality": {
                "direction": "maximize",
                "adjustments": [
                    {"parameter": "print_speed", "action": "decrease", "factor": 10.0},
                    {"parameter": "layer_height", "action": "decrease", "factor": 0.04},
                    {"parameter": "fan_speed", "action": "increase", "factor": 10.0},
                ]
            },
            "layer_adhesion": {
                "direction": "maximize",
                "adjustments": [
                    {"parameter": "nozzle_temperature", "action": "increase", "factor": 5.0},
                    {"parameter": "print_speed", "action": "decrease", "factor": 5.0},
                    {"parameter": "fan_speed", "action": "decrease", "factor": 15.0},
                ]
            },
            "warping": {
                "direction": "minimize",
                "adjustments": [
                    {"parameter": "bed_temperature", "action": "increase", "factor": 5.0},
                    {"parameter": "fan_speed", "action": "decrease", "factor": 20.0},
                    {"parameter": "first_layer_speed", "action": "decrease", "factor": 5.0},
                ]
            },
            "stringing": {
                "direction": "minimize",
                "adjustments": [
                    {"parameter": "retraction_distance", "action": "increase", "factor": 0.2},
                    {"parameter": "nozzle_temperature", "action": "decrease", "factor": 5.0},
                    {"parameter": "travel_speed", "action": "increase", "factor": 20.0},
                ]
            },
        }

        for metric, current in metrics.items():
            target = targets.get(metric)
            if target is None:
                continue

            rule = lego_metric_rules.get(metric)
            if not rule:
                continue

            error = target - current
            if abs(error) < 0.01:
                continue

            # Calculate adjustment amounts based on error magnitude
            suggested_adjustments = []
            for adj in rule["adjustments"]:
                amount = adj["factor"] * abs(error)

                # Determine direction based on rule and error
                if adj["action"] == "increase":
                    action = "increase" if error > 0 else "decrease"
                elif adj["action"] == "decrease":
                    action = "decrease" if error > 0 else "increase"
                else:
                    action = "increase" if error > 0 else "decrease"

                suggested_adjustments.append({
                    "parameter": adj["parameter"],
                    "action": action,
                    "amount": round(amount, 2),
                    "current_value": self._current_values.get(adj["parameter"]),
                    "lego_critical": self._bounds.get(adj["parameter"], ParameterBounds("", 0, 0)).lego_critical
                })

            suggestions.append({
                "metric": metric,
                "current": current,
                "target": target,
                "error": round(error, 4),
                "priority": "high" if abs(error) > 0.1 else "medium",
                "suggested_adjustments": suggested_adjustments
            })

        return suggestions

    def rollback_adjustment(self, adjustment: Adjustment) -> Optional[Adjustment]:
        """
        Rollback a previous adjustment.

        Args:
            adjustment: The adjustment to rollback

        Returns:
            New adjustment record for the rollback
        """
        if not adjustment.rollback_possible:
            logger.warning(f"Cannot rollback adjustment: {adjustment.reason}")
            return None

        return self.adjust(
            parameter=adjustment.parameter,
            target_value=adjustment.old_value,
            reason=f"Rollback: {adjustment.reason}",
            priority=adjustment.priority
        )

    def get_current_values(self) -> Dict[str, float]:
        """Get current parameter values."""
        return self._current_values.copy()

    def get_lego_critical_values(self) -> Dict[str, float]:
        """Get only LEGO-critical parameter values."""
        return {
            name: value for name, value in self._current_values.items()
            if self._bounds.get(name, ParameterBounds("", 0, 0)).lego_critical
        }

    def get_adjustment_history(self,
                              parameter: Optional[str] = None,
                              defect_type: Optional[LEGODefectType] = None,
                              limit: int = 50) -> List[Adjustment]:
        """
        Get adjustment history with optional filtering.

        Args:
            parameter: Filter by parameter name
            defect_type: Filter by defect type
            limit: Maximum number of records

        Returns:
            List of adjustments
        """
        history = self._adjustment_history[-limit:]

        if parameter:
            history = [a for a in history if a.parameter == parameter]

        if defect_type:
            history = [a for a in history if a.defect_type == defect_type]

        return history

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive adjustment statistics for LEGO manufacturing.

        Returns:
            Dict with statistics including defect corrections, parameter usage, etc.
        """
        if not self._adjustment_history:
            return {
                'total_adjustments': 0,
                'material': self._material.value,
                'profile': self._profile.name
            }

        # Parameter adjustment counts
        param_counts: Dict[str, int] = {}
        for adj in self._adjustment_history:
            param_counts[adj.parameter] = param_counts.get(adj.parameter, 0) + 1

        # Defect correction counts
        defect_counts: Dict[str, int] = {}
        for adj in self._adjustment_history:
            if adj.defect_type:
                key = adj.defect_type.value
                defect_counts[key] = defect_counts.get(key, 0) + 1

        # Priority distribution
        priority_counts = {p.name: 0 for p in AdjustmentPriority}
        for adj in self._adjustment_history:
            priority_counts[adj.priority.name] += 1

        # Calculate adjustment effectiveness (if tracked)
        effectiveness_summary = {}
        for param, scores in self._adjustment_effectiveness.items():
            if scores:
                effectiveness_summary[param] = {
                    'mean': sum(scores) / len(scores),
                    'count': len(scores)
                }

        # LEGO-specific statistics
        lego_critical_adjustments = sum(
            1 for adj in self._adjustment_history
            if self._bounds.get(adj.parameter, ParameterBounds("", 0, 0)).lego_critical
        )

        return {
            'total_adjustments': len(self._adjustment_history),
            'adjustments_per_parameter': param_counts,
            'defect_corrections': defect_counts,
            'priority_distribution': priority_counts,
            'lego_critical_adjustments': lego_critical_adjustments,
            'defect_application_counts': {
                k.value: v for k, v in self._defect_application_counts.items()
            },
            'effectiveness': effectiveness_summary,
            'material': self._material.value,
            'profile': self._profile.name,
            'current_values': self._current_values.copy()
        }

    def export_profile(self) -> Dict[str, Any]:
        """
        Export current parameter profile for saving or sharing.

        Returns:
            Dict containing all parameters and settings
        """
        return {
            'material': self._material.value,
            'brick_type': self._brick_type.value,
            'parameters': self._current_values.copy(),
            'bounds': {
                name: {
                    'min': b.min_value,
                    'max': b.max_value,
                    'step': b.step_size,
                    'unit': b.unit,
                    'lego_critical': b.lego_critical
                }
                for name, b in self._bounds.items()
            },
            'profile_name': self._profile.name,
            'lego_suitability': self._profile.lego_suitability
        }

    def import_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        Import a parameter profile.

        Args:
            profile_data: Dict from export_profile()
        """
        if 'material' in profile_data:
            try:
                self._material = LEGOMaterial(profile_data['material'])
                self._profile = MATERIAL_PROFILES.get(
                    self._material, MATERIAL_PROFILES[LEGOMaterial.PLA]
                )
            except ValueError:
                logger.warning(f"Unknown material: {profile_data['material']}")

        if 'brick_type' in profile_data:
            try:
                self._brick_type = LEGOBrickType(profile_data['brick_type'])
            except ValueError:
                pass

        if 'parameters' in profile_data:
            for name, value in profile_data['parameters'].items():
                if name in self._bounds:
                    self._current_values[name] = value
                    self._bounds[name].current_value = value

        logger.info(f"Imported profile for {self._material.value}")

    def reset_to_defaults(self) -> None:
        """Reset all parameters to default values for current material."""
        self._load_default_bounds()
        self._apply_material_profile()
        self._adjustment_history.clear()
        self._defect_application_counts.clear()
        logger.info(f"Reset to defaults for {self._material.value}")

    def get_material_recommendation(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get material recommendation based on requirements.

        Args:
            requirements: Dict with keys like 'outdoor_use', 'high_strength',
                         'tight_tolerance', 'flexible', etc.

        Returns:
            Dict with recommended material and reasoning
        """
        scores: Dict[LEGOMaterial, float] = {}

        for material, profile in MATERIAL_PROFILES.items():
            score = profile.lego_suitability * 100

            # Adjust based on requirements
            if requirements.get('outdoor_use'):
                if material in [LEGOMaterial.ASA, LEGOMaterial.ABS]:
                    score += 20
                elif material == LEGOMaterial.PLA:
                    score -= 30

            if requirements.get('high_strength'):
                if material in [LEGOMaterial.PETG, LEGOMaterial.ABS]:
                    score += 15

            if requirements.get('tight_tolerance'):
                # Materials with lower shrinkage
                score -= (profile.shrinkage_factor - 1.0) * 1000

            if requirements.get('flexible'):
                if material == LEGOMaterial.TPU:
                    score += 50
                else:
                    score -= 20

            if requirements.get('easy_printing'):
                if material == LEGOMaterial.PLA:
                    score += 20
                elif material in [LEGOMaterial.ABS, LEGOMaterial.ASA]:
                    score -= 15

            if requirements.get('optimal_clutch'):
                score += profile.lego_suitability * 20

            scores[material] = score

        # Find best material
        best_material = max(scores.keys(), key=lambda m: scores[m])
        best_profile = MATERIAL_PROFILES[best_material]

        return {
            'recommended_material': best_material.value,
            'profile_name': best_profile.name,
            'lego_suitability': best_profile.lego_suitability,
            'score': scores[best_material],
            'all_scores': {m.value: s for m, s in sorted(
                scores.items(), key=lambda x: x[1], reverse=True
            )},
            'recommended_settings': {
                'nozzle_temperature': best_profile.nozzle_temp_default,
                'bed_temperature': best_profile.bed_temp_default,
                'print_speed': best_profile.print_speed_default,
                'flow_rate': best_profile.flow_rate_default,
            }
        }


# === Backward Compatibility Alias ===

# Alias for backward compatibility with existing code
ParameterAdjuster = LEGOParameterAdjuster


# === Module Exports ===

__all__ = [
    # Main classes
    'LEGOParameterAdjuster',
    'ParameterAdjuster',  # Backward compatible alias

    # Enums
    'LEGOMaterial',
    'LEGOBrickType',
    'LEGOFeature',
    'LEGODefectType',
    'PrintPhase',
    'AdjustmentPriority',

    # Data classes
    'ParameterBounds',
    'Adjustment',
    'MaterialProfile',
    'DefectCorrectionRule',
    'FeatureParameters',
    'ClutchPowerAnalysis',
    'DimensionalAnalysis',

    # Constants
    'LEGOSpecs',
    'MATERIAL_PROFILES',
    'DEFECT_CORRECTION_RULES',
    'FEATURE_PARAMETERS',
]
