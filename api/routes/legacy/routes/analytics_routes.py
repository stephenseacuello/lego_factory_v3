"""
Analytics API Routes for Flask CNC SCADA System
================================================
API endpoints for advanced analytics services.

Includes:
- Vibration FFT analysis
- Anomaly detection
- Quality prediction
- Machine fleet management
- CAM integration
- Digital twin

Author: Flask CNC SCADA System
"""

import logging
from flask import Blueprint, jsonify, request

from services.auth_service import require_auth, require_permission, optional_auth
from services.vibration_analysis import get_vibration_analyzer, analyze_vibration_batch
from services.anomaly_detection import get_anomaly_detector, check_sensor_anomalies
from services.quality_prediction import get_quality_predictor
from services.machine_manager import get_machine_manager, MachineConfig
from services.cam_link import get_cam_link
from services.digital_twin import get_digital_twin, update_twin_from_tinyg
from services.oee_service import get_oee_service, DowntimeType, LossCategory
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# =============================================================================
# Vibration Analysis Endpoints
# =============================================================================

@bp.route('/vibration/analyze', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def analyze_vibration():
    """
    Analyze vibration data batch.

    Request JSON:
        {
            "sensor_id": 1,
            "samples": [{"ax": 0, "ay": 0, "az": 1}, ...]
        }

    Response:
        {
            "results": [VibrationResult, ...]
        }
    """
    data = request.get_json() or {}
    sensor_id = data.get('sensor_id', 1)
    samples = data.get('samples', [])

    if not samples:
        return jsonify({"error": "No samples provided"}), 400

    results = analyze_vibration_batch(sensor_id, samples)

    return jsonify({
        "success": True,
        "results": [
            {
                "timestamp": r.timestamp,
                "rms": r.rms,
                "peak": r.peak,
                "crest_factor": r.crest_factor,
                "dominant_frequency": r.dominant_frequency,
                "severity": r.severity,
                "health_score": r.health_score,
                "fault_indicators": r.fault_indicators,
                "frequency_bands": r.frequency_bands
            }
            for r in results
        ],
        "count": len(results)
    })


@bp.route('/vibration/fft/<int:sensor_id>', methods=['GET'])
@optional_auth
def get_vibration_fft(sensor_id: int):
    """
    Get last FFT analysis result for sensor.

    Response includes full frequency spectrum for visualization.
    """
    analyzer = get_vibration_analyzer()
    baseline = analyzer.get_baseline(sensor_id)

    return jsonify({
        "success": True,
        "sensor_id": sensor_id,
        "baseline": baseline,
        "spindle_freq": analyzer.spindle_freq
    })


@bp.route('/vibration/config', methods=['PUT'])
@require_auth
@require_permission('configure_machine')
def configure_vibration():
    """Update vibration analyzer configuration."""
    data = request.get_json() or {}
    analyzer = get_vibration_analyzer()

    if 'spindle_rpm' in data:
        analyzer.set_spindle_rpm(data['spindle_rpm'])

    return jsonify({
        "success": True,
        "spindle_freq": analyzer.spindle_freq
    })


# =============================================================================
# Anomaly Detection Endpoints
# =============================================================================

@bp.route('/anomaly/check', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def check_anomalies():
    """
    Check sensor data for anomalies.

    Request JSON:
        {
            "sensor_id": 1,
            "data": {"temperature": 45.0, "rms": 1.5, ...}
        }
    """
    data = request.get_json() or {}
    sensor_id = data.get('sensor_id', 1)
    sensor_data = data.get('data', {})

    anomalies = check_sensor_anomalies(sensor_id, sensor_data)

    return jsonify({
        "success": True,
        "anomalies": [a.to_dict() for a in anomalies],
        "count": len(anomalies)
    })


@bp.route('/anomaly/baselines', methods=['GET'])
@optional_auth
def get_baselines():
    """Get all anomaly detection baselines."""
    detector = get_anomaly_detector()
    return jsonify({
        "success": True,
        "baselines": detector.get_all_baselines()
    })


@bp.route('/anomaly/baselines/<int:sensor_id>', methods=['DELETE'])
@require_auth
@require_permission('calibrate_sensors')
def reset_baseline(sensor_id: int):
    """Reset baseline for sensor."""
    metric = request.args.get('metric')
    detector = get_anomaly_detector()
    detector.reset_baseline(sensor_id, metric)

    return jsonify({
        "success": True,
        "message": f"Reset baseline for sensor {sensor_id}"
    })


@bp.route('/anomaly/recent', methods=['GET'])
@optional_auth
def get_recent_anomalies():
    """Get recent anomalies."""
    limit = request.args.get('limit', 100, type=int)
    detector = get_anomaly_detector()
    anomalies = detector.get_recent_anomalies(limit)

    return jsonify({
        "success": True,
        "anomalies": [a.to_dict() for a in anomalies],
        "count": len(anomalies)
    })


# =============================================================================
# Quality Prediction Endpoints
# =============================================================================

@bp.route('/quality/start', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def start_quality_tracking():
    """Start quality tracking for new part."""
    data = request.get_json() or {}
    part_id = data.get('part_id')

    predictor = get_quality_predictor()
    predictor.start_part(part_id)

    return jsonify({
        "success": True,
        "part_id": predictor._current_part_id
    })


@bp.route('/quality/predict', methods=['GET'])
@optional_auth
def get_quality_prediction():
    """Get current quality prediction."""
    predictor = get_quality_predictor()
    prediction = predictor.get_current_prediction()

    return jsonify({
        "success": True,
        "prediction": {
            "score": prediction.predicted_score,
            "confidence": prediction.confidence,
            "risk_level": prediction.risk_level,
            "risk_factors": prediction.risk_factors,
            "recommendations": prediction.recommendations
        }
    })


@bp.route('/quality/end', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def end_quality_tracking():
    """End part and optionally label quality."""
    data = request.get_json() or {}

    predictor = get_quality_predictor()

    # If quality score provided, record as training data
    if 'score' in data:
        predictor.label_part(
            overall_score=data['score'],
            dimension_ok=data.get('dimension_ok', True),
            surface_ok=data.get('surface_ok', True),
            notes=data.get('notes', '')
        )

    prediction = predictor.get_current_prediction()

    return jsonify({
        "success": True,
        "final_prediction": {
            "score": prediction.predicted_score,
            "risk_level": prediction.risk_level
        }
    })


@bp.route('/quality/train', methods=['POST'])
@require_auth
@require_permission('calibrate_sensors')
def train_quality_model():
    """Train quality prediction model."""
    predictor = get_quality_predictor()
    result = predictor.train()
    return jsonify(result)


@bp.route('/quality/stats', methods=['GET'])
@optional_auth
def get_quality_stats():
    """Get quality prediction statistics."""
    predictor = get_quality_predictor()
    return jsonify({
        "success": True,
        "statistics": predictor.get_statistics()
    })


# =============================================================================
# Machine Fleet Management Endpoints
# =============================================================================

@bp.route('/machines', methods=['GET'])
@optional_auth
def list_machines():
    """List all registered machines."""
    manager = get_machine_manager()
    status = request.args.get('status')
    location = request.args.get('location')

    machines = manager.list_machines(status=status, location=location)

    return jsonify({
        "success": True,
        "machines": [m.to_dict() for m in machines],
        "count": len(machines)
    })


@bp.route('/machines', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def register_machine():
    """Register new machine."""
    data = request.get_json() or {}

    required = ['machine_id', 'name']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    manager = get_machine_manager()

    config = None
    if 'config' in data:
        config = MachineConfig(**data['config'])

    machine = manager.register_machine(
        machine_id=data['machine_id'],
        name=data['name'],
        location=data.get('location', ''),
        machine_type=data.get('machine_type', 'mill_3axis'),
        description=data.get('description', ''),
        config=config
    )

    return jsonify({
        "success": True,
        "machine": machine.to_dict()
    }), 201


@bp.route('/machines/<machine_id>', methods=['GET'])
@optional_auth
def get_machine(machine_id: str):
    """Get machine details."""
    manager = get_machine_manager()
    machine = manager.get_machine(machine_id)

    if not machine:
        return jsonify({"error": "Machine not found"}), 404

    return jsonify({
        "success": True,
        "machine": machine.to_dict()
    })


@bp.route('/machines/<machine_id>', methods=['DELETE'])
@require_auth
@require_permission('configure_machine')
def delete_machine(machine_id: str):
    """Unregister machine."""
    manager = get_machine_manager()

    if not manager.unregister_machine(machine_id):
        return jsonify({"error": "Machine not found"}), 404

    return jsonify({
        "success": True,
        "message": f"Machine {machine_id} unregistered"
    })


@bp.route('/machines/fleet', methods=['GET'])
@optional_auth
def get_fleet_status():
    """Get fleet status summary."""
    manager = get_machine_manager()
    return jsonify({
        "success": True,
        "fleet": manager.get_fleet_status()
    })


# =============================================================================
# CAM Integration Endpoints
# =============================================================================

@bp.route('/cam/jobs', methods=['GET'])
@optional_auth
def list_cam_jobs():
    """List imported CAM jobs."""
    cam = get_cam_link()
    return jsonify({
        "success": True,
        "jobs": cam.list_jobs()
    })


@bp.route('/cam/import', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def import_gcode():
    """Import G-code file."""
    data = request.get_json() or {}
    filepath = data.get('filepath')

    if not filepath:
        return jsonify({"error": "filepath required"}), 400

    try:
        cam = get_cam_link()
        job = cam.import_gcode(filepath)

        return jsonify({
            "success": True,
            "job": {
                "job_id": job.job_id,
                "filename": job.filename,
                "operations": len(job.operations),
                "tools": len(job.tools),
                "estimated_time": job.estimated_time_seconds
            }
        }), 201
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/cam/jobs/<job_id>', methods=['GET'])
@optional_auth
def get_cam_job(job_id: str):
    """Get CAM job details."""
    cam = get_cam_link()
    job = cam.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "success": True,
        "job": {
            "job_id": job.job_id,
            "filename": job.filename,
            "program_name": job.program_name,
            "cam_software": job.cam_software,
            "operations": [
                {
                    "name": op.name,
                    "type": op.type,
                    "tool": op.tool_number,
                    "feed": op.feed_rate,
                    "spindle": op.spindle_rpm
                }
                for op in job.operations
            ],
            "tools": [
                {
                    "number": t.number,
                    "name": t.name,
                    "diameter": t.diameter
                }
                for t in job.tools
            ],
            "bounds": job.get_bounds(),
            "estimated_time": job.estimated_time_seconds
        }
    })


@bp.route('/cam/jobs/<job_id>/toolpath', methods=['GET'])
@optional_auth
def get_toolpath(job_id: str):
    """Get toolpath preview data."""
    simplify = request.args.get('simplify', 'true').lower() == 'true'

    cam = get_cam_link()
    points = cam.get_toolpath_preview(job_id, simplify=simplify)

    if not points:
        return jsonify({"error": "Job not found or no toolpath"}), 404

    return jsonify({
        "success": True,
        "points": points,
        "count": len(points)
    })


@bp.route('/cam/scan', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def scan_gcode_directory():
    """Scan and auto-import new G-code files."""
    cam = get_cam_link()
    imported = cam.auto_import_new()

    return jsonify({
        "success": True,
        "imported": [
            {"job_id": job.job_id, "filename": job.filename}
            for job in imported
        ],
        "count": len(imported)
    })


# =============================================================================
# Digital Twin Endpoints
# =============================================================================

@bp.route('/twin/<machine_id>/state', methods=['GET'])
@optional_auth
def get_twin_state(machine_id: str):
    """Get digital twin render state."""
    twin = get_digital_twin(machine_id)
    return jsonify({
        "success": True,
        "state": twin.get_render_state()
    })


@bp.route('/twin/<machine_id>/trail', methods=['GET'])
@optional_auth
def get_twin_trail(machine_id: str):
    """Get toolpath trail for visualization."""
    max_points = request.args.get('max_points', 1000, type=int)

    twin = get_digital_twin(machine_id)
    return jsonify({
        "success": True,
        "trail": twin.get_trail(max_points)
    })


@bp.route('/twin/<machine_id>/geometry', methods=['GET'])
@optional_auth
def get_twin_geometry(machine_id: str):
    """Get machine geometry for 3D model."""
    twin = get_digital_twin(machine_id)
    return jsonify({
        "success": True,
        "geometry": twin.get_machine_geometry()
    })


@bp.route('/twin/<machine_id>/trail', methods=['DELETE'])
@require_auth
@require_permission('run_gcode')
def clear_twin_trail(machine_id: str):
    """Clear toolpath trail."""
    twin = get_digital_twin(machine_id)
    twin.clear_trail()
    return jsonify({"success": True, "message": "Trail cleared"})


@bp.route('/twin/<machine_id>/stock', methods=['PUT'])
@require_auth
@require_permission('configure_machine')
def set_twin_stock(machine_id: str):
    """Set stock dimensions for digital twin."""
    data = request.get_json() or {}

    twin = get_digital_twin(machine_id)
    twin.set_stock(
        width=data.get('width', 100),
        depth=data.get('depth', 100),
        height=data.get('height', 25),
        origin_x=data.get('origin_x', 0),
        origin_y=data.get('origin_y', 0),
        origin_z=data.get('origin_z', 0),
        material=data.get('material', 'aluminum')
    )

    return jsonify({"success": True})


# =============================================================================
# OEE (Overall Equipment Effectiveness) Endpoints
# =============================================================================

@bp.route('/oee/scores', methods=['GET'])
@optional_auth
def get_oee_scores():
    """
    Get OEE scores for all machines (for scheduler use).

    Query Parameters:
        hours: Hours to look back (default: 24)

    Response:
        {
            "success": true,
            "scores": {
                "machine-01": 0.85,
                "machine-02": 0.72,
                ...
            },
            "details": {
                "machine-01": {
                    "oee": 85.0,
                    "availability": 92.0,
                    "performance": 95.0,
                    "quality": 97.5
                },
                ...
            }
        }
    """
    hours = request.args.get('hours', 24, type=int)

    oee_service = get_oee_service()
    manager = get_machine_manager()

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    scores = {}
    details = {}

    for machine in manager.list_machines():
        try:
            metrics = oee_service.calculate_oee(
                machine.machine_id,
                start_time,
                end_time
            )
            scores[machine.machine_id] = round(metrics.oee / 100, 3)  # 0.0-1.0 scale
            details[machine.machine_id] = {
                'oee': round(metrics.oee, 1),
                'availability': round(metrics.availability, 1),
                'performance': round(metrics.performance, 1),
                'quality': round(metrics.quality, 1)
            }
        except Exception as e:
            logger.warning(f"Could not calculate OEE for {machine.machine_id}: {e}")
            scores[machine.machine_id] = 0.0
            details[machine.machine_id] = {
                'oee': 0.0,
                'availability': 0.0,
                'performance': 0.0,
                'quality': 0.0
            }

    return jsonify({
        "success": True,
        "period_hours": hours,
        "scores": scores,
        "details": details
    })


@bp.route('/oee/<machine_id>', methods=['GET'])
@optional_auth
def get_machine_oee(machine_id: str):
    """
    Get OEE metrics for a specific machine.

    Query Parameters:
        start: ISO timestamp (default: 24h ago)
        end: ISO timestamp (default: now)
        shift_date: Date for shift-based OEE (YYYY-MM-DD)
        shift_start_hour: Hour shift starts (default: 6)

    Response includes full OEE breakdown.
    """
    oee_service = get_oee_service()

    # Check for shift-based calculation
    shift_date = request.args.get('shift_date')
    if shift_date:
        try:
            date = datetime.fromisoformat(shift_date)
            shift_start = request.args.get('shift_start_hour', 6, type=int)
            metrics = oee_service.calculate_shift_oee(
                machine_id,
                date,
                shift_start_hour=shift_start
            )
            return jsonify({
                "success": True,
                "oee": metrics.to_dict()
            })
        except ValueError as e:
            return jsonify({"error": f"Invalid date format: {e}"}), 400

    # Time-range based calculation
    end_str = request.args.get('end')
    start_str = request.args.get('start')

    end_time = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()
    start_time = datetime.fromisoformat(start_str) if start_str else end_time - timedelta(hours=24)

    metrics = oee_service.calculate_oee(machine_id, start_time, end_time)

    return jsonify({
        "success": True,
        "oee": metrics.to_dict()
    })


@bp.route('/oee/<machine_id>/trend', methods=['GET'])
@optional_auth
def get_oee_trend(machine_id: str):
    """
    Get OEE trend over time.

    Query Parameters:
        hours: Total hours to analyze (default: 24)
        interval: Interval per point in hours (default: 1)
    """
    hours = request.args.get('hours', 24, type=int)
    interval = request.args.get('interval', 1, type=int)

    oee_service = get_oee_service()

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    trend = oee_service.get_oee_trend(
        machine_id,
        start_time,
        end_time,
        interval_hours=interval
    )

    return jsonify({
        "success": True,
        "machine_id": machine_id,
        "trend": trend
    })


@bp.route('/oee/<machine_id>/mtbf', methods=['GET'])
@optional_auth
def get_mtbf_metrics(machine_id: str):
    """
    Get MTBF/MTTR reliability metrics.

    Query Parameters:
        hours: Hours to analyze (default: 168 = 1 week)
    """
    hours = request.args.get('hours', 168, type=int)

    oee_service = get_oee_service()

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    metrics = oee_service.calculate_mtbf_mttr(machine_id, start_time, end_time)

    return jsonify({
        "success": True,
        "mtbf": metrics.to_dict()
    })


@bp.route('/oee/<machine_id>/downtime', methods=['GET'])
@optional_auth
def get_downtime_pareto(machine_id: str):
    """
    Get Pareto analysis of downtime reasons.

    Query Parameters:
        hours: Hours to analyze (default: 168 = 1 week)
        limit: Max reasons to return (default: 10)
    """
    hours = request.args.get('hours', 168, type=int)
    limit = request.args.get('limit', 10, type=int)

    oee_service = get_oee_service()

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    pareto = oee_service.get_downtime_pareto(
        machine_id,
        start_time,
        end_time,
        limit=limit
    )

    return jsonify({
        "success": True,
        "machine_id": machine_id,
        "pareto": pareto
    })


@bp.route('/oee/<machine_id>/downtime', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def record_downtime_start(machine_id: str):
    """
    Record start of downtime event.

    Request JSON:
        {
            "type": "unplanned",  // or "planned"
            "reason_code": "MECH01",
            "description": "Bearing failure",
            "loss_category": "equipment_failure",
            "operator_id": "op123"
        }
    """
    data = request.get_json() or {}

    oee_service = get_oee_service()

    downtime_type = DowntimeType.PLANNED if data.get('type') == 'planned' else DowntimeType.UNPLANNED

    loss_category = None
    if data.get('loss_category'):
        try:
            loss_category = LossCategory(data['loss_category'])
        except ValueError:
            pass

    event = oee_service.record_downtime_start(
        machine_id=machine_id,
        downtime_type=downtime_type,
        reason_code=data.get('reason_code'),
        reason_description=data.get('description', ''),
        loss_category=loss_category,
        operator_id=data.get('operator_id')
    )

    return jsonify({
        "success": True,
        "event": event.to_dict()
    }), 201


@bp.route('/oee/downtime/<event_id>/end', methods=['POST'])
@require_auth
@require_permission('configure_machine')
def record_downtime_end(event_id: str):
    """
    Record end of downtime event.

    Request JSON:
        {
            "notes": "Replaced bearing"
        }
    """
    data = request.get_json() or {}

    oee_service = get_oee_service()
    event = oee_service.record_downtime_end(
        event_id=event_id,
        notes=data.get('notes', '')
    )

    if not event:
        return jsonify({"error": "Downtime event not found"}), 404

    return jsonify({
        "success": True,
        "event": event.to_dict()
    })


@bp.route('/oee/downtime/active', methods=['GET'])
@optional_auth
def get_active_downtime():
    """
    Get currently active (unclosed) downtime events.

    Query Parameters:
        machine_id: Optional filter by machine
    """
    machine_id = request.args.get('machine_id')

    oee_service = get_oee_service()
    active = oee_service.get_active_downtime(machine_id)

    return jsonify({
        "success": True,
        "active": [e.to_dict() for e in active],
        "count": len(active)
    })


@bp.route('/oee/<machine_id>/production', methods=['POST'])
@require_auth
@require_permission('run_gcode')
def record_production(machine_id: str):
    """
    Record production counts.

    Request JSON:
        {
            "good": 10,
            "scrap": 1,
            "rework": 0
        }
    """
    data = request.get_json() or {}

    oee_service = get_oee_service()
    oee_service.record_production(
        machine_id=machine_id,
        good_count=data.get('good', 0),
        scrap_count=data.get('scrap', 0),
        rework_count=data.get('rework', 0)
    )

    return jsonify({
        "success": True,
        "message": f"Production recorded for {machine_id}"
    })


@bp.route('/oee/<machine_id>/cycle-time', methods=['PUT'])
@require_auth
@require_permission('configure_machine')
def set_cycle_time(machine_id: str):
    """
    Set ideal cycle time for OEE calculation.

    Request JSON:
        {
            "cycle_time_min": 1.5  // minutes per piece
        }
    """
    data = request.get_json() or {}

    if 'cycle_time_min' not in data:
        return jsonify({"error": "cycle_time_min required"}), 400

    oee_service = get_oee_service()
    oee_service.set_ideal_cycle_time(
        machine_id,
        data['cycle_time_min']
    )

    return jsonify({
        "success": True,
        "message": f"Cycle time set for {machine_id}"
    })
