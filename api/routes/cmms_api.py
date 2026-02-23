"""
LEGO Factory v3 - CMMS REST API
===============================
REST API endpoints for Computerized Maintenance Management System.

Provides endpoints for:
- Asset management
- Maintenance work orders
- PM schedules
- Meter readings
- Spare parts
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

cmms_api_bp = Blueprint('cmms_api', __name__, url_prefix='/api/cmms')


def _get_open_session():
    """Get an open database session (caller must close)."""
    from database.db import get_session
    return get_session()


def get_asset_service():
    """Get asset service instance with an open session."""
    try:
        from services.cmms.asset_service import get_asset_service as _get_svc
        session = _get_open_session()
        return _get_svc(session)
    except Exception as e:
        logger.warning(f"Asset service not available: {e}")
        return None


def get_maintenance_service():
    """Get maintenance service instance with an open session."""
    try:
        from services.cmms.maintenance_service import get_maintenance_service as _get_svc
        session = _get_open_session()
        return _get_svc(session)
    except Exception as e:
        logger.warning(f"Maintenance service not available: {e}")
        return None


def get_pm_service():
    """Get PM service instance with an open session."""
    try:
        from services.cmms.maintenance_service import get_pm_service as _get_svc
        session = _get_open_session()
        return _get_svc(session)
    except Exception as e:
        logger.warning(f"PM service not available: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Assets
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/assets', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def list_assets():
    """
    List assets.

    Query params:
    - status: Filter by status
    - criticality: Filter by criticality
    - class_code: Filter by asset class
    - location: Filter by location
    - limit: Max results (default: 100)
    """
    service = get_asset_service()
    if not service:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_assets
            data = get_demo_assets()
            return jsonify({**data, 'demo': True})

        logger.error("CMMS asset service unavailable")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503

    status = request.args.get('status')
    criticality = request.args.get('criticality')
    asset_class_id = request.args.get('asset_class_id') or request.args.get('class_code')
    location_id = request.args.get('location_id') or request.args.get('location')
    limit = int(request.args.get('limit', 100))

    assets = service.get_assets(
        status=status,
        criticality=criticality,
        asset_class_id=asset_class_id,
        location_id=location_id,
        limit=limit
    )

    return jsonify({
        'assets': assets,
        'count': len(assets),
    })


@cmms_api_bp.route('/assets', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def create_asset():
    """
    Create a new asset.

    JSON body:
    - asset_id: Unique asset identifier (required)
    - name: Asset name (required)
    - description: Description
    - asset_class_id: Asset class UUID
    - status: operational, degraded, down, maintenance
    - criticality: critical, essential, important, standard
    - location_id: Location identifier
    - serial_number: Serial number
    - manufacturer: Manufacturer name
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    if 'asset_id' not in data or 'name' not in data:
        return jsonify({'error': 'asset_id and name required'}), 400

    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service

        with get_db_session() as session:
            service = get_asset_service(session)
            asset = service.create_asset(data)
            return jsonify(asset), 201

    except ValueError as e:
        return jsonify({'error': 'Internal server error'}), 400
    except Exception as e:
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            demo_asset = {
                'asset_id': data.get('asset_id'),
                'name': data.get('name'),
                'description': data.get('description'),
                'status': data.get('status', 'operational'),
                'criticality': data.get('criticality', 'standard'),
                'message': 'Asset created (demo mode)',
                'demo': True,
            }
            return jsonify(demo_asset), 201

        logger.error(f"Error creating asset: {e}", exc_info=True)
        return jsonify({'error': 'Asset service not available'}), 503


@cmms_api_bp.route('/assets/<asset_id>', methods=['GET'])
@jwt_required(optional=True)
def get_asset(asset_id: str):
    """Get asset details."""
    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            asset = service.get_asset(asset_id)
            if not asset:
                return jsonify({'error': 'Asset not found'}), 404
            return jsonify(asset)

    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_asset
            data = get_demo_asset(asset_id)
            if not data:
                return jsonify({'error': 'Asset not found'}), 404
            return jsonify({**data, 'demo': True})

        logger.error(f"CMMS asset service unavailable: {e}")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503


