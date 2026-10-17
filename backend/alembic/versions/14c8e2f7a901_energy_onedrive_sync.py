"""Read-only OneDrive workbook provenance and durable synchronization state."""
from alembic import op

revision = '14c8e2f7a901'
down_revision = '087a91d20b31'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE energy_source_revisions (
        revision_id uuid PRIMARY KEY, source_key varchar(64) NOT NULL,
        remote_etag varchar(1024) NOT NULL,
        import_id uuid NOT NULL REFERENCES energy_imports(import_id),
        content_hash varchar(64) NOT NULL, source_modified_at timestamptz NOT NULL,
        captured_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_energy_source_version UNIQUE(source_key,remote_etag));
      CREATE TABLE energy_sync_state (
        name varchar(40) PRIMARY KEY, source_key varchar(64) NOT NULL,
        active_revision_id uuid REFERENCES energy_source_revisions(revision_id),
        remote_etag varchar(1024), source_name varchar(200), source_modified_at timestamptz,
        last_checked_at timestamptz, last_success_at timestamptz, last_import_at timestamptz,
        next_attempt_at timestamptz, requested_at timestamptz,
        failure_count integer NOT NULL DEFAULT 0 CHECK(failure_count>=0),
        last_error_code varchar(80), last_error_message varchar(300));
      CREATE TRIGGER energy_source_immutable BEFORE UPDATE OR DELETE ON energy_source_revisions
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER energy_source_no_truncate BEFORE TRUNCATE ON energy_source_revisions
        FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER audit_change AFTER INSERT ON energy_source_revisions FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('revision_id','revision_id,source_key,import_id,content_hash,source_modified_at,captured_at');
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE ON energy_sync_state FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('name','name,source_key,active_revision_id,last_success_at,last_import_at,requested_at,failure_count,last_error_code');
    """)


def downgrade():
    op.execute('DROP TABLE energy_sync_state, energy_source_revisions')
