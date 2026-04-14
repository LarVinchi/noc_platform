"""simplify_workflow_stages

Revision ID: 2bf45fdfe8b1
Revises: 79983d3f81f0
Create Date: 2026-04-07 05:31:34.456152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bf45fdfe8b1'
down_revision: Union[str, Sequence[str], None] = '79983d3f81f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Convert the column temporarily to standard text
    op.execute("ALTER TABLE service_orders ALTER COLUMN status TYPE VARCHAR(255)")
    
    # 2. Drop the old ENUM type
    op.execute("DROP TYPE IF EXISTS workflowstage")
    
    # 3. Create the new clean 5-step ENUM
    op.execute("CREATE TYPE workflowstage AS ENUM ('REQUESTED', 'SCHEDULED', 'IN_PROGRESS', 'PENDING_ACCEPTANCE', 'MONITORED')")
    
    # 4. Safely map any old data to the new statuses so the app doesn't crash
    op.execute("UPDATE service_orders SET status = 'SCHEDULED' WHERE status = 'DESIGNED'")
    op.execute("UPDATE service_orders SET status = 'IN_PROGRESS' WHERE status IN ('PFS_TESTING', 'NAP_TESTING', 'ROSETTE_TESTING', 'DROP_INSTALLATION')")
    op.execute("UPDATE service_orders SET status = 'MONITORED' WHERE status = 'ACTIVE'")
    
    # 5. Lock the column back into the new ENUM
    op.execute("ALTER TABLE service_orders ALTER COLUMN status TYPE workflowstage USING status::workflowstage")


def downgrade() -> None:
    pass
