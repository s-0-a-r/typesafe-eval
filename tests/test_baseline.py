"""Tests for `--baseline` diff mode and regression detection."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.models import (
    DocumentEvalResult,
    ScoreResult,
    NoulResult,
    PresetConfig,
    QuestionConfig,
)
from typesafe_eval.baseline import (
    load_baseline,
    compare_document_with_baseline,
)


def _make_eval_result(
    filepath: str,
    score_val: float = 0.90,
    prob_val: float = 0.10,
    was_truncated: bool = False,
    preset_name: str = "quality",
) -> DocumentEvalResult:
    p = Path(filepath)
    return DocumentEvalResult(
        filepath=filepath,
        filename=p.name,
        preset_name=preset_name,
        scores={
            "clarity": ScoreResult(
                score=score_val,
                max_score=1.0,
                normalized_score=score_val,
                confidence=0.9,
                probabilities={},
            )
        },
        nouls={"has_pii": NoulResult(probability=prob_val)},
        was_truncated=was_truncated,
        passed_thresholds=True,
    )


def test_baseline_load_and_match(tmp_path):
    doc_path = tmp_path / "doc.md"
    doc_path.write_text("# Doc", encoding="utf-8")

    prev_res = _make_eval_result(str(doc_path), score_val=0.85)
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    lookup = load_baseline(baseline_file)
    assert doc_path.name in lookup
    assert str(doc_path) in lookup


def test_baseline_drop_exceeding_threshold_fails(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    # Baseline: clarity was 0.90
    prev_res = _make_eval_result(str(doc), score_val=0.90)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    # Current: clarity dropped to 0.75 (drop 0.15 > 0.10 default threshold)
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.75),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--baseline", str(baseline_file)])
    assert result.exit_code == 1
    assert "Baseline drop: 'clarity' dropped by 0.15" in result.output
    assert "FAIL" in result.output


def test_baseline_drop_within_threshold_passes(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    # Baseline: clarity was 0.90
    prev_res = _make_eval_result(str(doc), score_val=0.90)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    # Current: clarity dropped to 0.85 (drop 0.05 <= 0.10 default threshold)
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.85),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--baseline", str(baseline_file)])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_baseline_custom_max_drop_in_yaml(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    config_file = tmp_path / "custom.yaml"
    config_file.write_text(
        "name: custom\n"
        "questions:\n"
        "  clarity:\n"
        "    type: score\n"
        "    instructions: clarity check\n"
        "    max_drop: 0.25\n",
        encoding="utf-8",
    )

    # Baseline clarity: 0.90
    prev_res = _make_eval_result(str(doc), score_val=0.90)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    # Current clarity: 0.72 (drop 0.18 <= 0.25 custom threshold)
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.72),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--config", str(config_file), "--baseline", str(baseline_file)],
    )
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_baseline_truncation_warning(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    # Baseline was not truncated
    prev_res = _make_eval_result(str(doc), score_val=0.90, was_truncated=False)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    # Current was truncated
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.90, was_truncated=True),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--baseline", str(baseline_file)])
    assert result.exit_code == 0
    assert "Truncation status differs" in (result.stderr or result.output)


def test_baseline_missing_document_marked_new(tmp_path, monkeypatch):
    doc_new = tmp_path / "new_doc.md"
    doc_new.write_text("# New Doc", encoding="utf-8")

    # Baseline contains other file
    prev_res = _make_eval_result(str(tmp_path / "other.md"), score_val=0.90)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc_new), score_val=0.90),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(doc_new), "--preset", "quality", "--baseline", str(baseline_file)])
    assert "PASS" in result.output
    assert "(new)" in result.output


def test_baseline_json_format_details(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    prev_res = _make_eval_result(str(doc), score_val=0.88)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.82),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--preset", "quality", "--baseline", str(baseline_file), "--format", "json"],
    )
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert len(data) == 1
    doc_data = data[0]
    assert doc_data["baseline_diff"]["status"] == "compared"
    diff_q = doc_data["baseline_diff"]["questions"]["clarity"]
    assert pytest.approx(diff_q["previous"]) == 0.88
    assert pytest.approx(diff_q["current"]) == 0.82
    assert pytest.approx(diff_q["delta"]) == -0.06
    assert diff_q["regressed"] is False


def test_baseline_markdown_format(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    prev_res = _make_eval_result(str(doc), score_val=0.88)
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.82),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--preset", "quality", "--baseline", str(baseline_file), "--format", "markdown"],
    )
    assert result.exit_code == 0
    assert "## Baseline Comparison Details" in result.stdout
    assert "`clarity`" in result.stdout
    assert "-0.06" in result.stdout


def test_baseline_missing_file_exit_code_2(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--baseline", str(tmp_path / "nonexistent.json")],
    )
    assert result.exit_code == 2
