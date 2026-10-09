"""Allow Layer 2 service core allocations without weakening other usage checks."""
from alembic import op

revision = "b2e5d6019a37"
down_revision = "a6d71f3b0c29"
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE fiber_cores DROP CONSTRAINT IF EXISTS fiber_cores_usage_type_check")
    op.execute("ALTER TABLE fiber_cores ADD CONSTRAINT fiber_cores_usage_type_check CHECK (usage_type IN ('DIA','DARKFIBER','ISP','FTTH','FREE','LAYER2'))")


def downgrade():
    # Existing Layer 2 allocations must be reconciled before downgrade.
    op.execute("ALTER TABLE fiber_cores DROP CONSTRAINT IF EXISTS fiber_cores_usage_type_check")
    op.execute("ALTER TABLE fiber_cores ADD CONSTRAINT fiber_cores_usage_type_check CHECK (usage_type IN ('DIA','DARKFIBER','ISP','FTTH','FREE'))")
