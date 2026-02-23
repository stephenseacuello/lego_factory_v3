"""
Predictive Maintenance API - Equipment health and maintenance scheduling.
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime

from models import get_db_session
from services.digital_twin import PredictiveMaintenanceService

maintenance_bp = Blueprint('maintenance', __name__, url_prefix='/maintenance')


# =============================================================================
# Dashboard Page Route
# =============================================================================

@maintenance_bp.route('/page', methods=['GET'])
def maintenance_dashboard():
    """Render the Predictive Maintenance dashboard page."""
    return render_template('pages/digital_twin/maintenance_dashboard.html')


# =============================================================================
# API Routes
# =============================================================================

@maintenance_bp.route('/health/<work_center_id>', methods=['GET'])
def get_equipment_health(work_center_id: str):
    """
    Get equipment health score and status.

    Returns overall health score (0-100) with component breakdown.
    """
    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)

        try:
            health = service.calculate_health_score(work_center_id)

            return jsonify({
                'work_center_id': work_center_id,
                'overall_score': health.overall,
                'status': health.status.value,
                'components': health.components,
                'recommendations': health.recommendations,
                'calculated_at': datetime.utcnow().isoformat()
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 404


@maintenance_bp.route('/health/dashboard', methods=['GET'])
def get_health_dashboard():
    """Get health dashboard for all equipment."""
    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)
        dashboard = service.get_health_dashboard()

        return jsonify(dashboard)


@maintenance_bp.route('/recommendations', methods=['GET'])
def get_recommendations():
    """
    Get maintenance recommendations.

    Query params:
    - work_center_id: Filter by work center (optional)
    """
    work_center_id = request.args.get('work_center_id')

    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)
        recommendations = service.generate_recommendations(work_center_id)

        return jsonify({
            'recommendations': [
                {
                    'work_center_id': r.work_center_id,
                    'maintenance_type': r.maintenance_type.value,
                    'priority': r.priority,
                    'action': r.action,
                    'reason': r.reason,
                    'estimated_hours': r.estimated_hours,
                    'due_date': r.due_date.isoformat()
                }
                for r in recommendations
            ],
            'total': len(recommendations),
            'generated_at': datetime.utcnow().isoformat()
        })


@maintenance_bp.route('/schedule', methods=['GET'])
def get_maintenance_schedule():
    """
    Get maintenance schedule.

    Query params:
    - work_center_id: Filter by work center (optional)
    - include_completed: Include completed tasks (default false)
    """
    work_center_id = request.args.get('work_center_id')
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'

    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)
        schedule = service.get_maintenance_schedule(
            work_center_id=work_center_id,
            include_completed=include_completed
        )

        return jsonify({
            'schedule': schedule,
            'total': len(schedule)
        })


@maintenance_bp.route('/schedule', methods=['POST'])
def schedule_maintenance():
    """
    Schedule a maintenance task.

    Body:
    {
        "work_center_id": "uuid",
        "maintenance_type": "preventive|predictive|corrective|emergency",
        "description": "Maintenance description",
        "scheduled_date": "2024-01-15T10:00:00",
        "estimated_hours": 2.0
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['work_center_id', 'maintenance_type', 'description', 'scheduled_date']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400

    try:
        scheduled_date = datetime.fromisoformat(data['scheduled_date'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid scheduled_date format'}), 400

    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)

        try:
            record = service.schedule_maintenance(
                work_center_id=data['work_center_id'],
                maintenance_type=data['maintenance_type'],
                description=data['description'],
                scheduled_date=scheduled_date,
                estimated_hours=data.get('estimated_hours', 2.0)
            )

            return jsonify({
                'success': True,
                'maintenance_id': str(record.id),
                'status': record.status,
                'scheduled_date': record.scheduled_date.isoformat()
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@maintenance_bp.route('/complete/<maintenance_id>', methods=['POST'])
def complete_maintenance(maintenance_id: str):
    """
    Complete a maintenance task.

    Body:
    {
        "actual_hours": 2.5,
        "cost": 150.00,
        "notes": "Optional completion notes"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    actual_hours = data.get('actual_hours')
    if actual_hours is None:
        return jsonify({'error': 'actual_hours required'}), 400

    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)

        try:
            record = service.complete_maintenance(
                maintenance_id=maintenance_id,
                actual_hours=actual_hours,
                cost=data.get('cost', 0),
                notes=data.get('notes')
            )

            return jsonify({
                'success': True,
                'maintenance_id': str(record.id),
                'status': record.status,
                'completed_date': record.completed_date.isoformat() if record.completed_date else None,
                'actual_hours': record.actual_hours,
                'cost': float(record.cost) if record.cost else 0
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 404


@maintenance_bp.route('/alerts', methods=['GET'])
def get_maintenance_alerts():
    """
    Get maintenance alerts for equipment needing attention.

    Returns equipment with POOR or CRITICAL health status.
    """
    with get_db_session() as session:
        service = PredictiveMaintenanceService(session)
        dashboard = service.get_health_dashboard()

        alerts = []
        for equipment in dashboard.get('equipment', []):
            if equipment.get('status') in ['poor', 'critical']:
                alerts.append({
                    'work_center_id': equipment['work_center_id'],
                    'work_center_code': equipment.get('work_center_code'),
                    'work_center_name': equipment.get('work_center_name'),
                    'health_score': equipment.get('health_score'),
                    'status': equipment.get('status'),
                    'recommendations': equipment.get('recommendations', []),
                    'priority': 'CRITICAL' if equipment.get('status') == 'critical' else 'HIGH'
                })

        return jsonify({
            'alerts': alerts,
            'total': len(alerts),
            'generated_at': datetime.utcnow().isoformat()
        })
