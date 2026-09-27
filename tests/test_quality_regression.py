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
    # Note: 0.65 > min_threshold 0.60, so no warning, but baseline regressed!
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


def test_feasibility_check_dry_run(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc 1\nSection 1 text.\n\n## Section 2\nSection 2 text.", encoding="utf-8")

    report = run_feasibility(
        doc_paths=[doc1],
        preset_name="quality",
        runs=1,
        dry_run=True,
    )
    assert report["num_pairs"] == 3
    assert report["preset"] == "quality"
    assert "within_pair_gap" in report
    assert "gap_to_spread_ratio" in report
