"""
Migration 012 - Active Clock Sessions
======================================
Persists active clock-in sessions so they survive service restarts.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'active_clock_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('worker_id', UUID(as_uuid=True), sa.ForeignKey('workers.id'), nullable=False, index=True),
        sa.Column('employee_id', sa.String(50), nullable=False, index=True),
        sa.Column('job_id', sa.String(100)),
        sa.Column('machine_id', sa.String(100)),
        sa.Column('skill_id', sa.String(100)),
        sa.Column('clock_in', sa.DateTime(), nullable=False),
        sa.Column('breaks', sa.JSON(), server_default='[]'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('active_clock_sessions')
