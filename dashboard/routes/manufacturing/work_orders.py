"""
Work Order Management API - Create, manage, and track work orders.

Provides:
- Work order CRUD
- Work order lifecycle (release, start, complete, cancel)
- Operation management
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime

from models import get_db_session, WorkOrder, Part
from models.manufacturing import WorkOrderStatus
from services.manufacturing import WorkOrderService

work_orders_bp = Blueprint('work_orders', __name__, url_prefix='/work-orders')


# Dashboard Page Routes
@work_orders_bp.route('/page', methods=['GET'])
def work_orders_page():
    """Render work orders dashboard page."""
    return render_template('pages/manufacturing/mes_dashboard.html')


@work_orders_bp.route('/wip/page', methods=['GET'])
def wip_dashboard_page():
    """Render WIP & Order Tracking dashboard page."""
    return render_template('pages/manufacturing/wip_dashboard.html')


@work_orders_bp.route('', methods=['GET'])
def list_work_orders():
    """
    List work orders with optional filters.

    Query params:
    - status: Filter by status
    - part_id: Filter by part
    - priority: Filter by priority
    - limit: Max results (default 50)
    - offset: Pagination offset
    """
    status = request.args.get('status')
    part_id = request.args.get('part_id')
    priority = request.args.get('priority', type=int)
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    with get_db_session() as session:
        query = session.query(WorkOrder)

        if status:
            query = query.filter(WorkOrder.status == status)
        if part_id:
            query = query.filter(WorkOrder.part_id == part_id)
        if priority:
            query = query.filter(WorkOrder.priority == priority)

        total = query.count()
        work_orders = query.order_by(
            WorkOrder.priority.desc(),
            WorkOrder.scheduled_start
        ).offset(offset).limit(limit).all()

        return jsonify({
            'work_orders': [{
                'id': str(wo.id),
                'work_order_number': wo.work_order_number,
                'part': {
                    'id': str(wo.part_id),
                    'part_number': wo.part.part_number,
                    'name': wo.part.name
                } if wo.part else None,
                'quantity_ordered': wo.quantity_ordered,
                'quantity_completed': wo.quantity_completed,
                'status': wo.status,
                'priority': wo.priority,
                'scheduled_start': wo.scheduled_start.isoformat() if wo.scheduled_start else None,
                'scheduled_end': wo.scheduled_end.isoformat() if wo.scheduled_end else None,
                'actual_start': wo.actual_start.isoformat() if wo.actual_start else None,
                'actual_end': wo.actual_end.isoformat() if wo.actual_end else None,
                'created_at': wo.created_at.isoformat() if wo.created_at else None
            } for wo in work_orders],
            'total': total,
            'limit': limit,
            'offset': offset
        })


@work_orders_bp.route('', methods=['POST'])
def create_work_order():
    """
    Create a new work order.

    Request body:
    {
        "part_id": "uuid",
        "quantity": 10,
        "priority": 3,
        "scheduled_start": "2024-01-15T08:00:00",
        "notes": "Rush order"
    }
    """
    data = request.get_json()

    part_id = data.get('part_id')
    quantity = data.get('quantity', 1)
    priority = data.get('priority', 3)
    scheduled_start = data.get('scheduled_start')
    notes = data.get('notes')

    if not part_id:
        return jsonify({'error': 'part_id is required'}), 400

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.create_work_order(
                part_id=part_id,
                quantity=quantity,
                priority=priority,
                scheduled_start=datetime.fromisoformat(scheduled_start) if scheduled_start else None
            )

            if notes:
                work_order.notes = notes
                session.commit()

            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'message': 'Work order created successfully'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/<work_order_id>', methods=['GET'])
def get_work_order(work_order_id: str):
    """Get work order details including operations."""
    with get_db_session() as session:
        wo_service = WorkOrderService(session)
        details = wo_service.get_work_order_details(work_order_id)

        if not details:
            return jsonify({'error': 'Work order not found'}), 404

        return jsonify(details)


@work_orders_bp.route('/<work_order_id>/release', methods=['POST'])
def release_work_order(work_order_id: str):
    """Release work order for production."""
    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.release_work_order(work_order_id)
            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'message': 'Work order released'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/<work_order_id>/start', methods=['POST'])
def start_work_order(work_order_id: str):
    """Start work order (begin first operation)."""
    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.start_work_order(work_order_id)
            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'actual_start': work_order.actual_start.isoformat() if work_order.actual_start else None,
                'message': 'Work order started'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/<work_order_id>/complete', methods=['POST'])
def complete_work_order(work_order_id: str):
    """Complete work order."""
    data = request.get_json() or {}
    quantity_completed = data.get('quantity_completed')
    quantity_scrapped = data.get('quantity_scrapped', 0)

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.complete_work_order(
                work_order_id,
                quantity_completed=quantity_completed,
                quantity_scrapped=quantity_scrapped
            )
            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'quantity_completed': work_order.quantity_completed,
                'actual_end': work_order.actual_end.isoformat() if work_order.actual_end else None,
                'message': 'Work order completed'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/<work_order_id>/cancel', methods=['POST'])
def cancel_work_order(work_order_id: str):
    """Cancel work order."""
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelled by user')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.cancel_work_order(work_order_id, reason=reason)
            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'message': 'Work order cancelled'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/<work_order_id>/hold', methods=['POST'])
def hold_work_order(work_order_id: str):
    """Put work order on hold."""
    data = request.get_json() or {}
    reason = data.get('reason', 'On hold')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            work_order = wo_service.hold_work_order(work_order_id, reason=reason)
            return jsonify({
                'id': str(work_order.id),
                'work_order_number': work_order.work_order_number,
                'status': work_order.status,
                'message': 'Work order on hold'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


# Operation endpoints

@work_orders_bp.route('/operations/<operation_id>/start', methods=['POST'])
def start_operation(operation_id: str):
    """Start a work order operation."""
    data = request.get_json() or {}
    work_center_id = data.get('work_center_id')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            operation = wo_service.start_operation(operation_id, work_center_id)
            return jsonify({
                'id': str(operation.id),
                'operation_code': operation.operation_code,
                'status': operation.status,
                'actual_start': operation.actual_start.isoformat() if operation.actual_start else None,
                'message': 'Operation started'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/operations/<operation_id>/complete', methods=['POST'])
def complete_operation(operation_id: str):
    """
    Complete a work order operation.

    Request body:
    {
        "quantity_completed": 10,
        "quantity_scrapped": 0,
        "scrap_reason": "Optional reason"
    }
    """
    data = request.get_json() or {}
    quantity_completed = data.get('quantity_completed', 0)
    quantity_scrapped = data.get('quantity_scrapped', 0)
    scrap_reason = data.get('scrap_reason')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            operation = wo_service.complete_operation(
                operation_id,
                quantity_completed=quantity_completed,
                quantity_scrapped=quantity_scrapped,
                scrap_reason=scrap_reason
            )
            return jsonify({
                'id': str(operation.id),
                'operation_code': operation.operation_code,
                'status': operation.status,
                'quantity_completed': operation.quantity_completed,
                'quantity_scrapped': operation.quantity_scrapped,
                'actual_end': operation.actual_end.isoformat() if operation.actual_end else None,
                'message': 'Operation completed'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@work_orders_bp.route('/operations/<operation_id>/report-scrap', methods=['POST'])
def report_scrap(operation_id: str):
    """
    Report scrap during operation.

    Request body:
    {
        "quantity": 1,
        "reason_code": "DEFECT",
        "notes": "Surface defect"
    }
    """
    data = request.get_json()
    quantity = data.get('quantity', 1)
    reason_code = data.get('reason_code')
    notes = data.get('notes')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        try:
            operation = wo_service.report_scrap(
                operation_id,
                quantity=quantity,
                reason_code=reason_code,
                notes=notes
            )
            return jsonify({
                'id': str(operation.id),
                'quantity_scrapped': operation.quantity_scrapped,
                'message': f'Reported {quantity} scrapped parts'
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
