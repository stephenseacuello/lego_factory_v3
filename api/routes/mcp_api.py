"""
LEGO Factory v3 - MCP REST API
==============================
REST and WebSocket API for Model Context Protocol server.

Provides endpoints for:
- Tool listing and discovery
- Tool execution
- Server status and configuration
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

logger = logging.getLogger(__name__)

mcp_api_bp = Blueprint('mcp_api', __name__, url_prefix='/api/mcp')


def get_mcp_server():
    """Get MCP server instance."""
    try:
        from services.mcp.server import get_mcp_server
        return get_mcp_server()
    except Exception as e:
        logger.warning(f"MCP server not available: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Server Status
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/status', methods=['GET'])
@jwt_required()
def server_status():
    """Get MCP server status."""
    server = get_mcp_server()

    if not server:
        return jsonify({
            'available': False,
            'error': 'MCP server not initialized',
        }), 503

    # Count tools by category
    category_counts = {}
    for tool in server.tools.values():
        cat = tool.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return jsonify({
        'available': True,
        'version': '3.0.0',
        'tool_count': len(server.tools),
        'categories': category_counts,
        'protocol': 'MCP/1.0',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool Discovery
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/tools', methods=['GET'])
@jwt_required()
def list_tools():
    """
    List available MCP tools.

    Query params:
    - category: Filter by category (scada, mes, erp, qms, cmms, lego, ml, robotics, unity)
    """
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    category = request.args.get('category')

    tools = server.get_tools_list()

    if category:
        # Filter by category
        filtered_tools = []
        for tool in tools:
            tool_def = server.tools.get(tool['name'])
            if tool_def and tool_def.category.value == category:
                filtered_tools.append(tool)
        tools = filtered_tools

    return jsonify({
        'tools': tools,
        'count': len(tools),
    })


@mcp_api_bp.route('/tools/<tool_name>', methods=['GET'])
@jwt_required()
def get_tool(tool_name: str):
    """Get details for a specific tool."""
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    if tool_name not in server.tools:
        return jsonify({'error': f'Tool not found: {tool_name}'}), 404

    tool = server.tools[tool_name]

    return jsonify({
        'name': tool.name,
        'description': tool.description,
        'category': tool.category.value,
        'inputSchema': {
            'type': 'object',
            'properties': tool.parameters,
            'required': [k for k, v in tool.parameters.items() if v.get('required')],
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool Execution
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/execute', methods=['POST'])
@jwt_required()
def execute_tool():
    """
    Execute an MCP tool.

    JSON body:
    - tool: Tool name (required)
    - arguments: Tool arguments (dict)
    """
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    tool_name = data.get('tool')
    if not tool_name:
        return jsonify({'error': 'tool name required'}), 400

    arguments = data.get('arguments', {})

    # Validate tool exists
    if tool_name not in server.tools:
        return jsonify({'error': f'Unknown tool: {tool_name}'}), 404

    # Validate required parameters
    tool = server.tools[tool_name]
    for param_name, param_def in tool.parameters.items():
        if param_def.get('required') and param_name not in arguments:
            return jsonify({'error': f'Missing required parameter: {param_name}'}), 400

    # Execute tool
    result = server.execute_tool(tool_name, arguments)

    if 'error' in result and result['error']:
        return jsonify(result), 500

    return jsonify(result)


@mcp_api_bp.route('/execute/<tool_name>', methods=['POST'])
@jwt_required()
def execute_tool_by_name(tool_name: str):
    """
    Execute a tool by name (arguments in body).

    JSON body: Tool arguments
    """
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    if tool_name not in server.tools:
        return jsonify({'error': f'Unknown tool: {tool_name}'}), 404

    arguments = request.get_json() or {}

    # Validate required parameters
    tool = server.tools[tool_name]
    for param_name, param_def in tool.parameters.items():
        if param_def.get('required') and param_name not in arguments:
            return jsonify({'error': f'Missing required parameter: {param_name}'}), 400

    result = server.execute_tool(tool_name, arguments)

    if 'error' in result and result['error']:
        return jsonify(result), 500

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# Batch Execution
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/batch', methods=['POST'])
@jwt_required()
def batch_execute():
    """
    Execute multiple tools in batch.

    JSON body:
    - calls: List of {tool, arguments}
    - stop_on_error: Stop on first error (default: false)
    """
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    data = request.get_json()
    if not data or 'calls' not in data:
        return jsonify({'error': 'calls array required'}), 400

    stop_on_error = data.get('stop_on_error', False)
    results = []

    for i, call in enumerate(data['calls']):
        tool_name = call.get('tool')
        arguments = call.get('arguments', {})

        if not tool_name:
            result = {'index': i, 'error': 'tool name required'}
        elif tool_name not in server.tools:
            result = {'index': i, 'error': f'Unknown tool: {tool_name}'}
        else:
            exec_result = server.execute_tool(tool_name, arguments)
            result = {'index': i, 'tool': tool_name, **exec_result}

        results.append(result)

        if stop_on_error and 'error' in result:
            break

    return jsonify({
        'results': results,
        'count': len(results),
        'success_count': sum(1 for r in results if 'error' not in r),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Categories
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/categories', methods=['GET'])
@jwt_required()
def list_categories():
    """List tool categories with descriptions."""
    categories = [
        {
            'id': 'scada',
            'name': 'SCADA',
            'description': 'Machine control, alarms, historian',
            'icon': 'industry',
        },
        {
            'id': 'mes',
            'name': 'MES',
            'description': 'Work orders, scheduling, OEE',
            'icon': 'clipboard-list',
        },
        {
            'id': 'erp',
            'name': 'ERP',
            'description': 'Sales, purchasing, inventory, MRP',
            'icon': 'building',
        },
        {
            'id': 'qms',
            'name': 'QMS',
            'description': 'Documents, NCR/CAPA, audits',
            'icon': 'certificate',
        },
        {
            'id': 'cmms',
            'name': 'CMMS',
            'description': 'Assets, maintenance, PM schedules',
            'icon': 'wrench',
        },
        {
            'id': 'lego',
            'name': 'LEGO',
            'description': 'Brick design, catalog, slicing',
            'icon': 'cubes',
        },
        {
            'id': 'ml',
            'name': 'ML',
            'description': 'Fingerprinting, anomaly detection',
            'icon': 'brain',
        },
        {
            'id': 'robotics',
            'name': 'Robotics',
            'description': 'Robot control, cell orchestration',
            'icon': 'robot',
        },
        {
            'id': 'unity',
            'name': 'Unity',
            'description': 'Digital Twin visualization',
            'icon': 'cube',
        },
    ]

    # Add tool counts if server available
    server = get_mcp_server()
    if server:
        for cat in categories:
            count = sum(1 for t in server.tools.values() if t.category.value == cat['id'])
            cat['tool_count'] = count

    return jsonify({
        'categories': categories,
        'count': len(categories),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Schema Export (for Claude/MCP clients)
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/schema', methods=['GET'])
@jwt_required()
def export_schema():
    """
    Export full MCP schema for Claude integration.

    Returns schema in Claude-compatible format.
    """
    server = get_mcp_server()

    if not server:
        return jsonify({'error': 'MCP server not available'}), 503

    tools_schema = []
    for tool in server.tools.values():
        tools_schema.append({
            'name': tool.name,
            'description': tool.description,
            'input_schema': {
                'type': 'object',
                'properties': tool.parameters,
                'required': [k for k, v in tool.parameters.items() if v.get('required')],
            },
        })

    return jsonify({
        'schema_version': '1.0',
        'server_name': 'lego-factory-mcp',
        'server_version': '3.0.0',
        'tools': tools_schema,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SSE Stream for real-time tool notifications
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/stream', methods=['GET'])
@jwt_required()
def stream_events():
    """
    SSE stream for real-time MCP events.

    Events include:
    - tool_executed: A tool was executed
    - tool_error: A tool execution failed
    """
    from flask import Response
    import time

    def generate():
        # Send initial connection event
        yield f"event: connected\ndata: {{\"server\": \"lego-factory-mcp\"}}\n\n"

        # Keep connection alive
        while True:
            time.sleep(30)
            yield f"event: heartbeat\ndata: {{\"timestamp\": \"{time.time()}\"}}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parts Catalog Integration (Fusion 360 MCP)
# ─────────────────────────────────────────────────────────────────────────────

@mcp_api_bp.route('/catalog/part/<part_number>/fusion-params', methods=['GET'])
@jwt_required(optional=True)
def get_fusion_params_for_part(part_number: str):
    """
    Get Fusion 360 design parameters for a catalog part.

    Returns the parameters needed to create this brick in Fusion 360
    using the create_brick MCP tool.
    """
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoPart

        with get_db_session() as session:
            part = session.query(LegoPart).filter_by(part_number=part_number).first()
            if not part:
                return jsonify({'error': f'Part {part_number} not found'}), 404

            # Map catalog part to Fusion 360 brick type
            fusion_type_map = {
                'brick': 'brick',
                'plate': 'plate',
                'tile': 'tile',
                'slope_45': 'slope',
                'slope_33': 'slope',
                'slope_inverted': 'slope_inverted',
                'wedge': 'wedge',
                'technic': 'technic',
                'special': 'brick',
            }

            fusion_type = fusion_type_map.get(part.category.value, 'brick')

            # Build Fusion 360 parameters
            params = {
                'part_number': part.part_number,
                'name': part.name,
                'brick_type': fusion_type,
                'studs_x': part.studs_length,
                'studs_y': part.studs_width,
                'height_units': part.height_plates / 3.0,  # Convert plates to brick units
                'has_studs': part.has_studs,
            }

            # Add slope angle if applicable
            if part.slope_angle:
                params['slope_angle'] = part.slope_angle

            # Add technic holes if applicable
            if part.has_holes:
                params['has_holes'] = True
                params['hole_count'] = part.hole_count or 0

            return jsonify({
                'part_number': part_number,
                'fusion_params': params,
                'mcp_tool': 'create_brick',
                'dimensions_mm': {
                    'width': part.width_mm,
                    'length': part.length_mm,
                    'height': part.height_mm,
                },
            })

    except Exception as e:
        logger.warning(f"Error getting Fusion params: {e}")
        return jsonify({'error': str(e)}), 500


@mcp_api_bp.route('/catalog/part/<part_number>/create-in-fusion', methods=['POST'])
@jwt_required(optional=True)
def create_part_in_fusion(part_number: str):
    """
    Create a catalog part in Fusion 360 using MCP.

    Optional JSON body:
    - color: Color name or hex code
    - material: Material type for weight calculation
    """
    server = get_mcp_server()
    if not server:
        return jsonify({
            'error': 'MCP server not available',
            'suggestion': 'Ensure the Fusion 360 MCP server is running',
        }), 503

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoPart

        with get_db_session() as session:
            part = session.query(LegoPart).filter_by(part_number=part_number).first()
            if not part:
                return jsonify({'error': f'Part {part_number} not found'}), 404

            # Get optional parameters from request
            data = request.get_json() or {}
            color = data.get('color', 'red')

            # Map catalog part to Fusion 360 brick type
            fusion_type_map = {
                'brick': 'brick',
                'plate': 'plate',
                'tile': 'tile',
                'slope_45': 'slope',
                'slope_33': 'slope',
                'slope_inverted': 'slope_inverted',
                'wedge': 'wedge',
                'technic': 'technic',
                'special': 'brick',
            }

            # Build MCP tool arguments
            arguments = {
                'studs_x': part.studs_length,
                'studs_y': part.studs_width,
                'height_units': part.height_plates / 3.0,
                'brick_type': fusion_type_map.get(part.category.value, 'brick'),
                'color': color,
            }

            if part.slope_angle:
                arguments['slope_angle'] = part.slope_angle

            # Execute MCP tool
            if 'create_brick' in server.tools:
                result = server.execute_tool('create_brick', arguments)
                return jsonify({
                    'success': True,
                    'part_number': part_number,
                    'mcp_result': result,
                })
            else:
                return jsonify({
                    'error': 'create_brick tool not available',
                    'available_tools': list(server.tools.keys())[:10],
                }), 503

    except Exception as e:
        logger.error(f"Error creating part in Fusion: {e}")
        return jsonify({'error': str(e)}), 500


@mcp_api_bp.route('/catalog/product/<sku>/export', methods=['POST'])
@jwt_required(optional=True)
def export_product_design(sku: str):
    """
    Export a product design to STL/STEP.

    JSON body:
    - format: 'stl' or 'step' (default: 'stl')
    - output_path: Optional output path
    """
    server = get_mcp_server()
    if not server:
        return jsonify({
            'error': 'MCP server not available',
            'suggestion': 'Ensure the Fusion 360 MCP server is running',
        }), 503

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoPart

        data = request.get_json() or {}
        export_format = data.get('format', 'stl').lower()
        output_path = data.get('output_path')

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': f'Product {sku} not found'}), 404

            part = session.query(LegoPart).filter_by(part_number=product.part_number).first()
            if not part:
                return jsonify({'error': f'Part {product.part_number} not found'}), 404

            # Generate default output path if not provided
            if not output_path:
                import os
                export_dir = os.path.join(os.getcwd(), 'data', 'exports')
                os.makedirs(export_dir, exist_ok=True)
                output_path = os.path.join(export_dir, f'{sku}.{export_format}')

            # Determine export tool
            export_tool = 'export_stl' if export_format == 'stl' else 'export_step'

            if export_tool in server.tools:
                result = server.execute_tool(export_tool, {
                    'output_path': output_path,
                    'part_number': product.part_number,
                })

                # Update product with export path
                if export_format == 'stl':
                    product.gcode_file = output_path  # Store STL path for reference
                else:
                    product.cam_file = output_path
                session.commit()

                return jsonify({
                    'success': True,
                    'sku': sku,
                    'format': export_format,
                    'output_path': output_path,
                    'mcp_result': result,
                })
            else:
                return jsonify({
                    'error': f'{export_tool} tool not available',
                    'suggestion': 'First create the design in Fusion 360 using /create-in-fusion',
                }), 503

    except Exception as e:
        logger.error(f"Error exporting product design: {e}")
        return jsonify({'error': str(e)}), 500


@mcp_api_bp.route('/catalog/product/<sku>/generate-gcode', methods=['POST'])
@jwt_required(optional=True)
def generate_product_gcode(sku: str):
    """
    Generate G-code for a product using the slicer or CAM.

    For FDM materials: Uses slicer to generate print G-code
    For CNC materials: Uses Fusion 360 CAM to generate toolpaths

    JSON body:
    - quality: 'draft', 'standard', 'quality' (FDM only)
    - machine_id: Target machine ID
    """
    server = get_mcp_server()

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoMaterial

        data = request.get_json() or {}
        quality = data.get('quality', 'standard')
        machine_id = data.get('machine_id')

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': f'Product {sku} not found'}), 404

            material = session.query(LegoMaterial).filter_by(code=product.material_code).first()
            if not material:
                return jsonify({'error': f'Material {product.material_code} not found'}), 404

            process_type = material.process_type.value if material.process_type else 'fdm'

            import os
            gcode_dir = os.path.join(os.getcwd(), 'data', 'gcode')
            os.makedirs(gcode_dir, exist_ok=True)
            gcode_path = os.path.join(gcode_dir, f'{sku}.gcode')

            if process_type == 'fdm':
                # Use slicer for FDM
                # First need STL, then slice
                stl_path = product.gcode_file or f'/tmp/{sku}.stl'

                if server and 'slice_model' in server.tools:
                    result = server.execute_tool('slice_model', {
                        'stl_path': stl_path,
                        'output_path': gcode_path,
                        'quality': quality,
                        'material': product.material_code.lower(),
                    })
                else:
                    result = {'message': 'Slicer not available, would generate G-code here'}

            elif process_type == 'cnc_mill':
                # Use CAM for CNC
                if server and 'generate_cam_toolpath' in server.tools:
                    result = server.execute_tool('generate_cam_toolpath', {
                        'part_number': product.part_number,
                        'material': product.material_code,
                        'output_path': gcode_path,
                    })
                else:
                    result = {'message': 'CAM not available, would generate toolpaths here'}

            else:
                return jsonify({'error': f'Unsupported process type: {process_type}'}), 400

            # Update product with G-code path
            product.gcode_file = gcode_path
            session.commit()

            return jsonify({
                'success': True,
                'sku': sku,
                'process_type': process_type,
                'gcode_path': gcode_path,
                'result': result,
            })

    except Exception as e:
        logger.error(f"Error generating G-code: {e}")
        return jsonify({'error': str(e)}), 500
