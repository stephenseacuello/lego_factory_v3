"""
Procurement API - Purchase orders and supplier management.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime

from models import get_db_session
from services.erp import ProcurementService

procurement_bp = Blueprint('procurement', __name__, url_prefix='/procurement')


# Supplier endpoints

@procurement_bp.route('/suppliers', methods=['GET'])
def list_suppliers():
    """List all suppliers."""
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    with get_db_session() as session:
        service = ProcurementService(session)
        suppliers = service.list_suppliers(active_only=active_only)

        return jsonify({
            'suppliers': suppliers,
            'total': len(suppliers)
        })


@procurement_bp.route('/suppliers', methods=['POST'])
def create_supplier():
    """
    Create a new supplier.

    Request body:
    {
        "name": "LEGO Parts Co",
        "code": "LPC-001",
        "contact_email": "orders@legoparts.com",
        "lead_time_days": 7,
        "payment_terms": "NET30"
    }
    """
    data = request.get_json()

    name = data.get('name')
    code = data.get('code')

    if not all([name, code]):
        return jsonify({'error': 'name and code are required'}), 400

    with get_db_session() as session:
        service = ProcurementService(session)

        try:
            supplier = service.create_supplier(
                name=name,
                code=code,
                contact_email=data.get('contact_email'),
                contact_phone=data.get('contact_phone'),
                lead_time_days=data.get('lead_time_days', 7),
                min_order_value=data.get('min_order_value', 0),
                payment_terms=data.get('payment_terms', 'NET30')
            )

            return jsonify(supplier), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@procurement_bp.route('/suppliers/<supplier_code>', methods=['GET'])
def get_supplier(supplier_code: str):
    """Get supplier details."""
    with get_db_session() as session:
        service = ProcurementService(session)
        supplier = service.get_supplier(supplier_code)

        if not supplier:
            return jsonify({'error': 'Supplier not found'}), 404

        return jsonify(supplier)


# Purchase order endpoints

@procurement_bp.route('/purchase-orders', methods=['GET'])
def list_purchase_orders():
    """
    List purchase orders.

    Query params:
    - supplier_code: Filter by supplier
    - status: Filter by status
    - limit: Max results
    """
    supplier_code = request.args.get('supplier_code')
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)

    with get_db_session() as session:
        service = ProcurementService(session)
        orders = service.list_purchase_orders(
            supplier_code=supplier_code,
            status=status,
            limit=limit
        )

        return jsonify({
            'purchase_orders': orders,
            'total': len(orders)
        })


@procurement_bp.route('/purchase-orders', methods=['POST'])
def create_purchase_order():
    """
    Create a new purchase order.

    Request body:
    {
        "supplier_code": "LPC-001",
        "lines": [
            {"part_id": "uuid", "quantity": 100, "unit_price": 0.15}
        ],
        "notes": "Rush order",
        "requested_date": "2024-02-01"
    }
    """
    data = request.get_json()

    supplier_code = data.get('supplier_code')
    lines = data.get('lines', [])

    if not supplier_code or not lines:
        return jsonify({'error': 'supplier_code and lines are required'}), 400

    requested_date = None
    if data.get('requested_date'):
        requested_date = datetime.fromisoformat(data['requested_date'])

    with get_db_session() as session:
        service = ProcurementService(session)

        try:
            po = service.create_purchase_order(
                supplier_code=supplier_code,
                lines=lines,
                notes=data.get('notes'),
                requested_date=requested_date
            )

            return jsonify(po), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@procurement_bp.route('/purchase-orders/<po_number>', methods=['GET'])
def get_purchase_order(po_number: str):
    """Get purchase order details."""
    with get_db_session() as session:
        service = ProcurementService(session)
        po = service.get_purchase_order(po_number)

        if not po:
            return jsonify({'error': 'Purchase order not found'}), 404

        return jsonify(po)


@procurement_bp.route('/purchase-orders/<po_number>/approve', methods=['POST'])
def approve_purchase_order(po_number: str):
    """Approve a purchase order."""
    data = request.get_json() or {}

    with get_db_session() as session:
        service = ProcurementService(session)

        try:
            po = service.approve_purchase_order(
                po_number=po_number,
                approved_by=data.get('approved_by')
            )
            return jsonify(po)

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@procurement_bp.route('/purchase-orders/<po_number>/send', methods=['POST'])
def send_purchase_order(po_number: str):
    """Mark purchase order as sent to supplier."""
    with get_db_session() as session:
        service = ProcurementService(session)

        try:
            po = service.send_purchase_order(po_number)
            return jsonify(po)

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@procurement_bp.route('/purchase-orders/<po_number>/receive', methods=['POST'])
def receive_purchase_order(po_number: str):
    """
    Receive items against a purchase order.

    Request body:
    {
        "receipts": [
            {"line_number": 1, "quantity_received": 50}
        ],
        "location_id": "uuid"
    }
    """
    data = request.get_json()

    receipts = data.get('receipts', [])
    if not receipts:
        return jsonify({'error': 'receipts are required'}), 400

    with get_db_session() as session:
        service = ProcurementService(session)

        try:
            po = service.receive_purchase_order(
                po_number=po_number,
                receipts=receipts,
                location_id=data.get('location_id')
            )
            return jsonify(po)

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@procurement_bp.route('/open-orders/<part_id>', methods=['GET'])
def get_open_orders(part_id: str):
    """Get open purchase order lines for a part."""
    with get_db_session() as session:
        service = ProcurementService(session)
        orders = service.get_open_orders_by_part(part_id)

        return jsonify({
            'part_id': part_id,
            'open_orders': orders
        })


@procurement_bp.route('/reorder-point/<part_id>', methods=['GET'])
def get_reorder_point(part_id: str):
    """
    Calculate reorder point for a part.

    Query params:
    - lead_time_days: Supplier lead time
    - safety_stock_days: Days of safety stock
    """
    lead_time = request.args.get('lead_time_days', 7, type=int)
    safety_stock = request.args.get('safety_stock_days', 3, type=int)

    with get_db_session() as session:
        service = ProcurementService(session)
        result = service.calculate_reorder_point(
            part_id=part_id,
            lead_time_days=lead_time,
            safety_stock_days=safety_stock
        )

        return jsonify(result)
