"""
TinyG Routes Module
===================
API routes for TinyG CNC controller operations.

Authentication:
- GET /status: optional_auth (public read, authenticated gets more detail)
- POST operations: require_auth with appropriate permissions

Author: Flask CNC SCADA System
"""

import re
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

from config import get_config
from core.controllers.tinyg_controller import TinyGController
from services.influxdb_service import InfluxDBService
from services.auth_service import (
    require_auth,
    require_permission,
    optional_auth,
    get_current_user
)
from api.utils.responses import (
    success_response,
    error_response,
    validation_error_response,
    not_found_response,
    service_unavailable_response,
    hardware_error_response,
    validate_request,
    ErrorCodes,
)
from api.schemas.tinyg import (
    ConnectRequest,
    PollingRequest,
    AutoReconnectConfig,
    DryRunPositionRequest,
)
from api.schemas.gcode import (
    GCodeCommand,
    GCodeFileRequest,
    JogRequest,
    ZeroAxisRequest,
)
from pydantic import ValidationError

# Setup logger
logger = logging.getLogger(__name__)

# Load configuration
config = get_config()

# G-code validation constants
MAX_GCODE_LENGTH = 256  # Maximum characters per command
# Allow letters, numbers, whitespace, arithmetic, brackets, punctuation, and quotes for TinyG JSON commands
GCODE_ALLOWED_PATTERN = re.compile(r'^[A-Za-z0-9\s\.\-\+\*\/\(\)\[\]\{\}\;\:\,\$\#\%\=\!\"\']+$')

# Allowed G-code file extensions
ALLOWED_GCODE_EXTENSIONS = {'.gcode', '.nc', '.tap', '.ngc'}


def validate_gcode_command(command: str) -> tuple[bool, str]:
    """
    Validate a G-code command for safety.

    Args:
        command: G-code command string

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not command or not isinstance(command, str):
        return False, "Command must be a non-empty string"

    # Strip whitespace
    command = command.strip()

    # Length check
    if len(command) > MAX_GCODE_LENGTH:
        return False, f"Command exceeds maximum length of {MAX_GCODE_LENGTH} characters"

    # Character validation - only allow safe characters
    if not GCODE_ALLOWED_PATTERN.match(command):
        return False, "Command contains invalid characters"

    # Log the command for audit purposes
    logger.info(f"G-code command: {command}")

    return True, ""


def validate_gcode_filepath(filepath: str) -> tuple[bool, str, str]:
    """
    Validate that a G-code filepath is within the allowed directory.

    Args:
        filepath: Path to G-code file

    Returns:
        Tuple of (is_valid: bool, error_message: str, safe_path: str)
    """
    if not filepath or not isinstance(filepath, str):
        return False, "Filepath must be a non-empty string", ""

    try:
        # Get the configured G-code directory
        gcode_dir = Path(config.GCODE_DIR).resolve()

        # Handle both absolute and relative paths
        requested_path = Path(filepath)

        # If relative path, resolve relative to GCODE_DIR
        if not requested_path.is_absolute():
            full_path = gcode_dir / requested_path
        else:
            full_path = requested_path

        # Resolve to get absolute path
        resolved_path = full_path.resolve()

        # Security check 1: Must be within GCODE_DIR
        if not str(resolved_path).startswith(str(gcode_dir)):
            logger.warning(f"Path traversal attempt blocked: {filepath}")
            return False, "File must be within the G-code directory", ""

        # Security check 2: No symlinks
        if full_path.exists() and full_path.is_symlink():
            return False, "Symlinks not allowed", ""

        # Security check 3: Extension whitelist
        if resolved_path.suffix.lower() not in ALLOWED_GCODE_EXTENSIONS:
            return False, f"File type not allowed. Allowed: {', '.join(ALLOWED_GCODE_EXTENSIONS)}", ""

        # Security check 4: File exists
        if not resolved_path.exists():
            return False, "File not found", ""

        return True, "", str(resolved_path)

    except Exception as e:
        logger.error(f"Error validating G-code filepath: {e}")
        return False, "Invalid file path", ""

# Create blueprint
bp = Blueprint('tinyg', __name__)

# Global controller instance (will be better managed later with application context)
tinyg = TinyGController()
influx_service = InfluxDBService()


@bp.route('/status')
@optional_auth
def get_status():
    """
    Get TinyG controller status.

    Auth: Optional (more details for authenticated users)

    Returns:
        JSON with controller status
    """
    status = tinyg.status()
    return jsonify({
        "success": True,
        "status": status
    })


@bp.route('/connect', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def connect():
    """
    Connect to TinyG controller.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "port": "/dev/ttyUSB0",
            "baud": 115200  # optional
        }

    Returns:
        JSON with connection result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = ConnectRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    result, message = tinyg.connect(validated.port, validated.baud)

    if result:
        return success_response(
            message=message,
            data={"port": validated.port, "machine_id": validated.machine_id}
        )
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.CONNECTION_FAILED,
        )


