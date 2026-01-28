"""
Milling Tools - CNC Machining Operations

Complete CNC milling functionality for LEGO brick manufacturing.
Supports various operations, toolpaths, and machine configurations.
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import math


# ============================================================================
# ENUMS
# ============================================================================


class OperationType(Enum):
    """Types of CNC milling operations."""

    FACE = "face"  # Face milling (flatten top)
    ADAPTIVE = "adaptive"  # Adaptive clearing (roughing)
    POCKET = "pocket"  # Pocket milling (cavities)
    CONTOUR = "contour"  # Contour/profile milling
    SLOT = "slot"  # Slot milling
    BORE = "bore"  # Boring (holes)
    DRILL = "drill"  # Drilling
    TAP = "tap"  # Tapping (threads)
    ENGRAVE = "engrave"  # Engraving/text
    CHAMFER = "chamfer"  # Chamfer edges
    THREAD_MILL = "thread_mill"  # Thread milling


class ToolType(Enum):
    """Types of cutting tools."""

    FLAT_ENDMILL = "flat_endmill"
    BALL_ENDMILL = "ball_endmill"
    BULL_ENDMILL = "bull_endmill"
    DRILL = "drill"
    SPOT_DRILL = "spot_drill"
    TAP = "tap"
    CHAMFER_MILL = "chamfer_mill"
    ENGRAVING = "engraving"
    THREAD_MILL = "thread_mill"


class MaterialType(Enum):
    """Workpiece materials with cutting parameters."""

    ABS = "abs"
    PLA = "pla"
    NYLON = "nylon"
    ACETAL = "acetal"
    HDPE = "hdpe"
    ACRYLIC = "acrylic"
    ALUMINUM = "aluminum"


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================


@dataclass
class CuttingTool:
    """Definition of a cutting tool."""

    name: str
    type: ToolType
    diameter: float  # mm
    flute_length: float  # mm
    overall_length: float  # mm
    flutes: int = 2
    corner_radius: float = 0  # mm (for bull endmills)
    point_angle: float = 118  # degrees (for drills)
    helix_angle: float = 30  # degrees
    coating: str = "uncoated"

    # Tool holder
    holder_gauge_length: float = 50.0  # mm


# Standard tool library for LEGO brick machining
LEGO_TOOL_LIBRARY = {
    "flat_2mm": CuttingTool("2mm Flat Endmill", ToolType.FLAT_ENDMILL, 2.0, 8.0, 50.0, 2),
    "flat_3mm": CuttingTool("3mm Flat Endmill", ToolType.FLAT_ENDMILL, 3.0, 12.0, 50.0, 2),
    "flat_4mm": CuttingTool("4mm Flat Endmill", ToolType.FLAT_ENDMILL, 4.0, 16.0, 50.0, 2),
    "flat_6mm": CuttingTool("6mm Flat Endmill", ToolType.FLAT_ENDMILL, 6.0, 20.0, 60.0, 3),
    "ball_1mm": CuttingTool("1mm Ball Endmill", ToolType.BALL_ENDMILL, 1.0, 4.0, 50.0, 2),
    "ball_2mm": CuttingTool("2mm Ball Endmill", ToolType.BALL_ENDMILL, 2.0, 8.0, 50.0, 2),
    "ball_3mm": CuttingTool("3mm Ball Endmill", ToolType.BALL_ENDMILL, 3.0, 12.0, 50.0, 2),
    "drill_1.5mm": CuttingTool("1.5mm Drill", ToolType.DRILL, 1.5, 20.0, 45.0, 2),
    "drill_2.4mm": CuttingTool("2.4mm Drill (Technic)", ToolType.DRILL, 2.4, 30.0, 55.0, 2),
    "drill_4.8mm": CuttingTool("4.8mm Drill (Pin Hole)", ToolType.DRILL, 4.8, 40.0, 70.0, 2),
    "spot_3mm": CuttingTool(
        "3mm Spot Drill", ToolType.SPOT_DRILL, 3.0, 5.0, 40.0, 2, point_angle=90
    ),
    "chamfer_6mm": CuttingTool("6mm 45° Chamfer", ToolType.CHAMFER_MILL, 6.0, 6.0, 50.0, 2),
    "engraving_0.2mm": CuttingTool(
        "0.2mm Engraving", ToolType.ENGRAVING, 0.2, 3.0, 40.0, 1, point_angle=30
    ),
}


# ============================================================================
# CUTTING PARAMETERS
# ============================================================================

# Cutting parameters by material (surface speed m/min, chip load mm/tooth)
CUTTING_PARAMS = {
    MaterialType.ABS: {
        ToolType.FLAT_ENDMILL: {"sfm": 150, "chip_load": 0.05, "doc": 0.5, "woc": 0.4},
        ToolType.BALL_ENDMILL: {"sfm": 120, "chip_load": 0.03, "doc": 0.3, "woc": 0.3},
        ToolType.DRILL: {"sfm": 50, "chip_load": 0.08, "peck": 2.0},
    },
    MaterialType.PLA: {
        ToolType.FLAT_ENDMILL: {"sfm": 100, "chip_load": 0.04, "doc": 0.4, "woc": 0.35},
        ToolType.BALL_ENDMILL: {"sfm": 80, "chip_load": 0.025, "doc": 0.25, "woc": 0.25},
        ToolType.DRILL: {"sfm": 40, "chip_load": 0.06, "peck": 1.5},
    },
    MaterialType.ACETAL: {
        ToolType.FLAT_ENDMILL: {"sfm": 180, "chip_load": 0.06, "doc": 0.6, "woc": 0.45},
        ToolType.BALL_ENDMILL: {"sfm": 150, "chip_load": 0.04, "doc": 0.4, "woc": 0.35},
        ToolType.DRILL: {"sfm": 60, "chip_load": 0.1, "peck": 2.5},
    },
    MaterialType.ALUMINUM: {
        ToolType.FLAT_ENDMILL: {"sfm": 300, "chip_load": 0.08, "doc": 0.8, "woc": 0.5},
        ToolType.BALL_ENDMILL: {"sfm": 250, "chip_load": 0.05, "doc": 0.5, "woc": 0.4},
        ToolType.DRILL: {"sfm": 80, "chip_load": 0.15, "peck": 3.0},
    },
}


def calculate_speeds_feeds(tool: CuttingTool, material: MaterialType) -> Dict[str, float]:
    """
    Calculate spindle speed and feed rate for a tool/material combo.

    Returns:
        Dict with rpm, feed_rate (mm/min), plunge_rate, doc, woc
    """
    params = CUTTING_PARAMS.get(material, CUTTING_PARAMS[MaterialType.ABS])
    tool_params = params.get(tool.type, params[ToolType.FLAT_ENDMILL])

    # Calculate RPM from surface feet per minute
    sfm = tool_params["sfm"]
    rpm = (sfm * 1000) / (math.pi * tool.diameter)
    rpm = min(rpm, 24000)  # Cap at typical spindle max

    # Calculate feed rate
    chip_load = tool_params["chip_load"]
    feed_rate = rpm * chip_load * tool.flutes

    # Plunge rate (typically 30-50% of feed)
    plunge_rate = feed_rate * 0.4

    # Depth and width of cut as ratio of tool diameter
    doc = tool.diameter * tool_params.get("doc", 0.5)
    woc = tool.diameter * tool_params.get("woc", 0.4)

    return {
        "rpm": round(rpm),
        "feed_rate": round(feed_rate, 1),
        "plunge_rate": round(plunge_rate, 1),
        "depth_of_cut": round(doc, 2),
        "width_of_cut": round(woc, 2),
    }


# ============================================================================
# OPERATION DEFINITIONS
# ============================================================================


@dataclass
class MillingOperation:
    """Definition of a milling operation."""

    name: str
    type: OperationType
    tool_name: str

    # Geometry
    geometry_type: str = "solid"  # solid, face, edge, sketch
    geometry_selection: str = ""  # Face/feature to machine

    # Heights (mm from origin)
    clearance_height: float = 10.0
    retract_height: float = 5.0
    top_height: float = 0.0
    bottom_height: float = -10.0

    # Cutting parameters (if None, calculated from material)
    rpm: Optional[int] = None
    feed_rate: Optional[float] = None
    plunge_rate: Optional[float] = None
    depth_of_cut: Optional[float] = None
    width_of_cut: Optional[float] = None

    # Strategy options
    stepover: float = 0.4  # As ratio of tool diameter
    stepdown: float = 0.5  # As ratio of tool diameter
    smoothing: bool = True
    both_ways: bool = True  # Climb and conventional

    # Stock to leave
    radial_stock: float = 0.0  # mm
    axial_stock: float = 0.0  # mm


# ============================================================================
# LEGO-SPECIFIC OPERATIONS
# ============================================================================


def create_stud_operation(
    stud_positions: List[Tuple[float, float]],
    stud_height: float = 1.7,
    stud_diameter: float = 4.8,
    material: MaterialType = MaterialType.ABS,
) -> List[MillingOperation]:
    """
    Create operations to machine studs on top of brick.
    Uses a combination of adaptive clearing and finishing.
    """
    operations = []

    # Roughing with 3mm endmill
    rough = MillingOperation(
        name="Studs Roughing",
        type=OperationType.ADAPTIVE,
        tool_name="flat_3mm",
        geometry_type="solid",
        top_height=stud_height,
        bottom_height=0,
        stepover=0.4,
        stepdown=0.5,
        radial_stock=0.1,
    )
    operations.append(rough)

    # Finishing with 2mm endmill
    finish = MillingOperation(
        name="Studs Finishing",
        type=OperationType.CONTOUR,
        tool_name="flat_2mm",
        geometry_type="solid",
        top_height=stud_height,
        bottom_height=0,
        stepdown=0.3,
        radial_stock=0,
        smoothing=True,
    )
    operations.append(finish)

    return operations


def create_hollow_operation(
    width: float,
    depth: float,
    height: float,
    wall_thickness: float = 1.5,
    material: MaterialType = MaterialType.ABS,
) -> List[MillingOperation]:
    """
    Create operations to machine hollow interior of brick.
    """
    operations = []

    # Main cavity roughing
    rough = MillingOperation(
        name="Cavity Roughing",
        type=OperationType.ADAPTIVE,
        tool_name="flat_4mm",
        geometry_type="pocket",
        top_height=0,
        bottom_height=-(height - 1.0),  # Leave 1mm floor
        stepover=0.4,
        stepdown=0.6,
        radial_stock=0.15,
    )
    operations.append(rough)

    # Wall finishing
    finish = MillingOperation(
        name="Cavity Walls Finishing",
        type=OperationType.CONTOUR,
        tool_name="flat_2mm",
        geometry_type="pocket",
        top_height=0,
        bottom_height=-(height - 1.0),
        stepdown=0.3,
        radial_stock=0,
    )
    operations.append(finish)

    return operations


def create_tube_operation(
    tube_positions: List[Tuple[float, float]],
    tube_outer: float = 6.51,
    tube_inner: float = 4.8,
    tube_height: float = 8.6,
    material: MaterialType = MaterialType.ABS,
) -> List[MillingOperation]:
    """
    Create operations to machine bottom tubes.
    This is typically done from the bottom setup.
    """
    operations = []

    # Bore the inner holes
    bore = MillingOperation(
        name="Tube Inner Bore",
        type=OperationType.BORE,
        tool_name="flat_3mm",  # Helical bore with 3mm
        geometry_type="circle",
        top_height=0,
        bottom_height=-tube_height,
        stepdown=0.4,
    )
    operations.append(bore)

    return operations


def create_technic_hole_operation(
    hole_positions: List[Tuple[float, float, float]],
    hole_diameter: float = 4.8,
    axis: str = "x",
    material: MaterialType = MaterialType.ABS,
) -> List[MillingOperation]:
    """
    Create operations to machine Technic pin holes.
    """
    operations = []

    # Spot drill for accuracy
    spot = MillingOperation(
        name="Pin Holes Spot",
        type=OperationType.DRILL,
        tool_name="spot_3mm",
        geometry_type="point",
        bottom_height=-2.0,  # 2mm spot depth
    )
    operations.append(spot)

    # Drill through
    drill = MillingOperation(
        name="Pin Holes Drill",
        type=OperationType.DRILL,
        tool_name="drill_4.8mm",
        geometry_type="point",
        bottom_height=-10.0,  # Through
    )
    operations.append(drill)

    return operations


def create_slope_operation(
    angle: float,
    direction: str,
    width: float,
    depth: float,
    height: float,
    material: MaterialType = MaterialType.ABS,
) -> List[MillingOperation]:
    """
    Create operations to machine a slope surface.
    Uses 3D adaptive and 3D contour for smooth finish.
    """
    operations = []

    # 3D roughing
    rough = MillingOperation(
        name="Slope 3D Roughing",
        type=OperationType.ADAPTIVE,
        tool_name="ball_3mm",
        geometry_type="solid",
        top_height=height,
        bottom_height=0,
        stepover=0.35,
        stepdown=0.4,
        radial_stock=0.1,
    )
    operations.append(rough)

    # 3D finishing with ball endmill
    finish = MillingOperation(
        name="Slope 3D Finishing",
        type=OperationType.CONTOUR,
        tool_name="ball_2mm",
        geometry_type="solid",
        top_height=height,
        bottom_height=0,
        stepover=0.15,  # Fine stepover for smooth surface
        smoothing=True,
    )
    operations.append(finish)

    return operations


def create_engraving_operation(
    text: str, face: str, depth: float = 0.3, material: MaterialType = MaterialType.ABS
) -> MillingOperation:
    """
    Create operation to engrave text or patterns.
    """
    return MillingOperation(
        name=f"Engrave '{text}'",
        type=OperationType.ENGRAVE,
        tool_name="engraving_0.2mm",
        geometry_type="sketch",
        top_height=0,
        bottom_height=-depth,
        stepdown=0.1,
    )


# ============================================================================
# MACHINE CONFIGURATIONS
# ============================================================================

MACHINES = {
    "haas_vf2": {
        "name": "Haas VF-2",
        "type": "vertical_mill",
        "controller": "haas",
        "post_processor": "haas_ngc.cps",
        "travel": {"x": 762, "y": 406, "z": 508},
        "spindle_max": 8100,
        "rapid_xy": 25400,
        "rapid_z": 15240,
    },
    "tormach_1100mx": {
        "name": "Tormach 1100MX",
        "type": "vertical_mill",
        "controller": "pathpilot",
        "post_processor": "tormach_pathpilot.cps",
        "travel": {"x": 457, "y": 267, "z": 406},
        "spindle_max": 10000,
        "rapid_xy": 6350,
        "rapid_z": 3810,
    },
    "datron_neo": {
        "name": "Datron Neo",
        "type": "high_speed_mill",
        "controller": "datron",
        "post_processor": "datron.cps",
        "travel": {"x": 500, "y": 420, "z": 220},
        "spindle_max": 60000,
        "rapid_xy": 60000,
        "rapid_z": 40000,
    },
    "shapeoko_4": {
        "name": "Shapeoko 4",
        "type": "router",
        "controller": "grbl",
        "post_processor": "grbl.cps",
        "travel": {"x": 838, "y": 838, "z": 100},
        "spindle_max": 24000,
        "rapid_xy": 5000,
        "rapid_z": 3000,
    },
    "nomad_3": {
        "name": "Carbide3D Nomad 3",
        "type": "desktop_mill",
        "controller": "grbl",
        "post_processor": "carbide3d.cps",
        "travel": {"x": 203, "y": 203, "z": 76},
        "spindle_max": 24000,
        "rapid_xy": 2540,
        "rapid_z": 1270,
    },
    "bantam_desktop": {
        "name": "Bantam Tools Desktop CNC",
        "type": "desktop_mill",
        "controller": "bantam",
        "post_processor": "bantam.cps",
        "travel": {"x": 140, "y": 114, "z": 38},
        "spindle_max": 28000,
        "rapid_xy": 4500,
        "rapid_z": 2500,
    },
    "roland_srm20": {
        "name": "Roland SRM-20",
        "type": "desktop_mill",
        "controller": "roland",
        "post_processor": "roland.cps",
        "travel": {"x": 203, "y": 152, "z": 60},
        "spindle_max": 7000,
        "rapid_xy": 1800,
        "rapid_z": 1800,
    },
    "grbl_generic": {
        "name": "Generic GRBL Machine",
        "type": "router",
        "controller": "grbl",
        "post_processor": "grbl.cps",
        "travel": {"x": 300, "y": 300, "z": 100},
        "spindle_max": 24000,
        "rapid_xy": 5000,
        "rapid_z": 3000,
    },
}


# ============================================================================
# COMPLETE BRICK MILLING SETUP
# ============================================================================


def generate_brick_operations(
    brick_type: str,
    dimensions: Dict[str, float],
    features: Dict[str, Any],
    material: MaterialType = MaterialType.ABS,
) -> Dict[str, Any]:
    """
    Generate complete milling operations for a LEGO brick.

    Args:
        brick_type: Type of brick (standard, plate, tile, slope, technic)
        dimensions: Dict with width, depth, height in mm
        features: Dict with stud_positions, tube_positions, holes, etc.
        material: Workpiece material

    Returns:
        Complete operation setup with all toolpaths
    """
    operations = []

    width = dimensions.get("width", 16.0)
    depth = dimensions.get("depth", 32.0)
    height = dimensions.get("height", 9.6)

    # Setup 1: Top (studs and exterior)
    setup1_ops = []

    # Face mill top
    setup1_ops.append(
        MillingOperation(
            name="Face Top",
            type=OperationType.FACE,
            tool_name="flat_6mm",
            top_height=0.5,
            bottom_height=0,
        )
    )

    # Studs
    if features.get("stud_positions"):
        setup1_ops.extend(create_stud_operation(features["stud_positions"], material=material))

    # Exterior contour
    setup1_ops.append(
        MillingOperation(
            name="Exterior Profile",
            type=OperationType.CONTOUR,
            tool_name="flat_3mm",
            top_height=height,
            bottom_height=0,
            stepdown=0.5,
        )
    )

    # Slope if present
    if "slope" in features:
        slope = features["slope"]
        setup1_ops.extend(
            create_slope_operation(
                slope["angle"], slope["direction"], width, depth, height, material
            )
        )

    # Setup 2: Bottom (hollow and tubes)
    setup2_ops = []

    # Hollow interior
    if features.get("hollow", True):
        setup2_ops.extend(create_hollow_operation(width, depth, height, material=material))

    # Tubes
    if features.get("tube_positions"):
        setup2_ops.extend(create_tube_operation(features["tube_positions"], material=material))

    # Setup 3: Side holes (Technic)
    setup3_ops = []

    if features.get("technic_holes"):
        for axis in ["x", "y"]:
            holes = [h for h in features["technic_holes"] if h.get("axis") == axis]
            if holes:
                setup3_ops.extend(
                    create_technic_hole_operation(
                        [h["position"] for h in holes], axis=axis, material=material
                    )
                )

    return {
        "brick_type": brick_type,
        "material": material.value,
        "setups": [
            {
                "name": "Setup 1 - Top",
                "orientation": "top_up",
                "operations": [op.__dict__ for op in setup1_ops],
            },
            {
                "name": "Setup 2 - Bottom",
                "orientation": "bottom_up",
                "operations": [op.__dict__ for op in setup2_ops],
            },
            {
                "name": "Setup 3 - Side Holes",
                "orientation": "side",
                "operations": [op.__dict__ for op in setup3_ops],
            },
        ],
        "total_operations": len(setup1_ops) + len(setup2_ops) + len(setup3_ops),
    }


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

MILLING_TOOLS = {
    "generate_gcode": {
        "description": """Generate CNC milling G-code for a LEGO brick component.

