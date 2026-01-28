"""
LEGO Factory v3 - ERP API Documentation
========================================
Flask-RESTX namespace for Enterprise Resource Planning endpoints.
"""

from flask import request
from flask_restx import Namespace, Resource, fields
import logging

logger = logging.getLogger(__name__)

# Create namespace
erp_ns = Namespace(
    'erp',
    description='ERP - Enterprise Resource Planning (Level 4)',
    path='/erp',
)

# =============================================================================
# API MODELS - Financial / GL
# =============================================================================

gl_account_model = erp_ns.model('GLAccount', {
    'account_number': fields.String(description='Account number', example='1000'),
    'name': fields.String(description='Account name', example='Cash'),
    'description': fields.String(description='Account description'),
    'account_type': fields.String(
        description='Account type',
        enum=['asset', 'liability', 'equity', 'revenue', 'expense'],
        example='asset'
    ),
    'parent_account': fields.String(description='Parent account number'),
    'is_active': fields.Boolean(description='Account active status', example=True),
    'balance': fields.Float(description='Current balance', example=125000.00),
    'normal_balance': fields.String(
        description='Normal balance side',
        enum=['debit', 'credit'],
        example='debit'
    ),
    'created_at': fields.DateTime(description='Creation timestamp'),
})

gl_account_create = erp_ns.model('GLAccountCreate', {
    'account_number': fields.String(required=True, description='Account number', example='1010'),
    'name': fields.String(required=True, description='Account name', example='Petty Cash'),
    'description': fields.String(description='Account description'),
    'account_type': fields.String(required=True, description='Account type', enum=['asset', 'liability', 'equity', 'revenue', 'expense']),
    'parent_account': fields.String(description='Parent account number'),
})

gl_account_balance = erp_ns.model('GLAccountBalance', {
    'account_number': fields.String(description='Account number'),
    'account_name': fields.String(description='Account name'),
    'as_of_date': fields.Date(description='Balance date'),
    'balance': fields.Float(description='Account balance', example=125000.00),
})

journal_line_model = erp_ns.model('JournalLine', {
    'account_number': fields.String(description='GL account', example='1000'),
    'description': fields.String(description='Line description'),
    'debit': fields.Float(description='Debit amount', example=1000.00),
    'credit': fields.Float(description='Credit amount', example=0.00),
    'reference': fields.String(description='Reference'),
    'cost_center': fields.String(description='Cost center'),
})

journal_entry_model = erp_ns.model('JournalEntry', {
    'journal_number': fields.String(description='Journal entry number', example='JE-20240115-001'),
    'journal_date': fields.Date(description='Journal date'),
    'status': fields.String(
        description='Journal status',
        enum=['draft', 'pending', 'posted', 'reversed'],
        example='posted'
    ),
    'description': fields.String(description='Journal description', example='Sales revenue for work order WO-20240110-001'),
    'reference': fields.String(description='Reference document'),
    'lines': fields.List(fields.Nested(journal_line_model)),
    'total_debit': fields.Float(description='Total debit', example=5000.00),
    'total_credit': fields.Float(description='Total credit', example=5000.00),
    'created_by': fields.String(description='Creator'),
    'posted_by': fields.String(description='Poster'),
    'posted_at': fields.DateTime(description='Post timestamp'),
})

journal_entry_create = erp_ns.model('JournalEntryCreate', {
    'description': fields.String(required=True, description='Journal description'),
    'journal_date': fields.Date(description='Journal date (defaults to today)'),
    'reference': fields.String(description='Reference document'),
    'lines': fields.List(fields.Nested(journal_line_model), required=True, description='Journal lines'),
})


# =============================================================================
# API MODELS - Accounts Payable/Receivable
# =============================================================================

ap_invoice_model = erp_ns.model('APInvoice', {
    'invoice_number': fields.String(description='Internal invoice number', example='AP-20240115-001'),
    'vendor_invoice_number': fields.String(description='Vendor invoice number', example='INV-12345'),
    'vendor_id': fields.String(description='Vendor ID', example='V001'),
    'vendor_name': fields.String(description='Vendor name'),
    'status': fields.String(
        description='Invoice status',
        enum=['draft', 'pending', 'approved', 'paid', 'void'],
        example='approved'
    ),
    'invoice_date': fields.Date(description='Invoice date'),
    'due_date': fields.Date(description='Due date'),
    'subtotal': fields.Float(description='Subtotal', example=3000.00),
    'tax': fields.Float(description='Tax amount', example=500.00),
    'total': fields.Float(description='Total amount', example=3500.00),
    'amount_paid': fields.Float(description='Amount paid', example=0.00),
    'balance_due': fields.Float(description='Balance due', example=3500.00),
    'description': fields.String(description='Invoice description'),
    'lines': fields.Raw(description='Invoice line items'),
    'created_at': fields.DateTime(description='Creation timestamp'),
})