@bp.route('/disconnect', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def disconnect():
    """
    Disconnect from TinyG controller.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Returns:
        JSON with disconnection result
    """
    result, message = tinyg.disconnect()

    if result:
        return success_response(message=message)
    else:
        return error_response(
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
            status_code=400,
        )


@bp.route('/start_polling', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def start_polling():
    """
    Start polling TinyG for status reports.

    Auth: Requires 'run_gcode' permission (operator+)

    Request JSON:
        {
            "experiment_name": "test",   # optional
            "trial_number": 1,           # optional
            "interval": 0.05             # optional, poll interval in seconds
        }

    Returns:
        JSON with start result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = PollingRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    # Set session tags for InfluxDB
    if influx_service.is_available():
        influx_service.set_session_tags(validated.experiment_name, validated.trial_number)

    result, message = tinyg.start_polling(
        experiment_name=validated.experiment_name,
        trial_number=validated.trial_number,
        interval=validated.interval
    )

    if result:
        return success_response(
            message=message,
            data={"interval": validated.interval, "experiment_name": validated.experiment_name}
        )
    else:
        return error_response(
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
            status_code=400,
        )


@bp.route('/stop_polling', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def stop_polling():
    """
    Stop polling TinyG.

    Auth: Requires 'run_gcode' permission (operator+)

    Returns:
        JSON with stop result
    """
    result, message = tinyg.stop_polling()

    if result:
        return success_response(message=message)
    else:
        return error_response(
            message=message,
            code=ErrorCodes.STATE_CONFLICT,
            status_code=400,
        )


@bp.route('/send', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def send_gcode():
    """
    Send a single G-code command.

    Auth: Requires 'run_gcode' permission (operator+)

    Request JSON:
        {
            "command": "G0 X10 Y10"
        }

    Returns:
        JSON with send result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = GCodeCommand.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    # Additional G-code specific validation
    is_valid, error_msg = validate_gcode_command(validated.command)
    if not is_valid:
        return error_response(
            message=error_msg,
            code=ErrorCodes.INVALID_GCODE,
            field="command",
        )

    result, message = tinyg.send_gcode(validated.command.strip())

    if result:
        return success_response(message=message, data={"command": validated.command})
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.SERIAL_ERROR,
        )


@bp.route('/load_gcode', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def load_gcode():
    """
    Load G-code file for execution.

    Auth: Requires 'run_gcode' permission (operator+)

    Request JSON:
        {
            "filepath": "file.gcode"  # Relative to GCODE_DIR or absolute within it
        }

    Returns:
        JSON with load result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = GCodeFileRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    # Validate filepath is within GCODE_DIR
    is_valid, error_msg, safe_path = validate_gcode_filepath(validated.filepath)
    if not is_valid:
        if "not found" in error_msg.lower():
            return not_found_response("G-code file", validated.filepath)
        return error_response(
            message=error_msg,
            code=ErrorCodes.INVALID_PARAMETER,
            field="filepath",
        )

    result, message = tinyg.load_gcode_file(safe_path)

    if result:
        return success_response(message=message, data={"filepath": safe_path})
    else:
        return error_response(
            message=message,
            code=ErrorCodes.INTERNAL_ERROR,
            status_code=500,
        )


@bp.route('/run_gcode', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def run_gcode():
    """
    Run loaded G-code file.

    Auth: Requires 'run_gcode' permission (operator+)

    Returns:
        JSON with run result
    """
    result, message = tinyg.run_gcode()

    if result:
        return success_response(message=message)
    else:
        return error_response(
            message=message,
            code=ErrorCodes.STATE_CONFLICT,
            status_code=400,
        )


@bp.route('/jog', methods=['POST'])
@require_auth
@require_permission('jog_machine')
def jog():
    """
    Jog machine in specified axis.

    Auth: Requires 'jog_machine' permission (operator+)

    Request JSON:
        {
            "axis": "X",        # X, Y, or Z
            "distance": 10.0,   # mm
            "speed": 1000       # mm/min, optional
        }

    Returns:
        JSON with jog result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = JogRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    result, message = tinyg.jog(validated.axis, validated.distance, validated.speed)

    if result:
        return success_response(
            message=message,
            data={"axis": validated.axis, "distance": validated.distance}
        )
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
        )


@bp.route('/zero', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def zero_axis():
    """
    Zero work coordinate for specified axis.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "axis": "X"  # X, Y, Z, or ALL
        }

    Returns:
        JSON with zero result
    """
    data = request.get_json() or {}

    # Validate request with Pydantic schema
    try:
        validated = ZeroAxisRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    result, message = tinyg.zero_axis(validated.axis)

    if result:
        return success_response(message=message, data={"axis": validated.axis})
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
        )


@bp.route('/feed_hold', methods=['POST'])
@require_auth
@require_permission('pause_resume')
def feed_hold():
    """
    Send feed hold command (pause).

    Auth: Requires 'pause_resume' permission (operator+)

    Returns:
        JSON with feed hold result
    """
    result, message = tinyg.feed_hold()

    if result:
        return success_response(message=message)
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
        )


