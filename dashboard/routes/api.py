"""
API Routes

REST API endpoints for AJAX calls.
LEGO MCP v5.0 World-Class Manufacturing Platform
"""

from flask import Blueprint, request, jsonify
from services.catalog_service import CatalogService
from services.builder_service import BuilderService
from services.file_service import FileService
from services.status_service import StatusService
from services.mcp_bridge import MCPBridge

api_bp = Blueprint("api", __name__)


# =============================================================================
# HEALTH CHECK API
# =============================================================================


@api_bp.route("/health")
def api_health():
    """
    API health check endpoint.

    Returns the health status of the dashboard and connected services.
    """
    status = StatusService.get_all_status(use_cache=True)

    # Determine overall health
    fusion360_ok = status.get("fusion360", {}).get("status") == "connected"
    slicer_ok = status.get("slicer", {}).get("status") == "connected"

    overall_status = "ok" if (fusion360_ok or slicer_ok) else "degraded"

    return jsonify({
        "status": overall_status,
        "version": "5.0.0",
        "platform": "LegoMCP World-Class CPPS",
        "services": {
            "fusion360": "connected" if fusion360_ok else "disconnected",
            "slicer": "connected" if slicer_ok else "disconnected",
        },
        "modules": {
            "manufacturing": True,
            "quality": True,
            "erp": True,
            "mrp": True,
            "digital_twin": True,
        }
    })


# =============================================================================
# CATALOG API
# =============================================================================


@api_bp.route("/catalog")
def api_catalog():
    """Get brick catalog."""
    category = request.args.get("category")
    search = request.args.get("q")
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    result = CatalogService.get_all_bricks(
        category=category,
        search_query=search,
        sort_by=sort,
        sort_order=order,
        limit=limit,
        offset=offset,
    )

    return jsonify(result)


@api_bp.route("/catalog/<brick_id>")
def api_catalog_brick(brick_id):
    """Get single brick."""
    brick = CatalogService.get_brick(brick_id)

    if not brick:
        return jsonify({"error": "Brick not found"}), 404

    return jsonify(brick)


@api_bp.route("/catalog/search")
def api_catalog_search():
    """Search bricks."""
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 20))

    results = CatalogService.search_bricks(query, limit)
    return jsonify(results)


@api_bp.route("/catalog/categories")
def api_catalog_categories():
    """Get categories."""
    categories = CatalogService.get_categories()
    return jsonify(categories)


@api_bp.route("/catalog/stats")
def api_catalog_stats():
    """Get catalog stats."""
    stats = CatalogService.get_stats()
    return jsonify(stats)


# =============================================================================
# BRICK CREATION API
# =============================================================================


@api_bp.route("/brick/validate", methods=["POST"])
def api_brick_validate():
    """Validate brick parameters."""
    data = request.get_json()
    result = BuilderService.validate_params(
        data.get("width_studs", 2),
        data.get("depth_studs", 4),
        data.get("height_plates", 3),
        data.get("brick_type", "standard"),
        data.get("features"),
    )
    return jsonify(result)


@api_bp.route("/brick/dimensions", methods=["POST"])
def api_brick_dimensions():
    """Compute brick dimensions."""
    data = request.get_json()
    dims = BuilderService.compute_dimensions(
        data.get("width_studs", 2), data.get("depth_studs", 4), data.get("height_plates", 3)
    )
    return jsonify(dims)


@api_bp.route("/brick/create", methods=["POST"])
def api_brick_create():
    """Create a brick."""
    data = request.get_json()

    definition = BuilderService.build_brick_definition(
        name=data.get("name", "custom_brick"),
        width_studs=data.get("width_studs", 2),
        depth_studs=data.get("depth_studs", 4),
        height_plates=data.get("height_plates", 3),
        brick_type=data.get("brick_type", "standard"),
        hollow=data.get("hollow", True),
        studs=data.get("studs", True),
        tubes=data.get("tubes", True),
        slope_angle=data.get("slope_angle"),
        slope_direction=data.get("slope_direction", "front"),
        technic_holes=data.get("technic_holes", False),
        chamfers=data.get("chamfers", False),
    )

    result = MCPBridge.execute_tool("create_custom_brick", definition)
    return jsonify(result)


@api_bp.route("/brick/presets")
def api_brick_presets():
    """Get brick presets."""
    presets = BuilderService.get_presets()
    return jsonify(presets)


# =============================================================================
# FILES API
# =============================================================================


@api_bp.route("/files")
@api_bp.route("/files/<path:directory>")
def api_files(directory=""):
    """List files."""
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")
    file_type = request.args.get("type")

    result = FileService.list_files(
        directory=directory, file_type=file_type, sort_by=sort, sort_order=order
    )
    return jsonify(result)


@api_bp.route("/files/info/<path:file_path>")
def api_file_info(file_path):
    """Get file info."""
    info = FileService.get_file(file_path)
    if not info:
        return jsonify({"error": "File not found"}), 404
    return jsonify(info)


