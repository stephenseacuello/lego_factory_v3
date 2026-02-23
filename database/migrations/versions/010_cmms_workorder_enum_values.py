"""Add missing CMMS/QMS enum values.

The MES module created workorderstatus with: DRAFT, PLANNED, RELEASED,
IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED.
The CMMS module needs: APPROVED, WAITING_PARTS, WAITING_SCHEDULE, SCHEDULED, CLOSED.

The ML module created trainingstatus with: QUEUED, PREPARING, TRAINING,
VALIDATING, COMPLETED, FAILED, CANCELLED.
The QMS module needs: SCHEDULED, IN_PROGRESS, EXPIRED, WAIVED.
"""

from alembic import op


revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    for value in ['APPROVED', 'WAITING_PARTS', 'WAITING_SCHEDULE', 'SCHEDULED', 'CLOSED']:
        op.execute(f"ALTER TYPE workorderstatus ADD VALUE IF NOT EXISTS '{value}'")

    for value in ['SCHEDULED', 'IN_PROGRESS', 'EXPIRED', 'WAIVED']:
        op.execute(f"ALTER TYPE trainingstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    # PostgreSQL does not support removing enum values.
    pass
