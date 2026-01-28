"""
MTConnect REST API Routes
=========================
Exposes MTConnect-compliant REST endpoints for device data.

Standard MTConnect endpoints:
- GET /mtconnect/probe - Device metadata and data item definitions
- GET /mtconnect/current - Current values of all data items
- GET /mtconnect/sample - Historical sample stream

Additional JSON endpoints:
- GET /mtconnect/probe/json - Probe response as JSON
- GET /mtconnect/current/json - Current values as JSON
- GET /mtconnect/sample/json - Sample stream as JSON
- GET /mtconnect/status - Agent status information

Reference: MTConnect Standard v2.0 - REST Protocol
"""

import logging
from flask import Blueprint, Response, jsonify, request

from services.mtconnect import get_mtconnect_agent, get_mtconnect_adapter

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('mtconnect', __name__, url_prefix='/mtconnect')


# =============================================================================
# Standard MTConnect XML Endpoints
# =============================================================================

@bp.route('/probe')
def probe():
    """
    MTConnect Probe request - device metadata.

    Returns XML document describing the device structure and
    all available data items per MTConnect specification.

    Returns:
        XML: MTConnectDevices document
    """
    try:
        agent = get_mtconnect_agent()
        xml_response = agent.probe()
        return Response(
            xml_response,
            mimetype='application/xml',
            headers={'Content-Type': 'application/xml; charset=utf-8'}
        )
    except Exception as e:
        logger.error(f"MTConnect probe error: {e}")
        agent = get_mtconnect_agent()
        return Response(
            agent.error("INTERNAL_ERROR", str(e)),
            mimetype='application/xml',
            status=500
        )


@bp.route('/current')
def current():
    """
    MTConnect Current request - latest data item values.

    Query Parameters:
        path: Filter by data item path (optional)
        at: Sequence number to retrieve values at (optional)

    Returns:
        XML: MTConnectStreams document with current values
    """
    try:
        path = request.args.get('path')
        at_seq = request.args.get('at', type=int)

        agent = get_mtconnect_agent()
        xml_response = agent.current(path=path, at=at_seq)
        return Response(
            xml_response,
            mimetype='application/xml',
            headers={'Content-Type': 'application/xml; charset=utf-8'}
        )
    except Exception as e:
        logger.error(f"MTConnect current error: {e}")
        agent = get_mtconnect_agent()
        return Response(
            agent.error("INTERNAL_ERROR", str(e)),
            mimetype='application/xml',
            status=500
        )


@bp.route('/sample')
def sample():
    """
    MTConnect Sample request - historical data stream.

    Query Parameters:
        from: Starting sequence number (default: first in buffer)
        count: Maximum samples to return (default: 100, max: 10000)
        path: Filter by data item path (optional)

    Returns:
        XML: MTConnectStreams document with historical samples
    """
    try:
        from_seq = request.args.get('from', type=int)
        count = request.args.get('count', default=100, type=int)
        path = request.args.get('path')

        # Limit count to prevent memory issues
        count = min(count, 10000)

        agent = get_mtconnect_agent()
        xml_response = agent.sample(from_seq=from_seq, count=count, path=path)
        return Response(
            xml_response,
            mimetype='application/xml',
            headers={'Content-Type': 'application/xml; charset=utf-8'}
        )
    except Exception as e:
        logger.error(f"MTConnect sample error: {e}")
        agent = get_mtconnect_agent()
        return Response(
            agent.error("INTERNAL_ERROR", str(e)),
            mimetype='application/xml',
            status=500
        )


# =============================================================================
# JSON Endpoints (Non-standard but useful)
# =============================================================================

