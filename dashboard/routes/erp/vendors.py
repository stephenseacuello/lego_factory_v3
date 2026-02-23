"""
Vendor/Supplier Management API Routes

ISA-95 Level 4 Supplier Management:
- Vendor master CRUD operations
- Performance scorecarding
- Certification tracking
- Quote and contract management

RESTful API endpoints for enterprise vendor management.
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import date, datetime
from typing import Optional

from services.erp.vendor_service import (
    get_vendor_service,
    VendorStatus,
    VendorType,
    PaymentTerms,
    RiskLevel,
    CertificationType
)

vendors_bp = Blueprint('vendors', __name__, url_prefix='/vendors')


# ---------------------------------------------------------------------------
# Dashboard Page Routes
# ---------------------------------------------------------------------------

@vendors_bp.route('/page', methods=['GET'])
def vendors_page():
    """Render vendor management dashboard page."""
    return render_template('pages/erp/vendor_dashboard.html')


@vendors_bp.route('/scorecard/<vendor_id>/page', methods=['GET'])
def vendor_scorecard_page(vendor_id: str):
    """Render vendor scorecard page."""
    return render_template('pages/erp/vendor_scorecard.html', vendor_id=vendor_id)


# ---------------------------------------------------------------------------
# Vendor CRUD Operations
# ---------------------------------------------------------------------------

@vendors_bp.route('', methods=['GET'])
def list_vendors():
    """
    List all vendors with optional filtering.

    Query Parameters:
        status: Filter by vendor status (approved, preferred, etc.)
        type: Filter by vendor type (raw_material, component, etc.)
        risk: Filter by risk level (low, medium, high, critical)
        search: Search by name or code
        limit: Maximum results (default 100)

    Returns:
        JSON array of vendor objects
    """
    service = get_vendor_service()

    # Parse filters
    status = None
    if request.args.get('status'):
        try:
            status = VendorStatus(request.args.get('status'))
        except ValueError:
            pass

    vendor_type = None
    if request.args.get('type'):
        try:
            vendor_type = VendorType(request.args.get('type'))
        except ValueError:
            pass

    risk_level = None
    if request.args.get('risk'):
        try:
            risk_level = RiskLevel(request.args.get('risk'))
        except ValueError:
            pass

    search = request.args.get('search', '')
    limit = int(request.args.get('limit', 100))

    vendors = service.list_vendors(
        status=status,
        vendor_type=vendor_type,
        risk_level=risk_level,
        search=search,
        limit=limit
    )

    return jsonify([
        {
            'vendor_id': v.vendor_id,
            'vendor_code': v.vendor_code,
            'name': v.name,
            'vendor_type': v.vendor_type.value,
            'status': v.status.value,
            'risk_level': v.risk_level.value,
            'payment_terms': v.payment_terms.value,
            'lead_time_days': v.lead_time_days,
            'contacts_count': len(v.contacts),
            'certifications_count': len(v.certifications),
            'created_at': v.created_at.isoformat()
        }
        for v in vendors
    ])


@vendors_bp.route('', methods=['POST'])
def create_vendor():
    """
    Create a new vendor.

    Request Body:
        {
            "code": "SUP001",
            "name": "Acme Plastics Inc.",
            "vendor_type": "raw_material",
            "payment_terms": "net_30",
            "lead_time_days": 14,
            "tax_id": "12-3456789",
            "currency": "USD",
            "categories": ["plastics", "abs", "pla"]
        }

    Returns:
        Created vendor object
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('code'):
        return jsonify({'error': 'Vendor code is required'}), 400
    if not data.get('name'):
        return jsonify({'error': 'Vendor name is required'}), 400
    if not data.get('vendor_type'):
        return jsonify({'error': 'Vendor type is required'}), 400

    try:
        vendor_type = VendorType(data['vendor_type'])
    except ValueError:
        return jsonify({'error': f"Invalid vendor_type. Valid: {[t.value for t in VendorType]}"}), 400

    payment_terms = PaymentTerms.NET_30
    if data.get('payment_terms'):
        try:
            payment_terms = PaymentTerms(data['payment_terms'])
        except ValueError:
            pass

    service = get_vendor_service()

    try:
        vendor = service.create_vendor(
            code=data['code'],
            name=data['name'],
            vendor_type=vendor_type,
            payment_terms=payment_terms,
            **{k: v for k, v in data.items() if k not in ['code', 'name', 'vendor_type', 'payment_terms']}
        )

        return jsonify({
            'vendor_id': vendor.vendor_id,
            'vendor_code': vendor.vendor_code,
            'name': vendor.name,
            'status': vendor.status.value,
            'message': 'Vendor created successfully'
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@vendors_bp.route('/<vendor_id>', methods=['GET'])
def get_vendor(vendor_id: str):
    """
    Get vendor details by ID.

    Returns:
        Complete vendor object with contacts, addresses, certifications
    """
    service = get_vendor_service()
    vendor = service.get_vendor(vendor_id)

    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'vendor_id': vendor.vendor_id,
        'vendor_code': vendor.vendor_code,
        'name': vendor.name,
        'legal_name': vendor.legal_name,
        'vendor_type': vendor.vendor_type.value,
        'status': vendor.status.value,
        'risk_level': vendor.risk_level.value,
        'payment_terms': vendor.payment_terms.value,
        'currency': vendor.currency,
        'lead_time_days': vendor.lead_time_days,
        'minimum_order': float(vendor.minimum_order),
        'credit_limit': float(vendor.credit_limit),
        'tax_id': vendor.tax_id,
        'duns_number': vendor.duns_number,
        'website': vendor.website,
        'is_1099': vendor.is_1099,
        'categories': vendor.categories,
        'notes': vendor.notes,
        'contacts': [
            {
                'contact_id': c.contact_id,
                'name': c.name,
                'title': c.title,
                'email': c.email,
                'phone': c.phone,
                'is_primary': c.is_primary
            }
            for c in vendor.contacts
        ],
        'addresses': [
            {
                'address_id': a.address_id,
                'type': a.address_type,
                'street_1': a.street_1,
                'street_2': a.street_2,
                'city': a.city,
                'state': a.state,
                'postal_code': a.postal_code,
                'country': a.country,
                'is_default': a.is_default
            }
            for a in vendor.addresses
        ],
        'certifications': [
            {
                'certification_id': c.certification_id,
                'type': c.certification_type.value,
                'certificate_number': c.certificate_number,
                'issue_date': c.issue_date.isoformat(),
                'expiry_date': c.expiry_date.isoformat(),
                'issuing_body': c.issuing_body,
                'verified': c.verified
            }
            for c in vendor.certifications
        ],
        'approved_by': vendor.approved_by,
        'approved_date': vendor.approved_date.isoformat() if vendor.approved_date else None,
        'created_at': vendor.created_at.isoformat(),
        'updated_at': vendor.updated_at.isoformat()
    })


