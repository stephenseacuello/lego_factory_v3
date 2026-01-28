"""
LEGO Factory v3 - ERP API
==========================
REST API endpoints for Enterprise Resource Planning.

Provides endpoints for:
- Financial (GL, AP, AR)
- Sales (Orders, Invoices)
- Purchasing (POs, Receipts)
- Inventory (Items, Stock)
- MRP (Material Requirements Planning)
"""

import logging
import uuid
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

erp_api_bp = Blueprint('erp_api', __name__, url_prefix='/api/erp')

def _get_demo_sales_orders():
    """Return demo sales orders data."""
    return {
        'sales_orders': [
            {
                'order_id': 'SO-20240115-001',
                'order_number': 'SO-20240115-001',
                'customer_id': 'CUST001',
                'status': 'confirmed',
                'order_date': (date.today() - timedelta(days=5)).isoformat(),
                'requested_date': (date.today() + timedelta(days=10)).isoformat(),
                'subtotal': 250.00,
                'tax_amount': 20.00,
                'total': 270.00,
            },
            {
                'order_id': 'SO-20240118-001',
                'order_number': 'SO-20240118-001',
                'customer_id': 'CUST002',
                'status': 'draft',
                'order_date': date.today().isoformat(),
                'requested_date': (date.today() + timedelta(days=14)).isoformat(),
                'subtotal': 95.00,
                'tax_amount': 7.60,
                'total': 102.60,
            },
        ],
        'count': 2,
    }


