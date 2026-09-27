"""Sanitizer and guard utilities for documents sent to TypeSafe."""

import re
from typing import Tuple, Dict, Any, Union, Literal, overload

PLACEHOLDER_SUBSTRINGS = (
    "your_", "example", "dummy", "xxxx", "replace_me", "insert_",
)

ROLE_EMAIL_LOCAL_PARTS = {
    "admin", "administrator", "info", "support", "help", "contact",
    "legal", "compliance", "security", "sales", "billing", "marketing",
    "careers", "jobs", "press", "media", "privacy", "postmaster",
    "hostmaster", "root", "noreply", "no-reply", "team", "office",
    "dev", "ops", "hr", "inquiries", "feedback",
}

FREE_OR_PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "zoho.com", "mail.com", "gmx.com",
}

def is_credential_placeholder(token: str) -> bool:
    """Checks whether token is an obvious documentation or example placeholder."""
    token_lower = token.lower()
    return any(p in token_lower for p in PLACEHOLDER_SUBSTRINGS)

def classify_email(email_str: str) -> str:
    """Classifies email address as 'role' or 'personal'."""
    parts = email_str.split("@", 1)
    if len(parts) != 2:
        return "personal"
    local_part, domain = parts[0].lower(), parts[1].lower()
    if local_part in ROLE_EMAIL_LOCAL_PARTS:
        return "role"
    return "personal"

PATTERN_SPECS = [
    (re.compile(r"\bapikey_[0-9a-zA-Z_]{20,}\b", re.IGNORECASE), "[REDACTED_API_KEY]", "credentials", "api_key"),
    (re.compile(r"\bgh[pousr]_[0-9a-zA-Z]{36}\b", re.IGNORECASE), "[REDACTED_GH_TOKEN]", "credentials", "github_token"),
    (re.compile(r"\bsk-[0-9a-zA-Z]{20,}\b", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "credentials", "secret_key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]", "credentials", "aws_key"),
    (re.compile(r"\bbearer\s+[a-zA-Z0-9\-_\.=]{20,}\b", re.IGNORECASE), "Bearer [REDACTED_TOKEN]", "credentials", "bearer_token"),
    (re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"), "[REDACTED_EMAIL]", "pii", "email"),
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
        "pii_personal": 0,
        "pii_role": 0,
        "by_type": {},
    }
    sanitized = text

    for pattern, default_replacement, category, type_name in PATTERN_SPECS:
        if category == "credentials":
            def repl_cred(match: re.Match) -> str:
                nonlocal total_redactions
                token = match.group(0)
                if is_credential_placeholder(token):
                    return token
                total_redactions += 1
                details["credentials"] += 1
                details["by_type"][type_name] = details["by_type"].get(type_name, 0) + 1
                return default_replacement

            sanitized = pattern.sub(repl_cred, sanitized)

        elif category == "pii" and type_name == "email":
            def repl_email(match: re.Match) -> str:
                nonlocal total_redactions
                email_str = match.group(0)
                email_kind = classify_email(email_str)
                total_redactions += 1
                details["pii"] += 1
                if email_kind == "role":
                    details["pii_role"] += 1
                    details["by_type"]["email_role"] = details["by_type"].get("email_role", 0) + 1
                    return "[REDACTED_ROLE_EMAIL]"
                else:
                    details["pii_personal"] += 1
                    details["by_type"]["email_personal"] = details["by_type"].get("email_personal", 0) + 1
                    return "[REDACTED_PERSONAL_EMAIL]"

            sanitized = pattern.sub(repl_email, sanitized)

        else:
            def repl_generic(match: re.Match) -> str:
                nonlocal total_redactions
                total_redactions += 1
                details[category] = details.get(category, 0) + 1
                details["by_type"][type_name] = details["by_type"].get(type_name, 0) + 1
                return default_replacement

            sanitized = pattern.sub(repl_generic, sanitized)

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
