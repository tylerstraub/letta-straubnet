"""
Simple tests for WorldInfoInjectionStateManager.

Tests manager methods directly with minimal dependencies.
"""

import sys
import os

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "letta"))

import pytest
from sqlalchemy import select

from letta.orm import WorldInfoEntry, WorldInfoInjectionState
from letta.server.db import db_registry
from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager


# ============================================================================
# Basic CRUD Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_and_retrieve_state():
    """Test creating and retrieving an injection state."""
    manager = WorldInfoInjectionStateManager()

    async with db_registry.async_session() as session:
        # Create a World Info entry first
        entry = WorldInfoEntry(
            keywords=["test"],
            content="Test content",
            insertion_order=100,
            enabled=True,
            agent_id=None,  # Global entry
            organization_id="test-org",
            cooldown=5,
            expiration=10,
        )
        await entry.create_async(session)
        await session.commit()
        await session.refresh(entry)

        # Create state
        state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=5,
            current_expiration=10,
            cooldown_setting=5,
            expiration_setting=10,
        )

        assert state.id is not None
        assert state.id.startswith("wiis-")
        assert state.world_info_entry_id == entry.id
        assert state.agent_id == "test-agent"
        assert state.current_cooldown == 5
        assert state.current_expiration == 10

        # Retrieve it
        retrieved = await manager.get_injection_state_by_entry(entry.id, "test-agent")
        assert retrieved is not None
        assert retrieved.id == state.id

        # Cleanup
        await manager.delete_injection_state(state.id)
        await session.delete(entry)
        await session.commit()


@pytest.mark.asyncio
async def test_update_state():
    """Test updating an injection state."""
    manager = WorldInfoInjectionStateManager()

    async with db_registry.async_session() as session:
        # Create entry
        entry = WorldInfoEntry(
            keywords=["test"],
            content="Test content",
            insertion_order=100,
            enabled=True,
            agent_id=None,
            organization_id="test-org",
            cooldown=5,
            expiration=0,
        )
        await entry.create_async(session)
        await session.commit()
        await session.refresh(entry)

        # Create state
        state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=5,
            current_expiration=None,  # Never expire
            cooldown_setting=5,
            expiration_setting=0,
        )

        # Update cooldown
        updated = await manager.update_injection_state(
            injection_state_id=state.id,
            current_cooldown=3,
            current_expiration=None,
        )

        assert updated.current_cooldown == 3
        assert updated.current_expiration is None

        # Set cooldown to 0 (should become None)
        updated2 = await manager.update_injection_state(
            injection_state_id=state.id,
            current_cooldown=0,
        )

        assert updated2.current_cooldown is None

        # Cleanup
        await manager.delete_injection_state(state.id)
        await session.delete(entry)
        await session.commit()


@pytest.mark.asyncio
async def test_null_values():
    """Test that NULL values are handled correctly."""
    manager = WorldInfoInjectionStateManager()

    async with db_registry.async_session() as session:
        # Create entry with NULL cooldown/expiration
        entry = WorldInfoEntry(
            keywords=["test"],
            content="Test content",
            insertion_order=100,
            enabled=True,
            agent_id=None,
            organization_id="test-org",
            cooldown=None,  # No cooldown
            expiration=None,  # No expiration
        )
        await entry.create_async(session)
        await session.commit()
        await session.refresh(entry)

        # Create state with NULLs
        state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=None,
            current_expiration=None,
            cooldown_setting=0,  # NULL settings treated as 0
            expiration_setting=0,
        )

        assert state.current_cooldown is None
        assert state.current_expiration is None

        # Cleanup
        await manager.delete_injection_state(state.id)
        await session.delete(entry)
        await session.commit()


@pytest.mark.asyncio
async def test_delete_state():
    """Test deleting an injection state."""
    manager = WorldInfoInjectionStateManager()

    async with db_registry.async_session() as session:
        # Create entry
        entry = WorldInfoEntry(
            keywords=["test"],
            content="Test content",
            insertion_order=100,
            enabled=True,
            agent_id=None,
            organization_id="test-org",
            cooldown=1,
            expiration=1,
        )
        await entry.create_async(session)
        await session.commit()
        await session.refresh(entry)

        # Create state
        state = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=1,
            current_expiration=1,
            cooldown_setting=1,
            expiration_setting=1,
        )

        # Verify it exists
        retrieved = await manager.get_injection_state_by_entry(entry.id, "test-agent")
        assert retrieved is not None

        # Delete it
        await manager.delete_injection_state(state.id)

        # Verify it's gone
        retrieved = await manager.get_injection_state_by_entry(entry.id, "test-agent")
        assert retrieved is None

        # Cleanup entry
        await session.delete(entry)
        await session.commit()


@pytest.mark.asyncio
async def test_unique_constraint():
    """Test unique constraint on (world_info_entry_id, agent_id)."""
    manager = WorldInfoInjectionStateManager()

    async with db_registry.async_session() as session:
        # Create entry
        entry = WorldInfoEntry(
            keywords=["test"],
            content="Test content",
            insertion_order=100,
            enabled=True,
            agent_id=None,
            organization_id="test-org",
            cooldown=2,
            expiration=0,
        )
        await entry.create_async(session)
        await session.commit()
        await session.refresh(entry)

        # Create first state
        state1 = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=2,
            current_expiration=None,
            cooldown_setting=2,
            expiration_setting=0,
        )

        # Try to create second state with same entry/agent
        # Manager should find existing state
        state2 = await manager.create_injection_state(
            world_info_entry_id=entry.id,
            agent_id="test-agent",
            organization_id="test-org",
            current_cooldown=5,
            current_expiration=None,
            cooldown_setting=5,
            expiration_setting=0,
        )

        # Should return same state (not create new one)
        assert state2.id == state1.id
        assert state2.world_info_entry_id == entry.id

        # Cleanup
        await manager.delete_injection_state(state1.id)
        await session.delete(entry)
        await session.commit()

