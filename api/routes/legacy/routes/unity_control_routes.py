"""
Unity Control Routes
=====================
REST API endpoints for Unity remote control commands.

Provides:
- Command submission with validation
- Jog control (continuous, incremental, MPG)
- Spindle and coolant control
- Program execution
- E-stop and safety controls

Security:
- JWT authentication required
- Role-based authorization
- Rate limiting per command type
- Full audit logging

Author: Flask CNC SCADA System
"""

import logging
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, g

from services.command_validator_service import AuthLevel, ValidationResult

logger = logging.getLogger(__name__)

# Blueprint for Unity control routes
unity_control_bp = Blueprint(
    'unity_control',
    __name__,
    url_prefix='/api/unity/control'
)


# =============================================================================
# Lazy Service Imports
# =============================================================================

def get_validator():
    """Lazy import of command validator service."""
    from services.command_validator_service import get_command_validator
    return get_command_validator()


def get_ros2_bridge():
    """Lazy import of ROS2 bridge service."""
    try:
        from services.ros2_bridge_service import get_ros2_bridge
        return get_ros2_bridge()
    except ImportError:
        return None


# =============================================================================
# Authentication Decorator
# =============================================================================

# Role level mapping for authorization
ROLE_LEVELS = {
    'viewer': 1,
    'operator': 2,
    'supervisor': 3,
    'maintenance': 3,
    'management': 4,
    'admin': 5
}


def require_auth(min_level: str = 'operator'):
    """
    Decorator to require authentication and authorization.

    Args:
        min_level: Minimum authorization level required
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from config import get_config
            config = get_config()

            # Check if JWT is enabled
            if not getattr(config, 'JWT_ENABLED', False):
                # Development mode - use default user
                g.user_id = 'dev-user'
                g.auth_level = 'operator'
                g.client_ip = request.remote_addr
                return f(*args, **kwargs)

            # Get auth header
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Authorization required'}), 401

            try:
                # Extract token (Bearer <token>)
                if not auth_header.startswith('Bearer '):
                    return jsonify({'error': 'Invalid authorization format'}), 401

                token = auth_header[7:]  # Remove 'Bearer ' prefix

                # Validate JWT token
                from services.auth_service import verify_token, get_user_store
                payload = verify_token(token, "access")

                if not payload:
                    return jsonify({'error': 'Invalid or expired token'}), 401

                # Get user from token
                store = get_user_store()
                user = store.get(payload.get("sub"))

                if not user or not user.active:
                    return jsonify({'error': 'User not found or disabled'}), 401

                # Check authorization level
                user_level = ROLE_LEVELS.get(user.role, 0)
                required_level = ROLE_LEVELS.get(min_level, 0)

                if user_level < required_level:
                    logger.warning(
                        f"User {user.username} (role: {user.role}) "
                        f"denied access requiring {min_level} level"
                    )
                    return jsonify({
                        'error': 'Forbidden',
                        'message': f'Requires {min_level} role or higher'
                    }), 403

                # Store user info in request context
                g.user_id = user.username
                g.auth_level = user.role
                g.client_ip = request.remote_addr
                g.current_user = user

            except Exception as e:
                logger.warning(f"Auth failed: {e}")
                return jsonify({'error': 'Invalid authorization'}), 401

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============================================================================
# Jog Control
# =============================================================================

@unity_control_bp.route('/jog', methods=['POST'])
@require_auth('operator')
def jog_command():
    """
    Execute jog command.

    Request body:
    {
        "machine_id": "cnc-1",
        "axis": "X",
        "direction": 1,
        "mode": "continuous",
        "distance": 10.0,
        "feed_rate": 500.0
    }

    Response:
    {
        "status": "accepted",
        "command_id": "cmd-123",
        "timestamp": "2024-01-10T12:00:00Z"
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'axis', 'direction']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    validator = get_validator()

    # Build command
    command = {
        'type': 'jog',
        'axis': data['axis'].upper(),
        'direction': data['direction'],
        'mode': data.get('mode', 'continuous'),
        'distance': data.get('distance', 1.0),
        'feed_rate': data.get('feed_rate', 500.0)
    }

    # Validate command
    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command['type'],
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message,
            'result': result.value
        }), 403

    # Execute via ROS2 bridge if available
    ros2 = get_ros2_bridge()
    if ros2:
        try:
            ros2.send_jog_command(
                machine_id=data['machine_id'],
                axis=command['axis'],
                direction=command['direction'],
                feed_rate=command['feed_rate']
            )
        except Exception as e:
            logger.error(f"ROS2 jog command failed: {e}")

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'sanitized_command': validated_cmd.params
    })


