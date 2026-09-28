import json
import sys
from pathlib import Path
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.validator import (
    load_labels_file,
    run_validation,
    render_validation_markdown,
    render_validation_table,
)
from scripts.feasibility_check import run_feasibility


def test_tech_spec_preset_definition():
    preset = load_preset("tech-spec")
    assert preset.name == "tech-spec"
    assert "technical_depth" in preset.questions
    assert preset.questions["technical_depth"].type == "score"
    assert "edge_case_coverage" in preset.questions
    assert preset.questions["edge_case_coverage"].type == "score"
    assert "has_test_plan" in preset.questions
    assert preset.questions["has_test_plan"].type == "noul"
    assert "readiness" in preset.questions
    assert preset.questions["readiness"].type == "choice"


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
        "pairs": [
            {
                "before": str(doc_full),
                "after": str(doc_degraded),
                "expect": {
                    "technical_depth": "down",
                    "edge_case_coverage": "down",
                },
            }
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
    assert len(report.pair_results) == 2

    # Verify readiness distribution was recorded (non-gating)
    assert "readiness" in report.choice_distributions
    readiness_counts = report.choice_distributions["readiness"]
    assert sum(readiness_counts.values()) > 0

    # Verify markdown includes choice distributions
    md_output = render_validation_markdown(report)
    assert "Choice Distributions (Non-gating)" in md_output
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


def test_feasibility_check_with_tech_spec_preset(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Tech Spec\nSystem design details.", encoding="utf-8")

    report = run_feasibility(
        doc_paths=[doc1],
        preset_name="tech-spec",
        question_id="technical_depth",
        runs=1,
        dry_run=True,
    )

    assert report["preset"] == "tech-spec"
    assert report["num_pairs"] == 3
    assert len(report["pairs"]) == 3
