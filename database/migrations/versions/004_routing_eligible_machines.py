"""Add lego_routings and lego_routing_operations tables with eligible_machines

Revision ID: 004_routing_eligible
Revises: 003_qms_cmms
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_routing_eligible'
down_revision = '003_qms_cmms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create lego_routings if it doesn't exist
    if not conn.dialect.has_table(conn, 'lego_routings'):
        op.create_table(
            'lego_routings',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('updated_by', sa.String(100), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_by', sa.String(100), nullable=True),
            sa.Column('routing_id', sa.String(50), unique=True, nullable=False, index=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('process_type', sa.String(50), nullable=False),
            sa.Column('estimated_time_min', sa.Integer()),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('revision', sa.String(20), server_default='1.0'),
        )

    # Create lego_routing_operations if it doesn't exist
    if not conn.dialect.has_table(conn, 'lego_routing_operations'):
        op.create_table(
            'lego_routing_operations',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('updated_by', sa.String(100), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_by', sa.String(100), nullable=True),
            sa.Column('routing_id', sa.String(50), sa.ForeignKey('lego_routings.routing_id'), nullable=False),
            sa.Column('sequence', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('operation_type', sa.String(50)),
            sa.Column('work_center_id', sa.String(50)),
            sa.Column('machine_id', sa.String(50)),
            sa.Column('eligible_machines', postgresql.JSONB(), server_default='[]', nullable=True),
            sa.Column('setup_time_min', sa.Integer(), server_default='0'),
            sa.Column('run_time_min', sa.Integer(), server_default='0'),
            sa.Column('instructions', sa.Text()),
            sa.Column('gcode_template', sa.String(500)),
            sa.UniqueConstraint('routing_id', 'sequence', name='uq_lego_routing_op'),
            sa.Index('ix_lego_routing_ops_routing', 'routing_id'),
        )
    else:
        # Table exists but may be missing eligible_machines column
        inspector = sa.inspect(conn)
        columns = [c['name'] for c in inspector.get_columns('lego_routing_operations')]
        if 'eligible_machines' not in columns:
            op.add_column(
                'lego_routing_operations',
                sa.Column('eligible_machines', postgresql.JSONB(), server_default='[]', nullable=True)
            )


def downgrade() -> None:
    op.drop_table('lego_routing_operations')
    op.drop_table('lego_routings')