@bp.route('/cycle_start', methods=['POST'])
@require_auth
@require_permission('pause_resume')
def cycle_start():
    """
    Send cycle start / resume command.

    Auth: Requires 'pause_resume' permission (operator+)

    Note: For safer operation, consider using /safe_resume instead,
    which verifies machine position before resuming.

    Returns:
        JSON with cycle start result
    """
    result, message = tinyg.cycle_start()

    if result:
        return success_response(message=message)
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
        )


@bp.route('/safe_resume', methods=['POST'])
@require_auth
@require_permission('pause_resume')
def safe_resume():
    """
    Safely resume after feed hold with position verification.

    This endpoint verifies the machine is at the expected position
    before resuming motion. If the machine has drifted, it will
    refuse to resume unless force=True is set.

    Auth: Requires 'pause_resume' permission (operator+)

    Request JSON (optional):
        {
            "force": false  // Set to true to override position verification
        }

    Returns:
        JSON with:
        - success: Whether resume was successful
        - message: Status message
        - verification: Position verification details
    """
    data = request.get_json() or {}
    force = data.get('force', False)

    result, message, verification = tinyg.safe_resume(force=force)

    if result:
        return success_response(
            message=message,
            data={"verification": verification}
        )
    else:
        return error_response(
            message=message,
            code=ErrorCodes.STATE_CONFLICT,
            status_code=409,
            details={"verification": verification},
        )


@bp.route('/feed_hold/status', methods=['GET'])
@optional_auth
def feed_hold_status():
    """
    Get current feed hold status and position information.

    Returns:
        JSON with:
        - feed_hold_active: Whether feed hold is currently active
        - stored_position: Position when feed hold was triggered
        - current_position: Current machine position
        - position_delta: Difference between stored and current position
        - within_tolerance: Whether position drift is acceptable
        - tolerance: Current position tolerance setting
    """
    status = tinyg.get_feed_hold_status()

    return success_response(data={"feed_hold": status})


