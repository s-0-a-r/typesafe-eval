"""Tests for character offset to line/column tracking and structured violations."""

from typesafe_eval.models import DocumentEvalResult, SecretEvaluationResult, ViolationItem
from typesafe_eval.reporter import render_github_annotations
from typesafe_eval.sanitizer import mask_sensitive_data, offset_to_line_col


def test_offset_to_line_col_basic() -> None:
    text = "hello\nworld\nfoo bar"
    # line 1
    assert offset_to_line_col(text, 0) == (1, 1)
    assert offset_to_line_col(text, 4) == (1, 5)
    # newline at index 5
    assert offset_to_line_col(text, 5) == (1, 6)
    # line 2: 'world' starts at index 6
    assert offset_to_line_col(text, 6) == (2, 1)
    assert offset_to_line_col(text, 10) == (2, 5)
    # line 3: 'foo bar' starts at index 12
    assert offset_to_line_col(text, 12) == (3, 1)
    assert offset_to_line_col(text, 16) == (3, 5)


def test_offset_to_line_col_empty_and_single_line() -> None:
    assert offset_to_line_col("", 0) == (1, 1)
    assert offset_to_line_col("single line", 7) == (1, 8)


def test_sanitizer_tracks_secret_coordinates() -> None:
    slack_token = "xoxb-" + "1234567890" + "-abcdef123456"
    doc = f"# Configuration\n\nHere is the token:\n{slack_token}\n\nDone.\n"
    sanitized, count, details = mask_sensitive_data(doc, mask=True, return_details=True)
    assert count >= 1
    secrets = details.get("redacted_secrets", [])
    assert len(secrets) == 1
    sec = secrets[0]
    # Token is on line 4, starting at column 1
    assert sec["line"] == 4
    assert sec["column"] == 1
    assert sec["end_line"] == 4
    assert sec["end_column"] == len(slack_token) + 1


def test_sanitizer_tracks_email_coordinates() -> None:
    doc = "Title\nContact me at alice.smith@gmail.com for details.\n"
    sanitized, count, details = mask_sensitive_data(doc, mask=True, return_details=True)
    emails = details.get("redacted_emails", [])
    assert len(emails) == 1
    em = emails[0]
    # 'alice.smith@gmail.com' starts at column 15 of line 2
    assert em["line"] == 2
    assert em["column"] == 15
    assert em["end_line"] == 2
    assert em["end_column"] == 36


def test_document_eval_result_populates_structured_violations() -> None:
    sec = SecretEvaluationResult(
        placeholder="[SECRET_1]",
        features={"line": 10, "column": 5, "end_line": 10, "end_column": 45},
        outcome="secret",
        decided_by="rule",
    )
    result = DocumentEvalResult(
        filepath="docs/auth.md",
        filename="auth.md",
        preset_name="safety",
        passed_thresholds=False,
        secret_evaluations=[sec],
        violations=["Credential Exposure: [SECRET_1] is a known format secret"],
        warnings=["[SECRET_1] near threshold warning"],
    )
    assert len(result.structured_violations) == 2
    err_v = result.structured_violations[0]
    assert err_v.level == "error"
    assert err_v.line == 10
    assert err_v.column == 5
    assert err_v.end_line == 10
    assert err_v.end_column == 45
    assert "[SECRET_1]" in err_v.message

    warn_v = result.structured_violations[1]
    assert warn_v.level == "warning"
    assert warn_v.line == 10
    assert warn_v.column == 5


def test_render_github_annotations() -> None:
    result = DocumentEvalResult(
        filepath="docs/secret.md",
        filename="secret.md",
        preset_name="safety",
        passed_thresholds=False,
        structured_violations=[
            ViolationItem(
                message="Exposed AWS key",
                line=12,
                column=3,
                end_line=12,
                end_column=23,
                level="error",
            ),
            ViolationItem(
                message="Advisory: Readability could be improved",
                line=None,
                column=None,
                level="warning",
            ),
        ],
    )
    annotations = render_github_annotations([result])
    lines = annotations.splitlines()
    assert len(lines) == 2
    assert (
        lines[0]
        == "::error file=docs/secret.md,line=12,col=3,endLine=12,endColumn=23::Exposed AWS key"
    )
    assert lines[1] == "::warning file=docs/secret.md::Advisory: Readability could be improved"
