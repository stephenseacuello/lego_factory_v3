"""
Traceability API Routes for Flask CNC SCADA
============================================
REST API for part traceability, genealogy, and compliance reporting.

Endpoints:
    POST   /api/traceability/records         - Create as-built record
    GET    /api/traceability/records/<id>    - Get record details
    GET    /api/traceability/serial/<sn>     - Get record by serial number
    PUT    /api/traceability/records/<id>/status - Update status
    POST   /api/traceability/records/<id>/operation/start - Start operation
    POST   /api/traceability/records/<id>/operation/complete - Complete operation
    POST   /api/traceability/genealogy       - Link parent/child
    GET    /api/traceability/genealogy/<id>  - Get genealogy tree
    POST   /api/traceability/materials       - Create material lot
    POST   /api/traceability/records/<id>/sign - Electronic signature
    GET    /api/traceability/reports/dhr/<id> - Generate DHR
    GET    /api/traceability/reports/batch/<lot> - Generate batch record
    GET    /api/traceability/search          - Search affected parts
"""

import logging
from flask import Blueprint, request, jsonify

from services.traceability_service import (
    get_traceability_service,
    RecordType,
    RecordStatus,
    SensorSnapshot
)
from services.auth_service import (
    require_auth,
    require_role,
    get_current_user,
    verify_password,
    get_user_store
)

logger = logging.getLogger(__name__)

bp = Blueprint('traceability', __name__, url_prefix='/api/traceability')


# ==================== Record Management ====================

@bp.route('/records', methods=['POST'])
@require_auth
@require_role('operator')
def create_record():
    """
    Create a new as-built record.

    Request JSON:
        {
            "serial_number": "SN-2024-001",
            "part_number": "PART-100",
            "part_revision": "A",
            "record_type": "serial",
            "work_order_id": "WO-001",
            "part_description": "Widget Assembly"
        }

    Response:
        - 201: Record created
        - 400: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    required_fields = ['serial_number', 'part_number', 'part_revision']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    user = get_current_user()
    service = get_traceability_service()

    try:
        # Parse record type
        record_type_str = data.get('record_type', 'serial')
        record_type = RecordType(record_type_str)

        record = service.create_record(
            serial_number=data['serial_number'],
            part_number=data['part_number'],
            part_revision=data['part_revision'],
            record_type=record_type,
            work_order_id=data.get('work_order_id'),
            user_id=user.username if user else 'system',
            part_description=data.get('part_description'),
            lot_number=data.get('lot_number'),
            quantity=data.get('quantity', 1.0)
        )

        return jsonify({
            'message': 'Record created',
            'record': record.to_dict()
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/records/<record_id>', methods=['GET'])
@require_auth
def get_record(record_id: str):
    """
    Get record details by ID.

    Response:
        - 200: Record details
        - 404: Record not found
    """
    service = get_traceability_service()
    record = service.get_record(record_id)

    if not record:
        return jsonify({'error': 'Record not found'}), 404

    return jsonify({'record': record.to_dict()})


@bp.route('/serial/<serial_number>', methods=['GET'])
@require_auth
def get_by_serial(serial_number: str):
    """
    Get record by serial number.

    Response:
        - 200: Record details
        - 404: Record not found
    """
    service = get_traceability_service()
    record = service.get_by_serial(serial_number)

    if not record:
        return jsonify({'error': f'No record found for serial: {serial_number}'}), 404

    return jsonify({'record': record.to_dict()})


@bp.route('/records/<record_id>/status', methods=['PUT'])
@require_auth
@require_role('operator')
def update_status(record_id: str):
    """
    Update record status.

    Request JSON:
        {
            "status": "completed",
            "reason": "All operations complete"
        }

    Response:
        - 200: Status updated
        - 400: Invalid status
        - 404: Record not found
    """
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Status required'}), 400

    try:
        status = RecordStatus(data['status'])
    except ValueError:
        valid = [s.value for s in RecordStatus]
        return jsonify({'error': f'Invalid status. Valid: {valid}'}), 400

    user = get_current_user()
    service = get_traceability_service()

    if service.update_status(
        record_id,
        status,
        user.username if user else 'system',
        data.get('reason')
    ):
        record = service.get_record(record_id)
        return jsonify({
            'message': 'Status updated',
            'record': record.to_dict()
        })
    else:
        return jsonify({'error': 'Record not found'}), 404


# ==================== Operation Tracking ====================

@bp.route('/records/<record_id>/operation/start', methods=['POST'])
@require_auth
@require_role('operator')
def start_operation(record_id: str):
    """
    Record operation start with optional sensor snapshot.

    Request JSON:
        {
            "operation_id": "OP-001",
            "operation_name": "CNC Machining",
            "machine_id": "cnc-01"
        }

    Response:
        - 200: Operation started
        - 404: Record not found
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    required = ['operation_id', 'operation_name', 'machine_id']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    user = get_current_user()
    service = get_traceability_service()

    # Capture sensor snapshot
    snapshot = service.capture_sensor_snapshot(
        machine_id=data['machine_id'],
        operation_id=data['operation_id']
    )

    if service.record_operation_start(
        record_id=record_id,
        operation_id=data['operation_id'],
        operation_name=data['operation_name'],
        machine_id=data['machine_id'],
        user_id=user.username if user else 'system',
        sensor_snapshot=snapshot
    ):
        record = service.get_record(record_id)
        return jsonify({
            'message': 'Operation started',
            'record': record.to_dict()
        })
    else:
        return jsonify({'error': 'Record not found'}), 404


