"""
Capacity Planning API - Capacity and scheduling endpoints.
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime

from models import get_db_session
from services.mrp import CapacityPlanner, SchedulingDirection

capacity_bp = Blueprint('capacity', __name__, url_prefix='/capacity')


# =============================================================================
# Dashboard Page Route
# =============================================================================

@capacity_bp.route('/page', methods=['GET'])
def capacity_dashboard():
    """Render the Capacity Planning dashboard page."""
    return render_template('pages/mrp/capacity_dashboard.html')


# =============================================================================
# API Routes
# =============================================================================

@capacity_bp.route('/overview', methods=['GET'])
def get_capacity_overview():
    """
    Get capacity overview for work centers.

    Query params:
    - work_center_id: Filter by work center
    - horizon_weeks: Planning horizon (default 4)
    - period_type: 'day' or 'week' (default 'day')
    """
    work_center_id = request.args.get('work_center_id')
    horizon_weeks = request.args.get('horizon_weeks', 4, type=int)
    period_type = request.args.get('period_type', 'day')

    with get_db_session() as session:
        planner = CapacityPlanner(session)

        overview = planner.get_capacity_overview(
            work_center_id=work_center_id,
            horizon_weeks=horizon_weeks,
            period_type=period_type
        )

        return jsonify(overview)


@capacity_bp.route('/bottlenecks', methods=['GET'])
def get_bottlenecks():
    """
    Identify capacity bottlenecks.

    Query params:
    - horizon_weeks: Planning horizon (default 4)
    - threshold: Utilization threshold % (default 90)
    """
    horizon_weeks = request.args.get('horizon_weeks', 4, type=int)
    threshold = request.args.get('threshold', 90, type=float)

    with get_db_session() as session:
        planner = CapacityPlanner(session)

        bottlenecks = planner.identify_bottlenecks(
            horizon_weeks=horizon_weeks,
            threshold_percent=threshold
        )

        return jsonify({
            'bottlenecks': bottlenecks,
            'total': len(bottlenecks),
            'critical': sum(1 for b in bottlenecks if b['severity'] == 'CRITICAL')
        })


@capacity_bp.route('/schedule/<work_order_id>', methods=['POST'])
def schedule_work_order(work_order_id: str):
    """
    Schedule a work order using finite capacity.

    Request body:
    {
        "direction": "backward"  // or "forward"
    }
    """
    data = request.get_json() or {}
    direction_str = data.get('direction', 'backward')

    try:
        direction = SchedulingDirection(direction_str)
    except ValueError:
        return jsonify({'error': f'Invalid direction: {direction_str}'}), 400

    with get_db_session() as session:
        planner = CapacityPlanner(session)

        try:
            scheduled = planner.schedule_work_order(
                work_order_id=work_order_id,
                direction=direction
            )

            return jsonify({
                'work_order_id': work_order_id,
                'direction': direction_str,
                'operations_scheduled': len(scheduled),
                'schedule': [
                    {
                        'operation_id': op.operation_id,
                        'operation': op.operation_code,
                        'work_center': op.work_center_code,
                        'start': op.scheduled_start.isoformat(),
                        'end': op.scheduled_end.isoformat(),
                        'hours': round(op.total_hours, 2)
                    }
                    for op in scheduled
                ]
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@capacity_bp.route('/gantt', methods=['GET'])
def get_gantt_data():
    """
    Get schedule data for Gantt chart display.

    Query params:
    - work_center_id: Filter by work center
    - start: Start date (ISO format)
    - end: End date (ISO format)
    """
    work_center_id = request.args.get('work_center_id')
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    start_date = datetime.fromisoformat(start_str) if start_str else None
    end_date = datetime.fromisoformat(end_str) if end_str else None

    with get_db_session() as session:
        planner = CapacityPlanner(session)

        gantt = planner.get_schedule_gantt(
            work_center_id=work_center_id,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(gantt)


@capacity_bp.route('/load-level', methods=['POST'])
def load_level():
    """
    Attempt to level load across work centers.

    Request body:
    {
        "work_order_ids": ["uuid1", "uuid2"],
        "target_utilization": 80
    }
    """
    data = request.get_json()
    work_order_ids = data.get('work_order_ids', [])
    target_utilization = data.get('target_utilization', 80)

    if not work_order_ids:
        return jsonify({'error': 'work_order_ids are required'}), 400

    with get_db_session() as session:
        planner = CapacityPlanner(session)

        results = []
        for wo_id in work_order_ids:
            try:
                scheduled = planner.schedule_work_order(wo_id)
                results.append({
                    'work_order_id': wo_id,
                    'status': 'scheduled',
                    'operations': len(scheduled)
                })
            except Exception as e:
                results.append({
                    'work_order_id': wo_id,
                    'status': 'failed',
                    'error': str(e)
                })

        return jsonify({
            'results': results,
            'scheduled': sum(1 for r in results if r['status'] == 'scheduled'),
            'failed': sum(1 for r in results if r['status'] == 'failed')
        })
