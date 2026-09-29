"""Sanitizer and guard utilities for documents sent to TypeSafe."""

import re
import fnmatch
import ipaddress
import urllib.parse
from typing import Tuple, Dict, Any, Union, Literal, Optional, List, overload

PLACEHOLDER_SUBSTRINGS = (
    "your_", "example", "dummy", "xxxx", "replace_me", "insert_",
)

AWS_EXAMPLE_KEYS = {"AKIAIOSFODNN7EXAMPLE", "AKIAEXAMPLEKEY123456"}

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

PHONE_SUPPORT_PREFIXES = ("0120", "0800", "0570", "1-800", "800")
PHONE_SUPPORT_KEYWORDS = {
    "support", "representative", "switchboard", "helpdesk", "toll-free", "toll free",
    "customer", "care", "service", "corporate desk", "desk", "inquiries",
    "代表", "窓口", "問い合わせ", "お問合せ", "問合せ", "サポート", "ヘルプデスク"
}

EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net", "localhost"}
EXAMPLE_TLDS = (".example", ".invalid", ".test", ".localhost")
INTERNAL_TLDS = (".internal", ".local", ".corp", ".intra", ".lan", ".home")

def is_credential_placeholder(token: str) -> bool:
    """Checks whether token is an obvious documentation or example placeholder."""
    if token.startswith("AKIA"):
        return token in AWS_EXAMPLE_KEYS
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

def extract_phone_features(phone_str: str, surrounding_text: str = "") -> Dict[str, Any]:
    """Extracts structural features from a phone number candidate."""
    norm = phone_str.strip()
    is_support_prefix = any(norm.startswith(p) for p in PHONE_SUPPORT_PREFIXES)
    text_lower = surrounding_text.lower()
    near_support_kw = any(kw in text_lower for kw in PHONE_SUPPORT_KEYWORDS)

    country_format = "JP"
    if norm.startswith("+1") or norm.startswith("1-800"):
        country_format = "US"
    elif norm.startswith("+"):
        country_format = "international"
    elif norm.startswith("0"):
        country_format = "JP"

    is_mobile_prefix = norm.startswith(("090", "080", "070"))
    looks_like_support = (is_support_prefix or near_support_kw) and not is_mobile_prefix
    if is_support_prefix:
        looks_like_support = True

    return {
        "country_format": country_format,
        "looks_like_support": looks_like_support,
        "is_support_prefix": is_support_prefix,
        "near_support_keyword": near_support_kw,
    }

