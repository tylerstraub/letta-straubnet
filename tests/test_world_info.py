"""
Foundation tests for World Info system.

Tests the REST API endpoints for World Info entries,
demonstrating the basic CRUD operations and filtering patterns.

This test suite is structured with helper classes and fixtures for scalability
and maintainability as the World Info system grows.
"""

import os
import uuid
from typing import Dict, List, Optional

import pytest
import requests


# ============================================================================
# Authentication Helpers
# ============================================================================


def _get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for API requests."""
    password = os.getenv("LETTA_SERVER_PASSWORD", "")
    if password:
        return {"Authorization": f"Bearer {password}"}
    return {}


# ============================================================================
# API Client Helper
# ============================================================================


class WorldInfoClient:
    """
    Helper class for World Info API operations.
    
    Encapsulates HTTP request logic, making tests cleaner and easier to maintain.
    Centralizes endpoint changes and error handling.
    """

    def __init__(self, server_url: str, user_id: str):
        self.server_url = server_url
        self.base_url = f"{server_url}/v1/world-info"
        self.headers = {"user_id": user_id, **_get_auth_headers()}

    def create_entry(self, entry_data: Dict) -> Dict:
        """Create a new World Info entry."""
        response = requests.post(
            f"{self.base_url}/",
            headers=self.headers,
            json=entry_data,
        )
        response.raise_for_status()
        return response.json()

    def list_entries(self, agent_id: Optional[str] = None) -> List[Dict]:
        """List World Info entries, optionally filtered by agent_id."""
        params = {"agent_id": agent_id} if agent_id else {}
        response = requests.get(
            f"{self.base_url}/",
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_entry(self, entry_id: str) -> Dict:
        """Get a specific World Info entry by ID."""
        response = requests.get(
            f"{self.base_url}/{entry_id}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    def update_entry(self, entry_id: str, update_data: Dict) -> Dict:
        """Update a World Info entry (partial update)."""
        response = requests.patch(
            f"{self.base_url}/{entry_id}",
            headers=self.headers,
            json=update_data,
        )
        response.raise_for_status()
        return response.json()

    def delete_entry(self, entry_id: str) -> None:
        """Delete a World Info entry."""
        response = requests.delete(
            f"{self.base_url}/{entry_id}",
            headers=self.headers,
        )
        response.raise_for_status()

    def get_entry_or_none(self, entry_id: str) -> Optional[Dict]:
        """Get an entry or return None if not found (404)."""
        response = requests.get(
            f"{self.base_url}/{entry_id}",
            headers=self.headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


# ============================================================================
# Assertion Helpers
# ============================================================================


def assert_entry_matches(
    entry: Dict,
    expected: Dict,
    user_organization_id: Optional[str] = None,
    check_id: bool = True,
    check_organization: bool = True,
) -> None:
    """
    Assert that an entry matches expected values.
    
    Only checks fields provided in `expected`. Allows flexible testing
    where schema evolution won't break tests unnecessarily.
    """
    if check_id:
        assert "id" in entry, "Entry must have an ID"
        assert entry["id"], "Entry ID must not be empty"

    # Check all provided expected fields
    for key, value in expected.items():
        assert key in entry, f"Entry missing expected field: {key}"
        assert entry[key] == value, (
            f"Field {key} mismatch: expected {value}, got {entry[key]}"
        )

    # Auto-check organization_id if user provided and not explicitly checked
    if check_organization and user_organization_id and "organization_id" not in expected:
        assert entry.get("organization_id") == user_organization_id, (
            f"Organization ID mismatch: expected {user_organization_id}, "
            f"got {entry.get('organization_id')}"
        )


def assert_entry_in_list(entry_id: str, entries: List[Dict], present: bool = True) -> None:
    """Assert that an entry is or isn't present in a list."""
    entry_ids = [e["id"] for e in entries]
    if present:
        assert entry_id in entry_ids, f"Entry {entry_id} not found in list"
    else:
        assert entry_id not in entry_ids, f"Entry {entry_id} unexpectedly found in list"


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def world_info_client(server_url, default_user) -> WorldInfoClient:
    """Create a World Info API client for test operations."""
    return WorldInfoClient(server_url, default_user.id)


