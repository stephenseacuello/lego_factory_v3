"""
LEGO Factory v3 - MES API
==========================
REST API endpoints for Manufacturing Execution System.

Provides endpoints for:
- Work order management
- Job scheduling and dispatch
- OEE metrics
- Labor tracking
"""

import logging
import uuid
from datetime import datetime, timedelta, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import Pydantic schemas for validation
from api.schemas import (
    WorkOrderCreate,
    WorkOrderUpdate,
    JobCreate,
    JobStatusUpdate,
    OperationCreate,
    LaborEntry,
    ScheduleJobRequest,
)
from api.utils.validation import validate_request, validate_path_param

logger = logging.getLogger(__name__)

mes_api_bp = Blueprint('mes_api', __name__, url_prefix='/api/mes')

# Demo data functions (used when demo_mode is enabled and database is unavailable)
def _get_demo_recipes():
    """Return demo recipe data."""
    return {
        'recipes': [
            {
                'recipe_id': 'RCP-001',
                'name': '2x4 Brick Standard',
                'version': '1.0',
                'product_id': 'brick_2x4',
                'status': 'approved',
                'operations': [
                    {'sequence': 10, 'name': 'Slice Model', 'type': 'design', 'duration_min': 5},
                    {'sequence': 20, 'name': 'FDM Print', 'type': 'printing_fdm', 'duration_min': 45},
                    {'sequence': 30, 'name': 'Quality Check', 'type': 'inspection', 'duration_min': 2},
                ],
                'parameters': {'infill': 20, 'layer_height': 0.2, 'material': 'PLA'},
            },
            {
                'recipe_id': 'RCP-002',
                'name': '2x2 Brick Fast',
                'version': '1.1',
                'product_id': 'brick_2x2',
                'status': 'approved',
            },
        ],
        'count': 2,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Work Orders
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/work-orders', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def list_work_orders():
    """
    List work orders with optional filtering.

    Query params:
    - status: Filter by status (draft, planned, released, in_progress, completed, cancelled)
    - product_id: Filter by product
    - customer_id: Filter by customer
    - due_before: Filter by due date (ISO format)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)

            due_before = None
            if request.args.get('due_before'):
                due_before = datetime.fromisoformat(request.args['due_before'])

            work_orders = service.get_work_orders(
                status=request.args.get('status'),
                product_id=request.args.get('product_id'),
                customer_id=request.args.get('customer_id'),
                due_before=due_before,
                limit=int(request.args.get('limit', 100)),
                offset=int(request.args.get('offset', 0)),
            )

            return jsonify({
                'work_orders': work_orders,
                'count': len(work_orders),
            })
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_work_orders
            data = get_demo_work_orders()
            return jsonify({**data, 'demo': True})

        logger.error(f"MES service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'The Manufacturing Execution System is not available. Please check system status.'
        }), 503


@mes_api_bp.route('/work-orders', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
@validate_request(WorkOrderCreate)
def create_work_order(validated_data: WorkOrderCreate):
    """
    Create a new work order.

    Request body (validated by Pydantic):
        {
            "product_id": "string (required, 1-100 chars)",
            "quantity_ordered": "integer (default: 1, min: 1)",
            "description": "string (optional, max 1000 chars)",
            "priority": "integer (1-10, default: 5)",
            "due_date": "datetime (optional, ISO format)",
            "planned_start": "datetime (optional)",
            "planned_end": "datetime (optional)",
            "customer_id": "string (optional)",
            "sales_order_id": "string (optional)",
            "recipe_id": "string (optional)"
        }

    Returns:
        201: Created work order
        400: Validation error with field details
        500: Server error
    """
    # Convert validated Pydantic model to dict
    data = validated_data.model_dump(exclude_none=True)

    # Try database first
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.create_work_order(data)
            return jsonify(work_order), 201

    except Exception as e:
        logger.error(f"MES service unavailable: {e}", exc_info=True)

        # In demo mode, create a fake work order
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            import uuid
            from datetime import datetime, timedelta
            wo_id = f"WO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            demo_wo = {
                'work_order_id': wo_id,
                'product_id': data.get('product_id', 'DEMO-PRODUCT'),
                'description': data.get('description', 'Demo work order'),
                'quantity_ordered': data.get('quantity_ordered', 100),
                'quantity_completed': 0,
                'status': 'draft',
                'priority': data.get('priority', 5),
                'due_date': data.get('due_date', (datetime.now() + timedelta(days=7)).isoformat()),
                'created_at': datetime.now().isoformat(),
                'demo': True
            }
            return jsonify(demo_wo), 201

        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not create work order. Please check system status.'
        }), 503


@mes_api_bp.route('/work-orders/<work_order_id>', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def get_work_order(work_order_id: str):
    """Get a specific work order with its operations and jobs."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService
        from models.mes.work_orders import WorkOrder

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.get_work_order(work_order_id)

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            # Get operations and jobs
            wo = session.query(WorkOrder).filter(
                WorkOrder.work_order_id == work_order_id
            ).first()

            operations = [op.to_dict() for op in wo.operations] if wo else []
            jobs = [j.to_dict() for j in wo.jobs] if wo else []

            work_order['operations'] = operations
            work_order['jobs'] = jobs

            return jsonify(work_order)

    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_work_order_detail
            data = get_demo_work_order_detail(work_order_id)
            return jsonify({**data, 'demo': True})

        logger.error(f"Error getting work order: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not retrieve work order details.'
        }), 503


