"""merge_migrations

Revision ID: 03333fdb06f0
Revises: 006_add_users_table, 5279b8691612
Create Date: 2025-08-23 02:17:19.017691+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03333fdb06f0'
down_revision: Union[str, None] = ('006_add_users_table', '5279b8691612')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass