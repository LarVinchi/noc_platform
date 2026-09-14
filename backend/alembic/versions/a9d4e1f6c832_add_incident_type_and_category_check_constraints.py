"""add_incident_type_and_category_check_constraints

Revision ID: a9d4e1f6c832
Revises: f3a1c9e2d7b4
Create Date: 2026-09-05 00:00:00.000000

This codifies a constraint that had previously only been added directly to
a live database by hand (outside version control). It also extends the
allowed incident_type list with 5 real categories found in the historical
data (Alarms & Triggers, Fiberwatch issue, Network Configuration Issue,
Splitter & Passive Components, Transmission) that were missing from the
original enumeration and would otherwise still fail import.

Uses DROP CONSTRAINT IF EXISTS first so this is safe to run whether or not
a constraint with this name already exists locally.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a9d4e1f6c832'
down_revision: Union[str, Sequence[str], None] = 'f3a1c9e2d7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_INCIDENT_TYPES = [
    "Environmental Issue", "Power Issue", "Fiber Incident", "Interface or Link Issue",
    "Virtualization Incident", "Service Unavailability", "Infrastructure Damage",
    "Security & Safety Alert", "Monitoring Alert", "Testing Activity",
    "Migration & Upgrade", "Maintenance", "Other",
    "Alarms & Triggers", "Fiberwatch issue", "Network Configuration Issue",
    "Splitter & Passive Components", "Transmission",
]

VALID_TICKET_CATEGORIES = ["FIBER", "POWER", "TECHNICAL", "MAINTENANCE", "OTHER"]


def upgrade() -> None:
    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_incident_type_check")
    incident_type_list = ", ".join(f"'{t}'" for t in VALID_INCIDENT_TYPES)
    op.execute(
        f"ALTER TABLE incidents ADD CONSTRAINT incidents_incident_type_check "
        f"CHECK (incident_type IN ({incident_type_list}))"
    )

    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_ticket_category_check")
    category_list = ", ".join(f"'{c}'" for c in VALID_TICKET_CATEGORIES)
    op.execute(
        f"ALTER TABLE incidents ADD CONSTRAINT incidents_ticket_category_check "
        f"CHECK (ticket_category IS NULL OR ticket_category IN ({category_list}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_ticket_category_check")
    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_incident_type_check")
