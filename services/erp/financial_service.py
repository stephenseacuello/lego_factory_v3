"""
LEGO Factory v3 - Financial Service
===================================
General Ledger, AP, AR, and cost accounting services.
"""

import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class FinancialService:
    """
    Financial management service.

    Handles:
    - Chart of Accounts management
    - Journal entry creation and posting
    - AP invoice processing
    - AR invoice processing
    - Payment processing
    - Financial reporting
    """

    def __init__(self, session: Session):
        self.session = session

    # ─────────────────────────────────────────────────────────────────────────
    # Chart of Accounts
    # ─────────────────────────────────────────────────────────────────────────

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GL account."""
        from models.erp.financial import GLAccount, AccountType, AccountCategory

        account = GLAccount(
            account_number=data['account_number'],
            name=data['name'],
            description=data.get('description'),
            account_type=AccountType(data['account_type']),
            account_category=AccountCategory(data['account_category']) if data.get('account_category') else None,
            parent_id=data.get('parent_id'),
            is_active=data.get('is_active', True),
            is_posting=data.get('is_posting', True),
            normal_balance=data.get('normal_balance', 'debit' if data['account_type'] in ['asset', 'expense'] else 'credit'),
            currency=data.get('currency', 'USD'),
            is_bank_account=data.get('is_bank_account', False),
            bank_name=data.get('bank_name'),
            bank_account_number=data.get('bank_account_number'),
            is_control_account=data.get('is_control_account', False),
            subledger_type=data.get('subledger_type'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(account)
        self.session.flush()
        logger.info(f"Created GL account: {account.account_number}")
        return account.to_dict()

    def get_chart_of_accounts(
        self,
        account_type: str = None,
        is_active: bool = True,
        is_posting: bool = None
    ) -> List[Dict[str, Any]]:
        """Get chart of accounts with filtering."""
        from models.erp.financial import GLAccount, AccountType

        query = self.session.query(GLAccount)

        if is_active is not None:
            query = query.filter(GLAccount.is_active == is_active)
        if account_type:
            query = query.filter(GLAccount.account_type == AccountType(account_type))
        if is_posting is not None:
            query = query.filter(GLAccount.is_posting == is_posting)

        accounts = query.order_by(GLAccount.account_number).all()
        return [a.to_dict() for a in accounts]

    def get_account_balance(
        self,
        account_number: str,
        as_of_date: date = None
    ) -> Dict[str, Any]:
        """Get account balance as of a date."""
        from models.erp.financial import GLAccount, JournalLine, JournalEntry, JournalStatus

        as_of_date = as_of_date or date.today()

        account = self.session.query(GLAccount).filter(
            GLAccount.account_number == account_number
        ).first()

        if not account:
            return {'error': 'Account not found'}

        # Sum posted journal lines
        debit_total = self.session.query(func.coalesce(func.sum(JournalLine.debit_amount), 0)).join(
            JournalEntry, JournalLine.journal_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == account.id,
            JournalEntry.status == JournalStatus.POSTED,
            JournalEntry.posting_date <= as_of_date
        ).scalar()

        credit_total = self.session.query(func.coalesce(func.sum(JournalLine.credit_amount), 0)).join(
            JournalEntry, JournalLine.journal_id == JournalEntry.id
        ).filter(
            JournalLine.account_id == account.id,
            JournalEntry.status == JournalStatus.POSTED,
            JournalEntry.posting_date <= as_of_date
        ).scalar()

        balance = float(debit_total) - float(credit_total)
        if account.normal_balance == 'credit':
            balance = -balance

        return {
            'account_number': account_number,
            'account_name': account.name,
            'as_of_date': as_of_date.isoformat(),
            'debit_total': float(debit_total),
            'credit_total': float(credit_total),
            'balance': balance,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Journal Entries
    # ─────────────────────────────────────────────────────────────────────────

    def create_journal_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a journal entry."""
        from models.erp.financial import JournalEntry, JournalLine, JournalStatus

        # Validate lines balance
        lines = data.get('lines', [])
        total_debit = sum(Decimal(str(l.get('debit_amount', 0))) for l in lines)
        total_credit = sum(Decimal(str(l.get('credit_amount', 0))) for l in lines)

        if total_debit != total_credit:
            raise ValueError(f"Journal entry must balance. Debit: {total_debit}, Credit: {total_credit}")

        journal = JournalEntry(
            journal_number=data.get('journal_number', f"JE-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            status=JournalStatus.DRAFT,
            journal_date=data.get('journal_date', date.today()),
            description=data['description'],
            reference=data.get('reference'),
            source_type=data.get('source_type', 'manual'),
            source_id=data.get('source_id'),
            total_debit=total_debit,
            total_credit=total_credit,
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(journal)
        self.session.flush()

        # Create lines
        for i, line_data in enumerate(lines, 1):
            line = JournalLine(
                journal_id=journal.id,
                line_number=i,
                account_id=line_data['account_id'],
                debit_amount=Decimal(str(line_data.get('debit_amount', 0))),
                credit_amount=Decimal(str(line_data.get('credit_amount', 0))),
                description=line_data.get('description'),
                partner_id=line_data.get('partner_id'),
                department=line_data.get('department'),
                project=line_data.get('project'),
                cost_center=line_data.get('cost_center'),
                created_by=data.get('created_by', 'system'),
            )
            self.session.add(line)

        self.session.flush()
        logger.info(f"Created journal entry: {journal.journal_number}")
        return journal.to_dict()

    def post_journal_entry(self, journal_number: str, user_id: str = 'system') -> Dict[str, Any]:
        """Post a journal entry."""
        from models.erp.financial import JournalEntry, JournalStatus

        journal = self.session.query(JournalEntry).filter(
            JournalEntry.journal_number == journal_number
        ).first()

        if not journal:
            raise ValueError("Journal entry not found")

        if journal.status != JournalStatus.DRAFT:
            raise ValueError(f"Cannot post journal in status: {journal.status.value}")

        journal.status = JournalStatus.POSTED
        journal.posting_date = date.today()
        journal.approved_by = user_id
        journal.approved_date = datetime.utcnow()
        journal.updated_by = user_id
        journal.updated_at = datetime.utcnow()

        self.session.flush()
        logger.info(f"Posted journal entry: {journal_number}")
        return journal.to_dict()

    def get_journal_entries(
        self,
        status: str = None,
        start_date: date = None,
        end_date: date = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get journal entries with filtering."""
        from models.erp.financial import JournalEntry, JournalStatus

        query = self.session.query(JournalEntry)

        if status:
            query = query.filter(JournalEntry.status == JournalStatus(status))
        if start_date:
            query = query.filter(JournalEntry.journal_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.journal_date <= end_date)

        journals = query.order_by(JournalEntry.journal_date.desc()).limit(limit).all()
        return [j.to_dict() for j in journals]

    # ─────────────────────────────────────────────────────────────────────────
    # Accounts Payable
    # ─────────────────────────────────────────────────────────────────────────

    def create_ap_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an AP invoice."""
        from models.erp.financial import APInvoice, APInvoiceLine, InvoiceStatus

        # Calculate totals
        lines = data.get('lines', [])
        subtotal = sum(Decimal(str(l.get('line_total', 0))) for l in lines)
        tax = Decimal(str(data.get('tax_amount', 0)))
        freight = Decimal(str(data.get('freight_amount', 0)))
        total = subtotal + tax + freight

        invoice = APInvoice(
            invoice_number=data.get('invoice_number', f"AP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            vendor_invoice_number=data.get('vendor_invoice_number'),
            vendor_id=data['vendor_id'],
            status=InvoiceStatus.DRAFT,
            purchase_order_id=data.get('purchase_order_id'),
            invoice_date=data.get('invoice_date', date.today()),
            due_date=data.get('due_date'),
            payment_terms=data.get('payment_terms'),
            currency=data.get('currency', 'USD'),
            subtotal=subtotal,
            tax_amount=tax,
            freight_amount=freight,
            total=total,
            balance_due=total,
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(invoice)
        self.session.flush()

        # Create lines
        for i, line_data in enumerate(lines, 1):
            line = APInvoiceLine(
                invoice_id=invoice.id,
                line_number=i,
                item_id=line_data.get('item_id'),
                description=line_data['description'],
                quantity=line_data.get('quantity'),
                unit_price=Decimal(str(line_data.get('unit_price', 0))) if line_data.get('unit_price') else None,
                line_total=Decimal(str(line_data['line_total'])),
                gl_account_id=line_data['gl_account_id'],
                department=line_data.get('department'),
                project=line_data.get('project'),
                created_by=data.get('created_by', 'system'),
            )
            self.session.add(line)

        self.session.flush()
        logger.info(f"Created AP invoice: {invoice.invoice_number}")
        return invoice.to_dict()

    def get_ap_invoices(
        self,
        vendor_id: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get AP invoices."""
        from models.erp.financial import APInvoice, InvoiceStatus

        query = self.session.query(APInvoice)

        if vendor_id:
            query = query.filter(APInvoice.vendor_id == vendor_id)
        if status:
            query = query.filter(APInvoice.status == InvoiceStatus(status))

        invoices = query.order_by(APInvoice.invoice_date.desc()).limit(limit).all()
        return [i.to_dict() for i in invoices]

    def get_ap_aging(self) -> Dict[str, Any]:
        """Get AP aging summary."""
        from models.erp.financial import APInvoice, InvoiceStatus

        today = date.today()
        aging = {
            'current': Decimal('0'),
            '1_30': Decimal('0'),
            '31_60': Decimal('0'),
            '61_90': Decimal('0'),
            'over_90': Decimal('0'),
            'total': Decimal('0'),
        }

        invoices = self.session.query(APInvoice).filter(
            APInvoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]),
            APInvoice.balance_due > 0
        ).all()

        for inv in invoices:
            days = (today - inv.due_date).days if inv.due_date else 0
            balance = inv.balance_due or Decimal('0')

            if days <= 0:
                aging['current'] += balance
            elif days <= 30:
                aging['1_30'] += balance
            elif days <= 60:
                aging['31_60'] += balance
            elif days <= 90:
                aging['61_90'] += balance
            else:
                aging['over_90'] += balance

            aging['total'] += balance

        return {k: float(v) for k, v in aging.items()}

    # ─────────────────────────────────────────────────────────────────────────
    # Accounts Receivable
    # ─────────────────────────────────────────────────────────────────────────

    def create_ar_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an AR invoice."""
        from models.erp.financial import ARInvoice, ARInvoiceLine, InvoiceStatus

        # Calculate totals
        lines = data.get('lines', [])
        subtotal = sum(Decimal(str(l.get('line_total', 0))) for l in lines)
        discount = Decimal(str(data.get('discount_amount', 0)))
        tax = Decimal(str(data.get('tax_amount', 0)))
        freight = Decimal(str(data.get('freight_amount', 0)))
        total = subtotal - discount + tax + freight

        invoice = ARInvoice(
            invoice_number=data.get('invoice_number', f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            customer_id=data['customer_id'],
            status=InvoiceStatus.DRAFT,
            sales_order_id=data.get('sales_order_id'),
            invoice_date=data.get('invoice_date', date.today()),
            due_date=data.get('due_date'),
            payment_terms=data.get('payment_terms'),
            currency=data.get('currency', 'USD'),
            subtotal=subtotal,
            discount_amount=discount,
            tax_amount=tax,
            freight_amount=freight,
            total=total,
            balance_due=total,
            bill_to_name=data.get('bill_to_name'),
            bill_to_address1=data.get('bill_to_address1'),
            bill_to_city=data.get('bill_to_city'),
            bill_to_state=data.get('bill_to_state'),
            bill_to_postal=data.get('bill_to_postal'),
            bill_to_country=data.get('bill_to_country'),
            notes=data.get('notes'),
            salesperson_id=data.get('salesperson_id'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(invoice)
        self.session.flush()

        # Create lines
        for i, line_data in enumerate(lines, 1):
            line = ARInvoiceLine(
                invoice_id=invoice.id,
                line_number=i,
                item_id=line_data.get('item_id'),
                description=line_data['description'],
                quantity=line_data.get('quantity'),
                unit_price=Decimal(str(line_data.get('unit_price', 0))) if line_data.get('unit_price') else None,
                discount_percent=line_data.get('discount_percent', 0),
                line_total=Decimal(str(line_data['line_total'])),
                gl_account_id=line_data['gl_account_id'],
                created_by=data.get('created_by', 'system'),
            )
            self.session.add(line)

        self.session.flush()
        logger.info(f"Created AR invoice: {invoice.invoice_number}")
        return invoice.to_dict()

    def get_ar_invoices(
        self,
        customer_id: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get AR invoices."""
        from models.erp.financial import ARInvoice, InvoiceStatus

        query = self.session.query(ARInvoice)

        if customer_id:
            query = query.filter(ARInvoice.customer_id == customer_id)
        if status:
            query = query.filter(ARInvoice.status == InvoiceStatus(status))

        invoices = query.order_by(ARInvoice.invoice_date.desc()).limit(limit).all()
        return [i.to_dict() for i in invoices]

    def get_ar_aging(self) -> Dict[str, Any]:
        """Get AR aging summary."""
        from models.erp.financial import ARInvoice, InvoiceStatus

        today = date.today()
        aging = {
            'current': Decimal('0'),
            '1_30': Decimal('0'),
            '31_60': Decimal('0'),
            '61_90': Decimal('0'),
            'over_90': Decimal('0'),
            'total': Decimal('0'),
        }

        invoices = self.session.query(ARInvoice).filter(
            ARInvoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]),
            ARInvoice.balance_due > 0
        ).all()

        for inv in invoices:
            days = (today - inv.due_date).days if inv.due_date else 0
            balance = inv.balance_due or Decimal('0')

            if days <= 0:
                aging['current'] += balance
            elif days <= 30:
                aging['1_30'] += balance
            elif days <= 60:
                aging['31_60'] += balance
            elif days <= 90:
                aging['61_90'] += balance
            else:
                aging['over_90'] += balance

            aging['total'] += balance

        return {k: float(v) for k, v in aging.items()}

    # ─────────────────────────────────────────────────────────────────────────
    # Payments
    # ─────────────────────────────────────────────────────────────────────────

    def create_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment record."""
        from models.erp.financial import Payment, PaymentApplication

        payment = Payment(
            payment_number=data.get('payment_number', f"PAY-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            payment_type=data['payment_type'],  # 'ap' or 'ar'
            partner_id=data['partner_id'],
            payment_method=data.get('payment_method'),
            check_number=data.get('check_number'),
            reference=data.get('reference'),
            payment_date=data.get('payment_date', date.today()),
            currency=data.get('currency', 'USD'),
            amount=Decimal(str(data['amount'])),
            discount_taken=Decimal(str(data.get('discount_taken', 0))),
            bank_account_id=data.get('bank_account_id'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(payment)
        self.session.flush()

        # Apply to invoices
        for app_data in data.get('applications', []):
            app = PaymentApplication(
                payment_id=payment.id,
                ap_invoice_id=app_data.get('ap_invoice_id'),
                ar_invoice_id=app_data.get('ar_invoice_id'),
                amount_applied=Decimal(str(app_data['amount_applied'])),
                discount_applied=Decimal(str(app_data.get('discount_applied', 0))),
                created_by=data.get('created_by', 'system'),
            )
            self.session.add(app)

            # Update invoice balance
            if app_data.get('ap_invoice_id'):
                from models.erp.financial import APInvoice
                inv = self.session.query(APInvoice).get(app_data['ap_invoice_id'])
                if inv:
                    inv.amount_paid = (inv.amount_paid or Decimal('0')) + Decimal(str(app_data['amount_applied']))
                    inv.balance_due = inv.total - inv.amount_paid
            elif app_data.get('ar_invoice_id'):
                from models.erp.financial import ARInvoice
                inv = self.session.query(ARInvoice).get(app_data['ar_invoice_id'])
                if inv:
                    inv.amount_paid = (inv.amount_paid or Decimal('0')) + Decimal(str(app_data['amount_applied']))
                    inv.balance_due = inv.total - inv.amount_paid

        self.session.flush()
        logger.info(f"Created payment: {payment.payment_number}")
        return payment.to_dict()

    # ─────────────────────────────────────────────────────────────────────────
    # Financial Reports
    # ─────────────────────────────────────────────────────────────────────────

    def get_trial_balance(self, as_of_date: date = None) -> Dict[str, Any]:
        """Generate trial balance report."""
        from models.erp.financial import GLAccount, JournalLine, JournalEntry, JournalStatus

        as_of_date = as_of_date or date.today()
        accounts = []

        gl_accounts = self.session.query(GLAccount).filter(
            GLAccount.is_active == True,
            GLAccount.is_posting == True
        ).order_by(GLAccount.account_number).all()

        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for account in gl_accounts:
            debit = self.session.query(func.coalesce(func.sum(JournalLine.debit_amount), 0)).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == account.id,
                JournalEntry.status == JournalStatus.POSTED,
                JournalEntry.posting_date <= as_of_date
            ).scalar()

            credit = self.session.query(func.coalesce(func.sum(JournalLine.credit_amount), 0)).join(
                JournalEntry, JournalLine.journal_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == account.id,
                JournalEntry.status == JournalStatus.POSTED,
                JournalEntry.posting_date <= as_of_date
            ).scalar()

            if debit > 0 or credit > 0:
                balance_debit = debit - credit if debit > credit else Decimal('0')
                balance_credit = credit - debit if credit > debit else Decimal('0')

                accounts.append({
                    'account_number': account.account_number,
                    'account_name': account.name,
                    'account_type': account.account_type.value,
                    'debit_balance': float(balance_debit),
                    'credit_balance': float(balance_credit),
                })

                total_debit += balance_debit
                total_credit += balance_credit

        return {
            'as_of_date': as_of_date.isoformat(),
            'accounts': accounts,
            'total_debit': float(total_debit),
            'total_credit': float(total_credit),
            'is_balanced': abs(total_debit - total_credit) < Decimal('0.01'),
        }

    def get_income_statement(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate income statement."""
        from models.erp.financial import GLAccount, JournalLine, JournalEntry, JournalStatus, AccountType

        def get_balance_for_type(account_type: AccountType) -> Decimal:
            accounts = self.session.query(GLAccount).filter(
                GLAccount.account_type == account_type,
                GLAccount.is_active == True
            ).all()

            total = Decimal('0')
            for account in accounts:
                debit = self.session.query(func.coalesce(func.sum(JournalLine.debit_amount), 0)).join(
                    JournalEntry, JournalLine.journal_id == JournalEntry.id
                ).filter(
                    JournalLine.account_id == account.id,
                    JournalEntry.status == JournalStatus.POSTED,
                    JournalEntry.posting_date >= start_date,
                    JournalEntry.posting_date <= end_date
                ).scalar()

                credit = self.session.query(func.coalesce(func.sum(JournalLine.credit_amount), 0)).join(
                    JournalEntry, JournalLine.journal_id == JournalEntry.id
                ).filter(
                    JournalLine.account_id == account.id,
                    JournalEntry.status == JournalStatus.POSTED,
                    JournalEntry.posting_date >= start_date,
                    JournalEntry.posting_date <= end_date
                ).scalar()

                # Revenue accounts have credit normal balance
                if account_type == AccountType.REVENUE:
                    total += credit - debit
                else:
                    total += debit - credit

            return total

        revenue = get_balance_for_type(AccountType.REVENUE)
        expenses = get_balance_for_type(AccountType.EXPENSE)
        net_income = revenue - expenses

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'revenue': float(revenue),
            'expenses': float(expenses),
            'net_income': float(net_income),
        }


def get_financial_service(session: Session) -> FinancialService:
    """Get financial service instance."""
    return FinancialService(session)
