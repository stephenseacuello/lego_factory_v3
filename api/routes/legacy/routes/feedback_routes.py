"""
Feedback Loop API Routes for Flask CNC SCADA
============================================
REST API for time accuracy tracking and ML prediction.

Endpoints:
    POST   /api/feedback/time-accuracy       - Record job completion time
    GET    /api/feedback/time-accuracy/stats - Get accuracy statistics
    GET    /api/feedback/time-accuracy/trend - Get accuracy trend over time
    GET    /api/feedback/time-accuracy/recent - Get recent records
    GET    /api/feedback/time-accuracy/outliers - Get estimation outliers

    POST   /api/feedback/predict             - Predict execution time
    POST   /api/feedback/predict/gcode       - Predict from G-code content
    POST   /api/feedback/train               - Train ML model
    GET    /api/feedback/model               - Get model information
    GET    /api/feedback/correction-factors  - Get correction factors
"""

import logging
from flask import Blueprint, request, jsonify

from services.analytics import get_time_accuracy_tracker, get_ml_predictor
from services.auth_service import require_auth, require_role

logger = logging.getLogger(__name__)

bp = Blueprint('feedback', __name__, url_prefix='/api/feedback')


# ============================================================================
# Time Accuracy Endpoints
# ============================================================================

@bp.route('/time-accuracy', methods=['POST'])
@require_auth
def record_time_accuracy():
    """
    Record job completion with time accuracy data.

    Request JSON:
        {
            "job_id": "job-001",
            "estimated_sec": 300,
            "actual_sec": 285,
            "metadata": {
                "operation": "roughing",
                "material": "aluminum",
                "tool": "6mm_endmill"
            }
        }

    Response:
        - 201: Record created
        - 400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    job_id = data.get('job_id')
    estimated_sec = data.get('estimated_sec')
    actual_sec = data.get('actual_sec')

    if not all([job_id, estimated_sec is not None, actual_sec is not None]):
        return jsonify({
            'error': 'job_id, estimated_sec, and actual_sec are required'
        }), 400

    tracker = get_time_accuracy_tracker()

    try:
        record = tracker.record_completion(
            job_id=job_id,
            estimated_sec=float(estimated_sec),
            actual_sec=float(actual_sec),
            metadata=data.get('metadata', {}),
        )

        return jsonify({
            'message': 'Time accuracy recorded',
            'record': record.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Time accuracy recording error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/time-accuracy/stats', methods=['GET'])
@require_auth
def get_accuracy_stats():
    """
    Get time accuracy statistics.

    Query Parameters:
        - hours: Time window in hours (default: all data)
        - operation: Filter by operation type
        - material: Filter by material type

    Response:
        - 200: Accuracy statistics
    """
    hours = request.args.get('hours', type=float)
    operation = request.args.get('operation')
    material = request.args.get('material')

    tracker = get_time_accuracy_tracker()

    if operation:
        stats = tracker.get_statistics_by_operation(operation, hours)
    elif material:
        stats = tracker.get_statistics_by_material(material, hours)
    else:
        stats = tracker.get_statistics(hours)

    return jsonify({
        'statistics': stats.to_dict(),
        'filters': {
            'hours': hours,
            'operation': operation,
            'material': material,
        }
    })


@bp.route('/time-accuracy/trend', methods=['GET'])
@require_auth
def get_accuracy_trend():
    """
    Get time accuracy trend over time.

    Query Parameters:
        - days: Number of days (default: 7)
        - bucket_hours: Hours per data point (default: 24)

    Response:
        - 200: Trend data points
    """
    days = request.args.get('days', default=7, type=int)
    bucket_hours = request.args.get('bucket_hours', default=24, type=int)

    tracker = get_time_accuracy_tracker()
    trend = tracker.get_trend(days=days, bucket_hours=bucket_hours)

    return jsonify({
        'trend': trend,
        'days': days,
        'bucket_hours': bucket_hours,
    })


@bp.route('/time-accuracy/recent', methods=['GET'])
@require_auth
def get_recent_records():
    """
    Get most recent time accuracy records.

    Query Parameters:
        - limit: Maximum records (default: 20)

    Response:
        - 200: List of recent records
    """
    limit = request.args.get('limit', default=20, type=int)

    tracker = get_time_accuracy_tracker()
    records = tracker.get_recent_records(limit=limit)

    return jsonify({
        'records': records,
        'count': len(records),
    })


@bp.route('/time-accuracy/outliers', methods=['GET'])
@require_auth
def get_outliers():
    """
    Get jobs with significant estimation errors.

    Query Parameters:
        - threshold: Error threshold percent (default: 30)
        - hours: Time window in hours (default: 24)

    Response:
        - 200: List of outlier records
    """
    threshold = request.args.get('threshold', default=30.0, type=float)
    hours = request.args.get('hours', default=24.0, type=float)

    tracker = get_time_accuracy_tracker()
    outliers = tracker.get_outliers(
        threshold_percent=threshold,
        time_window_hours=hours
    )

    return jsonify({
        'outliers': outliers,
        'count': len(outliers),
        'threshold_percent': threshold,
        'hours': hours,
    })


@bp.route('/time-accuracy/correction-factor', methods=['GET'])
@require_auth
def get_correction_factor():
    """
    Get correction factor for time estimates.

    Query Parameters:
        - operation: Operation type
        - material: Material type
        - hours: Time window (default: 168 = 1 week)

    Response:
        - 200: Correction factor
    """
    operation = request.args.get('operation')
    material = request.args.get('material')
    hours = request.args.get('hours', default=168, type=float)

    tracker = get_time_accuracy_tracker()
    factor = tracker.get_correction_factor(
        operation=operation,
        material=material,
        time_window_hours=hours
    )

    return jsonify({
        'correction_factor': round(factor, 4),
        'operation': operation,
        'material': material,
        'hours': hours,
        'interpretation': (
            f"Multiply estimates by {factor:.3f} "
            f"({'increase' if factor > 1 else 'decrease'} estimates by "
            f"{abs((factor - 1) * 100):.1f}%)"
        )
    })


@bp.route('/time-accuracy/export', methods=['GET'])
@require_auth
@require_role('maintenance')
def export_accuracy_data():
    """
    Export all time accuracy data for backup/analysis.

    Response:
        - 200: Complete data export
    """
    tracker = get_time_accuracy_tracker()
    data = tracker.export_data()

    return jsonify(data)


# ============================================================================
# ML Prediction Endpoints
# ============================================================================

@bp.route('/predict', methods=['POST'])
@require_auth
def predict_time():
    """
    Predict execution time from G-code features.

    Request JSON:
        {
            "features": {
                "total_lines": 1500,
                "rapid_moves": 200,
                "linear_moves": 1200,
                "arc_moves": 50,
                "tool_changes": 2,
                "total_distance_mm": 5000,
                "avg_feed_rate": 800
            },
            "operation": "roughing",
            "material": "aluminum"
        }

    Response:
        - 200: Time prediction
    """
    data = request.get_json()

    if not data or 'features' not in data:
        return jsonify({'error': 'features object is required'}), 400

    predictor = get_ml_predictor()

    try:
        from services.analytics.ml_predictor import GCodeFeatures

        features = GCodeFeatures(**data['features'])
        prediction = predictor.predict_time(
            features,
            operation_type=data.get('operation'),
            material_type=data.get('material'),
        )

        return jsonify({
            'prediction': prediction.to_dict()
        })

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/predict/gcode', methods=['POST'])
@require_auth
def predict_from_gcode():
    """
    Predict execution time from G-code content.

    Request JSON:
        {
            "gcode": "G0 X0 Y0\\nG1 X10 Y10 F500\\n...",
            "operation": "roughing",
            "material": "aluminum"
        }

    Response:
        - 200: Time prediction with extracted features
    """
    data = request.get_json()

    if not data or 'gcode' not in data:
        return jsonify({'error': 'gcode content is required'}), 400

    predictor = get_ml_predictor()

    try:
        # Extract features
        features = predictor.extract_features(data['gcode'])

        # Predict
        prediction = predictor.predict_time(
            features,
            operation_type=data.get('operation'),
            material_type=data.get('material'),
        )

        return jsonify({
            'features': features.to_dict(),
            'prediction': prediction.to_dict(),
        })

    except Exception as e:
        logger.error(f"G-code prediction error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/train', methods=['POST'])
@require_auth
@require_role('maintenance')
def train_model():
    """
    Train ML model on historical data.

    Request JSON:
        {
            "training_data": [
                {
                    "features": {...},
                    "actual_time_sec": 300
                },
                {
                    "gcode": "G0 X0...",
                    "actual_time_sec": 285
                }
            ]
        }

    Response:
        - 200: Training results
        - 400: Invalid request
    """
    data = request.get_json()

    if not data or 'training_data' not in data:
        return jsonify({'error': 'training_data array is required'}), 400

    predictor = get_ml_predictor()

    try:
        result = predictor.train(data['training_data'])
        return jsonify(result)

    except Exception as e:
        logger.error(f"Training error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/train/from-history', methods=['POST'])
@require_auth
@require_role('maintenance')
def train_from_history():
    """
    Train ML model from time accuracy history.

    This endpoint pulls data from the time accuracy tracker
    and trains the ML model.

    Request JSON (optional):
        {
            "hours": 720,     // Time window (default: 30 days)
            "min_samples": 20 // Minimum samples required
        }

    Response:
        - 200: Training results
        - 400: Insufficient data
    """
    data = request.get_json() or {}

    hours = data.get('hours', 720)  # 30 days
    min_samples = data.get('min_samples', 20)

    tracker = get_time_accuracy_tracker()
    predictor = get_ml_predictor()

    # Get records from tracker
    stats = tracker.get_statistics(hours)

    if stats.sample_count < min_samples:
        return jsonify({
            'error': f'Insufficient samples ({stats.sample_count}), need at least {min_samples}'
        }), 400

    # Note: In a full implementation, we'd need to store the G-code features
    # with each time record. For now, return guidance.
    return jsonify({
        'message': 'Historical training requires G-code features stored with time records',
        'available_samples': stats.sample_count,
        'guidance': 'Use POST /api/feedback/train with full training_data array'
    })


@bp.route('/model', methods=['GET'])
@require_auth
def get_model_info():
    """
    Get information about the ML model.

    Response:
        - 200: Model information
    """
    predictor = get_ml_predictor()
    info = predictor.get_model_info()

    return jsonify(info)


@bp.route('/correction-factors', methods=['GET'])
@require_auth
def get_all_correction_factors():
    """
    Get all configured correction factors.

    Response:
        - 200: Dictionary of correction factors
    """
    predictor = get_ml_predictor()
    info = predictor.get_model_info()

    return jsonify({
        'correction_factors': info['correction_factors']
    })


@bp.route('/correction-factors', methods=['POST'])
@require_auth
@require_role('maintenance')
def set_correction_factor():
    """
    Set a correction factor.

    Request JSON:
        {
            "key": "roughing",
            "factor": 1.15
        }

    Response:
        - 200: Factor set
    """
    data = request.get_json()

    if not data or 'key' not in data or 'factor' not in data:
        return jsonify({'error': 'key and factor are required'}), 400

    predictor = get_ml_predictor()
    predictor.set_correction_factor(
        key=data['key'],
        factor=float(data['factor'])
    )

    return jsonify({
        'message': 'Correction factor set',
        'key': data['key'],
        'factor': float(data['factor'])
    })


# ============================================================================
# Dashboard Summary
# ============================================================================

@bp.route('/dashboard', methods=['GET'])
@require_auth
def get_dashboard_data():
    """
    Get summary data for feedback loop dashboard.

    Response:
        - 200: Dashboard summary data
    """
    tracker = get_time_accuracy_tracker()
    predictor = get_ml_predictor()

    # Get statistics for different time windows
    stats_24h = tracker.get_statistics(24)
    stats_7d = tracker.get_statistics(168)
    stats_30d = tracker.get_statistics(720)

    # Get recent trend
    trend = tracker.get_trend(days=7, bucket_hours=24)

    # Get model info
    model_info = predictor.get_model_info()

    return jsonify({
        'statistics': {
            'last_24h': stats_24h.to_dict(),
            'last_7d': stats_7d.to_dict(),
            'last_30d': stats_30d.to_dict(),
        },
        'trend': trend,
        'model': {
            'ml_available': model_info['has_sklearn'],
            'model_trained': model_info['ml_model_trained'],
            'training_samples': model_info['training_samples'],
        },
        'correction_factors': model_info['correction_factors'],
    })
