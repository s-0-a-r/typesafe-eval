from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

def test_mask_sensitive_data():
    raw = "My API key is apikey_abc1234567890abcdef123456 and email user@example.com."
    masked, count = mask_sensitive_data(raw)
    assert count == 2
    assert "apikey_" not in masked
    assert "user@example.com" not in masked
    assert "[REDACTED_API_KEY]" in masked
    assert "[REDACTED_EMAIL]" in masked

def test_mask_sensitive_data_details():
    raw = (
        "AWS: AKIA1234567890ABCDEF, "
        "GH: ghp_123456789012345678901234567890123456, "
        "Bearer: Bearer my_secret_token_1234567890_xyz, "
        "Email: test@company.com"
    )
    masked, count, details = mask_sensitive_data(raw, return_details=True)
    assert count == 4
    assert details["total"] == 4
    assert details["credentials"] == 3
    assert details["pii"] == 1
    assert details["by_type"]["aws_key"] == 1
    assert details["by_type"]["github_token"] == 1
    assert details["by_type"]["bearer_token"] == 1
    assert details["by_type"]["email"] == 1

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
