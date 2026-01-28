"""
MES API Routes for Flask CNC SCADA
==================================
Manufacturing Execution System REST API for work orders, labor, and quality.

Endpoints:
    POST   /api/mes/workorders          - Create work order
    GET    /api/mes/workorders          - List work orders
    GET    /api/mes/workorders/<id>     - Get work order details
    PUT    /api/mes/workorders/<id>     - Update work order
    POST   /api/mes/workorders/<id>/operations - Add operation

    POST   /api/mes/labor/clock-in      - Clock in to work order
    POST   /api/mes/labor/clock-out     - Clock out from work order
    GET    /api/mes/labor/active        - List active labor
    GET    /api/mes/labor/history       - Get labor history

    POST   /api/mes/quality/inspection  - Record inspection
    GET    /api/mes/quality/inspections - List inspections
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify

from services.auth_service import require_auth, require_role, get_current_user
from services.integration.event_dispatcher import get_event_dispatcher, EventType

logger = logging.getLogger(__name__)

bp = Blueprint('mes', __name__, url_prefix='/api/mes')

# In-memory storage (would be PostgreSQL in production)
_work_orders: Dict[str, Dict[str, Any]] = {}
_labor_entries: Dict[str, Dict[str, Any]] = {}
_active_labor: Dict[str, Dict[str, Any]] = {}
_inspections: list = []
_wo_counter = 0


def _generate_wo_number() -> str:
    """Generate work order number."""
    global _wo_counter
    _wo_counter += 1
    return f"WO-{datetime.now().strftime('%Y%m%d')}-{_wo_counter:04d}"


# ============================================================================
# Work Order Endpoints
# ============================================================================

@bp.route('/workorders', methods=['POST'])
@require_auth
@require_role('operator')
def create_work_order():
    """
    Create a new work order.

    Request JSON:
        {
            "part_number": "PART-001",
            "quantity": 10,
            "priority": 2,
            "due_date": "2025-01-15T10:00:00",
            "customer": "ACME Corp",
            "notes": "Rush order"
        }

    Response:
        - 201: Work order created
        - 400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    if not data.get('part_number'):
        return jsonify({'error': 'part_number is required'}), 400

    wo_number = _generate_wo_number()

    # Parse due date
    due_date = data.get('due_date')
    if due_date and isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except ValueError:
            due_date = datetime.now()
    else:
        due_date = datetime.now()

    work_order = {
        'wo_number': wo_number,
        'part_number': data.get('part_number'),
        'quantity': int(data.get('quantity', 1)),
        'priority': int(data.get('priority', 2)),
        'due_date': due_date.isoformat(),
        'customer': data.get('customer', ''),
        'notes': data.get('notes', ''),
        'status': 'pending',
        'progress': 0,
        'operations': [],
        'created_at': datetime.now().isoformat(),
        'created_by': get_current_user().username if get_current_user() else 'system',
    }

    _work_orders[wo_number] = work_order

    # Publish event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.WORK_ORDER_CREATED, work_order)

    logger.info(f"Work order created: {wo_number}")

    return jsonify({
        'message': 'Work order created',
        'work_order': work_order
    }), 201


@bp.route('/workorders', methods=['GET'])
@require_auth
def list_work_orders():
    """
    List all work orders.

    Query Parameters:
        - status: Filter by status (pending, in_progress, completed)
        - limit: Maximum number to return (default 50)

    Response:
        - 200: List of work orders
    """
    status_filter = request.args.get('status')
    limit = int(request.args.get('limit', 50))

    work_orders = list(_work_orders.values())

    if status_filter:
        work_orders = [wo for wo in work_orders if wo['status'] == status_filter]

    # Sort by due date
    work_orders.sort(key=lambda wo: wo.get('due_date', ''))

    return jsonify({
        'work_orders': work_orders[:limit],
        'total': len(work_orders)
    })


