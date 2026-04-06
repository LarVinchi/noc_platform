"""expand_service_order_add_install_metrics

Revision ID: 895fc00dfdb1
Revises: ffc980c60b1b
Create Date: 2026-04-06 10:01:16.399119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '895fc00dfdb1'
down_revision: Union[str, Sequence[str], None] = 'ffc980c60b1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. Create the new install_metrics table
    op.create_table('install_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=True),
        sa.Column('flexscan_result_dbm', sa.Float(), nullable=True),
        sa.Column('checklist_completed', sa.Boolean(), nullable=True),
        sa.Column('photo_nap_url', sa.String(), nullable=True),
        sa.Column('photo_routing_url', sa.String(), nullable=True),
        sa.Column('photo_rosette_url', sa.String(), nullable=True),
        sa.Column('photo_flexscan_url', sa.String(), nullable=True),
        sa.Column('acceptance_doc_url', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['service_orders.order_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. Add the new columns to service_orders
    op.add_column('service_orders', sa.Column('coverage_zone_name', sa.String(), nullable=True))
    op.add_column('service_orders', sa.Column('pfs_split_level', sa.String(), nullable=True))
    op.add_column('service_orders', sa.Column('ont_tech_name', sa.String(), nullable=True))
    
    # 3. Handle the columns we want to explicitly modify or drop on service_orders
    op.drop_column('service_orders', 'cpe_tech_name')
    op.drop_column('service_orders', 'noc_personnel_id')
    op.drop_column('service_orders', 'requested_by_id')
    op.drop_column('service_orders', 'approved_by_id')


def downgrade() -> None:
    """Downgrade schema."""
    
    # 1. Add back dropped columns on service_orders
    op.add_column('service_orders', sa.Column('approved_by_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('service_orders', sa.Column('requested_by_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('service_orders', sa.Column('noc_personnel_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('service_orders', sa.Column('cpe_tech_name', sa.VARCHAR(), autoincrement=False, nullable=True))
    
    # 2. Drop the newly added columns on service_orders
    op.drop_column('service_orders', 'ont_tech_name')
    op.drop_column('service_orders', 'pfs_split_level')
    op.drop_column('service_orders', 'coverage_zone_name')
    
    # 3. Drop the new install_metrics table
    op.drop_table('install_metrics')