"""
MCC DAQ Routes Module
=====================
API routes for MCC DAQ recorder operations.

Authentication:
- GET endpoints: optional_auth (public read)
- POST operations: require_auth with appropriate permissions

Author: Flask CNC SCADA System
"""

from flask import Blueprint, jsonify, request

from core.controllers.mcc_controller import MCCRecorder
from services.influxdb_service import InfluxDBService
from services.auth_service import (
    require_auth,
    require_permission,
    optional_auth
)

# Create blueprint
bp = Blueprint('mcc', __name__)

# Global recorder instance
mcc_recorder = MCCRecorder()
influx_service = InfluxDBService()


@bp.route('/status')
@optional_auth
def get_status():
    """
    Get MCC DAQ recorder status.

    Auth: Optional

    Returns:
        JSON with recorder status and current statistics
    """
    status = mcc_recorder.status()
    return jsonify({
        "success": True,
        "status": status
    })


@bp.route('/test_connection', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def test_connection():
    """
    Test connection to MCC helper.

    Auth: Requires 'configure_machine' permission (maintenance+)

    Request JSON:
        {
            "timeout_ms": 1000  # optional, default 1000
        }

    Returns:
        JSON with connection test result
    """
    data = request.get_json() or {}
    timeout_ms = data.get('timeout_ms', 1000)

    try:
        timeout_ms = int(timeout_ms)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Invalid timeout value"
        }), 400

    success, message = mcc_recorder.test_connection(timeout_ms)

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/start', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def start_recording():
    """
    Start MCC DAQ recording.

    Auth: Requires 'view_sensors' permission (operator+)

    Request JSON:
        {
            "experiment_name": "test",  # optional
            "trial_number": 1           # optional
        }

    Returns:
        JSON with start result
    """
    data = request.get_json() or {}
    experiment_name = data.get('experiment_name', '')
    trial_number = data.get('trial_number')

    # Set session tags for InfluxDB
    if influx_service.is_available():
        influx_service.set_session_tags(experiment_name, trial_number)

    success, message = mcc_recorder.start(
        experiment_name=experiment_name,
        trial_number=trial_number
    )

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/stop', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def stop_recording():
    """
    Stop MCC DAQ recording.

    Auth: Requires 'view_sensors' permission (operator+)

    Returns:
        JSON with stop result
    """
    success, message = mcc_recorder.stop()

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/stats')
@optional_auth
def get_current_stats():
    """
    Get current real-time statistics.

    Auth: Optional

    Returns:
        JSON with current motor current statistics
    """
    stats = mcc_recorder.get_current_stats()

    return jsonify({
        "success": True,
        "stats": stats
    })
