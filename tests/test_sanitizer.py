from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

def test_mask_sensitive_data():
    raw = "My API key is apikey_abc1234567890abcdef123456 and email user@example.com."
    masked, count = mask_sensitive_data(raw)
    assert count == 2
    assert "apikey_" not in masked
    assert "user@example.com" not in masked
    assert "[REDACTED_API_KEY]" in masked
    assert "[REDACTED_PERSONAL_EMAIL]" in masked

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
    assert "[REDACTED_ROLE_EMAIL]" in masked
    assert "[REDACTED_PERSONAL_EMAIL]" in masked

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
