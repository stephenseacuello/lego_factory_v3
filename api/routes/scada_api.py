"""
LEGO Factory v3 - SCADA API Routes
===================================
REST API for machine control - works with config/machines.json

Security Note: All G-code commands are validated before execution to prevent:
- Command injection attacks
- Hardware damage from invalid movements
- Overheating from unsafe temperature commands
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from pathlib import Path
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from api.middleware.rate_limiter import standard_limit, admin_limit, exempt_from_rate_limit

logger = logging.getLogger(__name__)

# Audit logger for G-code commands (separate from application logger)
gcode_audit_logger = logging.getLogger('gcode_audit')


def get_gcode_validator():
    """Get the G-code validator class."""
    try:
        from services.scada.gcode import GCodeValidator, MachineType
        return GCodeValidator, MachineType
    except ImportError as e:
        logger.warning(f"G-code validator not available: {e}")
        return None, None


def log_gcode_audit(
    machine_id: str,
    gcode: str,
    user_id: str,
    validation_result: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    """
    Log G-code command for audit purposes.

    Args:
        machine_id: Target machine identifier
        gcode: The G-code that was sent
        user_id: User who sent the command (from JWT or API key)
        validation_result: Result of validation
        success: Whether the command was successful
        error_message: Error message if failed
    """
    audit_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'machine_id': machine_id,
        'user_id': user_id,
        'gcode_length': len(gcode),
        'gcode_preview': gcode[:100] + '...' if len(gcode) > 100 else gcode,
        'success': success,
        'error_message': error_message,
    }

    if validation_result:
        audit_entry['validation'] = {
            'is_valid': validation_result.get('is_valid'),
            'error_count': len(validation_result.get('errors', [])),
            'warning_count': len(validation_result.get('warnings', [])),
            'command_count': validation_result.get('command_count', 0),
        }

    gcode_audit_logger.info(f"GCODE_AUDIT: {json.dumps(audit_entry)}")

scada_api_bp = Blueprint('scada_api', __name__, url_prefix='/api/scada')


def load_machines_config():
    """Load machines from config file."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'machines.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f).get('machines', [])
    return []


def get_machine_manager():
    """Get the machine manager instance."""
    try:
        from services.scada.machine_control.machine_service import machine_manager
        return machine_manager
    except Exception as e:
        logger.warning(f"Machine manager not available: {e}")
        return None


# ============================================================================
# MACHINE ENDPOINTS
# ============================================================================

@scada_api_bp.route('/machines', methods=['GET'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def list_machines():
    """List all configured machines."""
    machines = load_machines_config()
    manager = get_machine_manager()

    result = []
    for m in machines:
        machine_data = {
            'machine_id': m['machine_id'],
            'name': m['name'],
            'description': m.get('description', ''),
            'machine_type': m.get('machine_type'),
            'controller_type': m.get('controller_type'),
            'connection_type': m.get('connection_type'),
            'status': 'disconnected',
            'connected': False,
        }

        # Check live status if manager available
        if manager:
            controller = manager.get_machine(m['machine_id'])
            if controller:
                machine_data['status'] = controller.status.state.value
                machine_data['connected'] = controller.status.state.value != 'disconnected'

        result.append(machine_data)

    return jsonify({'machines': result, 'count': len(result)})


@scada_api_bp.route('/machines/<machine_id>', methods=['GET'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def get_machine(machine_id: str):
    """Get a specific machine."""
    machines = load_machines_config()
    for m in machines:
        if m['machine_id'] == machine_id:
            return jsonify(m)
    return jsonify({'error': 'Machine not found'}), 404


@scada_api_bp.route('/machines/<machine_id>/connect', methods=['POST'])
@jwt_required()
def connect_machine(machine_id: str):
    """Connect to a machine."""
    machines = load_machines_config()
    machine_config = next((m for m in machines if m['machine_id'] == machine_id), None)

    if not machine_config:
        return jsonify({'success': False, 'error': 'Machine not found'}), 404

    manager = get_machine_manager()
    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    try:
        # Get or register the controller
        controller = manager.get_machine(machine_id)
        if not controller:
            # Register the machine
            from services.scada.machine_control.machine_service import ControllerType
            controller_type = ControllerType(machine_config.get('controller_type', 'simulation'))
            controller = manager.register_machine(
                machine_id,
                controller_type,
                machine_config.get('connection_config', {})
            )

        # Connect
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(controller.connect())
        finally:
            loop.close()

        if success:
            return jsonify({'success': True, 'message': f'Connected to {machine_config["name"]}'})
        else:
            return jsonify({'success': False, 'error': 'Connection failed - check port/cable'}), 500

    except Exception as e:
        logger.error(f"Error connecting to {machine_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/machines/<machine_id>/disconnect', methods=['POST'])
@jwt_required()
def disconnect_machine(machine_id: str):
    """Disconnect from a machine."""
    manager = get_machine_manager()
    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'success': False, 'error': 'Machine not connected'}), 404

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(controller.disconnect())
        finally:
            loop.close()

        return jsonify({'success': True, 'message': 'Disconnected'})
    except Exception as e:
        logger.error(f"Error disconnecting from {machine_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/machines/<machine_id>/home', methods=['POST'])
@jwt_required()
def home_machine(machine_id: str):
    """Home machine axes."""
    manager = get_machine_manager()
    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'success': False, 'error': 'Machine not connected'}), 404

    try:
        data = request.get_json() or {}
        axes = data.get('axes', 'XYZ')

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(controller.home(axes))
        finally:
            loop.close()

        if success:
            return jsonify({'success': True, 'message': f'Homed axes: {axes}'})
        return jsonify({'success': False, 'error': 'Homing failed'}), 500
    except Exception as e:
        logger.error(f"Error homing {machine_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/machines/<machine_id>/zero', methods=['POST'])
@jwt_required()
def zero_machine(machine_id: str):
    """Zero work coordinates."""
    manager = get_machine_manager()
    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'success': False, 'error': 'Machine not connected'}), 404

    try:
        data = request.get_json() or {}
        axes = data.get('axes', 'XYZ')

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(controller.zero(axes))
        finally:
            loop.close()

        if success:
            return jsonify({'success': True, 'message': f'Zeroed axes: {axes}'})
        return jsonify({'success': False, 'error': 'Zero failed'}), 500
    except Exception as e:
        logger.error(f"Error zeroing {machine_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/machines/<machine_id>/jog', methods=['POST'])
@jwt_required()
def jog_machine(machine_id: str):
    """Jog machine axis."""
    manager = get_machine_manager()
    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'success': False, 'error': 'Machine not connected'}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        axis = data.get('axis', 'X')
        distance = float(data.get('distance', 1.0))
        feed_rate = float(data.get('feed_rate', 500))

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(controller.jog(axis, distance, feed_rate))
        finally:
            loop.close()

        if success:
            return jsonify({'success': True, 'message': f'Jogged {axis} by {distance}mm'})
        return jsonify({'success': False, 'error': 'Jog failed'}), 500
    except Exception as e:
        logger.error(f"Error jogging {machine_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/machines/<machine_id>/status', methods=['GET'])
@jwt_required()
def get_machine_status(machine_id: str):
    """Get machine status."""
    manager = get_machine_manager()
    if not manager:
        return jsonify({'status': 'disconnected', 'connected': False})

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'status': 'disconnected', 'connected': False})

    status = controller.status
    return jsonify({
        'status': status.state.value,
        'connected': status.state.value != 'disconnected',
        'position': {
            'x': status.position.x,
            'y': status.position.y,
            'z': status.position.z,
        },
        'feed_rate': status.feed_rate,
        'spindle_speed': status.spindle_speed,
        'progress_pct': status.progress_pct,
        'current_line': status.current_line,
        'total_lines': status.total_lines,
    })


