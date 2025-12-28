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
from letta.schemas.world_info_entry_state import WorldInfoEntriesStateResponse, WorldInfoEntryWithState
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
    return await server.world_info_manager.create_entry_async(entry_create=request, actor=actor)


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
    Entries are ordered by insertion_order ASC (lower values first, higher values last).
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)
    return await server.world_info_manager.list_entries_async(actor=actor, agent_id=agent_id, enabled=enabled)


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
        return await server.world_info_manager.get_entry_async(entry_id=entry_id, actor=actor)
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
        return await server.world_info_manager.update_entry_async(
            entry_id=entry_id, entry_update=request, actor=actor
        )
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
        await server.world_info_manager.delete_entry_async(entry_id=entry_id, actor=actor)
    except NoResultFound:
        raise HTTPException(status_code=404, detail=f"World Info entry '{entry_id}' not found")


@router.get(
    "/agent/{agent_id}/state",
    response_model=WorldInfoEntriesStateResponse,
    operation_id="get_world_info_entries_state",
)
async def get_world_info_entries_state(
    agent_id: str,
    server: SyncServer = Depends(get_letta_server),
    headers: HeaderParams = Depends(get_headers),
):
    """
    Get World Info entries for an agent with their current runtime state.

    This endpoint is optimized for frequent polling by frontends to track which entries
    are currently active and their cooldown/expiration counters.

    Returns all entries applicable to the agent (agent-specific + global) along with
    their current injection state (cooldown/expiration counters).
    """
    actor = await server.user_manager.get_actor_or_default_async(actor_id=headers.actor_id)

    entries_with_state = await server.world_info_manager.get_entries_with_state_async(
        agent_id=agent_id, actor=actor
    )

    # Convert dict format to schema format
    result_entries = [
        WorldInfoEntryWithState(entry=item["entry"], state=item["state"])
        for item in entries_with_state
    ]

    return WorldInfoEntriesStateResponse(entries=result_entries)
