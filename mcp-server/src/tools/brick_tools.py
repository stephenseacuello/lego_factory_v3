"""
Enhanced Brick Tools for MCP Server

Provides comprehensive LEGO brick creation capabilities:
1. Create any brick from the catalog (100+ types)
2. Create fully custom bricks with any combination of features
3. List and search the entire brick catalog
"""

from typing import Dict, Any, List, Optional
import sys
import os

# Add shared module to path
SHARED_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
sys.path.insert(0, SHARED_DIR)

from brick_catalog import (
    BRICK_CATALOG,
    get_brick,
    search_bricks,
    get_bricks_by_category,
    list_categories,
    get_catalog_stats,
    BrickDefinition,
)

from custom_brick_builder import (
    CustomBrickBuilder,
    CustomBrickDefinition,
    brick,
    plate,
    tile,
    slope_brick,
    technic_brick,
    snot_brick,
    arch_brick,
    round_brick,
)


# ============================================================================
# CATALOG TOOLS
# ============================================================================


def list_brick_catalog(
    category: Optional[str] = None, search: Optional[str] = None, limit: int = 50
) -> Dict[str, Any]:
    """
    List bricks from the catalog.

    Args:
        category: Filter by category (brick, plate, tile, slope, etc.)
        search: Search by name or part number
        limit: Maximum results to return

    Returns:
        Dict with bricks list and metadata
    """
    if search:
        bricks = search_bricks(search)
    elif category:
        bricks = get_bricks_by_category(category)
    else:
        bricks = list(BRICK_CATALOG.values())

    # Convert to serializable format
    brick_list = []
    for b in bricks[:limit]:
        brick_list.append(
            {
                "name": b.name,
                "category": b.category.value if hasattr(b.category, "value") else b.category,
                "part_number": b.part_number,
                "dimensions": f"{b.studs_x}x{b.studs_y}x{b.height_plates}p",
                "description": _get_brick_description(b),
            }
        )

    return {
        "total": len(bricks),
        "returned": len(brick_list),
        "bricks": brick_list,
        "categories": list_categories() if not category else [category],
    }