ar_invoice_model = erp_ns.model('ARInvoice', {
    'invoice_number': fields.String(description='Invoice number', example='INV-20240115-001'),
    'customer_id': fields.String(description='Customer ID', example='C001'),
    'customer_name': fields.String(description='Customer name'),
    'status': fields.String(
        description='Invoice status',
        enum=['draft', 'sent', 'partially_paid', 'paid', 'void', 'overdue'],
        example='sent'
    ),
    'invoice_date': fields.Date(description='Invoice date'),
    'due_date': fields.Date(description='Due date'),
    'subtotal': fields.Float(description='Subtotal'),
    'tax': fields.Float(description='Tax amount'),
    'total': fields.Float(description='Total amount', example=8500.00),
    'amount_paid': fields.Float(description='Amount paid', example=0.00),
    'balance_due': fields.Float(description='Balance due', example=8500.00),
    'work_order_id': fields.String(description='Related work order'),
    'sales_order_id': fields.String(description='Related sales order'),
    'created_at': fields.DateTime(description='Creation timestamp'),
})

aging_model = erp_ns.model('AgingReport', {
    'current': fields.Float(description='Current (0-30 days)', example=11000.00),
    '1_30': fields.Float(description='1-30 days past due', example=4500.00),
    '31_60': fields.Float(description='31-60 days past due', example=1200.00),
    '61_90': fields.Float(description='61-90 days past due', example=500.00),
    'over_90': fields.Float(description='Over 90 days past due', example=0.00),
    'total': fields.Float(description='Total outstanding', example=17200.00),
})


# =============================================================================
# API MODELS - Sales Orders
# =============================================================================

sales_order_line = erp_ns.model('SalesOrderLine', {
    'line_id': fields.String(description='Line ID'),
    'item_id': fields.String(description='Item ID', example='brick_2x4_red'),
    'item_name': fields.String(description='Item name'),
    'quantity': fields.Integer(description='Quantity ordered', example=500),
    'unit_price': fields.Float(description='Unit price', example=0.35),
    'line_total': fields.Float(description='Line total', example=175.00),
    'quantity_shipped': fields.Integer(description='Quantity shipped', example=0),
    'quantity_invoiced': fields.Integer(description='Quantity invoiced', example=0),
})

sales_order_model = erp_ns.model('SalesOrder', {
    'order_id': fields.String(description='Sales order ID', example='SO-20240115-001'),
    'customer_id': fields.String(description='Customer ID', example='CUST001'),
    'customer_name': fields.String(description='Customer name'),
    'status': fields.String(
        description='Order status',
        enum=['draft', 'confirmed', 'in_production', 'shipped', 'invoiced', 'completed', 'cancelled'],
        example='confirmed'
    ),
    'order_date': fields.Date(description='Order date'),
    'requested_date': fields.Date(description='Requested delivery date'),
    'promised_date': fields.Date(description='Promised delivery date'),
    'lines': fields.List(fields.Nested(sales_order_line)),
    'subtotal': fields.Float(description='Subtotal', example=250.00),
    'tax': fields.Float(description='Tax amount', example=20.00),
    'total': fields.Float(description='Total amount', example=270.00),
    'shipping_address': fields.Raw(description='Shipping address'),
    'billing_address': fields.Raw(description='Billing address'),
    'notes': fields.String(description='Order notes'),
    'work_order_ids': fields.List(fields.String, description='Related work orders'),
    'created_at': fields.DateTime(description='Creation timestamp'),
})

sales_order_create = erp_ns.model('SalesOrderCreate', {
    'customer_id': fields.String(required=True, description='Customer ID'),
    'requested_date': fields.Date(description='Requested delivery date'),
    'lines': fields.List(fields.Nested(erp_ns.model('SalesOrderLineCreate', {
        'item_id': fields.String(required=True, description='Item ID'),
        'quantity': fields.Integer(required=True, description='Quantity', example=100),
        'unit_price': fields.Float(description='Unit price (defaults to list price)'),
    }))),
    'notes': fields.String(description='Order notes'),
    'shipping_address': fields.Raw(description='Shipping address'),
    'billing_address': fields.Raw(description='Billing address'),
})


# =============================================================================
# API MODELS - Customers & Partners
# =============================================================================

