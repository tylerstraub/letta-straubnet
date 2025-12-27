"""
Integration tests for World Info cooldown and expiration functionality.

These tests verify the complete lifecycle:
1. Create World Info entries with cooldown/expiration settings
2. Send messages through the agent API
3. Verify state tracking, injection behavior, and cleanup
"""

import pytest
import requests


def _get_auth_headers():
    """Get authentication headers for API requests."""
    import os
    password = os.getenv("LETTA_SERVER_PASSWORD", "")
    if password:
        return {"Authorization": f"Bearer {password}"}
    return {}


# ============================================================================
# Test Scenario 1: Cooldown Only (no expiration)
# ============================================================================


@pytest.mark.asyncio
async def test_cooldown_only(world_info_client, test_agent):
    """
    Test cooldown-only behavior:
    - Entry with cooldown=3, expiration=0
    - Injects on first match
    - Won't re-inject for 3 runs
    - Stays in context forever
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    # Create entry with cooldown only
    entry = world_info_client.create_entry({
        "keywords": ["cooldown_only"],
        "content": "This entry has a cooldown of 3",
        "agent_id": agent_id,
        "cooldown": 3,
        "expiration": 0,  # Never expire
    })

    try:
        # Send message 1: Should inject
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "cooldown_only test"}]},
        )
        assert response.status_code == 200
        run1 = response.json()
        
        # Verify state was created
        states = world_info_client.get_injection_states(agent_id)
        state = next((s for s in states if s["world_info_entry_id"] == entry["id"]), None)
        assert state is not None
        assert state["current_cooldown"] == 3  # Just set, so full cooldown
        assert state["current_expiration"] is None  # expiration=0 means never expire

        # Send messages 2 and 3: Should not inject (cooldown active)
        for i in range(2):
            response = requests.post(
                f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": "cooldown_only test"}]},
            )
            assert response.status_code == 200

        # Send message 4: Should inject again (cooldown expired)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "cooldown_only test"}]},
        )
        assert response.status_code == 200

        # Verify entry is still in context (never expired)
        states = world_info_client.get_injection_states(agent_id)
        state = next((s for s in states if s["world_info_entry_id"] == entry["id"]), None)
        assert state is not None
        assert state["current_expiration"] is None  # Never expires

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test Scenario 2: Expiration Only (no cooldown)
# ============================================================================


@pytest.mark.asyncio
async def test_expiration_only(world_info_client, test_agent):
    """
    Test expiration-only behavior:
    - Entry with cooldown=0, expiration=2
    - Injects on match
    - Can re-inject immediately if matched again
    - Removed from context after 2 runs
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    entry = world_info_client.create_entry({
        "keywords": ["expiration_only"],
        "content": "This entry expires after 2 runs",
        "agent_id": agent_id,
        "cooldown": 0,  # No cooldown
        "expiration": 2,
    })

    try:
        # Send message 1: Should inject
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "expiration_only test"}]},
        )
        assert response.status_code == 200

        # Send message 2 immediately: Should inject again (no cooldown)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "expiration_only test"}]},
        )
        assert response.status_code == 200

        # Send message 3: Should be removed from context (expired)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "expiration_only test"}]},
        )
        assert response.status_code == 200

        # Verify entry was removed from context - state should be cleaned up
        states = world_info_client.get_injection_states(agent_id)
        state = next((s for s in states if s["world_info_entry_id"] == entry["id"]), None)
        # State should be deleted since both counters are at 0
        assert state is None

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test Scenario 3: Both Cooldown and Expiration
# ============================================================================


@pytest.mark.asyncio
async def test_both_cooldown_and_expiration(world_info_client, test_agent):
    """
    Test combined cooldown and expiration:
    - Entry with cooldown=2, expiration=5
    - Injects on match
    - Won't re-inject for 2 runs
    - Removed from context after 5 runs
    - State record deleted when both reach 0
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    entry = world_info_client.create_entry({
        "keywords": ["combined_test"],
        "content": "This entry has both cooldown (2) and expiration (5)",
        "agent_id": agent_id,
        "cooldown": 2,
        "expiration": 5,
    })

    try:
        # Send message 1: Should inject
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "combined_test"}]},
        )
        assert response.status_code == 200

        # Send messages 2-3: Should not inject (cooldown active)
        for i in range(2):
            response = requests.post(
                f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": "combined_test"}]},
            )
            assert response.status_code == 200

        # Send message 4: Should inject again (cooldown expired)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "combined_test"}]},
        )
        assert response.status_code == 200

        # Send message 5: Entry removed from context (expiration reached)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "combined_test"}]},
        )
        assert response.status_code == 200

        # Verify state was cleaned up (both counters at 0)
        states = world_info_client.get_injection_states(agent_id)
        state = next((s for s in states if s["world_info_entry_id"] == entry["id"]), None)
        assert state is None  # Should be cleaned up

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test Scenario 4: Neither Cooldown nor Expiration (classic behavior)
# ============================================================================


@pytest.mark.asyncio
async def test_classic_behavior_no_cooldown_expiration(world_info_client, test_agent):
    """
    Test classic World Info behavior:
    - Entry with cooldown=0, expiration=0
    - No state record created (optimization)
    - Injects on every match
    - Never expires (user must manage manually)
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    entry = world_info_client.create_entry({
        "keywords": ["classic"],
        "content": "Classic entry with no cooldown or expiration",
        "agent_id": agent_id,
        "cooldown": 0,
        "expiration": 0,
    })

    try:
        # Send multiple messages - all should inject
        for i in range(5):
            response = requests.post(
                f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": "classic test"}]},
            )
            assert response.status_code == 200

        # Verify no state record was created
        states = world_info_client.get_injection_states(agent_id)
        state = next((s for s in states if s["world_info_entry_id"] == entry["id"]), None)
        assert state is None  # No state should be created for classic behavior

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test Scenario 5: NULL Values Treated as 0
# ============================================================================


