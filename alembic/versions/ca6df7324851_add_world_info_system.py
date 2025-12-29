"""add world_info_system

Revision ID: ca6df7324851
Revises: 39577145c45d
Create Date: 2025-12-23 22:30:00.000000

This migration creates the World Info system tables with the final schema.
Consolidated from multiple intermediate migrations to include only necessary fields.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ca6df7324851"
down_revision: Union[str, None] = "39577145c45d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create world_info_entries table
    op.create_table(
        "world_info_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("keywords", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("insertion_order", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("case_sensitive", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("match_whole_words", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("cooldown", sa.Integer(), nullable=True),
        sa.Column("expiration", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("_created_by_id", sa.String(), nullable=True),
        sa.Column("_last_updated_by_id", sa.String(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for world_info_entries
    op.create_index(
        "ix_world_info_entries_organization_id_agent_id",
        "world_info_entries",
        ["organization_id", "agent_id"],
    )
    op.create_index(
        "ix_world_info_entries_insertion_order",
        "world_info_entries",
        ["insertion_order"],
    )
    
    # Create world_info_injection_states table
    op.create_table(
        "world_info_injection_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("world_info_entry_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("current_cooldown", sa.Integer(), nullable=True),
        sa.Column("current_expiration", sa.Integer(), nullable=True),
        sa.Column("cooldown_setting", sa.Integer(), nullable=False),
        sa.Column("expiration_setting", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("_created_by_id", sa.String(), nullable=True),
        sa.Column("_last_updated_by_id", sa.String(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["world_info_entry_id"],
            ["world_info_entries.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("world_info_entry_id", "agent_id", name="uq_world_info_entry_agent"),
    )
    
    # Create indexes for world_info_injection_states
    op.create_index(
        "ix_world_info_injection_states_entry_agent",
        "world_info_injection_states",
        ["world_info_entry_id", "agent_id"],
    )
    op.create_index(
        "ix_world_info_injection_states_organization_id",
        "world_info_injection_states",
        ["organization_id"],
    )
    op.create_index(
        "ix_world_info_injection_states_agent_id",
        "world_info_injection_states",
        ["agent_id"],
    )


def downgrade() -> None:
    # Drop indexes for world_info_injection_states
    op.drop_index("ix_world_info_injection_states_agent_id", table_name="world_info_injection_states")
    op.drop_index("ix_world_info_injection_states_organization_id", table_name="world_info_injection_states")
    op.drop_index("ix_world_info_injection_states_entry_agent", table_name="world_info_injection_states")
    
    # Drop world_info_injection_states table
    op.drop_table("world_info_injection_states")
    
    # Drop indexes for world_info_entries
    op.drop_index("ix_world_info_entries_insertion_order", table_name="world_info_entries")
    op.drop_index("ix_world_info_entries_organization_id_agent_id", table_name="world_info_entries")
    
    # Drop world_info_entries table
    op.drop_table("world_info_entries")

