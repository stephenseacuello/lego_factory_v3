"""
Engraving API Routes for Flask CNC SCADA
========================================
REST API for text and QR code engraving G-code generation.

Endpoints:
    POST   /api/engraving/text       - Generate text engraving
    POST   /api/engraving/qr         - Generate QR code engraving
    POST   /api/engraving/serial     - Generate serial number
    POST   /api/engraving/trace      - Generate traceability QR
    POST   /api/engraving/combined   - Generate combined serial + QR
    POST   /api/engraving/validate   - Validate engraving fits work area
"""

import logging
from flask import Blueprint, request, jsonify

from services.engraving import get_engraving_service
from services.auth_service import require_auth, require_role

logger = logging.getLogger(__name__)

bp = Blueprint('engraving', __name__, url_prefix='/api/engraving')


@bp.route('/text', methods=['POST'])
@require_auth
def generate_text_engraving():
    """
    Generate G-code for text engraving.

    Request JSON:
        {
            "text": "SERIAL-001",
            "x": 0,
            "y": 0,
            "height": 5.0,
            "depth": 0.3,
            "feed_rate": 300
        }

    Response:
        - 200: G-code generated
        - 400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    text = data.get('text')
    if not text:
        return jsonify({'error': 'text is required'}), 400

    service = get_engraving_service()

    try:
        result = service.generate_text(
            text=text,
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            height=float(data.get('height', 5.0)),
            depth=float(data.get('depth', 0.3)),
            feed_rate=float(data.get('feed_rate', 300)),
        )

        logger.info(f"Text engraving generated: '{text[:20]}...' ({result['line_count']} lines)")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Text engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/qr', methods=['POST'])
@require_auth
def generate_qr_engraving():
    """
    Generate G-code for QR code engraving.

    Request JSON:
        {
            "data": "https://example.com/trace/123",
            "x": 0,
            "y": 0,
            "size": 20.0,
            "depth": 0.3,
            "feed_rate": 500
        }

    Response:
        - 200: G-code generated
        - 400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    qr_data = data.get('data')
    if not qr_data:
        return jsonify({'error': 'data is required'}), 400

    service = get_engraving_service()

    try:
        result = service.generate_qr(
            data=qr_data,
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            size=float(data.get('size', 20.0)),
            depth=float(data.get('depth', 0.3)),
            feed_rate=float(data.get('feed_rate', 500)),
        )

        logger.info(f"QR engraving generated: {qr_data[:30]}... ({result['line_count']} lines)")

        return jsonify(result)

    except Exception as e:
        logger.error(f"QR engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/serial', methods=['POST'])
@require_auth
def generate_serial_engraving():
    """
    Generate serial number engraving.

    Request JSON:
        {
            "prefix": "SN",
            "number": 1000,    // Optional - auto-increment if omitted
            "suffix": "",
            "x": 0,
            "y": 0,
            "height": 5.0,
            "depth": 0.3
        }

    Response:
        - 200: G-code generated with serial number
    """
    data = request.get_json() or {}

    service = get_engraving_service()

    try:
        result = service.generate_serial_number(
            prefix=data.get('prefix', 'SN'),
            number=data.get('number'),  # None for auto-increment
            suffix=data.get('suffix', ''),
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            height=float(data.get('height', 5.0)),
            depth=float(data.get('depth', 0.3)),
        )

        logger.info(f"Serial engraving generated: {result['serial_number']}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Serial engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/date', methods=['POST'])
@require_auth
def generate_date_engraving():
    """
    Generate date code engraving.

    Request JSON:
        {
            "format": "%Y%m%d",   // Python strftime format
            "x": 0,
            "y": 0,
            "height": 3.0,
            "depth": 0.3
        }

    Response:
        - 200: G-code generated with date code
    """
    data = request.get_json() or {}

    service = get_engraving_service()

    try:
        result = service.generate_date_code(
            format_str=data.get('format', '%Y%m%d'),
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            height=float(data.get('height', 3.0)),
            depth=float(data.get('depth', 0.3)),
        )

        logger.info(f"Date engraving generated: {result['date_code']}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Date engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/trace', methods=['POST'])
@require_auth
def generate_trace_qr():
    """
    Generate traceability QR code.

    Request JSON:
        {
            "trace_id": "TR-2025-001234",
            "base_url": "http://localhost:5000/api/traceability",
            "x": 0,
            "y": 0,
            "size": 15.0,
            "depth": 0.3
        }

    Response:
        - 200: G-code generated with trace URL
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    trace_id = data.get('trace_id')
    if not trace_id:
        return jsonify({'error': 'trace_id is required'}), 400

    service = get_engraving_service()

    try:
        result = service.generate_trace_qr(
            trace_id=trace_id,
            base_url=data.get('base_url', 'http://localhost:5000/api/traceability'),
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            size=float(data.get('size', 15.0)),
            depth=float(data.get('depth', 0.3)),
        )

        logger.info(f"Trace QR generated: {trace_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Trace QR error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/combined', methods=['POST'])
@require_auth
def generate_combined_engraving():
    """
    Generate combined serial number and QR code.

    Request JSON:
        {
            "serial": "SN-001234",
            "trace_id": "TR-2025-001234",
            "x": 0,
            "y": 0,
            "serial_height": 4.0,
            "qr_size": 15.0,
            "depth": 0.3,
            "spacing": 5.0
        }

    Response:
        - 200: Combined G-code generated
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    serial = data.get('serial')
    trace_id = data.get('trace_id')

    if not serial or not trace_id:
        return jsonify({'error': 'serial and trace_id are required'}), 400

    service = get_engraving_service()

    try:
        result = service.generate_combined(
            serial=serial,
            trace_id=trace_id,
            x=float(data.get('x', 0)),
            y=float(data.get('y', 0)),
            serial_height=float(data.get('serial_height', 4.0)),
            qr_size=float(data.get('qr_size', 15.0)),
            depth=float(data.get('depth', 0.3)),
            spacing=float(data.get('spacing', 5.0)),
        )

        logger.info(f"Combined engraving generated: {serial} + {trace_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Combined engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/validate', methods=['POST'])
@require_auth
def validate_engraving():
    """
    Validate that engraving fits within machine work area.

    Request JSON:
        {
            "bounds": {"width": 50, "height": 30},
            "position": {"x": 10, "y": 10},
            "machine_limits": {
                "x_min": 0,
                "x_max": 200,
                "y_min": 0,
                "y_max": 200
            }
        }

    Response:
        - 200: Validation result
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    bounds = data.get('bounds', {})
    position = data.get('position', {})
    machine_limits = data.get('machine_limits')

    if not bounds.get('width') or not bounds.get('height'):
        return jsonify({'error': 'bounds (width, height) are required'}), 400

    if 'x' not in position or 'y' not in position:
        return jsonify({'error': 'position (x, y) is required'}), 400

    service = get_engraving_service()

    valid, message = service.validate_engraving_area(
        bounds=bounds,
        position=position,
        machine_limits=machine_limits,
    )

    return jsonify({
        'valid': valid,
        'message': message,
        'bounds': bounds,
        'position': position,
    })


@bp.route('/preview', methods=['POST'])
@require_auth
def preview_engraving():
    """
    Generate preview data for engraving visualization.

    Request JSON:
        {
            "type": "text",  // or "qr"
            "text": "SAMPLE",
            // ... other params
        }

    Response:
        - 200: Preview data with bounds and estimated time
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    engrave_type = data.get('type', 'text')
    service = get_engraving_service()

    try:
        if engrave_type == 'text':
            text = data.get('text', 'PREVIEW')
            result = service.generate_text(
                text=text,
                height=float(data.get('height', 5.0)),
            )
        elif engrave_type == 'qr':
            qr_data = data.get('data', 'https://example.com')
            result = service.generate_qr(
                data=qr_data,
                size=float(data.get('size', 20.0)),
            )
        else:
            return jsonify({'error': f'Unknown type: {engrave_type}'}), 400

        # Return preview without full G-code
        preview = {
            'type': result['type'],
            'bounds': result['bounds'],
            'estimated_time_sec': result['estimated_time_sec'],
            'line_count': result['line_count'],
            'gcode_preview': '\n'.join(result['gcode'].splitlines()[:20]) + '\n...',
        }

        return jsonify(preview)

    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# MCP-Powered Engraving Endpoints
# =============================================================================

def _get_mcp_engraving_service():
    """Get MCP engraving service instance."""
    try:
        from services.engraving_mcp_service import get_engraving_service as get_mcp_service
        return get_mcp_service()
    except ImportError:
        return None


@bp.route('/mcp/text', methods=['POST'])
@require_auth
def create_mcp_text():
    """
    Create text via MCP for engraving.

    Uses Fusion 360 MCP server for precise text vectorization
    when available, with fallback to local stroke font.

    Request JSON:
        {
            "text": "PART-12345",
            "height": 5.0,
            "font": "Arial",
            "position": {"x": 10, "y": 10},
            "alignment": "left"
        }

    Response:
        - 200: Text profile created
        - 400: Invalid request
        - 500: Server error
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    text = data.get('text')
    if not text:
        return jsonify({'error': 'text is required'}), 400

    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        from services.engraving_mcp_service import Point2D, TextAlignment

        position = data.get('position')
        pos = Point2D(position['x'], position['y']) if position else None

        alignment_str = data.get('alignment', 'left')
        alignment = TextAlignment(alignment_str)

        profile = service.create_text_profile(
            text=text,
            height=float(data.get('height', 5.0)),
            position=pos,
            font=data.get('font'),
            alignment=alignment
        )

        result = service.get_profile(profile.profile_id)
        logger.info(f"MCP text profile created: {profile.profile_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"MCP text creation error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/mcp/engrave', methods=['POST'])
@require_auth
def mcp_engrave():
    """
    Engrave text using MCP with CAM.

    Supports multiple engraving styles:
    - line: Single pass line engraving
    - v_carve: Variable depth V-carving
    - pocket: Clear inside of letters
    - outline: Trace around letters

    Request JSON:
        {
            "profile_id": "text_xxx",
            "style": "v_carve",
            "depth": 0.5,
            "feed_rate": 500,
            "v_bit_angle": 60,
            "tool_diameter": 3.0
        }

    Response:
        - 200: G-code generated
        - 400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    profile_id = data.get('profile_id')
    if not profile_id:
        return jsonify({'error': 'profile_id is required'}), 400

    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        style = data.get('style', 'line')
        depth = float(data.get('depth', 0.5))
        feed_rate = data.get('feed_rate')
        v_bit_angle = float(data.get('v_bit_angle', 60))
        tool_diameter = data.get('tool_diameter')

        # Call appropriate method based on style
        if style == 'line':
            result = service.engrave_to_depth(profile_id, depth, feed_rate)
        elif style == 'v_carve':
            result = service.generate_v_carve_gcode(profile_id, v_bit_angle, depth, feed_rate)
        elif style == 'pocket':
            if not tool_diameter:
                return jsonify({'error': 'tool_diameter required for pocket'}), 400
            result = service.pocket_text(profile_id, depth, float(tool_diameter), feed_rate=feed_rate)
        elif style == 'outline':
            if not tool_diameter:
                return jsonify({'error': 'tool_diameter required for outline'}), 400
            result = service.outline_text(profile_id, depth, float(tool_diameter), feed_rate)
        else:
            return jsonify({'error': f'Unknown style: {style}'}), 400

        logger.info(f"MCP engraving generated: {profile_id} ({style})")

        return jsonify({
            'success': result.success,
            'profile_id': result.profile_id,
            'style': result.style.value,
            'gcode': result.gcode,
            'toolpath_length': result.toolpath_length,
            'estimated_time_seconds': result.estimated_time_seconds,
            'error': result.error
        })

    except Exception as e:
        logger.error(f"MCP engrave error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/mcp/fonts', methods=['GET'])
@require_auth
def get_mcp_fonts():
    """
    Get available fonts from MCP/Fusion 360.

    Response:
        - 200: List of available fonts
    """
    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        fonts = service.get_available_fonts()
        return jsonify({'fonts': fonts, 'count': len(fonts)})
    except Exception as e:
        logger.error(f"Get fonts error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/serial-number', methods=['POST'])
@require_auth
def generate_serial_number_template():
    """
    Generate engraving from serial number template.

    Auto-increments serial numbers and supports
    multiple engraving positions.

    Request JSON:
        {
            "prefix": "SN-",
            "start_number": 1001,
            "padding": 5,
            "positions": [
                {"x": 10, "y": 10},
                {"x": 10, "y": 30}
            ],
            "height": 3.0,
            "depth": 0.3,
            "style": "line"
        }

    Response:
        - 200: G-code with serial numbers
    """
    data = request.get_json() or {}

    service = _get_mcp_engraving_service()
    if not service:
        # Fallback to basic service
        return generate_serial_engraving()

    try:
        prefix = data.get('prefix', 'SN-')
        start_number = data.get('start_number', 1)
        padding = data.get('padding', 5)
        positions = data.get('positions', [{"x": 0, "y": 0}])
        height = float(data.get('height', 3.0))
        depth = float(data.get('depth', 0.3))
        style = data.get('style', 'line')

        # Create template
        template_id = f"serial_{prefix.strip('-')}"
        template = service.create_template(
            template_id=template_id,
            prefix=prefix,
            start_number=start_number,
            padding=padding
        )

        all_gcode = []
        generated_serials = []

        from services.engraving_mcp_service import Point2D

        for pos in positions:
            # Generate serial number
            serial = service.apply_template(template_id)
            generated_serials.append(serial)

            # Create text profile
            position = Point2D(pos['x'], pos['y'])
            profile = service.create_text_profile(
                text=serial,
                height=height,
                position=position
            )

            # Generate engraving
            if style == 'v_carve':
                v_angle = float(data.get('v_bit_angle', 60))
                result = service.generate_v_carve_gcode(profile.profile_id, v_angle, depth)
            else:
                result = service.engrave_to_depth(profile.profile_id, depth)

            if result.success:
                all_gcode.append(f"; Serial: {serial}")
                all_gcode.append(result.gcode)

        logger.info(f"Serial numbers generated: {generated_serials}")

        return jsonify({
            'success': True,
            'serial_numbers': generated_serials,
            'gcode': '\n'.join(all_gcode),
            'count': len(generated_serials)
        })

    except Exception as e:
        logger.error(f"Serial number template error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/qr-code', methods=['POST'])
@require_auth
def generate_qr_code_engraving():
    """
    Generate QR code engraving (enhanced endpoint).

    Request JSON:
        {
            "data": "https://example.com/part/12345",
            "size": 15.0,
            "position": {"x": 100, "y": 10},
            "error_correction": "M",
            "depth": 0.2,
            "style": "pocket"
        }

    Response:
        - 200: G-code for QR code
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    qr_data = data.get('data')
    if not qr_data:
        return jsonify({'error': 'data is required'}), 400

    # Use basic QR service for now
    # MCP integration would generate vectorized QR in Fusion
    service = get_engraving_service()

    try:
        position = data.get('position', {"x": 0, "y": 0})

        result = service.generate_qr(
            data=qr_data,
            x=float(position.get('x', 0)),
            y=float(position.get('y', 0)),
            size=float(data.get('size', 15.0)),
            depth=float(data.get('depth', 0.2)),
            feed_rate=float(data.get('feed_rate', 500)),
        )

        logger.info(f"QR code engraving generated: {qr_data[:30]}...")

        return jsonify(result)

    except Exception as e:
        logger.error(f"QR code error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/barcode', methods=['POST'])
@require_auth
def generate_barcode_engraving():
    """
    Generate barcode engraving.

    Request JSON:
        {
            "data": "123456789012",
            "type": "code128",
            "width": 50.0,
            "height": 10.0,
            "position": {"x": 0, "y": 0},
            "depth": 0.2
        }

    Response:
        - 200: G-code for barcode
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    barcode_data = data.get('data')
    if not barcode_data:
        return jsonify({'error': 'data is required'}), 400

    # Barcode support would need additional library
    # For now, return placeholder
    return jsonify({
        'success': False,
        'error': 'Barcode support requires additional library installation',
        'message': 'Use QR code endpoint for machine-readable marking'
    }), 501


@bp.route('/pattern', methods=['POST'])
@require_auth
def apply_pattern_to_engraving():
    """
    Apply a pattern to engraving (repeat at multiple locations).

    Request JSON:
        {
            "profile_id": "text_xxx",
            "pattern_type": "rectangular",
            "pattern_params": {
                "x_count": 2,
                "y_count": 3,
                "x_spacing": 50,
                "y_spacing": 30
            },
            "depth": 0.3,
            "style": "line"
        }

    Response:
        - 200: G-code for patterned engravings
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    profile_id = data.get('profile_id')
    pattern_type = data.get('pattern_type', 'rectangular')
    pattern_params = data.get('pattern_params', {})

    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        from services.pattern_mcp_service import get_pattern_service, Point2D
        pattern_service = get_pattern_service()

        # Create pattern
        if pattern_type == 'rectangular':
            result = pattern_service.create_rectangular_pattern(
                source_feature_id=profile_id,
                x_count=pattern_params.get('x_count', 2),
                y_count=pattern_params.get('y_count', 2),
                x_spacing=pattern_params.get('x_spacing', 25),
                y_spacing=pattern_params.get('y_spacing', 25)
            )
        elif pattern_type == 'circular':
            center = pattern_params.get('center', {'x': 50, 'y': 50})
            result = pattern_service.create_circular_pattern(
                source_feature_id=profile_id,
                center=Point2D(center['x'], center['y']),
                count=pattern_params.get('count', 4),
                radius=pattern_params.get('radius', 30)
            )
        else:
            return jsonify({'error': f'Unknown pattern type: {pattern_type}'}), 400

        if not result.success:
            return jsonify({'error': result.error}), 400

        # Generate engraving for original profile
        depth = float(data.get('depth', 0.3))
        style = data.get('style', 'line')

        if style == 'v_carve':
            engrave_result = service.generate_v_carve_gcode(
                profile_id, data.get('v_bit_angle', 60), depth
            )
        else:
            engrave_result = service.engrave_to_depth(profile_id, depth)

        if not engrave_result.success:
            return jsonify({'error': engrave_result.error}), 400

        # Apply pattern to G-code
        pattern_gcode = pattern_service.generate_pattern_gcode(
            result.pattern_id,
            engrave_result.gcode
        )

        logger.info(f"Pattern engraving: {result.instance_count} instances")

        return jsonify({
            'success': True,
            'pattern_id': result.pattern_id,
            'instance_count': result.instance_count,
            'gcode': pattern_gcode
        })

    except Exception as e:
        logger.error(f"Pattern engraving error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/mcp/profiles', methods=['GET'])
@require_auth
def list_mcp_profiles():
    """
    List all text profiles.

    Response:
        - 200: List of profiles
    """
    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        profiles = service.list_profiles()
        return jsonify({'profiles': profiles, 'count': len(profiles)})
    except Exception as e:
        logger.error(f"List profiles error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/mcp/profiles/<profile_id>', methods=['DELETE'])
@require_auth
def delete_mcp_profile(profile_id):
    """
    Delete a text profile.

    Response:
        - 200: Profile deleted
        - 404: Profile not found
    """
    service = _get_mcp_engraving_service()
    if not service:
        return jsonify({'error': 'MCP engraving service not available'}), 500

    try:
        deleted = service.delete_profile(profile_id)
        if deleted:
            return jsonify({'success': True, 'message': 'Profile deleted'})
        else:
            return jsonify({'error': 'Profile not found'}), 404
    except Exception as e:
        logger.error(f"Delete profile error: {e}")
        return jsonify({'error': str(e)}), 500
