"""Unit tests for safety detection in HTML comments before stripping (#80)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.validator import load_labels_file, run_validation


def _make_mock_client():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {
        "confidentiality_risk": MagicMock(
            score=0.1, confidence=0.9, probabilities={"0": 0.9, "1": 0.1}
        )
    }
    mock_resp.nouls = {
        "has_secrets": MagicMock(noul=0.1),
        "has_pii": MagicMock(noul=0.1),
        "secret_1": MagicMock(noul=0.85),
        "email_pii_1": MagicMock(noul=0.85),
    }
    mock_resp.choices = {
        "policy_compliance": MagicMock(
            choice="compliant",
            confidence=0.9,
            probabilities={"compliant": 0.9, "non_compliant": 0.1},
        )
    }
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    return mock_client


def test_secret_in_html_comment_known_format_masked(tmp_path: Path):
    """Known format secret in HTML comment must be detected and flagged in masked mode."""
    doc = tmp_path / "secret_comment.md"
    doc.write_text(
        "# Safe Document\n"
        "<!-- DB_PASSWORD=AKIA1234567890ABCDEF -->\n"
        "All database operations are encrypted.\n",
        encoding="utf-8",
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")
    mock_client = _make_mock_client()
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    # 1. Detected in redaction details
    assert result.redaction_details is not None
    assert result.redaction_details["credentials"] >= 1
    assert any(
        s["placeholder"] == "[REDACTED_AWS_KEY]" and s["is_known_format"]
        for s in result.redaction_details["redacted_secrets"]
    )

    # 2. Flagged by deterministic rule
    assert any(
        s.placeholder == "[REDACTED_AWS_KEY]" and s.outcome == "secret" and s.decided_by == "rule"
        for s in result.secret_evaluations
    )
    assert not result.passed_thresholds
    assert any("Credential Exposure" in v for v in result.violations)

    # 3. Model receives text with comment stripped
    sent_state = mock_client.system_one.call_args.kwargs["state"]
    assert "<!--" not in sent_state["document"]
    assert "AKIA1234567890ABCDEF" not in sent_state["document"]


def test_secret_in_html_comment_known_format_no_mask(tmp_path: Path):
    """Known format secret in HTML comment must be detected and flagged in --no-mask mode."""
    doc = tmp_path / "secret_comment_no_mask.md"
    doc.write_text(
        "# Safe Document\n"
        "<!-- DB_PASSWORD=AKIA1234567890ABCDEF -->\n"
        "All database operations are encrypted.\n",
        encoding="utf-8",
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")
    mock_client = _make_mock_client()
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=False)

    assert result.redaction_details is not None
    assert result.redaction_details["credentials"] >= 1
    assert any(
        s.placeholder == "[REDACTED_AWS_KEY]" and s.outcome == "secret" and s.decided_by == "rule"
        for s in result.secret_evaluations
    )
    assert not result.passed_thresholds

    # Sent document to model has comment stripped
    sent_state = mock_client.system_one.call_args.kwargs["state"]
    assert "<!--" not in sent_state["document"]
    assert "AKIA1234567890ABCDEF" not in sent_state["document"]


@pytest.mark.parametrize("mask", [True, False])
def test_free_mail_email_in_html_comment(tmp_path: Path, mask: bool):
    """Personal free-mail email in HTML comment must be detected and flagged in both modes."""
    doc = tmp_path / "email_comment.md"
    doc.write_text(
        "# Contact Guide\n"
        "<!-- internal note: escalated to dev_admin@gmail.com -->\n"
        "Please use official support channels.\n",
        encoding="utf-8",
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")
    mock_client = _make_mock_client()
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=mask)

    assert result.redaction_details is not None
    assert result.redaction_details["pii_personal"] >= 1
    assert any(
        e.outcome == "personal" and e.decided_by == "free_mail" for e in result.email_evaluations
    )
    assert not result.passed_thresholds
    assert any("PII Exposure" in v for v in result.violations)

    sent_state = mock_client.system_one.call_args.kwargs["state"]
    assert "<!--" not in sent_state["document"]
    assert "dev_admin@gmail.com" not in sent_state["document"]


def test_dry_run_detects_prose_secrets_and_pii_in_html_comments(tmp_path: Path):
    """Dry run (mock result) inspects raw content including HTML comments."""
    doc = tmp_path / "mock_comments.md"
    doc.write_text(
        "# System Architecture\n"
        "<!-- Legacy note: the password is supersecret123 -->\n"
        "<!-- Created by Taro Yamada -->\n"
        "Production cluster config.\n",
        encoding="utf-8",
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")

    result = evaluator.evaluate_document(str(doc), preset=preset, dry_run=True)
    assert result.mock is True
    assert result.nouls["has_secrets"].probability == 0.90
    assert result.nouls["has_pii"].probability == 0.90


def test_ambiguous_secret_in_html_comment_evaluated_by_model(tmp_path: Path):
    """Ambiguous candidate in HTML comment is evaluated by model without error."""
    doc = tmp_path / "ambiguous_secret_comment.md"
    doc.write_text(
        "# Server Specs\n"
        "<!-- api_key: customsecrettoken987654321 -->\n"
        "Overview of system services.\n",
        encoding="utf-8",
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")
    mock_client = _make_mock_client()
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    assert "secret_1" in mock_client.system_one.call_args.kwargs["questions"]
    assert any(
        s.placeholder == "[SECRET_1]" and s.outcome == "secret" and s.decided_by == "model"
        for s in result.secret_evaluations
    )
    # Ensure no false unplaced warnings
    assert not any("were not found in any of the chunks" in w for w in result.warnings)


@pytest.mark.parametrize("mask", [True, False])
def test_long_document_html_comment_secret_no_unplaced_warning(tmp_path: Path, mask: bool):
    """Long chunked document with comment secret stripped does not emit false unplaced warnings."""
    # Build text > 20000 characters
    filler = "This is normal public operational documentation.\n" * 500
    comment = "<!-- DB_PASSWORD=AKIA1234567890ABCDEF -->\n"
    content = f"# Long Ops Manual\n{comment}\n{filler}"
    doc = tmp_path / "long_ops.md"
    doc.write_text(content, encoding="utf-8")

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")
    mock_client = _make_mock_client()
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=mask)

    # Known format secret is detected and flagged
    assert any(
        s.placeholder == "[REDACTED_AWS_KEY]" and s.outcome == "secret" and s.decided_by == "rule"
        for s in result.secret_evaluations
    )
    # Stripped comment placeholders should NOT be reported as unplaced boundary warnings
    assert not any("were not found in any of the chunks" in w for w in result.warnings)


def test_validation_with_comment_secret_masked_mode(tmp_path: Path):
    """Validation in masked mode handles HTML comment secret without triggering false matching-bug runtime error."""
    doc = tmp_path / "comment_secret_doc.md"
    doc.write_text(
        "# Safe Document\n<!-- DB_PASSWORD=AKIA1234567890ABCDEF -->\nDocumentation content.\n",
        encoding="utf-8",
    )

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"""preset: safety
documents:
  - path: {doc.name}
    expect:
      has_secrets: present
      has_pii: absent
""",
        encoding="utf-8",
    )

    labels_cfg, base_dir = load_labels_file(labels_file)
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    report, has_runtime_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=base_dir,
        evaluator=evaluator,
        runs_override=1,
        dry_run=True,
        mask_secrets=True,
    )

    # Must NOT have runtime error from unplaced warning
    assert not has_runtime_error
    assert len(report.unplaced_warnings) == 0

    # Also test via CLI
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "--dry-run"])
    assert result.exit_code != 3
    assert "Unplaced item in masked mode" not in (result.stderr or result.output)
