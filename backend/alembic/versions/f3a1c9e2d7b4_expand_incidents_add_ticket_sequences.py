"""expand_incidents_add_ticket_sequences

Revision ID: f3a1c9e2d7b4
Revises: 2bf45fdfe8b1
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a1c9e2d7b4'
down_revision: Union[str, Sequence[str], None] = '2bf45fdfe8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extend incidents with fields from the historical incident log ---
    op.add_column('incidents', sa.Column('tt_number', sa.String(), nullable=True))
    op.create_index('ix_incidents_tt_number', 'incidents', ['tt_number'], unique=True)
    op.add_column('incidents', sa.Column('ticket_category', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('category', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('severity', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('short_description', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('notes', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('reason_for_delay', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('rfo_root_cause', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('rfo_root_cause_detail', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('impact', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('impact_details', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('is_planned', sa.Boolean(), nullable=True))
    op.add_column('incidents', sa.Column('network_route', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('network_node', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('resolution_team', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('resolution_method', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('responsible_person', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('opened_by', sa.String(), nullable=True))
    op.add_column('incidents', sa.Column('closed_by', sa.String(), nullable=True))

    # --- New table backing auto-generated ticket numbers ---
    op.create_table(
        'ticket_sequences',
        sa.Column('category_code', sa.String(), primary_key=True),
        sa.Column('last_sequence', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('ticket_sequences')

    op.drop_column('incidents', 'closed_by')
    op.drop_column('incidents', 'opened_by')
    op.drop_column('incidents', 'responsible_person')
    op.drop_column('incidents', 'resolution_method')
    op.drop_column('incidents', 'resolution_team')
    op.drop_column('incidents', 'network_node')
    op.drop_column('incidents', 'network_route')
    op.drop_column('incidents', 'is_planned')
    op.drop_column('incidents', 'impact_details')
    op.drop_column('incidents', 'impact')
    op.drop_column('incidents', 'rfo_root_cause_detail')
    op.drop_column('incidents', 'rfo_root_cause')
    op.drop_column('incidents', 'reason_for_delay')
    op.drop_column('incidents', 'notes')
    op.drop_column('incidents', 'short_description')
    op.drop_column('incidents', 'severity')
    op.drop_column('incidents', 'category')
    op.drop_column('incidents', 'ticket_category')
    op.drop_index('ix_incidents_tt_number', table_name='incidents')
    op.drop_column('incidents', 'tt_number')
