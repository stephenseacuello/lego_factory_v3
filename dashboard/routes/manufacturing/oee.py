"""
OEE Dashboard API - Overall Equipment Effectiveness monitoring.

OEE = Availability x Performance x Quality

Provides:
- OEE calculations and trends
- Downtime tracking and analysis
- Production metrics
- Shift reports
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime, timedelta

from models import get_db_session, WorkCenter
from models.analytics import OEEEvent
from services.manufacturing import OEEService

oee_bp = Blueprint('oee', __name__, url_prefix='/oee')


# Dashboard Page Route
@oee_bp.route('', methods=['GET'])
def oee_page():
    """Render OEE dashboard page."""
    return render_template('pages/manufacturing/oee_dashboard.html')


@oee_bp.route('/dashboard', methods=['GET'])
def get_oee_dashboard():
    """
    Get OEE dashboard for all work centers.

    Query params:
    - period: 'shift', 'day', 'week', 'month' (default: 'day')
    """
    period = request.args.get('period', 'day')

    with get_db_session() as session:
        oee_service = OEEService(session)
        work_centers = session.query(WorkCenter).all()

        # Calculate period
        now = datetime.utcnow()
        if period == 'shift':
            hours = 8
        elif period == 'week':
            hours = 168
        elif period == 'month':
            hours = 720
        else:  # day
            hours = 24

        start_time = now - timedelta(hours=hours)

        dashboard_data = []
        for wc in work_centers:
            oee_data = oee_service.calculate_oee(
                str(wc.id),
                start_time=start_time,
                end_time=now
            )

            dashboard_data.append({
                'work_center': {
                    'id': str(wc.id),
                    'code': wc.code,
                    'name': wc.name,
                    'type': wc.type,
                    'status': wc.status
                },
                'oee': oee_data
            })

        # Calculate plant-wide OEE
        total_oee = 0
        total_availability = 0
        total_performance = 0
        total_quality = 0
        count = len(dashboard_data)

        if count > 0:
            for item in dashboard_data:
                oee = item['oee']
                total_oee += oee.get('oee', 0)
                total_availability += oee.get('availability', 0)
                total_performance += oee.get('performance', 0)
                total_quality += oee.get('quality', 0)

        return jsonify({
            'period': period,
            'start_time': start_time.isoformat(),
            'end_time': now.isoformat(),
            'plant_oee': {
                'oee': round(total_oee / count, 1) if count > 0 else 0,
                'availability': round(total_availability / count, 1) if count > 0 else 0,
                'performance': round(total_performance / count, 1) if count > 0 else 0,
                'quality': round(total_quality / count, 1) if count > 0 else 0
            },
            'work_centers': dashboard_data
        })


@oee_bp.route('/<work_center_id>', methods=['GET'])
def get_work_center_oee(work_center_id: str):
    """
    Get detailed OEE for specific work center.

    Query params:
    - start: Start datetime (ISO format)
    - end: End datetime (ISO format)
    - period: Alternative to start/end
    """
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    period = request.args.get('period', 'day')

    now = datetime.utcnow()

    if start_str and end_str:
        start_time = datetime.fromisoformat(start_str)
        end_time = datetime.fromisoformat(end_str)
    else:
        if period == 'shift':
            hours = 8
        elif period == 'week':
            hours = 168
        elif period == 'month':
            hours = 720
        else:
            hours = 24
        start_time = now - timedelta(hours=hours)
        end_time = now

    with get_db_session() as session:
        oee_service = OEEService(session)

        oee_data = oee_service.calculate_oee(
            work_center_id,
            start_time=start_time,
            end_time=end_time
        )

        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        return jsonify({
            'work_center': {
                'id': str(wc.id),
                'code': wc.code,
                'name': wc.name
            } if wc else None,
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'oee': oee_data
        })


@oee_bp.route('/<work_center_id>/trend', methods=['GET'])
def get_oee_trend(work_center_id: str):
    """
    Get OEE trend over time.

    Query params:
    - period: 'day', 'week', 'month' (default: 'week')
    - interval: 'hour', 'day' (default: 'day')
    """
    period = request.args.get('period', 'week')
    interval = request.args.get('interval', 'day')

    now = datetime.utcnow()

    if period == 'day':
        start_time = now - timedelta(days=1)
        interval_hours = 1 if interval == 'hour' else 24
    elif period == 'month':
        start_time = now - timedelta(days=30)
        interval_hours = 24
    else:  # week
        start_time = now - timedelta(days=7)
        interval_hours = 24 if interval == 'day' else 1

    with get_db_session() as session:
        oee_service = OEEService(session)

        trend_data = []
        current = start_time

        while current < now:
            interval_end = current + timedelta(hours=interval_hours)
            if interval_end > now:
                interval_end = now

            oee_data = oee_service.calculate_oee(
                work_center_id,
                start_time=current,
                end_time=interval_end
            )

            trend_data.append({
                'timestamp': current.isoformat(),
                'oee': oee_data.get('oee', 0),
                'availability': oee_data.get('availability', 0),
                'performance': oee_data.get('performance', 0),
                'quality': oee_data.get('quality', 0)
            })

            current = interval_end

        return jsonify({
            'work_center_id': work_center_id,
            'period': period,
            'interval': interval,
            'trend': trend_data
        })


@oee_bp.route('/downtime/pareto', methods=['GET'])
def get_downtime_pareto():
    """
    Get downtime Pareto analysis.

    Query params:
    - work_center_id: Filter by work center (optional)
    - period: 'day', 'week', 'month' (default: 'week')
    """
    work_center_id = request.args.get('work_center_id')
    period = request.args.get('period', 'week')

    now = datetime.utcnow()
    if period == 'day':
        start_time = now - timedelta(days=1)
    elif period == 'month':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(days=7)

    with get_db_session() as session:
        oee_service = OEEService(session)
        pareto = oee_service.get_downtime_pareto(
            work_center_id=work_center_id,
            start_time=start_time,
            end_time=now
        )

        return jsonify({
            'period': period,
            'start_time': start_time.isoformat(),
            'end_time': now.isoformat(),
            'pareto': pareto
        })


@oee_bp.route('/events', methods=['POST'])
def record_oee_event():
    """
    Record an OEE event (production start/stop, downtime, etc).

    Request body:
    {
        "work_center_id": "uuid",
        "event_type": "production_start|production_end|downtime_start|downtime_end",
        "reason_code": "SETUP",
        "parts_produced": 10,
        "parts_defective": 0,
        "notes": "Optional notes"
    }
    """
    data = request.get_json()

    work_center_id = data.get('work_center_id')
    event_type = data.get('event_type')

    if not all([work_center_id, event_type]):
        return jsonify({'error': 'work_center_id and event_type are required'}), 400

    with get_db_session() as session:
        oee_service = OEEService(session)

        if event_type == 'production_start':
            oee_service.record_production_start(work_center_id)
            return jsonify({'message': 'Production started'})

        elif event_type == 'production_end':
            parts_produced = data.get('parts_produced', 0)
            parts_defective = data.get('parts_defective', 0)
            oee_service.record_production_end(
                work_center_id,
                parts_produced=parts_produced,
                parts_defective=parts_defective
            )
            return jsonify({'message': 'Production ended'})

        elif event_type == 'downtime_start':
            reason_code = data.get('reason_code', 'UNPLANNED')
            oee_service.record_downtime(
                work_center_id,
                reason_code=reason_code,
                notes=data.get('notes')
            )
            return jsonify({'message': 'Downtime recorded'})

        elif event_type == 'downtime_end':
            # Find and end active downtime
            active_downtime = session.query(OEEEvent).filter(
                OEEEvent.work_center_id == work_center_id,
                OEEEvent.event_type == 'downtime',
                OEEEvent.end_time.is_(None)
            ).first()

            if active_downtime:
                active_downtime.end_time = datetime.utcnow()
                session.commit()
                return jsonify({'message': 'Downtime ended'})
            else:
                return jsonify({'message': 'No active downtime found'}), 404

        else:
            return jsonify({'error': f'Unknown event type: {event_type}'}), 400


@oee_bp.route('/shift-report', methods=['GET'])
def get_shift_report():
    """
    Get shift production report.

    Query params:
    - work_center_id: Filter by work center (optional)
    - shift: 'current', 'previous', or datetime (default: 'current')
    """
    work_center_id = request.args.get('work_center_id')
    shift = request.args.get('shift', 'current')

    # Calculate shift times (assuming 8-hour shifts at 6:00, 14:00, 22:00)
    now = datetime.utcnow()
    hour = now.hour

    if shift == 'current':
        if hour < 6:
            start = now.replace(hour=22, minute=0, second=0) - timedelta(days=1)
            end = now.replace(hour=6, minute=0, second=0)
        elif hour < 14:
            start = now.replace(hour=6, minute=0, second=0)
            end = now.replace(hour=14, minute=0, second=0)
        elif hour < 22:
            start = now.replace(hour=14, minute=0, second=0)
            end = now.replace(hour=22, minute=0, second=0)
        else:
            start = now.replace(hour=22, minute=0, second=0)
            end = now.replace(hour=6, minute=0, second=0) + timedelta(days=1)

        # Cap end time at current time for current shift
        if end > now:
            end = now
    elif shift == 'previous':
        if hour < 6:
            start = now.replace(hour=14, minute=0, second=0) - timedelta(days=1)
            end = now.replace(hour=22, minute=0, second=0) - timedelta(days=1)
        elif hour < 14:
            start = now.replace(hour=22, minute=0, second=0) - timedelta(days=1)
            end = now.replace(hour=6, minute=0, second=0)
        elif hour < 22:
            start = now.replace(hour=6, minute=0, second=0)
            end = now.replace(hour=14, minute=0, second=0)
        else:
            start = now.replace(hour=14, minute=0, second=0)
            end = now.replace(hour=22, minute=0, second=0)
    else:
        # Parse datetime
        start = datetime.fromisoformat(shift)
        end = start + timedelta(hours=8)

    with get_db_session() as session:
        oee_service = OEEService(session)

        if work_center_id:
            work_centers = [session.query(WorkCenter).filter(
                WorkCenter.id == work_center_id
            ).first()]
        else:
            work_centers = session.query(WorkCenter).all()

        report_data = []
        for wc in work_centers:
            if not wc:
                continue

            oee_data = oee_service.calculate_oee(
                str(wc.id),
                start_time=start,
                end_time=end
            )

            report_data.append({
                'work_center': {
                    'id': str(wc.id),
                    'code': wc.code,
                    'name': wc.name
                },
                'oee': oee_data
            })

        return jsonify({
            'shift': {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'duration_hours': (end - start).total_seconds() / 3600
            },
            'work_centers': report_data
        })
