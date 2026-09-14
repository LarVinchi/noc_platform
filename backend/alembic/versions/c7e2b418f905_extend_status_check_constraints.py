"""extend_status_check_constraints

Revision ID: c7e2b418f905
Revises: a9d4e1f6c832
Create Date: 2026-09-05 00:00:00.000000

The original schema (db/init-scripts/03_incidents_tickets.sql) restricted
status to ('open','investigating','resolved','closed'). The Incident
Management frontend needs a richer lifecycle that matches how staff
actually track incidents day to day, so this extends the same lowercase
vocabulary with 'pending' and 'aborted' rather than replacing it — existing
rows using the original four values remain valid unchanged.

Applied to both `incidents` and `tickets`, since both tables carry the same
original constraint and `tickets` would hit the identical wall once it's
wired into the API.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c7e2b418f905'
down_revision: Union[str, Sequence[str], None] = 'a9d4e1f6c832'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_STATUSES = ['open', 'investigating', 'pending', 'resolved', 'closed', 'aborted']


def upgrade() -> None:
    status_list = ", ".join(f"'{s}'" for s in VALID_STATUSES)

    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_status_check")
    op.execute(f"ALTER TABLE incidents ADD CONSTRAINT incidents_status_check CHECK (status IN ({status_list}))")

    op.execute("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_status_check")
    op.execute(f"ALTER TABLE tickets ADD CONSTRAINT tickets_status_check CHECK (status IN ({status_list}))")


def downgrade() -> None:
    original_list = "'open', 'investigating', 'resolved', 'closed'"
    op.execute("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_status_check")
    op.execute(f"ALTER TABLE tickets ADD CONSTRAINT tickets_status_check CHECK (status IN ({original_list}))")

    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_status_check")
    op.execute(f"ALTER TABLE incidents ADD CONSTRAINT incidents_status_check CHECK (status IN ({original_list}))")
