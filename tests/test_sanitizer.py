from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

def test_mask_sensitive_data():
    raw = "My API key is apikey_abc1234567890abcdef123456 and email user@example.com."
    masked, count = mask_sensitive_data(raw)
    assert count == 2
    assert "apikey_" not in masked
    assert "user@example.com" not in masked
    assert "[REDACTED_API_KEY]" in masked
    assert "[EMAIL_1]" in masked

def test_mask_sensitive_data_details():
    raw = (
        "AWS: AKIA1234567890ABCDEF, "
        "GH: ghp_123456789012345678901234567890123456, "
        "Bearer: Bearer my_secret_token_1234567890_xyz, "
        "Role: admin@company.com, "
        "Personal: john.doe@gmail.com"
    )
    masked, count, details = mask_sensitive_data(raw, return_details=True)
    assert count == 5
    assert details["total"] == 5
    assert details["credentials"] == 3
    assert details["pii"] == 2
    assert details["pii_role"] == 1
    assert details["pii_personal"] == 1
    assert "[EMAIL_1]" in masked
    assert "[EMAIL_2]" in masked
    assert len(details["redacted_emails"]) == 2
    assert details["redacted_emails"][0]["placeholder"] == "[EMAIL_1]"
    assert details["redacted_emails"][0]["domain_type"] == "corporate"
    assert details["redacted_emails"][1]["placeholder"] == "[EMAIL_2]"
    assert details["redacted_emails"][1]["domain_type"] == "free_mail"

def test_mask_boundaries_and_placeholder_neutralization():
    # Boundary check: task-... and desk-... must not match sk- pattern
    not_secrets = "ID task-1234567890123456789012 and desk-1234567890123456789012"
    masked, count = mask_sensitive_data(not_secrets)
    assert count == 0
    assert masked == not_secrets

    # Placeholder neutralization: dummy / your_ / xxxx are neutralized to [EXAMPLE_*]
    # and must not be flagged as credentials in details
    placeholders = (
        "Config: apikey_your_api_key_here_1234 "
        "OpenAI: sk-xxxxxxxxxxxxxxxxxxxxxxxx "
        "Bearer: Bearer dummy_token_1234567890_xyz "
        "AWS: AKIAEXAMPLEKEY123456"
    )
    masked_ph, count_ph, details_ph = mask_sensitive_data(placeholders, return_details=True)
    assert count_ph == 0
    assert details_ph["credentials"] == 0
    assert details_ph["examples"] == 4
    assert "[EXAMPLE_API_KEY]" in masked_ph
    assert "[EXAMPLE_SECRET_KEY]" in masked_ph
    assert "Bearer [EXAMPLE_TOKEN]" in masked_ph
    assert "[EXAMPLE_AWS_KEY]" in masked_ph

def test_bearer_token_trailing_padding():
    # Issue #20: Trailing '=' padding must not leak outside redaction
    raw = "Authorization: Bearer abcDEF1234567890ghiJKL== next"
    masked, count = mask_sensitive_data(raw)
    assert count == 1
    assert masked == "Authorization: Bearer [REDACTED_TOKEN] next"

def test_classify_email_domain():
    # Issue #18: Free or personal domains should be classified as personal even with role-like local part
    from typesafe_eval.sanitizer import classify_email
    assert classify_email("support@gmail.com") == "personal"
    assert classify_email("admin@yahoo.com") == "personal"
    assert classify_email("support@company.com") == "role"
    assert classify_email("hanako.suzuki@acme-corp.com") == "personal"

def test_generic_and_team_role_emails():
    # Issue #27: Common generic addresses and team affixes should be role emails
    from typesafe_eval.sanitizer import classify_email, mask_sensitive_data
    assert classify_email("hello@company.com") == "role"
    assert classify_email("hi@company.com") == "role"
    assert classify_email("notifications@company.com") == "role"
    assert classify_email("accounts@company.com") == "role"
    assert classify_email("newsletter@company.com") == "role"
    assert classify_email("hr-team@company.com") == "role"
    assert classify_email("dev-team@company.com") == "role"
    assert classify_email("team-infra@company.com") == "role"
    assert classify_email("it-support@company.com") == "role"

    # Free domain takes precedence
    assert classify_email("hello@gmail.com") == "personal"
    assert classify_email("team@yahoo.com") == "personal"

    # Masking test
    masked, count, details = mask_sensitive_data("Questions? Write to hello@company.com for help.", return_details=True)
    assert count == 1
    assert details["pii_role"] == 1
    assert details["pii_personal"] == 0
    assert "[EMAIL_1]" in masked
    assert "hello@company.com" not in masked

def test_example_key_doc_snippet_regression():
    # Issue #17: Example key snippet from README/docs
    snippet = """
    ## Setup

    Set your API key before running the CLI:

    ```bash
    export TYPESAFE_API_KEY=apikey_your_api_key_here_1234567890
    ```
    """
    masked, count, details = mask_sensitive_data(snippet, return_details=True)
    assert count == 0
    assert details["credentials"] == 0
    assert details["examples"] == 1
    assert "[EXAMPLE_API_KEY]" in masked
    assert "apikey_your_api_key_here_1234567890" not in masked

def test_guard_document_length_normal():
    text = "Short document content."
    processed, truncated = guard_document_length(text, max_chars=100)
    assert not truncated
    assert processed == text

