"""
ORM model for World Info injection states.

World Info injection states track ephemeral state for active World Info entries,
including cooldown counters and expiration timers.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from letta.orm.mixins import OrganizationMixin
from letta.orm.sqlalchemy_base import SqlalchemyBase
from letta.schemas.world_info_injection_state import WorldInfoInjectionState as PydanticWorldInfoInjectionState

if TYPE_CHECKING:
    from letta.orm.agent import Agent
    from letta.orm.organization import Organization
    from letta.orm.world_info_entry import WorldInfoEntry


class WorldInfoInjectionState(SqlalchemyBase, OrganizationMixin):
    """ORM model for World Info injection state tracking."""

    __pydantic_model__ = PydanticWorldInfoInjectionState
    __tablename__ = "world_info_injection_states"
    __table_args__ = (
        Index("ix_world_info_injection_states_entry_agent", "world_info_entry_id", "agent_id"),
        UniqueConstraint("world_info_entry_id", "agent_id", name="uq_world_info_entry_agent"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: f"wiis-{uuid.uuid4()}",
        doc="Unique identifier for the injection state.",
    )

    # Foreign keys
    world_info_entry_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("world_info_entries.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID of the World Info entry this state tracks.",
    )

    agent_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID of the agent this state is for.",
    )

    # Counters
    current_cooldown: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Remaining cooldown runs. NULL or 0 means no cooldown (can inject).",
    )

    current_expiration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Remaining runs before removal from context. NULL means never expire (persist indefinitely). 0 means expired (should be removed).",
    )

    # Cached configuration (avoid JOINs during hot path)
    cooldown_setting: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Cooldown setting from WorldInfoEntry (cached).",
    )

    expiration_setting: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Expiration setting from WorldInfoEntry (cached).",
    )

    # Note: created_at and updated_at are provided automatically by SqlalchemyBase
    # via CommonSqlalchemyMetaMixins with server_default=func.now()

