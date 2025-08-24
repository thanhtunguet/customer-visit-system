"""Add workers table

Revision ID: 008_add_workers_table
Revises: 007_create_base_tables
Create Date: 2025-08-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '008_add_workers_table'
down_revision = '007_create_base_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workers table
    op.create_table(
        'workers',
        sa.Column('worker_id', sa.String(64), nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('worker_name', sa.String(255), nullable=False),
        sa.Column('worker_version', sa.String(32), nullable=True),
        sa.Column('capabilities', sa.Text(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='offline'),
        sa.Column('site_id', sa.BigInteger(), nullable=True),
        sa.Column('camera_id', sa.BigInteger(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_faces_processed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('registration_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('worker_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index(
        'idx_workers_tenant_status', 
        'workers', 
        ['tenant_id', 'status']
    )
    op.create_index(
        'idx_workers_heartbeat', 
        'workers', 
        ['tenant_id', 'last_heartbeat']
    )
    op.create_index(
        'idx_workers_hostname', 
        'workers', 
        ['tenant_id', 'hostname']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_workers_hostname', table_name='workers')
    op.drop_index('idx_workers_heartbeat', table_name='workers')
    op.drop_index('idx_workers_tenant_status', table_name='workers')
    
    # Drop table
    op.drop_table('workers')