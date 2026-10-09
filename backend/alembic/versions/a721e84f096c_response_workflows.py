"""Engineer ownership, versioned targets, confirmed outages and draft escalation."""
from alembic import op
revision = "a721e84f096c"
down_revision = "f519a30ce842"
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE engineers (
        engineer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(200) NOT NULL,
        email varchar(320) UNIQUE NOT NULL, team varchar(100) NOT NULL, enabled boolean NOT NULL DEFAULT true);
      CREATE TABLE response_policies (
        policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(200) NOT NULL,
        severity varchar(20) CHECK(severity IN ('Critical','High','Medium','Low')),
        service_id uuid REFERENCES services(service_id), version integer NOT NULL CHECK(version>0),
        acknowledgment_minutes integer NOT NULL CHECK(acknowledgment_minutes>0),
        restoration_minutes integer NOT NULL CHECK(restoration_minutes>=acknowledgment_minutes),
        followup_minutes integer NOT NULL CHECK(followup_minutes>0),
        default_engineer_id uuid REFERENCES engineers(engineer_id), escalation_recipients jsonb NOT NULL DEFAULT '[]',
        preview_only boolean NOT NULL DEFAULT true, effective_from timestamptz NOT NULL,
        CONSTRAINT ck_response_policy_scope CHECK(num_nonnulls(severity, service_id)=1));
      CREATE UNIQUE INDEX uq_policy_severity_version ON response_policies(severity,version) WHERE severity IS NOT NULL;
      CREATE UNIQUE INDEX uq_policy_service_version ON response_policies(service_id,version) WHERE service_id IS NOT NULL;
      ALTER TABLE incidents ADD COLUMN assigned_engineer_id uuid REFERENCES engineers(engineer_id),
        ADD COLUMN response_policy_id uuid REFERENCES response_policies(policy_id),
        ADD COLUMN acknowledged_at timestamptz, ADD COLUMN acknowledged_by varchar(100),
        ADD COLUMN ack_deadline_at timestamptz, ADD COLUMN restore_deadline_at timestamptz,
        ADD COLUMN escalation_level integer NOT NULL DEFAULT 0 CHECK(escalation_level BETWEEN 0 AND 3);
      CREATE TABLE service_outages (
        outage_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), incident_id uuid NOT NULL REFERENCES incidents(incident_id),
        service_id uuid NOT NULL REFERENCES services(service_id), policy_id uuid REFERENCES response_policies(policy_id),
        started_at timestamptz NOT NULL, restored_at timestamptz, ack_deadline_at timestamptz, restore_deadline_at timestamptz,
        confirmed_by varchar(100) NOT NULL, restored_by varchar(100), confirmation_note text NOT NULL,
        restoration_note text, excluded boolean NOT NULL DEFAULT false, exclusion_reason varchar(500),
        CHECK(restored_at IS NULL OR restored_at>=started_at), CHECK(NOT excluded OR length(trim(exclusion_reason))>0));
      CREATE UNIQUE INDEX uq_open_outage ON service_outages(incident_id,service_id) WHERE restored_at IS NULL;
      CREATE INDEX ix_service_outages_incident_id ON service_outages(incident_id);
      CREATE INDEX ix_service_outages_service_id ON service_outages(service_id);
      CREATE TABLE response_events (
        event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_key varchar(250) UNIQUE NOT NULL,
        incident_id uuid NOT NULL REFERENCES incidents(incident_id), outage_id uuid REFERENCES service_outages(outage_id),
        event_type varchar(50) NOT NULL, message text NOT NULL, actor_id varchar(100) NOT NULL, occurred_at timestamptz NOT NULL);
      CREATE INDEX ix_response_events_incident_id ON response_events(incident_id);
      CREATE TABLE notification_drafts (
        draft_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_key varchar(250) UNIQUE NOT NULL,
        incident_id uuid NOT NULL REFERENCES incidents(incident_id), service_id uuid REFERENCES services(service_id),
        audience varchar(30) NOT NULL, recipients jsonb NOT NULL DEFAULT '[]', subject varchar(250) NOT NULL,
        body text NOT NULL, status varchar(20) NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','reviewed','discarded')),
        created_at timestamptz NOT NULL DEFAULT now(), reviewed_at timestamptz, reviewed_by varchar(100));
      CREATE INDEX ix_notification_drafts_incident_id ON notification_drafts(incident_id);
      CREATE TABLE worker_heartbeats(worker_name varchar(100) PRIMARY KEY, updated_at timestamptz NOT NULL);
      CREATE TRIGGER immutable_policy BEFORE UPDATE OR DELETE ON response_policies
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER immutable_response_event BEFORE UPDATE OR DELETE ON response_events
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      DROP TRIGGER audit_change ON incidents;
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON incidents FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('incident_id','incident_id,status,severity,reported_at,resolved_at,route_id,cable_id,assigned_engineer_id,response_policy_id,acknowledged_at,acknowledged_by,ack_deadline_at,restore_deadline_at,escalation_level');
    """)
    for table, identifier, fields in (
        ("engineers", "engineer_id", "engineer_id,team,enabled"),
        ("response_policies", "policy_id", "policy_id,severity,service_id,version,acknowledgment_minutes,restoration_minutes,followup_minutes,default_engineer_id,preview_only,effective_from"),
        ("service_outages", "outage_id", "outage_id,incident_id,service_id,policy_id,started_at,restored_at,ack_deadline_at,restore_deadline_at,confirmed_by,restored_by,excluded,exclusion_reason"),
        ("response_events", "event_id", "event_id,incident_id,outage_id,event_type,actor_id,occurred_at"),
        ("notification_drafts", "draft_id", "draft_id,incident_id,service_id,audience,status,created_at,reviewed_at,reviewed_by"),
    ):
        op.execute(f"CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW "
                   f"EXECUTE FUNCTION noc_capture_change('{identifier}','{fields}')")


def downgrade():
    op.execute("""
      DROP TABLE worker_heartbeats,notification_drafts,response_events,service_outages;
      DROP TRIGGER audit_change ON incidents;
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON incidents FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('incident_id','incident_id,status,severity,reported_at,resolved_at,route_id,cable_id,core_id,nap_id,is_planned');
      ALTER TABLE incidents DROP COLUMN assigned_engineer_id, DROP COLUMN response_policy_id,
        DROP COLUMN acknowledged_at,DROP COLUMN acknowledged_by,DROP COLUMN ack_deadline_at,
        DROP COLUMN restore_deadline_at,DROP COLUMN escalation_level;
      DROP TABLE response_policies,engineers;
    """)