@api_bp.route("/files/delete", methods=["POST"])
def api_file_delete():
    """Delete file."""
    data = request.get_json()
    result = FileService.delete_file(data.get("path", ""))
    return jsonify(result)


@api_bp.route("/files/stats")
def api_file_stats():
    """Get file stats."""
    stats = FileService.get_storage_stats()
    return jsonify(stats)


# =============================================================================
# STATUS API
# =============================================================================


@api_bp.route("/status")
def api_status():
    """Get system status."""
    status = StatusService.get_all_status(use_cache=False)
    return jsonify(status)


@api_bp.route("/status/<service>")
def api_status_service(service):
    """Get service status."""
    result = StatusService.get_service_status(service)
    return jsonify({"service": service, **result})


@api_bp.route("/status/circuits")
def api_circuits():
    """Get circuit breakers."""
    circuits = StatusService.get_circuit_breakers()
    return jsonify(circuits)


@api_bp.route("/status/errors")
def api_errors():
    """Get error log."""
    limit = int(request.args.get("limit", 50))
    errors = StatusService.get_error_log(limit)
    return jsonify(errors)


# =============================================================================
# HISTORY API
# =============================================================================


@api_bp.route("/history")
def api_history():
    """Get operation history."""
    limit = int(request.args.get("limit", 50))
    result = MCPBridge.execute_tool("get_history", {"limit": limit})
    return jsonify(result)


@api_bp.route("/history/undo", methods=["POST"])
def api_undo():
    """Undo operation."""
    result = MCPBridge.execute_tool("undo", {})
    return jsonify(result)


@api_bp.route("/history/redo", methods=["POST"])
def api_redo():
    """Redo operation."""
    result = MCPBridge.execute_tool("redo", {})
    return jsonify(result)


@api_bp.route("/history/stats")
def api_history_stats():
    """Get history stats."""
    result = MCPBridge.execute_tool("get_statistics", {})
    return jsonify(result)


# =============================================================================
# TOOLS API
# =============================================================================


@api_bp.route("/tools")
def api_tools():
    """List tools."""
    tools = MCPBridge.get_tools()
    categories = MCPBridge.get_tool_categories()
    return jsonify({"tools": list(tools.keys()), "categories": categories, "total": len(tools)})


@api_bp.route("/tools/<tool_name>")
def api_tool_info(tool_name):
    """Get tool info."""
    tool = MCPBridge.get_tool(tool_name)
    if not tool:
        return jsonify({"error": "Tool not found"}), 404

    return jsonify(
        {
            "name": tool_name,
            "description": tool.get("description", ""),
            "schema": tool.get("inputSchema", {}),
            "example": MCPBridge.get_tool_examples(tool_name),
        }
    )


@api_bp.route("/tools/execute", methods=["POST"])
def api_tool_execute():
    """Execute tool."""
    data = request.get_json()
    tool = data.get("tool")
    params = data.get("params", {})

    if not tool:
        return jsonify({"success": False, "error": "No tool specified"})

    result = MCPBridge.execute_tool(tool, params)
    return jsonify(result)


# =============================================================================
# EXPORT API
# =============================================================================


@api_bp.route("/export/stl", methods=["POST"])
def api_export_stl():
    """Export to STL."""
    data = request.get_json()
    result = MCPBridge.execute_tool(
        "export_stl",
        {
            "component_name": data.get("component"),
            "output_path": data.get("output_path"),
            "refinement": data.get("refinement", "high"),
        },
    )
    return jsonify(result)


@api_bp.route("/export/formats")
def api_export_formats():
    """Get export formats."""
    result = MCPBridge.execute_tool("list_export_formats", {})
    return jsonify(result)


# =============================================================================
# PRINTING API
# =============================================================================


@api_bp.route("/print/config", methods=["POST"])
def api_print_config():
    """Generate print config."""
    data = request.get_json()
    result = MCPBridge.execute_tool(
        "generate_print_config",
        {
            "stl_path": data.get("stl_path"),
            "printer": data.get("printer", "prusa_mk3s"),
            "material": data.get("material", "pla_generic"),
            "quality": data.get("quality", "lego"),
        },
    )
    return jsonify(result)


@api_bp.route("/print/printers")
def api_printers():
    """List printers."""
    result = MCPBridge.execute_tool("list_printers", {})
    return jsonify(result)


@api_bp.route("/print/materials")
def api_materials():
    """List materials."""
    result = MCPBridge.execute_tool("list_materials", {})
    return jsonify(result)


# =============================================================================
# BATCH API
# =============================================================================


@api_bp.route("/batch/sets")
def api_batch_sets():
    """Get available brick sets."""
    sets = ["basic", "plates", "slopes", "technic", "tiles", "starter", "all_1x"]
    return jsonify({"sets": sets})


@api_bp.route("/batch/generate", methods=["POST"])
def api_batch_generate():
    """Generate brick set."""
    data = request.get_json()
    set_type = data.get("set_type", "basic")
    result = MCPBridge.execute_tool("generate_brick_set", {"set_type": set_type})
    return jsonify(result)
