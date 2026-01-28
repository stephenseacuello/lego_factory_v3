"""
MCP API Routes
==============
REST API endpoints for Fusion 360 MCP integration.

Provides endpoints for:
- MCP server status and tools
- Design operations
- Text engraving
- Pattern creation
- G-code generation
"""

import logging
import re
from flask import Blueprint, jsonify, request

from config import get_config
from api.utils.validation import validate_uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Input Validation Constants and Helpers
# =============================================================================

# Allowed tool names for MCP execution
ALLOWED_TOOLS = frozenset({
    # Design operations
    "get_design_info", "get_component_tree", "get_parameters",
    "create_component", "create_sketch", "draw_rectangle", "draw_circle",
    "draw_line", "extrude", "fillet", "chamfer", "export",
    # Engraving operations
    "create_text_profile", "engrave_to_depth", "generate_v_carve_gcode",
    "pocket_text", "outline_text",
    # Pattern operations
    "create_rectangular_pattern", "create_circular_pattern",
    "create_path_pattern", "mirror_bodies",
})

# Allowed geometry types
ALLOWED_GEOMETRY_TYPES = frozenset({"rectangle", "circle", "line"})

# Allowed feature types
ALLOWED_FEATURE_TYPES = frozenset({"extrude", "fillet", "chamfer", "revolve", "sweep", "loft"})

# Allowed export formats
ALLOWED_EXPORT_FORMATS = frozenset({"step", "stl", "iges", "obj", "f3d", "smt"})

# Allowed engraving styles
ALLOWED_ENGRAVING_STYLES = frozenset({"line", "v_carve", "pocket", "outline"})

# Allowed sketch planes
ALLOWED_PLANES = frozenset({"XY", "XZ", "YZ"})

# Allowed mirror planes
ALLOWED_MIRROR_PLANES = frozenset({"XY", "XZ", "YZ"})

# Allowed spacing types
ALLOWED_SPACING_TYPES = frozenset({"equal", "fixed_distance"})

# Allowed text alignments
ALLOWED_ALIGNMENTS = frozenset({"left", "center", "right"})

# Allowed priority levels
ALLOWED_PRIORITIES = frozenset({"low", "normal", "high", "critical"})

# Numeric bounds
NUMERIC_BOUNDS = {
    "depth": (0.001, 100.0),
    "height": (0.1, 1000.0),
    "feed_rate": (1, 50000),
    "v_bit_angle": (10, 120),
    "tool_diameter": (0.1, 50.0),
    "x_count": (1, 1000),
    "y_count": (1, 1000),
    "count": (1, 10000),
    "radius": (0.1, 10000.0),
    "total_angle": (0.1, 360.0),
    "start_angle": (-360.0, 360.0),
    "x_spacing": (0.1, 10000.0),
    "y_spacing": (0.1, 10000.0),
    "safe_z": (-1000.0, 1000.0),
    "rapid_z": (-1000.0, 1000.0),
    "feature_size": (0.1, 10000.0),
    "padding": (0, 20),
    "start_number": (0, 999999999),
    "increment": (1, 1000),
}

# Text length limits
MAX_TEXT_LENGTH = 1000
MAX_TEMPLATE_ID_LENGTH = 64
MAX_GCODE_LENGTH = 1000000  # 1MB of G-code


def validate_numeric_param(value, param_name: str, required: bool = False):
    """Validate a numeric parameter against defined bounds."""
    if value is None:
        if required:
            raise ValueError(f"{param_name} is required")
        return None

    try:
        num_value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{param_name} must be a number")

    if param_name in NUMERIC_BOUNDS:
        min_val, max_val = NUMERIC_BOUNDS[param_name]
        if num_value < min_val or num_value > max_val:
            raise ValueError(f"{param_name} must be between {min_val} and {max_val}")

    return num_value