customer_model = erp_ns.model('Customer', {
    'customer_id': fields.String(description='Customer ID', example='CUST001'),
    'name': fields.String(description='Customer name', example='LEGO Enthusiasts Inc'),
    'email': fields.String(description='Email', example='orders@legoenth.com'),
    'phone': fields.String(description='Phone number'),
    'address': fields.Raw(description='Address'),
    'status': fields.String(
        description='Customer status',
        enum=['active', 'inactive', 'on_hold'],
        example='active'
    ),
    'credit_limit': fields.Float(description='Credit limit'),
    'payment_terms': fields.String(description='Payment terms', example='Net 30'),
    'created_at': fields.DateTime(description='Creation timestamp'),
})

customer_create = erp_ns.model('CustomerCreate', {
    'name': fields.String(required=True, description='Customer name'),
    'email': fields.String(description='Email'),
    'phone': fields.String(description='Phone'),
    'address': fields.Raw(description='Address'),
    'credit_limit': fields.Float(description='Credit limit'),
    'payment_terms': fields.String(description='Payment terms'),
})


# =============================================================================
# API MODELS - Inventory
# =============================================================================

item_model = erp_ns.model('Item', {
    'item_id': fields.String(description='Item ID', example='brick_2x4_red'),
    'name': fields.String(description='Item name', example='2x4 Brick Red'),
    'description': fields.String(description='Item description'),
    'item_type': fields.String(
        description='Item type',
        enum=['raw_material', 'wip', 'finished_good', 'mro'],
        example='finished_good'
    ),
    'unit_of_measure': fields.String(description='Unit of measure', example='EA'),
    'unit_cost': fields.Float(description='Standard unit cost', example=0.15),
    'list_price': fields.Float(description='List price', example=0.35),
    'qty_on_hand': fields.Integer(description='Quantity on hand', example=5000),
    'qty_available': fields.Integer(description='Quantity available (on hand - allocated)', example=4500),
    'qty_on_order': fields.Integer(description='Quantity on order', example=1000),
    'qty_allocated': fields.Integer(description='Quantity allocated to orders', example=500),
    'reorder_point': fields.Integer(description='Reorder point', example=1000),
    'reorder_qty': fields.Integer(description='Reorder quantity', example=5000),
    'lead_time_days': fields.Integer(description='Lead time in days', example=7),
    'location': fields.String(description='Storage location', example='WAREHOUSE-A-1-1'),
    'is_active': fields.Boolean(description='Item active status', example=True),
})

item_create = erp_ns.model('ItemCreate', {
    'item_id': fields.String(required=True, description='Item ID'),
    'name': fields.String(required=True, description='Item name'),
    'description': fields.String(description='Description'),
    'item_type': fields.String(description='Item type', default='finished_good'),
    'unit_of_measure': fields.String(description='Unit of measure', default='EA'),
    'unit_cost': fields.Float(description='Standard cost', default=0),
    'list_price': fields.Float(description='List price', default=0),
    'qty_on_hand': fields.Integer(description='Initial quantity', default=0),
    'reorder_point': fields.Integer(description='Reorder point', default=0),
    'lead_time_days': fields.Integer(description='Lead time', default=7),
})


# =============================================================================
# API MODELS - MRP
# =============================================================================

mrp_planned_order = erp_ns.model('MRPPlannedOrder', {
    'item_id': fields.String(description='Item ID'),
    'item_name': fields.String(description='Item name'),
    'gross_requirement': fields.Integer(description='Gross requirement'),
    'on_hand': fields.Integer(description='On hand quantity'),
    'safety_stock': fields.Integer(description='Safety stock'),
    'net_requirement': fields.Integer(description='Net requirement'),
    'planned_order_qty': fields.Integer(description='Planned order quantity'),
    'planned_order_date': fields.Date(description='Planned order date'),
    'lead_time_days': fields.Integer(description='Lead time'),
    'unit_cost': fields.Float(description='Unit cost'),
    'total_cost': fields.Float(description='Total cost'),
})

mrp_shortage = erp_ns.model('MRPShortage', {
    'item_id': fields.String(description='Item ID'),
    'item_name': fields.String(description='Item name'),
    'required': fields.Integer(description='Required quantity'),
    'available': fields.Integer(description='Available quantity'),
    'shortage': fields.Integer(description='Shortage quantity'),
})

