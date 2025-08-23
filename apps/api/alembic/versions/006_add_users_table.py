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
    # Create enum type for user roles
    user_role_enum = sa.Enum('SYSTEM_ADMIN', 'TENANT_ADMIN', 'SITE_MANAGER', 'WORKER', name='userrole')
    user_role_enum.create(op.get_bind())
    
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
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Create indices
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])

    # Insert default system admin user
    op.execute("""
        INSERT INTO users (user_id, username, email, first_name, last_name, password_hash, role, is_active, is_email_verified, password_changed_at, created_at, updated_at)
        VALUES (
            gen_random_uuid()::text,
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
    # Drop indices first
    op.drop_index('idx_users_tenant_id', table_name='users')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_username', table_name='users')
    
    # Drop table
    op.drop_table('users')
    
    # Drop enum
    op.execute('DROP TYPE userrole')