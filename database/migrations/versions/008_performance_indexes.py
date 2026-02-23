"""Add composite indexes for common query patterns

Revision ID: 008_perf_indexes
Revises: 006_genealogy
Create Date: 2026-01-28
"""
import logging
from alembic import op
import sqlalchemy as sa

logger = logging.getLogger(__name__)

revision = '008_perf_indexes'
down_revision = '006_genealogy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    indexes = [
        ('ix_wo_status_due', 'work_orders', ['status', 'due_date'], False),
        ('ix_job_machine_status', 'jobs', ['machine_id', 'status'], False),
        ('ix_je_period_status', 'journal_entries', ['period_id', 'status'], True),
        ('ix_invoice_customer_status', 'ar_invoices', ['customer_id', 'status'], True),
    ]

    for idx_name, table, columns, check_table in indexes:
        try:
            if check_table and not conn.dialect.has_table(conn, table):
                continue
            conn.execute(sa.text(f"SAVEPOINT idx_sp"))
            op.create_index(idx_name, table, columns)
            conn.execute(sa.text(f"RELEASE SAVEPOINT idx_sp"))
        except Exception as e:
            conn.execute(sa.text(f"ROLLBACK TO SAVEPOINT idx_sp"))
            logger.warning(f"Index {idx_name} skipped: {e}")


def downgrade() -> None:
    conn = op.get_bind()
    for idx_name, table in [
        ('ix_wo_status_due', 'work_orders'),
        ('ix_job_machine_status', 'jobs'),
        ('ix_je_period_status', 'journal_entries'),
        ('ix_invoice_customer_status', 'ar_invoices'),
    ]:
        try:
            conn.execute(sa.text("SAVEPOINT idx_sp"))
            op.drop_index(idx_name, table)
            conn.execute(sa.text("RELEASE SAVEPOINT idx_sp"))
        except Exception as e:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT idx_sp"))
            logger.warning(f"Index {idx_name} drop skipped: {e}")
