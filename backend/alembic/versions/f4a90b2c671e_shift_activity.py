"""Persist shared shift activities and incident/order links."""
from alembic import op
import sqlalchemy as sa

revision = "f4a90b2c671e"
down_revision = "e2f8a61c4d90"
branch_labels = depends_on = None


def upgrade():
    op.create_table("activity_entries",
        sa.Column("activity_id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        *[sa.Column(name, sa.String(), nullable=False) for name in ("person", "shift", "category", "title", "description", "status")],
        *[sa.Column(name, sa.String(), nullable=True) for name in ("severity", "affected_system", "vendor_reference")],
        sa.Column("handover", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("incident_id", sa.UUID(), sa.ForeignKey("incidents.incident_id")),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("service_orders.order_id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for name in ("person", "category", "created_at"):
        op.create_index(f"ix_activity_entries_{name}", "activity_entries", [name])


def downgrade():
    op.drop_table("activity_entries")
