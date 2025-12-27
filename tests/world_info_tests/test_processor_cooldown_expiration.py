"""
Unit tests for WorldInfoProcessor cooldown and expiration logic.

These tests verify the processor logic directly without requiring
full end-to-end LLM API calls.
"""

import pytest

from letta.schemas.enums import MessageRole
from letta.schemas.message import MessageCreate
from straubnet_extensions.world_info.processor import WorldInfoProcessor


# ============================================================================
# Scenario 1: Cooldown Only (no expiration)
# ============================================================================


@pytest.mark.asyncio
async def test_processor_cooldown_only(
    world_info_client,
    test_agent,
    server,
):
    """
    Test cooldown-only behavior in processor:
    - Entry with cooldown=3, expiration=0
    - Injects on first match
    - Won't re-inject for 3 runs
    - Stays in context forever
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    # Create entry with cooldown only
    entry = world_info_client.create_entry({
        "keywords": ["cooldown_only"],
        "content": "This entry has a cooldown of 3",
        "agent_id": agent_id,
        "cooldown": 3,
        "expiration": 0,  # Never expire
    })

    try:
        # Run 1: First match - should inject
        messages = [MessageCreate(role=MessageRole.user, content="cooldown_only test")]
        context = {
            "run_id": "run-001",
            "agent_id": agent_id,
            "organization_id": organization_id,
        }

        result = await processor.process(messages, context)

        # Verify injection occurred
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry has a cooldown" in m.content]
        assert len(world_info_messages) == 1, "Should inject on first match"

        # Verify state was created
        async with server.async_session() as session:
            from letta.orm import WorldInfoInjectionState
            from sqlalchemy import select

            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_result.scalar_one_or_none()
            assert state is not None
            assert state.current_cooldown == 3
            assert state.current_expiration is None  # expiration=0

        # Run 2 and 3: Cooldown active - should NOT inject
        for run_num in ["run-002", "run-003"]:
            context["run_id"] = run_num
            result = await processor.process(messages, context)
            world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry has a cooldown" in m.content]
            assert len(world_info_messages) == 0, f"Should NOT inject during cooldown (run {run_num})"

            # Verify cooldown was decremented
            async with server.async_session() as session:
                state_result = await session.execute(
                    select(WorldInfoInjectionState).where(
                        WorldInfoInjectionState.world_info_entry_id == entry["id"],
                        WorldInfoInjectionState.agent_id == agent_id,
                    )
                )
                state = state_result.scalar_one()
                expected = 5 - int(run_num.split("-")[1])  # 3 -> 2 -> 1
                assert state.current_cooldown == expected

        # Run 4: Cooldown expired - should inject again
        context["run_id"] = "run-004"
        result = await processor.process(messages, context)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry has a cooldown" in m.content]
        assert len(world_info_messages) == 1, "Should inject again after cooldown expires"

        # Verify cooldown reset to 3
        async with server.async_session() as session:
            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_result.scalar_one()
            assert state.current_cooldown == 3, "Cooldown should reset to original value"
            assert state.current_expiration is None, "Expiration should remain None"

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Scenario 2: Expiration Only (no cooldown)
# ============================================================================


@pytest.mark.asyncio
async def test_processor_expiration_only(world_info_client, test_agent, server):
    """
    Test expiration-only behavior in processor:
    - Entry with cooldown=0, expiration=2
    - Injects on every match (no cooldown)
    - Removed from context after 2 runs
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    entry = world_info_client.create_entry({
        "keywords": ["expire_only"],
        "content": "This entry expires after 2 runs",
        "agent_id": agent_id,
        "cooldown": 0,
        "expiration": 2,
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="expire_only test")]

        # Run 1: Should inject
        context = {
            "run_id": "run-001",
            "agent_id": agent_id,
            "organization_id": organization_id,
        }

        result = await processor.process(messages, context)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry expires" in m.content]
        assert len(world_info_messages) == 1

        # Verify state: expiration=2 (just injected, hasn't decremented yet)
        async with server.async_session() as session:
            from letta.orm import WorldInfoInjectionState
            from sqlalchemy import select

            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_result.scalar_one_or_none()
            assert state is not None
            assert state.current_cooldown is None
            assert state.current_expiration == 2

        # Run 2: Should inject again (no cooldown), but decrement expiration
        context["run_id"] = "run-002"
        result = await processor.process(messages, context)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry expires" in m.content]
        assert len(world_info_messages) == 1, "Should inject again (no cooldown)"

        # Run 3: Should NOT inject (expired)
        context["run_id"] = "run-003"
        result = await processor.process(messages, context)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry expires" in m.content]
        assert len(world_info_messages) == 0, "Should NOT inject after expiration"

        # Run 4: Still expired, should not inject
        context["run_id"] = "run-004"
        result = await processor.process(messages, context)
        world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry expires" in m.content]
        assert len(world_info_messages) == 0

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Scenario 3: Both Cooldown and Expiration
# ============================================================================


