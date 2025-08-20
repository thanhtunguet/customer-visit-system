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
    # Create staff_face_images table
    op.create_table('staff_face_images',
        sa.Column('tenant_id', String(64), primary_key=True),
        sa.Column('image_id', String(64), primary_key=True),
        sa.Column('staff_id', String(64), nullable=False),
        sa.Column('image_path', String(500), nullable=False),
        sa.Column('face_landmarks', Text, nullable=True),  # JSON serialized landmarks
        sa.Column('face_embedding', Text, nullable=True),  # JSON serialized vector
        sa.Column('is_primary', Boolean, default=False, nullable=False),
        sa.Column('created_at', DateTime, default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', DateTime, default=datetime.utcnow, nullable=False),
        
        # Foreign key constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id', 'staff_id'], ['staff.tenant_id', 'staff.staff_id'], ondelete='CASCADE'),
        
        # Indexes
        sa.PrimaryKeyConstraint('tenant_id', 'image_id'),
    )
    
    # Add indexes
    op.create_index('idx_staff_face_images_staff_id', 'staff_face_images', ['tenant_id', 'staff_id'])
    op.create_index('idx_staff_face_images_primary', 'staff_face_images', ['tenant_id', 'is_primary'])

def downgrade():
    op.drop_index('idx_staff_face_images_primary', 'staff_face_images')
    op.drop_index('idx_staff_face_images_staff_id', 'staff_face_images')
    op.drop_table('staff_face_images')