import json
import sys
from pathlib import Path
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.models import (
    DocumentEvalResult,
    ScoreResult,
    ChoiceResult,
    PresetConfig,
    QuestionConfig,
)
from scripts.feasibility_check import compute_roc_auc, compute_ci95, run_feasibility


def test_quality_preset_definition():
    preset = load_preset("quality")
    assert preset.name == "quality"
    assert preset.thresholds_as_warnings is True
    assert "clarity" in preset.questions
    assert preset.questions["clarity"].weight == 1.0
    assert preset.questions["clarity"].min_threshold == 0.6
    assert "tone" in preset.questions
    assert "completeness" not in preset.questions
    assert "actionable" not in preset.questions


def test_quality_threshold_below_minimum_is_warning_not_violation(tmp_path):
    preset = load_preset("quality")
    evaluator = TypeSafeEvaluator()

    # Create dummy mock results with clarity normalized_score = 0.40 (< min_threshold 0.60)
    scores = {
        "clarity": ScoreResult(
            score=0.8,
            max_score=2.0,
            normalized_score=0.40,
            confidence=0.9,
            probabilities={"0": 0.6, "1": 0.4},
        )
    }
    choices = {
        "tone": ChoiceResult(
            choice="professional",
            confidence=0.9,
            probabilities={"professional": 0.9},
        )
    }

    composite, passed, violations, warnings = evaluator._evaluate_thresholds_and_composite(
        preset=preset,
        scores=scores,
        nouls={},
        choices=choices,
    )

    # In quality preset, low clarity is a warning, NOT a violation, and passed remains True!
    assert passed is True
    assert len(violations) == 0
    assert len(warnings) == 1
    assert "Clarity & Structure: score 0.40 is below minimum 0.60 (warning)" in warnings[0]
    assert composite == pytest.approx(0.40)


def test_warning_behavior_solely_depends_on_thresholds_as_warnings():
    evaluator = TypeSafeEvaluator()
    scores = {
        "clarity": ScoreResult(
            score=1.0,
            max_score=2.0,
            normalized_score=0.50,
            confidence=0.9,
            probabilities={"0": 0.5, "1": 0.5},
        )
    }

    # Preset 1: name: quality, but thresholds_as_warnings is False -> MUST fail (violation)
    preset_name_quality = PresetConfig(
        name="quality",
        thresholds_as_warnings=False,
        questions={
            "clarity": QuestionConfig(type="score", instructions="clarity", min_threshold=0.99)
        },
    )
    _, passed1, violations1, warnings1 = evaluator._evaluate_thresholds_and_composite(
        preset=preset_name_quality, scores=scores, nouls={}, choices={}
    )
    assert passed1 is False
    assert len(violations1) == 1
    assert len(warnings1) == 0

    # Preset 2: name: myquality, but thresholds_as_warnings is True -> MUST pass (warning)
    preset_myquality = PresetConfig(
        name="myquality",
        thresholds_as_warnings=True,
        questions={
            "clarity": QuestionConfig(type="score", instructions="clarity", min_threshold=0.99)
        },
    )
    _, passed2, violations2, warnings2 = evaluator._evaluate_thresholds_and_composite(
        preset=preset_myquality, scores=scores, nouls={}, choices={}
    )
    assert passed2 is True
    assert len(violations2) == 0
    assert len(warnings2) == 1
    assert "warning" in warnings2[0]


def test_quality_cli_with_baseline_regression_fails(tmp_path, monkeypatch):
    runner = CliRunner()
    doc = tmp_path / "article.md"
    doc.write_text("# Test Article\nSome content here.", encoding="utf-8")

    # Baseline has clarity 0.85
    baseline_res = DocumentEvalResult(
        filepath=str(doc),
        filename=doc.name,
        preset_name="quality",
        scores={
            "clarity": ScoreResult(
                score=1.70,
                max_score=2.0,
                normalized_score=0.85,
                confidence=0.90,
                probabilities={},
            )
        },
        passed_thresholds=True,
    )
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps([baseline_res.model_dump()]), encoding="utf-8")

    # Current evaluation has clarity 0.65 (drop of 0.20 > max_drop 0.10)
    def mock_eval(self, filepath, preset, **kwargs):
        return DocumentEvalResult(
            filepath=filepath,
            filename=Path(filepath).name,
            preset_name="quality",
            scores={
                "clarity": ScoreResult(
                    score=1.30,
                    max_score=2.0,
                    normalized_score=0.65,
                    confidence=0.90,
                    probabilities={},
                )
            },
            passed_thresholds=True,
            violations=[],
            warnings=[],
        )

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    result = runner.invoke(
        main,
        [str(doc), "--preset", "quality", "--baseline", str(baseline_file)],
    )

    # Regressions from baseline MUST fail with exit code 1
    assert result.exit_code == 1
    assert "Baseline drop: 'clarity' dropped by 0.20" in result.output


