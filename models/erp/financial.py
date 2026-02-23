"""
LEGO Factory v3 - ERP Financial Models
=======================================
General Ledger, Accounts Payable, Accounts Receivable.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from decimal import Decimal

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class AccountType(str, Enum):
    """GL Account type."""
    ASSET = 'asset'
    LIABILITY = 'liability'
    EQUITY = 'equity'
    REVENUE = 'revenue'
    EXPENSE = 'expense'


class AccountCategory(str, Enum):
    """GL Account category."""
    CASH = 'cash'
    RECEIVABLE = 'receivable'
    INVENTORY = 'inventory'
    FIXED_ASSET = 'fixed_asset'
    PAYABLE = 'payable'
    ACCRUED = 'accrued'
    EQUITY = 'equity'
    SALES = 'sales'
    COGS = 'cogs'
    OPERATING_EXPENSE = 'operating_expense'
    OTHER_INCOME = 'other_income'
    OTHER_EXPENSE = 'other_expense'


class JournalStatus(str, Enum):
    """Journal entry status."""
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    POSTED = 'posted'
    REVERSED = 'reversed'


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    SENT = 'sent'
    PARTIALLY_PAID = 'partially_paid'
    PAID = 'paid'
    VOIDED = 'voided'


class FiscalYear(AuditedModel):
    """Fiscal year definition."""

    __tablename__ = 'fiscal_years'

    year = Column(Integer, unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    is_closed = Column(Boolean, default=False)
    closed_date = Column(DateTime)
    closed_by = Column(String(50))

    # Relationships
    periods = relationship('FiscalPeriod', back_populates='fiscal_year', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'year': self.year,
            'name': self.name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_closed': self.is_closed,
        }


class FiscalPeriod(AuditedModel):
    """Fiscal period (month) within a fiscal year."""

    __tablename__ = 'fiscal_periods'

    fiscal_year_id = Column(UUID(as_uuid=True), ForeignKey('fiscal_years.id'), nullable=False)
    period_number = Column(Integer, nullable=False)  # 1-12 (or 13 for adjustments)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    is_closed = Column(Boolean, default=False)
    is_adjustment = Column(Boolean, default=False)  # For year-end adjustments

    closed_date = Column(DateTime)
    closed_by = Column(String(50))

    # Relationships
    fiscal_year = relationship('FiscalYear', back_populates='periods')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'period_number': self.period_number,
            'name': self.name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_closed': self.is_closed,
        }


class GLAccount(AuditedModel):
    """General Ledger account."""

    __tablename__ = 'gl_accounts'

    account_number = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Classification
    account_type = Column(SQLEnum(AccountType), nullable=False)
    account_category = Column(SQLEnum(AccountCategory))
    parent_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))

    # Behavior
    is_active = Column(Boolean, default=True)
    is_posting = Column(Boolean, default=True)  # False = summary account
    normal_balance = Column(String(10))  # 'debit' or 'credit'

    # Currency
    currency = Column(String(3), default='USD')

    # Control
    is_bank_account = Column(Boolean, default=False)
    bank_name = Column(String(200))
    bank_account_number = Column(String(100))

    is_control_account = Column(Boolean, default=False)  # AR/AP control
    subledger_type = Column(String(50))  # 'ar', 'ap', 'inventory'

    # Budget
    budget_amount = Column(Float)

    # Relationships
    parent = relationship('GLAccount', remote_side='GLAccount.id', backref='children')

    __table_args__ = (
        Index('ix_gl_type', 'account_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'account_number': self.account_number,
            'name': self.name,
            'account_type': self.account_type.value if self.account_type else None,
            'account_category': self.account_category.value if self.account_category else None,
            'is_active': self.is_active,
            'is_posting': self.is_posting,
        }


class JournalEntry(AuditedModel):
    """Journal entry header."""

    __tablename__ = 'journal_entries'

    journal_number = Column(String(50), unique=True, nullable=False, index=True)

    # Status
    status = Column(SQLEnum(JournalStatus), default=JournalStatus.DRAFT)

    # Dates
    journal_date = Column(Date, nullable=False)
    posting_date = Column(Date)
    period_id = Column(UUID(as_uuid=True), ForeignKey('fiscal_periods.id'))

    # Description
    description = Column(String(500), nullable=False)
    reference = Column(String(100))

    # Source
    source_type = Column(String(50))  # 'manual', 'inventory', 'ap', 'ar', etc.
    source_id = Column(String(50))

    # Totals (should balance)
    total_debit = Column(Numeric(18, 2), default=0)
    total_credit = Column(Numeric(18, 2), default=0)

    # Approval
    approved_by = Column(String(50))
    approved_date = Column(DateTime)

    # Reversal
    is_reversing = Column(Boolean, default=False)
    reversed_journal_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'))
    reversal_date = Column(Date)

    # Relationships
    period = relationship('FiscalPeriod')
    lines = relationship('JournalLine', back_populates='journal', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_je_date', 'journal_date'),
        Index('ix_je_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'journal_number': self.journal_number,
            'status': self.status.value if self.status else None,
            'journal_date': self.journal_date.isoformat() if self.journal_date else None,
            'description': self.description,
            'total_debit': float(self.total_debit) if self.total_debit else 0,
            'total_credit': float(self.total_credit) if self.total_credit else 0,
        }


class JournalLine(AuditedModel):
    """Journal entry line."""

    __tablename__ = 'journal_lines'

    journal_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Account
    account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'), nullable=False)

    # Amount (one should be zero)
    debit_amount = Column(Numeric(18, 2), default=0)
    credit_amount = Column(Numeric(18, 2), default=0)

    # Description
    description = Column(String(500))

    # Subledger reference
    partner_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'))
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'))

    # Dimensions
    department = Column(String(50))
    project = Column(String(50))
    cost_center = Column(String(50))

    # Relationships
    journal = relationship('JournalEntry', back_populates='lines')
    account = relationship('GLAccount')
    partner = relationship('Partner')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'journal_id': str(self.journal_id),
            'line_number': self.line_number,
            'account_id': str(self.account_id),
            'debit_amount': float(self.debit_amount) if self.debit_amount else 0,
            'credit_amount': float(self.credit_amount) if self.credit_amount else 0,
            'description': self.description,
        }


class APInvoice(AuditedModel):
    """Accounts Payable invoice."""

    __tablename__ = 'ap_invoices'

    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    vendor_invoice_number = Column(String(100))

    # Vendor
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)

    # Status
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    # Source
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'))
    receipt_id = Column(UUID(as_uuid=True), ForeignKey('receipts.id'))

    # Dates
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date)
    posting_date = Column(Date)

    # Payment terms
    payment_terms = Column(String(50))
    discount_date = Column(Date)
    discount_percent = Column(Float, default=0)

    # Amounts
    currency = Column(String(3), default='USD')
    subtotal = Column(Numeric(18, 2), default=0)
    tax_amount = Column(Numeric(18, 2), default=0)
    freight_amount = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    amount_paid = Column(Numeric(18, 2), default=0)
    balance_due = Column(Numeric(18, 2), default=0)

    # GL
    gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))
    journal_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'))

    notes = Column(Text)

    # Approval
    approved_by = Column(String(50))
    approved_date = Column(DateTime)

    # Relationships
    vendor = relationship('Partner')
    purchase_order = relationship('PurchaseOrder')
    lines = relationship('APInvoiceLine', back_populates='invoice', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_ap_vendor', 'vendor_id'),
        Index('ix_ap_status', 'status'),
        Index('ix_ap_due_date', 'due_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'invoice_number': self.invoice_number,
            'vendor_id': str(self.vendor_id),
            'vendor_invoice_number': self.vendor_invoice_number,
            'status': self.status.value if self.status else None,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'total': float(self.total) if self.total else 0,
            'balance_due': float(self.balance_due) if self.balance_due else 0,
        }


class APInvoiceLine(AuditedModel):
    """AP invoice line item."""

    __tablename__ = 'ap_invoice_lines'

    invoice_id = Column(UUID(as_uuid=True), ForeignKey('ap_invoices.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item (optional)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'))
    description = Column(String(500), nullable=False)

    # Quantity and amount
    quantity = Column(Float)
    unit_price = Column(Numeric(18, 4))
    line_total = Column(Numeric(18, 2), nullable=False)

    # GL Distribution
    gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'), nullable=False)
    department = Column(String(50))
    project = Column(String(50))

    # PO reference
    po_line_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_lines.id'))

    # Relationships
    invoice = relationship('APInvoice', back_populates='lines')
    account = relationship('GLAccount')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'invoice_id': str(self.invoice_id),
            'line_number': self.line_number,
            'description': self.description,
            'line_total': float(self.line_total) if self.line_total else 0,
        }


class ARInvoice(AuditedModel):
    """Accounts Receivable invoice."""

    __tablename__ = 'ar_invoices'

    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    # Customer
    customer_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)

    # Status
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    # Source
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey('sales_orders.id'))
    shipment_id = Column(UUID(as_uuid=True), ForeignKey('shipments.id'))

    # Dates
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date)
    posting_date = Column(Date)

    # Payment terms
    payment_terms = Column(String(50))

    # Amounts
    currency = Column(String(3), default='USD')
    subtotal = Column(Numeric(18, 2), default=0)
    discount_amount = Column(Numeric(18, 2), default=0)
    tax_amount = Column(Numeric(18, 2), default=0)
    freight_amount = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    amount_paid = Column(Numeric(18, 2), default=0)
    balance_due = Column(Numeric(18, 2), default=0)

    # Billing address
    bill_to_name = Column(String(200))
    bill_to_address1 = Column(String(200))
    bill_to_address2 = Column(String(200))
    bill_to_city = Column(String(100))
    bill_to_state = Column(String(100))
    bill_to_postal = Column(String(20))
    bill_to_country = Column(String(100))

    # GL
    gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))
    journal_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'))

    notes = Column(Text)

    # Salesperson
    salesperson_id = Column(String(50))

    # Relationships
    customer = relationship('Partner')
    sales_order = relationship('SalesOrder')
    lines = relationship('ARInvoiceLine', back_populates='invoice', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_ar_customer', 'customer_id'),
        Index('ix_ar_status', 'status'),
        Index('ix_ar_due_date', 'due_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'invoice_number': self.invoice_number,
            'customer_id': str(self.customer_id),
            'status': self.status.value if self.status else None,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'total': float(self.total) if self.total else 0,
            'balance_due': float(self.balance_due) if self.balance_due else 0,
        }


class ARInvoiceLine(AuditedModel):
    """AR invoice line item."""

    __tablename__ = 'ar_invoice_lines'

    invoice_id = Column(UUID(as_uuid=True), ForeignKey('ar_invoices.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'))
    description = Column(String(500), nullable=False)

    # Quantity and amount
    quantity = Column(Float)
    unit_price = Column(Numeric(18, 4))
    discount_percent = Column(Float, default=0)
    line_total = Column(Numeric(18, 2), nullable=False)

    # GL Distribution
    gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'), nullable=False)

    # SO reference
    so_line_id = Column(UUID(as_uuid=True), ForeignKey('sales_order_lines.id'))

    # Relationships
    invoice = relationship('ARInvoice', back_populates='lines')
    account = relationship('GLAccount')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'invoice_id': str(self.invoice_id),
            'line_number': self.line_number,
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price) if self.unit_price else 0,
            'line_total': float(self.line_total) if self.line_total else 0,
        }


class Payment(AuditedModel):
    """Payment record (for both AP and AR)."""

    __tablename__ = 'payments'

    payment_number = Column(String(50), unique=True, nullable=False, index=True)

    # Type
    payment_type = Column(String(20), nullable=False)  # 'ap' or 'ar'
    partner_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)

    # Method
    payment_method = Column(String(50))  # 'check', 'eft', 'wire', 'credit_card'
    check_number = Column(String(50))
    reference = Column(String(100))

    # Dates
    payment_date = Column(Date, nullable=False)
    posting_date = Column(Date)

    # Amount
    currency = Column(String(3), default='USD')
    amount = Column(Numeric(18, 2), nullable=False)
    discount_taken = Column(Numeric(18, 2), default=0)

    # Bank
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))

    # GL
    journal_id = Column(UUID(as_uuid=True), ForeignKey('journal_entries.id'))

    notes = Column(Text)

    # Relationships
    partner = relationship('Partner')
    bank_account = relationship('GLAccount')
    applications = relationship('PaymentApplication', back_populates='payment', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'payment_number': self.payment_number,
            'payment_type': self.payment_type,
            'partner_id': str(self.partner_id),
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount) if self.amount else 0,
        }


class PaymentApplication(AuditedModel):
    """Payment application to invoice."""

    __tablename__ = 'payment_applications'

    payment_id = Column(UUID(as_uuid=True), ForeignKey('payments.id'), nullable=False)

    # Invoice reference (one or the other)
    ap_invoice_id = Column(UUID(as_uuid=True), ForeignKey('ap_invoices.id'))
    ar_invoice_id = Column(UUID(as_uuid=True), ForeignKey('ar_invoices.id'))

    # Amount applied
    amount_applied = Column(Numeric(18, 2), nullable=False)
    discount_applied = Column(Numeric(18, 2), default=0)

    # Relationships
    payment = relationship('Payment', back_populates='applications')
    ap_invoice = relationship('APInvoice')
    ar_invoice = relationship('ARInvoice')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'payment_id': str(self.payment_id),
            'ap_invoice_id': str(self.ap_invoice_id) if self.ap_invoice_id else None,
            'ar_invoice_id': str(self.ar_invoice_id) if self.ar_invoice_id else None,
            'amount_applied': float(self.amount_applied) if self.amount_applied else 0,
        }


class BudgetLine(BaseModel):
    """Budget line item for a GL account within a fiscal period."""

    __tablename__ = 'budget_lines'

    fiscal_year = Column(String(10), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'), nullable=False)
    period = Column(Integer)  # month number 1-12
    amount = Column(Float, default=0)
    notes = Column(Text)

    # Relationships
    account = relationship('GLAccount')

    __table_args__ = (
        Index('ix_budget_year_account', 'fiscal_year', 'account_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'fiscal_year': self.fiscal_year,
            'account_id': str(self.account_id),
            'period': self.period,
            'amount': self.amount,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
