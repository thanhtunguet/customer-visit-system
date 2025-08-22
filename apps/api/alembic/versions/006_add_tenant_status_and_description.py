"""Add tenant status and description fields

Revision ID: 006_add_tenant_status_and_description
Revises: aa1b2c3d4e5f
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_tenant_status_and_description'
down_revision = 'aa1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    # Add description and is_active columns to tenants table
    op.add_column('tenants', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('tenants', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade():
    # Remove description and is_active columns from tenants table
    op.drop_column('tenants', 'is_active')
    op.drop_column('tenants', 'description')