@bp.route('/workorders/<wo_number>', methods=['GET'])
@require_auth
def get_work_order(wo_number: str):
    """
    Get work order details.

    Response:
        - 200: Work order details
        - 404: Not found
    """
    work_order = _work_orders.get(wo_number)

    if not work_order:
        return jsonify({'error': 'Work order not found'}), 404

    return jsonify({'work_order': work_order})


@bp.route('/workorders/<wo_number>', methods=['PUT'])
@require_auth
@require_role('operator')
def update_work_order(wo_number: str):
    """
    Update work order.

    Request JSON:
        {
            "status": "in_progress",
            "progress": 50,
            "notes": "Updated notes"
        }

    Response:
        - 200: Updated work order
        - 404: Not found
    """
    work_order = _work_orders.get(wo_number)

    if not work_order:
        return jsonify({'error': 'Work order not found'}), 404

    data = request.get_json() or {}

    # Update allowed fields
    if 'status' in data:
        work_order['status'] = data['status']
    if 'progress' in data:
        work_order['progress'] = int(data['progress'])
    if 'priority' in data:
        work_order['priority'] = int(data['priority'])
    if 'notes' in data:
        work_order['notes'] = data['notes']

    work_order['updated_at'] = datetime.now().isoformat()

    # Publish update event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.WORK_ORDER_UPDATED, work_order)

    return jsonify({
        'message': 'Work order updated',
        'work_order': work_order
    })


@bp.route('/workorders/<wo_number>/operations', methods=['POST'])
@require_auth
@require_role('operator')
def add_operation(wo_number: str):
    """
    Add operation to work order.

    Request JSON:
        {
            "name": "Roughing",
            "description": "Initial material removal",
            "sequence": 1,
            "estimated_time_sec": 300,
            "setup_time_sec": 60
        }

    Response:
        - 201: Operation added
        - 404: Work order not found
    """
    work_order = _work_orders.get(wo_number)

    if not work_order:
        return jsonify({'error': 'Work order not found'}), 404

    data = request.get_json() or {}

    operation = {
        'id': f"op-{len(work_order['operations']) + 1:03d}",
        'name': data.get('name', 'Operation'),
        'description': data.get('description', ''),
        'sequence': int(data.get('sequence', len(work_order['operations']) + 1)),
        'estimated_time_sec': int(data.get('estimated_time_sec', 0)),
        'setup_time_sec': int(data.get('setup_time_sec', 0)),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
    }

    work_order['operations'].append(operation)

    return jsonify({
        'message': 'Operation added',
        'operation': operation
    }), 201


# ============================================================================
# Labor Tracking Endpoints
# ============================================================================

@bp.route('/labor/clock-in', methods=['POST'])
@require_auth
def clock_in():
    """
    Clock in to a work order/operation.

    Request JSON:
        {
            "employee_id": "EMP001",
            "employee_name": "John Doe",
            "work_order": "WO-20250115-0001",
            "operation": "op-001"
        }

    Response:
        - 200: Clocked in successfully
        - 400: Already clocked in
    """
    data = request.get_json() or {}

    employee_id = data.get('employee_id')
    if not employee_id:
        user = get_current_user()
        employee_id = user.username if user else 'unknown'

    # Check if already clocked in
    if employee_id in _active_labor:
        return jsonify({
            'error': 'Already clocked in',
            'current_entry': _active_labor[employee_id]
        }), 400

    entry = {
        'id': f"labor-{int(time.time())}",
        'employee_id': employee_id,
        'employee_name': data.get('employee_name', employee_id),
        'work_order': data.get('work_order', ''),
        'operation': data.get('operation', ''),
        'clock_in': datetime.now().isoformat(),
        'clock_out': None,
        'duration_sec': 0,
    }

    _active_labor[employee_id] = entry
    _labor_entries[entry['id']] = entry

    # Publish event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.LABOR_CLOCK_IN, {
        **entry,
        'action': 'clock_in',
        'timestamp': entry['clock_in']
    })

    logger.info(f"Labor clock in: {employee_id} -> {entry['work_order']}")

    return jsonify({
        'message': 'Clocked in successfully',
        'entry': entry
    })


