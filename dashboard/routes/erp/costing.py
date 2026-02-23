"""
Costing API - Standard/actual costing and variance analysis.
"""

from flask import Blueprint, jsonify, request, render_template

from models import get_db_session
from services.erp import CostService

costing_bp = Blueprint('costing', __name__, url_prefix='/costing')


# Dashboard Page Route
@costing_bp.route('/page', methods=['GET'])
def costing_page():
    """Render costing dashboard page."""
    return render_template('pages/erp/costing_dashboard.html')


@costing_bp.route('/<part_id>', methods=['GET'])
def get_standard_cost(part_id: str):
    """Get standard cost breakdown for a part."""
    with get_db_session() as session:
        service = CostService(session)
        cost = service.calculate_standard_cost(part_id)

        return jsonify(cost)


@costing_bp.route('/rollup/<part_id>', methods=['POST'])
def rollup_costs(part_id: str):
    """Roll up costs through BOM hierarchy."""
    with get_db_session() as session:
        service = CostService(session)
        result = service.rollup_costs(part_id)

        return jsonify(result)


@costing_bp.route('/actual', methods=['POST'])
def record_actual_cost():
    """
    Record actual costs for a work order.

    Request body:
    {
        "work_order_id": "uuid",
        "material_cost": 10.50,
        "labor_cost": 5.00,
        "machine_cost": 2.50,
        "overhead_cost": 1.00
    }
    """
    data = request.get_json()

    work_order_id = data.get('work_order_id')
    if not work_order_id:
        return jsonify({'error': 'work_order_id is required'}), 400

    with get_db_session() as session:
        service = CostService(session)

        try:
            ledger = service.record_actual_cost(
                work_order_id=work_order_id,
                material_cost=data.get('material_cost', 0),
                labor_cost=data.get('labor_cost', 0),
                machine_cost=data.get('machine_cost', 0),
                overhead_cost=data.get('overhead_cost', 0)
            )

            return jsonify({
                'id': str(ledger.id),
                'total_actual': float(ledger.actual_cost),
                'total_variance': float(ledger.variance),
                'message': 'Actual costs recorded'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@costing_bp.route('/variance/<work_order_id>', methods=['GET'])
def get_variance(work_order_id: str):
    """Get cost variance analysis for a work order."""
    with get_db_session() as session:
        service = CostService(session)

        try:
            variance = service.analyze_variance(work_order_id)
            return jsonify(variance)
        except ValueError as e:
            return jsonify({'error': str(e)}), 404


@costing_bp.route('/variance/summary', methods=['GET'])
def get_variance_summary():
    """
    Get variance summary across all work orders.

    Query params:
    - start: Start date
    - end: End date
    """
    from datetime import datetime, timedelta

    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if start_str:
        start_date = datetime.fromisoformat(start_str)
    else:
        start_date = datetime.utcnow() - timedelta(days=30)

    end_date = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

    with get_db_session() as session:
        service = CostService(session)
        summary = service.get_variance_summary(start_date, end_date)

        return jsonify(summary)
