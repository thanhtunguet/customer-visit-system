"""Add users table for authentication

Revision ID: 006_add_users_table
Revises: 80f6904d4052
Create Date: 2025-08-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '006_add_users_table'
down_revision = '80f6904d4052'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # This migration is now a no-op as users table, userrole enum, and default admin user are already created in 007_create_base_tables.py
    pass

def downgrade() -> None:
    # This migration is now a no-op as users table, userrole enum, and default admin user are already created in 007_create_base_tables.py
    pass