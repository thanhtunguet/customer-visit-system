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
    # This migration is now a no-op as description and is_active columns are already created in 007_create_base_tables.py
    pass


def downgrade() -> None:
    # This migration is now a no-op as description and is_active columns are already created in 007_create_base_tables.py
    pass