"""
Manager for World Info entry operations.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from letta.log import get_logger
from letta.orm.errors import NoResultFound
from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel
from letta.otel.tracing import trace_method
from letta.schemas.user import User as PydanticUser
from letta.schemas.world_info_entry import (
    WorldInfoEntry as PydanticWorldInfoEntry,
    WorldInfoEntryCreate,
    WorldInfoEntryUpdate,
)
from letta.schemas.world_info_entry_state import WorldInfoEntryState
from letta.server.db import db_registry
from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
from letta.utils import enforce_types

logger = get_logger(__name__)


class WorldInfoManager:
    """
    Manages World Info entry CRUD operations.
    """

    @enforce_types
    @trace_method
    async def list_entries_async(
        self,
        actor: PydanticUser,
        agent_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[PydanticWorldInfoEntry]:
        """
        List World Info entries for the actor's organization.

        Args:
            actor: The user making the request
            agent_id: Optional agent ID filter. If provided, returns agent-specific entries plus global entries.
                     If None, returns only global entries.
            enabled: Optional enabled status filter. If None, returns both enabled and disabled entries.

        Returns:
            List of World Info entries, ordered by insertion_order ASC
        """
        if not actor.organization_id:
            raise ValueError("Actor must have an organization_id")

        async with db_registry.async_session() as session:
            # Build the query
            query = select(WorldInfoEntryModel).where(
                WorldInfoEntryModel.organization_id == actor.organization_id,
            )

            # Filter by enabled status if specified
            if enabled is not None:
                query = query.where(WorldInfoEntryModel.enabled == enabled)

            # Filter by is_deleted (soft-delete support)
            query = query.where(WorldInfoEntryModel.is_deleted == False)  # noqa: E712

            # Apply agent filter
            if agent_id is not None:
                # Get both agent-specific entries AND global entries (NULL agent_id)
                query = query.where(
                    or_(
                        WorldInfoEntryModel.agent_id == agent_id,
                        WorldInfoEntryModel.agent_id.is_(None),
                    )
                )
            else:
                # Only get global entries (no agent_id)
                query = query.where(WorldInfoEntryModel.agent_id.is_(None))

            # Order by insertion_order ASC (lower numbers first, higher numbers last)
            query = query.order_by(WorldInfoEntryModel.insertion_order.asc())

            # Execute query
            result = await session.execute(query)
            entries = result.scalars().all()

            return [entry.to_pydantic() for entry in entries]

    @enforce_types
    @trace_method
    async def get_entry_async(
        self,
        entry_id: str,
        actor: PydanticUser,
    ) -> PydanticWorldInfoEntry:
        """
        Retrieve a World Info entry by ID.

        Args:
            entry_id: The entry ID
            actor: The user making the request

        Returns:
            World Info entry

        Raises:
            NoResultFound: If entry not found or doesn't belong to actor's organization
        """
        async with db_registry.async_session() as session:
            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise NoResultFound(f"World Info entry '{entry_id}' not found")

            return entry.to_pydantic()

    @enforce_types
    @trace_method
    async def create_entry_async(
        self,
        entry_create: WorldInfoEntryCreate,
        actor: PydanticUser,
    ) -> PydanticWorldInfoEntry:
        """
        Create a new World Info entry.

        Args:
            entry_create: The entry data
            actor: The user creating the entry

        Returns:
            Created World Info entry
        """
        if not actor.organization_id:
            raise ValueError("Actor must have an organization_id")

        async with db_registry.async_session() as session:
            # Create the entry with organization_id from actor
            entry_data = entry_create.model_dump(to_orm=True, exclude_none=True)
            entry_data["organization_id"] = actor.organization_id

            # Create the ORM model
            entry = WorldInfoEntryModel(**entry_data)
            await entry.create_async(session, actor=actor)
            await session.commit()
            return entry.to_pydantic()

    @enforce_types
    @trace_method
    async def update_entry_async(
        self,
        entry_id: str,
        entry_update: WorldInfoEntryUpdate,
        actor: PydanticUser,
    ) -> PydanticWorldInfoEntry:
        """
        Update a World Info entry.

        Args:
            entry_id: The entry ID
            entry_update: The update data
            actor: The user updating the entry

        Returns:
            Updated World Info entry

        Raises:
            NoResultFound: If entry not found or doesn't belong to actor's organization
        """
        async with db_registry.async_session() as session:
            # Retrieve the existing entry
            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise NoResultFound(f"World Info entry '{entry_id}' not found")

            # Update only the fields that are provided
            # exclude_none=False allows clearing optional fields by setting them to None
            update_data = entry_update.model_dump(to_orm=True, exclude_unset=True, exclude_none=False)
            for key, value in update_data.items():
                setattr(entry, key, value)

            # Save the changes
            await entry.update_async(db_session=session, actor=actor, no_commit=True, no_refresh=True)
            await session.commit()
            return entry.to_pydantic()

    @enforce_types
    @trace_method
    async def delete_entry_async(
        self,
        entry_id: str,
        actor: PydanticUser,
    ) -> None:
        """
        Delete a World Info entry (hard delete).

        Args:
            entry_id: The entry ID
            actor: The user deleting the entry

        Raises:
            NoResultFound: If entry not found or doesn't belong to actor's organization
        """
        async with db_registry.async_session() as session:
            # Retrieve the entry to verify it exists and belongs to the organization
            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise NoResultFound(f"World Info entry '{entry_id}' not found")

            # Hard delete the entry
            await entry.hard_delete_async(db_session=session, actor=actor)

    @enforce_types
    @trace_method
    async def get_entries_with_state_async(
        self,
        agent_id: str,
        actor: PydanticUser,
    ) -> List[Dict[str, Any]]:
        """
        Get World Info entries for an agent with their current injection state.

        This method combines entries with their runtime state (cooldown/expiration counters)
        for efficient polling by frontends.

        Args:
            agent_id: The agent ID
            actor: The user making the request

        Returns:
            List of dicts with 'entry' (PydanticWorldInfoEntry) and 'state' (WorldInfoEntryState or None) keys.
            State is None if entry is not currently active.
        """
        # Get all entries for the agent (agent-specific + global)
        entries = await self.list_entries_async(actor=actor, agent_id=agent_id, enabled=None)

        # Get all injection states for this agent
        state_manager = WorldInfoInjectionStateManager()
        states = await state_manager.get_injection_states_by_agent(agent_id)

        # Create a map of entry_id -> state for quick lookup
        state_by_entry_id = {state.world_info_entry_id: state for state in states}

        # Combine entries with their states
        result = []
        for entry in entries:
            state = state_by_entry_id.get(entry.id)
            if state:
                entry_state = WorldInfoEntryState(
                    current_cooldown=state.current_cooldown,
                    current_expiration=state.current_expiration,
                    is_active=True,
                    cooldown_setting=state.cooldown_setting,
                    expiration_setting=state.expiration_setting,
                )
            else:
                entry_state = None

            result.append({
                "entry": entry,
                "state": entry_state,
            })

        return result

