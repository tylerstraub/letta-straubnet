"""Database storage layer for World Info entries."""

from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from letta.orm.world_info_entry import WorldInfoEntry


async def get_world_info_entries(
    session: AsyncSession,
    organization_id: str,
    agent_id: Optional[str] = None,
) -> List[WorldInfoEntry]:
    """
    Query World Info entries from the database.

    Returns entries that:
    - Belong to the specified organization
    - Are enabled (enabled=True)
    - Are not soft-deleted (is_deleted=False)
    - Match the agent filter:
      - If agent_id is provided: returns entries where agent_id == agent_id OR agent_id IS NULL
        (agent-specific entries + global entries)
      - If agent_id is None: returns only global entries (agent_id IS NULL)
    - Ordered by insertion_order DESC (higher priority entries first, then lower)

    Args:
        session: SQLAlchemy async session
        organization_id: The organization ID to filter by (required)
        agent_id: Optional agent ID. If provided, returns agent-specific + global entries.
                  If None, returns only global entries.

    Returns:
        List of WorldInfoEntry objects, ordered by insertion_order DESC
    """
    # Build the query
    query = select(WorldInfoEntry).where(
        WorldInfoEntry.organization_id == organization_id,
        WorldInfoEntry.enabled == True,  # noqa: E712
    )

    # Filter by is_deleted if the field exists (soft-delete support)
    if hasattr(WorldInfoEntry, "is_deleted"):
        query = query.where(WorldInfoEntry.is_deleted == False)  # noqa: E712

    # Apply agent filter
    if agent_id is not None:
        # Get both agent-specific entries AND global entries (NULL agent_id)
        query = query.where(
            or_(
                WorldInfoEntry.agent_id == agent_id,
                WorldInfoEntry.agent_id.is_(None),
            )
        )
    else:
        # Only get global entries (no agent_id)
        query = query.where(WorldInfoEntry.agent_id.is_(None))

    # Order by insertion_order DESC (higher numbers = higher priority = inserted later)
    query = query.order_by(WorldInfoEntry.insertion_order.desc())

    # Execute query
    result = await session.execute(query)
    entries = result.scalars().all()

    return list(entries)

