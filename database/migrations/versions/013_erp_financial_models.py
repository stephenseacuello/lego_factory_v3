"""
Migration 013 - ERP Financial Models (Batches C & D)
=====================================================
Fixed assets, depreciation, bank reconciliation, tax, budgets,
material shortages, and PM tasks.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # ----- Fixed Assets -----
    op.create_table(
        'fixed_assets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('acquisition_date', sa.Date()),
        sa.Column('acquisition_cost', sa.Float(), default=0),
        sa.Column('useful_life_months', sa.Integer()),
        sa.Column('salvage_value', sa.Float(), default=0),
        sa.Column('depreciation_method', sa.String(50)),
        sa.Column('accumulated_depreciation', sa.Float(), default=0),
        sa.Column('net_book_value', sa.Float(), default=0),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('location_id', sa.String(100)),
        sa.Column('department', sa.String(100)),
        # AuditedModel fields
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('deleted_at', sa.DateTime()),
        sa.Column('deleted_by', sa.String(100)),
    )
    op.create_index('ix_fixed_asset_category', 'fixed_assets', ['category'])
    op.create_index('ix_fixed_asset_status', 'fixed_assets', ['status'])

    # ----- Depreciation Entries -----
    op.create_table(
        'depreciation_entries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', UUID(as_uuid=True), sa.ForeignKey('fixed_assets.id'), nullable=False, index=True),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('depreciation_amount', sa.Float(), nullable=False),
        sa.Column('accumulated_total', sa.Float(), nullable=False),
        sa.Column('method', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_depreciation_asset_period', 'depreciation_entries', ['asset_id', 'period_end'])

    # ----- Asset Disposals -----
    op.create_table(
        'asset_disposals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', UUID(as_uuid=True), sa.ForeignKey('fixed_assets.id'), nullable=False, index=True),
        sa.Column('disposal_date', sa.Date(), nullable=False),
        sa.Column('disposal_method', sa.String(50)),
        sa.Column('sale_price', sa.Float(), default=0),
        sa.Column('gain_loss', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ----- Bank Transactions -----
    op.create_table(
        'bank_transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('bank_account_id', sa.String(100), nullable=False, index=True),
        sa.Column('transaction_date', sa.Date(), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('reference', sa.String(200)),
        sa.Column('match_status', sa.String(50), server_default='unmatched'),
        sa.Column('matched_gl_entry_id', UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_bank_tx_account_date', 'bank_transactions', ['bank_account_id', 'transaction_date'])
    op.create_index('ix_bank_tx_match_status', 'bank_transactions', ['match_status'])

    # ----- Reconciliation Sessions -----
    op.create_table(
        'reconciliation_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('bank_account_id', sa.String(100), nullable=False, index=True),
        sa.Column('statement_date', sa.Date(), nullable=False),
        sa.Column('ending_balance', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), server_default='in_progress'),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('adjustments', sa.JSON(), server_default='[]'),
        # AuditedModel fields
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('deleted_at', sa.DateTime()),
        sa.Column('deleted_by', sa.String(100)),
    )
    op.create_index('ix_recon_account_date', 'reconciliation_sessions', ['bank_account_id', 'statement_date'])
    op.create_index('ix_recon_status', 'reconciliation_sessions', ['status'])

    # ----- Outstanding Checks -----
    op.create_table(
        'outstanding_checks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('bank_account_id', sa.String(100), nullable=False, index=True),
        sa.Column('check_number', sa.String(50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('issued_date', sa.Date(), nullable=False),
        sa.Column('payee', sa.String(200), nullable=False),
        sa.Column('cleared_date', sa.Date()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_outstanding_check_account', 'outstanding_checks', ['bank_account_id', 'check_number'])

    # ----- Tax Jurisdictions -----
    op.create_table(
        'tax_jurisdictions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('country', sa.String(100), nullable=False),
        sa.Column('state', sa.String(100)),
        sa.Column('tax_types', sa.JSON(), server_default='[]'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ----- Tax Rates -----
    op.create_table(
        'tax_rates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('jurisdiction_code', sa.String(50), nullable=False, index=True),
        sa.Column('tax_type', sa.String(50), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date()),
        sa.Column('category', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_tax_rate_jurisdiction_type', 'tax_rates', ['jurisdiction_code', 'tax_type'])
    op.create_index('ix_tax_rate_effective', 'tax_rates', ['effective_date'])

    # ----- Tax Exemptions -----
    op.create_table(
        'tax_exemptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', sa.String(100), nullable=False, index=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('jurisdiction_code', sa.String(50), nullable=False),
        sa.Column('tax_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date()),
        sa.Column('certificate_number', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_tax_exempt_entity', 'tax_exemptions', ['entity_id', 'entity_type'])
    op.create_index('ix_tax_exempt_jurisdiction', 'tax_exemptions', ['jurisdiction_code', 'tax_type'])

    # ----- Budget Lines -----
    op.create_table(
        'budget_lines',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('fiscal_year', sa.String(10), nullable=False, index=True),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('gl_accounts.id'), nullable=False),
        sa.Column('period', sa.Integer()),
        sa.Column('amount', sa.Float(), default=0),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_budget_year_account', 'budget_lines', ['fiscal_year', 'account_id'])

    # ----- Material Shortages -----
    op.create_table(
        'material_shortages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('shortage_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('material_id', sa.String(100), nullable=False, index=True),
        sa.Column('quantity_short', sa.Float(), nullable=False),
        sa.Column('required_date', sa.Date()),
        sa.Column('job_id', sa.String(100)),
        sa.Column('work_order_id', sa.String(100)),
        sa.Column('status', sa.String(50), server_default='open'),
        sa.Column('resolution_type', sa.String(50)),
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_shortage_status', 'material_shortages', ['status'])
    op.create_index('ix_shortage_material_date', 'material_shortages', ['material_id', 'required_date'])

    # ----- PM Tasks -----
    op.create_table(
        'pm_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('machine_id', sa.String(100), nullable=False, index=True),
        sa.Column('task_name', sa.String(200), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False, index=True),
        sa.Column('duration_hours', sa.Float(), server_default='1.0'),
        sa.Column('priority', sa.String(20), server_default='medium'),
        sa.Column('status', sa.String(50), server_default='scheduled'),
        sa.Column('technician_id', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_pm_task_machine_date', 'pm_tasks', ['machine_id', 'scheduled_date'])
    op.create_index('ix_pm_task_status', 'pm_tasks', ['status'])


def downgrade():
    op.drop_table('pm_tasks')
    op.drop_table('material_shortages')
    op.drop_table('budget_lines')
    op.drop_table('tax_exemptions')
    op.drop_table('tax_rates')
    op.drop_table('tax_jurisdictions')
    op.drop_table('outstanding_checks')
    op.drop_table('reconciliation_sessions')
    op.drop_table('bank_transactions')
    op.drop_table('asset_disposals')
    op.drop_table('depreciation_entries')
    op.drop_table('fixed_assets')
