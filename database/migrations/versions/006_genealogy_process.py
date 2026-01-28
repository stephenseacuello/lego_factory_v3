"""Add genealogy and process tracking tables

Revision ID: 006_genealogy
Revises: 005_resource_tracking
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '006_genealogy'
down_revision = '005_resource_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Product Genealogy table
    op.create_table(
        'product_genealogy',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('serial_number', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('batch_number', sa.String(50), index=True),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('work_orders.id'), index=True),
        sa.Column('job_id', sa.String(50), index=True),
        sa.Column('product_id', sa.String(50), nullable=False, index=True),
        sa.Column('product_name', sa.String(200)),
        sa.Column('product_revision', sa.String(20)),
        sa.Column('status', sa.String(20), nullable=False, default='in_progress'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('parent_lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id')),
        sa.Column('overall_quality', sa.String(20), default='pending'),
        sa.Column('quality_score', sa.Float),
        sa.Column('current_location', sa.String(100)),
        sa.Column('shipped_to', sa.String(200)),
        sa.Column('shipped_at', sa.DateTime(timezone=True)),
        sa.Column('customer_order', sa.String(50)),
        sa.Column('notes', sa.Text),
        sa.Column('extra_data', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
    )

    op.create_index('ix_product_genealogy_product_status', 'product_genealogy', ['product_id', 'status'])

    # Process Steps table
    op.create_table(
        'process_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('genealogy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product_genealogy.id'), nullable=False, index=True),
        sa.Column('operation_id', sa.String(50), index=True),
        sa.Column('operation_name', sa.String(200)),
        sa.Column('sequence', sa.Integer, nullable=False),
        sa.Column('machine_id', sa.String(50), index=True),
        sa.Column('worker_id', sa.String(50), index=True),
        sa.Column('workstation', sa.String(100)),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('planned_duration_mins', sa.Float),
        sa.Column('actual_duration_mins', sa.Float),
        sa.Column('parameters', postgresql.JSONB, server_default='{}'),
        sa.Column('setpoints', postgresql.JSONB, server_default='{}'),
        sa.Column('actuals', postgresql.JSONB, server_default='{}'),
        sa.Column('quality_result', sa.String(20), default='pending'),
        sa.Column('inspection_data', postgresql.JSONB, server_default='{}'),
        sa.Column('defects_found', postgresql.JSONB, server_default='[]'),
        sa.Column('sensor_data_ref', sa.String(200)),
        sa.Column('notes', sa.Text),
        sa.Column('operator_comments', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_process_steps_genealogy_seq', 'process_steps', ['genealogy_id', 'sequence'])
    op.create_index('ix_process_steps_machine', 'process_steps', ['machine_id', 'started_at'])

    # Lot Traces table
    op.create_table(
        'lot_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id'), nullable=False, index=True),
        sa.Column('consumed_by_job_id', sa.String(50), nullable=False, index=True),
        sa.Column('work_order_id', sa.String(50), index=True),
        sa.Column('output_genealogy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product_genealogy.id'), index=True),
        sa.Column('quantity_consumed', sa.Float, nullable=False),
        sa.Column('unit_of_measure', sa.String(20)),
        sa.Column('transformation_type', sa.String(50)),
        sa.Column('consumed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table('lot_traces')
    op.drop_table('process_steps')
    op.drop_table('product_genealogy')
