"""
Shared fixtures and utilities for World Info tests.

All fixtures defined here are automatically available to all test files
in this directory and subdirectories.
"""

import os
import uuid
from typing import Dict, List, Optional

import pytest
import requests


def _get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for API requests."""
    password = os.getenv("LETTA_SERVER_PASSWORD", "")
    if password:
        return {"Authorization": f"Bearer {password}"}
    return {}


class WorldInfoClient:
    """Helper class for World Info API operations."""

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

    def get_injection_states(self, agent_id: str) -> List[Dict]:
        """
        Get injection states for an agent (direct DB access for testing).
        
        This bypasses the API since we don't expose states via REST.
        """
        from letta.orm import WorldInfoInjectionState
        from letta.db import db
        
        states = db.session.query(WorldInfoInjectionState).filter_by(agent_id=agent_id).all()
        return [
            {
                "id": state.id,
                "world_info_entry_id": state.world_info_entry_id,
                "agent_id": state.agent_id,
                "current_cooldown": state.current_cooldown,
                "current_expiration": state.current_expiration,
                "last_processed_run_id": state.last_processed_run_id,
                "injected_message_id": state.injected_message_id,
                "cooldown_setting": state.cooldown_setting,
                "expiration_setting": state.expiration_setting,
            }
            for state in states
        ]


@pytest.fixture
def world_info_client(server_url, default_user) -> WorldInfoClient:
    """Create a World Info API client for test operations."""
    return WorldInfoClient(server_url, default_user.id)


@pytest.fixture
def test_agent(server_url, default_user) -> Dict:
    """Create a test agent for agent-specific entry tests."""
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
    agent = response.json()

    yield agent

    # Cleanup
    try:
        requests.delete(
            f"{server_url}/v1/agents/{agent['id']}",
            headers=headers,
        )
    except Exception:
        pass