@vendors_bp.route('/<vendor_id>', methods=['PUT'])
def update_vendor(vendor_id: str):
    """
    Update vendor attributes.

    Request Body:
        Any vendor attributes to update
    """
    data = request.get_json()
    service = get_vendor_service()

    vendor = service.update_vendor(vendor_id, **data)

    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'vendor_id': vendor.vendor_id,
        'vendor_code': vendor.vendor_code,
        'message': 'Vendor updated successfully'
    })


@vendors_bp.route('/<vendor_id>/approve', methods=['POST'])
def approve_vendor(vendor_id: str):
    """
    Approve a vendor for purchasing.

    Request Body:
        {
            "approver": "john.smith",
            "notes": "Approved after quality audit"
        }
    """
    data = request.get_json()
    approver = data.get('approver', 'system')
    notes = data.get('notes', '')

    service = get_vendor_service()
    vendor = service.approve_vendor(vendor_id, approver, notes)

    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'vendor_id': vendor.vendor_id,
        'status': vendor.status.value,
        'approved_by': vendor.approved_by,
        'approved_date': vendor.approved_date.isoformat() if vendor.approved_date else None,
        'message': 'Vendor approved successfully'
    })


# ---------------------------------------------------------------------------
# Contact Management
# ---------------------------------------------------------------------------

