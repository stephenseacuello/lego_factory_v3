"""
Builder Routes

Custom brick builder interface.
"""

from flask import Blueprint, render_template, request, jsonify
from services.builder_service import BuilderService
from services.mcp_bridge import MCPBridge

builder_bp = Blueprint("builder", __name__)


@builder_bp.route("/")
def builder():
    """Brick builder page."""
    # Get builder options
    brick_types = BuilderService.get_brick_types()
    slope_angles = BuilderService.get_slope_angles()
    slope_directions = BuilderService.get_slope_directions()
    presets = BuilderService.get_presets()
    lego_specs = BuilderService.get_lego_specs()

    # Load preset if specified
    preset_id = request.args.get("preset")
    preset_params = None
    if preset_id:
        for preset in presets:
            if preset["id"] == preset_id:
                preset_params = preset["params"]
                break

    # Load from catalog brick if specified
    catalog_brick = request.args.get("from_catalog")
    if catalog_brick:
        from services.catalog_service import CatalogService

        brick = CatalogService.get_brick(catalog_brick)
        if brick:
            preset_params = {
                "width_studs": brick["studs_x"],
                "depth_studs": brick["studs_y"],
                "height_plates": brick["height_plates"],
                "brick_type": "standard",
            }

    return render_template(
        "pages/builder.html",
        brick_types=brick_types,
        slope_angles=slope_angles,
        slope_directions=slope_directions,
        presets=presets,
        preset_params=preset_params,
        lego_specs=lego_specs,
    )


@builder_bp.route("/validate", methods=["POST"])
def validate():
    """Validate brick parameters."""
    data = request.get_json()

    result = BuilderService.validate_params(
        width_studs=data.get("width_studs", 2),
        depth_studs=data.get("depth_studs", 4),
        height_plates=data.get("height_plates", 3),
        brick_type=data.get("brick_type", "standard"),
        features=data.get("features"),
    )

    return jsonify(result)


@builder_bp.route("/compute", methods=["POST"])
def compute_dimensions():
    """Compute brick dimensions."""
    data = request.get_json()

    dimensions = BuilderService.compute_dimensions(
        width_studs=data.get("width_studs", 2),
        depth_studs=data.get("depth_studs", 4),
        height_plates=data.get("height_plates", 3),
    )

    return jsonify(dimensions)


@builder_bp.route("/create", methods=["POST"])
def create_brick():
    """Create a brick."""
    data = request.get_json()

    # Pass parameters directly to MCP bridge (it expects flat structure)
    params = {
        "name": data.get("name", "custom_brick"),
        "width_studs": data.get("width_studs", 2),
        "depth_studs": data.get("depth_studs", 4),
        "height_plates": data.get("height_plates", 3),
        "brick_type": data.get("brick_type", "standard"),
        "color": data.get("color"),
        "hollow": data.get("hollow", True),
        "slope_angle": data.get("slope_angle"),
        "slope_direction": data.get("slope_direction", "front"),
        "technic_axis": data.get("technic_axis", "x"),
    }

    # Execute via MCP bridge
    result = MCPBridge.execute_tool("create_custom_brick", params)

    # Flatten the response - MCP bridge wraps result
    if result.get("success") and result.get("result"):
        inner = result["result"]
        return jsonify({
            "success": inner.get("success", True),
            "brick_id": inner.get("brick_id"),
            "component_name": inner.get("component_name"),
            "dimensions": inner.get("dimensions"),
            "error": inner.get("error"),
        })

    return jsonify(result)


@builder_bp.route("/presets")
def get_presets():
    """Get available presets."""
    presets = BuilderService.get_presets()
    return jsonify(presets)


@builder_bp.route("/specs")
def get_specs():
    """Get LEGO specifications."""
    specs = BuilderService.get_lego_specs()
    return jsonify(specs)
