"""Enforce unique NAP port and drop reservations for provisioned orders."""
from alembic import op
import sqlalchemy as sa

revision = "e2f8a61c4d90"
down_revision = "d8e1f407b2a6"
branch_labels = depends_on = None


def upgrade():
    op.add_column("service_orders", sa.Column("activated_service_id", sa.UUID(), sa.ForeignKey("services.service_id"), nullable=True))
    for name, fields in (("uq_order_nap_port", ["nap_id", "nap_port"]),
                         ("uq_order_drop", ["drop_cable_id"])):
        op.create_index(name, "service_orders", fields, unique=True,
                        postgresql_where=sa.text("status <> 'REQUESTED'"))


def downgrade():
    op.drop_index("uq_order_drop", table_name="service_orders")
    op.drop_index("uq_order_nap_port", table_name="service_orders")
    op.drop_column("service_orders", "activated_service_id")