@vendors_bp.route('/<vendor_id>/contacts', methods=['POST'])
def add_contact(vendor_id: str):
    """
    Add a contact to a vendor.

    Request Body:
        {
            "name": "John Doe",
            "email": "john@acme.com",
            "phone": "555-1234",
            "title": "Sales Manager",
            "is_primary": true
        }
    """
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Contact name is required'}), 400

    service = get_vendor_service()
    contact = service.add_contact(
        vendor_id,
        name=data['name'],
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        title=data.get('title', ''),
        is_primary=data.get('is_primary', False)
    )

    if not contact:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'contact_id': contact.contact_id,
        'name': contact.name,
        'message': 'Contact added successfully'
    }), 201


# ---------------------------------------------------------------------------
# Address Management
# ---------------------------------------------------------------------------

@vendors_bp.route('/<vendor_id>/addresses', methods=['POST'])
def add_address(vendor_id: str):
    """
    Add an address to a vendor.

    Request Body:
        {
            "address_type": "shipping",
            "street_1": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62701",
            "country": "USA"
        }
    """
    data = request.get_json()

    required = ['address_type', 'street_1', 'city', 'state', 'postal_code']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    service = get_vendor_service()
    address = service.add_address(vendor_id, **data)

    if not address:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'address_id': address.address_id,
        'message': 'Address added successfully'
    }), 201


# ---------------------------------------------------------------------------
# Certification Management
# ---------------------------------------------------------------------------

@vendors_bp.route('/<vendor_id>/certifications', methods=['POST'])
def add_certification(vendor_id: str):
    """
    Add a certification to a vendor.

    Request Body:
        {
            "cert_type": "ISO 9001",
            "certificate_number": "ISO-2024-12345",
            "issue_date": "2024-01-15",
            "expiry_date": "2027-01-14",
            "issuing_body": "BSI Group"
        }
    """
    data = request.get_json()

    required = ['cert_type', 'certificate_number', 'issue_date', 'expiry_date', 'issuing_body']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    try:
        cert_type = CertificationType(data['cert_type'])
    except ValueError:
        return jsonify({
            'error': f"Invalid certification type. Valid: {[c.value for c in CertificationType]}"
        }), 400

    issue_date = date.fromisoformat(data['issue_date'])
    expiry_date = date.fromisoformat(data['expiry_date'])

    service = get_vendor_service()
    cert = service.add_certification(
        vendor_id,
        cert_type=cert_type,
        certificate_number=data['certificate_number'],
        issue_date=issue_date,
        expiry_date=expiry_date,
        issuing_body=data['issuing_body'],
        document_url=data.get('document_url', '')
    )

    if not cert:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify({
        'certification_id': cert.certification_id,
        'type': cert.certification_type.value,
        'message': 'Certification added successfully'
    }), 201


@vendors_bp.route('/<vendor_id>/certifications/<cert_id>/verify', methods=['POST'])
def verify_certification(vendor_id: str, cert_id: str):
    """Verify a vendor certification."""
    data = request.get_json()
    verified_by = data.get('verified_by', 'system')

    service = get_vendor_service()
    success = service.verify_certification(vendor_id, cert_id, verified_by)

    if not success:
        return jsonify({'error': 'Vendor or certification not found'}), 404

    return jsonify({'message': 'Certification verified successfully'})


