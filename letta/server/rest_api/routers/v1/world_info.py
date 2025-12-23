"""
REST API endpoints for World Info entries.

World Info entries enable keyword-based prompt injection,
similar to SillyTavern's World Info / Lorebook system.
"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from letta.orm.errors import NoResultFound
from letta.schemas.world_info_entry import (
    WorldInfoEntry,
    WorldInfoEntryCreate,
    WorldInfoEntryUpdate,
)
from sqlalchemy import or_, select

from letta.server.db import db_registry
from letta.server.rest_api.dependencies import HeaderParams, get_headers, get_letta_server
from letta.server.server import SyncServer

router = APIRouter(prefix="/world-info", tags=["world-info"])


@router.post(
    "/",
    response_model=WorldInfoEntry,
    operation_id="create_world_info_entry",
)
async def create_world_info_entry(
    request: WorldInfoEntryCreate = Body(...),
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    Create a new World Info entry.

    The entry will be associated with the actor's organization.
    If agent_id is provided, the entry will be agent-specific.
    If agent_id is None, the entry will apply globally to all agents in the organization.
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    if not actor.organization_id:
        raise HTTPException(status_code=400, detail="Actor must have an organization_id")

    async with db_registry.async_session() as session:
        # Create the entry with organization_id from actor
        entry_data = request.model_dump(to_orm=True, exclude_none=True)
        entry_data["organization_id"] = actor.organization_id

        # Create the ORM model
        from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel

        entry = WorldInfoEntryModel(**entry_data)
        await entry.create_async(session, actor=actor)
        pydantic_entry = entry.to_pydantic()
        await session.commit()
        return pydantic_entry


@router.get(
    "/",
    response_model=List[WorldInfoEntry],
    operation_id="list_world_info_entries",
)
async def list_world_info_entries(
    agent_id: Optional[str] = Query(
        None,
        description="Filter entries by agent ID. If None, returns only global entries. If provided, returns agent-specific entries plus global entries.",
    ),
    enabled: Optional[bool] = Query(
        None,
        description="Filter entries by enabled status. If None, returns both enabled and disabled entries.",
    ),
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    List World Info entries for the actor's organization.

    Returns entries that belong to the actor's organization, optionally filtered by agent_id and enabled status.
    Entries are ordered by insertion_order DESC (higher priority first).
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    if not actor.organization_id:
        raise HTTPException(status_code=400, detail="Actor must have an organization_id")

    async with db_registry.async_session() as session:
        from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel

        # Build the query
        query = select(WorldInfoEntryModel).where(
            WorldInfoEntryModel.organization_id == actor.organization_id,
        )

        # Filter by enabled status if specified
        if enabled is not None:
            query = query.where(WorldInfoEntryModel.enabled == enabled)

        # Filter by is_deleted if the field exists (soft-delete support)
        if hasattr(WorldInfoEntryModel, "is_deleted"):
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

        # Order by insertion_order DESC (higher numbers = higher priority = inserted later)
        query = query.order_by(WorldInfoEntryModel.insertion_order.desc())

        # Execute query
        result = await session.execute(query)
        entries = result.scalars().all()

        # Convert to Pydantic models
        return [entry.to_pydantic() for entry in entries]


@router.get(
    "/{entry_id}",
    response_model=WorldInfoEntry,
    operation_id="retrieve_world_info_entry",
)
async def retrieve_world_info_entry(
    entry_id: str,
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    Retrieve a specific World Info entry by its ID.

    The entry must belong to the actor's organization.
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    try:
        async with db_registry.async_session() as session:
            from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel

            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise HTTPException(
                    status_code=403,
                    detail="Entry does not belong to your organization",
                )

            return entry.to_pydantic()
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"World Info entry '{entry_id}' not found")


@router.patch(
    "/{entry_id}",
    response_model=WorldInfoEntry,
    operation_id="update_world_info_entry",
)
async def update_world_info_entry(
    entry_id: str,
    request: WorldInfoEntryUpdate = Body(...),
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    Update an existing World Info entry.

    Only the fields provided in the request will be updated.
    The entry must belong to the actor's organization.
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    try:
        async with db_registry.async_session() as session:
            from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel

            # Retrieve the existing entry
            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise HTTPException(
                    status_code=403,
                    detail="Entry does not belong to your organization",
                )

            # Update only the fields that are provided
            update_data = request.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(entry, key, value)

            # Save the changes
            await entry.update_async(db_session=session, actor=actor, no_commit=True, no_refresh=True)
            pydantic_entry = entry.to_pydantic()
            await session.commit()
            return pydantic_entry
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"World Info entry '{entry_id}' not found")


@router.delete(
    "/{entry_id}",
    status_code=204,
    operation_id="delete_world_info_entry",
)
async def delete_world_info_entry(
    entry_id: str,
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    Delete a World Info entry by its ID.

    The entry must belong to the actor's organization.
    This is a hard delete - the entry will be permanently removed from the database.
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    try:
        async with db_registry.async_session() as session:
            from letta.orm.world_info_entry import WorldInfoEntry as WorldInfoEntryModel

            # Retrieve the entry to verify it exists and belongs to the organization
            entry = await WorldInfoEntryModel.read_async(
                db_session=session,
                identifier=entry_id,
                actor=actor,
            )

            # Verify the entry belongs to the actor's organization
            if entry.organization_id != actor.organization_id:
                raise HTTPException(
                    status_code=403,
                    detail="Entry does not belong to your organization",
                )

            # Hard delete the entry
            await entry.hard_delete_async(db_session=session, actor=actor)
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"World Info entry '{entry_id}' not found")