@cmms_api_bp.route('/assets/<asset_id>', methods=['PUT'])
@jwt_required(optional=True)
def update_asset(asset_id: str):
    """Update asset."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            asset = service.update_asset(asset_id, data)
            if not asset:
                return jsonify({'error': 'Asset not found'}), 404
            return jsonify(asset)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'asset_id': asset_id,
                **data,
                'message': 'Asset updated (demo mode)',
                'demo': True,
            })

        logger.error(f"Error updating asset: {e}")
        return jsonify({'error': 'Asset service not available'}), 503


@cmms_api_bp.route('/assets/<asset_id>/status', methods=['PUT'])
@jwt_required(optional=True)
def update_asset_status(asset_id: str):
    """
    Update asset status.

    JSON body:
    - status: New status
    - reason: Reason for status change
    """
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400

    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            asset = service.update_asset(asset_id, {
                'status': data['status'],
            })

            if not asset:
                return jsonify({'error': 'Asset not found'}), 404

            return jsonify({
                'asset_id': asset_id,
                'status': asset['status'],
            })

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'asset_id': asset_id,
                'status': data['status'],
                'message': 'Status updated (demo mode)',
                'demo': True,
            })

        logger.error(f"Error updating asset status: {e}")
        return jsonify({'error': 'Asset service not available'}), 503


# ─────────────────────────────────────────────────────────────────────────────
# Meters
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/assets/<asset_id>/meters', methods=['GET'])
@jwt_required(optional=True)
def get_asset_meters(asset_id: str):
    """Get meters for an asset."""
    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            meters = service.get_meters(asset_id)

            return jsonify({
                'asset_id': asset_id,
                'meters': meters,
                'count': len(meters),
            })

    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_meters
            data = get_demo_meters(asset_id)
            return jsonify({**data, 'demo': True})

        logger.error(f"CMMS asset service unavailable: {e}")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503


@cmms_api_bp.route('/meters/<meter_id>/readings', methods=['POST'])
@jwt_required(optional=True)
def record_meter_reading(meter_id: str):
    """
    Record a meter reading.

    JSON body:
    - reading_value: The reading value (required)
    - reading_date: Reading timestamp (optional, defaults to now)
    - recorded_by: User ID
    """
    service = get_asset_service()
    if not service:
        return jsonify({'error': 'Asset service not available'}), 503

    data = request.get_json()
    if not data or 'reading_value' not in data:
        return jsonify({'error': 'reading_value required'}), 400

    try:
        reading = service.record_meter_reading(
            meter_id,
            data['reading_value'],
            data.get('reading_date'),
            data.get('source', 'manual'),
            data.get('recorded_by'),
        )
        return jsonify(reading), 201
    except ValueError as e:
        return jsonify({'error': 'Internal server error'}), 400


@cmms_api_bp.route('/meters/<meter_id>/readings', methods=['GET'])
@jwt_required(optional=True)
def get_meter_readings(meter_id: str):
    """
    Get meter reading history.

    Query params:
    - start_date: Start date (ISO format)
    - end_date: End date (ISO format)
    - limit: Max results (default: 100)
    """
    service = get_asset_service()
    if not service:
        return jsonify({'error': 'Asset service not available'}), 503

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = int(request.args.get('limit', 100))

    readings = service.get_meter_readings(
        meter_id,
        start_date=datetime.fromisoformat(start_date) if start_date else None,
        end_date=datetime.fromisoformat(end_date) if end_date else None,
        limit=limit
    )

    return jsonify({
        'meter_id': meter_id,
        'readings': readings,
        'count': len(readings),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Work Orders
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/work-orders', methods=['GET'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def list_work_orders():
    """
    List maintenance work orders.

    Query params:
    - status: Filter by status (draft, approved, in_progress, completed)
    - wo_type: Filter by type (corrective, preventive, emergency)
    - priority: Filter by priority
    - asset_id: Filter by asset
    - assigned_to: Filter by assignee
    - limit: Max results
    """
    service = get_maintenance_service()
    if not service:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_work_orders_cmms
            data = get_demo_work_orders_cmms()
            return jsonify({**data, 'demo': True})

        logger.error("CMMS maintenance service unavailable")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503

    status = request.args.get('status')
    wo_type = request.args.get('wo_type')
    priority = request.args.get('priority')
    asset_id = request.args.get('asset_id')
    assigned_to = request.args.get('assigned_to')
    limit = int(request.args.get('limit', 100))

    work_orders = service.get_work_orders(
        status=status,
        wo_type=wo_type,
        priority=priority,
        asset_id=asset_id,
        assigned_to=assigned_to,
        limit=limit
    )

    return jsonify({
        'work_orders': work_orders,
        'count': len(work_orders),
    })


@cmms_api_bp.route('/work-orders', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def create_work_order():
    """
    Create a maintenance work order.

    JSON body:
    - asset_id: Asset identifier (required)
    - description: Work order description (required)
    - wo_type: corrective, preventive, emergency, inspection
    - priority: critical, high, medium, low
    - problem_description: Problem details
    - target_start: Target start date
    - target_completion: Target completion date
    - assigned_to: Assignee
    - estimated_hours: Estimated labor hours
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    if 'asset_id' not in data or 'description' not in data:
        return jsonify({'error': 'asset_id and description required'}), 400

    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service

        with get_db_session() as session:
            service = get_maintenance_service(session)
            wo = service.create_work_order(data)
            return jsonify(wo), 201

    except ValueError as e:
        return jsonify({'error': 'Internal server error'}), 400
    except Exception as e:
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            import uuid
            demo_wo = {
                'wo_number': f"MWO-{uuid.uuid4().hex[:8].upper()}",
                'asset_id': data.get('asset_id'),
                'description': data.get('description'),
                'wo_type': data.get('wo_type', 'corrective'),
                'priority': data.get('priority', 'medium'),
                'status': 'draft',
                'message': 'Maintenance work order created (demo mode)',
                'demo': True,
            }
            return jsonify(demo_wo), 201

        logger.error(f"Error creating work order: {e}", exc_info=True)
        return jsonify({'error': 'Maintenance service not available'}), 503