@bp.route('/labor/clock-out', methods=['POST'])
@require_auth
def clock_out():
    """
    Clock out from current work.

    Request JSON:
        {
            "employee_id": "EMP001",
            "notes": "Completed operation"
        }

    Response:
        - 200: Clocked out successfully
        - 400: Not clocked in
    """
    data = request.get_json() or {}

    employee_id = data.get('employee_id')
    if not employee_id:
        user = get_current_user()
        employee_id = user.username if user else 'unknown'

    if employee_id not in _active_labor:
        return jsonify({'error': 'Not clocked in'}), 400

    entry = _active_labor[employee_id]
    clock_out_time = datetime.now()
    clock_in_time = datetime.fromisoformat(entry['clock_in'])

    entry['clock_out'] = clock_out_time.isoformat()
    entry['duration_sec'] = (clock_out_time - clock_in_time).total_seconds()
    entry['notes'] = data.get('notes', '')

    # Update in labor entries
    _labor_entries[entry['id']] = entry

    # Remove from active
    del _active_labor[employee_id]

    # Publish event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.LABOR_CLOCK_OUT, {
        **entry,
        'action': 'clock_out',
        'timestamp': entry['clock_out']
    })

    logger.info(f"Labor clock out: {employee_id} ({entry['duration_sec']:.0f}s)")

    return jsonify({
        'message': 'Clocked out successfully',
        'entry': entry
    })


@bp.route('/labor/active', methods=['GET'])
@require_auth
def get_active_labor():
    """
    Get all currently active labor entries.

    Response:
        - 200: List of active labor
    """
    return jsonify({
        'active_labor': list(_active_labor.values()),
        'count': len(_active_labor)
    })


@bp.route('/labor/history', methods=['GET'])
@require_auth
def get_labor_history():
    """
    Get labor history.

    Query Parameters:
        - employee_id: Filter by employee
        - work_order: Filter by work order
        - limit: Maximum number (default 50)

    Response:
        - 200: Labor history
    """
    employee_filter = request.args.get('employee_id')
    wo_filter = request.args.get('work_order')
    limit = int(request.args.get('limit', 50))

    entries = list(_labor_entries.values())

    if employee_filter:
        entries = [e for e in entries if e['employee_id'] == employee_filter]
    if wo_filter:
        entries = [e for e in entries if e['work_order'] == wo_filter]

    # Sort by clock_in descending
    entries.sort(key=lambda e: e.get('clock_in', ''), reverse=True)

    return jsonify({
        'labor_history': entries[:limit],
        'total': len(entries)
    })


# ============================================================================
# Quality Inspection Endpoints
# ============================================================================

@bp.route('/quality/inspection', methods=['POST'])
@require_auth
@require_role('operator')
def record_inspection():
    """
    Record a quality inspection.

    Request JSON:
        {
            "job_id": "job-001",
            "work_order": "WO-20250115-0001",
            "result": "pass",
            "measurements": {
                "dimension_x": 10.05,
                "dimension_y": 20.02,
                "surface_finish": 1.6
            },
            "notes": "Within tolerance"
        }

    Response:
        - 201: Inspection recorded
    """
    data = request.get_json() or {}

    inspection = {
        'id': f"insp-{int(time.time())}",
        'job_id': data.get('job_id', ''),
        'work_order': data.get('work_order', ''),
        'result': data.get('result', 'pending'),  # pass, fail, rework
        'measurements': data.get('measurements', {}),
        'notes': data.get('notes', ''),
        'inspector': get_current_user().username if get_current_user() else 'system',
        'timestamp': datetime.now().isoformat(),
    }

    _inspections.append(inspection)

    # Publish event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.QUALITY_INSPECTION, inspection)

    logger.info(f"Quality inspection: {inspection['job_id']} -> {inspection['result']}")

    return jsonify({
        'message': 'Inspection recorded',
        'inspection': inspection
    }), 201