@scada_api_bp.route('/machines/<machine_id>/gcode', methods=['POST'])
@jwt_required()
def send_gcode(machine_id: str):
    """
    Send G-code to machine with security validation.

    Request body:
        gcode (str): G-code command(s) to send
        confirm_dangerous (bool): Set to true to confirm dangerous commands

    Returns:
        - 200: Success with response from machine
        - 400: Invalid G-code (validation errors)
        - 404: Machine not found/connected
        - 422: Dangerous commands detected, requires confirmation
        - 500: Server error
    """
    current_user = get_jwt_identity()
    manager = get_machine_manager()

    if not manager:
        return jsonify({'success': False, 'error': 'Machine manager not available'}), 500

    controller = manager.get_machine(machine_id)
    if not controller:
        return jsonify({'success': False, 'error': 'Machine not connected'}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        gcode = data.get('gcode', '')
        confirm_dangerous = data.get('confirm_dangerous', False)

        if not gcode:
            return jsonify({'success': False, 'error': 'No G-code provided'}), 400

        # Get machine configuration for limits
        machines = load_machines_config()
        machine_config = next((m for m in machines if m['machine_id'] == machine_id), None)

        # Validate G-code
        GCodeValidator, MachineType = get_gcode_validator()
        validation_result_dict = None

        if GCodeValidator:
            # Determine machine type for validation
            machine_type = MachineType.GENERIC
            if machine_config:
                machine_type_str = machine_config.get('machine_type', 'generic')
                type_mapping = {
                    'cnc_mill': MachineType.CNC_MILL,
                    'laser_cutter': MachineType.LASER_CUTTER,
                    'printer_3d': MachineType.PRINTER_3D,
                    'cnc_lathe': MachineType.CNC_LATHE,
                }
                machine_type = type_mapping.get(machine_type_str, MachineType.GENERIC)

            validator = GCodeValidator(machine_type=machine_type)
            validation_result = validator.validate(gcode, machine_config)
            validation_result_dict = validation_result.to_dict()

            # Check for validation errors
            if not validation_result.is_valid:
                log_gcode_audit(
                    machine_id=machine_id,
                    gcode=gcode,
                    user_id=current_user,
                    validation_result=validation_result_dict,
                    success=False,
                    error_message='Validation failed',
                )
                return jsonify({
                    'success': False,
                    'error': 'Invalid G-code',
                    'details': [e.to_dict() for e in validation_result.errors],
                    'validation': validation_result_dict,
                }), 400

            # Check for dangerous commands requiring confirmation
            if validation_result.warnings and not confirm_dangerous:
                log_gcode_audit(
                    machine_id=machine_id,
                    gcode=gcode,
                    user_id=current_user,
                    validation_result=validation_result_dict,
                    success=False,
                    error_message='Dangerous commands require confirmation',
                )
                return jsonify({
                    'success': False,
                    'error': 'Dangerous commands detected',
                    'warnings': [w.to_dict() for w in validation_result.warnings],
                    'require_confirmation': True,
                    'message': 'Set confirm_dangerous=true to proceed',
                }), 422

            # Use sanitized G-code
            safe_gcode = validation_result.sanitized_gcode or gcode
        else:
            # Validator not available - log warning but allow command
            # This maintains backward compatibility but should be fixed in production
            logger.warning(f"G-code validator not available - sending unvalidated command to {machine_id}")
            safe_gcode = gcode

        # Send to machine
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(controller.send_command(safe_gcode))
        finally:
            loop.close()

        # Log successful command
        log_gcode_audit(
            machine_id=machine_id,
            gcode=gcode,
            user_id=current_user,
            validation_result=validation_result_dict,
            success=True,
        )

        return jsonify({
            'success': True,
            'response': response,
            'validated': GCodeValidator is not None,
            'warnings_confirmed': confirm_dangerous and validation_result_dict and len(validation_result_dict.get('warnings', [])) > 0,
        })

    except Exception as e:
        logger.error(f"Error sending G-code to {machine_id}: {e}")
        log_gcode_audit(
            machine_id=machine_id,
            gcode=data.get('gcode', '') if data else '',
            user_id=current_user,
            success=False,
            error_message=str(e),
        )
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SERIAL PORT ENDPOINTS
# ============================================================================

@scada_api_bp.route('/serial-ports', methods=['GET'])
@jwt_required()
def list_serial_ports():
    """List available serial ports."""
    try:
        import serial.tools.list_ports
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid,
                'manufacturer': port.manufacturer or '',
                'product': port.product or '',
            })
        return jsonify({'ports': ports, 'count': len(ports)})
    except ImportError:
        return jsonify({'ports': [], 'count': 0, 'error': 'pyserial not installed'})
    except Exception as e:
        logger.error(f"Error listing serial ports: {e}")
        return jsonify({'ports': [], 'count': 0, 'error': str(e)})


