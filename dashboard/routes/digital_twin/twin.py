"""
Digital Twin API - Real-time equipment state and monitoring.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime

from models import get_db_session
from services.digital_twin import DigitalTwinManager

twin_bp = Blueprint('twin', __name__, url_prefix='/state')


@twin_bp.route('/<work_center_id>', methods=['GET'])
def get_twin_state(work_center_id: str):
    """
    Get current digital twin state for a work center.

    Returns real-time snapshot of equipment state.
    """
    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        try:
            state = manager.get_current_state(work_center_id)

            return jsonify({
                'work_center_id': work_center_id,
                'snapshot': {
                    'timestamp': state.timestamp.isoformat(),
                    'status': state.status.value if hasattr(state.status, 'value') else state.status,
                    'temperature': state.temperature,
                    'position': state.position,
                    'speed': state.speed,
                    'power': state.power,
                    'job_id': state.job_id,
                    'job_progress': state.job_progress,
                    'estimated_completion': state.estimated_completion.isoformat() if state.estimated_completion else None,
                    'alerts': state.alerts
                }
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 404


@twin_bp.route('/<work_center_id>', methods=['POST'])
def update_twin_state(work_center_id: str):
    """
    Update digital twin state.

    Body:
    {
        "state_type": "temperature|position|status|job|metrics",
        "state_data": {...}
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    state_type = data.get('state_type')
    state_data = data.get('state_data')

    if not state_type or not state_data:
        return jsonify({'error': 'state_type and state_data required'}), 400

    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        try:
            result = manager.update_state(
                work_center_id=work_center_id,
                state_type=state_type,
                state_data=state_data
            )

            return jsonify({
                'success': True,
                'work_center_id': work_center_id,
                'state_type': state_type,
                'updated_at': datetime.utcnow().isoformat()
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@twin_bp.route('/<work_center_id>/history', methods=['GET'])
def get_state_history(work_center_id: str):
    """
    Get historical state data.

    Query params:
    - state_type: Filter by state type
    - hours: Hours of history (default 24)
    - limit: Max records (default 100)
    """
    state_type = request.args.get('state_type')
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 100, type=int)

    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        history = manager.get_state_history(
            work_center_id=work_center_id,
            state_type=state_type,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'work_center_id': work_center_id,
            'state_type': state_type,
            'hours': hours,
            'records': history
        })


@twin_bp.route('/all', methods=['GET'])
def get_all_twins():
    """Get overview of all digital twins."""
    with get_db_session() as session:
        manager = DigitalTwinManager(session)
        twins = manager.get_all_twins()

        return jsonify({
            'twins': twins,
            'total': len(twins),
            'generated_at': datetime.utcnow().isoformat()
        })


@twin_bp.route('/<work_center_id>/kpis', methods=['GET'])
def get_twin_kpis(work_center_id: str):
    """
    Get KPIs calculated from twin state data.

    Query params:
    - hours: Hours to analyze (default 24)
    """
    hours = request.args.get('hours', 24, type=int)

    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        try:
            kpis = manager.calculate_kpis(
                work_center_id=work_center_id,
                hours=hours
            )

            return jsonify(kpis)

        except ValueError as e:
            return jsonify({'error': str(e)}), 404