@cmms_api_bp.route('/work-orders/<wo_number>', methods=['GET'])
@jwt_required(optional=True)
def get_work_order(wo_number: str):
    """Get work order details."""
    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            wo = service.get_work_order(wo_number)
            if not wo:
                return jsonify({'error': 'Work order not found'}), 404
            return jsonify(wo)

    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_work_order_cmms
            data = get_demo_work_order_cmms(wo_number)
            if not data:
                return jsonify({'error': 'Work order not found'}), 404
            return jsonify({**data, 'demo': True})

        logger.error(f"CMMS maintenance service unavailable: {e}")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503


@cmms_api_bp.route('/work-orders/<wo_number>', methods=['PUT'])
@jwt_required(optional=True)
def update_work_order(wo_number: str):
    """Update a work order."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            wo = service.update_work_order(wo_number, data)
            if not wo:
                return jsonify({'error': 'Work order not found'}), 404
            return jsonify(wo)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'wo_number': wo_number,
                **data,
                'message': 'Work order updated (demo mode)',
                'demo': True,
            })

        logger.error(f"Error updating work order: {e}")
        return jsonify({'error': 'Maintenance service not available'}), 503


@cmms_api_bp.route('/work-orders/<wo_number>/start', methods=['POST'])
@jwt_required(optional=True)
def start_work_order(wo_number: str):
    """Start a work order."""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'system')

    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            wo = service.start_work_order(wo_number, user_id)
            if not wo:
                return jsonify({'error': 'Work order not found'}), 404
            return jsonify(wo)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'wo_number': wo_number,
                'status': 'in_progress',
                'started_by': user_id,
                'message': 'Work order started (demo mode)',
                'demo': True,
            })

        logger.error(f"Error starting work order: {e}")
        return jsonify({'error': 'Maintenance service not available'}), 503


@cmms_api_bp.route('/work-orders/<wo_number>/complete', methods=['POST'])
@jwt_required(optional=True)
def complete_work_order(wo_number: str):
    """
    Complete a work order.

    JSON body:
    - completion_notes: Notes about the work completed
    - actual_hours: Actual hours worked
    - user_id: User completing the work
    """
    data = request.get_json() or {}

    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            wo = service.complete_work_order(
                wo_number,
                completion_notes=data.get('completion_notes'),
                actual_hours=data.get('actual_hours'),
                user_id=data.get('user_id', 'system')
            )

            if not wo:
                return jsonify({'error': 'Work order not found'}), 404

            return jsonify(wo)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'wo_number': wo_number,
                'status': 'completed',
                'completion_notes': data.get('completion_notes'),
                'actual_hours': data.get('actual_hours'),
                'message': 'Work order completed (demo mode)',
                'demo': True,
            })

        logger.error(f"Error completing work order: {e}")
        return jsonify({'error': 'Maintenance service not available'}), 503


@cmms_api_bp.route('/work-orders/<wo_number>/tasks', methods=['POST'])
@jwt_required(optional=True)
def add_work_order_task(wo_number: str):
    """
    Add a task to a work order.

    JSON body:
    - name: Task name (required)
    - description: Task description
    - instructions: Work instructions
    - estimated_minutes: Estimated duration
    """
    service = get_maintenance_service()
    if not service:
        return jsonify({'error': 'Maintenance service not available'}), 503

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'name required'}), 400

    task = service.add_task(wo_number, data)
    if not task:
        return jsonify({'error': 'Work order not found'}), 404

    return jsonify(task), 201


@cmms_api_bp.route('/work-orders/<wo_number>/labor', methods=['POST'])
@jwt_required(optional=True)
def record_work_order_labor(wo_number: str):
    """
    Record labor on a work order.

    JSON body:
    - worker_id: Worker ID (required)
    - regular_hours: Regular hours worked
    - overtime_hours: Overtime hours worked
    - hourly_rate: Hourly labor rate
    - notes: Work notes
    """
    service = get_maintenance_service()
    if not service:
        return jsonify({'error': 'Maintenance service not available'}), 503

    data = request.get_json()
    if not data or 'worker_id' not in data:
        return jsonify({'error': 'worker_id required'}), 400

    labor = service.record_labor(wo_number, data)
    if not labor:
        return jsonify({'error': 'Work order not found'}), 404

    return jsonify(labor), 201


@cmms_api_bp.route('/work-orders/<wo_number>/materials', methods=['POST'])
@jwt_required(optional=True)
def record_work_order_material(wo_number: str):
    """
    Record material usage on a work order.

    JSON body:
    - description: Material description (required)
    - quantity_used: Quantity used
    - spare_id: Spare part ID (optional)
    - unit_cost: Cost per unit
    """
    service = get_maintenance_service()
    if not service:
        return jsonify({'error': 'Maintenance service not available'}), 503

    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'description required'}), 400

    material = service.record_material(wo_number, data)
    if not material:
        return jsonify({'error': 'Work order not found'}), 404

    return jsonify(material), 201


# ─────────────────────────────────────────────────────────────────────────────
# PM Schedules
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/pm-schedules', methods=['GET'])
@jwt_required(optional=True)
def list_pm_schedules():
    """
    List PM schedules.

    Query params:
    - asset_id: Filter by asset
    - is_active: Filter by active status
    - due_within_days: Filter by due date
    """
    service = get_pm_service()
    if not service:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_pm_schedules
            data = get_demo_pm_schedules()
            return jsonify({**data, 'demo': True})

        logger.error("CMMS PM service unavailable")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503

    asset_id = request.args.get('asset_id')
    is_active = request.args.get('is_active')
    due_within_days = request.args.get('due_within_days')

    schedules = service.get_pm_schedules(
        asset_id=asset_id,
        is_active=is_active == 'true' if is_active else None,
        due_within_days=int(due_within_days) if due_within_days else None
    )

    return jsonify({
        'pm_schedules': schedules,
        'count': len(schedules),
    })


@cmms_api_bp.route('/pm-schedules', methods=['POST'])
@jwt_required(optional=True)
def create_pm_schedule():
    """
    Create a PM schedule.

    JSON body:
    - asset_id: Asset identifier (required)
    - name: PM name (required)
    - trigger_type: calendar, meter, runtime
    - frequency_days: Frequency for calendar-based PMs
    - next_due_date: Next due date
    - priority: Work order priority
    - estimated_hours: Estimated hours for PM
    - instructions: Work instructions
    """
    service = get_pm_service()
    if not service:
        return jsonify({'error': 'PM service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    if 'asset_id' not in data or 'name' not in data:
        return jsonify({'error': 'asset_id and name required'}), 400

    try:
        pm = service.create_pm_schedule(data)
        return jsonify(pm), 201
    except ValueError as e:
        return jsonify({'error': 'Internal server error'}), 400


@cmms_api_bp.route('/pm-schedules/<pm_id>', methods=['GET'])
@jwt_required(optional=True)
def get_pm_schedule(pm_id: str):
    """Get PM schedule details."""
    service = get_pm_service()
    if not service:
        return jsonify({'error': 'PM service not available'}), 503

    pm = service.get_pm_schedule(pm_id)
    if not pm:
        return jsonify({'error': 'PM schedule not found'}), 404

    return jsonify(pm)


@cmms_api_bp.route('/pm-schedules/<pm_id>', methods=['PUT'])
@jwt_required(optional=True)
def update_pm_schedule(pm_id: str):
    """Update a PM schedule."""
    service = get_pm_service()
    if not service:
        return jsonify({'error': 'PM service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    pm = service.update_pm_schedule(pm_id, data)
    if not pm:
        return jsonify({'error': 'PM schedule not found'}), 404

    return jsonify(pm)


@cmms_api_bp.route('/pm-schedules/generate', methods=['POST'])
@jwt_required(optional=True)
def generate_pm_work_orders():
    """
    Generate work orders for upcoming PMs.

    JSON body:
    - days_ahead: How many days ahead to look (default: 7)
    """
    service = get_pm_service()
    if not service:
        return jsonify({'error': 'PM service not available'}), 503

    data = request.get_json() or {}
    days_ahead = data.get('days_ahead', 7)

    generated = service.generate_pm_work_orders(days_ahead)

    return jsonify({
        'generated_work_orders': generated,
        'count': len(generated),
    })


@cmms_api_bp.route('/pm-schedules/compliance', methods=['GET'])
@jwt_required(optional=True)
def get_pm_compliance():
    """
    Get PM compliance metrics.

    Query params:
    - days: Period to analyze (default: 30)
    """
    service = get_pm_service()
    if not service:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_pm_compliance
            data = get_demo_pm_compliance()
            return jsonify({**data, 'demo': True})

        logger.error("CMMS PM service unavailable")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503

    days = int(request.args.get('days', 30))
    compliance = service.get_pm_compliance(days)

    return jsonify(compliance)


# ─────────────────────────────────────────────────────────────────────────────
# Backlog Summary
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/backlog', methods=['GET'])
@jwt_required(optional=True)
def get_backlog():
    """Get maintenance backlog summary."""
    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service as get_svc

        with get_db_session() as session:
            service = get_svc(session)
            backlog = service.get_backlog_summary()
            return jsonify(backlog)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_backlog
            data = get_demo_backlog()
            return jsonify({**data, 'demo': True})

        logger.error(f"CMMS maintenance service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Spare Parts
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/spares', methods=['GET'])
@jwt_required(optional=True)
def list_spares():
    """List spare parts."""
    service = get_asset_service()
    if not service:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_spares
            data = get_demo_spares()
            return jsonify({**data, 'demo': True})

        logger.error("CMMS asset service unavailable")
        return jsonify({
            'error': 'CMMS service unavailable',
            'message': 'The Maintenance Management System is not available. Please check system status.'
        }), 503

    spares = service.get_spares(limit=int(request.args.get('limit', 100)))

    return jsonify({
        'spares': spares,
        'count': len(spares),
    })


@cmms_api_bp.route('/spares/low-stock', methods=['GET'])
@jwt_required(optional=True)
def get_low_stock_spares():
    """Get spare parts below reorder point."""
    service = get_asset_service()
    if not service:
        return jsonify({'error': 'Asset service not available'}), 503

    spares = service.get_low_stock_spares()

    return jsonify({
        'low_stock_spares': spares,
        'count': len(spares),
    })


# Note: Demo data functions have been moved to api/routes/demo_data.py
# They are only used when DEMO_MODE environment variable is set to 'true'


# ─────────────────────────────────────────────────────────────────────────────
# DELETE Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@cmms_api_bp.route('/assets/<asset_id>', methods=['DELETE'])
def delete_asset(asset_id: str):
    """
    Soft delete an asset.

    Requires admin role. Returns 204 on success.
    Cannot delete assets with open work orders.
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

            service = get_asset_service()
            if not service:
                return jsonify({'error': 'Asset service not available'}), 503

            asset = service.get_asset(asset_id)
            if not asset:
                return jsonify({'error': 'Asset not found'}), 404

            # Check for open work orders
            maint_service = get_maintenance_service()
            if maint_service:
                open_wos = maint_service.get_work_orders(
                    asset_id=asset_id,
                    status='in_progress'
                )
                if open_wos:
                    return jsonify({'error': 'Cannot delete asset with open work orders'}), 409

            try:
                from config.database import get_db_session
                from models.cmms.assets import Asset

                with get_db_session() as session:
                    asset_record = session.query(Asset).filter(Asset.asset_id == asset_id).first()
                    if asset_record:
                        asset_record.deleted_at = datetime.utcnow()
                        asset_record.deleted_by = current_user
                        asset_record.status = 'retired'
                        session.commit()

                logger.info(f"Asset {asset_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                logger.error(f"Error deleting asset: {e}")
                return jsonify({'error': 'Failed to delete asset'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


@cmms_api_bp.route('/work-orders/<wo_id>', methods=['DELETE'])
def delete_work_order(wo_id: str):
    """
    Soft delete a maintenance work order.

    Requires admin role. Returns 204 on success.
    Can only delete draft or cancelled work orders.
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

            service = get_maintenance_service()
            if not service:
                return jsonify({'error': 'Maintenance service not available'}), 503

            wo = service.get_work_order(wo_id)
            if not wo:
                return jsonify({'error': 'Work order not found'}), 404

            # Can only delete draft/cancelled work orders
            if wo.get('status') not in ('draft', 'cancelled', 'scheduled'):
                return jsonify({'error': f"Cannot delete work order with status '{wo.get('status')}'. Only draft, scheduled, or cancelled work orders can be deleted."}), 409

            try:
                from config.database import get_db_session
                from models.cmms.work_orders import MaintenanceWorkOrder

                with get_db_session() as session:
                    wo_record = session.query(MaintenanceWorkOrder).filter(
                        MaintenanceWorkOrder.wo_number == wo_id
                    ).first()

                    if wo_record:
                        wo_record.deleted_at = datetime.utcnow()
                        wo_record.deleted_by = current_user
                        wo_record.status = 'deleted'
                        session.commit()

                logger.info(f"Work order {wo_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                logger.error(f"Error deleting work order: {e}")
                return jsonify({'error': 'Failed to delete work order'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


@cmms_api_bp.route('/pm-schedules/<schedule_id>', methods=['DELETE'])
def delete_pm_schedule(schedule_id: str):
    """
    Delete a PM schedule.

    Requires admin role. Returns 204 on success.
    Will deactivate the schedule rather than hard delete.
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

            service = get_pm_service()
            if not service:
                return jsonify({'error': 'PM service not available'}), 503

            pm = service.get_pm_schedule(schedule_id)
            if not pm:
                return jsonify({'error': 'PM schedule not found'}), 404

            try:
                from config.database import get_db_session
                from models.cmms.pm_schedules import PMSchedule

                with get_db_session() as session:
                    pm_record = session.query(PMSchedule).filter(
                        PMSchedule.pm_id == schedule_id
                    ).first()

                    if pm_record:
                        pm_record.is_active = False
                        pm_record.deleted_at = datetime.utcnow()
                        pm_record.deleted_by = current_user
                        session.commit()

                logger.info(f"PM schedule {schedule_id} deleted by {current_user}")
                return '', 204

            except Exception as e:
                logger.error(f"Error deleting PM schedule: {e}")
                return jsonify({'error': 'Failed to delete PM schedule'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


# ---------------------------------------------------------------------------
# Reliability Endpoints
# ---------------------------------------------------------------------------

@cmms_api_bp.route('/assets/<asset_id>/reliability', methods=['GET'])
def get_asset_reliability(asset_id: str):
    """Get MTBF and MTTR metrics for an asset."""
    try:
        from services.cmms.reliability_service import ReliabilityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = ReliabilityService(session)
            period_days = request.args.get('period_days', 90, type=int)
            mtbf = service.calculate_mtbf(asset_id, period_days=period_days)
            mttr = service.calculate_mttr(asset_id, period_days=period_days)
            trend = service.reliability_trend(asset_id, months=12)
            return jsonify({
                'asset_id': asset_id,
                'mtbf': mtbf,
                'mttr': mttr,
                'trend': trend
            }), 200
    except Exception as e:
        logger.error(f"Error getting reliability for asset {asset_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cmms_api_bp.route('/reliability/worst-performers', methods=['GET'])
def get_worst_performers():
    """Get worst performing assets by reliability."""
    try:
        from services.cmms.reliability_service import ReliabilityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = ReliabilityService(session)
            limit = request.args.get('limit', 10, type=int)
            performers = service.get_worst_performers(limit=limit)
            return jsonify({'worst_performers': performers}), 200
    except Exception as e:
        logger.error(f"Error getting worst performers: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# PM Calendar Endpoints
# ---------------------------------------------------------------------------

@cmms_api_bp.route('/pm-calendar', methods=['GET'])
def get_pm_calendar():
    """Get PM calendar events for a given month."""
    try:
        from services.cmms.pm_calendar_service import PMCalendarService
        from config.database import get_db_session
        with get_db_session() as session:
            service = PMCalendarService(session)
            month = request.args.get('month')
            machine_id = request.args.get('machine_id')
            events = service.get_calendar_events(month, machine_id=machine_id)
            return jsonify({'events': events}), 200
    except Exception as e:
        logger.error(f"Error getting PM calendar: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cmms_api_bp.route('/pm-calendar/auto-schedule', methods=['POST'])
def auto_schedule_pm():
    """Auto-schedule a PM based on its configuration."""
    try:
        from services.cmms.pm_calendar_service import PMCalendarService
        from config.database import get_db_session
        with get_db_session() as session:
            service = PMCalendarService(session)
            data = request.get_json()
            pm_id = data.get('pm_id')
            result = service.auto_schedule_pm(pm_id)
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error auto-scheduling PM: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Condition-Based Maintenance (CBM) Endpoints
# ---------------------------------------------------------------------------

@cmms_api_bp.route('/cbm/evaluate/<machine_id>', methods=['POST'])
def evaluate_cbm(machine_id: str):
    """Evaluate condition-based maintenance for a specific machine."""
    try:
        from services.cmms.cbm_service import CBMService
        from config.database import get_db_session
        with get_db_session() as session:
            service = CBMService(session)
            result = service.evaluate_conditions(machine_id)
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error evaluating CBM for machine {machine_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cmms_api_bp.route('/cbm/evaluate-all', methods=['POST'])
def evaluate_cbm_all():
    """Evaluate condition-based maintenance for all machines."""
    try:
        from services.cmms.cbm_service import CBMService
        from config.database import get_db_session
        with get_db_session() as session:
            service = CBMService(session)
            result = service.evaluate_all_machines()
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error evaluating CBM for all machines: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Spare Parts Endpoints
# ---------------------------------------------------------------------------

@cmms_api_bp.route('/spare-parts/availability/<work_order_id>', methods=['GET'])
def get_spare_parts_availability(work_order_id: str):
    """Check spare parts availability for a work order."""
    try:
        from services.cmms.spare_parts_service import SparePartsService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SparePartsService(session)
            availability = service.check_parts_availability(work_order_id)
            return jsonify(availability), 200
    except Exception as e:
        logger.error(f"Error checking parts availability for WO {work_order_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cmms_api_bp.route('/spare-parts/requisition', methods=['POST'])
def create_spare_parts_requisition():
    """Create an auto-requisition for a spare part."""
    try:
        from services.cmms.spare_parts_service import SparePartsService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SparePartsService(session)
            data = request.get_json()
            part_id = data.get('part_id')
            quantity = data.get('quantity')
            result = service.auto_requisition(part_id, quantity)
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error creating spare parts requisition: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cmms_api_bp.route('/spare-parts/usage/<part_id>', methods=['GET'])
def get_spare_parts_usage(part_id: str):
    """Get usage history for a spare part."""
    try:
        from services.cmms.spare_parts_service import SparePartsService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SparePartsService(session)
            history = service.get_usage_history(part_id)
            return jsonify({'part_id': part_id, 'usage_history': history}), 200
    except Exception as e:
        logger.error(f"Error getting usage history for part {part_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
