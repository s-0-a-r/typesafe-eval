# Redaction, Masking & Zero Raw Leak Guarantee

How `typesafe-eval` sanitizes documents before network evaluation to protect sensitive credentials and personal data.

---

## The Zero Raw Leak Guarantee

`typesafe-eval` guarantees that **raw credentials, secret keys, and personal phone/email strings never leave your machine**:

1. **Local Redaction**: Regex engines and rules identify secrets and personal contacts entirely on your local machine before any network request is formed.
2. **Payload Sanitization**: The payload transmitted to the TypeSafe System One API replaces sensitive values with synthetic tokens (e.g., `[SECRET_1]`, `[EMAIL_1]`).
3. **Safe Diagnostics**: In JSON output, metadata, and error messages, raw secrets are never displayed. Only masked placeholders (e.g. `[REDACTED_AWS_KEY]`) are emitted.

---

## Sanitization Order & Prose Comment Stripping

To ensure maximum safety, sanitization follows a strict two-stage sequence:

1. **Secret & PII Detection (First)**: Regex detectors identify secrets, API keys, credentials, and PII across the entire document text (including within HTML comments). This guarantees that even secrets hidden inside HTML comments are flagged as violations.
2. **Prose Comment Stripping (Second)**: HTML comments in regular prose are stripped from the payload before contextual evaluation or transmission to the TypeSafe System One API.

```markdown
Here is the public API design.
<!-- Note: Internal staging key is AKIAIOSFODNN7EXAMPLE -->
```

By default (`strip_prose_comments=True`):
- The credential `AKIAIOSFODNN7EXAMPLE` is caught in stage 1, registered as a violation, and masked.
- The prose comment `<!-- ... -->` is then stripped from the evaluation payload sent to the API.
- **Fenced code blocks are preserved**: Comments inside fenced markdown code blocks (e.g. ` ```html <!-- safe comment --> ``` `) are preserved untouched so technical code examples are not corrupted.
