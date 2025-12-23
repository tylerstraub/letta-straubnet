"""
Message Processor Registry - Manages registered message processors
"""

from typing import List

from straubnet_extensions.message_processors.protocol import MessageProcessor


class MessageProcessorRegistry:
    """
    Registry for message processors.

    Processors are executed in the order they are registered.
    """

    def __init__(self):
        self._processors: List[MessageProcessor] = []

    def register(self, processor: MessageProcessor):
        """
        Register a message processor.

        Args:
            processor: The processor to register
        """
        if processor not in self._processors:
            self._processors.append(processor)

    def unregister(self, processor: MessageProcessor):
        """
        Unregister a message processor.

        Args:
            processor: The processor to unregister
        """
        if processor in self._processors:
            self._processors.remove(processor)

    def get_processors(self) -> List[MessageProcessor]:
        """
        Get all registered processors in registration order.

        Returns:
            List of registered processors
        """
        return self._processors.copy()

    def clear(self):
        """Clear all registered processors."""
        self._processors.clear()

