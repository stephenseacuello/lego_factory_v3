"""
MCP Bridge Service

Bridge between Flask dashboard and MCP tools.
Allows direct execution of MCP tools from the web interface.
Now with actual HTTP calls to Fusion 360 add-in for brick creation.
"""

import asyncio
import json
import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Optional requests import for HTTP calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=4)

# Service URLs from environment variables with correct defaults
# Port 8767 = Fusion 360 add-in HTTP server (matches LegoMCP.py)
# Port 8766 = Slicer service (matches docker-compose.yml)
FUSION_API_URL = os.environ.get("FUSION_API_URL", "http://127.0.0.1:8767")
SLICER_API_URL = os.environ.get("SLICER_API_URL", "http://localhost:8766")


def _call_fusion_api(command: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    """Make HTTP call to Fusion 360 add-in API."""
    if not REQUESTS_AVAILABLE:
        return {"success": False, "error": "requests library not available"}

    try:
        response = requests.post(
            FUSION_API_URL,
            json={"command": command, "params": params},
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to Fusion 360. Is the add-in running?"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"Request timed out after {timeout}s"}
    except Exception as e:
        logger.error(f"Fusion API error: {e}")
        return {"success": False, "error": str(e)}


def _call_slicer_api(endpoint: str, method: str = "GET", data: Dict[str, Any] = None, timeout: float = 300.0) -> Dict[str, Any]:
    """Make HTTP call to slicer service API."""
    if not REQUESTS_AVAILABLE:
        return {"success": False, "error": "requests library not available"}

    try:
        url = f"{SLICER_API_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        else:
            response = requests.post(url, json=data, timeout=timeout)

        if response.status_code == 200:
            result = response.json()
            result["success"] = True
            return result
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to slicer service. Is it running?"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"Slicing timed out after {timeout}s"}
    except Exception as e:
        logger.error(f"Slicer API error: {e}")
        return {"success": False, "error": str(e)}


class MCPBridge:
    """Bridge to execute MCP tools from the dashboard."""

    # Tool registry - loaded from MCP server
    _tools: Dict[str, Dict[str, Any]] = {}
    _tools_loaded: bool = False

    @classmethod
    def load_tools(cls):
        """Load tool definitions from MCP server."""
        if cls._tools_loaded:
            return

        try:
            # Import tool definitions
            from tools.brick_tools import BRICK_TOOLS
            from tools.export_tools import EXPORT_TOOLS
            from tools.milling_tools import MILLING_TOOLS
            from tools.printing_tools import PRINTING_TOOLS

            cls._tools.update(BRICK_TOOLS)
            cls._tools.update(EXPORT_TOOLS)
            cls._tools.update(MILLING_TOOLS)
            cls._tools.update(PRINTING_TOOLS)

            # Try to load additional tools
            try:
                from history_manager import HISTORY_TOOLS

                cls._tools.update(HISTORY_TOOLS)
            except ImportError:
                pass

            try:
                from batch_operations import BATCH_TOOLS

                cls._tools.update(BATCH_TOOLS)
            except ImportError:
                pass

            cls._tools_loaded = True

        except ImportError as e:
            print(f"Warning: Could not load MCP tools: {e}")

    @classmethod
    def get_tools(cls) -> Dict[str, Dict[str, Any]]:
        """Get all available tools."""
        cls.load_tools()
        return cls._tools

    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool definition."""
        cls.load_tools()
        return cls._tools.get(tool_name)

    @classmethod
    def get_tool_categories(cls) -> Dict[str, List[str]]:
        """Get tools organized by category."""
        cls.load_tools()

        categories = {
            "brick": [],
            "export": [],
            "milling": [],
            "printing": [],
            "history": [],
            "batch": [],
            "other": [],
        }

        for name in cls._tools:
            if name.startswith(("create_", "list_brick", "get_brick")):
                categories["brick"].append(name)
            elif name.startswith("export_") or "format" in name:
                categories["export"].append(name)
            elif "mill" in name or "machine" in name or "cutting" in name:
                categories["milling"].append(name)
            elif "print" in name or "slice" in name or "printer" in name or "material" in name:
                categories["printing"].append(name)
            elif name in ("undo", "redo", "get_history", "get_statistics"):
                categories["history"].append(name)
            elif name.startswith("batch_") or "set" in name:
                categories["batch"].append(name)
            else:
                categories["other"].append(name)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    # Known tools that can be executed directly without tool definitions
    DIRECT_EXECUTE_TOOLS = {
        "create_brick", "create_standard_brick", "create_plate", "create_plate_brick",
        "create_tile", "create_tile_brick", "create_slope", "create_slope_brick",
        "create_technic", "create_technic_brick", "create_round", "create_round_brick",
        "create_arch", "create_arch_brick", "create_custom_brick",
        "export_stl", "export_step", "export_3mf",
        "list_brick_catalog", "get_brick_details",
        "list_printers", "list_materials", "list_machines", "list_tools",
        # Workflow tools - end-to-end automation
        "create_and_export", "create_and_print", "create_and_mill", "create_and_engrave",
    }

    @classmethod
    def execute_tool(cls, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool.

        Returns:
            Result dict with success status and data
        """
        cls.load_tools()

        # Allow direct execution of known tools even if tool definitions fail to load
        if tool_name not in cls._tools and tool_name not in cls.DIRECT_EXECUTE_TOOLS:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "tool": tool_name}

        start_time = time.time()

        try:
            result = cls._execute_tool_internal(tool_name, params)
            duration = (time.time() - start_time) * 1000

            return {
                "success": True,
                "tool": tool_name,
                "params": params,
                "result": result,
                "duration_ms": round(duration, 1),
                "executed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return {
                "success": False,
                "tool": tool_name,
                "params": params,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration, 1),
                "executed_at": datetime.now().isoformat(),
            }

    @classmethod
    def _execute_tool_internal(cls, tool_name: str, params: Dict[str, Any]) -> Any:
        """Internal tool execution."""

        # Brick tools - LOCAL (catalog lookup)
        if tool_name == "list_brick_catalog":
            from tools.brick_tools import list_brick_catalog

            return list_brick_catalog(**params)

        elif tool_name == "get_brick_details":
            from tools.brick_tools import get_brick_details

            return get_brick_details(params.get("brick_name") or params.get("brick_id"))

        # Brick creation tools - CALL FUSION 360 ADD-IN
        # Support both "create_brick" and "create_standard_brick" names
        elif tool_name in ("create_standard_brick", "create_brick"):
            # Call Fusion 360 to actually create the brick
            return _call_fusion_api("create_brick", {
                "studs_x": params.get("width", params.get("studs_x", 2)),
                "studs_y": params.get("depth", params.get("studs_y", 4)),
                "height_units": params.get("height_bricks", params.get("height_units", 1)),
                "hollow": params.get("hollow", True),
                "name": params.get("name"),
            })

        elif tool_name in ("create_plate_brick", "create_plate"):
            # Call Fusion 360 to create plate
            return _call_fusion_api("create_plate", {
                "studs_x": params.get("width", params.get("studs_x", 2)),
                "studs_y": params.get("depth", params.get("studs_y", 4)),
                "name": params.get("name"),
            })

        elif tool_name in ("create_tile_brick", "create_tile"):
            # Call Fusion 360 to create tile
            return _call_fusion_api("create_tile", {
                "studs_x": params.get("width", params.get("studs_x", 2)),
                "studs_y": params.get("depth", params.get("studs_y", 2)),
                "name": params.get("name"),
            })

        elif tool_name in ("create_slope_brick", "create_slope"):
            # Call Fusion 360 to create slope
            return _call_fusion_api("create_slope", {
                "studs_x": params.get("width", params.get("studs_x", 2)),
                "studs_y": params.get("depth", params.get("studs_y", 3)),
                "slope_angle": params.get("angle", params.get("slope_angle", 45)),
                "slope_direction": params.get("direction", params.get("slope_direction", "front")),
                "name": params.get("name"),
            })

        elif tool_name in ("create_technic_brick", "create_technic"):
            # Call Fusion 360 to create technic brick with pin holes
            return _call_fusion_api("create_technic", {
                "studs_x": params.get("width", params.get("studs_x", 1)),
                "studs_y": params.get("depth", params.get("studs_y", 6)),
                "hole_axis": params.get("hole_axis", params.get("hole_type", "x")),
                "name": params.get("name"),
            })

        elif tool_name in ("create_round_brick", "create_round"):
            # Call Fusion 360 to create cylindrical round brick
            return _call_fusion_api("create_round", {
                "diameter_studs": params.get("diameter", params.get("width", 2)),
                "height_units": params.get("height_bricks", params.get("height_units", 1.0)),
                "name": params.get("name"),
            })

        elif tool_name in ("create_arch_brick", "create_arch"):
            # Call Fusion 360 to create arch brick
            return _call_fusion_api("create_arch", {
                "studs_x": params.get("width", params.get("studs_x", 4)),
                "studs_y": params.get("depth", params.get("studs_y", 1)),
                "arch_height": params.get("arch_height", 1),
                "name": params.get("name"),
            })

        elif tool_name == "create_custom_brick":
            # Custom brick - call Fusion 360 with full parameters based on brick type
            brick_type = params.get("brick_type", "standard")
            studs_x = params.get("width_studs", 2)
            studs_y = params.get("depth_studs", 4)
            height_plates = params.get("height_plates", 3)
            hollow = params.get("hollow", True)
            name = params.get("name")
            color = params.get("color")

            # Route to appropriate command based on brick type
            if brick_type == "tile":
                return _call_fusion_api("create_tile", {
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "name": name,
                    "color": color,
                })
            elif brick_type.startswith("slope"):
                return _call_fusion_api("create_slope", {
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "slope_angle": params.get("slope_angle", 45),
                    "slope_direction": params.get("slope_direction", "front"),
                    "name": name,
                    "color": color,
                })
            elif brick_type == "technic":
                return _call_fusion_api("create_technic", {
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "hole_axis": params.get("technic_axis", "x"),
                    "name": name,
                    "color": color,
                })
            elif brick_type == "plate":
                return _call_fusion_api("create_plate", {
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "name": name,
                    "color": color,
                })
            else:
                # Standard brick or double height
                return _call_fusion_api("create_brick", {
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "height_units": height_plates / 3.0,  # Convert plates to brick units
                    "hollow": hollow,
                    "name": name,
                    "color": color,
                })

        # Export tools - CALL FUSION 360 ADD-IN
        elif tool_name == "export_stl":
            return _call_fusion_api("export_stl", {
                "component_name": params.get("component_name"),
                "output_path": params.get("output_path"),
                "resolution": params.get("refinement", "medium"),
            }, timeout=60.0)

        elif tool_name == "export_step":
            return _call_fusion_api("export_step", {
                "component_name": params.get("component_name"),
                "output_path": params.get("output_path"),
            }, timeout=60.0)

        elif tool_name == "export_3mf":
            return _call_fusion_api("export_3mf", {
                "component_name": params.get("component_name"),
                "output_path": params.get("output_path"),
            }, timeout=60.0)

        elif tool_name == "list_export_formats":
            from tools.export_tools import list_export_formats

            return list_export_formats()

        # Slicing tools - CALL SLICER SERVICE
        elif tool_name == "slice_for_print":
            quality = params.get("quality", "lego")
            if quality == "lego":
                return _call_slicer_api("/slice/lego", "POST", {
                    "stl_path": params.get("stl_path"),
                    "printer": params.get("printer", "prusa_mk3s"),
                    "brick_type": params.get("brick_type", "standard"),
                    "output_path": params.get("output_path"),
                })
            else:
                return _call_slicer_api("/slice", "POST", {
                    "stl_path": params.get("stl_path"),
                    "printer": params.get("printer", "prusa_mk3s"),
                    "quality": quality,
                    "material": params.get("material", "pla"),
                    "output_path": params.get("output_path"),
                })

        # Printing tools
        elif tool_name == "generate_print_config":
            from tools.printing_tools import generate_print_config

            return generate_print_config(
                params.get("stl_path"),
                params.get("printer", "prusa_mk3s"),
                params.get("material", "pla_generic"),
                params.get("quality", "lego"),
            )

        elif tool_name == "list_printers":
            from tools.printing_tools import list_printers

            return list_printers()

        elif tool_name == "list_materials":
            from tools.printing_tools import list_materials

            return list_materials()

        elif tool_name == "get_lego_settings":
            from tools.printing_tools import get_lego_print_settings

            return get_lego_print_settings(params.get("brick_type", "standard"))

        # Milling tools
        elif tool_name == "generate_milling_operations":
            from tools.milling_tools import generate_brick_operations

            return generate_brick_operations(
                params.get("brick_type", "standard"),
                params.get("dimensions", {}),
                params.get("features", {}),
                params.get("material", "abs"),
            )

        elif tool_name == "generate_gcode":
            # First set up CAM in Fusion 360
            component_name = params.get("component_name")
            machine = params.get("machine", "grbl")
            material = params.get("material", "abs")
            output_path = params.get("output_path", f"/output/gcode/{component_name}.nc")

            cam_result = _call_fusion_api("setup_cam", {
                "component_name": component_name,
                "machine": machine,
                "material": material,
            }, timeout=60.0)

            if not cam_result.get("success", True):
                return cam_result

            # Then generate G-code
            return _call_fusion_api("generate_gcode", {
                "component_name": component_name,
                "output_path": output_path,
                "machine": machine,
            }, timeout=120.0)

        elif tool_name == "list_machines":
            from tools.milling_tools import list_machines

            return list_machines()

        elif tool_name == "list_tools":
            from tools.milling_tools import list_tools

            return list_tools()

        # History tools
        elif tool_name == "undo":
            from history_manager import get_history_manager

            return get_history_manager().undo()

        elif tool_name == "redo":
            from history_manager import get_history_manager

            return get_history_manager().redo()

        elif tool_name == "get_history":
            from history_manager import get_history_manager

            return get_history_manager().get_history(limit=params.get("limit", 50))

        elif tool_name == "get_statistics":
            from history_manager import get_history_manager

            return get_history_manager().get_statistics()

        # Batch tools
        elif tool_name == "generate_brick_set":
            from batch_operations import generate_brick_set

            return generate_brick_set(params.get("set_type", "basic"))

        # =================================================================
        # WORKFLOW TOOLS - End-to-end automation
        # =================================================================

        elif tool_name == "create_and_export":
            # Workflow: Create brick -> Export to STL/3MF/STEP
            brick_type = params.get("brick_type", "standard")
            width = params.get("width", 2)
            depth = params.get("depth", 4)
            height = params.get("height_bricks", 1.0)
            export_format = params.get("export_format", "stl")
            name = params.get("name") or f"{brick_type}_{width}x{depth}"

            # Step 1: Create brick
            create_result = _call_fusion_api("create_brick", {
                "studs_x": width,
                "studs_y": depth,
                "height_units": height,
                "name": name
            })

            if not create_result.get("success"):
                return {"success": False, "error": f"Brick creation failed: {create_result.get('error')}"}

            component_name = create_result.get("component_name", name)

            # Step 2: Export
            export_cmd = f"export_{export_format}"
            export_result = _call_fusion_api(export_cmd, {
                "component_name": component_name,
                "resolution": "high"
            }, timeout=60.0)

            return {
                "success": export_result.get("success", False),
                "workflow": "create_and_export",
                "brick": {"name": component_name, "type": brick_type, "width": width, "depth": depth},
                "export": {"format": export_format, "path": export_result.get("path")},
                "error": export_result.get("error") if not export_result.get("success") else None
            }

        elif tool_name == "create_and_print":
            # Workflow: Create brick -> Export STL -> Slice for 3D printing
            brick_type = params.get("brick_type", "standard")
            width = params.get("width", 2)
            depth = params.get("depth", 4)
            height = params.get("height_bricks", 1.0)
            printer = params.get("printer", "bambu_p1s")
            quality = params.get("quality", "lego")
            material = params.get("material", "pla")
            name = f"{brick_type}_{width}x{depth}"

            # Step 1: Create brick
            create_result = _call_fusion_api("create_brick", {
                "studs_x": width,
                "studs_y": depth,
                "height_units": height,
                "name": name
            })

            if not create_result.get("success"):
                return {"success": False, "error": f"Brick creation failed: {create_result.get('error')}"}

            component_name = create_result.get("component_name", name)

            # Step 2: Export STL
            export_result = _call_fusion_api("export_stl", {
                "component_name": component_name,
                "resolution": "high"
            }, timeout=60.0)

            if not export_result.get("success"):
                return {"success": False, "error": f"STL export failed: {export_result.get('error')}"}

            stl_path = export_result.get("path")

            # Step 3: Slice for printing
            slice_result = _call_slicer_api("/slice/lego", "POST", {
                "stl_path": stl_path,
                "printer": printer,
                "brick_type": brick_type
            })

            return {
                "success": slice_result.get("success", False),
                "workflow": "create_and_print",
                "brick": {"name": component_name, "type": brick_type, "width": width, "depth": depth},
                "stl_path": stl_path,
                "print": {
                    "printer": printer,
                    "quality": quality,
                    "material": material,
                    "gcode_path": slice_result.get("path"),
                    "estimated_time_min": slice_result.get("estimated_time_min"),
                    "filament_grams": slice_result.get("filament_grams")
                },
                "error": slice_result.get("error") if not slice_result.get("success") else None
            }

        elif tool_name == "create_and_mill":
            # Workflow: Create brick -> Setup CAM -> Generate milling G-code
            brick_type = params.get("brick_type", "standard")
            width = params.get("width", 2)
            depth = params.get("depth", 4)
            height = params.get("height_bricks", 1.0)
            machine = params.get("machine", "grbl")
            stock_material = params.get("stock_material", "abs")
            name = f"{brick_type}_{width}x{depth}_mill"

            # Step 1: Create brick (solid for milling)
            create_result = _call_fusion_api("create_brick", {
                "studs_x": width,
                "studs_y": depth,
                "height_units": height,
                "hollow": False,
                "name": name
            })

            if not create_result.get("success"):
                return {"success": False, "error": f"Brick creation failed: {create_result.get('error')}"}

            component_name = create_result.get("component_name", name)

            # Step 2: Setup CAM
            cam_result = _call_fusion_api("setup_cam", {
                "component_name": component_name,
                "machine": machine,
                "material": stock_material
            }, timeout=60.0)

            if not cam_result.get("success", True):
                return {"success": False, "error": f"CAM setup failed: {cam_result.get('error')}"}

            # Step 3: Generate G-code
            gcode_result = _call_fusion_api("generate_gcode", {
                "component_name": component_name,
                "machine": machine
            }, timeout=120.0)

            return {
                "success": gcode_result.get("success", False),
                "workflow": "create_and_mill",
                "brick": {"name": component_name, "type": brick_type, "width": width, "depth": depth},
                "milling": {
                    "machine": machine,
                    "stock_material": stock_material,
                    "gcode_path": gcode_result.get("path"),
                    "operations": cam_result.get("operations", []),
                    "estimated_time_min": gcode_result.get("estimated_time_min")
                },
                "error": gcode_result.get("error") if not gcode_result.get("success") else None
            }

        elif tool_name == "create_and_engrave":
            # Workflow: Create brick -> Generate laser engraving G-code
            brick_type = params.get("brick_type", "tile")
            width = params.get("width", 2)
            depth = params.get("depth", 2)
            text = params.get("text")
            svg_path = params.get("svg_path")
            engrave_preset = params.get("engrave_preset", "abs_engrave_light")
            name = f"engrave_{width}x{depth}"

            # Step 1: Create tile/brick
            create_result = _call_fusion_api("create_tile", {
                "studs_x": width,
                "studs_y": depth,
                "name": name
            })

            if not create_result.get("success"):
                return {"success": False, "error": f"Brick creation failed: {create_result.get('error')}"}

            component_name = create_result.get("component_name", name)

            # Step 2: Generate laser G-code
            engrave_params = {
                "component_name": component_name,
                "preset": engrave_preset
            }
            if text:
                engrave_params["text"] = text
            if svg_path:
                engrave_params["svg_path"] = svg_path

            engrave_result = _call_fusion_api("generate_laser_gcode", engrave_params, timeout=60.0)

            return {
                "success": engrave_result.get("success", False),
                "workflow": "create_and_engrave",
                "brick": {"name": component_name, "type": brick_type, "width": width, "depth": depth},
                "engrave": {
                    "preset": engrave_preset,
                    "text": text,
                    "svg_path": svg_path,
                    "gcode_path": engrave_result.get("path")
                },
                "error": engrave_result.get("error") if not engrave_result.get("success") else None
            }

        else:
            raise ValueError(f"Tool not implemented: {tool_name}")

    @classmethod
    def validate_params(cls, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters for a tool."""
        cls.load_tools()

        tool = cls._tools.get(tool_name)
        if not tool:
            return {"valid": False, "errors": [f"Unknown tool: {tool_name}"]}

        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        errors = []

        # Check required params
        for req in required:
            if req not in params:
                errors.append(f"Missing required parameter: {req}")

        # Check param types
        for param_name, param_value in params.items():
            if param_name in properties:
                prop = properties[param_name]
                expected_type = prop.get("type")

                if expected_type == "integer" and not isinstance(param_value, int):
                    errors.append(f"{param_name} should be an integer")
                elif expected_type == "string" and not isinstance(param_value, str):
                    errors.append(f"{param_name} should be a string")
                elif expected_type == "boolean" and not isinstance(param_value, bool):
                    errors.append(f"{param_name} should be a boolean")
                elif expected_type == "array" and not isinstance(param_value, list):
                    errors.append(f"{param_name} should be an array")

        return {"valid": len(errors) == 0, "errors": errors}

    @classmethod
    def get_tool_examples(cls, tool_name: str) -> Dict[str, Any]:
        """Get example parameters for a tool."""
        examples = {
            "create_standard_brick": {"width": 2, "depth": 4, "height_bricks": 1},
            "create_plate_brick": {"width": 4, "depth": 4},
            "create_tile_brick": {"width": 2, "depth": 2},
            "create_slope_brick": {"width": 2, "depth": 3, "angle": 45, "direction": "front"},
            "create_technic_brick": {"width": 1, "depth": 6, "hole_type": "pin"},
            "list_brick_catalog": {"category": "brick", "limit": 10},
            "get_brick_details": {"brick_name": "brick_2x4"},
            "export_stl": {
                "component_name": "Brick_2x4",
                "output_path": "/output/stl/brick.stl",
                "refinement": "high",
            },
            "generate_print_config": {
                "stl_path": "/output/stl/brick.stl",
                "printer": "prusa_mk3s",
                "material": "pla_generic",
                "quality": "lego",
            },
            "generate_brick_set": {"set_type": "basic"},
            # Workflow examples
            "create_and_export": {
                "brick_type": "standard",
                "width": 2,
                "depth": 4,
                "export_format": "stl"
            },
            "create_and_print": {
                "brick_type": "standard",
                "width": 2,
                "depth": 4,
                "printer": "bambu_p1s",
                "quality": "lego",
                "material": "pla"
            },
            "create_and_mill": {
                "brick_type": "standard",
                "width": 2,
                "depth": 4,
                "machine": "grbl",
                "stock_material": "abs"
            },
            "create_and_engrave": {
                "brick_type": "tile",
                "width": 4,
                "depth": 4,
                "text": "LEGO",
                "engrave_preset": "abs_engrave_light"
            },
        }

        return examples.get(tool_name, {})


# Singleton
mcp_bridge = MCPBridge()
