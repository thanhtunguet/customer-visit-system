"""merge camera sessions and customer face images migrations

Revision ID: 6f30dd0aa5a8
Revises: 010_add_customer_face_images, fad58bb4f71c
Create Date: 2025-09-05 03:45:56.953314+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f30dd0aa5a8'
down_revision: Union[str, None] = ('010_add_customer_face_images', 'fad58bb4f71c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass