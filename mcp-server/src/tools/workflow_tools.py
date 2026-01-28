"""
Workflow Tools - End-to-End Automation

Provides single-command workflows for complete brick creation pipelines:
- create_and_export: Create brick -> Export STL/3MF
- create_and_print: Create brick -> Export -> Slice for 3D printing
- create_and_mill: Create brick -> Export -> CAM setup -> G-code

These workflows chain together individual operations and return
consolidated results with all file paths.
"""

from typing import Dict, Any, List, Optional
import os
import time
import logging

logger = logging.getLogger(__name__)

# Workflow tool definitions for MCP
WORKFLOW_TOOLS = [
    {
        "name": "create_and_export",
        "description": "Create a LEGO brick and export it to STL/3MF format. Returns the brick details and export file path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "description": "Type of brick: standard, plate, tile, slope, technic, round",
                    "enum": ["standard", "plate", "tile", "slope", "technic", "round"],
                    "default": "standard"
                },
                "width": {
                    "type": "integer",
                    "description": "Width in studs (X dimension)",
                    "minimum": 1,
                    "maximum": 48
                },
                "depth": {
                    "type": "integer",
                    "description": "Depth in studs (Y dimension)",
                    "minimum": 1,
                    "maximum": 48
                },
                "height_bricks": {
                    "type": "number",
                    "description": "Height in brick units (1 brick = 3 plates)",
                    "default": 1.0
                },
                "export_format": {
                    "type": "string",
                    "description": "Export format: stl, 3mf, step",
                    "enum": ["stl", "3mf", "step"],
                    "default": "stl"
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the brick"
                }
            },
            "required": ["width", "depth"]
        }
    },
    {
        "name": "create_and_print",
        "description": "Complete 3D printing workflow: Create brick -> Export STL -> Slice with printer profile -> Generate G-code. Returns all file paths and print estimates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "description": "Type of brick",
                    "enum": ["standard", "plate", "tile", "slope", "technic", "round"],
                    "default": "standard"
                },
                "width": {
                    "type": "integer",
                    "description": "Width in studs",
                    "minimum": 1,
                    "maximum": 48
                },
                "depth": {
                    "type": "integer",
                    "description": "Depth in studs",
                    "minimum": 1,
                    "maximum": 48
                },
                "height_bricks": {
                    "type": "number",
                    "description": "Height in brick units",
                    "default": 1.0
                },
                "printer": {
                    "type": "string",
                    "description": "Printer profile: bambu_p1s, bambu_x1c, prusa_mk3s, ender3",
                    "enum": ["bambu_p1s", "bambu_x1c", "bambu_a1", "prusa_mk3s", "prusa_mk4", "ender3"],
                    "default": "bambu_p1s"
                },
                "quality": {
                    "type": "string",
                    "description": "Print quality preset",
                    "enum": ["draft", "normal", "fine", "ultra", "lego"],
                    "default": "lego"
                },
                "material": {
                    "type": "string",
                    "description": "Filament material",
                    "enum": ["pla", "petg", "abs", "asa"],
                    "default": "pla"
                }
            },
            "required": ["width", "depth"]
        }
    },
    {
        "name": "create_and_mill",
        "description": "Complete CNC milling workflow: Create brick -> Setup CAM -> Generate toolpaths -> Export G-code. Returns NC file path and machining estimates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "description": "Type of brick",
                    "enum": ["standard", "plate", "tile", "slope", "technic"],
                    "default": "standard"
                },
                "width": {
                    "type": "integer",
                    "description": "Width in studs",
                    "minimum": 1,
                    "maximum": 16
                },
                "depth": {
                    "type": "integer",
                    "description": "Depth in studs",
                    "minimum": 1,
                    "maximum": 16
                },
                "height_bricks": {
                    "type": "number",
                    "description": "Height in brick units",
                    "default": 1.0
                },
                "machine": {
                    "type": "string",
                    "description": "CNC machine/controller",
                    "enum": ["grbl", "tinyg_bantam", "haas", "linuxcnc", "mach3"],
                    "default": "grbl"
                },
                "stock_material": {
                    "type": "string",
                    "description": "Stock material for feeds/speeds",
                    "enum": ["abs", "delrin", "aluminum", "brass", "hdpe"],
                    "default": "abs"
                }
            },
            "required": ["width", "depth"]
        }
    },
    {
        "name": "create_and_engrave",
        "description": "Create brick and generate laser engraving G-code for custom text/logo on top surface.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "enum": ["standard", "plate", "tile"],
                    "default": "tile"
                },
                "width": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16
                },
                "depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16
                },
                "text": {
                    "type": "string",
                    "description": "Text to engrave on brick"
                },
                "svg_path": {
                    "type": "string",
                    "description": "Path to SVG file for custom design (alternative to text)"
                },
                "engrave_preset": {
                    "type": "string",
                    "description": "Laser power/speed preset",
                    "enum": ["abs_engrave_light", "abs_engrave_deep", "abs_cut_thin"],
                    "default": "abs_engrave_light"
                }
            },
            "required": ["width", "depth"]
        }
    }
]


