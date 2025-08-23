"""Create base tables

Revision ID: 007_create_base_tables  
Revises: 03333fdb06f0
Create Date: 2025-08-23 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '007_create_base_tables'
down_revision = '03333fdb06f0'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create enum types
    camera_type_enum = sa.Enum('RTSP', 'WEBCAM', name='cameratype')
    camera_type_enum.create(op.get_bind())
    
    user_role_enum = sa.Enum('SYSTEM_ADMIN', 'TENANT_ADMIN', 'SITE_MANAGER', 'WORKER', name='userrole')
    user_role_enum.create(op.get_bind())

    # Create tenants table
    op.create_table('tenants',
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id')
    )

    # Create users table
    op.create_table('users',
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(255), nullable=False),
        sa.Column('last_name', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', user_role_enum, nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    # Create sites table
    op.create_table('sites',
        sa.Column('site_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('site_id')
    )

    # Create cameras table
    op.create_table('cameras',
        sa.Column('camera_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('site_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('camera_type', camera_type_enum, nullable=False),
        sa.Column('rtsp_url', sa.Text(), nullable=True),
        sa.Column('device_index', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.site_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('camera_id')
    )

    # Create staff table
    op.create_table('staff',
        sa.Column('staff_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('site_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('staff_id')
    )

    # Create staff_face_images table
    op.create_table('staff_face_images',
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('image_id', sa.String(64), nullable=False),
        sa.Column('staff_id', sa.BigInteger(), nullable=False),
        sa.Column('image_path', sa.String(500), nullable=False),
        sa.Column('face_landmarks', sa.Text(), nullable=True),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('image_hash', sa.String(64), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.staff_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'image_id')
    )

    # Create customers table
    op.create_table('customers',
        sa.Column('customer_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('gender', sa.String(16), nullable=True),
        sa.Column('estimated_age_range', sa.String(32), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=False),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('visit_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('customer_id')
    )

    # Create visits table
    op.create_table('visits',
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('visit_id', sa.String(64), nullable=False),
        sa.Column('person_id', sa.BigInteger(), nullable=False),
        sa.Column('person_type', sa.String(16), nullable=False),
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

    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('key_id', sa.String(64), nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('hashed_key', sa.Text(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('key_id')
    )

    # Create indices
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_customers_last_seen', 'customers', ['tenant_id', 'last_seen'])
    op.create_index('idx_visits_timestamp', 'visits', ['tenant_id', 'timestamp'])
    op.create_index('idx_visits_person', 'visits', ['tenant_id', 'person_id', 'timestamp'])
    op.create_index('idx_visits_site', 'visits', ['tenant_id', 'site_id', 'timestamp'])
    op.create_index('idx_staff_face_images_staff_id', 'staff_face_images', ['tenant_id', 'staff_id'])
    op.create_index('idx_staff_face_images_primary', 'staff_face_images', ['tenant_id', 'is_primary'])
    op.create_index('idx_staff_face_images_hash', 'staff_face_images', ['tenant_id', 'staff_id', 'image_hash'], unique=True)

    # Insert default system admin user
    op.execute("""
        INSERT INTO users (user_id, username, email, first_name, last_name, password_hash, role, is_active, is_email_verified, password_changed_at, created_at, updated_at)
        VALUES (
            'admin-' || substr(md5(random()::text), 1, 8),
            'admin',
            'admin@system.local',
            'System',
            'Administrator',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBdVbURqGvmFvG',  -- password: admin123
            'SYSTEM_ADMIN',
            true,
            true,
            NOW(),
            NOW(),
            NOW()
        )
    """)

def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('api_keys')
    op.drop_table('visits')
    op.drop_table('customers')
    op.drop_table('staff_face_images')
    op.drop_table('staff')
    op.drop_table('cameras')
    op.drop_table('sites')
    op.drop_table('users')
    op.drop_table('tenants')
    
    # Drop enums
    op.execute('DROP TYPE userrole')
    op.execute('DROP TYPE cameratype')