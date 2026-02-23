"""
Zero-Defect Routes - Predictive Quality API

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Provides:
- Predictive quality prediction
- In-process control
- Process fingerprinting
- Virtual metrology
- Golden batch comparison
"""

from datetime import datetime
from flask import Blueprint, jsonify, request

zero_defect_bp = Blueprint('zero_defect', __name__, url_prefix='/zero-defect')

# Try to import zero-defect services
try:
    from services.quality.zero_defect import (
        PredictiveQualityModel,
        QualityPrediction,
        InterventionDecision,
        ProcessFingerprint,
        FingerprintMatcher,
        VirtualMetrology,
    )
    from services.quality.zero_defect.predictive_quality import ProcessSignals
    ZERO_DEFECT_AVAILABLE = True
except ImportError:
    ZERO_DEFECT_AVAILABLE = False

# Global model instance
_predictive_model = None
_fingerprints = {}


def _get_model():
    """Get or create predictive model."""
    global _predictive_model
    if _predictive_model is None and ZERO_DEFECT_AVAILABLE:
        _predictive_model = PredictiveQualityModel()
    return _predictive_model


@zero_defect_bp.route('/predict', methods=['POST'])
def predict_quality():
    """
    Predict quality from current process signals.

    Request body:
    {
        "machine_id": "WC-001",
        "job_id": "JOB-001",
        "nozzle_temp": 210.0,
        "bed_temp": 60.0,
        "print_speed": 40.0,
        "flow_rate": 100.0,
        "layer_number": 50,
        "total_layers": 200,
        "layer_height": 0.12,
        "humidity": 50.0
    }

    Returns:
        JSON with quality prediction
    """
    data = request.get_json() or {}

    if not ZERO_DEFECT_AVAILABLE:
        # Fallback prediction
        return jsonify({
            'prediction': {
                'defect_probability': 0.05,
                'risk_level': 'low',
                'pass_probability': 0.95,
                'predicted_clutch_power': 2.0,
                'predicted_surface_grade': 4.5,
            },
            'intervention': {
                'should_intervene': False,
                'rationale': 'Process within acceptable parameters.'
            },
            'available': False,
            'message': 'Zero-defect services not available, using fallback'
        })

    model = _get_model()

    # Build process signals
    signals = ProcessSignals(
        timestamp=datetime.utcnow(),
        machine_id=data.get('machine_id', 'unknown'),
        job_id=data.get('job_id', 'unknown'),
        nozzle_temp=float(data.get('nozzle_temp', 210.0)),
        bed_temp=float(data.get('bed_temp', 60.0)),
        ambient_temp=float(data.get('ambient_temp', 25.0)),
        print_speed=float(data.get('print_speed', 40.0)),
        acceleration=float(data.get('acceleration', 1000.0)),
        layer_height=float(data.get('layer_height', 0.12)),
        flow_rate=float(data.get('flow_rate', 100.0)),
        filament_diameter=float(data.get('filament_diameter', 1.75)),
        humidity=float(data.get('humidity', 50.0)),
        layer_number=int(data.get('layer_number', 0)),
        total_layers=int(data.get('total_layers', 100)),
        elapsed_time_seconds=float(data.get('elapsed_time', 0)),
    )

    # Get prediction
    prediction = model.predict(signals)

    # Check for intervention
    intervention = model.should_intervene(prediction)

    return jsonify({
        'prediction': {
            'defect_probability': prediction.defect_probability,
            'risk_level': prediction.risk_level,
            'pass_probability': prediction.pass_probability,
            'predicted_defect_types': [d.value for d in prediction.predicted_defect_types],
            'predicted_clutch_power': prediction.predicted_clutch_power,
            'clutch_power_range': prediction.clutch_power_range,
            'predicted_dimensions': prediction.predicted_dimensions,
            'predicted_surface_grade': prediction.predicted_surface_grade,
        },
        'intervention': {
            'should_intervene': intervention.should_intervene,
            'intervention_type': intervention.intervention_type.value,
            'parameters': intervention.parameters,
            'urgency': intervention.urgency,
            'rationale': intervention.rationale,
            'confidence': intervention.confidence,
        },
        'signals_received': {
            'machine_id': signals.machine_id,
            'job_id': signals.job_id,
            'layer': signals.layer_number,
        }
    })


