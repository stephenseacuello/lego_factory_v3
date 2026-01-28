"""
LEGO Factory v3 - LEGO Brick Dimension Standards
================================================
Official LEGO dimensions based on measurements, patents, and industry research.
All measurements in millimeters unless otherwise noted.

References:
- LEGO Patents (1958-present)
- Christoph Bartneck's measurements
- ISA-95 manufacturing standards integration
"""

from dataclasses import dataclass
from typing import Tuple, Dict, List
from enum import Enum
import math


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
    Official LEGO brick dimensions (in mm).

    All dimensions follow the LEGO Unit (LDU) system where 1 LDU = 1.6mm
    and stud pitch = 5 LDU = 8.0mm.
    """

    # === Fundamental Units ===
    LDU: float = 1.6  # LEGO Design Unit
    STUD_PITCH: float = 8.0  # Distance between stud centers

    # === Stud Dimensions ===
    STUD_DIAMETER: float = 4.8
    STUD_HEIGHT: float = 1.7
    STUD_INNER_DIAMETER: float = 3.0
    STUD_INNER_DIAMETER_DUPLO: float = 4.9

    # === Brick Heights ===
    BRICK_HEIGHT: float = 9.6  # Standard brick (6 LDU, 3 plates)
    PLATE_HEIGHT: float = 3.2  # Plate = 1/3 brick height
    TILE_HEIGHT: float = 3.2

    # === Wall Structure ===
    WALL_THICKNESS: float = 1.6  # 1 LDU
    TOP_THICKNESS: float = 1.0
    BOTTOM_THICKNESS: float = 0.0

    # === Inter-brick Clearance ===
    CLEARANCE_PER_SIDE: float = 0.1
    INTER_BRICK_GAP: float = 0.2

    # === Bottom Tubes ===
    TUBE_OUTER_DIAMETER: float = 6.51
    TUBE_INNER_DIAMETER: float = 4.8

    # === Bottom Ribs ===
    RIB_THICKNESS: float = 1.0
    RIB_HEIGHT: float = 9.6

    # === Technic Dimensions ===
    TECHNIC_PIN_HOLE_DIAMETER: float = 4.9
    TECHNIC_AXLE_HOLE_SIZE: float = 4.8
    TECHNIC_AXLE_CROSS_WIDTH: float = 1.8
    TECHNIC_HOLE_SPACING: float = 8.0
    TECHNIC_BEAM_HEIGHT: float = 7.8

    # === Bar/Rod/Clip Constants ===
    BAR_DIAMETER: float = 3.18
    CLIP_INNER_DIAMETER: float = 3.2
    CLIP_OUTER_DIAMETER: float = 4.85

    # === SNOT Geometry ===
    HALF_PLATE_OFFSET: float = 1.6
    SNOT_BRACKET_OFFSET: float = 3.2

    # === Duplo Dimensions ===
    DUPLO_SCALE: float = 2.0
    DUPLO_STUD_PITCH: float = 16.0
    DUPLO_STUD_DIAMETER: float = 9.6
    DUPLO_BRICK_HEIGHT: float = 19.2

    # === Manufacturing Tolerances ===
    LEGO_MOLD_TOLERANCE: float = 0.002
    LEGO_PART_TOLERANCE: float = 0.01
    FDM_TOLERANCE: float = 0.15
    SLA_TOLERANCE: float = 0.05
    CNC_TOLERANCE: float = 0.02

    # === Slope Angles (degrees) ===
    SLOPE_18: float = 18.0
    SLOPE_33: float = 33.0
    SLOPE_45: float = 45.0
    SLOPE_65: float = 65.0
    SLOPE_75: float = 75.0


LEGO = LegoStandard()


MANUFACTURING_TOLERANCES: Dict[str, Dict[str, float]] = {
    "injection_molding": {
        "general": 0.01,
        "stud": 0.01,
        "xy_compensation": 0.0,
        "shrinkage": 0.004,
    },
    "fdm_standard": {
        "general": 0.15,
        "stud": 0.20,
        "xy_compensation": -0.08,
        "shrinkage": 0.002,
    },
    "fdm_fine": {
        "general": 0.10,
        "stud": 0.15,
        "xy_compensation": -0.05,
        "shrinkage": 0.002,
    },
    "sla_resin": {
        "general": 0.05,
        "stud": 0.08,
        "xy_compensation": -0.02,
        "shrinkage": 0.001,
    },
    "cnc_milling": {
        "general": 0.02,
        "stud": 0.03,
        "xy_compensation": 0.0,
        "shrinkage": 0.0,
    }
}


MATERIAL_PROPERTIES: Dict[str, Dict[str, float]] = {
    "abs": {
        "density": 1.05,
        "shrinkage": 0.004,
        "melt_temp": 232,
        "bed_temp": 100,
        "cost_per_kg": 25.0,
        "tensile_strength": 40,
    },
    "pla": {
        "density": 1.24,
        "shrinkage": 0.002,
        "melt_temp": 215,
        "bed_temp": 60,
        "cost_per_kg": 20.0,
        "tensile_strength": 50,
    },
    "petg": {
        "density": 1.27,
        "shrinkage": 0.003,
        "melt_temp": 240,
        "bed_temp": 85,
        "cost_per_kg": 22.0,
        "tensile_strength": 53,
    },
}


BRICK_TYPES: Dict[str, Dict] = {
    "standard": {"has_studs": True, "hollow": True, "height_units": 1.0},
    "plate": {"has_studs": True, "hollow": True, "height_units": 1 / 3},
    "tile": {"has_studs": False, "hollow": False, "height_units": 1 / 3},
    "slope": {"has_studs": True, "hollow": True, "height_units": 1.0, "slope_angle": 45.0},
    "technic": {"has_studs": True, "hollow": True, "height_units": 1.0, "has_holes": True},
    "baseplate": {"has_studs": True, "hollow": False, "height_units": 0.1},
}


COMMON_BRICKS: List[Dict] = [
    {"name": "1x1", "studs_x": 1, "studs_y": 1},
    {"name": "1x2", "studs_x": 1, "studs_y": 2},
    {"name": "1x4", "studs_x": 1, "studs_y": 4},
    {"name": "1x6", "studs_x": 1, "studs_y": 6},
    {"name": "1x8", "studs_x": 1, "studs_y": 8},
    {"name": "2x2", "studs_x": 2, "studs_y": 2},
    {"name": "2x4", "studs_x": 2, "studs_y": 4},
    {"name": "2x6", "studs_x": 2, "studs_y": 6},
    {"name": "2x8", "studs_x": 2, "studs_y": 8},
    {"name": "4x4", "studs_x": 4, "studs_y": 4},
    {"name": "4x6", "studs_x": 4, "studs_y": 6},
    {"name": "8x8", "studs_x": 8, "studs_y": 8},
    {"name": "16x16", "studs_x": 16, "studs_y": 16, "type": "baseplate"},
    {"name": "32x32", "studs_x": 32, "studs_y": 32, "type": "baseplate"},
]


def brick_dimensions(
    studs_x: int, studs_y: int, height_units: float = 1.0
) -> Tuple[float, float, float]:
    """Calculate brick dimensions for given stud configuration."""
    width = studs_x * LEGO.STUD_PITCH
    depth = studs_y * LEGO.STUD_PITCH
    height = height_units * LEGO.BRICK_HEIGHT
    return (width, depth, height)


def brick_dimensions_with_clearance(
    studs_x: int, studs_y: int, height_units: float = 1.0
) -> Tuple[float, float, float]:
    """Calculate brick dimensions with manufacturing clearance."""
    width = studs_x * LEGO.STUD_PITCH - LEGO.INTER_BRICK_GAP
    depth = studs_y * LEGO.STUD_PITCH - LEGO.INTER_BRICK_GAP
    height = height_units * LEGO.BRICK_HEIGHT
    return (width, depth, height)


def stud_positions(studs_x: int, studs_y: int) -> List[Tuple[float, float]]:
    """Calculate center positions for all studs."""
    positions = []
    for i in range(studs_x):
        for j in range(studs_y):
            x = (i + 0.5) * LEGO.STUD_PITCH
            y = (j + 0.5) * LEGO.STUD_PITCH
            positions.append((x, y))
    return positions


def tube_positions(studs_x: int, studs_y: int) -> List[Tuple[float, float]]:
    """Calculate center positions for bottom tubes."""
    if studs_x < 2 or studs_y < 2:
        return []

    positions = []
    for i in range(studs_x - 1):
        for j in range(studs_y - 1):
            x = (i + 1) * LEGO.STUD_PITCH
            y = (j + 1) * LEGO.STUD_PITCH
            positions.append((x, y))
    return positions


def calculate_volume(
    studs_x: int, studs_y: int, height_units: float = 1.0, hollow: bool = True
) -> float:
    """Calculate approximate volume of a brick in mm³."""
    width, depth, height = brick_dimensions(studs_x, studs_y, height_units)

    outer_volume = width * depth * height

    stud_volume = (
        studs_x * studs_y *
        math.pi * (LEGO.STUD_DIAMETER / 2) ** 2 * LEGO.STUD_HEIGHT
    )

    if not hollow:
        return outer_volume + stud_volume

    inner_width = width - 2 * LEGO.WALL_THICKNESS
    inner_depth = depth - 2 * LEGO.WALL_THICKNESS
    inner_height = height - LEGO.TOP_THICKNESS
    hollow_volume = max(0, inner_width * inner_depth * inner_height)

    num_tubes = max(0, (studs_x - 1) * (studs_y - 1))
    tube_volume = (
        num_tubes *
        math.pi * ((LEGO.TUBE_OUTER_DIAMETER / 2) ** 2 - (LEGO.TUBE_INNER_DIAMETER / 2) ** 2) *
        inner_height
    )

    return outer_volume + stud_volume - hollow_volume + tube_volume


def calculate_weight(volume_mm3: float, material: str = "abs") -> float:
    """Calculate weight of a brick given its volume."""
    density = MATERIAL_PROPERTIES.get(material, {}).get("density", 1.05)
    volume_cm3 = volume_mm3 / 1000
    return volume_cm3 * density
