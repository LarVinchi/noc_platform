"""Read-only workbook revisions and isolated, append-only collector trial."""
from alembic import op

revision = '087a91d20b31'
down_revision = 'f386257c13f4'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE energy_imports (
        import_id uuid PRIMARY KEY, content_hash varchar(64) NOT NULL UNIQUE,
        source_name varchar(200) NOT NULL, records jsonb NOT NULL,
        record_count integer NOT NULL CHECK(record_count>0),
        entered_by varchar(100) NOT NULL, entered_at timestamptz NOT NULL DEFAULT now());
      CREATE INDEX ix_energy_imports_entered ON energy_imports(entered_at, import_id);
      CREATE TABLE energy_trial_events (
        event_id uuid PRIMARY KEY, request_key uuid NOT NULL UNIQUE, request_hash varchar(64) NOT NULL,
        site varchar(20) NOT NULL CHECK(site IN ('PROJN01','LEKKP01','ADEMP01')),
        revision integer NOT NULL CHECK(revision>0), effective_at timestamptz NOT NULL,
        observation jsonb NOT NULL, entered_by varchar(100) NOT NULL,
        entered_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_energy_trial_revision UNIQUE(site,revision));
      CREATE INDEX ix_energy_trial_effective ON energy_trial_events(site,effective_at);
      CREATE TRIGGER energy_import_immutable BEFORE UPDATE OR DELETE ON energy_imports
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER energy_import_no_truncate BEFORE TRUNCATE ON energy_imports
        FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER energy_trial_immutable BEFORE UPDATE OR DELETE ON energy_trial_events
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER energy_trial_no_truncate BEFORE TRUNCATE ON energy_trial_events
        FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER audit_change AFTER INSERT ON energy_imports FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('import_id','import_id,content_hash,source_name,record_count,entered_by,entered_at');
      CREATE TRIGGER audit_change AFTER INSERT ON energy_trial_events FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('event_id','event_id,site,revision,effective_at,observation,entered_by,entered_at');
    """)


def downgrade():
    op.execute('DROP TABLE energy_trial_events,energy_imports')