@zero_defect_bp.route('/fingerprint', methods=['POST'])
def create_fingerprint():
    """
    Create a process fingerprint from golden batch.

    Request body:
    {
        "fingerprint_id": "FP-BRICK-2X4",
        "part_id": "BRICK-2X4",
        "process_data": [
            {"nozzle_temp": 210, "flow_rate": 100, "speed": 40},
            ...
        ],
        "quality_results": {
            "clutch_power": 2.1,
            "stud_diameter": 4.80,
            "surface_grade": 4.8
        }
    }

    Returns:
        JSON with created fingerprint
    """
    data = request.get_json() or {}

    fingerprint_id = data.get('fingerprint_id', f"FP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")

    fingerprint = {
        'fingerprint_id': fingerprint_id,
        'part_id': data.get('part_id'),
        'created_at': datetime.utcnow().isoformat(),
        'sample_count': len(data.get('process_data', [])),
        'quality_targets': data.get('quality_results', {}),
        'process_signature': {
            'mean_temp': sum(p.get('nozzle_temp', 210) for p in data.get('process_data', [])) / max(1, len(data.get('process_data', []))),
            'mean_flow': sum(p.get('flow_rate', 100) for p in data.get('process_data', [])) / max(1, len(data.get('process_data', []))),
            'mean_speed': sum(p.get('speed', 40) for p in data.get('process_data', [])) / max(1, len(data.get('process_data', []))),
        },
        'status': 'active'
    }

    _fingerprints[fingerprint_id] = fingerprint

    return jsonify({
        'success': True,
        'fingerprint': fingerprint
    }), 201


@zero_defect_bp.route('/fingerprint/<fingerprint_id>', methods=['GET'])
def get_fingerprint(fingerprint_id: str):
    """Get a process fingerprint."""
    fingerprint = _fingerprints.get(fingerprint_id)
    if not fingerprint:
        return jsonify({'error': 'Fingerprint not found'}), 404

    return jsonify(fingerprint)


@zero_defect_bp.route('/fingerprint/<fingerprint_id>/compare', methods=['POST'])
def compare_fingerprint(fingerprint_id: str):
    """
    Compare current process to golden fingerprint.

    Request body:
    {
        "current_data": {
            "nozzle_temp": 212,
            "flow_rate": 102,
            "speed": 42
        }
    }

    Returns:
        JSON with similarity score and deviation analysis
    """
    fingerprint = _fingerprints.get(fingerprint_id)
    if not fingerprint:
        return jsonify({'error': 'Fingerprint not found'}), 404

    data = request.get_json() or {}
    current = data.get('current_data', {})

    signature = fingerprint.get('process_signature', {})

    # Calculate deviations
    temp_deviation = abs(current.get('nozzle_temp', 210) - signature.get('mean_temp', 210))
    flow_deviation = abs(current.get('flow_rate', 100) - signature.get('mean_flow', 100))
    speed_deviation = abs(current.get('speed', 40) - signature.get('mean_speed', 40))

    # Calculate similarity (simple approach)
    temp_sim = max(0, 1 - temp_deviation / 10)  # 10C = 0 similarity
    flow_sim = max(0, 1 - flow_deviation / 10)  # 10% = 0 similarity
    speed_sim = max(0, 1 - speed_deviation / 20)  # 20mm/s = 0 similarity

    overall_similarity = (temp_sim + flow_sim + speed_sim) / 3

    # Determine status
    if overall_similarity >= 0.9:
        status = 'excellent'
    elif overall_similarity >= 0.7:
        status = 'good'
    elif overall_similarity >= 0.5:
        status = 'acceptable'
    else:
        status = 'out_of_spec'

    return jsonify({
        'fingerprint_id': fingerprint_id,
        'comparison': {
            'overall_similarity': overall_similarity,
            'status': status,
            'deviations': {
                'temperature': temp_deviation,
                'flow_rate': flow_deviation,
                'speed': speed_deviation,
            },
            'component_similarity': {
                'temperature': temp_sim,
                'flow_rate': flow_sim,
                'speed': speed_sim,
            }
        },
        'recommendation': 'No action needed' if overall_similarity >= 0.7 else 'Review process parameters'
    })


@zero_defect_bp.route('/fingerprints', methods=['GET'])
def list_fingerprints():
    """List all process fingerprints."""
    return jsonify({
        'fingerprints': list(_fingerprints.values()),
        'count': len(_fingerprints)
    })


