"""Add staff face images table

Revision ID: 004
Revises: 003
Create Date: 2025-08-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import DateTime, String, Integer, Boolean, Text, ForeignKey
from datetime import datetime

# revision identifiers
revision = '004_staff_face_images'
down_revision = 'aa1b2c3d4e5f'
branch_labels = None
depends_on = None

def upgrade():
    # This migration is now a no-op as staff_face_images table was created in 007_create_base_tables.py
    pass

def downgrade():
    # This migration is now a no-op as staff_face_images table was created in 007_create_base_tables.py
    pass