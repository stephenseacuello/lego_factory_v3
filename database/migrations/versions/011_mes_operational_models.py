"""
Migration 011 - MES Operational Models
=======================================
Creates tables for rework orders, scrap events, shift handovers,
kanban cards, WIP snapshots, and cycle time records.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # --- Rework Orders ---
    op.create_table(
        'rework_orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('rework_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('original_wo_id', sa.String(50), nullable=False, index=True),
        sa.Column('ncr_id', sa.String(50)),
        sa.Column('reason', sa.Text()),
        sa.Column('rework_operations', sa.JSON(), server_default='[]'),
        sa.Column('quantity', sa.Integer(), server_default='0'),
        sa.Column('cost', sa.Float(), server_default='0'),
        sa.Column('status', sa.Enum('open', 'in_progress', 'completed', 'cancelled',
                                     name='reworkstatus'), nullable=False, server_default='open'),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),
    )
    op.create_index('ix_rework_status', 'rework_orders', ['status'])

    # --- Scrap Events ---
    op.create_table(
        'scrap_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id'), index=True),
        sa.Column('machine_id', sa.String(50), index=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('unit_cost', sa.Float(), server_default='0'),
        sa.Column('total_cost', sa.Float(), server_default='0'),
        sa.Column('dispositioned_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),
    )
    op.create_index('ix_scrap_job_reason', 'scrap_events', ['job_id', 'reason'])

    # --- Shift Handovers ---
    op.create_table(
        'shift_handovers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('handover_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('shift_date', sa.Date(), nullable=False, index=True),
        sa.Column('shift_type', sa.String(20), nullable=False),
        sa.Column('outgoing_worker', sa.String(100)),
        sa.Column('incoming_worker', sa.String(100)),
        sa.Column('status', sa.Enum('draft', 'completed', name='handoverstatus'),
                  nullable=False, server_default='draft'),
        sa.Column('items', sa.JSON(), server_default='[]'),
        sa.Column('notes', sa.Text()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),
    )
    op.create_index('ix_handover_date_shift', 'shift_handovers', ['shift_date', 'shift_type'])

    # --- Kanban Cards ---
    op.create_table(
        'kanban_cards',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('card_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('product_id', sa.String(100), nullable=False, index=True),
        sa.Column('work_center_id', sa.String(50), nullable=False, index=True),
        sa.Column('quantity', sa.Integer(), server_default='0'),
        sa.Column('target_qty', sa.Integer(), nullable=False),
        sa.Column('reorder_point', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), server_default='empty'),
        sa.Column('signal', sa.String(20), server_default='replenish'),
        sa.Column('last_replenish_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),
    )

    # --- WIP Snapshots ---
    op.create_table(
        'wip_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('total_wip', sa.Integer(), nullable=False),
        sa.Column('by_machine', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_wip_snapshot_time', 'wip_snapshots', ['created_at'])

    # --- Cycle Time Records ---
    op.create_table(
        'cycle_time_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('work_center_id', sa.String(50), nullable=False, index=True),
        sa.Column('cycle_seconds', sa.Float(), nullable=False),
        sa.Column('takt_target_seconds', sa.Float(), nullable=False),
        sa.Column('deviation_seconds', sa.Float()),
        sa.Column('on_takt', sa.Boolean(), server_default='true'),
        sa.Column('job_id', sa.String(100)),
        sa.Column('operator_id', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_cycle_time_wc_time', 'cycle_time_records', ['work_center_id', 'created_at'])


def downgrade():
    op.drop_table('cycle_time_records')
    op.drop_table('wip_snapshots')
    op.drop_table('kanban_cards')
    op.drop_table('shift_handovers')
    op.drop_table('scrap_events')
    op.drop_table('rework_orders')

    op.execute("DROP TYPE IF EXISTS reworkstatus")
    op.execute("DROP TYPE IF EXISTS handoverstatus")
