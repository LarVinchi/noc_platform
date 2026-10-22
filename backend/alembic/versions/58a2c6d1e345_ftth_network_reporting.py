"""Reconciled FTTH snapshots without modifying daily installation totals."""
from alembic import op
revision='58a2c6d1e345'
down_revision='47f1b5c0d234'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE TABLE ftth_network_snapshots (
        snapshot_id uuid PRIMARY KEY, report_date date NOT NULL, source_note varchar(2000) NOT NULL,
        payload jsonb NOT NULL, sha256 varchar(64) NOT NULL UNIQUE, created_by varchar(100) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now());
        CREATE INDEX ix_ftth_network_snapshots_report_date ON ftth_network_snapshots(report_date);''')


def downgrade():
    op.execute('DROP TABLE ftth_network_snapshots;')
