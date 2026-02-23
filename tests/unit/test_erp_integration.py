"""
Unit Tests for ERP Integration Services.

Tests General Ledger, Accounts Receivable/Payable, and EDI processing.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.services.erp.gl_integration import (
    GeneralLedgerService, AccountType, JournalEntryType,
    create_gl_service
)
from dashboard.services.erp.ar_ap_service import (
    AccountsReceivableService, AccountsPayableService,
    InvoiceStatus, PaymentTerms, create_ar_service, create_ap_service
)
from dashboard.services.erp.edi_processor import (
    EDIProcessor, TransactionType, create_edi_processor
)


class TestGeneralLedgerService:
    """Tests for General Ledger integration."""

    @pytest.fixture
    def gl_service(self):
        """Create GL service instance."""
        return create_gl_service()

    @pytest.mark.asyncio
    async def test_create_account(self, gl_service):
        """Test creating a GL account."""
        account = await gl_service.create_account(
            account_number="1000",
            account_name="Cash",
            account_type=AccountType.ASSET,
            description="Cash and cash equivalents"
        )

        assert account.account_number == "1000"
        assert account.account_name == "Cash"
        assert account.account_type == AccountType.ASSET
        assert account.balance == 0.0
        assert account.is_active

    @pytest.mark.asyncio
    async def test_create_journal_entry(self, gl_service):
        """Test creating a balanced journal entry."""
        # Create accounts
        cash = await gl_service.create_account("1000", "Cash", AccountType.ASSET)
        revenue = await gl_service.create_account("4000", "Revenue", AccountType.REVENUE)

        # Create journal entry
        entry = await gl_service.create_journal_entry(
            entry_type=JournalEntryType.STANDARD,
            description="Record sale",
            debit_account="1000",
            credit_account="4000",
            amount=1000.0,
            created_by="test_user"
        )

        assert entry.entry_type == JournalEntryType.STANDARD
        assert entry.is_balanced()
        assert entry.total_debits == 1000.0
        assert entry.total_credits == 1000.0

    @pytest.mark.asyncio
    async def test_post_journal_entry(self, gl_service):
        """Test posting a journal entry updates balances."""
        # Create accounts
        await gl_service.create_account("1000", "Cash", AccountType.ASSET)
        await gl_service.create_account("4000", "Revenue", AccountType.REVENUE)

        # Create and post entry
        entry = await gl_service.create_journal_entry(
            entry_type=JournalEntryType.STANDARD,
            description="Record sale",
            debit_account="1000",
            credit_account="4000",
            amount=1000.0,
            created_by="test_user"
        )

        posted_entry = await gl_service.post_entry(entry.entry_id, "approver")

        assert posted_entry.status == "posted"

        # Check balances updated
        cash_account = gl_service.accounts["1000"]
        revenue_account = gl_service.accounts["4000"]

        assert cash_account.balance == 1000.0
        assert revenue_account.balance == 1000.0

    @pytest.mark.asyncio
    async def test_trial_balance(self, gl_service):
        """Test generating trial balance."""
        # Create and post entries
        await gl_service.create_account("1000", "Cash", AccountType.ASSET)
        await gl_service.create_account("2000", "Accounts Payable", AccountType.LIABILITY)
        await gl_service.create_account("4000", "Revenue", AccountType.REVENUE)

        entry = await gl_service.create_journal_entry(
            entry_type=JournalEntryType.STANDARD,
            description="Test entry",
            debit_account="1000",
            credit_account="4000",
            amount=500.0,
            created_by="test_user"
        )
        await gl_service.post_entry(entry.entry_id, "approver")

        trial_balance = await gl_service.get_trial_balance()

        assert trial_balance["is_balanced"]
        assert trial_balance["total_debits"] == trial_balance["total_credits"]

    @pytest.mark.asyncio
    async def test_record_material_purchase(self, gl_service):
        """Test recording material purchase."""
        # Initialize standard accounts
        await gl_service.initialize_manufacturing_coa()

        entry = await gl_service.record_material_purchase(
            material_id="MAT-001",
            vendor_id="VENDOR-001",
            amount=5000.0,
            created_by="purchasing"
        )

        assert entry is not None
        assert entry.description == "Material purchase: MAT-001 from VENDOR-001"


class TestAccountsReceivableService:
    """Tests for Accounts Receivable service."""

    @pytest.fixture
    def ar_service(self):
        """Create AR service instance."""
        return create_ar_service()

    @pytest.mark.asyncio
    async def test_create_invoice(self, ar_service):
        """Test creating an invoice."""
        invoice = await ar_service.create_invoice(
            customer_id="CUST-001",
            customer_name="Test Customer",
            amount=1000.0,
            payment_terms=PaymentTerms.NET_30,
            line_items=[
                {"description": "Product A", "quantity": 10, "unit_price": 100.0}
            ],
            created_by="sales"
        )

        assert invoice.customer_id == "CUST-001"
        assert invoice.amount == 1000.0
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.payment_terms == PaymentTerms.NET_30

    @pytest.mark.asyncio
    async def test_post_invoice(self, ar_service):
        """Test posting an invoice sets due date."""
        invoice = await ar_service.create_invoice(
            customer_id="CUST-001",
            customer_name="Test Customer",
            amount=500.0,
            payment_terms=PaymentTerms.NET_30,
            created_by="sales"
        )

        posted = await ar_service.post_invoice(invoice.invoice_id, "approver")

        assert posted.status == InvoiceStatus.OPEN
        assert posted.due_date is not None
        # NET_30 should be ~30 days from now
        days_until_due = (posted.due_date - datetime.now()).days
        assert 29 <= days_until_due <= 31

    @pytest.mark.asyncio
    async def test_apply_payment(self, ar_service):
        """Test applying payment to invoice."""
        invoice = await ar_service.create_invoice(
            customer_id="CUST-001",
            customer_name="Test Customer",
            amount=1000.0,
            payment_terms=PaymentTerms.NET_30,
            created_by="sales"
        )
        await ar_service.post_invoice(invoice.invoice_id, "approver")

        # Partial payment
        updated = await ar_service.apply_payment(
            invoice_id=invoice.invoice_id,
            amount=400.0,
            payment_method="check",
            reference="CHK-12345"
        )

        assert updated.amount_paid == 400.0
        assert updated.balance_due == 600.0
        assert updated.status == InvoiceStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_full_payment_closes_invoice(self, ar_service):
        """Test full payment closes invoice."""
        invoice = await ar_service.create_invoice(
            customer_id="CUST-001",
            customer_name="Test Customer",
            amount=500.0,
            payment_terms=PaymentTerms.DUE_ON_RECEIPT,
            created_by="sales"
        )
        await ar_service.post_invoice(invoice.invoice_id, "approver")

        updated = await ar_service.apply_payment(
            invoice_id=invoice.invoice_id,
            amount=500.0,
            payment_method="wire"
        )

        assert updated.amount_paid == 500.0
        assert updated.balance_due == 0.0
        assert updated.status == InvoiceStatus.PAID

    @pytest.mark.asyncio
    async def test_aging_report(self, ar_service):
        """Test generating aging report."""
        # Create invoices with different ages
        invoice1 = await ar_service.create_invoice(
            customer_id="CUST-001",
            customer_name="Customer 1",
            amount=1000.0,
            payment_terms=PaymentTerms.NET_30,
            created_by="sales"
        )
        await ar_service.post_invoice(invoice1.invoice_id, "approver")

        aging = await ar_service.get_aging_report()

        assert "current" in aging
        assert "period_1_30" in aging
        assert aging["total_outstanding"] >= 1000.0


class TestAccountsPayableService:
    """Tests for Accounts Payable service."""

    @pytest.fixture
    def ap_service(self):
        """Create AP service instance."""
        return create_ap_service()

    @pytest.mark.asyncio
    async def test_create_bill(self, ap_service):
        """Test creating a vendor bill."""
        bill = await ap_service.create_bill(
            vendor_id="VENDOR-001",
            vendor_name="Test Vendor",
            amount=2000.0,
            payment_terms=PaymentTerms.NET_45,
            invoice_number="VINV-001",
            line_items=[
                {"description": "Raw material", "quantity": 100, "unit_price": 20.0}
            ],
            created_by="purchasing"
        )

        assert bill.vendor_id == "VENDOR-001"
        assert bill.amount == 2000.0
        assert bill.vendor_invoice_number == "VINV-001"

    @pytest.mark.asyncio
    async def test_approve_bill(self, ap_service):
        """Test approving a bill for payment."""
        bill = await ap_service.create_bill(
            vendor_id="VENDOR-001",
            vendor_name="Test Vendor",
            amount=1500.0,
            payment_terms=PaymentTerms.NET_30,
            invoice_number="VINV-002",
            created_by="purchasing"
        )

        approved = await ap_service.approve_bill(bill.bill_id, "manager")

        assert approved.status == InvoiceStatus.APPROVED

    @pytest.mark.asyncio
    async def test_process_payment(self, ap_service):
        """Test processing payment for a bill."""
        bill = await ap_service.create_bill(
            vendor_id="VENDOR-001",
            vendor_name="Test Vendor",
            amount=750.0,
            payment_terms=PaymentTerms.NET_30,
            invoice_number="VINV-003",
            created_by="purchasing"
        )
        await ap_service.approve_bill(bill.bill_id, "manager")

        paid = await ap_service.process_payment(
            bill_id=bill.bill_id,
            amount=750.0,
            payment_method="ach",
            bank_account="MAIN-CHECKING"
        )

        assert paid.amount_paid == 750.0
        assert paid.status == InvoiceStatus.PAID


class TestEDIProcessor:
    """Tests for EDI processing."""

    @pytest.fixture
    def edi_processor(self):
        """Create EDI processor instance."""
        return create_edi_processor()

    @pytest.mark.asyncio
    async def test_register_trading_partner(self, edi_processor):
        """Test registering a trading partner."""
        partner = await edi_processor.register_trading_partner(
            partner_name="Acme Corp",
            partner_code="ACME",
            isa_id="ACME12345",
            gs_id="ACME",
            transaction_types=[TransactionType.PO_850, TransactionType.INVOICE_810],
            protocol="AS2"
        )

        assert partner.partner_name == "Acme Corp"
        assert partner.partner_code == "ACME"
        assert TransactionType.PO_850 in partner.transaction_types

    @pytest.mark.asyncio
    async def test_parse_x12_850(self, edi_processor):
        """Test parsing X12 850 Purchase Order."""
        # Register partner first
        await edi_processor.register_trading_partner(
            partner_name="Test Partner",
            partner_code="TEST",
            isa_id="TESTID123",
            gs_id="TEST"
        )

        # Simple X12 850 structure
        x12_data = """ISA*00*          *00*          *ZZ*TESTID123     *ZZ*RECEIVER123   *231215*1200*U*00401*000000001*0*P*>~
