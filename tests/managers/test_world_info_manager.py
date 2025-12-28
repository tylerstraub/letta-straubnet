"""
Tests for WorldInfoManager.

Tests the manager methods directly following Letta patterns.
"""

import pytest

from letta.orm.errors import NoResultFound
from letta.schemas.world_info_entry import WorldInfoEntry, WorldInfoEntryCreate, WorldInfoEntryUpdate
from letta.server.server import SyncServer


# ======================================================================================================================
# World Info Manager Tests - CRUD Operations
# ======================================================================================================================


@pytest.mark.asyncio
async def test_list_entries(server: SyncServer, default_user, sarah_agent):
    """Test listing World Info entries."""
    # Create a global entry (agent_id=None)
    global_entry_create = WorldInfoEntryCreate(
        keywords=["global", "test"],
        content="Global test content",
        insertion_order=100,
        enabled=True,
        agent_id=None,  # Global entry
    )
    global_entry = await server.world_info_manager.create_entry_async(entry_create=global_entry_create, actor=default_user)

    # Create an agent-specific entry
    agent_entry_create = WorldInfoEntryCreate(
        keywords=["agent", "test"],
        content="Agent test content",
        insertion_order=100,
        enabled=True,
        agent_id=sarah_agent.id,
    )
    agent_entry = await server.world_info_manager.create_entry_async(entry_create=agent_entry_create, actor=default_user)

    # List all entries (should only return global entries when agent_id is not provided)
    all_entries = await server.world_info_manager.list_entries_async(actor=default_user)
    assert len(all_entries) == 1
    assert all_entries[0].id == global_entry.id
    assert all_entries[0].agent_id is None

    # List entries for specific agent (should include global + agent-specific)
    agent_entries = await server.world_info_manager.list_entries_async(agent_id=sarah_agent.id, actor=default_user)
    assert len(agent_entries) == 2
    agent_entry_ids = {e.id for e in agent_entries}
    assert global_entry.id in agent_entry_ids
    assert agent_entry.id in agent_entry_ids

    # List entries for non-existent agent (should still return global entries)
    entries_for_nonexistent = await server.world_info_manager.list_entries_async(agent_id="non-existent", actor=default_user)
    assert len(entries_for_nonexistent) == 1  # Only global entry, no agent-specific entry for non-existent agent
    assert entries_for_nonexistent[0].id == global_entry.id

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=global_entry.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=agent_entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_list_entries_with_filters(server: SyncServer, default_user, sarah_agent):
    """Test listing entries with enabled filter."""
    # Create enabled entry
    enabled_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["enabled"],
            content="Enabled content",
            enabled=True,
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # Create disabled entry
    disabled_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["disabled"],
            content="Disabled content",
            enabled=False,
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # List all entries (should include both)
    all_entries = await server.world_info_manager.list_entries_async(agent_id=sarah_agent.id, actor=default_user)
    assert len(all_entries) == 2

    # List only enabled entries
    enabled_entries = await server.world_info_manager.list_entries_async(
        agent_id=sarah_agent.id, enabled=True, actor=default_user
    )
    assert len(enabled_entries) == 1
    assert enabled_entries[0].id == enabled_entry.id

    # List only disabled entries
    disabled_entries = await server.world_info_manager.list_entries_async(
        agent_id=sarah_agent.id, enabled=False, actor=default_user
    )
    assert len(disabled_entries) == 1
    assert disabled_entries[0].id == disabled_entry.id

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=enabled_entry.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=disabled_entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_create_entry(server: SyncServer, default_user, sarah_agent):
    """Test creating a World Info entry."""
    entry_create = WorldInfoEntryCreate(
        keywords=["create", "test"],
        content="Create test content",
        insertion_order=50,
        enabled=True,
        agent_id=sarah_agent.id,
        case_sensitive=False,
        match_whole_words=True,
        cooldown=5,
        expiration=10,
        label="Test Entry",
    )

    entry = await server.world_info_manager.create_entry_async(entry_create=entry_create, actor=default_user)

    assert entry.id is not None
    assert entry.id.startswith("world-info-entry-")
    assert entry.keywords == ["create", "test"]
    assert entry.content == "Create test content"
    assert entry.insertion_order == 50
    assert entry.enabled is True
    assert entry.agent_id == sarah_agent.id
    assert entry.organization_id == default_user.organization_id
    assert entry.case_sensitive is False
    assert entry.match_whole_words is True
    assert entry.cooldown == 5
    assert entry.expiration == 10
    assert entry.label == "Test Entry"

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_create_global_entry(server: SyncServer, default_user):
    """Test creating a global entry (no agent_id)."""
    entry_create = WorldInfoEntryCreate(
        keywords=["global"],
        content="Global entry content",
        agent_id=None,  # Global entry
    )

    entry = await server.world_info_manager.create_entry_async(entry_create=entry_create, actor=default_user)

    assert entry.agent_id is None
    assert entry.organization_id == default_user.organization_id
    assert entry.label is None  # Label is optional, should be None if not provided

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_create_entry_without_label(server: SyncServer, default_user, sarah_agent):
    """Test creating an entry without label (optional field)."""
    entry_create = WorldInfoEntryCreate(
        keywords=["no-label"],
        content="Entry without label",
        agent_id=sarah_agent.id,
    )

    entry = await server.world_info_manager.create_entry_async(entry_create=entry_create, actor=default_user)

    assert entry.label is None  # Label should be None when not provided

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_update_entry_label(server: SyncServer, default_user, sarah_agent):
    """Test updating an entry's label."""
    # Create entry without label
    created_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["label-test"],
            content="Label test content",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    assert created_entry.label is None

    # Update to add label
    entry_update = WorldInfoEntryUpdate(label="New Label")
    updated_entry = await server.world_info_manager.update_entry_async(
        entry_id=created_entry.id, entry_update=entry_update, actor=default_user
    )

    assert updated_entry.label == "New Label"

    # Update to change label
    entry_update2 = WorldInfoEntryUpdate(label="Changed Label")
    updated_entry2 = await server.world_info_manager.update_entry_async(
        entry_id=created_entry.id, entry_update=entry_update2, actor=default_user
    )

    assert updated_entry2.label == "Changed Label"

    # Update to clear label (set to None)
    entry_update3 = WorldInfoEntryUpdate(label=None)
    updated_entry3 = await server.world_info_manager.update_entry_async(
        entry_id=created_entry.id, entry_update=entry_update3, actor=default_user
    )

    assert updated_entry3.label is None

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=created_entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_get_entry(server: SyncServer, default_user, sarah_agent):
    """Test retrieving a specific entry."""
    # Create entry
    created_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["get", "test"],
            content="Get test content",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # Retrieve it
    retrieved_entry = await server.world_info_manager.get_entry_async(entry_id=created_entry.id, actor=default_user)

    assert retrieved_entry.id == created_entry.id
    assert retrieved_entry.keywords == ["get", "test"]
    assert retrieved_entry.content == "Get test content"

    # Try to get non-existent entry
    with pytest.raises(NoResultFound):
        await server.world_info_manager.get_entry_async(entry_id="non-existent", actor=default_user)

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=created_entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_update_entry(server: SyncServer, default_user, sarah_agent):
    """Test updating an entry."""
    # Create entry
    created_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["update", "test"],
            content="Original content",
            insertion_order=100,
            enabled=True,
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # Update entry
    entry_update = WorldInfoEntryUpdate(
        content="Updated content",
        enabled=False,
        insertion_order=200,
        label="Updated Label",
    )
    updated_entry = await server.world_info_manager.update_entry_async(
        entry_id=created_entry.id, entry_update=entry_update, actor=default_user
    )

    assert updated_entry.id == created_entry.id
    assert updated_entry.content == "Updated content"
    assert updated_entry.enabled is False
    assert updated_entry.insertion_order == 200
    assert updated_entry.label == "Updated Label"
    # Keywords should remain unchanged
    assert updated_entry.keywords == ["update", "test"]

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=created_entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_delete_entry(server: SyncServer, default_user, sarah_agent):
    """Test deleting an entry."""
    # Create entry
    created_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["delete", "test"],
            content="Delete test content",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    entry_id = created_entry.id

    # Delete it
    await server.world_info_manager.delete_entry_async(entry_id=entry_id, actor=default_user)

    # Verify it's gone
    with pytest.raises(NoResultFound):
        await server.world_info_manager.get_entry_async(entry_id=entry_id, actor=default_user)


