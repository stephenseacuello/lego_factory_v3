"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

LegoMCP PhD-Level Manufacturing Platform
Database Migration Script
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """
    Upgrade database schema.

    This migration applies forward changes to the database.
    All operations should be idempotent where possible.
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """
    Downgrade database schema.

    This migration reverts changes made in upgrade().
    Ensure all operations can be safely rolled back.
    """
    ${downgrades if downgrades else "pass"}
