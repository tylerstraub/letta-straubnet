"""
Message Processor Protocol - Interface for message processors
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from letta.schemas.message import MessageCreate

if TYPE_CHECKING:
    from letta.orm import User


class MessageProcessor(ABC):
    """
    Abstract base class for message processors.

    Message processors can inspect and modify messages before they are sent to agents.
    They receive the message list and a context dictionary, and return a (possibly modified) message list.
    """

    @abstractmethod
    def process(
        self,
        messages: List[MessageCreate],
        context: dict,
    ) -> List[MessageCreate]:
        """
        Process messages and return modified message list.

        Args:
            messages: List of MessageCreate objects to process
            context: Context dictionary containing:
                - agent_id: The agent ID
                - actor: The user making the request
                - Any additional context provided by the caller

        Returns:
            Modified list of MessageCreate objects
        """
        pass

