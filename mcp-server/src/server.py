"""
LEGO MCP Server - Main Entry Point

This is the main MCP server that connects Claude to the LEGO brick manufacturing system.
It provides tools for:
- Creating LEGO bricks (323+ types from catalog + fully custom)
- Exporting to STL, STEP, 3MF, OBJ formats
- Generating 3D print G-code (15+ printer profiles)
- Generating CNC milling toolpaths (8 machine configs)
- Generating preview images

Usage:
    python -m src.server

Claude Desktop config:
    {
        "mcpServers": {
            "lego-mcp": {
                "command": "python",
                "args": ["-m", "src.server"],
                "cwd": "/path/to/lego-mcp-fusion360/mcp-server"
            }
        }
    }
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import MCP SDK
try:
    from mcp.server import Server, InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        CallToolResult,
        ListToolsResult,
        ServerCapabilities,
        ToolsCapability
    )
except ImportError:
    print("MCP SDK not found. Install with: pip install mcp")
    sys.exit(1)

# Import tool modules
from src.tools.brick_tools import (
    BRICK_TOOLS,
    list_brick_catalog,
    get_brick_details,
    create_custom_brick,
    create_standard_brick,
    create_plate_brick,
    create_tile_brick,
    create_slope_brick_helper,
    create_technic_brick_helper,
    get_full_catalog_stats,
)

from src.tools.export_tools import (
    EXPORT_TOOLS,
    export_stl,
    export_step,
    export_3mf,
    export_batch,
    list_export_formats,
)

from src.tools.milling_tools import (
    MILLING_TOOLS,
    generate_brick_operations,
    calculate_speeds_feeds,
    list_machines,
    list_tools as list_milling_tools,
    MaterialType as MillingMaterial,
    LEGO_TOOL_LIBRARY,
)

from src.tools.printing_tools import (
    PRINTING_TOOLS,
    generate_print_config,
    estimate_print_time,
    create_batch_print_job,
    list_printers,
    list_materials,
    get_lego_print_settings,
)

from src.tools.workflow_tools import (
    WORKFLOW_TOOLS,
    WORKFLOW_HANDLERS,
    handle_create_and_export,
    handle_create_and_print,
    handle_create_and_mill,
    handle_create_and_engrave,
)

# Import clients
from src.fusion_client import FusionClient
from src.slicer_client import SlicerClient


# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("lego-mcp")


# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

SERVER_NAME = "lego-mcp"
SERVER_VERSION = "1.0.0"

# Fusion 360 API endpoint (use 127.0.0.1 to avoid IPv6 conflicts)
FUSION_API_URL = os.getenv("FUSION_API_URL", "http://127.0.0.1:8767")

# Slicer service endpoint
SLICER_API_URL = os.getenv("SLICER_API_URL", "http://localhost:8766")

# Output directory
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")


# ============================================================================
# TOOL REGISTRY
# ============================================================================

# Combine all tools from modules
ALL_TOOLS: Dict[str, Dict[str, Any]] = {}
ALL_TOOLS.update(BRICK_TOOLS)
ALL_TOOLS.update(EXPORT_TOOLS)
ALL_TOOLS.update(MILLING_TOOLS)
ALL_TOOLS.update(PRINTING_TOOLS)

# Add workflow tools
for wf_tool in WORKFLOW_TOOLS:
    ALL_TOOLS[wf_tool["name"]] = {
        "description": wf_tool["description"],
        "inputSchema": wf_tool["inputSchema"]
    }

# Add preview tools
PREVIEW_TOOLS = {
    "generate_preview": {
        "description": "Generate a preview image of a LEGO brick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {"type": "string"},
                "output_path": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["front", "top", "isometric", "isometric_bottom"],
                    "default": "isometric",
                },
                "width": {"type": "integer", "default": 800},
                "height": {"type": "integer", "default": 600},
            },
            "required": ["component_name", "output_path"],
        },
    },
    "generate_thumbnail": {
        "description": "Generate a small thumbnail image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {"type": "string"},
                "output_path": {"type": "string"},
                "size": {"type": "integer", "default": 256},
            },
            "required": ["component_name", "output_path"],
        },
    },
}
ALL_TOOLS.update(PREVIEW_TOOLS)

# Add utility tools
UTILITY_TOOLS = {
    "get_server_info": {
        "description": "Get information about the LEGO MCP server.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "health_check": {
        "description": "Check if all services are running.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}
ALL_TOOLS.update(UTILITY_TOOLS)


# ============================================================================
# TOOL HANDLERS
# ============================================================================


async def handle_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    fusion_client: FusionClient,
    slicer_client: SlicerClient,
) -> Dict[str, Any]:
    """
    Handle a tool call and return the result.
    """
    logger.info(f"Handling tool call: {tool_name}")

    try:
        # ============ Brick Tools ============
        if tool_name == "list_brick_catalog":
            return list_brick_catalog(
                category=arguments.get("category"),
                search=arguments.get("search"),
                limit=arguments.get("limit", 50),
            )

        elif tool_name == "get_brick_details":
            return get_brick_details(arguments["brick_name"])

        elif tool_name == "create_custom_brick":
            return create_custom_brick(
                name=arguments["name"],
                width_studs=arguments["width_studs"],
                depth_studs=arguments["depth_studs"],
                height_plates=arguments.get("height_plates", 3),
                features=arguments.get("features"),
            )

        elif tool_name == "create_brick":
            brick_def = create_standard_brick(
                arguments["width"], arguments["depth"], arguments.get("height_bricks", 1)
            )
            result = await fusion_client.create_brick(brick_def["brick"])
            return result

        elif tool_name == "create_plate":
            brick_def = create_plate_brick(arguments["width"], arguments["depth"])
            result = await fusion_client.create_brick(brick_def["brick"])
            return result

        elif tool_name == "create_tile":
            brick_def = create_tile_brick(arguments["width"], arguments["depth"])
            result = await fusion_client.create_brick(brick_def["brick"])
            return result

        elif tool_name == "create_slope":
            brick_def = create_slope_brick_helper(
                arguments["width"],
                arguments["depth"],
                arguments.get("angle", 45),
                arguments.get("direction", "front"),
            )
            result = await fusion_client.create_brick(brick_def["brick"])
            return result

        elif tool_name == "create_technic":
            result = await fusion_client.create_technic_brick(
                studs_x=arguments["width"],
                studs_y=arguments["depth"],
                hole_axis=arguments.get("hole_axis", "x"),
                name=arguments.get("name"),
            )
            return result

        elif tool_name == "create_round":
            result = await fusion_client.create_round_brick(
                diameter_studs=arguments.get("diameter", 2),
                height_units=arguments.get("height_units", 1.0),
                name=arguments.get("name"),
            )
            return result

        elif tool_name == "create_arch":
            result = await fusion_client.create_arch(
                studs_x=arguments.get("width", 4),
                studs_y=arguments.get("depth", 1),
                arch_height=arguments.get("arch_height", 1),
                name=arguments.get("name"),
            )
            return result

        # ============ Export Tools ============
        elif tool_name == "export_stl":
            result = await fusion_client.export_stl(
                arguments["component_name"],
                arguments["output_path"],
                arguments.get("refinement", "medium"),
            )
            return result

        elif tool_name == "export_step":
            result = await fusion_client.export_step(
                arguments["component_name"], arguments["output_path"]
            )
            return result

        elif tool_name == "export_3mf":
            result = await fusion_client.export_3mf(
                arguments["component_name"], arguments["output_path"]
            )
            return result

        elif tool_name == "export_batch":
            return export_batch(
                arguments["components"], arguments["output_dir"], arguments.get("formats", ["stl"])
            )

        elif tool_name == "list_export_formats":
            return list_export_formats()

        # ============ Milling Tools ============
        elif tool_name == "generate_milling_operations":
            material = MillingMaterial.ABS
            for m in MillingMaterial:
                if m.value == arguments.get("material", "abs"):
                    material = m
                    break

            return generate_brick_operations(
                arguments["brick_type"],
                arguments["dimensions"],
                arguments.get("features", {}),
                material,
            )

        elif tool_name == "calculate_cutting_params":
            tool = LEGO_TOOL_LIBRARY.get(arguments["tool_name"])
            if not tool:
                return {"error": f"Unknown tool: {arguments['tool_name']}"}

            material = MillingMaterial.ABS
            for m in MillingMaterial:
                if m.value == arguments.get("material", "abs"):
                    material = m
                    break

            return calculate_speeds_feeds(tool, material)

        elif tool_name == "list_machines":
            return list_machines()

        elif tool_name == "list_tools":
            return list_milling_tools()

        elif tool_name == "generate_gcode":
            # Call Fusion 360 to generate actual G-code
            component_name = arguments["component_name"]
            output_path = arguments.get("output_path", f"/output/gcode/{component_name}.nc")
            machine = arguments.get("machine", "grbl")
            material = arguments.get("material", "abs")

            # First set up CAM
            cam_result = await fusion_client.generate_cam_setup(
                component_name, machine, material
            )
            if not cam_result.get("success", True):
                return cam_result

            # Then generate G-code
            result = await fusion_client.post_process(
                component_name, output_path, machine
            )
            return result

        # ============ Printing Tools ============
        elif tool_name == "slice_for_print":
            # Call slicer service to generate actual G-code
            stl_path = arguments["stl_path"]
            quality = arguments.get("quality", "lego")
            printer = arguments.get("printer", "prusa_mk3s")
            brick_type = arguments.get("brick_type", "standard")
            output_path = arguments.get("output_path")

            if quality == "lego":
                # Use LEGO-optimized slicing
                result = await slicer_client.slice_lego(
                    stl_path=stl_path,
                    printer=printer,
                    brick_type=brick_type,
                    output_path=output_path,
                )
            else:
                # Use standard slicing with specified quality
                material = arguments.get("material", "pla")
                result = await slicer_client.slice(
                    stl_path=stl_path,
                    printer=printer,
                    quality=quality,
                    material=material,
                    output_path=output_path,
                )
            return result

        elif tool_name == "generate_print_config":
            return generate_print_config(
                arguments["stl_path"],
                arguments["printer"],
                arguments["material"],
                arguments.get("quality", "lego"),
                arguments.get("brick_type", "standard"),
            )

        elif tool_name == "estimate_print_time":
            from src.tools.printing_tools import QualityPreset

            quality = QualityPreset.LEGO_OPTIMAL
            for q in QualityPreset:
                if q.value == arguments.get("quality", "lego"):
                    quality = q
                    break
            return estimate_print_time(
                arguments["volume_mm3"], quality, arguments.get("printer", "prusa_mk3s")
            )

        elif tool_name == "create_batch_print":
            return create_batch_print_job(
                arguments["stl_files"],
                arguments["printer"],
                arguments["material"],
                arguments.get("quality", "lego"),
            )

        elif tool_name == "list_printers":
            return list_printers()

        elif tool_name == "list_materials":
            return list_materials()

        elif tool_name == "get_lego_settings":
            from src.tools.printing_tools import QualityPreset

            quality = QualityPreset.LEGO_OPTIMAL
            for q in QualityPreset:
                if q.value == arguments.get("quality", "lego"):
                    quality = q
                    break
            return get_lego_print_settings(arguments.get("brick_type", "standard"), quality)

        # ============ Preview Tools ============
        elif tool_name == "generate_preview":
            result = await fusion_client.generate_preview(
                arguments["component_name"],
                arguments["output_path"],
                arguments.get("view", "isometric"),
                arguments.get("width", 800),
                arguments.get("height", 600),
            )
            return result

        elif tool_name == "generate_thumbnail":
            result = await fusion_client.generate_preview(
                arguments["component_name"],
                arguments["output_path"],
                "isometric",
                arguments.get("size", 256),
                arguments.get("size", 256),
            )
            return result

        # ============ Utility Tools ============
        elif tool_name == "get_server_info":
            stats = get_full_catalog_stats()
            return {
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "catalog": stats["catalog"],
                "features": stats["custom_features"],
                "tools_available": len(ALL_TOOLS),
                "fusion_api": FUSION_API_URL,
                "slicer_api": SLICER_API_URL,
            }

        elif tool_name == "health_check":
            fusion_ok = await fusion_client.health_check()
            slicer_ok = await slicer_client.health_check()

            return {
                "status": "healthy" if fusion_ok and slicer_ok else "degraded",
                "services": {
                    "fusion360": "up" if fusion_ok else "down",
                    "slicer": "up" if slicer_ok else "down",
                },
            }

        # ============ Workflow Tools ============
        elif tool_name == "create_and_export":
            return await handle_create_and_export(fusion_client, arguments)

        elif tool_name == "create_and_print":
            return await handle_create_and_print(fusion_client, slicer_client, arguments)

        elif tool_name == "create_and_mill":
            return await handle_create_and_mill(fusion_client, arguments)

        elif tool_name == "create_and_engrave":
            return await handle_create_and_engrave(fusion_client, arguments)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Error handling tool {tool_name}: {e}")
        return {"error": str(e)}


# ============================================================================
# MCP SERVER
# ============================================================================


async def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting {SERVER_NAME} v{SERVER_VERSION}")

    # Create clients
    fusion_client = FusionClient(FUSION_API_URL)
    slicer_client = SlicerClient(SLICER_API_URL)

    # Create MCP server
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> ListToolsResult:
        """List all available tools."""
        tools = []
        for name, spec in ALL_TOOLS.items():
            tools.append(
                Tool(
                    name=name,
                    description=spec.get("description", ""),
                    inputSchema=spec.get("inputSchema", {"type": "object", "properties": {}}),
                )
            )
        return ListToolsResult(tools=tools)

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle a tool call."""
        result = await handle_tool_call(name, arguments, fusion_client, slicer_client)

        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    # Run server
    logger.info("Server ready, waiting for connections...")

    init_options = InitializationOptions(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        capabilities=ServerCapabilities(
            tools=ToolsCapability(listChanged=True)
        )
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


def run():
    """Entry point for running the server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
