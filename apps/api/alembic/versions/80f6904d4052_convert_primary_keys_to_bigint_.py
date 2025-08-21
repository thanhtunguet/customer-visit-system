"""convert_primary_keys_to_bigint_autoincrement

Revision ID: 80f6904d4052
Revises: 005_add_image_hash
Create Date: 2025-08-21 17:57:06.005608+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '80f6904d4052'
down_revision: Union[str, None] = '005_add_image_hash'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, we need to handle this migration carefully since we're changing primary keys
    # This migration will recreate tables with new schema
    
    # 1. Create backup tables for data preservation
    op.execute("CREATE TABLE sites_backup AS SELECT * FROM sites")
    op.execute("CREATE TABLE staff_backup AS SELECT * FROM staff")  
    op.execute("CREATE TABLE customers_backup AS SELECT * FROM customers")
    op.execute("CREATE TABLE cameras_backup AS SELECT * FROM cameras")
    op.execute("CREATE TABLE staff_face_images_backup AS SELECT * FROM staff_face_images")
    op.execute("CREATE TABLE visits_backup AS SELECT * FROM visits")
    
    # 2. Drop existing tables in correct order (foreign keys first)
    op.drop_table('visits')
    op.drop_table('staff_face_images')
    op.drop_table('cameras')
    op.drop_table('staff')
    op.drop_table('customers')
    op.drop_table('sites')
    
    # 3. Create new sites table with BIGINT primary key
    op.create_table('sites',
        sa.Column('site_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('site_id')
    )
    
    # 4. Create new staff table with BIGINT primary key
    op.create_table('staff',
        sa.Column('staff_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('site_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.site_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('staff_id')
    )
    
    # 5. Create new customers table with BIGINT primary key
    op.create_table('customers',
        sa.Column('customer_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('gender', sa.String(length=16), nullable=True),
        sa.Column('estimated_age_range', sa.String(length=32), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=False),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('visit_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('customer_id')
    )
    
    # 6. Create new cameras table with updated foreign key references
    op.create_table('cameras',
        sa.Column('camera_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('site_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('camera_type', postgresql.ENUM('RTSP', 'WEBCAM', name='cameratype', create_type=False), nullable=False),
        sa.Column('rtsp_url', sa.Text(), nullable=True),
        sa.Column('device_index', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.site_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('camera_id')
    )
    
    # 7. Create new staff_face_images table with updated foreign key references
    op.create_table('staff_face_images',
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('image_id', sa.String(length=64), nullable=False),
        sa.Column('staff_id', sa.BigInteger(), nullable=False),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('face_landmarks', sa.Text(), nullable=True),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('image_hash', sa.String(length=64), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.staff_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'image_id')
    )
    
    # 8. Create new visits table with updated foreign key references
    op.create_table('visits',
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('visit_id', sa.String(length=64), nullable=False),
        sa.Column('person_id', sa.BigInteger(), nullable=False),
        sa.Column('person_type', sa.String(length=16), nullable=False),
        sa.Column('site_id', sa.BigInteger(), nullable=False),
        sa.Column('camera_id', sa.BigInteger(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('image_path', sa.Text(), nullable=True),
        sa.Column('bbox_x', sa.Float(), nullable=True),
        sa.Column('bbox_y', sa.Float(), nullable=True),
        sa.Column('bbox_w', sa.Float(), nullable=True),
        sa.Column('bbox_h', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('tenant_id', 'visit_id')
    )
    
    # Create indexes for visits table
    op.create_index('idx_visits_timestamp', 'visits', ['tenant_id', 'timestamp'])
    op.create_index('idx_visits_person', 'visits', ['tenant_id', 'person_id', 'timestamp'])
    op.create_index('idx_visits_site', 'visits', ['tenant_id', 'site_id', 'timestamp'])
    
    # Create indexes for staff_face_images table
    op.create_index('idx_staff_face_images_staff_id', 'staff_face_images', ['tenant_id', 'staff_id'])
    op.create_index('idx_staff_face_images_primary', 'staff_face_images', ['tenant_id', 'is_primary'])
    op.create_index('idx_staff_face_images_hash', 'staff_face_images', ['tenant_id', 'staff_id', 'image_hash'], unique=True)
    
    # Note: Data migration would need to be done manually or with custom scripts
    # since we're changing from string IDs to auto-increment integers
    # The backup tables contain the original data for reference


def downgrade() -> None:
    # Restore original tables from backup
    op.drop_table('cameras')
    op.drop_table('staff')
    op.drop_table('customers') 
    op.drop_table('sites')
    
    # Restore from backup tables
    op.execute("CREATE TABLE sites AS SELECT * FROM sites_backup")
    op.execute("CREATE TABLE staff AS SELECT * FROM staff_backup")
    op.execute("CREATE TABLE customers AS SELECT * FROM customers_backup")
    op.execute("CREATE TABLE cameras AS SELECT * FROM cameras_backup")
    op.execute("CREATE TABLE staff_face_images AS SELECT * FROM staff_face_images_backup")
    op.execute("CREATE TABLE visits AS SELECT * FROM visits_backup")
    
    # Drop backup tables
    op.drop_table('sites_backup')
    op.drop_table('staff_backup')
    op.drop_table('customers_backup')
    op.drop_table('cameras_backup')
    op.drop_table('staff_face_images_backup')
    op.drop_table('visits_backup')