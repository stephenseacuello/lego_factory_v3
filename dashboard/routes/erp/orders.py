"""
Customer Order Routes - Order Management API

LegoMCP World-Class Manufacturing System v5.0
Phase 8: Customer Orders & ATP/CTP

ISA-95 Level 4 Customer Order Operations:
- Order creation and lifecycle management
- Available-to-Promise (ATP) checking
- Capable-to-Promise (CTP) checking
- Order status tracking
"""

from datetime import datetime, date
from flask import Blueprint, jsonify, request

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')


# Dashboard Page Route
@orders_bp.route('/page', methods=['GET'])
def orders_page():
    """Render customer orders dashboard page."""
    from flask import render_template
    return render_template('pages/manufacturing/wip_dashboard.html')


# Try to import order services
try:
    from services.erp.order_service import (
        OrderService,
        OrderCreateRequest,
        OrderLineRequest,
    )
    from services.erp.atp_service import ATPService, InventoryPosition
    from services.erp.ctp_service import CTPService, CapacitySlot
    ORDER_SERVICES_AVAILABLE = True
except ImportError:
    ORDER_SERVICES_AVAILABLE = False

# Global service instances
_order_service = None
_atp_service = None
_ctp_service = None


def _get_order_service():
    """Get or create order service."""
    global _order_service, _atp_service, _ctp_service
    if _order_service is None and ORDER_SERVICES_AVAILABLE:
        _atp_service = ATPService()
        _ctp_service = CTPService()
        _order_service = OrderService(
            atp_service=_atp_service,
            ctp_service=_ctp_service,
        )
        # Initialize with demo inventory data
        _initialize_demo_data()
    return _order_service


def _initialize_demo_data():
    """Initialize demo inventory and capacity data."""
    global _atp_service, _ctp_service

    if not _atp_service or not _ctp_service:
        return

    # Add demo inventory positions
    demo_parts = [
        ('BRICK-2X4', 1000, 100),
        ('BRICK-2X2', 500, 50),
        ('PLATE-4X8', 200, 20),
        ('STUD-SINGLE', 2000, 200),
    ]

    for part_id, on_hand, allocated in demo_parts:
        _atp_service.set_inventory_position(InventoryPosition(
            part_id=part_id,
            quantity_on_hand=on_hand,
            quantity_allocated=allocated,
            safety_stock=50,
            by_location={'MAIN-WH': on_hand},
        ))

    # Add demo capacity slots
    today = date.today()
    for wc_id in ['WC-PRINT-01', 'WC-PRINT-02', 'WC-ASSEMBLY']:
        for day_offset in range(30):
            slot_date = today + __import__('datetime').timedelta(days=day_offset)
            _ctp_service.add_capacity_slot(CapacitySlot(
                work_center_id=wc_id,
                work_center_name=wc_id,
                slot_date=slot_date,
                total_capacity=480,
                available_capacity=480,
            ))

    # Add part production info
    _ctp_service.set_part_info(
        'BRICK-2X4',
        setup_time_min=15,
        run_time_per_unit_min=0.5,
        eligible_work_centers=['WC-PRINT-01', 'WC-PRINT-02'],
        bom=[{'part_id': 'PLA-RED', 'quantity': 5, 'available': 10000}],
    )


@orders_bp.route('', methods=['GET'])
def list_orders():
    """
    List customer orders.

    Query params:
    - status: Filter by status
    - customer_id: Filter by customer
    - open_only: If true, only return open orders

    Returns:
        JSON with list of orders
    """
    status = request.args.get('status')
    customer_id = request.args.get('customer_id')
    open_only = request.args.get('open_only', '').lower() == 'true'

    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'orders': [],
            'count': 0,
            'message': 'Order services not available',
        })

    service = _get_order_service()

    if open_only:
        orders = service.get_open_orders()
    elif status:
        orders = service.get_orders_by_status(status)
    elif customer_id:
        orders = service.get_orders_by_customer(customer_id)
    else:
        # Return all orders
        orders = list(service._orders.values())

    return jsonify({
        'orders': orders,
        'count': len(orders),
    })


