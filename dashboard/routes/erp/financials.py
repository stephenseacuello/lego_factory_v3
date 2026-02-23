"""
Financial Management API Routes

ISA-95 Level 4 Financial Operations:
- Accounts Receivable (AR) management
- Accounts Payable (AP) management
- General Ledger operations
- Financial reporting and analysis

Standards:
- GAAP/IFRS compliance
- SOX internal controls
- ASC 310 (Receivables) / ASC 405 (Liabilities)
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import date, datetime, timedelta
from typing import Optional

from services.erp.ar_ap_service import (
    AccountsReceivableService,
    AccountsPayableService,
    PaymentMethod,
    InvoiceStatus,
    CreditRating
)
from services.erp.gl_integration import (
    GeneralLedgerService,
    JournalEntryStatus
)

financials_bp = Blueprint('financials', __name__, url_prefix='/financials')

# Initialize services (in production, these would be injected via DI)
_gl_service: Optional[GeneralLedgerService] = None
_ar_service: Optional[AccountsReceivableService] = None
_ap_service: Optional[AccountsPayableService] = None


def get_gl_service() -> GeneralLedgerService:
    """Get or create GL service singleton."""
    global _gl_service
    if _gl_service is None:
        _gl_service = GeneralLedgerService()
    return _gl_service


def get_ar_service() -> AccountsReceivableService:
    """Get or create AR service singleton."""
    global _ar_service
    if _ar_service is None:
        _ar_service = AccountsReceivableService(gl_service=get_gl_service())
    return _ar_service


def get_ap_service() -> AccountsPayableService:
    """Get or create AP service singleton."""
    global _ap_service
    if _ap_service is None:
        _ap_service = AccountsPayableService(gl_service=get_gl_service())
    return _ap_service


# ---------------------------------------------------------------------------
# Dashboard Page Routes
# ---------------------------------------------------------------------------

@financials_bp.route('/dashboard/page', methods=['GET'])
def financials_dashboard():
    """Render main financials dashboard page."""
    return render_template('pages/erp/financials_dashboard.html')


@financials_bp.route('/ar/page', methods=['GET'])
def ar_page():
    """Render Accounts Receivable dashboard page."""
    return render_template('pages/erp/ar_dashboard.html')


@financials_bp.route('/ap/page', methods=['GET'])
def ap_page():
    """Render Accounts Payable dashboard page."""
    return render_template('pages/erp/ap_dashboard.html')


@financials_bp.route('/gl/page', methods=['GET'])
def gl_page():
    """Render General Ledger dashboard page."""
    return render_template('pages/erp/gl_dashboard.html')


# ---------------------------------------------------------------------------
# ACCOUNTS RECEIVABLE (AR)
# ---------------------------------------------------------------------------

# Customer Management

@financials_bp.route('/ar/customers', methods=['GET'])
def list_ar_customers():
    """List all customers."""
    service = get_ar_service()
    customers = list(service._customers.values())

    return jsonify([
        {
            'customer_id': c.customer_id,
            'name': c.name,
            'credit_limit': float(c.credit_limit),
            'credit_rating': c.credit_rating.value,
            'payment_terms': c.payment_terms,
            'balance': float(service.get_customer_balance(c.customer_id)),
            'is_active': c.is_active
        }
        for c in customers
    ])


@financials_bp.route('/ar/customers', methods=['POST'])
def create_ar_customer():
    """
    Create a new customer.

    Request Body:
        {
            "name": "LEGO Builders Inc.",
            "credit_limit": 50000,
            "payment_terms": 30,
            "email": "billing@legobuilders.com",
            "address": "123 Brick Lane"
        }
    """
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Customer name is required'}), 400

    service = get_ar_service()
    customer = service.add_customer(
        name=data['name'],
        credit_limit=data.get('credit_limit', 10000),
        payment_terms=data.get('payment_terms', 30),
        email=data.get('email', ''),
        address=data.get('address', ''),
        tax_id=data.get('tax_id', '')
    )

    return jsonify({
        'customer_id': customer.customer_id,
        'name': customer.name,
        'message': 'Customer created successfully'
    }), 201


@financials_bp.route('/ar/customers/<customer_id>', methods=['GET'])
def get_ar_customer(customer_id: str):
    """Get customer details."""
    service = get_ar_service()
    customer = service.get_customer(customer_id)

    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    return jsonify({
        'customer_id': customer.customer_id,
        'name': customer.name,
        'credit_limit': float(customer.credit_limit),
        'credit_rating': customer.credit_rating.value,
        'payment_terms': customer.payment_terms,
        'contact_email': customer.contact_email,
        'billing_address': customer.billing_address,
        'tax_id': customer.tax_id,
        'balance': float(service.get_customer_balance(customer.customer_id)),
        'is_active': customer.is_active,
        'created_at': customer.created_at.isoformat()
    })


# Invoice Management

@financials_bp.route('/ar/invoices', methods=['GET'])
def list_invoices():
    """
    List all invoices with optional filtering.

    Query Parameters:
        customer_id: Filter by customer
        status: Filter by status
        limit: Max results
    """
    service = get_ar_service()
    invoices = list(service._invoices.values())

    customer_id = request.args.get('customer_id')
    status = request.args.get('status')

    if customer_id:
        invoices = [i for i in invoices if i.customer_id == customer_id]

    if status:
        try:
            status_enum = InvoiceStatus(status)
            invoices = [i for i in invoices if i.status == status_enum]
        except ValueError:
            pass

    limit = int(request.args.get('limit', 100))
    invoices = sorted(invoices, key=lambda x: x.invoice_date, reverse=True)[:limit]

    return jsonify([
        {
            'invoice_id': i.invoice_id,
            'invoice_number': i.invoice_number,
            'customer_name': i.customer_name,
            'invoice_date': i.invoice_date.isoformat(),
            'due_date': i.due_date.isoformat(),
            'total_amount': float(i.total_amount),
            'balance_due': float(i.balance_due),
            'status': i.status.value
        }
        for i in invoices
    ])


@financials_bp.route('/ar/invoices', methods=['POST'])
def create_invoice():
    """
    Create a new customer invoice.

    Request Body:
        {
            "customer_id": "uuid",
            "line_items": [
                {"description": "LEGO Bricks 2x4", "qty": 100, "price": 0.25}
            ],
            "sales_order_ref": "SO-001234",
            "tax_rate": 0.08
        }
    """
    data = request.get_json()

    if not data.get('customer_id'):
        return jsonify({'error': 'customer_id is required'}), 400
    if not data.get('line_items'):
        return jsonify({'error': 'line_items is required'}), 400

    service = get_ar_service()

    invoice_date = None
    if data.get('invoice_date'):
        invoice_date = date.fromisoformat(data['invoice_date'])

    try:
        invoice = service.create_invoice(
            customer_id=data['customer_id'],
            line_items=data['line_items'],
            invoice_date=invoice_date,
            sales_order_ref=data.get('sales_order_ref', ''),
            tax_rate=data.get('tax_rate', 0.08),
            notes=data.get('notes', '')
        )

        return jsonify({
            'invoice_id': invoice.invoice_id,
            'invoice_number': invoice.invoice_number,
            'total_amount': float(invoice.total_amount),
            'message': 'Invoice created successfully'
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@financials_bp.route('/ar/invoices/<invoice_id>', methods=['GET'])
def get_invoice(invoice_id: str):
    """Get invoice details."""
    service = get_ar_service()
    invoice = service._invoices.get(invoice_id)

    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404

    return jsonify({
        'invoice_id': invoice.invoice_id,
        'invoice_number': invoice.invoice_number,
        'customer_id': invoice.customer_id,
        'customer_name': invoice.customer_name,
        'invoice_date': invoice.invoice_date.isoformat(),
        'due_date': invoice.due_date.isoformat(),
        'line_items': invoice.line_items,
        'subtotal': float(invoice.subtotal),
        'tax_amount': float(invoice.tax_amount),
        'total_amount': float(invoice.total_amount),
        'amount_paid': float(invoice.amount_paid),
        'balance_due': float(invoice.balance_due),
        'status': invoice.status.value,
        'payment_terms': invoice.payment_terms,
        'sales_order_ref': invoice.sales_order_ref,
        'payments': invoice.payments,
        'notes': invoice.notes
    })


@financials_bp.route('/ar/invoices/<invoice_id>/send', methods=['POST'])
def send_invoice(invoice_id: str):
    """Mark invoice as sent to customer."""
    service = get_ar_service()
    invoice = service.send_invoice(invoice_id)

    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404

    return jsonify({
        'invoice_id': invoice.invoice_id,
        'status': invoice.status.value,
        'message': 'Invoice marked as sent'
    })


@financials_bp.route('/ar/invoices/<invoice_id>/payments', methods=['POST'])
def apply_payment(invoice_id: str):
    """
    Apply payment to an invoice.

    Request Body:
        {
            "amount": 1500.00,
            "payment_method": "ach",
            "reference": "CHK-12345"
        }
    """
    data = request.get_json()

    if 'amount' not in data:
        return jsonify({'error': 'amount is required'}), 400

    try:
        payment_method = PaymentMethod(data.get('payment_method', 'ach'))
    except ValueError:
        return jsonify({'error': f"Invalid payment method. Valid: {[m.value for m in PaymentMethod]}"}), 400

    payment_date = None
    if data.get('payment_date'):
        payment_date = date.fromisoformat(data['payment_date'])

    service = get_ar_service()
    payment = service.apply_payment(
        invoice_id=invoice_id,
        amount=data['amount'],
        payment_method=payment_method,
        payment_date=payment_date,
        reference=data.get('reference', '')
    )

    if not payment:
        return jsonify({'error': 'Invoice not found'}), 404

    return jsonify({
        'payment_id': payment.payment_id,
        'amount': float(payment.amount),
        'message': 'Payment applied successfully'
    }), 201


# AR Reports

@financials_bp.route('/ar/aging', methods=['GET'])
def get_ar_aging():
    """
    Get AR aging report.

    Query Parameters:
        as_of: Date for aging calculation (default: today)
    """
    as_of_date = None
    if request.args.get('as_of'):
        as_of_date = date.fromisoformat(request.args.get('as_of'))

    service = get_ar_service()
    report = service.get_aging_report(as_of_date)

    return jsonify(report)


@financials_bp.route('/ar/forecast', methods=['GET'])
def get_ar_forecast():
    """
    Get cash receipts forecast.

    Query Parameters:
        days: Forecast horizon (default: 30)
    """
    days = int(request.args.get('days', 30))

    service = get_ar_service()
    forecast = service.forecast_cash_receipts(days)

    return jsonify(forecast)


@financials_bp.route('/ar/summary', methods=['GET'])
def get_ar_summary():
    """Get AR summary statistics."""
    service = get_ar_service()

    invoices = list(service._invoices.values())
    customers = list(service._customers.values())

    total_ar = sum(i.balance_due for i in invoices if i.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
    overdue = sum(
        i.balance_due for i in invoices
        if i.status == InvoiceStatus.OVERDUE or (i.due_date < date.today() and i.balance_due > 0)
    )

    return jsonify({
        'total_ar': float(total_ar),
        'overdue_amount': float(overdue),
        'total_customers': len(customers),
        'active_invoices': len([i for i in invoices if i.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]]),
        'dso': service.calculate_dso()
    })


# ---------------------------------------------------------------------------
# ACCOUNTS PAYABLE (AP)
# ---------------------------------------------------------------------------

# Vendor Management (for AP purposes)

@financials_bp.route('/ap/vendors', methods=['GET'])
def list_ap_vendors():
    """List all AP vendors."""
    service = get_ap_service()
    vendors = list(service._vendors.values())

    return jsonify([
        {
            'vendor_id': v.vendor_id,
            'name': v.name,
            'payment_terms': v.payment_terms,
            'preferred_method': v.preferred_payment_method.value,
            'balance': float(service.get_vendor_balance(v.vendor_id)),
            'is_1099': v.is_1099_vendor,
            'is_active': v.is_active
        }
        for v in vendors
    ])


@financials_bp.route('/ap/vendors', methods=['POST'])
def create_ap_vendor():
    """
    Create a new AP vendor.

    Request Body:
        {
            "name": "Plastics Supply Co.",
            "payment_terms": 30,
            "is_1099": true,
            "email": "billing@plastics.com"
        }
    """
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'Vendor name is required'}), 400

    service = get_ap_service()
    vendor = service.add_vendor(
        name=data['name'],
        payment_terms=data.get('payment_terms', 30),
        is_1099=data.get('is_1099', False),
        email=data.get('email', ''),
        address=data.get('address', ''),
        tax_id=data.get('tax_id', '')
    )

    return jsonify({
        'vendor_id': vendor.vendor_id,
        'name': vendor.name,
        'message': 'Vendor created successfully'
    }), 201


# Bill Management

@financials_bp.route('/ap/bills', methods=['GET'])
def list_bills():
    """
    List all bills with optional filtering.

    Query Parameters:
        vendor_id: Filter by vendor
        status: Filter by status
        limit: Max results
    """
    service = get_ap_service()
    bills = list(service._bills.values())

    vendor_id = request.args.get('vendor_id')
    status = request.args.get('status')

    if vendor_id:
        bills = [b for b in bills if b.vendor_id == vendor_id]

    if status:
        try:
            status_enum = InvoiceStatus(status)
            bills = [b for b in bills if b.status == status_enum]
        except ValueError:
            pass

    limit = int(request.args.get('limit', 100))
    bills = sorted(bills, key=lambda x: x.bill_date, reverse=True)[:limit]

    return jsonify([
        {
            'bill_id': b.bill_id,
            'bill_number': b.bill_number,
            'vendor_name': b.vendor_name,
            'bill_date': b.bill_date.isoformat(),
            'due_date': b.due_date.isoformat(),
            'total_amount': float(b.total_amount),
            'balance_due': float(b.balance_due),
            'status': b.status.value
        }
        for b in bills
    ])


@financials_bp.route('/ap/bills', methods=['POST'])
def create_bill():
    """
    Create a new vendor bill.

    Request Body:
        {
            "vendor_id": "uuid",
            "line_items": [
                {"description": "ABS Plastic Pellets", "amount": 5000, "account": "1100"}
            ],
            "bill_number": "INV-12345",
            "purchase_order_ref": "PO-001234"
        }
    """
    data = request.get_json()

    if not data.get('vendor_id'):
        return jsonify({'error': 'vendor_id is required'}), 400
    if not data.get('line_items'):
        return jsonify({'error': 'line_items is required'}), 400

    service = get_ap_service()

    bill_date = None
    if data.get('bill_date'):
        bill_date = date.fromisoformat(data['bill_date'])

    try:
        bill = service.create_bill(
            vendor_id=data['vendor_id'],
            line_items=data['line_items'],
            bill_date=bill_date,
            bill_number=data.get('bill_number', ''),
            purchase_order_ref=data.get('purchase_order_ref', ''),
            notes=data.get('notes', '')
        )

        return jsonify({
            'bill_id': bill.bill_id,
            'bill_number': bill.bill_number,
            'total_amount': float(bill.total_amount),
            'message': 'Bill created successfully'
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@financials_bp.route('/ap/bills/<bill_id>', methods=['GET'])
def get_bill(bill_id: str):
    """Get bill details."""
    service = get_ap_service()
    bill = service._bills.get(bill_id)

    if not bill:
        return jsonify({'error': 'Bill not found'}), 404

    return jsonify({
        'bill_id': bill.bill_id,
        'bill_number': bill.bill_number,
        'vendor_id': bill.vendor_id,
        'vendor_name': bill.vendor_name,
        'bill_date': bill.bill_date.isoformat(),
        'due_date': bill.due_date.isoformat(),
        'line_items': bill.line_items,
        'subtotal': float(bill.subtotal),
        'tax_amount': float(bill.tax_amount),
        'total_amount': float(bill.total_amount),
        'amount_paid': float(bill.amount_paid),
        'balance_due': float(bill.balance_due),
        'status': bill.status.value,
        'payment_terms': bill.payment_terms,
        'purchase_order_ref': bill.purchase_order_ref,
        'payments': bill.payments,
        'notes': bill.notes
    })


@financials_bp.route('/ap/bills/<bill_id>/approve', methods=['POST'])
def approve_bill(bill_id: str):
    """Approve a bill for payment."""
    data = request.get_json()
    approver = data.get('approver', 'system')

    service = get_ap_service()
    bill = service.approve_bill(bill_id, approver)

    if not bill:
        return jsonify({'error': 'Bill not found'}), 404

    return jsonify({
        'bill_id': bill.bill_id,
        'status': bill.status.value,
        'message': 'Bill approved for payment'
    })


@financials_bp.route('/ap/bills/<bill_id>/pay', methods=['POST'])
def pay_bill(bill_id: str):
    """
    Process payment for a bill.

    Request Body:
        {
            "payment_method": "ach",
            "amount": 5000.00,
            "reference": "ACH-12345"
        }
    """
    data = request.get_json()

    try:
        payment_method = PaymentMethod(data.get('payment_method', 'ach'))
    except ValueError:
        return jsonify({'error': f"Invalid payment method. Valid: {[m.value for m in PaymentMethod]}"}), 400

    payment_date = None
    if data.get('payment_date'):
        payment_date = date.fromisoformat(data['payment_date'])

    service = get_ap_service()
    payment = service.process_payment(
        bill_id=bill_id,
        payment_method=payment_method,
        amount=data.get('amount'),
        payment_date=payment_date,
        reference=data.get('reference', '')
    )

    if not payment:
        return jsonify({'error': 'Bill not found'}), 404

    return jsonify({
        'payment_id': payment.payment_id,
        'amount': float(payment.amount),
        'message': 'Payment processed successfully'
    }), 201


# AP Reports

@financials_bp.route('/ap/aging', methods=['GET'])
def get_ap_aging():
    """Get AP aging report."""
    as_of_date = None
    if request.args.get('as_of'):
        as_of_date = date.fromisoformat(request.args.get('as_of'))

    service = get_ap_service()
    report = service.get_aging_report(as_of_date)

    return jsonify(report)


@financials_bp.route('/ap/schedule', methods=['GET'])
def get_payment_schedule():
    """
    Get payment schedule for upcoming bills.

    Query Parameters:
        start: Start date
        end: End date
    """
    start_date = None
    end_date = None

    if request.args.get('start'):
        start_date = date.fromisoformat(request.args.get('start'))
    if request.args.get('end'):
        end_date = date.fromisoformat(request.args.get('end'))

    service = get_ap_service()
    schedule = service.get_payment_schedule(start_date, end_date)

    return jsonify(schedule)


@financials_bp.route('/ap/1099', methods=['GET'])
def get_1099_summary():
    """
    Get 1099 summary for tax year.

    Query Parameters:
        year: Tax year (default: current year)
    """
    year = int(request.args.get('year', datetime.now().year))

    service = get_ap_service()
    summary = service.get_1099_summary(year)

    return jsonify(summary)


@financials_bp.route('/ap/summary', methods=['GET'])
def get_ap_summary():
    """Get AP summary statistics."""
    service = get_ap_service()

    bills = list(service._bills.values())
    vendors = list(service._vendors.values())

    total_ap = sum(b.balance_due for b in bills if b.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
    overdue = sum(
        b.balance_due for b in bills
        if b.due_date < date.today() and b.balance_due > 0 and b.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]
    )

    return jsonify({
        'total_ap': float(total_ap),
        'overdue_amount': float(overdue),
        'total_vendors': len(vendors),
        'active_bills': len([b for b in bills if b.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]]),
        'dpo': service.calculate_dpo()
    })


# ---------------------------------------------------------------------------
# GENERAL LEDGER (GL)
# ---------------------------------------------------------------------------

@financials_bp.route('/gl/accounts', methods=['GET'])
def list_gl_accounts():
    """List all GL accounts."""
    service = get_gl_service()

    accounts = sorted(service._accounts.values(), key=lambda a: a.account_number)

    return jsonify([
        {
            'account_id': a.account_id,
            'account_number': a.account_number,
            'name': a.name,
            'type': a.account_type.value,
            'balance': float(service.get_account_balance(a.account_number)),
            'is_active': a.is_active
        }
        for a in accounts
    ])


@financials_bp.route('/gl/accounts/<account_number>/balance', methods=['GET'])
def get_account_balance(account_number: str):
    """Get account balance."""
    as_of_date = None
    if request.args.get('as_of'):
        as_of_date = date.fromisoformat(request.args.get('as_of'))

    service = get_gl_service()
    balance = service.get_account_balance(account_number, as_of_date)

    return jsonify({
        'account_number': account_number,
        'balance': float(balance),
        'as_of': (as_of_date or date.today()).isoformat()
    })


@financials_bp.route('/gl/journal-entries', methods=['GET'])
def list_journal_entries():
    """
    List journal entries with filtering.

    Query Parameters:
        start: Start date
        end: End date
        status: Entry status
        account: Account number
    """
    service = get_gl_service()

    start_date = None
    end_date = None
    status = None

    if request.args.get('start'):
        start_date = date.fromisoformat(request.args.get('start'))
    if request.args.get('end'):
        end_date = date.fromisoformat(request.args.get('end'))
    if request.args.get('status'):
        try:
            status = JournalEntryStatus(request.args.get('status'))
        except ValueError:
            pass

    entries = service.get_journal_entries(
        start_date=start_date,
        end_date=end_date,
        status=status,
        account_number=request.args.get('account')
    )

    return jsonify([
        {
            'entry_id': e.entry_id,
            'entry_number': e.entry_number,
            'entry_date': e.entry_date.isoformat(),
            'description': e.description,
            'status': e.status.value,
            'total_debit': sum(float(l.debit_amount) for l in e.lines),
            'total_credit': sum(float(l.credit_amount) for l in e.lines),
            'source': e.source
        }
        for e in entries
    ])


@financials_bp.route('/gl/journal-entries', methods=['POST'])
def create_journal_entry():
    """
    Create a manual journal entry.

    Request Body:
        {
            "description": "Monthly depreciation",
            "lines": [
                {"account": "6300", "debit": 1000, "description": "Depreciation expense"},
                {"account": "1510", "credit": 1000, "description": "Accumulated depreciation"}
            ]
        }
    """
    data = request.get_json()

    if not data.get('description'):
        return jsonify({'error': 'description is required'}), 400
    if not data.get('lines'):
        return jsonify({'error': 'lines is required'}), 400

    entry_date = None
    if data.get('entry_date'):
        entry_date = date.fromisoformat(data['entry_date'])

    service = get_gl_service()

    try:
        entry = service.create_journal_entry(
            description=data['description'],
            lines=data['lines'],
            entry_date=entry_date,
            source=data.get('source', 'manual'),
            source_document=data.get('source_document', ''),
            created_by=data.get('created_by', 'user')
        )

        return jsonify({
            'entry_id': entry.entry_id,
            'entry_number': entry.entry_number,
            'status': entry.status.value,
            'message': 'Journal entry created'
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@financials_bp.route('/gl/trial-balance', methods=['GET'])
def get_trial_balance():
    """Get trial balance report."""
    as_of_date = None
    if request.args.get('as_of'):
        as_of_date = date.fromisoformat(request.args.get('as_of'))

    service = get_gl_service()
    tb = service.get_trial_balance(as_of_date)

    return jsonify({
        'as_of_date': tb.as_of_date.isoformat(),
        'period': tb.period,
        'accounts': tb.accounts,
        'total_debits': float(tb.total_debits),
        'total_credits': float(tb.total_credits),
        'is_balanced': tb.is_balanced
    })


@financials_bp.route('/gl/income-statement', methods=['GET'])
def get_income_statement():
    """
    Get income statement.

    Query Parameters:
        start: Period start date
        end: Period end date
    """
    if not request.args.get('start') or not request.args.get('end'):
        # Default to current month
        today = date.today()
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    else:
        start_date = date.fromisoformat(request.args.get('start'))
        end_date = date.fromisoformat(request.args.get('end'))

    service = get_gl_service()
    statement = service.get_income_statement(start_date, end_date)

    return jsonify(statement)


# ---------------------------------------------------------------------------
# Financial Summary
# ---------------------------------------------------------------------------

@financials_bp.route('/summary', methods=['GET'])
def get_financial_summary():
    """Get comprehensive financial summary."""
    ar_service = get_ar_service()
    ap_service = get_ap_service()
    gl_service = get_gl_service()

    ar_invoices = list(ar_service._invoices.values())
    ap_bills = list(ap_service._bills.values())

    total_ar = sum(i.balance_due for i in ar_invoices if i.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
    total_ap = sum(b.balance_due for b in ap_bills if b.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED])

    # Get key balances
    cash = gl_service.get_account_balance("1000")
    inventory = (
        gl_service.get_account_balance("1100") +
        gl_service.get_account_balance("1110") +
        gl_service.get_account_balance("1120")
    )

    return jsonify({
        'cash_balance': float(cash),
        'total_ar': float(total_ar),
        'total_ap': float(total_ap),
        'net_working_capital': float(cash + total_ar + inventory - total_ap),
        'inventory_value': float(inventory),
        'ar_dso': ar_service.calculate_dso(),
        'ap_dpo': ap_service.calculate_dpo(),
        'ar_customers': len(ar_service._customers),
        'ap_vendors': len(ap_service._vendors),
        'open_invoices': len([i for i in ar_invoices if i.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]]),
        'open_bills': len([b for b in ap_bills if b.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]])
    })
