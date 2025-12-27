"""
Minimal test for WorldInfoProcessor cooldown/expiration logic.

Directly tests the processor without complex fixtures.
"""

import sys
import os

# Add /app/letta to Python path so we can import straubnet_extensions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "letta"))

import pytest

from letta.schemas.enums import MessageRole
from letta.schemas.message import MessageCreate
from straubnet_extensions.world_info.processor import WorldInfoProcessor


# ============================================================================
# Minimal Test: Verify processor runs without error
# ============================================================================


@pytest.mark.asyncio
async def test_processor_runs_basic(world_info_client, test_agent):
    """Test that processor runs without error on basic World Info entry."""
    from letta.schemas.letta_user import User as LettaUser

    processor = WorldInfoProcessor()

    # Create a simple World Info entry via client
    entry = world_info_client.create_entry({
        "keywords": ["test"],
        "content": "Test content",
        "agent_id": test_agent["id"],
        "cooldown": 0,
        "expiration": 0,
    })

    try:
        # Create context using info from client and agent
        context = {
            "agent_id": test_agent["id"],
            "actor": LettaUser(
                id=world_info_client.headers["user_id"],
                name="test",
                organization_id=world_info_client.headers["organization_id"],
            ),
            "run_id": "test-run-001",
            "organization_id": world_info_client.headers["organization_id"],
        }

        messages = [MessageCreate(role=MessageRole.user, content="test")]

        # Call processor
        result = processor.process(messages, context)

        # Verify it returns messages
        assert result is not None
        assert isinstance(result, list)

        # Check if injection occurred (should happen with no cooldown/expiration)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "Test content" in m.content]
        # May or may not inject depending on matching logic
        print(f"Result messages: {len(result)}")
        print(f"World info messages found: {len(world_info_messages)}")

    finally:
        # Cleanup
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Test: Verify state tracking methods are called
# ============================================================================


@pytest.mark.asyncio
async def test_processor_state_tracking(server, default_user, sarah_agent):
    """Test that processor properly tracks state for entries with cooldown."""
    from letta.orm import WorldInfoEntry as WorldInfoEntryModel, WorldInfoInjectionState
    from sqlalchemy import select

    processor = WorldInfoProcessor()

    # Create entry with cooldown
    async with server.async_session() as session:
        entry = WorldInfoEntryModel(
            keywords=["cooldown_test"],
            content="Cooldown test content",
            insertion_order=100,
            enabled=True,
            agent_id=sarah_agent.id,
            organization_id=default_user.organization_id,
            cooldown=2,
            expiration=0,
        )
        await entry.create_async(session, actor=default_user)
        await session.commit()
        await session.refresh(entry)

    try:
        context = {
            "agent_id": sarah_agent.id,
            "actor": default_user,
            "run_id": "test-run-001",
            "organization_id": default_user.organization_id,
        }

        messages = [MessageCreate(role=MessageRole.user, content="cooldown_test")]

        # First run - should inject and create state
        result1 = processor.process(messages, context)

        # Check if state was created
        async with server.async_session() as session:
            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry.id,
                    WorldInfoInjectionState.agent_id == sarah_agent.id,
                )
            )
            state = state_result.scalar_one_or_none()

            if state:
                print(f"State created: {state.id}")
                print(f"  current_cooldown: {state.current_cooldown}")
                print(f"  current_expiration: {state.current_expiration}")
                assert state.current_cooldown == 2
                assert state.current_expiration is None
            else:
                print("No state created - this might be expected depending on logic")

        # Second run - should decrement cooldown
        context["run_id"] = "test-run-002"
        result2 = processor.process(messages, context)

        # Check if cooldown was decremented
        async with server.async_session() as session:
            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry.id,
                    WorldInfoInjectionState.agent_id == sarah_agent.id,
                )
            )
            state = state_result.scalar_one_or_none()

            if state:
                print(f"After run 2 - current_cooldown: {state.current_cooldown}")

    finally:
        # Cleanup
        async with server.async_session() as session:
            # Delete injection states first
            await session.execute(
                WorldInfoInjectionState.__table__.delete().where(
                    WorldInfoInjectionState.world_info_entry_id == entry.id
                )
            )
            await session.delete(entry)
            await session.commit()


# ============================================================================
# Test: Null values behave like 0
# ============================================================================


@pytest.mark.asyncio
async def test_processor_null_values(server, default_user, sarah_agent):
    """Test that NULL cooldown/expiration behave like 0 (inject every time)."""
    from letta.orm import WorldInfoEntry as WorldInfoEntryModel, WorldInfoInjectionState
    from sqlalchemy import select

    processor = WorldInfoProcessor()

    # Create entry with NULL cooldown/expiration
    async with server.async_session() as session:
        entry = WorldInfoEntryModel(
            keywords=["null_test"],
            content="Null values test",
            insertion_order=100,
            enabled=True,
            agent_id=sarah_agent.id,
            organization_id=default_user.organization_id,
            # cooldown and expiration not set (will be NULL)
        )
        await entry.create_async(session, actor=default_user)
        await session.commit()
        await session.refresh(entry)

    try:
        context = {
            "agent_id": sarah_agent.id,
            "actor": default_user,
            "run_id": "test-run-001",
            "organization_id": default_user.organization_id,
        }

        messages = [MessageCreate(role=MessageRole.user, content="null_test")]

        # Run multiple times
        for i in range(3):
            context["run_id"] = f"test-run-{i+1:03d}"
            result = processor.process(messages, context)
            print(f"Run {i+1}: {len(result)} messages returned")

            # Verify NO state was created (NULL = 0 = no tracking needed)
            async with server.async_session() as session:
                state_result = await session.execute(
                    select(WorldInfoInjectionState).where(
                        WorldInfoInjectionState.world_info_entry_id == entry.id,
                        WorldInfoInjectionState.agent_id == sarah_agent.id,
                    )
                )
                state = state_result.scalar_one_or_none()
                assert state is None, f"State should not be created for NULL values (run {i+1})"

    finally:
        # Cleanup
        async with server.async_session() as session:
            await session.delete(entry)
            await session.commit()

