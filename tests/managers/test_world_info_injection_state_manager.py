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
    )

    assert updated.id == created.id
    assert updated.current_cooldown == 9
    assert updated.current_expiration == 19

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
async def test_delete_completed_states(server, default_organization, sarah_agent, default_user):
    """Test deletion of completed states.
    
    A state is complete when:
    - Cooldown is None or 0 (no cooldown)
    - AND expiration is 0 (expired, not None - None means never expire)
    """
    from letta.schemas.world_info_entry import WorldInfoEntryCreate
    
    manager = WorldInfoInjectionStateManager()
    world_info_manager = server.world_info_manager

    # Create actual World Info entries for the states
    entry1 = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test1"],
            content="Test entry 1",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )
    
    entry2 = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test2"],
            content="Test entry 2",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )
    
    entry3 = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test3"],
            content="Test entry 3",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )
    
    entry4 = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test4"],
            content="Test entry 4",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    try:
        # Create multiple states with different completion states
        # completed1: cooldown=0, expiration=0 -> should be deleted (complete)
        completed1 = await manager.create_injection_state(
            world_info_entry_id=entry1.id,
            agent_id=sarah_agent.id,
            current_cooldown=0,
            current_expiration=0,
            cooldown_setting=5,
            expiration_setting=10,
            organization_id=default_organization.id,
        )

        # never_expires: cooldown=None, expiration=None -> should NOT be deleted (expiration=None means never expire)
        never_expires = await manager.create_injection_state(
            world_info_entry_id=entry2.id,
            agent_id=sarah_agent.id,
            current_cooldown=None,
            current_expiration=None,  # None means never expire, so NOT complete
            cooldown_setting=0,
            expiration_setting=0,
            organization_id=default_organization.id,
        )

        # completed3: cooldown=None, expiration=0 -> should be deleted (complete)
        completed3 = await manager.create_injection_state(
            world_info_entry_id=entry3.id,
            agent_id=sarah_agent.id,
            current_cooldown=None,
            current_expiration=0,  # 0 means expired, so complete
            cooldown_setting=0,
            expiration_setting=5,
            organization_id=default_organization.id,
        )

        # active: cooldown=5, expiration=10 -> should NOT be deleted (not complete)
        active = await manager.create_injection_state(
            world_info_entry_id=entry4.id,
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
        assert await manager.get_injection_state_by_entry(entry1.id, sarah_agent.id) is None, "completed1 should be deleted"
        assert await manager.get_injection_state_by_entry(entry3.id, sarah_agent.id) is None, "completed3 should be deleted"
        
        # Verify never_expires state remains (expiration=None means never expire, not complete)
        remaining_never_expires = await manager.get_injection_state_by_entry(entry2.id, sarah_agent.id)
        assert remaining_never_expires is not None, "never_expires state should remain (expiration=None means never expire)"
        assert remaining_never_expires.current_expiration is None
        
        # Verify active state remains
        remaining_active = await manager.get_injection_state_by_entry(entry4.id, sarah_agent.id)
        assert remaining_active is not None, "active state should remain"
        assert remaining_active.current_cooldown == 5

        # Cleanup
        await manager.delete_injection_state(never_expires.id)
        await manager.delete_injection_state(active.id)
    finally:
        # Cleanup entries
        await world_info_manager.delete_entry_async(entry1.id, default_user)
        await world_info_manager.delete_entry_async(entry2.id, default_user)
        await world_info_manager.delete_entry_async(entry3.id, default_user)
        await world_info_manager.delete_entry_async(entry4.id, default_user)


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_unique_constraint_per_entry_agent(server, default_organization, sarah_agent, default_user):
    """Test that only one state can exist per entry/agent combination, and that existing states are updated with new values."""
    from letta.schemas.world_info_entry import WorldInfoEntryCreate
    
    manager = WorldInfoInjectionStateManager()
    world_info_manager = server.world_info_manager

    # Create a real World Info entry
    entry = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test"],
            content="Test entry",
            agent_id=sarah_agent.id,
        ),
        actor=default_user,
    )

    try:
        # Create first state
        state1 = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id=sarah_agent.id,
            current_cooldown=1,
            current_expiration=2,
            cooldown_setting=1,
            expiration_setting=2,
            organization_id=default_organization.id,
            actor=default_user,
        )

        # Attempt to create second state with same entry/agent
        # Manager should UPDATE the existing state with new values (not return stale state)
        state2 = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id=sarah_agent.id,
            current_cooldown=3,
            current_expiration=4,
            cooldown_setting=3,
            expiration_setting=4,
            organization_id=default_organization.id,
            actor=default_user,
        )

        # Should return the same state ID (not create new one)
        assert state2.id == state1.id
        assert state2.world_info_entry_id == entry.id
        
        # CRITICAL: State should be UPDATED with new values, not returned unchanged
        # This verifies the fix for the regression where stale states were left behind
        assert state2.current_cooldown == 3, "State should be updated with new cooldown value"
        assert state2.current_expiration == 4, "State should be updated with new expiration value"
        assert state2.cooldown_setting == 3, "State should be updated with new cooldown_setting"
        assert state2.expiration_setting == 4, "State should be updated with new expiration_setting"
        
        # Verify the old values are gone
        assert state2.current_cooldown != state1.current_cooldown, "Cooldown should have changed"
        assert state2.current_expiration != state1.current_expiration, "Expiration should have changed"

        await manager.delete_injection_state(state1.id)
    finally:
        await world_info_manager.delete_entry_async(entry.id, default_user)