@orders_bp.route('', methods=['POST'])
def create_order():
    """
    Create a new customer order.

    Request body:
    {
        "customer_id": "CUST-001",
        "customer_name": "ACME Corp",
        "requested_delivery_date": "2024-03-15",
        "priority_class": "B",
        "shipping_method": "standard",
        "notes": "Rush order"
    }

    Returns:
        JSON with created order
    """
    data = request.get_json() or {}

    if not ORDER_SERVICES_AVAILABLE:
        # Fallback response
        order_id = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        return jsonify({
            'order_id': order_id,
            'order_number': f"SO-{order_id[-6:]}",
            'customer_id': data.get('customer_id'),
            'customer_name': data.get('customer_name'),
            'status': 'draft',
            'created_at': datetime.utcnow().isoformat(),
            'available': False,
            'message': 'Order services not available, using fallback',
        }), 201

    service = _get_order_service()

    # Parse requested date
    requested_date = None
    if data.get('requested_delivery_date'):
        try:
            requested_date = date.fromisoformat(data['requested_delivery_date'])
        except (ValueError, TypeError):
            pass

    order_request = OrderCreateRequest(
        customer_id=data.get('customer_id', 'unknown'),
        customer_name=data.get('customer_name', 'Unknown Customer'),
        requested_delivery_date=requested_date,
        priority_class=data.get('priority_class', 'B'),
        shipping_method=data.get('shipping_method', 'standard'),
        notes=data.get('notes', ''),
    )

    order = service.create_order(order_request)

    return jsonify(order), 201


@orders_bp.route('/<order_id>', methods=['GET'])
def get_order(order_id: str):
    """
    Get order by ID.

    Returns:
        JSON with order details
    """
    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()
    order = service.get_order(order_id)

    if not order:
        return jsonify({'error': 'Order not found'}), 404

    return jsonify(order)


@orders_bp.route('/<order_id>/lines', methods=['POST'])
def add_order_line(order_id: str):
    """
    Add a line item to an order.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "part_name": "Standard 2x4 Brick",
        "quantity": 100,
        "unit_price": 0.50,
        "quality_level": "standard",
        "is_rush": false
    }

    Returns:
        JSON with added line item
    """
    data = request.get_json() or {}

    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()

    line_request = OrderLineRequest(
        part_id=data.get('part_id', ''),
        part_name=data.get('part_name', ''),
        quantity=int(data.get('quantity', 1)),
        unit_price=float(data.get('unit_price', 0.0)),
        quality_level=data.get('quality_level', 'standard'),
        is_rush=data.get('is_rush', False),
    )

    line = service.add_line(order_id, line_request)

    if not line:
        return jsonify({
            'error': 'Could not add line. Order not found or in wrong status.',
        }), 400

    return jsonify(line), 201


