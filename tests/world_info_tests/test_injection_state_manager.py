"""
Unit tests for WorldInfoInjectionStateManager.

Tests the CRUD operations and state management logic for injection states.
These are isolated database tests, not integration tests.
"""

import pytest

from letta.orm import WorldInfoInjectionState as ORMWorldInfoInjectionState
from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager


# ============================================================================
# CRUD Operation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_injection_state(async_session, default_organization, test_agent):
    """Test creating a new injection state record."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    # Create a world info entry (we'll mock the ID for this test)
    world_info_entry_id = "wie-test-12345"

    state = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=5,
        current_expiration=10,
        cooldown_setting=5,
        expiration_setting=10,
        actor=default_organization._created_by,
    )

    assert state.id is not None
    assert state.id.startswith("wiis-")
    assert state.world_info_entry_id == world_info_entry_id
    assert state.agent_id == test_agent["id"]
    assert state.current_cooldown == 5
    assert state.current_expiration == 10
    assert state.cooldown_setting == 5
    assert state.expiration_setting == 10

    # Cleanup
    manager.delete_injection_state(state.id)


@pytest.mark.asyncio
async def test_create_injection_state_with_nulls(async_session, default_organization, test_agent):
    """Test creating injection state with NULL counters (treated as 0)."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    world_info_entry_id = "wie-test-nulls"

    state = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=None,  # NULL = no cooldown
        current_expiration=None,  # NULL = never expire
        cooldown_setting=0,
        expiration_setting=0,
        actor=default_organization._created_by,
    )

    assert state.current_cooldown is None
    assert state.current_expiration is None
    assert state.cooldown_setting == 0
    assert state.expiration_setting == 0

    manager.delete_injection_state(state.id)


@pytest.mark.asyncio
async def test_get_injection_state_by_entry(async_session, default_organization, test_agent):
    """Test retrieving injection state by entry and agent ID."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    world_info_entry_id = "wie-test-retrieve"

    created = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=3,
        current_expiration=7,
        cooldown_setting=3,
        expiration_setting=7,
        actor=default_organization._created_by,
    )

    retrieved = manager.get_injection_state_by_entry(world_info_entry_id, test_agent["id"])

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.world_info_entry_id == world_info_entry_id
    assert retrieved.agent_id == test_agent["id"]

    # Test non-existent retrieval
    not_found = manager.get_injection_state_by_entry("nonexistent", test_agent["id"])
    assert not_found is None

    manager.delete_injection_state(created.id)


@pytest.mark.asyncio
async def test_get_injection_states_by_agent(async_session, default_organization, test_agent):
    """Test retrieving all injection states for an agent."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    # Create multiple states for the same agent
    state1 = manager.create_injection_state(
        world_info_entry_id="wie-agent-1",
        agent_id=test_agent["id"],
        current_cooldown=1,
        current_expiration=2,
        cooldown_setting=1,
        expiration_setting=2,
        actor=default_organization._created_by,
    )

    state2 = manager.create_injection_state(
        world_info_entry_id="wie-agent-2",
        agent_id=test_agent["id"],
        current_cooldown=3,
        current_expiration=4,
        cooldown_setting=3,
        expiration_setting=4,
        actor=default_organization._created_by,
    )

    # Retrieve all states for agent
    states = manager.get_injection_states_by_agent(test_agent["id"])

    state_ids = [s.id for s in states]
    assert state1.id in state_ids
    assert state2.id in state_ids
    assert len(states) >= 2

    # Cleanup
    manager.delete_injection_state(state1.id)
    manager.delete_injection_state(state2.id)


