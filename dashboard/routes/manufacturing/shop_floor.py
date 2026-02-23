"""
Shop Floor Display API - Real-time manufacturing visibility.

Provides:
- Work queue by work center
- Real-time machine status
- Active operations dashboard
- Production metrics
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime, timedelta

from models import get_db_session, WorkCenter, WorkOrder, WorkOrderOperation
from models.manufacturing import WorkCenterStatus, WorkOrderStatus
from services.manufacturing import WorkOrderService, OEEService

shop_floor_bp = Blueprint('shop_floor', __name__, url_prefix='/shop-floor')


# Dashboard Page Routes
@shop_floor_bp.route('', methods=['GET'])
@shop_floor_bp.route('/page', methods=['GET'])
def shop_floor_page():
    """Render shop floor dashboard page."""
    return render_template('pages/manufacturing/shop_floor.html')


@shop_floor_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """
    Get shop floor dashboard overview.

    Returns summary of all work centers, active work orders, and key metrics.
    """
    with get_db_session() as session:
        # Get all work centers
        work_centers = session.query(WorkCenter).all()

        # Get active work orders
        active_statuses = [
            WorkOrderStatus.RELEASED.value,
            WorkOrderStatus.IN_PROGRESS.value
        ]
        active_orders = session.query(WorkOrder).filter(
            WorkOrder.status.in_(active_statuses)
        ).all()

        # Build response
        centers_data = []
        for wc in work_centers:
            # Get current operation for this work center
            current_op = session.query(WorkOrderOperation).filter(
                WorkOrderOperation.work_center_id == wc.id,
                WorkOrderOperation.status == 'in_progress'
            ).first()

            centers_data.append({
                'id': str(wc.id),
                'code': wc.code,
                'name': wc.name,
                'type': wc.type,
                'status': wc.status,
                'current_operation': {
                    'work_order_number': current_op.work_order.work_order_number,
                    'operation_code': current_op.operation_code,
                    'progress_percent': (
                        (current_op.quantity_completed / current_op.quantity_scheduled * 100)
                        if current_op.quantity_scheduled else 0
                    )
                } if current_op else None
            })

        orders_data = [{
            'id': str(wo.id),
            'work_order_number': wo.work_order_number,
            'part_number': wo.part.part_number if wo.part else None,
            'part_name': wo.part.name if wo.part else None,
            'quantity_ordered': wo.quantity_ordered,
            'quantity_completed': wo.quantity_completed,
            'status': wo.status,
            'priority': wo.priority,
            'progress_percent': (
                (wo.quantity_completed / wo.quantity_ordered * 100)
                if wo.quantity_ordered else 0
            )
        } for wo in active_orders]

        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'work_centers': centers_data,
            'active_work_orders': orders_data,
            'summary': {
                'total_work_centers': len(work_centers),
                'running_work_centers': sum(
                    1 for wc in work_centers
                    if wc.status == WorkCenterStatus.IN_USE.value
                ),
                'active_work_orders': len(active_orders),
                'total_parts_scheduled': sum(wo.quantity_ordered for wo in active_orders),
                'total_parts_completed': sum(wo.quantity_completed for wo in active_orders)
            }
        })


@shop_floor_bp.route('/queue', methods=['GET'])
def get_work_queue():
    """
    Get work queue for all or specific work center.

    Query params:
    - work_center_id: Filter by work center
    - status: Filter by operation status
    """
    work_center_id = request.args.get('work_center_id')
    status_filter = request.args.get('status')

    with get_db_session() as session:
        wo_service = WorkOrderService(session)

        if work_center_id:
            queue = wo_service.get_work_queue(work_center_id)
        else:
            # Get queue for all work centers
            work_centers = session.query(WorkCenter).all()
            queue = []
            for wc in work_centers:
                wc_queue = wo_service.get_work_queue(str(wc.id))
                for item in wc_queue:
                    item['work_center_code'] = wc.code
                    item['work_center_name'] = wc.name
                queue.extend(wc_queue)

        # Apply status filter
        if status_filter:
            queue = [item for item in queue if item.get('status') == status_filter]

        # Sort by priority then scheduled start
        queue.sort(key=lambda x: (
            -x.get('priority', 0),
            x.get('scheduled_start') or ''
        ))

        return jsonify({
            'queue': queue,
            'total_items': len(queue)
        })


@shop_floor_bp.route('/queue/<work_center_id>', methods=['GET'])
def get_work_center_queue(work_center_id: str):
    """Get work queue for specific work center."""
    with get_db_session() as session:
        wo_service = WorkOrderService(session)
        queue = wo_service.get_work_queue(work_center_id)

        return jsonify({
            'work_center_id': work_center_id,
            'queue': queue,
            'total_items': len(queue)
        })


@shop_floor_bp.route('/active-operations', methods=['GET'])
def get_active_operations():
    """Get all currently active (in-progress) operations."""
    with get_db_session() as session:
        operations = session.query(WorkOrderOperation).filter(
            WorkOrderOperation.status == 'in_progress'
        ).all()

        result = []
        for op in operations:
            elapsed = None
            if op.actual_start:
                elapsed = (datetime.utcnow() - op.actual_start).total_seconds()

            result.append({
                'id': str(op.id),
                'work_order_number': op.work_order.work_order_number,
                'operation_sequence': op.operation_sequence,
                'operation_code': op.operation_code,
                'work_center': {
                    'id': str(op.work_center_id) if op.work_center_id else None,
                    'code': op.work_center.code if op.work_center else None,
                    'name': op.work_center.name if op.work_center else None
                },
                'part': {
                    'part_number': op.work_order.part.part_number if op.work_order.part else None,
                    'name': op.work_order.part.name if op.work_order.part else None
                },
                'quantity_scheduled': op.quantity_scheduled,
                'quantity_completed': op.quantity_completed,
                'quantity_scrapped': op.quantity_scrapped,
                'actual_start': op.actual_start.isoformat() if op.actual_start else None,
                'elapsed_seconds': elapsed,
                'progress_percent': (
                    (op.quantity_completed / op.quantity_scheduled * 100)
                    if op.quantity_scheduled else 0
                )
            })

        return jsonify({
            'active_operations': result,
            'count': len(result)
        })


@shop_floor_bp.route('/production-summary', methods=['GET'])
def get_production_summary():
    """
    Get production summary for current shift/day.

    Query params:
    - period: 'shift', 'day', 'week' (default: 'day')
    """
    period = request.args.get('period', 'day')

    # Calculate period start
    now = datetime.utcnow()
    if period == 'shift':
        # Assume 8-hour shifts starting at 6:00, 14:00, 22:00
        hour = now.hour
        if hour < 6:
            start = now.replace(hour=22, minute=0, second=0) - timedelta(days=1)
        elif hour < 14:
            start = now.replace(hour=6, minute=0, second=0)
        elif hour < 22:
            start = now.replace(hour=14, minute=0, second=0)
        else:
            start = now.replace(hour=22, minute=0, second=0)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0)
    else:  # day
        start = now.replace(hour=0, minute=0, second=0)

    with get_db_session() as session:
        # Get completed operations in period
        completed_ops = session.query(WorkOrderOperation).filter(
            WorkOrderOperation.status == 'complete',
            WorkOrderOperation.actual_end >= start
        ).all()

        # Get completed work orders in period
        completed_orders = session.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatus.COMPLETE.value,
            WorkOrder.actual_end >= start
        ).all()

        # Calculate metrics
        total_good = sum(op.quantity_completed for op in completed_ops)
        total_scrap = sum(op.quantity_scrapped for op in completed_ops)
        total_produced = total_good + total_scrap

        return jsonify({
            'period': period,
            'start': start.isoformat(),
            'end': now.isoformat(),
            'summary': {
                'operations_completed': len(completed_ops),
                'work_orders_completed': len(completed_orders),
                'total_parts_produced': total_produced,
                'good_parts': total_good,
                'scrapped_parts': total_scrap,
                'yield_percent': (
                    (total_good / total_produced * 100) if total_produced > 0 else 100
                )
            },
            'by_work_center': _summarize_by_work_center(completed_ops)
        })


def _summarize_by_work_center(operations):
    """Summarize operations by work center."""
    summary = {}
    for op in operations:
        wc_id = str(op.work_center_id) if op.work_center_id else 'unassigned'
        if wc_id not in summary:
            summary[wc_id] = {
                'work_center_code': op.work_center.code if op.work_center else 'Unassigned',
                'operations_completed': 0,
                'good_parts': 0,
                'scrapped_parts': 0
            }
        summary[wc_id]['operations_completed'] += 1
        summary[wc_id]['good_parts'] += op.quantity_completed
        summary[wc_id]['scrapped_parts'] += op.quantity_scrapped

    return list(summary.values())


@shop_floor_bp.route('/andon', methods=['GET'])
def get_andon_display():
    """
    Get Andon display data - visual status of all work centers.

    Returns color-coded status for shop floor displays.
    """
    with get_db_session() as session:
        work_centers = session.query(WorkCenter).order_by(WorkCenter.code).all()
        oee_service = OEEService(session)

        andon_data = []
        for wc in work_centers:
            # Determine color based on WorkCenterStatus enum values
            if wc.status == WorkCenterStatus.IN_USE.value:
                color = 'green'
            elif wc.status == WorkCenterStatus.AVAILABLE.value:
                color = 'yellow'
            elif wc.status in [WorkCenterStatus.OFFLINE.value, WorkCenterStatus.MAINTENANCE.value]:
                color = 'red'
            else:
                color = 'gray'

            # Get current shift OEE (with rollback on error to avoid transaction issues)
            oee = 0
            try:
                status = oee_service.get_work_center_status(str(wc.id))
                oee = status.get('current_shift_oee', {}).get('oee', 0)
            except Exception:
                # Rollback to clear any failed transaction state
                session.rollback()
                oee = 0

            # Get current operation
            try:
                current_op = session.query(WorkOrderOperation).filter(
                    WorkOrderOperation.work_center_id == wc.id,
                    WorkOrderOperation.status == 'in_progress'
                ).first()
            except Exception:
                session.rollback()
                current_op = None

            andon_data.append({
                'code': wc.code,
                'name': wc.name,
                'status': wc.status,
                'color': color,
                'oee': oee,
                'current_job': current_op.work_order.work_order_number if current_op else None,
                'progress': (
                    (current_op.quantity_completed / current_op.quantity_scheduled * 100)
                    if current_op and current_op.quantity_scheduled else 0
                )
            })

        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'work_centers': andon_data
        })