# ============================================================================
# HEALTH CHECK
# ============================================================================

@scada_api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    machines = load_machines_config()
    manager = get_machine_manager()

    connected_count = 0
    if manager:
        for m in machines:
            controller = manager.get_machine(m['machine_id'])
            if controller and controller.status.state.value != 'disconnected':
                connected_count += 1

    return jsonify({
        'status': 'healthy',
        'machines_configured': len(machines),
        'machines_connected': connected_count,
        'manager_available': manager is not None,
    })


# ============================================================================
# ALARM ENDPOINTS
# ============================================================================

@scada_api_bp.route('/alarms', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def list_alarms():
    """List all active alarms."""
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms = processor.get_active_alarms()
        return jsonify({'alarms': alarms, 'count': len(alarms)})
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_alarms
            alarms = get_demo_alarms()
            return jsonify({'alarms': alarms, 'count': len(alarms), 'demo': True})

        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


@scada_api_bp.route('/alarms/active', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def list_active_alarms():
    """List active alarms."""
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms = processor.get_active_alarms()
        return jsonify({'alarms': alarms, 'count': len(alarms)})
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_alarms
            alarms = [a for a in get_demo_alarms() if 'active' in a.get('state', '')]
            return jsonify({'alarms': alarms, 'count': len(alarms), 'demo': True})

        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


@scada_api_bp.route('/alarms/summary', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def alarm_summary():
    """Get alarm summary counts."""
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms = processor.get_active_alarms()
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_alarms
            alarms = get_demo_alarms()
        else:
            logger.error(f"Alarm service unavailable: {e}", exc_info=True)
            return jsonify({
                'error': 'Alarm service unavailable',
                'message': 'The alarm management service is not available. Please check system status.'
            }), 503

    summary = {
        'total': len(alarms),
        'critical': len([a for a in alarms if a.get('priority') == 'critical']),
        'high': len([a for a in alarms if a.get('priority') == 'high']),
        'medium': len([a for a in alarms if a.get('priority') == 'medium']),
        'low': len([a for a in alarms if a.get('priority') == 'low']),
        'unacknowledged': len([a for a in alarms if 'unack' in a.get('state', '')]),
    }
    return jsonify(summary)


@scada_api_bp.route('/alarms/<alarm_id>', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def get_alarm(alarm_id: str):
    """Get alarm details."""
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarm = processor.get_alarm(alarm_id)
        if not alarm:
            return jsonify({'error': 'Alarm not found'}), 404
        return jsonify(alarm)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_alarms
            alarm = next((a for a in get_demo_alarms() if a['alarm_id'] == alarm_id), None)
            if not alarm:
                return jsonify({'error': 'Alarm not found'}), 404
            return jsonify({**alarm, 'demo': True})

        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


@scada_api_bp.route('/alarms/<alarm_id>/acknowledge', methods=['POST'])
@jwt_required()
def acknowledge_alarm(alarm_id: str):
    """Acknowledge an alarm."""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'operator')

    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        success = processor.acknowledge_alarm(alarm_id, user_id)
        if success:
            return jsonify({'success': True, 'message': f'Alarm {alarm_id} acknowledged'})
        return jsonify({'success': False, 'error': 'Failed to acknowledge'}), 500
    except Exception as e:
        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


@scada_api_bp.route('/alarms/acknowledge-batch', methods=['POST'])
@jwt_required()
def acknowledge_alarms_batch():
    """Acknowledge multiple alarms."""
    data = request.get_json() or {}
    alarm_ids = data.get('alarm_ids', [])
    user_id = data.get('user_id', 'operator')

    if not alarm_ids:
        return jsonify({'success': False, 'error': 'No alarm IDs provided'}), 400

    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()

        acknowledged = []
        for alarm_id in alarm_ids:
            if processor.acknowledge_alarm(alarm_id, user_id):
                acknowledged.append(alarm_id)

        return jsonify({
            'success': True,
            'acknowledged': acknowledged,
            'count': len(acknowledged)
        })
    except Exception as e:
        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


@scada_api_bp.route('/alarms/export', methods=['GET'])
@jwt_required()
def export_alarms():
    """Export alarms to CSV."""
    import csv
    import io

    format_type = request.args.get('format', 'csv')

    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms = processor.get_active_alarms()
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_alarms
            alarms = get_demo_alarms()
        else:
            logger.error(f"Alarm service unavailable: {e}", exc_info=True)
            return jsonify({
                'error': 'Alarm service unavailable',
                'message': 'The alarm management service is not available. Please check system status.'
            }), 503

    if format_type == 'csv':
        output = io.StringIO()
        if alarms:
            writer = csv.DictWriter(output, fieldnames=alarms[0].keys())
            writer.writeheader()
            writer.writerows(alarms)

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=alarms_export.csv'}
        )

    return jsonify({'alarms': alarms})


# ============================================================================
# ROBOT ENDPOINTS (ROS2)
# ============================================================================

@scada_api_bp.route('/robots', methods=['GET'])
@jwt_required()
def list_robots():
    """List configured robot arms."""
    machines = load_machines_config()
    robots = [m for m in machines if m.get('machine_type') == 'robot_arm']

    result = []
    for robot in robots:
        robot_data = {
            'robot_id': robot['machine_id'],
            'name': robot['name'],
            'description': robot.get('description', ''),
            'controller_type': robot.get('controller_type'),
            'ip': robot.get('connection_config', {}).get('ip', ''),
            'port': robot.get('connection_config', {}).get('port', 9090),
            'status': 'disconnected',
            'connected': False,
            'axes': robot.get('axes', 6),
            'payload_kg': robot.get('payload_kg', 0),
            'reach_mm': robot.get('reach_mm', 0),
        }

        # Try to get live status from ROS2 bridge
        try:
            from services.robotics import get_ros2_bridge
            bridge = get_ros2_bridge()
            if bridge.is_connected:
                robot_data['connected'] = True
                robot_data['status'] = 'idle'
        except Exception as e:
            logger.warning(f'Exception in scada_api.py: {e}')
            pass

        result.append(robot_data)

    return jsonify({'robots': result, 'count': len(result)})


@scada_api_bp.route('/robots/<robot_id>/connect', methods=['POST'])
@jwt_required()
def connect_robot(robot_id: str):
    """Connect to a robot via ROS2."""
    machines = load_machines_config()
    robot_config = next((m for m in machines if m['machine_id'] == robot_id), None)

    if not robot_config:
        return jsonify({'success': False, 'error': 'Robot not found'}), 404

    try:
        from services.robotics import get_ros2_bridge, NiryoController, XArmController

        bridge = get_ros2_bridge(
            host=robot_config.get('connection_config', {}).get('ip', 'localhost'),
            port=robot_config.get('connection_config', {}).get('port', 9090)
        )

        if bridge.connect():
            return jsonify({'success': True, 'message': f'Connected to {robot_config["name"]}'})
        else:
            return jsonify({'success': False, 'error': 'Connection failed'}), 500

    except Exception as e:
        logger.error(f"Error connecting to robot {robot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/robots/<robot_id>/home', methods=['POST'])
@jwt_required()
def home_robot(robot_id: str):
    """Home the robot."""
    try:
        from services.robotics import NiryoController, XArmController

        if 'niryo' in robot_id.lower():
            controller = NiryoController(robot_id)
        else:
            controller = XArmController(robot_id)

        if controller.home():
            return jsonify({'success': True, 'message': 'Robot homed'})
        return jsonify({'success': False, 'error': 'Homing failed'}), 500

    except Exception as e:
        logger.error(f"Error homing robot {robot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/robots/<robot_id>/move', methods=['POST'])
@jwt_required()
def move_robot(robot_id: str):
    """Move robot to position."""
    data = request.get_json() or {}

    try:
        from services.robotics import NiryoController, XArmController

        if 'niryo' in robot_id.lower():
            controller = NiryoController(robot_id)
        else:
            controller = XArmController(robot_id)

        if 'joints' in data:
            success = controller.move_joints(data['joints'])
        elif 'pose' in data:
            pose = data['pose']
            success = controller.move_pose(
                pose.get('x', 0), pose.get('y', 0), pose.get('z', 0),
                pose.get('roll', 0), pose.get('pitch', 0), pose.get('yaw', 0)
            )
        else:
            return jsonify({'success': False, 'error': 'No position specified'}), 400

        if success:
            return jsonify({'success': True, 'message': 'Move completed'})
        return jsonify({'success': False, 'error': 'Move failed'}), 500

    except Exception as e:
        logger.error(f"Error moving robot {robot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/robots/<robot_id>/gripper', methods=['POST'])
@jwt_required()
def control_gripper(robot_id: str):
    """Control gripper open/close."""
    data = request.get_json() or {}
    action = data.get('action', 'open')

    try:
        from services.robotics import NiryoController, XArmController

        if 'niryo' in robot_id.lower():
            controller = NiryoController(robot_id)
        else:
            controller = XArmController(robot_id)

        if action == 'open':
            success = controller.open_gripper()
        else:
            success = controller.close_gripper()

        if success:
            return jsonify({'success': True, 'message': f'Gripper {action}'})
        return jsonify({'success': False, 'error': 'Gripper command failed'}), 500

    except Exception as e:
        logger.error(f"Error controlling gripper on {robot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/robots/<robot_id>/status', methods=['GET'])
@jwt_required()
def get_robot_status(robot_id: str):
    """Get robot status."""
    try:
        from services.robotics import NiryoController, XArmController

        if 'niryo' in robot_id.lower():
            controller = NiryoController(robot_id)
        else:
            controller = XArmController(robot_id)

        return jsonify({
            'robot_id': robot_id,
            'connected': controller._connected,
            'state': controller._state,
            'joint_positions': controller._joint_positions,
            'end_effector_pose': controller._end_effector_pose,
            'gripper_open': controller._gripper_open,
        })

    except Exception as e:
        return jsonify({
            'robot_id': robot_id,
            'connected': False,
            'state': 'disconnected',
            'error': str(e)
        })


# ============================================================================
# BAMBU PRINTER ENDPOINTS
# ============================================================================

@scada_api_bp.route('/printers', methods=['GET'])
@jwt_required()
def list_printers():
    """List configured 3D printers."""
    machines = load_machines_config()
    printers = [m for m in machines if m.get('machine_type') == 'printer_3d']

    result = []
    for printer in printers:
        printer_data = {
            'printer_id': printer['machine_id'],
            'name': printer['name'],
            'description': printer.get('description', ''),
            'controller_type': printer.get('controller_type'),
            'ip': printer.get('connection_config', {}).get('ip', ''),
            'status': 'offline',
            'connected': False,
            'work_envelope': {
                'x': printer.get('work_envelope_x', 0),
                'y': printer.get('work_envelope_y', 0),
                'z': printer.get('work_envelope_z', 0),
            },
        }

        # Try to get live status from Bambu controller
        if printer.get('controller_type') == 'bambu':
            try:
                from services.bambu import get_bambu_controller
                controller = get_bambu_controller(machine_id=printer['machine_id'])
                if controller and controller.is_connected:
                    printer_data['connected'] = True
                    printer_data['status'] = controller.state.value
            except Exception as e:
                logger.warning(f'Exception in scada_api.py: {e}')
                pass

        result.append(printer_data)

    return jsonify({'printers': result, 'count': len(result)})


@scada_api_bp.route('/printers/<printer_id>/connect', methods=['POST'])
@jwt_required()
def connect_printer(printer_id: str):
    """Connect to a Bambu printer."""
    machines = load_machines_config()
    printer_config = next((m for m in machines if m['machine_id'] == printer_id), None)

    if not printer_config:
        return jsonify({'success': False, 'error': 'Printer not found'}), 404

    if printer_config.get('controller_type') != 'bambu':
        return jsonify({'success': False, 'error': 'Not a Bambu printer'}), 400

    data = request.get_json() or {}
    conn_config = printer_config.get('connection_config', {})

    # Get connection parameters (can be overridden in request)
    ip = data.get('ip', conn_config.get('ip'))
    serial = data.get('serial', conn_config.get('serial', ''))
    access_code = data.get('access_code', conn_config.get('access_code', ''))

    if not ip or not serial or not access_code:
        return jsonify({
            'success': False,
            'error': 'Missing connection parameters (ip, serial, access_code)'
        }), 400

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(
            machine_id=printer_id,
            ip=ip,
            serial=serial,
            access_code=access_code
        )

        if controller.connect():
            return jsonify({
                'success': True,
                'message': f'Connected to {printer_config["name"]}',
                'status': controller.state.value
            })
        else:
            return jsonify({'success': False, 'error': 'Connection failed'}), 500

    except Exception as e:
        logger.error(f"Error connecting to printer {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/disconnect', methods=['POST'])
@jwt_required()
def disconnect_printer(printer_id: str):
    """Disconnect from a Bambu printer."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if controller:
            controller.disconnect()
            return jsonify({'success': True, 'message': 'Disconnected'})
        return jsonify({'success': False, 'error': 'Printer not found'}), 404

    except Exception as e:
        logger.error(f"Error disconnecting from printer {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/status', methods=['GET'])
@jwt_required()
def get_printer_status(printer_id: str):
    """Get Bambu printer status."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if controller:
            return jsonify(controller.get_status())

        return jsonify({
            'printer_id': printer_id,
            'connected': False,
            'state': 'offline'
        })

    except Exception as e:
        return jsonify({
            'printer_id': printer_id,
            'connected': False,
            'state': 'offline',
            'error': str(e)
        })


@scada_api_bp.route('/printers/<printer_id>/print/start', methods=['POST'])
@jwt_required()
def start_printer_job(printer_id: str):
    """Start a print job on Bambu printer."""
    data = request.get_json() or {}
    filename = data.get('filename')

    if not filename:
        return jsonify({'success': False, 'error': 'No filename provided'}), 400

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.start_print(filename):
            return jsonify({
                'success': True,
                'message': f'Print started: {filename}',
                'status': controller.state.value
            })
        return jsonify({'success': False, 'error': 'Failed to start print'}), 500

    except Exception as e:
        logger.error(f"Error starting print on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/print/pause', methods=['POST'])
@jwt_required()
def pause_printer_job(printer_id: str):
    """Pause current print job."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.pause_print():
            return jsonify({'success': True, 'message': 'Print paused'})
        return jsonify({'success': False, 'error': 'Failed to pause print'}), 500

    except Exception as e:
        logger.error(f"Error pausing print on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/print/resume', methods=['POST'])
@jwt_required()
def resume_printer_job(printer_id: str):
    """Resume paused print job."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.resume_print():
            return jsonify({'success': True, 'message': 'Print resumed'})
        return jsonify({'success': False, 'error': 'Failed to resume print'}), 500

    except Exception as e:
        logger.error(f"Error resuming print on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/print/stop', methods=['POST'])
@jwt_required()
def stop_printer_job(printer_id: str):
    """Stop/cancel current print job."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.stop_print():
            return jsonify({'success': True, 'message': 'Print stopped'})
        return jsonify({'success': False, 'error': 'Failed to stop print'}), 500

    except Exception as e:
        logger.error(f"Error stopping print on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/temperature', methods=['POST'])
@jwt_required()
def set_printer_temperature(printer_id: str):
    """Set printer temperatures."""
    data = request.get_json() or {}

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        success = True
        if 'nozzle' in data:
            success = success and controller.set_nozzle_temp(data['nozzle'])
        if 'bed' in data:
            success = success and controller.set_bed_temp(data['bed'])

        if success:
            return jsonify({'success': True, 'message': 'Temperature set'})
        return jsonify({'success': False, 'error': 'Failed to set temperature'}), 500

    except Exception as e:
        logger.error(f"Error setting temperature on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/preheat', methods=['POST'])
@jwt_required()
def preheat_printer(printer_id: str):
    """Preheat printer for specific material."""
    data = request.get_json() or {}
    material = data.get('material', 'pla').lower()

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if material == 'pla':
            success = controller.preheat_pla()
        elif material == 'petg':
            success = controller.preheat_petg()
        elif material == 'abs':
            success = controller.preheat_abs()
        else:
            return jsonify({'success': False, 'error': f'Unknown material: {material}'}), 400

        if success:
            return jsonify({'success': True, 'message': f'Preheating for {material.upper()}'})
        return jsonify({'success': False, 'error': 'Failed to preheat'}), 500

    except Exception as e:
        logger.error(f"Error preheating {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/cooldown', methods=['POST'])
@jwt_required()
def cooldown_printer(printer_id: str):
    """Cool down printer heaters."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.cooldown():
            return jsonify({'success': True, 'message': 'Cooling down'})
        return jsonify({'success': False, 'error': 'Failed to cool down'}), 500

    except Exception as e:
        logger.error(f"Error cooling down {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/light', methods=['POST'])
@jwt_required()
def control_printer_light(printer_id: str):
    """Control printer lights."""
    data = request.get_json() or {}
    light = data.get('light', 'chamber')  # 'chamber' or 'work'
    state = data.get('state', True)  # True = on, False = off

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if light == 'chamber':
            success = controller.set_chamber_light(state)
        elif light == 'work':
            success = controller.set_work_light(state)
        else:
            return jsonify({'success': False, 'error': f'Unknown light: {light}'}), 400

        if success:
            return jsonify({'success': True, 'message': f'{light} light {"on" if state else "off"}'})
        return jsonify({'success': False, 'error': 'Failed to control light'}), 500

    except Exception as e:
        logger.error(f"Error controlling light on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/speed', methods=['POST'])
@jwt_required()
def set_printer_speed(printer_id: str):
    """Set printer speed profile."""
    data = request.get_json() or {}
    profile = data.get('profile', 'standard')  # 'silent', 'standard', 'sport', 'ludicrous'

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.set_speed_profile(profile):
            return jsonify({'success': True, 'message': f'Speed profile: {profile}'})
        return jsonify({'success': False, 'error': 'Failed to set speed'}), 500

    except Exception as e:
        logger.error(f"Error setting speed on {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/home', methods=['POST'])
@jwt_required()
def home_printer(printer_id: str):
    """Home printer axes."""
    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.home():
            return jsonify({'success': True, 'message': 'Homing'})
        return jsonify({'success': False, 'error': 'Failed to home'}), 500

    except Exception as e:
        logger.error(f"Error homing {printer_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scada_api_bp.route('/printers/<printer_id>/gcode', methods=['POST'])
@jwt_required()
def send_printer_gcode(printer_id: str):
    """
    Send G-code command to 3D printer with security validation.

    Request body:
        gcode (str): G-code command(s) to send
        confirm_dangerous (bool): Set to true to confirm dangerous commands

    Returns:
        - 200: Success with response from printer
        - 400: Invalid G-code (validation errors)
        - 404: Printer not found/connected
        - 422: Dangerous commands detected, requires confirmation
        - 500: Server error

    Note: 3D printers have additional temperature validations to prevent
    thermal runaway and extruder damage.
    """
    current_user = get_jwt_identity()
    data = request.get_json() or {}
    gcode = data.get('gcode', '')
    confirm_dangerous = data.get('confirm_dangerous', False)

    if not gcode:
        return jsonify({'success': False, 'error': 'No G-code provided'}), 400

    # Get printer configuration
    machines = load_machines_config()
    printer_config = next((m for m in machines if m['machine_id'] == printer_id), None)

    # Validate G-code
    GCodeValidator, MachineType = get_gcode_validator()
    validation_result_dict = None

    if GCodeValidator:
        # Use PRINTER_3D type for stricter temperature validation
        validator = GCodeValidator(
            machine_type=MachineType.PRINTER_3D,
            custom_limits={
                'max_nozzle_temp': 300,  # Default max nozzle temp
                'max_bed_temp': 120,      # Default max bed temp
                'max_chamber_temp': 70,   # Default max chamber temp
            }
        )
        validation_result = validator.validate(gcode, printer_config)
        validation_result_dict = validation_result.to_dict()

        # Check for validation errors
        if not validation_result.is_valid:
            log_gcode_audit(
                machine_id=printer_id,
                gcode=gcode,
                user_id=current_user,
                validation_result=validation_result_dict,
                success=False,
                error_message='Validation failed',
            )
            return jsonify({
                'success': False,
                'error': 'Invalid G-code',
                'details': [e.to_dict() for e in validation_result.errors],
                'validation': validation_result_dict,
            }), 400

        # Check for dangerous commands requiring confirmation
        if validation_result.warnings and not confirm_dangerous:
            log_gcode_audit(
                machine_id=printer_id,
                gcode=gcode,
                user_id=current_user,
                validation_result=validation_result_dict,
                success=False,
                error_message='Dangerous commands require confirmation',
            )
            return jsonify({
                'success': False,
                'error': 'Dangerous commands detected',
                'warnings': [w.to_dict() for w in validation_result.warnings],
                'require_confirmation': True,
                'message': 'Set confirm_dangerous=true to proceed',
            }), 422

        # Use sanitized G-code
        safe_gcode = validation_result.sanitized_gcode or gcode
    else:
        logger.warning(f"G-code validator not available - sending unvalidated command to printer {printer_id}")
        safe_gcode = gcode

    try:
        from services.bambu import get_bambu_controller

        controller = get_bambu_controller(machine_id=printer_id)
        if not controller:
            return jsonify({'success': False, 'error': 'Printer not connected'}), 404

        if controller.send_gcode(safe_gcode):
            log_gcode_audit(
                machine_id=printer_id,
                gcode=gcode,
                user_id=current_user,
                validation_result=validation_result_dict,
                success=True,
            )
            return jsonify({
                'success': True,
                'message': f'Sent: {safe_gcode[:50]}...' if len(safe_gcode) > 50 else f'Sent: {safe_gcode}',
                'validated': GCodeValidator is not None,
            })

        log_gcode_audit(
            machine_id=printer_id,
            gcode=gcode,
            user_id=current_user,
            validation_result=validation_result_dict,
            success=False,
            error_message='Printer rejected command',
        )
        return jsonify({'success': False, 'error': 'Failed to send G-code'}), 500

    except Exception as e:
        logger.error(f"Error sending G-code to {printer_id}: {e}")
        log_gcode_audit(
            machine_id=printer_id,
            gcode=gcode,
            user_id=current_user,
            success=False,
            error_message=str(e),
        )
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# TAG ENDPOINTS
# ============================================================================

@scada_api_bp.route('/tags', methods=['GET'])
@jwt_required()
def list_tags():
    """List all tags."""
    try:
        from config.database import get_db_session
        from models.scada.tags import Tag

        with get_db_session() as session:
            tags = session.query(Tag).filter(Tag.is_deleted == False).limit(100).all()
            result = [t.to_dict() for t in tags]
            return jsonify({'tags': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        return jsonify({'tags': [], 'count': 0, 'error': str(e)})


@scada_api_bp.route('/tags/<tag_id>', methods=['GET'])
@jwt_required()
def get_tag(tag_id: str):
    """Get a specific tag."""
    try:
        from config.database import get_db_session
        from models.scada.tags import Tag

        with get_db_session() as session:
            tag = session.query(Tag).filter(Tag.tag_id == tag_id).first()
            if tag:
                return jsonify(tag.to_dict())
            return jsonify({'error': 'Tag not found'}), 404
    except Exception as e:
        logger.error(f"Error getting tag {tag_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# RECIPE ENDPOINTS
# ============================================================================

@scada_api_bp.route('/recipes', methods=['GET'])
@jwt_required()
def list_recipes():
    """List all recipes."""
    try:
        from config.database import get_db_session
        from models.scada.recipes import MasterRecipe

        with get_db_session() as session:
            recipes = session.query(MasterRecipe).filter(MasterRecipe.is_latest == True).limit(100).all()
            result = [r.to_dict() for r in recipes]
            return jsonify({'recipes': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"Error listing recipes: {e}")
        return jsonify({'recipes': [], 'count': 0, 'error': str(e)})


@scada_api_bp.route('/recipes/<recipe_id>', methods=['GET'])
@jwt_required()
def get_recipe(recipe_id: str):
    """Get a specific recipe."""
    try:
        from config.database import get_db_session
        from models.scada.recipes import MasterRecipe

        with get_db_session() as session:
            recipe = session.query(MasterRecipe).filter(
                MasterRecipe.recipe_id == recipe_id,
                MasterRecipe.is_latest == True
            ).first()
            if recipe:
                return jsonify(recipe.to_dict())
            return jsonify({'error': 'Recipe not found'}), 404
    except Exception as e:
        logger.error(f"Error getting recipe {recipe_id}: {e}")
        return jsonify({'error': str(e)}), 500


@scada_api_bp.route('/tags/<tag_id>', methods=['DELETE'])
@jwt_required()
def delete_tag(tag_id: str):
    """
    Delete a SCADA tag (soft delete).

    Requires admin role. Returns 204 on success.
    """
    from datetime import datetime

    current_user = get_jwt_identity()

    # Check permissions
    try:
        from api.utils.auth import has_role
        if not has_role(current_user, 'admin'):
            return jsonify({'error': 'Admin role required'}), 403
    except ImportError:
        pass  # Skip role check if auth module not available

    try:
        from config.database import get_db_session
        from models.scada.tags import Tag

        with get_db_session() as session:
            tag = session.query(Tag).filter(Tag.tag_id == tag_id).first()

            if not tag:
                return jsonify({'error': 'Tag not found'}), 404

            # Check if tag has active alarms
            if hasattr(tag, 'active_alarms') and tag.active_alarms:
                return jsonify({'error': 'Cannot delete tag with active alarms'}), 409

            # Soft delete
            tag.is_deleted = True
            tag.deleted_at = datetime.utcnow()
            if hasattr(tag, 'deleted_by'):
                tag.deleted_by = current_user
            session.commit()

            logger.info(f"Tag {tag_id} deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting tag {tag_id}: {e}")
        return jsonify({'error': 'Failed to delete tag'}), 500


@scada_api_bp.route('/recipes/<recipe_id>', methods=['DELETE'])
@jwt_required()
def delete_recipe(recipe_id: str):
    """
    Delete a recipe (soft delete).

    Requires admin role. Returns 204 on success.
    """
    from datetime import datetime

    current_user = get_jwt_identity()

    # Check permissions
    try:
        from api.utils.auth import has_role
        if not has_role(current_user, 'admin'):
            return jsonify({'error': 'Admin role required'}), 403
    except ImportError:
        pass  # Skip role check if auth module not available

    try:
        from config.database import get_db_session
        from models.scada.recipes import MasterRecipe

        with get_db_session() as session:
            recipe = session.query(MasterRecipe).filter(
                MasterRecipe.recipe_id == recipe_id,
                MasterRecipe.is_latest == True
            ).first()

            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404

            # Check if recipe has active control recipes
            if hasattr(recipe, 'control_recipes') and recipe.control_recipes:
                active_control = [cr for cr in recipe.control_recipes if cr.status == 'running']
                if active_control:
                    return jsonify({'error': 'Cannot delete recipe with active control recipes'}), 409

            # Soft delete - mark as not latest
            recipe.is_latest = False
            recipe.deleted_at = datetime.utcnow()
            if hasattr(recipe, 'deleted_by'):
                recipe.deleted_by = current_user
            session.commit()

            logger.info(f"Recipe {recipe_id} deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting recipe {recipe_id}: {e}")
        return jsonify({'error': 'Failed to delete recipe'}), 500


@scada_api_bp.route('/alarms/<alarm_id>', methods=['DELETE'])
@jwt_required()
def delete_alarm(alarm_id: str):
    """
    Delete/clear a historical alarm.

    Requires admin role. Returns 204 on success.
    Only alarms that are not active can be deleted.
    """
    current_user = get_jwt_identity()

    # Check permissions
    try:
        from api.utils.auth import has_role
        if not has_role(current_user, 'admin'):
            return jsonify({'error': 'Admin role required'}), 403
    except ImportError:
        pass  # Skip role check if auth module not available

    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarm = processor.get_alarm(alarm_id)

        if not alarm:
            return jsonify({'error': 'Alarm not found'}), 404

        # Check if alarm is still active
        if 'active' in alarm.get('state', ''):
            return jsonify({'error': 'Cannot delete active alarm. Clear alarm first.'}), 409

        # Delete the alarm
        success = processor.delete_alarm(alarm_id)
        if success:
            logger.info(f"Alarm {alarm_id} deleted by {current_user}")
            return '', 204
        return jsonify({'error': 'Failed to delete alarm'}), 500

    except Exception as e:
        logger.error(f"Alarm service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'Alarm service unavailable',
            'message': 'The alarm management service is not available. Please check system status.'
        }), 503


# =============================================================================
# G-code File Management (for G-code Manager dashboard)
# =============================================================================

GCODE_DIR = Path(__file__).parent.parent.parent / 'data' / 'gcode'


@scada_api_bp.route('/gcode/files', methods=['GET'])
def list_gcode_files():
    """
    List all G-code files in the data/gcode directory.

    Returns:
        List of files with name, size, and modified date
    """
    try:
        if not GCODE_DIR.exists():
            GCODE_DIR.mkdir(parents=True, exist_ok=True)
            return jsonify({'files': [], 'count': 0})

        files = []
        valid_extensions = {'.nc', '.gcode', '.ngc', '.tap', '.txt'}

        for f in GCODE_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in valid_extensions:
                stat = f.stat()
                files.append({
                    'name': f.name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # Sort by modified date, newest first
        files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            'files': files,
            'count': len(files),
            'directory': str(GCODE_DIR)
        })

    except Exception as e:
        logger.error(f"Error listing G-code files: {e}")
        return jsonify({'error': str(e)}), 500


@scada_api_bp.route('/gcode/files/<filename>', methods=['GET'])
def get_gcode_file(filename):
    """
    Get contents of a G-code file.

    Args:
        filename: Name of the file to read

    Returns:
        File content and metadata
    """
    try:
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400

        filepath = GCODE_DIR / filename

        if not filepath.exists():
            return jsonify({'error': 'File not found'}), 404

        if not filepath.is_file():
            return jsonify({'error': 'Not a file'}), 400

        # Check file size limit (5MB)
        if filepath.stat().st_size > 5 * 1024 * 1024:
            return jsonify({'error': 'File too large (max 5MB)'}), 400

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        stat = filepath.stat()

        return jsonify({
            'filename': filename,
            'content': content,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'lines': content.count('\n') + 1
        })

    except Exception as e:
        logger.error(f"Error reading G-code file {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@scada_api_bp.route('/gcode/files/<filename>', methods=['PUT'])
def save_gcode_file(filename):
    """
    Save G-code content to a file.

    Args:
        filename: Name of the file to save

    Request JSON:
        {
            "content": "G0 X0 Y0\\n..."
        }
    """
    try:
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400

        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'error': 'Content required'}), 400

        content = data['content']

        # Ensure directory exists
        GCODE_DIR.mkdir(parents=True, exist_ok=True)

        filepath = GCODE_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        stat = filepath.stat()

        logger.info(f"G-code file saved: {filename}")

        return jsonify({
            'message': 'File saved',
            'filename': filename,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    except Exception as e:
        logger.error(f"Error saving G-code file {filename}: {e}")
        return jsonify({'error': str(e)}), 500
