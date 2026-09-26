"""Sanitizer and guard utilities for documents sent to TypeSafe."""

import re
from typing import Tuple, Dict, Any, Union, Literal, overload

PATTERN_SPECS = [
    (re.compile(r"apikey_[0-9a-zA-Z_]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]", "credentials", "api_key"),
    (re.compile(r"gh[pousr]_[0-9a-zA-Z]{36}", re.IGNORECASE), "[REDACTED_GH_TOKEN]", "credentials", "github_token"),
    (re.compile(r"sk-[0-9a-zA-Z]{20,}", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "credentials", "secret_key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]", "credentials", "aws_key"),
    (re.compile(r"bearer\s+[a-zA-Z0-9\-_\.=]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]", "credentials", "bearer_token"),
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]", "pii", "email"),
]

SECRET_PATTERNS = [(pattern, replacement) for pattern, replacement, _, _ in PATTERN_SPECS]

@overload
def mask_sensitive_data(text: str, return_details: Literal[False] = False) -> Tuple[str, int]: ...

@overload
def mask_sensitive_data(text: str, return_details: Literal[True]) -> Tuple[str, int, Dict[str, Any]]: ...

def mask_sensitive_data(
    text: str, return_details: bool = False
) -> Union[Tuple[str, int], Tuple[str, int, Dict[str, Any]]]:
    """Replaces detected credentials, tokens, and PII with redaction placeholders.
    
    Args:
        text: Original document content.
        return_details: If True, returns detailed breakdown by category and type.

    Returns:
        (sanitized_text, count_of_redactions) when return_details=False,
        or (sanitized_text, count_of_redactions, details_dict) when return_details=True.
    """
    total_redactions = 0
    details: Dict[str, Any] = {
        "total": 0,
        "credentials": 0,
        "pii": 0,
        "by_type": {},
    }
    sanitized = text
    for pattern, replacement, category, type_name in PATTERN_SPECS:
        sanitized, count = pattern.subn(replacement, sanitized)
        if count > 0:
            total_redactions += count
            details[category] = details.get(category, 0) + count
            details["by_type"][type_name] = details["by_type"].get(type_name, 0) + count

    details["total"] = total_redactions

    if return_details:
        return sanitized, total_redactions, details
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
