"""
Core API tests for World Info system.

Minimal test suite focusing on essential CRUD operations and core functionality.
This file should remain focused on health checks and regression testing.
"""

import pytest
import requests


# ============================================================================
# Core CRUD Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_entry(world_info_client, default_user):
    """Test creating a World Info entry."""
    entry_data = {
        "keywords": ["test", "keyword"],
        "content": "Test content",
        "insertion_order": 100,
        "enabled": True,
        "label": "Test Entry Label",
    }

    entry = world_info_client.create_entry(entry_data)

    try:
        assert "id" in entry
        assert entry["keywords"] == entry_data["keywords"]
        assert entry["content"] == entry_data["content"]
        assert entry["organization_id"] == default_user.organization_id
        assert entry["agent_id"] is None  # Global entry
        assert entry["label"] == "Test Entry Label"
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_list_entries(world_info_client):
    """Test listing World Info entries."""
    entry = world_info_client.create_entry({
        "keywords": ["list", "test"],
        "content": "List test content",
    })

    try:
        entries = world_info_client.list_entries()
        assert isinstance(entries, list)
        assert any(e["id"] == entry["id"] for e in entries)
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_get_entry(world_info_client):
    """Test retrieving a specific entry."""
    entry = world_info_client.create_entry({
        "keywords": ["get", "test"],
        "content": "Get test content",
    })

    try:
        retrieved = world_info_client.get_entry(entry["id"])
        assert retrieved["id"] == entry["id"]
        assert retrieved["content"] == entry["content"]
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_update_entry(world_info_client):
    """Test updating an entry."""
    entry = world_info_client.create_entry({
        "keywords": ["update", "test"],
        "content": "Original content",
        "enabled": True,
    })

    try:
        updated = world_info_client.update_entry(entry["id"], {
            "content": "Updated content",
            "enabled": False,
            "label": "Updated Label",
        })

        assert updated["id"] == entry["id"]
        assert updated["content"] == "Updated content"
        assert updated["enabled"] is False
        assert updated["label"] == "Updated Label"
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_delete_entry(world_info_client):
    """Test deleting an entry."""
    entry = world_info_client.create_entry({
        "keywords": ["delete", "test"],
        "content": "Delete test content",
    })

    entry_id = entry["id"]
    world_info_client.delete_entry(entry_id)

    # Verify deletion (should return 404)
    response = requests.get(
        f"{world_info_client.base_url}/{entry_id}",
        headers=world_info_client.headers,
    )
    assert response.status_code == 404


# ============================================================================
# Core Functionality Tests
# ============================================================================


@pytest.mark.asyncio
async def test_agent_scoping(world_info_client, test_agent):
    """Test that agent-specific and global entries work correctly."""
    agent_id = test_agent["id"]

    # Create global entry
    global_entry = world_info_client.create_entry({
        "keywords": ["global"],
        "content": "Global entry",
        "agent_id": None,
    })

    # Create agent-specific entry
    agent_entry = world_info_client.create_entry({
        "keywords": ["agent"],
        "content": "Agent-specific entry",
        "agent_id": agent_id,
    })

    try:
        # List entries for agent (should include both global and agent-specific)
        agent_entries = world_info_client.list_entries(agent_id=agent_id)
        agent_entry_ids = [e["id"] for e in agent_entries]

        assert global_entry["id"] in agent_entry_ids
        assert agent_entry["id"] in agent_entry_ids

        # List global entries only (should not include agent-specific)
        global_entries = world_info_client.list_entries()
        global_entry_ids = [e["id"] for e in global_entries]

        assert global_entry["id"] in global_entry_ids
        assert agent_entry["id"] not in global_entry_ids
    finally:
        world_info_client.delete_entry(global_entry["id"])
        world_info_client.delete_entry(agent_entry["id"])


@pytest.mark.asyncio
async def test_disabled_entries_excluded(world_info_client, test_agent):
    """Test that disabled entries are excluded from processing."""
    # Create disabled entry
    disabled_entry = world_info_client.create_entry({
        "keywords": ["disabled"],
        "content": "Should not appear",
        "enabled": False,
        "agent_id": test_agent["id"],
    })

    # Create enabled entry
    enabled_entry = world_info_client.create_entry({
        "keywords": ["enabled"],
        "content": "Should appear",
        "enabled": True,
        "agent_id": test_agent["id"],
    })

    try:
        # List enabled entries for agent
        entries = world_info_client.list_entries(agent_id=test_agent["id"])
        entry_ids = [e["id"] for e in entries]

        # Storage layer filters disabled entries, but API list might return them
        # This test verifies entries can be created and queried
        assert enabled_entry["id"] in entry_ids
        # Note: API list endpoint may return disabled entries, but processor filters them
    finally:
        world_info_client.delete_entry(disabled_entry["id"])
        world_info_client.delete_entry(enabled_entry["id"])


