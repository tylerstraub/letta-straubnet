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
        from letta.services.world_info_injection_state_manager import WorldInfoInjectionStateManager
        
        self.agent_manager = AgentManager()
        self.message_manager = MessageManager()
        self.injection_state_manager = WorldInfoInjectionStateManager()

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
            
            logger.debug(f"[World Info] Processing messages for agent {agent_id}, run_id={run_id}")
            
            if not actor:
                logger.warning("[World Info] No actor in context, skipping World Info processing")
                return messages

            organization_id = actor.organization_id
            if not organization_id:
                logger.warning("[World Info] Actor has no organization_id, skipping World Info processing")
                return messages

            # Step 1: UPDATE STATE - decrement counters for all active injections
            self._update_injection_states(agent_id, run_id, actor)
            
            # Step 2: REMOVE EXPIRED - delete messages that hit expiration=0
            self._remove_expired_entries(agent_id, actor)
            
            # Step 3: CLEAN UP - delete state records that are complete
            self._cleanup_completed_states(agent_id, actor)
            
            # Get World Info entries from database (async operation)
            entries = self._get_entries_sync(organization_id, agent_id)
            logger.debug(f"[World Info] Retrieved {len(entries)} entries from database for org {organization_id}, agent {agent_id}")
            
            if not entries:
                logger.debug(f"[World Info] No entries found for organization {organization_id}, agent {agent_id}")
                return messages

            # Extract text from all messages for keyword matching
            combined_text = self._extract_combined_text(messages)
            logger.debug(f"[World Info] Extracted text: {combined_text[:100]}..." if combined_text else "[World Info] No text extracted")
            
            if not combined_text:
                logger.debug("[World Info] No text content in messages, skipping keyword matching")
                return messages

            # Step 4: MATCH KEYWORDS - find matching WorldInfoEntries
            matched_entries = self._find_matching_entries(entries, combined_text)
            logger.debug(f"[World Info] Found {len(matched_entries)} matching entries")

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
        Decrement counters for all active injection states.
        
        Args:
            agent_id: The agent ID
            run_id: The current run ID (unused, kept for API compatibility)
            actor: The user for permission checking
        """
        # Get all injection states for this agent
        states = self._get_injection_states_sync(agent_id)
        logger.debug(f"[World Info] Found {len(states)} injection states for agent {agent_id}")
        
        for state in states:
            logger.debug(f"[World Info] Checking state {state.id}: cooldown={state.current_cooldown}, expiration={state.current_expiration}")
            # Decrement counters
            new_cooldown = None
            new_expiration = None
            
            if state.current_cooldown is not None and state.current_cooldown > 0:
                new_cooldown = state.current_cooldown - 1
                logger.debug(f"[World Info] State {state.id}: cooldown decremented from {state.current_cooldown} to {new_cooldown}")
            
            if state.current_expiration is not None and state.current_expiration > 0:
                new_expiration = state.current_expiration - 1
                logger.debug(f"[World Info] State {state.id}: expiration decremented from {state.current_expiration} to {new_expiration}")
            
            # Update state with new counters
            self._update_injection_state_sync(
                self.injection_state_manager, state.id,
                current_cooldown=new_cooldown,
                current_expiration=new_expiration,
                actor=actor
            )
    
    def _remove_expired_entries(self, agent_id: str, actor) -> None:
        """
        Remove system messages where expiration hit 0.
        
        Note: expiration=None means "never expire" (persist indefinitely), so only
        expiration=0 means expired and should be removed.
        
        Args:
            agent_id: The agent ID
            actor: The user for permission checking
        """
        # Get all injection states for this agent
        states = self._get_injection_states_sync(agent_id)
        logger.debug(f"[World Info] Checking {len(states)} states for expired entries")
        
        # Filter for expired states (expiration = 0 means expired, None means never expire)
        expired_states = [
            state for state in states
            if state.current_expiration == 0
        ]
        logger.debug(f"[World Info] Found {len(expired_states)} expired states (expiration is 0, None means never expire)")
        
        if not expired_states:
            return
        
        # Get agent's current message_ids and fetch the messages
        agent = self._get_agent_by_id_sync(agent_id, actor)
        if not agent or not agent.message_ids:
            logger.debug(f"[World Info] Agent {agent_id} has no messages in context")
            return
        
        # Fetch all messages to match by name field
        messages = self._get_messages_by_ids_sync(agent.message_ids, actor)
        logger.debug(f"[World Info] Fetched {len(messages)} messages from agent context")
        message_by_name = {msg.name: msg for msg in messages if msg.name and msg.name.startswith("world-info-")}
        logger.debug(f"[World Info] Found {len(message_by_name)} messages with world-info name markers: {list(message_by_name.keys())}")
        
        # Process each expired state
        message_ids_to_remove = []
        for state in expired_states:
            try:
                # Match message by name field (format: "world-info-{entry.id}")
                expected_name = f"world-info-{state.world_info_entry_id}"
                matched_message = message_by_name.get(expected_name)
                
                if matched_message:
                    message_ids_to_remove.append(matched_message.id)
                    logger.debug(f"[World Info] Found expired message {matched_message.id} for entry {state.world_info_entry_id} (name={expected_name})")
                else:
                    logger.debug(f"[World Info] No message found with name {expected_name} for expired state {state.id}")
                    
            except Exception as e:
                logger.error(f"[World Info] Error processing expired state {state.id}: {e}", exc_info=True)
        
        # Remove all matched messages from context in one update
        if message_ids_to_remove:
            new_message_ids = [msg_id for msg_id in agent.message_ids if msg_id not in message_ids_to_remove]
            
            # Update agent's message_ids
            self._update_message_ids_sync(agent_id, new_message_ids, actor)
            logger.info(f"[World Info] Removed {len(message_ids_to_remove)} expired injection messages from context: {message_ids_to_remove}")
    
    def _is_state_complete(self, state) -> bool:
        """
        Check if a state is complete (can be deleted).
        
        A state is complete when:
        - Cooldown is None or 0 (no cooldown = complete)
        - AND expiration is 0 (expired, not None - None means never expire = not complete)
        
        Args:
            state: Injection state to check
            
        Returns:
            True if state is complete and can be deleted, False otherwise
        """
        # Cooldown complete: None or 0 means no cooldown (complete)
        cooldown_complete = state.current_cooldown is None or state.current_cooldown == 0
        
        # Expiration complete: Only 0 means expired (complete). None means never expire (not complete)
        expiration_complete = state.current_expiration == 0
        
        return cooldown_complete and expiration_complete
    
    def _cleanup_completed_states(self, agent_id: str, actor) -> None:
        """
        Delete state records that are complete (can be safely removed).
        
        A state is complete when:
        - Cooldown is None or 0 (no cooldown = complete)
        - AND expiration is 0 (expired, not None - None means never expire = not complete)
        
        Args:
            agent_id: The agent ID
            actor: The user for permission checking
        """
        # Get all states for this agent
        states = self._get_injection_states_sync(agent_id)
        
        for state in states:
            if self._is_state_complete(state):
                # Both counters are done - delete the state
                # Note: With the new name-based matching, we don't rely on injected_message_id anymore
                # Note: expiration=None means never expire (not complete), only expiration=0 means expired
                logger.info(f"[World Info] Deleting completed state {state.id} (cooldown=None/0 and expiration=0)")
                self._delete_injection_state_sync(self.injection_state_manager, state.id)
    
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
        # If both cooldown and expiration are 0/None, inject freely (current behavior)
        entry_cooldown = entry.cooldown or 0
        entry_expiration = entry.expiration or 0
        if entry_cooldown == 0 and entry_expiration == 0:
            return True
        
        # Check if already injected and still in cooldown
        existing_state = self._get_injection_state_by_entry_sync(entry.id, agent_id)
        
        if existing_state:
            # Check if cooldown is still active
            if existing_state.current_cooldown is not None and existing_state.current_cooldown > 0:
                logger.debug(f"[World Info] Entry {entry.id} is in cooldown ({existing_state.current_cooldown} runs remaining)")
                return False
            
            # Check if still in context (expiration not complete)
            if existing_state.current_expiration is not None and existing_state.current_expiration > 0:
                logger.debug(f"[World Info] Entry {entry.id} still in context ({existing_state.current_expiration} runs remaining)")
                return False
        
            # State should have been cleaned up by _cleanup_completed_states(), but if it hasn't,
            # we still check if it's complete to avoid re-injection during cooldown/expiration
            # Note: Actual deletion happens in _cleanup_completed_states() to avoid redundant operations
        
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
        system_messages = []
        
        for entry in entries:
            # Check if should inject
            if not self._should_inject(entry, agent_id, actor):
                continue
            
            # Create system message with name marker for tracking (name field is not sent to LLM for system messages)
            name_marker = f"world-info-{entry.id}"
            system_message = MessageCreate(
                role=MessageRole.system,
                content=[TextContent(text=entry.content)],
                name=name_marker
            )
            system_messages.append(system_message)
            logger.debug(f"[World Info] Created system message for entry {entry.id} with name marker: {name_marker}")
            
            # Create state record if needed
            entry_cooldown = entry.cooldown or 0
            entry_expiration = entry.expiration or 0
            
            if entry_cooldown > 0 or entry_expiration > 0:
                state = self._create_injection_state_sync(
                    self.injection_state_manager,
                    world_info_entry_id=entry.id,
                    agent_id=agent_id,
                    current_cooldown=entry_cooldown if entry_cooldown > 0 else None,
                    current_expiration=entry_expiration if entry_expiration > 0 else None,
                    cooldown_setting=entry_cooldown,
                    expiration_setting=entry_expiration,
                    organization_id=actor.organization_id,
                    actor=actor
                )
                if state:
                    logger.info(
                        f"[World Info] Created injection state for entry {entry.id}: "
                        f"cooldown={entry_cooldown}, expiration={entry_expiration}"
                    )
        
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

    def _get_injection_states_sync(self, agent_id: str) -> List:
        """
        Get injection states for an agent (synchronous wrapper for async operation).
        
        Args:
            agent_id: The agent ID
            
        Returns:
            List of injection states
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(self.injection_state_manager.get_injection_states_by_agent(agent_id))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return []
        except Exception as e:
            logger.error(f"[World Info] Error getting injection states: {e}", exc_info=True)
            return []

    def _get_injection_state_by_entry_sync(self, world_info_entry_id: str, agent_id: str):
        """
        Get injection state for a specific entry and agent (synchronous wrapper).
        
        Args:
            world_info_entry_id: The World Info entry ID
            agent_id: The agent ID
            
        Returns:
            Injection state if found, None otherwise
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(self.injection_state_manager.get_injection_state_by_entry(world_info_entry_id, agent_id))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return None
        except Exception as e:
            logger.error(f"[World Info] Error getting injection state: {e}", exc_info=True)
            return None

    def _update_injection_state_sync(self, manager, injection_state_id: str, **kwargs):
        """
        Update an injection state (synchronous wrapper).
        
        Args:
            manager: WorldInfoInjectionStateManager instance
            injection_state_id: The injection state ID
            **kwargs: Fields to update (current_cooldown, current_expiration, optional actor)
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(manager.update_injection_state(injection_state_id, **kwargs))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return None
        except Exception as e:
            logger.error(f"[World Info] Error updating injection state: {e}", exc_info=True)
            return None

    def _create_injection_state_sync(self, manager, **kwargs):
        """
        Create an injection state (synchronous wrapper).
        
        Args:
            manager: WorldInfoInjectionStateManager instance
            **kwargs: Fields for the new state (including optional actor parameter)
            
        Returns:
            Created injection state
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(manager.create_injection_state(**kwargs))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return None
        except Exception as e:
            logger.error(f"[World Info] Error creating injection state: {e}", exc_info=True)
            return None

    def _delete_injection_state_sync(self, manager, injection_state_id: str):
        """
        Delete an injection state (synchronous wrapper).
        
        Args:
            manager: WorldInfoInjectionStateManager instance
            injection_state_id: The injection state ID
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(manager.delete_injection_state(injection_state_id))
            )
            future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
        except Exception as e:
            logger.error(f"[World Info] Error deleting injection state: {e}", exc_info=True)

    def _get_agent_by_id_sync(self, agent_id: str, actor) -> Optional:
        """
        Get agent by ID (synchronous wrapper for async operation).
        
        Args:
            agent_id: The agent ID
            actor: The user for permission checking
            
        Returns:
            PydanticAgentState or None if not found
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(self.agent_manager.get_agent_by_id_async(agent_id, actor))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return None
        except Exception as e:
            logger.error(f"[World Info] Error getting agent by ID: {e}", exc_info=True)
            return None

    def _update_message_ids_sync(self, agent_id: str, message_ids: List[str], actor) -> None:
        """
        Update agent's message IDs (synchronous wrapper for async operation).
        
        Args:
            agent_id: The agent ID
            message_ids: New list of message IDs
            actor: The user for permission checking
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(self.agent_manager.update_message_ids_async(agent_id, message_ids, actor))
            )
            future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
        except Exception as e:
            logger.error(f"[World Info] Error updating message IDs: {e}", exc_info=True)

    def _get_messages_by_ids_sync(self, message_ids: List[str], actor) -> List:
        """
        Get messages by IDs (synchronous wrapper for async operation).
        
        Args:
            message_ids: List of message IDs to fetch
            actor: The user for permission checking
            
        Returns:
            List of PydanticMessage objects
        """
        try:
            future = _executor.submit(
                lambda: asyncio.run(self.message_manager.get_messages_by_ids_async(message_ids, actor))
            )
            return future.result(timeout=10.0)
        except TimeoutError:
            logger.error("[World Info] Database query timed out after 10 seconds")
            return []
        except Exception as e:
            logger.error(f"[World Info] Error getting messages by IDs: {e}", exc_info=True)
            return []

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

