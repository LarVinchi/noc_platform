"""add_pending_acceptance_to_enum

Revision ID: 79983d3f81f0
Revises: 895fc00dfdb1
Create Date: 2026-04-06 10:51:02.861796

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79983d3f81f0'
down_revision: Union[str, Sequence[str], None] = '895fc00dfdb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Execute raw SQL to add the new value to the PostgreSQL ENUM
    op.execute("ALTER TYPE workflowstage ADD VALUE 'PENDING_ACCEPTANCE'")


def downgrade() -> None:
    # PostgreSQL does not easily support removing ENUM values.
    # Leaving this blank is standard practice for ENUM additions.
    pass
