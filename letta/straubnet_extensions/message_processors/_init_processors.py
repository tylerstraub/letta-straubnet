"""
Initialize default message processors

This module is imported to register default processors when the extension system loads.
"""

from letta.log import get_logger

from straubnet_extensions.message_processors import register_processor
from straubnet_extensions.world_info.processor import WorldInfoProcessor

logger = get_logger(__name__)

# Register the World Info processor
try:
    _world_info_processor = WorldInfoProcessor()
    register_processor(_world_info_processor)
    logger.info("[StraubNet Extensions] WorldInfoProcessor registered successfully")
except Exception as e:
    logger.error(f"[StraubNet Extensions] Failed to register WorldInfoProcessor: {e}", exc_info=True)

