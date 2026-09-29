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
from typesafe_eval.presets import load_preset


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
    assert str(doc_path) in lookup
    assert str(doc_path.resolve()) in lookup


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
    prev_res = _make_eval_result(str(doc), score_val=0.90, preset_name="custom")
    baseline_file = tmp_path / "prev.json"
    baseline_file.write_text(json.dumps([prev_res.model_dump()]), encoding="utf-8")

    # Current clarity: 0.72 (drop 0.18 <= 0.25 custom threshold)
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), score_val=0.72, preset_name="custom"),
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


def test_baseline_risk_question_rise_and_drop(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    from typesafe_eval.client import TypeSafeEvaluator

    # Case 1: Baseline has_pii was 0.00 -> Current is 0.78 (rise of 0.78 > 0.10 max_drop) -> FAILS
    prev_res_low = _make_eval_result(str(doc), prob_val=0.00, preset_name="safety")
    baseline_file_low = tmp_path / "baseline_low.json"
    baseline_file_low.write_text(json.dumps([prev_res_low.model_dump()]), encoding="utf-8")

    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_eval_result(str(doc), prob_val=0.78, preset_name="safety"),
    )

    runner = CliRunner()
    res1 = runner.invoke(main, [str(doc), "--preset", "safety", "--baseline", str(baseline_file_low)])
    assert res1.exit_code == 1
    assert "Baseline risk rise: 'has_pii' rose by 0.78" in res1.output

    # Case 2: Baseline has_pii was 0.99 -> Current is 0.78 (drop in risk is an improvement) -> PASSES
    prev_res_high = _make_eval_result(str(doc), prob_val=0.99, preset_name="safety")
    baseline_file_high = tmp_path / "baseline_high.json"
    baseline_file_high.write_text(json.dumps([prev_res_high.model_dump()]), encoding="utf-8")

    res2 = runner.invoke(main, [str(doc), "--preset", "safety", "--baseline", str(baseline_file_high)])
    assert res2.exit_code == 0
    assert "Baseline risk rise" not in res2.output
    assert "Baseline drop" not in res2.output


def test_baseline_multiple_same_filename_no_collision(tmp_path, monkeypatch):
    doc_a = tmp_path / "docs" / "a" / "README.md"
    doc_b = tmp_path / "docs" / "b" / "README.md"
    doc_c = tmp_path / "docs" / "c" / "README.md"

    doc_a.parent.mkdir(parents=True, exist_ok=True)
    doc_b.parent.mkdir(parents=True, exist_ok=True)
    doc_c.parent.mkdir(parents=True, exist_ok=True)

    doc_a.write_text("# Doc A", encoding="utf-8")
    doc_b.write_text("# Doc B", encoding="utf-8")
    doc_c.write_text("# Doc C", encoding="utf-8")

    # Baseline only contains a/README.md and b/README.md
    res_a = _make_eval_result(str(doc_a), score_val=0.90)
    res_b = _make_eval_result(str(doc_b), score_val=0.85)
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps([res_a.model_dump(), res_b.model_dump()]), encoding="utf-8")

    lookup = load_baseline(baseline_file)
    assert str(doc_a) in lookup or str(doc_a.resolve()) in lookup
    assert str(doc_b) in lookup or str(doc_b.resolve()) in lookup
    assert "README.md" not in lookup

    from typesafe_eval.client import TypeSafeEvaluator

    def mock_eval(self, filepath, **kwargs):
        p = Path(filepath)
        if "a" in p.parts:
            return _make_eval_result(str(doc_a), score_val=0.90)
        elif "b" in p.parts:
            return _make_eval_result(str(doc_b), score_val=0.85)
        else:
            return _make_eval_result(str(doc_c), score_val=0.80)

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc_a), str(doc_b), str(doc_c), "--preset", "quality", "--baseline", str(baseline_file), "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 3

    diffs_by_file = {d["filepath"]: d["baseline_diff"] for d in data}
    assert diffs_by_file[str(doc_a)]["status"] == "compared"
    assert diffs_by_file[str(doc_b)]["status"] == "compared"
    # doc_c must be "new", not falsely compared to a or b!
    assert diffs_by_file[str(doc_c)]["status"] == "new"


def test_baseline_with_mock_rejected(tmp_path):
    """B: Baseline containing mock: true documents is rejected with exit code 2."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    res = _make_eval_result(str(doc), score_val=0.90)
    data = res.model_dump()
    data["mock"] = True

    baseline_file = tmp_path / "baseline_mock.json"
    baseline_file.write_text(json.dumps([data]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--baseline", str(baseline_file)])
    assert result.exit_code == 2
    assert "mock=true" in result.output.lower() or "dry-run" in result.output.lower()


def test_baseline_with_mismatched_preset_rejected(tmp_path):
    """B: Baseline containing documents evaluated with a different preset is rejected with exit code 2."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    res = _make_eval_result(str(doc), preset_name="safety")
    baseline_file = tmp_path / "baseline_safety.json"
    baseline_file.write_text(json.dumps([res.model_dump()]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--baseline", str(baseline_file)])
    assert result.exit_code == 2
    assert "preset" in result.output.lower()
    assert "safety" in result.output.lower()


def test_compare_rejects_mock_prev():
    """B: compare_document_with_baseline rejects a mock baseline entry when called directly."""
    preset = load_preset("quality")
    cur = DocumentEvalResult(filepath="d.md", filename="d.md", preset_name="quality")
    prev = DocumentEvalResult(filepath="d.md", filename="d.md", preset_name="quality", mock=True)
    with pytest.raises(ValueError, match="mock"):
        compare_document_with_baseline(cur, {"d.md": prev}, preset)


def test_compare_rejects_other_preset_prev():
    """B: compare_document_with_baseline rejects a baseline entry from another preset when called directly."""
    preset = load_preset("quality")
    cur = DocumentEvalResult(filepath="d.md", filename="d.md", preset_name="quality")
    prev = DocumentEvalResult(filepath="d.md", filename="d.md", preset_name="safety")
    with pytest.raises(ValueError, match="preset"):
        compare_document_with_baseline(cur, {"d.md": prev}, preset)


def test_baseline_v030_dry_run_without_mock_key_rejected(tmp_path):
    """B: a v0.3.0 dry-run JSON has no mock key but model 'mock-jev'; it is rejected too."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    res = _make_eval_result(str(doc), score_val=0.90)
    data = res.model_dump()
    data.pop("mock", None)
    data["model"] = "mock-jev"

    baseline_file = tmp_path / "baseline_v030.json"
    baseline_file.write_text(json.dumps([data]), encoding="utf-8")

    with pytest.raises(ValueError, match="mock"):
        load_baseline(baseline_file, expected_preset="quality")



