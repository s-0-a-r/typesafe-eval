"""Tests for `typesafe-eval validate` command, statistical CI, criteria checks, and ablation helper."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.models import DocumentEvalResult, ScoreResult, NoulResult
from typesafe_eval.validator import (
    compute_ci_95,
    get_t_crit_95,
    generate_ablation_variants,
)


def _make_noul_result(filepath: str, prob: float, question_id: str = "has_pii") -> DocumentEvalResult:
    p = Path(filepath)
    return DocumentEvalResult(
        filepath=filepath,
        filename=p.name,
        preset_name="safety",
        nouls={question_id: NoulResult(probability=prob)},
        passed_thresholds=True,
    )


def _make_score_result(filepath: str, score_val: float, question_id: str = "clarity") -> DocumentEvalResult:
    p = Path(filepath)
    return DocumentEvalResult(
        filepath=filepath,
        filename=p.name,
        preset_name="quality",
        scores={
            question_id: ScoreResult(
                score=score_val,
                max_score=1.0,
                normalized_score=score_val,
                confidence=0.9,
                probabilities={},
            )
        },
        passed_thresholds=True,
    )


def test_t_crit_and_ci_computation():
    assert get_t_crit_95(1) == 12.706
    assert get_t_crit_95(2) == 4.303
    assert get_t_crit_95(30) == 2.042

    # Deltas with zero variance
    mean_val, low, high = compute_ci_95([-0.2, -0.2, -0.2])
    assert pytest.approx(mean_val) == -0.2
    assert pytest.approx(low) == -0.2
    assert pytest.approx(high) == -0.2

    # Deltas with variance
    deltas = [-0.10, -0.20, -0.30]
    mean_val, low, high = compute_ci_95(deltas)
    assert pytest.approx(mean_val) == -0.20
    # s = 0.10, SE = 0.10 / sqrt(3) = 0.0577, margin = 4.303 * 0.0577 = 0.2484
    assert low < mean_val < high


def test_ablation_generator(tmp_path):
    doc = tmp_path / "design.md"
    doc.write_text(
        "# My Architecture Design\n\n"
        "Introduction to the architecture.\n\n"
        "## Goal\n"
        "Define primary business goals.\n\n"
        "## Rollback Plan\n"
        "Steps to rollback if deployment fails.\n\n"
        "## Migration\n"
        "Data migration sequence.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "ablated"
    variants, labels_yaml = generate_ablation_variants(
        doc_path=doc,
        out_dir=out_dir,
        preset_name="design_doc",
    )

    assert len(variants) == 3
    var_names = [v.name for v in variants]
    assert "design_without_goal.md" in var_names
    assert "design_without_rollback_plan.md" in var_names
    assert "design_without_migration.md" in var_names

    # Check content of design_without_goal.md
    goal_variant = out_dir / "design_without_goal.md"
    content = goal_variant.read_text(encoding="utf-8")
    assert "## Goal" not in content
    assert "Define primary business goals" not in content
    assert "## Rollback Plan" in content
    assert "## Migration" in content

    # Check starter labels YAML
    assert "preset: design_doc" in labels_yaml
    assert "min_detected: 3" in labels_yaml
    assert "design_without_goal.md" in labels_yaml
    assert "goal: absent" in labels_yaml


def test_cli_validate_ablate_flag(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Title\n\n## Section One\nContent 1\n\n## Section Two\nContent 2\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["validate", "--ablate", str(doc), "--ablate-out-dir", str(tmp_path / "variants")])
    assert result.exit_code == 0
    assert "Generated 2 ablation variants:" in result.output
    assert "doc_without_section_one.md" in result.output


def test_validate_presence_detected_and_false_alarm(tmp_path, monkeypatch):
    doc_full = tmp_path / "full.md"
    doc_full.write_text("Document with sensitive PII", encoding="utf-8")
    doc_clean = tmp_path / "clean.md"
    doc_clean.write_text("Clean document without PII", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"runs: 3\n"
        f"criteria:\n"
        f"  min_detected: 1\n"
        f"  max_false_alarms: 0\n"
        f"documents:\n"
        f"  - path: {doc_full.name}\n"
        f"    expect: {{has_pii: present}}\n"
        f"  - path: {doc_clean.name}\n"
        f"    expect: {{has_pii: absent}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    def mock_eval(self, filepath, **kwargs):
        if "full" in filepath:
            # Expected present: high probability in all runs
            return _make_noul_result(filepath, prob=0.92, question_id="has_pii")
        else:
            # Expected absent: low probability in all runs (< 0.5)
            return _make_noul_result(filepath, prob=0.08, question_id="has_pii")

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 0
    assert "✔ PASS" in result.output
    assert "has_pii" in result.output
    assert "1 (100%)" in result.output  # Detected 1/1


def test_validate_presence_failure_triggers_exit_1(tmp_path, monkeypatch):
    doc_clean = tmp_path / "clean.md"
    doc_clean.write_text("Clean document", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"runs: 3\n"
        f"criteria:\n"
        f"  min_detected: 1\n"
        f"documents:\n"
        f"  - path: {doc_clean.name}\n"
        f"    expect: {{has_pii: absent}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    # Model returned 0.85 (>= 0.5 threshold) -> missed detection
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_noul_result(str(doc_clean), prob=0.85, question_id="has_pii"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 1
    assert "✘ FAIL" in result.output


def test_validate_score_pairs_mode(tmp_path, monkeypatch):
    a = tmp_path / "a.md"
    a.write_text("Original text", encoding="utf-8")
    a_shuffled = tmp_path / "a_shuffled.md"
    a_shuffled.write_text("Shuffled degraded text", encoding="utf-8")
    a_paraphrased = tmp_path / "a_paraphrased.md"
    a_paraphrased.write_text("Paraphrased text", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: quality\n"
        f"runs: 3\n"
        f"criteria:\n"
        f"  max_neutral_delta: 0.05\n"
        f"  min_degradation_drop: 0.2\n"
        f"pairs:\n"
        f"  - before: {a.name}\n"
        f"    after: {a_shuffled.name}\n"
        f"    expect: {{clarity: down}}\n"
        f"  - before: {a.name}\n"
        f"    after: {a_paraphrased.name}\n"
        f"    expect: {{clarity: neutral}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    def mock_eval(self, filepath, **kwargs):
        if "shuffled" in filepath:
            return _make_score_result(filepath, score_val=0.30, question_id="clarity")
        elif "paraphrased" in filepath:
            return _make_score_result(filepath, score_val=0.88, question_id="clarity")
        else:
            # original
            return _make_score_result(filepath, score_val=0.90, question_id="clarity")

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 0
    assert "clarity" in result.output
    assert "-0.600" in result.output  # 0.30 - 0.90 = -0.60
    assert "-0.020" in result.output  # 0.88 - 0.90 = -0.02


def test_validate_json_format_stability(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("Test content", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"runs: 2\n"
        f"documents:\n"
        f"  - path: {doc.name}\n"
        f"    expect: {{has_pii: absent}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_noul_result(str(doc), prob=0.10, question_id="has_pii"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["preset_name"] == "safety"
    assert data["runs"] == 2
    assert "has_pii" in data["question_stats"]
    assert data["question_stats"]["has_pii"]["detected_count"] == 1


def test_validate_markdown_format(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("Test content", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"runs: 2\n"
        f"documents:\n"
        f"  - path: {doc.name}\n"
        f"    expect: {{has_pii: absent}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_noul_result(str(doc), prob=0.10, question_id="has_pii"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "--format", "markdown"])
    assert result.exit_code == 0
    assert "# TypeSafe Validation Report" in result.stdout
    assert "| `has_pii` |" in result.stdout


def test_validate_exit_code_2_usage_and_config_errors():
    runner = CliRunner()
    # Missing argument
    res1 = runner.invoke(main, ["validate"])
    assert res1.exit_code == 2

    # Nonexistent file
    res2 = runner.invoke(main, ["validate", "nonexistent_labels.yaml"])
    assert res2.exit_code == 2


def test_validate_exit_code_3_runtime_error(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("Test", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"documents:\n"
        f"  - path: {doc.name}\n"
        f"    expect: {{has_pii: present}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API Network Timeout")),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 3


def test_validate_precedence_1_over_3(tmp_path, monkeypatch):
    doc_fail = tmp_path / "fail.md"
    doc_fail.write_text("Fail content", encoding="utf-8")
    doc_err = tmp_path / "err.md"
    doc_err.write_text("Err content", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"preset: safety\n"
        f"criteria:\n"
        f"  min_detected: 1\n"
        f"documents:\n"
        f"  - path: {doc_fail.name}\n"
        f"    expect: {{has_pii: absent}}\n"
        f"  - path: {doc_err.name}\n"
        f"    expect: {{has_pii: absent}}\n",
        encoding="utf-8",
    )

    from typesafe_eval.client import TypeSafeEvaluator

    def mock_eval(self, filepath, **kwargs):
        if "fail" in filepath:
            # Returns prob 0.90 -> missed (criterion fails)
            return _make_noul_result(filepath, prob=0.90, question_id="has_pii")
        raise RuntimeError("API internal error")

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file)])
    # Criterion failed (code 1) takes precedence over runtime error (code 3)
    assert result.exit_code == 1