mrp_result_model = erp_ns.model('MRPResult', {
    'run_id': fields.String(description='MRP run ID', example='MRP-20240115120000'),
    'run_date': fields.DateTime(description='Run timestamp'),
    'horizon_days': fields.Integer(description='Planning horizon', example=90),
    'include_safety_stock': fields.Boolean(description='Included safety stock', example=True),
    'status': fields.String(description='Run status', example='completed'),
    'summary': fields.Nested(erp_ns.model('MRPSummary', {
        'total_items_analyzed': fields.Integer(description='Items analyzed'),
        'items_with_shortages': fields.Integer(description='Items with shortages'),
        'planned_orders_count': fields.Integer(description='Planned orders'),
        'total_planned_cost': fields.Float(description='Total planned cost'),
    })),
    'planned_orders': fields.List(fields.Nested(mrp_planned_order)),
    'shortages': fields.List(fields.Nested(mrp_shortage)),
    'recommendations': fields.List(fields.Raw(description='Recommendations')),
})

mrp_request = erp_ns.model('MRPRequest', {
    'horizon_days': fields.Integer(description='Planning horizon in days', default=90, example=90),
    'include_safety_stock': fields.Boolean(description='Include safety stock', default=True),
})


# =============================================================================
# API MODELS - Financial Reports
# =============================================================================

trial_balance_model = erp_ns.model('TrialBalance', {
    'as_of_date': fields.Date(description='Balance date'),
    'accounts': fields.List(fields.Nested(erp_ns.model('TrialBalanceLine', {
        'account_number': fields.String(description='Account number'),
        'account_name': fields.String(description='Account name'),
        'account_type': fields.String(description='Account type'),
        'debit_balance': fields.Float(description='Debit balance'),
        'credit_balance': fields.Float(description='Credit balance'),
    }))),
    'total_debit': fields.Float(description='Total debits'),
    'total_credit': fields.Float(description='Total credits'),
    'is_balanced': fields.Boolean(description='Trial balance is balanced'),
})

income_statement_model = erp_ns.model('IncomeStatement', {
    'period': fields.Raw(description='Report period'),
    'revenue': fields.Float(description='Total revenue', example=185000.00),
    'cost_of_goods_sold': fields.Float(description='Cost of goods sold', example=92000.00),
    'gross_profit': fields.Float(description='Gross profit', example=93000.00),
    'operating_expenses': fields.Float(description='Operating expenses', example=45000.00),
    'operating_income': fields.Float(description='Operating income', example=48000.00),
    'other_income': fields.Float(description='Other income', example=500.00),
    'other_expenses': fields.Float(description='Other expenses', example=1200.00),
    'net_income': fields.Float(description='Net income', example=47300.00),
})

financial_dashboard_model = erp_ns.model('FinancialDashboard', {
    'period': fields.String(description='Dashboard period'),
    'summary': fields.Nested(erp_ns.model('DashboardSummary', {
        'cash_balance': fields.Float(description='Cash balance'),
        'ar_balance': fields.Float(description='AR balance'),
        'ap_balance': fields.Float(description='AP balance'),
        'net_working_capital': fields.Float(description='Net working capital'),
    })),
    'income': fields.Nested(erp_ns.model('DashboardIncome', {
        'revenue_mtd': fields.Float(description='Revenue MTD'),
        'revenue_ytd': fields.Float(description='Revenue YTD'),
        'gross_margin': fields.Float(description='Gross margin %'),
        'net_income_mtd': fields.Float(description='Net income MTD'),
    })),
    'ratios': fields.Nested(erp_ns.model('FinancialRatios', {
        'current_ratio': fields.Float(description='Current ratio'),
        'quick_ratio': fields.Float(description='Quick ratio'),
        'ar_turnover': fields.Float(description='AR turnover'),
        'ap_turnover': fields.Float(description='AP turnover'),
    })),
    'trends': fields.Raw(description='Trend data for charts'),
})


# =============================================================================
# RESOURCES - GL Accounts
# =============================================================================

@erp_ns.route('/gl/accounts')
class GLAccountList(Resource):
    """General Ledger account listing."""

    @erp_ns.doc(
        'list_gl_accounts',
        params={
            'type': {'description': 'Filter by account type', 'enum': ['asset', 'liability', 'equity', 'revenue', 'expense']},
            'active': {'description': 'Filter by active status', 'type': 'boolean', 'default': True},
        },
        responses={
            200: 'List of GL accounts',
        }
    )
    def get(self):
        """
        List GL accounts (Chart of Accounts).

        Returns all general ledger accounts organized by type.
        This forms the foundation of the double-entry bookkeeping system.

        **Account Types:**
        - `asset`: Resources owned (Cash, Inventory, Equipment)
        - `liability`: Obligations owed (Accounts Payable, Loans)
        - `equity`: Owner's stake (Retained Earnings, Capital)
        - `revenue`: Income from operations (Sales Revenue)
        - `expense`: Costs of operations (COGS, Wages)
        """
        from api.routes.erp_api import list_gl_accounts
        return list_gl_accounts()

    @erp_ns.doc(
        'create_gl_account',
        responses={
            201: ('Account created', gl_account_model),
            400: 'Validation error',
        }
    )
    @erp_ns.expect(gl_account_create, validate=True)
    @erp_ns.marshal_with(gl_account_model, code=201)
    def post(self):
        """
        Create a GL account.

        Adds a new account to the chart of accounts.

        **Account Numbering Convention:**
        - 1000-1999: Assets
        - 2000-2999: Liabilities
        - 3000-3999: Equity
        - 4000-4999: Revenue
        - 5000-5999: Cost of Goods Sold
        - 6000-6999: Operating Expenses
        """
        from api.routes.erp_api import create_gl_account
        return create_gl_account()


