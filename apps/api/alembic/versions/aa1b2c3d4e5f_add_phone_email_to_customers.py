"""Add phone and email to customers

Revision ID: aa1b2c3d4e5f
Revises: 5e1ced01ece7
Create Date: 2025-08-20 04:15:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa1b2c3d4e5f'
down_revision: Union[str, None] = '5e1ced01ece7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is now a no-op as phone and email columns were created in 007_create_base_tables.py
    pass


def downgrade() -> None:
    # This migration is now a no-op as phone and email columns were created in 007_create_base_tables.py
    pass
