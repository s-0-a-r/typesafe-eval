"""Tests for GitHub Actions workflow commands formatter in CLI."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main


def test_cli_github_format_clean_doc(tmp_path: Path) -> None:
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean Architecture\n\nAll good.\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "--dry-run", "-f", "github"])
    assert result.exit_code == 0
    # Clean doc should produce no error annotations
    assert "::error" not in result.output


def test_cli_github_format_violating_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typesafe_eval.client import TypeSafeEvaluator
    from typesafe_eval.models import DocumentEvalResult, SecretEvaluationResult, ViolationItem

    slack_token = "xoxb-" + "1234567890" + "-abcdef123456"
    doc = tmp_path / "secrets.md"
    doc.write_text(
        f"# Config\napi_key: {slack_token}\ncontact: bob.builder@gmail.com\n",
        encoding="utf-8",
    )

    mock_result = DocumentEvalResult(
        filepath=str(doc),
        filename="secrets.md",
        preset_name="safety",
        passed_thresholds=False,
        secret_evaluations=[
            SecretEvaluationResult(
                placeholder="[SECRET_1]",
                line=2,
                column=10,
                end_line=2,
                end_column=66,
                outcome="secret",
                decided_by="rule",
            )
        ],
        violations=["Credential Exposure: [SECRET_1] is a known format secret"],
        structured_violations=[
            ViolationItem(
                message="Credential Exposure: [SECRET_1] is a known format secret",
                line=2,
                column=10,
                end_line=2,
                end_column=66,
                level="error",
            )
        ],
    )

    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: mock_result,
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "-f", "github"])
    assert result.exit_code == 1
    assert "::error file=" in result.output
    assert "line=2,col=10" in result.output