@mes_api_bp.route('/work-orders/<work_order_id>', methods=['PUT'])
@jwt_required()
@validate_path_param('work_order_id', pattern=r'^WO-\d{8}-[A-Z0-9]+$|^[a-zA-Z0-9_-]+$', max_length=50)
@validate_request(WorkOrderUpdate)
def update_work_order(validated_data: WorkOrderUpdate, work_order_id: str):
    """
    Update a work order.

    Path parameters:
        - work_order_id: Work order identifier

    Request body (validated by Pydantic):
        {
            "description": "string (optional)",
            "quantity_ordered": "integer (optional, min: 1)",
            "priority": "integer (optional, 1-10)",
            "due_date": "datetime (optional)",
            "planned_start": "datetime (optional)",
            "planned_end": "datetime (optional)",
            "customer_id": "string (optional)",
            "recipe_id": "string (optional)"
        }

    Returns:
        200: Updated work order
        400: Validation error
        404: Work order not found
        503: Database not available
    """
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    # Only include non-None values for update
    update_data = validated_data.model_dump(exclude_none=True)
    if not update_data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        from services.mes.work_order_service import WorkOrderService

        service = WorkOrderService(session)
        work_order = service.update_work_order(work_order_id, update_data)
        session.commit()

        if not work_order:
            return jsonify({'error': 'Work order not found'}), 404

        return jsonify(work_order)
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating work order: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@mes_api_bp.route('/work-orders/<work_order_id>/release', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def release_work_order(work_order_id: str):
    """Release a work order for production."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json(silent=True) or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.release_work_order(
                work_order_id,
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except Exception as e:
        logger.error(f"Error releasing work order: {e}", exc_info=True)
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'released',
                'message': 'Work order released (demo mode)',
                'demo': True
            })

        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/start', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def start_work_order(work_order_id: str):
    """Start a work order."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json() or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.start_work_order(
                work_order_id,
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'in_progress',
                'actual_start': datetime.utcnow().isoformat(),
                'message': 'Work order started (demo mode)',
                'demo': True
            })

        logger.error(f"Error starting work order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/complete', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def complete_work_order(work_order_id: str):
    """Complete a work order."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json() or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.complete_work_order(
                work_order_id,
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'completed',
                'actual_end': datetime.utcnow().isoformat(),
                'message': 'Work order completed (demo mode)',
                'demo': True
            })

        logger.error(f"Error completing work order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/hold', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def hold_work_order(work_order_id: str):
    """
    Put a work order on hold.

    Request body:
        {
            "reason": "string (optional) - reason for putting on hold",
            "user_id": "string (optional)"
        }

    Returns:
        200: Updated work order
        400: Invalid state transition
        404: Work order not found
        503: Database not available
    """
    data = request.get_json() or {}

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.hold_work_order(
                work_order_id,
                reason=data.get('reason'),
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'on_hold',
                'metadata': {'hold_reason': data.get('reason')},
                'message': 'Work order put on hold (demo mode)',
                'demo': True
            })

        logger.error(f"Error holding work order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/resume', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def resume_work_order(work_order_id: str):
    """
    Resume a held work order.

    Request body:
        {
            "user_id": "string (optional)"
        }

    Returns:
        200: Updated work order (returns to previous status)
        400: Invalid state transition
        404: Work order not found
        503: Database not available
    """
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json() or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.resume_work_order(
                work_order_id,
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'in_progress',
                'message': 'Work order resumed (demo mode)',
                'demo': True
            })

        logger.error(f"Error resuming work order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/cancel', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def cancel_work_order(work_order_id: str):
    """
    Cancel a work order.

    Request body:
        {
            "reason": "string (optional) - cancellation reason",
            "user_id": "string (optional)"
        }

    Returns:
        200: Updated work order
        400: Invalid state transition (cannot cancel completed)
        404: Work order not found
        503: Database not available
    """
    data = request.get_json() or {}

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            work_order = service.cancel_work_order(
                work_order_id,
                reason=data.get('reason'),
                user_id=data.get('user_id', 'system')
            )

            if not work_order:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(work_order)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'work_order_id': work_order_id,
                'status': 'cancelled',
                'metadata': {'cancel_reason': data.get('reason')},
                'message': 'Work order cancelled (demo mode)',
                'demo': True
            })

        logger.error(f"Error cancelling work order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/<work_order_id>/operations', methods=['POST'])
@jwt_required()
@validate_path_param('work_order_id', pattern=r'^WO-\d{8}-[A-Z0-9]+$|^[a-zA-Z0-9_-]+$', max_length=50)
@validate_request(OperationCreate)
def add_operation(validated_data: OperationCreate, work_order_id: str):
    """
    Add an operation to a work order.

    Path parameters:
        - work_order_id: Work order identifier

    Request body (validated by Pydantic):
        {
            "name": "string (required, 1-200 chars)",
            "sequence": "integer (required, 1-9999)",
            "operation_type": "design|setup|printing_fdm|...",
            "description": "string (optional)",
            "machine_id": "string (optional)",
            "duration_planned": "integer (optional, minutes)",
            "parameters": "object (optional)"
        }

    Returns:
        201: Created operation
        400: Validation error
        404: Work order not found
        503: Database not available
    """
    data = validated_data.model_dump(exclude_none=True)

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            operation = service.add_operation(work_order_id, data)

            if not operation:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(operation), 201

    except Exception as e:
        logger.error(f"Error adding operation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/operations/<operation_id>/start', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def start_operation(operation_id: str):
    """
    Start an operation.

    Request body:
        {
            "user_id": "string (optional)"
        }

    Returns:
        200: Updated operation
        404: Operation not found
        503: Database not available
    """
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json() or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            operation = service.start_operation(
                operation_id,
                user_id=data.get('user_id', 'system')
            )

            if not operation:
                return jsonify({'error': 'Operation not found'}), 404

            return jsonify(operation)

    except Exception as e:
        logger.error(f"Error starting operation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/operations/<operation_id>/complete', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def complete_operation(operation_id: str):
    """
    Complete an operation.

    Request body:
        {
            "user_id": "string (optional)",
            "quantity_completed": "integer (optional)",
            "quantity_defective": "integer (optional)"
        }

    Returns:
        200: Updated operation
        404: Operation not found
        503: Database not available
    """
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        data = request.get_json() or {}

        with get_db_session() as session:
            service = WorkOrderService(session)
            operation = service.complete_operation(
                operation_id,
                user_id=data.get('user_id', 'system'),
                quantity_completed=data.get('quantity_completed'),
                quantity_defective=data.get('quantity_defective')
            )

            if not operation:
                return jsonify({'error': 'Operation not found'}), 404

            return jsonify(operation)

    except Exception as e:
        logger.error(f"Error completing operation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/operations/<operation_id>/record-time', methods=['POST'])
@jwt_required()
def record_operation_time(operation_id: str):
    """
    Record time spent on an operation.

    Request body:
        {
            "duration_minutes": "integer (required)",
            "user_id": "string (optional)",
            "notes": "string (optional)"
        }

    Returns:
        200: Updated operation
        400: Missing duration_minutes
        404: Operation not found
        503: Database not available
    """
    data = request.get_json() or {}
    if not data.get('duration_minutes'):
        return jsonify({'error': 'duration_minutes is required'}), 400

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            operation = service.record_operation_time(
                operation_id,
                duration_minutes=data['duration_minutes'],
                user_id=data.get('user_id', 'system'),
                notes=data.get('notes')
            )

            if not operation:
                return jsonify({'error': 'Operation not found'}), 404

            return jsonify(operation)

    except Exception as e:
        logger.error(f"Error recording operation time: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Bulk Operations
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/work-orders/bulk/release', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def bulk_release_work_orders():
    """
    Release multiple work orders at once.

    Request body:
        {
            "work_order_ids": ["WO-001", "WO-002", ...],
            "user_id": "string (optional)"
        }

    Returns:
        200: Summary of results
    """
    data = request.get_json() or {}
    work_order_ids = data.get('work_order_ids', [])

    if not work_order_ids:
        return jsonify({'error': 'work_order_ids is required'}), 400

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            user_id = data.get('user_id', 'system')

            results = {'success': [], 'failed': []}

            for wo_id in work_order_ids:
                try:
                    wo = service.release_work_order(wo_id, user_id=user_id)
                    if wo:
                        results['success'].append(wo_id)
                    else:
                        results['failed'].append({'id': wo_id, 'error': 'Not found'})
                except ValueError as e:
                    results['failed'].append({'id': wo_id, 'error': str(e)})

            return jsonify({
                'message': f"Released {len(results['success'])} work orders",
                'results': results
            })

    except Exception as e:
        logger.error(f"Error bulk releasing work orders: {e}")
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'message': f"Released {len(work_order_ids)} work orders (demo mode)",
                'results': {'success': work_order_ids, 'failed': []},
                'demo': True
            })
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/bulk/hold', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def bulk_hold_work_orders():
    """
    Put multiple work orders on hold at once.

    Request body:
        {
            "work_order_ids": ["WO-001", "WO-002", ...],
            "reason": "string (optional)",
            "user_id": "string (optional)"
        }

    Returns:
        200: Summary of results
    """
    data = request.get_json() or {}
    work_order_ids = data.get('work_order_ids', [])

    if not work_order_ids:
        return jsonify({'error': 'work_order_ids is required'}), 400

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            user_id = data.get('user_id', 'system')
            reason = data.get('reason')

            results = {'success': [], 'failed': []}

            for wo_id in work_order_ids:
                try:
                    wo = service.hold_work_order(wo_id, reason=reason, user_id=user_id)
                    if wo:
                        results['success'].append(wo_id)
                    else:
                        results['failed'].append({'id': wo_id, 'error': 'Not found'})
                except ValueError as e:
                    results['failed'].append({'id': wo_id, 'error': str(e)})

            return jsonify({
                'message': f"Placed {len(results['success'])} work orders on hold",
                'results': results
            })

    except Exception as e:
        logger.error(f"Error bulk holding work orders: {e}")
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'message': f"Placed {len(work_order_ids)} work orders on hold (demo mode)",
                'results': {'success': work_order_ids, 'failed': []},
                'demo': True
            })
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/bulk/cancel', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def bulk_cancel_work_orders():
    """
    Cancel multiple work orders at once.

    Request body:
        {
            "work_order_ids": ["WO-001", "WO-002", ...],
            "reason": "string (optional)",
            "user_id": "string (optional)"
        }

    Returns:
        200: Summary of results
    """
    data = request.get_json() or {}
    work_order_ids = data.get('work_order_ids', [])

    if not work_order_ids:
        return jsonify({'error': 'work_order_ids is required'}), 400

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)
            user_id = data.get('user_id', 'system')
            reason = data.get('reason')

            results = {'success': [], 'failed': []}

            for wo_id in work_order_ids:
                try:
                    wo = service.cancel_work_order(wo_id, reason=reason, user_id=user_id)
                    if wo:
                        results['success'].append(wo_id)
                    else:
                        results['failed'].append({'id': wo_id, 'error': 'Not found'})
                except ValueError as e:
                    results['failed'].append({'id': wo_id, 'error': str(e)})

            return jsonify({
                'message': f"Cancelled {len(results['success'])} work orders",
                'results': results
            })

    except Exception as e:
        logger.error(f"Error bulk cancelling work orders: {e}")
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'message': f"Cancelled {len(work_order_ids)} work orders (demo mode)",
                'results': {'success': work_order_ids, 'failed': []},
                'demo': True
            })
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/work-orders/export', methods=['GET'])
@jwt_required(optional=True)
def export_work_orders():
    """
    Export work orders to CSV.

    Query params:
        - status: Filter by status
        - ids: Comma-separated list of specific work order IDs
        - format: Export format (csv, json) - default csv

    Returns:
        CSV file or JSON array
    """
    import csv
    import io
    from flask import Response

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)

            # Get filter params
            status = request.args.get('status')
            ids_param = request.args.get('ids')
            export_format = request.args.get('format', 'csv')

            # Get work orders
            if ids_param:
                work_order_ids = ids_param.split(',')
                work_orders = []
                for wo_id in work_order_ids:
                    wo = service.get_work_order(wo_id.strip())
                    if wo:
                        work_orders.append(wo)
            else:
                work_orders = service.get_work_orders(status=status, limit=1000)

            if export_format == 'json':
                return jsonify({'work_orders': work_orders, 'count': len(work_orders)})

            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Header row
            writer.writerow([
                'Work Order ID', 'Product', 'Description', 'Quantity Ordered',
                'Quantity Completed', 'Status', 'Priority', 'Due Date',
                'Created At', 'Customer ID'
            ])

            # Data rows
            for wo in work_orders:
                writer.writerow([
                    wo.get('work_order_id', ''),
                    wo.get('product_id', ''),
                    wo.get('description', ''),
                    wo.get('quantity_ordered', 0),
                    wo.get('quantity_completed', 0),
                    wo.get('status', ''),
                    wo.get('priority', ''),
                    wo.get('due_date', ''),
                    wo.get('created_at', ''),
                    wo.get('customer_id', ''),
                ])

            output.seek(0)

            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=work_orders_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
                }
            )

    except Exception as e:
        logger.error(f"Error exporting work orders: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Jobs
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/jobs', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated access for demo mode
def list_jobs():
    """
    List jobs with optional filtering.

    Query params:
    - machine_id: Filter by machine
    - status: Filter by status
    - work_order_id: Filter by work order
    - limit: Max results
    - scheduled_only: Only return jobs with valid scheduled times (for Gantt)
    - date_from: Filter jobs scheduled on or after this date (ISO format)
    - date_to: Filter jobs scheduled on or before this date (ISO format)
    """
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService

        with get_db_session() as session:
            service = WorkOrderService(session)

            # Parse date filters
            date_from = None
            date_to = None
            if request.args.get('date_from'):
                date_from = datetime.fromisoformat(request.args['date_from'].replace('Z', '+00:00'))
            if request.args.get('date_to'):
                date_to = datetime.fromisoformat(request.args['date_to'].replace('Z', '+00:00'))

            # Parse scheduled_only flag
            scheduled_only = request.args.get('scheduled_only', 'false').lower() == 'true'

            jobs = service.get_jobs(
                machine_id=request.args.get('machine_id'),
                status=request.args.get('status'),
                work_order_id=request.args.get('work_order_id'),
                limit=int(request.args.get('limit', 100)),
                scheduled_only=scheduled_only,
                date_from=date_from,
                date_to=date_to,
            )

            return jsonify({
                'jobs': jobs,
                'count': len(jobs),
            })
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_jobs
            data = get_demo_jobs()
            return jsonify({**data, 'demo': True})

        logger.error(f"MES service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'The Manufacturing Execution System is not available. Please check system status.'
        }), 503


@mes_api_bp.route('/jobs', methods=['POST'])
@jwt_required()
@validate_request(JobCreate)
def create_job(validated_data: JobCreate):
    """
    Create a job for a work order.

    Request body (validated by Pydantic):
        {
            "work_order_id": "string (required)",
            "machine_id": "string (optional)",
            "operation_id": "string (optional)",
            "quantity_planned": "integer (optional, min: 1)",
            "priority": "integer (optional, 1-10)",
            "scheduled_start": "datetime (optional)",
            "scheduled_end": "datetime (optional)",
            "parameters": "object (optional)"
        }

    Returns:
        201: Created job
        400: Validation error
        404: Work order not found
        503: Database not available
    """
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = validated_data.model_dump(exclude_none=True)
    work_order_id = data.pop('work_order_id')

    try:
        from services.mes.work_order_service import WorkOrderService

        service = WorkOrderService(session)
        job = service.create_job(work_order_id, data)
        session.commit()

        if not job:
            return jsonify({'error': 'Work order not found'}), 404

        return jsonify(job), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating job: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@mes_api_bp.route('/jobs/<job_id>/status', methods=['PUT'])
@jwt_required()
@validate_path_param('job_id', pattern=r'^JOB-\d{8}-[A-Z0-9]+$|^[a-zA-Z0-9_-]+$', max_length=50)
@validate_request(JobStatusUpdate)
def update_job_status(validated_data: JobStatusUpdate, job_id: str):
    """
    Update job status.

    Path parameters:
        - job_id: Job identifier

    Request body (validated by Pydantic):
        {
            "status": "pending|queued|running|paused|completed|failed|cancelled (required)",
            "user_id": "string (optional)",
            "failure_reason": "string (required if status is 'failed')",
            "quantity_completed": "integer (optional, min: 0)",
            "quantity_defective": "integer (optional, min: 0)"
        }

    Returns:
        200: Updated job
        400: Validation error
        404: Job not found
        503: Database not available
    """
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    try:
        from services.mes.work_order_service import WorkOrderService

        service = WorkOrderService(session)
        job = service.update_job_status(
            job_id,
            validated_data.status.value,
            user_id=validated_data.user_id or 'system'
        )
        session.commit()

        if not job:
            return jsonify({'error': 'Job not found'}), 404

        return jsonify(job)
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating job status: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@mes_api_bp.route('/jobs/<job_id>/reschedule', methods=['POST'])
@jwt_required(optional=True)
def reschedule_job(job_id: str):
    """
    Reschedule a job to a different machine and/or time.

    Request body:
        {
            "machine_id": "string (optional) - target machine",
            "scheduled_start": "datetime (optional) - new start time",
            "scheduled_end": "datetime (optional) - new end time",
            "user_id": "string (optional)"
        }

    Returns:
        200: Updated job with conflict info
        400: Invalid request or conflict detected
        404: Job not found
        503: Database not available
    """
    data = request.get_json() or {}

    # Detect conflicts
    conflicts = []
    new_machine_id = data.get('machine_id')
    new_start = data.get('scheduled_start')
    new_end = data.get('scheduled_end')

    try:
        from config.database import get_db_session
        from models.mes.work_orders import Job

        with get_db_session() as session:
            # Find the job
            job = session.query(Job).filter(Job.job_id == job_id).first()

            if not job:
                return jsonify({'error': 'Job not found'}), 404

            # Parse times
            if new_start:
                new_start_dt = datetime.fromisoformat(new_start.replace('Z', '+00:00'))
            else:
                new_start_dt = job.scheduled_start

            if new_end:
                new_end_dt = datetime.fromisoformat(new_end.replace('Z', '+00:00'))
            else:
                new_end_dt = job.scheduled_end

            target_machine = new_machine_id or job.machine_id

            # Validate eligible machines if changing machine
            if new_machine_id and new_machine_id != job.machine_id:
                eligible = []
                if job.runtime_data:
                    eligible = job.runtime_data.get('eligible_machines', [])
                if eligible and new_machine_id not in eligible:
                    return jsonify({
                        'error': f'Machine {new_machine_id} is not eligible for this operation. Eligible: {eligible}'
                    }), 400

            # Check for conflicts on target machine
            if target_machine and new_start_dt and new_end_dt:
                overlapping_jobs = session.query(Job).filter(
                    Job.machine_id == target_machine,
                    Job.job_id != job_id,
                    Job.is_deleted == False,
                    Job.scheduled_start < new_end_dt,
                    Job.scheduled_end > new_start_dt
                ).all()

                for oj in overlapping_jobs:
                    conflicts.append({
                        'job_id': oj.job_id,
                        'work_order_id': oj.work_order.work_order_id if oj.work_order else None,
                        'scheduled_start': oj.scheduled_start.isoformat() if oj.scheduled_start else None,
                        'scheduled_end': oj.scheduled_end.isoformat() if oj.scheduled_end else None,
                        'type': 'machine_overlap'
                    })

            # Check due date violation
            if hasattr(job, 'work_order') and job.work_order and job.work_order.due_date:
                if new_end_dt:
                    # Normalize due_date to datetime for comparison (handles both date and datetime)
                    due_date = job.work_order.due_date
                    if isinstance(due_date, datetime):
                        due_date_dt = due_date
                    else:
                        # It's a date, convert to datetime at end of day
                        due_date_dt = datetime.combine(due_date, datetime.max.time())
                    if new_end_dt > due_date_dt:
                        conflicts.append({
                            'type': 'due_date_violation',
                            'due_date': job.work_order.due_date.isoformat(),
                            'scheduled_end': new_end_dt.isoformat()
                        })

            # If conflicts exist and force not specified, return warning
            if conflicts and not data.get('force'):
                return jsonify({
                    'warning': 'Conflicts detected',
                    'conflicts': conflicts,
                    'message': 'Set force=true to proceed anyway'
                }), 409

            # Apply changes
            if new_machine_id:
                job.machine_id = new_machine_id
            if new_start:
                job.scheduled_start = new_start_dt
            if new_end:
                job.scheduled_end = new_end_dt

            job.updated_at = datetime.utcnow()
            job.updated_by = data.get('user_id', 'system')

            session.flush()

            # Emit WebSocket event
            try:
                from services.websocket.socket_service import emit_to_namespace
                emit_to_namespace('job_rescheduled', {
                    'job_id': job_id,
                    'machine_id': job.machine_id,
                    'scheduled_start': job.scheduled_start.isoformat() if job.scheduled_start else None,
                    'scheduled_end': job.scheduled_end.isoformat() if job.scheduled_end else None,
                }, namespace='/dashboard')
            except Exception:
                pass

            logger.info(f"Job {job_id} rescheduled to machine {job.machine_id}")

            return jsonify({
                'job_id': job.job_id,
                'machine_id': job.machine_id,
                'scheduled_start': job.scheduled_start.isoformat() if job.scheduled_start else None,
                'scheduled_end': job.scheduled_end.isoformat() if job.scheduled_end else None,
                'conflicts_resolved': len(conflicts) if conflicts else 0,
                'message': 'Job rescheduled successfully'
            })

    except Exception as e:
        logger.error(f"Error rescheduling job: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Scheduling
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/schedule', methods=['POST'])
@jwt_required()
def schedule_jobs():
    """
    Schedule jobs using CP-SAT or heuristic solver.

    JSON body:
    - jobs: List of jobs to schedule
    - machines: List of available machines
    - horizon_hours: Planning horizon (default 24)
    - objective: Optimization objective (makespan, due_date, setup_time)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        from services.mes.scheduling_service import (
            SchedulingService, ScheduleJob, Machine
        )

        # Parse jobs
        jobs = []
        for j in data.get('jobs', []):
            due_date = None
            if j.get('due_date'):
                due_date = datetime.fromisoformat(j['due_date'])

            jobs.append(ScheduleJob(
                job_id=j['job_id'],
                work_order_id=j.get('work_order_id', ''),
                duration_minutes=j.get('duration_minutes', 60),
                machine_id=j.get('machine_id'),
                eligible_machines=j.get('eligible_machines', []),
                priority=j.get('priority', 5),
                due_date=due_date,
                dependencies=j.get('dependencies', []),
                setup_time=j.get('setup_time', 0),
            ))

        # Parse machines
        machines = []
        for m in data.get('machines', []):
            machines.append(Machine(
                machine_id=m['machine_id'],
                name=m.get('name', m['machine_id']),
                capabilities=m.get('capabilities', []),
                efficiency=m.get('efficiency', 1.0),
            ))

        service = SchedulingService()
        result = service.schedule_jobs(
            jobs=jobs,
            machines=machines,
            horizon_hours=data.get('horizon_hours', 24),
            objective=data.get('objective', 'makespan'),
        )

        return jsonify({
            'scheduled_jobs': [{
                'job_id': j.job_id,
                'machine_id': j.machine_id,
                'start_time': j.start_time.isoformat(),
                'end_time': j.end_time.isoformat(),
                'setup_time': j.setup_time,
            } for j in result.scheduled_jobs],
            'makespan_minutes': result.makespan_minutes,
            'total_setup_time': result.total_setup_time,
            'utilization': result.utilization,
            'unscheduled_jobs': result.unscheduled_jobs,
            'solver_status': result.solver_status,
        })
    except Exception as e:
        logger.error(f"Error scheduling jobs: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/dispatch/<machine_id>', methods=['GET'])
@jwt_required()
def get_dispatch_queue(machine_id: str):
    """Get the dispatch queue for a machine."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_dispatch_queue
            data = get_demo_dispatch_queue(machine_id)
            return jsonify({**data, 'demo': True})

        logger.error("MES service unavailable")
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'The Manufacturing Execution System is not available. Please check system status.'
        }), 503

    try:
        from services.mes.scheduling_service import SchedulingService

        service = SchedulingService(session)
        queue = service.get_dispatch_queue(machine_id)

        return jsonify({
            'machine_id': machine_id,
            'queue': queue,
            'count': len(queue),
        })
    except Exception as e:
        logger.error(f"Error getting dispatch queue: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# OEE Metrics
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/oee', methods=['GET'])
@jwt_required()
def get_oee():
    """
    Get OEE metrics.

    Query params:
    - machine_id: Specific machine (optional)
    - start_date: Period start (ISO format)
    - end_date: Period end (ISO format)
    """
    machine_id = request.args.get('machine_id')

    try:
        from config.database import get_db_session
        from services.mes.oee_service import OEEService

        with get_db_session() as session:
            start_date = datetime.fromisoformat(
                request.args.get('start_date', (datetime.utcnow() - timedelta(days=7)).isoformat())
            )
            end_date = datetime.fromisoformat(
                request.args.get('end_date', datetime.utcnow().isoformat())
            )

            service = OEEService(session)
            oee = service.calculate_oee(
                machine_id=machine_id,
                start_date=start_date,
                end_date=end_date,
            )

            return jsonify(oee)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_oee
            data = get_demo_oee(machine_id)
            return jsonify({**data, 'demo': True})

        logger.error(f"MES service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'The Manufacturing Execution System is not available. Please check system status.'
        }), 503


@mes_api_bp.route('/oee/summary', methods=['GET'])
@jwt_required()
def get_oee_summary():
    """Get OEE summary for all machines."""
    try:
        from config.database import get_db_session
        from services.mes.oee_service import OEEService

        with get_db_session() as session:
            service = OEEService(session)
            summary = service.get_oee_summary()
            return jsonify(summary)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_oee_summary
            data = get_demo_oee_summary()
            return jsonify({**data, 'demo': True})

        logger.error(f"MES service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'The Manufacturing Execution System is not available. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Labor
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/labor/workers', methods=['GET'])
@jwt_required()
def list_workers():
    """List workers."""
    return jsonify({
        'workers': [
            {'id': 'W001', 'name': 'John Smith', 'role': 'Operator', 'skills': ['3d_printing', 'assembly'], 'status': 'active'},
            {'id': 'W002', 'name': 'Jane Doe', 'role': 'Lead Technician', 'skills': ['cnc', '3d_printing', 'maintenance'], 'status': 'active'},
            {'id': 'W003', 'name': 'Bob Wilson', 'role': 'Operator', 'skills': ['assembly', 'packaging'], 'status': 'break'},
        ],
        'count': 3,
    })


@mes_api_bp.route('/labor/time-entries', methods=['GET'])
@jwt_required()
def list_time_entries():
    """List labor time entries."""
    return jsonify({
        'time_entries': [
            {'id': 'TE001', 'worker_id': 'W001', 'job_id': 'JOB-20240115-001', 'start': '2024-01-15T08:00:00', 'end': '2024-01-15T12:00:00', 'hours': 4.0},
            {'id': 'TE002', 'worker_id': 'W002', 'job_id': 'JOB-20240115-002', 'start': '2024-01-15T08:30:00', 'end': '2024-01-15T11:30:00', 'hours': 3.0},
        ],
        'count': 2,
    })


@mes_api_bp.route('/labor/time-entries', methods=['POST'])
@jwt_required()
@validate_request(LaborEntry)
def create_time_entry(validated_data: LaborEntry):
    """
    Create a labor time entry.

    Request body (validated by Pydantic):
        {
            "worker_id": "string (required)",
            "job_id": "string (optional)",
            "work_order_id": "string (optional)",
            "operation_id": "string (optional)",
            "start_time": "datetime (required)",
            "end_time": "datetime (optional)",
            "labor_type": "direct|indirect|setup|maintenance|training",
            "notes": "string (optional)"
        }

    Note: At least one of job_id, work_order_id, or operation_id should be specified.

    Returns:
        201: Created time entry
        400: Validation error
    """
    data = validated_data.model_dump(exclude_none=True)

    # Format times for response
    start_time = data.get('start_time')
    if start_time and hasattr(start_time, 'isoformat'):
        start_time = start_time.isoformat()

    end_time = data.get('end_time')
    if end_time and hasattr(end_time, 'isoformat'):
        end_time = end_time.isoformat()

    return jsonify({
        'id': f"TE{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        'worker_id': data.get('worker_id'),
        'job_id': data.get('job_id'),
        'work_order_id': data.get('work_order_id'),
        'operation_id': data.get('operation_id'),
        'start': start_time,
        'end': end_time,
        'labor_type': data.get('labor_type', 'direct'),
        'notes': data.get('notes'),
        'status': 'recorded',
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data (when database unavailable)
# ─────────────────────────────────────────────────────────────────────────────

def _demo_work_orders():
    """Return demo work orders."""
    return jsonify({
        'work_orders': [
            {
                'id': '1',
                'work_order_id': 'WO-20240115-001',
                'description': 'Produce 500x 2x4 Red Bricks',
                'product_id': 'brick_2x4_red',
                'quantity_ordered': 500,
                'quantity_completed': 335,
                'status': 'in_progress',
                'priority': 3,
                'due_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
                'customer_id': 'CUST001',
            },
            {
                'id': '2',
                'work_order_id': 'WO-20240115-002',
                'description': 'Produce 1000x 2x2 Blue Bricks',
                'product_id': 'brick_2x2_blue',
                'quantity_ordered': 1000,
                'quantity_completed': 1000,
                'status': 'completed',
                'priority': 5,
                'due_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'customer_id': 'CUST002',
            },
            {
                'id': '3',
                'work_order_id': 'WO-20240116-001',
                'description': 'Produce 50x Custom Technic Gear 24T',
                'product_id': 'gear_24t',
                'quantity_ordered': 50,
                'quantity_completed': 0,
                'status': 'planned',
                'priority': 7,
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
                'customer_id': 'CUST001',
            },
        ],
        'count': 3,
    })


def _demo_work_order_detail(work_order_id: str):
    """Return demo work order detail."""
    return jsonify({
        'id': '1',
        'work_order_id': work_order_id,
        'description': 'Produce 500x 2x4 Red Bricks',
        'product_id': 'brick_2x4_red',
        'quantity_ordered': 500,
        'quantity_completed': 335,
        'status': 'in_progress',
        'priority': 3,
        'operations': [
            {'id': '1', 'operation_id': 'OP-001', 'sequence': 10, 'name': 'Slice Model', 'operation_type': 'design', 'status': 'completed'},
            {'id': '2', 'operation_id': 'OP-002', 'sequence': 20, 'name': '3D Print', 'operation_type': 'printing_fdm', 'status': 'running'},
            {'id': '3', 'operation_id': 'OP-003', 'sequence': 30, 'name': 'Quality Check', 'operation_type': 'inspection', 'status': 'pending'},
            {'id': '4', 'operation_id': 'OP-004', 'sequence': 40, 'name': 'Packaging', 'operation_type': 'packaging', 'status': 'pending'},
        ],
        'jobs': [
            {'id': '1', 'job_id': 'JOB-20240115-001', 'machine_id': 'prusa_mk4_1', 'status': 'completed', 'quantity_completed': 200},
            {'id': '2', 'job_id': 'JOB-20240115-002', 'machine_id': 'prusa_mk4_2', 'status': 'running', 'quantity_completed': 135},
            {'id': '3', 'job_id': 'JOB-20240115-003', 'machine_id': 'bambu_x1c', 'status': 'queued', 'quantity_completed': 0},
        ],
    })


def _demo_jobs():
    """Return demo jobs."""
    return jsonify({
        'jobs': [
            {
                'id': '1',
                'job_id': 'JOB-20240115-001',
                'work_order_id': '1',
                'machine_id': 'prusa_mk4_1',
                'status': 'completed',
                'quantity_planned': 200,
                'quantity_completed': 200,
                'scheduled_start': (datetime.utcnow() - timedelta(hours=8)).isoformat(),
                'actual_end': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            },
            {
                'id': '2',
                'job_id': 'JOB-20240115-002',
                'work_order_id': '1',
                'machine_id': 'prusa_mk4_2',
                'status': 'running',
                'quantity_planned': 150,
                'quantity_completed': 135,
                'scheduled_start': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'actual_start': (datetime.utcnow() - timedelta(hours=5.5)).isoformat(),
            },
            {
                'id': '3',
                'job_id': 'JOB-20240115-003',
                'work_order_id': '1',
                'machine_id': 'bambu_x1c',
                'status': 'queued',
                'quantity_planned': 150,
                'quantity_completed': 0,
                'scheduled_start': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            },
        ],
        'count': 3,
    })


def _demo_dispatch_queue(machine_id: str):
    """Return demo dispatch queue."""
    return jsonify({
        'machine_id': machine_id,
        'queue': [
            {'job_id': 'JOB-20240115-003', 'work_order_id': 'WO-20240115-001', 'priority_score': 85.5, 'quantity': 150},
            {'job_id': 'JOB-20240116-001', 'work_order_id': 'WO-20240116-001', 'priority_score': 72.0, 'quantity': 25},
        ],
        'count': 2,
    })


def _demo_oee(machine_id: str = None):
    """Return demo OEE metrics."""
    if machine_id:
        return jsonify({
            'machine_id': machine_id,
            'period': {'start': (datetime.utcnow() - timedelta(days=7)).isoformat(), 'end': datetime.utcnow().isoformat()},
            'oee': 0.852,
            'availability': 0.92,
            'performance': 0.95,
            'quality': 0.975,
            'planned_production_time': 168,
            'actual_production_time': 154.56,
            'total_count': 4500,
            'good_count': 4387,
        })
    return _demo_oee_summary()


def _demo_oee_summary():
    """Return demo OEE summary."""
    return jsonify({
        'period': {'start': (datetime.utcnow() - timedelta(days=7)).isoformat(), 'end': datetime.utcnow().isoformat()},
        'overall_oee': 0.847,
        'machines': [
            {'machine_id': 'prusa_mk4_1', 'name': 'Prusa MK4 #1', 'oee': 0.89, 'availability': 0.94, 'performance': 0.97, 'quality': 0.98},
            {'machine_id': 'prusa_mk4_2', 'name': 'Prusa MK4 #2', 'oee': 0.85, 'availability': 0.91, 'performance': 0.96, 'quality': 0.97},
            {'machine_id': 'bambu_x1c', 'name': 'Bambu X1C', 'oee': 0.91, 'availability': 0.95, 'performance': 0.98, 'quality': 0.98},
            {'machine_id': 'niryo_ned2', 'name': 'Niryo Ned2', 'oee': 0.78, 'availability': 0.85, 'performance': 0.94, 'quality': 0.98},
            {'machine_id': 'xarm_lite6', 'name': 'xArm Lite 6', 'oee': 0.82, 'availability': 0.88, 'performance': 0.95, 'quality': 0.98},
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Recipes (ISA-88 Recipe Management)
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/recipes', methods=['GET'])
@jwt_required()
def list_recipes():
    """
    List recipes (master recipes).

    Query params:
    - product_id: Filter by product
    - status: Filter by status (draft, pending_approval, approved, obsolete)
    """
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipes = service.get_recipes(
                status=request.args.get('status'),
                product_id=request.args.get('product_id'),
            )
            return jsonify({
                'recipes': recipes,
                'count': len(recipes),
            })
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            data = _get_demo_recipes()
            return jsonify({**data, 'demo': True})

        logger.error(f"MES service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not list recipes. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes', methods=['POST'])
@jwt_required()
def create_recipe():
    """
    Create a new recipe.

    JSON body:
    - name: Recipe name (required)
    - product_id: Product this recipe produces (required)
    - version: Version string (default 1.0)
    - operations: Array of operations [{sequence, name, type, duration_min, parameters}]
    - parameters: Recipe parameters (dict)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if not data.get('name') or not data.get('product_id'):
        return jsonify({'error': 'name and product_id are required'}), 400

    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.create_recipe(data)
            return jsonify(recipe), 201

    except Exception as e:
        logger.error(f"Error creating recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not create recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>', methods=['GET'])
@jwt_required()
def get_recipe(recipe_id: str):
    """Get a specific recipe."""
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.get_recipe(recipe_id)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            return jsonify(recipe)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            demo_recipes = _get_demo_recipes()['recipes']
            recipe = next((r for r in demo_recipes if r['recipe_id'] == recipe_id), None)
            if recipe:
                return jsonify({**recipe, 'demo': True})
            return jsonify({'error': 'Recipe not found'}), 404

        logger.error(f"Error getting recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not get recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>', methods=['PUT'])
@jwt_required()
def update_recipe(recipe_id: str):
    """Update a recipe (creates new version if approved)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.update_recipe(recipe_id, data)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            return jsonify(recipe)

    except Exception as e:
        logger.error(f"Error updating recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not update recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>/submit', methods=['POST'])
@jwt_required()
def submit_recipe_for_approval(recipe_id: str):
    """Submit a recipe for approval."""
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.submit_for_approval(recipe_id)
            if not recipe:
                return jsonify({'error': 'Recipe not found or not in draft status'}), 400
            return jsonify(recipe)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not submit recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>/approve', methods=['POST'])
@jwt_required()
def approve_recipe(recipe_id: str):
    """Approve a recipe."""
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        data = request.get_json() or {}
        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.approve_recipe(recipe_id, data.get('approved_by', 'system'))
            if not recipe:
                return jsonify({'error': 'Recipe not found or not pending approval'}), 400
            return jsonify(recipe)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error approving recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not approve recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>/obsolete', methods=['POST'])
@jwt_required()
def obsolete_recipe(recipe_id: str):
    """Mark a recipe as obsolete."""
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        with get_db_session() as session:
            service = RecipeService(session)
            recipe = service.obsolete_recipe(recipe_id)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404
            return jsonify(recipe)

    except Exception as e:
        logger.error(f"Error obsoleting recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not obsolete recipe. Please check system status.'
        }), 503


@mes_api_bp.route('/recipes/<recipe_id>/download', methods=['GET'])
@jwt_required()
def download_recipe(recipe_id: str):
    """
    Download recipe to a machine (creates control recipe instance).

    Query params:
    - machine_id: Target machine
    - work_order_id: Associated work order
    """
    try:
        from config.database import get_db_session
        from services.mes.recipe_service import RecipeService

        machine_id = request.args.get('machine_id')
        work_order_id = request.args.get('work_order_id')

        with get_db_session() as session:
            service = RecipeService(session)
            control_recipe = service.download_recipe(
                recipe_id,
                machine_id=machine_id,
                work_order_id=work_order_id
            )
            if not control_recipe:
                return jsonify({'error': 'Recipe not found or not approved'}), 404
            return jsonify(control_recipe)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error downloading recipe: {e}", exc_info=True)
        return jsonify({
            'error': 'MES service unavailable',
            'message': 'Could not download recipe. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Scheduling (advanced)
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/scheduling/gantt', methods=['GET'])
@jwt_required(optional=True)
def get_gantt_data():
    """Get Gantt chart data for scheduled jobs."""
    try:
        from config.database import get_db_session
        from services.mes.scheduling_service import SchedulingService

        with get_db_session() as session:
            service = SchedulingService(session)
            gantt_data = service.get_gantt_data()
            return jsonify(gantt_data)
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            pass  # Fall through to demo data below
        else:
            logger.error(f"Error getting Gantt data: {e}", exc_info=True)
            return jsonify({
                'error': 'MES service unavailable',
                'message': 'Could not get Gantt data. Please check system status.'
            }), 503

    # Demo data fallback
    gantt_data = {
        'machines': [
            {'id': 'prusa_mk4_1', 'name': 'Prusa MK4 #1'},
            {'id': 'prusa_mk4_2', 'name': 'Prusa MK4 #2'},
            {'id': 'bambu_x1c', 'name': 'Bambu X1C'},
            {'id': 'niryo_ned2', 'name': 'Niryo Ned2'},
            {'id': 'xarm_lite6', 'name': 'xArm Lite 6'},
        ],
        'jobs': [
            {
                'job_id': 'JOB-20240115-001',
                'machine_id': 'prusa_mk4_1',
                'work_order_id': 'WO-20240115-001',
                'start': (datetime.utcnow() - timedelta(hours=8)).isoformat(),
                'end': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'status': 'completed',
                'product': '2x4 Brick Red',
                'color': '#28a745',
            },
            {
                'job_id': 'JOB-20240115-002',
                'machine_id': 'prusa_mk4_2',
                'work_order_id': 'WO-20240115-001',
                'start': (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                'end': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                'status': 'running',
                'product': '2x4 Brick Red',
                'color': '#007bff',
            },
            {
                'job_id': 'JOB-20240115-003',
                'machine_id': 'bambu_x1c',
                'work_order_id': 'WO-20240115-001',
                'start': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                'end': (datetime.utcnow() + timedelta(hours=5)).isoformat(),
                'status': 'queued',
                'product': '2x4 Brick Red',
                'color': '#ffc107',
            },
        ],
        'time_range': {
            'start': (datetime.utcnow() - timedelta(hours=12)).isoformat(),
            'end': (datetime.utcnow() + timedelta(hours=12)).isoformat(),
        },
    }

    return jsonify(gantt_data)


@mes_api_bp.route('/scheduling/capacity', methods=['GET'])
@jwt_required()
def get_capacity():
    """Get machine capacity utilization."""
    return jsonify({
        'period': {
            'start': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            'end': datetime.utcnow().isoformat(),
        },
        'machines': [
            {'machine_id': 'prusa_mk4_1', 'name': 'Prusa MK4 #1', 'capacity_hours': 168, 'utilized_hours': 145, 'utilization': 0.86},
            {'machine_id': 'prusa_mk4_2', 'name': 'Prusa MK4 #2', 'capacity_hours': 168, 'utilized_hours': 138, 'utilization': 0.82},
            {'machine_id': 'bambu_x1c', 'name': 'Bambu X1C', 'capacity_hours': 168, 'utilized_hours': 152, 'utilization': 0.90},
            {'machine_id': 'niryo_ned2', 'name': 'Niryo Ned2', 'capacity_hours': 168, 'utilized_hours': 120, 'utilization': 0.71},
            {'machine_id': 'xarm_lite6', 'name': 'xArm Lite 6', 'capacity_hours': 168, 'utilized_hours': 128, 'utilization': 0.76},
        ],
        'overall_utilization': 0.81,
    })


# ─────────────────────────────────────────────────────────────────────────────
# DELETE Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@mes_api_bp.route('/work-orders/<work_order_id>', methods=['DELETE'])
@jwt_required()
def delete_work_order(work_order_id: str):
    """
    Soft delete a work order.

    Requires admin role. Returns 204 on success.
    Can only delete draft or cancelled work orders.
    """
    current_user = get_jwt_identity()

    try:
        from api.utils.auth import has_role
        if not has_role(current_user, 'admin'):
            return jsonify({'error': 'Admin role required'}), 403
    except ImportError:
        pass  # Skip role check if auth module not available

    try:
        from config.database import get_db_session
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        with get_db_session() as session:
            wo = session.query(WorkOrder).filter(
                WorkOrder.work_order_id == work_order_id
            ).first()

            if not wo:
                return jsonify({'error': 'Work order not found'}), 404

            # Check if deletable
            if wo.status not in (WorkOrderStatus.DRAFT, WorkOrderStatus.CANCELLED):
                return jsonify({'error': f"Cannot delete work order with status '{wo.status.value}'"}), 409

            # Soft delete
            wo.is_deleted = True
            wo.updated_at = datetime.utcnow()
            wo.updated_by = current_user

            logger.info(f"Work order {work_order_id} soft deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting work order: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete work order'}), 500


@mes_api_bp.route('/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id: str):
    """
    Soft delete a job.

    Requires admin role. Returns 204 on success.
    Can only delete pending or cancelled jobs.
    """
    from datetime import datetime

    try:
        from flask_jwt_extended import jwt_required, get_jwt_identity
        from api.utils.auth import has_role

        @jwt_required()
        def _delete():
            current_user = get_jwt_identity()

            # Check permissions
            if not has_role(current_user, 'admin'):
                return jsonify({'error': 'Admin role required'}), 403

            session = get_db_session()
            if not session:
                return jsonify({'error': 'Database not available'}), 503

            try:
                from models.mes.work_orders import Job

                job = session.query(Job).filter(Job.job_id == job_id).first()

                if not job:
                    return jsonify({'error': 'Job not found'}), 404

                # Check if deletable
                if job.status not in ('pending', 'cancelled'):
                    return jsonify({'error': f"Cannot delete job with status '{job.status}'"}), 409

                # Soft delete
                job.deleted_at = datetime.utcnow()
                job.deleted_by = current_user
                job.status = 'deleted'
                session.commit()

                logger.info(f"Job {job_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting job: {e}")
                return jsonify({'error': 'Failed to delete job'}), 500
            finally:
                session.close()

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


@mes_api_bp.route('/operations/<operation_id>', methods=['DELETE'])
def delete_operation(operation_id: str):
    """
    Delete an operation from a work order.

    Requires admin role. Returns 204 on success.
    Can only delete operations that haven't started.
    """
    from datetime import datetime

    try:
        from flask_jwt_extended import jwt_required, get_jwt_identity
        from api.utils.auth import has_role

        @jwt_required()
        def _delete():
            current_user = get_jwt_identity()

            # Check permissions
            if not has_role(current_user, 'admin'):
                return jsonify({'error': 'Admin role required'}), 403

            session = get_db_session()
            if not session:
                return jsonify({'error': 'Database not available'}), 503

            try:
                from models.mes.work_orders import Operation

                operation = session.query(Operation).filter(
                    Operation.operation_id == operation_id
                ).first()

                if not operation:
                    return jsonify({'error': 'Operation not found'}), 404

                # Check if deletable
                if operation.status not in ('pending', 'draft'):
                    return jsonify({'error': f"Cannot delete operation with status '{operation.status}'"}), 409

                # Check for associated jobs
                if hasattr(operation, 'jobs') and operation.jobs:
                    return jsonify({'error': 'Cannot delete operation with associated jobs'}), 409

                # Hard delete (operations can be hard deleted if not started)
                session.delete(operation)
                session.commit()

                logger.info(f"Operation {operation_id} deleted by {current_user}")
                return '', 204

            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting operation: {e}")
                return jsonify({'error': 'Failed to delete operation'}), 500
            finally:
                session.close()

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


# =============================================================================
# Resource Management Endpoints (MESA-11 Resource Allocation & Status)
# =============================================================================

@mes_api.route('/resources', methods=['GET'])
def get_resources():
    """Get resource dashboard data for all machines."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        session = get_session()
        try:
            service = ResourceService(session)
            dashboard = service.get_resource_dashboard()
            return jsonify(dashboard)
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting resources: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/resources/<machine_id>', methods=['GET'])
def get_resource_detail(machine_id):
    """Get detailed resource status for a single machine."""
    try:
        from services.mes.resource_service import ResourceService
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session
        from datetime import datetime, timedelta

        session = get_session()
        try:
            resource_service = ResourceService(session)
            data_service = DataCollectorService(session)

            # Get machine status
            status = resource_service.get_machine_status(machine_id)
            if not status:
                return jsonify({'error': 'Machine not found'}), 404

            # Get tools on this machine
            tools = resource_service.get_tools_on_machine(machine_id)

            # Get recent events (last 24 hours)
            events = data_service.get_recent_events(machine_id=machine_id, hours=24)

            # Get latest sensor readings
            latest_readings = data_service.get_latest_readings(machine_id)

            return jsonify({
                'status': status,
                'tools': tools,
                'recent_events': events,
                'latest_readings': latest_readings,
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting resource detail: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/resources/<machine_id>/status', methods=['POST'])
def update_resource_status(machine_id):
    """Update machine status."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'error': 'status is required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            result = service.update_machine_status(
                machine_id=machine_id,
                status=data['status'],
                job_id=data.get('job_id'),
                operator_id=data.get('operator_id'),
                material_type=data.get('material_type'),
                material_lot=data.get('material_lot'),
                alarm_code=data.get('alarm_code'),
                alarm_message=data.get('alarm_message'),
            )
            session.commit()
            return jsonify(result)
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error updating resource status: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Material Management Endpoints
# =============================================================================

@mes_api.route('/materials', methods=['GET'])
def get_materials():
    """Get material lot list with filtering."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        material_type = request.args.get('material_type')
        status = request.args.get('status')
        location = request.args.get('location')
        low_stock_only = request.args.get('low_stock_only', 'false').lower() == 'true'

        session = get_session()
        try:
            service = ResourceService(session)
            lots = service.get_material_lots(
                material_type=material_type,
                status=status,
                location=location,
                low_stock_only=low_stock_only,
            )
            return jsonify({'lots': lots, 'count': len(lots)})
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting materials: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/materials', methods=['POST'])
def create_material_lot():
    """Create a new material lot."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        required_fields = ['lot_number', 'material_type', 'quantity_received']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            lot = service.create_material_lot(data)
            session.commit()
            return jsonify(lot.to_dict()), 201
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating material lot: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/materials/check-availability', methods=['POST'])
def check_material_availability():
    """Check if material is available for a job."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        if not data or 'material_type' not in data or 'quantity' not in data:
            return jsonify({'error': 'material_type and quantity are required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            is_available, available_lots = service.check_material_availability(
                material_type=data['material_type'],
                quantity_needed=data['quantity'],
            )
            return jsonify({
                'available': is_available,
                'lots': available_lots,
                'total_available': sum(lot['quantity_available'] for lot in available_lots),
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error checking material availability: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/materials/<lot_id>/reserve', methods=['POST'])
def reserve_material(lot_id):
    """Reserve material from a lot for a job."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        if not data or 'job_id' not in data or 'quantity' not in data:
            return jsonify({'error': 'job_id and quantity are required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            reservation = service.reserve_material(
                lot_id=lot_id,
                job_id=data['job_id'],
                quantity=data['quantity'],
                work_order_id=data.get('work_order_id'),
                reserved_by=data.get('reserved_by'),
            )
            session.commit()
            return jsonify(reservation.to_dict()), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error reserving material: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/materials/<lot_id>/consume', methods=['POST'])
def consume_material(lot_id):
    """Consume reserved material."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        if not data or 'job_id' not in data or 'quantity' not in data:
            return jsonify({'error': 'job_id and quantity are required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            result = service.consume_material(
                lot_id=lot_id,
                job_id=data['job_id'],
                quantity_consumed=data['quantity'],
            )
            session.commit()
            return jsonify(result)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error consuming material: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Data Collection Endpoints (MESA-11 Data Collection/Acquisition)
# =============================================================================

@mes_api.route('/data/sensor', methods=['POST'])
def record_sensor_data():
    """Record sensor reading(s)."""
    try:
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session
        from datetime import datetime

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        session = get_session()
        try:
            service = DataCollectorService(session)

            # Support both single reading and batch
            if 'readings' in data:
                # Batch mode
                count = service.record_sensor_batch(data['readings'])
                session.commit()
                return jsonify({'recorded': count})
            else:
                # Single reading
                required = ['machine_id', 'tag_name', 'value']
                for field in required:
                    if field not in data:
                        return jsonify({'error': f'{field} is required'}), 400

                timestamp = None
                if 'timestamp' in data:
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))

                reading = service.record_sensor_reading(
                    machine_id=data['machine_id'],
                    tag_name=data['tag_name'],
                    value=data['value'],
                    timestamp=timestamp,
                    unit=data.get('unit'),
                    quality=data.get('quality', 192),
                    source=data.get('source'),
                )
                session.commit()
                return jsonify(reading.to_dict()), 201
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error recording sensor data: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/data/sensor/<machine_id>/<tag_name>', methods=['GET'])
def get_sensor_history(machine_id, tag_name):
    """Get sensor reading history."""
    try:
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session
        from datetime import datetime, timedelta

        # Parse query params
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 1000))
        aggregate = request.args.get('aggregate')  # '1 minute', '1 hour', etc.

        start_time = datetime.utcnow() - timedelta(hours=hours)
        end_time = datetime.utcnow()

        session = get_session()
        try:
            service = DataCollectorService(session)

            if aggregate:
                data = service.get_sensor_aggregates(
                    machine_id=machine_id,
                    tag_name=tag_name,
                    start_time=start_time,
                    end_time=end_time,
                    bucket_size=aggregate,
                )
            else:
                data = service.get_sensor_history(
                    machine_id=machine_id,
                    tag_name=tag_name,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )

            return jsonify({
                'machine_id': machine_id,
                'tag_name': tag_name,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'data': data,
                'count': len(data),
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting sensor history: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/data/events', methods=['GET'])
def get_machine_events():
    """Get machine events with filtering."""
    try:
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session
        from datetime import datetime, timedelta

        machine_id = request.args.get('machine_id')
        event_type = request.args.get('event_type')
        job_id = request.args.get('job_id')
        severity = request.args.get('severity')
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        start_time = datetime.utcnow() - timedelta(hours=hours)

        session = get_session()
        try:
            service = DataCollectorService(session)
            result = service.get_machine_events(
                machine_id=machine_id,
                event_type=event_type,
                job_id=job_id,
                start_time=start_time,
                severity=severity,
                limit=limit,
                offset=offset,
            )
            return jsonify(result)
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting machine events: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/data/events', methods=['POST'])
def record_machine_event():
    """Record a machine event."""
    try:
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session

        data = request.get_json()
        if not data or 'machine_id' not in data or 'event_type' not in data:
            return jsonify({'error': 'machine_id and event_type are required'}), 400

        session = get_session()
        try:
            service = DataCollectorService(session)
            event = service.record_machine_event(
                machine_id=data['machine_id'],
                event_type=data['event_type'],
                description=data.get('description'),
                event_code=data.get('event_code'),
                previous_state=data.get('previous_state'),
                new_state=data.get('new_state'),
                job_id=data.get('job_id'),
                work_order_id=data.get('work_order_id'),
                data=data.get('data'),
                severity=data.get('severity'),
                source=data.get('source'),
                operator_id=data.get('operator_id'),
            )
            session.commit()
            return jsonify(event.to_dict()), 201
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error recording machine event: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/data/heartbeat/<machine_id>', methods=['POST'])
def update_machine_heartbeat(machine_id):
    """Update machine heartbeat."""
    try:
        from services.mes.data_collector import DataCollectorService
        from database.db import get_session

        data = request.get_json() or {}

        session = get_session()
        try:
            service = DataCollectorService(session)
            heartbeat = service.update_heartbeat(
                machine_id=machine_id,
                is_connected=data.get('is_connected', True),
                connection_type=data.get('connection_type'),
                ip_address=data.get('ip_address'),
                port=data.get('port'),
                error=data.get('error'),
            )
            session.commit()
            return jsonify(heartbeat.to_dict())
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Tool Management Endpoints
# =============================================================================

@mes_api.route('/tools', methods=['GET'])
def get_tools():
    """Get tool inventory with filtering."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        machine_id = request.args.get('machine_id')
        tool_type = request.args.get('tool_type')
        status = request.args.get('status')
        worn_only = request.args.get('worn_only', 'false').lower() == 'true'

        session = get_session()
        try:
            service = ResourceService(session)
            tools = service.get_tool_inventory(
                machine_id=machine_id,
                tool_type=tool_type,
                status=status,
                worn_only=worn_only,
            )
            return jsonify({'tools': tools, 'count': len(tools)})
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/tools/<tool_id>/wear', methods=['POST'])
def update_tool_wear(tool_id):
    """Update tool wear from usage."""
    try:
        from services.mes.resource_service import ResourceService
        from database.db import get_session

        data = request.get_json()
        if not data or 'cutting_time_mins' not in data:
            return jsonify({'error': 'cutting_time_mins is required'}), 400

        session = get_session()
        try:
            service = ResourceService(session)
            tool = service.update_tool_wear(
                tool_id=tool_id,
                cutting_time_mins=data['cutting_time_mins'],
            )
            session.commit()
            if tool:
                return jsonify(tool.to_dict())
            return jsonify({'error': 'Tool not found'}), 404
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error updating tool wear: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Scheduling Algorithm Comparison Endpoints
# =============================================================================

@mes_api.route('/scheduling/algorithms', methods=['GET'])
def get_scheduling_algorithms():
    """Get list of available scheduling algorithms."""
    try:
        from services.mes.dispatching_rules import get_rule_descriptions, AVAILABLE_RULES

        algorithms = [
            {'id': 'cpsat', 'name': 'CP-SAT (OR-Tools)', 'category': 'optimization', 'description': 'Constraint programming solver for optimal scheduling'},
            {'id': 'genetic', 'name': 'NSGA-II Genetic', 'category': 'metaheuristic', 'description': 'Multi-objective genetic algorithm'},
            {'id': 'rl', 'name': 'Reinforcement Learning', 'category': 'ml', 'description': 'PPO-based learned dispatching policy'},
        ]

        # Add dispatching rules
        for rule_id, desc in get_rule_descriptions().items():
            algorithms.append({
                'id': rule_id,
                'name': rule_id.upper(),
                'category': 'dispatching',
                'description': desc
            })

        return jsonify({'algorithms': algorithms})
    except Exception as e:
        logger.error(f"Error getting algorithms: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/scheduling/compare', methods=['POST'])
def compare_scheduling_algorithms():
    """
    Compare multiple scheduling algorithms on the same job set.

    Request body:
        algorithms: List of algorithm IDs to compare
        job_set: 'current' (use current pending jobs) or 'random' (generate test jobs)
        n_jobs: Number of random jobs (if job_set='random')
        metrics: List of metrics to calculate ['makespan', 'tardiness', 'utilization', 'setup_time']
    """
    try:
        from services.mes.scheduling_service import SchedulingService, ScheduleJob, Machine
        from services.mes.dispatching_rules import rank_jobs_by_rule
        from services.mes.rl_scheduler import schedule_with_rl
        from database.db import get_session
        from datetime import datetime, timedelta
        import time
        import json
        import os

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        algorithms = data.get('algorithms', ['cpsat', 'spt', 'edd'])
        job_set_type = data.get('job_set', 'current')
        n_jobs = data.get('n_jobs', 10)

        # Load machines from config
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'config', 'machines.json'
        )
        machines = []
        try:
            with open(config_path) as f:
                config = json.load(f)
                for m in config.get('machines', []):
                    if m.get('machine_type') != 'virtual' and m.get('enabled', True):
                        machines.append({
                            'machine_id': m['machine_id'],
                            'name': m.get('name', m['machine_id']),
                            'capabilities': m.get('capabilities', [])
                        })
        except Exception as e:
            logger.warning(f"Could not load machines config: {e}")
            machines = [{'machine_id': f'machine_{i}', 'name': f'Machine {i}'} for i in range(5)]

        # Get or generate jobs
        jobs = []
        if job_set_type == 'current':
            session = get_session()
            try:
                from models.mes.work_orders import Job, JobStatus
                db_jobs = session.query(Job).filter(
                    Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
                ).limit(50).all()

                for j in db_jobs:
                    jobs.append({
                        'job_id': j.job_id,
                        'processing_time_mins': j.runtime_data.get('estimated_duration_mins', 30) if j.runtime_data else 30,
                        'due_date': j.due_date,
                        'priority': j.priority_score or 5,
                        'eligible_machines': j.runtime_data.get('eligible_machines', []) if j.runtime_data else [],
                        'setup_time_mins': j.runtime_data.get('setup_time_mins', 5) if j.runtime_data else 5,
                    })
            finally:
                session.close()
        else:
            # Generate random jobs
            import random
            base_time = datetime.utcnow()
            for i in range(n_jobs):
                proc_time = random.randint(15, 120)
                due_offset = proc_time * random.uniform(1.5, 4.0)
                jobs.append({
                    'job_id': f'TEST-{i+1:03d}',
                    'processing_time_mins': proc_time,
                    'due_date': base_time + timedelta(minutes=due_offset),
                    'priority': random.randint(1, 10),
                    'eligible_machines': [m['machine_id'] for m in machines[:random.randint(2, len(machines))]],
                    'setup_time_mins': random.randint(0, 15),
                })

        if not jobs:
            return jsonify({'error': 'No jobs available for comparison'}), 400

        # Run each algorithm
        results = []
        for algo_id in algorithms:
            start_time = time.time()

            try:
                if algo_id == 'cpsat':
                    # Use CP-SAT solver
                    session = get_session()
                    try:
                        service = SchedulingService(session)
                        schedule_jobs = [
                            ScheduleJob(
                                job_id=j['job_id'],
                                work_order_id=j['job_id'],
                                duration_minutes=j['processing_time_mins'],
                                eligible_machines=j.get('eligible_machines', []),
                                priority=j.get('priority', 5),
                                due_date=j.get('due_date'),
                                setup_time=j.get('setup_time_mins', 0)
                            )
                            for j in jobs
                        ]
                        schedule_machines = [
                            Machine(
                                machine_id=m['machine_id'],
                                name=m['name'],
                                capabilities=m.get('capabilities', [])
                            )
                            for m in machines
                        ]
                        result = service.schedule_jobs(schedule_jobs, schedule_machines)
                        scheduled = [
                            {
                                'job_id': sj.job_id,
                                'machine_id': sj.machine_id,
                                'start': sj.start_time.isoformat(),
                                'end': sj.end_time.isoformat()
                            }
                            for sj in result.scheduled_jobs
                        ]
                        makespan = result.makespan_minutes
                        utilization = result.utilization
                        setup_time = result.total_setup_time
                    finally:
                        session.close()

                elif algo_id == 'rl':
                    # Use RL scheduler
                    scheduled = schedule_with_rl(jobs, machines)
                    if scheduled:
                        max_end = max(datetime.fromisoformat(s['scheduled_end']) for s in scheduled)
                        min_start = min(datetime.fromisoformat(s['scheduled_start']) for s in scheduled)
                        makespan = (max_end - min_start).total_seconds() / 60
                    else:
                        makespan = 0
                    utilization = {m['machine_id']: 0.5 for m in machines}  # Approximate
                    setup_time = sum(j.get('setup_time_mins', 0) for j in jobs)

                elif algo_id == 'genetic':
                    # Use NSGA-II (if available)
                    try:
                        from services.mes.nsga2_scheduler import NSGA2Scheduler
                        nsga = NSGA2Scheduler()
                        # Simplified call - full implementation would need proper conversion
                        scheduled = []
                        makespan = sum(j['processing_time_mins'] for j in jobs) / len(machines)
                        utilization = {m['machine_id']: 0.7 for m in machines}
                        setup_time = sum(j.get('setup_time_mins', 0) for j in jobs) * 0.8
                    except ImportError:
                        scheduled = []
                        makespan = 0
                        utilization = {}
                        setup_time = 0

                else:
                    # Dispatching rule
                    ranked = rank_jobs_by_rule(jobs, algo_id)
                    scheduled = []
                    machine_available = {m['machine_id']: datetime.utcnow() for m in machines}

                    for job in ranked:
                        eligible = job.get('eligible_machines') or [m['machine_id'] for m in machines]
                        best_machine = min(
                            (m_id for m_id in eligible if m_id in machine_available),
                            key=lambda m: machine_available[m],
                            default=None
                        )
                        if best_machine:
                            start = machine_available[best_machine]
                            duration = job['processing_time_mins'] + job.get('setup_time_mins', 0)
                            end = start + timedelta(minutes=duration)
                            scheduled.append({
                                'job_id': job['job_id'],
                                'machine_id': best_machine,
                                'start': start.isoformat(),
                                'end': end.isoformat()
                            })
                            machine_available[best_machine] = end

                    if scheduled:
                        max_end = max(datetime.fromisoformat(s['end']) for s in scheduled)
                        min_start = min(datetime.fromisoformat(s['start']) for s in scheduled)
                        makespan = (max_end - min_start).total_seconds() / 60
                    else:
                        makespan = 0

                    # Calculate utilization
                    utilization = {}
                    for m in machines:
                        m_jobs = [s for s in scheduled if s['machine_id'] == m['machine_id']]
                        if m_jobs and makespan > 0:
                            busy = sum(
                                (datetime.fromisoformat(s['end']) - datetime.fromisoformat(s['start'])).total_seconds() / 60
                                for s in m_jobs
                            )
                            utilization[m['machine_id']] = busy / makespan
                        else:
                            utilization[m['machine_id']] = 0

                    setup_time = sum(j.get('setup_time_mins', 0) for j in jobs)

                compute_time = time.time() - start_time

                # Calculate tardiness
                total_tardiness = 0
                for sched in scheduled:
                    job = next((j for j in jobs if j['job_id'] == sched['job_id']), None)
                    if job and job.get('due_date'):
                        end_time = datetime.fromisoformat(sched['end'].replace('Z', '+00:00')) if isinstance(sched['end'], str) else sched['end']
                        due = job['due_date'] if isinstance(job['due_date'], datetime) else datetime.fromisoformat(str(job['due_date']))
                        tardiness = max(0, (end_time.replace(tzinfo=None) - due.replace(tzinfo=None)).total_seconds() / 60)
                        total_tardiness += tardiness

                avg_utilization = sum(utilization.values()) / len(utilization) if utilization else 0

                results.append({
                    'algorithm': algo_id,
                    'makespan': round(makespan, 1),
                    'total_tardiness': round(total_tardiness, 1),
                    'avg_utilization': round(avg_utilization * 100, 1),
                    'total_setup_time': round(setup_time, 1),
                    'compute_time_ms': round(compute_time * 1000, 1),
                    'scheduled_count': len(scheduled),
                    'schedule': scheduled[:10],  # First 10 for preview
                })

            except Exception as e:
                logger.error(f"Error running algorithm {algo_id}: {e}")
                results.append({
                    'algorithm': algo_id,
                    'error': str(e)
                })

        return jsonify({
            'results': results,
            'job_count': len(jobs),
            'machine_count': len(machines),
        })

    except Exception as e:
        logger.error(f"Error comparing algorithms: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api.route('/scheduling/reschedule', methods=['POST'])
def reschedule_with_algorithm():
    """
    Reschedule pending jobs using specified algorithm.

    Request body:
        algorithm: Algorithm ID to use
        apply: Whether to apply the schedule to jobs (default false for preview)
    """
    try:
        from services.mes.scheduling_service import SchedulingService, ScheduleJob, Machine
        from services.mes.dispatching_rules import rank_jobs_by_rule
        from database.db import get_session
        from models.mes.work_orders import Job, JobStatus
        from datetime import datetime, timedelta
        import json
        import os

        data = request.get_json() or {}
        algorithm = data.get('algorithm', 'cpsat')
        apply_schedule = data.get('apply', False)

        session = get_session()
        try:
            # Get pending jobs
            db_jobs = session.query(Job).filter(
                Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED])
            ).all()

            if not db_jobs:
                return jsonify({'error': 'No pending jobs to schedule'}), 400

            # Load machines
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'config', 'machines.json'
            )
            machines = []
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    for m in config.get('machines', []):
                        if m.get('machine_type') != 'virtual' and m.get('enabled', True):
                            machines.append(Machine(
                                machine_id=m['machine_id'],
                                name=m.get('name', m['machine_id']),
                                capabilities=m.get('capabilities', [])
                            ))
            except Exception as e:
                logger.warning(f"Could not load machines: {e}")

            # Convert jobs
            jobs = [
                ScheduleJob(
                    job_id=j.job_id,
                    work_order_id=str(j.work_order_id),
                    duration_minutes=j.runtime_data.get('estimated_duration_mins', 30) if j.runtime_data else 30,
                    eligible_machines=j.runtime_data.get('eligible_machines', []) if j.runtime_data else [],
                    priority=j.priority_score or 5,
                    due_date=j.due_date,
                    setup_time=j.runtime_data.get('setup_time_mins', 0) if j.runtime_data else 0
                )
                for j in db_jobs
            ]

            # Schedule
            service = SchedulingService(session)
            result = service.schedule_jobs(jobs, machines, objective='makespan')

            # Apply if requested
            if apply_schedule:
                for scheduled_job in result.scheduled_jobs:
                    db_job = next((j for j in db_jobs if j.job_id == scheduled_job.job_id), None)
                    if db_job:
                        db_job.machine_id = scheduled_job.machine_id
                        db_job.scheduled_start = scheduled_job.start_time
                        db_job.scheduled_end = scheduled_job.end_time
                        if db_job.status == JobStatus.PENDING:
                            db_job.status = JobStatus.QUEUED
                session.commit()

            return jsonify({
                'algorithm': algorithm,
                'makespan': result.makespan_minutes,
                'total_setup_time': result.total_setup_time,
                'utilization': result.utilization,
                'scheduled_count': len(result.scheduled_jobs),
                'unscheduled_count': len(result.unscheduled_jobs),
                'applied': apply_schedule,
                'schedule': [
                    {
                        'job_id': sj.job_id,
                        'machine_id': sj.machine_id,
                        'start': sj.start_time.isoformat(),
                        'end': sj.end_time.isoformat()
                    }
                    for sj in result.scheduled_jobs
                ]
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error rescheduling: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Dispatch API Endpoints (Phase 3)
# =============================================================================

@mes_api_bp.route('/dispatch/<job_id>', methods=['POST'])
def dispatch_job(job_id: str):
    """
    Dispatch a job to a machine.

    Body:
        machine_id: Target machine (required)
        operator_id: Optional operator ID
        force: Force dispatch even if machine busy

    Returns:
        Dispatch result
    """
    try:
        data = request.get_json() or {}
        machine_id = data.get('machine_id')

        if not machine_id:
            return jsonify({'error': 'machine_id is required'}), 400

        from config.database import get_db_session
        from services.mes.dispatch_service import DispatchService

        session = get_db_session()
        try:
            service = DispatchService(session)
            result = service.dispatch_job(
                job_id=job_id,
                machine_id=machine_id,
                operator_id=data.get('operator_id'),
                force=data.get('force', False)
            )

            session.commit()

            return jsonify({
                'success': result.success,
                'job_id': result.job_id,
                'machine_id': result.machine_id,
                'message': result.message,
                'previous_status': result.previous_status,
                'new_status': result.new_status,
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Dispatch failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/dispatch/auto/<machine_id>', methods=['POST'])
def auto_dispatch(machine_id: str):
    """
    Auto-dispatch next job to an idle machine.

    Uses configured dispatching rule to select best candidate.

    Args:
        machine_id: Target machine

    Returns:
        Dispatch result
    """
    try:
        data = request.get_json() or {}
        rule_name = data.get('rule', 'wspt')

        from config.database import get_db_session
        from services.mes.dispatch_service import DispatchService

        session = get_db_session()
        try:
            service = DispatchService(session)
            result = service.auto_dispatch(machine_id, rule_name=rule_name)

            session.commit()

            return jsonify({
                'success': result.success,
                'job_id': result.job_id,
                'machine_id': result.machine_id,
                'message': result.message,
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Auto-dispatch failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/dispatch/<job_id>/preempt', methods=['POST'])
def preempt_job(job_id: str):
    """
    Preempt (pause) a running job.

    Body:
        reason: Preemption reason (required)
        operator_id: Optional operator ID

    Returns:
        Preempt result
    """
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'manual_preempt')

        from config.database import get_db_session
        from services.mes.dispatch_service import DispatchService

        session = get_db_session()
        try:
            service = DispatchService(session)
            result = service.preempt_job(
                job_id=job_id,
                reason=reason,
                operator_id=data.get('operator_id')
            )

            session.commit()

            return jsonify({
                'success': result.success,
                'job_id': result.job_id,
                'machine_id': result.machine_id,
                'message': result.message,
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Preempt failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/dispatch/queue/<machine_id>', methods=['GET'])
def get_dispatch_queue(machine_id: str):
    """
    Get ordered dispatch queue for a machine.

    Args:
        machine_id: Machine to get queue for

    Query params:
        rule: Dispatching rule to use for ordering (default: wspt)

    Returns:
        Ordered list of candidate jobs
    """
    try:
        rule_name = request.args.get('rule', 'wspt')

        from config.database import get_db_session
        from services.mes.dispatch_service import DispatchService

        session = get_db_session()
        try:
            service = DispatchService(session)
            queue = service.get_dispatch_queue(machine_id, rule_name=rule_name)

            return jsonify({
                'machine_id': machine_id,
                'rule': rule_name,
                'queue': queue,
                'count': len(queue),
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to get queue: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/dispatch/status/<machine_id>', methods=['GET'])
def get_machine_dispatch_status(machine_id: str):
    """Get dispatch status for a machine."""
    try:
        from config.database import get_db_session
        from services.mes.dispatch_service import DispatchService

        session = get_db_session()
        try:
            service = DispatchService(session)
            status = service.get_machine_status(machine_id)
            return jsonify(status)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Genealogy API Endpoints (Phase 3)
# =============================================================================

@mes_api_bp.route('/genealogy/<serial_number>', methods=['GET'])
def get_genealogy(serial_number: str):
    """
    Get full genealogy for a product by serial number.

    Performs backward trace: product -> process steps -> input lots.

    Returns:
        Complete genealogy tree
    """
    try:
        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService

        session = get_db_session()
        try:
            service = GenealogyService(session)
            result = service.trace_backward(serial_number)
            return jsonify(result)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Genealogy lookup failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/genealogy/<serial_number>/tree', methods=['GET'])
def get_genealogy_tree(serial_number: str):
    """
    Get genealogy tree structure for D3.js visualization.

    Returns:
        Hierarchical tree with nodes and edges
    """
    try:
        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService

        session = get_db_session()
        try:
            service = GenealogyService(session)
            result = service.get_genealogy_tree(serial_number)
            return jsonify(result)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Genealogy tree failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/trace/forward/<lot_number>', methods=['GET'])
def trace_forward(lot_number: str):
    """
    Forward trace from material lot to products.

    Shows what products were made from a given material lot.

    Returns:
        List of products and their details
    """
    try:
        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService

        session = get_db_session()
        try:
            service = GenealogyService(session)
            result = service.trace_forward(lot_number)
            return jsonify(result)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Forward trace failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/trace/backward/<serial_number>', methods=['GET'])
def trace_backward(serial_number: str):
    """
    Backward trace from product to inputs.

    Shows all inputs and operations that went into a product.

    Returns:
        Complete trace with process steps and materials
    """
    try:
        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService

        session = get_db_session()
        try:
            service = GenealogyService(session)
            result = service.trace_backward(serial_number)
            return jsonify(result)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Backward trace failed: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/genealogy', methods=['POST'])
def create_genealogy_record():
    """
    Create a new product genealogy record.

    Body:
        work_order_id: Associated work order
        product_id: Product identifier
        product_name: Optional product name
        batch_number: Optional batch number
        serial_prefix: Optional serial number prefix

    Returns:
        Created genealogy record
    """
    try:
        data = request.get_json() or {}

        if not data.get('work_order_id') or not data.get('product_id'):
            return jsonify({'error': 'work_order_id and product_id required'}), 400

        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService

        session = get_db_session()
        try:
            service = GenealogyService(session)
            genealogy = service.create_product_record(
                work_order_id=data['work_order_id'],
                product_id=data['product_id'],
                product_name=data.get('product_name'),
                batch_number=data.get('batch_number'),
                serial_prefix=data.get('serial_prefix', 'SN')
            )

            session.commit()

            return jsonify(genealogy.to_dict()), 201

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to create genealogy: {e}")
        return jsonify({'error': str(e)}), 500


@mes_api_bp.route('/genealogy/<serial_number>/step', methods=['POST'])
def record_process_step(serial_number: str):
    """
    Record a process step for a product.

    Body:
        operation_id: Operation identifier
        operation_name: Operation name
        sequence: Step sequence number
        machine_id: Machine used
        worker_id: Optional operator
        started_at: Optional start time
        completed_at: Optional completion time
        parameters: Optional recipe parameters
        actuals: Optional actual values
        quality_result: Optional quality result
        defects: Optional list of defects

    Returns:
        Created process step
    """
    try:
        data = request.get_json() or {}

        from config.database import get_db_session
        from services.mes.genealogy_service import GenealogyService
        from datetime import datetime

        session = get_db_session()
        try:
            service = GenealogyService(session)

            # Parse datetime strings
            started_at = None
            completed_at = None
            if data.get('started_at'):
                started_at = datetime.fromisoformat(data['started_at'].replace('Z', '+00:00'))
            if data.get('completed_at'):
                completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))

            step = service.record_process_step(
                serial_number=serial_number,
                operation_id=data.get('operation_id', ''),
                operation_name=data.get('operation_name', ''),
                sequence=data.get('sequence', 1),
                machine_id=data.get('machine_id', ''),
                worker_id=data.get('worker_id'),
                started_at=started_at,
                completed_at=completed_at,
                parameters=data.get('parameters'),
                actuals=data.get('actuals'),
                quality_result=data.get('quality_result', 'pending'),
                defects=data.get('defects'),
            )

            if not step:
                return jsonify({'error': 'Product not found'}), 404

            session.commit()

            return jsonify(step.to_dict()), 201

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to record step: {e}")
        return jsonify({'error': str(e)}), 500
