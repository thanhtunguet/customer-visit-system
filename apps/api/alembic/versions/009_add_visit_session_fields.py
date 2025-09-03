"""Add visit session fields for deduplication

Revision ID: 009
Revises: 008
Create Date: 2025-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_visit_session_fields'
down_revision = '008_add_workers_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to visits table for session management
    op.add_column('visits', sa.Column('visit_session_id', sa.String(64), nullable=True))
    op.add_column('visits', sa.Column('first_seen', sa.DateTime, nullable=True))
    op.add_column('visits', sa.Column('last_seen', sa.DateTime, nullable=True))
    op.add_column('visits', sa.Column('visit_duration_seconds', sa.Integer, nullable=True))
    op.add_column('visits', sa.Column('detection_count', sa.Integer, default=1, nullable=False))
    op.add_column('visits', sa.Column('highest_confidence', sa.Float, nullable=True))
    
    # Add indexes for efficient session queries
    op.create_index('idx_visits_session', 'visits', ['tenant_id', 'visit_session_id'])
    op.create_index('idx_visits_person_time', 'visits', ['tenant_id', 'person_id', 'last_seen'])
    
    # Migrate existing data: set first_seen and last_seen to timestamp, session_id to visit_id
    op.execute("""
        UPDATE visits 
        SET 
            visit_session_id = visit_id,
            first_seen = timestamp,
            last_seen = timestamp,
            visit_duration_seconds = 0,
            detection_count = 1,
            highest_confidence = confidence_score
        WHERE visit_session_id IS NULL
    """)
    
    # Make visit_session_id and first_seen NOT NULL after data migration
    op.alter_column('visits', 'visit_session_id', nullable=False)
    op.alter_column('visits', 'first_seen', nullable=False)
    op.alter_column('visits', 'last_seen', nullable=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_visits_session', 'visits')
    op.drop_index('idx_visits_person_time', 'visits')
    
    # Remove columns
    op.drop_column('visits', 'highest_confidence')
    op.drop_column('visits', 'detection_count')
    op.drop_column('visits', 'visit_duration_seconds')
    op.drop_column('visits', 'last_seen')
    op.drop_column('visits', 'first_seen')
    op.drop_column('visits', 'visit_session_id')