async def handle_create_and_export(
    fusion_client,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a brick and export it.

    Steps:
    1. Create brick in Fusion 360
    2. Export to specified format
    """
    results = {
        "workflow": "create_and_export",
        "steps": [],
        "start_time": time.time()
    }

    try:
        # Step 1: Create brick
        brick_type = params.get("brick_type", "standard")
        width = params["width"]
        depth = params["depth"]
        height = params.get("height_bricks", 1.0)
        name = params.get("name") or f"{brick_type}_{width}x{depth}"

        create_result = await fusion_client.call_api("create_brick", {
            "studs_x": width,
            "studs_y": depth,
            "height_units": height,
            "name": name
        })

        results["steps"].append({
            "step": "create_brick",
            "success": create_result.get("success", False),
            "component_name": create_result.get("component_name"),
            "dimensions": create_result.get("dimensions")
        })

        if not create_result.get("success"):
            results["success"] = False
            results["error"] = f"Brick creation failed: {create_result.get('error')}"
            return results

        component_name = create_result.get("component_name")

        # Step 2: Export
        export_format = params.get("export_format", "stl")
        output_dir = os.environ.get("OUTPUT_DIR", "./output")
        export_path = os.path.join(output_dir, export_format, f"{component_name}.{export_format}")

        export_result = await fusion_client.call_api(f"export_{export_format}", {
            "component_name": component_name,
            "output_path": export_path,
            "resolution": "high"
        })

        results["steps"].append({
            "step": f"export_{export_format}",
            "success": export_result.get("success", False),
            "path": export_result.get("path"),
            "size_kb": export_result.get("size_kb")
        })

        if not export_result.get("success"):
            results["success"] = False
            results["error"] = f"Export failed: {export_result.get('error')}"
            return results

        # Success
        results["success"] = True
        results["brick"] = {
            "name": component_name,
            "type": brick_type,
            "dimensions": create_result.get("dimensions")
        }
        results["export"] = {
            "format": export_format,
            "path": export_result.get("path"),
            "size_kb": export_result.get("size_kb")
        }
        results["duration_sec"] = round(time.time() - results["start_time"], 2)

    except Exception as e:
        logger.error(f"create_and_export error: {e}")
        results["success"] = False
        results["error"] = str(e)

    return results


async def handle_create_and_print(
    fusion_client,
    slicer_client,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete 3D printing workflow.

    Steps:
    1. Create brick in Fusion 360
    2. Export as STL
    3. Slice with printer profile
    4. Return G-code path and print estimates
    """
    results = {
        "workflow": "create_and_print",
        "steps": [],
        "start_time": time.time()
    }

    try:
        # Step 1: Create brick
        brick_type = params.get("brick_type", "standard")
        width = params["width"]
        depth = params["depth"]
        height = params.get("height_bricks", 1.0)
        name = f"{brick_type}_{width}x{depth}"

        create_result = await fusion_client.call_api("create_brick", {
            "studs_x": width,
            "studs_y": depth,
            "height_units": height,
            "name": name
        })

        results["steps"].append({
            "step": "create_brick",
            "success": create_result.get("success", False),
            "component_name": create_result.get("component_name")
        })

        if not create_result.get("success"):
            results["success"] = False
            results["error"] = f"Brick creation failed: {create_result.get('error')}"
            return results

        component_name = create_result.get("component_name")

        # Step 2: Export STL
        output_dir = os.environ.get("OUTPUT_DIR", "./output")
        stl_path = os.path.join(output_dir, "stl", f"{component_name}.stl")

        export_result = await fusion_client.call_api("export_stl", {
            "component_name": component_name,
            "output_path": stl_path,
            "resolution": "high"
        })

        results["steps"].append({
            "step": "export_stl",
            "success": export_result.get("success", False),
            "path": export_result.get("path")
        })

        if not export_result.get("success"):
            results["success"] = False
            results["error"] = f"STL export failed: {export_result.get('error')}"
            return results

        # Step 3: Slice for printing
        printer = params.get("printer", "bambu_p1s")
        quality = params.get("quality", "lego")
        material = params.get("material", "pla")

        slice_result = await slicer_client.slice_lego(
            stl_path=stl_path,
            printer=printer,
            quality=quality,
            material=material
        )

        results["steps"].append({
            "step": "slice",
            "success": slice_result.get("success", False),
            "gcode_path": slice_result.get("path"),
            "estimated_time_min": slice_result.get("estimated_time_min"),
            "filament_used_g": slice_result.get("filament_used_g")
        })

        if not slice_result.get("success"):
            results["success"] = False
            results["error"] = f"Slicing failed: {slice_result.get('error')}"
            return results

        # Success
        results["success"] = True
        results["brick"] = {
            "name": component_name,
            "type": brick_type,
            "dimensions": create_result.get("dimensions")
        }
        results["print"] = {
            "printer": printer,
            "quality": quality,
            "material": material,
            "stl_path": stl_path,
            "gcode_path": slice_result.get("path"),
            "estimated_time_min": slice_result.get("estimated_time_min"),
            "filament_used_g": slice_result.get("filament_used_g")
        }
        results["duration_sec"] = round(time.time() - results["start_time"], 2)

    except Exception as e:
        logger.error(f"create_and_print error: {e}")
        results["success"] = False
        results["error"] = str(e)

    return results


async def handle_create_and_mill(
    fusion_client,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete CNC milling workflow.

    Steps:
    1. Create brick in Fusion 360
    2. Setup CAM with stock and tools
    3. Generate toolpaths
    4. Export G-code for specified machine
    """
    results = {
        "workflow": "create_and_mill",
        "steps": [],
        "start_time": time.time()
    }

    try:
        # Step 1: Create brick
        brick_type = params.get("brick_type", "standard")
        width = params["width"]
        depth = params["depth"]
        height = params.get("height_bricks", 1.0)
        name = f"{brick_type}_{width}x{depth}_mill"

        create_result = await fusion_client.call_api("create_brick", {
            "studs_x": width,
            "studs_y": depth,
            "height_units": height,
            "hollow": False,  # Solid for milling
            "name": name
        })

        results["steps"].append({
            "step": "create_brick",
            "success": create_result.get("success", False),
            "component_name": create_result.get("component_name")
        })

        if not create_result.get("success"):
            results["success"] = False
            results["error"] = f"Brick creation failed: {create_result.get('error')}"
            return results

        component_name = create_result.get("component_name")

        # Step 2: Setup CAM
        machine = params.get("machine", "grbl")
        stock_material = params.get("stock_material", "abs")

        cam_result = await fusion_client.call_api("setup_cam", {
            "component_name": component_name,
            "machine_type": machine,
            "stock_material": stock_material
        })

        results["steps"].append({
            "step": "setup_cam",
            "success": cam_result.get("success", False),
            "operations": cam_result.get("operations", [])
        })

        if not cam_result.get("success"):
            results["success"] = False
            results["error"] = f"CAM setup failed: {cam_result.get('error')}"
            return results

        # Step 3: Generate G-code
        output_dir = os.environ.get("OUTPUT_DIR", "./output")
        gcode_path = os.path.join(output_dir, "gcode", "milling", f"{component_name}.nc")

        gcode_result = await fusion_client.call_api("generate_gcode", {
            "component_name": component_name,
            "output_path": gcode_path,
            "machine_type": machine
        })

        results["steps"].append({
            "step": "generate_gcode",
            "success": gcode_result.get("success", False),
            "path": gcode_result.get("path"),
            "estimated_time_min": gcode_result.get("estimated_time_min")
        })

        if not gcode_result.get("success"):
            results["success"] = False
            results["error"] = f"G-code generation failed: {gcode_result.get('error')}"
            return results

        # Success
        results["success"] = True
        results["brick"] = {
            "name": component_name,
            "type": brick_type,
            "dimensions": create_result.get("dimensions")
        }
        results["milling"] = {
            "machine": machine,
            "stock_material": stock_material,
            "gcode_path": gcode_result.get("path"),
            "operations": cam_result.get("operations", []),
            "estimated_time_min": gcode_result.get("estimated_time_min")
        }
        results["duration_sec"] = round(time.time() - results["start_time"], 2)

    except Exception as e:
        logger.error(f"create_and_mill error: {e}")
        results["success"] = False
        results["error"] = str(e)

    return results


async def handle_create_and_engrave(
    fusion_client,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create brick and generate laser engraving G-code.

    Steps:
    1. Create brick (typically a tile for engraving)
    2. Generate laser engraving toolpath
    3. Export laser G-code
    """
    results = {
        "workflow": "create_and_engrave",
        "steps": [],
        "start_time": time.time()
    }

    try:
        # Step 1: Create brick
        brick_type = params.get("brick_type", "tile")
        width = params["width"]
        depth = params["depth"]
        text = params.get("text")
        svg_path = params.get("svg_path")
        name = f"engrave_{width}x{depth}"

        create_result = await fusion_client.call_api("create_brick", {
            "studs_x": width,
            "studs_y": depth,
            "height_units": 1/3,  # Plate/tile height
            "name": name
        })

        results["steps"].append({
            "step": "create_brick",
            "success": create_result.get("success", False),
            "component_name": create_result.get("component_name")
        })

        if not create_result.get("success"):
            results["success"] = False
            results["error"] = f"Brick creation failed: {create_result.get('error')}"
            return results

        component_name = create_result.get("component_name")

        # Step 2: Generate laser engraving G-code
        engrave_preset = params.get("engrave_preset", "abs_engrave_light")
        output_dir = os.environ.get("OUTPUT_DIR", "./output")
        laser_gcode_path = os.path.join(output_dir, "gcode", "laser", f"{component_name}.nc")

        engrave_params = {
            "component_name": component_name,
            "output_path": laser_gcode_path,
            "preset": engrave_preset
        }

        if text:
            engrave_params["text"] = text
        if svg_path:
            engrave_params["svg_path"] = svg_path

        engrave_result = await fusion_client.call_api("generate_laser_gcode", engrave_params)

        results["steps"].append({
            "step": "generate_laser_gcode",
            "success": engrave_result.get("success", False),
            "path": engrave_result.get("path")
        })

        if not engrave_result.get("success"):
            # Laser engraving may not be implemented yet
            results["success"] = False
            results["error"] = f"Laser G-code generation failed: {engrave_result.get('error', 'Not implemented')}"
            results["note"] = "Laser engraving requires additional CAM setup in Fusion 360"
            return results

        # Success
        results["success"] = True
        results["brick"] = {
            "name": component_name,
            "type": brick_type
        }
        results["engrave"] = {
            "preset": engrave_preset,
            "text": text,
            "svg_path": svg_path,
            "gcode_path": engrave_result.get("path")
        }
        results["duration_sec"] = round(time.time() - results["start_time"], 2)

    except Exception as e:
        logger.error(f"create_and_engrave error: {e}")
        results["success"] = False
        results["error"] = str(e)

    return results


# Handler dispatch
WORKFLOW_HANDLERS = {
    "create_and_export": handle_create_and_export,
    "create_and_print": handle_create_and_print,
    "create_and_mill": handle_create_and_mill,
    "create_and_engrave": handle_create_and_engrave
}
