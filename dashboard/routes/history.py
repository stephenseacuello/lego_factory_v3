"""
History Routes

Operation history and undo/redo functionality.
"""

from flask import Blueprint, render_template, request, jsonify
from services.mcp_bridge import MCPBridge

history_bp = Blueprint("history", __name__)


@history_bp.route("/")
def history_list():
    """Operation history page."""
    # Get query params
    limit = int(request.args.get("limit", 50))
    op_type = request.args.get("type")

    # Get history
    params = {"limit": limit}
    if op_type:
        params["operation_type"] = op_type

    result = MCPBridge.execute_tool("get_history", params)
    operations = result.get("result", []) if result.get("success") else []

    # Get statistics
    stats_result = MCPBridge.execute_tool("get_statistics", {})
    stats = stats_result.get("result", {}) if stats_result.get("success") else {}

    # Operation types for filter
    op_types = ["create_brick", "modify_brick", "delete_brick", "export", "batch_create"]

    return render_template(
        "pages/history.html",
        operations=operations,
        stats=stats,
        op_types=op_types,
        current_type=op_type,
        limit=limit,
    )


@history_bp.route("/undo", methods=["POST"])
def undo():
    """Undo last operation."""
    result = MCPBridge.execute_tool("undo", {})
    return jsonify(result)


@history_bp.route("/redo", methods=["POST"])
def redo():
    """Redo last undone operation."""
    result = MCPBridge.execute_tool("redo", {})
    return jsonify(result)


@history_bp.route("/stats")
def stats():
    """Get history statistics."""
    result = MCPBridge.execute_tool("get_statistics", {})
    return jsonify(result)


@history_bp.route("/export")
def export_history():
    """Export history as JSON."""
    result = MCPBridge.execute_tool("get_history", {"limit": 1000})

    if result.get("success"):
        from flask import Response
        import json

        return Response(
            json.dumps(result["result"], indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=history.json"},
        )

    return jsonify({"error": "Could not export history"}), 500
