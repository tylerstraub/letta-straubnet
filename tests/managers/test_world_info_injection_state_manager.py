"""
Unit tests for WorldInfoInjectionStateManager.

Tests the CRUD operations and state management logic for injection states.
These are isolated database tests, not integration tests.
"""

import pytest

from letta.orm import WorldInfoInjectionState as WorldInfoInjectionStateModel
from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager


# ============================================================================
# CRUD Operation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_injection_state(server, default_organization, sarah_agent, default_world_info_entry):
    """Test creating a new injection state record."""
    manager = WorldInfoInjectionStateManager()

    state = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=5,
        current_expiration=10,
        cooldown_setting=5,
        expiration_setting=10,
        organization_id=default_organization.id,
    )

    assert state.id is not None
    assert state.id.startswith("wiis-")
    assert state.world_info_entry_id == default_world_info_entry.id
    assert state.agent_id == sarah_agent.id
    assert state.current_cooldown == 5
    assert state.current_expiration == 10
    assert state.cooldown_setting == 5
    assert state.expiration_setting == 10

    # Cleanup
    await manager.delete_injection_state(state.id)


@pytest.mark.asyncio
async def test_create_injection_state_with_nulls(server, default_organization, sarah_agent, default_world_info_entry):
    """Test creating injection state with NULL counters (treated as 0)."""
    manager = WorldInfoInjectionStateManager()

    state = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=None,  # NULL = no cooldown
        current_expiration=None,  # NULL = never expire
        cooldown_setting=0,
        expiration_setting=0,
        organization_id=default_organization.id,
    )

    assert state.current_cooldown is None
    assert state.current_expiration is None
    assert state.cooldown_setting == 0
    assert state.expiration_setting == 0

    await manager.delete_injection_state(state.id)


@pytest.mark.asyncio
async def test_get_injection_state_by_entry(server, default_organization, sarah_agent, default_world_info_entry):
    """Test retrieving injection state by entry and agent ID."""
    manager = WorldInfoInjectionStateManager()

    created = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=3,
        current_expiration=7,
        cooldown_setting=3,
        expiration_setting=7,
        organization_id=default_organization.id,
    )

    retrieved = await manager.get_injection_state_by_entry(default_world_info_entry.id, sarah_agent.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.world_info_entry_id == default_world_info_entry.id
    assert retrieved.agent_id == sarah_agent.id

    # Test non-existent retrieval
    not_found = await manager.get_injection_state_by_entry("nonexistent", sarah_agent.id)
    assert not_found is None

    await manager.delete_injection_state(created.id)


@pytest.mark.asyncio
async def test_get_injection_states_by_agent(server, default_organization, sarah_agent):
    """Test retrieving all injection states for an agent."""
    manager = WorldInfoInjectionStateManager()

    # Create multiple states for the same agent
    state1 = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=1,
        current_expiration=2,
        cooldown_setting=1,
        expiration_setting=2,
        organization_id=default_organization.id,
    )

    state2 = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=3,
        current_expiration=4,
        cooldown_setting=3,
        expiration_setting=4,
        organization_id=default_organization.id,
    )

    # Retrieve all states for agent
    states = await manager.get_injection_states_by_agent(sarah_agent.id)

    state_ids = [s.id for s in states]
    assert state1.id in state_ids
    assert state2.id in state_ids
    assert len(states) >= 2

    # Cleanup
    await manager.delete_injection_state(state1.id)
    await manager.delete_injection_state(state2.id)


@pytest.mark.asyncio
async def test_update_injection_state(server, default_organization, sarah_agent):
    """Test updating an injection state."""
    manager = WorldInfoInjectionStateManager()

    world_info_entry_id = "wie-test-update"

    created = await manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=sarah_agent.id,
        current_cooldown=10,
        current_expiration=20,
        cooldown_setting=10,
        expiration_setting=20,
        organization_id=default_organization.id,
    )

    # Decrement counters
    updated = await manager.update_injection_state(
        injection_state_id=created.id,
        current_cooldown=9,
        current_expiration=19,
        last_processed_run_id="run-123",
    )

    assert updated.id == created.id
    assert updated.current_cooldown == 9
    assert updated.current_expiration == 19
    assert updated.last_processed_run_id == "run-123"

    # Update with None (should convert to NULL)
    updated2 = await manager.update_injection_state(
        injection_state_id=created.id,
        current_cooldown=0,  # Should become None
        current_expiration=0,  # Should become None
    )

    assert updated2.current_cooldown is None
    assert updated2.current_expiration is None

    await manager.delete_injection_state(created.id)