def get_brick_details(brick_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific brick.

    Args:
        brick_name: Name or part number of the brick

    Returns:
        Detailed brick specification
    """
    # Try by name first
    brick = get_brick(brick_name)

    # Try by part number
    if not brick:
        for b in BRICK_CATALOG.values():
            if b.part_number == brick_name:
                brick = b
                break

    if not brick:
        return {"error": f"Brick not found: {brick_name}"}

    return {
        "name": brick.name,
        "category": brick.category.value if hasattr(brick.category, "value") else brick.category,
        "part_number": brick.part_number,
        "dimensions": {
            "studs_x": brick.studs_x,
            "studs_y": brick.studs_y,
            "height_plates": brick.height_plates,
            "width_mm": brick.studs_x * 8.0,
            "depth_mm": brick.studs_y * 8.0,
            "height_mm": brick.height_plates * 3.2,
        },
        "features": {
            "stud_type": (
                brick.stud_type.value if hasattr(brick.stud_type, "value") else str(brick.stud_type)
            ),
            "bottom_type": (
                brick.bottom_type.value
                if hasattr(brick.bottom_type, "value")
                else str(brick.bottom_type)
            ),
            "is_hollow": brick.hollow,
            "has_slope": brick.slope is not None,
            "has_holes": len(brick.holes) > 0 if hasattr(brick, "holes") else False,
            "has_side_features": (
                len(brick.side_features) > 0 if hasattr(brick, "side_features") else False
            ),
        },
        "notes": brick.notes if hasattr(brick, "notes") else "",
    }


def _get_brick_description(brick: BrickDefinition) -> str:
    """Generate a human-readable description of a brick."""
    parts = []

    # Size
    if brick.height_plates == 1:
        if hasattr(brick, "stud_type") and str(brick.stud_type) == "StudType.NONE":
            parts.append(f"{brick.studs_x}x{brick.studs_y} tile")
        else:
            parts.append(f"{brick.studs_x}x{brick.studs_y} plate")
    else:
        bricks_high = brick.height_plates // 3
        if bricks_high == 1:
            parts.append(f"{brick.studs_x}x{brick.studs_y} brick")
        else:
            parts.append(f"{brick.studs_x}x{brick.studs_y}x{bricks_high} brick")

    # Category-specific
    cat = brick.category.value if hasattr(brick.category, "value") else brick.category
    if cat == "slope":
        parts.append("slope")
    elif cat == "technic":
        parts.append("with Technic holes")
    elif cat == "modified":
        parts.append("modified")

    return " ".join(parts)


# ============================================================================
# CUSTOM BRICK CREATION TOOLS
# ============================================================================


def create_custom_brick(
    name: str,
    width_studs: int,
    depth_studs: int,
    height_plates: int = 3,
    features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a fully custom LEGO brick.

    Args:
        name: Name for the custom brick
        width_studs: Width in stud units (1-48)
        depth_studs: Depth in stud units (1-48)
        height_plates: Height in plate units (1-36)
        features: Dict of features to add:
            - studs: bool or list of (x,y) positions
            - hollow: bool
            - tubes: bool (auto if 2x2 or larger)
            - ribs: bool (auto if 1xN)
            - technic_holes: dict with axis, rows, hole_type
            - slope: dict with angle, direction, type
            - side_studs: list of dicts with face, x, z
            - clips: list of dicts with face, x, z, orientation
            - bars: list of dicts with face, x, z, length
            - cutouts: list of dicts with face, shape, position, size
            - text: list of dicts with text, face, position
            - round: bool

    Returns:
        Custom brick definition ready for generation
    """
    builder = CustomBrickBuilder()
    builder.set_base(width_studs, depth_studs, height_plates)

    if features is None:
        features = {}

    # Process features

    # Studs
    studs = features.get("studs", True)
    if studs is True:
        builder.add_studs()
    elif studs is False:
        builder.no_studs()
    elif isinstance(studs, list):
        builder.add_studs(positions=studs)

    # Bottom structure
    if features.get("hollow", True):
        builder.hollow_bottom()
    else:
        builder.solid_bottom()

    if features.get("tubes", width_studs > 1 and depth_studs > 1):
        builder.add_tubes()

    if features.get("ribs", width_studs == 1 or depth_studs == 1):
        builder.add_ribs()

    # Round shape
    if features.get("round", False):
        builder.set_round(True)

    # Technic holes
    if "technic_holes" in features:
        th = features["technic_holes"]
        builder.add_technic_holes(
            axis=th.get("axis", "x"), hole_type=th.get("hole_type", "pin"), rows=th.get("rows")
        )

    # Slope
    if "slope" in features:
        s = features["slope"]
        if s.get("type") == "double":
            builder.add_double_slope(s.get("angle", 45))
        elif s.get("type") == "inverted":
            builder.add_inverted_slope(s.get("angle", 45), s.get("direction", "front"))
        else:
            builder.add_slope(
                s.get("angle", 45), s.get("direction", "front"), s.get("type", "straight")
            )

    # Side studs
    for ss in features.get("side_studs", []):
        builder.add_side_stud(ss["face"], ss.get("x", 0.5), ss.get("z", 0.5))

    # Clips
    for clip in features.get("clips", []):
        builder.add_clip(
            clip["face"],
            clip.get("x", 0.5),
            clip.get("z", 0.5),
            clip.get("orientation", "horizontal"),
        )

    # Bars
    for bar in features.get("bars", []):
        builder.add_bar(bar["face"], bar.get("x", 0.5), bar.get("z", 0.5), bar.get("length", 6.0))

    # Cutouts
    for cut in features.get("cutouts", []):
        builder.add_cutout(
            cut["face"],
            cut["shape"],
            cut["x"],
            cut["y"],
            cut["width"],
            cut["height"],
            cut.get("depth", 0),
        )

    # Text
    for txt in features.get("text", []):
        builder.add_text(
            txt["text"],
            txt.get("face", "top"),
            txt.get("x"),
            txt.get("y"),
            txt.get("height", 2.0),
            txt.get("embossed", True),
        )

    # Notes
    if "notes" in features:
        builder.add_notes(features["notes"])

    # Build
    brick_def = builder.build(name)

    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


def _serialize_custom_brick(brick: CustomBrickDefinition) -> Dict[str, Any]:
    """Convert CustomBrickDefinition to serializable dict."""
    return {
        "name": brick.name,
        "dimensions": {
            "width_studs": brick.width_studs,
            "depth_studs": brick.depth_studs,
            "height_plates": brick.height_plates,
            "width_mm": brick.width_mm,
            "depth_mm": brick.depth_mm,
            "height_mm": brick.height_mm,
        },
        "features": {
            "studs": len(brick.studs),
            "tubes": len(brick.tubes),
            "ribs": len(brick.ribs),
            "technic_holes": len(brick.holes),
            "slopes": len(brick.slopes),
            "side_studs": len(brick.side_studs),
            "clips": len(brick.clips),
            "bars": len(brick.bars),
            "cutouts": len(brick.cutouts),
            "text": len(brick.text),
        },
        "is_round": brick.is_round,
        "is_hollow": brick.is_hollow,
        "notes": brick.notes,
    }


# ============================================================================
# QUICK CREATION HELPERS
# ============================================================================


def create_standard_brick(width: int, depth: int, height_bricks: int = 1) -> Dict[str, Any]:
    """Quick create a standard brick."""
    builder = brick(width, depth, height_bricks)
    brick_def = builder.build(f"brick_{width}x{depth}x{height_bricks}")
    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


def create_plate_brick(width: int, depth: int) -> Dict[str, Any]:
    """Quick create a plate."""
    builder = plate(width, depth)
    brick_def = builder.build(f"plate_{width}x{depth}")
    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


def create_tile_brick(width: int, depth: int) -> Dict[str, Any]:
    """Quick create a tile."""
    builder = tile(width, depth)
    brick_def = builder.build(f"tile_{width}x{depth}")
    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


def create_slope_brick_helper(
    width: int, depth: int, angle: float = 45, direction: str = "front"
) -> Dict[str, Any]:
    """Quick create a slope brick."""
    builder = slope_brick(width, depth, angle, direction)
    brick_def = builder.build(f"slope_{int(angle)}_{width}x{depth}")
    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


def create_technic_brick_helper(width: int, depth: int, axis: str = "x") -> Dict[str, Any]:
    """Quick create a Technic brick."""
    builder = technic_brick(width, depth, axis)
    brick_def = builder.build(f"technic_{width}x{depth}")
    return {"success": True, "brick": _serialize_custom_brick(brick_def)}


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

BRICK_TOOLS = {
    "list_brick_catalog": {
        "description": """List LEGO bricks from the catalog.

The catalog contains 100+ official LEGO brick types organized by category:
- brick: Standard bricks (1x1, 2x4, etc.)
- plate: Thin plates (1/3 height)
- tile: Flat pieces without studs
- slope: Sloped bricks (33°, 45°, 65°, etc.)
- technic: Bricks with pin/axle holes
- modified: SNOT bricks, clips, bars
- bracket: L-shaped brackets
- hinge: Hinge bricks and plates
- arch: Arch bricks
- wedge: Wedge plates
- round: Round bricks and cylinders
- baseplate: Large baseplates

You can search by name, part number, or filter by category.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "brick",
                        "plate",
                        "tile",
                        "slope",
                        "technic",
                        "modified",
                        "bracket",
                        "hinge",
                        "arch",
                        "wedge",
                        "round",
                        "baseplate",
                        "jumper",
                    ],
                    "description": "Filter by brick category",
                },
                "search": {"type": "string", "description": "Search by name or part number"},
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum results to return",
                },
            },
        },
    },
    "get_brick_details": {
        "description": "Get detailed specifications for a specific brick by name or LEGO part number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_name": {
                    "type": "string",
                    "description": "Brick name (e.g., 'brick_2x4') or part number (e.g., '3001')",
                }
            },
            "required": ["brick_name"],
        },
    },
    "create_custom_brick": {
        "description": """Create a fully custom LEGO brick with any combination of features.

This is the most powerful brick creation tool - you can combine any features:
- Standard studs, partial studs, or no studs (tile)
- Hollow or solid construction
- Technic pin/axle holes in any direction
- Slopes at various angles (18°, 33°, 45°, 65°, 75°)
- Side studs (SNOT - Studs Not On Top)
- Clips and bars
- Custom cutouts (rectangles, circles, arches)
- Embossed or debossed text
- Round/cylindrical shapes

Examples:
1. Technic slope: 2x4 brick with 45° slope and pin holes
2. SNOT brick: 1x2 with studs on front and back
3. Custom window: 2x4x3 with arch cutout
4. Logo brick: 2x2 with embossed text""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for your custom brick"},
                "width_studs": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 48,
                    "description": "Width in stud units",
                },
                "depth_studs": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 48,
                    "description": "Depth in stud units",
                },
                "height_plates": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 36,
                    "default": 3,
                    "description": "Height in plate units (3 = one brick height)",
                },
                "features": {
                    "type": "object",
                    "description": "Features to add to the brick",
                    "properties": {
                        "studs": {
                            "oneOf": [
                                {"type": "boolean"},
                                {
                                    "type": "array",
                                    "items": {"type": "array", "items": {"type": "integer"}},
                                },
                            ],
                            "description": "true for all studs, false for none, or list of [x,y] positions",
                        },
                        "hollow": {"type": "boolean", "default": True},
                        "round": {
                            "type": "boolean",
                            "default": False,
                            "description": "Make the brick cylindrical",
                        },
                        "technic_holes": {
                            "type": "object",
                            "properties": {
                                "axis": {"type": "string", "enum": ["x", "y", "z"]},
                                "hole_type": {
                                    "type": "string",
                                    "enum": ["pin", "axle", "pin_axle"],
                                },
                                "rows": {"type": "array", "items": {"type": "integer"}},
                            },
                        },
                        "slope": {
                            "type": "object",
                            "properties": {
                                "angle": {"type": "number", "enum": [18, 33, 45, 65, 75]},
                                "direction": {
                                    "type": "string",
                                    "enum": ["front", "back", "left", "right"],
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["straight", "curved", "inverted", "double"],
                                },
                            },
                        },
                        "side_studs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "face": {
                                        "type": "string",
                                        "enum": ["front", "back", "left", "right"],
                                    },
                                    "x": {"type": "number"},
                                    "z": {"type": "number"},
                                },
                            },
                        },
                        "clips": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "face": {"type": "string"},
                                    "x": {"type": "number"},
                                    "z": {"type": "number"},
                                    "orientation": {
                                        "type": "string",
                                        "enum": ["horizontal", "vertical"],
                                    },
                                },
                            },
                        },
                        "cutouts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "face": {"type": "string"},
                                    "shape": {
                                        "type": "string",
                                        "enum": ["rectangle", "circle", "arch", "slot"],
                                    },
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "width": {"type": "number"},
                                    "height": {"type": "number"},
                                    "depth": {"type": "number"},
                                },
                            },
                        },
                        "text": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "face": {"type": "string"},
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "embossed": {"type": "boolean"},
                                },
                            },
                        },
                    },
                },
            },
            "required": ["name", "width_studs", "depth_studs"],
        },
    },
    "create_brick": {
        "description": "Quick create a standard LEGO brick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 16},
                "depth": {"type": "integer", "minimum": 1, "maximum": 16},
                "height_bricks": {"type": "integer", "minimum": 1, "maximum": 12, "default": 1},
            },
            "required": ["width", "depth"],
        },
    },
    "create_plate": {
        "description": "Quick create a LEGO plate (1/3 brick height).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 16},
                "depth": {"type": "integer", "minimum": 1, "maximum": 16},
            },
            "required": ["width", "depth"],
        },
    },
    "create_tile": {
        "description": "Quick create a LEGO tile (flat, no studs).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 16},
                "depth": {"type": "integer", "minimum": 1, "maximum": 16},
            },
            "required": ["width", "depth"],
        },
    },
    "create_slope": {
        "description": "Quick create a slope brick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 8},
                "depth": {"type": "integer", "minimum": 1, "maximum": 8},
                "angle": {"type": "number", "enum": [18, 33, 45, 65, 75], "default": 45},
                "direction": {
                    "type": "string",
                    "enum": ["front", "back", "left", "right"],
                    "default": "front",
                },
            },
            "required": ["width", "depth"],
        },
    },
    "create_technic": {
        "description": "Quick create a Technic brick with pin holes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1, "maximum": 16},
                "depth": {"type": "integer", "minimum": 1, "maximum": 16},
                "hole_axis": {"type": "string", "enum": ["x", "y"], "default": "x"},
                "name": {"type": "string", "description": "Custom name for the brick"},
            },
            "required": ["width", "depth"],
        },
    },
    "create_round": {
        "description": "Quick create a cylindrical round LEGO brick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diameter": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 8,
                    "description": "Diameter in stud units (1, 2, 4 common)",
                },
                "height_units": {
                    "type": "number",
                    "minimum": 0.333,
                    "maximum": 12,
                    "default": 1.0,
                    "description": "Height in brick units (1.0 = standard, 0.333 = plate)",
                },
                "name": {"type": "string", "description": "Custom name for the brick"},
            },
            "required": ["diameter"],
        },
    },
    "create_arch": {
        "description": "Quick create an arch brick with curved cutout.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 12,
                    "description": "Width of arch in studs",
                },
                "depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                    "description": "Depth/thickness in studs",
                },
                "arch_height": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                    "description": "Height of arch opening in brick units",
                },
                "name": {"type": "string", "description": "Custom name for the brick"},
            },
            "required": ["width"],
        },
    },
}


# ============================================================================
# CATALOG STATISTICS
# ============================================================================


def get_full_catalog_stats() -> Dict[str, Any]:
    """Get comprehensive statistics about available bricks."""
    stats = get_catalog_stats()

    return {
        "catalog": {"total_bricks": stats["total_elements"], "categories": stats["by_category"]},
        "custom_features": [
            "studs (solid, hollow, partial, jumper)",
            "bottom (tubes, ribs, solid, hollow)",
            "technic holes (pin, axle, pin_axle)",
            "slopes (18°, 33°, 45°, 65°, 75°)",
            "slope types (straight, curved, inverted, double)",
            "side studs (SNOT)",
            "clips (horizontal, vertical)",
            "bars/handles",
            "cutouts (rectangle, circle, arch, slot)",
            "text (embossed, debossed)",
            "round/cylindrical shapes",
        ],
        "max_dimensions": {"width_studs": 48, "depth_studs": 48, "height_plates": 36},
    }