@unity_control_bp.route('/jog/stop', methods=['POST'])
@require_auth('operator')
def jog_stop():
    """
    Stop jog motion.

    Request body:
    {
        "machine_id": "cnc-1",
        "axis": "X"  // optional, stops all axes if omitted
    }
    """
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    command = {
        'type': 'jog_stop',
        'axis': data.get('axis', 'all').upper()
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command['type'],
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message
        }), 403

    # Execute
    ros2 = get_ros2_bridge()
    if ros2:
        ros2.send_jog_stop(data['machine_id'], data.get('axis'))

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id
    })


# =============================================================================
# Spindle Control
# =============================================================================

@unity_control_bp.route('/spindle', methods=['POST'])
@require_auth('operator')
def spindle_control():
    """
    Control spindle.

    Request body:
    {
        "machine_id": "cnc-1",
        "action": "on",  // on, off, speed
        "speed": 12000,
        "direction": "cw"
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'action']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    validator = get_validator()

    command = {
        'type': f"spindle_{data['action']}",
        'speed': data.get('speed', 0),
        'direction': data.get('direction', 'cw')
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command['type'],
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message,
            'result': result.value
        }), 403

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id,
        'sanitized_command': validated_cmd.params
    })


# =============================================================================
# Coolant Control
# =============================================================================

@unity_control_bp.route('/coolant', methods=['POST'])
@require_auth('operator')
def coolant_control():
    """
    Control coolant.

    Request body:
    {
        "machine_id": "cnc-1",
        "type": "flood",  // flood, mist
        "action": "on"    // on, off
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'type', 'action']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    validator = get_validator()

    command = {
        'type': f"coolant_{data['type']}_{data['action']}"
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command['type'],
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message
        }), 403

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id
    })


# =============================================================================
# Program Control
# =============================================================================

@unity_control_bp.route('/program/run', methods=['POST'])
@require_auth('operator')
def run_program():
    """
    Start program execution.

    Request body:
    {
        "machine_id": "cnc-1",
        "program": "part-001.nc",
        "start_line": 0
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'program']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    validator = get_validator()

    command = {
        'type': 'run_program',
        'program': data['program'],
        'start_line': data.get('start_line', 0)
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command['type'],
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message
        }), 403

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id
    })


@unity_control_bp.route('/program/pause', methods=['POST'])
@require_auth('operator')
def pause_program():
    """Pause program execution."""
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='pause',
        params={'type': 'pause_program'},
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({'status': 'accepted', 'command_id': validated_cmd.command_id})


@unity_control_bp.route('/program/resume', methods=['POST'])
@require_auth('operator')
def resume_program():
    """Resume program execution."""
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='resume',
        params={'type': 'resume_program'},
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({'status': 'accepted', 'command_id': validated_cmd.command_id})


@unity_control_bp.route('/program/stop', methods=['POST'])
@require_auth('operator')
def stop_program():
    """Stop program execution."""
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='stop',
        params={'type': 'stop_program'},
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({'status': 'accepted', 'command_id': validated_cmd.command_id})


# =============================================================================
# MDI (Manual Data Input)
# =============================================================================

@unity_control_bp.route('/mdi', methods=['POST'])
@require_auth('operator')
def mdi_command():
    """
    Execute MDI (G-code line).

    Request body:
    {
        "machine_id": "cnc-1",
        "gcode": "G0 X100 Y50"
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'gcode']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    validator = get_validator()

    command = {
        'type': 'gcode',
        'line': data['gcode']
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='gcode',
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({
            'error': 'Command rejected',
            'reason': message,
            'result': result.value
        }), 403

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id,
        'sanitized_gcode': validated_cmd.params.get('line')
    })


# =============================================================================
# Safety Controls
# =============================================================================