@pytest.mark.asyncio
async def test_delete_injection_state(server, default_organization, sarah_agent):
    """Test deleting an injection state."""
    manager = WorldInfoInjectionStateManager()

    world_info_entry_id = "wie-test-delete"

    created = await manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=sarah_agent.id,
        current_cooldown=1,
        current_expiration=1,
        cooldown_setting=1,
        expiration_setting=1,
        organization_id=default_organization.id,
    )

    # Verify it exists
    retrieved = await manager.get_injection_state_by_entry(world_info_entry_id, sarah_agent.id)
    assert retrieved is not None

    # Delete it
    await manager.delete_injection_state(created.id)

    # Verify it's gone
    retrieved = await manager.get_injection_state_by_entry(world_info_entry_id, sarah_agent.id)
    assert retrieved is None


# ============================================================================
# Cleanup Logic Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_completed_states(server, default_organization, sarah_agent):
    """Test deletion of completed states (both counters at 0 or None)."""
    manager = WorldInfoInjectionStateManager()

    # Create multiple states with different completion states
    completed1 = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=0,
        current_expiration=0,
        cooldown_setting=5,
        expiration_setting=10,
        organization_id=default_organization.id,
    )

    completed2 = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=None,
        current_expiration=None,
        cooldown_setting=0,
        expiration_setting=0,
        organization_id=default_organization.id,
    )

    completed3 = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=None,
        current_expiration=0,
        cooldown_setting=0,
        expiration_setting=5,
        organization_id=default_organization.id,
    )

    active = await manager.create_injection_state(
        world_info_entry_id=default_world_info_entry.id,
        agent_id=sarah_agent.id,
        current_cooldown=5,
        current_expiration=10,
        cooldown_setting=5,
        expiration_setting=10,
        organization_id=default_organization.id,
    )

    # Delete completed states
    await manager.delete_completed_states(sarah_agent.id)

    # Verify completed states are gone
    assert await manager.get_injection_state_by_entry("wie-completed-1", sarah_agent.id) is None
    assert await manager.get_injection_state_by_entry("wie-completed-2", sarah_agent.id) is None
    assert await manager.get_injection_state_by_entry("wie-completed-3", sarah_agent.id) is None

    # Verify active state remains
    remaining = await manager.get_injection_state_by_entry("wie-active", sarah_agent.id)
    assert remaining is not None
    assert remaining.current_cooldown == 5

    # Cleanup
    await manager.delete_injection_state(active.id)


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_unique_constraint_per_entry_agent(server, default_organization, sarah_agent):
    """Test that only one state can exist per entry/agent combination."""
    manager = WorldInfoInjectionStateManager()

    world_info_entry_id = "wie-unique-constraint"

    # Create first state
    state1 = await manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=sarah_agent.id,
        current_cooldown=1,
        current_expiration=2,
        cooldown_setting=1,
        expiration_setting=2,
        organization_id=default_organization.id,
    )

    # Attempt to create second state with same entry/agent
    # Manager should return the existing state
    state2 = await manager.create_injection_state(
        world_info_entry_id=world_info_entry_id,
        agent_id=sarah_agent.id,
        current_cooldown=3,
        current_expiration=4,
        cooldown_setting=3,
        expiration_setting=4,
        organization_id=default_organization.id,
    )

    # Should return the same state (not create new one)
    assert state2.id == state1.id
    assert state2.world_info_entry_id == world_info_entry_id

    await manager.delete_injection_state(state1.id)


@pytest.mark.asyncio
async def test_update_nonexistent_state(server, default_organization, sarah_agent):
    """Test updating a non-existent state returns None."""
    manager = WorldInfoInjectionStateManager()

    result = await manager.update_injection_state(
        injection_state_id="nonexistent-id",
        current_cooldown=5,
    )

    assert result is None
