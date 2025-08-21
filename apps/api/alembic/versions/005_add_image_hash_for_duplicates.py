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
    # Add image_hash column to staff_face_images table
    op.add_column('staff_face_images', 
                  sa.Column('image_hash', String(64), nullable=True))
    
    # Add unique constraint on tenant_id, staff_id, image_hash to prevent duplicates
    op.create_index('idx_staff_face_images_hash', 'staff_face_images', 
                   ['tenant_id', 'staff_id', 'image_hash'], unique=True)

def downgrade():
    op.drop_index('idx_staff_face_images_hash', 'staff_face_images')
    op.drop_column('staff_face_images', 'image_hash')