@erp_ns.route('/gl/accounts/<string:account_number>/balance')
@erp_ns.param('account_number', 'GL account number')
class GLAccountBalance(Resource):
    """GL account balance endpoint."""

    @erp_ns.doc(
        'get_account_balance',
        params={
            'as_of': {'description': 'Balance date (ISO format)', 'type': 'string'},
        },
        responses={
            200: ('Account balance', gl_account_balance),
            404: 'Account not found',
        }
    )
    @erp_ns.marshal_with(gl_account_balance)
    def get(self, account_number):
        """
        Get GL account balance.

        Returns the account balance as of the specified date
        (or current date if not specified).
        """
        from api.routes.erp_api import get_account_balance
        return get_account_balance(account_number)


# =============================================================================
# RESOURCES - Journal Entries
# =============================================================================

@erp_ns.route('/gl/journal-entries')
class JournalEntryList(Resource):
    """Journal entry listing."""

    @erp_ns.doc(
        'list_journal_entries',
        params={
            'status': {'description': 'Filter by status', 'enum': ['draft', 'pending', 'posted', 'reversed']},
            'start_date': {'description': 'Start date (ISO format)'},
            'end_date': {'description': 'End date (ISO format)'},
            'limit': {'description': 'Max results', 'default': 100},
        },
        responses={
            200: 'List of journal entries',
        }
    )
    def get(self):
        """
        List journal entries.

        Returns journal entries within the specified criteria.
        """
        from api.routes.erp_api import list_journal_entries
        return list_journal_entries()

    @erp_ns.doc(
        'create_journal_entry',
        responses={
            201: ('Journal entry created', journal_entry_model),
            400: 'Validation error (unbalanced or missing lines)',
        }
    )
    @erp_ns.expect(journal_entry_create, validate=True)
    @erp_ns.marshal_with(journal_entry_model, code=201)
    def post(self):
        """
        Create a journal entry.

        Creates a new journal entry in draft status.
        The entry must be balanced (total debits = total credits).

        **Double-Entry Requirement:**
        Every transaction must have equal debits and credits.
        The system will reject unbalanced entries.
        """
        from api.routes.erp_api import create_journal_entry
        return create_journal_entry()


@erp_ns.route('/gl/journal-entries/<string:journal_number>/post')
@erp_ns.param('journal_number', 'Journal entry number')
class JournalEntryPost(Resource):
    """Journal entry posting endpoint."""

    @erp_ns.doc(
        'post_journal_entry',
        responses={
            200: ('Journal entry posted', journal_entry_model),
            400: 'Cannot post (invalid status or unbalanced)',
            404: 'Journal entry not found',
        }
    )
    def post(self, journal_number):
        """
        Post a journal entry.

        Posts the journal entry, making it permanent and updating
        account balances. Posted entries cannot be modified.

        **Note:** Once posted, entries can only be corrected by
        creating a reversing entry.
        """
        from api.routes.erp_api import post_journal_entry
        return post_journal_entry(journal_number)


# =============================================================================
# RESOURCES - Accounts Payable
# =============================================================================

@erp_ns.route('/ap/invoices')
class APInvoiceList(Resource):
    """Accounts Payable invoice listing."""

    @erp_ns.doc(
        'list_ap_invoices',
        params={
            'vendor_id': {'description': 'Filter by vendor'},
            'status': {'description': 'Filter by status', 'enum': ['draft', 'pending', 'approved', 'paid', 'void']},
            'limit': {'description': 'Max results', 'default': 100},
        },
        responses={
            200: 'List of AP invoices',
        }
    )
    def get(self):
        """
        List AP invoices.

        Returns vendor invoices for accounts payable.
        """
        from api.routes.erp_api import list_ap_invoices
        return list_ap_invoices()

    @erp_ns.doc(
        'create_ap_invoice',
        responses={
            201: ('AP invoice created', ap_invoice_model),
            400: 'Validation error',
        }
    )
    def post(self):
        """
        Create an AP invoice.

        Records a vendor invoice for payment processing.
        """
        from api.routes.erp_api import create_ap_invoice
        return create_ap_invoice()


