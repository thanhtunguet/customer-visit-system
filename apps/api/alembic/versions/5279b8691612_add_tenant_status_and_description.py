"""add_tenant_status_and_description

Revision ID: 5279b8691612
Revises: 41c1191346ad
Create Date: 2025-08-22 16:25:48.124680+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5279b8691612'
down_revision: Union[str, None] = '41c1191346ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add description and is_active columns to tenants table
    op.add_column('tenants', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('tenants', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade() -> None:
    # Remove description and is_active columns from tenants table
    op.drop_column('tenants', 'is_active')
    op.drop_column('tenants', 'description')