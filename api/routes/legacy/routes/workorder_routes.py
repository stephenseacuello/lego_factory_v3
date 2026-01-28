"""
Work Order Management API Routes.

Provides REST API endpoints for MES work order lifecycle management
including creation, status transitions, operation tracking, and analytics.
"""

from flask import Blueprint, request, jsonify
from typing import Optional
import logging

logger = logging.getLogger(__name__)

workorder_bp = Blueprint('workorder', __name__, url_prefix='/api/workorders')

# Lazy service initialization
_workorder_service = None


def get_workorder_service():
    """Get or create the workorder service instance."""
    global _workorder_service
    if _workorder_service is None:
        from services.workorder_service import WorkOrderService
        _workorder_service = WorkOrderService()
    return _workorder_service


# =============================================================================
# Work Order CRUD Operations
# =============================================================================

@workorder_bp.route('/', methods=['GET'])
def list_work_orders():
    """
    List all work orders with optional filtering.

    Query Parameters:
        status: Filter by status (created, released, in_progress, completed, cancelled)
        priority: Filter by priority (1-10)
        part_number: Filter by part number
        limit: Maximum number of results (default 100)
        offset: Pagination offset
    """
    try:
        service = get_workorder_service()

        status = request.args.get('status')
        priority = request.args.get('priority', type=int)
        part_number = request.args.get('part_number')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Get all work orders
        work_orders = list(service.work_orders.values())

        # Apply filters
        if status:
            from services.workorder_service import WorkOrderStatus
            try:
                status_enum = WorkOrderStatus(status)
                work_orders = [wo for wo in work_orders if wo.status == status_enum]
            except ValueError:
                pass

        if priority:
            from services.workorder_service import Priority
            try:
                priority_enum = Priority(priority)
                work_orders = [wo for wo in work_orders if wo.priority == priority_enum]
            except ValueError:
                pass

        if part_number:
            work_orders = [wo for wo in work_orders if wo.part_number == part_number]

        # Sort by due date
        work_orders.sort(key=lambda x: x.due_date or x.created_at)

        # Apply pagination
        total = len(work_orders)
        work_orders = work_orders[offset:offset + limit]

        return jsonify({
            'success': True,
            'total': total,
            'limit': limit,
            'offset': offset,
            'work_orders': [wo.to_dict() for wo in work_orders]
        })

    except Exception as e:
        logger.error(f"Error listing work orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/', methods=['POST'])
def create_work_order():
    """
    Create a new work order.

    Request Body:
        part_number: Part number (required)
        part_name: Part name (required)
        quantity: Order quantity (required)
        due_date: ISO format due date (optional)
        priority: Priority 1-10 (default 5)
        customer_id: Customer identifier (optional)
        notes: Additional notes (optional)
        operations: List of operation definitions (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'Request body required'}), 400

        required = ['part_number', 'part_name', 'quantity']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {missing}'
            }), 400

        service = get_workorder_service()

        # Parse due date
        due_date = None
        if data.get('due_date'):
            from datetime import datetime
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))

        # Parse priority
        priority = None
        if data.get('priority'):
            from services.workorder_service import Priority
            priority = Priority(data['priority'])

        work_order = service.create_work_order(
            part_number=data['part_number'],
            part_name=data['part_name'],
            quantity=data['quantity'],
            due_date=due_date,
            priority=priority,
            customer_id=data.get('customer_id'),
            notes=data.get('notes')
        )

        # Add operations if provided
        if data.get('operations'):
            for op in data['operations']:
                service.add_operation(
                    work_order_id=work_order.id,
                    operation_name=op.get('name', 'Operation'),
                    work_center=op.get('work_center', 'DEFAULT'),
                    machine_id=op.get('machine_id'),
                    setup_time_min=op.get('setup_time_min', 0),
                    run_time_min=op.get('run_time_min', 0),
                    gcode_file=op.get('gcode_file'),
                    tool_list=op.get('tool_list')
                )

        return jsonify({
            'success': True,
            'work_order': work_order.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error creating work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>', methods=['GET'])
def get_work_order(work_order_id: str):
    """Get a specific work order by ID."""
    try:
        service = get_workorder_service()
        work_order = service.get_work_order(work_order_id)

        if not work_order:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404

        return jsonify({
            'success': True,
            'work_order': work_order.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>', methods=['PUT'])
def update_work_order(work_order_id: str):
    """
    Update work order details.

    Request Body:
        quantity: New quantity (optional)
        due_date: New due date (optional)
        priority: New priority (optional)
        notes: Updated notes (optional)
    """
    try:
        data = request.get_json()
        service = get_workorder_service()

        work_order = service.get_work_order(work_order_id)
        if not work_order:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404

        updated = service.update_work_order(
            work_order_id=work_order_id,
            quantity=data.get('quantity'),
            due_date=data.get('due_date'),
            priority=data.get('priority'),
            notes=data.get('notes')
        )

        if updated:
            return jsonify({
                'success': True,
                'work_order': updated.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Update failed'
            }), 500

    except Exception as e:
        logger.error(f"Error updating work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Work Order Status Transitions
# =============================================================================

@workorder_bp.route('/<work_order_id>/release', methods=['POST'])
def release_work_order(work_order_id: str):
    """Release a work order to production."""
    try:
        service = get_workorder_service()
        data = request.get_json() or {}

        work_order = service.release_work_order(
            work_order_id=work_order_id,
            user_id=data.get('user_id')
        )

        if work_order:
            return jsonify({
                'success': True,
                'work_order': work_order.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to release work order'
            }), 400

    except Exception as e:
        logger.error(f"Error releasing work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/start', methods=['POST'])
def start_work_order(work_order_id: str):
    """Start production on a work order."""
    try:
        service = get_workorder_service()
        data = request.get_json() or {}

        work_order = service.start_work_order(
            work_order_id=work_order_id,
            user_id=data.get('user_id')
        )

        if work_order:
            return jsonify({
                'success': True,
                'work_order': work_order.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start work order'
            }), 400

    except Exception as e:
        logger.error(f"Error starting work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/complete', methods=['POST'])
def complete_work_order(work_order_id: str):
    """
    Complete a work order.

    Request Body:
        quantity_good: Good parts produced (optional, uses current if not provided)
        quantity_scrap: Scrap parts (optional)
        user_id: Completing user (optional)
    """
    try:
        service = get_workorder_service()
        data = request.get_json() or {}

        work_order = service.complete_work_order(
            work_order_id=work_order_id,
            quantity_good=data.get('quantity_good'),
            quantity_scrap=data.get('quantity_scrap'),
            user_id=data.get('user_id')
        )

        if work_order:
            return jsonify({
                'success': True,
                'work_order': work_order.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to complete work order'
            }), 400

    except Exception as e:
        logger.error(f"Error completing work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/cancel', methods=['POST'])
def cancel_work_order(work_order_id: str):
    """
    Cancel a work order.

    Request Body:
        reason: Cancellation reason (optional)
        user_id: Cancelling user (optional)
    """
    try:
        service = get_workorder_service()
        data = request.get_json() or {}

        work_order = service.cancel_work_order(
            work_order_id=work_order_id,
            reason=data.get('reason', ''),
            user_id=data.get('user_id')
        )

        if work_order:
            return jsonify({
                'success': True,
                'work_order': work_order.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to cancel work order'
            }), 400

    except Exception as e:
        logger.error(f"Error cancelling work order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Operation Management
# =============================================================================

@workorder_bp.route('/<work_order_id>/operations', methods=['GET'])
def list_operations(work_order_id: str):
    """List all operations for a work order."""
    try:
        service = get_workorder_service()
        work_order = service.get_work_order(work_order_id)

        if not work_order:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404

        return jsonify({
            'success': True,
            'operations': [op.to_dict() for op in work_order.operations]
        })

    except Exception as e:
        logger.error(f"Error listing operations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/operations', methods=['POST'])
def add_operation(work_order_id: str):
    """
    Add an operation to a work order.

    Request Body:
        name: Operation name (required)
        work_center: Work center ID (required)
        machine_id: Machine ID (optional)
        setup_time_min: Setup time in minutes (default 0)
        run_time_min: Run time per piece in minutes (default 0)
        gcode_file: Associated G-code file (optional)
        tool_list: List of tool IDs (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('name') or not data.get('work_center'):
            return jsonify({
                'success': False,
                'error': 'Operation name and work_center required'
            }), 400

        service = get_workorder_service()

        operation = service.add_operation(
            work_order_id=work_order_id,
            operation_name=data['name'],
            work_center=data['work_center'],
            machine_id=data.get('machine_id'),
            setup_time_min=data.get('setup_time_min', 0),
            run_time_min=data.get('run_time_min', 0),
            gcode_file=data.get('gcode_file'),
            tool_list=data.get('tool_list')
        )

        if operation:
            return jsonify({
                'success': True,
                'operation': operation.to_dict()
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add operation'
            }), 400

    except Exception as e:
        logger.error(f"Error adding operation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/operations/<operation_id>/start', methods=['POST'])
def start_operation(work_order_id: str, operation_id: str):
    """
    Start an operation.

    Request Body:
        operator_id: Operator ID (optional)
        machine_id: Machine ID (optional, uses default if not provided)
    """
    try:
        service = get_workorder_service()
        data = request.get_json() or {}

        operation = service.start_operation(
            work_order_id=work_order_id,
            operation_id=operation_id,
            operator_id=data.get('operator_id'),
            machine_id=data.get('machine_id')
        )

        if operation:
            return jsonify({
                'success': True,
                'operation': operation.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start operation'
            }), 400

    except Exception as e:
        logger.error(f"Error starting operation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/operations/<operation_id>/complete', methods=['POST'])
def complete_operation(work_order_id: str, operation_id: str):
    """
    Complete an operation.

    Request Body:
        quantity_good: Good parts produced (required)
        quantity_scrap: Scrap parts (default 0)
        operator_id: Completing operator (optional)
        notes: Completion notes (optional)
    """
    try:
        data = request.get_json()

        if not data or 'quantity_good' not in data:
            return jsonify({
                'success': False,
                'error': 'quantity_good required'
            }), 400

        service = get_workorder_service()

        operation = service.complete_operation(
            work_order_id=work_order_id,
            operation_id=operation_id,
            quantity_good=data['quantity_good'],
            quantity_scrap=data.get('quantity_scrap', 0),
            operator_id=data.get('operator_id'),
            notes=data.get('notes')
        )

        if operation:
            return jsonify({
                'success': True,
                'operation': operation.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to complete operation'
            }), 400

    except Exception as e:
        logger.error(f"Error completing operation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Analytics and Reports
# =============================================================================

@workorder_bp.route('/<work_order_id>/progress', methods=['GET'])
def get_progress(work_order_id: str):
    """Get detailed progress for a work order."""
    try:
        service = get_workorder_service()
        progress = service.get_work_order_progress(work_order_id)

        if progress:
            return jsonify({
                'success': True,
                'progress': progress
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/alerts/due-date', methods=['GET'])
def get_due_date_alerts():
    """
    Get work orders approaching due date.

    Query Parameters:
        days_ahead: Days to look ahead (default 7)
    """
    try:
        service = get_workorder_service()
        days_ahead = request.args.get('days_ahead', 7, type=int)

        alerts = service.get_due_date_alerts(days_ahead=days_ahead)

        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })

    except Exception as e:
        logger.error(f"Error getting due date alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get work order analytics summary."""
    try:
        service = get_workorder_service()

        from services.workorder_service import WorkOrderStatus

        work_orders = list(service.work_orders.values())

        # Count by status
        by_status = {}
        for status in WorkOrderStatus:
            by_status[status.value] = len([wo for wo in work_orders if wo.status == status])

        # Calculate metrics
        completed = [wo for wo in work_orders if wo.status == WorkOrderStatus.COMPLETED]

        total_ordered = sum(wo.quantity_ordered for wo in work_orders)
        total_good = sum(wo.quantity_good for wo in completed)
        total_scrap = sum(wo.quantity_scrap for wo in completed)

        on_time = 0
        late = 0
        for wo in completed:
            if wo.due_date and wo.completed_at:
                if wo.completed_at <= wo.due_date:
                    on_time += 1
                else:
                    late += 1

        return jsonify({
            'success': True,
            'summary': {
                'total_work_orders': len(work_orders),
                'by_status': by_status,
                'total_quantity_ordered': total_ordered,
                'total_quantity_good': total_good,
                'total_quantity_scrap': total_scrap,
                'yield_rate': (total_good / (total_good + total_scrap) * 100) if (total_good + total_scrap) > 0 else 0,
                'on_time_completion': on_time,
                'late_completion': late,
                'on_time_rate': (on_time / (on_time + late) * 100) if (on_time + late) > 0 else 0
            }
        })

    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workorder_bp.route('/<work_order_id>/history', methods=['GET'])
def get_work_order_history(work_order_id: str):
    """Get event history for a work order."""
    try:
        service = get_workorder_service()
        work_order = service.get_work_order(work_order_id)

        if not work_order:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404

        return jsonify({
            'success': True,
            'history': [event.to_dict() for event in work_order.events]
        })

    except Exception as e:
        logger.error(f"Error getting work order history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
