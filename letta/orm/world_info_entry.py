"""
ORM model for World Info entries.

World Info entries are used for keyword-based prompt injection,
similar to SillyTavern's World Info / Lorebook system.
"""

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from letta.orm.mixins import OrganizationMixin
from letta.orm.sqlalchemy_base import SqlalchemyBase
from letta.schemas.world_info_entry import WorldInfoEntry as PydanticWorldInfoEntry


class WorldInfoEntry(SqlalchemyBase, OrganizationMixin):
    """ORM model for World Info entries."""

    __pydantic_model__ = PydanticWorldInfoEntry
    __tablename__ = "world_info_entries"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: f"world-info-entry-{uuid.uuid4()}",
        doc="Unique identifier for the World Info entry.",
    )

    keywords: Mapped[List[str]] = mapped_column(
        JSON,
        doc="List of keywords or regex patterns that trigger this entry.",
    )

    content: Mapped[str] = mapped_column(
        String,
        doc="The content to inject when keywords are matched.",
    )

    insertion_order: Mapped[int] = mapped_column(
        Integer,
        default=100,
        doc="Priority/order for insertion. Higher numbers are inserted later (closer to end of context).",
    )

    agent_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        doc="Optional agent ID. If None, entry applies globally to all agents in the organization.",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="Whether this entry is enabled and should be checked.",
    )

    case_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Whether keyword matching should be case-sensitive.",
    )

    match_whole_words: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="Whether keywords should match whole words only (word boundaries).",
    )

    scan_depth: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="How many messages back to scan. If None, uses global default.",
    )

