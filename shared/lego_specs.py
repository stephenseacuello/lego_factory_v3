"""
LEGO Brick Dimension Standards v2.0

Official LEGO dimensions based on measurements, patents, and industry research.
All measurements in millimeters unless otherwise noted.

References:
- LEGO Patents (1958-present)
- Christoph Bartneck's measurements
- The Wave Engineer manufacturing analysis
- ISA-95 manufacturing standards integration

Corrections from v1.0:
- Wall thickness: 1.5mm -> 1.6mm (matches LEGO Unit)
- Added inter-brick clearance (0.1mm per side)
- Pin hole diameter: 4.8mm -> 4.9mm (for bearing fit)
- Added bar diameter constant (3.18mm)
- Rib height: 8.0mm -> 9.6mm (full height, no recess)
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional
from enum import Enum


class ManufacturingProcess(Enum):
    """Manufacturing process types for tolerance selection."""
    INJECTION_MOLDING = "injection_molding"
    FDM_STANDARD = "fdm_standard"
    FDM_FINE = "fdm_fine"
    SLA_RESIN = "sla_resin"
    CNC_MILLING = "cnc_milling"


class WorkCenterType(Enum):
    """Types of manufacturing work centers (ISA-95 Level 2)."""
    DESIGN_WORKSTATION = "DESIGN_WORKSTATION"
    FDM_PRINTER = "FDM_PRINTER"
    SLA_PRINTER = "SLA_PRINTER"
    CNC_MILL = "CNC_MILL"
    LASER_ENGRAVER = "LASER_ENGRAVER"
    INSPECTION_STATION = "INSPECTION_STATION"
    ASSEMBLY_STATION = "ASSEMBLY_STATION"


@dataclass(frozen=True)
class LegoStandard:
    """
    Official LEGO brick dimensions (in mm) - CORRECTED v2.0

    All dimensions follow the LEGO Unit (LDU) system where 1 LDU = 1.6mm
    and stud pitch = 5 LDU = 8.0mm.
    """

    # === Fundamental Units ===
    LDU: float = 1.6  # LEGO Design Unit - base measurement
    STUD_PITCH: float = 8.0  # Distance between stud centers (5 LDU)

    # === Stud Dimensions ===
    STUD_DIAMETER: float = 4.8  # Cylinder on top (3 LDU)
    STUD_HEIGHT: float = 1.7  # Height above brick surface
    STUD_INNER_DIAMETER: float = 3.0  # Hollow stud interior
    STUD_INNER_DIAMETER_DUPLO: float = 4.9  # For Duplo compatibility

    # === Brick Heights ===
    BRICK_HEIGHT: float = 9.6  # Standard brick (6 LDU, 3 plates)
    PLATE_HEIGHT: float = 3.2  # Plate = 1/3 brick height (2 LDU)
    TILE_HEIGHT: float = 3.2  # Same as plate, no studs

    # === CORRECTED Wall Structure ===
    WALL_THICKNESS: float = 1.6  # CORRECTED: 1.5 -> 1.6 (1 LDU)
    TOP_THICKNESS: float = 1.0  # Top surface thickness
    BOTTOM_THICKNESS: float = 0.0  # Open bottom (hollow)

    # === CORRECTED Inter-brick Clearance ===
    CLEARANCE_PER_SIDE: float = 0.1  # NEW: Gap per brick side
    INTER_BRICK_GAP: float = 0.2  # NEW: Total gap between adjacent bricks

    # === Bottom Tubes (for clutch power) ===
    TUBE_OUTER_DIAMETER: float = 6.51
    TUBE_INNER_DIAMETER: float = 4.8  # Matches stud for grip

    # === CORRECTED Bottom Ribs (for 1xN bricks) ===
    RIB_THICKNESS: float = 1.0
    RIB_HEIGHT: float = 9.6  # CORRECTED: Full height (was 8.0 with 2mm recess)
    RIB_BOTTOM_RECESS: float = 0.0  # CORRECTED: 2.0 -> 0.0 (ribs touch bottom)

    # === CORRECTED Technic Dimensions ===
    TECHNIC_PIN_HOLE_DIAMETER: float = 4.9  # CORRECTED: 4.8 -> 4.9 (bearing fit)
    TECHNIC_AXLE_HOLE_SIZE: float = 4.8  # Cross-shaped axle hole
    TECHNIC_AXLE_CROSS_WIDTH: float = 1.8  # Width of each arm of cross
    TECHNIC_HOLE_SPACING: float = 8.0  # Same as stud pitch
    TECHNIC_BEAM_HEIGHT: float = 7.8  # Standard liftarm height
    TECHNIC_BEAM_HEIGHT_NARROW: float = 7.4  # Narrow beam variant

    # === NEW Bar/Rod/Clip Constants ===
    BAR_DIAMETER: float = 3.18  # Standard bar diameter (minifig hand grip)
    BAR_CLUTCH_DIAMETER: float = 3.18  # Bar for clutch connections
    CLIP_INNER_DIAMETER: float = 3.2  # Slightly larger for bar fit
    CLIP_OUTER_DIAMETER: float = 4.85  # Outer clip dimension

    # === SNOT (Studs Not On Top) Geometry ===
    HALF_PLATE_OFFSET: float = 1.6  # Offset for side-stud mounting (1 LDU)
    SNOT_BRACKET_OFFSET: float = 3.2  # Common bracket offset (2 LDU)

    # === Duplo Dimensions (2:1 scale) ===
    DUPLO_SCALE: float = 2.0
    DUPLO_STUD_PITCH: float = 16.0  # 2x standard
    DUPLO_STUD_DIAMETER: float = 9.6  # 2x standard
    DUPLO_STUD_HEIGHT: float = 4.8  # Hollow, accepts standard studs
    DUPLO_BRICK_HEIGHT: float = 19.2  # 2x standard
    DUPLO_HOLLOW_STUD_ID: float = 4.9  # Accepts standard LEGO studs

    # === Manufacturing Tolerances (Official LEGO) ===
    LEGO_MOLD_TOLERANCE: float = 0.002  # 2 microns - injection mold precision
    LEGO_PART_TOLERANCE: float = 0.01  # 10 microns - finished part tolerance
    STUD_TOLERANCE: float = 0.01  # Stud diameter tolerance

    # === 3D Printing Tolerances ===
    FDM_TOLERANCE: float = 0.15  # Standard FDM printing tolerance
    FDM_FINE_TOLERANCE: float = 0.10  # Fine FDM (0.25mm nozzle)
    SLA_TOLERANCE: float = 0.05  # SLA/resin printing tolerance
    CNC_TOLERANCE: float = 0.02  # CNC milling tolerance

    # === Slope Angles (degrees) ===
    SLOPE_18: float = 18.0
    SLOPE_25: float = 25.0  # Added
    SLOPE_33: float = 33.0
    SLOPE_45: float = 45.0
    SLOPE_65: float = 65.0
    SLOPE_75: float = 75.0

    # === Technic Connector Angles ===
    CONNECTOR_90: float = 90.0
    CONNECTOR_112_5: float = 112.5
    CONNECTOR_135: float = 135.0
    CONNECTOR_157_5: float = 157.5
    CONNECTOR_180: float = 180.0

    # Backwards compatibility alias
    TECHNIC_HOLE_DIAMETER: float = 4.9  # Alias for PIN_HOLE_DIAMETER


# Singleton instance
LEGO = LegoStandard()


# === Manufacturing Tolerance Profiles ===

MANUFACTURING_TOLERANCES: Dict[str, Dict[str, float]] = {
    "injection_molding": {
        "general": 0.01,
        "stud": 0.01,
        "xy_compensation": 0.0,
        "shrinkage": 0.004,  # 0.4% for ABS
        "description": "Official LEGO injection molding quality"
    },
    "fdm_standard": {
        "general": 0.15,
        "stud": 0.20,
        "xy_compensation": -0.08,
        "shrinkage": 0.002,  # PLA
        "description": "Consumer FDM with 0.4mm nozzle, 0.2mm layers"
    },
    "fdm_fine": {
        "general": 0.10,
        "stud": 0.15,
        "xy_compensation": -0.05,
        "shrinkage": 0.002,
        "description": "High-quality FDM with 0.25mm nozzle, 0.12mm layers"
    },
    "sla_resin": {
        "general": 0.05,
        "stud": 0.08,
        "xy_compensation": -0.02,
        "shrinkage": 0.001,
        "description": "SLA/resin printing - high precision but brittle"
    },
    "cnc_milling": {
        "general": 0.02,
        "stud": 0.03,
        "xy_compensation": 0.0,
        "shrinkage": 0.0,
        "description": "CNC machined ABS or Delrin"
    }
}


# === Color-Specific Shrinkage Compensation ===

SHRINKAGE_COMPENSATION: Dict[str, float] = {
    # PLA colors (multiply dimensions by factor)
    "pla_white": 1.002,
    "pla_black": 1.001,
    "pla_red": 1.001,
    "pla_yellow": 1.002,
    "pla_blue": 1.001,
    "pla_green": 1.001,
    "pla_orange": 1.001,
    "pla_trans": 1.003,  # Transparent materials shrink more

    # PETG colors
    "petg_white": 1.004,
    "petg_black": 1.003,
    "petg_any": 1.003,

    # ABS colors (significant shrinkage)
    "abs_white": 1.004,
    "abs_black": 1.005,
    "abs_red": 1.004,
    "abs_yellow": 1.004,
    "abs_dark_brown": 1.006,  # Dark colors shrink more
    "abs_reddish_brown": 1.006,
    "abs_any": 1.005,

    # ASA colors
    "asa_any": 1.005,
}


def get_shrinkage_factor(material: str, color: str = "any") -> float:
    """
    Get shrinkage compensation factor for material/color combination.

    Args:
        material: Material type (pla, petg, abs, asa)
        color: Color name or 'any' for default

    Returns:
        Multiplication factor for dimensions (e.g., 1.004 = 0.4% larger)
    """
    key = f"{material.lower()}_{color.lower()}"
    if key in SHRINKAGE_COMPENSATION:
        return SHRINKAGE_COMPENSATION[key]

    # Try material with 'any' color
    any_key = f"{material.lower()}_any"
    if any_key in SHRINKAGE_COMPENSATION:
        return SHRINKAGE_COMPENSATION[any_key]

    # Default: no compensation
    return 1.0


# === Material Properties (for costing and manufacturing) ===

MATERIAL_PROPERTIES: Dict[str, Dict[str, float]] = {
    "abs": {
        "density": 1.05,  # g/cm³
        "shrinkage": 0.004,  # 0.4%
        "shrinkage_dark": 0.005,  # 0.5% for dark colors
        "melt_temp": 232,  # °C
        "bed_temp": 100,  # °C
        "cost_per_kg": 25.0,  # USD
        "tensile_strength": 40,  # MPa
    },
    "pla": {
        "density": 1.24,  # g/cm³
        "shrinkage": 0.002,  # 0.2%
        "melt_temp": 215,  # °C
        "bed_temp": 60,  # °C
        "cost_per_kg": 20.0,  # USD
        "tensile_strength": 50,  # MPa
    },
    "petg": {
        "density": 1.27,  # g/cm³
        "shrinkage": 0.003,  # 0.3%
        "melt_temp": 240,  # °C
        "bed_temp": 85,  # °C
        "cost_per_kg": 22.0,  # USD
        "tensile_strength": 53,  # MPa
        "notes": "Best for 3D printed LEGO - good flex for clutch power"
    },
    "asa": {
        "density": 1.07,  # g/cm³
        "shrinkage": 0.004,  # 0.4%
        "melt_temp": 260,  # °C
        "bed_temp": 100,  # °C
        "cost_per_kg": 30.0,  # USD
        "tensile_strength": 42,  # MPa
        "notes": "UV resistant, good for outdoor use"
    },
    "delrin": {
        "density": 1.41,  # g/cm³
        "shrinkage": 0.02,  # 2% - significant for CNC
        "melt_temp": 175,  # °C
        "cost_per_kg": 45.0,  # USD
        "tensile_strength": 70,  # MPa
        "notes": "CNC machining, excellent clutch power"
    }
}


# === Helper Functions ===

def brick_dimensions(
    studs_x: int, studs_y: int, height_units: float = 1.0
) -> Tuple[float, float, float]:
    """
    Calculate brick dimensions for given stud configuration.

    Args:
        studs_x: Number of studs in X direction
        studs_y: Number of studs in Y direction
        height_units: Height in brick units (1.0 = brick, 0.333 = plate)

    Returns:
        Tuple of (width, depth, height) in mm
    """
    width = studs_x * LEGO.STUD_PITCH
    depth = studs_y * LEGO.STUD_PITCH
    height = height_units * LEGO.BRICK_HEIGHT
    return (width, depth, height)


def brick_dimensions_with_clearance(
    studs_x: int, studs_y: int, height_units: float = 1.0
) -> Tuple[float, float, float]:
    """
    Calculate brick dimensions with manufacturing clearance applied.

    The clearance (0.1mm per side) ensures proper fit between bricks.

    Args:
        studs_x: Number of studs in X direction
        studs_y: Number of studs in Y direction
        height_units: Height in brick units

    Returns:
        Tuple of (width, depth, height) in mm with clearance subtracted
    """
    width = studs_x * LEGO.STUD_PITCH - LEGO.INTER_BRICK_GAP
    depth = studs_y * LEGO.STUD_PITCH - LEGO.INTER_BRICK_GAP
    height = height_units * LEGO.BRICK_HEIGHT
    return (width, depth, height)


def stud_positions(studs_x: int, studs_y: int) -> List[Tuple[float, float]]:
    """
    Calculate center positions for all studs.

    Returns:
        List of (x, y) tuples for stud centers
    """
    positions = []
    for i in range(studs_x):
        for j in range(studs_y):
            x = (i + 0.5) * LEGO.STUD_PITCH
            y = (j + 0.5) * LEGO.STUD_PITCH
            positions.append((x, y))
    return positions


def tube_positions(studs_x: int, studs_y: int) -> List[Tuple[float, float]]:
    """
    Calculate center positions for bottom tubes.
    Tubes go between studs, so for NxM brick there are (N-1)x(M-1) tubes.

    Returns:
        List of (x, y) tuples for tube centers
    """
    if studs_x < 2 or studs_y < 2:
        return []  # No tubes for 1xN bricks

    positions = []
    for i in range(studs_x - 1):
        for j in range(studs_y - 1):
            x = (i + 1) * LEGO.STUD_PITCH
            y = (j + 1) * LEGO.STUD_PITCH
            positions.append((x, y))
    return positions


def rib_positions(studs_x: int, studs_y: int) -> List[Tuple[float, float, str]]:
    """
    Calculate center positions for bottom ribs (1xN bricks only).

    Returns:
        List of (x, y, orientation) tuples
    """
    if studs_x == 1 and studs_y > 1:
        # Ribs perpendicular to length
        return [(LEGO.STUD_PITCH / 2, (i + 1) * LEGO.STUD_PITCH, "x") for i in range(studs_y - 1)]
    elif studs_y == 1 and studs_x > 1:
        # Ribs perpendicular to length
        return [((i + 1) * LEGO.STUD_PITCH, LEGO.STUD_PITCH / 2, "y") for i in range(studs_x - 1)]
    return []


def calculate_volume(
    studs_x: int, studs_y: int, height_units: float = 1.0, hollow: bool = True
) -> float:
    """
    Calculate approximate volume of a brick in mm³.

    Args:
        studs_x: Number of studs in X direction
        studs_y: Number of studs in Y direction
        height_units: Height in brick units
        hollow: Whether brick is hollow (standard) or solid

    Returns:
        Volume in mm³
    """
    import math

    width, depth, height = brick_dimensions(studs_x, studs_y, height_units)

    # Outer volume
    outer_volume = width * depth * height

    # Stud volume (cylinders)
    stud_volume = (
        studs_x * studs_y *
        math.pi * (LEGO.STUD_DIAMETER / 2) ** 2 * LEGO.STUD_HEIGHT
    )

    if not hollow:
        return outer_volume + stud_volume

    # Hollow interior
    inner_width = width - 2 * LEGO.WALL_THICKNESS
    inner_depth = depth - 2 * LEGO.WALL_THICKNESS
    inner_height = height - LEGO.TOP_THICKNESS
    hollow_volume = max(0, inner_width * inner_depth * inner_height)

    # Tube volume (adds back material)
    num_tubes = max(0, (studs_x - 1) * (studs_y - 1))
    tube_volume = (
        num_tubes *
        math.pi * ((LEGO.TUBE_OUTER_DIAMETER / 2) ** 2 - (LEGO.TUBE_INNER_DIAMETER / 2) ** 2) *
        inner_height
    )

    return outer_volume + stud_volume - hollow_volume + tube_volume


def calculate_weight(volume_mm3: float, material: str = "abs") -> float:
    """
    Calculate weight of a brick given its volume.

    Args:
        volume_mm3: Volume in cubic millimeters
        material: Material type (abs, pla, petg, etc.)

    Returns:
        Weight in grams
    """
    density = MATERIAL_PROPERTIES.get(material, {}).get("density", 1.05)
    volume_cm3 = volume_mm3 / 1000  # mm³ to cm³
    return volume_cm3 * density


def validate_clutch_power(stud_diameter: float, tube_id: float) -> Dict[str, any]:
    """
    Validate interference fit for proper clutch power.

    Clutch power is the ability of LEGO bricks to snap together tightly
    while being easy to separate. It's an interference fit.

    Args:
        stud_diameter: Actual stud diameter in mm
        tube_id: Actual tube inner diameter in mm

    Returns:
        Dict with interference_mm, in_range, and assessment
    """
    # Interference = stud diameter - gap between tube and wall
    wall_gap = tube_id - LEGO.WALL_THICKNESS
    interference = stud_diameter - wall_gap

    # Optimal interference range for good clutch power
    optimal_min = 0.08  # mm
    optimal_max = 0.15  # mm

    in_range = optimal_min <= interference <= optimal_max

    if interference < optimal_min:
        assessment = "too_loose"
    elif interference > optimal_max:
        assessment = "too_tight"
    else:
        assessment = "optimal"

    return {
        "interference_mm": round(interference, 3),
        "in_range": in_range,
        "assessment": assessment,
        "optimal_range": (optimal_min, optimal_max)
    }


# === Brick Type Definitions ===

BRICK_TYPES: Dict[str, Dict] = {
    "standard": {
        "description": "Standard brick with studs",
        "has_studs": True,
        "hollow": True,
        "height_units": 1.0,
    },
    "plate": {
        "description": "Thin plate (1/3 brick height)",
        "has_studs": True,
        "hollow": True,
        "height_units": 1 / 3,
    },
    "tile": {
        "description": "Flat tile without studs",
        "has_studs": False,
        "hollow": False,
        "height_units": 1 / 3,
    },
    "slope": {
        "description": "Sloped brick",
        "has_studs": True,
        "hollow": True,
        "height_units": 1.0,
        "slope_angle": 45.0,
    },
    "technic": {
        "description": "Technic brick with holes",
        "has_studs": True,
        "hollow": True,
        "height_units": 1.0,
        "has_holes": True,
    },
    "technic_liftarm": {
        "description": "Technic liftarm (no studs)",
        "has_studs": False,
        "hollow": False,
        "height_units": 1.0,
        "has_holes": True,
        "hole_type": "pin",
    },
    "duplo": {
        "description": "DUPLO brick (2x LEGO scale)",
        "has_studs": True,
        "hollow": True,
        "hollow_studs": True,
        "height_units": 2.0,
        "scale": 2.0,
    },
    "baseplate": {
        "description": "Thin baseplate",
        "has_studs": True,
        "hollow": False,
        "height_units": 0.1,
    },
}


# === Common Brick Configurations ===

COMMON_BRICKS: List[Dict] = [
    # Single-row bricks
    {"name": "1x1", "studs_x": 1, "studs_y": 1},
    {"name": "1x2", "studs_x": 1, "studs_y": 2},
    {"name": "1x3", "studs_x": 1, "studs_y": 3},
    {"name": "1x4", "studs_x": 1, "studs_y": 4},
    {"name": "1x6", "studs_x": 1, "studs_y": 6},
    {"name": "1x8", "studs_x": 1, "studs_y": 8},
    {"name": "1x10", "studs_x": 1, "studs_y": 10},
    {"name": "1x12", "studs_x": 1, "studs_y": 12},
    {"name": "1x16", "studs_x": 1, "studs_y": 16},

    # 2-wide bricks
    {"name": "2x2", "studs_x": 2, "studs_y": 2},
    {"name": "2x3", "studs_x": 2, "studs_y": 3},
    {"name": "2x4", "studs_x": 2, "studs_y": 4},
    {"name": "2x6", "studs_x": 2, "studs_y": 6},
    {"name": "2x8", "studs_x": 2, "studs_y": 8},
    {"name": "2x10", "studs_x": 2, "studs_y": 10},

    # Large bricks
    {"name": "4x4", "studs_x": 4, "studs_y": 4},
    {"name": "4x6", "studs_x": 4, "studs_y": 6},
    {"name": "4x8", "studs_x": 4, "studs_y": 8},
    {"name": "4x10", "studs_x": 4, "studs_y": 10},
    {"name": "6x6", "studs_x": 6, "studs_y": 6},
    {"name": "6x8", "studs_x": 6, "studs_y": 8},
    {"name": "8x8", "studs_x": 8, "studs_y": 8},

    # Baseplates
    {"name": "8x16", "studs_x": 8, "studs_y": 16, "type": "baseplate"},
    {"name": "16x16", "studs_x": 16, "studs_y": 16, "type": "baseplate"},
    {"name": "32x32", "studs_x": 32, "studs_y": 32, "type": "baseplate"},
    {"name": "48x48", "studs_x": 48, "studs_y": 48, "type": "baseplate"},
]


# === ISA-95 Manufacturing Operations ===

OPERATION_CODES: Dict[str, Dict] = {
    "CAD_DESIGN": {
        "description": "CAD design in Fusion 360",
        "work_center_type": WorkCenterType.DESIGN_WORKSTATION,
        "default_time_min": 5.0,
    },
    "3D_PRINT_FDM": {
        "description": "FDM 3D printing",
        "work_center_type": WorkCenterType.FDM_PRINTER,
        "default_time_min": 30.0,  # Varies by size
    },
    "3D_PRINT_SLA": {
        "description": "SLA/Resin 3D printing",
        "work_center_type": WorkCenterType.SLA_PRINTER,
        "default_time_min": 45.0,
    },
    "CNC_MILL": {
        "description": "CNC milling operation",
        "work_center_type": WorkCenterType.CNC_MILL,
        "default_time_min": 15.0,
    },
    "LASER_ENGRAVE": {
        "description": "Laser engraving",
        "work_center_type": WorkCenterType.LASER_ENGRAVER,
        "default_time_min": 5.0,
    },
    "QC_INSPECT": {
        "description": "Quality control inspection",
        "work_center_type": WorkCenterType.INSPECTION_STATION,
        "default_time_min": 2.0,
    },
    "QC_FIT_TEST": {
        "description": "LEGO fit/clutch power test",
        "work_center_type": WorkCenterType.INSPECTION_STATION,
        "default_time_min": 1.0,
    },
    "ASSEMBLY": {
        "description": "Manual assembly operation",
        "work_center_type": WorkCenterType.ASSEMBLY_STATION,
        "default_time_min": 5.0,
    },
}


# === OEE Downtime Reason Codes ===

DOWNTIME_REASONS: Dict[str, str] = {
    "SETUP": "Machine setup/changeover",
    "MATERIAL": "Waiting for material",
    "MAINTENANCE_PLANNED": "Scheduled maintenance",
    "MAINTENANCE_UNPLANNED": "Unplanned breakdown",
    "QUALITY_ISSUE": "Quality problem/rework",
    "OPERATOR": "Operator not available",
    "TOOLING": "Tool change/problem",
    "POWER": "Power outage",
    "SOFTWARE": "Software/control issue",
    "CALIBRATION": "Machine calibration",
    "FILAMENT_CHANGE": "Filament/material change",
    "BED_ADHESION": "Print bed adhesion issue",
    "CLOG": "Nozzle/extruder clog",
    "LAYER_SHIFT": "Layer shift detected",
    "OTHER": "Other unspecified reason",
}


# === Quality Defect Codes (LEGO-specific) ===

DEFECT_CODES: Dict[str, str] = {
    "DIM_OOS": "Dimension out of specification",
    "STUD_FIT_LOOSE": "Stud fit too loose",
    "STUD_FIT_TIGHT": "Stud fit too tight",
    "CLUTCH_WEAK": "Insufficient clutch power",
    "CLUTCH_STRONG": "Excessive clutch power",
    "SURFACE_ROUGH": "Surface finish too rough",
    "LAYER_LINES": "Visible layer lines",
    "WARPING": "Part warping/distortion",
    "STRINGING": "Stringing/oozing",
    "UNDER_EXTRUSION": "Under-extrusion",
    "OVER_EXTRUSION": "Over-extrusion",
    "COLOR_MISMATCH": "Color doesn't match spec",
    "CRACK": "Crack or fracture",
    "INCOMPLETE": "Incomplete print/feature",
    "CONTAMINATION": "Foreign material contamination",
}


# === Convenience exports for common constants ===
# These allow `from lego_specs import STUD_PITCH` style imports

STUD_PITCH = LEGO.STUD_PITCH  # 8.0mm - Distance between stud centers
STUD_DIAMETER = LEGO.STUD_DIAMETER  # 4.8mm - Stud diameter
STUD_HEIGHT = LEGO.STUD_HEIGHT  # 1.7mm - Stud height above brick
BRICK_HEIGHT = LEGO.BRICK_HEIGHT  # 9.6mm - Standard brick height
PLATE_HEIGHT = LEGO.PLATE_HEIGHT  # 3.2mm - Plate height
WALL_THICKNESS = LEGO.WALL_THICKNESS  # 1.6mm - Wall thickness
TOP_THICKNESS = LEGO.TOP_THICKNESS  # 1.0mm - Top surface thickness
TUBE_OUTER_DIAMETER = LEGO.TUBE_OUTER_DIAMETER  # 6.51mm
TUBE_INNER_DIAMETER = LEGO.TUBE_INNER_DIAMETER  # 4.8mm
LDU = LEGO.LDU  # 1.6mm - LEGO Design Unit