This tool calls Fusion 360's CAM system to generate actual G-code files
that can be run on a CNC machine.

Requires a brick to already be created in Fusion 360.
Returns the path to the generated G-code file.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string",
                    "description": "Name of the component in Fusion 360 to mill",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path for the output G-code file",
                },
                "material": {
                    "type": "string",
                    "enum": ["abs", "pla", "nylon", "acetal", "hdpe", "acrylic", "aluminum"],
                    "default": "abs",
                    "description": "Material to be milled",
                },
                "machine": {
                    "type": "string",
                    "enum": ["grbl", "mach3", "linuxcnc", "fanuc", "haas"],
                    "default": "grbl",
                    "description": "Target CNC controller/post processor",
                },
            },
            "required": ["component_name"],
        },
    },
    "generate_milling_operations": {
        "description": """Generate CNC milling operations for a LEGO brick.

Creates a complete machining setup with multiple operations for:
- Top side: Face milling, studs, exterior profile, slopes
- Bottom side: Hollow cavity, tubes, ribs
- Side holes: Technic pin holes

Supports materials: ABS, PLA, Nylon, Acetal, HDPE, Acrylic, Aluminum""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "enum": ["standard", "plate", "tile", "slope", "technic"],
                    "description": "Type of brick",
                },
                "dimensions": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "number"},
                        "depth": {"type": "number"},
                        "height": {"type": "number"},
                    },
                    "description": "Brick dimensions in mm",
                },
                "features": {
                    "type": "object",
                    "description": "Brick features (stud_positions, tube_positions, hollow, slope, technic_holes)",
                },
                "material": {
                    "type": "string",
                    "enum": ["abs", "pla", "nylon", "acetal", "hdpe", "acrylic", "aluminum"],
                    "default": "abs",
                },
            },
            "required": ["brick_type", "dimensions"],
        },
    },
    "calculate_cutting_params": {
        "description": "Calculate optimal cutting parameters for a tool and material.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": list(LEGO_TOOL_LIBRARY.keys()),
                    "description": "Tool from library",
                },
                "material": {
                    "type": "string",
                    "enum": ["abs", "pla", "nylon", "acetal", "hdpe", "acrylic", "aluminum"],
                    "default": "abs",
                },
            },
            "required": ["tool_name"],
        },
    },
    "list_machines": {
        "description": "List available CNC machine configurations.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "list_tools": {
        "description": "List available cutting tools in the library.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def list_machines() -> Dict[str, Any]:
    """List all available machine configurations."""
    return {"machines": MACHINES}


def list_tools() -> Dict[str, Any]:
    """List all tools in the library."""
    return {
        "tools": {
            name: {
                "name": tool.name,
                "type": tool.type.value,
                "diameter": tool.diameter,
                "flutes": tool.flutes,
            }
            for name, tool in LEGO_TOOL_LIBRARY.items()
        }
    }
