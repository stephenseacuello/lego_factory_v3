"""
LEGO Factory v3 - ML View Routes
=================================
Machine Learning and analytics dashboards.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

ml_bp = Blueprint('ml', __name__, url_prefix='/ml')


@ml_bp.route('/fingerprint')
def fingerprint():
    """GCode fingerprinting dashboard."""
    return render_template('ml/fingerprint.html')


@ml_bp.route('/anomaly')
def anomaly():
    """Anomaly detection dashboard."""
    return render_template('ml/anomaly.html')


@ml_bp.route('/tool-wear')
def tool_wear():
    """Tool wear prediction dashboard."""
    return render_template('ml/tool_wear.html')


@ml_bp.route('/training')
def training():
    """Model training dashboard."""
    return render_template('ml/training.html')


@ml_bp.route('/models')
def models():
    """Model management dashboard."""
    return render_template('ml/models.html')


@ml_bp.route('/api/predict', methods=['POST'])
def predict():
    """Run ML prediction."""
    data = request.json

    try:
        from services.ml.inference_service import get_inference_service
        service = get_inference_service()

        result = service.predict(
            sensor_data=data.get('sensor_data'),
            model_type=data.get('model_type', 'fingerprint')
        )
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/api/anomaly-score', methods=['POST'])
def anomaly_score():
    """Calculate anomaly score."""
    data = request.json

    try:
        from services.ml.inference_service import get_inference_service
        service = get_inference_service()

        score = service.get_anomaly_score(
            sensor_data=data.get('sensor_data'),
            machine_id=data.get('machine_id')
        )
        return jsonify({'anomaly_score': score})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
