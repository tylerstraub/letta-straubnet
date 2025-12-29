"""add_id_column_to_world_info_injection_states

Revision ID: 874ef24db445
Revises: 63cdb17629d0
Create Date: 2025-12-29 02:24:47.997803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '874ef24db445'
down_revision: Union[str, None] = '63cdb17629d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add id column as nullable first
    op.add_column(
        "world_info_injection_states",
        sa.Column("id", sa.String(), nullable=True)
    )
    
    # Generate IDs for existing rows using the format: wiis-{uuid}
    # PostgreSQL's gen_random_uuid() function generates UUIDs
    op.execute(
        text("""
            UPDATE world_info_injection_states
            SET id = 'wiis-' || gen_random_uuid()::text
            WHERE id IS NULL
        """)
    )
    
    # Make id NOT NULL
    op.alter_column("world_info_injection_states", "id", nullable=False)
    
    # Add primary key constraint on id
    op.create_primary_key(
        "world_info_injection_states_pkey",
        "world_info_injection_states",
        ["id"]
    )


def downgrade() -> None:
    # Drop primary key constraint
    op.drop_constraint(
        "world_info_injection_states_pkey",
        "world_info_injection_states",
        type_="primary"
    )
    
    # Drop id column
    op.drop_column("world_info_injection_states", "id")
