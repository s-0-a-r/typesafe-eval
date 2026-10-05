"""Tests for question-level advisory gating (Reliable vs Advisory separation)."""

import json
from pathlib import Path

from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import (
    DocumentEvalResult,
    NoulResult,
    PresetConfig,
    QuestionConfig,
)
from typesafe_eval.presets import load_preset


def test_preset_advisory_flags_loaded():
    """Verify built-in presets correctly mark unreliable questions as advisory."""
    design_doc = load_preset("design-doc")
    assert design_doc.questions["rollback"].advisory is False
    assert design_doc.questions["alternatives"].advisory is False
    assert design_doc.questions["open_questions"].advisory is False
    assert design_doc.questions["goal"].advisory is False
    assert design_doc.questions["owner_timeline"].advisory is False

    # Unreliable / unmeasured questions MUST be advisory
    assert design_doc.questions["non_goals"].advisory is True
    assert design_doc.questions["risks"].advisory is True
    assert design_doc.questions["metrics"].advisory is True
    assert design_doc.questions["migration"].advisory is True
    assert design_doc.questions["impact"].advisory is True

    pr_desc = load_preset("pr-description")
    assert pr_desc.questions["testing"].advisory is False

    # Unreliable questions MUST be advisory
    assert pr_desc.questions["summary"].advisory is True
    assert pr_desc.questions["impact"].advisory is True
    assert pr_desc.questions["breaking_changes"].advisory is True
    assert pr_desc.questions["related_issues"].advisory is True


def test_advisory_question_failure_does_not_block_gate(tmp_path):
    """When an advisory question fails min_threshold, it warns but does not fail the gate."""
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nSample content.", encoding="utf-8")

    preset = PresetConfig(
        name="test_preset",
        questions={
            "strict_noul": QuestionConfig(
                type="noul",
                instructions="strict question",
                min_threshold=0.5,
                advisory=False,
            ),
            "advisory_noul": QuestionConfig(
                type="noul",
                instructions="advisory question",
                min_threshold=0.5,
                advisory=True,
            ),
        },
    )

    evaluator = TypeSafeEvaluator()

    # Case 1: Only advisory question fails
    scores = {}
    nouls = {
        "strict_noul": NoulResult(probability=0.80),
        "advisory_noul": NoulResult(probability=0.20),
    }
    choices = {}

    composite, passed, violations, warnings = evaluator._evaluate_thresholds_and_composite(
        preset=preset,
        scores=scores,
        nouls=nouls,
        choices=choices,
    )

    assert passed is True
    assert len(violations) == 0
    assert len(warnings) == 1
    assert "advisory_noul" in warnings[0]
    assert "(warning)" in warnings[0]

    # Case 2: Strict question fails
    nouls["strict_noul"] = NoulResult(probability=0.30)
    composite, passed, violations, warnings = evaluator._evaluate_thresholds_and_composite(
        preset=preset,
        scores=scores,
        nouls=nouls,
        choices=choices,
    )

    assert passed is False
    assert len(violations) == 1
    assert "strict_noul" in violations[0]
    assert len(warnings) == 1
    assert "advisory_noul" in warnings[0]


def test_advisory_baseline_regression_warns_without_exit_1(tmp_path, monkeypatch):
    """Regression on an advisory question emits warning and exits 0; strict regression exits 1."""
    doc = tmp_path / "design.md"
    doc.write_text("# Design\nSample content.", encoding="utf-8")

    cfg_file = tmp_path / "custom.yaml"
    cfg_file.write_text(
        """
name: "custom_adv"
questions:
  strict_q:
    type: "noul"
    instructions: "strict"
    min_threshold: 0.5
    advisory: false
  advisory_q:
    type: "noul"
    instructions: "advisory"
    min_threshold: 0.5
    advisory: true
""",
        encoding="utf-8",
    )

    # Baseline: both were 0.90
    baseline_res = DocumentEvalResult(
        filepath=str(doc),
        filename=doc.name,
        preset_name="custom_adv",
        nouls={
            "strict_q": NoulResult(probability=0.90),
            "advisory_q": NoulResult(probability=0.90),
        },
        passed_thresholds=True,
    )
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps([baseline_res.model_dump()]), encoding="utf-8")

    # Current run: advisory drops to 0.50 (drop 0.40 > 0.10), strict stays 0.90
    def mock_eval_advisory_drop(self, filepath, preset, **kwargs):
        return DocumentEvalResult(
            filepath=filepath,
            filename=Path(filepath).name,
            preset_name="custom_adv",
            nouls={
                "strict_q": NoulResult(probability=0.90),
                "advisory_q": NoulResult(probability=0.50),
            },
            passed_thresholds=True,
            violations=[],
            warnings=[],
        )

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval_advisory_drop)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--config", str(cfg_file), "--baseline", str(baseline_file)],
    )

    # Advisory drop MUST NOT trigger Exit 1
    assert result.exit_code == 0
    assert "Baseline drop (advisory)" in result.output or "Baseline drop" in result.output

    # Current run: strict drops to 0.50 (drop 0.40 > 0.10)
    def mock_eval_strict_drop(self, filepath, preset, **kwargs):
        return DocumentEvalResult(
            filepath=filepath,
            filename=Path(filepath).name,
            preset_name="custom_adv",
            nouls={
                "strict_q": NoulResult(probability=0.50),
                "advisory_q": NoulResult(probability=0.90),
            },
            passed_thresholds=True,
            violations=[],
            warnings=[],
        )

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval_strict_drop)

    result_strict = runner.invoke(
        main,
        [str(doc), "--config", str(cfg_file), "--baseline", str(baseline_file)],
    )

    # Strict drop MUST trigger Exit 1
    assert result_strict.exit_code == 1
    assert "Baseline drop" in result_strict.output
