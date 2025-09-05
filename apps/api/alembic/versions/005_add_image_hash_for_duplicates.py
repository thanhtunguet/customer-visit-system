"""Add image_hash field for duplicate detection

Revision ID: 005
Revises: 004
Create Date: 2025-08-21 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import String

# revision identifiers
revision = '005_add_image_hash'
down_revision = '35a0a746c522'
branch_labels = None
depends_on = None

def upgrade():
    # This migration is now a no-op as image_hash column and index were created in 007_create_base_tables.py
    pass

def downgrade():
    # This migration is now a no-op as image_hash column and index were created in 007_create_base_tables.py
    pass