@unity_control_bp.route('/estop', methods=['POST'])
@require_auth('viewer')  # Anyone can trigger E-stop
def emergency_stop():
    """
    Trigger emergency stop.

    Request body:
    {
        "machine_id": "cnc-1",
        "reason": "operator initiated"
    }
    """
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    command = {
        'type': 'estop',
        'reason': data.get('reason', 'Unity client E-stop')
    }

    # E-stop always allowed - use VIEWER level minimum
    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.VIEWER

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='estop',
        params=command,
        auth_level=auth_level
    )

    # Execute immediately via ROS2
    ros2 = get_ros2_bridge()
    if ros2:
        ros2.send_estop(data['machine_id'])

    logger.warning(f"E-STOP triggered by {g.user_id} on {data['machine_id']}: {command['reason']}")

    command_id = validated_cmd.command_id if validated_cmd else f"estop-{int(datetime.utcnow().timestamp() * 1000)}"
    return jsonify({
        'status': 'executed',
        'command_id': command_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@unity_control_bp.route('/reset', methods=['POST'])
@require_auth('operator')
def reset_machine():
    """Reset machine after E-stop or alarm."""
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='reset',
        params={'type': 'reset'},
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({'status': 'accepted', 'command_id': validated_cmd.command_id})


@unity_control_bp.route('/home', methods=['POST'])
@require_auth('operator')
def home_machine():
    """
    Home machine axes.

    Request body:
    {
        "machine_id": "cnc-1",
        "axes": ["X", "Y", "Z"]  // optional, homes all if omitted
    }
    """
    data = request.get_json() or {}

    if 'machine_id' not in data:
        return jsonify({'error': 'machine_id is required'}), 400

    validator = get_validator()

    command = {
        'type': 'home',
        'axes': data.get('axes', ['X', 'Y', 'Z'])
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type='home',
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({'status': 'accepted', 'command_id': validated_cmd.command_id})


# =============================================================================
# Overrides
# =============================================================================

@unity_control_bp.route('/override', methods=['POST'])
@require_auth('operator')
def set_override():
    """
    Set feed or spindle override.

    Request body:
    {
        "machine_id": "cnc-1",
        "type": "feed",  // feed, rapid, spindle
        "percent": 100
    }
    """
    data = request.get_json() or {}

    required = ['machine_id', 'type', 'percent']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # Validate percent range
    percent = data['percent']
    if not (0 <= percent <= 200):
        return jsonify({'error': 'percent must be between 0 and 200'}), 400

    validator = get_validator()

    override_type = data['type']
    command_type_map = {
        'feed': 'feed_override',
        'spindle': 'spindle_override',
        'rapid': 'rapid_override'
    }
    command_type = command_type_map.get(override_type, f"{override_type}_override")

    command = {
        'type': command_type,
        'percent': percent
    }

    try:
        auth_level = AuthLevel[g.auth_level.upper()]
    except KeyError:
        auth_level = AuthLevel.OPERATOR

    result, validated_cmd, message = validator.validate_command(
        client_id=g.user_id,
        machine_id=data['machine_id'],
        command_type=command_type,
        params=command,
        auth_level=auth_level
    )

    if result != ValidationResult.VALID or validated_cmd is None:
        return jsonify({'error': 'Command rejected', 'reason': message}), 403

    return jsonify({
        'status': 'accepted',
        'command_id': validated_cmd.command_id,
        'applied_percent': validated_cmd.params.get('percent', percent)
    })


# =============================================================================
# Audit Log
# =============================================================================

@unity_control_bp.route('/audit', methods=['GET'])
@require_auth('supervisor')
def get_audit_log():
    """
    Get command audit log.

    Query params:
    - machine_id: Filter by machine
    - user_id: Filter by user
    - start_time: ISO timestamp
    - end_time: ISO timestamp
    - limit: Max records (default 100)
    """
    validator = get_validator()

    # Get filter params
    filters = {}
    if request.args.get('machine_id'):
        filters['machine_id'] = request.args.get('machine_id')
    if request.args.get('user_id'):
        filters['user_id'] = request.args.get('user_id')

    limit = min(int(request.args.get('limit', 100)), 1000)

    # Get recent audit entries
    audit_log = validator.get_audit_log(limit=limit, **filters)

    return jsonify({
        'entries': audit_log,
        'count': len(audit_log)
    })


# =============================================================================
# Rate Limit Status
# =============================================================================

@unity_control_bp.route('/rate-limits', methods=['GET'])
@require_auth('operator')
def get_rate_limits():
    """Get current rate limit status for the user."""
    validator = get_validator()

    status = validator.get_rate_limit_status(g.user_id)

    return jsonify(status)


# =============================================================================
# Health Check
# =============================================================================

@unity_control_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for Unity control service."""
    validator = get_validator()

    return jsonify({
        'status': 'healthy',
        'validator': 'active',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