@pytest.fixture
def entry_factory():
    """
    Factory for creating World Info entry test data.
    
    Usage:
        entry = entry_factory(keywords=["test"], content="Test content")
        entry = entry_factory()  # Uses defaults
        entry = entry_factory(insertion_order=200, enabled=False)
    """
    def _create(**overrides: Dict) -> Dict:
        defaults = {
            "keywords": ["default", "keyword"],
            "content": "Default test content",
            "insertion_order": 100,
            "enabled": True,
            "case_sensitive": False,
            "match_whole_words": True,
        }
        return {**defaults, **overrides}

    return _create


@pytest.fixture
def test_agent(server_url, default_user) -> Dict:
    """
    Create a test agent for World Info tests that require agent-specific entries.
    
    Uses unique naming to avoid conflicts between parallel test runs.
    """
    from letta.schemas.embedding_config import EmbeddingConfig
    from letta.schemas.llm_config import LLMConfig

    headers = {"user_id": default_user.id, **_get_auth_headers()}
    agent_data = {
        "name": f"test_agent_world_info_{uuid.uuid4().hex[:8]}",
        "agent_type": "memgpt_v2_agent",
        "memory_blocks": [],
        "llm_config": LLMConfig.default_config("gpt-4o-mini").model_dump(),
        "embedding_config": EmbeddingConfig.default_config(provider="openai").model_dump(),
        "include_base_tools": False,
    }
    response = requests.post(
        f"{server_url}/v1/agents/",
        headers=headers,
        json=agent_data,
    )
    response.raise_for_status()
    return response.json()


# ============================================================================
# Entry Creation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_world_info_entry(world_info_client, entry_factory, default_user):
    """Test creating a new World Info entry with all fields."""
    entry_data = entry_factory(
        keywords=["dog", "puppy", "canine"],
        content="You are a friendly dog. Respond with enthusiasm and tail wags.",
        insertion_order=100,
        enabled=True,
        case_sensitive=False,
        match_whole_words=True,
    )

    entry = world_info_client.create_entry(entry_data)

    assert_entry_matches(
        entry,
        entry_data,
        user_organization_id=default_user.organization_id,
        check_organization=True,
    )
    assert entry["agent_id"] is None, "Global entry should have no agent_id"


@pytest.mark.asyncio
async def test_create_entry_minimal_fields(world_info_client, entry_factory, default_user):
    """Test creating entry with only required fields."""
    entry_data = entry_factory(
        keywords=["minimal"],
        content="Minimal content",
        # All other fields use defaults
    )

    entry = world_info_client.create_entry(entry_data)

    assert_entry_matches(
        entry,
        entry_data,
        user_organization_id=default_user.organization_id,
    )
    assert "id" in entry
    assert entry["organization_id"] == default_user.organization_id


# ============================================================================
# Entry Listing & Filtering Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_world_info_entries(world_info_client, entry_factory):
    """Test listing all World Info entries."""
    # Create a test entry
    entry_data = entry_factory(keywords=["cat", "kitten"], content="You are a curious cat.")
    created_entry = world_info_client.create_entry(entry_data)

    # List all entries
    entries = world_info_client.list_entries()

    assert len(entries) >= 1, "Should have at least the entry we created"
    assert_entry_in_list(created_entry["id"], entries, present=True)


