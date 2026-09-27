"""Sanitizer and guard utilities for documents sent to TypeSafe."""

import re
import fnmatch
from typing import Tuple, Dict, Any, Union, Literal, Optional, List, overload

PLACEHOLDER_SUBSTRINGS = (
    "your_", "example", "dummy", "xxxx", "replace_me", "insert_",
)

ROLE_EMAIL_LOCAL_PARTS = {
    "admin", "administrator", "info", "support", "help", "contact",
    "legal", "compliance", "security", "sales", "billing", "marketing",
    "careers", "jobs", "press", "media", "privacy", "postmaster",
    "hostmaster", "root", "noreply", "no-reply", "team", "office",
    "dev", "ops", "hr", "inquiries", "feedback",
    "hello", "hi", "notifications", "notification", "alerts", "alert",
    "accounts", "account", "newsletter", "news", "service", "services",
    "general", "community", "events", "partners", "partnership",
    "customercare", "customer-care", "customerservice", "customer-service",
}

ROLE_EMAIL_AFFIXES = (
    "-team", "team-", "-support", "support-", "-ops", "-dev", "-service",
)

FREE_OR_PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "zoho.com", "mail.com", "gmx.com",
}

def is_credential_placeholder(token: str) -> bool:
    """Checks whether token is an obvious documentation or example placeholder."""
    token_lower = token.lower()
    return any(p in token_lower for p in PLACEHOLDER_SUBSTRINGS)

def detect_local_part_shape(local_part: str) -> str:
    """Classifies the structural pattern of the email local part."""
    if "." in local_part:
        return "dotted_name"
    if "-" in local_part:
        return "hyphenated"
    clean = local_part.replace("_", "")
    if clean.isalnum():
        return "single_word"
    return "other"

def is_known_role_word(local_part: str) -> bool:
    """Checks whether local part matches standard role vocabulary or affixes."""
    lp = local_part.lower()
    if lp in ROLE_EMAIL_LOCAL_PARTS:
        return True
    if any(lp.startswith(affix) or lp.endswith(affix) for affix in ROLE_EMAIL_AFFIXES):
        return True
    return False

