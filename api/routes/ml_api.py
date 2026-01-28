"""
LEGO Factory v3 - ML Inference API
==================================
REST API endpoints for Machine Learning inference and anomaly detection.

Provides endpoints for:
- Model management
- Real-time inference
- Fingerprint generation and comparison
- Anomaly detection
- Training data export
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import numpy as np

logger = logging.getLogger(__name__)

ml_api_bp = Blueprint('ml_api', __name__, url_prefix='/api/ml')


def get_inference_service():
    """Get ML inference service instance."""
    try:
        from services.ml.inference.inference_service import inference_service
        return inference_service
    except Exception as e:
        logger.warning(f"ML inference service not available: {e}")
        return None


def get_model_registry():
    """Get model registry instance."""
    try:
        from services.ml.inference.inference_service import model_registry
        return model_registry
    except Exception as e:
        logger.warning(f"Model registry not available: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Service Status
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/status', methods=['GET'])
def service_status():
    """Get ML service status."""
    service = get_inference_service()

    if not service:
        return jsonify({
            'available': False,
            'error': 'ML inference service not initialized',
        })

    stats = service.get_stats()

    return jsonify({
        'available': True,
        'model_loaded': stats['model_loaded'],
        'device': stats['device'],
        'inference_count': stats['inference_count'],
        'running': stats['running'],
        'config': {
            'anomaly_threshold': service.config.anomaly_threshold,
            'sequence_length': service.config.sequence_length,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Model Management
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/models', methods=['GET'])
@jwt_required()
def list_models():
    """List registered models."""
    registry = get_model_registry()

    if not registry:
        return _demo_models()

    models = registry.list_models()

    model_info = []
    for name in models:
        config = registry.get_config(name)
        model_info.append({
            'name': name,
            'config': config,
        })

    return jsonify({
        'models': model_info,
        'count': len(models),
    })


@ml_api_bp.route('/models/<model_name>/load', methods=['POST'])
@jwt_required()
def load_model(model_name: str):
    """
    Load a model from checkpoint.

    JSON body:
    - model_path: Path to model checkpoint (required)
    - model_type: Model type (mm_dtae_lstm, enhanced_encoder)
    """
    service = get_inference_service()

    if not service:
        return jsonify({'error': 'ML inference service not available'}), 503

    data = request.get_json()
    if not data or 'model_path' not in data:
        return jsonify({'error': 'model_path required'}), 400

    model_path = data['model_path']
    model_type = data.get('model_type', 'mm_dtae_lstm')

    try:
        service.load_model(model_path, model_type)
        return jsonify({
            'status': 'loaded',
            'model_name': model_name,
            'model_type': model_type,
            'model_path': model_path,
        })
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Inference
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/predict', methods=['POST'])
@jwt_required()
def predict():
    """
    Run inference on sensor data.

    JSON body:
    - sensor_data: 2D array of sensor readings [time, features]
    - return_fingerprint: Whether to return fingerprint (default: true)
    """
    service = get_inference_service()

    if not service:
        return _demo_prediction()

    data = request.get_json()
    if not data or 'sensor_data' not in data:
        return jsonify({'error': 'sensor_data required'}), 400

    try:
        sensor_data = np.array(data['sensor_data'])

        if service._model is None:
            return _demo_prediction()

        results = service.predict(sensor_data)

        response = {
            'inference_id': results['inference_id'],
            'timestamp': results['timestamp'],
            'anomaly_score': float(results['anomaly_score'].mean()),
            'anomaly_detected': results.get('anomaly_detected', False),
            'classification': results['classification'].tolist(),
        }

        if data.get('return_fingerprint', True):
            response['fingerprint'] = results['fingerprint'].tolist()

        return jsonify(response)

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/encode', methods=['POST'])
@jwt_required()
def encode():
    """
    Encode sensor data to fingerprint embedding.

    JSON body:
    - sensor_data: 2D array of sensor readings [time, features]
    """
    service = get_inference_service()

    if not service:
        return _demo_fingerprint()

    data = request.get_json()
    if not data or 'sensor_data' not in data:
        return jsonify({'error': 'sensor_data required'}), 400

    try:
        sensor_data = np.array(data['sensor_data'])
        fingerprint = service.encode(sensor_data)

        return jsonify({
            'fingerprint': fingerprint.tolist(),
            'dimensions': fingerprint.shape,
            'timestamp': datetime.utcnow().isoformat(),
        })

    except RuntimeError as e:
        return _demo_fingerprint()
    except Exception as e:
        logger.error(f"Encoding error: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Fingerprint Comparison
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/compare', methods=['POST'])
@jwt_required()
def compare_fingerprints():
    """
    Compare two fingerprints.

    JSON body:
    - fingerprint1: First fingerprint array
    - fingerprint2: Second fingerprint array
    """
    service = get_inference_service()

    if not service:
        return jsonify({'error': 'ML inference service not available'}), 503

    data = request.get_json()
    if not data or 'fingerprint1' not in data or 'fingerprint2' not in data:
        return jsonify({'error': 'fingerprint1 and fingerprint2 required'}), 400

    try:
        fp1 = np.array(data['fingerprint1'])
        fp2 = np.array(data['fingerprint2'])

        similarity = service.compare_fingerprints(fp1, fp2)

        threshold = service.config.fingerprint_similarity_threshold
        is_match = similarity >= threshold

        return jsonify({
            'similarity': similarity,
            'is_match': is_match,
            'threshold': threshold,
            'confidence': abs(similarity - threshold) / (1 - threshold) if not is_match else abs(similarity - threshold) / threshold,
        })

    except Exception as e:
        logger.error(f"Comparison error: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detection
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/anomaly/detect', methods=['POST'])
@jwt_required()
def detect_anomaly():
    """
    Detect anomalies in sensor data.

    JSON body:
    - machine_id: Machine identifier (required)
    - sensor_data: Optional sensor data array
    - start_time: Start time for historian query
    - end_time: End time for historian query
    """
    service = get_inference_service()

    if not service:
        return _demo_anomaly()

    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({'error': 'machine_id required'}), 400

    machine_id = data['machine_id']

    try:
        if 'sensor_data' in data:
            sensor_data = np.array(data['sensor_data'])
        else:
            # Would query historian for sensor data
            return _demo_anomaly()

        if service._model is None:
            return _demo_anomaly()

        results = service.predict(sensor_data)

        return jsonify({
            'machine_id': machine_id,
            'anomaly_score': float(results['anomaly_score'].mean()),
            'anomaly_detected': results.get('anomaly_detected', False),
            'threshold': service.config.anomaly_threshold,
            'timestamp': results['timestamp'],
            'recommendations': _get_anomaly_recommendations(results),
        })

    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomaly/history', methods=['GET'])
@jwt_required()
def get_anomaly_history():
    """
    Get anomaly detection history.

    Query params:
    - machine_id: Filter by machine
    - start_time: Start time (ISO format)
    - end_time: End time (ISO format)
    - limit: Max results (default: 100)
    """
    # Demo data - would query from historian/database
    machine_id = request.args.get('machine_id')

    return jsonify({
        'anomalies': [
            {
                'anomaly_id': 'ANOM-001',
                'machine_id': machine_id or 'printer_1',
                'detected_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'anomaly_score': 0.87,
                'anomaly_type': 'temperature_drift',
                'resolved': True,
            },
            {
                'anomaly_id': 'ANOM-002',
                'machine_id': machine_id or 'printer_2',
                'detected_at': (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                'anomaly_score': 0.72,
                'anomaly_type': 'vibration_pattern',
                'resolved': False,
            },
        ],
        'count': 2,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool Wear Prediction
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/tool-wear', methods=['POST'])
@jwt_required()
def predict_tool_wear():
    """
    Predict remaining tool life.

    JSON body:
    - machine_id: Machine identifier (required)
    - tool_id: Optional specific tool ID
    """
    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({'error': 'machine_id required'}), 400

    machine_id = data['machine_id']
    tool_id = data.get('tool_id', 'default_tool')

    # Demo response - would use actual ML model
    return jsonify({
        'machine_id': machine_id,
        'tool_id': tool_id,
        'remaining_life_hours': 85.5,
        'remaining_life_percent': 68.4,
        'confidence': 0.82,
        'wear_rate': 0.12,
        'predicted_failure_date': (datetime.utcnow() + timedelta(hours=85)).isoformat(),
        'recommendation': 'Schedule replacement within 3 shifts',
        'timestamp': datetime.utcnow().isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Training Data Export
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/training/export', methods=['POST'])
@jwt_required()
def export_training_data():
    """
    Export historian data for ML training.

    JSON body:
    - tag_ids: List of tag IDs to export (required)
    - start_time: Start time (ISO format, required)
    - end_time: End time (ISO format, required)
    - output_path: Output file path
    - sequence_length: Sequence length (default: 256)
    - stride: Stride between sequences (default: 64)
    """
    try:
        from services.ml.inference.inference_service import historian_ml_bridge

        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        tag_ids = data.get('tag_ids')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([tag_ids, start_time, end_time]):
            return jsonify({'error': 'tag_ids, start_time, and end_time required'}), 400

        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

        output_path = data.get('output_path', f'/tmp/training_data_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.npz')
        sequence_length = data.get('sequence_length', 256)
        stride = data.get('stride', 64)

        result_path = historian_ml_bridge.export_training_data(
            tag_ids=tag_ids,
            start=start,
            end=end,
            output_path=output_path,
            sequence_length=sequence_length,
            stride=stride,
        )

        return jsonify({
            'status': 'exported',
            'output_path': result_path,
            'tag_ids': tag_ids,
            'time_range': {
                'start': start_time,
                'end': end_time,
            },
            'parameters': {
                'sequence_length': sequence_length,
                'stride': stride,
            },
        })

    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/training/jobs', methods=['GET'])
@jwt_required()
def list_training_jobs():
    """List training jobs."""
    # Demo data
    return jsonify({
        'jobs': [
            {
                'job_id': 'TRAIN-001',
                'model_type': 'mm_dtae_lstm',
                'status': 'completed',
                'created_at': '2024-01-15T10:00:00Z',
                'completed_at': '2024-01-15T14:30:00Z',
                'epochs': 100,
                'final_loss': 0.0234,
                'accuracy': 0.91,
            },
            {
                'job_id': 'TRAIN-002',
                'model_type': 'enhanced_encoder',
                'status': 'running',
                'created_at': '2024-01-18T08:00:00Z',
                'epochs_completed': 45,
                'epochs_total': 100,
                'current_loss': 0.0312,
            },
        ],
        'count': 2,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Batch Inference
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/batch', methods=['POST'])
@jwt_required()
def batch_inference():
    """
    Run batch inference on historian data.

    JSON body:
    - tag_ids: List of tag IDs (required)
    - start_time: Start time (ISO format, required)
    - end_time: End time (ISO format, required)
    - sequence_length: Sequence length (default: 256)
    - stride: Stride between sequences (default: 64)
    """
    try:
        from services.ml.inference.inference_service import historian_ml_bridge

        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        tag_ids = data.get('tag_ids')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([tag_ids, start_time, end_time]):
            return jsonify({'error': 'tag_ids, start_time, and end_time required'}), 400

        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

        sequence_length = data.get('sequence_length', 256)
        stride = data.get('stride', 64)

        results = historian_ml_bridge.batch_inference(
            tag_ids=tag_ids,
            start=start,
            end=end,
            sequence_length=sequence_length,
            stride=stride,
        )

        # Summarize results
        anomalies = [r for r in results if r.get('anomaly_detected')]

        return jsonify({
            'total_sequences': len(results),
            'anomalies_detected': len(anomalies),
            'anomaly_rate': len(anomalies) / len(results) if results else 0,
            'time_range': {
                'start': start_time,
                'end': end_time,
            },
            'results': results[:10],  # First 10 for preview
        })

    except Exception as e:
        logger.error(f"Batch inference error: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@ml_api_bp.route('/config', methods=['GET'])
@jwt_required()
def get_config():
    """Get ML service configuration."""
    service = get_inference_service()

    if not service:
        return jsonify({
            'device': 'cpu',
            'batch_size': 1,
            'sequence_length': 256,
            'anomaly_threshold': 0.7,
        })

    return jsonify({
        'device': service.config.device,
        'batch_size': service.config.batch_size,
        'sequence_length': service.config.sequence_length,
        'overlap': service.config.overlap,
        'anomaly_threshold': service.config.anomaly_threshold,
        'fingerprint_similarity_threshold': service.config.fingerprint_similarity_threshold,
    })


@ml_api_bp.route('/config', methods=['PUT'])
@jwt_required()
def update_config():
    """
    Update ML service configuration.

    JSON body:
    - anomaly_threshold: Anomaly detection threshold
    - fingerprint_similarity_threshold: Fingerprint matching threshold
    """
    service = get_inference_service()

    if not service:
        return jsonify({'error': 'ML inference service not available'}), 503

    data = request.get_json() or {}

    if 'anomaly_threshold' in data:
        service.config.anomaly_threshold = float(data['anomaly_threshold'])
    if 'fingerprint_similarity_threshold' in data:
        service.config.fingerprint_similarity_threshold = float(data['fingerprint_similarity_threshold'])

    return jsonify({
        'anomaly_threshold': service.config.anomaly_threshold,
        'fingerprint_similarity_threshold': service.config.fingerprint_similarity_threshold,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def _get_anomaly_recommendations(results: dict) -> list:
    """Generate recommendations based on anomaly detection results."""
    recommendations = []
    score = float(results['anomaly_score'].mean())

    if score > 0.9:
        recommendations.append('Immediate inspection recommended')
        recommendations.append('Consider stopping production')
    elif score > 0.7:
        recommendations.append('Schedule maintenance within 24 hours')
        recommendations.append('Monitor closely for deterioration')
    elif score > 0.5:
        recommendations.append('Add to maintenance watchlist')

    return recommendations


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_models():
    """Return demo models."""
    return jsonify({
        'models': [
            {
                'name': 'mm_dtae_lstm',
                'config': {
                    'embedding_dim': 256,
                    'hidden_dim': 512,
                    'num_layers': 3,
                    'accuracy': 0.90,
                },
            },
        ],
        'count': 1,
    })


def _demo_prediction():
    """Return demo prediction."""
    return jsonify({
        'inference_id': 12345,
        'timestamp': datetime.utcnow().isoformat(),
        'anomaly_score': 0.23,
        'anomaly_detected': False,
        'classification': [0.85, 0.10, 0.05],
        'fingerprint': [0.1, 0.2, 0.3, 0.4, 0.5],
        'demo': True,
    })


def _demo_fingerprint():
    """Return demo fingerprint."""
    return jsonify({
        'fingerprint': [0.15, 0.23, 0.45, 0.67, 0.12, 0.89, 0.34, 0.56],
        'dimensions': [8],
        'timestamp': datetime.utcnow().isoformat(),
        'demo': True,
    })


def _demo_anomaly():
    """Return demo anomaly detection."""
    return jsonify({
        'machine_id': 'printer_1',
        'anomaly_score': 0.32,
        'anomaly_detected': False,
        'threshold': 0.7,
        'timestamp': datetime.utcnow().isoformat(),
        'recommendations': [],
        'demo': True,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detection Service Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def get_anomaly_detection_service():
    """Get anomaly detection service instance."""
    try:
        from services.ml.anomaly.anomaly_detection_service import anomaly_detection_service
        return anomaly_detection_service
    except Exception as e:
        logger.warning(f"Anomaly detection service not available: {e}")
        return None


@ml_api_bp.route('/anomalies', methods=['GET'])
@jwt_required()
def list_anomalies():
    """
    List recent anomalies detected by the ML system.

    Query params:
    - tag_id: Filter by tag ID
    - min_severity: Minimum severity level (INFO, LOW, MEDIUM, HIGH, CRITICAL)
    - limit: Max results (default: 100)
    - start_time: Start time (ISO format)
    - end_time: End time (ISO format)
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({
            'anomalies': [],
            'count': 0,
            'error': 'Anomaly detection service not available',
        })

    try:
        from services.ml.anomaly.anomaly_types import AnomalySeverity

        tag_id = request.args.get('tag_id')
        limit = int(request.args.get('limit', 100))
        min_severity_str = request.args.get('min_severity', 'INFO').upper()

        # Parse severity
        min_severity = None
        if min_severity_str:
            try:
                min_severity = AnomalySeverity[min_severity_str]
            except KeyError:
                pass

        # Get anomalies
        anomalies = service.get_recent_anomalies(
            tag_id=tag_id,
            limit=limit,
            min_severity=min_severity
        )

        # Filter by time if provided
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')

        if start_time_str:
            start = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            anomalies = [a for a in anomalies if a.timestamp >= start]

        if end_time_str:
            end = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            anomalies = [a for a in anomalies if a.timestamp <= end]

        return jsonify({
            'anomalies': [a.to_dict() for a in anomalies],
            'count': len(anomalies),
            'filters': {
                'tag_id': tag_id,
                'min_severity': min_severity_str,
                'limit': limit,
            },
        })

    except Exception as e:
        logger.error(f"Error listing anomalies: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomalies/detect', methods=['POST'])
@jwt_required()
def detect_anomalies_endpoint():
    """
    Run anomaly detection on provided data.

    JSON body:
    - tag_id: Tag identifier (required)
    - tag_name: Human-readable tag name (optional)
    - values: Array of numeric values (required)
    - timestamps: Array of ISO timestamps (optional)
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    tag_id = data.get('tag_id')
    values = data.get('values')

    if not tag_id or values is None:
        return jsonify({'error': 'tag_id and values are required'}), 400

    try:
        values_array = np.array(values, dtype=float)
        tag_name = data.get('tag_name', tag_id)

        # Parse timestamps if provided
        timestamps = None
        if 'timestamps' in data:
            timestamps = [
                datetime.fromisoformat(ts.replace('Z', '+00:00'))
                for ts in data['timestamps']
            ]

        # Run detection
        anomalies = service.detect_batch(
            tag_id=tag_id,
            values=values_array,
            timestamps=timestamps,
            tag_name=tag_name
        )

        # Compute summary statistics
        severity_counts = {}
        category_counts = {}
        for a in anomalies:
            sev = a.severity.name
            cat = a.category.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return jsonify({
            'tag_id': tag_id,
            'tag_name': tag_name,
            'total_points': len(values),
            'anomalies_detected': len(anomalies),
            'anomaly_rate': len(anomalies) / len(values) if values else 0,
            'anomalies': [a.to_dict() for a in anomalies],
            'summary': {
                'by_severity': severity_counts,
                'by_category': category_counts,
            },
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomalies/realtime', methods=['POST'])
@jwt_required()
def detect_realtime_endpoint():
    """
    Real-time anomaly detection for a single value.

    JSON body:
    - tag_id: Tag identifier (required)
    - value: Numeric value (required)
    - tag_name: Human-readable tag name (optional)
    - timestamp: ISO timestamp (optional, defaults to now)
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    tag_id = data.get('tag_id')
    value = data.get('value')

    if not tag_id or value is None:
        return jsonify({'error': 'tag_id and value are required'}), 400

    try:
        tag_name = data.get('tag_name', tag_id)
        timestamp = None
        if 'timestamp' in data:
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))

        # Run real-time detection
        result = service.detect_realtime(
            tag_id=tag_id,
            value=float(value),
            timestamp=timestamp,
            tag_name=tag_name
        )

        if result:
            return jsonify({
                'anomaly_detected': True,
                'anomaly': result.to_dict(),
            })
        else:
            return jsonify({
                'anomaly_detected': False,
                'tag_id': tag_id,
                'value': value,
                'timestamp': (timestamp or datetime.utcnow()).isoformat(),
            })

    except Exception as e:
        logger.error(f"Error in real-time detection: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomalies/config', methods=['GET'])
@jwt_required()
def get_anomaly_config():
    """
    Get anomaly detection configuration.

    Returns current detection thresholds and settings.
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({
            'error': 'Anomaly detection service not available',
            'default_config': {
                'enabled': True,
                'window_size': 100,
                'zscore_threshold': 3.0,
                'ml_threshold': 0.7,
            }
        })

    return jsonify({
        'config': service.config.to_dict(),
        'stats': service.get_stats(),
    })


@ml_api_bp.route('/anomalies/config', methods=['PUT'])
@jwt_required()
def update_anomaly_config():
    """
    Update anomaly detection configuration.

    JSON body:
    - enabled: Enable/disable detection
    - window_size: Sliding window size
    - min_samples: Minimum samples before detection
    - ml_threshold: ML model threshold (0-1)
    - zscore_threshold: Z-score threshold
    - iqr_multiplier: IQR outlier multiplier
    - use_ml_detection: Enable ML-based detection
    - use_statistical_detection: Enable statistical detection
    - use_threshold_detection: Enable threshold detection
    - generate_alarms: Generate alarms for anomalies
    - alarm_cooldown_seconds: Cooldown between alarms
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    data = request.get_json() or {}

    try:
        from services.ml.anomaly.anomaly_types import AnomalyConfig

        # Get current config and update
        current = service.config
        config_dict = current.to_dict()

        # Update provided fields
        updatable_fields = [
            'enabled', 'window_size', 'min_samples', 'ml_threshold',
            'zscore_threshold', 'iqr_multiplier', 'use_ml_detection',
            'use_statistical_detection', 'use_threshold_detection',
            'use_pattern_detection', 'pattern_sequence_length',
            'generate_alarms', 'alarm_cooldown_seconds', 'detection_interval_seconds'
        ]

        for field in updatable_fields:
            if field in data:
                config_dict[field] = data[field]

        # Create new config and apply
        new_config = AnomalyConfig.from_dict(config_dict)
        service.configure(new_config)

        logger.info(f"Updated anomaly detection config: {data}")

        return jsonify({
            'status': 'updated',
            'config': service.config.to_dict(),
        })

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomalies/config/tag/<tag_id>', methods=['GET'])
@jwt_required()
def get_tag_threshold_config(tag_id: str):
    """
    Get threshold configuration for a specific tag.
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    config = service.config.get_tag_config(tag_id)

    return jsonify({
        'tag_id': tag_id,
        'config': config.to_dict(),
    })


@ml_api_bp.route('/anomalies/config/tag/<tag_id>', methods=['PUT'])
@jwt_required()
def update_tag_threshold_config(tag_id: str):
    """
    Update threshold configuration for a specific tag.

    JSON body:
    - high_high: Critical high threshold
    - high: Warning high threshold
    - low: Warning low threshold
    - low_low: Critical low threshold
    - zscore_threshold: Z-score threshold
    - iqr_multiplier: IQR multiplier
    - max_rate_of_change: Max allowed rate of change per second
    - flatline_threshold: Variance threshold for flatline detection
    - flatline_duration_seconds: Duration threshold for flatline
    - spike_threshold: Z-score threshold for spike detection
    - deadband: Value change deadband
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    data = request.get_json() or {}

    try:
        from services.ml.anomaly.anomaly_types import ThresholdConfig

        # Get current config or create new
        current = service.config.get_tag_config(tag_id)
        config_dict = current.to_dict()

        # Update provided fields
        updatable_fields = [
            'high_high', 'high', 'low', 'low_low', 'zscore_threshold',
            'iqr_multiplier', 'max_rate_of_change', 'flatline_threshold',
            'flatline_duration_seconds', 'spike_threshold', 'spike_duration_seconds',
            'deadband'
        ]

        for field in updatable_fields:
            if field in data:
                config_dict[field] = data[field]

        # Create and set new config
        new_config = ThresholdConfig.from_dict(config_dict)
        service.config.set_tag_config(tag_id, new_config)

        logger.info(f"Updated threshold config for tag {tag_id}: {data}")

        return jsonify({
            'status': 'updated',
            'tag_id': tag_id,
            'config': new_config.to_dict(),
        })

    except Exception as e:
        logger.error(f"Error updating tag config: {e}")
        return jsonify({'error': str(e)}), 500


@ml_api_bp.route('/anomalies/window/<tag_id>', methods=['GET'])
@jwt_required()
def get_tag_window_stats(tag_id: str):
    """
    Get sliding window statistics for a tag.

    Useful for debugging and understanding current baseline.
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    window = service.get_window(tag_id)

    if window.count == 0:
        return jsonify({
            'tag_id': tag_id,
            'count': 0,
            'message': 'No data in window for this tag',
        })

    return jsonify({
        'tag_id': tag_id,
        'window_stats': {
            'count': window.count,
            'max_size': window.max_size,
            'mean': window.mean,
            'std': window.std,
            'variance': window.variance,
            'median': window.median,
            'q1': window.q1,
            'q3': window.q3,
            'iqr': window.iqr,
            'min': window.min_value,
            'max': window.max_value,
        },
        'recent_values': [
            {'timestamp': ts.isoformat(), 'value': val}
            for ts, val in window.get_recent(10)
        ],
    })


@ml_api_bp.route('/anomalies/window/<tag_id>', methods=['DELETE'])
@jwt_required()
def clear_tag_window(tag_id: str):
    """
    Clear the sliding window for a tag.

    Useful when resetting baseline after maintenance.
    """
    service = get_anomaly_detection_service()

    if not service:
        return jsonify({'error': 'Anomaly detection service not available'}), 503

    service.clear_window(tag_id)

    return jsonify({
        'status': 'cleared',
        'tag_id': tag_id,
        'message': f'Window cleared for tag {tag_id}',
    })
