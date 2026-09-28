"""Tests for near_threshold indicator, margin constant, and reporting (Issue #44)."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from typesafe_eval.models import (
    NEAR_THRESHOLD_MARGIN,
    PresetConfig,
    QuestionConfig,
    ScoreResult,
    NoulResult,
    DocumentEvalResult,
)
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.reporter import render_table, render_markdown, render_json
from typesafe_eval.cli import main


def test_near_threshold_constant():
    assert NEAR_THRESHOLD_MARGIN == 0.1


def test_near_threshold_score_min_threshold():
    preset = PresetConfig(
        name="test-score-preset",
        questions={
            "clarity": QuestionConfig(
                type="score",
                instructions="Clarity test",
                min_threshold=0.5,
            )
        },
    )
    evaluator = TypeSafeEvaluator()

    # Within margin (0.50 +/- 0.10)
    for score_val in [0.40, 0.45, 0.50, 0.51, 0.55, 0.60]:
        scores = {
            "clarity": ScoreResult(
                score=score_val * 2,
                max_score=2.0,
                normalized_score=score_val,
                confidence=0.9,
                probabilities={},
            )
        }
        evaluator._evaluate_thresholds_and_composite(preset, scores, {}, {})
        assert scores["clarity"].near_threshold is True, f"Failed for {score_val}"

    # Outside margin
    for score_val in [0.0, 0.20, 0.39, 0.61, 0.75, 0.99, 1.0]:
        scores = {
            "clarity": ScoreResult(
                score=score_val * 2,
                max_score=2.0,
                normalized_score=score_val,
                confidence=0.9,
                probabilities={},
            )
        }
        evaluator._evaluate_thresholds_and_composite(preset, scores, {}, {})
        assert scores["clarity"].near_threshold is False, f"Failed for {score_val}"


def test_near_threshold_noul_max_threshold():
    preset = PresetConfig(
        name="test-noul-preset",
        questions={
            "has_secrets": QuestionConfig(
                type="noul",
                instructions="Secrets check",
                max_threshold=0.2,
            )
        },
    )
    evaluator = TypeSafeEvaluator()

    # Within margin (0.20 +/- 0.10 -> 0.10 to 0.30)
    for prob_val in [0.10, 0.15, 0.20, 0.25, 0.30]:
        nouls = {"has_secrets": NoulResult(probability=prob_val)}
        evaluator._evaluate_thresholds_and_composite(preset, {}, nouls, {})
        assert nouls["has_secrets"].near_threshold is True, f"Failed for {prob_val}"

    # Outside margin
    for prob_val in [0.0, 0.05, 0.09, 0.31, 0.50, 0.90]:
        nouls = {"has_secrets": NoulResult(probability=prob_val)}
        evaluator._evaluate_thresholds_and_composite(preset, {}, nouls, {})
        assert nouls["has_secrets"].near_threshold is False, f"Failed for {prob_val}"


def test_near_threshold_question_without_threshold():
    preset = PresetConfig(
        name="test-no-thresh",
        questions={
            "tone": QuestionConfig(
                type="score",
                instructions="Tone check",
                weight=1.0,
                # No min_threshold, no max_threshold
            )
        },
    )
    evaluator = TypeSafeEvaluator()
    scores = {
        "tone": ScoreResult(
            score=1.0,
            max_score=2.0,
            normalized_score=0.5,
            confidence=0.9,
            probabilities={},
        )
    }
    evaluator._evaluate_thresholds_and_composite(preset, scores, {}, {})
    assert scores["tone"].near_threshold is False


def test_near_threshold_noul_none_prob():
    preset = PresetConfig(
        name="test-none-prob",
        questions={
            "has_secrets": QuestionConfig(
                type="noul",
                instructions="Secrets check",
                max_threshold=0.2,
                preflight="credentials",
            )
        },
    )
    evaluator = TypeSafeEvaluator()
    nouls = {"has_secrets": NoulResult(probability=None, overridden_by="preflight_scan")}
    evaluator._evaluate_thresholds_and_composite(preset, {}, nouls, {})
    assert nouls["has_secrets"].near_threshold is False


def test_near_threshold_cli_json_table_markdown(tmp_path, monkeypatch):
    doc = tmp_path / "test_doc.md"
    doc.write_text("# Test Document\nContent", encoding="utf-8")

    # Near threshold: clarity = 0.51 (threshold 0.50) -> near_threshold: True
    # Far from threshold: completeness = 0.90 (threshold 0.50) -> near_threshold: False
    def mock_evaluate(*args, **kwargs):
        return DocumentEvalResult(
            filepath=str(doc),
            filename="test_doc.md",
            preset_name="quality",
            scores={
                "clarity": ScoreResult(
                    score=1.02,
                    max_score=2.0,
                    normalized_score=0.51,
                    confidence=0.9,
                    probabilities={},
                    near_threshold=True,
                ),
                "completeness": ScoreResult(
                    score=1.80,
                    max_score=2.0,
                    normalized_score=0.90,
                    confidence=0.9,
                    probabilities={},
                    near_threshold=False,
                ),
            },
            nouls={},
            choices={},
            passed_thresholds=True,
        )

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_evaluate)

    custom_preset_yaml = tmp_path / "custom.yaml"
    import yaml
    custom_preset_yaml.write_text(
        yaml.dump({
            "name": "custom-quality",
            "questions": {
                "clarity": {
                    "type": "score",
                    "instructions": "Clarity",
                    "min_threshold": 0.5,
                },
                "completeness": {
                    "type": "score",
                    "instructions": "Completeness",
                    "min_threshold": 0.5,
                },
            },
        }),
        encoding="utf-8",
    )

    runner = CliRunner()

    # 1. JSON output
    res_json = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml), "--format", "json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert len(data) == 1
    scores_data = data[0]["scores"]
    assert scores_data["clarity"]["near_threshold"] is True
    assert scores_data["completeness"]["near_threshold"] is False

    # 2. Markdown output
    res_md = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml), "--format", "markdown"])
    assert res_md.exit_code == 0
    assert "51% ~" in res_md.stdout
    assert "90%" in res_md.stdout
    assert "90% ~" not in res_md.stdout
    assert "near_threshold" in res_md.stdout

    # 3. Table output
    res_table = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml), "--format", "table"])
    assert res_table.exit_code == 0
    assert "~" in res_table.stdout
    assert "near_threshold" in res_table.stdout


def test_near_threshold_preserves_exit_codes(tmp_path, monkeypatch):
    doc = tmp_path / "test_doc.md"
    doc.write_text("# Doc\nContent", encoding="utf-8")

    custom_preset_yaml = tmp_path / "custom.yaml"
    import yaml
    custom_preset_yaml.write_text(
        yaml.dump({
            "name": "gate-test",
            "questions": {
                "clarity": {
                    "type": "score",
                    "instructions": "Clarity",
                    "min_threshold": 0.50,
                },
            },
        }),
        encoding="utf-8",
    )

    runner = CliRunner()

    # Case 1: 0.51 (near_threshold: True, passed: True) -> Exit 0
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: DocumentEvalResult(
            filepath=str(doc),
            filename="test_doc.md",
            preset_name="gate-test",
            scores={
                "clarity": ScoreResult(
                    score=1.02,
                    max_score=2.0,
                    normalized_score=0.51,
                    confidence=0.9,
                    probabilities={},
                    near_threshold=True,
                )
            },
            passed_thresholds=True,
        ),
    )
    result = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml)])
    assert result.exit_code == 0

    # Case 2: 0.49 (near_threshold: True, passed: False) -> Exit 1
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: DocumentEvalResult(
            filepath=str(doc),
            filename="test_doc.md",
            preset_name="gate-test",
            scores={
                "clarity": ScoreResult(
                    score=0.98,
                    max_score=2.0,
                    normalized_score=0.49,
                    confidence=0.9,
                    probabilities={},
                    near_threshold=True,
                )
            },
            passed_thresholds=False,
            violations=["Clarity: score 0.49 is below required minimum 0.50"],
        ),
    )
    result = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml)])
    assert result.exit_code == 1

    # Case 3: 0.99 (near_threshold: False, passed: True) -> Exit 0
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: DocumentEvalResult(
            filepath=str(doc),
            filename="test_doc.md",
            preset_name="gate-test",
            scores={
                "clarity": ScoreResult(
                    score=1.98,
                    max_score=2.0,
                    normalized_score=0.99,
                    confidence=0.9,
                    probabilities={},
                    near_threshold=False,
                )
            },
            passed_thresholds=True,
        ),
    )
    result = runner.invoke(main, [str(doc), "--config", str(custom_preset_yaml)])
    assert result.exit_code == 0