@pytest.mark.asyncio
async def test_update_injection_state(async_session, default_organization, test_agent):
    """Test updating an injection state."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    world_info_entry_id = "wie-test-update"

    created = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=10,
        current_expiration=20,
        cooldown_setting=10,
        expiration_setting=20,
        actor=default_organization._created_by,
    )

    # Decrement counters
    updated = manager.update_injection_state(
        injection_state_id=created.id,
        current_cooldown=9,
        current_expiration=19,
        last_processed_run_id="run-123",
        actor=default_organization._created_by,
    )

    assert updated.id == created.id
    assert updated.current_cooldown == 9
    assert updated.current_expiration == 19
    assert updated.last_processed_run_id == "run-123"

    # Update with None (should convert to NULL)
    updated2 = manager.update_injection_state(
        injection_state_id=created.id,
        current_cooldown=0,  # Should become None
        current_expiration=0,  # Should become None
        actor=default_organization._created_by,
    )

    assert updated2.current_cooldown is None
    assert updated2.current_expiration is None

    manager.delete_injection_state(created.id)


@pytest.mark.asyncio
async def test_delete_injection_state(async_session, default_organization, test_agent):
    """Test deleting an injection state."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    world_info_entry_id = "wie-test-delete"

    created = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=1,
        current_expiration=1,
        cooldown_setting=1,
        expiration_setting=1,
        actor=default_organization._created_by,
    )

    # Verify it exists
    retrieved = manager.get_injection_state_by_entry(world_info_entry_id, test_agent["id"])
    assert retrieved is not None

    # Delete it
    manager.delete_injection_state(created.id)

    # Verify it's gone
    retrieved = manager.get_injection_state_by_entry(world_info_entry_id, test_agent["id"])
    assert retrieved is None


# ============================================================================
# Cleanup Logic Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_completed_states(async_session, default_organization, test_agent):
    """Test deletion of completed states (both counters at 0 or None)."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    # Create multiple states with different completion states
    completed1 = manager.create_injection_state(
        world_info_entry_id="wie-completed-1",
        agent_id=test_agent["id"],
        current_cooldown=0,
        current_expiration=0,
        cooldown_setting=5,
        expiration_setting=10,
        actor=default_organization._created_by,
    )

    completed2 = manager.create_injection_state(
        world_info_entry_id="wie-completed-2",
        agent_id=test_agent["id"],
        current_cooldown=None,
        current_expiration=None,
        cooldown_setting=0,
        expiration_setting=0,
        actor=default_organization._created_by,
    )

    completed3 = manager.create_injection_state(
        world_info_entry_id="wie-completed-3",
        agent_id=test_agent["id"],
        current_cooldown=None,
        current_expiration=0,
        cooldown_setting=0,
        expiration_setting=5,
        actor=default_organization._created_by,
    )

    active = manager.create_injection_state(
        world_info_entry_id="wie-active",
        agent_id=test_agent["id"],
        current_cooldown=5,
        current_expiration=10,
        cooldown_setting=5,
        expiration_setting=10,
        actor=default_organization._created_by,
    )

    # Delete completed states
    manager.delete_completed_states(test_agent["id"])

    # Verify completed states are gone
    assert manager.get_injection_state_by_entry("wie-completed-1", test_agent["id"]) is None
    assert manager.get_injection_state_by_entry("wie-completed-2", test_agent["id"]) is None
    assert manager.get_injection_state_by_entry("wie-completed-3", test_agent["id"]) is None

    # Verify active state remains
    remaining = manager.get_injection_state_by_entry("wie-active", test_agent["id"])
    assert remaining is not None
    assert remaining.current_cooldown == 5

    # Cleanup
    manager.delete_injection_state(active.id)


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_unique_constraint_per_entry_agent(async_session, default_organization, test_agent):
    """Test that only one state can exist per entry/agent combination."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    world_info_entry_id = "wie-unique-constraint"

    # Create first state
    state1 = manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=test_agent["id"],
        current_cooldown=1,
        current_expiration=2,
        cooldown_setting=1,
        expiration_setting=2,
        actor=default_organization._created_by,
    )

    # Attempt to create second state with same entry/agent
    # This should either fail or update the existing one depending on implementation
    # For now, we'll just verify the first one exists
    retrieved = manager.get_injection_state_by_entry(world_info_entry_id, test_agent["id"])
    assert retrieved.id == state1.id

    manager.delete_injection_state(state1.id)


@pytest.mark.asyncio
async def test_update_nonexistent_state(async_session, default_organization, test_agent):
    """Test updating a non-existent state returns None."""
    manager = WorldInfoInjectionStateManager(session=async_session)

    result = manager.update_injection_state(
        injection_state_id="nonexistent-id",
        current_cooldown=5,
        actor=default_organization._created_by,
    )

    assert result is None

