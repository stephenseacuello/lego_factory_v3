"""
LEGO Brick Catalog - Complete Element Library

This module defines ALL standard LEGO brick types with their parameters.
Used by the brick generator to create any element from the catalog.

Organization follows LEGO's own categorization system.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal
from enum import Enum, auto


# ============================================================================
# ENUMS - Brick Properties
# ============================================================================


class BrickCategory(Enum):
    """Main brick categories."""

    BASIC = "basic"
    PLATE = "plate"
    TILE = "tile"
    SLOPE = "slope"
    CURVED = "curved"
    WEDGE = "wedge"
    CONE = "cone"
    CYLINDER = "cylinder"
    ARCH = "arch"
    TECHNIC = "technic"
    MODIFIED = "modified"
    BRACKET = "bracket"
    HINGE = "hinge"
    TURNTABLE = "turntable"
    SPECIAL = "special"


class StudType(Enum):
    """Types of studs on top surface."""

    SOLID = "solid"  # Standard solid stud
    HOLLOW = "hollow"  # Hollow stud (can accept bar)
    NONE = "none"  # No studs (tile)
    PARTIAL = "partial"  # Only some positions have studs
    JUMPER = "jumper"  # Single centered stud (jumper plate)
    RECESSED = "recessed"  # Recessed stud (Technic)


class BottomType(Enum):
    """Types of bottom connection structure."""

    TUBES = "tubes"  # Standard tubes between studs
    RIBS = "ribs"  # Ribs for 1xN bricks
    HOLLOW = "hollow"  # Open hollow (no structure)
    SOLID = "solid"  # Solid bottom
    ANTI_STUD = "anti_stud"  # Single anti-stud cylinder
    TECHNIC = "technic"  # Technic-style with holes


class SideFeature(Enum):
    """Features on brick sides."""

    NONE = "none"
    STUD = "stud"  # Side stud
    ANTI_STUD = "anti_stud"  # Side hole for stud
    CLIP = "clip"  # Clip for bars
    BAR = "bar"  # Horizontal bar
    PIN_HOLE = "pin_hole"  # Technic pin hole
    AXLE_HOLE = "axle_hole"  # Technic axle hole
    HANDLE = "handle"  # Handle/bar holder
    HINGE = "hinge"  # Hinge connection


class HoleType(Enum):
    """Types of holes through bricks."""

    NONE = "none"
    PIN = "pin"  # Technic pin hole (4.8mm)
    AXLE = "axle"  # Technic axle hole (cross-shaped)
    BAR = "bar"  # Bar hole (3.18mm)
    STUD = "stud"  # Stud-sized hole


# ============================================================================
# DATACLASSES - Brick Definitions
# ============================================================================


@dataclass
class SlopeSpec:
    """Specification for sloped surfaces."""

    angle: float  # Degrees (18, 25, 33, 45, 65, 75)
    direction: str  # "front", "back", "left", "right", "double"
    studs_on_slope: int = 0  # Number of studs that are on the sloped portion
    inverted: bool = False  # True for inverted slopes


@dataclass
class CurveSpec:
    """Specification for curved surfaces."""

    radius: float  # Curve radius in mm
    arc_degrees: float  # Arc sweep in degrees (90, 180, etc.)
    direction: str  # "top", "side", "front"


@dataclass
class HoleSpec:
    """Specification for holes in bricks."""

    hole_type: HoleType
    positions: List[Tuple[float, float, float]]  # (x, y, z) positions
    axis: str = "z"  # Hole axis: "x", "y", "z"
    through: bool = True  # Through hole or blind


@dataclass
class SideFeatureSpec:
    """Specification for side features."""

    feature: SideFeature
    side: str  # "front", "back", "left", "right", "top", "bottom"
    position: Tuple[float, float] = (0.5, 0.5)  # Relative position on side
    count: int = 1


@dataclass
class BrickDefinition:
    """Complete definition of a LEGO brick type."""

    # Identity
    id: str  # Unique identifier
    name: str  # Human-readable name
    category: BrickCategory
    lego_id: Optional[str] = None  # Official LEGO part number

    # Dimensions (in stud units)
    studs_x: int = 1
    studs_y: int = 1
    height_units: float = 1.0  # 1.0 = brick, 0.333 = plate

    # Top surface
    stud_type: StudType = StudType.SOLID
    stud_positions: Optional[List[Tuple[int, int]]] = None  # Custom stud positions

    # Bottom surface
    bottom_type: BottomType = BottomType.TUBES
    hollow: bool = True

    # Modifications
    slope: Optional[SlopeSpec] = None
    curve: Optional[CurveSpec] = None
    holes: Optional[List[HoleSpec]] = None
    side_features: Optional[List[SideFeatureSpec]] = None

    # Special geometry
    corner_radius: float = 0.0  # For rounded bricks
    chamfer: float = 0.0  # Edge chamfer

    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)


# ============================================================================
# BRICK CATALOG - All Standard Elements
# ============================================================================

BRICK_CATALOG: Dict[str, BrickDefinition] = {}


def register_brick(brick: BrickDefinition):
    """Register a brick definition in the catalog."""
    BRICK_CATALOG[brick.id] = brick
    return brick


# ----------------------------------------------------------------------------
# BASIC BRICKS
# ----------------------------------------------------------------------------

# Standard bricks in all common sizes
for x in [1, 2]:
    for y in [1, 2, 3, 4, 6, 8, 10, 12, 16]:
        if x <= y:  # Avoid duplicates like 2x1 (same as 1x2)
            brick_id = f"brick_{x}x{y}"
            register_brick(
                BrickDefinition(
                    id=brick_id,
                    name=f"Brick {x}×{y}",
                    category=BrickCategory.BASIC,
                    studs_x=x,
                    studs_y=y,
                    height_units=1.0,
                    stud_type=StudType.SOLID,
                    bottom_type=BottomType.TUBES if (x > 1 and y > 1) else BottomType.RIBS,
                    tags=["basic", "brick", f"{x}x{y}"],
                )
            )

# Larger bricks
for size in [(2, 2), (2, 4), (2, 6), (2, 8), (2, 10), (4, 4), (4, 6), (4, 10), (6, 6), (8, 8)]:
    x, y = size
    brick_id = f"brick_{x}x{y}"
    if brick_id not in BRICK_CATALOG:
        register_brick(
            BrickDefinition(
                id=brick_id,
                name=f"Brick {x}×{y}",
                category=BrickCategory.BASIC,
                studs_x=x,
                studs_y=y,
                height_units=1.0,
                stud_type=StudType.SOLID,
                bottom_type=BottomType.TUBES,
                tags=["basic", "brick", "large"],
            )
        )

# Tall bricks (2 and 3 bricks high)
for height in [2, 3]:
    for x, y in [(1, 1), (1, 2), (2, 2), (2, 4)]:
        brick_id = f"brick_{x}x{y}x{height}"
        register_brick(
            BrickDefinition(
                id=brick_id,
                name=f"Brick {x}×{y}×{height}",
                category=BrickCategory.BASIC,
                studs_x=x,
                studs_y=y,
                height_units=float(height),
                stud_type=StudType.SOLID,
                bottom_type=BottomType.TUBES if (x > 1 and y > 1) else BottomType.RIBS,
                tags=["basic", "brick", "tall"],
            )
        )


# ----------------------------------------------------------------------------
# PLATES
# ----------------------------------------------------------------------------

# Standard plates
for x in [1, 2, 4, 6, 8]:
    for y in [1, 2, 3, 4, 6, 8, 10, 12, 16]:
        if x <= y:
            plate_id = f"plate_{x}x{y}"
            register_brick(
                BrickDefinition(
                    id=plate_id,
                    name=f"Plate {x}×{y}",
                    category=BrickCategory.PLATE,
                    studs_x=x,
                    studs_y=y,
                    height_units=1 / 3,
                    stud_type=StudType.SOLID,
                    bottom_type=BottomType.TUBES if (x > 1 and y > 1) else BottomType.RIBS,
                    tags=["plate", f"{x}x{y}"],
                )
            )

# Jumper plates (1x2 with centered stud)
register_brick(
    BrickDefinition(
        id="plate_1x2_jumper",
        name="Jumper Plate 1×2",
        lego_id="3794",
        category=BrickCategory.PLATE,
        studs_x=1,
        studs_y=2,
        height_units=1 / 3,
        stud_type=StudType.JUMPER,
        description="Plate with single centered stud, allows half-stud offset",
        tags=["plate", "jumper", "offset"],
    )
)

register_brick(
    BrickDefinition(
        id="plate_2x2_jumper",
        name="Jumper Plate 2×2",
        category=BrickCategory.PLATE,
        studs_x=2,
        studs_y=2,
        height_units=1 / 3,
        stud_type=StudType.JUMPER,
        tags=["plate", "jumper", "offset"],
    )
)


# ----------------------------------------------------------------------------
# TILES (Flat plates without studs)
# ----------------------------------------------------------------------------

for x in [1, 2, 4, 6, 8]:
    for y in [1, 2, 3, 4, 6, 8]:
        if x <= y:
            tile_id = f"tile_{x}x{y}"
            register_brick(
                BrickDefinition(
                    id=tile_id,
                    name=f"Tile {x}×{y}",
                    category=BrickCategory.TILE,
                    studs_x=x,
                    studs_y=y,
                    height_units=1 / 3,
                    stud_type=StudType.NONE,
                    hollow=False,
                    description="Smooth top surface without studs",
                    tags=["tile", "smooth", f"{x}x{y}"],
                )
            )

# Round tiles
for diameter in [1, 2, 4]:
    register_brick(
        BrickDefinition(
            id=f"tile_round_{diameter}x{diameter}",
            name=f"Round Tile {diameter}×{diameter}",
            category=BrickCategory.TILE,
            studs_x=diameter,
            studs_y=diameter,
            height_units=1 / 3,
            stud_type=StudType.NONE,
            corner_radius=diameter * 4.0,  # Full radius = round
            tags=["tile", "round", "smooth"],
        )
    )


# ----------------------------------------------------------------------------
# SLOPES
# ----------------------------------------------------------------------------

SLOPE_ANGLES = [18, 25, 33, 45, 65, 75]
SLOPE_SIZES = [
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 1),
    (2, 2),
    (2, 3),
    (2, 4),
    (3, 1),
    (3, 2),
    (3, 3),
    (3, 4),
    (4, 2),
    (4, 4),
    (6, 6),
]

for angle in [33, 45, 65]:
    for x, y in [(1, 2), (1, 3), (2, 2), (2, 3), (2, 4)]:
        slope_id = f"slope_{angle}_{x}x{y}"
        register_brick(
            BrickDefinition(
                id=slope_id,
                name=f"Slope {angle}° {x}×{y}",
                category=BrickCategory.SLOPE,
                studs_x=x,
                studs_y=y,
                height_units=1.0,
                stud_type=StudType.PARTIAL,
                slope=SlopeSpec(angle=float(angle), direction="front", studs_on_slope=0),
                tags=["slope", f"{angle}deg", f"{x}x{y}"],
            )
        )

# Inverted slopes
for angle in [33, 45]:
    for x, y in [(1, 2), (2, 2), (2, 3)]:
        slope_id = f"slope_inverted_{angle}_{x}x{y}"
        register_brick(
            BrickDefinition(
                id=slope_id,
                name=f"Slope Inverted {angle}° {x}×{y}",
                category=BrickCategory.SLOPE,
                studs_x=x,
                studs_y=y,
                height_units=1.0,
                stud_type=StudType.SOLID,
                slope=SlopeSpec(angle=float(angle), direction="front", inverted=True),
                tags=["slope", "inverted", f"{angle}deg"],
            )
        )

# Double slopes (roof ridge)
for x, y in [(2, 2), (2, 4), (4, 4)]:
    register_brick(
        BrickDefinition(
            id=f"slope_double_45_{x}x{y}",
            name=f"Slope Double 45° {x}×{y}",
            category=BrickCategory.SLOPE,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.PARTIAL,
            slope=SlopeSpec(angle=45.0, direction="double"),
            description="Roof ridge piece, sloped on two opposite sides",
            tags=["slope", "double", "roof"],
        )
    )

# Cheese slope (1x1 30°)
register_brick(
    BrickDefinition(
        id="slope_cheese",
        name="Cheese Slope 1×1",
        lego_id="50746",
        category=BrickCategory.SLOPE,
        studs_x=1,
        studs_y=1,
        height_units=2 / 3,
        stud_type=StudType.NONE,
        slope=SlopeSpec(angle=30.0, direction="front"),
        description="Small 30° slope, nicknamed 'cheese' slope",
        tags=["slope", "cheese", "small"],
    )
)


# ----------------------------------------------------------------------------
# CURVED SLOPES
# ----------------------------------------------------------------------------

for x, y in [(1, 2), (2, 2), (2, 4), (3, 2), (4, 2)]:
    register_brick(
        BrickDefinition(
            id=f"slope_curved_{x}x{y}",
            name=f"Curved Slope {x}×{y}",
            category=BrickCategory.CURVED,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.PARTIAL,
            curve=CurveSpec(radius=8.0 * y, arc_degrees=90, direction="top"),
            tags=["slope", "curved"],
        )
    )

# Inverted curved slopes
for x, y in [(2, 2), (2, 4)]:
    register_brick(
        BrickDefinition(
            id=f"slope_curved_inverted_{x}x{y}",
            name=f"Curved Slope Inverted {x}×{y}",
            category=BrickCategory.CURVED,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            curve=CurveSpec(radius=8.0 * y, arc_degrees=90, direction="bottom"),
            tags=["slope", "curved", "inverted"],
        )
    )


# ----------------------------------------------------------------------------
# WEDGES
# ----------------------------------------------------------------------------

for x, y in [(2, 3), (2, 4), (3, 3), (4, 4), (6, 4)]:
    # Right wedge
    register_brick(
        BrickDefinition(
            id=f"wedge_right_{x}x{y}",
            name=f"Wedge Right {x}×{y}",
            category=BrickCategory.WEDGE,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.PARTIAL,
            slope=SlopeSpec(angle=45.0, direction="right"),
            description="Wedge shape tapering to the right",
            tags=["wedge", "right"],
        )
    )
    # Left wedge
    register_brick(
        BrickDefinition(
            id=f"wedge_left_{x}x{y}",
            name=f"Wedge Left {x}×{y}",
            category=BrickCategory.WEDGE,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.PARTIAL,
            slope=SlopeSpec(angle=45.0, direction="left"),
            description="Wedge shape tapering to the left",
            tags=["wedge", "left"],
        )
    )

# Wedge plates
for x, y in [(2, 2), (2, 3), (2, 4), (3, 3), (3, 6), (4, 4)]:
    register_brick(
        BrickDefinition(
            id=f"wedge_plate_{x}x{y}",
            name=f"Wedge Plate {x}×{y}",
            category=BrickCategory.WEDGE,
            studs_x=x,
            studs_y=y,
            height_units=1 / 3,
            stud_type=StudType.PARTIAL,
            slope=SlopeSpec(angle=45.0, direction="right"),
            tags=["wedge", "plate"],
        )
    )


# ----------------------------------------------------------------------------
# ROUND BRICKS & CYLINDERS
# ----------------------------------------------------------------------------

# Round bricks (circular cross-section)
for diameter in [1, 2, 4]:
    for height in [1, 2]:
        register_brick(
            BrickDefinition(
                id=f"brick_round_{diameter}x{diameter}x{height}",
                name=f"Round Brick {diameter}×{diameter}×{height}",
                category=BrickCategory.CYLINDER,
                studs_x=diameter,
                studs_y=diameter,
                height_units=float(height),
                stud_type=StudType.SOLID if diameter > 1 else StudType.HOLLOW,
                corner_radius=diameter * 4.0,  # Full radius
                tags=["round", "cylinder", "brick"],
            )
        )

# Cones
for diameter in [1, 2, 4]:
    register_brick(
        BrickDefinition(
            id=f"cone_{diameter}x{diameter}",
            name=f"Cone {diameter}×{diameter}",
            category=BrickCategory.CONE,
            studs_x=diameter,
            studs_y=diameter,
            height_units=1.0,
            stud_type=StudType.NONE,
            corner_radius=diameter * 4.0,
            curve=CurveSpec(radius=0, arc_degrees=0, direction="top"),  # Indicates cone
            tags=["cone", "round"],
        )
    )

# Round plates
for diameter in [1, 2, 4, 6, 8]:
    register_brick(
        BrickDefinition(
            id=f"plate_round_{diameter}x{diameter}",
            name=f"Round Plate {diameter}×{diameter}",
            category=BrickCategory.CYLINDER,
            studs_x=diameter,
            studs_y=diameter,
            height_units=1 / 3,
            stud_type=StudType.SOLID if diameter > 1 else StudType.HOLLOW,
            corner_radius=diameter * 4.0,
            tags=["round", "plate"],
        )
    )


# ----------------------------------------------------------------------------
# ARCHES
# ----------------------------------------------------------------------------

ARCH_SIZES = [(1, 3), (1, 4), (1, 5), (1, 6), (1, 8), (1, 12)]

for x, y in ARCH_SIZES:
    register_brick(
        BrickDefinition(
            id=f"arch_{x}x{y}",
            name=f"Arch {x}×{y}",
            category=BrickCategory.ARCH,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            curve=CurveSpec(radius=y * 4.0, arc_degrees=180, direction="front"),
            description="Architectural arch element",
            tags=["arch", "curved"],
        )
    )

# Inverted arches
for x, y in [(1, 3), (1, 4), (1, 5)]:
    register_brick(
        BrickDefinition(
            id=f"arch_inverted_{x}x{y}",
            name=f"Arch Inverted {x}×{y}",
            category=BrickCategory.ARCH,
            studs_x=x,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            curve=CurveSpec(radius=y * 4.0, arc_degrees=180, direction="bottom"),
            tags=["arch", "inverted"],
        )
    )


# ----------------------------------------------------------------------------
# TECHNIC BRICKS
# ----------------------------------------------------------------------------

# Technic bricks with holes
for y in [1, 2, 4, 6, 8, 10, 12, 14, 16]:
    register_brick(
        BrickDefinition(
            id=f"technic_brick_1x{y}",
            name=f"Technic Brick 1×{y}",
            category=BrickCategory.TECHNIC,
            studs_x=1,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            holes=[
                HoleSpec(
                    hole_type=HoleType.PIN,
                    positions=[(0.5 * 8.0, (i + 0.5) * 8.0, 4.8) for i in range(y)],
                    axis="x",
                    through=True,
                )
            ],
            description="Brick with Technic pin holes through sides",
            tags=["technic", "holes", "pin"],
        )
    )

# Technic bricks with axle holes
for y in [2, 4, 6, 8]:
    register_brick(
        BrickDefinition(
            id=f"technic_brick_axle_1x{y}",
            name=f"Technic Brick Axle 1×{y}",
            category=BrickCategory.TECHNIC,
            studs_x=1,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            holes=[
                HoleSpec(
                    hole_type=HoleType.AXLE,
                    positions=[(0.5 * 8.0, (i + 0.5) * 8.0, 4.8) for i in range(y)],
                    axis="x",
                    through=True,
                )
            ],
            description="Brick with cross-shaped axle holes",
            tags=["technic", "holes", "axle"],
        )
    )

# Technic liftarms
for length in [3, 5, 7, 9, 11, 13, 15]:
    register_brick(
        BrickDefinition(
            id=f"technic_liftarm_1x{length}",
            name=f"Technic Liftarm 1×{length}",
            category=BrickCategory.TECHNIC,
            studs_x=1,
            studs_y=length,
            height_units=1.0,
            stud_type=StudType.NONE,
            holes=[
                HoleSpec(
                    hole_type=HoleType.PIN,
                    positions=[(4.0, (i + 0.5) * 8.0, 4.8) for i in range(length)],
                    axis="z",
                    through=True,
                )
            ],
            description="Studless Technic beam with pin holes",
            tags=["technic", "liftarm", "studless"],
        )
    )


# ----------------------------------------------------------------------------
# MODIFIED BRICKS (SNOT, clips, bars, etc.)
# ----------------------------------------------------------------------------

# SNOT bricks (Studs Not On Top) - studs on side
for y in [1, 2, 4]:
    register_brick(
        BrickDefinition(
            id=f"brick_snot_1x{y}",
            name=f"Brick Modified 1×{y} with Studs on Side",
            category=BrickCategory.MODIFIED,
            studs_x=1,
            studs_y=y,
            height_units=1.0,
            stud_type=StudType.SOLID,
            side_features=[
                SideFeatureSpec(
                    feature=SideFeature.STUD, side="front", position=(0.5, 0.5), count=y
                )
            ],
            description="Has studs on one side for SNOT building",
            tags=["modified", "snot", "side_studs"],
        )
    )

# Headlight brick (1x1 with side stud and recessed stud)
register_brick(
    BrickDefinition(
        id="brick_headlight",
        name="Brick Headlight 1×1",
        lego_id="4070",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=1,
        height_units=1.0,
        stud_type=StudType.RECESSED,
        side_features=[
            SideFeatureSpec(feature=SideFeature.STUD, side="front"),
            SideFeatureSpec(feature=SideFeature.ANTI_STUD, side="back"),
        ],
        description="Classic headlight/Erling brick",
        tags=["modified", "headlight", "erling", "snot"],
    )
)

# Brick with clip
register_brick(
    BrickDefinition(
        id="brick_1x1_clip_vertical",
        name="Brick 1×1 with Vertical Clip",
        lego_id="30241",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=1,
        height_units=1.0,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.CLIP, side="front")],
        description="Brick with clip for holding bars",
        tags=["modified", "clip"],
    )
)

register_brick(
    BrickDefinition(
        id="brick_1x1_clip_horizontal",
        name="Brick 1×1 with Horizontal Clip",
        lego_id="60476",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=1,
        height_units=1.0,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.CLIP, side="front")],
        tags=["modified", "clip", "horizontal"],
    )
)

# Brick with bar/handle
register_brick(
    BrickDefinition(
        id="brick_1x1_bar",
        name="Brick 1×1 with Bar",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=1,
        height_units=1.0,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.BAR, side="front")],
        tags=["modified", "bar", "handle"],
    )
)

# Brick with pin hole
register_brick(
    BrickDefinition(
        id="brick_1x2_pin_hole",
        name="Brick 1×2 with Pin Hole",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=2,
        height_units=1.0,
        stud_type=StudType.SOLID,
        holes=[HoleSpec(hole_type=HoleType.PIN, positions=[(4.0, 8.0, 4.8)], axis="x")],
        tags=["modified", "technic", "pin"],
    )
)

# Brick with axle hole
register_brick(
    BrickDefinition(
        id="brick_1x2_axle_hole",
        name="Brick 1×2 with Axle Hole",
        category=BrickCategory.MODIFIED,
        studs_x=1,
        studs_y=2,
        height_units=1.0,
        stud_type=StudType.SOLID,
        holes=[HoleSpec(hole_type=HoleType.AXLE, positions=[(4.0, 8.0, 4.8)], axis="x")],
        tags=["modified", "technic", "axle"],
    )
)


# ----------------------------------------------------------------------------
# BRACKETS
# ----------------------------------------------------------------------------

# 1x2 bracket
register_brick(
    BrickDefinition(
        id="bracket_1x2_1x2",
        name="Bracket 1×2 - 1×2",
        lego_id="99781",
        category=BrickCategory.BRACKET,
        studs_x=1,
        studs_y=2,
        height_units=1 / 3,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.STUD, side="front", count=2)],
        description="L-shaped bracket plate",
        tags=["bracket", "snot"],
    )
)

# 1x2 - 2x2 bracket
register_brick(
    BrickDefinition(
        id="bracket_1x2_2x2",
        name="Bracket 1×2 - 2×2",
        lego_id="44728",
        category=BrickCategory.BRACKET,
        studs_x=1,
        studs_y=2,
        height_units=1 / 3,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.STUD, side="front", count=4)],
        tags=["bracket", "snot"],
    )
)


# ----------------------------------------------------------------------------
# HINGE ELEMENTS
# ----------------------------------------------------------------------------

register_brick(
    BrickDefinition(
        id="hinge_brick_1x4_base",
        name="Hinge Brick 1×4 Base",
        category=BrickCategory.HINGE,
        studs_x=1,
        studs_y=4,
        height_units=1.0,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.HINGE, side="front")],
        description="Base part of 1x4 hinge",
        tags=["hinge", "base"],
    )
)

register_brick(
    BrickDefinition(
        id="hinge_brick_1x4_top",
        name="Hinge Brick 1×4 Top",
        category=BrickCategory.HINGE,
        studs_x=1,
        studs_y=4,
        height_units=1.0,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.HINGE, side="bottom")],
        description="Top part of 1x4 hinge",
        tags=["hinge", "top"],
    )
)

register_brick(
    BrickDefinition(
        id="hinge_plate_1x2",
        name="Hinge Plate 1×2",
        category=BrickCategory.HINGE,
        studs_x=1,
        studs_y=2,
        height_units=1 / 3,
        stud_type=StudType.SOLID,
        side_features=[SideFeatureSpec(feature=SideFeature.HINGE, side="front")],
        tags=["hinge", "plate"],
    )
)


# ----------------------------------------------------------------------------
# SPECIAL ELEMENTS
# ----------------------------------------------------------------------------

# Ingot / Gold bar
register_brick(
    BrickDefinition(
        id="ingot",
        name="Ingot / Bar",
        lego_id="99563",
        category=BrickCategory.SPECIAL,
        studs_x=1,
        studs_y=1,
        height_units=1 / 3,
        stud_type=StudType.NONE,
        chamfer=0.5,
        description="Ingot/treasure bar shape",
        tags=["special", "ingot", "treasure"],
    )
)

# 1x1 round with hole
register_brick(
    BrickDefinition(
        id="plate_round_1x1_hole",
        name="Plate Round 1×1 with Hole",
        lego_id="85861",
        category=BrickCategory.SPECIAL,
        studs_x=1,
        studs_y=1,
        height_units=1 / 3,
        stud_type=StudType.HOLLOW,
        corner_radius=4.0,
        holes=[HoleSpec(hole_type=HoleType.BAR, positions=[(4.0, 4.0, 1.6)], axis="z")],
        tags=["round", "hole", "plate"],
    )
)

# Turntable
register_brick(
    BrickDefinition(
        id="turntable_2x2",
        name="Turntable 2×2",
        category=BrickCategory.TURNTABLE,
        studs_x=2,
        studs_y=2,
        height_units=2 / 3,
        stud_type=StudType.SOLID,
        corner_radius=8.0,
        description="Rotating turntable base",
        tags=["turntable", "rotating"],
    )
)

# Baseplate (large)
for size in [8, 16, 32, 48]:
    register_brick(
        BrickDefinition(
            id=f"baseplate_{size}x{size}",
            name=f"Baseplate {size}×{size}",
            category=BrickCategory.SPECIAL,
            studs_x=size,
            studs_y=size,
            height_units=1 / 9,  # Very thin
            stud_type=StudType.SOLID,
            hollow=False,
            bottom_type=BottomType.SOLID,
            description="Large building baseplate",
            tags=["baseplate", "large"],
        )
    )


# ============================================================================
# CATALOG QUERY FUNCTIONS
# ============================================================================


def get_brick(brick_id: str) -> Optional[BrickDefinition]:
    """Get a brick definition by ID."""
    return BRICK_CATALOG.get(brick_id)


def search_bricks(
    category: Optional[BrickCategory] = None,
    tags: Optional[List[str]] = None,
    studs_x: Optional[int] = None,
    studs_y: Optional[int] = None,
    name_contains: Optional[str] = None,
) -> List[BrickDefinition]:
    """Search for bricks matching criteria."""
    results = list(BRICK_CATALOG.values())

    if category:
        results = [b for b in results if b.category == category]

    if tags:
        results = [b for b in results if all(t in b.tags for t in tags)]

    if studs_x is not None:
        results = [b for b in results if b.studs_x == studs_x]

    if studs_y is not None:
        results = [b for b in results if b.studs_y == studs_y]

    if name_contains:
        name_lower = name_contains.lower()
        results = [b for b in results if name_lower in b.name.lower()]

    return results


def get_bricks_by_category(category: str) -> List[BrickDefinition]:
    """Get all bricks in a category."""
    return [b for b in BRICK_CATALOG.values() if b.category.value == category]


def list_categories() -> List[Dict]:
    """List all categories with counts."""
    from collections import Counter

    counts = Counter(b.category.value for b in BRICK_CATALOG.values())
    return [{"category": cat, "count": count} for cat, count in sorted(counts.items())]


def get_catalog_stats() -> Dict:
    """Get statistics about the catalog."""
    return {
        "total_bricks": len(BRICK_CATALOG),
        "categories": list_categories(),
        "tags": list(set(tag for b in BRICK_CATALOG.values() for tag in b.tags)),
    }


# ============================================================================
# REGISTRATION COMPLETE
# ============================================================================

print(f"LEGO Brick Catalog loaded: {len(BRICK_CATALOG)} elements")