def extract_email_features(email_str: str, custom_role_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """Extracts objective structural features from an email address."""
    parts = email_str.split("@", 1)
    if len(parts) != 2:
        return {
            "domain_type": "corporate",
            "local_part_shape": "other",
            "known_role_word": False,
            "matches_custom_role": False,
        }
    local_part, domain = parts[0].lower(), parts[1].lower()
    domain_type = "free_mail" if domain in FREE_OR_PERSONAL_DOMAINS else "corporate"
    shape = detect_local_part_shape(local_part)
    known_role = is_known_role_word(local_part)
    matches_custom = False
    if custom_role_patterns:
        matches_custom = any(fnmatch.fnmatch(local_part, p.lower()) for p in custom_role_patterns)

    return {
        "domain_type": domain_type,
        "local_part_shape": shape,
        "known_role_word": known_role,
        "matches_custom_role": matches_custom,
    }

def classify_email(email_str: str, custom_role_patterns: Optional[List[str]] = None) -> str:
    """Classifies email address as 'role' or 'personal' (legacy / backward-compatibility)."""
    parts = email_str.split("@", 1)
    if len(parts) != 2:
        return "personal"
    local_part, domain = parts[0].lower(), parts[1].lower()
    if domain in FREE_OR_PERSONAL_DOMAINS:
        return "personal"
    if local_part in ROLE_EMAIL_LOCAL_PARTS:
        return "role"
    if any(local_part.startswith(affix) or local_part.endswith(affix) for affix in ROLE_EMAIL_AFFIXES):
        return "role"
    if custom_role_patterns:
        for pattern in custom_role_patterns:
            if fnmatch.fnmatch(local_part, pattern.lower()):
                return "role"
    return "personal"

EXAMPLE_REPLACEMENTS = {
    "api_key": "[EXAMPLE_API_KEY]",
    "github_token": "[EXAMPLE_GH_TOKEN]",
    "secret_key": "[EXAMPLE_SECRET_KEY]",
    "aws_key": "[EXAMPLE_AWS_KEY]",
    "bearer_token": "Bearer [EXAMPLE_TOKEN]",
}

PATTERN_SPECS = [
    (re.compile(r"\bapikey_[0-9a-zA-Z_]{20,}\b", re.IGNORECASE), "[REDACTED_API_KEY]", "credentials", "api_key"),
    (re.compile(r"\bgh[pousr]_[0-9a-zA-Z]{36}\b", re.IGNORECASE), "[REDACTED_GH_TOKEN]", "credentials", "github_token"),
    (re.compile(r"\bsk-[0-9a-zA-Z]{20,}\b", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "credentials", "secret_key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]", "credentials", "aws_key"),
    (re.compile(r"\bbearer\s+[a-zA-Z0-9\-_\.=]{20,}(?![a-zA-Z0-9\-_\.=])", re.IGNORECASE), "Bearer [REDACTED_TOKEN]", "credentials", "bearer_token"),
    (re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"), "[REDACTED_EMAIL]", "pii", "email"),
]

SECRET_PATTERNS = [(pattern, replacement) for pattern, replacement, _, _ in PATTERN_SPECS]

@overload
def mask_sensitive_data(
    text: str, return_details: Literal[False] = False, custom_role_patterns: Optional[List[str]] = None
) -> Tuple[str, int]: ...

@overload
def mask_sensitive_data(
    text: str, return_details: Literal[True], custom_role_patterns: Optional[List[str]] = None
) -> Tuple[str, int, Dict[str, Any]]: ...

def mask_sensitive_data(
    text: str, return_details: bool = False, custom_role_patterns: Optional[List[str]] = None
) -> Union[Tuple[str, int], Tuple[str, int, Dict[str, Any]]]:
    """Replaces detected credentials, tokens, and PII with redaction placeholders.
    
    Args:
        text: Original document content.
        return_details: If True, returns detailed breakdown by category and type.
        custom_role_patterns: Optional list of glob patterns for custom role emails.

    Returns:
        (sanitized_text, count_of_redactions) when return_details=False,
        or (sanitized_text, count_of_redactions, details_dict) when return_details=True.
    """
    total_redactions = 0
    distinct_emails: Dict[str, Dict[str, Any]] = {}
    details: Dict[str, Any] = {
        "total": 0,
        "credentials": 0,
        "pii": 0,
        "pii_personal": 0,
        "pii_role": 0,
        "examples": 0,
        "redacted_emails": [],
        "by_type": {},
    }
    sanitized = text

    for pattern, default_replacement, category, type_name in PATTERN_SPECS:
        if category == "credentials":
            def repl_cred(match: re.Match) -> str:
                nonlocal total_redactions
                token = match.group(0)
                if is_credential_placeholder(token):
                    example_token = EXAMPLE_REPLACEMENTS.get(type_name, "[EXAMPLE_SECRET]")
                    details["examples"] = details.get("examples", 0) + 1
                    details["by_type"][f"example_{type_name}"] = details["by_type"].get(f"example_{type_name}", 0) + 1
                    return example_token
                total_redactions += 1
                details["credentials"] += 1
                details["by_type"][type_name] = details["by_type"].get(type_name, 0) + 1
                return default_replacement

            sanitized = pattern.sub(repl_cred, sanitized)

        elif category == "pii" and type_name == "email":
            def repl_email(match: re.Match) -> str:
                nonlocal total_redactions
                email_str = match.group(0)
                norm_email = email_str.lower()
                total_redactions += 1
                details["pii"] += 1

                if norm_email not in distinct_emails:
                    idx = len(distinct_emails) + 1
                    placeholder = f"[EMAIL_{idx}]"
                    features = extract_email_features(norm_email, custom_role_patterns=custom_role_patterns)
                    features["placeholder"] = placeholder
                    distinct_emails[norm_email] = {
                        "placeholder": placeholder,
                        "features": features,
                    }
                else:
                    placeholder = distinct_emails[norm_email]["placeholder"]
                    features = distinct_emails[norm_email]["features"]

                if features["domain_type"] == "free_mail":
                    details["pii_personal"] = details.get("pii_personal", 0) + 1
                    details["by_type"]["email_free_mail"] = details["by_type"].get("email_free_mail", 0) + 1
                elif features.get("known_role_word") or features.get("matches_custom_role"):
                    details["pii_role"] = details.get("pii_role", 0) + 1
                    details["by_type"]["email_role"] = details["by_type"].get("email_role", 0) + 1
                else:
                    details["pii_personal"] = details.get("pii_personal", 0) + 1
                    details["by_type"]["email_personal"] = details["by_type"].get("email_personal", 0) + 1

                return placeholder

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
    details["redacted_emails"] = [v["features"] for v in distinct_emails.values()]

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
