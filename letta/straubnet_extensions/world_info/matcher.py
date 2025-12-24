"""Keyword matching for World Info entries."""

import re
from typing import List


def match_keywords(
    text: str,
    keywords: List[str],
    case_sensitive: bool = False,
    match_whole_words: bool = True,
) -> bool:
    """
    Check if any keyword matches in the given text.

    If match_whole_words is True (default), uses word boundary matching to ensure
    keywords only match complete words. If False, performs substring matching.

    Args:
        text: The text to search in
        keywords: List of keywords to search for
        case_sensitive: Whether matching should be case-sensitive (default: False)
        match_whole_words: Whether keywords should match whole words only using
                          word boundaries (default: True)

    Returns:
        True if any keyword is found in the text, False otherwise
    """
    if not text or not keywords:
        return False

    # Normalize text and keywords for case-insensitive matching
    if not case_sensitive:
        text = text.lower()
        keywords = [kw.lower() for kw in keywords]

    # Check if any keyword matches
    for keyword in keywords:
        if not keyword:  # Skip empty keywords
            continue

        if match_whole_words:
            # Use word boundaries to match whole words only
            # \b matches word boundaries (between word chars and non-word chars)
            # We escape the keyword to handle special regex characters
            pattern = r"\b" + re.escape(keyword) + r"\b"
            flags = 0 if case_sensitive else re.IGNORECASE
            if re.search(pattern, text, flags):
                return True
        else:
            # Simple substring matching (original behavior)
            if keyword in text:
                return True

    return False

