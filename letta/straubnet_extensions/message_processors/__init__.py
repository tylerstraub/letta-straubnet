"""
Message Processors - Extension point for modifying messages before agent processing

Message processors can inspect and modify messages before they are sent to agents.
This enables features like dynamic prompt injection, content filtering, etc.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from letta.orm import User
    from letta.schemas.message import MessageCreate
else:
    # Import at runtime to avoid circular dependencies
    from letta.schemas.message import MessageCreate

from straubnet_extensions.message_processors.registry import MessageProcessorRegistry

# Global registry instance
_registry = MessageProcessorRegistry()


def apply_message_extensions(
    messages: List[MessageCreate],
    agent_id: str,
    actor: "User",
    context: dict | None = None,
) -> List[MessageCreate]:
    """
    Apply all registered message processors to the message list.

    This is the main entry point for message extensions. It processes messages
    through all registered processors in order.

    Args:
        messages: List of MessageCreate objects to process
        agent_id: The agent ID these messages are being sent to
        actor: The user making the request
        context: Optional context dictionary for processors

    Returns:
        Modified list of MessageCreate objects (may have additional messages injected)
    """
    # Import logger here to avoid circular dependencies
    from letta.log import get_logger
    
    logger = get_logger(__name__)
    logger.info(f"[StraubNet Extensions] apply_message_extensions called for agent {agent_id} with {len(messages)} messages")
    
    if context is None:
        context = {}

    # Add standard context
    context["agent_id"] = agent_id
    context["actor"] = actor

    # Process through all registered processors
    processors = _registry.get_processors()
    logger.info(f"[StraubNet Extensions] Found {len(processors)} registered processors")
    
    processed_messages = messages
    for processor in processors:
        logger.info(f"[StraubNet Extensions] Processing with {type(processor).__name__}")
        processed_messages = processor.process(processed_messages, context)
        logger.info(f"[StraubNet Extensions] After processing: {len(processed_messages)} messages")
    
    return processed_messages


def register_processor(processor: "MessageProcessor"):
    """
    Register a message processor.

    Args:
        processor: The processor instance to register
    """
    _registry.register(processor)


def unregister_processor(processor: "MessageProcessor"):
    """
    Unregister a message processor.

    Args:
        processor: The processor instance to unregister
    """
    _registry.unregister(processor)

