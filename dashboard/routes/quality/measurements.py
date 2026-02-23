"""
Measurements API - Dimensional measurement endpoints.
"""

from flask import Blueprint, jsonify, request

from models import get_db_session
from services.quality import MeasurementService

measurements_bp = Blueprint('measurements', __name__, url_prefix='/measurements')


@measurements_bp.route('/dimension', methods=['POST'])
def record_dimension():
    """
    Record a dimensional measurement.

    Request body:
    {
        "inspection_id": "uuid",
        "dimension_name": "stud_diameter",
        "nominal": 4.80,
        "measured": 4.82,
        "tolerance_plus": 0.05,
        "tolerance_minus": 0.05,
        "equipment_type": "caliper_digital",
        "unit": "mm"
    }
    """
    data = request.get_json()

    required = ['inspection_id', 'dimension_name', 'nominal', 'measured', 'tolerance_plus']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400

    with get_db_session() as session:
        service = MeasurementService(session)

        result = service.record_dimension(
            inspection_id=data['inspection_id'],
            dimension_name=data['dimension_name'],
            nominal=data['nominal'],
            measured=data['measured'],
            tolerance_plus=data['tolerance_plus'],
            tolerance_minus=data.get('tolerance_minus'),
            equipment_type=data.get('equipment_type', 'caliper_digital'),
            unit=data.get('unit', 'mm')
        )

        return jsonify({
            'value': result.value,
            'in_tolerance': result.in_tolerance,
            'deviation': round(result.deviation, 4),
            'uncertainty': result.uncertainty,
            'unit': result.unit
        }), 201


@measurements_bp.route('/batch', methods=['POST'])
def record_batch():
    """
    Record multiple measurements at once.

    Request body:
    {
        "inspection_id": "uuid",
        "equipment_type": "caliper_digital",
        "measurements": [
            {"dimension_name": "stud_diameter", "nominal": 4.80, "measured": 4.82, "tolerance_plus": 0.05},
            {"dimension_name": "stud_height", "nominal": 1.70, "measured": 1.68, "tolerance_plus": 0.05}
        ]
    }
    """
    data = request.get_json()

    inspection_id = data.get('inspection_id')
    measurements = data.get('measurements', [])

    if not inspection_id or not measurements:
        return jsonify({'error': 'inspection_id and measurements are required'}), 400

    with get_db_session() as session:
        service = MeasurementService(session)

        results = service.record_batch_measurements(
            inspection_id=inspection_id,
            measurements=measurements,
            equipment_type=data.get('equipment_type', 'caliper_digital')
        )

        return jsonify({
            'total': len(results),
            'passed': sum(1 for r in results if r.in_tolerance),
            'failed': sum(1 for r in results if not r.in_tolerance),
            'results': [
                {
                    'value': r.value,
                    'in_tolerance': r.in_tolerance,
                    'deviation': round(r.deviation, 4)
                }
                for r in results
            ]
        }), 201


@measurements_bp.route('/cpk/<metric_name>', methods=['GET'])
def get_cpk(metric_name: str):
    """
    Get Process Capability Index (Cpk) for a metric.

    Query params:
    - part_id: Filter by part
    - limit: Number of samples (default 30)
    """
    part_id = request.args.get('part_id')
    limit = request.args.get('limit', 30, type=int)

    with get_db_session() as session:
        service = MeasurementService(session)
        cpk = service.calculate_cpk(
            metric_name=metric_name,
            part_id=part_id,
            limit=limit
        )

        return jsonify(cpk)


@measurements_bp.route('/trend/<metric_name>', methods=['GET'])
def get_trend(metric_name: str):
    """Get measurement trend data for charting."""
    limit = request.args.get('limit', 50, type=int)

    with get_db_session() as session:
        service = MeasurementService(session)
        trend = service.get_measurement_trend(
            metric_name=metric_name,
            limit=limit
        )

        return jsonify(trend)


@measurements_bp.route('/report/<inspection_id>', methods=['GET'])
def get_inspection_report(inspection_id: str):
    """Get dimensional inspection report."""
    with get_db_session() as session:
        service = MeasurementService(session)
        report = service.generate_inspection_report(inspection_id)

        if 'error' in report:
            return jsonify(report), 404

        return jsonify(report)
