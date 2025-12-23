"""Message text extraction for World Info keyword scanning."""

from typing import List

from letta.schemas.message import MessageCreate


def extract_text_from_message(message: MessageCreate) -> str:
    """
    Extract plain text from a MessageCreate object for keyword scanning.

    Handles both string content and content array formats. Extracts text from
    TextContent, ReasoningContent, and other content types that have text
    representations. Skips non-text content types (e.g., ImageContent).

    Args:
        message: The MessageCreate object to extract text from

    Returns:
        Concatenated plain text string from all text-containing content blocks.
        Returns empty string if no text content is found.
    """
    if not message.content:
        return ""

    # Handle string content (simple case)
    if isinstance(message.content, str):
        return message.content

    # Handle content array
    if isinstance(message.content, list):
        text_parts: List[str] = []

        for content_item in message.content:
            # Use the canonical .to_text() method first
            # This is the standard way to extract text from any MessageContent type
            extracted_text = content_item.to_text()

            # Fall back to direct attribute access if to_text() returns None
            # This handles edge cases where to_text() might not be implemented
            if not extracted_text:
                if hasattr(content_item, "text") and content_item.text:
                    extracted_text = content_item.text
                elif hasattr(content_item, "reasoning") and content_item.reasoning:
                    extracted_text = content_item.reasoning
                elif hasattr(content_item, "content") and content_item.content:
                    extracted_text = content_item.content

            # Only add non-empty text
            if extracted_text:
                text_parts.append(extracted_text)

        # Join all text parts with spaces
        return " ".join(text_parts)

    # Fallback: return empty string for unexpected content types
    return ""