@orders_bp.route('/<order_id>/status', methods=['PUT'])
def update_order_status(order_id: str):
    """
    Update order status (submit, confirm, release, cancel).

    Request body:
    {
        "action": "submit" | "confirm" | "release" | "cancel",
        "promised_date": "2024-03-15",  // Required for confirm
        "reason": "Out of stock"         // Required for cancel
    }

    Returns:
        JSON with updated order
    """
    data = request.get_json() or {}
    action = data.get('action', '').lower()

    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()

    if action == 'submit':
        order = service.submit_order(order_id)
    elif action == 'confirm':
        promised_date_str = data.get('promised_date')
        if not promised_date_str:
            return jsonify({'error': 'promised_date required for confirm'}), 400
        try:
            promised_date = date.fromisoformat(promised_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        order = service.confirm_order(order_id, promised_date)
    elif action == 'release':
        order = service.release_order(order_id)
    elif action == 'cancel':
        reason = data.get('reason', 'No reason provided')
        order = service.cancel_order(order_id, reason)
    else:
        return jsonify({
            'error': f'Invalid action: {action}. Use submit, confirm, release, or cancel.',
        }), 400

    if not order:
        return jsonify({'error': 'Order not found or action not allowed'}), 404

    return jsonify(order)


@orders_bp.route('/<order_id>/atp', methods=['GET'])
def check_atp(order_id: str):
    """
    Check Available-to-Promise for order lines.

    Returns inventory availability for each line item.

    Returns:
        JSON with ATP results for each line
    """
    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()
    order = service.get_order(order_id)

    if not order:
        return jsonify({'error': 'Order not found'}), 404

    global _atp_service
    if not _atp_service:
        return jsonify({
            'error': 'ATP service not available',
        }), 503

    results = []
    for line in order.get('lines', []):
        atp_result = _atp_service.check_availability(
            line['part_id'],
            line['quantity_ordered'],
            date.fromisoformat(order['requested_delivery_date']) if order.get('requested_delivery_date') else None,
            order.get('shipping_method', 'standard'),
        )
        results.append({
            'line_id': line['line_id'],
            'part_id': line['part_id'],
            'quantity_ordered': line['quantity_ordered'],
            'atp': atp_result.to_dict(),
        })

    all_available = all(r['atp']['can_fulfill'] for r in results)

    return jsonify({
        'order_id': order_id,
        'order_number': order.get('order_number'),
        'all_available': all_available,
        'line_results': results,
        'inventory_summary': _atp_service.get_inventory_summary(),
    })


@orders_bp.route('/<order_id>/ctp', methods=['GET'])
def check_ctp(order_id: str):
    """
    Check Capable-to-Promise for order lines.

    Returns production capability for each line item when
    inventory is insufficient.

    Returns:
        JSON with CTP results for each line
    """
    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()
    order = service.get_order(order_id)

    if not order:
        return jsonify({'error': 'Order not found'}), 404

    global _ctp_service
    if not _ctp_service:
        return jsonify({
            'error': 'CTP service not available',
        }), 503

    results = []
    for line in order.get('lines', []):
        ctp_result = _ctp_service.check_production_capability(
            line['part_id'],
            line['quantity_ordered'],
            date.fromisoformat(order['requested_delivery_date']) if order.get('requested_delivery_date') else None,
            order.get('priority_class', 'B'),
        )
        results.append({
            'line_id': line['line_id'],
            'part_id': line['part_id'],
            'quantity_ordered': line['quantity_ordered'],
            'ctp': ctp_result.to_dict(),
        })

    all_can_produce = all(r['ctp']['can_produce'] for r in results)

    # Find earliest delivery across all lines
    delivery_dates = [
        r['ctp']['delivery_date']
        for r in results
        if r['ctp'].get('delivery_date')
    ]
    earliest_full_delivery = max(delivery_dates) if delivery_dates else None

    return jsonify({
        'order_id': order_id,
        'order_number': order.get('order_number'),
        'all_can_produce': all_can_produce,
        'earliest_full_delivery': earliest_full_delivery,
        'line_results': results,
    })


@orders_bp.route('/<order_id>/promise', methods=['POST'])
def calculate_promise(order_id: str):
    """
    Calculate best promise date using ATP+CTP.

    Combines inventory availability (ATP) and production capability (CTP)
    to determine the optimal promise date.

    Request body:
    {
        "strategy": "fastest" | "cheapest" | "balanced"
    }

    Returns:
        JSON with recommended promise date and fulfillment plan
    """
    data = request.get_json() or {}
    strategy = data.get('strategy', 'balanced')

    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Order services not available',
        }), 503

    service = _get_order_service()
    order = service.get_order(order_id)

    if not order:
        return jsonify({'error': 'Order not found'}), 404

    global _atp_service, _ctp_service

    fulfillment_plan = []
    latest_date = date.today()

    for line in order.get('lines', []):
        requested_date = None
        if order.get('requested_delivery_date'):
            requested_date = date.fromisoformat(order['requested_delivery_date'])

        # First try ATP
        atp_result = None
        if _atp_service:
            atp_result = _atp_service.check_availability(
                line['part_id'],
                line['quantity_ordered'],
                requested_date,
            )

        # If ATP can't fulfill, try CTP
        ctp_result = None
        if (not atp_result or not atp_result.can_fulfill) and _ctp_service:
            ctp_result = _ctp_service.check_production_capability(
                line['part_id'],
                line['quantity_ordered'],
                requested_date,
            )

        # Determine best fulfillment
        if atp_result and atp_result.can_fulfill:
            source = 'inventory'
            promise_date = atp_result.available_date
            confidence = 0.95
        elif ctp_result and ctp_result.can_produce:
            source = 'production'
            promise_date = ctp_result.delivery_date
            confidence = ctp_result.confidence
        else:
            source = 'unavailable'
            promise_date = None
            confidence = 0.0

        if promise_date and promise_date > latest_date:
            latest_date = promise_date

        fulfillment_plan.append({
            'line_id': line['line_id'],
            'part_id': line['part_id'],
            'quantity': line['quantity_ordered'],
            'source': source,
            'promise_date': promise_date.isoformat() if promise_date else None,
            'confidence': confidence,
            'atp_result': atp_result.to_dict() if atp_result else None,
            'ctp_result': ctp_result.to_dict() if ctp_result else None,
        })

    all_available = all(p['source'] != 'unavailable' for p in fulfillment_plan)

    return jsonify({
        'order_id': order_id,
        'order_number': order.get('order_number'),
        'strategy': strategy,
        'can_fulfill': all_available,
        'recommended_promise_date': latest_date.isoformat() if all_available else None,
        'fulfillment_plan': fulfillment_plan,
        'summary': {
            'from_inventory': sum(1 for p in fulfillment_plan if p['source'] == 'inventory'),
            'from_production': sum(1 for p in fulfillment_plan if p['source'] == 'production'),
            'unavailable': sum(1 for p in fulfillment_plan if p['source'] == 'unavailable'),
        },
    })


