"""Private manual mail triage preview, without a mailbox connector."""
from alembic import op
revision='e164035a91d2'
down_revision='d053f24980c1'
branch_labels=depends_on=None


def upgrade():
    op.execute("""
      CREATE TABLE mail_triage_items (
        item_id uuid PRIMARY KEY,owner_id varchar(100) NOT NULL,request_key uuid NOT NULL,
        request_hash varchar(64) NOT NULL,source varchar(30) NOT NULL DEFAULT 'manual_preview',
        subject varchar(250) NOT NULL,sender varchar(320) NOT NULL,received_at timestamptz,
        entered_at timestamptz NOT NULL DEFAULT now(),excerpt varchar(400) NOT NULL,classification jsonb NOT NULL,
        state varchar(30) NOT NULL DEFAULT 'needs_review' CHECK(state IN ('needs_review','acknowledged','dismissed')),
        incident_id uuid REFERENCES incidents(incident_id),order_id uuid REFERENCES service_orders(order_id),
        action_note text,reviewed_by varchar(100),reviewed_at timestamptz,
        CONSTRAINT uq_mail_preview_request UNIQUE(owner_id,request_key));
      CREATE INDEX ix_mail_triage_items_owner_id ON mail_triage_items(owner_id);
      CREATE INDEX ix_mail_triage_review ON mail_triage_items(state,entered_at);
      CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON mail_triage_items FOR EACH ROW
        EXECUTE FUNCTION noc_capture_change('item_id','item_id,owner_id,source,state,incident_id,order_id,reviewed_by,reviewed_at,entered_at');
    """)


def downgrade():
    op.execute('DROP TABLE mail_triage_items')
