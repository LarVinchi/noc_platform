"""Tighten outage exclusions and retain complete incident audit references."""
from alembic import op
revision = 'b831d0276ea9'
down_revision = 'a721e84f096c'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE service_outages ADD CONSTRAINT ck_outage_exclusion_reason
        CHECK(NOT excluded OR (exclusion_reason IS NOT NULL AND length(trim(exclusion_reason))>0));
      CREATE INDEX ix_incident_response_deadlines ON incidents(status,ack_deadline_at,restore_deadline_at)
        WHERE response_policy_id IS NOT NULL;
      CREATE INDEX ix_open_outage_deadlines ON service_outages(restore_deadline_at)
        WHERE restored_at IS NULL AND NOT excluded;
      DROP TRIGGER audit_change ON incidents;
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON incidents FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('incident_id','incident_id,status,severity,reported_at,resolved_at,route_id,cable_id,core_id,nap_id,is_planned,assigned_engineer_id,response_policy_id,acknowledged_at,acknowledged_by,ack_deadline_at,restore_deadline_at,escalation_level');
    """)


def downgrade():
    op.execute("""
      ALTER TABLE service_outages DROP CONSTRAINT ck_outage_exclusion_reason;
      DROP INDEX ix_incident_response_deadlines;
      DROP INDEX ix_open_outage_deadlines;
    """)
