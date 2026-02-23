"""Add additional composite indexes for performance

Revision ID: 009_additional_indexes
Revises: 008_perf_indexes
Create Date: 2026-01-31
"""
import logging
from alembic import op
import sqlalchemy as sa

logger = logging.getLogger(__name__)

revision = '009_additional_indexes'
down_revision = '008_perf_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Additional indexes for common query patterns
    indexes = [
        # MachineAvailability - scheduler queries
        ('ix_machine_avail_composite', 'machine_availability',
         ['machine_id', 'availability_type', 'start_datetime', 'end_datetime'], True),

        # DispatchQueue - work order filtering
        ('ix_dispatch_wo_status', 'dispatch_queue', ['work_order_id', 'status'], True),

        # BOM - parent/child lookups for BOM explosion
        ('ix_bom_parent_type', 'bom_lines', ['parent_item_id', 'is_active'], True),
        ('ix_bom_child', 'bom_lines', ['child_item_id'], True),

        # OEE records - dashboard queries
        ('ix_oee_machine_date', 'oee_records', ['machine_id', 'record_date'], True),

        # Downtime events - pareto analysis
        ('ix_downtime_machine_time', 'downtime_events', ['machine_id', 'start_time'], True),

        # Machine events - utilization queries
        ('ix_machine_event_time', 'machine_events', ['machine_id', 'created_at'], True),

        # Maintenance work orders - backlog queries
        ('ix_maint_wo_status_target', 'maintenance_work_orders',
         ['status', 'target_completion'], True),

        # Jobs - work order job queries
        ('ix_jobs_wo_status', 'jobs', ['work_order_id', 'status'], True),
    ]

    for idx_name, table, columns, check_table in indexes:
        try:
            if check_table and not conn.dialect.has_table(conn, table):
                logger.info(f"Table {table} does not exist, skipping index {idx_name}")
                continue
            conn.execute(sa.text("SAVEPOINT idx_sp"))
            op.create_index(idx_name, table, columns)
            conn.execute(sa.text("RELEASE SAVEPOINT idx_sp"))
            logger.info(f"Created index {idx_name} on {table}")
        except Exception as e:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT idx_sp"))
            logger.warning(f"Index {idx_name} skipped: {e}")


def downgrade() -> None:
    conn = op.get_bind()

    indexes_to_drop = [
        ('ix_machine_avail_composite', 'machine_availability'),
        ('ix_dispatch_wo_status', 'dispatch_queue'),
        ('ix_bom_parent_type', 'bom_lines'),
        ('ix_bom_child', 'bom_lines'),
        ('ix_oee_machine_date', 'oee_records'),
        ('ix_downtime_machine_time', 'downtime_events'),
        ('ix_machine_event_time', 'machine_events'),
        ('ix_maint_wo_status_target', 'maintenance_work_orders'),
        ('ix_jobs_wo_status', 'jobs'),
    ]

    for idx_name, table in indexes_to_drop:
        try:
            conn.execute(sa.text("SAVEPOINT idx_sp"))
            op.drop_index(idx_name, table_name=table)
            conn.execute(sa.text("RELEASE SAVEPOINT idx_sp"))
        except Exception as e:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT idx_sp"))
            logger.warning(f"Index {idx_name} drop skipped: {e}")