@erp_ns.route('/ap/aging')
class APAging(Resource):
    """AP aging report endpoint."""

    @erp_ns.doc(
        'get_ap_aging',
        responses={
            200: ('AP aging report', aging_model),
        }
    )
    @erp_ns.marshal_with(aging_model)
    def get(self):
        """
        Get AP aging report.

        Returns accounts payable aging buckets showing
        outstanding vendor balances by age.
        """
        from api.routes.erp_api import get_ap_aging
        return get_ap_aging()


# =============================================================================
# RESOURCES - Accounts Receivable
# =============================================================================

@erp_ns.route('/ar/invoices')
class ARInvoiceList(Resource):
    """Accounts Receivable invoice listing."""

    @erp_ns.doc(
        'list_ar_invoices',
        params={
            'customer_id': {'description': 'Filter by customer'},
            'status': {'description': 'Filter by status', 'enum': ['draft', 'sent', 'partially_paid', 'paid', 'void', 'overdue']},
            'limit': {'description': 'Max results', 'default': 100},
        },
        responses={
            200: 'List of AR invoices',
        }
    )
    def get(self):
        """
        List AR invoices.

        Returns customer invoices for accounts receivable.
        """
        from api.routes.erp_api import list_ar_invoices
        return list_ar_invoices()

    @erp_ns.doc(
        'create_ar_invoice',
        responses={
            201: ('AR invoice created', ar_invoice_model),
            400: 'Validation error',
        }
    )
    def post(self):
        """
        Create an AR invoice.

        Creates a customer invoice for billing.
        """
        from api.routes.erp_api import create_ar_invoice
        return create_ar_invoice()


@erp_ns.route('/ar/aging')
class ARAging(Resource):
    """AR aging report endpoint."""

    @erp_ns.doc(
        'get_ar_aging',
        responses={
            200: ('AR aging report', aging_model),
        }
    )
    @erp_ns.marshal_with(aging_model)
    def get(self):
        """
        Get AR aging report.

        Returns accounts receivable aging buckets showing
        outstanding customer balances by age.
        """
        from api.routes.erp_api import get_ar_aging
        return get_ar_aging()


# =============================================================================
# RESOURCES - Financial Reports
# =============================================================================

@erp_ns.route('/reports/trial-balance')
class TrialBalanceReport(Resource):
    """Trial balance report endpoint."""

    @erp_ns.doc(
        'get_trial_balance',
        params={
            'as_of': {'description': 'Balance date (ISO format)'},
        },
        responses={
            200: ('Trial balance', trial_balance_model),
        }
    )
    @erp_ns.marshal_with(trial_balance_model)
    def get(self):
        """
        Get trial balance report.

        Returns all accounts with their debit or credit balances.
        Total debits must equal total credits if books are balanced.
        """
        from api.routes.erp_api import get_trial_balance
        return get_trial_balance()


@erp_ns.route('/reports/income-statement')
class IncomeStatementReport(Resource):
    """Income statement report endpoint."""

    @erp_ns.doc(
        'get_income_statement',
        params={
            'start_date': {'description': 'Period start (ISO format)'},
            'end_date': {'description': 'Period end (ISO format)'},
        },
        responses={
            200: ('Income statement', income_statement_model),
        }
    )
    @erp_ns.marshal_with(income_statement_model)
    def get(self):
        """
        Get income statement (P&L).

        Returns the profit and loss statement for the specified period.

        **Structure:**
        - Revenue
        - Less: Cost of Goods Sold
        - = Gross Profit
        - Less: Operating Expenses
        - = Operating Income
        - +/- Other Income/Expenses
        - = Net Income
        """
        from api.routes.erp_api import get_income_statement
        return get_income_statement()


@erp_ns.route('/reports/dashboard')
class FinancialDashboardReport(Resource):
    """Financial dashboard endpoint."""

    @erp_ns.doc(
        'get_financial_dashboard',
        responses={
            200: ('Financial dashboard', financial_dashboard_model),
        }
    )
    @erp_ns.marshal_with(financial_dashboard_model)
    def get(self):
        """
        Get financial dashboard summary.

        Returns key financial metrics and KPIs for management dashboards.
        """
        from api.routes.erp_api import get_financial_dashboard
        return get_financial_dashboard()