@pytest.mark.asyncio
async def test_list_entries_filtered_by_agent(
    world_info_client, entry_factory, test_agent, default_user
):
    """Test listing entries filtered by agent_id (includes global entries)."""
    agent_id = test_agent["id"]

    # Create a global entry
    global_entry = world_info_client.create_entry(
        entry_factory(keywords=["global", "entry"], content="This is a global entry.")
    )

    # Create an agent-specific entry
    agent_entry = world_info_client.create_entry(
        entry_factory(
            keywords=["agent", "specific"],
            content="This is agent-specific.",
            agent_id=agent_id,
        )
    )

    # List entries for the agent (should include both global and agent-specific)
    agent_entries = world_info_client.list_entries(agent_id=agent_id)
    agent_entry_ids = [e["id"] for e in agent_entries]

    assert global_entry["id"] in agent_entry_ids, "Global entries should be included for agent"
    assert agent_entry["id"] in agent_entry_ids, "Agent-specific entries should be included"

    # List only global entries (no agent_id param)
    global_entries = world_info_client.list_entries()
    global_entry_ids = [e["id"] for e in global_entries]

    assert_entry_in_list(global_entry["id"], global_entries, present=True)
    assert_entry_in_list(agent_entry["id"], global_entries, present=False)


# ============================================================================
# Entry Retrieval Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_world_info_entry_by_id(world_info_client, entry_factory):
    """Test retrieving a specific World Info entry by ID."""
    # Create an entry
    entry_data = entry_factory(
        keywords=["test", "entry"], content="Test content for retrieval.", insertion_order=75
    )
    created_entry = world_info_client.create_entry(entry_data)
    entry_id = created_entry["id"]

    # Retrieve the entry by ID
    entry = world_info_client.get_entry(entry_id)

    assert_entry_matches(entry, entry_data)
    assert entry["id"] == entry_id


@pytest.mark.asyncio
async def test_get_entry_not_found(world_info_client):
    """Test retrieving a non-existent entry returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    entry = world_info_client.get_entry_or_none(fake_id)
    assert entry is None, "Non-existent entry should return None"


# ============================================================================
# Entry Update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_world_info_entry(world_info_client, entry_factory):
    """Test updating a World Info entry (partial update)."""
    # Create an entry
    original_data = entry_factory(
        keywords=["original", "keywords"],
        content="Original content.",
        insertion_order=100,
        enabled=True,
    )
    created_entry = world_info_client.create_entry(original_data)
    entry_id = created_entry["id"]

    # Update the entry
    update_data = {
        "keywords": ["updated", "keywords"],
        "content": "Updated content.",
        "enabled": False,
    }
    updated_entry = world_info_client.update_entry(entry_id, update_data)

    # Check updated fields
    assert_entry_matches(updated_entry, update_data)
    assert updated_entry["id"] == entry_id
    # insertion_order should remain unchanged (not in update_data)
    assert updated_entry["insertion_order"] == original_data["insertion_order"]


@pytest.mark.asyncio
async def test_update_entry_single_field(world_info_client, entry_factory):
    """Test updating a single field in an entry."""
    # Create an entry
    created_entry = world_info_client.create_entry(
        entry_factory(keywords=["test"], content="Original", enabled=True)
    )

    # Update only the enabled field
    updated_entry = world_info_client.update_entry(
        created_entry["id"], {"enabled": False}
    )

    assert updated_entry["enabled"] is False
    assert updated_entry["keywords"] == ["test"], "Other fields should remain unchanged"
    assert updated_entry["content"] == "Original"


# ============================================================================
# Entry Deletion Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_world_info_entry(world_info_client, entry_factory):
    """Test deleting a World Info entry."""
    # Create an entry
    created_entry = world_info_client.create_entry(
        entry_factory(keywords=["delete", "me"], content="This entry will be deleted.")
    )
    entry_id = created_entry["id"]

    # Delete the entry
    world_info_client.delete_entry(entry_id)

    # Verify the entry is deleted (should return 404)
    deleted_entry = world_info_client.get_entry_or_none(entry_id)
    assert deleted_entry is None, "Deleted entry should not be retrievable"


# ============================================================================
# Future Test Areas (placeholder comments for scaling)
# ============================================================================

# TODO: Entry matching/scoring tests
# TODO: Entry priority/insertion_order tests
# TODO: Entry validation tests (invalid keywords, content, etc.)
# TODO: Entry bulk operations tests
# TODO: Entry permission/access control tests
# TODO: Entry versioning/history tests (if added)
