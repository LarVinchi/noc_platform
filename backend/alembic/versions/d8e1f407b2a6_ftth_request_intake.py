"""FTTH external references, provenance, uniqueness and atomic numbering."""
from alembic import op
import sqlalchemy as sa

revision = "d8e1f407b2a6"
down_revision = "c7e2b418f905"
branch_labels = depends_on = None


def upgrade():
    # Abort safely if existing data cannot support the new identity guarantee.
    # Do not delete or merge customer orders automatically.
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("""
        SELECT 1 FROM service_orders WHERE NULLIF(TRIM(fn_number), '') IS NOT NULL
        GROUP BY isp, UPPER(TRIM(fn_number)) HAVING COUNT(*) > 1 LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError("Duplicate FN numbers exist for an ISP. Reconcile these orders before migrating; no records were removed.")
    op.execute("UPDATE service_orders SET fn_number = NULLIF(UPPER(TRIM(fn_number)), '')")
    for name in ("work_order_id", "source_status", "intake_source", "raw_request_text"):
        op.add_column("service_orders", sa.Column(name, sa.String(), nullable=True))
    op.create_index("uq_service_orders_isp_fn", "service_orders", ["isp", "fn_number"],
                    unique=True, postgresql_where=sa.text("fn_number IS NOT NULL AND fn_number <> ''"))
    op.create_index("uq_service_orders_isp_work_order", "service_orders", ["isp", "work_order_id"],
                    unique=True, postgresql_where=sa.text("work_order_id IS NOT NULL AND work_order_id <> ''"))
    op.create_table("service_order_sequences",
                    sa.Column("prefix", sa.String(), primary_key=True),
                    sa.Column("last_sequence", sa.Integer(), nullable=False))
    op.execute("""
        INSERT INTO service_order_sequences (prefix, last_sequence)
        SELECT regexp_replace(service_order_number, '-[0-9]+$', ''),
               MAX(substring(service_order_number from '[0-9]+$')::integer)
        FROM service_orders WHERE service_order_number ~ '^.+-[0-9]+$'
        GROUP BY regexp_replace(service_order_number, '-[0-9]+$', '')
    """)


def downgrade():
    op.drop_table("service_order_sequences")
    op.drop_index("uq_service_orders_isp_work_order", table_name="service_orders")
    op.drop_index("uq_service_orders_isp_fn", table_name="service_orders")
    for name in ("raw_request_text", "intake_source", "source_status", "work_order_id"):
        op.drop_column("service_orders", name)
