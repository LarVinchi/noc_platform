"""Persist map imports and explicit inventory route links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a6d71f3b0c29"
down_revision = "f4a90b2c671e"
branch_labels = depends_on = None


def upgrade():
    op.create_table("network_map_imports",
        sa.Column("import_id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        *[sa.Column(name, sa.String(), nullable=False) for name in ("name", "filename", "sha256")],
        sa.Column("geojson", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("sha256"))
    op.create_table("map_route_links",
        sa.Column("import_id", sa.UUID(), sa.ForeignKey("network_map_imports.import_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("feature_index", sa.Integer(), primary_key=True),
        sa.Column("route_id", sa.UUID(), sa.ForeignKey("fiber_routes.route_id"), nullable=False))


def downgrade():
    op.drop_table("map_route_links")
    op.drop_table("network_map_imports")
