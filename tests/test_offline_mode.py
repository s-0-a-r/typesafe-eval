"""Tests for offline / rules-only evaluation mode (--offline / --rules-only)."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from typesafe_eval.api import evaluate
from typesafe_eval.cli import main


def test_python_api_offline_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    content = "# Clean System Architecture\n\nNo sensitive keys or emails here.\n"
    res = evaluate(content, preset="safety", offline=True)
    assert res.passed_thresholds is True
    assert len(res.violations) == 0
    assert res.api_calls == 0
    assert res.model == "offline-rules"


def test_python_api_offline_violating(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    slack_token = "xoxb-" + "1234567890" + "-abcdef123456"
    content = f"# Config\napi_key: {slack_token}\ncontact: bob.builder@gmail.com\n"
    res = evaluate(content, preset="safety", offline=True)
    assert res.passed_thresholds is False
    assert len(res.violations) >= 2
    assert res.api_calls == 0
    assert res.model == "offline-rules"
    assert any("Credential Exposure" in v for v in res.violations)
    assert any("PII Exposure" in v for v in res.violations)
    # Check that position tracking is preserved
    assert len(res.structured_violations) >= 2
    assert all(v.line is not None for v in res.structured_violations)


def test_cli_offline_clean_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean Architecture\n\nAll clear.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "--offline"])
    assert result.exit_code == 0


def test_cli_offline_violating_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    slack_token = "xoxb-" + "1234567890" + "-abcdef123456"
    doc = tmp_path / "secrets.md"
    doc.write_text(
        f"# Sensitive Config\nsecret: {slack_token}\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "--offline"])
    assert result.exit_code == 1
    assert "Credential Exposure" in result.output


def test_cli_rules_only_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean\n\nOK.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "--rules-only"])
    assert result.exit_code == 0