@zero_defect_bp.route('/virtual-metrology', methods=['POST'])
def virtual_metrology():
    """
    Predict dimensions from process data (virtual measurement).

    Request body:
    {
        "machine_id": "WC-001",
        "job_id": "JOB-001",
        "process_data": {
            "nozzle_temp": 210,
            "flow_rate": 100,
            "speed": 40,
            "layer_height": 0.12
        }
    }

    Returns:
        JSON with predicted dimensions
    """
    data = request.get_json() or {}
    process = data.get('process_data', {})

    # Nominal dimensions
    stud_diameter_nom = 4.8
    stud_height_nom = 1.8
    wall_thickness_nom = 1.6

    # Calculate predicted deviations based on process
    flow_factor = (process.get('flow_rate', 100) - 100) / 100
    temp_factor = (process.get('nozzle_temp', 210) - 210) / 50

    # Predict dimensions
    predicted = {
        'stud_diameter': {
            'value': stud_diameter_nom + flow_factor * 0.05 + temp_factor * 0.01,
            'tolerance': 0.02,
            'target': stud_diameter_nom,
            'in_spec': True
        },
        'stud_height': {
            'value': stud_height_nom + flow_factor * 0.02,
            'tolerance': 0.02,
            'target': stud_height_nom,
            'in_spec': True
        },
        'wall_thickness': {
            'value': wall_thickness_nom + flow_factor * 0.03,
            'tolerance': 0.02,
            'target': wall_thickness_nom,
            'in_spec': True
        },
        'overall_height': {
            'value': 9.6 + flow_factor * 0.05,
            'tolerance': 0.05,
            'target': 9.6,
            'in_spec': True
        }
    }

    # Check in-spec
    for dim in predicted.values():
        deviation = abs(dim['value'] - dim['target'])
        dim['in_spec'] = deviation <= dim['tolerance']
        dim['deviation'] = dim['value'] - dim['target']

    all_in_spec = all(d['in_spec'] for d in predicted.values())

    return jsonify({
        'virtual_metrology': {
            'machine_id': data.get('machine_id'),
            'job_id': data.get('job_id'),
            'predicted_dimensions': predicted,
            'all_in_spec': all_in_spec,
            'confidence': 0.85,  # Would be from trained model
        },
        'process_inputs': process
    })


@zero_defect_bp.route('/model-info', methods=['GET'])
def get_model_info():
    """Get predictive model information."""
    if not ZERO_DEFECT_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Zero-defect services not available'
        })

    model = _get_model()
    info = model.get_model_info()
    info['available'] = True

    return jsonify(info)


@zero_defect_bp.route('/train', methods=['POST'])
def train_model():
    """
    Train predictive model on historical data.

    Request body:
    {
        "process_data": [...],  // List of process signals
        "quality_results": [...]  // Corresponding quality outcomes
    }

    Returns:
        JSON with training results
    """
    if not ZERO_DEFECT_AVAILABLE:
        return jsonify({
            'error': 'Zero-defect services not available',
            'available': False
        }), 400

    data = request.get_json() or {}

    process_data = data.get('process_data', [])
    quality_results = data.get('quality_results', [])

    if len(process_data) < 100:
        return jsonify({
            'error': 'Insufficient training data (need 100+ samples)',
            'provided': len(process_data)
        }), 400

    model = _get_model()

    # Convert to ProcessSignals (simplified)
    signals = []
    for p in process_data:
        signals.append(ProcessSignals(
            timestamp=datetime.utcnow(),
            machine_id=p.get('machine_id', 'unknown'),
            job_id=p.get('job_id', 'unknown'),
            nozzle_temp=p.get('nozzle_temp', 210),
            bed_temp=p.get('bed_temp', 60),
            print_speed=p.get('speed', 40),
            flow_rate=p.get('flow_rate', 100),
            layer_number=p.get('layer', 0),
        ))

    result = model.train(signals, quality_results)

    return jsonify({
        'success': True,
        'training_result': result
    })


@zero_defect_bp.route('/summary', methods=['GET'])
def get_summary():
    """
    Get zero-defect system summary.

    Returns:
        JSON with system status and statistics
    """
    return jsonify({
        'zero_defect_system': {
            'available': ZERO_DEFECT_AVAILABLE,
            'model_status': 'ready' if ZERO_DEFECT_AVAILABLE else 'unavailable',
            'fingerprints_count': len(_fingerprints),
            'target_dpmo': 10,  # Target: <10 Defects Per Million Opportunities
            'capabilities': {
                'predictive_quality': True,
                'in_process_control': True,
                'process_fingerprinting': True,
                'virtual_metrology': True,
            }
        },
        'thresholds': {
            'defect_probability': 0.3,
            'high_risk': 0.6,
            'critical': 0.85,
        }
    })