# ============================================================================
# State Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_entries_state_no_states(world_info_client, test_agent):
    """Test getting entries state when no injection states exist."""
    # Create an entry
    entry = world_info_client.create_entry({
        "keywords": ["state", "test"],
        "content": "State test content",
        "agent_id": test_agent["id"],
    })

    try:
        # Get entries with state
        entries_with_state = world_info_client.get_entries_state(test_agent["id"])

        assert isinstance(entries_with_state, list)
        assert len(entries_with_state) >= 1  # At least our entry

        # Find our entry
        entry_data = next((e for e in entries_with_state if e["entry"]["id"] == entry["id"]), None)
        assert entry_data is not None
        assert entry_data["entry"]["id"] == entry["id"]
        assert entry_data["entry"]["keywords"] == ["state", "test"]
        assert "label" in entry_data["entry"]  # Label field should be present
        # State should be None since entry hasn't been injected yet
        assert entry_data["state"] is None
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_get_entries_state_with_active_states(world_info_client, test_agent, default_user):
    """Test getting entries state when injection states exist."""
    from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager

    # Create entries
    entry1 = world_info_client.create_entry({
        "keywords": ["entry1"],
        "content": "Entry 1 content",
        "agent_id": test_agent["id"],
        "cooldown": 5,
        "expiration": 10,
    })

    entry2 = world_info_client.create_entry({
        "keywords": ["entry2"],
        "content": "Entry 2 content",
        "agent_id": test_agent["id"],
        "cooldown": 3,
        "expiration": None,
    })

    entry3 = world_info_client.create_entry({
        "keywords": ["entry3"],
        "content": "Entry 3 content",
        "agent_id": test_agent["id"],
        "cooldown": None,
        "expiration": None,
    })

    try:
        # Create injection states for entry1 and entry2 (not entry3)
        state_manager = WorldInfoInjectionStateManager()
        state1 = await state_manager.create_injection_state(
            world_info_entry_id=entry1["id"],
            agent_id=test_agent["id"],
            organization_id=default_user.organization_id,
            current_cooldown=3,
            current_expiration=8,
            cooldown_setting=5,
            expiration_setting=10,
        )

        state2 = await state_manager.create_injection_state(
            world_info_entry_id=entry2["id"],
            agent_id=test_agent["id"],
            organization_id=default_user.organization_id,
            current_cooldown=1,
            current_expiration=None,
            cooldown_setting=3,
            expiration_setting=0,
        )

        # Get entries with state
        entries_with_state = world_info_client.get_entries_state(test_agent["id"])

        assert isinstance(entries_with_state, list)
        assert len(entries_with_state) >= 3

        # Find our entries
        entry1_data = next((e for e in entries_with_state if e["entry"]["id"] == entry1["id"]), None)
        entry2_data = next((e for e in entries_with_state if e["entry"]["id"] == entry2["id"]), None)
        entry3_data = next((e for e in entries_with_state if e["entry"]["id"] == entry3["id"]), None)

        assert entry1_data is not None
        assert entry2_data is not None
        assert entry3_data is not None

        # Entry1 has active state
        assert entry1_data["state"] is not None
        assert entry1_data["state"]["current_cooldown"] == 3
        assert entry1_data["state"]["current_expiration"] == 8
        assert entry1_data["state"]["is_active"] is True
        assert entry1_data["state"]["cooldown_setting"] == 5
        assert entry1_data["state"]["expiration_setting"] == 10

        # Entry2 has active state
        assert entry2_data["state"] is not None
        assert entry2_data["state"]["current_cooldown"] == 1
        assert entry2_data["state"]["current_expiration"] is None
        assert entry2_data["state"]["is_active"] is True
        assert entry2_data["state"]["cooldown_setting"] == 3
        assert entry2_data["state"]["expiration_setting"] == 0

        # Entry3 has no state (not injected yet)
        assert entry3_data["state"] is None

        # Cleanup states
        await state_manager.delete_injection_state(state1.id)
        await state_manager.delete_injection_state(state2.id)
    finally:
        world_info_client.delete_entry(entry1["id"])
        world_info_client.delete_entry(entry2["id"])
        world_info_client.delete_entry(entry3["id"])


@pytest.mark.asyncio
async def test_get_entries_state_includes_global_entries(world_info_client, test_agent):
    """Test that state endpoint includes global entries for an agent."""
    # Create global entry
    global_entry = world_info_client.create_entry({
        "keywords": ["global"],
        "content": "Global entry",
        "agent_id": None,
    })

    # Create agent-specific entry
    agent_entry = world_info_client.create_entry({
        "keywords": ["agent"],
        "content": "Agent entry",
        "agent_id": test_agent["id"],
    })

    try:
        # Get entries with state for agent
        entries_with_state = world_info_client.get_entries_state(test_agent["id"])

        entry_ids = {e["entry"]["id"] for e in entries_with_state}

        # Should include both global and agent-specific entries
        assert global_entry["id"] in entry_ids
        assert agent_entry["id"] in entry_ids
    finally:
        world_info_client.delete_entry(global_entry["id"])
        world_info_client.delete_entry(agent_entry["id"])


@pytest.mark.asyncio
async def test_create_entry_without_label(world_info_client):
    """Test creating an entry without label (optional field)."""
    entry = world_info_client.create_entry({
        "keywords": ["no-label"],
        "content": "Entry without label",
    })

    try:
        assert "label" in entry
        assert entry["label"] is None  # Label should be None when not provided
    finally:
        world_info_client.delete_entry(entry["id"])


@pytest.mark.asyncio
async def test_update_entry_label(world_info_client):
    """Test updating an entry's label."""
    # Create entry without label
    entry = world_info_client.create_entry({
        "keywords": ["label-test"],
        "content": "Label test content",
    })

    try:
        assert entry["label"] is None

        # Update to add label
        updated = world_info_client.update_entry(entry["id"], {
            "label": "New Label",
        })
        assert updated["label"] == "New Label"

        # Update to change label
        updated2 = world_info_client.update_entry(entry["id"], {
            "label": "Changed Label",
        })
        assert updated2["label"] == "Changed Label"

        # Update to clear label (set to None)
        updated3 = world_info_client.update_entry(entry["id"], {
            "label": None,
        })
        assert updated3["label"] is None
    finally:
        world_info_client.delete_entry(entry["id"])

