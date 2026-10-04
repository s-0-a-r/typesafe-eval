import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.feasibility_check import run_feasibility
from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.validator import (
    load_labels_file,
    render_validation_markdown,
    run_validation,
)


def test_tech_spec_preset_definition():
    preset = load_preset("tech-spec")
    assert preset.name == "tech-spec"
    assert "has_test_plan" in preset.questions
    assert preset.questions["has_test_plan"].type == "noul"
    assert preset.questions["has_test_plan"].weight == 1.0
    assert "readiness" in preset.questions
    assert preset.questions["readiness"].type == "choice"
    score_questions = [q for q in preset.questions.values() if q.type == "score"]
    assert len(score_questions) == 0


def test_validate_with_tech_spec_preset(tmp_path):
    # Create sample docs
    doc_full = tmp_path / "spec_full.md"
    doc_full.write_text(
        "# Spec\n"
        "## Architecture\nDetails here.\n"
        "## Failure Modes\nRetries and timeouts.\n"
        "## Test Plan\nUnit tests and integration tests.\n",
        encoding="utf-8",
    )

    doc_degraded = tmp_path / "spec_degraded.md"
    doc_degraded.write_text(
        "# Spec\nHandwaving content without failure modes or test plan.\n",
        encoding="utf-8",
    )

    labels_data = {
        "preset": "tech-spec",
        "runs": 2,
        "criteria": {
            "min_detected": 1,
            "max_false_alarms": 0,
        },
        "documents": [
            {
                "path": str(doc_full),
                "expect": {"has_test_plan": "present"},
            },
            {
                "path": str(doc_degraded),
                "expect": {"has_test_plan": "absent"},
            },
        ],
    }

    labels_file = tmp_path / "labels.yaml"
    import yaml

    labels_file.write_text(yaml.dump(labels_data), encoding="utf-8")

    labels_cfg, base_dir = load_labels_file(labels_file)
    evaluator = TypeSafeEvaluator()

    report, has_error = run_validation(
        labels_cfg=labels_cfg,
        base_dir=base_dir,
        evaluator=evaluator,
        dry_run=True,
    )

    assert not has_error
    assert report.preset_name == "tech-spec"
    assert len(report.presence_results) == 2
    assert len(report.pair_results) == 0

    # Verify readiness distribution was recorded (non-gating)
    assert "readiness" in report.choice_distributions
    readiness_counts = report.choice_distributions["readiness"]
    assert sum(readiness_counts.values()) > 0

    # Verify markdown includes choice distributions
    md_output = render_validation_markdown(report)
    assert "Choice Distributions (Non-gating" in md_output
    assert "`readiness`" in md_output


def test_cli_validate_tech_spec_dry_run(tmp_path):
    runner = CliRunner()
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nArchitecture\n", encoding="utf-8")

    labels_data = {
        "preset": "tech-spec",
        "runs": 1,
        "documents": [
            {
                "path": str(doc),
                "expect": {"has_test_plan": "present"},
            }
        ],
    }
    labels_file = tmp_path / "labels.yaml"
    import yaml

    labels_file.write_text(yaml.dump(labels_data), encoding="utf-8")

    result = runner.invoke(main, ["validate", str(labels_file), "--dry-run"])
    assert result.exit_code in (0, 1)  # Depends on criteria pass/fail, but not crash (exit 2 or 3)
    assert "TypeSafe Validation Report" in result.output
    assert "tech-spec" in result.output
    assert "Choice Question Distributions" in result.output


def test_feasibility_check_with_quality_preset(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Tech Spec\nSystem design details.", encoding="utf-8")

    report = run_feasibility(
        doc_paths=[doc1],
        preset_name="quality",
        question_id="clarity",
        runs=1,
        dry_run=True,
    )

    assert report["preset"] == "quality"
    assert report["num_pairs"] == 3
    assert len(report["pairs"]) == 3


def test_validate_expect_label_typo_fails_at_load_time(tmp_path):
    runner = CliRunner()
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nContent", encoding="utf-8")

    labels_data = {
        "preset": "tech-spec",
        "documents": [
            {
                "path": str(doc),
                "expect": {"has_test_plan": "presnt"},
            }
        ],
    }
    labels_file = tmp_path / "labels_typo.yaml"
    import yaml

    labels_file.write_text(yaml.dump(labels_data), encoding="utf-8")

    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 2
    out = " ".join(result.output.split())
    assert "Invalid expectation 'presnt' for question 'has_test_plan'" in out
    assert "must be 'present' or 'absent'" in out


def test_validate_choice_question_label_rejected(tmp_path):
    runner = CliRunner()
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nContent", encoding="utf-8")

    labels_data = {
        "preset": "tech-spec",
        "documents": [
            {
                "path": str(doc),
                "expect": {"readiness": "present"},
            }
        ],
    }
    labels_file = tmp_path / "labels_choice.yaml"
    import yaml

    labels_file.write_text(yaml.dump(labels_data), encoding="utf-8")

    result = runner.invoke(main, ["validate", str(labels_file)])
    assert result.exit_code == 2
    out = " ".join(result.output.split())
    assert (
        "readiness is a choice question; its distribution is recorded automatically, do not label it"
        in out
    )


def test_feasibility_check_question_validation_typo_and_noul(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nContent", encoding="utf-8")

    # Typo in question_id
    with pytest.raises(ValueError) as excinfo_typo:
        run_feasibility(
            doc_paths=[doc],
            preset_name="quality",
            question_id="calrity",
            dry_run=True,
        )
    assert "Question 'calrity' is not a valid score question in preset 'quality'" in str(
        excinfo_typo.value
    )
    assert "Available score question(s): clarity" in str(excinfo_typo.value)

    # Noul question_id passed as score
    with pytest.raises(ValueError) as excinfo_noul:
        run_feasibility(
            doc_paths=[doc],
            preset_name="safety",
            question_id="has_secrets",
            dry_run=True,
        )
    assert "Question 'has_secrets' is not a valid score question in preset 'safety'" in str(
        excinfo_noul.value
    )
    assert "Available score question(s): confidentiality_risk" in str(excinfo_noul.value)

    # Preset without clarity and no question specified
    with pytest.raises(ValueError) as excinfo_no_q:
        run_feasibility(
            doc_paths=[doc],
            preset_name="safety",
            question_id=None,
            dry_run=True,
        )
    assert (
        "Preset 'safety' has no 'clarity' question. Specify a score question with --question."
        in str(excinfo_no_q.value)
    )
    assert "Available score question(s): confidentiality_risk" in str(excinfo_no_q.value)


def test_feasibility_check_with_tech_spec_no_score_questions(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nContent", encoding="utf-8")

    # When --question is used with tech-spec (which has no score questions)
    with pytest.raises(ValueError) as excinfo_q:
        run_feasibility(
            doc_paths=[doc],
            preset_name="tech-spec",
            question_id="has_test_plan",
            dry_run=True,
        )
    assert "Question 'has_test_plan' is not a valid score question in preset 'tech-spec'." in str(
        excinfo_q.value
    )
    assert "Available score question(s): none" in str(excinfo_q.value)

    # When question_id is omitted with tech-spec
    with pytest.raises(ValueError) as excinfo_no_q:
        run_feasibility(
            doc_paths=[doc],
            preset_name="tech-spec",
            question_id=None,
            dry_run=True,
        )
    assert (
        "Preset 'tech-spec' has no 'clarity' question. Specify a score question with --question."
        in str(excinfo_no_q.value)
    )
    assert "Available score question(s): none" in str(excinfo_no_q.value)
