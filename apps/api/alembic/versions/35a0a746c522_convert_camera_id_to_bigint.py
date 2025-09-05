"""convert_camera_id_to_bigint

Revision ID: 35a0a746c522
Revises: 004_staff_face_images
Create Date: 2025-08-21 07:23:52.198242+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35a0a746c522'
down_revision: Union[str, None] = '004_staff_face_images'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is now a no-op as camera_id is already created as BigInteger in 007_create_base_tables.py
    pass


def downgrade() -> None:
    # This migration is now a no-op as camera_id is already created as BigInteger in 007_create_base_tables.py
    pass