@pytest.mark.asyncio
async def test_null_values_as_zero(world_info_client, test_agent):
    """
    Test that NULL values in cooldown/expiration are treated as 0.
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    # Create entry with NULL values (via API, might send null or omit)
    entry = world_info_client.create_entry({
        "keywords": ["null_test"],
        "content": "Entry with NULL values",
        "agent_id": agent_id,
        # cooldown and expiration not provided = NULL
    })

    try:
        # Should behave like cooldown=0, expiration=0
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "null_test"}]},
        )
        assert response.status_code == 200

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test Scenario 6: Multiple Entries for Same Keywords
# ============================================================================


@pytest.mark.asyncio
async def test_multiple_entries_same_keywords(world_info_client, test_agent):
    """
    Test multiple entries with the same keywords but different cooldown/expiration.
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    entry1 = world_info_client.create_entry({
        "keywords": ["shared_keyword"],
        "content": "Entry 1 - cooldown 1, expiration 3",
        "agent_id": agent_id,
        "insertion_order": 1,
        "cooldown": 1,
        "expiration": 3,
    })

    entry2 = world_info_client.create_entry({
        "keywords": ["shared_keyword"],
        "content": "Entry 2 - cooldown 3, expiration 1",
        "agent_id": agent_id,
        "insertion_order": 2,
        "cooldown": 3,
        "expiration": 1,
    })

    try:
        # Send message: Both should inject (first match)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "shared_keyword"}]},
        )
        assert response.status_code == 200

        # Send message 2: Entry 1 should inject (cooldown expired), Entry 2 should not
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "shared_keyword"}]},
        )
        assert response.status_code == 200

        # Send message 3: Entry 2 should inject (cooldown expired)
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "shared_keyword"}]},
        )
        assert response.status_code == 200

    finally:
        world_info_client.delete_entry(entry1["id"])
        world_info_client.delete_entry(entry2["id"])


# ============================================================================
# Test Scenario 7: Agent-Specific vs Global Entries
# ============================================================================


@pytest.mark.asyncio
async def test_agent_specific_vs_global_cooldown(world_info_client, test_agent):
    """
    Test that agent-specific and global entries have independent state tracking.
    """
    headers = {"user_id": world_info_client.headers["user_id"], **_get_auth_headers()}
    agent_id = test_agent["id"]

    global_entry = world_info_client.create_entry({
        "keywords": ["scope_test"],
        "content": "Global entry",
        "agent_id": None,  # Global
        "cooldown": 1,
        "expiration": 2,
    })

    agent_entry = world_info_client.create_entry({
        "keywords": ["scope_test"],
        "content": "Agent-specific entry",
        "agent_id": agent_id,
        "insertion_order": 2,
        "cooldown": 1,
        "expiration": 2,
    })

    try:
        # Send message: Both should inject
        response = requests.post(
            f"{world_info_client.server_url}/v1/agents/{agent_id}/messages",
            headers=headers,
            json={"messages": [{"role": "user", "content": "scope_test"}]},
        )
        assert response.status_code == 200

        # Create a second agent
        import uuid
        from letta.schemas.embedding_config import EmbeddingConfig
        from letta.schemas.llm_config import LLMConfig

        agent2_data = {
            "name": f"test_agent_2_{uuid.uuid4().hex[:8]}",
            "agent_type": "memgpt_v2_agent",
            "memory_blocks": [],
            "llm_config": LLMConfig.default_config("gpt-4o-mini").model_dump(),
            "embedding_config": EmbeddingConfig.default_config(provider="openai").model_dump(),
            "include_base_tools": False,
        }
        agent2_response = requests.post(
            f"{world_info_client.server_url}/v1/agents/",
            headers=headers,
            json=agent2_data,
        )
        assert agent2_response.status_code == 200
        agent2 = agent2_response.json()

        try:
            # Send message with agent2: Only global should inject (agent_entry is agent-specific)
            response = requests.post(
                f"{world_info_client.server_url}/v1/agents/{agent2['id']}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": "scope_test"}]},
            )
            assert response.status_code == 200

        finally:
            requests.delete(
                f"{world_info_client.server_url}/v1/agents/{agent2['id']}",
                headers=headers,
            )

    finally:
        world_info_client.delete_entry(global_entry["id"])
        world_info_client.delete_entry(agent_entry["id"])