@pytest.mark.asyncio
async def test_processor_both_cooldown_and_expiration(world_info_client, test_agent, server):
    """
    Test both cooldown and expiration together:
    - Entry with cooldown=2, expiration=5
    - Won't inject more often than every 2 runs
    - Will expire after 5 runs total
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    entry = world_info_client.create_entry({
        "keywords": ["both"],
        "content": "This entry has cooldown=2 and expiration=5",
        "agent_id": agent_id,
        "cooldown": 2,
        "expiration": 5,
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="both test")]

        # Track injections
        injection_count = 0

        # Run through 6 runs
        for run_num in range(1, 7):
            context = {
                "run_id": f"run-{run_num:03d}",
                "agent_id": agent_id,
                "organization_id": organization_id,
            }

            result = await processor.process(messages, context)
            world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry has" in m.content]

            # Should inject on runs 1, 3, 5 (every 2 runs) but not after expiration
            expected_injection = run_num in [1, 3, 5] and run_num <= 5

            if expected_injection:
                assert len(world_info_messages) == 1, f"Should inject on run {run_num}"
                injection_count += 1
            else:
                assert len(world_info_messages) == 0, f"Should NOT inject on run {run_num}"

        # Should have injected 3 times (runs 1, 3, 5)
        assert injection_count == 3

        # Verify state is cleaned up (both counters at 0)
        async with server.async_session() as session:
            from letta.orm import WorldInfoInjectionState
            from sqlalchemy import select

            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_result.scalar_one_or_none()
            # State should be deleted when both counters reach 0
            assert state is None, "State should be cleaned up when both counters at 0"

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Scenario 4: No Cooldown, No Expiration (default behavior)
# ============================================================================


@pytest.mark.asyncio
async def test_processor_no_cooldown_no_expiration(world_info_client, test_agent):
    """
    Test default behavior (no cooldown, no expiration):
    - Entry with cooldown=0, expiration=0
    - Should inject on every match
    - No state tracking needed
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    entry = world_info_client.create_entry({
        "keywords": ["no_limits"],
        "content": "This entry has no cooldown or expiration",
        "agent_id": agent_id,
        "cooldown": 0,
        "expiration": 0,
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="no_limits test")]

        # Run multiple times - should always inject
        for run_num in range(1, 6):
            context = {
                "run_id": f"run-{run_num:03d}",
                "agent_id": agent_id,
                "organization_id": organization_id,
            }

            result = await processor.process(messages, context)
            world_info_messages = [m for m in result if m.role == MessageRole.system and "This entry has no" in m.content]
            assert len(world_info_messages) == 1, f"Should always inject (run {run_num})"

        # Verify NO state was created (both 0, so no tracking needed)
        async with server.async_session() as session:
            from letta.orm import WorldInfoInjectionState
            from sqlalchemy import select

            state_result = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_result.scalar_one_or_none()
            assert state is None, "No state should be created when cooldown=0 and expiration=0"

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Scenario 5: NULL values treated as 0
# ============================================================================


