"""Host health snapshots and bounded metric history."""
from alembic import op
revision = '25d9f3a8b012'
down_revision = '14c8e2f7a901'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE platform_hosts (
        host_id varchar(64) PRIMARY KEY, observed_at timestamptz NOT NULL,
        received_at timestamptz NOT NULL, payload jsonb NOT NULL);
        CREATE TABLE platform_samples (
        sample_id uuid PRIMARY KEY, host_id varchar(64) NOT NULL REFERENCES platform_hosts(host_id),
        observed_at timestamptz NOT NULL, digest varchar(64) NOT NULL,
        cpu_percent double precision CHECK (cpu_percent BETWEEN 0 AND 100),
        memory_percent double precision NOT NULL CHECK (memory_percent BETWEEN 0 AND 100),
        storage_percent double precision CHECK (storage_percent BETWEEN 0 AND 100));
        CREATE INDEX ix_platform_samples_host_time ON platform_samples(host_id, observed_at);''')


def downgrade():
    op.execute('DROP TABLE platform_samples; DROP TABLE platform_hosts;')
