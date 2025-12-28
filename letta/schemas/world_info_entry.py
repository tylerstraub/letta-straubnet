"""
Pydantic schemas for World Info entries.

World Info entries are used for keyword-based prompt injection,
similar to SillyTavern's World Info / Lorebook system.
"""

from typing import List, Optional

from pydantic import Field

from letta.schemas.letta_base import OrmMetadataBase


class WorldInfoEntryBase(OrmMetadataBase):
    """Base schema for World Info entries."""

    __id_prefix__ = "world-info-entry"

    organization_id: str = Field(..., description="The organization this entry belongs to.")
    keywords: List[str] = Field(..., description="List of keywords or regex patterns that trigger this entry.")
    content: str = Field(..., description="The content to inject when keywords are matched.")
    insertion_order: int = Field(
        default=100,
        description="Priority/order for insertion. Lower values are injected earlier (further from user message), higher values are injected later (closer to user message).",
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Optional agent ID. If None, entry applies globally to all agents in the organization.",
    )
    enabled: bool = Field(default=True, description="Whether this entry is enabled and should be checked.")
    case_sensitive: bool = Field(
        default=False,
        description="Whether keyword matching should be case-sensitive.",
    )
    match_whole_words: bool = Field(
        default=True,
        description="Whether keywords should match whole words only (word boundaries).",
    )
    cooldown: Optional[int] = Field(
        default=None,
        description="Number of runs to wait before this entry can be injected again. NULL or 0 = no cooldown.",
    )
    expiration: Optional[int] = Field(
        default=None,
        description="Number of runs before this entry should be removed from context. NULL or 0 = never expire.",
    )


class WorldInfoEntry(WorldInfoEntryBase):
    """World Info entry schema."""

    id: str = Field(..., description="The unique identifier of the World Info entry.")


class WorldInfoEntryCreate(WorldInfoEntryBase):
    """
    Schema for creating a new World Info entry.

    Note: organization_id is intentionally omitted - it is set from the actor's
    organization_id by the API endpoint, not from the request body.
    """

    organization_id: Optional[str] = Field(None, description="Not required - set from actor's organization")


class WorldInfoEntryUpdate(OrmMetadataBase):
    """
    Schema for updating a World Info entry.

    Note: organization_id is intentionally omitted - entries cannot be moved
    between organizations. Only the entry's content and configuration can be updated.
    """

    keywords: Optional[List[str]] = Field(None, description="List of keywords or regex patterns.")
    content: Optional[str] = Field(None, description="The content to inject.")
    insertion_order: Optional[int] = Field(None, description="Priority/order for insertion.")
    agent_id: Optional[str] = Field(None, description="Optional agent ID.")
    enabled: Optional[bool] = Field(None, description="Whether this entry is enabled.")
    case_sensitive: Optional[bool] = Field(None, description="Whether keyword matching should be case-sensitive.")
    match_whole_words: Optional[bool] = Field(None, description="Whether keywords should match whole words only.")
    cooldown: Optional[int] = Field(None, description="Number of runs to wait before this entry can be injected again. NULL or 0 = no cooldown.")
    expiration: Optional[int] = Field(None, description="Number of runs before this entry should be removed from context. NULL or 0 = never expire (persist indefinitely). Note: When set to 0 or NULL, the entry will persist indefinitely. When set to a positive value, it counts down and is removed when it reaches 0.")