@pytest.mark.asyncio
async def test_processor_null_values(world_info_client, test_agent):
    """
    Test that NULL cooldown/expiration are treated as 0:
    - Entry with cooldown=None, expiration=None
    - Should behave like cooldown=0, expiration=0
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    # Create entry with NULL values
    entry = world_info_client.create_entry({
        "keywords": ["null_values"],
        "content": "This entry has NULL cooldown and expiration",
        "agent_id": agent_id,
        # cooldown and expiration omitted (will be NULL)
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="null_values test")]

        # Run multiple times - should always inject
        for run_num in range(1, 4):
            context = {
                "run_id": f"run-{run_num:03d}",
                "agent_id": agent_id,
                "organization_id": organization_id,
            }

            result = await processor.process(messages, context)
            world_info_messages = [m for m in result if m.role == MessageRole.system and "NULL cooldown" in m.content]
            assert len(world_info_messages) == 1, f"NULL values should behave like 0 (run {run_num})"

    finally:
        world_info_client.delete_entry(entry["id"])


# ============================================================================
# Scenario 6: Multiple entries with different settings
# ============================================================================


@pytest.mark.asyncio
async def test_processor_multiple_entries(world_info_client, test_agent):
    """
    Test multiple entries with different cooldown/expiration settings:
    - Entry A: cooldown=2, expiration=0
    - Entry B: cooldown=0, expiration=3
    - Both should inject appropriately
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    entry_a = world_info_client.create_entry({
        "keywords": ["entry_a"],
        "content": "Entry A: cooldown=2, expiration=0",
        "agent_id": agent_id,
        "cooldown": 2,
        "expiration": 0,
    })

    entry_b = world_info_client.create_entry({
        "keywords": ["entry_b"],
        "content": "Entry B: cooldown=0, expiration=3",
        "agent_id": agent_id,
        "cooldown": 0,
        "expiration": 3,
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="entry_a and entry_b test")]

        # Run 1: Both should inject
        context = {
            "run_id": "run-001",
            "agent_id": agent_id,
            "organization_id": organization_id,
        }

        result = await processor.process(messages, context)
        assert any("Entry A" in m.content and m.role == MessageRole.system for m in result), "Entry A should inject"
        assert any("Entry B" in m.content and m.role == MessageRole.system for m in result), "Entry B should inject"

        # Run 2: Only B should inject (A is on cooldown)
        context["run_id"] = "run-002"
        result = await processor.process(messages, context)
        assert not any("Entry A" in m.content and m.role == MessageRole.system for m in result), "Entry A on cooldown"
        assert any("Entry B" in m.content and m.role == MessageRole.system for m in result), "Entry B should inject"

        # Run 3: A should inject again (cooldown over), B still active
        context["run_id"] = "run-003"
        result = await processor.process(messages, context)
        assert any("Entry A" in m.content and m.role == MessageRole.system for m in result), "Entry A should inject again"
        assert any("Entry B" in m.content and m.role == MessageRole.system for m in result), "Entry B should inject"

        # Run 4: A on cooldown, B on final run
        context["run_id"] = "run-004"
        result = await processor.process(messages, context)
        assert not any("Entry A" in m.content and m.role == MessageRole.system for m in result), "Entry A on cooldown"
        assert any("Entry B" in m.content and m.role == MessageRole.system for m in result), "Entry B final injection"

        # Run 5: A should inject, B expired
        context["run_id"] = "run-005"
        result = await processor.process(messages, context)
        assert any("Entry A" in m.content and m.role == MessageRole.system for m in result), "Entry A should inject"
        assert not any("Entry B" in m.content and m.role == MessageRole.system for m in result), "Entry B expired"

    finally:
        world_info_client.delete_entry(entry_a["id"])
        world_info_client.delete_entry(entry_b["id"])


# ============================================================================
# Scenario 7: State cleanup verification
# ============================================================================


@pytest.mark.asyncio
async def test_processor_state_cleanup(world_info_client, test_agent, server):
    """
    Verify that states are properly cleaned up:
    - States with both counters at 0/None should be deleted
    - States with active counters should be retained
    """
    processor = WorldInfoProcessor()
    agent_id = test_agent["id"]
    organization_id = world_info_client.headers["organization_id"]

    # Entry that will complete (both counters at 0)
    entry_complete = world_info_client.create_entry({
        "keywords": ["complete"],
        "content": "This entry completes after 2 runs",
        "agent_id": agent_id,
        "cooldown": 1,
        "expiration": 1,
    })

    # Entry that stays active
    entry_active = world_info_client.create_entry({
        "keywords": ["active"],
        "content": "This entry stays active",
        "agent_id": agent_id,
        "cooldown": 10,
        "expiration": 20,
    })

    try:
        messages = [MessageCreate(role=MessageRole.user, content="complete and active test")]

        # Run 1: Both inject
        context = {
            "run_id": "run-001",
            "agent_id": agent_id,
            "organization_id": organization_id,
        }

        await processor.process([MessageCreate(role=MessageRole.user, content="complete")], context)
        await processor.process([MessageCreate(role=MessageRole.user, content="active")], context)

        # Run 2: Both inject again, but complete entry will have counters at 0
        context["run_id"] = "run-002"
        await processor.process([MessageCreate(role=MessageRole.user, content="complete")], context)
        await processor.process([MessageCreate(role=MessageRole.user, content="active")], context)

        # Verify states
        async with server.async_session() as session:
            from letta.orm import WorldInfoInjectionState
            from sqlalchemy import select

            # Complete entry state should be deleted
            state_complete = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry_complete["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            assert state_complete.scalar_one_or_none() is None, "Completed entry state should be deleted"

            # Active entry state should still exist
            state_active = await session.execute(
                select(WorldInfoInjectionState).where(
                    WorldInfoInjectionState.world_info_entry_id == entry_active["id"],
                    WorldInfoInjectionState.agent_id == agent_id,
                )
            )
            state = state_active.scalar_one_or_none()
            assert state is not None, "Active entry state should exist"
            assert state.current_cooldown == 10
            assert state.current_expiration == 20

    finally:
        world_info_client.delete_entry(entry_complete["id"])
        world_info_client.delete_entry(entry_active["id"])

