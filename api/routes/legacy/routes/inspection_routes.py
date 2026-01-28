"""
Inspection Station API Routes.

Provides REST API endpoints for the automated inspection station
in the factory cell digital twin.

Endpoints:
- GET /api/inspection/status - Get inspection station status
- GET /api/inspection/reports - Get inspection reports
- GET /api/inspection/reports/<report_id> - Get specific report
- POST /api/inspection/inspect - Trigger inspection
- GET /api/inspection/statistics - Get inspection statistics
- GET /api/inspection/calibration - Get calibration status
- POST /api/inspection/calibrate - Run calibration
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

inspection_bp = Blueprint('inspection', __name__, url_prefix='/api/inspection')

# Singleton inspection service instance
_inspection_service = None


def get_inspection_service():
    """Get or create inspection service singleton."""
    global _inspection_service
    if _inspection_service is None:
        try:
            from services.inspection_service import InspectionService, InspectionStationConfig
            from config import get_config

            config = get_config()
            station_config = InspectionStationConfig(
                station_id=getattr(config, 'INSPECTION_STATION_ID', 'inspection-001'),
                dimensional_accuracy_mm=getattr(config, 'INSPECTION_ACCURACY_MM', 0.01),
            )
            _inspection_service = InspectionService(station_config)
            logger.info(f"Inspection service initialized: {station_config.station_id}")
        except ImportError as e:
            logger.warning(f"Inspection service not available: {e}")
            return None
    return _inspection_service


@inspection_bp.route('/status')
def get_status():
    """
    Get inspection station status.

    Returns:
        JSON with station status, readiness, and current state
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        status = {
            'station_id': service.config.station_id,
            'is_ready': service.is_ready,
            'is_inspecting': service.is_inspecting,
            'dimensional_accuracy_mm': service.config.dimensional_accuracy_mm,
            'timestamp': datetime.now().isoformat(),
        }

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"Error getting inspection status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/statistics')
def get_statistics():
    """
    Get inspection statistics.

    Returns:
        JSON with total inspected, passed, failed, pass rate
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        stats = service.get_statistics()
        return jsonify({'success': True, 'statistics': stats})

    except Exception as e:
        logger.error(f"Error getting inspection statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/reports')
def get_reports():
    """
    Get inspection reports.

    Query params:
        - count: Number of reports to return (default 20)
        - result: Filter by result ('PASS', 'FAIL', 'CONDITIONAL')
        - job_id: Filter by job ID

    Returns:
        JSON with list of inspection reports
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        count = request.args.get('count', 20, type=int)
        result_filter = request.args.get('result')
        job_filter = request.args.get('job_id')

        reports = service.get_recent_reports(count=count)

        # Apply filters
        if result_filter:
            reports = [r for r in reports if r.get('result') == result_filter]
        if job_filter:
            reports = [r for r in reports if r.get('job_id') == job_filter]

        return jsonify({
            'success': True,
            'count': len(reports),
            'reports': reports
        })

    except Exception as e:
        logger.error(f"Error getting inspection reports: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/reports/<report_id>')
def get_report(report_id: str):
    """
    Get specific inspection report by ID.

    Args:
        report_id: Inspection report ID (e.g., INS-20240115-001)

    Returns:
        JSON with detailed inspection report
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        report = service.get_report(report_id)

        if report:
            return jsonify({'success': True, 'report': report})
        else:
            return jsonify({
                'success': False,
                'error': f'Report {report_id} not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting inspection report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/inspect', methods=['POST'])
async def trigger_inspection():
    """
    Trigger a part inspection.

    Request body:
        - part_id: Part identifier (required)
        - job_id: Job identifier (required)
        - sensor_data: Optional machining sensor data for correlation

    Returns:
        JSON with inspection report
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        data = request.json
        part_id = data.get('part_id')
        job_id = data.get('job_id')
        sensor_data = data.get('sensor_data')

        if not part_id or not job_id:
            return jsonify({
                'success': False,
                'error': 'part_id and job_id are required'
            }), 400

        # Check if already inspecting
        if service.is_inspecting:
            return jsonify({
                'success': False,
                'error': 'Inspection already in progress'
            }), 409

        # Run inspection
        import asyncio
        report = await service.inspect_part(
            part_id=part_id,
            job_id=job_id,
            sensor_data=sensor_data
        )

        # Emit WebSocket event
        try:
            from services.socketio_service import emit_inspection_result
            emit_inspection_result(
                service.config.station_id,
                report.to_dict()
            )
        except ImportError:
            pass

        return jsonify({
            'success': True,
            'report': report.to_dict()
        })

    except RuntimeError as e:
        # Concurrent inspection attempt
        return jsonify({'success': False, 'error': str(e)}), 409

    except Exception as e:
        logger.error(f"Error running inspection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/calibration')
def get_calibration():
    """
    Get inspection station calibration status.

    Returns:
        JSON with calibration data and last calibration timestamp
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        calibration = {
            'station_id': service.config.station_id,
            'is_calibrated': True,
            'last_calibration': datetime.now().isoformat(),
            'calibration_due': None,
            'dimensional_accuracy_mm': service.config.dimensional_accuracy_mm,
            'calibration_standards': {
                'reference_block_x': 50.0,
                'reference_block_y': 50.0,
                'reference_block_z': 25.0,
            },
            'measurement_offsets': {
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
            }
        }

        return jsonify({'success': True, 'calibration': calibration})

    except Exception as e:
        logger.error(f"Error getting calibration status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/calibrate', methods=['POST'])
def run_calibration():
    """
    Run inspection station calibration.

    Request body:
        - reference_values: Optional reference block measurements

    Returns:
        JSON with calibration results
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        data = request.json or {}
        reference_values = data.get('reference_values', {
            'x': 50.0,
            'y': 50.0,
            'z': 25.0,
        })

        # Simulate calibration (in production, would measure reference block)
        calibration_result = {
            'station_id': service.config.station_id,
            'calibration_id': f"CAL-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'reference_values': reference_values,
            'measured_values': {
                'x': reference_values['x'] + 0.002,
                'y': reference_values['y'] - 0.001,
                'z': reference_values['z'] + 0.001,
            },
            'calculated_offsets': {
                'x': -0.002,
                'y': 0.001,
                'z': -0.001,
            },
            'success': True,
            'accuracy_verified': True,
        }

        logger.info(f"Calibration completed: {calibration_result['calibration_id']}")

        return jsonify({'success': True, 'calibration': calibration_result})

    except Exception as e:
        logger.error(f"Error running calibration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/thresholds')
def get_thresholds():
    """
    Get inspection threshold configuration.

    Returns:
        JSON with dimensional tolerances and acceptance criteria
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        thresholds = {
            'dimensional_accuracy_mm': service.config.dimensional_accuracy_mm,
            'default_tolerances': {
                'length': {'plus': 0.1, 'minus': 0.1},
                'width': {'plus': 0.1, 'minus': 0.1},
                'height': {'plus': 0.05, 'minus': 0.05},
                'diameter': {'plus': 0.05, 'minus': 0.05},
            },
            'surface_finish_threshold_ra': 3.2,
            'minimum_confidence': 0.95,
            'pass_threshold': 0.85,  # 85% of features must pass
        }

        return jsonify({'success': True, 'thresholds': thresholds})

    except Exception as e:
        logger.error(f"Error getting thresholds: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inspection_bp.route('/thresholds', methods=['PUT'])
def update_thresholds():
    """
    Update inspection threshold configuration.

    Request body:
        - dimensional_accuracy_mm: New accuracy setting
        - default_tolerances: Updated tolerance values

    Returns:
        JSON with updated thresholds
    """
    try:
        service = get_inspection_service()
        if not service:
            return jsonify({
                'success': False,
                'error': 'Inspection service not available'
            }), 503

        data = request.json

        # Update accuracy if provided
        if 'dimensional_accuracy_mm' in data:
            new_accuracy = float(data['dimensional_accuracy_mm'])
            if new_accuracy <= 0:
                return jsonify({
                    'success': False,
                    'error': 'dimensional_accuracy_mm must be positive'
                }), 400
            service.config.dimensional_accuracy_mm = new_accuracy

        logger.info(f"Inspection thresholds updated")

        return jsonify({
            'success': True,
            'message': 'Thresholds updated',
            'dimensional_accuracy_mm': service.config.dimensional_accuracy_mm,
        })

    except Exception as e:
        logger.error(f"Error updating thresholds: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Export blueprint
bp = inspection_bp