@bp.route('/quality/inspections', methods=['GET'])
@require_auth
def list_inspections():
    """
    List quality inspections.

    Query Parameters:
        - job_id: Filter by job
        - result: Filter by result (pass, fail, rework)
        - limit: Maximum number (default 50)

    Response:
        - 200: List of inspections
    """
    job_filter = request.args.get('job_id')
    result_filter = request.args.get('result')
    limit = int(request.args.get('limit', 50))

    inspections = _inspections.copy()

    if job_filter:
        inspections = [i for i in inspections if i['job_id'] == job_filter]
    if result_filter:
        inspections = [i for i in inspections if i['result'] == result_filter]

    # Sort by timestamp descending
    inspections.sort(key=lambda i: i.get('timestamp', ''), reverse=True)

    return jsonify({
        'inspections': inspections[:limit],
        'total': len(inspections)
    })


@bp.route('/quality/summary', methods=['GET'])
@require_auth
def get_quality_summary():
    """
    Get quality summary statistics.

    Response:
        - 200: Quality statistics
    """
    total = len(_inspections)
    passed = len([i for i in _inspections if i['result'] == 'pass'])
    failed = len([i for i in _inspections if i['result'] == 'fail'])
    rework = len([i for i in _inspections if i['result'] == 'rework'])

    return jsonify({
        'summary': {
            'total_inspections': total,
            'passed': passed,
            'failed': failed,
            'rework': rework,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'first_pass_yield': (passed / (passed + failed + rework) * 100) if (passed + failed + rework) > 0 else 0,
        }
    })


# ============================================================================
# Scheduler Integration (OEE-Aware Multi-Machine)
# ============================================================================

