"""Change staff site_id from string to bigint

Revision ID: 41c1191346ad
Revises: 80f6904d4052
Create Date: 2025-08-22 09:05:57.715933+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41c1191346ad'
down_revision: Union[str, None] = '80f6904d4052'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is now a no-op as staff.site_id is already created as BigInteger in 007_create_base_tables.py
    pass


def downgrade() -> None:
    # This migration is now a no-op as staff.site_id is already created as BigInteger in 007_create_base_tables.py
    pass