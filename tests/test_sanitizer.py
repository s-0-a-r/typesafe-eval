from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

def test_mask_sensitive_data():
    raw = "My API key is apikey_abc1234567890abcdef123456 and email user@example.com."
    masked, count = mask_sensitive_data(raw)
    assert count == 2
    assert "apikey_" not in masked
    assert "user@example.com" not in masked
    assert "[REDACTED_API_KEY]" in masked
    assert "[REDACTED_EMAIL]" in masked

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
