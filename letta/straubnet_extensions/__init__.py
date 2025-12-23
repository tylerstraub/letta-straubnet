"""
StraubNet Extensions - Modular extension system for Letta

This module provides a clean extension framework that allows adding custom
functionality to Letta without modifying core code, making upstream sync easier.
"""

from straubnet_extensions.message_processors import apply_message_extensions

__all__ = ["apply_message_extensions"]

