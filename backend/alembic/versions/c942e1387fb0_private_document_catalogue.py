"""Private catalogue and immutable original file revisions."""
from alembic import op
revision = 'c942e1387fb0'
down_revision = 'b831d0276ea9'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE documents (
        document_id uuid PRIMARY KEY, title varchar(200) NOT NULL, document_type varchar(40) NOT NULL,
        owner_id varchar(100) NOT NULL, visibility varchar(20) NOT NULL DEFAULT 'private',
        order_id uuid REFERENCES service_orders(order_id), service_id uuid REFERENCES services(service_id),
        customer_id uuid REFERENCES customers(customer_id), incident_id uuid REFERENCES incidents(incident_id),
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT ck_document_visibility CHECK(visibility IN ('private','noc')));
      CREATE INDEX ix_documents_owner ON documents(owner_id);
      CREATE INDEX ix_documents_order ON documents(order_id);
      CREATE TABLE document_versions (
        version_id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES documents(document_id),
        revision integer NOT NULL CHECK(revision>0), storage_key varchar(200) UNIQUE NOT NULL,
        original_filename varchar(240) NOT NULL, media_type varchar(100) NOT NULL,
        byte_size integer NOT NULL CHECK(byte_size>0 AND byte_size<=20971520), sha256 varchar(64) NOT NULL,
        uploaded_by varchar(100) NOT NULL, change_note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_document_revision UNIQUE(document_id,revision));
      CREATE INDEX ix_document_versions_document_id ON document_versions(document_id);
      CREATE TRIGGER immutable_document_version BEFORE UPDATE OR DELETE ON document_versions
        FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON documents FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('document_id','document_id,document_type,owner_id,visibility,order_id,service_id,customer_id,incident_id');
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON document_versions FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('version_id','version_id,document_id,revision,byte_size,sha256,uploaded_by,created_at');
    """)


def downgrade():
    op.execute('DROP TABLE document_versions,documents')
