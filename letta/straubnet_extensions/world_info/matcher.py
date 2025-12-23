"""Keyword matching for World Info entries."""

from typing import List


def match_keywords(text: str, keywords: List[str], case_sensitive: bool = False) -> bool:
    """
    Check if any keyword matches in the given text.

    Performs simple substring matching. If case_sensitive is False (default),
    the comparison is case-insensitive. Returns True if any keyword is found
    in the text.

    Args:
        text: The text to search in
        keywords: List of keywords to search for
        case_sensitive: Whether matching should be case-sensitive (default: False)

    Returns:
        True if any keyword is found in the text, False otherwise
    """
    if not text or not keywords:
        return False

    # Normalize text and keywords for case-insensitive matching
    if not case_sensitive:
        text = text.lower()
        keywords = [kw.lower() for kw in keywords]

    # Check if any keyword is a substring of the text
    for keyword in keywords:
        if not keyword:  # Skip empty keywords
            continue
        if keyword in text:
            return True

    return False

