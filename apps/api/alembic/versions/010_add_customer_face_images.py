"""Add customer face images table for face gallery

Revision ID: 010
Revises: 009
Create Date: 2025-01-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_customer_face_images'
down_revision = '009_add_visit_session_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create customer_face_images table
    op.create_table(
        'customer_face_images',
        sa.Column('image_id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('customer_id', sa.BigInteger, nullable=False),
        sa.Column('image_path', sa.String(500), nullable=False),
        sa.Column('confidence_score', sa.Float, nullable=False),
        sa.Column('quality_score', sa.Float, nullable=True),
        sa.Column('face_bbox', sa.JSON, nullable=True),  # [x, y, w, h]
        sa.Column('embedding', sa.JSON, nullable=True),  # Face embedding vector
        sa.Column('image_hash', sa.String(64), nullable=True),  # For duplicate detection
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('visit_id', sa.String(64), nullable=True),  # Reference to source visit
        sa.Column('detection_metadata', sa.JSON, nullable=True),  # Additional metadata (detector, landmarks, etc.)
    )
    
    # Add indexes
    op.create_index('idx_customer_face_images_tenant_customer', 'customer_face_images', 
                   ['tenant_id', 'customer_id'])
    op.create_index('idx_customer_face_images_confidence', 'customer_face_images', 
                   ['tenant_id', 'customer_id', 'confidence_score'])
    op.create_index('idx_customer_face_images_hash', 'customer_face_images', 
                   ['tenant_id', 'image_hash'])
    op.create_index('idx_customer_face_images_created', 'customer_face_images', 
                   ['tenant_id', 'customer_id', 'created_at'])
    
    # Add foreign key constraint (customer_id is the primary key)
    op.create_foreign_key(
        'fk_customer_face_images_customer',
        'customer_face_images', 'customers',
        ['customer_id'], ['customer_id'],
        ondelete='CASCADE'
    )
    
    # Add RLS policy for multi-tenancy (skip in development)
    # op.execute("""
    #     ALTER TABLE customer_face_images ENABLE ROW LEVEL SECURITY;
    #     
    #     CREATE POLICY customer_face_images_tenant_policy ON customer_face_images
    #     FOR ALL TO authenticated
    #     USING (tenant_id = current_setting('app.tenant_id', true));
    # """)


def downgrade() -> None:
    # Drop RLS policy (skip in development)
    # op.execute("""
    #     DROP POLICY IF EXISTS customer_face_images_tenant_policy ON customer_face_images;
    #     ALTER TABLE customer_face_images DISABLE ROW LEVEL SECURITY;
    # """)
    
    # Drop foreign key constraint
    op.drop_constraint('fk_customer_face_images_customer', 'customer_face_images', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('idx_customer_face_images_created', 'customer_face_images')
    op.drop_index('idx_customer_face_images_hash', 'customer_face_images')
    op.drop_index('idx_customer_face_images_confidence', 'customer_face_images')
    op.drop_index('idx_customer_face_images_tenant_customer', 'customer_face_images')
    
    # Drop table
    op.drop_table('customer_face_images')