@bp.route('/workorders/schedule', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_work_orders():
    """
    Schedule pending work orders using OEE-aware multi-machine scheduling.

    This endpoint converts work orders to scheduler jobs and assigns them
    to machines based on OEE fitness scores.

    Request JSON:
        {
            "work_orders": ["WO-20250115-0001", "WO-20250115-0002"],  // Optional: specific WOs
            "machines": [                                             // Optional: override machines
                {"id": "machine-01", "name": "Nomad 3 - Bay 1"},
                {"id": "machine-02", "name": "Nomad 3 - Bay 2"}
            ],
            "weights": {                                              // Optional: OEE weights
                "oee": 0.4,
                "utilization": 0.3,
                "capability": 0.2,
                "queue": 0.1
            }
        }

    Response:
        - 200: Schedule with machine assignments
        - 204: No work orders to schedule
        - 500: Scheduling failed
    """
    from services.scheduler_service import get_scheduler_service, Job, Operation, Machine
    from services.machine_manager import get_machine_manager

    data = request.get_json() or {}

    # Get work orders to schedule
    wo_numbers = data.get('work_orders')
    if wo_numbers:
        work_orders = [_work_orders[wo] for wo in wo_numbers if wo in _work_orders]
    else:
        # Get all pending work orders
        work_orders = [wo for wo in _work_orders.values() if wo['status'] == 'pending']

    if not work_orders:
        return '', 204

    # Parse weights
    weights = data.get('weights', {})
    oee_weight = weights.get('oee', 0.4)
    utilization_weight = weights.get('utilization', 0.3)
    capability_weight = weights.get('capability', 0.2)
    queue_weight = weights.get('queue', 0.1)

    # Convert work orders to scheduler jobs
    scheduler_jobs = []
    for wo in work_orders:
        # Calculate total processing time from operations
        total_time = sum(op.get('estimated_time_sec', 300) for op in wo.get('operations', []))
        if total_time == 0:
            total_time = 300  # Default 5 minutes

        total_setup = sum(op.get('setup_time_sec', 0) for op in wo.get('operations', []))

        # Parse due date
        due_date = None
        if wo.get('due_date'):
            try:
                due_dt = datetime.fromisoformat(wo['due_date'].replace('Z', '+00:00'))
                due_date = int((due_dt - datetime.now()).total_seconds() / 60)
                due_date = max(0, due_date)
            except (ValueError, TypeError):
                pass

        # Create operation for each WO operation, or default single operation
        operations = []
        if wo.get('operations'):
            for i, wo_op in enumerate(wo['operations']):
                operations.append(Operation(
                    id=wo_op.get('id', f"{wo['wo_number']}_op{i+1}"),
                    name=wo_op.get('name', f"Operation {i+1}"),
                    machine_id=wo_op.get('machine_id', 'machine-01'),  # Default to first machine
                    processing_time=int(wo_op.get('estimated_time_sec', 300) / 60),
                    setup_time=int(wo_op.get('setup_time_sec', 0) / 60)
                ))
        else:
            # Create single default operation
            operations.append(Operation(
                id=f"{wo['wo_number']}_op1",
                name=wo.get('part_number', 'Part'),
                machine_id='machine-01',
                processing_time=int(total_time / 60),
                setup_time=int(total_setup / 60)
            ))

        scheduler_jobs.append(Job(
            id=wo['wo_number'],
            name=f"{wo['part_number']} (Qty: {wo['quantity']})",
            operations=operations,
            priority=wo.get('priority', 5),
            due_date=due_date,
            release_date=0
        ))

    # Get machines
    scheduler_machines = []
    if data.get('machines'):
        for m in data['machines']:
            scheduler_machines.append(Machine(
                id=m['id'],
                name=m.get('name', m['id']),
                available_from=0,
                available_until=480
            ))
    else:
        # Get from machine manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            scheduler_machines.append(Machine(
                id=machine.machine_id,
                name=machine.name,
                available_from=0,
                available_until=480
            ))

        # Fallback
        if not scheduler_machines:
            scheduler_machines = [
                Machine(id='machine-01', name='Machine 1', available_from=0, available_until=480),
                Machine(id='machine-02', name='Machine 2', available_from=0, available_until=480)
            ]

    # Run OEE-aware scheduling
    scheduler = get_scheduler_service()
    result = scheduler.schedule_with_oee(
        jobs=scheduler_jobs,
        machines=scheduler_machines,
        oee_weight=oee_weight,
        utilization_weight=utilization_weight,
        capability_weight=capability_weight,
        queue_weight=queue_weight
    )

    if not result.success:
        return jsonify({
            'error': 'Scheduling failed',
            'message': result.status
        }), 500

    # Update work orders with machine assignments
    for task in result.tasks:
        wo_number = task.job_id
        if wo_number in _work_orders:
            wo = _work_orders[wo_number]
            wo['assigned_machine'] = task.machine_id
            wo['scheduled_start'] = task.start_time
            wo['scheduled_end'] = task.end_time
            wo['status'] = 'scheduled'

    # Publish event
    dispatcher = get_event_dispatcher()
    dispatcher.publish(EventType.SCHEDULE_UPDATED, {
        'work_orders': [wo['wo_number'] for wo in work_orders],
        'algorithm': 'oee_aware',
        'makespan_min': result.makespan
    })

    return jsonify({
        'success': True,
        'algorithm': 'oee_aware',
        'schedule': result.to_dict(),
        'gantt': result.to_gantt_data(),
        'work_orders_scheduled': len(work_orders),
        'machines_used': list(result.by_machine.keys()),
        'summary': {
            'makespan_min': result.makespan,
            'makespan_hours': round(result.makespan / 60, 2),
            'computation_time_ms': round(result.solve_time_ms, 2)
        }
    })
