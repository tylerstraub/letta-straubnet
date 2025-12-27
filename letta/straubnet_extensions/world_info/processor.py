"""World Info Processor - Keyword-based prompt injection processor with cooldown and expiration."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from letta.log import get_logger
from letta.schemas.enums import MessageRole
from letta.schemas.message import MessageCreate
from letta.schemas.letta_message_content import TextContent
from letta.server.db import db_registry
from letta.services.agent_manager import AgentManager
from letta.services.message_manager import MessageManager

from straubnet_extensions.message_processors.protocol import MessageProcessor
from straubnet_extensions.world_info.matcher import match_keywords
from straubnet_extensions.world_info.scanner import extract_text_from_message
from straubnet_extensions.world_info.storage import get_world_info_entries

logger = get_logger(__name__)

# Thread pool executor for running async database queries from sync context
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world-info-db")


class WorldInfoProcessor(MessageProcessor):
    """
    World Info processor that injects system messages based on keyword matching
    with cooldown and expiration support.

    This processor:
    1. Updates injection states - decrements counters for all active injections
    2. Removes expired entries - deletes messages that hit expiration=0
    3. Cleans up - deletes state records that are complete
    4. Queries World Info entries from the database for the organization/agent
    5. Extracts text from incoming messages
    6. Matches keywords against the text
    7. Injects matched entries as system messages (if not in cooldown), ordered by insertion_order
       (lower values first = further from user, higher values last = closer to user)
    """

    def __init__(self):
        """Initialize processor with managers."""
        self.agent_manager = AgentManager()
        self.message_manager = MessageManager()

    def process(
        self,
        messages: List[MessageCreate],
        context: dict,
    ) -> List[MessageCreate]:
        """
        Process messages by injecting World Info entries based on keyword matching.

        Args:
            messages: List of MessageCreate objects to process
            context: Context dictionary containing:
                - agent_id: The agent ID
                - actor: The user making the request (has organization_id)
                - run_id: The current run ID (required for cooldown/expiration tracking)
                - server: Optional server object

        Returns:
            Modified message list with World Info entries injected as system messages
        """
        try:
            # Extract context
            agent_id = context.get("agent_id")
            actor = context.get("actor")
            run_id = context.get("run_id")
            
            if not actor:
                logger.warning("[World Info] No actor in context, skipping World Info processing")
                return messages

            organization_id = actor.organization_id
            if not organization_id:
                logger.warning("[World Info] Actor has no organization_id, skipping World Info processing")
                return messages

            # Step 1: UPDATE STATE - decrement counters for all active injections
            if run_id:
                self._update_injection_states(agent_id, run_id, actor)
            
            # Step 2: REMOVE EXPIRED - delete messages that hit expiration=0
            self._remove_expired_entries(agent_id, actor)
            
            # Step 3: CLEAN UP - delete state records that are complete
            self._cleanup_completed_states(agent_id, actor)
            
            # Get World Info entries from database (async operation)
            entries = self._get_entries_sync(organization_id, agent_id)
            
            if not entries:
                logger.debug(f"[World Info] No entries found for organization {organization_id}, agent {agent_id}")
                return messages

            # Extract text from all messages for keyword matching
            combined_text = self._extract_combined_text(messages)
            
            if not combined_text:
                logger.debug("[World Info] No text content in messages, skipping keyword matching")
                return messages

            # Step 4: MATCH KEYWORDS - find matching WorldInfoEntries
            matched_entries = self._find_matching_entries(entries, combined_text)

            if not matched_entries:
                logger.debug("[World Info] No entries matched keywords in message text")
                return messages

            # Step 5: INJECT - inject entries not in cooldown
            system_messages = self._inject_entries(matched_entries, agent_id, run_id, actor)

            if not system_messages:
                logger.debug("[World Info] No entries injected (all in cooldown)")
                return messages

            # Inject system messages at the beginning (before user messages)
            # System messages should come first in the context
            logger.info(f"[World Info] Injecting {len(system_messages)} World Info entries as system messages")
            return system_messages + messages

        except Exception as e:
            logger.error(f"[World Info] Error processing messages: {e}", exc_info=True)
            # On error, return original messages unchanged
            return messages
    
    def _update_injection_states(self, agent_id: str, run_id: str, actor) -> None:
        """
        Decrement counters for all active states where last_processed_run_id != run_id.
        
        Args:
            agent_id: The agent ID
            run_id: The current run ID
            actor: The user for permission checking
        """
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        
        manager = WorldInfoInjectionStateManager()
        
        # Get all injection states for this agent
        states = manager.get_injection_states_by_agent(agent_id, actor=actor)
        
        for state in states:
            if state.last_processed_run_id != run_id:
                # Decrement counters
                new_cooldown = None
                new_expiration = None
                
                if state.current_cooldown is not None and state.current_cooldown > 0:
                    new_cooldown = state.current_cooldown - 1
                    logger.debug(f"[World Info] State {state.id}: cooldown decremented from {state.current_cooldown} to {new_cooldown}")
                
                if state.current_expiration is not None and state.current_expiration > 0:
                    new_expiration = state.current_expiration - 1
                    logger.debug(f"[World Info] State {state.id}: expiration decremented from {state.current_expiration} to {new_expiration}")
                
                # Update state with new counters and last_processed_run_id
                manager.update_injection_state(
                    injection_state_id=state.id,
                    current_cooldown=new_cooldown,
                    current_expiration=new_expiration,
                    last_processed_run_id=run_id,
                    actor=actor
                )
    
    def _remove_expired_entries(self, agent_id: str, actor) -> None:
        """
        Remove system messages where expiration hit 0.
        
        Args:
            agent_id: The agent ID
            actor: The user for permission checking
        """
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        from letta.orm.world_info_injection_state import WorldInfoInjectionState
        from letta.db import db
        from sqlalchemy import and_
        
        manager = WorldInfoInjectionStateManager()
        
        # Find expired states (expiration = 0)
        with db.async_session() as session:
            expired_states = session.query(WorldInfoInjectionState).filter(
                WorldInfoInjectionState.agent_id == agent_id,
                WorldInfoInjectionState.current_expiration == 0,
                WorldInfoInjectionState.injected_message_id.isnot(None)
            ).all()
            
            for state in expired_states:
                try:
                    # Get agent's current message_ids
                    agent = self.agent_manager.get_agent_by_id(agent_id=agent_id, actor=actor)
                    
                    # Remove message from context if still present
                    if state.injected_message_id in agent.message_ids:
                        new_message_ids = [msg_id for msg_id in agent.message_ids if msg_id != state.injected_message_id]
                        
                        # Update agent's message_ids
                        self.agent_manager.update_message_ids(
                            agent_id=agent_id,
                            message_ids=new_message_ids,
                            actor=actor
                        )
                        logger.info(f"[World Info] Removed expired injection message {state.injected_message_id} from context")
                    else:
                        logger.debug(f"[World Info] Message {state.injected_message_id} already removed from context")
                    
                    # Clear injected_message_id from state
                    manager.update_injection_state(
                        injection_state_id=state.id,
                        injected_message_id=None,
                        actor=actor
                    )
                except Exception as e:
                    logger.error(f"[World Info] Error removing expired entry {state.id}: {e}", exc_info=True)
    
    def _cleanup_completed_states(self, agent_id: str, actor) -> None:
        """
        Delete state records that are done (both cooldown and expiration at 0 or None).
        
        Args:
            agent_id: The agent ID
            actor: The user for permission checking
        """
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        
        manager = WorldInfoInjectionStateManager()
        
        # Get all states for this agent
        states = manager.get_injection_states_by_agent(agent_id, actor=actor)
        
        for state in states:
            # Check if state is complete (both counters at 0 or None)
            cooldown_complete = state.current_cooldown is None or state.current_cooldown == 0
            expiration_complete = state.current_expiration is None or state.current_expiration == 0
            
            if cooldown_complete and expiration_complete:
                # Also ensure message_id is cleared (already removed from context)
                if state.injected_message_id is None:
                    logger.debug(f"[World Info] Deleting completed state {state.id}")
                    manager.delete_injection_state(state.id, actor=actor)
                else:
                    logger.debug(f"[World Info] State {state.id} has completed but message_id still set, waiting for removal")
    
    def _should_inject(self, entry, agent_id: str, actor) -> bool:
        """
        Check if entry should be injected (not in cooldown).
        
        Args:
            entry: WorldInfoEntry to check
            agent_id: The agent ID
            actor: The user for permission checking
            
        Returns:
            True if entry should be injected, False otherwise
        """
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        
        # If both cooldown and expiration are 0/None, inject freely (current behavior)
        entry_cooldown = entry.cooldown or 0
        entry_expiration = entry.expiration or 0
        if entry_cooldown == 0 and entry_expiration == 0:
            return True
        
        # Check if already injected and still in cooldown
        manager = WorldInfoInjectionStateManager()
        existing_state = manager.get_injection_state_by_entry(entry.id, agent_id, actor=actor)
        
        if existing_state:
            # Check if cooldown is still active
            if existing_state.current_cooldown is not None and existing_state.current_cooldown > 0:
                logger.debug(f"[World Info] Entry {entry.id} is in cooldown ({existing_state.current_cooldown} runs remaining)")
                return False
            
            # Check if still in context (expiration not complete)
            if existing_state.current_expiration is not None and existing_state.current_expiration > 0:
                logger.debug(f"[World Info] Entry {entry.id} still in context ({existing_state.current_expiration} runs remaining)")
                return False
        
            # Cooldown complete but state record exists - delete it and allow re-injection
            if existing_state.current_cooldown is None or existing_state.current_cooldown == 0:
                logger.debug(f"[World Info] Entry {entry.id} cooldown complete, removing old state and allowing re-injection")
                manager.delete_injection_state(existing_state.id, actor=actor)
        
        return True
    
    def _inject_entries(
        self, entries: List, agent_id: str, run_id: Optional[str], actor
    ) -> List[MessageCreate]:
        """
        Inject entries as system messages and create state records if needed.
        
        Args:
            entries: List of WorldInfoEntry objects to inject (already ordered by insertion_order ASC)
            agent_id: The agent ID
            run_id: The current run ID
            actor: The user for permission checking
            
        Returns:
            List of system messages to inject
        """
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        
        manager = WorldInfoInjectionStateManager()
        system_messages = []
        
        for entry in entries:
            # Check if should inject
            if not self._should_inject(entry, agent_id, actor):
                continue
            
            # Create system message
            system_message = MessageCreate(
                role=MessageRole.system,
                content=[TextContent(text=entry.content)]
            )
            system_messages.append(system_message)
            
            # Create state record if needed
            entry_cooldown = entry.cooldown or 0
            entry_expiration = entry.expiration or 0
            
            if entry_cooldown > 0 or entry_expiration > 0:
                state = manager.create_injection_state(
                    world_info_entry_id=entry.id,
                    agent_id=agent_id,
                    current_cooldown=entry_cooldown if entry_cooldown > 0 else None,
                    current_expiration=entry_expiration if entry_expiration > 0 else None,
                    cooldown_setting=entry_cooldown,
                    expiration_setting=entry_expiration,
                    last_processed_run_id=run_id,
                    actor=actor
                )
                logger.info(
                    f"[World Info] Created injection state for entry {entry.id}: "
                    f"cooldown={entry_cooldown}, expiration={entry_expiration}"
                )
        
        return system_messages
    
    def _create_system_messages(self, entries: List) -> List[MessageCreate]:
        """
        Create system messages from World Info entries.
        
        This is now handled by _inject_entries, kept for backward compatibility.
        
        Args:
            entries: List of WorldInfoEntry objects (already ordered by insertion_order ASC)
                     Lower numbers first (injected earlier, further from user), higher numbers last (closer to user)
        
        Returns:
            List of MessageCreate objects with role=system
        """
        system_messages = []
        for entry in entries:
            system_message = MessageCreate(
                role=MessageRole.system,
                content=[TextContent(text=entry.content)],
            )
            system_messages.append(system_message)
            logger.debug(f"[World Info] Created system message from entry '{entry.id}' (insertion_order={entry.insertion_order})")
        
        return system_messages

    def _get_entries_sync(self, organization_id: str, agent_id: str | None) -> List:
        """
        Get World Info entries from database (synchronous wrapper for async operation).

        Since process() is sync but database queries are async, we need to handle
        the event loop. We use a thread pool executor to run the async query in a
        separate thread, which avoids deadlocks when called from an async context.

        This pattern is necessary because:
        - MessageProcessor.process() is a synchronous interface (required by the protocol)
        - Database queries in Letta are async (using SQLAlchemy async)
        - We're called from an async context (FastAPI endpoint), so there's a running event loop
        - Using run_coroutine_threadsafe() can deadlock if called from the same thread
        - Solution: Run the async query in a separate thread using ThreadPoolExecutor

        Args:
            organization_id: The organization ID
            agent_id: Optional agent ID

        Returns:
            List of WorldInfoEntry objects
        """
        try:
            # Run the async query in a separate thread to avoid deadlock
            # This works even when called from an async context
            future = _executor.submit(
                lambda: asyncio.run(self._get_entries_async(organization_id, agent_id))
            )
            # Wait for result with timeout (10 seconds - increased from 5)
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return []
        except Exception as e:
            logger.error(f"[World Info] Error getting entries from database: {e}", exc_info=True)
            return []

    async def _get_entries_async(self, organization_id: str, agent_id: str | None) -> List:
        """
        Async helper to get entries from database.

        Args:
            organization_id: The organization ID
            agent_id: Optional agent ID

        Returns:
            List of WorldInfoEntry objects
        """
        async with db_registry.async_session() as session:
            return await get_world_info_entries(session, organization_id, agent_id)

    def _extract_combined_text(self, messages: List[MessageCreate]) -> str:
        """
        Extract and combine text from all messages.

        Args:
            messages: List of MessageCreate objects

        Returns:
            Combined text from all messages
        """
        text_parts = []
        for message in messages:
            text = extract_text_from_message(message)
            if text:
                text_parts.append(text)
        
        return " ".join(text_parts)

    def _find_matching_entries(self, entries: List, text: str) -> List:
        """
        Find entries that match keywords in the text.

        Args:
            entries: List of WorldInfoEntry objects
            text: Text to match against

        Returns:
            List of matching WorldInfoEntry objects (ordered by insertion_order ASC)
            Lower numbers first (injected earlier, further from user), higher numbers last (closer to user)
        """
        matched = []
        for entry in entries:
            # Match keywords (case sensitivity and whole word matching from entry settings)
            if match_keywords(
                text,
                entry.keywords,
                case_sensitive=entry.case_sensitive,
                match_whole_words=entry.match_whole_words,
            ):
                matched.append(entry)
                logger.debug(
                    f"[World Info] Entry '{entry.id}' matched keywords {entry.keywords} "
                    f"(case_sensitive={entry.case_sensitive}, match_whole_words={entry.match_whole_words})"
                )
        
        return matched

    def _create_system_messages(self, entries: List) -> List[MessageCreate]:
        """
        Create system messages from World Info entries.

        Args:
            entries: List of WorldInfoEntry objects (already ordered by insertion_order ASC)
                     Lower numbers first (injected earlier, further from user), higher numbers last (closer to user)

        Returns:
            List of MessageCreate objects with role=system
        """
        system_messages = []
        for entry in entries:
            system_message = MessageCreate(
                role=MessageRole.system,
                content=entry.content,
            )
            system_messages.append(system_message)
            logger.debug(f"[World Info] Created system message from entry '{entry.id}' (insertion_order={entry.insertion_order})")
        
        return system_messages

