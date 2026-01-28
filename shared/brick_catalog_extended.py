"""
LEGO Brick Catalog - Extended Edition

Complete catalog of 200+ LEGO element types organized by category.
This is the most comprehensive programmatic LEGO parts library.

Categories:
- Basic Bricks
- Plates
- Tiles
- Slopes (standard, curved, inverted, cheese)
- Technic (bricks, beams, liftarms, connectors, pins, axles)
- Modified Bricks (SNOT, clips, bars, handles, masonry)
- Round Elements (bricks, plates, cones, domes, dishes)
- Arches
- Wedges & Wings
- Windows & Doors
- Fences & Railings
- Panels
- Brackets
- Hinges & Turntables
- Containers
- Vehicle Parts
- Specialty Elements
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal, Union
from enum import Enum, auto


# ============================================================================
# ENUMS
# ============================================================================


class Category(Enum):
    BRICK = "brick"
    PLATE = "plate"
    TILE = "tile"
    SLOPE = "slope"
    SLOPE_CURVED = "slope_curved"
    SLOPE_INVERTED = "slope_inverted"
    TECHNIC_BRICK = "technic_brick"
    TECHNIC_BEAM = "technic_beam"
    TECHNIC_LIFTARM = "technic_liftarm"
    TECHNIC_CONNECTOR = "technic_connector"
    TECHNIC_PIN = "technic_pin"
    TECHNIC_AXLE = "technic_axle"
    TECHNIC_GEAR = "technic_gear"
    MODIFIED = "modified"
    SNOT = "snot"
    ROUND_BRICK = "round_brick"
    ROUND_PLATE = "round_plate"
    CONE = "cone"
    DOME = "dome"
    DISH = "dish"
    CYLINDER = "cylinder"
    ARCH = "arch"
    WEDGE = "wedge"
    WING = "wing"
    WINDOW = "window"
    DOOR = "door"
    FENCE = "fence"
    PANEL = "panel"
    BRACKET = "bracket"
    HINGE = "hinge"
    TURNTABLE = "turntable"
    CONTAINER = "container"
    VEHICLE = "vehicle"
    SPECIALTY = "specialty"
    BASEPLATE = "baseplate"
    DUPLO = "duplo"


class StudPattern(Enum):
    """Pattern of studs on top."""

    FULL = "full"  # All positions
    NONE = "none"  # No studs (tiles)
    HOLLOW = "hollow"  # Hollow studs
    PARTIAL = "partial"  # Some positions only
    JUMPER = "jumper"  # Single offset stud
    ANTI = "anti"  # Anti-stud recesses
    LOGO = "logo"  # With LEGO logo imprint


class BottomPattern(Enum):
    """Pattern on bottom."""

    TUBES = "tubes"  # Standard tubes
    RIBS = "ribs"  # Center ribs (1xN)
    HOLLOW = "hollow"  # Open hollow
    SOLID = "solid"  # Solid bottom
    ANTI_STUDS = "anti_studs"  # Anti-stud pattern
    TECHNIC = "technic"  # Technic pin holes in tubes


class HolePattern(Enum):
    """Pattern of holes."""

    NONE = "none"
    PIN = "pin"  # Round pin holes
    AXLE = "axle"  # Cross axle holes
    PIN_AXLE = "pin_axle"  # Alternating or combo
    AXLE_CONNECTOR = "axle_connector"  # Perpendicular axle
    TOWBALL = "towball"  # Ball joint socket


class SideFeatureType(Enum):
    """Types of side features."""

    STUD = "stud"  # Side stud
    ANTI_STUD = "anti_stud"  # Side anti-stud
    CLIP_H = "clip_h"  # Horizontal clip
    CLIP_V = "clip_v"  # Vertical clip
    BAR = "bar"  # Bar/handle
    PIN = "pin"  # Technic pin
    AXLE = "axle"  # Technic axle
    BALL = "ball"  # Ball joint
    SOCKET = "socket"  # Ball socket
    HINGE_FINGER = "hinge_finger"
    HINGE_FORK = "hinge_fork"
    CLICK_HINGE = "click_hinge"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class SideFeature:
    """A feature on the side of a brick."""

    type: SideFeatureType
    face: str  # front, back, left, right
    positions: List[Tuple[float, float]] = field(default_factory=list)  # (x, z) on face


@dataclass
class TechnicHole:
    """A Technic hole specification."""

    type: HolePattern
    axis: str  # x, y, z
    positions: List[Tuple[float, float, float]] = field(default_factory=list)


@dataclass
class Slope:
    """Slope specification."""

    angle: float
    direction: str  # front, back, left, right
    type: str = "straight"  # straight, curved, inverted, concave, convex
    start_row: int = 0


@dataclass
class Cutout:
    """Cutout specification."""

    shape: str  # rectangle, circle, arch, slot, grille
    face: str
    position: Tuple[float, float]
    size: Tuple[float, float]
    depth: float = 0  # 0 = through


@dataclass
class Curve:
    """Curve specification for round elements."""

    type: str  # quarter, half, macaroni, full, dome, dish
    radius: float  # in stud units
    angle: float = 90  # degrees
    direction: str = "up"  # up, down, horizontal


@dataclass
class BrickSpec:
    """
    Complete specification for a LEGO brick element.
    """

    # Identity
    name: str
    part_number: str
    category: Category
    description: str = ""

    # Dimensions (stud units for x/y, plate units for height)
    studs_x: int = 1
    studs_y: int = 1
    height_plates: int = 3  # 3 plates = 1 brick

    # Stud pattern
    stud_pattern: StudPattern = StudPattern.FULL
    stud_positions: Optional[List[Tuple[int, int]]] = None

    # Bottom pattern
    bottom_pattern: BottomPattern = BottomPattern.TUBES

    # Shape modifiers
    is_hollow: bool = True
    is_round: bool = False

    # Features
    technic_holes: List[TechnicHole] = field(default_factory=list)
    slopes: List[Slope] = field(default_factory=list)
    side_features: List[SideFeature] = field(default_factory=list)
    cutouts: List[Cutout] = field(default_factory=list)
    curve: Optional[Curve] = None

    # Special flags
    has_hollow_studs: bool = False
    has_anti_studs: bool = False
    has_axle_hole: bool = False
    has_pin_hole: bool = False
    has_bar: bool = False
    has_clip: bool = False
    has_ball: bool = False
    has_socket: bool = False

    # Manufacturing
    notes: str = ""

    def dimensions_mm(self) -> Tuple[float, float, float]:
        """Get dimensions in mm."""
        return (self.studs_x * 8.0, self.studs_y * 8.0, self.height_plates * 3.2)


# ============================================================================
# BRICK REGISTRY
# ============================================================================

BRICKS: Dict[str, BrickSpec] = {}


def brick(spec: BrickSpec) -> BrickSpec:
    """Register a brick specification."""
    BRICKS[spec.name] = spec
    return spec


# ============================================================================
# BASIC BRICKS
# ============================================================================

# 1xN Bricks
brick(
    BrickSpec(
        "brick_1x1",
        "3005",
        Category.BRICK,
        "Basic 1x1 brick",
        1,
        1,
        3,
        bottom_pattern=BottomPattern.HOLLOW,
    )
)
brick(
    BrickSpec(
        "brick_1x2",
        "3004",
        Category.BRICK,
        "Basic 1x2 brick",
        1,
        2,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x3",
        "3622",
        Category.BRICK,
        "Basic 1x3 brick",
        1,
        3,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x4",
        "3010",
        Category.BRICK,
        "Basic 1x4 brick",
        1,
        4,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x6",
        "3009",
        Category.BRICK,
        "Basic 1x6 brick",
        1,
        6,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x8",
        "3008",
        Category.BRICK,
        "Basic 1x8 brick",
        1,
        8,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x10",
        "6111",
        Category.BRICK,
        "Basic 1x10 brick",
        1,
        10,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x12",
        "6112",
        Category.BRICK,
        "Basic 1x12 brick",
        1,
        12,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "brick_1x16",
        "2465",
        Category.BRICK,
        "Basic 1x16 brick",
        1,
        16,
        3,
        bottom_pattern=BottomPattern.RIBS,
    )
)

# 2xN Bricks
brick(BrickSpec("brick_2x2", "3003", Category.BRICK, "Basic 2x2 brick", 2, 2, 3))
brick(BrickSpec("brick_2x3", "3002", Category.BRICK, "Basic 2x3 brick", 2, 3, 3))
brick(BrickSpec("brick_2x4", "3001", Category.BRICK, "Classic 2x4 brick", 2, 4, 3))
brick(BrickSpec("brick_2x6", "2456", Category.BRICK, "Basic 2x6 brick", 2, 6, 3))
brick(BrickSpec("brick_2x8", "3007", Category.BRICK, "Basic 2x8 brick", 2, 8, 3))
brick(BrickSpec("brick_2x10", "3006", Category.BRICK, "Basic 2x10 brick", 2, 10, 3))

# Larger Bricks
brick(BrickSpec("brick_4x6", "2356", Category.BRICK, "Basic 4x6 brick", 4, 6, 3))
brick(BrickSpec("brick_4x10", "6212", Category.BRICK, "Basic 4x10 brick", 4, 10, 3))

# Tall Bricks
brick(BrickSpec("brick_1x1x2", "3581", Category.BRICK, "Tall 1x1x2 brick", 1, 1, 6))
brick(BrickSpec("brick_1x2x2", "3245", Category.BRICK, "Tall 1x2x2 brick", 1, 2, 6))
brick(BrickSpec("brick_1x2x3", "22886", Category.BRICK, "Tall 1x2x3 brick", 1, 2, 9))
brick(BrickSpec("brick_1x2x5", "2454", Category.BRICK, "Tall 1x2x5 brick", 1, 2, 15))


# ============================================================================
# PLATES
# ============================================================================

# 1xN Plates
brick(
    BrickSpec(
        "plate_1x1",
        "3024",
        Category.PLATE,
        "Basic 1x1 plate",
        1,
        1,
        1,
        bottom_pattern=BottomPattern.HOLLOW,
    )
)
brick(
    BrickSpec(
        "plate_1x2",
        "3023",
        Category.PLATE,
        "Basic 1x2 plate",
        1,
        2,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x3",
        "3623",
        Category.PLATE,
        "Basic 1x3 plate",
        1,
        3,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x4",
        "3710",
        Category.PLATE,
        "Basic 1x4 plate",
        1,
        4,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x6",
        "3666",
        Category.PLATE,
        "Basic 1x6 plate",
        1,
        6,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x8",
        "3460",
        Category.PLATE,
        "Basic 1x8 plate",
        1,
        8,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x10",
        "4477",
        Category.PLATE,
        "Basic 1x10 plate",
        1,
        10,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)
brick(
    BrickSpec(
        "plate_1x12",
        "60479",
        Category.PLATE,
        "Basic 1x12 plate",
        1,
        12,
        1,
        bottom_pattern=BottomPattern.RIBS,
    )
)

# 2xN Plates
brick(BrickSpec("plate_2x2", "3022", Category.PLATE, "Basic 2x2 plate", 2, 2, 1))
brick(BrickSpec("plate_2x3", "3021", Category.PLATE, "Basic 2x3 plate", 2, 3, 1))
brick(BrickSpec("plate_2x4", "3020", Category.PLATE, "Basic 2x4 plate", 2, 4, 1))
brick(BrickSpec("plate_2x6", "3795", Category.PLATE, "Basic 2x6 plate", 2, 6, 1))
brick(BrickSpec("plate_2x8", "3034", Category.PLATE, "Basic 2x8 plate", 2, 8, 1))
brick(BrickSpec("plate_2x10", "3832", Category.PLATE, "Basic 2x10 plate", 2, 10, 1))
brick(BrickSpec("plate_2x12", "2445", Category.PLATE, "Basic 2x12 plate", 2, 12, 1))
brick(BrickSpec("plate_2x14", "91988", Category.PLATE, "Basic 2x14 plate", 2, 14, 1))
brick(BrickSpec("plate_2x16", "4282", Category.PLATE, "Basic 2x16 plate", 2, 16, 1))

# Larger Plates
brick(BrickSpec("plate_4x4", "3031", Category.PLATE, "Basic 4x4 plate", 4, 4, 1))
brick(BrickSpec("plate_4x6", "3032", Category.PLATE, "Basic 4x6 plate", 4, 6, 1))
brick(BrickSpec("plate_4x8", "3035", Category.PLATE, "Basic 4x8 plate", 4, 8, 1))
brick(BrickSpec("plate_4x10", "3030", Category.PLATE, "Basic 4x10 plate", 4, 10, 1))
brick(BrickSpec("plate_4x12", "3029", Category.PLATE, "Basic 4x12 plate", 4, 12, 1))
brick(BrickSpec("plate_6x6", "3958", Category.PLATE, "Basic 6x6 plate", 6, 6, 1))
brick(BrickSpec("plate_6x8", "3036", Category.PLATE, "Basic 6x8 plate", 6, 8, 1))
brick(BrickSpec("plate_6x10", "3033", Category.PLATE, "Basic 6x10 plate", 6, 10, 1))
brick(BrickSpec("plate_6x12", "3028", Category.PLATE, "Basic 6x12 plate", 6, 12, 1))
brick(BrickSpec("plate_6x14", "3456", Category.PLATE, "Basic 6x14 plate", 6, 14, 1))
brick(BrickSpec("plate_6x16", "3027", Category.PLATE, "Basic 6x16 plate", 6, 16, 1))
brick(BrickSpec("plate_6x24", "3026", Category.PLATE, "Basic 6x24 plate", 6, 24, 1))
brick(BrickSpec("plate_8x8", "41539", Category.PLATE, "Basic 8x8 plate", 8, 8, 1))
brick(BrickSpec("plate_8x16", "92438", Category.PLATE, "Basic 8x16 plate", 8, 16, 1))
brick(BrickSpec("plate_16x16", "91405", Category.PLATE, "Basic 16x16 plate", 16, 16, 1))


# ============================================================================
# TILES (No studs)
# ============================================================================

brick(
    BrickSpec(
        "tile_1x1", "3070", Category.TILE, "Flat 1x1 tile", 1, 1, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_1x2", "3069", Category.TILE, "Flat 1x2 tile", 1, 2, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_1x3", "63864", Category.TILE, "Flat 1x3 tile", 1, 3, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_1x4", "2431", Category.TILE, "Flat 1x4 tile", 1, 4, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_1x6", "6636", Category.TILE, "Flat 1x6 tile", 1, 6, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_1x8", "4162", Category.TILE, "Flat 1x8 tile", 1, 8, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_2x2", "3068", Category.TILE, "Flat 2x2 tile", 2, 2, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_2x3", "26603", Category.TILE, "Flat 2x3 tile", 2, 3, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_2x4", "87079", Category.TILE, "Flat 2x4 tile", 2, 4, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_2x6", "69729", Category.TILE, "Flat 2x6 tile", 2, 6, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_4x4", "1751", Category.TILE, "Flat 4x4 tile", 4, 4, 1, stud_pattern=StudPattern.NONE
    )
)
brick(
    BrickSpec(
        "tile_6x6", "10202", Category.TILE, "Flat 6x6 tile", 6, 6, 1, stud_pattern=StudPattern.NONE
    )
)

# Tiles with special features
brick(
    BrickSpec(
        "tile_1x1_round",
        "98138",
        Category.TILE,
        "Round 1x1 tile",
        1,
        1,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
    )
)
brick(
    BrickSpec(
        "tile_2x2_round",
        "14769",
        Category.TILE,
        "Round 2x2 tile",
        2,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
    )
)
brick(
    BrickSpec(
        "tile_1x2_grille",
        "2412",
        Category.TILE,
        "1x2 grille tile",
        1,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        cutouts=[Cutout("grille", "top", (0.5, 1), (6, 14))],
    )
)


# ============================================================================
# SLOPES - Standard
# ============================================================================

# 33 degree slopes
brick(
    BrickSpec(
        "slope_33_1x1",
        "54200",
        Category.SLOPE,
        "33° slope 1x1",
        1,
        1,
        2,
        slopes=[Slope(33, "front")],
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "slope_33_1x2",
        "85984",
        Category.SLOPE,
        "33° slope 1x2",
        1,
        2,
        2,
        slopes=[Slope(33, "front")],
        stud_positions=[(0, 1)],
    )
)
brick(
    BrickSpec(
        "slope_33_1x3",
        "4286",
        Category.SLOPE,
        "33° slope 1x3",
        1,
        3,
        3,
        slopes=[Slope(33, "front")],
        stud_positions=[(0, 2)],
    )
)
brick(
    BrickSpec(
        "slope_33_2x2",
        "3300",
        Category.SLOPE,
        "33° slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(33, "front")],
        stud_positions=[(0, 1), (1, 1)],
    )
)
brick(
    BrickSpec(
        "slope_33_2x4",
        "3298",
        Category.SLOPE,
        "33° slope 2x4 double",
        2,
        4,
        3,
        slopes=[Slope(33, "front"), Slope(33, "back")],
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "slope_33_3x1",
        "4286",
        Category.SLOPE,
        "33° slope 3x1",
        3,
        1,
        3,
        slopes=[Slope(33, "front")],
        stud_positions=[(2, 0)],
    )
)
brick(
    BrickSpec(
        "slope_33_3x2",
        "3298",
        Category.SLOPE,
        "33° slope 3x2",
        3,
        2,
        3,
        slopes=[Slope(33, "front")],
        stud_positions=[(2, 0), (2, 1)],
    )
)

# 45 degree slopes
brick(
    BrickSpec(
        "slope_45_1x1",
        "54200",
        Category.SLOPE,
        "45° slope 1x1",
        1,
        1,
        2,
        slopes=[Slope(45, "front")],
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "slope_45_1x2",
        "3040",
        Category.SLOPE,
        "45° slope 1x2",
        2,
        1,
        3,
        slopes=[Slope(45, "front")],
        stud_positions=[(1, 0)],
    )
)
brick(
    BrickSpec(
        "slope_45_2x1",
        "3040",
        Category.SLOPE,
        "45° slope 2x1",
        2,
        1,
        3,
        slopes=[Slope(45, "front")],
        stud_positions=[(1, 0)],
    )
)
brick(
    BrickSpec(
        "slope_45_2x2",
        "3039",
        Category.SLOPE,
        "45° slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(45, "front")],
        stud_positions=[(1, 0), (1, 1)],
    )
)
brick(
    BrickSpec(
        "slope_45_2x3",
        "3038",
        Category.SLOPE,
        "45° slope 2x3",
        2,
        3,
        3,
        slopes=[Slope(45, "front")],
        stud_positions=[(1, 0), (1, 1), (1, 2)],
    )
)
brick(
    BrickSpec(
        "slope_45_2x4",
        "3037",
        Category.SLOPE,
        "45° slope 2x4",
        2,
        4,
        3,
        slopes=[Slope(45, "front")],
        stud_positions=[(1, 0), (1, 1), (1, 2), (1, 3)],
    )
)
brick(
    BrickSpec(
        "slope_45_2x2_double",
        "3043",
        Category.SLOPE,
        "45° double slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(45, "front"), Slope(45, "back")],
        stud_pattern=StudPattern.NONE,
    )
)

# 65 degree slopes
brick(
    BrickSpec(
        "slope_65_1x2",
        "60481",
        Category.SLOPE,
        "65° slope 1x2",
        1,
        2,
        3,
        slopes=[Slope(65, "front")],
        stud_positions=[(0, 1)],
    )
)
brick(
    BrickSpec(
        "slope_65_2x1",
        "60481",
        Category.SLOPE,
        "65° slope 2x1",
        2,
        1,
        3,
        slopes=[Slope(65, "front")],
        stud_positions=[(1, 0)],
    )
)
brick(
    BrickSpec(
        "slope_65_2x2",
        "3678",
        Category.SLOPE,
        "65° slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(65, "front")],
        stud_positions=[(1, 0), (1, 1)],
    )
)

# 75 degree slopes
brick(
    BrickSpec(
        "slope_75_2x1x3",
        "4460",
        Category.SLOPE,
        "75° slope 2x1x3",
        2,
        1,
        9,
        slopes=[Slope(75, "front")],
        stud_positions=[(1, 0)],
    )
)
brick(
    BrickSpec(
        "slope_75_2x2x3",
        "3684",
        Category.SLOPE,
        "75° slope 2x2x3",
        2,
        2,
        9,
        slopes=[Slope(75, "front")],
        stud_positions=[(1, 0), (1, 1)],
    )
)

# 18 degree slopes (gentle)
brick(
    BrickSpec(
        "slope_18_4x2",
        "30363",
        Category.SLOPE,
        "18° slope 4x2",
        4,
        2,
        3,
        slopes=[Slope(18, "front")],
        stud_positions=[(2, 0), (2, 1), (3, 0), (3, 1)],
    )
)

# Cheese slopes (1x1 mini slopes)
brick(
    BrickSpec(
        "cheese_slope",
        "54200",
        Category.SLOPE,
        "Popular small decorative slope",
        1,
        1,
        2,
        slopes=[Slope(33, "front")],
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# SLOPES - Curved
# ============================================================================

brick(
    BrickSpec(
        "slope_curved_2x1",
        "11477",
        Category.SLOPE_CURVED,
        "Curved slope 2x1",
        2,
        1,
        3,
        slopes=[Slope(45, "front", "curved")],
        stud_positions=[(1, 0)],
    )
)
brick(
    BrickSpec(
        "slope_curved_2x2",
        "15068",
        Category.SLOPE_CURVED,
        "Curved slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(45, "front", "curved")],
        stud_positions=[(1, 0), (1, 1)],
    )
)
brick(
    BrickSpec(
        "slope_curved_3x1",
        "50950",
        Category.SLOPE_CURVED,
        "Curved slope 3x1",
        3,
        1,
        3,
        slopes=[Slope(33, "front", "curved")],
        stud_positions=[(2, 0)],
    )
)
brick(
    BrickSpec(
        "slope_curved_3x2",
        "24309",
        Category.SLOPE_CURVED,
        "Curved slope 3x2",
        3,
        2,
        3,
        slopes=[Slope(33, "front", "curved")],
        stud_positions=[(2, 0), (2, 1)],
    )
)
brick(
    BrickSpec(
        "slope_curved_4x1",
        "61678",
        Category.SLOPE_CURVED,
        "Curved slope 4x1",
        4,
        1,
        3,
        slopes=[Slope(25, "front", "curved")],
        stud_positions=[(3, 0)],
    )
)
brick(
    BrickSpec(
        "slope_curved_4x2",
        "93606",
        Category.SLOPE_CURVED,
        "Curved slope 4x2",
        4,
        2,
        3,
        slopes=[Slope(25, "front", "curved")],
        stud_positions=[(3, 0), (3, 1)],
    )
)
brick(
    BrickSpec(
        "slope_curved_6x1",
        "42022",
        Category.SLOPE_CURVED,
        "Curved slope 6x1",
        6,
        1,
        3,
        slopes=[Slope(18, "front", "curved")],
        stud_positions=[(5, 0)],
    )
)

# Double curved slopes
brick(
    BrickSpec(
        "slope_curved_double_2x2",
        "15068",
        Category.SLOPE_CURVED,
        "Double curved slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(45, "front", "curved"), Slope(45, "back", "curved")],
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "slope_curved_double_4x1",
        "93273",
        Category.SLOPE_CURVED,
        "Double curved slope 4x1",
        4,
        1,
        3,
        slopes=[Slope(33, "front", "curved"), Slope(33, "back", "curved")],
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# SLOPES - Inverted
# ============================================================================

brick(
    BrickSpec(
        "slope_inv_33_1x2",
        "3665",
        Category.SLOPE_INVERTED,
        "33° inverted slope 1x2",
        1,
        2,
        3,
        slopes=[Slope(33, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_33_2x2",
        "3660",
        Category.SLOPE_INVERTED,
        "33° inverted slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(33, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_45_1x2",
        "3665",
        Category.SLOPE_INVERTED,
        "45° inverted slope 1x2",
        1,
        2,
        3,
        slopes=[Slope(45, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_45_2x1",
        "3665",
        Category.SLOPE_INVERTED,
        "45° inverted slope 2x1",
        2,
        1,
        3,
        slopes=[Slope(45, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_45_2x2",
        "3660",
        Category.SLOPE_INVERTED,
        "45° inverted slope 2x2",
        2,
        2,
        3,
        slopes=[Slope(45, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_45_4x2",
        "4871",
        Category.SLOPE_INVERTED,
        "45° inverted slope 4x2",
        4,
        2,
        6,
        slopes=[Slope(45, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_45_6x1",
        "52501",
        Category.SLOPE_INVERTED,
        "45° inverted slope 6x1",
        6,
        1,
        3,
        slopes=[Slope(45, "front", "inverted")],
    )
)
brick(
    BrickSpec(
        "slope_inv_75_2x1x3",
        "2449",
        Category.SLOPE_INVERTED,
        "75° inverted slope 2x1x3",
        2,
        1,
        9,
        slopes=[Slope(75, "front", "inverted")],
    )
)


# ============================================================================
# TECHNIC - Bricks with Holes
# ============================================================================

brick(
    BrickSpec(
        "technic_brick_1x1",
        "6541",
        Category.TECHNIC_BRICK,
        "Technic brick 1x1 with hole",
        1,
        1,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, 0.5, 0.5)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x2",
        "3700",
        Category.TECHNIC_BRICK,
        "Technic brick 1x2 with holes",
        1,
        2,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, 0.5, 0.5), (0.5, 1.5, 0.5)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x4",
        "3701",
        Category.TECHNIC_BRICK,
        "Technic brick 1x4 with holes",
        1,
        4,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(4)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x6",
        "3894",
        Category.TECHNIC_BRICK,
        "Technic brick 1x6 with holes",
        1,
        6,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(6)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x8",
        "3702",
        Category.TECHNIC_BRICK,
        "Technic brick 1x8 with holes",
        1,
        8,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(8)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x10",
        "2730",
        Category.TECHNIC_BRICK,
        "Technic brick 1x10 with holes",
        1,
        10,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(10)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x12",
        "3895",
        Category.TECHNIC_BRICK,
        "Technic brick 1x12 with holes",
        1,
        12,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(12)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x14",
        "32018",
        Category.TECHNIC_BRICK,
        "Technic brick 1x14 with holes",
        1,
        14,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(14)])],
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_brick_1x16",
        "3703",
        Category.TECHNIC_BRICK,
        "Technic brick 1x16 with holes",
        1,
        16,
        3,
        technic_holes=[TechnicHole(HolePattern.PIN, "x", [(0.5, i + 0.5, 0.5) for i in range(16)])],
        has_pin_hole=True,
    )
)

# Technic bricks with axle holes
brick(
    BrickSpec(
        "technic_brick_1x2_axle",
        "32064",
        Category.TECHNIC_BRICK,
        "Technic brick 1x2 with axle hole",
        1,
        2,
        3,
        technic_holes=[TechnicHole(HolePattern.AXLE, "x", [(0.5, 0.5, 0.5)])],
        has_axle_hole=True,
        stud_positions=[(0, 1)],
    )
)  # One stud removed


# ============================================================================
# TECHNIC - Beams
# ============================================================================

brick(
    BrickSpec(
        "technic_beam_1",
        "18654",
        Category.TECHNIC_BEAM,
        "Technic beam 1 (1L)",
        1,
        1,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, 0.5, 0)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_2",
        "43857",
        Category.TECHNIC_BEAM,
        "Technic beam 2",
        1,
        2,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(2)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_3",
        "32523",
        Category.TECHNIC_BEAM,
        "Technic beam 3",
        1,
        3,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(3)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_4",
        "32449",
        Category.TECHNIC_BEAM,
        "Technic beam 4",
        1,
        4,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(4)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_5",
        "32316",
        Category.TECHNIC_BEAM,
        "Technic beam 5",
        1,
        5,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(5)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_6",
        "32063",
        Category.TECHNIC_BEAM,
        "Technic beam 6",
        1,
        6,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(6)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_7",
        "32524",
        Category.TECHNIC_BEAM,
        "Technic beam 7",
        1,
        7,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(7)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_8",
        "40490",
        Category.TECHNIC_BEAM,
        "Technic beam 8",
        1,
        8,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(8)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_9",
        "40391",
        Category.TECHNIC_BEAM,
        "Technic beam 9",
        1,
        9,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(9)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_11",
        "32525",
        Category.TECHNIC_BEAM,
        "Technic beam 11",
        1,
        11,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(11)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_13",
        "41239",
        Category.TECHNIC_BEAM,
        "Technic beam 13",
        1,
        13,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(13)])],
    )
)
brick(
    BrickSpec(
        "technic_beam_15",
        "32278",
        Category.TECHNIC_BEAM,
        "Technic beam 15",
        1,
        15,
        2,
        stud_pattern=StudPattern.NONE,
        technic_holes=[TechnicHole(HolePattern.PIN, "z", [(0.5, i + 0.5, 0) for i in range(15)])],
    )
)

# Thick beams (1x2 cross-section)
brick(
    BrickSpec(
        "technic_beam_thick_3",
        "32523",
        Category.TECHNIC_BEAM,
        "Technic thick beam 3",
        2,
        3,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_beam_thick_5",
        "32316",
        Category.TECHNIC_BEAM,
        "Technic thick beam 5",
        2,
        5,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_beam_thick_7",
        "32524",
        Category.TECHNIC_BEAM,
        "Technic thick beam 7",
        2,
        7,
        2,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# TECHNIC - Liftarms
# ============================================================================

brick(
    BrickSpec(
        "technic_liftarm_2",
        "43857",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 2",
        1,
        2,
        2,
        stud_pattern=StudPattern.NONE,
        is_round=False,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_3",
        "6632",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 3",
        1,
        3,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_5",
        "32316",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 5",
        1,
        5,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_7",
        "32524",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 7",
        1,
        7,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_9",
        "40490",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 9",
        1,
        9,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_11",
        "32525",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 11",
        1,
        11,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_13",
        "41239",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 13",
        1,
        13,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_15",
        "32278",
        Category.TECHNIC_LIFTARM,
        "Technic liftarm 15",
        1,
        15,
        2,
        stud_pattern=StudPattern.NONE,
    )
)

# Angle liftarms
brick(
    BrickSpec(
        "technic_liftarm_angle_2x4",
        "32140",
        Category.TECHNIC_LIFTARM,
        "Technic angle liftarm 2x4",
        2,
        4,
        2,
        stud_pattern=StudPattern.NONE,
        notes="90° bend",
    )
)
brick(
    BrickSpec(
        "technic_liftarm_angle_3x3",
        "32056",
        Category.TECHNIC_LIFTARM,
        "Technic angle liftarm 3x3",
        3,
        3,
        2,
        stud_pattern=StudPattern.NONE,
        notes="90° bend",
    )
)
brick(
    BrickSpec(
        "technic_liftarm_angle_3x5",
        "32526",
        Category.TECHNIC_LIFTARM,
        "Technic angle liftarm 3x5",
        3,
        5,
        2,
        stud_pattern=StudPattern.NONE,
        notes="90° bend",
    )
)
brick(
    BrickSpec(
        "technic_liftarm_angle_4x6",
        "6629",
        Category.TECHNIC_LIFTARM,
        "Technic angle liftarm 4x6",
        4,
        6,
        2,
        stud_pattern=StudPattern.NONE,
        notes="90° bend",
    )
)

# Triangle/T liftarms
brick(
    BrickSpec(
        "technic_liftarm_triangle_3x5",
        "2905",
        Category.TECHNIC_LIFTARM,
        "Technic triangle 3x5",
        3,
        5,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_triangle_5x3",
        "32250",
        Category.TECHNIC_LIFTARM,
        "Technic triangle 5x3",
        5,
        3,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_liftarm_t_3x3",
        "60484",
        Category.TECHNIC_LIFTARM,
        "Technic T-beam 3x3",
        3,
        3,
        2,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# TECHNIC - Connectors
# ============================================================================

brick(
    BrickSpec(
        "technic_connector_perpendicular",
        "32034",
        Category.TECHNIC_CONNECTOR,
        "Perpendicular axle connector",
        1,
        1,
        3,
        stud_pattern=StudPattern.NONE,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_connector_toggle",
        "32126",
        Category.TECHNIC_CONNECTOR,
        "Toggle joint connector",
        1,
        1,
        3,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_connector_cv",
        "32494",
        Category.TECHNIC_CONNECTOR,
        "CV joint connector",
        1,
        1,
        3,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_universal_joint",
        "61903",
        Category.TECHNIC_CONNECTOR,
        "Universal joint",
        2,
        2,
        4,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# TECHNIC - Pins
# ============================================================================

brick(
    BrickSpec(
        "technic_pin",
        "2780",
        Category.TECHNIC_PIN,
        "Standard friction pin",
        1,
        1,
        2,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_pin_long",
        "6558",
        Category.TECHNIC_PIN,
        "Technic pin long (3L)",
        1,
        1,
        4,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_pin_friction_3l",
        "6558",
        Category.TECHNIC_PIN,
        "Technic friction pin 3L",
        1,
        1,
        4,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_pin_half",
        "4274",
        Category.TECHNIC_PIN,
        "Technic half pin",
        1,
        1,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_pin_stud",
        "2817",
        Category.TECHNIC_PIN,
        "Technic pin with stud",
        1,
        1,
        2,
        stud_pattern=StudPattern.PARTIAL,
        has_pin_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_pin_double",
        "32556",
        Category.TECHNIC_PIN,
        "Technic double pin",
        1,
        1,
        3,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_pin_towball",
        "6628",
        Category.TECHNIC_PIN,
        "Technic pin with towball",
        1,
        1,
        3,
        stud_pattern=StudPattern.NONE,
        has_ball=True,
    )
)


# ============================================================================
# TECHNIC - Axles
# ============================================================================

brick(
    BrickSpec(
        "technic_axle_2",
        "32062",
        Category.TECHNIC_AXLE,
        "Technic axle 2",
        1,
        2,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_3",
        "4519",
        Category.TECHNIC_AXLE,
        "Technic axle 3",
        1,
        3,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_4",
        "3705",
        Category.TECHNIC_AXLE,
        "Technic axle 4",
        1,
        4,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_5",
        "32073",
        Category.TECHNIC_AXLE,
        "Technic axle 5",
        1,
        5,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_5.5",
        "32209",
        Category.TECHNIC_AXLE,
        "Technic axle 5.5 with stop",
        1,
        5,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_6",
        "3706",
        Category.TECHNIC_AXLE,
        "Technic axle 6",
        1,
        6,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_7",
        "44294",
        Category.TECHNIC_AXLE,
        "Technic axle 7",
        1,
        7,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_8",
        "3707",
        Category.TECHNIC_AXLE,
        "Technic axle 8",
        1,
        8,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_9",
        "60485",
        Category.TECHNIC_AXLE,
        "Technic axle 9",
        1,
        9,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_10",
        "3737",
        Category.TECHNIC_AXLE,
        "Technic axle 10",
        1,
        10,
        1,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "technic_axle_12",
        "3708",
        Category.TECHNIC_AXLE,
        "Technic axle 12",
        1,
        12,
        1,
        stud_pattern=StudPattern.NONE,
    )
)

# Axle with stops/pins
brick(
    BrickSpec(
        "technic_axle_pin",
        "3749",
        Category.TECHNIC_AXLE,
        "Technic axle pin",
        1,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        notes="Half axle, half pin",
    )
)
brick(
    BrickSpec(
        "technic_axle_pin_3l",
        "11214",
        Category.TECHNIC_AXLE,
        "Technic axle pin 3L",
        1,
        3,
        1,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# TECHNIC - Gears
# ============================================================================

brick(
    BrickSpec(
        "technic_gear_8t",
        "3647",
        Category.TECHNIC_GEAR,
        "Technic gear 8 tooth",
        1,
        1,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_12t_bevel",
        "6589",
        Category.TECHNIC_GEAR,
        "Technic bevel gear 12 tooth",
        2,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_16t",
        "4019",
        Category.TECHNIC_GEAR,
        "Technic gear 16 tooth",
        2,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_20t_bevel",
        "32198",
        Category.TECHNIC_GEAR,
        "Technic bevel gear 20 tooth",
        2,
        2,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_24t",
        "3648",
        Category.TECHNIC_GEAR,
        "Technic gear 24 tooth",
        3,
        3,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_40t",
        "3649",
        Category.TECHNIC_GEAR,
        "Technic gear 40 tooth",
        5,
        5,
        1,
        stud_pattern=StudPattern.NONE,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_worm",
        "4716",
        Category.TECHNIC_GEAR,
        "Technic worm gear",
        1,
        2,
        2,
        stud_pattern=StudPattern.NONE,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "technic_gear_rack_4",
        "3743",
        Category.TECHNIC_GEAR,
        "Technic gear rack 4",
        1,
        4,
        1,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# MODIFIED BRICKS - SNOT
# ============================================================================

brick(
    BrickSpec(
        "brick_1x1_stud_side",
        "87087",
        Category.SNOT,
        "1x1 brick with stud on side",
        1,
        1,
        3,
        side_features=[SideFeature(SideFeatureType.STUD, "front", [(0.5, 0.5)])],
    )
)
brick(
    BrickSpec(
        "brick_1x1_studs_2_sides",
        "26604",
        Category.SNOT,
        "1x1 brick with studs on 2 sides",
        1,
        1,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(0.5, 0.5)]),
            SideFeature(SideFeatureType.STUD, "right", [(0.5, 0.5)]),
        ],
    )
)
brick(
    BrickSpec(
        "brick_1x1_studs_4_sides",
        "4733",
        Category.SNOT,
        "1x1 brick with studs on 4 sides",
        1,
        1,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(0.5, 0.5)]),
            SideFeature(SideFeatureType.STUD, "back", [(0.5, 0.5)]),
            SideFeature(SideFeatureType.STUD, "left", [(0.5, 0.5)]),
            SideFeature(SideFeatureType.STUD, "right", [(0.5, 0.5)]),
        ],
    )
)
brick(
    BrickSpec(
        "brick_1x2_studs_1_side",
        "11211",
        Category.SNOT,
        "1x2 brick with studs on 1 side",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.STUD, "front", [(0.5, 0.5), (1.5, 0.5)])],
    )
)
brick(
    BrickSpec(
        "brick_1x2_studs_2_sides",
        "52107",
        Category.SNOT,
        "1x2 brick with studs on 2 sides",
        1,
        2,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(0.5, 0.5), (1.5, 0.5)]),
            SideFeature(SideFeatureType.STUD, "back", [(0.5, 0.5), (1.5, 0.5)]),
        ],
    )
)
brick(
    BrickSpec(
        "brick_1x4_studs_1_side",
        "30414",
        Category.SNOT,
        "1x4 brick with studs on 1 side",
        1,
        4,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(i + 0.5, 0.5) for i in range(4)])
        ],
    )
)
brick(
    BrickSpec(
        "brick_2x2_studs_bottom",
        "41855",
        Category.SNOT,
        "2x2 brick with studs on bottom",
        2,
        2,
        3,
        has_anti_studs=True,
    )
)


# ============================================================================
# MODIFIED BRICKS - Clips and Bars
# ============================================================================

brick(
    BrickSpec(
        "brick_1x1_clip_h",
        "60476",
        Category.MODIFIED,
        "1x1 brick with horizontal clip",
        1,
        1,
        3,
        side_features=[SideFeature(SideFeatureType.CLIP_H, "front", [(0.5, 0.5)])],
        has_clip=True,
    )
)
brick(
    BrickSpec(
        "brick_1x1_clip_v",
        "60475",
        Category.MODIFIED,
        "1x1 brick with vertical clip",
        1,
        1,
        3,
        side_features=[SideFeature(SideFeatureType.CLIP_V, "front", [(0.5, 0.5)])],
        has_clip=True,
    )
)
brick(
    BrickSpec(
        "brick_1x2_clip_h",
        "30237",
        Category.MODIFIED,
        "1x2 brick with horizontal clip",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.CLIP_H, "front", [(1.0, 0.5)])],
        has_clip=True,
    )
)
brick(
    BrickSpec(
        "brick_1x1_bar_h",
        "2921",
        Category.MODIFIED,
        "1x1 brick with horizontal bar",
        1,
        1,
        3,
        side_features=[SideFeature(SideFeatureType.BAR, "front", [(0.5, 0.5)])],
        has_bar=True,
    )
)
brick(
    BrickSpec(
        "brick_1x2_bar_h",
        "30236",
        Category.MODIFIED,
        "1x2 brick with horizontal bar",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.BAR, "front", [(1.0, 0.5)])],
        has_bar=True,
    )
)
brick(
    BrickSpec(
        "plate_1x1_clip_h",
        "4085",
        Category.MODIFIED,
        "1x1 plate with horizontal clip",
        1,
        1,
        1,
        side_features=[SideFeature(SideFeatureType.CLIP_H, "front", [(0.5, 0.3)])],
        has_clip=True,
    )
)
brick(
    BrickSpec(
        "plate_1x1_clip_v",
        "4081",
        Category.MODIFIED,
        "1x1 plate with vertical clip",
        1,
        1,
        1,
        side_features=[SideFeature(SideFeatureType.CLIP_V, "front", [(0.5, 0.3)])],
        has_clip=True,
    )
)
brick(
    BrickSpec(
        "plate_1x2_bar",
        "48336",
        Category.MODIFIED,
        "1x2 plate with bar",
        1,
        2,
        1,
        side_features=[SideFeature(SideFeatureType.BAR, "front", [(1.0, 0.3)])],
        has_bar=True,
    )
)


# ============================================================================
# MODIFIED BRICKS - Masonry
# ============================================================================

brick(
    BrickSpec(
        "brick_masonry_1x2",
        "98283",
        Category.MODIFIED,
        "Masonry brick 1x2",
        1,
        2,
        3,
        notes="Textured surface resembling real bricks",
    )
)
brick(BrickSpec("brick_masonry_1x3", "98284", Category.MODIFIED, "Masonry brick 1x3", 1, 3, 3))
brick(BrickSpec("brick_masonry_1x4", "15533", Category.MODIFIED, "Masonry brick 1x4", 1, 4, 3))
brick(
    BrickSpec(
        "brick_log_1x2",
        "30136",
        Category.MODIFIED,
        "Log brick 1x2",
        1,
        2,
        3,
        notes="Round log texture",
    )
)
brick(
    BrickSpec(
        "brick_palisade_1x2",
        "30137",
        Category.MODIFIED,
        "Palisade brick 1x2",
        1,
        2,
        3,
        notes="Fence/palisade texture",
    )
)


# ============================================================================
# ROUND BRICKS
# ============================================================================

brick(
    BrickSpec(
        "brick_round_1x1", "3062", Category.ROUND_BRICK, "Round brick 1x1", 1, 1, 3, is_round=True
    )
)
brick(
    BrickSpec(
        "brick_round_1x1_open",
        "3062b",
        Category.ROUND_BRICK,
        "Round brick 1x1 open stud",
        1,
        1,
        3,
        is_round=True,
        has_hollow_studs=True,
    )
)
brick(
    BrickSpec(
        "brick_round_2x2",
        "3941",
        Category.ROUND_BRICK,
        "Round brick 2x2",
        2,
        2,
        3,
        is_round=True,
        stud_positions=[(0.5, 0.5)],
    )
)  # Single center stud
brick(
    BrickSpec(
        "brick_round_2x2_axle",
        "6143",
        Category.ROUND_BRICK,
        "Round brick 2x2 with axle hole",
        2,
        2,
        3,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "brick_round_4x4", "87081", Category.ROUND_BRICK, "Round brick 4x4", 4, 4, 3, is_round=True
    )
)


# ============================================================================
# ROUND PLATES
# ============================================================================

brick(
    BrickSpec(
        "plate_round_1x1", "4073", Category.ROUND_PLATE, "Round plate 1x1", 1, 1, 1, is_round=True
    )
)
brick(
    BrickSpec(
        "plate_round_1x1_open",
        "85861",
        Category.ROUND_PLATE,
        "Round plate 1x1 open stud",
        1,
        1,
        1,
        is_round=True,
        has_hollow_studs=True,
    )
)
brick(
    BrickSpec(
        "plate_round_2x2", "4032", Category.ROUND_PLATE, "Round plate 2x2", 2, 2, 1, is_round=True
    )
)
brick(
    BrickSpec(
        "plate_round_2x2_axle",
        "4032b",
        Category.ROUND_PLATE,
        "Round plate 2x2 with axle hole",
        2,
        2,
        1,
        is_round=True,
        has_axle_hole=True,
    )
)
brick(
    BrickSpec(
        "plate_round_4x4", "60474", Category.ROUND_PLATE, "Round plate 4x4", 4, 4, 1, is_round=True
    )
)
brick(
    BrickSpec(
        "plate_round_6x6", "11213", Category.ROUND_PLATE, "Round plate 6x6", 6, 6, 1, is_round=True
    )
)
brick(
    BrickSpec(
        "plate_round_8x8", "74611", Category.ROUND_PLATE, "Round plate 8x8", 8, 8, 1, is_round=True
    )
)


# ============================================================================
# CONES
# ============================================================================

brick(
    BrickSpec(
        "cone_1x1",
        "4589",
        Category.CONE,
        "Cone 1x1",
        1,
        1,
        3,
        is_round=True,
        stud_pattern=StudPattern.NONE,
        curve=Curve("cone", 0.5, 90),
    )
)
brick(
    BrickSpec(
        "cone_1x1x2/3",
        "59900",
        Category.CONE,
        "Small cone",
        1,
        1,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "cone_2x2x1",
        "3942",
        Category.CONE,
        "Cone 2x2x1",
        2,
        2,
        3,
        is_round=True,
        stud_positions=[(0.5, 0.5)],
    )
)
brick(BrickSpec("cone_2x2x2", "3942b", Category.CONE, "Cone 2x2x2", 2, 2, 6, is_round=True))
brick(BrickSpec("cone_4x4x2", "3943", Category.CONE, "Cone 4x4x2", 4, 4, 6, is_round=True))


# ============================================================================
# DOMES AND DISHES
# ============================================================================

brick(
    BrickSpec(
        "dome_2x2",
        "553",
        Category.DOME,
        "Dome 2x2",
        2,
        2,
        3,
        is_round=True,
        curve=Curve("dome", 1.0, 180),
    )
)
brick(
    BrickSpec(
        "dome_4x4",
        "79850",
        Category.DOME,
        "Dome 4x4",
        4,
        4,
        3,
        is_round=True,
        curve=Curve("dome", 2.0, 180),
    )
)

brick(
    BrickSpec(
        "dish_2x2",
        "4740",
        Category.DISH,
        "Dish 2x2",
        2,
        2,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
        curve=Curve("dish", 1.0, 90),
    )
)
brick(
    BrickSpec(
        "dish_2x2_inverted",
        "4740b",
        Category.DISH,
        "Dish 2x2 inverted",
        2,
        2,
        2,
        is_round=True,
        curve=Curve("dish", 1.0, 90, "down"),
    )
)
brick(
    BrickSpec(
        "dish_3x3",
        "43898",
        Category.DISH,
        "Dish 3x3",
        3,
        3,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "dish_4x4",
        "3960",
        Category.DISH,
        "Dish 4x4",
        4,
        4,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "dish_6x6",
        "44375",
        Category.DISH,
        "Dish 6x6 inverted (radar)",
        6,
        6,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "dish_8x8",
        "3961",
        Category.DISH,
        "Dish 8x8",
        8,
        8,
        2,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)
brick(
    BrickSpec(
        "dish_10x10",
        "87654",
        Category.DISH,
        "Dish 10x10",
        10,
        10,
        3,
        is_round=True,
        stud_pattern=StudPattern.NONE,
    )
)


# ============================================================================
# CYLINDERS
# ============================================================================

brick(BrickSpec("cylinder_1x1", "3062", Category.CYLINDER, "Cylinder 1x1", 1, 1, 3, is_round=True))
brick(
    BrickSpec(
        "cylinder_1x1x2", "68639", Category.CYLINDER, "Cylinder 1x1x2", 1, 1, 6, is_round=True
    )
)
brick(
    BrickSpec("cylinder_2x2x2", "3941", Category.CYLINDER, "Cylinder 2x2x2", 2, 2, 6, is_round=True)
)
brick(
    BrickSpec(
        "cylinder_2x4x2",
        "6259",
        Category.CYLINDER,
        "Half cylinder 2x4x2",
        2,
        4,
        6,
        curve=Curve("half", 1.0, 180),
    )
)
brick(
    BrickSpec(
        "cylinder_3x6x2",
        "85080",
        Category.CYLINDER,
        "Half cylinder 3x6x2",
        3,
        6,
        6,
        curve=Curve("half", 1.5, 180),
    )
)


# ============================================================================
# ARCHES
# ============================================================================

brick(
    BrickSpec(
        "arch_1x3",
        "4490",
        Category.ARCH,
        "Arch 1x3",
        1,
        3,
        3,
        cutouts=[Cutout("arch", "front", (1.5, 0), (6, 6.4))],
    )
)
brick(
    BrickSpec(
        "arch_1x4",
        "3659",
        Category.ARCH,
        "Arch 1x4",
        1,
        4,
        3,
        cutouts=[Cutout("arch", "front", (2, 0), (14, 6.4))],
    )
)
brick(
    BrickSpec(
        "arch_1x5x4",
        "2339",
        Category.ARCH,
        "Arch 1x5x4",
        1,
        5,
        12,
        cutouts=[Cutout("arch", "front", (2.5, 0), (22, 25.6))],
    )
)
brick(
    BrickSpec(
        "arch_1x6",
        "3455",
        Category.ARCH,
        "Arch 1x6",
        1,
        6,
        3,
        cutouts=[Cutout("arch", "front", (3, 0), (30, 6.4))],
    )
)
brick(
    BrickSpec(
        "arch_1x6x2",
        "3307",
        Category.ARCH,
        "Arch 1x6x2",
        1,
        6,
        6,
        cutouts=[Cutout("arch", "front", (3, 0), (30, 12.8))],
    )
)
brick(
    BrickSpec(
        "arch_1x8x2",
        "3308",
        Category.ARCH,
        "Arch 1x8x2",
        1,
        8,
        6,
        cutouts=[Cutout("arch", "front", (4, 0), (46, 12.8))],
    )
)
brick(
    BrickSpec(
        "arch_1x12x3",
        "6108",
        Category.ARCH,
        "Arch 1x12x3",
        1,
        12,
        9,
        cutouts=[Cutout("arch", "front", (6, 0), (78, 19.2))],
    )
)

# Inverted arches
brick(BrickSpec("arch_inv_1x3", "18653", Category.ARCH, "Inverted arch 1x3", 1, 3, 3))
brick(BrickSpec("arch_inv_1x4", "15254", Category.ARCH, "Inverted arch 1x4", 1, 4, 3))
brick(BrickSpec("arch_inv_1x5x4", "30099", Category.ARCH, "Inverted arch 1x5x4", 1, 5, 12))


# ============================================================================
# WEDGES
# ============================================================================

# Wedge plates
brick(BrickSpec("wedge_plate_2x2_left", "24299", Category.WEDGE, "Wedge plate 2x2 left", 2, 2, 1))
brick(BrickSpec("wedge_plate_2x2_right", "24307", Category.WEDGE, "Wedge plate 2x2 right", 2, 2, 1))
brick(BrickSpec("wedge_plate_2x3_left", "43723", Category.WEDGE, "Wedge plate 2x3 left", 2, 3, 1))
brick(BrickSpec("wedge_plate_2x3_right", "43722", Category.WEDGE, "Wedge plate 2x3 right", 2, 3, 1))
brick(BrickSpec("wedge_plate_2x4_left", "41770", Category.WEDGE, "Wedge plate 2x4 left", 2, 4, 1))
brick(BrickSpec("wedge_plate_2x4_right", "41769", Category.WEDGE, "Wedge plate 2x4 right", 2, 4, 1))
brick(BrickSpec("wedge_plate_3x4_left", "2399", Category.WEDGE, "Wedge plate 3x4 left", 3, 4, 1))
brick(BrickSpec("wedge_plate_3x4_right", "2340", Category.WEDGE, "Wedge plate 3x4 right", 3, 4, 1))
brick(BrickSpec("wedge_plate_3x6_left", "54383", Category.WEDGE, "Wedge plate 3x6 left", 3, 6, 1))
brick(BrickSpec("wedge_plate_3x6_right", "54384", Category.WEDGE, "Wedge plate 3x6 right", 3, 6, 1))
brick(BrickSpec("wedge_plate_3x8_left", "50305", Category.WEDGE, "Wedge plate 3x8 left", 3, 8, 1))
brick(BrickSpec("wedge_plate_3x8_right", "50304", Category.WEDGE, "Wedge plate 3x8 right", 3, 8, 1))
brick(
    BrickSpec("wedge_plate_4x4", "30503", Category.WEDGE, "Wedge plate 4x4 (corner cut)", 4, 4, 1)
)
brick(BrickSpec("wedge_plate_6x3", "54383", Category.WEDGE, "Wedge plate 6x3 left", 6, 3, 1))

# Wedge bricks
brick(BrickSpec("wedge_brick_2x4_left", "43721", Category.WEDGE, "Wedge brick 2x4 left", 2, 4, 3))
brick(BrickSpec("wedge_brick_2x4_right", "43720", Category.WEDGE, "Wedge brick 2x4 right", 2, 4, 3))
brick(BrickSpec("wedge_brick_3x4_left", "2399b", Category.WEDGE, "Wedge brick 3x4 left", 3, 4, 3))
brick(BrickSpec("wedge_brick_3x4_right", "2340b", Category.WEDGE, "Wedge brick 3x4 right", 3, 4, 3))


# ============================================================================
# WINGS
# ============================================================================

brick(BrickSpec("wing_2x3_left", "43723", Category.WING, "Wing 2x3 left", 2, 3, 1))
brick(BrickSpec("wing_2x3_right", "43722", Category.WING, "Wing 2x3 right", 2, 3, 1))
brick(BrickSpec("wing_2x4_left", "41770", Category.WING, "Wing 2x4 left", 2, 4, 1))
brick(BrickSpec("wing_2x4_right", "41769", Category.WING, "Wing 2x4 right", 2, 4, 1))
brick(BrickSpec("wing_3x8_left", "50305", Category.WING, "Wing 3x8 left", 3, 8, 1))
brick(BrickSpec("wing_3x8_right", "50304", Category.WING, "Wing 3x8 right", 3, 8, 1))
brick(BrickSpec("wing_4x8_left", "3933", Category.WING, "Wing 4x8 left", 4, 8, 1))
brick(BrickSpec("wing_4x8_right", "3934", Category.WING, "Wing 4x8 right", 4, 8, 1))
brick(BrickSpec("wing_4x9_left", "2413", Category.WING, "Wing 4x9 left", 4, 9, 1))
brick(BrickSpec("wing_4x9_right", "2414", Category.WING, "Wing 4x9 right", 4, 9, 1))


# ============================================================================
# BRACKETS
# ============================================================================

brick(
    BrickSpec(
        "bracket_1x2_1x2",
        "99781",
        Category.BRACKET,
        "Bracket 1x2 - 1x2",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.STUD, "front", [(0.5, 0), (1.5, 0)])],
    )
)
brick(
    BrickSpec(
        "bracket_1x2_1x4",
        "2436",
        Category.BRACKET,
        "Bracket 1x2 - 1x4",
        1,
        2,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(0.5, 0), (1.5, 0), (2.5, 0), (3.5, 0)])
        ],
    )
)
brick(
    BrickSpec(
        "bracket_1x2_2x2",
        "44728",
        Category.BRACKET,
        "Bracket 1x2 - 2x2",
        1,
        2,
        3,
        side_features=[
            SideFeature(SideFeatureType.STUD, "front", [(0.5, 0), (1.5, 0), (0.5, 1), (1.5, 1)])
        ],
    )
)
brick(BrickSpec("bracket_1x2_2x4", "93274", Category.BRACKET, "Bracket 1x2 - 2x4", 1, 2, 3))
brick(BrickSpec("bracket_2x2_2x2", "3956", Category.BRACKET, "Bracket 2x2 - 2x2", 2, 2, 3))
brick(BrickSpec("bracket_5x2x1.33", "11215", Category.BRACKET, "Bracket 5x2x1⅓", 5, 2, 4))

# Inverted brackets
brick(
    BrickSpec(
        "bracket_inv_1x2_1x2", "99780", Category.BRACKET, "Inverted bracket 1x2 - 1x2", 1, 2, 3
    )
)


# ============================================================================
# HINGES
# ============================================================================

# Brick hinges
brick(
    BrickSpec(
        "hinge_brick_1x2_base",
        "3937",
        Category.HINGE,
        "Hinge brick 1x2 base",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.HINGE_FINGER, "front", [(1.0, 0.5)])],
    )
)
brick(
    BrickSpec(
        "hinge_brick_1x2_top",
        "3938",
        Category.HINGE,
        "Hinge brick 1x2 top",
        1,
        2,
        3,
        side_features=[SideFeature(SideFeatureType.HINGE_FORK, "front", [(1.0, 0.5)])],
    )
)
brick(BrickSpec("hinge_brick_1x4_base", "3830", Category.HINGE, "Hinge brick 1x4 base", 1, 4, 3))
brick(BrickSpec("hinge_brick_1x4_top", "3831", Category.HINGE, "Hinge brick 1x4 top", 1, 4, 3))

# Plate hinges
brick(
    BrickSpec(
        "hinge_plate_1x2_base",
        "73983",
        Category.HINGE,
        "Hinge plate 1x2 base",
        1,
        2,
        1,
        side_features=[SideFeature(SideFeatureType.CLICK_HINGE, "front", [(1.0, 0.3)])],
    )
)
brick(BrickSpec("hinge_plate_1x2_top", "73983b", Category.HINGE, "Hinge plate 1x2 top", 1, 2, 1))
brick(BrickSpec("hinge_plate_1x4_base", "44568", Category.HINGE, "Hinge plate 1x4 base", 1, 4, 1))
brick(BrickSpec("hinge_plate_1x4_top", "44569", Category.HINGE, "Hinge plate 1x4 top", 1, 4, 1))
brick(BrickSpec("hinge_plate_2x2_base", "92411", Category.HINGE, "Hinge plate 2x2 base", 2, 2, 1))
brick(BrickSpec("hinge_plate_2x2_top", "92412", Category.HINGE, "Hinge plate 2x2 top", 2, 2, 1))

# Click hinges
brick(BrickSpec("hinge_click_1x2_base", "30383", Category.HINGE, "Click hinge 1x2 base", 1, 2, 1))
brick(BrickSpec("hinge_click_1x2_top", "30383b", Category.HINGE, "Click hinge 1x2 top", 1, 2, 1))


# ============================================================================
# TURNTABLES
# ============================================================================

brick(
    BrickSpec(
        "turntable_2x2_plate", "3679", Category.TURNTABLE, "Turntable 2x2 plate base", 2, 2, 1
    )
)
brick(
    BrickSpec("turntable_2x2_top", "3680", Category.TURNTABLE, "Turntable 2x2 plate top", 2, 2, 1)
)
brick(BrickSpec("turntable_4x4_base", "60474", Category.TURNTABLE, "Turntable 4x4 base", 4, 4, 1))
brick(BrickSpec("turntable_4x4_top", "60474b", Category.TURNTABLE, "Turntable 4x4 top", 4, 4, 1))
brick(BrickSpec("turntable_6x6_base", "61485", Category.TURNTABLE, "Turntable 6x6 base", 6, 6, 1))


# ============================================================================
# WINDOWS AND DOORS
# ============================================================================

# Window frames
brick(
    BrickSpec(
        "window_1x2x2",
        "60592",
        Category.WINDOW,
        "Window frame 1x2x2",
        1,
        2,
        6,
        cutouts=[Cutout("rectangle", "front", (1, 1), (12, 16), 0)],
    )
)
brick(
    BrickSpec(
        "window_1x2x3",
        "60593",
        Category.WINDOW,
        "Window frame 1x2x3",
        1,
        2,
        9,
        cutouts=[Cutout("rectangle", "front", (1, 1.5), (12, 22), 0)],
    )
)
brick(
    BrickSpec(
        "window_1x4x3",
        "60594",
        Category.WINDOW,
        "Window frame 1x4x3",
        1,
        4,
        9,
        cutouts=[Cutout("rectangle", "front", (2, 1.5), (28, 22), 0)],
    )
)
brick(
    BrickSpec(
        "window_1x4x5",
        "2493",
        Category.WINDOW,
        "Window frame 1x4x5",
        1,
        4,
        15,
        cutouts=[Cutout("rectangle", "front", (2, 2.5), (28, 38), 0)],
    )
)
brick(
    BrickSpec(
        "window_1x4x6",
        "6160",
        Category.WINDOW,
        "Window frame 1x4x6",
        1,
        4,
        18,
        cutouts=[Cutout("rectangle", "front", (2, 3), (28, 48), 0)],
    )
)

# Door frames
brick(
    BrickSpec(
        "door_frame_1x4x6",
        "60596",
        Category.DOOR,
        "Door frame 1x4x6",
        1,
        4,
        18,
        cutouts=[Cutout("rectangle", "front", (2, 0), (28, 51), 0)],
    )
)
brick(
    BrickSpec(
        "door_frame_2x4x6",
        "60599",
        Category.DOOR,
        "Door frame 2x4x6",
        2,
        4,
        18,
        cutouts=[Cutout("rectangle", "front", (2, 0), (28, 51), 0)],
    )
)


# ============================================================================
# FENCES AND RAILINGS
# ============================================================================

brick(BrickSpec("fence_1x4x1", "3633", Category.FENCE, "Fence 1x4x1", 1, 4, 3))
brick(BrickSpec("fence_1x4x2", "3185", Category.FENCE, "Fence 1x4x2", 1, 4, 6))
brick(
    BrickSpec(
        "fence_lattice_1x4x1",
        "3633b",
        Category.FENCE,
        "Lattice fence 1x4x1",
        1,
        4,
        3,
        cutouts=[Cutout("grille", "front", (2, 0.5), (28, 6))],
    )
)
brick(
    BrickSpec("fence_ornamental_1x4x2", "19121", Category.FENCE, "Ornamental fence 1x4x2", 1, 4, 6)
)
brick(BrickSpec("railing_1x1x2", "19121b", Category.FENCE, "Railing 1x1x2", 1, 1, 6))


# ============================================================================
# PANELS
# ============================================================================

brick(
    BrickSpec(
        "panel_1x2x1",
        "4865",
        Category.PANEL,
        "Panel 1x2x1",
        1,
        2,
        3,
        cutouts=[Cutout("rectangle", "front", (1, 0.5), (12, 6), 1.2)],
    )
)
brick(
    BrickSpec(
        "panel_1x2x2",
        "87544",
        Category.PANEL,
        "Panel 1x2x2",
        1,
        2,
        6,
        cutouts=[Cutout("rectangle", "front", (1, 1), (12, 12), 1.2)],
    )
)
brick(BrickSpec("panel_1x2x3", "87544b", Category.PANEL, "Panel 1x2x3", 1, 2, 9))
brick(BrickSpec("panel_1x4x3", "60581", Category.PANEL, "Panel 1x4x3", 1, 4, 9))
brick(BrickSpec("panel_1x6x5", "59349", Category.PANEL, "Panel 1x6x5", 1, 6, 15))
brick(BrickSpec("panel_2x2x1", "4864", Category.PANEL, "Panel 2x2x1", 2, 2, 3))
brick(BrickSpec("panel_3x4x6", "60581b", Category.PANEL, "Panel 3x4x6", 3, 4, 18))

# Corner panels
brick(BrickSpec("panel_corner_1x2x2", "94638", Category.PANEL, "Corner panel 1x2x2", 1, 2, 6))
brick(BrickSpec("panel_corner_3x3x6", "87421", Category.PANEL, "Corner panel 3x3x6", 3, 3, 18))


# ============================================================================
# BASEPLATES
# ============================================================================

brick(
    BrickSpec(
        "baseplate_8x16",
        "3865",
        Category.BASEPLATE,
        "Baseplate 8x16",
        8,
        16,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)
brick(
    BrickSpec(
        "baseplate_16x16",
        "3867",
        Category.BASEPLATE,
        "Baseplate 16x16",
        16,
        16,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)
brick(
    BrickSpec(
        "baseplate_16x32",
        "3857",
        Category.BASEPLATE,
        "Baseplate 16x32",
        16,
        32,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)
brick(
    BrickSpec(
        "baseplate_32x32",
        "3811",
        Category.BASEPLATE,
        "Baseplate 32x32",
        32,
        32,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)
brick(
    BrickSpec(
        "baseplate_32x32_road",
        "44336",
        Category.BASEPLATE,
        "Baseplate 32x32 road",
        32,
        32,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)
brick(
    BrickSpec(
        "baseplate_48x48",
        "4186",
        Category.BASEPLATE,
        "Baseplate 48x48",
        48,
        48,
        1,
        bottom_pattern=BottomPattern.SOLID,
        is_hollow=False,
    )
)

# Raised baseplates
brick(
    BrickSpec(
        "baseplate_raised_32x32",
        "2552",
        Category.BASEPLATE,
        "Raised baseplate 32x32",
        32,
        32,
        5,
        bottom_pattern=BottomPattern.HOLLOW,
    )
)


# ============================================================================
# SPECIALTY ELEMENTS
# ============================================================================

# Jumper plates
brick(
    BrickSpec(
        "jumper_plate_1x2",
        "3794",
        Category.SPECIALTY,
        "Jumper plate 1x2",
        1,
        2,
        1,
        stud_pattern=StudPattern.JUMPER,
        stud_positions=[(0.5, 1.0)],
        notes="Single center stud for half-stud offset",
    )
)
brick(
    BrickSpec(
        "jumper_plate_2x2",
        "87580",
        Category.SPECIALTY,
        "Jumper plate 2x2",
        2,
        2,
        1,
        stud_pattern=StudPattern.JUMPER,
        stud_positions=[(1.0, 1.0)],
    )
)

# Brick separators
brick(
    BrickSpec(
        "brick_separator",
        "96874",
        Category.SPECIALTY,
        "Brick separator",
        3,
        6,
        3,
        stud_pattern=StudPattern.NONE,
        notes="Tool for separating bricks",
    )
)

# Minifig stands
brick(
    BrickSpec(
        "minifig_stand_3x4",
        "88646",
        Category.SPECIALTY,
        "Minifig stand 3x4",
        3,
        4,
        1,
        stud_positions=[(1.5, 1), (1.5, 2)],
    )
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get(name: str) -> Optional[BrickSpec]:
    """Get brick by name."""
    return BRICKS.get(name)


def find(part_number: str) -> Optional[BrickSpec]:
    """Find brick by part number."""
    for b in BRICKS.values():
        if b.part_number == part_number:
            return b
    return None


def search(query: str) -> List[BrickSpec]:
    """Search bricks by name, description, or part number."""
    query = query.lower()
    return [
        b
        for b in BRICKS.values()
        if query in b.name.lower() or query in b.description.lower() or query in b.part_number
    ]


def by_category(category: Category) -> List[BrickSpec]:
    """Get all bricks in a category."""
    return [b for b in BRICKS.values() if b.category == category]


def categories() -> List[str]:
    """List all category names."""
    return sorted(set(b.category.value for b in BRICKS.values()))


def stats() -> Dict[str, int]:
    """Get catalog statistics."""
    by_cat = {}
    for b in BRICKS.values():
        cat = b.category.value
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {"total": len(BRICKS), "by_category": by_cat}


# Print stats on module load
if __name__ == "__main__":
    s = stats()
    print(f"LEGO Brick Catalog: {s['total']} elements")
    for cat, count in sorted(s["by_category"].items()):
        print(f"  {cat}: {count}")
