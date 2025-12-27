"""
Manager for World Info injection state operations.
"""

from typing import List, Optional

from letta.log import get_logger
from letta.orm import WorldInfoInjectionState as ORMWorldInfoInjectionState
from letta.orm.mixins import OrganizationMixin
from letta.orm.sqlalchemy_base import SqlalchemyBase
from letta.schemas import LettaPaginationParams
from letta.schemas.world_info_injection_state import WorldInfoInjectionState as PydanticWorldInfoInjectionState

logger = get_logger(__name__)


class WorldInfoInjectionStateManager(OrganizationMixin):
    """
    Manages World Info injection state CRUD operations.
    """

    def __init__(self, session: Optional[object] = None):
        """Initialize the manager with an optional database session."""
        self.session = session
        self.model = ORMWorldInfoInjectionState
        self.pydantic_model = PydanticWorldInfoInjectionState

    def create_injection_state(
        self,
        world_info_entry_id: str,
        agent_id: str,
        current_cooldown: Optional[int] = None,
        current_expiration: Optional[int] = None,
        cooldown_setting: int = 0,
        expiration_setting: int = 0,
        last_processed_run_id: Optional[str] = None,
        actor=None,
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
            last_processed_run_id: Last run processed
            actor: User performing the action

        Returns:
            Created injection state
        """
        import uuid
        from letta.schemas.letta_user import User

        from letta.orm.sqlalchemy_base import SqlalchemyBase

        if actor is None:
            from letta.schemas.letta_user import User
            actor = User(id="", organization_id="", created_by_id="")

        obj = self.model(
            id=f"wiis-{uuid.uuid4()}",
            world_info_entry_id=world_info_entry_id,
            agent_id=agent_id,
            current_cooldown=current_cooldown,
            current_expiration=current_expiration,
            cooldown_setting=cooldown_setting,
            expiration_setting=expiration_setting,
            last_processed_run_id=last_processed_run_id,
            _created_by_id=actor.id if actor else None,
            organization_id=actor.organization_id if actor else "",
        )

        if self.session:
            self.session.add(obj)
            self.session.commit()
            self.session.refresh(obj)
        else:
            from letta.db import db
            db.session.add(obj)
            db.session.commit()
            db.session.refresh(obj)

        return self.pydantic_model.model_validate(obj)

    def get_injection_states_by_agent(
        self, agent_id: str, actor=None
    ) -> List[PydanticWorldInfoInjectionState]:
        """
        Get all injection states for a specific agent.

        Args:
            agent_id: ID of the agent
            actor: User for permission checking

        Returns:
            List of injection states for the agent
        """
        query = self.session.query(self.model).filter_by(agent_id=agent_id) if self.session else self.model.query.filter_by(agent_id=agent_id)

        return [self.pydantic_model.model_validate(state) for state in query.all()]

    def get_injection_state_by_entry(
        self, world_info_entry_id: str, agent_id: str, actor=None
    ) -> Optional[PydanticWorldInfoInjectionState]:
        """
        Get injection state for a specific World Info entry and agent.

        Args:
            world_info_entry_id: ID of the World Info entry
            agent_id: ID of the agent
            actor: User for permission checking

        Returns:
            Injection state if found, None otherwise
        """
        query = (
            self.session.query(self.model)
            .filter_by(world_info_entry_id=world_info_entry_id, agent_id=agent_id)
            if self.session
            else self.model.query.filter_by(world_info_entry_id=world_info_entry_id, agent_id=agent_id)
        )

        result = query.first()
        return self.pydantic_model.model_validate(result) if result else None

    def update_injection_state(
        self,
        injection_state_id: str,
        current_cooldown: Optional[int] = None,
        current_expiration: Optional[int] = None,
        last_processed_run_id: Optional[str] = None,
        injected_message_id: Optional[str] = None,
        actor=None,
    ) -> Optional[PydanticWorldInfoInjectionState]:
        """
        Update an injection state record.

        Args:
            injection_state_id: ID of the injection state
            current_cooldown: New cooldown counter value
            current_expiration: New expiration counter value
            last_processed_run_id: New last processed run ID
            injected_message_id: New injected message ID
            actor: User for permission checking

        Returns:
            Updated injection state if found, None otherwise
        """
        query = (
            self.session.query(self.model).filter_by(id=injection_state_id)
            if self.session
            else self.model.query.filter_by(id=injection_state_id)
        )

        state = query.first()
        if not state:
            return None

        if current_cooldown is not None:
            state.current_cooldown = current_cooldown if current_cooldown > 0 else None
        if current_expiration is not None:
            state.current_expiration = current_expiration if current_expiration > 0 else None
        if last_processed_run_id is not None:
            state.last_processed_run_id = last_processed_run_id
        if injected_message_id is not None:
            state.injected_message_id = injected_message_id

        if actor:
            state._last_updated_by_id = actor.id

        (self.session if self.session else SqlalchemyBase.session).commit()
        return self.pydantic_model.model_validate(state)

    def delete_injection_state(self, injection_state_id: str, actor=None):
        """
        Delete an injection state record.

        Args:
            injection_state_id: ID of the injection state
            actor: User for permission checking
        """
        query = (
            self.session.query(self.model).filter_by(id=injection_state_id)
            if self.session
            else self.model.query.filter_by(id=injection_state_id)
        )

        state = query.first()
        if state:
            (self.session if self.session else SqlalchemyBase.session).delete(state)
            (self.session if self.session else SqlalchemyBase.session).commit()

    def delete_completed_states(self, agent_id: str, actor=None):
        """
        Delete all completed injection states for an agent.

        A state is considered complete if both cooldown and expiration are 0 or None.

        Args:
            agent_id: ID of the agent
            actor: User for permission checking
        """
        from sqlalchemy import and_, or_

        query = (
            self.session.query(self.model).filter_by(agent_id=agent_id)
            if self.session
            else self.model.query.filter_by(agent_id=agent_id)
        )

        query = query.filter(
            or_(
                and_(
                    self.model.current_cooldown == 0,
                    self.model.current_expiration == 0,
                ),
                and_(
                    self.model.current_cooldown.is_(None),
                    self.model.current_expiration == 0,
                ),
                and_(
                    self.model.current_cooldown == 0,
                    self.model.current_expiration.is_(None),
                ),
                and_(
                    self.model.current_cooldown.is_(None),
                    self.model.current_expiration.is_(None),
                ),
            )
        )

        for state in query.all():
            (self.session if self.session else SqlalchemyBase.session).delete(state)

        (self.session if self.session else SqlalchemyBase.session).commit()

