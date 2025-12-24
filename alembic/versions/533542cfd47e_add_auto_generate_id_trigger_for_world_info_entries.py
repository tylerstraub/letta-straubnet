"""add auto-generate id trigger for world_info_entries

Revision ID: 533542cfd47e
Revises: ca6df7324851
Create Date: 2025-12-23 22:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
from letta.settings import settings

# revision identifiers, used by Alembic.
revision: str = "533542cfd47e"
down_revision: Union[str, None] = "ca6df7324851"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip this migration for SQLite (triggers not needed, ORM handles ID generation)
    if not settings.letta_pg_uri_no_default:
        return

    # Create function that generates world_info_entry IDs if they are NULL
    # Note: Uses search_path (set by database init) to determine schema
    op.execute(
        """
        CREATE OR REPLACE FUNCTION generate_world_info_entry_id()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.id IS NULL THEN
                NEW.id := 'world-info-entry-' || gen_random_uuid()::text;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function that sets default organization_id if NULL
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_default_organization_id()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.organization_id IS NULL THEN
                NEW.organization_id := 'org-00000000-0000-4000-8000-000000000000';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function that sets default timestamps if NULL
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_default_timestamps()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.created_at IS NULL THEN
                NEW.created_at := now();
            END IF;
            IF NEW.updated_at IS NULL THEN
                NEW.updated_at := now();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function that sets default field values if NULL
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_default_field_values()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.insertion_order IS NULL THEN
                NEW.insertion_order := 100;
            END IF;
            IF NEW.enabled IS NULL THEN
                NEW.enabled := TRUE;
            END IF;
            IF NEW.case_sensitive IS NULL THEN
                NEW.case_sensitive := FALSE;
            END IF;
            IF NEW.match_whole_words IS NULL THEN
                NEW.match_whole_words := TRUE;
            END IF;
            IF NEW.is_deleted IS NULL THEN
                NEW.is_deleted := FALSE;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Drop triggers if they exist (for idempotency if manually created)
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_generate_id ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_organization_id ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_timestamps ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_field_values ON world_info_entries;")

    # Create trigger for auto-generating IDs
    op.execute(
        """
        CREATE TRIGGER world_info_entries_generate_id
            BEFORE INSERT ON world_info_entries
            FOR EACH ROW
            EXECUTE FUNCTION generate_world_info_entry_id();
        """
    )

    # Create trigger for setting default organization_id
    op.execute(
        """
        CREATE TRIGGER world_info_entries_set_organization_id
            BEFORE INSERT ON world_info_entries
            FOR EACH ROW
            EXECUTE FUNCTION set_default_organization_id();
        """
    )

    # Create trigger for setting default timestamps
    op.execute(
        """
        CREATE TRIGGER world_info_entries_set_timestamps
            BEFORE INSERT ON world_info_entries
            FOR EACH ROW
            EXECUTE FUNCTION set_default_timestamps();
        """
    )

    # Create trigger for setting default field values
    op.execute(
        """
        CREATE TRIGGER world_info_entries_set_field_values
            BEFORE INSERT ON world_info_entries
            FOR EACH ROW
            EXECUTE FUNCTION set_default_field_values();
        """
    )


def downgrade() -> None:
    # Skip this migration for SQLite
    if not settings.letta_pg_uri_no_default:
        return

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_generate_id ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_organization_id ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_timestamps ON world_info_entries;")
    op.execute("DROP TRIGGER IF EXISTS world_info_entries_set_field_values ON world_info_entries;")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS generate_world_info_entry_id();")
    op.execute("DROP FUNCTION IF EXISTS set_default_organization_id();")
    op.execute("DROP FUNCTION IF EXISTS set_default_timestamps();")
    op.execute("DROP FUNCTION IF EXISTS set_default_field_values();")