@pytest.mark.asyncio
async def test_agent_scoping(server: SyncServer, default_user, sarah_agent, charles_agent):
    """Test that agent-specific and global entries work correctly."""
    # Create global entry
    global_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["global"],
            content="Global entry",
            agent_id=None,
        ),
        actor=default_user,
    )

    # Create agent-specific entry for sarah_agent
    sarah_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["sarah"],
            content="Sarah entry",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # Create agent-specific entry for charles_agent
    charles_entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["charles"],
            content="Charles entry",
            agent_id=charles_agent.id,
        ),
        actor=default_user,
    )

    # List entries for sarah_agent (should include global + sarah-specific)
    sarah_entries = await server.world_info_manager.list_entries_async(agent_id=sarah_agent.id, actor=default_user)
    sarah_entry_ids = {e.id for e in sarah_entries}
    assert global_entry.id in sarah_entry_ids
    assert sarah_entry.id in sarah_entry_ids
    assert charles_entry.id not in sarah_entry_ids

    # List entries for charles_agent (should include global + charles-specific)
    charles_entries = await server.world_info_manager.list_entries_async(agent_id=charles_agent.id, actor=default_user)
    charles_entry_ids = {e.id for e in charles_entries}
    assert global_entry.id in charles_entry_ids
    assert charles_entry.id in charles_entry_ids
    assert sarah_entry.id not in charles_entry_ids

    # List global entries only (should only include global)
    global_entries = await server.world_info_manager.list_entries_async(actor=default_user)
    global_entry_ids = {e.id for e in global_entries}
    assert global_entry.id in global_entry_ids
    assert sarah_entry.id not in global_entry_ids
    assert charles_entry.id not in global_entry_ids

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=global_entry.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=sarah_entry.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=charles_entry.id, actor=default_user)