def test_feasibility_check_math():
    # AUC: perfectly separated
    pos = [0.9, 0.85, 0.8]
    neg = [0.4, 0.35, 0.3]
    auc = compute_roc_auc(pos, neg)
    assert auc == 1.0

    # AUC: completely inverted
    auc_inv = compute_roc_auc(neg, pos)
    assert auc_inv == 0.0

    # CI95 math
    vals = [0.1, 0.1, 0.1, 0.1]
    mean, lower, upper = compute_ci95(vals)
    assert mean == 0.1
    assert lower == 0.1
    assert upper == 0.1


def test_feasibility_check_between_doc_spread_distinct_docs(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc2 = tmp_path / "doc2.md"
    doc1.write_text("# Doc 1\nContent 1", encoding="utf-8")
    doc2.write_text("# Doc 2\nContent 2", encoding="utf-8")

    report = run_feasibility(
        doc_paths=[doc1, doc2],
        preset_name="quality",
        runs=1,
        dry_run=True,
    )
    # 2 documents with 3 synthetic degradations each = 6 pairs
    assert report["num_pairs"] == 6
    assert report["num_distinct_docs"] == 2
    # In dry-run, mock results return the same normalized score 0.85, so stdev across distinct docs is 0.0
    assert report["between_doc_spread"] == 0.0


def test_feasibility_check_tuning_heldout_split_and_doc_types(tmp_path):
    # Create pairs JSON with 4 distinct documents and 2 document types
    pairs_data = [
        {"id": "p1", "doc_id": "doc_a", "doc_type": "design_doc", "better": "after", "before_text": "draft A", "after_text": "final A"},
        {"id": "p2", "doc_id": "doc_b", "doc_type": "design_doc", "better": "after", "before_text": "draft B", "after_text": "final B"},
        {"id": "p3", "doc_id": "doc_c", "doc_type": "article", "better": "before", "before_text": "orig C", "after_text": "degraded C"},
        {"id": "p4", "doc_id": "doc_d", "doc_type": "article", "better": "before", "before_text": "orig D", "after_text": "degraded D"},
    ]
    pairs_file = tmp_path / "pairs.json"
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    report = run_feasibility(
        pairs_file=pairs_file,
        preset_name="quality",
        runs=1,
        holdout_fraction=0.5,
        dry_run=True,
    )

    assert report["num_pairs"] == 4
    assert report["num_distinct_docs"] == 4
    assert len(report["tuning_docs"]) == 2
    assert len(report["holdout_docs"]) == 2
    # Ensure tuning and heldout are disjoint
    assert set(report["tuning_docs"]).isdisjoint(set(report["holdout_docs"]))

    # Group by doc_type
    assert "design_doc" in report["by_doc_type"]
    assert "article" in report["by_doc_type"]
    assert report["by_doc_type"]["design_doc"]["num_pairs"] == 2
    assert report["by_doc_type"]["article"]["num_pairs"] == 2


def test_feasibility_check_direction_better_handling(tmp_path):
    # Review pair: after is better (0.90) vs before (0.40)
    # Synthetic pair: before is better (0.90) vs after (0.40)
    pairs_data = [
        {"id": "p_review", "doc_id": "doc_rev", "doc_type": "article", "better": "after", "before_text": "bad", "after_text": "good"},
        {"id": "p_synth", "doc_id": "doc_syn", "doc_type": "article", "better": "before", "before_text": "good", "after_text": "bad"},
    ]
    pairs_file = tmp_path / "direction_pairs.json"
    pairs_file.write_text(json.dumps(pairs_data), encoding="utf-8")

    report = run_feasibility(
        pairs_file=pairs_file,
        preset_name="quality",
        runs=1,
        dry_run=True,
    )

    p_rev = next(p for p in report["pairs"] if p["id"] == "p_review")
    p_syn = next(p for p in report["pairs"] if p["id"] == "p_synth")

    assert p_rev["better"] == "after"
    assert p_syn["better"] == "before"