@bp.route('/records/<record_id>/operation/complete', methods=['POST'])
@require_auth
@require_role('operator')
def complete_operation(record_id: str):
    """
    Record operation completion.

    Request JSON:
        {
            "operation_id": "OP-001",
            "result": "pass",
            "notes": "Completed within tolerance"
        }

    Response:
        - 200: Operation completed
        - 404: Record not found
    """
    data = request.get_json()
    if not data or 'operation_id' not in data:
        return jsonify({'error': 'operation_id required'}), 400

    user = get_current_user()
    service = get_traceability_service()

    # Capture end-of-operation sensor snapshot
    record = service.get_record(record_id)
    if not record:
        return jsonify({'error': 'Record not found'}), 404

    # Find machine ID from operation
    machine_id = None
    for op in record.operations:
        if op.get('operation_id') == data['operation_id']:
            machine_id = op.get('machine_id')
            break

    snapshot = None
    if machine_id:
        snapshot = service.capture_sensor_snapshot(
            machine_id=machine_id,
            operation_id=data['operation_id']
        )

    if service.record_operation_complete(
        record_id=record_id,
        operation_id=data['operation_id'],
        user_id=user.username if user else 'system',
        result=data.get('result', 'pass'),
        sensor_snapshot=snapshot,
        notes=data.get('notes')
    ):
        record = service.get_record(record_id)
        return jsonify({
            'message': 'Operation completed',
            'record': record.to_dict()
        })
    else:
        return jsonify({'error': 'Failed to complete operation'}), 400


# ==================== Genealogy ====================

