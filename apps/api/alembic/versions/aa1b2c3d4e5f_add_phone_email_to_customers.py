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
    # Add new optional fields to customers
    op.add_column('customers', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('customers', sa.Column('email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'email')
    op.drop_column('customers', 'phone')
