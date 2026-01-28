"""
Downtime Tracking API Routes.

Provides REST API endpoints for equipment downtime tracking,
reason code management, and MTBF/MTTR analytics.
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

downtime_bp = Blueprint('downtime', __name__, url_prefix='/api/downtime')

# Lazy service initialization
_downtime_service = None


def get_downtime_service():
    """Get or create the downtime service instance."""
    global _downtime_service
    if _downtime_service is None:
        from services.downtime_service import DowntimeService
        _downtime_service = DowntimeService()
    return _downtime_service


# =============================================================================
# Downtime Event Management
# =============================================================================

@downtime_bp.route('/events', methods=['GET'])
def list_events():
    """
    List downtime events with filtering.

    Query Parameters:
        machine_id: Filter by machine
        status: Filter by status (active, resolved, acknowledged)
        category: Filter by category (equipment, tooling, material, quality, changeover, planned, external, operator)
        start_date: Start of date range (ISO format)
        end_date: End of date range (ISO format)
        limit: Maximum results (default 100)
    """
    try:
        service = get_downtime_service()

        machine_id = request.args.get('machine_id')
        status = request.args.get('status')
        category = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)

        events = list(service.events.values())

        if machine_id:
            events = [e for e in events if e.machine_id == machine_id]

        if status:
            from services.downtime_service import DowntimeStatus
            try:
                status_enum = DowntimeStatus(status)
                events = [e for e in events if e.status == status_enum]
            except ValueError:
                pass

        if category:
            from services.downtime_service import DowntimeCategory
            try:
                cat_enum = DowntimeCategory(category)
                events = [e for e in events if e.category == cat_enum]
            except ValueError:
                pass

        if start_date:
            from datetime import datetime
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            events = [e for e in events if e.start_time >= start]

        if end_date:
            from datetime import datetime
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            events = [e for e in events if e.start_time <= end]

        # Sort by start time descending
        events.sort(key=lambda x: x.start_time, reverse=True)

        # Apply limit
        events = events[:limit]

        return jsonify({
            'success': True,
            'events': [e.to_dict() for e in events],
            'count': len(events)
        })

    except Exception as e:
        logger.error(f"Error listing events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/events', methods=['POST'])
def start_downtime():
    """
    Start a downtime event.

    Request Body:
        machine_id: Machine ID (required)
        reason_code: Reason code (optional, uses UNPLANNED if not provided)
        description: Description (optional)
        operator_id: Reporting operator (optional)
        work_order_id: Affected work order (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('machine_id'):
            return jsonify({
                'success': False,
                'error': 'machine_id required'
            }), 400

        service = get_downtime_service()

        event = service.start_downtime(
            machine_id=data['machine_id'],
            reason_code=data.get('reason_code'),
            description=data.get('description'),
            operator_id=data.get('operator_id'),
            work_order_id=data.get('work_order_id')
        )

        return jsonify({
            'success': True,
            'event': event.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error starting downtime: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/events/<event_id>', methods=['GET'])
def get_event(event_id: str):
    """Get a specific downtime event."""
    try:
        service = get_downtime_service()
        event = service.events.get(event_id)

        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404

        return jsonify({
            'success': True,
            'event': event.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting event: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/events/<event_id>/end', methods=['POST'])
def end_downtime(event_id: str):
    """
    End a downtime event.

    Request Body:
        resolution: Resolution description (optional)
        corrective_action: Corrective action taken (optional)
        operator_id: Resolving operator (optional)
    """
    try:
        data = request.get_json() or {}

        service = get_downtime_service()

        event = service.end_downtime(
            event_id=event_id,
            resolution=data.get('resolution', ''),
            corrective_action=data.get('corrective_action'),
            operator_id=data.get('operator_id')
        )

        if event:
            return jsonify({
                'success': True,
                'event': event.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Event not found or already resolved'
            }), 400

    except Exception as e:
        logger.error(f"Error ending downtime: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/machines/<machine_id>/end', methods=['POST'])
def end_machine_downtime(machine_id: str):
    """
    End active downtime for a machine.

    Request Body:
        resolution: Resolution description (optional)
        corrective_action: Corrective action taken (optional)
        operator_id: Resolving operator (optional)
    """
    try:
        data = request.get_json() or {}

        service = get_downtime_service()

        event = service.end_downtime(
            machine_id=machine_id,
            resolution=data.get('resolution', ''),
            corrective_action=data.get('corrective_action'),
            operator_id=data.get('operator_id')
        )

        if event:
            return jsonify({
                'success': True,
                'event': event.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No active downtime found for machine'
            }), 400

    except Exception as e:
        logger.error(f"Error ending machine downtime: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Machine Status
# =============================================================================

@downtime_bp.route('/machines/down', methods=['GET'])
def get_machines_down():
    """Get list of machines currently in downtime."""
    try:
        service = get_downtime_service()

        machines_down = service.get_machines_down()

        return jsonify({
            'success': True,
            'machines_down': machines_down,
            'count': len(machines_down)
        })

    except Exception as e:
        logger.error(f"Error getting machines down: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/machines/<machine_id>/status', methods=['GET'])
def get_machine_status(machine_id: str):
    """Get current downtime status for a machine."""
    try:
        service = get_downtime_service()

        # Check for active downtime
        active = service.active_downtime.get(machine_id)

        if active:
            event = service.events.get(active)
            return jsonify({
                'success': True,
                'machine_id': machine_id,
                'is_down': True,
                'active_event': event.to_dict() if event else None
            })
        else:
            return jsonify({
                'success': True,
                'machine_id': machine_id,
                'is_down': False,
                'active_event': None
            })

    except Exception as e:
        logger.error(f"Error getting machine status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Reason Codes
# =============================================================================

@downtime_bp.route('/reason-codes', methods=['GET'])
def list_reason_codes():
    """
    List all reason codes.

    Query Parameters:
        category: Filter by category
        active_only: Only show active codes (default true)
    """
    try:
        service = get_downtime_service()

        category = request.args.get('category')
        active_only = request.args.get('active_only', 'true').lower() == 'true'

        codes = list(service.reason_codes.values())

        if active_only:
            codes = [c for c in codes if c.is_active]

        if category:
            from services.downtime_service import DowntimeCategory
            try:
                cat_enum = DowntimeCategory(category)
                codes = [c for c in codes if c.category == cat_enum]
            except ValueError:
                pass

        return jsonify({
            'success': True,
            'reason_codes': [c.to_dict() for c in codes],
            'count': len(codes)
        })

    except Exception as e:
        logger.error(f"Error listing reason codes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/reason-codes', methods=['POST'])
def create_reason_code():
    """
    Create a new reason code.

    Request Body:
        code: Unique code (required)
        description: Description (required)
        category: equipment, tooling, material, quality, changeover, planned, external, operator (required)
        planned: Is this planned downtime (default false)
    """
    try:
        data = request.get_json()

        if not data or not data.get('code') or not data.get('description') or not data.get('category'):
            return jsonify({
                'success': False,
                'error': 'code, description, and category required'
            }), 400

        service = get_downtime_service()

        from services.downtime_service import DowntimeCategory, ReasonCode
        try:
            cat_enum = DowntimeCategory(data['category'])
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid category: {data["category"]}'
            }), 400

        reason_code = ReasonCode(
            code=data['code'],
            description=data['description'],
            category=cat_enum,
            planned=data.get('planned', False)
        )

        service.reason_codes[data['code']] = reason_code

        return jsonify({
            'success': True,
            'reason_code': reason_code.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error creating reason code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Analytics
# =============================================================================

@downtime_bp.route('/analytics/pareto', methods=['GET'])
def get_pareto_analysis():
    """
    Get Pareto analysis of downtime.

    Query Parameters:
        machine_id: Filter by machine (optional)
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
        group_by: reason_code, category, machine_id (default reason_code)
        top_n: Number of top items (default 10)
    """
    try:
        service = get_downtime_service()

        machine_id = request.args.get('machine_id')
        start_date = None
        end_date = None
        group_by = request.args.get('group_by', 'reason_code')
        top_n = request.args.get('top_n', 10, type=int)

        if request.args.get('start_date'):
            from datetime import datetime
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            from datetime import datetime
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        pareto = service.get_pareto_analysis(
            machine_id=machine_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by
        )

        # Limit to top N
        pareto = pareto[:top_n]

        return jsonify({
            'success': True,
            'pareto': pareto,
            'group_by': group_by
        })

    except Exception as e:
        logger.error(f"Error getting Pareto analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/analytics/mtbf-mttr/<machine_id>', methods=['GET'])
def get_mtbf_mttr(machine_id: str):
    """
    Get MTBF and MTTR for a machine.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_downtime_service()

        start_date = None
        end_date = None

        if request.args.get('start_date'):
            from datetime import datetime
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            from datetime import datetime
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        metrics = service.calculate_mtbf_mttr(
            machine_id=machine_id,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'success': True,
            'metrics': metrics
        })

    except Exception as e:
        logger.error(f"Error getting MTBF/MTTR: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/analytics/summary', methods=['GET'])
def get_downtime_summary():
    """
    Get overall downtime summary.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_downtime_service()

        start_date = None
        end_date = None

        if request.args.get('start_date'):
            from datetime import datetime
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            from datetime import datetime
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        summary = service.get_downtime_summary(
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@downtime_bp.route('/analytics/trends', methods=['GET'])
def get_downtime_trends():
    """
    Get downtime trends over time.

    Query Parameters:
        machine_id: Filter by machine (optional)
        period: day, week, month (default day)
        periods: Number of periods to analyze (default 30)
    """
    try:
        service = get_downtime_service()

        from datetime import datetime, timedelta

        machine_id = request.args.get('machine_id')
        period = request.args.get('period', 'day')
        num_periods = request.args.get('periods', 30, type=int)

        events = list(service.events.values())

        if machine_id:
            events = [e for e in events if e.machine_id == machine_id]

        # Determine period duration
        if period == 'day':
            delta = timedelta(days=1)
        elif period == 'week':
            delta = timedelta(weeks=1)
        elif period == 'month':
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=1)

        # Calculate trends
        now = datetime.now()
        trends = []

        for i in range(num_periods):
            period_end = now - (i * delta)
            period_start = period_end - delta

            period_events = [
                e for e in events
                if period_start <= e.start_time < period_end
            ]

            total_minutes = sum(e.duration_minutes or 0 for e in period_events)

            trends.append({
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'event_count': len(period_events),
                'total_downtime_minutes': round(total_minutes, 2)
            })

        # Reverse to show oldest first
        trends.reverse()

        return jsonify({
            'success': True,
            'trends': trends,
            'period': period,
            'machine_id': machine_id
        })

    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