# =============================================================================
# RESOURCES - Sales Orders
# =============================================================================

@erp_ns.route('/sales-orders')
class SalesOrderList(Resource):
    """Sales order listing and creation."""

    @erp_ns.doc(
        'list_sales_orders',
        params={
            'status': {'description': 'Filter by status', 'enum': ['draft', 'confirmed', 'in_production', 'shipped', 'invoiced', 'completed', 'cancelled']},
            'customer_id': {'description': 'Filter by customer'},
        },
        responses={
            200: 'List of sales orders',
        }
    )
    def get(self):
        """
        List sales orders.

        Returns sales orders with optional filtering.
        """
        from api.routes.erp_api import list_sales_orders
        return list_sales_orders()

    @erp_ns.doc(
        'create_sales_order',
        responses={
            201: ('Sales order created', sales_order_model),
            400: 'Validation error',
        }
    )
    @erp_ns.expect(sales_order_create, validate=True)
    @erp_ns.marshal_with(sales_order_model, code=201)
    def post(self):
        """
        Create a sales order.

        Creates a new sales order in draft status.
        The order can be confirmed to trigger manufacturing.

        **Workflow:**
        1. Create order (draft)
        2. Confirm order -> Creates work orders
        3. Produce items
        4. Ship items
        5. Invoice customer
        """
        from api.routes.erp_api import create_sales_order
        return create_sales_order()


@erp_ns.route('/sales-orders/<string:order_id>')
@erp_ns.param('order_id', 'Sales order ID')
class SalesOrderDetail(Resource):
    """Single sales order operations."""

    @erp_ns.doc(
        'get_sales_order',
        responses={
            200: ('Sales order details', sales_order_model),
            404: 'Sales order not found',
        }
    )
    @erp_ns.marshal_with(sales_order_model)
    def get(self, order_id):
        """Get sales order details."""
        from api.routes.erp_api import get_sales_order
        return get_sales_order(order_id)

    @erp_ns.doc(
        'update_sales_order',
        responses={
            200: ('Sales order updated', sales_order_model),
            400: 'Validation error',
            404: 'Sales order not found',
        }
    )
    @erp_ns.marshal_with(sales_order_model)
    def put(self, order_id):
        """
        Update a sales order.

        Updates allowed fields on a draft order.
        Confirmed orders have limited update capability.
        """
        from api.routes.erp_api import update_sales_order
        return update_sales_order(order_id)


@erp_ns.route('/sales-orders/<string:order_id>/confirm')
@erp_ns.param('order_id', 'Sales order ID')
class SalesOrderConfirm(Resource):
    """Sales order confirmation endpoint."""

    @erp_ns.doc(
        'confirm_sales_order',
        responses={
            200: ('Sales order confirmed', sales_order_model),
            400: 'Cannot confirm (invalid status)',
            404: 'Sales order not found',
        }
    )
    def post(self, order_id):
        """
        Confirm a sales order.

        Changes status from 'draft' to 'confirmed'.
        This typically triggers work order creation in MES.
        """
        from api.routes.erp_api import confirm_sales_order
        return confirm_sales_order(order_id)


# =============================================================================
# RESOURCES - Customers
# =============================================================================

@erp_ns.route('/customers')
class CustomerList(Resource):
    """Customer listing and creation."""

    @erp_ns.doc(
        'list_customers',
        responses={
            200: 'List of customers',
        }
    )
    def get(self):
        """List customers."""
        from api.routes.erp_api import list_customers
        return list_customers()

    @erp_ns.doc(
        'create_customer',
        responses={
            201: ('Customer created', customer_model),
            400: 'Validation error',
        }
    )
    @erp_ns.expect(customer_create, validate=True)
    @erp_ns.marshal_with(customer_model, code=201)
    def post(self):
        """Create a customer."""
        from api.routes.erp_api import create_customer
        return create_customer()


# =============================================================================
# RESOURCES - Inventory Items
# =============================================================================

@erp_ns.route('/items')
class ItemList(Resource):
    """Inventory item listing."""

    @erp_ns.doc(
        'list_items',
        responses={
            200: 'List of items',
        }
    )
    def get(self):
        """
        List inventory items.

        Returns all items in the inventory master.
        """
        from api.routes.erp_api import list_items
        return list_items()

    @erp_ns.doc(
        'create_item',
        responses={
            201: ('Item created', item_model),
            400: 'Validation error',
        }
    )
    @erp_ns.expect(item_create, validate=True)
    @erp_ns.marshal_with(item_model, code=201)
    def post(self):
        """
        Create an inventory item.

        Adds a new item to the inventory master.
        """
        from api.routes.erp_api import create_item
        return create_item()


