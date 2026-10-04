"""Comprehensive tests for Issue #45: Dry-run mock, verdict N/A, exit 0 for every preset."""

import json

import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import list_builtin_presets, load_preset


@pytest.mark.parametrize("preset_name", list_builtin_presets())
def test_dry_run_exit_0_for_every_builtin_preset(tmp_path, preset_name):
    """AC 3: Exit code 0 for every preset on --dry-run."""
    doc = tmp_path / "sample.md"
    doc.write_text(
        "# Engineering Doc\n"
        "Contact: alice@acme.com\n"
        "Key: apikey_1234567890abcdef123456\n"
        "Content text for evaluation.",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", preset_name, "--dry-run"])
    assert result.exit_code == 0, (
        f"Preset {preset_name} failed with exit code {result.exit_code}: {result.output}"
    )


def test_dry_run_table_shows_mock_and_verdict_na(tmp_path):
    """AC 1 & 2: Table clearly says MOCK, verdict is N/A, not PASS or FAIL."""
    doc = tmp_path / "sample.md"
    doc.write_text("# Test Document\nSample body.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "--dry-run"])
    assert result.exit_code == 0
    assert "TypeSafe Evaluation Report (MOCK)" in result.output
    assert "N/A" in result.output
    assert "✔ PASS" not in result.output
    assert "✘ FAIL" not in result.output
    assert "Threshold & Baseline Violations" not in result.output


def test_dry_run_markdown_shows_mock_and_verdict_na(tmp_path):
    """AC 1 & 2: Markdown clearly says MOCK, verdict is N/A, not PASS or FAIL."""
    doc = tmp_path / "sample.md"
    doc.write_text("# Test Document\nSample body.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [str(doc), "--preset", "safety", "--dry-run", "--format", "markdown"]
    )
    assert result.exit_code == 0
    assert "# TypeSafe Evaluation Report (MOCK)" in result.output
    assert "**Mode:** MOCK (dry-run, no API calls made)" in result.output
    assert "| N/A |" in result.output
    assert "PASS" not in result.output
    assert "FAIL" not in result.output
    assert "## Threshold & Baseline Violations" not in result.output


def test_dry_run_json_has_mock_true_per_document(tmp_path):
    """AC 1: JSON output has 'mock': true per document."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc 1", encoding="utf-8")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Doc 2", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [str(doc1), str(doc2), "--preset", "quality", "--dry-run", "--format", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    for item in data:
        assert item["mock"] is True
        assert item["violations"] == []
        assert item["warnings"] == []


def test_dry_run_usage_errors_still_exit_2(tmp_path):
    """AC 3: Exit code 0 for every preset, unless there is a usage error (2)."""
    runner = CliRunner()

    # Non-existent file
    res_nofile = runner.invoke(
        main, ["non_existent_file_xyz123.md", "--preset", "quality", "--dry-run"]
    )
    assert res_nofile.exit_code == 2

    # Invalid preset
    doc = tmp_path / "doc.md"
    doc.write_text("Hello", encoding="utf-8")
    res_badpreset = runner.invoke(main, [str(doc), "--preset", "non_existent_preset", "--dry-run"])
    assert res_badpreset.exit_code == 2

    # No files specified
    res_nofiles = runner.invoke(main, ["--preset", "quality", "--dry-run"])
    assert res_nofiles.exit_code == 2


def test_evaluator_direct_dry_run():
    """Verify TypeSafeEvaluator.evaluate_document returns mock=True when dry_run=True."""
    evaluator = TypeSafeEvaluator()
    preset = load_preset("quality")
    res = evaluator.evaluate_document(
        "tests/fixtures/design_doc/en.md", preset=preset, dry_run=True
    )
    assert res.mock is True
    assert res.passed_thresholds is True
    assert res.violations == []
    assert res.warnings == []
    assert res.composite_score is not None


def test_validate_dry_run_pii_secrets_json():
    """AC: validate --dry-run sets mock=true, all_passed=null, criteria passed=null, exits 0."""
    labels_path = "tests/fixtures/pii_secrets/labels.yaml"
    runner = CliRunner()
    result = runner.invoke(main, ["validate", labels_path, "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["mock"] is True
    assert data["all_passed"] is None
    assert data["summary"]["criteria_passed"] is None
    assert len(data["criteria_results"]) > 0
    for crit in data["criteria_results"]:
        assert crit["passed"] is None
    # Stats are still computed
    assert data["summary"]["total_absent_expected"] == 23
    assert data["summary"]["total_detected"] == 23


def test_validate_dry_run_pii_secrets_table_and_markdown():
    """AC: validate --dry-run shows MOCK in header, Verdict: N/A (MOCK), exits 0."""
    labels_path = "tests/fixtures/pii_secrets/labels.yaml"
    runner = CliRunner()

    # Table format
    res_table = runner.invoke(main, ["validate", labels_path, "--dry-run", "-f", "table"])
    assert res_table.exit_code == 0
    assert "TypeSafe Validation Report (MOCK)" in res_table.output
    assert "Verdict: N/A (MOCK)" in res_table.output
    assert "Mode: MOCK (dry-run, no API calls made)" in res_table.output
    assert "✔ PASS" not in res_table.output
    assert "✘ FAIL" not in res_table.output

    # Markdown format
    res_md = runner.invoke(main, ["validate", labels_path, "--dry-run", "-f", "markdown"])
    assert res_md.exit_code == 0
    assert "# TypeSafe Validation Report (MOCK)" in res_md.output
    assert "**Verdict:** N/A (MOCK)" in res_md.output
    assert "**Mode:** MOCK (dry-run, no API calls made)" in res_md.output
    assert "**N/A (MOCK)**" in res_md.output
    assert "**PASS**" not in res_md.output
    assert "**FAIL**" not in res_md.output


def test_validate_dry_run_usage_errors_exit_2():
    """AC: Usage errors under validate --dry-run still exit 2."""
    runner = CliRunner()

    # Missing file
    res = runner.invoke(main, ["validate", "non_existent_labels_xyz.yaml", "--dry-run"])
    assert res.exit_code == 2

    # No argument
    res_noargs = runner.invoke(main, ["validate", "--dry-run"])
    assert res_noargs.exit_code == 2