GS*PO*TEST*RECEIVER*20231215*1200*1*X*004010~
ST*850*0001~
BEG*00*NE*PO12345**20231215~
PO1*1*10*EA*25.00**BP*ITEM-001~
CTT*1~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

        result = await edi_processor.parse_x12(x12_data)

        assert result is not None
        assert result.transaction_type == TransactionType.PO_850
        assert "order_number" in result.data

    @pytest.mark.asyncio
    async def test_generate_997_acknowledgment(self, edi_processor):
        """Test generating 997 functional acknowledgment."""
        # Register partner
        await edi_processor.register_trading_partner(
            partner_name="Test Partner",
            partner_code="TEST",
            isa_id="TESTID123",
            gs_id="TEST"
        )

        ack = await edi_processor.generate_997_acknowledgment(
            partner_id="TEST",
            original_gs_control="12345",
            original_transaction_id="ST0001",
            accepted=True
        )

        assert ack is not None
        assert "997" in ack or "FA" in ack.upper()


class TestIntegrationScenarios:
    """Integration tests for ERP scenarios."""

    @pytest.mark.asyncio
    async def test_purchase_to_pay_cycle(self):
        """Test complete purchase-to-pay cycle."""
        gl = create_gl_service()
        ap = create_ap_service()
        edi = create_edi_processor()

        # Initialize GL
        await gl.initialize_manufacturing_coa()

        # Register vendor as trading partner
        await edi.register_trading_partner(
            partner_name="Material Supplier",
            partner_code="MATSUP",
            isa_id="MATSUP123",
            gs_id="MATSUP"
        )

        # Create bill for materials received
        bill = await ap.create_bill(
            vendor_id="MATSUP",
            vendor_name="Material Supplier",
            amount=10000.0,
            payment_terms=PaymentTerms.NET_30,
            invoice_number="SUP-INV-001",
            created_by="receiving"
        )

        # Approve bill
        await ap.approve_bill(bill.bill_id, "ap_manager")

        # Record in GL
        await gl.record_material_purchase(
            material_id="RAW-MAT-001",
            vendor_id="MATSUP",
            amount=10000.0,
            created_by="ap_system"
        )

        # Process payment
        paid_bill = await ap.process_payment(
            bill_id=bill.bill_id,
            amount=10000.0,
            payment_method="ach",
            bank_account="CHECKING"
        )

        assert paid_bill.status == InvoiceStatus.PAID

        # Verify trial balance
        trial_balance = await gl.get_trial_balance()
        assert trial_balance["is_balanced"]

    @pytest.mark.asyncio
    async def test_order_to_cash_cycle(self):
        """Test complete order-to-cash cycle."""
        gl = create_gl_service()
        ar = create_ar_service()

        # Initialize GL
        await gl.initialize_manufacturing_coa()

        # Create and post invoice
        invoice = await ar.create_invoice(
            customer_id="CUST-ABC",
            customer_name="ABC Manufacturing",
            amount=5000.0,
            payment_terms=PaymentTerms.NET_30,
            line_items=[
                {"description": "Custom LEGO bricks", "quantity": 500, "unit_price": 10.0}
            ],
            created_by="order_mgmt"
        )

        await ar.post_invoice(invoice.invoice_id, "sales_mgr")

        # Record revenue in GL
        entry = await gl.record_sale(
            order_id="ORD-001",
            customer_id="CUST-ABC",
            amount=5000.0,
            created_by="ar_system"
        )

        # Receive payment
        await ar.apply_payment(
            invoice_id=invoice.invoice_id,
            amount=5000.0,
            payment_method="wire",
            reference="WIRE-REF-001"
        )

        # Verify
        updated_invoice = ar.invoices[invoice.invoice_id]
        assert updated_invoice.status == InvoiceStatus.PAID

        dso = await ar.calculate_dso()
        assert dso >= 0  # DSO should be calculated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
