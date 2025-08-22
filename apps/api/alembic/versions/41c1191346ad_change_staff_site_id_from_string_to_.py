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
    # Change staff.site_id from varchar to bigint
    op.execute('ALTER TABLE staff ALTER COLUMN site_id TYPE BIGINT USING site_id::BIGINT')


def downgrade() -> None:
    # Revert staff.site_id back to varchar
    op.execute('ALTER TABLE staff ALTER COLUMN site_id TYPE VARCHAR(64) USING site_id::VARCHAR(64)')