@orders_bp.route('/summary', methods=['GET'])
def get_order_summary():
    """
    Get order summary statistics.

    Returns:
        JSON with order statistics
    """
    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'summary': {
                'total_orders': 0,
                'by_status': {},
                'open_orders': 0,
                'late_orders': 0,
            },
            'available': False,
        })

    service = _get_order_service()
    summary = service.get_order_summary()

    return jsonify({
        'summary': summary,
        'available': True,
    })


@orders_bp.route('/late', methods=['GET'])
def get_late_orders():
    """
    Get orders past their promised delivery date.

    Returns:
        JSON with list of late orders
    """
    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'late_orders': [],
            'count': 0,
        })

    service = _get_order_service()
    late = service.get_late_orders()

    return jsonify({
        'late_orders': late,
        'count': len(late),
    })


@orders_bp.route('/due-soon', methods=['GET'])
def get_due_soon():
    """
    Get orders due within specified days.

    Query params:
    - days: Number of days to look ahead (default: 7)

    Returns:
        JSON with list of orders due soon
    """
    days = int(request.args.get('days', 7))

    if not ORDER_SERVICES_AVAILABLE:
        return jsonify({
            'due_soon': [],
            'count': 0,
            'days': days,
        })

    service = _get_order_service()
    due_soon = service.get_due_soon(days)

    return jsonify({
        'due_soon': due_soon,
        'count': len(due_soon),
        'days': days,
    })


@orders_bp.route('/atp/check', methods=['POST'])
def check_atp_direct():
    """
    Direct ATP check without an existing order.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100,
        "requested_date": "2024-03-15",
        "shipping_method": "standard"
    }

    Returns:
        JSON with ATP result
    """
    data = request.get_json() or {}

    # Initialize services if needed
    _get_order_service()

    global _atp_service
    if not _atp_service:
        return jsonify({
            'error': 'ATP service not available',
            'available': False,
        }), 503

    part_id = data.get('part_id', '')
    quantity = int(data.get('quantity', 1))
    shipping_method = data.get('shipping_method', 'standard')

    requested_date = None
    if data.get('requested_date'):
        try:
            requested_date = date.fromisoformat(data['requested_date'])
        except ValueError:
            pass

    result = _atp_service.check_availability(
        part_id,
        quantity,
        requested_date,
        shipping_method,
    )

    return jsonify({
        'atp_result': result.to_dict(),
        'available': True,
    })


@orders_bp.route('/ctp/check', methods=['POST'])
def check_ctp_direct():
    """
    Direct CTP check without an existing order.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100,
        "requested_date": "2024-03-15",
        "priority": "B"
    }

    Returns:
        JSON with CTP result
    """
    data = request.get_json() or {}

    # Initialize services if needed
    _get_order_service()

    global _ctp_service
    if not _ctp_service:
        return jsonify({
            'error': 'CTP service not available',
            'available': False,
        }), 503

    part_id = data.get('part_id', '')
    quantity = int(data.get('quantity', 1))
    priority = data.get('priority', 'B')

    requested_date = None
    if data.get('requested_date'):
        try:
            requested_date = date.fromisoformat(data['requested_date'])
        except ValueError:
            pass

    result = _ctp_service.check_production_capability(
        part_id,
        quantity,
        requested_date,
        priority,
    )

    return jsonify({
        'ctp_result': result.to_dict(),
        'available': True,
    })


@orders_bp.route('/atp/inventory', methods=['GET'])
def get_inventory_summary():
    """
    Get inventory summary for ATP.

    Returns:
        JSON with inventory statistics
    """
    # Initialize services if needed
    _get_order_service()

    global _atp_service
    if not _atp_service:
        return jsonify({
            'error': 'ATP service not available',
        }), 503

    return jsonify({
        'inventory_summary': _atp_service.get_inventory_summary(),
    })


@orders_bp.route('/ctp/capacity', methods=['GET'])
def get_capacity_summary():
    """
    Get capacity summary for CTP.

    Query params:
    - work_center_id: Optional filter by work center
    - days: Days ahead to check (default: 14)

    Returns:
        JSON with capacity utilization
    """
    work_center_id = request.args.get('work_center_id')
    days = int(request.args.get('days', 14))

    # Initialize services if needed
    _get_order_service()

    global _ctp_service
    if not _ctp_service:
        return jsonify({
            'error': 'CTP service not available',
        }), 503

    summary = _ctp_service.get_capacity_summary(work_center_id, days)

    return jsonify({
        'capacity_summary': summary,
        'days_ahead': days,
    })
