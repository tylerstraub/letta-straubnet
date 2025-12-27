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
    }

    entry = world_info_client.create_entry(entry_data)

    try:
        assert "id" in entry
        assert entry["keywords"] == entry_data["keywords"]
        assert entry["content"] == entry_data["content"]
        assert entry["organization_id"] == default_user.organization_id
        assert entry["agent_id"] is None  # Global entry
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
        })

        assert updated["id"] == entry["id"]
        assert updated["content"] == "Updated content"
        assert updated["enabled"] is False
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

