"""
Pydantic schemas for World Info injection states.

World Info injection states track ephemeral state for active World Info entries.
"""

from typing import Optional

from pydantic import Field

from letta.schemas.letta_base import OrmMetadataBase


class WorldInfoInjectionStateBase(OrmMetadataBase):
    """Base schema for World Info injection states."""

    __id_prefix__ = "wiis"

    organization_id: str = Field(..., description="The organization this injection state belongs to.")
    world_info_entry_id: str = Field(..., description="The ID of the World Info entry.")
    agent_id: str = Field(..., description="The ID of the agent.")
    current_cooldown: Optional[int] = Field(None, description="Remaining cooldown runs. NULL or 0 means no cooldown.")
    current_expiration: Optional[int] = Field(None, description="Remaining runs before removal. NULL means never expire (persist indefinitely). 0 means expired (should be removed).")
    cooldown_setting: int = Field(..., description="Cooldown setting from WorldInfoEntry (cached).")
    expiration_setting: int = Field(..., description="Expiration setting from WorldInfoEntry (cached).")


class WorldInfoInjectionState(WorldInfoInjectionStateBase):
    """World Info injection state schema."""

    id: str = Field(..., description="The unique identifier of the injection state.")

