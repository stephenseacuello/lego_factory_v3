"""
Labor Tracking API Routes.

Provides REST API endpoints for operator time tracking, clock in/out,
break management, and labor cost calculations.
"""

from flask import Blueprint, request, jsonify
from typing import Optional
import logging

logger = logging.getLogger(__name__)

labor_bp = Blueprint('labor', __name__, url_prefix='/api/labor')

# Lazy service initialization
_labor_service = None


def get_labor_service():
    """Get or create the labor service instance."""
    global _labor_service
    if _labor_service is None:
        from services.labor_service import LaborService
        _labor_service = LaborService()
    return _labor_service


# =============================================================================
# Operator Management
# =============================================================================

@labor_bp.route('/operators', methods=['GET'])
def list_operators():
    """
    List all registered operators.

    Query Parameters:
        active_only: Only show active operators (default false)
        department: Filter by department
    """
    try:
        service = get_labor_service()

        active_only = request.args.get('active_only', 'false').lower() == 'true'
        department = request.args.get('department')

        operators = list(service.operators.values())

        if active_only:
            operators = [op for op in operators if op.is_active]

        if department:
            operators = [op for op in operators if op.department == department]

        return jsonify({
            'success': True,
            'operators': [op.to_dict() for op in operators],
            'count': len(operators)
        })

    except Exception as e:
        logger.error(f"Error listing operators: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/operators', methods=['POST'])
def register_operator():
    """
    Register a new operator.

    Request Body:
        badge_number: Unique badge number (required)
        name: Operator name (required)
        department: Department (optional)
        shift: Shift assignment (optional)
        hourly_rate: Hourly pay rate (optional)
        skills: List of skill certifications (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('badge_number') or not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'badge_number and name required'
            }), 400

        service = get_labor_service()

        operator = service.register_operator(
            badge_number=data['badge_number'],
            name=data['name'],
            department=data.get('department'),
            shift=data.get('shift'),
            hourly_rate=data.get('hourly_rate'),
            skills=data.get('skills')
        )

        return jsonify({
            'success': True,
            'operator': operator.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error registering operator: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/operators/<operator_id>', methods=['GET'])
def get_operator(operator_id: str):
    """Get operator details by ID."""
    try:
        service = get_labor_service()
        operator = service.operators.get(operator_id)

        if not operator:
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404

        return jsonify({
            'success': True,
            'operator': operator.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting operator: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/operators/badge/<badge_number>', methods=['GET'])
def get_operator_by_badge(badge_number: str):
    """Get operator by badge number."""
    try:
        service = get_labor_service()
        operator = service.get_operator_by_badge(badge_number)

        if not operator:
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404

        return jsonify({
            'success': True,
            'operator': operator.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting operator by badge: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Clock In/Out Operations
# =============================================================================

@labor_bp.route('/clock-in', methods=['POST'])
def clock_in():
    """
    Clock in an operator.

    Request Body:
        operator_id: Operator ID (required, or badge_number)
        badge_number: Badge number (alternative to operator_id)
        labor_type: direct, indirect, setup, rework (default direct)
        work_order_id: Associated work order (optional)
        operation_id: Associated operation (optional)
        machine_id: Machine being operated (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        service = get_labor_service()

        # Get operator ID from badge if not provided directly
        operator_id = data.get('operator_id')
        if not operator_id and data.get('badge_number'):
            operator = service.get_operator_by_badge(data['badge_number'])
            if operator:
                operator_id = operator.id

        if not operator_id:
            return jsonify({
                'success': False,
                'error': 'operator_id or valid badge_number required'
            }), 400

        # Parse labor type
        labor_type = None
        if data.get('labor_type'):
            from services.labor_service import LaborType
            try:
                labor_type = LaborType(data['labor_type'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Invalid labor_type: {data["labor_type"]}'
                }), 400

        entry = service.clock_in(
            operator_id=operator_id,
            labor_type=labor_type,
            work_order_id=data.get('work_order_id'),
            operation_id=data.get('operation_id'),
            machine_id=data.get('machine_id')
        )

        if entry:
            return jsonify({
                'success': True,
                'time_entry': entry.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clock in - operator may already be clocked in'
            }), 400

    except Exception as e:
        logger.error(f"Error clocking in: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/clock-out', methods=['POST'])
def clock_out():
    """
    Clock out an operator.

    Request Body:
        operator_id: Operator ID (required, or badge_number)
        badge_number: Badge number (alternative to operator_id)
        quantity_produced: Parts produced (optional)
        quantity_scrap: Scrap parts (optional)
        notes: Clock out notes (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        service = get_labor_service()

        # Get operator ID from badge if not provided directly
        operator_id = data.get('operator_id')
        if not operator_id and data.get('badge_number'):
            operator = service.get_operator_by_badge(data['badge_number'])
            if operator:
                operator_id = operator.id

        if not operator_id:
            return jsonify({
                'success': False,
                'error': 'operator_id or valid badge_number required'
            }), 400

        entry = service.clock_out(
            operator_id=operator_id,
            quantity_produced=data.get('quantity_produced', 0),
            quantity_scrap=data.get('quantity_scrap', 0),
            notes=data.get('notes')
        )

        if entry:
            return jsonify({
                'success': True,
                'time_entry': entry.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clock out - operator may not be clocked in'
            }), 400

    except Exception as e:
        logger.error(f"Error clocking out: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Break Management
# =============================================================================

@labor_bp.route('/break/start', methods=['POST'])
def start_break():
    """
    Start a break for an operator.

    Request Body:
        operator_id: Operator ID (required, or badge_number)
        badge_number: Badge number (alternative to operator_id)
        break_type: short, lunch, personal (default short)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        service = get_labor_service()

        # Get operator ID from badge if not provided directly
        operator_id = data.get('operator_id')
        if not operator_id and data.get('badge_number'):
            operator = service.get_operator_by_badge(data['badge_number'])
            if operator:
                operator_id = operator.id

        if not operator_id:
            return jsonify({
                'success': False,
                'error': 'operator_id or valid badge_number required'
            }), 400

        break_entry = service.start_break(
            operator_id=operator_id,
            break_type=data.get('break_type', 'short')
        )

        if break_entry:
            return jsonify({
                'success': True,
                'break_entry': break_entry.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start break'
            }), 400

    except Exception as e:
        logger.error(f"Error starting break: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/break/end', methods=['POST'])
def end_break():
    """
    End a break for an operator.

    Request Body:
        operator_id: Operator ID (required, or badge_number)
        badge_number: Badge number (alternative to operator_id)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        service = get_labor_service()

        # Get operator ID from badge if not provided directly
        operator_id = data.get('operator_id')
        if not operator_id and data.get('badge_number'):
            operator = service.get_operator_by_badge(data['badge_number'])
            if operator:
                operator_id = operator.id

        if not operator_id:
            return jsonify({
                'success': False,
                'error': 'operator_id or valid badge_number required'
            }), 400

        break_entry = service.end_break(operator_id)

        if break_entry:
            return jsonify({
                'success': True,
                'break_entry': break_entry.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to end break - no active break found'
            }), 400

    except Exception as e:
        logger.error(f"Error ending break: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Time Entries
# =============================================================================

@labor_bp.route('/entries', methods=['GET'])
def list_time_entries():
    """
    List time entries with filtering.

    Query Parameters:
        operator_id: Filter by operator
        work_order_id: Filter by work order
        start_date: Start of date range (ISO format)
        end_date: End of date range (ISO format)
        status: Filter by status (active, completed)
        limit: Maximum results (default 100)
    """
    try:
        service = get_labor_service()

        operator_id = request.args.get('operator_id')
        work_order_id = request.args.get('work_order_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)

        entries = list(service.time_entries.values())

        # Apply filters
        if operator_id:
            entries = [e for e in entries if e.operator_id == operator_id]

        if work_order_id:
            entries = [e for e in entries if e.work_order_id == work_order_id]

        if start_date:
            from datetime import datetime
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            entries = [e for e in entries if e.clock_in_time >= start]

        if end_date:
            from datetime import datetime
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            entries = [e for e in entries if e.clock_in_time <= end]

        if status:
            from services.labor_service import TimeEntryStatus
            try:
                status_enum = TimeEntryStatus(status)
                entries = [e for e in entries if e.status == status_enum]
            except ValueError:
                pass

        # Sort by clock in time descending
        entries.sort(key=lambda x: x.clock_in_time, reverse=True)

        # Apply limit
        entries = entries[:limit]

        return jsonify({
            'success': True,
            'entries': [e.to_dict() for e in entries],
            'count': len(entries)
        })

    except Exception as e:
        logger.error(f"Error listing time entries: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/entries/<entry_id>', methods=['GET'])
def get_time_entry(entry_id: str):
    """Get a specific time entry."""
    try:
        service = get_labor_service()
        entry = service.time_entries.get(entry_id)

        if not entry:
            return jsonify({
                'success': False,
                'error': 'Time entry not found'
            }), 404

        return jsonify({
            'success': True,
            'entry': entry.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting time entry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Reports and Analytics
# =============================================================================

@labor_bp.route('/who-is-working', methods=['GET'])
def who_is_working():
    """Get list of operators currently working."""
    try:
        service = get_labor_service()
        working = service.get_who_is_working()

        return jsonify({
            'success': True,
            'working': working,
            'count': len(working)
        })

    except Exception as e:
        logger.error(f"Error getting who is working: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/operators/<operator_id>/summary', methods=['GET'])
def get_operator_summary(operator_id: str):
    """
    Get labor summary for an operator.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_labor_service()

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

        summary = service.get_operator_summary(
            operator_id=operator_id,
            start_date=start_date,
            end_date=end_date
        )

        if summary:
            return jsonify({
                'success': True,
                'summary': summary
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting operator summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/workorders/<work_order_id>/labor-cost', methods=['GET'])
def get_work_order_labor_cost(work_order_id: str):
    """Get total labor cost for a work order."""
    try:
        service = get_labor_service()
        cost = service.get_work_order_labor_cost(work_order_id)

        return jsonify({
            'success': True,
            'labor_cost': cost
        })

    except Exception as e:
        logger.error(f"Error getting work order labor cost: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/reports/daily', methods=['GET'])
def get_daily_report():
    """
    Get daily labor report.

    Query Parameters:
        date: Date for report (ISO format, default today)
    """
    try:
        service = get_labor_service()

        from datetime import datetime, timedelta

        report_date = datetime.now().date()
        if request.args.get('date'):
            report_date = datetime.fromisoformat(
                request.args.get('date').replace('Z', '+00:00')
            ).date()

        start = datetime.combine(report_date, datetime.min.time())
        end = datetime.combine(report_date, datetime.max.time())

        # Get entries for the day
        entries = [
            e for e in service.time_entries.values()
            if e.clock_in_time.date() == report_date
        ]

        # Aggregate by operator
        by_operator = {}
        for entry in entries:
            if entry.operator_id not in by_operator:
                operator = service.operators.get(entry.operator_id)
                by_operator[entry.operator_id] = {
                    'operator_id': entry.operator_id,
                    'operator_name': operator.name if operator else 'Unknown',
                    'total_hours': 0,
                    'break_hours': 0,
                    'entries': 0,
                    'quantity_produced': 0,
                    'quantity_scrap': 0
                }

            hours_worked = entry.total_hours or 0
            by_operator[entry.operator_id]['total_hours'] += hours_worked
            by_operator[entry.operator_id]['entries'] += 1
            by_operator[entry.operator_id]['quantity_produced'] += entry.quantity_produced
            by_operator[entry.operator_id]['quantity_scrap'] += entry.quantity_scrap

        return jsonify({
            'success': True,
            'report': {
                'date': report_date.isoformat(),
                'total_entries': len(entries),
                'total_operators': len(by_operator),
                'by_operator': list(by_operator.values())
            }
        })

    except Exception as e:
        logger.error(f"Error getting daily report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@labor_bp.route('/reports/efficiency', methods=['GET'])
def get_efficiency_report():
    """
    Get labor efficiency report.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_labor_service()

        from datetime import datetime, timedelta

        # Default to last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        if request.args.get('start_date'):
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        # Filter entries
        entries = [
            e for e in service.time_entries.values()
            if start_date <= e.clock_in_time <= end_date
        ]

        from services.labor_service import LaborType

        # Calculate metrics
        total_direct_hours = sum(
            e.total_hours or 0 for e in entries
            if e.labor_type == LaborType.DIRECT
        )
        total_indirect_hours = sum(
            e.total_hours or 0 for e in entries
            if e.labor_type == LaborType.INDIRECT
        )
        total_setup_hours = sum(
            e.total_hours or 0 for e in entries
            if e.labor_type == LaborType.SETUP
        )
        total_rework_hours = sum(
            e.total_hours or 0 for e in entries
            if e.labor_type == LaborType.REWORK
        )

        total_hours = total_direct_hours + total_indirect_hours + total_setup_hours + total_rework_hours

        return jsonify({
            'success': True,
            'efficiency_report': {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_hours': round(total_hours, 2),
                'direct_hours': round(total_direct_hours, 2),
                'indirect_hours': round(total_indirect_hours, 2),
                'setup_hours': round(total_setup_hours, 2),
                'rework_hours': round(total_rework_hours, 2),
                'direct_ratio': round(
                    (total_direct_hours / total_hours * 100) if total_hours > 0 else 0, 2
                ),
                'total_entries': len(entries)
            }
        })

    except Exception as e:
        logger.error(f"Error getting efficiency report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