@bp.route('/feed_hold/tolerance', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def set_position_tolerance():
    """
    Set the position tolerance for feed hold resume verification.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "tolerance": 0.01  // Tolerance in mm
        }

    Returns:
        JSON with result
    """
    from api.schemas.tinyg import PositionToleranceRequest

    data = request.get_json() or {}

    try:
        validated = PositionToleranceRequest.model_validate(data)
    except ValidationError as e:
        return validation_error_response(e)

    result, message = tinyg.set_position_tolerance(validated.tolerance)

    if result:
        return success_response(message=message, data={"tolerance": validated.tolerance})
    else:
        return error_response(
            message=message,
            code=ErrorCodes.INVALID_PARAMETER,
            field="tolerance",
        )


@bp.route('/queue_flush', methods=['POST'])
@require_auth
@require_permission('emergency_stop')
def queue_flush():
    """
    Flush the planner queue (emergency stop).

    Auth: Requires 'emergency_stop' permission (operator+)

    Returns:
        JSON with queue flush result
    """
    result, message = tinyg.queue_flush()

    if result:
        return success_response(message=message)
    else:
        return hardware_error_response(
            device="TinyG",
            message=message,
            code=ErrorCodes.DEVICE_NOT_CONNECTED,
        )


# =============================================================================
# Soft Limits API
# =============================================================================

@bp.route('/limits', methods=['GET'])
@optional_auth
def get_limits():
    """
    Get current soft limits configuration.

    Auth: Optional (public read)

    Returns:
        JSON with soft limits configuration and current position status
    """
    from services.soft_limits_service import get_soft_limits_service

    soft_limits = get_soft_limits_service()
    config = soft_limits.get_config()

    # Get current position from TinyG status
    status = tinyg.status()
    pos = status.get('last_status', {})
    x = pos.get('wx', 0) or pos.get('posx', 0) or 0
    y = pos.get('wy', 0) or pos.get('posy', 0) or 0
    z = pos.get('wz', 0) or pos.get('posz', 0) or 0

    position_status = soft_limits.get_position_status(x, y, z)

    return success_response(data={
        "config": config,
        "position": {"x": x, "y": y, "z": z},
        "position_status": position_status
    })


@bp.route('/limits', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def set_limits():
    """
    Update soft limits for an axis.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "axis": "x",       # Required: x, y, or z
            "min": -10.0,      # Optional: new minimum
            "max": 300.0,      # Optional: new maximum
            "enabled": true    # Optional: enable/disable this axis
        }

    Returns:
        JSON with updated configuration
    """
    from services.soft_limits_service import get_soft_limits_service

    data = request.get_json() or {}
    axis = data.get('axis')

    if not axis:
        return jsonify({
            "success": False,
            "error": "Axis is required (x, y, or z)"
        }), 400

    try:
        soft_limits = get_soft_limits_service()
        soft_limits.set_axis_limits(
            axis=axis,
            min_val=data.get('min'),
            max_val=data.get('max'),
            enabled=data.get('enabled')
        )

        return jsonify({
            "success": True,
            "message": f"Updated {axis.upper()} limits",
            "config": soft_limits.get_config()
        })
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@bp.route('/limits/enable', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def toggle_limits():
    """
    Enable or disable soft limits globally.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "enabled": true  # or false
        }

    Returns:
        JSON with updated configuration
    """
    from services.soft_limits_service import get_soft_limits_service

    data = request.get_json() or {}
    enabled = data.get('enabled')

    if enabled is None:
        return jsonify({
            "success": False,
            "error": "enabled field is required (true or false)"
        }), 400

    soft_limits = get_soft_limits_service()
    soft_limits.set_enabled(bool(enabled))

    return jsonify({
        "success": True,
        "message": f"Soft limits {'enabled' if enabled else 'disabled'}",
        "config": soft_limits.get_config()
    })


@bp.route('/limits/thresholds', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def set_thresholds():
    """
    Set warning and danger zone thresholds.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "warning": 0.10,  # 10% from limit triggers warning
            "danger": 0.05   # 5% from limit triggers danger
        }

    Returns:
        JSON with updated configuration
    """
    from services.soft_limits_service import get_soft_limits_service

    data = request.get_json() or {}

    soft_limits = get_soft_limits_service()
    soft_limits.set_thresholds(
        warning=data.get('warning'),
        danger=data.get('danger')
    )

    return jsonify({
        "success": True,
        "message": "Updated thresholds",
        "config": soft_limits.get_config()
    })


@bp.route('/limits/check', methods=['POST'])
@optional_auth
def check_move():
    """
    Check if a move would violate soft limits.

    Auth: Optional (public read)

    Request JSON:
        {
            "x": 100.0,  # Target X (or omit if not moving X)
            "y": 50.0,   # Target Y (or omit if not moving Y)
            "z": -10.0   # Target Z (or omit if not moving Z)
        }

    Returns:
        JSON with check result
    """
    from services.soft_limits_service import get_soft_limits_service

    data = request.get_json() or {}

    soft_limits = get_soft_limits_service()
    allowed, message = soft_limits.check_move(
        x=data.get('x'),
        y=data.get('y'),
        z=data.get('z')
    )

    return jsonify({
        "success": True,
        "allowed": allowed,
        "message": message
    })


# ==================== Dry Run Mode ====================

@bp.route('/dryrun', methods=['GET'])
@optional_auth
def get_dry_run_status():
    """
    Get dry run mode status.

    Auth: Optional (public read)

    Returns:
        JSON with dry run status and simulated position
    """
    status = tinyg.status()

    return jsonify({
        "success": True,
        "dry_run": status.get('dry_run', False),
        "position": status.get('dry_run_position'),
        "message": "Dry run mode is " + ("ENABLED" if status.get('dry_run') else "DISABLED")
    })


@bp.route('/dryrun', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def set_dry_run():
    """
    Enable or disable dry run mode.

    In dry run mode, G-code commands are parsed and position is simulated
    but nothing is sent to the machine. Useful for testing programs.

    Auth: Required with 'run_gcode' permission

    Request JSON:
        {
            "enabled": true  # true to enable, false to disable
        }

    Returns:
        JSON with result
    """
    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    success, message = tinyg.set_dry_run(enabled)

    return jsonify({
        "success": success,
        "dry_run": tinyg.is_dry_run(),
        "position": tinyg.get_dry_run_position() if tinyg.is_dry_run() else None,
        "message": message
    })


@bp.route('/dryrun/position', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def set_dry_run_position():
    """
    Set the simulated position in dry run mode.

    Auth: Required with 'run_gcode' permission

    Request JSON:
        {
            "x": 0.0,  # X position (optional)
            "y": 0.0,  # Y position (optional)
            "z": 0.0   # Z position (optional)
        }

    Returns:
        JSON with result
    """
    if not tinyg.is_dry_run():
        return jsonify({
            "success": False,
            "message": "Dry run mode is not enabled"
        }), 400

    data = request.get_json() or {}

    success, message = tinyg.set_dry_run_position(
        x=data.get('x'),
        y=data.get('y'),
        z=data.get('z')
    )

    return jsonify({
        "success": success,
        "position": tinyg.get_dry_run_position(),
        "message": message
    })


@bp.route('/dryrun/simulate', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def simulate_gcode():
    """
    Simulate a G-code command without sending to machine.

    This temporarily enables dry run mode if not already enabled,
    simulates the command, and returns the result.

    Auth: Required with 'run_gcode' permission

    Request JSON:
        {
            "command": "G1 X100 Y50 F1000"
        }

    Returns:
        JSON with simulation result
    """
    data = request.get_json() or {}
    command = data.get('command', '').strip()

    if not command:
        return jsonify({
            "success": False,
            "message": "No command provided"
        }), 400

    # Validate command
    is_valid, error_msg = validate_gcode_command(command)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    # Get current dry run state
    was_dry_run = tinyg.is_dry_run()
    position_before = tinyg.get_dry_run_position()

    # Enable dry run if needed
    if not was_dry_run:
        tinyg.set_dry_run(True)

    # Send command (will be simulated)
    success, message = tinyg.send_gcode(command)

    position_after = tinyg.get_dry_run_position()

    # Restore previous dry run state
    if not was_dry_run:
        tinyg.set_dry_run(False)

    return jsonify({
        "success": success,
        "command": command,
        "position_before": position_before,
        "position_after": position_after,
        "message": message
    })


# ==================== Auto-Reconnect ====================

@bp.route('/reconnect', methods=['GET'])
@optional_auth
def get_reconnect_status():
    """
    Get auto-reconnect configuration and status.

    Auth: Optional (public read)

    Returns:
        JSON with auto-reconnect status
    """
    status = tinyg.get_auto_reconnect_status()

    return jsonify({
        "success": True,
        **status
    })


@bp.route('/reconnect', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def set_reconnect():
    """
    Configure auto-reconnect behavior.

    Auth: Required with 'configure_machine' permission

    Request JSON:
        {
            "enabled": true,        # Enable/disable auto-reconnect
            "max_attempts": 10,     # Optional: max attempts
            "base_delay": 1.0,      # Optional: initial delay (seconds)
            "max_delay": 30.0       # Optional: max delay (seconds)
        }

    Returns:
        JSON with result
    """
    data = request.get_json() or {}

    if 'enabled' not in data:
        return jsonify({
            "success": False,
            "message": "Missing 'enabled' field"
        }), 400

    success, message = tinyg.set_auto_reconnect(
        enabled=data['enabled'],
        max_attempts=data.get('max_attempts'),
        base_delay=data.get('base_delay'),
        max_delay=data.get('max_delay')
    )

    return jsonify({
        "success": success,
        "message": message,
        **tinyg.get_auto_reconnect_status()
    })


@bp.route('/reconnect/cancel', methods=['POST'])
@require_auth
@require_permission('control_machine')
def cancel_reconnect():
    """
    Cancel any ongoing reconnection attempts.

    Auth: Required with 'control_machine' permission

    Returns:
        JSON with result
    """
    success, message = tinyg.cancel_reconnect()

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/reconnect/trigger', methods=['POST'])
@require_auth
@require_permission('control_machine')
def trigger_reconnect():
    """
    Manually trigger a reconnection attempt.

    Auth: Required with 'control_machine' permission

    Returns:
        JSON with result
    """
    status = tinyg.status()

    if status.get('connected'):
        return jsonify({
            "success": False,
            "message": "Already connected"
        }), 400

    reconnect_status = tinyg.get_auto_reconnect_status()

    if not reconnect_status.get('last_port'):
        return jsonify({
            "success": False,
            "message": "No previous connection info available"
        }), 400

    if tinyg.is_reconnecting():
        return jsonify({
            "success": False,
            "message": "Already attempting to reconnect"
        }), 400

    # Trigger reconnect
    tinyg._start_auto_reconnect()

    return jsonify({
        "success": True,
        "message": f"Reconnection started to {reconnect_status['last_port']}"
    })