def validate_text_input(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Validate and sanitize text input."""
    if not text:
        raise ValueError("Text content is required")

    if len(text) > max_length:
        raise ValueError(f"Text exceeds maximum length of {max_length} characters")

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return sanitized


def validate_identifier(value: str, name: str, max_length: int = 128) -> str:
    """Validate an identifier (IDs, names)."""
    if not value:
        raise ValueError(f"{name} is required")

    if len(value) > max_length:
        raise ValueError(f"{name} exceeds maximum length of {max_length}")

    # Allow alphanumeric, underscore, hyphen, and period
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', value):
        raise ValueError(f"{name} contains invalid characters")

    return value

bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')


def _get_bridge_service():
    """Get MCP bridge service instance."""
    from services.mcp_bridge_service import get_mcp_bridge
    return get_mcp_bridge()


def _get_engraving_service():
    """Get engraving service instance."""
    from services.engraving_mcp_service import get_engraving_service
    return get_engraving_service()


def _get_pattern_service():
    """Get pattern service instance."""
    from services.pattern_mcp_service import get_pattern_service
    return get_pattern_service()


# =============================================================================
# MCP Server Status
# =============================================================================

@bp.route('/status', methods=['GET'])
def get_status():
    """
    Get MCP server connection status.

    Returns:
        JSON with MCP status
    """
    try:
        bridge = _get_bridge_service()
        status = bridge.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Failed to get MCP status: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Perform health check on MCP components.

    Returns:
        JSON with health status
    """
    try:
        bridge = _get_bridge_service()
        health = bridge.health_check()
        return jsonify(health)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"error": str(e), "overall": False}), 500


@bp.route('/tools', methods=['GET'])
def list_tools():
    """
    List available MCP tools.

    Returns:
        JSON array of tools
    """
    try:
        from services.mcp_fusion_client import MCPToolRegistry
        registry = MCPToolRegistry()
        tools = registry.list_tools()
        return jsonify({"tools": tools, "count": len(tools)})
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/execute', methods=['POST'])
def execute_tool():
    """
    Execute an MCP tool.

    Request body:
        {
            "tool": "tool_name",
            "parameters": {...}
        }

    Returns:
        JSON with execution result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        tool_name = data.get('tool')
        parameters = data.get('parameters', {})

        if not tool_name:
            return jsonify({"error": "Tool name required"}), 400

        # Validate tool name against whitelist
        if tool_name not in ALLOWED_TOOLS:
            logger.warning(f"Rejected unknown MCP tool: {tool_name}")
            return jsonify({"error": f"Unknown tool: {tool_name}"}), 400

        bridge = _get_bridge_service()
        result = bridge.execute_design_operation(tool_name, parameters)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Design Operations
# =============================================================================

@bp.route('/design', methods=['GET'])
def get_design():
    """
    Get active design information.

    Returns:
        JSON with design info
    """
    try:
        bridge = _get_bridge_service()
        result = bridge.get_active_design()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get design: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/design/components', methods=['GET'])
def get_components():
    """
    Get design component tree.

    Query params:
        root_only: Only return root component (default: false)

    Returns:
        JSON with component tree
    """
    try:
        root_only = request.args.get('root_only', 'false').lower() == 'true'
        bridge = _get_bridge_service()
        result = bridge.get_component_tree(root_only=root_only)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get components: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/design/parameters', methods=['GET'])
def get_parameters():
    """
    Get design parameters.

    Returns:
        JSON with parameters
    """
    try:
        bridge = _get_bridge_service()
        result = bridge.get_parameters()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get parameters: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Sketch Operations
# =============================================================================

@bp.route('/sketch', methods=['POST'])
def create_sketch():
    """
    Create a new sketch.

    Request body:
        {
            "name": "sketch_name",
            "plane": "XY" | "XZ" | "YZ",
            "face_id": "optional_face_id"
        }

    Returns:
        JSON with sketch ID
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        name = data.get('name', 'Sketch')
        plane = data.get('plane', 'XY')
        face_id = data.get('face_id')

        # Validate plane
        if plane not in ALLOWED_PLANES:
            return jsonify({"error": f"Invalid plane. Must be one of: {', '.join(ALLOWED_PLANES)}"}), 400

        # Validate name length
        if len(name) > 128:
            return jsonify({"error": "Sketch name too long (max 128 characters)"}), 400

        bridge = _get_bridge_service()
        result = bridge.create_sketch_on_plane(name=name, plane=plane)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to create sketch: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/sketch/<sketch_id>/geometry', methods=['POST'])
