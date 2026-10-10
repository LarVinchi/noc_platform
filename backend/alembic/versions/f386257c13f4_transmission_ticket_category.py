"""TN identifies Transmission; preserve existing ticket IDs and relationships."""
from alembic import op

revision = 'f386257c13f4'
down_revision = 'f275146b02e3'
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint('incidents_ticket_category_check', 'incidents', type_='check')
    op.execute("UPDATE incidents SET ticket_category='TRANSMISSION' WHERE ticket_category='TECHNICAL'")
    op.create_check_constraint('incidents_ticket_category_check', 'incidents',
        "ticket_category IS NULL OR ticket_category IN ('FIBER','POWER','TRANSMISSION','MAINTENANCE','OTHER')")


def downgrade():
    op.drop_constraint('incidents_ticket_category_check', 'incidents', type_='check')
    op.execute("UPDATE incidents SET ticket_category='TECHNICAL' WHERE ticket_category='TRANSMISSION'")
    op.create_check_constraint('incidents_ticket_category_check', 'incidents',
        "ticket_category IS NULL OR ticket_category IN ('FIBER','POWER','TECHNICAL','MAINTENANCE','OTHER')")
