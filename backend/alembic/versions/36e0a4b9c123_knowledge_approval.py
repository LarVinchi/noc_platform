"""Version-pinned knowledge approval and minimal access audit."""
from alembic import op
revision = '36e0a4b9c123'
down_revision = '25d9f3a8b012'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE knowledge_approvals (
        version_id uuid PRIMARY KEY REFERENCES document_versions(version_id),
        approved boolean NOT NULL, reviewed_by varchar(100) NOT NULL,
        reviewed_at timestamptz NOT NULL, note text NOT NULL);
        CREATE TABLE knowledge_events (
        event_id uuid PRIMARY KEY, actor_id varchar(100) NOT NULL,
        kind varchar(40) NOT NULL, source_versions jsonb NOT NULL,
        occurred_at timestamptz NOT NULL);
        CREATE INDEX ix_knowledge_events_time ON knowledge_events(occurred_at);''')


def downgrade():
    op.execute('DROP TABLE knowledge_events; DROP TABLE knowledge_approvals;')