def add_geometry(sketch_id):
    """
    Add geometry to a sketch.

    Request body:
        {
            "type": "rectangle" | "circle" | "line",
            "params": {...}
        }

    Returns:
        JSON with geometry result
    """
    try:
        # Validate sketch_id format
        try:
            validate_identifier(sketch_id, "sketch_id")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        geom_type = data.get('type')
        params = data.get('params', {})

        if not geom_type:
            return jsonify({"error": "Geometry type required"}), 400

        # Validate geometry type against whitelist
        if geom_type not in ALLOWED_GEOMETRY_TYPES:
            return jsonify({"error": f"Invalid geometry type. Must be one of: {', '.join(ALLOWED_GEOMETRY_TYPES)}"}), 400

        # Map geometry type to tool
        tool_map = {
            "rectangle": "draw_rectangle",
            "circle": "draw_circle",
            "line": "draw_line"
        }

        tool_name = tool_map.get(geom_type)

        bridge = _get_bridge_service()
        result = bridge.add_sketch_geometry(sketch_id, tool_name, params)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to add geometry: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Feature Operations
# =============================================================================

@bp.route('/feature', methods=['POST'])
def create_feature():
    """
    Create a feature (extrude, fillet, etc.).

    Request body:
        {
            "type": "extrude" | "fillet" | "chamfer",
            "params": {...}
        }

    Returns:
        JSON with feature result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        feature_type = data.get('type')
        params = data.get('params', {})

        if not feature_type:
            return jsonify({"error": "Feature type required"}), 400

        # Validate feature type against whitelist
        if feature_type not in ALLOWED_FEATURE_TYPES:
            return jsonify({"error": f"Invalid feature type. Must be one of: {', '.join(ALLOWED_FEATURE_TYPES)}"}), 400

        bridge = _get_bridge_service()
        result = bridge.create_feature(feature_type, params)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to create feature: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/export', methods=['POST'])
def export_design():
    """
    Export design to file format.

    Request body:
        {
            "format": "step" | "stl" | "iges" | "obj",
            "options": {...}
        }

    Returns:
        JSON with export result or file data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        export_format = data.get('format', 'step')
        options = data.get('options', {})

        # Validate export format
        if export_format not in ALLOWED_EXPORT_FORMATS:
            return jsonify({"error": f"Invalid format. Must be one of: {', '.join(ALLOWED_EXPORT_FORMATS)}"}), 400

        bridge = _get_bridge_service()
        result = bridge.export_design(export_format, options)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to export design: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Operation Queue
# =============================================================================

