"""Tests for near_threshold indicator, margin constant, and reporting (Issue #44)."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from typesafe_eval.models import (
    NEAR_THRESHOLD_MARGIN,
    CANDIDATE_DECISION_THRESHOLD,
    PresetConfig,
    QuestionConfig,
    ScoreResult,
    NoulResult,
    EmailEvaluationResult,
    PhoneEvaluationResult,
    IPEvaluationResult,
    URLEvaluationResult,
    SecretEvaluationResult,
    DocumentEvalResult,
)
from typesafe_eval.client import TypeSafeEvaluator, _is_candidate_near_threshold
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


def test_candidate_near_threshold_unit():
    assert CANDIDATE_DECISION_THRESHOLD == 0.5

    # 1. Model decided at 0.55 (near: |0.55 - 0.50| = 0.05 <= 0.10)
    assert _is_candidate_near_threshold("model", 0.55) is True
    # At boundaries 0.40 and 0.60
    assert _is_candidate_near_threshold("model", 0.40) is True
    assert _is_candidate_near_threshold("model", 0.60) is True

    # 2. Model decided at 0.75 (not near: |0.75 - 0.50| = 0.25 > 0.10)
    assert _is_candidate_near_threshold("model", 0.75) is False
    assert _is_candidate_near_threshold("model", 0.25) is False

    # 3. Decided by rule (always False)
    assert _is_candidate_near_threshold("rule", 0.55) is False
    assert _is_candidate_near_threshold("rule", None) is False
    assert _is_candidate_near_threshold("free_mail", None) is False


def test_candidate_near_threshold_cli_reporting(tmp_path, monkeypatch):
    doc = tmp_path / "memo.md"
    doc.write_text("# Memo\nContact test", encoding="utf-8")

    # [EMAIL_1]: model at 0.55 (near_threshold: True, personal)
    # [URL_1]: model at 0.75 (near_threshold: False, sensitive)
    # [SECRET_1]: rule decided (near_threshold: False, secret)
    def mock_eval(*args, **kwargs):
        return DocumentEvalResult(
            filepath=str(doc),
            filename="memo.md",
            preset_name="safety",
            scores={},
            nouls={},
            choices={},
            email_evaluations=[
                EmailEvaluationResult(
                    placeholder="[EMAIL_1]",
                    question_id="email_pii_1",
                    outcome="personal",
                    probability=0.55,
                    decided_by="model",
                    near_threshold=True,
                )
            ],
            url_evaluations=[
                URLEvaluationResult(
                    placeholder="[URL_1]",
                    question_id="url_pii_1",
                    outcome="sensitive",
                    probability=0.75,
                    decided_by="model",
                    near_threshold=False,
                )
            ],
            secret_evaluations=[
                SecretEvaluationResult(
                    placeholder="[SECRET_1]",
                    outcome="secret",
                    probability=None,
                    decided_by="rule",
                    near_threshold=False,
                )
            ],
            passed_thresholds=False,
            violations=["PII Exposure: [EMAIL_1] is an individual address (model: 0.55)"],
        )

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()

    # 1. JSON: near_threshold true on [EMAIL_1], false on [URL_1] and [SECRET_1]
    res_json = runner.invoke(main, [str(doc), "--preset", "safety", "--format", "json"])
    assert res_json.exit_code == 1
    data = json.loads(res_json.stdout)
    assert len(data) == 1
    em = data[0]["email_evaluations"][0]
    assert em["near_threshold"] is True
    assert em["probability"] == 0.55

    url = data[0]["url_evaluations"][0]
    assert url["near_threshold"] is False

    sec = data[0]["secret_evaluations"][0]
    assert sec["near_threshold"] is False

    # 2. Table: displays "~ near threshold: [EMAIL_1] personal (p=0.55)"
    res_table = runner.invoke(main, [str(doc), "--preset", "safety", "--format", "table"])
    assert res_table.exit_code == 1
    assert "~ near threshold: [EMAIL_1] personal (p=0.55)" in res_table.stdout
    assert "[URL_1]" not in res_table.stdout
    assert "[SECRET_1]" not in res_table.stdout

    # 3. Markdown: displays "~ near threshold: [EMAIL_1] personal (p=0.55)"
    res_md = runner.invoke(main, [str(doc), "--preset", "safety", "--format", "markdown"])
    assert res_md.exit_code == 1
    assert "~ near threshold: [EMAIL_1] personal (p=0.55)" in res_md.stdout
    assert "[URL_1]" not in res_md.stdout
    assert "[SECRET_1]" not in res_md.stdout


def test_candidate_near_threshold_preserves_exit_codes(tmp_path, monkeypatch):
    doc = tmp_path / "memo.md"
    doc.write_text("# Memo\nContent", encoding="utf-8")

    runner = CliRunner()

    # Case 1: Candidate is safe (e.g. role email, prob 0.45, near_threshold: True)
    # Outcome is safe -> passed_thresholds: True -> Exit 0
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: DocumentEvalResult(
            filepath=str(doc),
            filename="memo.md",
            preset_name="safety",
            scores={},
            nouls={},
            choices={},
            email_evaluations=[
                EmailEvaluationResult(
                    placeholder="[EMAIL_1]",
                    question_id="email_pii_1",
                    outcome="role",
                    probability=0.45,
                    decided_by="model",
                    near_threshold=True,
                )
            ],
            passed_thresholds=True,
        ),
    )
    res_pass = runner.invoke(main, [str(doc), "--preset", "safety"])
    assert res_pass.exit_code == 0
    assert "~ near threshold: [EMAIL_1] role (p=0.45)" in res_pass.stdout

    # Case 2: Candidate is violation (e.g. personal email, prob 0.55, near_threshold: True)
    # Outcome is violation -> passed_thresholds: False -> Exit 1
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: DocumentEvalResult(
            filepath=str(doc),
            filename="memo.md",
            preset_name="safety",
            scores={},
            nouls={},
            choices={},
            email_evaluations=[
                EmailEvaluationResult(
                    placeholder="[EMAIL_1]",
                    question_id="email_pii_1",
                    outcome="personal",
                    probability=0.55,
                    decided_by="model",
                    near_threshold=True,
                )
            ],
            passed_thresholds=False,
            violations=["PII Exposure: [EMAIL_1] is an individual address (model: 0.55)"],
        ),
    )
    res_fail = runner.invoke(main, [str(doc), "--preset", "safety"])
    assert res_fail.exit_code == 1
    assert "~ near threshold: [EMAIL_1] personal (p=0.55)" in res_fail.stdout

