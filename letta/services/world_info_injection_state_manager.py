"""
Manager for World Info injection state operations.
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import select, and_, or_

from letta.log import get_logger
from letta.orm import WorldInfoInjectionState as WorldInfoInjectionStateModel
from letta.orm.errors import NoResultFound
from letta.schemas.world_info_injection_state import WorldInfoInjectionState as PydanticWorldInfoInjectionState
from letta.server.db import db_registry

if TYPE_CHECKING:
    from letta.schemas.user import User

logger = get_logger(__name__)


class WorldInfoInjectionStateManager:
    """
    Manages World Info injection state CRUD operations.
    """

    def __init__(self):
        """Initialize the manager."""
        pass

    async def create_injection_state(
        self,
        world_info_entry_id: str,
        agent_id: str,
        current_cooldown: Optional[int] = None,
        current_expiration: Optional[int] = None,
        cooldown_setting: int = 0,
        expiration_setting: int = 0,
        organization_id: str = "",
        actor: Optional["User"] = None,
    ) -> PydanticWorldInfoInjectionState:
        """
        Create a new injection state record.

        Args:
            world_info_entry_id: ID of the World Info entry
            agent_id: ID of the agent
            current_cooldown: Current cooldown counter (None = 0)
            current_expiration: Current expiration counter (None = 0)
            cooldown_setting: Cooldown setting from entry
            expiration_setting: Expiration setting from entry
            organization_id: Organization ID
            actor: Optional user creating the record (for _created_by_id/_last_updated_by_id tracking)

        Returns:
            Created injection state
        """
        async with db_registry.async_session() as session:
            # Check if state already exists (unique constraint)
            stmt = select(WorldInfoInjectionStateModel).where(
                and_(
                    WorldInfoInjectionStateModel.world_info_entry_id == world_info_entry_id,
                    WorldInfoInjectionStateModel.agent_id == agent_id,
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing state with new values (reset counters for new activation)
                existing.current_cooldown = current_cooldown if current_cooldown is not None and current_cooldown > 0 else None
                existing.current_expiration = current_expiration if current_expiration is not None and current_expiration > 0 else None
                existing.cooldown_setting = cooldown_setting
                existing.expiration_setting = expiration_setting
                await existing.update_async(session, actor=actor)
                await session.refresh(existing)
                return existing.to_pydantic()
            
            state = WorldInfoInjectionStateModel(
                world_info_entry_id=world_info_entry_id,
                agent_id=agent_id,
                current_cooldown=current_cooldown,
                current_expiration=current_expiration,
                cooldown_setting=cooldown_setting,
                expiration_setting=expiration_setting,
                organization_id=organization_id,
            )

            await state.create_async(session, actor=actor)
            await session.refresh(state)
            return state.to_pydantic()

    async def get_injection_states_by_agent(self, agent_id: str) -> List[PydanticWorldInfoInjectionState]:
        """
        Get all injection states for a specific agent.

        Args:
            agent_id: ID of the agent

        Returns:
            List of injection states for the agent
        """
        async with db_registry.async_session() as session:
            stmt = select(WorldInfoInjectionStateModel).where(
                WorldInfoInjectionStateModel.agent_id == agent_id
            )
            result = await session.execute(stmt)
            states = result.scalars().all()
            return [state.to_pydantic() for state in states]

    async def get_injection_state_by_entry(
        self, world_info_entry_id: str, agent_id: str
    ) -> Optional[PydanticWorldInfoInjectionState]:
        """
        Get injection state for a specific World Info entry and agent.

        Args:
            world_info_entry_id: ID of the World Info entry
            agent_id: ID of the agent

        Returns:
            Injection state if found, None otherwise
        """
        async with db_registry.async_session() as session:
            stmt = select(WorldInfoInjectionStateModel).where(
                and_(
                    WorldInfoInjectionStateModel.world_info_entry_id == world_info_entry_id,
                    WorldInfoInjectionStateModel.agent_id == agent_id,
                )
            )
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()
            return state.to_pydantic() if state else None

    async def update_injection_state(
        self,
        injection_state_id: str,
        current_cooldown: Optional[int] = None,
        current_expiration: Optional[int] = None,
        actor: Optional["User"] = None,
    ) -> Optional[PydanticWorldInfoInjectionState]:
        """
        Update an injection state record.

        Args:
            injection_state_id: ID of the injection state
            current_cooldown: New cooldown counter value
            current_expiration: New expiration counter value
            actor: Optional user updating the record (for _last_updated_by_id tracking)

        Returns:
            Updated injection state if found, None otherwise
        """
        async with db_registry.async_session() as session:
            state = await WorldInfoInjectionStateModel.read_async(db_session=session, identifier=injection_state_id)

            if current_cooldown is not None:
                # Preserve 0 as 0 (cooldown complete), only use None when there's no cooldown setting
                state.current_cooldown = current_cooldown
            if current_expiration is not None:
                # Preserve 0 as 0 (expiration complete), only use None when there's no expiration setting
                state.current_expiration = current_expiration

            await state.update_async(session, actor=actor)
            return state.to_pydantic()

    async def delete_injection_state(self, injection_state_id: str):
        """
        Delete an injection state record.

        Args:
            injection_state_id: ID of the injection state
        """
        async with db_registry.async_session() as session:
            state = await WorldInfoInjectionStateModel.read_async(db_session=session, identifier=injection_state_id)
            await state.hard_delete_async(session)

    async def delete_completed_states(self, agent_id: str):
        """
        Delete all completed injection states for an agent.

        A state is considered complete when:
        - Cooldown is None or 0 (no cooldown)
        - AND expiration is 0 (expired, not None - None means never expire)

        Args:
            agent_id: ID of the agent
        """
        async with db_registry.async_session() as session:
            stmt = select(WorldInfoInjectionStateModel).where(
                WorldInfoInjectionStateModel.agent_id == agent_id
            )
            # Only delete states where expiration=0 (expired), not None (never expire)
            stmt = stmt.where(
                and_(
                    WorldInfoInjectionStateModel.current_expiration == 0,
                    or_(
                        WorldInfoInjectionStateModel.current_cooldown == 0,
                        WorldInfoInjectionStateModel.current_cooldown.is_(None),
                    ),
                )
            )
            result = await session.execute(stmt)
            states = result.scalars().all()
            
            for state in states:
                await state.hard_delete_async(session)
