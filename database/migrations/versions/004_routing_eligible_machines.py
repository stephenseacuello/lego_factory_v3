"""Add eligible_machines column to lego_routing_operations

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
    op.add_column(
        'lego_routing_operations',
        sa.Column('eligible_machines', postgresql.JSONB(), server_default='[]', nullable=True)
    )


def downgrade() -> None:
    op.drop_column('lego_routing_operations', 'eligible_machines')