@pytest.mark.asyncio
async def test_update_nonexistent_state(server, default_organization, sarah_agent):
    """Test updating a non-existent state returns None."""
    manager = WorldInfoInjectionStateManager()

    result = await manager.update_injection_state(
        injection_state_id="nonexistent-id",
        current_cooldown=5,
    )

    assert result is None


@pytest.mark.asyncio
async def test_create_injection_state_resets_completed_state(server, default_organization, sarah_agent, default_user):
    """Test that creating a state when a completed state exists resets it with new values.
    
    This test verifies the fix for the regression where stale completed states (cooldown=None, expiration=0)
    were left behind when a new activation occurred. The state should be reset with new values instead
    of being returned unchanged.
    """
    from letta.schemas.world_info_entry import WorldInfoEntryCreate
    
    manager = WorldInfoInjectionStateManager()
    world_info_manager = server.world_info_manager

    # Create a real World Info entry
    entry = await world_info_manager.create_entry_async(
        entry_create=WorldInfoEntryCreate(
            keywords=["test"],
            content="Test entry",
            agent_id=sarah_agent.id,
            cooldown=5,
            expiration=10,
        ),
        actor=default_user,
    )

    try:
        # Create a completed state (cooldown=None, expiration=0) - this simulates a stale state
        completed_state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id=sarah_agent.id,
            current_cooldown=None,  # No cooldown (complete)
            current_expiration=0,  # Expired (complete)
            cooldown_setting=5,
            expiration_setting=10,
            organization_id=default_organization.id,
            actor=default_user,
        )
        
        # Verify it's in completed state
        assert completed_state.current_cooldown is None
        assert completed_state.current_expiration == 0

        # Now simulate a new activation - create_injection_state should RESET the state with new values
        # This is the critical fix: it should update the state, not return the stale completed state
        new_state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id=sarah_agent.id,
            current_cooldown=5,  # New cooldown value
            current_expiration=10,  # New expiration value
            cooldown_setting=5,
            expiration_setting=10,
            organization_id=default_organization.id,
            actor=default_user,
        )

        # Should be the same state ID (not a new state)
        assert new_state.id == completed_state.id
        
        # CRITICAL: State should be RESET with new values, not left in completed state
        # This verifies the fix prevents stale records from persisting
        assert new_state.current_cooldown == 5, "State should be reset with new cooldown (was None)"
        assert new_state.current_expiration == 10, "State should be reset with new expiration (was 0)"
        assert new_state.cooldown_setting == 5, "State should have updated cooldown_setting"
        assert new_state.expiration_setting == 10, "State should have updated expiration_setting"
        
        # Verify the state is no longer in completed state
        assert new_state.current_cooldown is not None, "Cooldown should not be None after reset"
        assert new_state.current_expiration != 0, "Expiration should not be 0 after reset"
        assert new_state.current_expiration is not None, "Expiration should not be None after reset"

        await manager.delete_injection_state(completed_state.id)
    finally:
        await world_info_manager.delete_entry_async(entry.id, default_user)
