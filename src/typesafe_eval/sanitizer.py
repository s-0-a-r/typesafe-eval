"""Sanitizer and guard utilities for documents sent to TypeSafe."""

import re
from typing import Tuple

SECRET_PATTERNS = [
    (re.compile(r"apikey_[0-9a-zA-Z_]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"gh[pousr]_[0-9a-zA-Z]{36}", re.IGNORECASE), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"sk-[0-9a-zA-Z]{20,}", re.IGNORECASE), "[REDACTED_SECRET_KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"bearer\s+[a-zA-Z0-9\-_\.=]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
]

def mask_sensitive_data(text: str) -> Tuple[str, int]:
    """Replaces detected credentials, tokens, and PII with redaction placeholders.
    
    Returns:
        (sanitized_text, count_of_redactions)
    """
    total_redactions = 0
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized, count = pattern.subn(replacement, sanitized)
        total_redactions += count
    return sanitized, total_redactions


def guard_document_length(
    text: str, max_chars: int = 25000, truncate_mode: str = "head_tail"
) -> Tuple[str, bool]:
    """Ensures document stays within reasonable context length limits.
    
    Args:
        text: Original document content.
        max_chars: Maximum character budget (default: 25,000 chars, ~6,000-8,000 tokens).
        truncate_mode: 'head_tail' (keep beginning & end) or 'raise'.
        
    Returns:
        (processed_text, was_truncated)
    """
    if len(text) <= max_chars:
        return text, False

    if truncate_mode == "raise":
        raise ValueError(
            f"Document length ({len(text)} chars) exceeds maximum allowable limit of {max_chars} chars."
        )

    half = max(max_chars // 2, 1)
    truncated_chars = max(len(text) - (half * 2), 0)
    truncated_msg = f"\n\n... [TRUNCATED {truncated_chars} CHARACTERS TO PREVENT TOKEN OVERFLOW] ...\n\n"
    tail = text[len(text) - half:] if half > 0 else ""
    processed = text[:half] + truncated_msg + tail
    return processed, True
