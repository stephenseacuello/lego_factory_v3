"""
Bantam Desktop CNC Sensor API Routes.

Provides REST API endpoints for Bantam Desktop Explorer CNC
sensor monitoring and adaptive feedback.

Endpoints:
- GET /api/bantam/status - Get CNC status
- GET /api/bantam/sensors - Get current sensor readings
- GET /api/bantam/sensors/history - Get sensor history
- GET /api/bantam/statistics - Get sensor statistics
- GET /api/bantam/alerts - Get active alerts
- GET /api/bantam/feedback - Get adaptive feedback recommendations
- POST /api/bantam/simulation/start - Start sensor simulation
- POST /api/bantam/simulation/stop - Stop sensor simulation
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

bantam_bp = Blueprint('bantam', __name__, url_prefix='/api/bantam')

# Singleton sensor service instance
_sensor_service = None


def get_sensor_service():
    """Get or create Bantam sensor service singleton."""
    global _sensor_service
    if _sensor_service is None:
        try:
            from services.bantam_sensor_service import BantamSensorService, BantamSensorConfig
            from config import get_config

            config = get_config()
            sensor_config = BantamSensorConfig(
                machine_id=getattr(config, 'BANTAM_ID', 'bantam-001'),
                simulation_mode=True,
                thresholds={
                    'spindle_temp_warning': getattr(config, 'BANTAM_SPINDLE_TEMP_WARNING', 45.0),
                    'spindle_temp_critical': getattr(config, 'BANTAM_SPINDLE_TEMP_CRITICAL', 55.0),
                    'vibration_warning': getattr(config, 'BANTAM_VIBRATION_WARNING', 1.5),
                    'vibration_critical': getattr(config, 'BANTAM_VIBRATION_CRITICAL', 2.5),
                }
            )
            _sensor_service = BantamSensorService(sensor_config)
            logger.info(f"Bantam sensor service initialized: {sensor_config.machine_id}")
        except ImportError as e:
            logger.warning(f"Bantam sensor service not available: {e}")
            return None
    return _sensor_service


@bantam_bp.route('/status')
def get_status():
    """
    Get Bantam CNC status.

    Returns:
        JSON with machine status, connection state, and mode
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        from config import get_config
        config = get_config()

        status = {
            'machine_id': service.config.machine_id,
            'is_running': service.is_running,
            'simulation_mode': service.config.simulation_mode,
            'sample_rate_hz': service.config.sample_rate_hz,
            'work_envelope': {
                'x': getattr(config, 'BANTAM_WORK_X', [0, 140]),
                'y': getattr(config, 'BANTAM_WORK_Y', [0, 114]),
                'z': getattr(config, 'BANTAM_WORK_Z', [-38, 0]),
            },
            'timestamp': datetime.now().isoformat(),
        }

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"Error getting Bantam status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/sensors')
def get_sensors():
    """
    Get current sensor readings.

    Returns:
        JSON with all current sensor values
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        reading = service.get_current_reading()

        if reading:
            sensor_data = {
                'timestamp': reading.timestamp.isoformat() if hasattr(reading, 'timestamp') else datetime.now().isoformat(),
                'spindle_temp_c': reading.spindle_temp_c,
                'ambient_temp_c': reading.ambient_temp_c,
                'vibration': {
                    'x_g': reading.vibration_x_g,
                    'y_g': reading.vibration_y_g,
                    'z_g': reading.vibration_z_g,
                    'rms_g': reading.vibration_rms_g,
                },
                'spindle_current_a': reading.spindle_current_a,
                'spindle_rpm': getattr(reading, 'spindle_rpm', 0),
                'feed_rate_mmpm': getattr(reading, 'feed_rate_mmpm', 0),
            }
        else:
            sensor_data = {
                'timestamp': datetime.now().isoformat(),
                'spindle_temp_c': 0.0,
                'ambient_temp_c': 22.0,
                'vibration': {'x_g': 0.0, 'y_g': 0.0, 'z_g': 0.0, 'rms_g': 0.0},
                'spindle_current_a': 0.0,
                'spindle_rpm': 0,
                'feed_rate_mmpm': 0,
                'note': 'No readings available - simulation may not be running',
            }

        return jsonify({'success': True, 'sensors': sensor_data})

    except Exception as e:
        logger.error(f"Error getting sensor readings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/sensors/history')
def get_sensor_history():
    """
    Get sensor reading history.

    Query params:
        - minutes: Time window in minutes (default 5)
        - limit: Maximum readings to return (default 100)

    Returns:
        JSON with historical sensor readings
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        minutes = request.args.get('minutes', 5, type=int)
        limit = request.args.get('limit', 100, type=int)

        history = service.get_history(minutes=minutes, limit=limit)

        return jsonify({
            'success': True,
            'count': len(history),
            'time_window_minutes': minutes,
            'history': history
        })

    except Exception as e:
        logger.error(f"Error getting sensor history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/statistics')
def get_statistics():
    """
    Get sensor statistics.

    Returns:
        JSON with aggregated statistics from sensor readings
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        stats = service.get_statistics()
        return jsonify({'success': True, 'statistics': stats})

    except Exception as e:
        logger.error(f"Error getting sensor statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/alerts')
def get_alerts():
    """
    Get active alerts.

    Query params:
        - severity: Filter by severity ('warning', 'critical')
        - acknowledged: Filter by acknowledgement status

    Returns:
        JSON with list of active alerts
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        severity_filter = request.args.get('severity')
        ack_filter = request.args.get('acknowledged')

        alerts = service.get_alerts()

        # Apply filters
        if severity_filter:
            alerts = [a for a in alerts if a.get('severity') == severity_filter]
        if ack_filter is not None:
            ack_bool = ack_filter.lower() == 'true'
            alerts = [a for a in alerts if a.get('acknowledged') == ack_bool]

        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': alerts
        })

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id: str):
    """
    Acknowledge an alert.

    Args:
        alert_id: Alert identifier

    Returns:
        JSON with acknowledgement status
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        data = request.json or {}
        operator_id = data.get('operator_id', 'unknown')

        result = service.acknowledge_alert(alert_id, operator_id)

        if result:
            return jsonify({
                'success': True,
                'message': f'Alert {alert_id} acknowledged by {operator_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Alert {alert_id} not found'
            }), 404

    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/feedback')
def get_feedback():
    """
    Get adaptive feedback recommendations.

    Returns feed rate and speed adjustments based on
    current sensor readings for Fusion 360 CAM optimization.

    Returns:
        JSON with adaptive feedback recommendations
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        feedback = service.get_adaptive_feedback()

        return jsonify({'success': True, 'feedback': feedback})

    except Exception as e:
        logger.error(f"Error getting adaptive feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/thresholds')
def get_thresholds():
    """
    Get sensor alert thresholds.

    Returns:
        JSON with all configured thresholds
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        thresholds = service.config.thresholds

        return jsonify({'success': True, 'thresholds': thresholds})

    except Exception as e:
        logger.error(f"Error getting thresholds: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/thresholds', methods=['PUT'])
def update_thresholds():
    """
    Update sensor alert thresholds.

    Request body:
        - spindle_temp_warning: Warning threshold for spindle temp
        - spindle_temp_critical: Critical threshold for spindle temp
        - vibration_warning: Warning threshold for vibration RMS
        - vibration_critical: Critical threshold for vibration RMS

    Returns:
        JSON with updated thresholds
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        data = request.json

        # Update thresholds
        for key in ['spindle_temp_warning', 'spindle_temp_critical',
                    'vibration_warning', 'vibration_critical']:
            if key in data:
                service.config.thresholds[key] = float(data[key])

        logger.info(f"Bantam thresholds updated: {service.config.thresholds}")

        return jsonify({
            'success': True,
            'message': 'Thresholds updated',
            'thresholds': service.config.thresholds
        })

    except Exception as e:
        logger.error(f"Error updating thresholds: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/simulation/start', methods=['POST'])
def start_simulation():
    """
    Start sensor simulation.

    Request body (optional):
        - profile: Simulation profile ('idle', 'machining', 'aggressive')

    Returns:
        JSON with simulation status
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        if service.is_running:
            return jsonify({
                'success': False,
                'error': 'Simulation already running'
            }), 409

        data = request.json or {}
        profile = data.get('profile', 'machining')

        service.start_simulation(profile=profile)

        logger.info(f"Bantam sensor simulation started: profile={profile}")

        return jsonify({
            'success': True,
            'message': 'Simulation started',
            'profile': profile,
            'sample_rate_hz': service.config.sample_rate_hz
        })

    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/simulation/stop', methods=['POST'])
def stop_simulation():
    """
    Stop sensor simulation.

    Returns:
        JSON with stop status
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        if not service.is_running:
            return jsonify({
                'success': False,
                'error': 'Simulation not running'
            }), 409

        service.stop_simulation()

        logger.info("Bantam sensor simulation stopped")

        return jsonify({
            'success': True,
            'message': 'Simulation stopped'
        })

    except Exception as e:
        logger.error(f"Error stopping simulation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/machining/progress')
def get_machining_progress():
    """
    Get current machining operation progress.

    Returns:
        JSON with current operation details and progress
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        progress = service.get_machining_progress()

        return jsonify({'success': True, 'progress': progress})

    except Exception as e:
        logger.error(f"Error getting machining progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bantam_bp.route('/tool')
def get_tool_info():
    """
    Get current tool information.

    Returns:
        JSON with active tool details
    """
    try:
        service = get_sensor_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Bantam sensor service not available'
            }), 503

        tool_info = {
            'tool_number': 1,
            'tool_type': 'end_mill',
            'diameter_mm': 3.175,
            'flutes': 2,
            'material': 'carbide',
            'max_rpm': 28000,
            'max_doc_mm': 1.0,
            'tool_life_remaining_pct': 85.0,
        }

        return jsonify({'success': True, 'tool': tool_info})

    except Exception as e:
        logger.error(f"Error getting tool info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Export blueprint
bp = bantam_bp
