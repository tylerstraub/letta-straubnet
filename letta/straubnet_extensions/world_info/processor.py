"""World Info Processor - Keyword-based prompt injection processor."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

from letta.log import get_logger
from letta.schemas.enums import MessageRole
from letta.schemas.message import MessageCreate
from letta.server.db import db_registry

from straubnet_extensions.message_processors.protocol import MessageProcessor
from straubnet_extensions.world_info.matcher import match_keywords
from straubnet_extensions.world_info.scanner import extract_text_from_message
from straubnet_extensions.world_info.storage import get_world_info_entries

logger = get_logger(__name__)

# Thread pool executor for running async database queries from sync context
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world-info-db")


class WorldInfoProcessor(MessageProcessor):
    """
    World Info processor that injects system messages based on keyword matching.

    This processor:
    1. Queries World Info entries from the database for the organization/agent
    2. Extracts text from incoming messages
    3. Matches keywords against the text
    4. Injects matched entries as system messages, ordered by insertion_order
    """

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
                - server: Optional server object

        Returns:
            Modified message list with World Info entries injected as system messages
        """
        try:
            # Extract context
            agent_id = context.get("agent_id")
            actor = context.get("actor")
            
            if not actor:
                logger.warning("[World Info] No actor in context, skipping World Info processing")
                return messages

            organization_id = actor.organization_id
            if not organization_id:
                logger.warning("[World Info] Actor has no organization_id, skipping World Info processing")
                return messages

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

            # Find matching entries
            matched_entries = self._find_matching_entries(entries, combined_text)

            if not matched_entries:
                logger.debug("[World Info] No entries matched keywords in message text")
                return messages

            # Create system messages from matched entries
            # Entries are already ordered by insertion_order DESC from storage layer
            system_messages = self._create_system_messages(matched_entries)

            # Inject system messages at the beginning (before user messages)
            # System messages should come first in the context
            logger.info(f"[World Info] Injecting {len(system_messages)} World Info entries as system messages")
            return system_messages + messages

        except Exception as e:
            logger.error(f"[World Info] Error processing messages: {e}", exc_info=True)
            # On error, return original messages unchanged
            return messages

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
            List of matching WorldInfoEntry objects (ordered by insertion_order DESC)
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
            entries: List of WorldInfoEntry objects (already ordered by insertion_order DESC)

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

