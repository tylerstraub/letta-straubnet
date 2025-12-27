"""
Additional fixtures for World Info manager tests.

This file adds World Info entry fixtures that are available
to all test files in tests/managers/ directory.
"""

import pytest

from letta.schemas.world_info_entry import CreateWorldInfoEntry


# ======================================================================================================================
# World Info Entry Fixture
# ======================================================================================================================


@pytest.fixture
async def default_world_info_entry(server, default_user, sarah_agent):
    """Create and return a default World Info entry."""
    entry = await server.world_info_entry_manager.create_world_info_entry(
        entry_data={
            "keywords": ["test_keyword"],
            "content": "Test World Info content",
            "insertion_order": 100,
            "enabled": True,
            "agent_id": sarah_agent.id,
        },
        actor=default_user,
    )
    yield entry
