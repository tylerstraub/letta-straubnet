"""
Schemas for World Info entry state responses.
"""

from typing import Optional

from pydantic import BaseModel, Field

from letta.schemas.world_info_entry import WorldInfoEntry


class WorldInfoEntryState(BaseModel):
    """Current runtime state for a World Info entry."""

    current_cooldown: Optional[int] = Field(
        None, description="Remaining cooldown runs. None if not active or no cooldown."
    )
    current_expiration: Optional[int] = Field(
        None, description="Remaining runs before removal. None if not active or no expiration."
    )
    is_active: bool = Field(..., description="Whether this entry is currently active (has injection state).")
    cooldown_setting: Optional[int] = Field(
        None, description="Cooldown setting from entry (cached). None if not active."
    )
    expiration_setting: Optional[int] = Field(
        None, description="Expiration setting from entry (cached). None if not active."
    )


class WorldInfoEntryWithState(BaseModel):
    """World Info entry with its current runtime state."""

    entry: WorldInfoEntry = Field(..., description="The World Info entry.")
    state: Optional[WorldInfoEntryState] = Field(
        None, description="Current runtime state. None if entry is not currently active."
    )


class WorldInfoEntriesStateResponse(BaseModel):
    """Response containing World Info entries with their runtime states."""

    entries: list[WorldInfoEntryWithState] = Field(
        ..., description="List of entries with their current state information."
    )

