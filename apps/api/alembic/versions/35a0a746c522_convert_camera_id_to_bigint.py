"""convert_camera_id_to_bigint

Revision ID: 35a0a746c522
Revises: 004_staff_face_images
Create Date: 2025-08-21 07:23:52.198242+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35a0a746c522'
down_revision: Union[str, None] = '004_staff_face_images'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, check if we need to do this migration by checking if camera_id is already bigint
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT data_type 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' AND column_name = 'camera_id'
    """))
    current_type = result.fetchone()
    
    if current_type and 'bigint' in current_type[0].lower():
        print("Camera ID is already bigint, skipping migration")
        return
    
    # Add new bigint camera_id_new column with auto-increment
    op.add_column('cameras', sa.Column('camera_id_new', sa.BigInteger(), autoincrement=True, nullable=True))
    
    # Add sequence for auto-increment (PostgreSQL specific)
    op.execute("CREATE SEQUENCE IF NOT EXISTS cameras_camera_id_new_seq")
    op.execute("ALTER TABLE cameras ALTER COLUMN camera_id_new SET DEFAULT nextval('cameras_camera_id_new_seq')")
    
    # Generate new IDs for existing records
    op.execute("""
        UPDATE cameras 
        SET camera_id_new = nextval('cameras_camera_id_new_seq')
        WHERE camera_id_new IS NULL
    """)
    
    # Update visits table - add new camera_id_new column
    op.add_column('visits', sa.Column('camera_id_new', sa.BigInteger(), nullable=True))
    
    # Map old camera_ids to new camera_id_new values
    op.execute("""
        UPDATE visits 
        SET camera_id_new = c.camera_id_new
        FROM cameras c
        WHERE visits.tenant_id = c.tenant_id 
          AND visits.site_id = c.site_id 
          AND visits.camera_id = c.camera_id
    """)
    
    # Get all foreign key constraints that reference the cameras table
    fk_constraints = connection.execute(sa.text("""
        SELECT tc.constraint_name, tc.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu 
        ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = 'cameras'
        AND ccu.column_name = 'camera_id'
    """))
    
    # Drop foreign key constraints
    for row in fk_constraints:
        constraint_name, table_name = row
        try:
            op.drop_constraint(constraint_name, table_name, type_='foreignkey')
            print(f"Dropped foreign key constraint: {constraint_name} on {table_name}")
        except Exception as e:
            print(f"Could not drop constraint {constraint_name}: {e}")
    
    # Drop old primary key constraint on cameras
    try:
        op.drop_constraint('cameras_pkey', 'cameras', type_='primary')
    except Exception as e:
        print(f"Could not drop primary key: {e}")
    
    # Drop old columns and rename new ones
    op.drop_column('visits', 'camera_id')
    op.drop_column('cameras', 'camera_id')
    
    # Rename new columns
    op.alter_column('cameras', 'camera_id_new', new_column_name='camera_id', nullable=False)
    op.alter_column('visits', 'camera_id_new', new_column_name='camera_id', nullable=False)
    
    # Add new primary key constraint
    op.create_primary_key('cameras_pkey', 'cameras', ['tenant_id', 'site_id', 'camera_id'])
    
    # Recreate foreign key constraint on visits
    op.create_foreign_key(
        'fk_visits_camera', 
        'visits', 'cameras',
        ['tenant_id', 'site_id', 'camera_id'], 
        ['tenant_id', 'site_id', 'camera_id'],
        ondelete='CASCADE'
    )
    
    print("Successfully converted camera_id to bigint")


def downgrade() -> None:
    # This downgrade is complex and potentially destructive
    # It would require converting bigint IDs back to string format
    # For now, we'll raise an exception to prevent accidental downgrades
    raise Exception("Downgrading camera_id from bigint to string is not supported due to data loss concerns")
    pass