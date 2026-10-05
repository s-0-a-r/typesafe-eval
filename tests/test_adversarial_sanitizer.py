"""Adversarial security and robustness tests for TypeSafe sanitizer.

Comprehensive Red Team test suite verifying boundaries of:
1. PII detection (international phones, free-mail edge cases, multiple emails on same line, homoglyphs/boundaries)
2. Secret detection (quoted secrets in complex JSON/YAML, multiline HTML comments, markdown backtick edge cases, API key patterns)
3. Zero raw leak guarantee (verifying NO raw secret or email leaks into sanitized_content or metadata)
4. Preserving code blocks (HTML comments inside fenced/inline code preserved, prose HTML comments stripped)
"""

from typing import Any

import pytest

from typesafe_eval.sanitizer import (
    classify_email,
    extract_email_features,
    extract_phone_features,
    extract_secret_features,
    is_credential_placeholder,
    mask_sensitive_data,
    strip_html_comments,
)


def _assert_zero_leak(raw_values: list[str], text: str, details: dict[str, Any]):
    """Strictly audits that no raw sensitive value leaks into text or details metadata."""
    # 1. Check sanitized text
    for val in raw_values:
        assert val not in text, f"CRITICAL LEAK: Raw value '{val}' leaked into sanitized text!"

    # 2. Check details metadata
    def _search_nested(obj: Any):
        if isinstance(obj, str):
            for val in raw_values:
                assert val not in obj, (
                    f"CRITICAL LEAK: Raw value '{val}' leaked into details metadata string: '{obj}'!"
                )
        elif isinstance(obj, dict):
            for v in obj.values():
                _search_nested(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                _search_nested(item)

    # When mask=True, _raw_mapping must NOT exist
    assert "_raw_mapping" not in details, (
        "Security failure: '_raw_mapping' leaked in masked details!"
    )

    # Deep scan details
    _search_nested(details)


# =============================================================================
# 1. PII DETECTION: PHONES, FREE-MAIL, REPEATED EMAILS, HOMOGLYPHS & BOUNDARIES
# =============================================================================


class TestPIIDetectionAdversarial:
    """Adversarial edge cases for PII detection (phones, emails, unicode boundaries)."""

    @pytest.mark.parametrize(
        "phone_str,expected_format,expected_support",
        [
            # E.164 variations
            ("+1-202-555-0143", "US", False),
            ("+1 202 555 0143", "US", False),
            ("+1.202.555.0143", "US", False),
            ("+12025550143", "US", False),
            ("+44-20-7946-0958", "international", False),
            ("+44 20 7946 0958", "international", False),
            ("+44.20.7946.0958", "international", False),
            ("+33 1 23 45 67 89", "international", False),
            ("+49-30-1234567", "international", False),
            ("+81-3-1234-5678", "international", False),
            # Toll-free and customer support prefixes
            ("1-800-555-0199", "US", True),
            ("+1-800-555-0199", "US", True),
            ("+1 800 555 0199", "US", True),
            ("0120-123-456", "JP", True),
            ("0800-123-456", "JP", True),
            ("0570-000-111", "JP", True),
            # Standard Japanese landline vs mobile
            ("03-1234-5678", "JP", False),
            ("090-1234-5678", "JP", False),  # Mobile prefix -> never support
            ("080-9876-5432", "JP", False),
            ("070-1122-3344", "JP", False),
        ],
    )
    def test_international_phone_variations(
        self, phone_str: str, expected_format: str, expected_support: bool
    ):
        raw_doc = f"Contact us at {phone_str} for details."
        masked, count, details = mask_sensitive_data(raw_doc, return_details=True)

        assert count == 1
        assert "[PHONE_1]" in masked
        assert phone_str not in masked

        phone_feats = details["redacted_phones"]
        assert len(phone_feats) == 1
        feat = phone_feats[0]
        assert feat["country_format"] == expected_format
        assert feat["looks_like_support"] == expected_support
        _assert_zero_leak([phone_str], masked, details)

    def test_japanese_mobile_near_support_keyword_remains_personal(self):
        """JP mobile numbers (090/080/070) must remain personal even next to support keywords."""
        doc = "カスタマーサポート担当者携帯: 090-9988-7766 (問い合わせ窓口)"
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 1
        assert details["pii_personal"] == 1
        assert details["pii_role"] == 0
        feat = details["redacted_phones"][0]
        assert feat["looks_like_support"] is False
        _assert_zero_leak(["090-9988-7766"], masked, details)

    def test_phone_wrapped_in_brackets_and_parentheses(self):
        """Phone numbers enclosed in parentheses or brackets should be correctly parsed."""
        doc = "Emergency: (+1-202-555-0143) or [+44-20-7946-0958]."
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 2
        assert "([PHONE_1])" in masked
        assert "[[PHONE_2]]" in masked
        _assert_zero_leak(["+1-202-555-0143", "+44-20-7946-0958"], masked, details)

    def test_phone_regex_internal_parentheses_boundary(self):
        """Documents the regex boundary: numbers with internal parentheses like +1 (202) 555-0143.

        The PHONE_PATTERN expects separator characters ([-.\\s]?), so internal parentheses
        break the full match. Red team verifies exact boundary behavior.
        """
        feats = extract_phone_features("+1-202-555-0143")
        assert feats["country_format"] == "US"

        doc = "Office: +1 (202) 555-0143"
        # Document boundary behavior: PHONE_PATTERN delimiter set
        masked, count = mask_sensitive_data(doc)
        # Internal parentheses are outside the delimiter class [-.\\s]?
        assert "(" in masked

    @pytest.mark.parametrize(
        "email,expected_domain_type,expected_role_outcome",
        [
            ("user@gmail.com", "free_mail", "personal"),
            ("user@googlemail.com", "free_mail", "personal"),
            ("user@yahoo.com", "free_mail", "personal"),
            ("user@ymail.com", "free_mail", "personal"),
            ("user@hotmail.com", "free_mail", "personal"),
            ("user@outlook.com", "free_mail", "personal"),
            ("user@live.com", "free_mail", "personal"),
            ("user@msn.com", "free_mail", "personal"),
            ("user@icloud.com", "free_mail", "personal"),
            ("user@me.com", "free_mail", "personal"),
            ("user@mac.com", "free_mail", "personal"),
            ("user@aol.com", "free_mail", "personal"),
            ("user@proton.me", "free_mail", "personal"),
            ("user@protonmail.com", "free_mail", "personal"),
            ("user@zoho.com", "free_mail", "personal"),
            ("user@mail.com", "free_mail", "personal"),
            ("user@gmx.com", "free_mail", "personal"),
            # Mixed and upper case domain variations
            ("USER@GMAIL.COM", "free_mail", "personal"),
            ("Admin@HOTMAIL.COM", "free_mail", "personal"),
            ("Support@Proton.Me", "free_mail", "personal"),
            # Local part looks like a role word, but free-mail domain takes absolute precedence
            ("support@gmail.com", "free_mail", "personal"),
            ("admin@outlook.com", "free_mail", "personal"),
            ("security@yahoo.com", "free_mail", "personal"),
            ("billing@protonmail.com", "free_mail", "personal"),
            # Dotted and plus addressing
            ("first.last+tag@googlemail.com", "free_mail", "personal"),
            ("dev-test.123@proton.me", "free_mail", "personal"),
            # Corporate role words
            ("security@internal-corp.io", "corporate", "role"),
            ("customercare@acme-systems.com", "corporate", "role"),
            ("billing-team@enterprise.org", "corporate", "role"),
            ("press@company.co.uk", "corporate", "role"),
        ],
    )
    def test_email_freemail_and_role_classification(
        self, email: str, expected_domain_type: str, expected_role_outcome: str
    ):
        feats = extract_email_features(email)
        assert feats["domain_type"] == expected_domain_type

        classified = classify_email(email)
        assert classified == expected_role_outcome

        masked, count, details = mask_sensitive_data(f"Contact {email}.", return_details=True)
        assert count == 1
        assert "[EMAIL_1]" in masked
        assert email not in masked

        if expected_domain_type == "free_mail":
            assert details["pii_personal"] == 1
            assert details["pii_role"] == 0
        elif expected_role_outcome == "role":
            assert details["pii_role"] == 1
            assert details["pii_personal"] == 0

        _assert_zero_leak([email], masked, details)

    def test_multiple_distinct_emails_on_same_line(self):
        """Multiple emails on a single line must all be individually masked with correct indices."""
        line = (
            "Escalation path: Alice <alice.smith@gmail.com>, "
            "Bob <bob.lead@internal-corp.com>, "
            "and Helpdesk <support@internal-corp.com>."
        )
        masked, count, details = mask_sensitive_data(line, return_details=True)

        assert count == 3
        assert "[EMAIL_1]" in masked
        assert "[EMAIL_2]" in masked
        assert "[EMAIL_3]" in masked

        raw_emails = [
            "alice.smith@gmail.com",
            "bob.lead@internal-corp.com",
            "support@internal-corp.com",
        ]
        _assert_zero_leak(raw_emails, masked, details)

        # Check types breakdown
        assert details["pii_personal"] == 2  # Alice (freemail) + Bob (corporate personal)
        assert details["pii_role"] == 1  # Support (corporate role)

    def test_same_email_repeated_across_document(self):
        """Repeated occurrences of the same email must reuse the exact same placeholder."""
        doc = (
            "First contact: dev@corp.com.\n"
            "Second contact: dev@corp.com.\n"
            "Final notice to dev@corp.com."
        )
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 3
        assert masked.count("[EMAIL_1]") == 3
        assert "[EMAIL_2]" not in masked
        assert len(details["redacted_emails"]) == 1
        _assert_zero_leak(["dev@corp.com"], masked, details)

    def test_custom_role_glob_patterns_adversarial(self):
        """Custom role glob patterns must match complex prefixes/suffixes, but yield to freemail."""
        patterns = ["sec-*", "*-triage", "*_duty", "*-infra-*"]

        assert classify_email("sec-lead@company.com", patterns) == "role"
        assert classify_email("backend-triage@company.com", patterns) == "role"
        assert classify_email("on_duty@company.com", patterns) == "role"
        assert classify_email("emea-infra-ops@company.com", patterns) == "role"

        # Free-mail must always take precedence over custom globs
        assert classify_email("sec-lead@gmail.com", patterns) == "personal"
        assert classify_email("backend-triage@yahoo.com", patterns) == "personal"

        doc = "Reach out to sec-lead@company.com or sec-lead@gmail.com."
        masked, count, details = mask_sensitive_data(
            doc, return_details=True, custom_role_patterns=patterns
        )
        assert count == 2
        assert details["pii_role"] == 1
        assert details["pii_personal"] == 1
        _assert_zero_leak(["sec-lead@company.com", "sec-lead@gmail.com"], masked, details)

    def test_email_surrounding_punctuation_boundaries(self):
        """Punctuation surrounding email addresses must not be swallowed or break boundary."""
        doc = "Emails: <user1@company.com>, (user2@company.com), [user3@company.com], 'user4@company.com'."
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 4
        assert "<[EMAIL_1]>" in masked
        assert "([EMAIL_2])" in masked
        assert "[[EMAIL_3]]" in masked
        assert "'[EMAIL_4]'" in masked
        _assert_zero_leak(
            ["user1@company.com", "user2@company.com", "user3@company.com", "user4@company.com"],
            masked,
            details,
        )


# =============================================================================
# 2. SECRET DETECTION: COMPLEX JSON/YAML, MULTILINE COMMENTS, BACKTICKS & SPECS
# =============================================================================


class TestSecretDetectionAdversarial:
    """Adversarial edge cases for credential and ambiguous secret detection."""

    @pytest.mark.parametrize(
        "secret_val,expected_placeholder,expected_type",
        [
            ("AKIA1234567890ABCDEF", "[REDACTED_AWS_KEY]", "aws_key"),
            ("ghp_123456789012345678901234567890123456", "[REDACTED_GH_TOKEN]", "github_token"),
            ("gho_123456789012345678901234567890123456", "[REDACTED_GH_TOKEN]", "github_token"),
            ("ghu_123456789012345678901234567890123456", "[REDACTED_GH_TOKEN]", "github_token"),
            ("ghs_123456789012345678901234567890123456", "[REDACTED_GH_TOKEN]", "github_token"),
            ("ghr_123456789012345678901234567890123456", "[REDACTED_GH_TOKEN]", "github_token"),
            ("xoxb-1234567890-abcdef123456", "[REDACTED_SLACK_TOKEN]", "slack_token"),
            ("xoxp-1234567890-abcdef123456", "[REDACTED_SLACK_TOKEN]", "slack_token"),
            ("xoxa-1234567890-abcdef123456", "[REDACTED_SLACK_TOKEN]", "slack_token"),
            ("xoxs-1234567890-abcdef123456", "[REDACTED_SLACK_TOKEN]", "slack_token"),
            ("xoxr-1234567890-abcdef123456", "[REDACTED_SLACK_TOKEN]", "slack_token"),
            ("sk" + "_live_1234567890abcdef12345678", "[REDACTED_SECRET_KEY]", "secret_key"),
            ("sk" + "_test_1234567890abcdef12345678", "[REDACTED_SECRET_KEY]", "secret_key"),
            ("sk-1234567890abcdef1234567890", "[REDACTED_SECRET_KEY]", "secret_key"),
            ("apikey_1234567890abcdef12345678", "[REDACTED_API_KEY]", "api_key"),
            ("Bearer token_abc1234567890xyz_padding==", "Bearer [REDACTED_TOKEN]", "bearer_token"),
            ("-----BEGIN RSA PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]", "private_key"),
            ("-----BEGIN EC PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]", "private_key"),
            ("-----BEGIN PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]", "private_key"),
        ],
    )
    def test_known_credential_specs_comprehensive(
        self, secret_val: str, expected_placeholder: str, expected_type: str
    ):
        doc = f"Production config: {secret_val}"
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 1
        assert expected_placeholder in masked
        assert details["credentials"] == 1
        assert details["by_type"][expected_type] == 1
        _assert_zero_leak([secret_val], masked, details)

    def test_credential_spec_boundary_rejections(self):
        """Boundary test: tokens that closely resemble credentials but fall short must not falsely match."""
        non_secrets = [
            ("AKIA1234567890abcdef", "AWS requires uppercase"),
            ("AKIA1234567890AB", "AWS requires 16+ chars after prefix"),
            ("ghp_shorttoken", "GitHub token requires 36+ chars"),
            ("ghx_123456789012345678901234567890123456", "Invalid GitHub prefix ghx_"),
            ("xoxb-short", "Slack token requires 10+ chars after prefix"),
            ("xozb-1234567890abcdef123456", "Invalid Slack prefix xozb-"),
            ("sk_dev_1234567890abcdef12345678", "Invalid stripe prefix sk_dev_"),
            ("sk-short123", "Secret key sk- requires 20+ chars"),
        ]
        for token, reason in non_secrets:
            doc = f"Checking {token} for boundary."
            masked, count, details = mask_sensitive_data(doc, return_details=True)
            assert details["credentials"] == 0, f"False positive match for {token} ({reason})"

    def test_placeholder_neutralization_adversarial(self):
        """Tokens with placeholder markers must be neutralized to example placeholders."""
        doc = (
            "Examples:\n"
            "AWS: AKIAIOSFODNN7EXAMPLE\n"
            "AWS2: AKIAEXAMPLEKEY123456\n"
            "API: apikey_your_api_key_here_12345678\n"
            "OpenAI: sk-xxxxxxxxxxxxxxxxxxxxxxxx\n"
            "Bearer: Bearer dummy_token_value_1234567890\n"
        )
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 0  # Examples do not count toward active redaction quota
        assert details["credentials"] == 0
        assert details["examples"] == 5
        assert "[EXAMPLE_AWS_KEY]" in masked
        assert "[EXAMPLE_API_KEY]" in masked
        assert "[EXAMPLE_SECRET_KEY]" in masked
        assert "Bearer [EXAMPLE_TOKEN]" in masked
        _assert_zero_leak(
            [
                "AKIAIOSFODNN7EXAMPLE",
                "AKIAEXAMPLEKEY123456",
                "apikey_your_api_key_here_12345678",
                "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
                "Bearer dummy_token_value_1234567890",
            ],
            masked,
            details,
        )

    def test_ambiguous_secrets_complex_json_payload(self):
        """Complex JSON payload with nested quoted keys, passwords, and tokens."""
        json_doc = """
{
  "database": {
    "host": "10.0.0.15",
    "db_password": "super#complex!password123",
    "passwd": "backup_db_password_456"
  },
  "auth": {
    "api_key": "apikey_9876543210fedcba987654",
    "access_token": "ghp_123456789012345678901234567890123456",
    "secret": "my-arbitrary-secret-token"
  }
}
"""
        masked, count, details = mask_sensitive_data(json_doc, return_details=True)

        # IP 10.0.0.15 is private, plus secrets
        assert "[REDACTED_API_KEY]" in masked
        assert "[REDACTED_GH_TOKEN]" in masked
        assert '"db_password": [SECRET_' in masked
        assert '"passwd": [SECRET_' in masked
        assert '"secret": [SECRET_' in masked

        raw_secrets = [
            "super#complex!password123",
            "backup_db_password_456",
            "apikey_9876543210fedcba987654",
            "ghp_123456789012345678901234567890123456",
            "my-arbitrary-secret-token",
            "10.0.0.15",
        ]
        _assert_zero_leak(raw_secrets, masked, details)

    def test_ambiguous_secrets_complex_yaml_payload(self):
        """Complex YAML payload with single quotes, double quotes, unquoted values, and placeholders."""
        yaml_doc = """
services:
  database:
    db_password: 'single_quoted_secret_val'
    password: "double_quoted_password_val"
    pwd: unquoted_secret_pass_12345
  placeholders:
    api_key: ${CONFIG_API_KEY}
    token: <INSERT_YOUR_TOKEN_HERE>
    secret_key: changeme_default_key
"""
        masked, count, details = mask_sensitive_data(yaml_doc, return_details=True)

        # Placeholders neutralized
        assert details["examples"] >= 3
        # Real secrets detected
        assert "db_password: [SECRET_" in masked
        assert "password: [SECRET_" in masked
        assert "pwd: [SECRET_" in masked

        raw_secrets = [
            "single_quoted_secret_val",
            "double_quoted_password_val",
            "unquoted_secret_pass_12345",
        ]
        _assert_zero_leak(raw_secrets, masked, details)

    def test_secrets_in_multiline_html_comments_masked_and_stripped(self):
        """Secrets inside multiline HTML comments must be detected in metadata, then stripped from output."""
        raw_doc = """# Ops Architecture
<!--
INTERNAL OPS CREDENTIALS:
AWS_KEY=AKIA1234567890ABCDEF
DB_PASSWORD="cluster_root_password_999"
Contact: devops-lead@gmail.com
-->
Public system description begins here.
"""
        # Step 1: Sanitizer masks and extracts features on raw document
        sanitized, count, details = mask_sensitive_data(raw_doc, return_details=True)
        assert count == 3
        assert details["credentials"] >= 1
        assert details["pii_personal"] >= 1
        assert any(s["placeholder"] == "[REDACTED_AWS_KEY]" for s in details["redacted_secrets"])

        # Step 2: Strip comments on sanitized content
        clean_content = strip_html_comments(sanitized)

        # Comment is stripped from clean content
        assert "<!--" not in clean_content
        assert "INTERNAL OPS CREDENTIALS" not in clean_content
        assert "Public system description begins here." in clean_content

        # Zero raw leak verification
        raw_secrets = [
            "AKIA1234567890ABCDEF",
            "cluster_root_password_999",
            "devops-lead@gmail.com",
        ]
        _assert_zero_leak(raw_secrets, sanitized, details)
        _assert_zero_leak(raw_secrets, clean_content, details)

    def test_markdown_backtick_inline_and_fenced_secrets(self):
        """Secrets inside inline backticks and fenced code blocks must be redacted cleanly."""
        doc = """# Security Guide

Use `AKIA1234567890ABCDEF` in your terminal:

```bash
export TYPESAFE_API_KEY="apikey_abcdef1234567890123456"
export SLACK_TOKEN="xoxb-1234567890-abcdef123456"
```
"""
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 3
        assert "`[REDACTED_AWS_KEY]`" in masked
        assert '"[REDACTED_API_KEY]"' in masked
        assert '"[REDACTED_SLACK_TOKEN]"' in masked
        _assert_zero_leak(
            [
                "AKIA1234567890ABCDEF",
                "apikey_abcdef1234567890123456",
                "xoxb-1234567890-abcdef123456",
            ],
            masked,
            details,
        )


# =============================================================================
# 3. ZERO RAW LEAK GUARANTEE AUDIT
# =============================================================================


class TestZeroRawLeakGuarantee:
    """Strict adversarial red team audit verifying zero raw leaks."""

    def test_zero_leak_comprehensive_adversarial_corpus(self):
        """Combined adversarial corpus containing all credential types, PII, IPs, URLs, and phones."""
        stripe_key = "sk" + "_live_abcdef1234567890abcdef12"
        corpus = f"""# Confidential Document
Author: hanako.tanaka@gmail.com
Emergency Phone: +1-202-555-0143
Support Line: 0120-111-222
Server IP: 192.168.1.100 (internal)
Database URL: ldap://ldap.internal/dc=example,dc=com

```json
{{
  "aws_key": "AKIA9876543210FEDCBA",
  "github": "ghp_abcdef1234567890abcdef12345678901234",
  "slack": "xoxb-9988776655-aabbccddeeff",
  "stripe": "{stripe_key}",
  "db_password": "super-private-db-password-123!"
}}
```

<!--
Hidden comment:
api_key: apikey_1122334455667788990011
admin_email: root@admin-internal.corp
-->
"""
        masked, count, details = mask_sensitive_data(corpus, return_details=True)
        assert count > 0

        raw_secrets_and_pii = [
            "hanako.tanaka@gmail.com",
            "+1-202-555-0143",
            "0120-111-222",
            "192.168.1.100",
            "ldap://ldap.internal/dc=example,dc=com",
            "AKIA9876543210FEDCBA",
            "ghp_abcdef1234567890abcdef12345678901234",
            "xoxb-9988776655-aabbccddeeff",
            stripe_key,
            "super-private-db-password-123!",
            "apikey_1122334455667788990011",
            "root@admin-internal.corp",
        ]

        # Audit sanitized content & details metadata
        _assert_zero_leak(raw_secrets_and_pii, masked, details)

        # Audit post-comment-stripping content
        clean = strip_html_comments(masked)
        _assert_zero_leak(raw_secrets_and_pii, clean, details)

    def test_extract_secret_features_state_never_contains_raw_value(self):
        """extract_secret_features contract: state NEVER contains raw value, fragment, or hash."""
        raw_secret = "super_classified_production_password_xyz987"
        feat = extract_secret_features(
            key_name="password",
            raw_val=raw_secret,
            surrounding_text=f"password: {raw_secret}",
            is_known_format=False,
            is_example=False,
        )

        # String representation of features dict must NOT contain any fragment of the secret
        feat_str = str(feat)
        assert raw_secret not in feat_str
        assert "super_classified" not in feat_str
        assert "xyz987" not in feat_str

    def test_masked_url_domain_popped(self):
        """When mask=True, URL features domain key must be popped to prevent raw domain leakage."""
        doc = "Service endpoint: https://sensitive-internal-api.corp/auth"
        masked, count, details = mask_sensitive_data(doc, return_details=True)

        assert count == 1
        assert "[URL_1]" in masked
        assert len(details["redacted_urls"]) == 1
        url_feat = details["redacted_urls"][0]
        assert "domain" not in url_feat, "Leaked domain in URL features when mask=True!"
        _assert_zero_leak(["sensitive-internal-api.corp"], masked, details)


# =============================================================================
# 4. PRESERVING CODE BLOCKS VS STRIPPING PROSE HTML COMMENTS
# =============================================================================


class TestCodeBlockPreservationAndCommentStripping:
    """Rigorous tests for strip_html_comments across code blocks and prose."""

    def test_fenced_code_blocks_triple_backticks_preserved(self):
        """HTML comments inside triple backtick fenced blocks must be preserved."""
        code = """```html
<!-- Safe: This is an HTML template example -->
<div class="header">Title</div>
```"""
        assert strip_html_comments(code) == code

    def test_fenced_code_blocks_triple_tildes_preserved(self):
        """HTML comments inside triple tilde fenced blocks must be preserved."""
        code = """~~~markdown
<!-- Safe: Markdown documentation example -->
# Example Header
~~~"""
        assert strip_html_comments(code) == code

    def test_fenced_code_blocks_with_indentation_preserved(self):
        """Fenced code blocks indented with 1 to 3 spaces must be preserved."""
        for indent in [" ", "  ", "   "]:
            code = f"""{indent}```python
# <!-- Safe inside python block -->
x = 42
{indent}```"""
            assert strip_html_comments(code) == code

    def test_inline_code_spans_preserved(self):
        """HTML comments inside single and multi-backtick inline spans must be preserved."""
        single_tick = "Refer to `<!-- safe inline -->` in your code."
        assert strip_html_comments(single_tick) == single_tick

        double_tick = "Refer to ``<!-- safe inline with ` backtick -->`` in your code."
        assert strip_html_comments(double_tick) == double_tick

    def test_interleaved_prose_and_code_blocks(self):
        """Prose HTML comments must be stripped, while adjacent code blocks are untouched."""
        doc = """# Architecture Plan

<!-- Internal comment 1: to be stripped -->

```python
# <!-- Code comment 1: MUST NOT BE STRIPPED -->
def start():
    pass
```

<!-- Internal comment 2: to be stripped -->

~~~yaml
# <!-- Code comment 2: MUST NOT BE STRIPPED -->
server:
  port: 8080
~~~

<!-- Internal comment 3: to be stripped -->
"""
        stripped = strip_html_comments(doc)

        # Prose comments stripped
        assert "Internal comment 1" not in stripped
        assert "Internal comment 2" not in stripped
        assert "Internal comment 3" not in stripped

        # Code block comments preserved
        assert "<!-- Code comment 1: MUST NOT BE STRIPPED -->" in stripped
        assert "<!-- Code comment 2: MUST NOT BE STRIPPED -->" in stripped

    def test_unclosed_html_comments_preserved(self):
        """Unclosed HTML comments without matching --> are left as-is to avoid mangling doc."""
        doc = "Some text <!-- unclosed comment that continues to EOF"
        assert strip_html_comments(doc) == doc

    def test_html_comment_with_internal_dashes(self):
        """HTML comments containing internal dashes (e.g. <!-- foo -- bar -->) must be stripped."""
        doc = "Start <!-- comment -- with -- double -- dashes --> End"
        assert strip_html_comments(doc) == "Start  End"

    def test_multiline_prose_comment_with_blank_lines(self):
        """Multiline comments with internal blank lines in prose must be stripped completely."""
        doc = "Header\n<!--\nLine 1\n\nLine 2\n\nLine 3\n-->\nFooter"
        assert strip_html_comments(doc) == "Header\n\nFooter"


# =============================================================================
# 5. CREDENTIAL PLACEHOLDER CHECKER DIRECT UNIT TESTS
# =============================================================================


class TestCredentialPlaceholderChecker:
    """Direct unit tests for is_credential_placeholder."""

    @pytest.mark.parametrize(
        "token,expected",
        [
            ("AKIAIOSFODNN7EXAMPLE", True),
            ("AKIAEXAMPLEKEY123456", True),
            ("AKIA1234567890ABCDEF", False),
            ("your_api_key_here", True),
            ("dummy_secret_value", True),
            ("xxxx-xxxx-xxxx-xxxx", True),
            ("replace_me_with_key", True),
            ("insert_secret_here", True),
            ("changeme_default_pwd", True),
            ("real_production_secret_token_12345", False),
        ],
    )
    def test_is_credential_placeholder(self, token: str, expected: bool):
        assert is_credential_placeholder(token) == expected
