"""Append-only FTTH lifecycle events and explicit incident associations."""
from alembic import op
revision = 'd053f24980c1'
down_revision = 'c942e1387fb0'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE ftth_stage_events (
        event_id uuid PRIMARY KEY,order_id uuid NOT NULL REFERENCES service_orders(order_id),
        from_stage varchar(30),to_stage varchar(30) NOT NULL,actor_id varchar(100) NOT NULL,
        occurred_at timestamptz NOT NULL,note text NOT NULL,
        CHECK(from_stage IS NULL OR from_stage IN ('REQUESTED','SCHEDULED','IN_PROGRESS','PENDING_ACCEPTANCE','MONITORED')),
        CHECK(to_stage IN ('REQUESTED','SCHEDULED','IN_PROGRESS','PENDING_ACCEPTANCE','MONITORED')));
      CREATE INDEX ix_ftth_stage_events_order_id ON ftth_stage_events(order_id);
      CREATE INDEX ix_ftth_stage_events_time ON ftth_stage_events(occurred_at);
      CREATE TABLE ftth_incident_links (
        link_id uuid PRIMARY KEY,order_id uuid NOT NULL REFERENCES service_orders(order_id),
        incident_id uuid NOT NULL REFERENCES incidents(incident_id),service_id uuid REFERENCES services(service_id),
        kind varchar(30) NOT NULL CHECK(kind IN ('installation_blocker','service_fault')),
        request_key uuid NOT NULL,request_hash varchar(64) NOT NULL,note text NOT NULL,
        linked_by varchar(100) NOT NULL,linked_at timestamptz NOT NULL DEFAULT now(),
        CHECK((kind='installation_blocker' AND service_id IS NULL) OR (kind='service_fault' AND service_id IS NOT NULL)),
        CONSTRAINT uq_ftth_request UNIQUE(order_id,request_key),
        CONSTRAINT uq_ftth_incident_link UNIQUE(order_id,incident_id,kind));
      CREATE INDEX ix_ftth_incident_links_order_id ON ftth_incident_links(order_id);
      CREATE INDEX ix_ftth_incident_links_incident_id ON ftth_incident_links(incident_id);
      CREATE TRIGGER immutable_ftth_stage BEFORE UPDATE OR DELETE ON ftth_stage_events
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER immutable_ftth_incident_link BEFORE UPDATE OR DELETE ON ftth_incident_links
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER audit_change AFTER INSERT ON ftth_stage_events FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('event_id','event_id,order_id,from_stage,to_stage,actor_id,occurred_at');
      CREATE TRIGGER audit_change AFTER INSERT ON ftth_incident_links FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('link_id','link_id,order_id,incident_id,service_id,kind,linked_by,linked_at');
    """)


def downgrade():
    op.execute('DROP TABLE ftth_incident_links,ftth_stage_events')
