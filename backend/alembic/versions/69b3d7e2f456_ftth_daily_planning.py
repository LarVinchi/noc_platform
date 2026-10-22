"""Frozen daily plans, revision evidence, weekly delivery and Telewyz provisioning."""
from alembic import op

revision = '69b3d7e2f456'
down_revision = '58a2c6d1e345'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TYPE isptype ADD VALUE IF NOT EXISTS 'TELEWYZ'")
    op.execute('''CREATE TABLE ftth_daily_plans (
        plan_id uuid PRIMARY KEY, report_date date NOT NULL UNIQUE, revision integer NOT NULL,
        status varchar(20) NOT NULL, payload jsonb NOT NULL, created_by varchar(100) NOT NULL,
        updated_by varchar(100) NOT NULL, updated_at timestamptz NOT NULL);
        CREATE TABLE ftth_plan_events (
        event_id uuid PRIMARY KEY, plan_id uuid NOT NULL REFERENCES ftth_daily_plans(plan_id),
        revision integer NOT NULL, action varchar(20) NOT NULL, actor_id varchar(100) NOT NULL,
        occurred_at timestamptz NOT NULL, payload jsonb NOT NULL, UNIQUE(plan_id,revision));
        CREATE TABLE ftth_report_deliveries (
        delivery_id uuid PRIMARY KEY, delivery_key varchar(64) NOT NULL UNIQUE,
        recipient varchar(254) NOT NULL, payload jsonb NOT NULL, status varchar(20) NOT NULL,
        attempts integer NOT NULL, updated_at timestamptz NOT NULL, error_type varchar(100));''')


def downgrade():
    op.execute('DROP TABLE ftth_report_deliveries; DROP TABLE ftth_plan_events; DROP TABLE ftth_daily_plans;')
    # PostgreSQL enum additions are intentionally retained; removing an in-use provider is unsafe.
