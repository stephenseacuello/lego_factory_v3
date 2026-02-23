"""
Suppliers Routes - Supply Chain API Endpoints

LegoMCP World-Class Manufacturing System v5.0
Phase 22: Supply Chain Integration

Provides:
- Supplier management
- Supplier scorecard
- Automated procurement
- Quality collaboration
- EDI integration
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template
import uuid

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


# Dashboard Page Routes
@suppliers_bp.route('/page', methods=['GET'])
def suppliers_page():
    """Render suppliers dashboard page."""
    return render_template('pages/supply_chain/suppliers.html')


@suppliers_bp.route('/dashboard', methods=['GET'])
def supply_chain_dashboard_page():
    """Render supply chain dashboard page."""
    return render_template('pages/supply_chain/supply_chain_dashboard.html')


@suppliers_bp.route('/inventory', methods=['GET'])
def inventory_page():
    """Render inventory dashboard page."""
    return render_template('pages/supply_chain/inventory_dashboard.html')

# Try to import supply chain services
try:
    from services.supply_chain.supplier_portal import SupplierPortalService
    SUPPLY_CHAIN_AVAILABLE = True
except ImportError:
    SUPPLY_CHAIN_AVAILABLE = False

# In-memory storage
_suppliers = {
    'SUP-001': {
        'supplier_id': 'SUP-001',
        'name': 'FilamentCo',
        'category': 'raw_material',
        'products': ['PLA Filament', 'PETG Filament'],
        'status': 'approved',
        'rating': 4.5,
        'created_at': '2023-01-15',
    },
    'SUP-002': {
        'supplier_id': 'SUP-002',
        'name': 'PrintParts Inc',
        'category': 'components',
        'products': ['Nozzles', 'Extruders'],
        'status': 'approved',
        'rating': 4.2,
        'created_at': '2023-03-20',
    },
}

_purchase_orders = {}


@suppliers_bp.route('/status', methods=['GET'])
def get_supply_chain_status():
    """Get supply chain system status."""
    return jsonify({
        'available': True,
        'capabilities': {
            'supplier_management': True,
            'auto_procurement': True,
            'supplier_quality': True,
            'edi_integration': True,
            'supplier_portal': True,
        },
        'active_suppliers': len([s for s in _suppliers.values() if s['status'] == 'approved']),
        'pending_orders': len(_purchase_orders),
    })


@suppliers_bp.route('/', methods=['GET'])
def list_suppliers():
    """List all suppliers."""
    category = request.args.get('category')
    status = request.args.get('status')

    suppliers = list(_suppliers.values())

    if category:
        suppliers = [s for s in suppliers if s['category'] == category]
    if status:
        suppliers = [s for s in suppliers if s['status'] == status]

    return jsonify({
        'suppliers': suppliers,
        'count': len(suppliers),
    })


@suppliers_bp.route('/', methods=['POST'])
def create_supplier():
    """
    Create a new supplier.

    Request body:
    {
        "name": "NewSupplier Inc",
        "category": "raw_material",
        "products": ["Material A"],
        "contact": {"email": "...", "phone": "..."},
        "address": {...}
    }
    """
    data = request.get_json() or {}

    supplier_id = f"SUP-{str(uuid.uuid4())[:4].upper()}"

    supplier = {
        'supplier_id': supplier_id,
        'name': data.get('name'),
        'category': data.get('category', 'general'),
        'products': data.get('products', []),
        'contact': data.get('contact', {}),
        'address': data.get('address', {}),
        'status': 'pending_approval',
        'rating': None,
        'created_at': datetime.utcnow().isoformat(),
    }

    _suppliers[supplier_id] = supplier

    return jsonify({
        'success': True,
        'supplier': supplier,
    }), 201


@suppliers_bp.route('/<supplier_id>', methods=['GET'])
def get_supplier(supplier_id: str):
    """Get supplier details."""
    supplier = _suppliers.get(supplier_id)
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404
    return jsonify(supplier)


@suppliers_bp.route('/<supplier_id>/scorecard', methods=['GET'])
def get_supplier_scorecard(supplier_id: str):
    """
    Get supplier scorecard.

    Returns performance metrics for supplier.
    """
    supplier = _suppliers.get(supplier_id)
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404

    scorecard = {
        'supplier_id': supplier_id,
        'supplier_name': supplier.get('name'),
        'period': 'last_12_months',
        'overall_score': 85.5,
        'rating': 'A',
        'metrics': {
            'quality': {
                'score': 92.0,
                'weight': 0.3,
                'details': {
                    'defect_rate_ppm': 150,
                    'lots_accepted': 48,
                    'lots_rejected': 2,
                    'ncrs_issued': 1,
                },
            },
            'delivery': {
                'score': 88.0,
                'weight': 0.25,
                'details': {
                    'on_time_rate': 0.88,
                    'avg_lead_time_days': 5,
                    'orders_delivered': 50,
                    'orders_late': 6,
                },
            },
            'cost': {
                'score': 75.0,
                'weight': 0.2,
                'details': {
                    'price_vs_market': 1.05,
                    'price_stability': 'stable',
                    'cost_reduction_yoy': -2,
                },
            },
            'responsiveness': {
                'score': 90.0,
                'weight': 0.15,
                'details': {
                    'avg_response_time_hours': 4,
                    'quote_turnaround_days': 1,
                    'issue_resolution_days': 2,
                },
            },
            'sustainability': {
                'score': 80.0,
                'weight': 0.1,
                'details': {
                    'iso14001_certified': True,
                    'carbon_disclosure': True,
                    'recycled_content_percent': 25,
                },
            },
        },
        'trend': 'improving',
        'recommendations': [
            'Consider for increased order volume',
            'Request cost reduction proposal',
        ],
    }

    return jsonify({'scorecard': scorecard})


@suppliers_bp.route('/<supplier_id>/quality', methods=['GET'])
def get_supplier_quality(supplier_id: str):
    """Get supplier quality history."""
    supplier = _suppliers.get(supplier_id)
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404

    quality = {
        'supplier_id': supplier_id,
        'summary': {
            'total_lots': 50,
            'accepted': 48,
            'rejected': 2,
            'acceptance_rate': 96.0,
            'defect_ppm': 150,
        },
        'recent_inspections': [
            {
                'lot_number': 'LOT-2024-050',
                'date': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                'material': 'PLA-RED',
                'result': 'accepted',
                'defects_found': 0,
            },
            {
                'lot_number': 'LOT-2024-049',
                'date': (datetime.utcnow() - timedelta(days=10)).isoformat(),
                'material': 'PLA-BLUE',
                'result': 'accepted',
                'defects_found': 0,
            },
        ],
        'ncrs': [
            {
                'ncr_id': 'NCR-2024-001',
                'date': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'issue': 'Diameter out of spec',
                'lot': 'LOT-2024-030',
                'status': 'closed',
                'corrective_action': 'Supplier adjusted extrusion line',
            },
        ],
        'certifications': [
            {'name': 'ISO 9001:2015', 'valid_until': '2025-06-30'},
            {'name': 'ISO 14001:2015', 'valid_until': '2025-06-30'},
        ],
    }

    return jsonify({'quality': quality})


@suppliers_bp.route('/orders', methods=['GET'])
def list_purchase_orders():
    """List purchase orders."""
    status = request.args.get('status')
    supplier_id = request.args.get('supplier_id')

    orders = list(_purchase_orders.values())

    if status:
        orders = [o for o in orders if o['status'] == status]
    if supplier_id:
        orders = [o for o in orders if o['supplier_id'] == supplier_id]

    return jsonify({
        'orders': orders,
        'count': len(orders),
    })


@suppliers_bp.route('/orders', methods=['POST'])
def create_purchase_order():
    """
    Create a purchase order.

    Request body:
    {
        "supplier_id": "SUP-001",
        "lines": [
            {"material_id": "PLA-RED", "quantity": 10, "unit": "kg", "unit_price": 25.00}
        ],
        "delivery_date": "2024-02-15",
        "notes": "..."
    }
    """
    data = request.get_json() or {}

    po_id = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

    lines = data.get('lines', [])
    total = sum(l.get('quantity', 0) * l.get('unit_price', 0) for l in lines)

    order = {
        'po_id': po_id,
        'supplier_id': data.get('supplier_id'),
        'lines': lines,
        'total_amount': total,
        'currency': 'USD',
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat(),
        'delivery_date': data.get('delivery_date'),
        'notes': data.get('notes'),
    }

    _purchase_orders[po_id] = order

    return jsonify({
        'success': True,
        'order': order,
    }), 201


@suppliers_bp.route('/orders/<po_id>', methods=['GET'])
def get_purchase_order(po_id: str):
    """Get purchase order details."""
    order = _purchase_orders.get(po_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    return jsonify(order)


@suppliers_bp.route('/orders/<po_id>/status', methods=['PUT'])
def update_order_status(po_id: str):
    """
    Update purchase order status.

    Request body:
    {
        "status": "confirmed|shipped|received|cancelled",
        "tracking_number": "...",
        "notes": "..."
    }
    """
    order = _purchase_orders.get(po_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    data = request.get_json() or {}

    order['status'] = data.get('status', order['status'])
    order['tracking_number'] = data.get('tracking_number')
    order['updated_at'] = datetime.utcnow().isoformat()

    if data.get('status') == 'received':
        order['received_at'] = datetime.utcnow().isoformat()

    return jsonify({
        'success': True,
        'order': order,
    })


@suppliers_bp.route('/auto-replenish', methods=['POST'])
def trigger_auto_replenishment():
    """
    Trigger automatic replenishment based on inventory levels.

    Request body:
    {
        "materials": ["PLA-RED", "PLA-BLUE"],  // Optional, all if not specified
        "threshold_type": "reorder_point|min_stock",
        "generate_orders": true
    }

    Returns:
        JSON with replenishment recommendations or generated orders
    """
    data = request.get_json() or {}

    materials = data.get('materials')
    generate = data.get('generate_orders', False)

    # Simulated inventory check and recommendations
    recommendations = [
        {
            'material_id': 'PLA-RED',
            'current_stock': 50,
            'reorder_point': 100,
            'recommended_quantity': 200,
            'preferred_supplier': 'SUP-001',
            'estimated_cost': 5000.00,
            'urgency': 'high',
        },
        {
            'material_id': 'PETG-CLEAR',
            'current_stock': 80,
            'reorder_point': 75,
            'recommended_quantity': 100,
            'preferred_supplier': 'SUP-001',
            'estimated_cost': 3500.00,
            'urgency': 'low',
        },
    ]

    if materials:
        recommendations = [r for r in recommendations if r['material_id'] in materials]

    generated_orders = []
    if generate:
        for rec in recommendations:
            if rec['urgency'] == 'high':
                po_id = f"PO-AUTO-{str(uuid.uuid4())[:6].upper()}"
                order = {
                    'po_id': po_id,
                    'supplier_id': rec['preferred_supplier'],
                    'lines': [{
                        'material_id': rec['material_id'],
                        'quantity': rec['recommended_quantity'],
                        'unit_price': rec['estimated_cost'] / rec['recommended_quantity'],
                    }],
                    'total_amount': rec['estimated_cost'],
                    'status': 'auto_generated',
                    'created_at': datetime.utcnow().isoformat(),
                }
                _purchase_orders[po_id] = order
                generated_orders.append(order)

    return jsonify({
        'recommendations': recommendations,
        'generated_orders': generated_orders if generate else [],
        'action_required': len([r for r in recommendations if r['urgency'] == 'high']),
    })


@suppliers_bp.route('/edi/send', methods=['POST'])
def send_edi_message():
    """
    Send EDI message to supplier.

    Request body:
    {
        "supplier_id": "SUP-001",
        "message_type": "850|855|856|810",  // PO, POAck, ASN, Invoice
        "document_id": "PO-001",
        "format": "X12|EDIFACT"
    }
    """
    data = request.get_json() or {}

    message = {
        'message_id': str(uuid.uuid4())[:8],
        'supplier_id': data.get('supplier_id'),
        'message_type': data.get('message_type'),
        'document_id': data.get('document_id'),
        'format': data.get('format', 'X12'),
        'status': 'sent',
        'sent_at': datetime.utcnow().isoformat(),
    }

    return jsonify({
        'success': True,
        'message': message,
    })


@suppliers_bp.route('/collaboration/<supplier_id>/share', methods=['POST'])
def share_with_supplier(supplier_id: str):
    """
    Share data with supplier via portal.

    Request body:
    {
        "data_type": "forecast|quality_spec|drawing",
        "document_id": "DOC-001",
        "access_level": "view|download",
        "expires_in_days": 30
    }
    """
    supplier = _suppliers.get(supplier_id)
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404

    data = request.get_json() or {}

    share = {
        'share_id': str(uuid.uuid4())[:8],
        'supplier_id': supplier_id,
        'data_type': data.get('data_type'),
        'document_id': data.get('document_id'),
        'access_level': data.get('access_level', 'view'),
        'shared_at': datetime.utcnow().isoformat(),
        'expires_at': (datetime.utcnow() + timedelta(days=data.get('expires_in_days', 30))).isoformat(),
        'portal_url': f"/supplier-portal/{supplier_id}/shared/{data.get('document_id')}",
    }

    return jsonify({
        'success': True,
        'share': share,
    })