def extract_ip_features(ip_str: str) -> Dict[str, Any]:
    """Extracts routing and RFC category features from an IP candidate."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return {
            "ip_type": "public",
            "is_documentation": False,
            "is_loopback": False,
            "is_private": False,
        }

    is_loop = ip.is_loopback
    is_doc = False
    if isinstance(ip, ipaddress.IPv4Address):
        if (
            ip in ipaddress.IPv4Network("192.0.2.0/24")
            or ip in ipaddress.IPv4Network("198.51.100.0/24")
            or ip in ipaddress.IPv4Network("203.0.113.0/24")
        ):
            is_doc = True
    elif isinstance(ip, ipaddress.IPv6Address):
        if ip in ipaddress.IPv6Network("2001:db8::/32"):
            is_doc = True

    is_priv = ip.is_private and not is_doc and not is_loop

    ip_type = "public"
    if is_doc:
        ip_type = "documentation"
    elif is_loop:
        ip_type = "loopback"
    elif is_priv:
        ip_type = "private"

    return {
        "ip_type": ip_type,
        "is_documentation": is_doc,
        "is_loopback": is_loop,
        "is_private": is_priv,
    }

def extract_url_features(url_str: str, mask: bool = True) -> Dict[str, Any]:
    """Extracts domain classification features from a URL candidate."""
    try:
        parsed = urllib.parse.urlparse(url_str if "://" in url_str else f"http://{url_str}")
        host = (parsed.hostname or "").lower()
    except Exception:
        host = ""

    ip_feat = extract_ip_features(host) if host else None
    is_loop = bool(ip_feat and ip_feat["is_loopback"])
    is_doc_ip = bool(ip_feat and ip_feat["is_documentation"])

    is_example = (
        is_loop
        or is_doc_ip
        or host == "localhost"
        or host in EXAMPLE_DOMAINS
        or any(host.endswith(tld) for tld in EXAMPLE_TLDS)
        or host.startswith("example.")
        or host.startswith("api.example.")
    )
    is_internal = any(host.endswith(tld) for tld in INTERNAL_TLDS)
    is_public = (host == "github.com" or host.endswith(".github.com"))

    suffix_class = None
    for tld in INTERNAL_TLDS:
        if host.endswith(tld):
            suffix_class = tld
            break
    if not suffix_class:
        for tld in EXAMPLE_TLDS:
            if host.endswith(tld):
                suffix_class = tld
                break

    features: Dict[str, Any] = {
        "is_example_domain": is_example,
        "is_loopback": is_loop,
        "is_documentation": is_doc_ip,
        "is_internal_tld": is_internal,
        "suffix_class": suffix_class,
        "matched_suffix": suffix_class,
        "is_public_common": is_public,
    }
    if not mask:
        features["domain"] = host

    return features

def extract_secret_features(
    key_name: str,
    raw_val: str,
    surrounding_text: str = "",
    is_known_format: bool = False,
    is_example: bool = False,
) -> Dict[str, Any]:
    """Extracts objective structural features from a secret candidate.

    STRICT SAFETY CONSTRAINT:
    State NEVER contains the value, a fragment of it, or a hash of it!
    """
    clean_val = raw_val.strip("\"'")
    val_len = len(clean_val)

    char_classes = []
    if any(c.islower() for c in clean_val):
        char_classes.append("lower")
    if any(c.isupper() for c in clean_val):
        char_classes.append("upper")
    if any(c.isdigit() for c in clean_val):
        char_classes.append("digit")
    if any(not c.isalnum() for c in clean_val):
        char_classes.append("symbol")

    is_placeholder = is_example or (
        (clean_val.startswith("${") and clean_val.endswith("}"))
        or (clean_val.startswith("<") and clean_val.endswith(">"))
        or (clean_val.startswith("{{") and clean_val.endswith("}}"))
        or any(p in clean_val.lower() for p in ("xxx", "changeme", "dummy", "replace_me", "your_"))
    )

    ctx_lower = surrounding_text.lower()
    near_example = any(w in ctx_lower for w in ("example", "例", "replace", "置き換えて", "sample", "template"))

    location = "prose"
    if "```env" in ctx_lower or "\n" + key_name.lower() + "=" in ctx_lower or "\n" + key_name.lower() + ":" in ctx_lower:
        location = "env_block"
    elif "```" in ctx_lower or "`" in surrounding_text:
        location = "code_block"

    return {
        "key_name": key_name,
        "value_length": val_len,
        "character_classes": char_classes,
        "placeholder_syntax": is_placeholder,
        "near_example_words": near_example,
        "location": location,
        "is_known_format": is_known_format,
    }

EXAMPLE_REPLACEMENTS = {
    "api_key": "[EXAMPLE_API_KEY]",
    "github_token": "[EXAMPLE_GH_TOKEN]",
    "secret_key": "[EXAMPLE_SECRET_KEY]",
    "aws_key": "[EXAMPLE_AWS_KEY]",
    "bearer_token": "Bearer [EXAMPLE_TOKEN]",
    "private_key": "[EXAMPLE_PRIVATE_KEY]",
}

KNOWN_CREDENTIAL_SPECS = [
    (re.compile(r"\bAKIA[0-9A-Z]{16,}\b"), "[REDACTED_AWS_KEY]", "aws_key"),
    (re.compile(r"\bgh[pousr]_[0-9a-zA-Z]{36,}\b", re.IGNORECASE), "[REDACTED_GH_TOKEN]", "github_token"),
    (re.compile(r"\bsk_(?:live|test)_[0-9a-zA-Z]{20,}\b", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "secret_key"),
    (re.compile(r"\bsk-[0-9a-zA-Z]{20,}\b", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "secret_key"),
    (re.compile(r"\bapikey_[0-9a-zA-Z_]{20,}\b", re.IGNORECASE), "[REDACTED_API_KEY]", "api_key"),
    (re.compile(r"\bbearer\s+[a-zA-Z0-9\-_\.=]{20,}(?![a-zA-Z0-9\-_\.=])", re.IGNORECASE), "Bearer [REDACTED_TOKEN]", "bearer_token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]", "private_key"),
]

AMBIGUOUS_SECRET_PATTERN = re.compile(
    r"\b(?P<key>db_password|password|passwd|pwd|api_key|apikey|auth_token|access_token|secret_key|secret|token)\s*[:=]\s*(?P<val>\"(?:[^\"]|\\.)*\"|'(?:[^']|\\.)*'|\$\{[^}]+\}|<[^>]+>|[^\s\n,;]+)",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")

PHONE_PATTERN = re.compile(
    r"(?:(?<!\w)\+1[-.\s]\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|\b1-800[-.\s]\d{3}[-.\s]\d{4}\b|\b0[1-9]\d{0,3}[-.\s]\d{1,4}[-.\s]\d{3,4}\b)"
)

URL_PATTERN = re.compile(r"\b(?:https?|ldap)://[^\s\"'<>)]+", re.IGNORECASE)

IP_PATTERN = re.compile(r"(?:::1\b|\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{0,4}){1,7}\b|\b(?:\d{1,3}\.){3}\d{1,3}\b)")

PATTERN_SPECS = [
    (re.compile(r"\bapikey_[0-9a-zA-Z_]{20,}\b", re.IGNORECASE), "[REDACTED_API_KEY]", "credentials", "api_key"),
    (re.compile(r"\bgh[pousr]_[0-9a-zA-Z]{36}\b", re.IGNORECASE), "[REDACTED_GH_TOKEN]", "credentials", "github_token"),
    (re.compile(r"\bsk-[0-9a-zA-Z]{20,}\b", re.IGNORECASE), "[REDACTED_SECRET_KEY]", "credentials", "secret_key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16,}\b"), "[REDACTED_AWS_KEY]", "credentials", "aws_key"),
    (re.compile(r"\bbearer\s+[a-zA-Z0-9\-_\.=]{20,}(?![a-zA-Z0-9\-_\.=])", re.IGNORECASE), "Bearer [REDACTED_TOKEN]", "credentials", "bearer_token"),
    (EMAIL_PATTERN, "[REDACTED_EMAIL]", "pii", "email"),
]

SECRET_PATTERNS = [(pattern, replacement) for pattern, replacement, _, _ in PATTERN_SPECS]


@overload
def mask_sensitive_data(
    text: str,
    mask: bool = True,
    return_details: Literal[False] = False,
    custom_role_patterns: Optional[List[str]] = None,
) -> Tuple[str, int]: ...

@overload
def mask_sensitive_data(
    text: str,
    mask: bool = True,
    return_details: Literal[True] = ...,
    custom_role_patterns: Optional[List[str]] = None,
) -> Tuple[str, int, Dict[str, Any]]: ...

def mask_sensitive_data(
    text: str,
    mask: bool = True,
    return_details: bool = False,
    custom_role_patterns: Optional[List[str]] = None,
) -> Union[Tuple[str, int], Tuple[str, int, Dict[str, Any]]]:
    """Replaces detected credentials, tokens, and PII with numbered redaction placeholders.
    
    When mask=False (--no-mask), detection, classification, and feature extraction still run
    identically and populate details, but the returned text remains unmasked.

    Args:
        text: Original document content.
        mask: If True, replaces sensitive tokens with placeholders. If False, preserves raw text.
        return_details: If True, returns detailed breakdown by category and type.
        custom_role_patterns: Optional list of glob patterns for custom role emails.

    Returns:
        (sanitized_text, count_of_redactions) when return_details=False,
        or (sanitized_text, count_of_redactions, details_dict) when return_details=True.
    """
    total_redactions = 0
    distinct_emails: Dict[str, Dict[str, Any]] = {}
    distinct_phones: Dict[str, Dict[str, Any]] = {}
    distinct_ips: Dict[str, Dict[str, Any]] = {}
    distinct_urls: Dict[str, Dict[str, Any]] = {}
    distinct_secrets: List[Dict[str, Any]] = []
    rule_violations: List[str] = []
    raw_mapping: Dict[str, List[str]] = {}

    details: Dict[str, Any] = {
        "total": 0,
        "credentials": 0,
        "pii": 0,
        "pii_personal": 0,
        "pii_role": 0,
        "examples": 0,
        "redacted_emails": [],
        "redacted_phones": [],
        "redacted_ips": [],
        "redacted_urls": [],
        "redacted_secrets": [],
        "rule_violations": [],
        "by_type": {},
    }

    # Replacement list of tuples: (start, end, replacement_str)
    replacements: List[Tuple[int, int, str]] = []
    occupied_spans: List[Tuple[int, int]] = []

    def span_overlaps(s: int, e: int) -> bool:
        for os, oe in occupied_spans:
            if not (e <= os or s >= oe):
                return True
        return False

    def add_span(s: int, e: int, repl: str):
        occupied_spans.append((s, e))
        replacements.append((s, e, repl))

    # 1. Known credential formats
    for pattern, default_repl, type_name in KNOWN_CREDENTIAL_SPECS:
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            if span_overlaps(s, e):
                continue
            token = m.group(0)
            if is_credential_placeholder(token):
                example_token = EXAMPLE_REPLACEMENTS.get(type_name, "[EXAMPLE_SECRET]")
                details["examples"] += 1
                details["by_type"][f"example_{type_name}"] = details["by_type"].get(f"example_{type_name}", 0) + 1
                add_span(s, e, example_token)
            else:
                total_redactions += 1
                details["credentials"] += 1
                details["by_type"][type_name] = details["by_type"].get(type_name, 0) + 1
                sec_idx = len(distinct_secrets) + 1
                placeholder = f"[SECRET_{sec_idx}]"
                rule_violations.append(f"Credential Exposure: {placeholder} is a known {type_name} credential")
                ctx_start = max(0, s - 60)
                ctx_end = min(len(text), e + 60)
                feat = extract_secret_features(
                    key_name=type_name,
                    raw_val=token,
                    surrounding_text=text[ctx_start:ctx_end],
                    is_known_format=True,
                    is_example=False,
                )
                feat["placeholder"] = default_repl
                feat["outcome"] = "secret"
                feat["decided_by"] = "rule"
                distinct_secrets.append(feat)
                add_span(s, e, default_repl)
                raw_mapping.setdefault(default_repl, []).append(token)

    # 2. Ambiguous secrets (key=val)
    for m in AMBIGUOUS_SECRET_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        if span_overlaps(s, e):
            continue
        key_name = m.group("key")
        val = m.group("val")
        ctx_start = max(0, s - 60)
        ctx_end = min(len(text), e + 60)
        ctx = text[ctx_start:ctx_end]
        feat = extract_secret_features(
            key_name=key_name,
            raw_val=val,
            surrounding_text=ctx,
            is_known_format=False,
            is_example=False,
        )
        sec_idx = len(distinct_secrets) + 1
        placeholder = f"[SECRET_{sec_idx}]"
        feat["placeholder"] = placeholder

        # Delimiter between key and val
        matched_str = m.group(0)
        delim = "=" if "=" in matched_str else ":"

        if feat["placeholder_syntax"]:
            details["examples"] += 1
            details["by_type"]["example_secret"] = details["by_type"].get("example_secret", 0) + 1
            feat["outcome"] = "safe"
            feat["decided_by"] = "rule"
            add_span(s, e, f"{key_name}{delim}{placeholder}")
        else:
            total_redactions += 1
            details["by_type"]["ambiguous_secret"] = details["by_type"].get("ambiguous_secret", 0) + 1
            feat["decided_by"] = "model"
            add_span(s, e, f"{key_name}{delim}{placeholder}")
            raw_mapping.setdefault(placeholder, []).append(matched_str)
            if val and val != matched_str:
                raw_mapping[placeholder].append(val)

        distinct_secrets.append(feat)

    # 3. Emails
    for m in EMAIL_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        if span_overlaps(s, e):
            continue
        email_str = m.group(0)
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

        raw_mapping.setdefault(placeholder, []).append(email_str)
        if norm_email != email_str:
            raw_mapping[placeholder].append(norm_email)

        if features["domain_type"] == "free_mail":
            details["pii_personal"] = details.get("pii_personal", 0) + 1
            details["by_type"]["email_free_mail"] = details["by_type"].get("email_free_mail", 0) + 1
        elif features.get("known_role_word") or features.get("matches_custom_role"):
            details["pii_role"] = details.get("pii_role", 0) + 1
            details["by_type"]["email_role"] = details["by_type"].get("email_role", 0) + 1
        else:
            details["pii_personal"] = details.get("pii_personal", 0) + 1
            details["by_type"]["email_personal"] = details["by_type"].get("email_personal", 0) + 1

        add_span(s, e, placeholder)

    # 4. URLs
    for m in URL_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        if span_overlaps(s, e):
            continue
        url_str = m.group(0)
        norm_url = url_str.strip()
        url_feat = extract_url_features(norm_url, mask=mask)

        if norm_url not in distinct_urls:
            idx = len(distinct_urls) + 1
            placeholder = f"[URL_{idx}]"
            url_feat["placeholder"] = placeholder
            distinct_urls[norm_url] = {
                "placeholder": placeholder,
                "features": url_feat,
            }
        else:
            placeholder = distinct_urls[norm_url]["placeholder"]
            url_feat = distinct_urls[norm_url]["features"]

        raw_mapping.setdefault(placeholder, []).append(url_str)
        if norm_url != url_str:
            raw_mapping[placeholder].append(norm_url)

        total_redactions += 1
        if url_feat["is_example_domain"] or url_feat["is_public_common"]:
            details["examples"] += 1
            details["by_type"]["example_url"] = details["by_type"].get("example_url", 0) + 1
        elif url_feat["is_internal_tld"]:
            details["pii"] += 1
            details["pii_personal"] += 1
            details["by_type"]["url_internal"] = details["by_type"].get("url_internal", 0) + 1
        else:
            details["pii"] += 1
            details["by_type"]["url_public"] = details["by_type"].get("url_public", 0) + 1

        add_span(s, e, placeholder)

    # 5. IP Addresses
    for m in IP_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        if span_overlaps(s, e):
            continue
        ip_str = m.group(0)
        try:
            ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        ip_feat = extract_ip_features(ip_str)
        if ip_str not in distinct_ips:
            idx = len(distinct_ips) + 1
            placeholder = f"[IP_{idx}]"
            ip_feat["placeholder"] = placeholder
            distinct_ips[ip_str] = {
                "placeholder": placeholder,
                "features": ip_feat,
            }
        else:
            placeholder = distinct_ips[ip_str]["placeholder"]
            ip_feat = distinct_ips[ip_str]["features"]

        raw_mapping.setdefault(placeholder, []).append(ip_str)

        total_redactions += 1
        if ip_feat["is_documentation"] or ip_feat["is_loopback"]:
            details["examples"] += 1
            details["by_type"]["example_ip"] = details["by_type"].get("example_ip", 0) + 1
        elif ip_feat["is_private"]:
            details["pii"] += 1
            details["pii_personal"] += 1
            details["by_type"]["ip_private"] = details["by_type"].get("ip_private", 0) + 1
        else:
            details["pii"] += 1
            details["by_type"]["ip_public"] = details["by_type"].get("ip_public", 0) + 1

        add_span(s, e, placeholder)

    # 6. Phone Numbers
    for m in PHONE_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        if span_overlaps(s, e):
            continue
        phone_str = m.group(0)
        ctx_start = max(0, s - 50)
        ctx_end = min(len(text), e + 50)
        phone_feat = extract_phone_features(phone_str, surrounding_text=text[ctx_start:ctx_end])

        if phone_str not in distinct_phones:
            idx = len(distinct_phones) + 1
            placeholder = f"[PHONE_{idx}]"
            phone_feat["placeholder"] = placeholder
            distinct_phones[phone_str] = {
                "placeholder": placeholder,
                "features": phone_feat,
            }
        else:
            placeholder = distinct_phones[phone_str]["placeholder"]
            phone_feat = distinct_phones[phone_str]["features"]

        raw_mapping.setdefault(placeholder, []).append(phone_str)

        total_redactions += 1
        details["pii"] += 1
        if phone_feat["looks_like_support"]:
            details["pii_role"] += 1
            details["by_type"]["phone_support"] = details["by_type"].get("phone_support", 0) + 1
        else:
            details["pii_personal"] += 1
            details["by_type"]["phone_personal"] = details["by_type"].get("phone_personal", 0) + 1

        add_span(s, e, placeholder)

    # Build sanitized text if mask=True
    if mask:
        # Sort replacements by start position in descending order to avoid offset drift
        sorted_replacements = sorted(replacements, key=lambda x: x[0], reverse=True)
        sanitized = text
        for s, e, repl in sorted_replacements:
            sanitized = sanitized[:s] + repl + sanitized[e:]
        for v in distinct_urls.values():
            v["features"].pop("domain", None)
    else:
        sanitized = text
        total_redactions = 0

    details["total"] = total_redactions if mask else len(replacements)
    details["redacted_emails"] = [v["features"] for v in distinct_emails.values()]
    details["redacted_phones"] = [v["features"] for v in distinct_phones.values()]
    details["redacted_ips"] = [v["features"] for v in distinct_ips.values()]
    details["redacted_urls"] = [v["features"] for v in distinct_urls.values()]
    details["redacted_secrets"] = distinct_secrets
    details["rule_violations"] = rule_violations
    details["_raw_mapping"] = raw_mapping

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


def chunk_text(
    text: str,
    max_chars: int = 25000,
    overlap: int = 2000,
) -> List[str]:
    """Splits text into overlapping chunks, each within max_chars.

    Prefers paragraph breaks (\\n\\n) or line breaks (\\n) for chunk boundaries
    to preserve context.

    Args:
        text: Original document content.
        max_chars: Maximum character limit per chunk (default 25,000).
        overlap: Character overlap between consecutive chunks (default 2,000).

    Returns:
        List of chunk strings covering the entire text.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(text) <= max_chars:
        return [text]

    effective_overlap = min(max(overlap, 0), max_chars // 2)
    chunks: List[str] = []
    start = 0
    total_len = len(text)

    while start < total_len:
        if total_len - start <= max_chars:
            chunks.append(text[start:])
            break

        target_end = start + max_chars
        # Look for clean break within the overlap window before target_end
        search_window_start = max(start + effective_overlap, target_end - 2000)
        split_pos = -1

        p_break = text.rfind("\n\n", search_window_start, target_end)
        if p_break != -1:
            split_pos = p_break + 2
        else:
            l_break = text.rfind("\n", search_window_start, target_end)
            if l_break != -1:
                split_pos = l_break + 1
            else:
                split_pos = target_end

        chunks.append(text[start:split_pos])

        # Next chunk starts roughly at split_pos - effective_overlap
        next_target = max(start + 1, split_pos - effective_overlap)
        p_next = text.find("\n\n", next_target, min(next_target + 500, split_pos))
        if p_next != -1:
            start = p_next + 2
        else:
            l_next = text.find("\n", next_target, min(next_target + 500, split_pos))
            if l_next != -1:
                start = l_next + 1
            else:
                start = next_target

    return chunks


_HTML_COMMENT_PATTERN = re.compile(
    r"(?P<fence>^[ ]{0,3}(?P<fence_char>[`~]{3,})[^\n]*\n[\s\S]*?(?:^[ ]{0,3}(?P=fence_char)[`~]*[ ]*(?:\n|\Z)|\Z))"
    r"|(?P<inline>(?P<tick>`+)(?:(?!\n\s*\n)[\s\S])*?(?P=tick))"
    r"|(?P<comment><!--[\s\S]*?-->)",
    re.MULTILINE,
)


def strip_html_comments(text: str) -> str:
    """Strips HTML comments (<!-- ... -->) outside of code blocks and inline code.

    Comments inside fenced code blocks (``` or ~~~) and inline code spans are left
    intact because they render literally. Unclosed comments (<!-- without matching -->)
    are left as is.
    """
    def _repl(m: re.Match) -> str:
        if m.group("comment"):
            return ""
        return m.group(0)

    return _HTML_COMMENT_PATTERN.sub(_repl, text)

