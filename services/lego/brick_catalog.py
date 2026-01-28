"""
LEGO Factory v3 - Brick Catalog
===============================
Complete LEGO element library with brick definitions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


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
    SPECIAL = "special"


class StudType(Enum):
    """Types of studs on top surface."""
    SOLID = "solid"
    HOLLOW = "hollow"
    NONE = "none"
    PARTIAL = "partial"
    JUMPER = "jumper"
    RECESSED = "recessed"


class BottomType(Enum):
    """Types of bottom connection structure."""
    TUBES = "tubes"
    RIBS = "ribs"
    HOLLOW = "hollow"
    SOLID = "solid"
    ANTI_STUD = "anti_stud"
    TECHNIC = "technic"


class SideFeature(Enum):
    """Features on brick sides."""
    NONE = "none"
    STUD = "stud"
    ANTI_STUD = "anti_stud"
    CLIP = "clip"
    BAR = "bar"
    PIN_HOLE = "pin_hole"
    AXLE_HOLE = "axle_hole"
    HANDLE = "handle"
    HINGE = "hinge"


class HoleType(Enum):
    """Types of holes through bricks."""
    NONE = "none"
    PIN = "pin"
    AXLE = "axle"
    BAR = "bar"
    STUD = "stud"


@dataclass
class SlopeSpec:
    """Specification for sloped surfaces."""
    angle: float
    direction: str
    studs_on_slope: int = 0
    inverted: bool = False


@dataclass
class BrickDefinition:
    """Complete definition of a LEGO brick type."""

    id: str
    name: str
    category: BrickCategory
    lego_id: Optional[str] = None

    studs_x: int = 1
    studs_y: int = 1
    height_units: float = 1.0

    stud_type: StudType = StudType.SOLID
    stud_positions: Optional[List[Tuple[int, int]]] = None

    bottom_type: BottomType = BottomType.TUBES
    hollow: bool = True

    slope: Optional[SlopeSpec] = None
    corner_radius: float = 0.0
    chamfer: float = 0.0

    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        # Default colors based on category
        default_colors = ['red', 'blue', 'yellow', 'green', 'black', 'white']
        if self.category == BrickCategory.TECHNIC:
            default_colors = ['black', 'gray', 'light_gray']
        elif self.category == BrickCategory.TILE:
            default_colors = ['black', 'white', 'gray']

        return {
            'id': self.id,
            'part_id': self.lego_id or self.id,  # Alias for template compatibility
            'name': self.name,
            'category': self.category.value,
            'lego_id': self.lego_id,
            'studs_x': self.studs_x,
            'studs_y': self.studs_y,
            'height_units': self.height_units,
            'height': int(self.height_units * 3),  # Alias: height in plate units
            'stud_type': self.stud_type.value,
            'bottom_type': self.bottom_type.value,
            'hollow': self.hollow,
            'description': self.description,
            'tags': self.tags,
            'colors': default_colors,  # Default available colors
            'usage': 0,  # Production count placeholder
        }


BRICK_CATALOG: Dict[str, BrickDefinition] = {}


def register_brick(brick: BrickDefinition):
    """Register a brick definition in the catalog."""
    BRICK_CATALOG[brick.id] = brick
    return brick


def _init_catalog():
    """Initialize the brick catalog with standard elements."""

    # Standard bricks
    for x in [1, 2]:
        for y in [1, 2, 3, 4, 6, 8, 10, 12, 16]:
            if x <= y:
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
    for size in [(4, 4), (4, 6), (4, 10), (6, 6), (8, 8)]:
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

    # Plates
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

    # Tiles
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
                        bottom_type=BottomType.HOLLOW,
                        tags=["tile", f"{x}x{y}"],
                    )
                )

    # Slopes
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
                    bottom_type=BottomType.TUBES if (x > 1 and y > 1) else BottomType.RIBS,
                    slope=SlopeSpec(angle=float(angle), direction="front"),
                    tags=["slope", f"{angle}deg", f"{x}x{y}"],
                )
            )

    # Technic bricks
    for y in [1, 2, 4, 6, 8, 10, 12, 14, 16]:
        technic_id = f"technic_brick_1x{y}"
        register_brick(
            BrickDefinition(
                id=technic_id,
                name=f"Technic Brick 1×{y}",
                category=BrickCategory.TECHNIC,
                studs_x=1,
                studs_y=y,
                height_units=1.0,
                stud_type=StudType.SOLID,
                bottom_type=BottomType.TECHNIC,
                tags=["technic", "brick", f"1x{y}"],
            )
        )

    # Jumper plates
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
            description="Plate with single centered stud",
            tags=["plate", "jumper", "offset"],
        )
    )


# Initialize catalog on import
_init_catalog()


def get_brick(brick_id: str) -> Optional[BrickDefinition]:
    """Get a brick definition by ID."""
    return BRICK_CATALOG.get(brick_id)


def search_bricks(
    category: BrickCategory = None,
    tag: str = None,
    studs_x: int = None,
    studs_y: int = None,
    search: str = None,
) -> List[BrickDefinition]:
    """Search for bricks matching criteria."""
    results = []
    for brick in BRICK_CATALOG.values():
        if category and brick.category != category:
            continue
        if tag and tag not in brick.tags:
            continue
        if studs_x and brick.studs_x != studs_x:
            continue
        if studs_y and brick.studs_y != studs_y:
            continue
        if search and search.lower() not in brick.name.lower():
            continue
        results.append(brick)
    return results


def list_categories() -> List[str]:
    """List all available brick categories."""
    return [c.value for c in BrickCategory]


def list_tags() -> List[str]:
    """List all unique tags in the catalog."""
    tags = set()
    for brick in BRICK_CATALOG.values():
        tags.update(brick.tags)
    return sorted(tags)


def get_catalog_stats() -> Dict:
    """Get statistics about the brick catalog."""
    categories = {}
    for brick in BRICK_CATALOG.values():
        cat = brick.category.value
        categories[cat] = categories.get(cat, 0) + 1

    return {
        'total_bricks': len(BRICK_CATALOG),
        'by_category': categories,
        'unique_tags': len(list_tags()),
    }