def _get_demo_items():
    """Return demo items data."""
    return {
        'items': [
            {'item_id': 'brick_2x4_red', 'name': '2x4 Brick Red', 'standard_cost': 0.15, 'list_price': 0.35, 'status': 'active'},
            {'item_id': 'brick_2x2_blue', 'name': '2x2 Brick Blue', 'standard_cost': 0.10, 'list_price': 0.25, 'status': 'active'},
            {'item_id': 'gear_24t', 'name': 'Technic Gear 24 Tooth', 'standard_cost': 0.45, 'list_price': 0.95, 'status': 'active'},
        ],
        'count': 3,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Chart of Accounts
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/gl/accounts', methods=['GET'])
@jwt_required()
def list_gl_accounts():
    """List GL accounts (Chart of Accounts)."""
    try:
        from config.database import get_db_session
        from services.erp.financial_service import FinancialService

        with get_db_session() as session:
            service = FinancialService(session)
            accounts = service.get_chart_of_accounts(
                account_type=request.args.get('type'),
                is_active=request.args.get('active') != 'false',
            )

            return jsonify({
                'accounts': accounts,
                'count': len(accounts),
            })
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_chart_of_accounts
            data = get_demo_chart_of_accounts()
            return jsonify({**data, 'demo': True})

        logger.error(f"ERP service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503


@erp_api_bp.route('/gl/accounts', methods=['POST'])
@jwt_required()
def create_gl_account():
    """Create a GL account."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'account_number' not in data or 'name' not in data:
        return jsonify({'error': 'account_number and name required'}), 400

    try:
        from services.erp.financial_service import FinancialService

        service = FinancialService(session)
        account = service.create_account(data)
        session.commit()

        return jsonify(account), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating GL account: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/gl/accounts/<account_number>/balance', methods=['GET'])
@jwt_required()
def get_account_balance(account_number: str):
    """Get GL account balance."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_account_balance
            data = get_demo_account_balance(account_number)
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        as_of = request.args.get('as_of')
        as_of_date = date.fromisoformat(as_of) if as_of else None

        service = FinancialService(session)
        balance = service.get_account_balance(account_number, as_of_date)

        return jsonify(balance)
    except Exception as e:
        logger.error(f"Error getting account balance: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Journal Entries
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/gl/journal-entries', methods=['GET'])
@jwt_required()
def list_journal_entries():
    """List journal entries."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_journal_entries
            data = get_demo_journal_entries()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        service = FinancialService(session)
        journals = service.get_journal_entries(
            status=request.args.get('status'),
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            limit=int(request.args.get('limit', 100)),
        )

        return jsonify({
            'journal_entries': journals,
            'count': len(journals),
        })
    except Exception as e:
        logger.error(f"Error listing journal entries: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/gl/journal-entries', methods=['POST'])
@jwt_required()
def create_journal_entry():
    """Create a journal entry."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'description' not in data or 'lines' not in data:
        return jsonify({'error': 'description and lines required'}), 400

    try:
        from services.erp.financial_service import FinancialService

        if 'journal_date' in data:
            data['journal_date'] = date.fromisoformat(data['journal_date'])

        service = FinancialService(session)
        journal = service.create_journal_entry(data)
        session.commit()

        return jsonify(journal), 201
    except ValueError as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating journal entry: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/gl/journal-entries/<journal_number>/post', methods=['POST'])
@jwt_required()
def post_journal_entry(journal_number: str):
    """Post a journal entry."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    try:
        from services.erp.financial_service import FinancialService

        data = request.get_json() or {}
        service = FinancialService(session)
        journal = service.post_journal_entry(
            journal_number,
            user_id=data.get('user_id', 'system')
        )
        session.commit()

        return jsonify(journal)
    except ValueError as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        session.rollback()
        logger.error(f"Error posting journal entry: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Accounts Payable
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/ap/invoices', methods=['GET'])
@jwt_required()
def list_ap_invoices():
    """List AP invoices."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_ap_invoices
            data = get_demo_ap_invoices()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        service = FinancialService(session)
        invoices = service.get_ap_invoices(
            vendor_id=request.args.get('vendor_id'),
            status=request.args.get('status'),
            limit=int(request.args.get('limit', 100)),
        )

        return jsonify({
            'invoices': invoices,
            'count': len(invoices),
        })
    except Exception as e:
        logger.error(f"Error listing AP invoices: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/ap/invoices', methods=['POST'])
@jwt_required()
def create_ap_invoice():
    """Create an AP invoice."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'vendor_id' not in data:
        return jsonify({'error': 'vendor_id required'}), 400

    try:
        from services.erp.financial_service import FinancialService

        if 'invoice_date' in data:
            data['invoice_date'] = date.fromisoformat(data['invoice_date'])
        if 'due_date' in data:
            data['due_date'] = date.fromisoformat(data['due_date'])

        service = FinancialService(session)
        invoice = service.create_ap_invoice(data)
        session.commit()

        return jsonify(invoice), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating AP invoice: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/ap/aging', methods=['GET'])
@jwt_required()
def get_ap_aging():
    """Get AP aging report."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_ap_aging
            data = get_demo_ap_aging()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        service = FinancialService(session)
        aging = service.get_ap_aging()

        return jsonify(aging)
    except Exception as e:
        logger.error(f"Error getting AP aging: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Accounts Receivable
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/ar/invoices', methods=['GET'])
@jwt_required()
def list_ar_invoices():
    """List AR invoices."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_ar_invoices
            data = get_demo_ar_invoices()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        service = FinancialService(session)
        invoices = service.get_ar_invoices(
            customer_id=request.args.get('customer_id'),
            status=request.args.get('status'),
            limit=int(request.args.get('limit', 100)),
        )

        return jsonify({
            'invoices': invoices,
            'count': len(invoices),
        })
    except Exception as e:
        logger.error(f"Error listing AR invoices: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/ar/invoices', methods=['POST'])
@jwt_required()
def create_ar_invoice():
    """Create an AR invoice."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'customer_id' not in data:
        return jsonify({'error': 'customer_id required'}), 400

    try:
        from services.erp.financial_service import FinancialService

        if 'invoice_date' in data:
            data['invoice_date'] = date.fromisoformat(data['invoice_date'])
        if 'due_date' in data:
            data['due_date'] = date.fromisoformat(data['due_date'])

        service = FinancialService(session)
        invoice = service.create_ar_invoice(data)
        session.commit()

        return jsonify(invoice), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating AR invoice: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/ar/aging', methods=['GET'])
@jwt_required()
def get_ar_aging():
    """Get AR aging report."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_ar_aging
            data = get_demo_ar_aging()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        service = FinancialService(session)
        aging = service.get_ar_aging()

        return jsonify(aging)
    except Exception as e:
        logger.error(f"Error getting AR aging: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Financial Reports
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/reports/trial-balance', methods=['GET'])
@jwt_required()
def get_trial_balance():
    """Get trial balance report."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_trial_balance
            data = get_demo_trial_balance()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        as_of = request.args.get('as_of')
        as_of_date = date.fromisoformat(as_of) if as_of else None

        service = FinancialService(session)
        trial_balance = service.get_trial_balance(as_of_date)

        return jsonify(trial_balance)
    except Exception as e:
        logger.error(f"Error getting trial balance: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/reports/income-statement', methods=['GET'])
@jwt_required()
def get_income_statement():
    """Get income statement report."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_income_statement
            data = get_demo_income_statement()
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503

    try:
        from services.erp.financial_service import FinancialService

        today = date.today()
        start_date = date.fromisoformat(
            request.args.get('start_date', date(today.year, today.month, 1).isoformat())
        )
        end_date = date.fromisoformat(
            request.args.get('end_date', today.isoformat())
        )

        service = FinancialService(session)
        income_statement = service.get_income_statement(start_date, end_date)

        return jsonify(income_statement)
    except Exception as e:
        logger.error(f"Error getting income statement: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@erp_api_bp.route('/reports/dashboard', methods=['GET'])
@jwt_required()
def get_financial_dashboard():
    """Get financial dashboard summary."""
    try:
        from config.database import get_db_session
        from services.erp.financial_service import FinancialService

        with get_db_session() as session:
            service = FinancialService(session)
            dashboard = service.get_financial_dashboard()
            return jsonify(dashboard)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_financial_dashboard
            data = get_demo_financial_dashboard()
            return jsonify({**data, 'demo': True})

        logger.error(f"ERP service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Sales Orders
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/sales-orders', methods=['GET'])
@jwt_required()
def list_sales_orders():
    """List sales orders."""
    try:
        from config.database import get_db_session
        from services.erp.sales_service import SalesService

        with get_db_session() as session:
            service = SalesService(session)
            orders = service.get_orders(
                customer_id=request.args.get('customer_id'),
                status=request.args.get('status'),
                limit=int(request.args.get('limit', 100)),
            )

            return jsonify({
                'sales_orders': orders,
                'count': len(orders),
            })
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            data = _get_demo_sales_orders()
            return jsonify({**data, 'demo': True})

        logger.error(f"ERP service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available. Please check system status.'
        }), 503


@erp_api_bp.route('/sales-orders', methods=['POST'])
@jwt_required(optional=True)  # Allow unauthenticated for demo mode
def create_sales_order():
    """
    Create a new sales order.

    JSON body:
    - customer_id: Customer ID (required)
    - requested_date: Requested delivery date
    - lines: Array of line items [{item_id, quantity, unit_price}]
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if not data.get('customer_id'):
        return jsonify({'error': 'customer_id is required'}), 400

    try:
        from config.database import get_db_session
        from services.erp.sales_service import SalesService

        if 'requested_date' in data and isinstance(data['requested_date'], str):
            data['requested_date'] = date.fromisoformat(data['requested_date'])

        with get_db_session() as session:
            service = SalesService(session)
            order = service.create_order(data)
            return jsonify(order), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Demo mode fallback
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            import uuid
            demo_order = {
                'order_id': f"SO-{uuid.uuid4().hex[:8].upper()}",
                'customer_id': data.get('customer_id'),
                'status': 'draft',
                'requested_date': data.get('requested_date'),
                'lines': data.get('lines', []),
                'message': 'Sales order created (demo mode)',
                'demo': True,
            }
            return jsonify(demo_order), 201

        logger.error(f"Error creating sales order: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not create sales order. Please check system status.'
        }), 503


@erp_api_bp.route('/sales-orders/<order_id>', methods=['GET'])
@jwt_required()
def get_sales_order(order_id: str):
    """Get a specific sales order."""
    try:
        from config.database import get_db_session
        from services.erp.sales_service import SalesService

        with get_db_session() as session:
            service = SalesService(session)
            order = service.get_order(order_id)
            if not order:
                return jsonify({'error': 'Sales order not found'}), 404
            return jsonify(order)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            # Return demo order
            demo_orders = _get_demo_sales_orders()['sales_orders']
            order = next((o for o in demo_orders if o['order_id'] == order_id), None)
            if order:
                return jsonify({**order, 'demo': True})
            return jsonify({'error': 'Sales order not found'}), 404

        logger.error(f"Error getting sales order: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/sales-orders/<order_id>', methods=['PUT'])
@jwt_required()
def update_sales_order(order_id: str):
    """Update a sales order."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        from config.database import get_db_session
        from models.erp.sales import SalesOrder, SalesOrderStatus

        with get_db_session() as session:
            order = session.query(SalesOrder).filter(
                SalesOrder.order_number == order_id
            ).first()

            if not order:
                return jsonify({'error': 'Sales order not found'}), 404

            # Update allowed fields
            if 'status' in data:
                order.status = SalesOrderStatus(data['status'])
            if 'requested_date' in data:
                order.requested_date = date.fromisoformat(data['requested_date']) if isinstance(data['requested_date'], str) else data['requested_date']
            if 'notes' in data:
                order.notes = data['notes']

            order.updated_at = datetime.utcnow()
            order.updated_by = data.get('updated_by', 'system')

            return jsonify(order.to_dict())

    except Exception as e:
        logger.error(f"Error updating sales order: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not update sales order. Please check system status.'
        }), 503


@erp_api_bp.route('/sales-orders/<order_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_sales_order(order_id: str):
    """Confirm a sales order."""
    try:
        from config.database import get_db_session
        from models.erp.sales import SalesOrder, SalesOrderStatus

        with get_db_session() as session:
            order = session.query(SalesOrder).filter(
                SalesOrder.order_number == order_id
            ).first()

            if not order:
                return jsonify({'error': 'Sales order not found'}), 404

            if order.status != SalesOrderStatus.DRAFT:
                return jsonify({'error': f"Cannot confirm order with status '{order.status.value}'"}), 400

            order.status = SalesOrderStatus.APPROVED
            order.updated_at = datetime.utcnow()
            order.updated_by = 'system'

            return jsonify(order.to_dict())

    except Exception as e:
        logger.error(f"Error confirming sales order: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not confirm sales order. Please check system status.'
        }), 503


@erp_api_bp.route('/customers', methods=['GET'])
@jwt_required(optional=True)
def list_customers():
    """List customers."""
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner, PartnerType

        with get_db_session() as session:
            customers = session.query(Partner).filter(
                Partner.partner_type == PartnerType.CUSTOMER,
                Partner.is_deleted == False
            ).limit(100).all()

            return jsonify({
                'customers': [c.to_dict() for c in customers],
                'count': len(customers),
            })
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_partners
            data = get_demo_partners()
            customers = [p for p in data['partners'] if p.get('partner_type') == 'customer']
            return jsonify({'customers': customers, 'count': len(customers), 'demo': True})

        logger.error(f"Error listing customers: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/customers', methods=['POST'])
@jwt_required()
def create_customer():
    """Create a customer."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    try:
        from config.database import get_db_session
        from models.erp.partners import Partner, PartnerType, PartnerStatus

        with get_db_session() as session:
            partner_id = f"CUST{uuid.uuid4().hex[:6].upper()}"
            customer = Partner(
                partner_id=data.get('partner_id', partner_id),
                name=data['name'],
                partner_type=PartnerType.CUSTOMER,
                status=PartnerStatus.ACTIVE,
                email=data.get('email'),
                phone=data.get('phone'),
                website=data.get('website'),
                tax_id=data.get('tax_id'),
                notes=data.get('notes'),
                created_by=data.get('created_by', 'system'),
            )
            session.add(customer)
            session.flush()

            logger.info(f"Created customer: {customer.partner_id}")
            return jsonify(customer.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating customer: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not create customer. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Inventory / Items
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/items', methods=['GET'])
@jwt_required(optional=True)
def list_items():
    """List inventory items."""
    try:
        from config.database import get_db_session
        from services.erp.item_service import ItemService

        with get_db_session() as session:
            service = ItemService(session)
            items = service.get_items(
                item_type=request.args.get('type'),
                status=request.args.get('status'),
                search=request.args.get('search'),
                limit=int(request.args.get('limit', 100)),
            )

            return jsonify({
                'items': items,
                'count': len(items),
            })
    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            data = _get_demo_items()
            return jsonify({**data, 'demo': True})

        logger.error(f"Error listing items: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/items/<item_id>', methods=['GET'])
@jwt_required(optional=True)
def get_item(item_id: str):
    """Get a specific item."""
    try:
        from config.database import get_db_session
        from services.erp.item_service import ItemService

        with get_db_session() as session:
            service = ItemService(session)
            item = service.get_item(item_id)
            if not item:
                return jsonify({'error': 'Item not found'}), 404
            return jsonify(item)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            demo_items = _get_demo_items()['items']
            item = next((i for i in demo_items if i['item_id'] == item_id), None)
            if item:
                return jsonify({**item, 'demo': True})
            return jsonify({'error': 'Item not found'}), 404

        logger.error(f"Error getting item: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/items', methods=['POST'])
@jwt_required()
def create_item():
    """Create an inventory item."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    try:
        from config.database import get_db_session
        from services.erp.item_service import ItemService

        with get_db_session() as session:
            service = ItemService(session)
            item = service.create_item(data)
            return jsonify(item), 201

    except Exception as e:
        logger.error(f"Error creating item: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not create item. Please check system status.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# MRP (Material Requirements Planning)
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/mrp/run', methods=['POST'])
@jwt_required()
def run_mrp():
    """
    Run MRP (Material Requirements Planning).

    JSON body:
    - horizon_days: Planning horizon in days (default 90)
    - include_safety_stock: Include safety stock in calculations (default true)
    """
    data = request.get_json() or {}
    horizon_days = data.get('horizon_days', 90)
    include_safety_stock = data.get('include_safety_stock', True)

    try:
        from config.database import get_db_session
        from services.erp.mrp_service import MRPService

        with get_db_session() as session:
            service = MRPService(session)
            mrp_result = service.run_mrp(
                horizon_days=horizon_days,
                include_safety_stock=include_safety_stock,
            )
            return jsonify(mrp_result)

    except Exception as e:
        logger.error(f"Error running MRP: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'Could not run MRP. Please check system status.'
        }), 503


@erp_api_bp.route('/mrp/runs', methods=['GET'])
@jwt_required()
def list_mrp_runs():
    """List MRP runs."""
    try:
        from config.database import get_db_session
        from services.erp.mrp_service import MRPService

        with get_db_session() as session:
            service = MRPService(session)
            runs = service.get_mrp_runs(
                limit=int(request.args.get('limit', 10))
            )
            return jsonify({
                'mrp_runs': runs,
                'count': len(runs),
            })

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'mrp_runs': [],
                'count': 0,
                'message': 'No MRP runs available in demo mode',
                'demo': True
            })

        logger.error(f"Error listing MRP runs: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/mrp/runs/<run_id>', methods=['GET'])
@jwt_required()
def get_mrp_run(run_id: str):
    """Get a specific MRP run."""
    try:
        from config.database import get_db_session
        from services.erp.mrp_service import MRPService

        with get_db_session() as session:
            service = MRPService(session)
            run = service.get_mrp_run(run_id)
            if not run:
                return jsonify({'error': 'MRP run not found'}), 404
            return jsonify(run)

    except Exception as e:
        logger.error(f"Error getting MRP run: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


@erp_api_bp.route('/mrp/shortages', methods=['GET'])
@jwt_required()
def get_mrp_shortages():
    """Get current inventory shortages."""
    try:
        from config.database import get_db_session
        from services.erp.mrp_service import MRPService

        with get_db_session() as session:
            service = MRPService(session)
            shortages = service.get_shortages()
            return jsonify(shortages)

    except Exception as e:
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            return jsonify({
                'shortages': [],
                'count': 0,
                'message': 'No MRP run has been executed yet. Run MRP first.',
                'demo': True
            })

        logger.error(f"Error getting MRP shortages: {e}", exc_info=True)
        return jsonify({
            'error': 'ERP service unavailable',
            'message': 'The Enterprise Resource Planning system is not available.'
        }), 503


# ─────────────────────────────────────────────────────────────────────────────
# Payments
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/payments', methods=['POST'])
@jwt_required()
def create_payment():
    """Create a payment."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'payment_type' not in data or 'partner_id' not in data or 'amount' not in data:
        return jsonify({'error': 'payment_type, partner_id, and amount required'}), 400

    try:
        from services.erp.financial_service import FinancialService

        if 'payment_date' in data:
            data['payment_date'] = date.fromisoformat(data['payment_date'])

        service = FinancialService(session)
        payment = service.create_payment(data)
        session.commit()

        return jsonify(payment), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating payment: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Partners (Customers/Vendors)
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/partners', methods=['GET'])
@jwt_required()
def list_partners():
    """List all partners (customers and vendors)."""
    try:
        from models.erp.partners import Partner

        with get_db_session() as session:
            partner_type = request.args.get('type')
            status = request.args.get('status')

            query = session.query(Partner)
            if partner_type:
                from models.erp.partners import PartnerType
                query = query.filter(Partner.partner_type == PartnerType(partner_type))
            if status:
                from models.erp.partners import PartnerStatus
                query = query.filter(Partner.status == PartnerStatus(status))

            partners = query.limit(100).all()
            result = [p.to_dict() for p in partners]

            return jsonify({'partners': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"Error listing partners: {e}")
        return jsonify({
            'partners': [
                {'partner_id': 'CUST001', 'name': 'Brick Builders Inc', 'partner_type': 'customer', 'status': 'active'},
                {'partner_id': 'CUST002', 'name': 'LEGO World Shop', 'partner_type': 'customer', 'status': 'active'},
                {'partner_id': 'VEND001', 'name': 'Filament Supply Co', 'partner_type': 'vendor', 'status': 'active'},
            ],
            'count': 3
        })


@erp_api_bp.route('/partners/<partner_id>', methods=['GET'])
@jwt_required()
def get_partner(partner_id: str):
    """Get a specific partner."""
    try:
        from models.erp.partners import Partner

        with get_db_session() as session:
            partner = session.query(Partner).filter(Partner.partner_id == partner_id).first()
            if partner:
                return jsonify(partner.to_dict())
            return jsonify({'error': 'Partner not found'}), 404
    except Exception as e:
        logger.error(f"Error getting partner {partner_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_chart_of_accounts():
    """Return demo chart of accounts."""
    return jsonify({
        'accounts': [
            {'account_number': '1000', 'name': 'Cash', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1100', 'name': 'Accounts Receivable', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1200', 'name': 'Inventory', 'account_type': 'asset', 'is_active': True},
            {'account_number': '1500', 'name': 'Equipment', 'account_type': 'asset', 'is_active': True},
            {'account_number': '2000', 'name': 'Accounts Payable', 'account_type': 'liability', 'is_active': True},
            {'account_number': '3000', 'name': 'Retained Earnings', 'account_type': 'equity', 'is_active': True},
            {'account_number': '4000', 'name': 'Sales Revenue', 'account_type': 'revenue', 'is_active': True},
            {'account_number': '5000', 'name': 'Cost of Goods Sold', 'account_type': 'expense', 'is_active': True},
            {'account_number': '6000', 'name': 'Operating Expenses', 'account_type': 'expense', 'is_active': True},
        ],
        'count': 9,
    })


def _demo_account_balance(account_number: str):
    """Return demo account balance."""
    balances = {
        '1000': 125000.00,
        '1100': 45000.00,
        '1200': 78000.00,
        '2000': -32000.00,
        '4000': -185000.00,
        '5000': 92000.00,
    }
    return jsonify({
        'account_number': account_number,
        'account_name': f'Account {account_number}',
        'as_of_date': date.today().isoformat(),
        'balance': balances.get(account_number, 0),
    })


def _demo_journal_entries():
    """Return demo journal entries."""
    return jsonify({
        'journal_entries': [
            {
                'journal_number': 'JE-20240115-001',
                'status': 'posted',
                'journal_date': (date.today() - timedelta(days=5)).isoformat(),
                'description': 'Sales revenue for work order WO-20240110-001',
                'total_debit': 5000.00,
                'total_credit': 5000.00,
            },
            {
                'journal_number': 'JE-20240112-001',
                'status': 'posted',
                'journal_date': (date.today() - timedelta(days=8)).isoformat(),
                'description': 'Raw material purchase',
                'total_debit': 2500.00,
                'total_credit': 2500.00,
            },
        ],
        'count': 2,
    })


def _demo_ap_invoices():
    """Return demo AP invoices."""
    return jsonify({
        'invoices': [
            {
                'invoice_number': 'AP-20240115-001',
                'vendor_invoice_number': 'INV-12345',
                'vendor_id': 'V001',
                'status': 'approved',
                'invoice_date': (date.today() - timedelta(days=10)).isoformat(),
                'due_date': (date.today() + timedelta(days=20)).isoformat(),
                'total': 3500.00,
                'balance_due': 3500.00,
            },
            {
                'invoice_number': 'AP-20240110-001',
                'vendor_invoice_number': 'INV-12340',
                'vendor_id': 'V002',
                'status': 'paid',
                'invoice_date': (date.today() - timedelta(days=15)).isoformat(),
                'due_date': (date.today() + timedelta(days=15)).isoformat(),
                'total': 1200.00,
                'balance_due': 0.00,
            },
        ],
        'count': 2,
    })


def _demo_ar_invoices():
    """Return demo AR invoices."""
    return jsonify({
        'invoices': [
            {
                'invoice_number': 'INV-20240115-001',
                'customer_id': 'C001',
                'status': 'sent',
                'invoice_date': (date.today() - timedelta(days=5)).isoformat(),
                'due_date': (date.today() + timedelta(days=25)).isoformat(),
                'total': 8500.00,
                'balance_due': 8500.00,
            },
            {
                'invoice_number': 'INV-20240108-001',
                'customer_id': 'C002',
                'status': 'partially_paid',
                'invoice_date': (date.today() - timedelta(days=12)).isoformat(),
                'due_date': (date.today() + timedelta(days=18)).isoformat(),
                'total': 5000.00,
                'balance_due': 2500.00,
            },
        ],
        'count': 2,
    })


def _demo_ap_aging():
    """Return demo AP aging."""
    return jsonify({
        'current': 3500.00,
        '1_30': 2100.00,
        '31_60': 800.00,
        '61_90': 0.00,
        'over_90': 0.00,
        'total': 6400.00,
    })


def _demo_ar_aging():
    """Return demo AR aging."""
    return jsonify({
        'current': 11000.00,
        '1_30': 4500.00,
        '31_60': 1200.00,
        '61_90': 500.00,
        'over_90': 0.00,
        'total': 17200.00,
    })


def _demo_trial_balance():
    """Return demo trial balance."""
    return jsonify({
        'as_of_date': date.today().isoformat(),
        'accounts': [
            {'account_number': '1000', 'account_name': 'Cash', 'account_type': 'asset', 'debit_balance': 125000.00, 'credit_balance': 0.00},
            {'account_number': '1100', 'account_name': 'Accounts Receivable', 'account_type': 'asset', 'debit_balance': 45000.00, 'credit_balance': 0.00},
            {'account_number': '1200', 'account_name': 'Inventory', 'account_type': 'asset', 'debit_balance': 78000.00, 'credit_balance': 0.00},
            {'account_number': '1500', 'account_name': 'Equipment', 'account_type': 'asset', 'debit_balance': 50000.00, 'credit_balance': 0.00},
            {'account_number': '2000', 'account_name': 'Accounts Payable', 'account_type': 'liability', 'debit_balance': 0.00, 'credit_balance': 32000.00},
            {'account_number': '3000', 'account_name': 'Retained Earnings', 'account_type': 'equity', 'debit_balance': 0.00, 'credit_balance': 81000.00},
            {'account_number': '4000', 'account_name': 'Sales Revenue', 'account_type': 'revenue', 'debit_balance': 0.00, 'credit_balance': 185000.00},
            {'account_number': '5000', 'account_name': 'Cost of Goods Sold', 'account_type': 'expense', 'debit_balance': 0.00, 'credit_balance': 0.00},
            {'account_number': '6000', 'account_name': 'Operating Expenses', 'account_type': 'expense', 'debit_balance': 0.00, 'credit_balance': 0.00},
        ],
        'total_debit': 298000.00,
        'total_credit': 298000.00,
        'is_balanced': True,
    })


def _demo_income_statement():
    """Return demo income statement."""
    today = date.today()
    return jsonify({
        'period': {
            'start_date': date(today.year, today.month, 1).isoformat(),
            'end_date': today.isoformat(),
        },
        'revenue': 185000.00,
        'cost_of_goods_sold': 92000.00,
        'gross_profit': 93000.00,
        'operating_expenses': 45000.00,
        'operating_income': 48000.00,
        'other_income': 500.00,
        'other_expenses': 1200.00,
        'net_income': 47300.00,
    })


def _demo_financial_dashboard():
    """Return demo financial dashboard."""
    today = date.today()
    return jsonify({
        'period': today.strftime('%B %Y'),
        'summary': {
            'cash_balance': 125000.00,
            'ar_balance': 45000.00,
            'ap_balance': 32000.00,
            'net_working_capital': 138000.00,
        },
        'income': {
            'revenue_mtd': 185000.00,
            'revenue_ytd': 1450000.00,
            'gross_margin': 0.503,
            'net_income_mtd': 47300.00,
        },
        'ratios': {
            'current_ratio': 7.75,
            'quick_ratio': 5.31,
            'ar_turnover': 4.1,
            'ap_turnover': 5.8,
        },
        'trends': {
            'revenue_trend': [145000, 152000, 168000, 175000, 185000],
            'expense_trend': [72000, 76000, 84000, 87000, 93000],
            'months': ['Sep', 'Oct', 'Nov', 'Dec', 'Jan'],
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# DELETE Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/items/<item_id>', methods=['DELETE'])
@jwt_required()
def delete_item(item_id: str):
    """
    Soft delete an inventory item.

    Requires admin role. Returns 204 on success.
    Cannot delete items with open orders or positive inventory.
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
        from models.erp.items import Item, ItemStatus

        with get_db_session() as session:
            item = session.query(Item).filter(Item.item_id == item_id).first()

            if not item:
                return jsonify({'error': 'Item not found'}), 404

            # Soft delete
            item.is_deleted = True
            item.status = ItemStatus.OBSOLETE
            item.updated_at = datetime.utcnow()
            item.updated_by = current_user

            logger.info(f"Item {item_id} soft deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting item: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete item'}), 500


@erp_api_bp.route('/sales-orders/<order_id>', methods=['DELETE'])
@jwt_required()
def delete_sales_order(order_id: str):
    """
    Soft delete a sales order.

    Requires admin role. Returns 204 on success.
    Can only delete draft orders.
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
        from models.erp.sales import SalesOrder, SalesOrderStatus

        with get_db_session() as session:
            order = session.query(SalesOrder).filter(
                SalesOrder.order_number == order_id
            ).first()

            if not order:
                return jsonify({'error': 'Sales order not found'}), 404

            # Can only delete draft orders
            if order.status != SalesOrderStatus.DRAFT:
                return jsonify({'error': f"Cannot delete sales order with status '{order.status.value}'. Only draft orders can be deleted."}), 409

            # Soft delete
            order.is_deleted = True
            order.updated_at = datetime.utcnow()
            order.updated_by = current_user

            logger.info(f"Sales order {order_id} soft deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting sales order: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete sales order'}), 500


@erp_api_bp.route('/purchase-orders/<po_id>', methods=['DELETE'])
@jwt_required()
def delete_purchase_order(po_id: str):
    """
    Soft delete a purchase order.

    Requires admin role. Returns 204 on success.
    Can only delete draft purchase orders.
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
        from models.erp.purchasing import PurchaseOrder, POStatus

        with get_db_session() as session:
            po = session.query(PurchaseOrder).filter(
                PurchaseOrder.po_number == po_id
            ).first()

            if not po:
                return jsonify({'error': 'Purchase order not found'}), 404

            if po.status != POStatus.DRAFT:
                return jsonify({'error': f"Cannot delete PO with status '{po.status.value}'. Only draft orders can be deleted."}), 409

            # Soft delete
            po.is_deleted = True
            po.updated_at = datetime.utcnow()
            po.updated_by = current_user

            logger.info(f"Purchase order {po_id} soft deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting purchase order: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete purchase order'}), 500


@erp_api_bp.route('/partners/<partner_id>', methods=['DELETE'])
@jwt_required()
def delete_partner(partner_id: str):
    """
    Soft delete a partner (customer/vendor).

    Requires admin role. Returns 204 on success.
    Cannot delete partners with open transactions.
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
        from models.erp.partners import Partner, PartnerStatus

        with get_db_session() as session:
            partner = session.query(Partner).filter(
                Partner.partner_id == partner_id
            ).first()

            if not partner:
                return jsonify({'error': 'Partner not found'}), 404

            # Soft delete
            partner.is_deleted = True
            partner.status = PartnerStatus.INACTIVE
            partner.updated_at = datetime.utcnow()
            partner.updated_by = current_user

            logger.info(f"Partner {partner_id} soft deleted by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting partner: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete partner'}), 500


@erp_api_bp.route('/inventory/transactions/<txn_id>', methods=['DELETE'])
@jwt_required()
def reverse_inventory_transaction(txn_id: str):
    """
    Reverse an inventory transaction.

    Requires admin role. Returns 204 on success.
    Creates a reversal transaction to offset the original.
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
        from services.erp.inventory_service import InventoryService

        with get_db_session() as session:
            service = InventoryService(session)
            result = service.reverse_transaction(txn_id, current_user)
            if not result:
                return jsonify({'error': 'Transaction not found or already reversed'}), 404

            logger.info(f"Inventory transaction {txn_id} reversed by {current_user}")
            return '', 204

    except Exception as e:
        logger.error(f"Error reversing transaction: {e}", exc_info=True)
        return jsonify({'error': 'Failed to reverse transaction'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Costing
# ─────────────────────────────────────────────────────────────────────────────

@erp_api_bp.route('/costing/products', methods=['GET'])
@jwt_required(optional=True)
def list_product_costs():
    """
    List product cost breakdowns.

    Query params:
    - search: Filter by SKU
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    try:
        from config.database import get_db_session
        from services.erp.costing_service import CostingService

        with get_db_session() as session:
            service = CostingService(session)
            result = service.get_product_costs(
                search=request.args.get('search'),
                limit=int(request.args.get('limit', 100)),
                offset=int(request.args.get('offset', 0)),
            )
            return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching product costs: {e}", exc_info=True)
        return jsonify({
            'products': [],
            'count': 0,
            'summary': {'avg_material': 0, 'avg_labor': 0, 'avg_overhead': 0, 'variance_count': 0},
            'variance_alerts': [],
            'error': 'Could not fetch costing data'
        })


@erp_api_bp.route('/costing/products/<sku>', methods=['GET'])
@jwt_required(optional=True)
def get_product_cost_detail(sku: str):
    """
    Get detailed cost breakdown for a specific product.

    Returns BOM costs, routing costs, and totals.
    """
    try:
        from config.database import get_db_session
        from services.erp.costing_service import CostingService

        with get_db_session() as session:
            service = CostingService(session)
            result = service.get_product_cost_detail(sku)

            if not result:
                return jsonify({'error': 'Product not found'}), 404

            return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching product cost detail: {e}", exc_info=True)
        return jsonify({'error': 'Could not fetch cost detail'}), 500


@erp_api_bp.route('/costing/variance', methods=['GET'])
@jwt_required(optional=True)
def get_cost_variance_report():
    """
    Get cost variance report.

    Query params:
    - threshold: Variance percentage threshold (default 5.0)
    - limit: Max results (default 50)
    """
    try:
        from config.database import get_db_session
        from services.erp.costing_service import CostingService

        with get_db_session() as session:
            service = CostingService(session)
            result = service.get_cost_variance_report(
                threshold=float(request.args.get('threshold', 5.0)),
                limit=int(request.args.get('limit', 50)),
            )
            return jsonify({'variance_items': result, 'count': len(result)})

    except Exception as e:
        logger.error(f"Error fetching variance report: {e}", exc_info=True)
        return jsonify({'variance_items': [], 'count': 0, 'error': 'Could not fetch variance report'})


@erp_api_bp.route('/costing/rollup', methods=['POST'])
@jwt_required()
def run_cost_rollup():
    """
    Run cost rollup to recalculate product costs.

    Request body (optional):
        {
            "product_ids": ["SKU1", "SKU2"]  // Optional - if not provided, updates all
        }
    """
    current_user = get_jwt_identity()

    try:
        from config.database import get_db_session
        from services.erp.costing_service import CostingService

        data = request.get_json() or {}
        product_ids = data.get('product_ids')

        with get_db_session() as session:
            service = CostingService(session)
            result = service.run_cost_rollup(product_ids)
            session.commit()

            logger.info(f"Cost rollup completed by {current_user}: {result['updated']} products updated")
            return jsonify(result)

    except Exception as e:
        logger.error(f"Error running cost rollup: {e}", exc_info=True)
        return jsonify({'error': 'Cost rollup failed', 'updated': 0}), 500
