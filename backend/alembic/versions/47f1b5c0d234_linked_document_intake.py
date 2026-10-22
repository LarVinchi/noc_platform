"""OneDrive origin metadata and derived extractions, without original-file blobs."""
from alembic import op
revision='47f1b5c0d234'
down_revision='36e0a4b9c123'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE TABLE linked_collections (
        collection_id uuid PRIMARY KEY, title varchar(200) NOT NULL, owner_id varchar(100) NOT NULL,
        enabled boolean NOT NULL, freshness_seconds integer NOT NULL, derived_limit_bytes integer NOT NULL,
        last_observed_at timestamptz);
        CREATE TABLE linked_revisions (
        version_id uuid PRIMARY KEY REFERENCES document_versions(version_id),
        collection_id uuid NOT NULL REFERENCES linked_collections(collection_id), source_path varchar(1000) NOT NULL,
        original_url varchar(2000), extraction_sha256 varchar(64) NOT NULL, chunks jsonb NOT NULL,
        derived_bytes integer NOT NULL, observed_at timestamptz NOT NULL, available boolean NOT NULL);
        CREATE INDEX ix_linked_revisions_collection_id ON linked_revisions(collection_id);
        CREATE TABLE linked_scans (
        run_id uuid PRIMARY KEY, collection_id uuid NOT NULL REFERENCES linked_collections(collection_id),
        payload_sha256 varchar(64) NOT NULL, observed_at timestamptz NOT NULL, summary jsonb NOT NULL);''')


def downgrade():
    op.execute('DROP TABLE linked_scans; DROP TABLE linked_revisions; DROP TABLE linked_collections;')