@erp_ns.route('/items/<string:item_id>')
@erp_ns.param('item_id', 'Item ID')
class ItemDetail(Resource):
    """Single item operations."""

    @erp_ns.doc(
        'get_item',
        responses={
            200: ('Item details', item_model),
            404: 'Item not found',
        }
    )
    @erp_ns.marshal_with(item_model)
    def get(self, item_id):
        """Get item details."""
        from api.routes.erp_api import get_item
        return get_item(item_id)


# =============================================================================
# RESOURCES - MRP
# =============================================================================

@erp_ns.route('/mrp/run')
class MRPRun(Resource):
    """MRP run endpoint."""

    @erp_ns.doc(
        'run_mrp',
        responses={
            200: ('MRP run results', mrp_result_model),
        }
    )
    @erp_ns.expect(mrp_request)
    @erp_ns.marshal_with(mrp_result_model)
    def post(self):
        """
        Run MRP (Material Requirements Planning).

        Calculates material requirements based on:
        - Open sales orders
        - Planned work orders
        - Current inventory levels
        - Lead times
        - Safety stock levels

        **Output:**
        - Planned purchase orders
        - Identified shortages
        - Recommendations

        **MRP Logic:**
        Net Requirement = Gross Requirement - On Hand + Safety Stock
        """
        from api.routes.erp_api import run_mrp
        return run_mrp()


@erp_ns.route('/mrp/runs')
class MRPRunList(Resource):
    """MRP run history endpoint."""

    @erp_ns.doc(
        'list_mrp_runs',
        params={
            'limit': {'description': 'Max results', 'default': 10},
        },
        responses={
            200: 'List of MRP runs',
        }
    )
    def get(self):
        """
        List MRP run history.

        Returns previous MRP runs with their results.
        """
        from api.routes.erp_api import list_mrp_runs
        return list_mrp_runs()


@erp_ns.route('/mrp/runs/<string:run_id>')
@erp_ns.param('run_id', 'MRP run ID')
class MRPRunDetail(Resource):
    """MRP run detail endpoint."""

    @erp_ns.doc(
        'get_mrp_run',
        responses={
            200: ('MRP run details', mrp_result_model),
            404: 'MRP run not found',
        }
    )
    @erp_ns.marshal_with(mrp_result_model)
    def get(self, run_id):
        """Get MRP run details."""
        from api.routes.erp_api import get_mrp_run
        return get_mrp_run(run_id)


@erp_ns.route('/mrp/shortages')
class MRPShortages(Resource):
    """MRP shortages endpoint."""

    @erp_ns.doc(
        'get_mrp_shortages',
        responses={
            200: 'Current inventory shortages',
        }
    )
    def get(self):
        """
        Get current inventory shortages.

        Returns items with shortages based on the most recent MRP run.
        """
        from api.routes.erp_api import get_mrp_shortages
        return get_mrp_shortages()


# =============================================================================
# RESOURCES - Partners
# =============================================================================

@erp_ns.route('/partners')
class PartnerList(Resource):
    """Partner listing endpoint."""

    @erp_ns.doc(
        'list_partners',
        params={
            'type': {'description': 'Filter by type', 'enum': ['customer', 'vendor']},
            'status': {'description': 'Filter by status', 'enum': ['active', 'inactive']},
        },
        responses={
            200: 'List of partners',
        }
    )
    def get(self):
        """
        List all partners (customers and vendors).

        Returns business partners that can be both customers and vendors.
        """
        from api.routes.erp_api import list_partners
        return list_partners()


@erp_ns.route('/partners/<string:partner_id>')
@erp_ns.param('partner_id', 'Partner ID')
class PartnerDetail(Resource):
    """Single partner operations."""

    @erp_ns.doc(
        'get_partner',
        responses={
            200: 'Partner details',
            404: 'Partner not found',
        }
    )
    def get(self, partner_id):
        """Get partner details."""
        from api.routes.erp_api import get_partner
        return get_partner(partner_id)


# =============================================================================
# RESOURCES - Payments
# =============================================================================

@erp_ns.route('/payments')
class PaymentList(Resource):
    """Payment endpoint."""

    @erp_ns.doc(
        'create_payment',
        responses={
            201: 'Payment created',
            400: 'Validation error',
        }
    )
    def post(self):
        """
        Create a payment.

        Records a payment for AP (vendor payment) or
        AR (customer receipt).

        **Payment Types:**
        - `ap_payment`: Payment to vendor
        - `ar_receipt`: Receipt from customer
        """
        from api.routes.erp_api import create_payment
        return create_payment()