def test_guard_document_length_truncate():
    text = "A" * 500
    processed, truncated = guard_document_length(text, max_chars=100)
    assert truncated
    assert len(processed) < 500
    assert "TRUNCATED" in processed

def test_custom_role_email_glob_patterns():
    from typesafe_eval.sanitizer import classify_email, mask_sensitive_data
    patterns = ["helpdesk", "ops-*", "*-duty", "*-incident-*"]

    # Exact match
    assert classify_email("helpdesk@company.com", patterns) == "role"
    # Prefix match
    assert classify_email("ops-lead@company.com", patterns) == "role"
    # Suffix match
    assert classify_email("night-duty@company.com", patterns) == "role"
    # Infix match
    assert classify_email("apac-incident-response@company.com", patterns) == "role"

    # Unmatched custom email defaults to personal
    assert classify_email("random.engineer@company.com", patterns) == "personal"

    # Free personal domains still take precedence
    assert classify_email("helpdesk@gmail.com", patterns) == "personal"
    assert classify_email("ops-lead@yahoo.com", patterns) == "personal"

    # Masking with custom patterns
    doc = "For assistance reach out to ops-lead@company.com or john@company.com."
    masked, count, details = mask_sensitive_data(doc, return_details=True, custom_role_patterns=patterns)
    assert count == 2
    assert details["pii_role"] == 1
    assert details["pii_personal"] == 1
    assert "ops-lead@company.com" not in masked
    assert "john@company.com" not in masked
    assert "[EMAIL_1]" in masked
    assert "[EMAIL_2]" in masked


def test_chunk_text_within_limit():
    from typesafe_eval.sanitizer import chunk_text
    text = "Short document content."
    chunks = chunk_text(text, max_chars=100)
    assert chunks == [text]


def test_chunk_text_splits_with_overlap():
    from typesafe_eval.sanitizer import chunk_text
    paragraphs = [f"Paragraph {i}: " + ("x" * 100) for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=500, overlap=100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 500
    # Verify every paragraph is present in at least one chunk
    for p in paragraphs:
        assert any(p in c for c in chunks)


def test_chunk_text_no_newlines():
    from typesafe_eval.sanitizer import chunk_text
    text = "a" * 1500
    chunks = chunk_text(text, max_chars=500, overlap=100)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= 500


def test_chunk_text_invalid_max_chars():
    from typesafe_eval.sanitizer import chunk_text
    import pytest
    with pytest.raises(ValueError):
        chunk_text("some text", max_chars=0)


def test_strip_html_comments_single_line():
    from typesafe_eval.sanitizer import strip_html_comments
    text = "Hello <!-- this is a single-line comment --> World"
    assert strip_html_comments(text) == "Hello  World"


def test_strip_html_comments_multi_line():
    from typesafe_eval.sanitizer import strip_html_comments
    text = "Line 1\n<!--\nthis is a\nmulti-line\ncomment\n-->\nLine 2"
    assert strip_html_comments(text) == "Line 1\n\nLine 2"


def test_strip_html_comments_fenced_block_kept():
    from typesafe_eval.sanitizer import strip_html_comments
    backtick_fence = "```python\n# <!-- comment in backticks -->\nx = 1\n```"
    assert strip_html_comments(backtick_fence) == backtick_fence

    tilde_fence = "~~~\n<!-- comment in tildes -->\n~~~"
    assert strip_html_comments(tilde_fence) == tilde_fence


def test_strip_html_comments_inline_code_span_kept():
    from typesafe_eval.sanitizer import strip_html_comments
    single_tick = "Here is `<!-- not a comment -->` inline"
    assert strip_html_comments(single_tick) == single_tick

    double_tick = "Here is ``<!-- not a comment -->`` inline"
    assert strip_html_comments(double_tick) == double_tick


def test_strip_html_comments_unclosed_kept():
    from typesafe_eval.sanitizer import strip_html_comments
    text = "Hello <!-- unclosed comment without end"
    assert strip_html_comments(text) == text


def test_strip_html_comments_no_comments_unchanged():
    from typesafe_eval.sanitizer import strip_html_comments
    text = "# Title\n\nThis is a standard document with no comments."
    assert strip_html_comments(text) == text


def test_consecutive_chunks_overlap():
    """A4: Consecutive chunks overlap under defaults on long text and with max_chars=500, overlap=100."""
    from typesafe_eval.sanitizer import chunk_text

    # 1. Defaults on long text
    long_text = ("Section Heading\n\nParagraph text line.\n" * 2000)
    chunks_default = chunk_text(long_text)
    assert len(chunks_default) > 1
    for i in range(len(chunks_default) - 1):
        c1, c2 = chunks_default[i], chunks_default[i + 1]
        assert any(c1[-k:] == c2[:k] for k in range(100, min(len(c1), len(c2))))

    # 2. max_chars=500, overlap=100
    custom_text = ("a" * 490 + "\n" + "b" * 490 + "\n") * 5
    chunks_custom = chunk_text(custom_text, max_chars=500, overlap=100)
    assert len(chunks_custom) > 1
    for i in range(len(chunks_custom) - 1):
        c1, c2 = chunks_custom[i], chunks_custom[i + 1]
        assert any(c1[-k:] == c2[:k] for k in range(10, min(len(c1), len(c2))))


