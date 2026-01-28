"""ERP, QMS, CMMS, LEGO, ML tables

Revision ID: 002_erp_qms
Revises: 001_initial
Create Date: 2024-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_erp_qms'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # ERP - Partners
    # ==========================================================================
    op.create_table('partners',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('partner_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('partner_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('payment_terms', sa.String(50), nullable=True),
        sa.Column('credit_limit', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('partner_id')
    )

    op.create_table('contacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('partner_addresses',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('address_type', sa.String(50), nullable=True),
        sa.Column('address_line1', sa.String(200), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # ERP - Items
    # ==========================================================================
    op.create_table('units_of_measure',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('uom_code', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uom_code')
    )

    op.create_table('item_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('category_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['item_categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_code')
    )

    op.create_table('items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('item_number', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('item_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('uom_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('standard_cost', sa.Float(), nullable=True),
        sa.Column('list_price', sa.Float(), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), nullable=True),
        sa.Column('safety_stock', sa.Float(), nullable=True),
        sa.Column('reorder_point', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['item_categories.id']),
        sa.ForeignKeyConstraint(['uom_id'], ['units_of_measure.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_number')
    )

    op.create_table('bom_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('parent_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('component_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['component_item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('routings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('routing_id', sa.String(50), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('routing_id')
    )

    op.create_table('routing_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('routing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('work_center', sa.String(100), nullable=True),
        sa.Column('setup_time_mins', sa.Float(), nullable=True),
        sa.Column('run_time_mins', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['routing_id'], ['routings.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('vendor_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_part_number', sa.String(100), nullable=True),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), nullable=True),
        sa.Column('is_preferred', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['vendor_id'], ['partners.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('price_lists',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('price_list_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('price_list_id')
    )

    op.create_table('price_list_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('price_list_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['price_list_id'], ['price_lists.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # ERP - Inventory
    # ==========================================================================
    op.create_table('locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('location_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('location_type', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_code')
    )

    op.create_table('bins',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bin_code', sa.String(50), nullable=False),
        sa.Column('description', sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('lots',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('lot_number', sa.String(100), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lot_number')
    )

    op.create_table('serial_numbers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('serial_number', sa.String(100), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('serial_number')
    )

    op.create_table('inventory_balances',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_on_hand', sa.Float(), default=0),
        sa.Column('quantity_reserved', sa.Float(), default=0),
        sa.Column('quantity_available', sa.Float(), default=0),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('inventory_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('transaction_id', sa.String(50), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id')
    )

    # ==========================================================================
    # ERP - Sales
    # ==========================================================================
    op.create_table('sales_quotes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('quote_number', sa.String(50), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quote_date', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quote_number')
    )

    op.create_table('sales_quote_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('line_total', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['quote_id'], ['sales_quotes.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('sales_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('order_number', sa.String(50), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False),
        sa.Column('requested_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number')
    )

    op.create_table('sales_order_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('quantity_shipped', sa.Float(), default=0),
        sa.Column('line_total', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['sales_orders.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('shipments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('shipment_number', sa.String(50), nullable=False),
        sa.Column('sales_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ship_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('tracking_number', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shipment_number')
    )

    op.create_table('shipment_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_line_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity_shipped', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id']),
        sa.ForeignKeyConstraint(['order_line_id'], ['sales_order_lines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # ERP - Purchasing
    # ==========================================================================
    op.create_table('purchase_requisitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('requisition_number', sa.String(50), nullable=False),
        sa.Column('requester', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('request_date', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('requisition_number')
    )

    op.create_table('purchase_requisition_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('needed_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['requisition_id'], ['purchase_requisitions.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('purchase_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('order_number', sa.String(50), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False),
        sa.Column('expected_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number')
    )

    op.create_table('purchase_order_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('quantity_received', sa.Float(), default=0),
        sa.ForeignKeyConstraint(['order_id'], ['purchase_orders.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('receipts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('receipt_number', sa.String(50), nullable=False),
        sa.Column('purchase_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('receipt_number')
    )

    op.create_table('receipt_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('receipt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_line_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity_received', sa.Float(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id']),
        sa.ForeignKeyConstraint(['po_line_id'], ['purchase_order_lines.id']),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # ERP - Financial (Core tables only)
    # ==========================================================================
    op.create_table('fiscal_years',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year')
    )

    op.create_table('fiscal_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('fiscal_year_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_number', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['fiscal_year_id'], ['fiscal_years.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('gl_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('account_type', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_number')
    )

    op.create_table('journal_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('entry_number', sa.String(50), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('total_debit', sa.Float(), nullable=True),
        sa.Column('total_credit', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entry_number')
    )

    op.create_table('journal_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('debit', sa.Float(), default=0),
        sa.Column('credit', sa.Float(), default=0),
        sa.Column('description', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['entry_id'], ['journal_entries.id']),
        sa.ForeignKeyConstraint(['account_id'], ['gl_accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ap_invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('invoice_number', sa.String(100), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('amount_paid', sa.Float(), default=0),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ap_invoice_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['ap_invoices.id']),
        sa.ForeignKeyConstraint(['account_id'], ['gl_accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ar_invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('invoice_number', sa.String(100), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('amount_paid', sa.Float(), default=0),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ar_invoice_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['ar_invoices.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('payment_number', sa.String(50), nullable=False),
        sa.Column('payment_type', sa.String(50), nullable=False),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_number')
    )

    op.create_table('payment_applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_type', sa.String(10), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount_applied', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('payment_applications')
    op.drop_table('payments')
    op.drop_table('ar_invoice_lines')
    op.drop_table('ar_invoices')
    op.drop_table('ap_invoice_lines')
    op.drop_table('ap_invoices')
    op.drop_table('journal_lines')
    op.drop_table('journal_entries')
    op.drop_table('gl_accounts')
    op.drop_table('fiscal_periods')
    op.drop_table('fiscal_years')
    op.drop_table('receipt_lines')
    op.drop_table('receipts')
    op.drop_table('purchase_order_lines')
    op.drop_table('purchase_orders')
    op.drop_table('purchase_requisition_lines')
    op.drop_table('purchase_requisitions')
    op.drop_table('shipment_lines')
    op.drop_table('shipments')
    op.drop_table('sales_order_lines')
    op.drop_table('sales_orders')
    op.drop_table('sales_quote_lines')
    op.drop_table('sales_quotes')
    op.drop_table('inventory_transactions')
    op.drop_table('inventory_balances')
    op.drop_table('serial_numbers')
    op.drop_table('lots')
    op.drop_table('bins')
    op.drop_table('locations')
    op.drop_table('price_list_items')
    op.drop_table('price_lists')
    op.drop_table('vendor_items')
    op.drop_table('routing_operations')
    op.drop_table('routings')
    op.drop_table('bom_lines')
    op.drop_table('items')
    op.drop_table('item_categories')
    op.drop_table('units_of_measure')
    op.drop_table('partner_addresses')
    op.drop_table('contacts')
    op.drop_table('partners')
