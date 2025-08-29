"""add camera_sessions table for lease-based delegation

Revision ID: fad58bb4f71c
Revises: 008_add_workers_table
Create Date: 2025-08-29 04:40:29.681017+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fad58bb4f71c'
down_revision: Union[str, None] = '008_add_workers_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create camera_sessions table for lease-based delegation
    op.create_table(
        'camera_sessions',
        sa.Column('camera_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=True),
        sa.Column('generation', sa.BigInteger(), nullable=False, default=0),
        sa.Column('state', sa.String(20), nullable=False, default='PENDING'),  # PENDING|ACTIVE|PAUSED|ORPHANED|TERMINATED
        sa.Column('lease_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('camera_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id']),
        sa.ForeignKeyConstraint(['site_id'], ['sites.site_id']),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.camera_id'])
    )
    
    # Add indexes for common queries
    op.create_index('idx_camera_sessions_tenant_site', 'camera_sessions', ['tenant_id', 'site_id'])
    op.create_index('idx_camera_sessions_worker', 'camera_sessions', ['worker_id'])
    op.create_index('idx_camera_sessions_state', 'camera_sessions', ['state'])
    op.create_index('idx_camera_sessions_lease_expires', 'camera_sessions', ['lease_expires_at'])
    
    # Add new columns to workers table for enhanced capacity tracking (only if they don't exist)
    # Note: status column already exists, so we skip it
    op.add_column('workers', sa.Column('capacity', sa.JSON(), nullable=False, server_default='{"slots":1,"cpu":0,"gpu":0,"mem":0}'))
    op.add_column('workers', sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Add new columns to cameras table for capabilities and probing
    op.add_column('cameras', sa.Column('caps', sa.JSON(), nullable=True))
    op.add_column('cameras', sa.Column('last_probe_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('cameras', sa.Column('last_state_change_at', sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from cameras table
    op.drop_column('cameras', 'last_state_change_at')
    op.drop_column('cameras', 'last_probe_at')
    op.drop_column('cameras', 'caps')
    
    # Remove columns from workers table (excluding status which existed before)
    op.drop_column('workers', 'last_seen_at')
    op.drop_column('workers', 'capacity')
    
    # Drop indexes
    op.drop_index('idx_camera_sessions_lease_expires')
    op.drop_index('idx_camera_sessions_state')
    op.drop_index('idx_camera_sessions_worker')
    op.drop_index('idx_camera_sessions_tenant_site')
    
    # Drop camera_sessions table
    op.drop_table('camera_sessions')