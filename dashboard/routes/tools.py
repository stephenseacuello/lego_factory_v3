"""
Tools Routes

Tool playground for testing MCP tools directly.
"""

from flask import Blueprint, render_template, request, jsonify
from services.mcp_bridge import MCPBridge

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/")
def playground():
    """Tool playground page."""
    # Get all tools
    tools = MCPBridge.get_tools()
    categories = MCPBridge.get_tool_categories()

    # Selected tool from query
    selected_tool = request.args.get("tool")
    tool_info = None
    example = {}

    if selected_tool and selected_tool in tools:
        tool_info = tools[selected_tool]
        example = MCPBridge.get_tool_examples(selected_tool)

    return render_template(
        "pages/tools.html",
        tools=tools,
        categories=categories,
        selected_tool=selected_tool,
        tool_info=tool_info,
        example=example,
    )


@tools_bp.route("/list")
def list_tools():
    """List all available tools."""
    tools = MCPBridge.get_tools()
    categories = MCPBridge.get_tool_categories()

    return jsonify(
        {
            "tools": {name: {"description": t.get("description", "")} for name, t in tools.items()},
            "categories": categories,
            "total": len(tools),
        }
    )


@tools_bp.route("/info/<tool_name>")
def tool_info(tool_name):
    """Get information about a specific tool."""
    tool = MCPBridge.get_tool(tool_name)

    if not tool:
        return jsonify({"error": f"Tool not found: {tool_name}"}), 404

    example = MCPBridge.get_tool_examples(tool_name)

    return jsonify(
        {
            "name": tool_name,
            "description": tool.get("description", ""),
            "schema": tool.get("inputSchema", {}),
            "example": example,
        }
    )


@tools_bp.route("/execute", methods=["POST"])
def execute_tool():
    """Execute a tool."""
    data = request.get_json()

    tool_name = data.get("tool")
    params = data.get("params", {})

    if not tool_name:
        return jsonify({"success": False, "error": "No tool specified"})

    # Validate first
    validation = MCPBridge.validate_params(tool_name, params)
    if not validation["valid"]:
        return jsonify(
            {
                "success": False,
                "error": "Validation failed",
                "validation_errors": validation["errors"],
            }
        )

    # Execute
    result = MCPBridge.execute_tool(tool_name, params)

    return jsonify(result)


@tools_bp.route("/validate", methods=["POST"])
def validate_params():
    """Validate tool parameters."""
    data = request.get_json()

    tool_name = data.get("tool")
    params = data.get("params", {})

    if not tool_name:
        return jsonify({"valid": False, "errors": ["No tool specified"]})

    result = MCPBridge.validate_params(tool_name, params)
    return jsonify(result)


@tools_bp.route("/example/<tool_name>")
def get_example(tool_name):
    """Get example parameters for a tool."""
    example = MCPBridge.get_tool_examples(tool_name)
    return jsonify(example)
