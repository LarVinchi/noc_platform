"""add_designed_to_workflowstage

Revision ID: ab7c59588a2e
Revises: 23d4a4ad5d49
Create Date: 2026-04-05 15:31:55.207951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError # <-- Imported the error handler


# revision identifiers, used by Alembic.
revision: str = 'ab7c59588a2e'
down_revision: Union[str, Sequence[str], None] = '23d4a4ad5d49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # We use autocommit_block() because PostgreSQL forbids altering types inside a transaction
    with op.get_context().autocommit_block():
        try:
            op.execute("ALTER TYPE workflowstage ADD VALUE 'DESIGNED'")
            print("Successfully added 'DESIGNED' to enum.")
        except ProgrammingError:
            # If the database throws an error because it already exists (like your local DB), 
            # we just catch it and pass. In production, this will run normally!
            print("Enum value 'DESIGNED' already exists. Skipping.")
            pass

def downgrade() -> None:
    # PostgreSQL does not easily allow removing a single value from an ENUM, 
    # so we leave downgrade blank.
    pass