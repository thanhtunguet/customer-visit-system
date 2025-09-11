"""Add site_id to users table

Revision ID: 001
Revises:
Create Date: 2025-01-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add site_id column to users table
    op.add_column("users", sa.Column("site_id", sa.BigInteger(), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_users_site_id",
        "users",
        "sites",
        ["site_id"],
        ["site_id"],
        ondelete="CASCADE",
    )

    # Add index for site_id
    op.create_index("idx_users_site_id", "users", ["site_id"])


def downgrade() -> None:
    # Drop index
    op.drop_index("idx_users_site_id", table_name="users")

    # Drop foreign key constraint
    op.drop_constraint("fk_users_site_id", "users", type_="foreignkey")

    # Drop column
    op.drop_column("users", "site_id")
