"""
LEGO Factory v3 - Level 1 PLC API Routes
==========================================
REST API for fine-grained machine control.

SECURITY: All routes require JWT authentication as they control physical equipment.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import logging

logger = logging.getLogger(__name__)

plc_api_bp = Blueprint('plc_api', __name__, url_prefix='/api/plc')


def get_plc(machine_id: str):
    """Get PLC controller for a machine."""
    from services.scada.plc import get_plc_controller
    import json
    from pathlib import Path

    # Get controller type from config
    config_path = Path(__file__).parent.parent.parent / 'config' / 'machines.json'
    controller_type = 'grbl'

    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
            for m in config.get('machines', []):
                if m['machine_id'] == machine_id:
                    controller_type = m.get('controller_type', 'grbl')
                    break

    return get_plc_controller(machine_id, controller_type)


# ============================================================================
# STATUS
# ============================================================================

@plc_api_bp.route('/<machine_id>/status', methods=['GET'])
@jwt_required()
def get_plc_status(machine_id: str):
    """Get PLC controller status."""
    try:
        plc = get_plc(machine_id)
        return jsonify(plc.get_status())
    except Exception as e:
        logger.warning(f"PLC service not available: {e}")
        return jsonify({
            'machine_id': machine_id,
            'status': 'demo',
            'current_wcs': 'G54',
            'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'spindle_rpm': 0,
            'feed_rate': 0,
            'tool_number': 1,
            'demo': True,
        })


# ============================================================================
# WORK COORDINATE SYSTEMS (WCS)
# ============================================================================

@plc_api_bp.route('/<machine_id>/wcs', methods=['GET'])
@jwt_required()
def list_wcs(machine_id: str):
    """List all WCS offsets."""
    plc = get_plc(machine_id)
    return jsonify({
        'current_wcs': plc.current_wcs.value,
        'offsets': plc.get_all_wcs_offsets()
    })


@plc_api_bp.route('/<machine_id>/wcs/<wcs_name>', methods=['GET'])
@jwt_required()
def get_wcs(machine_id: str, wcs_name: str):
    """Get specific WCS offset."""
    from services.scada.plc import WCS

    plc = get_plc(machine_id)

    try:
        wcs = WCS(wcs_name.upper())
        offset = plc.get_wcs_offset(wcs)
        return jsonify(offset.to_dict())
    except ValueError:
        return jsonify({'error': f'Invalid WCS: {wcs_name}'}), 400


@plc_api_bp.route('/<machine_id>/wcs/<wcs_name>/set', methods=['POST'])
@jwt_required()
def set_wcs(machine_id: str, wcs_name: str):
    """Switch to a WCS."""
    from services.scada.plc import WCS

    plc = get_plc(machine_id)

    try:
        wcs = WCS(wcs_name.upper())
        if plc.set_wcs(wcs):
            return jsonify({'success': True, 'wcs': wcs.value})
        return jsonify({'success': False, 'error': 'Failed to set WCS'}), 500
    except ValueError:
        return jsonify({'error': f'Invalid WCS: {wcs_name}'}), 400


@plc_api_bp.route('/<machine_id>/wcs/<wcs_name>/offset', methods=['POST'])
@jwt_required()
def set_wcs_offset(machine_id: str, wcs_name: str):
    """Set WCS offset values."""
    from services.scada.plc import WCS, Position

    plc = get_plc(machine_id)
    data = request.get_json() or {}

    try:
        wcs = WCS(wcs_name.upper())
        offset = Position(
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0),
            a=data.get('a', 0.0),
            b=data.get('b', 0.0),
            c=data.get('c', 0.0)
        )

        if plc.set_wcs_offset(wcs, offset, data.get('description', '')):
            return jsonify({'success': True, 'wcs': wcs.value, 'offset': offset.to_dict()})
        return jsonify({'success': False, 'error': 'Failed to set offset'}), 500
    except ValueError:
        return jsonify({'error': f'Invalid WCS: {wcs_name}'}), 400


@plc_api_bp.route('/<machine_id>/wcs/<wcs_name>/zero', methods=['POST'])
@jwt_required()
def zero_wcs(machine_id: str, wcs_name: str):
    """Zero WCS at current position."""
    from services.scada.plc import WCS

    plc = get_plc(machine_id)
    data = request.get_json() or {}
    axes = data.get('axes', 'XYZ')

    try:
        wcs = WCS(wcs_name.upper()) if wcs_name.upper() != 'CURRENT' else None
        if plc.zero_wcs(wcs, axes):
            return jsonify({'success': True, 'message': f'Zeroed {axes} in {wcs_name}'})
        return jsonify({'success': False, 'error': 'Failed to zero'}), 500
    except ValueError:
        return jsonify({'error': f'Invalid WCS: {wcs_name}'}), 400


# ============================================================================
# PROBING
# ============================================================================

@plc_api_bp.route('/<machine_id>/probe/z', methods=['POST'])
@jwt_required()
def probe_z(machine_id: str):
    """Probe Z axis (touch off)."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}
    feed_rate = data.get('feed_rate')
    max_distance = data.get('max_distance', 50.0)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(plc.probe_z(feed_rate, max_distance))
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@plc_api_bp.route('/<machine_id>/probe/tool-length', methods=['POST'])
@jwt_required()
def probe_tool_length(machine_id: str):
    """Probe tool length."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}

    tool_setter_z = data.get('tool_setter_z')
    if tool_setter_z is None:
        return jsonify({'error': 'tool_setter_z required'}), 400

    feed_rate = data.get('feed_rate')

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(plc.probe_tool_length(tool_setter_z, feed_rate))
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@plc_api_bp.route('/<machine_id>/probe/edge-x', methods=['POST'])
@jwt_required()
def probe_edge_x(machine_id: str):
    """Probe X edge."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}
    direction = data.get('direction', 1)
    feed_rate = data.get('feed_rate')
    max_distance = data.get('max_distance', 25.0)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(plc.probe_edge_x(direction, feed_rate, max_distance))
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@plc_api_bp.route('/<machine_id>/probe/edge-y', methods=['POST'])
@jwt_required()
def probe_edge_y(machine_id: str):
    """Probe Y edge."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}
    direction = data.get('direction', 1)
    feed_rate = data.get('feed_rate')
    max_distance = data.get('max_distance', 25.0)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(plc.probe_edge_y(direction, feed_rate, max_distance))
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@plc_api_bp.route('/<machine_id>/probe/corner', methods=['POST'])
@jwt_required()
def probe_corner(machine_id: str):
    """Probe corner to find X and Y."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}
    corner = data.get('corner', 'front_left')
    feed_rate = data.get('feed_rate')

    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(plc.probe_corner(corner, feed_rate))
        return jsonify({
            'x': results.get('x', {}).to_dict() if results.get('x') else None,
            'y': results.get('y', {}).to_dict() if results.get('y') else None,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@plc_api_bp.route('/<machine_id>/probe/center-x', methods=['POST'])
@jwt_required()
def probe_center_x(machine_id: str):
    """Probe to find center in X."""
    import asyncio

    plc = get_plc(machine_id)
    data = request.get_json() or {}

    expected_width = data.get('expected_width')
    if expected_width is None:
        return jsonify({'error': 'expected_width required'}), 400

    feed_rate = data.get('feed_rate')

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(plc.probe_center_x(expected_width, feed_rate))
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


# ============================================================================
# TOOL MANAGEMENT
# ============================================================================

@plc_api_bp.route('/<machine_id>/tools', methods=['GET'])
@jwt_required()
def list_tools(machine_id: str):
    """List all tools in tool table."""
    plc = get_plc(machine_id)
    return jsonify({
        'current_tool': plc._current_tool,
        'tools': plc.get_tool_table()
    })


@plc_api_bp.route('/<machine_id>/tools/<int:tool_number>', methods=['GET'])
@jwt_required()
def get_tool(machine_id: str, tool_number: int):
    """Get tool offset."""
    plc = get_plc(machine_id)
    tool = plc.get_tool_offset(tool_number)

    if tool:
        return jsonify(tool.to_dict())
    return jsonify({'error': 'Tool not found'}), 404


@plc_api_bp.route('/<machine_id>/tools/<int:tool_number>', methods=['POST', 'PUT'])
@jwt_required()
def set_tool(machine_id: str, tool_number: int):
    """Set tool offset."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}

    if plc.set_tool_offset(
        tool_number,
        length_offset=data.get('length_offset'),
        diameter=data.get('diameter'),
        x_offset=data.get('x_offset'),
        y_offset=data.get('y_offset'),
        description=data.get('description')
    ):
        return jsonify({'success': True, 'tool': plc.get_tool_offset(tool_number).to_dict()})
    return jsonify({'success': False, 'error': 'Failed to set tool'}), 500


@plc_api_bp.route('/<machine_id>/tools/<int:tool_number>/change', methods=['POST'])
@jwt_required()
def change_tool(machine_id: str, tool_number: int):
    """Execute tool change."""
    plc = get_plc(machine_id)

    if plc.tool_change(tool_number):
        return jsonify({'success': True, 'current_tool': tool_number})
    return jsonify({'success': False, 'error': 'Tool change failed'}), 500


# ============================================================================
# DATUM MANAGEMENT
# ============================================================================

@plc_api_bp.route('/<machine_id>/datums', methods=['GET'])
@jwt_required()
def list_datums(machine_id: str):
    """List all saved datums."""
    plc = get_plc(machine_id)
    return jsonify({'datums': plc.list_datums()})


@plc_api_bp.route('/<machine_id>/datums/<name>', methods=['GET'])
@jwt_required()
def get_datum(machine_id: str, name: str):
    """Get a specific datum."""
    plc = get_plc(machine_id)
    datum = plc.get_datum(name)

    if datum:
        return jsonify(datum.to_dict())
    return jsonify({'error': 'Datum not found'}), 404


@plc_api_bp.route('/<machine_id>/datums/<name>', methods=['POST', 'PUT'])
@jwt_required()
def save_datum(machine_id: str, name: str):
    """Save current position as a datum."""
    from services.scada.plc import Position

    plc = get_plc(machine_id)
    data = request.get_json() or {}

    position = None
    if 'x' in data or 'y' in data or 'z' in data:
        position = Position(
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0),
            a=data.get('a', 0.0),
            b=data.get('b', 0.0),
            c=data.get('c', 0.0)
        )

    datum = plc.save_datum(name, position, data.get('description', ''))
    return jsonify({'success': True, 'datum': datum.to_dict()})


@plc_api_bp.route('/<machine_id>/datums/<name>', methods=['DELETE'])
@jwt_required()
def delete_datum(machine_id: str, name: str):
    """Delete a datum."""
    plc = get_plc(machine_id)

    if plc.delete_datum(name):
        return jsonify({'success': True})
    return jsonify({'error': 'Datum not found'}), 404


@plc_api_bp.route('/<machine_id>/datums/<name>/goto', methods=['POST'])
@jwt_required()
def goto_datum(machine_id: str, name: str):
    """Move to a saved datum."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    feed_rate = data.get('feed_rate')

    if plc.go_to_datum(name, feed_rate):
        return jsonify({'success': True, 'message': f'Moving to datum {name}'})
    return jsonify({'success': False, 'error': 'Failed to go to datum'}), 500


# ============================================================================
# SPINDLE & COOLANT
# ============================================================================

@plc_api_bp.route('/<machine_id>/spindle/on', methods=['POST'])
@jwt_required()
def spindle_on(machine_id: str):
    """Turn spindle on."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    speed = data.get('speed', 1000)
    direction = data.get('direction', 'cw')

    if plc.spindle_on(speed, direction):
        return jsonify({'success': True, 'speed': speed, 'direction': direction})
    return jsonify({'success': False, 'error': 'Failed to start spindle'}), 500


@plc_api_bp.route('/<machine_id>/spindle/off', methods=['POST'])
@jwt_required()
def spindle_off(machine_id: str):
    """Turn spindle off."""
    plc = get_plc(machine_id)

    if plc.spindle_off():
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to stop spindle'}), 500


@plc_api_bp.route('/<machine_id>/coolant/on', methods=['POST'])
@jwt_required()
def coolant_on(machine_id: str):
    """Turn coolant on."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    mode = data.get('mode', 'flood')

    if plc.coolant_on(mode):
        return jsonify({'success': True, 'mode': mode})
    return jsonify({'success': False, 'error': 'Failed to start coolant'}), 500


@plc_api_bp.route('/<machine_id>/coolant/off', methods=['POST'])
@jwt_required()
def coolant_off(machine_id: str):
    """Turn coolant off."""
    plc = get_plc(machine_id)

    if plc.coolant_off():
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to stop coolant'}), 500


# ============================================================================
# OVERRIDES
# ============================================================================

@plc_api_bp.route('/<machine_id>/overrides', methods=['GET'])
@jwt_required()
def get_overrides(machine_id: str):
    """Get current override values."""
    plc = get_plc(machine_id)
    return jsonify({
        'feed_override': plc._feed_override,
        'rapid_override': plc._rapid_override,
        'spindle_override': plc._spindle_override,
    })


@plc_api_bp.route('/<machine_id>/overrides', methods=['POST'])
@jwt_required()
def set_overrides(machine_id: str):
    """Set override values."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}

    if 'feed' in data:
        plc.set_feed_override(int(data['feed']))
    if 'rapid' in data:
        plc.set_rapid_override(int(data['rapid']))
    if 'spindle' in data:
        plc.set_spindle_override(int(data['spindle']))

    return jsonify({
        'success': True,
        'feed_override': plc._feed_override,
        'rapid_override': plc._rapid_override,
        'spindle_override': plc._spindle_override,
    })


# ============================================================================
# SENSORS & DATA COLLECTION
# ============================================================================

@plc_api_bp.route('/<machine_id>/sensors', methods=['GET'])
@jwt_required()
def list_sensors(machine_id: str):
    """List all registered sensors."""
    plc = get_plc(machine_id)
    return jsonify({'sensors': plc.get_all_sensors()})


@plc_api_bp.route('/<machine_id>/sensors/<sensor_id>', methods=['GET'])
@jwt_required()
def get_sensor(machine_id: str, sensor_id: str):
    """Get sensor reading."""
    plc = get_plc(machine_id)
    reading = plc.get_sensor_reading(sensor_id)

    if reading:
        return jsonify(reading.to_dict())
    return jsonify({'error': 'Sensor not found'}), 404


@plc_api_bp.route('/<machine_id>/sensors/<sensor_id>', methods=['POST'])
@jwt_required()
def register_sensor(machine_id: str, sensor_id: str):
    """Register a sensor."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}

    sensor_type = data.get('sensor_type', 'generic')
    unit = data.get('unit', '')

    plc.register_sensor(sensor_id, sensor_type, unit)
    return jsonify({'success': True, 'sensor_id': sensor_id})


@plc_api_bp.route('/<machine_id>/sensors/<sensor_id>/update', methods=['POST'])
@jwt_required()
def update_sensor(machine_id: str, sensor_id: str):
    """Update sensor reading."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}

    value = data.get('value')
    if value is None:
        return jsonify({'error': 'value required'}), 400

    quality = data.get('quality', 'good')
    plc.update_sensor(sensor_id, float(value), quality)
    return jsonify({'success': True})


@plc_api_bp.route('/<machine_id>/data-collection/start', methods=['POST'])
@jwt_required()
def start_data_collection(machine_id: str):
    """Start data collection."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    interval = data.get('interval', 0.1)

    plc.start_data_collection(interval)
    return jsonify({'success': True, 'interval': interval})


@plc_api_bp.route('/<machine_id>/data-collection/stop', methods=['POST'])
@jwt_required()
def stop_data_collection(machine_id: str):
    """Stop data collection and get data."""
    plc = get_plc(machine_id)
    data = plc.stop_data_collection()
    return jsonify({'success': True, 'samples': len(data), 'data': data})


@plc_api_bp.route('/<machine_id>/data-collection/export', methods=['POST'])
@jwt_required()
def export_data(machine_id: str):
    """Export collected data to file."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    filepath = data.get('filepath', f'/tmp/{machine_id}_data.json')

    if plc.export_collected_data(filepath):
        return jsonify({'success': True, 'filepath': filepath})
    return jsonify({'success': False, 'error': 'Export failed'}), 500


# ============================================================================
# G-CODE EXECUTION
# ============================================================================

@plc_api_bp.route('/<machine_id>/gcode', methods=['POST'])
@jwt_required()
def send_gcode(machine_id: str):
    """Send G-code command."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    gcode = data.get('gcode', '')

    if not gcode:
        return jsonify({'error': 'gcode required'}), 400

    success, response = plc.send_gcode_sync(gcode)
    return jsonify({'success': success, 'response': response})


@plc_api_bp.route('/<machine_id>/gcode/batch', methods=['POST'])
@jwt_required()
def send_gcode_batch(machine_id: str):
    """Send multiple G-code commands."""
    plc = get_plc(machine_id)
    data = request.get_json() or {}
    commands = data.get('commands', [])

    if not commands:
        return jsonify({'error': 'commands required'}), 400

    results = []
    for cmd in commands:
        success, response = plc.send_gcode_sync(cmd)
        results.append({'gcode': cmd, 'success': success, 'response': response})

        if not success and data.get('stop_on_error', True):
            break

    return jsonify({'results': results})