@bp.route('/probe/json')
def probe_json():
    """
    MTConnect Probe as JSON (non-standard).

    Returns device metadata in JSON format for easier
    integration with web applications.

    Returns:
        JSON: Device structure and data items
    """
    try:
        agent = get_mtconnect_agent()
        return jsonify(agent.probe_json())
    except Exception as e:
        logger.error(f"MTConnect probe JSON error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/current/json')
def current_json():
    """
    MTConnect Current as JSON (non-standard).

    Query Parameters:
        path: Filter by data item path (optional)

    Returns:
        JSON: Current data item values
    """
    try:
        path = request.args.get('path')
        agent = get_mtconnect_agent()
        return jsonify(agent.current_json(path=path))
    except Exception as e:
        logger.error(f"MTConnect current JSON error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/sample/json')
def sample_json():
    """
    MTConnect Sample as JSON (non-standard).

    Query Parameters:
        from: Starting sequence number
        count: Maximum samples (default: 100, max: 10000)
        path: Filter by data item path (optional)

    Returns:
        JSON: Historical samples
    """
    try:
        from_seq = request.args.get('from', type=int)
        count = request.args.get('count', default=100, type=int)
        path = request.args.get('path')

        count = min(count, 10000)

        agent = get_mtconnect_agent()
        return jsonify(agent.sample_json(from_seq=from_seq, count=count, path=path))
    except Exception as e:
        logger.error(f"MTConnect sample JSON error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Status and Info Endpoints
# =============================================================================

@bp.route('/status')
def status():
    """
    MTConnect Agent status information.

    Returns:
        JSON: Agent status including buffer state and sequence numbers
    """
    try:
        adapter = get_mtconnect_adapter()
        agent = get_mtconnect_agent()

        return jsonify({
            "status": "running",
            "agent": {
                "sender": agent.sender,
                "version": agent.version,
            },
            "device": {
                "id": adapter.device_id,
                "name": adapter.device.name,
                "uuid": adapter.device.uuid,
                "data_items_count": len(adapter._data_items),
            },
            "buffer": {
                "size": adapter.buffer_size,
                "used": len(adapter._buffer),
                "first_sequence": adapter.get_first_sequence(),
                "last_sequence": adapter.get_current_sequence(),
                "instance_id": adapter.instance_id,
            }
        })
    except Exception as e:
        logger.error(f"MTConnect status error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/data-items')
def data_items():
    """
    List all data items with current values.

    Query Parameters:
        category: Filter by category (SAMPLE, EVENT, CONDITION)

    Returns:
        JSON: List of data items with current values
    """
    try:
        category_filter = request.args.get('category', '').upper()
        adapter = get_mtconnect_adapter()
        items = adapter.get_current_values()

        result = []
        for item_id, item in items.items():
            if category_filter and item.category.value != category_filter:
                continue
            # Convert enum types to their string values for JSON serialization
            item_type = item.type.value if hasattr(item.type, 'value') else str(item.type)
            result.append({
                "id": item.id,
                "name": item.name,
                "category": item.category.value,
                "type": item_type,
                "units": item.units,
                "value": item.value,
                "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                "sequence": item.sequence,
            })

        return jsonify({
            "count": len(result),
            "data_items": result
        })
    except Exception as e:
        logger.error(f"MTConnect data-items error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/sequences')
def sequences():
    """
    Get sequence number information for streaming.

    Useful for clients implementing MTConnect streaming
    to determine where to start polling.

    Returns:
        JSON: Sequence number information
    """
    try:
        adapter = get_mtconnect_adapter()
        return jsonify({
            "first_sequence": adapter.get_first_sequence(),
            "last_sequence": adapter.get_current_sequence(),
            "next_sequence": adapter.get_current_sequence() + 1,
            "buffer_size": adapter.buffer_size,
            "instance_id": adapter.instance_id,
        })
    except Exception as e:
        logger.error(f"MTConnect sequences error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Device-specific Endpoints
# =============================================================================

@bp.route('/position')
def position():
    """
    Get current machine position (convenience endpoint).

    Returns:
        JSON: X, Y, Z work and machine positions
    """
    try:
        adapter = get_mtconnect_adapter()
        items = adapter.get_current_values()

        device_id = adapter.device_id
        return jsonify({
            "work_position": {
                "x": items.get(f"{device_id}_xpos", {}).value if f"{device_id}_xpos" in items else None,
                "y": items.get(f"{device_id}_ypos", {}).value if f"{device_id}_ypos" in items else None,
                "z": items.get(f"{device_id}_zpos", {}).value if f"{device_id}_zpos" in items else None,
            },
            "machine_position": {
                "x": items.get(f"{device_id}_xmpos", {}).value if f"{device_id}_xmpos" in items else None,
                "y": items.get(f"{device_id}_ympos", {}).value if f"{device_id}_ympos" in items else None,
                "z": items.get(f"{device_id}_zmpos", {}).value if f"{device_id}_zmpos" in items else None,
            },
            "timestamp": items.get(f"{device_id}_xpos", {}).timestamp.isoformat()
            if f"{device_id}_xpos" in items and items.get(f"{device_id}_xpos").timestamp else None,
        })
    except Exception as e:
        logger.error(f"MTConnect position error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/execution')
def execution():
    """
    Get current execution state (convenience endpoint).

    Returns:
        JSON: Execution state, mode, program, and line
    """
    try:
        adapter = get_mtconnect_adapter()
        items = adapter.get_current_values()

        device_id = adapter.device_id
        return jsonify({
            "execution": items.get(f"{device_id}_exec", {}).value if f"{device_id}_exec" in items else None,
            "mode": items.get(f"{device_id}_mode", {}).value if f"{device_id}_mode" in items else None,
            "program": items.get(f"{device_id}_pgm", {}).value if f"{device_id}_pgm" in items else None,
            "line": items.get(f"{device_id}_line", {}).value if f"{device_id}_line" in items else None,
            "availability": items.get(f"{device_id}_avail", {}).value if f"{device_id}_avail" in items else None,
        })
    except Exception as e:
        logger.error(f"MTConnect execution error: {e}")
        return jsonify({"error": str(e)}), 500