@bp.route('/genealogy', methods=['POST'])
@require_auth
@require_role('operator')
def link_genealogy():
    """
    Create parent-child genealogy link.

    Request JSON:
        {
            "parent_id": "record-uuid-1",
            "child_id": "record-uuid-2",
            "link_type": "component",
            "quantity": 1
        }

    Response:
        - 200: Link created
        - 400: Invalid request
        - 404: Record not found
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    if 'parent_id' not in data or 'child_id' not in data:
        return jsonify({'error': 'parent_id and child_id required'}), 400

    user = get_current_user()
    service = get_traceability_service()

    if service.link_parent_child(
        parent_id=data['parent_id'],
        child_id=data['child_id'],
        link_type=data.get('link_type', 'component'),
        quantity=data.get('quantity', 1.0),
        user_id=user.username if user else 'system'
    ):
        return jsonify({'message': 'Genealogy link created'})
    else:
        return jsonify({'error': 'One or both records not found'}), 404


@bp.route('/genealogy/<record_id>', methods=['GET'])
@require_auth
def get_genealogy(record_id: str):
    """
    Get genealogy tree for a record.

    Query Parameters:
        - direction: "up", "down", or "both" (default)
        - max_depth: Maximum tree depth (default 10)

    Response:
        - 200: Genealogy tree
        - 404: Record not found
    """
    direction = request.args.get('direction', 'both')
    try:
        max_depth = int(request.args.get('max_depth', 10))
        if max_depth < 1 or max_depth > 100:
            return jsonify({'error': 'max_depth must be between 1 and 100'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid max_depth parameter'}), 400

    service = get_traceability_service()
    tree = service.get_genealogy_tree(record_id, direction, max_depth)

    if not tree:
        return jsonify({'error': 'Record not found'}), 404

    return jsonify({'genealogy': tree})


@bp.route('/records/<record_id>/material', methods=['POST'])
@require_auth
@require_role('operator')
def add_material(record_id: str):
    """
    Add material lot to a record.

    Request JSON:
        {
            "lot_id": "MAT-LOT-001",
            "quantity": 1.5
        }

    Response:
        - 200: Material added
        - 404: Record or lot not found
    """
    data = request.get_json()
    if not data or 'lot_id' not in data:
        return jsonify({'error': 'lot_id required'}), 400

    user = get_current_user()
    service = get_traceability_service()

    if service.add_material_lot(
        record_id=record_id,
        lot_id=data['lot_id'],
        user_id=user.username if user else 'system',
        quantity=data.get('quantity')
    ):
        record = service.get_record(record_id)
        return jsonify({
            'message': 'Material added',
            'record': record.to_dict()
        })
    else:
        return jsonify({'error': 'Record or material lot not found'}), 404


# ==================== Material Lots ====================

@bp.route('/materials', methods=['POST'])
@require_auth
@require_role('maintenance')
def create_material_lot():
    """
    Create a new material lot.

    Request JSON:
        {
            "lot_id": "MAT-LOT-001",
            "material_code": "AL6061",
            "material_name": "Aluminum 6061-T6",
            "supplier": "ABC Metals",
            "supplier_lot": "SUP-12345",
            "quantity": 100,
            "unit": "kg"
        }

    Response:
        - 201: Lot created
        - 400: Invalid request
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    required = ['lot_id', 'material_code', 'material_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    service = get_traceability_service()

    try:
        lot = service.create_material_lot(
            lot_id=data['lot_id'],
            material_code=data['material_code'],
            material_name=data['material_name'],
            supplier=data.get('supplier'),
            supplier_lot=data.get('supplier_lot'),
            received_date=data.get('received_date'),
            expiration_date=data.get('expiration_date'),
            quantity=data.get('quantity', 0),
            unit=data.get('unit', 'each'),
            certificate_of_conformance=data.get('certificate_of_conformance'),
            properties=data.get('properties', {})
        )

        from dataclasses import asdict
        return jsonify({
            'message': 'Material lot created',
            'lot': asdict(lot)
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/materials/<lot_id>', methods=['GET'])
@require_auth
def get_material_lot(lot_id: str):
    """
    Get material lot details.

    Response:
        - 200: Lot details
        - 404: Lot not found
    """
    service = get_traceability_service()
    lot = service.get_material_lot(lot_id)

    if not lot:
        return jsonify({'error': 'Material lot not found'}), 404

    from dataclasses import asdict
    return jsonify({'lot': asdict(lot)})


# ==================== Electronic Signatures ====================

@bp.route('/records/<record_id>/sign', methods=['POST'])
@require_auth
def sign_record(record_id: str):
    """
    Apply electronic signature (21 CFR Part 11 compliant).

    Request JSON:
        {
            "password": "user_password",
            "meaning": "Approved for production"
        }

    Response:
        - 200: Signature applied
        - 400: Invalid request
        - 401: Password verification failed
        - 404: Record not found
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    if 'password' not in data or 'meaning' not in data:
        return jsonify({'error': 'password and meaning required'}), 400

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # 21 CFR Part 11 compliance: Verify password before applying e-signature
    store = get_user_store()
    stored_user = store.get(user.username)
    if not stored_user:
        logger.error(f"E-signature failed: user {user.username} not found in store")
        return jsonify({'error': 'User not found'}), 401

    if not verify_password(data['password'], stored_user.password_hash):
        logger.warning(f"E-signature failed: invalid password for user {user.username}")
        return jsonify({'error': 'Password verification failed'}), 401

    service = get_traceability_service()

    if service.sign_record(
        record_id=record_id,
        user_id=user.username,
        password=data['password'],
        meaning=data['meaning']
    ):
        logger.info(f"E-signature applied by {user.username} on record {record_id}")
        return jsonify({'message': 'Electronic signature applied'})
    else:
        return jsonify({'error': 'Record not found'}), 404


# ==================== Compliance Reports ====================

@bp.route('/reports/dhr/<record_id>', methods=['GET'])
@require_auth
@require_role('quality')
def generate_dhr(record_id: str):
    """
    Generate Device History Record.

    Response:
        - 200: DHR document
        - 404: Record not found
    """
    service = get_traceability_service()
    dhr = service.generate_dhr(record_id)

    if not dhr:
        return jsonify({'error': 'Record not found'}), 404

    return jsonify({'dhr': dhr})


@bp.route('/reports/batch/<lot_number>', methods=['GET'])
@require_auth
@require_role('quality')
def generate_batch_record(lot_number: str):
    """
    Generate Batch Production Record.

    Response:
        - 200: Batch record
        - 404: No records found for lot
    """
    service = get_traceability_service()
    batch_record = service.generate_batch_record(lot_number)

    if not batch_record:
        return jsonify({'error': f'No records found for lot: {lot_number}'}), 404

    return jsonify({'batch_record': batch_record})


@bp.route('/search', methods=['GET'])
@require_auth
def search_affected():
    """
    Search for affected parts (for recalls, investigations).

    Query Parameters:
        - material_lot: Find parts using this material lot
        - part_number: Filter by part number
        - date_from: Production date range start (ISO format)
        - date_to: Production date range end (ISO format)

    Response:
        - 200: List of affected records
    """
    service = get_traceability_service()

    records = service.search_affected_parts(
        material_lot_id=request.args.get('material_lot'),
        part_number=request.args.get('part_number'),
        date_from=request.args.get('date_from'),
        date_to=request.args.get('date_to')
    )

    return jsonify({
        'records': [r.to_dict() for r in records],
        'count': len(records)
    })