# ======================================================================================================================
# World Info Manager Tests - State Operations
# ======================================================================================================================


@pytest.mark.asyncio
async def test_get_entries_with_state_no_states(server: SyncServer, default_user, sarah_agent):
    """Test getting entries with state when no injection states exist."""
    # Create an entry
    entry = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test"],
            content="Test content",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    # Get entries with state (no states exist yet)
    entries_with_state = await server.world_info_manager.get_entries_with_state_async(
        agent_id=sarah_agent.id, actor=default_user
    )

    assert len(entries_with_state) == 1
    assert entries_with_state[0]["entry"].id == entry.id
    assert entries_with_state[0]["state"] is None  # No state because entry hasn't been injected yet

    # Cleanup
    await server.world_info_manager.delete_entry_async(entry_id=entry.id, actor=default_user)


@pytest.mark.asyncio
async def test_get_entries_with_state_with_active_states(
    server: SyncServer, default_user, sarah_agent
):
    """Test getting entries with state when injection states exist."""
    from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager

    # Create entries
    entry1 = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["entry1"],
            content="Entry 1 content",
            agent_id=sarah_agent.id,
            cooldown=5,
            expiration=10,
        ),
        actor=default_user,
    )

    entry2 = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["entry2"],
            content="Entry 2 content",
            agent_id=sarah_agent.id,
            cooldown=3,
            expiration=None,
        ),
        actor=default_user,
    )

    entry3 = await server.world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["entry3"],
            content="Entry 3 content",
            agent_id=sarah_agent.id,
            cooldown=None,
            expiration=None,
        ),
        actor=default_user,
    )

    # Create injection states for entry1 and entry2 (not entry3)
    state_manager = WorldInfoInjectionStateManager()
    state1 = await state_manager.create_injection_state(
        world_info_entry_id=entry1.id,
        agent_id=sarah_agent.id,
        organization_id=default_user.organization_id,
        current_cooldown=3,  # Counted down from 5
        current_expiration=8,  # Counted down from 10
        cooldown_setting=5,
        expiration_setting=10,
    )

    state2 = await state_manager.create_injection_state(
        world_info_entry_id=entry2.id,
        agent_id=sarah_agent.id,
        organization_id=default_user.organization_id,
        current_cooldown=1,  # Counted down from 3
        current_expiration=None,  # No expiration
        cooldown_setting=3,
        expiration_setting=0,
    )

    # Get entries with state
    entries_with_state = await server.world_info_manager.get_entries_with_state_async(
        agent_id=sarah_agent.id, actor=default_user
    )

    assert len(entries_with_state) == 3

    # Find entries by ID
    entry1_data = next(e for e in entries_with_state if e["entry"].id == entry1.id)
    entry2_data = next(e for e in entries_with_state if e["entry"].id == entry2.id)
    entry3_data = next(e for e in entries_with_state if e["entry"].id == entry3.id)

    # Entry1 has active state
    assert entry1_data["state"] is not None
    assert entry1_data["state"].current_cooldown == 3
    assert entry1_data["state"].current_expiration == 8
    assert entry1_data["state"].is_active is True
    assert entry1_data["state"].cooldown_setting == 5
    assert entry1_data["state"].expiration_setting == 10

    # Entry2 has active state
    assert entry2_data["state"] is not None
    assert entry2_data["state"].current_cooldown == 1
    assert entry2_data["state"].current_expiration is None
    assert entry2_data["state"].is_active is True
    assert entry2_data["state"].cooldown_setting == 3
    assert entry2_data["state"].expiration_setting == 0

    # Entry3 has no state (not injected yet)
    assert entry3_data["state"] is None

    # Cleanup
    await state_manager.delete_injection_state(state1.id)
    await state_manager.delete_injection_state(state2.id)
    await server.world_info_manager.delete_entry_async(entry_id=entry1.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=entry2.id, actor=default_user)
    await server.world_info_manager.delete_entry_async(entry_id=entry3.id, actor=default_user)