@vendors_bp.route('/certifications/expiring', methods=['GET'])
def get_expiring_certifications():
    """
    Get list of expiring certifications.

    Query Parameters:
        days: Days ahead to check (default 90)
    """
    days = int(request.args.get('days', 90))

    service = get_vendor_service()
    expiring = service.get_expiring_certifications(days)

    return jsonify(expiring)


# ---------------------------------------------------------------------------
# Performance Tracking
# ---------------------------------------------------------------------------

@vendors_bp.route('/<vendor_id>/deliveries', methods=['POST'])
def record_delivery(vendor_id: str):
    """
    Record a delivery for performance tracking.

    Request Body:
        {
            "po_number": "PO-001234",
            "on_time": true,
            "qty_ordered": 1000,
            "qty_received": 998,
            "defects": 2,
            "delivery_date": "2024-01-20"
        }
    """
    data = request.get_json()

    required = ['po_number', 'qty_ordered', 'qty_received']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    delivery_date = None
    if data.get('delivery_date'):
        delivery_date = date.fromisoformat(data['delivery_date'])

    service = get_vendor_service()

    try:
        delivery = service.record_delivery(
            vendor_id,
            po_number=data['po_number'],
            on_time=data.get('on_time', True),
            qty_ordered=data['qty_ordered'],
            qty_received=data['qty_received'],
            defects=data.get('defects', 0),
            delivery_date=delivery_date,
            notes=data.get('notes', '')
        )

        return jsonify({
            'delivery_id': delivery['delivery_id'],
            'message': 'Delivery recorded successfully'
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@vendors_bp.route('/<vendor_id>/performance', methods=['GET'])
def get_performance(vendor_id: str):
    """
    Calculate and return vendor performance metrics.

    Query Parameters:
        period: Period in YYYY-MM format (default: current month)
    """
    period = request.args.get('period')

    service = get_vendor_service()
    performance = service.calculate_performance(vendor_id, period)

    if not performance:
        return jsonify({'error': 'Vendor not found or no data'}), 404

    return jsonify({
        'period': performance.period,
        'quality_score': performance.quality_score,
        'delivery_score': performance.delivery_score,
        'cost_score': performance.cost_score,
        'service_score': performance.service_score,
        'overall_score': performance.overall_score,
        'on_time_deliveries': performance.on_time_deliveries,
        'total_deliveries': performance.total_deliveries,
        'defect_ppm': performance.defect_ppm,
        'invoice_accuracy': performance.invoice_accuracy
    })


@vendors_bp.route('/<vendor_id>/scorecard', methods=['GET'])
def get_scorecard(vendor_id: str):
    """Get comprehensive vendor scorecard with trends and recommendations."""
    service = get_vendor_service()
    scorecard = service.get_vendor_scorecard(vendor_id)

    if not scorecard:
        return jsonify({'error': 'Vendor not found'}), 404

    return jsonify(scorecard)


# ---------------------------------------------------------------------------
# Summary and Reports
# ---------------------------------------------------------------------------

@vendors_bp.route('/summary', methods=['GET'])
def get_vendor_summary():
    """Get summary statistics of all vendors."""
    service = get_vendor_service()
    summary = service.get_vendor_summary()

    return jsonify(summary)


@vendors_bp.route('/types', methods=['GET'])
def get_vendor_types():
    """Get list of valid vendor types."""
    return jsonify([t.value for t in VendorType])


@vendors_bp.route('/statuses', methods=['GET'])
def get_vendor_statuses():
    """Get list of valid vendor statuses."""
    return jsonify([s.value for s in VendorStatus])


@vendors_bp.route('/payment-terms', methods=['GET'])
def get_payment_terms():
    """Get list of valid payment terms."""
    return jsonify([p.value for p in PaymentTerms])


@vendors_bp.route('/certification-types', methods=['GET'])
def get_certification_types():
    """Get list of valid certification types."""
    return jsonify([c.value for c in CertificationType])
