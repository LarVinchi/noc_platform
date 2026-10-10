"""Append-only reasons for operational record corrections."""
from alembic import op
revision='f275146b02e3'
down_revision='e164035a91d2'
branch_labels=depends_on=None


def upgrade():
    op.execute("""
      CREATE TABLE record_corrections (
        correction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        entity_type varchar(20) NOT NULL CHECK(entity_type IN ('incident','customer','service','ftth_order')),
        entity_id uuid NOT NULL,reason varchar(1000) NOT NULL CHECK(length(trim(reason))>=5),
        changed_fields jsonb NOT NULL,actor_id varchar(100) NOT NULL,actor_verified boolean NOT NULL,
        request_id varchar(100) NOT NULL,previous_ticket_id varchar(100),current_ticket_id varchar(100),
        created_at timestamptz NOT NULL DEFAULT now());
      CREATE TABLE incident_ticket_identifiers (
        ticket_id varchar(100) PRIMARY KEY,incident_id uuid NOT NULL REFERENCES incidents(incident_id),
        created_at timestamptz NOT NULL DEFAULT now());
      INSERT INTO incident_ticket_identifiers(ticket_id,incident_id)
        SELECT tt_number,incident_id FROM incidents WHERE tt_number IS NOT NULL;
      CREATE INDEX ix_incident_ticket_identifiers_incident ON incident_ticket_identifiers(incident_id);
      CREATE TRIGGER immutable_ticket_identifier BEFORE UPDATE OR DELETE ON incident_ticket_identifiers
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER immutable_ticket_identifier_truncate BEFORE TRUNCATE ON incident_ticket_identifiers
        FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
      CREATE INDEX ix_record_corrections_entity ON record_corrections(entity_type,entity_id,created_at);
      CREATE TRIGGER immutable_correction BEFORE UPDATE OR DELETE ON record_corrections
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER immutable_correction_truncate BEFORE TRUNCATE ON record_corrections
        FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER audit_change AFTER INSERT ON record_corrections FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('correction_id','correction_id,entity_type,entity_id,changed_fields,actor_id,actor_verified,request_id,created_at');
    """)


def downgrade():
    op.execute('DROP TABLE record_corrections,incident_ticket_identifiers')
