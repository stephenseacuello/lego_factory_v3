"""
Inspections API - Quality inspection management.
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime

from models import get_db_session
from services.quality import InspectionService

inspections_bp = Blueprint('inspections', __name__, url_prefix='/inspections')


# Dashboard Page Route
@inspections_bp.route('/page', methods=['GET'])
def inspections_page():
    """Render quality inspections dashboard page."""
    return render_template('pages/quality/quality_dashboard.html')


@inspections_bp.route('', methods=['GET'])
def list_inspections():
    """List inspections with filters."""
    work_order_id = request.args.get('work_order_id')
    status = request.args.get('status')
    inspection_type = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)

    with get_db_session() as session:
        service = InspectionService(session)

        if status == 'pending':
            inspections = service.get_pending_inspections(
                work_order_id=work_order_id,
                inspection_type=inspection_type
            )
        else:
            inspections = service.get_inspection_history(
                work_order_id=work_order_id,
                limit=limit
            )

        return jsonify({
            'inspections': inspections,
            'total': len(inspections)
        })


@inspections_bp.route('', methods=['POST'])
def create_inspection():
    """
    Create a new inspection.

    Request body:
    {
        "work_order_id": "uuid",
        "inspection_type": "in_process",
        "sample_size": 5,
        "notes": "Optional notes"
    }
    """
    data = request.get_json()

    work_order_id = data.get('work_order_id')
    inspection_type = data.get('inspection_type', 'in_process')

    if not work_order_id:
        return jsonify({'error': 'work_order_id is required'}), 400

    with get_db_session() as session:
        service = InspectionService(session)

        try:
            inspection = service.create_inspection(
                work_order_id=work_order_id,
                inspection_type=inspection_type,
                inspector_id=data.get('inspector_id'),
                operation_id=data.get('operation_id'),
                sample_size=data.get('sample_size', 1),
                notes=data.get('notes')
            )

            return jsonify({
                'id': str(inspection.id),
                'inspection_type': inspection.inspection_type,
                'message': 'Inspection created'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@inspections_bp.route('/<inspection_id>', methods=['GET'])
def get_inspection(inspection_id: str):
    """Get inspection details with metrics."""
    with get_db_session() as session:
        service = InspectionService(session)
        inspection = service.get_inspection(inspection_id)

        if not inspection:
            return jsonify({'error': 'Inspection not found'}), 404

        return jsonify(inspection)


@inspections_bp.route('/<inspection_id>/measure', methods=['POST'])
def record_measurement(inspection_id: str):
    """
    Record a measurement for an inspection.

    Request body:
    {
        "metric_name": "stud_diameter",
        "actual_value": 4.82,
        "target_value": 4.80,
        "tolerance_plus": 0.05,
        "tolerance_minus": 0.05,
        "unit": "mm"
    }
    """
    data = request.get_json()

    metric_name = data.get('metric_name')
    actual_value = data.get('actual_value')

    if not all([metric_name, actual_value is not None]):
        return jsonify({'error': 'metric_name and actual_value are required'}), 400

    with get_db_session() as session:
        service = InspectionService(session)

        try:
            metric = service.record_measurement(
                inspection_id=inspection_id,
                metric_name=metric_name,
                actual_value=actual_value,
                target_value=data.get('target_value'),
                tolerance_plus=data.get('tolerance_plus'),
                tolerance_minus=data.get('tolerance_minus'),
                unit=data.get('unit', 'mm'),
                notes=data.get('notes')
            )

            return jsonify({
                'id': str(metric.id),
                'metric_name': metric.metric_name,
                'passed': metric.passed,
                'message': 'Measurement recorded'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@inspections_bp.route('/<inspection_id>/complete', methods=['POST'])
def complete_inspection(inspection_id: str):
    """
    Complete an inspection.

    Request body:
    {
        "result": "pass",
        "disposition": "use_as_is",
        "defects_found": 0,
        "notes": "All dimensions within spec"
    }
    """
    data = request.get_json()

    result = data.get('result')
    if not result:
        return jsonify({'error': 'result is required'}), 400

    with get_db_session() as session:
        service = InspectionService(session)

        try:
            inspection = service.complete_inspection(
                inspection_id=inspection_id,
                result=result,
                disposition=data.get('disposition'),
                defects_found=data.get('defects_found', 0),
                notes=data.get('notes')
            )

            return jsonify({
                'id': str(inspection.id),
                'result': inspection.result,
                'disposition': inspection.disposition,
                'message': 'Inspection completed'
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@inspections_bp.route('/<inspection_id>/ncr', methods=['POST'])
def create_ncr(inspection_id: str):
    """
    Create a Non-Conformance Report.

    Request body:
    {
        "description": "Stud diameter out of tolerance",
        "root_cause": "Printer calibration drift",
        "corrective_action": "Recalibrate XY steps"
    }
    """
    data = request.get_json()

    description = data.get('description')
    if not description:
        return jsonify({'error': 'description is required'}), 400

    with get_db_session() as session:
        service = InspectionService(session)

        try:
            ncr = service.create_ncr(
                inspection_id=inspection_id,
                description=description,
                root_cause=data.get('root_cause'),
                corrective_action=data.get('corrective_action')
            )

            return jsonify(ncr), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@inspections_bp.route('/metrics/fpy', methods=['GET'])
def get_first_pass_yield():
    """
    Get First Pass Yield metrics.

    Query params:
    - part_id: Filter by part
    - start: Start date (ISO format)
    - end: End date (ISO format)
    """
    part_id = request.args.get('part_id')
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    start_date = datetime.fromisoformat(start_str) if start_str else None
    end_date = datetime.fromisoformat(end_str) if end_str else None

    with get_db_session() as session:
        service = InspectionService(session)
        fpy = service.calculate_first_pass_yield(
            part_id=part_id,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(fpy)