@bp.route('/queue', methods=['GET'])
def get_queue_status():
    """
    Get operation queue status.

    Returns:
        JSON with queue information
    """
    try:
        bridge = _get_bridge_service()
        status = bridge.get_status()
        return jsonify({
            "queue_size": status.get("queue_size", 0),
            "pending_operations": status.get("pending_operations", 0)
        })
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/queue', methods=['POST'])
def queue_operation():
    """
    Queue an operation for async execution.

    Request body:
        {
            "operation": "operation_type",
            "parameters": {...},
            "priority": "low" | "normal" | "high" | "critical"
        }

    Returns:
        JSON with operation ID
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        operation = data.get('operation')
        parameters = data.get('parameters', {})
        priority_str = data.get('priority', 'normal')

        if not operation:
            return jsonify({"error": "Operation type required"}), 400

        # Validate operation against tool whitelist
        if operation not in ALLOWED_TOOLS:
            logger.warning(f"Rejected unknown operation: {operation}")
            return jsonify({"error": f"Unknown operation: {operation}"}), 400

        # Validate priority
        if priority_str not in ALLOWED_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(ALLOWED_PRIORITIES)}"}), 400

        from services.mcp_bridge_service import OperationPriority
        priority_map = {
            "low": OperationPriority.LOW,
            "normal": OperationPriority.NORMAL,
            "high": OperationPriority.HIGH,
            "critical": OperationPriority.CRITICAL
        }
        priority = priority_map.get(priority_str, OperationPriority.NORMAL)

        bridge = _get_bridge_service()
        operation_id = bridge.queue_operation(operation, parameters, priority=priority)

        return jsonify({
            "operation_id": operation_id,
            "status": "queued"
        })
    except Exception as e:
        logger.error(f"Failed to queue operation: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/queue/<operation_id>', methods=['GET'])
def get_operation_result(operation_id):
    """
    Get result of a queued operation.

    Returns:
        JSON with operation result
    """
    try:
        bridge = _get_bridge_service()
        result = bridge.get_operation_result(operation_id)

        if result is None:
            return jsonify({"error": "Operation not found"}), 404

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get operation result: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/queue/<operation_id>', methods=['DELETE'])
def cancel_operation(operation_id):
    """
    Cancel a pending operation.

    Returns:
        JSON with cancellation result
    """
    try:
        bridge = _get_bridge_service()
        cancelled = bridge.cancel_operation(operation_id)

        if cancelled:
            return jsonify({"success": True, "message": "Operation cancelled"})
        else:
            return jsonify({"success": False, "message": "Operation cannot be cancelled"}), 400
    except Exception as e:
        logger.error(f"Failed to cancel operation: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Text Engraving
# =============================================================================

@bp.route('/text', methods=['POST'])
def create_text():
    """
    Create text profile for engraving.

    Request body:
        {
            "text": "Text content",
            "height": 5.0,
            "font": "Arial",
            "position": {"x": 0, "y": 0},
            "alignment": "left" | "center" | "right"
        }

    Returns:
        JSON with profile information
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        text = data.get('text')
        height = data.get('height', 5.0)
        font = data.get('font')
        position = data.get('position')
        alignment = data.get('alignment', 'left')

        # Validate and sanitize text input
        try:
            text = validate_text_input(text)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate height
        try:
            height = validate_numeric_param(height, "height")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate alignment
        if alignment not in ALLOWED_ALIGNMENTS:
            return jsonify({"error": f"Invalid alignment. Must be one of: {', '.join(ALLOWED_ALIGNMENTS)}"}), 400

        from services.engraving_mcp_service import Point2D, TextAlignment

        pos = Point2D(position['x'], position['y']) if position else None
        align = TextAlignment(alignment) if alignment else TextAlignment.LEFT

        service = _get_engraving_service()
        profile = service.create_text_profile(
            text=text,
            height=height,
            position=pos,
            font=font,
            alignment=align
        )

        return jsonify(service.get_profile(profile.profile_id))
    except Exception as e:
        logger.error(f"Failed to create text: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/text/fonts', methods=['GET'])
def get_fonts():
    """
    Get available fonts.

    Returns:
        JSON array of font names
    """
    try:
        service = _get_engraving_service()
        fonts = service.get_available_fonts()
        return jsonify({"fonts": fonts})
    except Exception as e:
        logger.error(f"Failed to get fonts: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/text/preview', methods=['POST'])
def preview_text():
    """
    Preview text as SVG.

    Request body:
        {
            "profile_id": "profile_xxx"
        }

    Returns:
        JSON with SVG data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        profile_id = data.get('profile_id')
        if not profile_id:
            return jsonify({"error": "Profile ID required"}), 400

        service = _get_engraving_service()
        preview = service.preview_engraving(profile_id)

        return jsonify(preview)
    except Exception as e:
        logger.error(f"Failed to preview text: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/engrave', methods=['POST'])
def engrave_text():
    """
    Create engraving from text profile.

    Request body:
        {
            "profile_id": "profile_xxx",
            "style": "line" | "v_carve" | "pocket" | "outline",
            "depth": 0.5,
            "feed_rate": 500,
            "v_bit_angle": 60,
            "tool_diameter": 3.0
        }

    Returns:
        JSON with engraving result and G-code
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        profile_id = data.get('profile_id')
        style = data.get('style', 'line')
        depth = data.get('depth', 0.5)
        feed_rate = data.get('feed_rate')
        v_bit_angle = data.get('v_bit_angle', 60)
        tool_diameter = data.get('tool_diameter')

        if not profile_id:
            return jsonify({"error": "Profile ID required"}), 400

        # Validate profile_id format
        try:
            validate_identifier(profile_id, "profile_id")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate style against whitelist
        if style not in ALLOWED_ENGRAVING_STYLES:
            return jsonify({"error": f"Invalid style. Must be one of: {', '.join(ALLOWED_ENGRAVING_STYLES)}"}), 400

        # Validate numeric parameters
        try:
            depth = validate_numeric_param(depth, "depth")
            if feed_rate is not None:
                feed_rate = validate_numeric_param(feed_rate, "feed_rate")
            v_bit_angle = validate_numeric_param(v_bit_angle, "v_bit_angle")
            if tool_diameter is not None:
                tool_diameter = validate_numeric_param(tool_diameter, "tool_diameter")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        from services.engraving_mcp_service import EngravingStyle
        service = _get_engraving_service()

        # Call appropriate method based on style
        if style == 'line':
            result = service.engrave_to_depth(profile_id, depth, feed_rate)
        elif style == 'v_carve':
            result = service.generate_v_carve_gcode(profile_id, v_bit_angle, depth, feed_rate)
        elif style == 'pocket':
            if not tool_diameter:
                return jsonify({"error": "Tool diameter required for pocket"}), 400
            result = service.pocket_text(profile_id, depth, tool_diameter, feed_rate=feed_rate)
        elif style == 'outline':
            if not tool_diameter:
                return jsonify({"error": "Tool diameter required for outline"}), 400
            result = service.outline_text(profile_id, depth, tool_diameter, feed_rate)
        else:
            return jsonify({"error": f"Unknown style: {style}"}), 400

        return jsonify({
            "success": result.success,
            "profile_id": result.profile_id,
            "style": result.style.value,
            "gcode": result.gcode,
            "toolpath_length": result.toolpath_length,
            "estimated_time_seconds": result.estimated_time_seconds,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to engrave text: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/engrave/gcode', methods=['POST'])
def generate_engraving_gcode():
    """
    Generate engraving G-code directly from text.

    Request body:
        {
            "text": "Text content",
            "height": 5.0,
            "position": {"x": 0, "y": 0},
            "style": "line" | "v_carve",
            "depth": 0.5,
            "feed_rate": 500
        }

    Returns:
        JSON with G-code
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        text = data.get('text')
        height = data.get('height', 5.0)
        position = data.get('position', {"x": 0, "y": 0})
        style = data.get('style', 'line')
        depth = data.get('depth', 0.5)
        feed_rate = data.get('feed_rate', 500)

        # Validate and sanitize text
        try:
            text = validate_text_input(text)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate style
        if style not in {'line', 'v_carve'}:
            return jsonify({"error": "Style must be 'line' or 'v_carve'"}), 400

        # Validate numeric parameters
        try:
            height = validate_numeric_param(height, "height")
            depth = validate_numeric_param(depth, "depth")
            feed_rate = validate_numeric_param(feed_rate, "feed_rate")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        from services.engraving_mcp_service import Point2D
        service = _get_engraving_service()

        # Create profile
        pos = Point2D(position['x'], position['y'])
        profile = service.create_text_profile(text, height, position=pos)

        # Generate G-code based on style
        if style == 'v_carve':
            v_angle = data.get('v_bit_angle', 60)
            try:
                v_angle = validate_numeric_param(v_angle, "v_bit_angle")
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            result = service.generate_v_carve_gcode(profile.profile_id, v_angle, depth, feed_rate)
        else:
            result = service.engrave_to_depth(profile.profile_id, depth, feed_rate)

        return jsonify({
            "success": result.success,
            "gcode": result.gcode,
            "estimated_time_seconds": result.estimated_time_seconds,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to generate engraving G-code: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Patterns
# =============================================================================

@bp.route('/pattern/rectangular', methods=['POST'])
def create_rectangular_pattern():
    """
    Create rectangular/grid pattern.

    Request body:
        {
            "source_feature_id": "feature_xxx",
            "x_count": 4,
            "y_count": 3,
            "x_spacing": 25.0,
            "y_spacing": 20.0,
            "start_position": {"x": 0, "y": 0}
        }

    Returns:
        JSON with pattern result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        source_id = data.get('source_feature_id', 'default')
        x_count = data.get('x_count', 2)
        y_count = data.get('y_count', 2)
        x_spacing = data.get('x_spacing', 10)
        y_spacing = data.get('y_spacing', 10)
        start_pos = data.get('start_position')

        # Validate numeric parameters
        try:
            x_count = int(validate_numeric_param(x_count, "x_count"))
            y_count = int(validate_numeric_param(y_count, "y_count"))
            x_spacing = validate_numeric_param(x_spacing, "x_spacing")
            y_spacing = validate_numeric_param(y_spacing, "y_spacing")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        from services.pattern_mcp_service import Point2D
        service = _get_pattern_service()

        start = Point2D(start_pos['x'], start_pos['y']) if start_pos else None

        result = service.create_rectangular_pattern(
            source_feature_id=source_id,
            x_count=x_count,
            y_count=y_count,
            x_spacing=x_spacing,
            y_spacing=y_spacing,
            start_position=start
        )

        return jsonify({
            "success": result.success,
            "pattern_id": result.pattern_id,
            "pattern_type": result.pattern_type.value,
            "instance_count": result.instance_count,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to create rectangular pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/circular', methods=['POST'])
def create_circular_pattern():
    """
    Create circular/radial pattern.

    Request body:
        {
            "source_feature_id": "feature_xxx",
            "center": {"x": 50, "y": 50},
            "count": 8,
            "radius": 30,
            "total_angle": 360,
            "start_angle": 0
        }

    Returns:
        JSON with pattern result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        source_id = data.get('source_feature_id', 'default')
        center = data.get('center', {"x": 0, "y": 0})
        count = data.get('count', 4)
        radius = data.get('radius')
        total_angle = data.get('total_angle', 360)
        start_angle = data.get('start_angle', 0)

        # Validate numeric parameters
        try:
            count = int(validate_numeric_param(count, "count"))
            if radius is not None:
                radius = validate_numeric_param(radius, "radius")
            total_angle = validate_numeric_param(total_angle, "total_angle")
            start_angle = validate_numeric_param(start_angle, "start_angle")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        from services.pattern_mcp_service import Point2D
        service = _get_pattern_service()

        center_pt = Point2D(center['x'], center['y'])

        result = service.create_circular_pattern(
            source_feature_id=source_id,
            center=center_pt,
            count=count,
            radius=radius,
            total_angle=total_angle,
            start_angle=start_angle
        )

        return jsonify({
            "success": result.success,
            "pattern_id": result.pattern_id,
            "pattern_type": result.pattern_type.value,
            "instance_count": result.instance_count,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to create circular pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/along-path', methods=['POST'])
def create_path_pattern():
    """
    Create pattern along a path.

    Request body:
        {
            "source_feature_id": "feature_xxx",
            "path_points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, ...],
            "count": 10,
            "spacing_type": "equal" | "fixed_distance",
            "fixed_distance": 15.0
        }

    Returns:
        JSON with pattern result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        source_id = data.get('source_feature_id', 'default')
        path_points = data.get('path_points', [])
        count = data.get('count', 5)
        spacing_type = data.get('spacing_type', 'equal')
        fixed_distance = data.get('fixed_distance')

        if len(path_points) < 2:
            return jsonify({"error": "At least 2 path points required"}), 400

        from services.pattern_mcp_service import Point2D, SpacingType
        service = _get_pattern_service()

        points = [Point2D(p['x'], p['y']) for p in path_points]
        spacing = SpacingType(spacing_type)

        result = service.create_path_pattern(
            source_feature_id=source_id,
            path_points=points,
            count=count,
            spacing_type=spacing,
            fixed_distance=fixed_distance
        )

        return jsonify({
            "success": result.success,
            "pattern_id": result.pattern_id,
            "pattern_type": result.pattern_type.value,
            "instance_count": result.instance_count,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to create path pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/mirror', methods=['POST'])
def create_mirror_pattern():
    """
    Mirror features across a plane.

    Request body:
        {
            "feature_ids": ["feature_xxx"],
            "mirror_plane": "XY" | "XZ" | "YZ",
            "copy": true
        }

    Returns:
        JSON with pattern result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        feature_ids = data.get('feature_ids', [])
        mirror_plane = data.get('mirror_plane', 'YZ')
        copy = data.get('copy', True)

        if not feature_ids:
            return jsonify({"error": "Feature IDs required"}), 400

        # Validate feature_ids are proper identifiers
        if len(feature_ids) > 100:
            return jsonify({"error": "Too many feature IDs (max 100)"}), 400

        # Validate mirror plane
        if mirror_plane not in ALLOWED_MIRROR_PLANES:
            return jsonify({"error": f"Invalid mirror plane. Must be one of: {', '.join(ALLOWED_MIRROR_PLANES)}"}), 400

        from services.pattern_mcp_service import MirrorPlane
        service = _get_pattern_service()

        plane = MirrorPlane(mirror_plane)

        result = service.mirror_bodies(
            feature_ids=feature_ids,
            mirror_plane=plane,
            copy=copy
        )

        return jsonify({
            "success": result.success,
            "pattern_id": result.pattern_id,
            "pattern_type": result.pattern_type.value,
            "instance_count": result.instance_count,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Failed to create mirror pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/preview', methods=['POST'])
def preview_pattern():
    """
    Preview pattern as SVG.

    Request body:
        {
            "pattern_id": "pattern_xxx",
            "feature_size": 10.0
        }

    Returns:
        JSON with SVG data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        pattern_id = data.get('pattern_id')
        feature_size = data.get('feature_size', 10.0)

        if not pattern_id:
            return jsonify({"error": "Pattern ID required"}), 400

        service = _get_pattern_service()
        preview = service.preview_pattern(pattern_id, feature_size)

        return jsonify(preview)
    except Exception as e:
        logger.error(f"Failed to preview pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/<pattern_id>', methods=['GET'])
def get_pattern(pattern_id):
    """
    Get pattern information.

    Returns:
        JSON with pattern details
    """
    try:
        service = _get_pattern_service()
        pattern = service.get_pattern(pattern_id)

        if pattern is None:
            return jsonify({"error": "Pattern not found"}), 404

        return jsonify(pattern)
    except Exception as e:
        logger.error(f"Failed to get pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/<pattern_id>', methods=['DELETE'])
def delete_pattern(pattern_id):
    """
    Delete a pattern.

    Returns:
        JSON with deletion result
    """
    try:
        service = _get_pattern_service()
        deleted = service.delete_pattern(pattern_id)

        if deleted:
            return jsonify({"success": True, "message": "Pattern deleted"})
        else:
            return jsonify({"success": False, "error": "Pattern not found"}), 404
    except Exception as e:
        logger.error(f"Failed to delete pattern: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/<pattern_id>/suppress', methods=['POST'])
def suppress_instances(pattern_id):
    """
    Suppress pattern instances.

    Request body:
        {
            "indices": [0, 2, 5]
        }

    Returns:
        JSON with result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        indices = data.get('indices', [])

        service = _get_pattern_service()
        success = service.suppress_pattern_instances(pattern_id, indices)

        if success:
            return jsonify({"success": True, "suppressed": indices})
        else:
            return jsonify({"success": False, "error": "Pattern not found"}), 404
    except Exception as e:
        logger.error(f"Failed to suppress instances: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pattern/<pattern_id>/gcode', methods=['POST'])
def generate_pattern_gcode(pattern_id):
    """
    Generate G-code for pattern.

    Request body:
        {
            "operation_gcode": "G0 X0 Y0\\nG1 Z-1 F100\\n...",
            "safe_z": 5.0,
            "rapid_z": 2.0
        }

    Returns:
        JSON with G-code
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        operation_gcode = data.get('operation_gcode', '')
        safe_z = data.get('safe_z', 5.0)
        rapid_z = data.get('rapid_z', 2.0)

        service = _get_pattern_service()
        gcode = service.generate_pattern_gcode(
            pattern_id=pattern_id,
            operation_gcode=operation_gcode,
            safe_z=safe_z,
            rapid_z=rapid_z
        )

        if gcode is None:
            return jsonify({"success": False, "error": "Pattern not found"}), 404

        return jsonify({
            "success": True,
            "gcode": gcode
        })
    except Exception as e:
        logger.error(f"Failed to generate pattern G-code: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Serial Number Templates
# =============================================================================

@bp.route('/templates', methods=['GET'])
def list_templates():
    """
    List all serial number templates.

    Returns:
        JSON array of templates
    """
    try:
        service = _get_engraving_service()
        templates = service.list_templates()
        return jsonify({"templates": templates, "count": len(templates)})
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/templates', methods=['POST'])
def create_template():
    """
    Create a serial number template.

    Request body:
        {
            "template_id": "sn_template_01",
            "prefix": "SN-",
            "suffix": "-A",
            "start_number": 1,
            "padding": 5,
            "increment": 1
        }

    Returns:
        JSON with template info
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        template_id = data.get('template_id')
        if not template_id:
            # Auto-generate template ID
            import uuid
            template_id = f"template_{uuid.uuid4().hex[:8]}"
        else:
            # Validate user-provided template ID
            try:
                template_id = validate_identifier(template_id, "template_id", MAX_TEMPLATE_ID_LENGTH)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        prefix = data.get('prefix', '')
        suffix = data.get('suffix', '')
        start_number = data.get('start_number', 1)
        padding = data.get('padding', 5)
        increment = data.get('increment', 1)

        # Validate prefix/suffix length
        if len(prefix) > 32:
            return jsonify({"error": "Prefix too long (max 32 characters)"}), 400
        if len(suffix) > 32:
            return jsonify({"error": "Suffix too long (max 32 characters)"}), 400

        # Validate numeric parameters
        try:
            start_number = int(validate_numeric_param(start_number, "start_number"))
            padding = int(validate_numeric_param(padding, "padding"))
            increment = int(validate_numeric_param(increment, "increment"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        service = _get_engraving_service()
        template = service.create_template(
            template_id=template_id,
            prefix=prefix,
            suffix=suffix,
            start_number=start_number,
            padding=padding
        )

        return jsonify({
            "success": True,
            "template_id": template.template_id,
            "prefix": template.prefix,
            "suffix": template.suffix,
            "current_number": template.current_number,
            "padding": template.padding
        })
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/templates/<template_id>/next', methods=['POST'])
def generate_next_serial(template_id):
    """
    Generate the next serial number from a template.

    Returns:
        JSON with generated serial number
    """
    try:
        data = request.get_json() or {}
        increment = data.get('increment', True)

        service = _get_engraving_service()
        serial = service.apply_template(template_id, increment=increment)

        return jsonify({
            "success": True,
            "serial_number": serial,
            "template_id": template_id
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to generate serial: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Cache Management
# =============================================================================

@bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """
    Clear MCP bridge cache.

    Returns:
        JSON with result
    """
    try:
        bridge = _get_bridge_service()
        bridge.clear_cache()
        return jsonify({"success": True, "message": "Cache cleared"})
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Get MCP bridge statistics.

    Returns:
        JSON with statistics
    """
    try:
        bridge = _get_bridge_service()
        stats = bridge.get_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return jsonify({"error": str(e)}), 500
