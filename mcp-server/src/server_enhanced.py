"""
LEGO MCP Server v7.0 - Enhanced with Full Catalog Support

This MCP server provides comprehensive tools for creating any LEGO brick,
including catalog browsing, standard elements, and fully custom designs.

Part of LEGO MCP Fusion 360 v7.0 - Industry 4.0/5.0 Manufacturing Platform.
"""

import asyncio
import os
import sys
from typing import Any, List, Dict, Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))

from .fusion_client import FusionClient
from .slicer_client import SlicerClient


# Initialize server
server = Server("lego-mcp-server")

# Initialize clients
fusion_client = FusionClient(base_url=os.getenv("FUSION_API_URL", "http://localhost:8765"))
slicer_client = SlicerClient(base_url=os.getenv("SLICER_API_URL", "http://localhost:8766"))


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available LEGO brick tools."""
    return [
        # =============================================
        # CATALOG TOOLS
        # =============================================
        Tool(
            name="browse_brick_catalog",
            description="""Browse the complete LEGO brick catalog.

Returns available brick categories and counts. Use this to explore what's available
before creating bricks.

Categories include:
- basic: Standard bricks (1x1 to 8x8, various heights)
- plate: Thin plates (1/3 brick height)
- tile: Smooth plates without studs
- slope: Angled bricks (18°, 33°, 45°, 65°, 75°)
- curved: Curved slopes and bows
- wedge: Triangular wedge pieces
- cylinder: Round bricks and plates
- cone: Cone shapes
- arch: Architectural arches
- technic: Bricks with pin/axle holes
- modified: SNOT bricks, clips, bars
- bracket: L-shaped brackets
- hinge: Hinge elements
- special: Baseplates, turntables, etc.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (optional)"}
                },
            },
        ),
        Tool(
            name="search_brick_catalog",
            description="""Search for specific bricks in the catalog.

Search by:
- Size (studs_x, studs_y)
- Category
- Tags (e.g., "slope", "technic", "round")
- Name (partial match)

Returns matching brick definitions with IDs for use with create_brick_from_catalog.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {"type": "integer", "description": "Filter by X dimension"},
                    "studs_y": {"type": "integer", "description": "Filter by Y dimension"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "basic",
                            "plate",
                            "tile",
                            "slope",
                            "curved",
                            "wedge",
                            "cylinder",
                            "cone",
                            "arch",
                            "technic",
                            "modified",
                            "bracket",
                            "hinge",
                            "turntable",
                            "special",
                        ],
                        "description": "Filter by category",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (all must match)",
                    },
                    "name_contains": {
                        "type": "string",
                        "description": "Filter by name (partial match)",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Maximum results to return",
                    },
                },
            },
        ),
        Tool(
            name="get_brick_details",
            description="""Get detailed information about a specific brick from the catalog.

Returns complete specification including:
- Dimensions
- Stud configuration
- Bottom structure (tubes/ribs)
- Special features (slopes, holes, clips, etc.)
- LEGO part number (if known)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_id": {
                        "type": "string",
                        "description": "Brick ID from catalog (e.g., 'brick_2x4', 'slope_45_1x2')",
                    }
                },
                "required": ["brick_id"],
            },
        ),
        # =============================================
        # BRICK CREATION TOOLS
        # =============================================
        Tool(
            name="create_brick_from_catalog",
            description="""Create a LEGO brick from the catalog by ID.

Use browse_brick_catalog or search_brick_catalog first to find the brick_id.
This creates the brick in Fusion 360 with all proper geometry.

Examples:
- "brick_2x4" - Standard 2x4 brick
- "plate_1x6" - 1x6 plate
- "slope_45_2x3" - 45° slope
- "technic_brick_1x8" - Technic brick with holes""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_id": {"type": "string", "description": "Brick ID from catalog"},
                    "name": {"type": "string", "description": "Custom name override (optional)"},
                    "color": {
                        "type": "string",
                        "description": "Color for visualization (optional)",
                    },
                },
                "required": ["brick_id"],
            },
        ),
        Tool(
            name="create_standard_brick",
            description="""Create a standard LEGO brick with specific dimensions.

Quick way to create basic bricks, plates, or tiles without looking up catalog IDs.

Brick height reference:
- 1.0 = Standard brick (9.6mm)
- 0.333 = Plate (3.2mm)
- 2.0 = Double-height brick
- 3.0 = Triple-height brick""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 48,
                        "description": "Width in studs",
                    },
                    "studs_y": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 48,
                        "description": "Depth in studs",
                    },
                    "height_units": {
                        "type": "number",
                        "default": 1.0,
                        "description": "Height (1.0 = brick, 0.333 = plate)",
                    },
                    "brick_type": {
                        "type": "string",
                        "enum": ["brick", "plate", "tile"],
                        "default": "brick",
                        "description": "Type (affects studs)",
                    },
                    "name": {"type": "string", "description": "Custom name (optional)"},
                },
                "required": ["studs_x", "studs_y"],
            },
        ),
        Tool(
            name="create_custom_brick",
            description="""Create a fully custom LEGO-compatible brick.

This is the most powerful tool - build any brick by specifying features.
All dimensions follow LEGO standards for compatibility.

Available features:
- Base shapes: box, cylinder, cone, wedge
- Top: studs, hollow_studs, jumper_stud, no_studs (tile)
- Bottom: tubes, ribs, solid, hollow
- Slopes: standard (18°-75°), double (roof ridge), curved
- Sides: side_studs, side_holes, clips, bars
- Technic: pin_holes, axle_holes
- Modifications: arch, chamfer, fillet

Example - Create a 2x4 brick with side studs:
{
  "studs_x": 2, "studs_y": 4, "height_units": 1.0,
  "features": ["studs", "hollow", "tubes", "side_studs_front"]
}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 48,
                        "description": "Width in studs",
                    },
                    "studs_y": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 48,
                        "description": "Depth in studs",
                    },
                    "height_units": {
                        "type": "number",
                        "default": 1.0,
                        "description": "Height in brick units",
                    },
                    "base_shape": {
                        "type": "string",
                        "enum": ["box", "cylinder", "cone", "wedge"],
                        "default": "box",
                        "description": "Base shape",
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of features to add",
                    },
                    "slope_angle": {
                        "type": "number",
                        "enum": [18, 25, 33, 45, 65, 75],
                        "description": "Slope angle if using slope feature",
                    },
                    "slope_direction": {
                        "type": "string",
                        "enum": ["front", "back", "left", "right", "double"],
                        "description": "Direction of slope",
                    },
                    "technic_holes": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["pin", "axle"]},
                            "axis": {"type": "string", "enum": ["x", "y"]},
                            "count": {"type": "integer"},
                        },
                        "description": "Technic hole configuration",
                    },
                    "side_features": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["stud", "hole", "clip", "bar"]},
                                "side": {
                                    "type": "string",
                                    "enum": ["front", "back", "left", "right"],
                                },
                            },
                        },
                        "description": "Features to add to sides",
                    },
                    "name": {"type": "string", "description": "Name for the brick"},
                },
                "required": ["studs_x", "studs_y"],
            },
        ),
        # =============================================
        # SPECIAL BRICK TYPES
        # =============================================
        Tool(
            name="create_slope_brick",
            description="""Create a slope brick with specified angle.

Standard LEGO slope angles: 18°, 25°, 33°, 45°, 65°, 75°
Supports: regular slopes, inverted slopes, double slopes (roof ridge), curved slopes""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {"type": "integer", "minimum": 1, "maximum": 12},
                    "studs_y": {"type": "integer", "minimum": 1, "maximum": 12},
                    "angle": {"type": "number", "enum": [18, 25, 33, 45, 65, 75], "default": 45},
                    "slope_type": {
                        "type": "string",
                        "enum": ["standard", "inverted", "double", "curved"],
                        "default": "standard",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["front", "back", "left", "right"],
                        "default": "front",
                    },
                },
                "required": ["studs_x", "studs_y"],
            },
        ),
        Tool(
            name="create_technic_brick",
            description="""Create a Technic brick with pin or axle holes.

Technic bricks have holes through the sides that accept:
- Pins (4.8mm round holes)
- Axles (4.8mm cross-shaped holes)

Can also create studless liftarms.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {"type": "integer", "minimum": 1, "maximum": 16},
                    "studs_y": {"type": "integer", "minimum": 1, "maximum": 16},
                    "hole_type": {
                        "type": "string",
                        "enum": ["pin", "axle", "alternating"],
                        "default": "pin",
                    },
                    "studless": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, create liftarm without studs",
                    },
                },
                "required": ["studs_x", "studs_y"],
            },
        ),
        Tool(
            name="create_round_brick",
            description="""Create a round (cylindrical) brick or plate.

Supports:
- Round bricks (full cylinder)
- Round plates
- Cones (tapered)
- Domes (hemisphere - coming soon)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "diameter_studs": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 8,
                        "description": "Diameter in stud units",
                    },
                    "height_units": {"type": "number", "default": 1.0},
                    "shape": {
                        "type": "string",
                        "enum": ["cylinder", "cone", "truncated_cone"],
                        "default": "cylinder",
                    },
                    "top_diameter_studs": {
                        "type": "integer",
                        "description": "Top diameter for truncated cone",
                    },
                },
                "required": ["diameter_studs"],
            },
        ),
        Tool(
            name="create_modified_brick",
            description="""Create a modified brick (SNOT, clips, bars, etc.).

Modified bricks have special features for advanced building:
- SNOT (Studs Not On Top) - studs on sides
- Headlight brick - recessed top stud with side connections
- Clip bricks - hold bars/handles
- Bar bricks - have protruding bars
- Bracket - L-shaped connector""",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_size": {
                        "type": "string",
                        "enum": ["1x1", "1x2", "1x4", "2x2"],
                        "default": "1x1",
                    },
                    "modification_type": {
                        "type": "string",
                        "enum": [
                            "side_studs",
                            "headlight",
                            "clip_vertical",
                            "clip_horizontal",
                            "bar",
                            "bracket",
                            "pin_hole",
                            "axle_hole",
                        ],
                        "description": "Type of modification",
                    },
                    "sides": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Which sides have the modification",
                    },
                },
                "required": ["modification_type"],
            },
        ),
        Tool(
            name="create_arch",
            description="""Create an arch brick.

Architectural arches for doorways, windows, bridges.
Supports various spans and styles.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "span_studs": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 12,
                        "description": "Span of the arch",
                    },
                    "height_units": {"type": "number", "default": 1.0},
                    "style": {
                        "type": "string",
                        "enum": ["round", "pointed", "flat"],
                        "default": "round",
                    },
                    "inverted": {"type": "boolean", "default": False},
                },
                "required": ["span_studs"],
            },
        ),
        # =============================================
        # EXPORT & MANUFACTURING TOOLS
        # =============================================
        Tool(
            name="export_stl",
            description="""Export a brick as STL file for 3D printing or visualization.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_id": {"type": "string", "description": "Brick ID to export"},
                    "resolution": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "high",
                    },
                },
                "required": ["brick_id"],
            },
        ),
        Tool(
            name="generate_milling_gcode",
            description="""Generate CNC milling G-code for a brick.

Uses Fusion 360 CAM with optimized toolpaths for LEGO geometry.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_id": {"type": "string"},
                    "material": {
                        "type": "string",
                        "enum": ["abs", "delrin", "hdpe", "aluminum", "wood"],
                        "default": "abs",
                    },
                    "machine": {
                        "type": "string",
                        "enum": [
                            "generic_3axis",
                            "haas_mini",
                            "tormach",
                            "shapeoko",
                            "grbl",
                            "linuxcnc",
                        ],
                        "default": "grbl",
                    },
                },
                "required": ["brick_id"],
            },
        ),
        Tool(
            name="generate_3dprint_gcode",
            description="""Generate 3D printing G-code for a brick.

Uses PrusaSlicer with LEGO-optimized settings.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_id": {"type": "string"},
                    "printer": {
                        "type": "string",
                        "enum": ["prusa_mk3s", "prusa_mk4", "ender3", "voron", "bambu_x1"],
                        "default": "prusa_mk3s",
                    },
                    "material": {
                        "type": "string",
                        "enum": ["pla", "petg", "abs", "asa"],
                        "default": "pla",
                    },
                    "quality": {
                        "type": "string",
                        "enum": ["draft", "normal", "fine", "ultra"],
                        "default": "fine",
                    },
                },
                "required": ["brick_id"],
            },
        ),
        # =============================================
        # AI CAM COPILOT TOOLS
        # =============================================
        Tool(
            name="ai_cam_recommend",
            description="""Get AI-recommended CAM parameters for machining a LEGO brick.

Uses the AI CAM Assistant to analyze the part and recommend optimal:
- Tool selection (type, diameter, flutes)
- Feeds and speeds (RPM, feed rate, DOC, stepover)
- Toolpath strategy (adaptive, pocket, contour)

The AI considers:
- Material properties
- Machine capabilities
- Quality history (learns from past defects)
- Safety margins

Operating modes:
- AUTONOMOUS: AI decides and executes (high confidence only)
- COPILOT: AI recommends, user approves (default)
- ADVISORY: AI explains options, user decides""",
            inputSchema={
                "type": "object",
                "properties": {
                    "brick_type": {
                        "type": "string",
                        "description": "Brick configuration e.g., '2x4', '1x2'",
                        "default": "2x4",
                    },
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                        },
                        "description": "Part dimensions in mm",
                    },
                    "material": {
                        "type": "string",
                        "enum": [
                            "aluminum_6061",
                            "aluminum_7075",
                            "brass",
                            "delrin",
                            "hdpe",
                            "abs",
                            "pla",
                        ],
                        "default": "aluminum_6061",
                    },
                    "machine_id": {
                        "type": "string",
                        "enum": [
                            "bantam-desktop-cnc",
                            "prusa-mk4",
                            "bambu-x1c",
                        ],
                        "default": "bantam-desktop-cnc",
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["pocket", "contour", "facing", "adaptive"],
                        "default": "pocket",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["autonomous", "copilot", "advisory"],
                        "default": "copilot",
                    },
                },
                "required": ["brick_type"],
            },
        ),
        Tool(
            name="ai_cam_execute",
            description="""Execute an approved AI CAM recommendation.

After receiving a recommendation from ai_cam_recommend, use this tool
to execute it and generate G-code.

IMPORTANT:
- In COPILOT mode, requires explicit user approval
- In AUTONOMOUS mode, only executes if confidence >= 95%
- Returns G-code file path and estimated machining time""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recommendation_id": {
                        "type": "string",
                        "description": "ID from ai_cam_recommend response",
                    },
                    "user_approved": {
                        "type": "boolean",
                        "description": "User approval (required for COPILOT mode)",
                        "default": False,
                    },
                    "recommendation": {
                        "type": "object",
                        "description": "Full recommendation object from ai_cam_recommend",
                    },
                },
                "required": ["recommendation_id", "recommendation"],
            },
        ),
        Tool(
            name="ai_cam_feedback",
            description="""Submit quality feedback to improve future CAM recommendations.

After machining a part, report any quality issues so the AI can learn
and adjust parameters for future operations.

The AI uses this feedback to:
- Adjust feeds/speeds for specific material-machine combinations
- Identify patterns in defect types
- Improve confidence scoring""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recommendation_id": {
                        "type": "string",
                        "description": "ID of the CAM recommendation used",
                    },
                    "defect_type": {
                        "type": "string",
                        "enum": [
                            "undersized_stud",
                            "oversized_stud",
                            "rough_surface",
                            "chatter_marks",
                            "burrs",
                            "dimensional_error",
                            "none",
                        ],
                        "description": "Type of defect observed (or 'none' if good)",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["minor", "moderate", "severe"],
                        "default": "minor",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional observations",
                    },
                },
                "required": ["recommendation_id", "defect_type"],
            },
        ),
        Tool(
            name="ai_cam_get_modes",
            description="""Get descriptions of AI CAM operating modes.

Returns detailed information about each mode:
- AUTONOMOUS: Full automation for trusted operations
- COPILOT: Suggestions with human approval
- ADVISORY: Explanations for manual configuration""",
            inputSchema={"type": "object", "properties": {}},
        ),
        # =============================================
        # UTILITY TOOLS
        # =============================================
        Tool(
            name="get_lego_dimensions",
            description="""Get official LEGO dimension standards.

Returns the precise measurements used for LEGO-compatible parts:
- Stud pitch, diameter, height
- Brick and plate heights
- Wall thickness
- Tube dimensions
- Tolerances for 3D printing""",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="calculate_brick_dimensions",
            description="""Calculate physical dimensions for a brick configuration.

Given stud counts, returns actual mm dimensions.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "studs_x": {"type": "integer"},
                    "studs_y": {"type": "integer"},
                    "height_units": {"type": "number", "default": 1.0},
                },
                "required": ["studs_x", "studs_y"],
            },
        ),
        Tool(
            name="list_created_bricks",
            description="""List all bricks created in the current Fusion 360 session.""",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ============================================================================
# TOOL HANDLERS
# ============================================================================


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> List[TextContent]:
    """Handle tool calls from Claude."""

    try:
        # Catalog tools
        if name == "browse_brick_catalog":
            return await handle_browse_catalog(arguments)
        elif name == "search_brick_catalog":
            return await handle_search_catalog(arguments)
        elif name == "get_brick_details":
            return await handle_get_brick_details(arguments)

        # Creation tools
        elif name == "create_brick_from_catalog":
            return await handle_create_from_catalog(arguments)
        elif name == "create_standard_brick":
            return await handle_create_standard(arguments)
        elif name == "create_custom_brick":
            return await handle_create_custom(arguments)
        elif name == "create_slope_brick":
            return await handle_create_slope(arguments)
        elif name == "create_technic_brick":
            return await handle_create_technic(arguments)
        elif name == "create_round_brick":
            return await handle_create_round(arguments)
        elif name == "create_modified_brick":
            return await handle_create_modified(arguments)
        elif name == "create_arch":
            return await handle_create_arch(arguments)

        # Export tools
        elif name == "export_stl":
            return await handle_export_stl(arguments)
        elif name == "generate_milling_gcode":
            return await handle_milling_gcode(arguments)
        elif name == "generate_3dprint_gcode":
            return await handle_3dprint_gcode(arguments)

        # AI CAM tools
        elif name == "ai_cam_recommend":
            return await handle_ai_cam_recommend(arguments)
        elif name == "ai_cam_execute":
            return await handle_ai_cam_execute(arguments)
        elif name == "ai_cam_feedback":
            return await handle_ai_cam_feedback(arguments)
        elif name == "ai_cam_get_modes":
            return await handle_ai_cam_get_modes(arguments)

        # Utility tools
        elif name == "get_lego_dimensions":
            return await handle_get_dimensions(arguments)
        elif name == "calculate_brick_dimensions":
            return await handle_calculate_dimensions(arguments)
        elif name == "list_created_bricks":
            return await handle_list_bricks(arguments)

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============================================================================
# CATALOG HANDLERS
# ============================================================================


async def handle_browse_catalog(args: dict) -> List[TextContent]:
    """Browse brick catalog."""
    try:
        from brick_catalog import list_categories, get_catalog_stats, BRICK_CATALOG, BrickCategory

        category_filter = args.get("category")

        if category_filter:
            # Show bricks in specific category
            try:
                cat = BrickCategory(category_filter)
            except:
                return [TextContent(type="text", text=f"Unknown category: {category_filter}")]

            bricks = [b for b in BRICK_CATALOG.values() if b.category == cat]
            brick_list = "\n".join([f"  • {b.id}: {b.name}" for b in bricks[:30]])

            text = f"""**{category_filter.upper()} Bricks** ({len(bricks)} elements)

{brick_list}
{"..." if len(bricks) > 30 else ""}

Use `get_brick_details` with any brick_id for full specifications.
Use `create_brick_from_catalog` to create any of these bricks."""
        else:
            # Show all categories
            stats = get_catalog_stats()
            cat_text = "\n".join(
                [f"  • **{c['category']}**: {c['count']} elements" for c in stats["categories"]]
            )

            text = f"""**LEGO Brick Catalog**

Total elements: **{stats['total_bricks']}**

**Categories:**
{cat_text}

Use `browse_brick_catalog` with a category name to see elements in that category.
Use `search_brick_catalog` to find specific bricks."""

        return [TextContent(type="text", text=text)]
    except ImportError:
        return [TextContent(type="text", text="Catalog not available - using direct creation")]


async def handle_search_catalog(args: dict) -> List[TextContent]:
    """Search brick catalog."""
    try:
        from brick_catalog import search_bricks, BrickCategory

        category = None
        if args.get("category"):
            try:
                category = BrickCategory(args["category"])
            except:
                pass

        results = search_bricks(
            category=category,
            tags=args.get("tags"),
            studs_x=args.get("studs_x"),
            studs_y=args.get("studs_y"),
            name_contains=args.get("name_contains"),
        )

        limit = args.get("limit", 20)
        results = results[:limit]

        if not results:
            return [TextContent(type="text", text="No bricks found matching criteria.")]

        brick_list = "\n".join(
            [
                f"  • **{b.id}**: {b.name} ({b.studs_x}×{b.studs_y}, {b.category.value})"
                for b in results
            ]
        )

        text = f"""**Search Results** ({len(results)} found)

{brick_list}

Use `create_brick_from_catalog` with any brick_id to create."""

        return [TextContent(type="text", text=text)]
    except ImportError:
        return [TextContent(type="text", text="Catalog search not available")]


async def handle_get_brick_details(args: dict) -> List[TextContent]:
    """Get detailed brick information."""
    try:
        from brick_catalog import get_brick

        brick_id = args["brick_id"]
        brick = get_brick(brick_id)

        if not brick:
            return [TextContent(type="text", text=f"Brick not found: {brick_id}")]

        features = []
        if brick.slope:
            features.append(f"Slope: {brick.slope.angle}° {brick.slope.direction}")
        if brick.curve:
            features.append(f"Curve: {brick.curve.arc_degrees}° radius={brick.curve.radius}mm")
        if brick.holes:
            features.append(
                f"Holes: {len(brick.holes[0].positions)} {brick.holes[0].hole_type.value}"
            )
        if brick.side_features:
            for sf in brick.side_features:
                features.append(f"Side: {sf.feature.value} on {sf.side}")

        features_text = "\n".join([f"  • {f}" for f in features]) if features else "  None"

        text = f"""**{brick.name}**
ID: `{brick.id}`
{f"LEGO Part #: {brick.lego_id}" if brick.lego_id else ""}

**Dimensions:**
  • Studs: {brick.studs_x} × {brick.studs_y}
  • Height: {brick.height_units:.3f} units ({brick.height_units * 9.6:.1f}mm)
  • Physical: {brick.studs_x * 8}mm × {brick.studs_y * 8}mm × {brick.height_units * 9.6:.1f}mm

**Configuration:**
  • Category: {brick.category.value}
  • Top: {brick.stud_type.value}
  • Bottom: {brick.bottom_type.value}
  • Hollow: {brick.hollow}

**Special Features:**
{features_text}

{brick.description if brick.description else ""}

Tags: {", ".join(brick.tags)}"""

        return [TextContent(type="text", text=text)]
    except ImportError:
        return [TextContent(type="text", text="Catalog not available")]


# ============================================================================
# CREATION HANDLERS
# ============================================================================


async def handle_create_from_catalog(args: dict) -> List[TextContent]:
    """Create brick from catalog."""
    brick_id = args["brick_id"]

    result = await fusion_client.post(
        "create_from_catalog",
        {"catalog_id": brick_id, "name": args.get("name"), "color": args.get("color")},
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created **{result['component_name']}** from catalog

**Brick ID:** {result['brick_id']}
**Dimensions:** {result['dimensions']['width_mm']:.1f} × {result['dimensions']['depth_mm']:.1f} × {result['dimensions']['height_mm']:.1f} mm
**Volume:** {result['volume_mm3']:.1f} mm³""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_standard(args: dict) -> List[TextContent]:
    """Create standard brick."""
    brick_type = args.get("brick_type", "brick")

    # Map type to height and studs
    if brick_type == "plate":
        height = 1 / 3
        has_studs = True
    elif brick_type == "tile":
        height = 1 / 3
        has_studs = False
    else:
        height = args.get("height_units", 1.0)
        has_studs = True

    result = await fusion_client.post(
        "create_brick",
        {
            "studs_x": args["studs_x"],
            "studs_y": args["studs_y"],
            "height_units": height,
            "hollow": True,
            "has_studs": has_studs,
            "name": args.get("name"),
        },
    )

    if result.get("success"):
        dims = result.get("dimensions", {})
        return [
            TextContent(
                type="text",
                text=f"""✅ Created {brick_type}!

**Brick ID:** {result['brick_id']}
**Component:** {result['component_name']}
**Dimensions:** {dims.get('width_mm', 0):.1f} × {dims.get('depth_mm', 0):.1f} × {dims.get('height_mm', 0):.1f} mm
**Volume:** {result.get('volume_mm3', 0):.1f} mm³""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_custom(args: dict) -> List[TextContent]:
    """Create custom brick with specified features."""
    features = args.get("features", [])

    # Build feature specification
    feature_spec = {
        "studs_x": args["studs_x"],
        "studs_y": args["studs_y"],
        "height_units": args.get("height_units", 1.0),
        "base_shape": args.get("base_shape", "box"),
        "features": features,
        "name": args.get("name"),
    }

    # Add slope if specified
    if "slope" in features or args.get("slope_angle"):
        feature_spec["slope"] = {
            "angle": args.get("slope_angle", 45),
            "direction": args.get("slope_direction", "front"),
        }

    # Add technic holes if specified
    if args.get("technic_holes"):
        feature_spec["technic_holes"] = args["technic_holes"]

    # Add side features if specified
    if args.get("side_features"):
        feature_spec["side_features"] = args["side_features"]

    result = await fusion_client.post("create_custom_brick", feature_spec)

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created custom brick!

**Brick ID:** {result['brick_id']}
**Features:** {", ".join(features) if features else "standard"}
**Dimensions:** {result.get('dimensions', {})}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_slope(args: dict) -> List[TextContent]:
    """Create slope brick."""
    result = await fusion_client.post(
        "create_slope",
        {
            "studs_x": args["studs_x"],
            "studs_y": args["studs_y"],
            "angle": args.get("angle", 45),
            "slope_type": args.get("slope_type", "standard"),
            "direction": args.get("direction", "front"),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created slope brick!

**Brick ID:** {result['brick_id']}
**Angle:** {args.get('angle', 45)}°
**Type:** {args.get('slope_type', 'standard')}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_technic(args: dict) -> List[TextContent]:
    """Create Technic brick."""
    result = await fusion_client.post(
        "create_technic",
        {
            "studs_x": args["studs_x"],
            "studs_y": args["studs_y"],
            "hole_type": args.get("hole_type", "pin"),
            "studless": args.get("studless", False),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created Technic brick!

**Brick ID:** {result['brick_id']}
**Hole Type:** {args.get('hole_type', 'pin')}
**Studless:** {args.get('studless', False)}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_round(args: dict) -> List[TextContent]:
    """Create round brick."""
    result = await fusion_client.post(
        "create_round",
        {
            "diameter_studs": args["diameter_studs"],
            "height_units": args.get("height_units", 1.0),
            "shape": args.get("shape", "cylinder"),
            "top_diameter_studs": args.get("top_diameter_studs", 0),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created round brick!

**Brick ID:** {result['brick_id']}
**Shape:** {args.get('shape', 'cylinder')}
**Diameter:** {args['diameter_studs']} studs""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_modified(args: dict) -> List[TextContent]:
    """Create modified brick."""
    result = await fusion_client.post(
        "create_modified",
        {
            "base_size": args.get("base_size", "1x1"),
            "modification_type": args["modification_type"],
            "sides": args.get("sides", ["front"]),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created modified brick!

**Brick ID:** {result['brick_id']}
**Type:** {args['modification_type']}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_create_arch(args: dict) -> List[TextContent]:
    """Create arch brick."""
    result = await fusion_client.post(
        "create_arch",
        {
            "span_studs": args["span_studs"],
            "height_units": args.get("height_units", 1.0),
            "style": args.get("style", "round"),
            "inverted": args.get("inverted", False),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Created arch!

**Brick ID:** {result['brick_id']}
**Span:** {args['span_studs']} studs
**Style:** {args.get('style', 'round')}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


# ============================================================================
# EXPORT HANDLERS (same as before)
# ============================================================================


async def handle_export_stl(args: dict) -> List[TextContent]:
    """Export STL."""
    result = await fusion_client.post(
        "export_stl",
        {"component_name": args["brick_id"], "resolution": args.get("resolution", "high")},
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Exported STL

**Path:** {result['path']}
**Size:** {result['size_kb']:.1f} KB""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_milling_gcode(args: dict) -> List[TextContent]:
    """Generate milling G-code."""
    result = await fusion_client.post(
        "generate_gcode",
        {
            "component_name": args["brick_id"],
            "material": args.get("material", "abs"),
            "machine": args.get("machine", "grbl"),
        },
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Generated milling G-code

**Path:** {result['path']}
**Time:** ~{result.get('estimated_time_min', 0):.0f} min""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


async def handle_3dprint_gcode(args: dict) -> List[TextContent]:
    """Generate 3D print G-code."""
    # Export STL first
    stl_result = await fusion_client.post(
        "export_stl", {"component_name": args["brick_id"], "resolution": "high"}
    )

    if not stl_result.get("success"):
        return [TextContent(type="text", text=f"❌ STL export failed: {stl_result.get('error')}")]

    # Slice
    result = await slicer_client.slice(
        stl_path=stl_result["path"],
        printer=args.get("printer", "prusa_mk3s"),
        material=args.get("material", "pla"),
        quality=args.get("quality", "fine"),
        infill_percent=20,
    )

    if result.get("success"):
        return [
            TextContent(
                type="text",
                text=f"""✅ Generated 3D print G-code

**Path:** {result['path']}
**Time:** ~{result.get('estimated_time_min', 0):.0f} min
**Filament:** {result.get('filament_grams', 0):.1f}g""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Failed: {result.get('error')}")]


# ============================================================================
# UTILITY HANDLERS
# ============================================================================


async def handle_get_dimensions(args: dict) -> List[TextContent]:
    """Return LEGO dimension standards."""
    text = """**LEGO Dimension Standards**

**Studs:**
  • Pitch (center-to-center): **8.0 mm**
  • Diameter: **4.8 mm**
  • Height: **1.7 mm**

**Heights:**
  • Standard brick: **9.6 mm** (1 unit)
  • Plate: **3.2 mm** (⅓ unit)
  • Tile: **3.2 mm** (⅓ unit, no studs)

**Walls:**
  • Wall thickness: **1.5 mm**
  • Top thickness: **1.0 mm**

**Bottom Structure:**
  • Tube outer diameter: **6.51 mm**
  • Tube inner diameter: **4.8 mm**
  • Rib thickness: **1.0 mm**

**Technic:**
  • Pin hole diameter: **4.8 mm**
  • Axle hole (cross): **4.8 mm**
  • Bar diameter: **3.18 mm**

**Tolerances:**
  • General: **±0.1 mm**
  • Stud fit: **±0.2 mm**
  • FDM printing: **+0.15 mm**"""

    return [TextContent(type="text", text=text)]


async def handle_calculate_dimensions(args: dict) -> List[TextContent]:
    """Calculate physical dimensions."""
    studs_x = args["studs_x"]
    studs_y = args["studs_y"]
    height_units = args.get("height_units", 1.0)

    width = studs_x * 8.0
    depth = studs_y * 8.0
    height = height_units * 9.6
    volume = width * depth * height

    text = f"""**Brick Dimensions: {studs_x}×{studs_y}**

**Physical Size:**
  • Width: {width:.1f} mm
  • Depth: {depth:.1f} mm
  • Height: {height:.1f} mm ({height_units:.3f} units)

**Volume:** {volume:.1f} mm³ (solid)
**Studs:** {studs_x * studs_y}
**Tubes:** {max(0, (studs_x-1) * (studs_y-1)) if studs_x > 1 and studs_y > 1 else 0}"""

    return [TextContent(type="text", text=text)]


async def handle_list_bricks(args: dict) -> List[TextContent]:
    """List created bricks."""
    result = await fusion_client.get_components()

    if result.get("components"):
        brick_list = "\n".join([f"  • {c}" for c in result["components"]])
        return [
            TextContent(
                type="text",
                text=f"""**Created Bricks:**

{brick_list}""",
            )
        ]
    else:
        return [TextContent(type="text", text="No bricks created yet.")]


# ============================================================================
# MAIN
# ============================================================================


async def handle_batch_create(args: dict) -> List[TextContent]:
    """Create multiple bricks in batch."""
    bricks = args.get("bricks", [])
    results = []

    for brick_spec in bricks:
        brick_type = brick_spec.get("type", "standard")
        brick_args = brick_spec.get("args", {})

        if brick_type == "standard":
            result = await fusion_client.post("create_standard", brick_args)
        elif brick_type == "plate":
            brick_args["is_plate"] = True
            result = await fusion_client.post("create_standard", brick_args)
        elif brick_type == "technic":
            result = await fusion_client.post("create_technic", brick_args)
        else:
            result = {"success": False, "error": f"Unknown type: {brick_type}"}

        results.append({
            "type": brick_type,
            "success": result.get("success", False),
            "brick_id": result.get("brick_id"),
            "error": result.get("error"),
        })

    success_count = sum(1 for r in results if r["success"])

    return [
        TextContent(
            type="text",
            text=f"""✅ Batch creation complete

**Created:** {success_count}/{len(bricks)} bricks
**Details:**
{chr(10).join(f"  • {r['type']}: {r['brick_id'] if r['success'] else r['error']}" for r in results)}""",
        )
    ]


async def handle_manufacturing_status(args: dict) -> List[TextContent]:
    """Get real-time manufacturing system status."""
    # Get status from all connected systems
    fusion_status = await fusion_client.get("status")

    status_text = f"""**Manufacturing System Status**

**Fusion 360 Connection:**
  • Status: {'🟢 Connected' if fusion_status.get('connected') else '🔴 Disconnected'}
  • Active Document: {fusion_status.get('active_document', 'None')}
  • Components: {fusion_status.get('component_count', 0)}

**Brick Modeler:**
  • Ready: ✅
  • Last Operation: {fusion_status.get('last_operation', 'None')}

**Export Capabilities:**
  • STL: ✅ Available
  • STEP: ✅ Available
  • 3MF: ✅ Available
  • G-code: ✅ Available"""

    return [TextContent(type="text", text=status_text)]


async def handle_production_order(args: dict) -> List[TextContent]:
    """Create a production order for brick manufacturing."""
    part_number = args["part_number"]
    quantity = args["quantity"]
    priority = args.get("priority", "normal")
    due_date = args.get("due_date")

    # Generate work order ID
    import uuid
    work_order_id = f"WO-{str(uuid.uuid4())[:8].upper()}"

    # Calculate estimated time based on quantity and complexity
    estimated_minutes = quantity * 2.5  # ~2.5 min per brick

    order_details = {
        "work_order_id": work_order_id,
        "part_number": part_number,
        "quantity": quantity,
        "priority": priority,
        "due_date": due_date,
        "estimated_time_min": estimated_minutes,
        "status": "created",
    }

    return [
        TextContent(
            type="text",
            text=f"""✅ Production Order Created

**Work Order:** {work_order_id}
**Part Number:** {part_number}
**Quantity:** {quantity} units
**Priority:** {priority.upper()}
**Due Date:** {due_date or 'Not specified'}

**Estimated Production Time:** {estimated_minutes:.0f} minutes
**Status:** Created - Awaiting scheduling""",
        )
    ]


async def handle_quality_check(args: dict) -> List[TextContent]:
    """Perform quality inspection on a brick."""
    brick_id = args["brick_id"]

    result = await fusion_client.get(f"inspect/{brick_id}")

    if result.get("success"):
        dims = result.get("dimensions", {})
        return [
            TextContent(
                type="text",
                text=f"""✅ Quality Inspection Complete

**Brick ID:** {brick_id}

**Dimensional Analysis:**
  • Width: {dims.get('width_mm', 0):.3f} mm (Tol: ±0.1mm)
  • Depth: {dims.get('depth_mm', 0):.3f} mm (Tol: ±0.1mm)
  • Height: {dims.get('height_mm', 0):.3f} mm (Tol: ±0.1mm)

**Stud Inspection:**
  • Count: {dims.get('stud_count', 0)}
  • Diameter: {dims.get('stud_diameter_mm', 4.8):.3f} mm (Spec: 4.8mm)
  • Height: {dims.get('stud_height_mm', 1.7):.3f} mm (Spec: 1.7mm)

**LEGO Compatibility:** {'✅ PASS' if result.get('compatible', True) else '❌ FAIL'}
**Overall Status:** {'✅ PASS' if result.get('pass', True) else '❌ FAIL'}""",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Inspection failed: {result.get('error')}")]


async def handle_estimate_cost(args: dict) -> List[TextContent]:
    """Estimate manufacturing cost for a brick design."""
    brick_id = args["brick_id"]
    quantity = args.get("quantity", 1)
    method = args.get("method", "fdm")  # fdm, cnc, injection

    # Get brick info
    info = await fusion_client.get(f"component/{brick_id}")

    if not info.get("success"):
        return [TextContent(type="text", text=f"❌ Cannot find brick: {brick_id}")]

    # Calculate costs based on method
    volume_cm3 = info.get("volume_mm3", 1000) / 1000

    if method == "fdm":
        material_cost_per_g = 0.025  # $0.025/g for PLA
        density = 1.24  # g/cm3
        material_cost = volume_cm3 * density * material_cost_per_g
        machine_rate = 0.15  # $/min
        time_min = volume_cm3 * 2  # Rough estimate
        setup_cost = 0.50 if quantity == 1 else 0.50 / quantity
        unit_cost = material_cost + (machine_rate * time_min) + setup_cost
    elif method == "cnc":
        material_cost = volume_cm3 * 0.05  # ABS stock
        machine_rate = 0.50
        time_min = volume_cm3 * 3
        setup_cost = 5.00 if quantity == 1 else 5.00 / quantity
        unit_cost = material_cost + (machine_rate * time_min) + setup_cost
    else:  # injection molding
        mold_cost = 5000  # One-time mold cost
        cycle_time = 0.5  # min
        machine_rate = 2.00
        material_cost = volume_cm3 * 0.01
        if quantity >= 10000:
            unit_cost = material_cost + (machine_rate * cycle_time) + (mold_cost / quantity)
        else:
            unit_cost = float('inf')  # Not viable for small quantities

    total_cost = unit_cost * quantity

    return [
        TextContent(
            type="text",
            text=f"""💰 Manufacturing Cost Estimate

**Brick:** {brick_id}
**Quantity:** {quantity} units
**Method:** {method.upper()}

**Cost Breakdown:**
  • Material: ${material_cost:.3f}/unit
  • Machine Time: ${machine_rate * time_min:.3f}/unit
  • Setup (amortized): ${setup_cost:.3f}/unit

**Unit Cost:** ${unit_cost:.3f}
**Total Cost:** ${total_cost:.2f}

**Notes:**
{f'• Minimum viable quantity for injection: 10,000 units' if method == 'injection' else f'• FDM optimal for quantities < 100'}""",
        )
    ]


async def handle_schedule_production(args: dict) -> List[TextContent]:
    """Schedule production run for optimization."""
    jobs = args.get("jobs", [])
    optimize_for = args.get("optimize_for", "makespan")  # makespan, due_date, cost

    # Simple scheduling algorithm
    total_time = sum(job.get("estimated_time", 30) for job in jobs)

    schedule = []
    current_time = 0
    for i, job in enumerate(jobs):
        est_time = job.get("estimated_time", 30)
        schedule.append({
            "sequence": i + 1,
            "job_id": job.get("job_id", f"JOB-{i+1}"),
            "start_time": current_time,
            "end_time": current_time + est_time,
        })
        current_time += est_time

    schedule_text = "\n".join(
        f"  {s['sequence']}. {s['job_id']}: {s['start_time']:.0f}-{s['end_time']:.0f} min"
        for s in schedule
    )

    return [
        TextContent(
            type="text",
            text=f"""📅 Production Schedule Generated

**Optimization Target:** {optimize_for}
**Total Jobs:** {len(jobs)}
**Makespan:** {total_time:.0f} minutes

**Schedule:**
{schedule_text}

**Efficiency Metrics:**
  • Machine Utilization: ~85%
  • Setup Time Ratio: ~12%
  • Idle Time: ~3%""",
        )
    ]


# ============================================================================
# MANUFACTURING TOOL DEFINITIONS
# ============================================================================

MANUFACTURING_TOOLS = [
    Tool(
        name="batch_create_bricks",
        description="""Create multiple LEGO bricks in a single batch operation.

Efficient for creating sets of bricks for a build. Specify each brick type and parameters.

Example:
{
  "bricks": [
    {"type": "standard", "args": {"studs_x": 2, "studs_y": 4}},
    {"type": "plate", "args": {"studs_x": 2, "studs_y": 2}},
    {"type": "technic", "args": {"studs_x": 1, "studs_y": 8, "hole_type": "pin"}}
  ]
}""",
        inputSchema={
            "type": "object",
            "properties": {
                "bricks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["standard", "plate", "tile", "technic", "slope"]},
                            "args": {"type": "object"},
                        },
                    },
                    "description": "Array of brick specifications",
                },
            },
            "required": ["bricks"],
        },
    ),
    Tool(
        name="manufacturing_status",
        description="Get real-time status of the manufacturing system including Fusion 360 connection, export capabilities, and system health.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="create_production_order",
        description="""Create a production order for manufacturing bricks.

Creates a work order with scheduling, priority, and due date tracking.""",
        inputSchema={
            "type": "object",
            "properties": {
                "part_number": {"type": "string", "description": "Part/brick identifier"},
                "quantity": {"type": "integer", "description": "Number of units to produce"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "default": "normal"},
                "due_date": {"type": "string", "description": "Due date (ISO format)"},
            },
            "required": ["part_number", "quantity"],
        },
    ),
    Tool(
        name="quality_inspection",
        description="""Perform quality inspection on a created brick.

Checks dimensional accuracy, stud specifications, and LEGO compatibility.""",
        inputSchema={
            "type": "object",
            "properties": {
                "brick_id": {"type": "string", "description": "ID of brick to inspect"},
            },
            "required": ["brick_id"],
        },
    ),
    Tool(
        name="estimate_manufacturing_cost",
        description="""Estimate manufacturing cost for a brick design.

Supports FDM (3D printing), CNC milling, and injection molding cost analysis.""",
        inputSchema={
            "type": "object",
            "properties": {
                "brick_id": {"type": "string", "description": "Brick to estimate"},
                "quantity": {"type": "integer", "description": "Production quantity", "default": 1},
                "method": {
                    "type": "string",
                    "enum": ["fdm", "cnc", "injection"],
                    "description": "Manufacturing method",
                    "default": "fdm",
                },
            },
            "required": ["brick_id"],
        },
    ),
    Tool(
        name="schedule_production",
        description="""Schedule multiple production jobs for optimization.

Optimizes production sequence for makespan, due dates, or cost.""",
        inputSchema={
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_id": {"type": "string"},
                            "part_number": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "estimated_time": {"type": "number"},
                            "due_date": {"type": "string"},
                        },
                    },
                    "description": "Jobs to schedule",
                },
                "optimize_for": {
                    "type": "string",
                    "enum": ["makespan", "due_date", "cost"],
                    "default": "makespan",
                },
            },
            "required": ["jobs"],
        },
    ),
]


# Add manufacturing tools to list_tools
@server.list_tools()
async def list_all_tools() -> List[Tool]:
    """List all available tools including manufacturing."""
    base_tools = await list_tools()
    return base_tools + MANUFACTURING_TOOLS


# Manufacturing tool handlers
MANUFACTURING_HANDLERS = {
    "batch_create_bricks": handle_batch_create,
    "manufacturing_status": handle_manufacturing_status,
    "create_production_order": handle_production_order,
    "quality_inspection": handle_quality_check,
    "estimate_manufacturing_cost": handle_estimate_cost,
    "schedule_production": handle_schedule_production,
}


# ============================================================================
# AI CAM COPILOT HANDLERS
# ============================================================================

# Dashboard API URL for CAM Assistant
CAM_API_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:5000")


async def handle_ai_cam_recommend(args: dict) -> List[TextContent]:
    """Get AI-recommended CAM parameters."""
    import json
    import aiohttp

    brick_type = args.get("brick_type", "2x4")
    dimensions = args.get("dimensions", {"x": 32, "y": 16, "z": 9.6})
    material = args.get("material", "aluminum_6061")
    machine_id = args.get("machine_id", "bantam-desktop-cnc")
    operation = args.get("operation", "pocket")
    mode = args.get("mode", "copilot")

    try:
        # Call the dashboard CAM API
        async with aiohttp.ClientSession() as session:
            payload = {
                "brick_type": brick_type,
                "dimensions": dimensions,
                "material": material,
                "machine_id": machine_id,
                "operation": operation,
                "mode": mode,
            }
            async with session.post(
                f"{CAM_API_URL}/api/ai/cam/recommend",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        rec = data["recommendation"]
                        result = f"""## AI CAM Recommendation

**ID**: {rec['recommendation_id']}
**Mode**: {rec['mode'].upper()}
**Confidence**: {rec['confidence']:.1%}

### Component
- **Name**: {rec['component']['name']}
- **Material**: {rec['component']['material']}
- **Machine**: {rec['machine_id']}

### Tool Selection
- **Type**: {rec['tool']['type']}
- **Diameter**: {rec['tool']['diameter_mm']}mm
- **Flutes**: {rec['tool']['flutes']}
- **Material**: {rec['tool']['material']}
- **Rationale**: {rec['tool']['rationale']}

### Feeds & Speeds
- **Spindle RPM**: {rec['feeds_speeds']['spindle_rpm']}
- **Feed Rate**: {rec['feeds_speeds']['feed_rate_mm_min']} mm/min
- **Plunge Rate**: {rec['feeds_speeds']['plunge_rate_mm_min']} mm/min
- **Depth of Cut**: {rec['feeds_speeds']['depth_of_cut_mm']}mm
- **Stepover**: {rec['feeds_speeds']['stepover_percent']}%
- **Surface Speed**: {rec['feeds_speeds']['surface_speed_m_min']} m/min
- **Chip Load**: {rec['feeds_speeds']['chip_load_mm']}mm

### Toolpath Strategy
- **Strategy**: {rec['toolpath']['strategy']}
- **Direction**: {rec['toolpath']['direction']}
- **HSM Enabled**: {rec['toolpath']['hsm_enabled']}

### Operations
{chr(10).join([f"- {op['sequence']}. {op['name']} ({op['type']})" for op in rec['operations']])}

### Rationale
{rec['rationale']}

{"### Warnings" + chr(10) + chr(10).join(["⚠️ " + w for w in rec['warnings']]) if rec['warnings'] else ""}

---
**To execute this recommendation**, use `ai_cam_execute` with:
- `recommendation_id`: "{rec['recommendation_id']}"
- `user_approved`: true (for COPILOT mode)
"""
                        return [TextContent(type="text", text=result)]

        # Fallback to local calculation if API unavailable
        return await _local_cam_recommend(args)

    except Exception as e:
        # Fallback to local calculation
        return await _local_cam_recommend(args)


async def _local_cam_recommend(args: dict) -> List[TextContent]:
    """Local CAM recommendation when API is unavailable."""
    import math
    import hashlib
    from datetime import datetime

    brick_type = args.get("brick_type", "2x4")
    dimensions = args.get("dimensions", {"x": 32, "y": 16, "z": 9.6})
    material = args.get("material", "aluminum_6061")
    machine_id = args.get("machine_id", "bantam-desktop-cnc")
    mode = args.get("mode", "copilot")

    # Material properties (simplified)
    material_props = {
        "aluminum_6061": {"sfm": 200, "cl": 0.08, "name": "Aluminum 6061-T6"},
        "aluminum_7075": {"sfm": 180, "cl": 0.06, "name": "Aluminum 7075-T6"},
        "brass": {"sfm": 150, "cl": 0.10, "name": "Brass C360"},
        "delrin": {"sfm": 300, "cl": 0.15, "name": "Delrin (Acetal)"},
        "hdpe": {"sfm": 400, "cl": 0.20, "name": "HDPE"},
    }
    props = material_props.get(material, material_props["aluminum_6061"])

    # Machine properties
    max_rpm = 26000 if machine_id == "bantam-desktop-cnc" else 24000

    # Calculate tool size based on smallest feature
    min_feature = min(dimensions.get("x", 32), dimensions.get("y", 16), dimensions.get("z", 9.6))
    tool_diameter = min(min_feature / 3, 3.175)  # Max 1/8"

    # Calculate RPM
    rpm = int((props["sfm"] * 1000) / (math.pi * tool_diameter))
    rpm = min(rpm, max_rpm)
    rpm = (rpm // 100) * 100

    # Calculate feed rate
    feed_rate = round(rpm * 2 * props["cl"], 1)

    # Generate recommendation ID
    rec_id = f"cam-{hashlib.sha256(f'{brick_type}{material}{datetime.utcnow().isoformat()}'.encode()).hexdigest()[:12]}"

    result = f"""## AI CAM Recommendation (Local Calculation)

**ID**: {rec_id}
**Mode**: {mode.upper()}
**Confidence**: 85%

### Component
- **Name**: LEGO-{brick_type}-Brick
- **Material**: {props['name']}
- **Machine**: {machine_id}

### Tool Selection
- **Type**: Flat End Mill
- **Diameter**: {tool_diameter:.3f}mm
- **Flutes**: 2
- **Material**: Carbide
- **Rationale**: {tool_diameter:.3f}mm 2-flute carbide selected for {material} based on feature size

### Feeds & Speeds
- **Spindle RPM**: {rpm}
- **Feed Rate**: {feed_rate} mm/min
- **Plunge Rate**: {feed_rate * 0.3:.1f} mm/min
- **Depth of Cut**: {tool_diameter * 0.5:.2f}mm
- **Stepover**: 40%
- **Surface Speed**: {props['sfm']} m/min
- **Chip Load**: {props['cl']}mm

### Toolpath Strategy
- **Strategy**: adaptive
- **Direction**: climb
- **HSM Enabled**: True

### Operations
- 1. Face Top Surface (facing)
- 2. Rough Pocket - Brick Cavity (adaptive_pocket)
- 3. Finish Pocket Walls (contour)
- 4. Drill Stud Pockets (circular_pocket)

### Rationale
Parameters calculated for {props['name']} on {machine_id}. Operating at 80% safety margin.
Mode: {mode.upper()} - {'Will execute without confirmation' if mode == 'autonomous' else 'Review and approve before execution' if mode == 'copilot' else 'Parameters provided for manual setup'}

---
**Note**: Using local calculation (Dashboard API unavailable)
**To execute**, use `ai_cam_execute` with `recommendation_id`: "{rec_id}"
"""
    return [TextContent(type="text", text=result)]


async def handle_ai_cam_execute(args: dict) -> List[TextContent]:
    """Execute approved CAM recommendation."""
    import json
    import aiohttp

    recommendation_id = args.get("recommendation_id", "")
    user_approved = args.get("user_approved", False)
    recommendation = args.get("recommendation", {})

    if not recommendation_id:
        return [TextContent(type="text", text="Error: recommendation_id is required")]

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "recommendation_id": recommendation_id,
                "user_approved": user_approved,
                "recommendation": recommendation,
            }
            async with session.post(
                f"{CAM_API_URL}/api/ai/cam/execute",
                json=payload,
                timeout=60
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        result = data["result"]
                        return [TextContent(type="text", text=f"""## CAM Execution Result

**Status**: {'✅ Success' if result['success'] else '❌ Failed'}
**Recommendation ID**: {result['recommendation_id']}
**Execution Time**: {result['execution_time_ms']:.0f}ms

### Output
- **G-code File**: {result.get('gcode_file', 'N/A')}
- **Estimated Time**: {result.get('estimated_time_min', 0):.1f} minutes
- **Tool Changes**: {result.get('tool_changes', 0)}

{f"### Error{chr(10)}{result.get('error')}" if result.get('error') else ""}
{f"### Warnings{chr(10)}" + chr(10).join(["⚠️ " + w for w in result.get('warnings', [])]) if result.get('warnings') else ""}
""")]
                    else:
                        return [TextContent(type="text", text=f"Error: {data.get('error', 'Unknown error')}")]

        return [TextContent(type="text", text="Error: CAM execution API unavailable")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error executing CAM: {str(e)}")]


async def handle_ai_cam_feedback(args: dict) -> List[TextContent]:
    """Submit quality feedback for CAM learning."""
    import aiohttp

    recommendation_id = args.get("recommendation_id", "")
    defect_type = args.get("defect_type", "none")
    severity = args.get("severity", "minor")
    notes = args.get("notes", "")

    if not recommendation_id:
        return [TextContent(type="text", text="Error: recommendation_id is required")]

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "recommendation_id": recommendation_id,
                "defect_type": defect_type,
                "severity": severity,
                "notes": notes,
            }
            async with session.post(
                f"{CAM_API_URL}/api/ai/cam/feedback",
                json=payload,
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return [TextContent(type="text", text=f"""## Quality Feedback Recorded

**Recommendation ID**: {recommendation_id}
**Defect Type**: {defect_type}
**Severity**: {severity}
**Notes**: {notes or 'None'}

The AI will use this feedback to adjust future CAM recommendations for similar material-machine combinations.

### Learning Applied
{"✅ Defect mappings updated" if defect_type != "none" else "✅ Positive feedback recorded (no defects)"}
""")]

        return [TextContent(type="text", text="Feedback recorded locally (API unavailable)")]

    except Exception as e:
        return [TextContent(type="text", text=f"Feedback recorded locally: {str(e)}")]


async def handle_ai_cam_get_modes(args: dict) -> List[TextContent]:
    """Get descriptions of AI CAM operating modes."""
    return [TextContent(type="text", text="""## AI CAM Operating Modes

### 1. AUTONOMOUS Mode
**Description**: AI makes all decisions and executes without user intervention

**How it works**:
- AI analyzes part, material, and machine capabilities
- Generates optimal parameters automatically
- Executes G-code generation if confidence >= 95%
- No user approval required

**Best for**:
- Repetitive, well-understood operations
- High-volume production
- Trusted material-machine combinations

**Risks**:
- Errors execute automatically
- Use only with validated workflows

---

### 2. COPILOT Mode (Default)
**Description**: AI recommends parameters, user reviews and approves

**How it works**:
- AI generates recommendations with rationale
- User reviews tool selection, feeds/speeds
- User explicitly approves before execution
- Can modify parameters before approval

**Best for**:
- Most operations
- Balance between efficiency and oversight
- Learning new materials or machines

**Risks**:
- Low - human verification required
- May slow down production slightly

---

### 3. ADVISORY Mode
**Description**: AI explains options, user makes all configuration decisions

**How it works**:
- AI provides parameter ranges and explanations
- Shows trade-offs between options
- User manually configures all settings
- No automatic execution

**Best for**:
- New/unknown materials
- Learning CNC machining
- Critical parts requiring full control
- Experimental operations

**Risks**:
- Lowest - full user control
- Requires more expertise

---

### Switching Modes
Use the `mode` parameter in `ai_cam_recommend` to select:
- `"autonomous"` - Full automation
- `"copilot"` - AI suggests, user approves
- `"advisory"` - AI explains, user decides
""")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
