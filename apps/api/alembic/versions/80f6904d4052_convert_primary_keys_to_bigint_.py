"""convert_primary_keys_to_bigint_autoincrement

Revision ID: 80f6904d4052
Revises: 005_add_image_hash
Create Date: 2025-08-21 17:57:06.005608+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '80f6904d4052'
down_revision: Union[str, None] = '005_add_image_hash'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is now a no-op as all primary keys are already created as BigInteger with autoincrement in 007_create_base_tables.py
    pass
    
    # Note: Data migration would need to be done manually or with custom scripts
    # since we're changing from string IDs to auto-increment integers
    # The backup tables contain the original data for reference


def downgrade() -> None:
    # This migration is now a no-op as all primary keys are already created as BigInteger with autoincrement in 007_create_base_tables.py
    pass