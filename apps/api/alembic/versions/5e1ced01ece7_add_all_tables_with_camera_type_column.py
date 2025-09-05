"""Add all tables with camera_type column

Revision ID: 5e1ced01ece7
Revises: f5c54a22f4c0
Create Date: 2025-08-20 03:13:29.069166+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e1ced01ece7'
down_revision: Union[str, None] = 'f5c54a22f4c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is now a no-op as the columns were created in 007_create_base_tables.py
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # This migration is now a no-op as the columns were created in 007_create_base_tables.py
    pass
    # ### end Alembic commands ###
    # ### end Alembic commands ###