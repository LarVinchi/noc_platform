"""Enforce referential integrity for the order's inventory path."""
from alembic import op

revision = "c1b4a8926e05"
down_revision = "b2e5d6019a37"
branch_labels = depends_on = None


def upgrade():
    for column, table, primary in (("nap_id", "nap", "nap_id"), ("pfp_id", "pfp", "pfp_id"),
                                   ("pfs_id", "pfs", "pfs_id"), ("drop_cable_id", "drop_cables", "drop_cable_id")):
        op.create_foreign_key(f"fk_order_{column}", "service_orders", table, [column], [primary])


def downgrade():
    for column in ("nap_id", "pfp_id", "pfs_id", "drop_cable_id"):
        op.drop_constraint(f"fk_order_{column}", "service_orders", type_="foreignkey")
