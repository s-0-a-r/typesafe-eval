"""Unit and integration tests for Issue #46: Chunking long documents for presence questions."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.models import DocumentEvalResult, BaselineDiff, PresetConfig, QuestionConfig
from typesafe_eval.baseline import compare_document_with_baseline
from typesafe_eval.reporter import render_table, render_markdown, render_json


def test_dry_run_noul_preset_long_doc_chunks(tmp_path):
    """AC 1 & 4: Noul preset splits long doc, api_calls > 1, was_truncated is False."""
    doc = tmp_path / "long_doc.md"
    # Create doc longer than 500 chars with max_chars=300
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(15)]), encoding="utf-8")

    evaluator = TypeSafeEvaluator()
    preset = load_preset("design-doc")
    res = evaluator.evaluate_document(str(doc), preset=preset, max_chars=300, dry_run=True)

    assert res.api_calls > 1
    assert res.was_truncated is False
    assert res.mock is True


def test_dry_run_quality_preset_long_doc_not_chunked(tmp_path):
    """AC 3: Score/Choice preset does not chunk, keeps head/tail truncation and was_truncated=True."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(15)]), encoding="utf-8")

    evaluator = TypeSafeEvaluator()
    preset = load_preset("quality")
    res = evaluator.evaluate_document(str(doc), preset=preset, max_chars=300, dry_run=True)

    assert res.api_calls == 1
    assert res.was_truncated is True
    assert res.mock is True


def test_dry_run_mixed_preset_long_doc(tmp_path):
    """Mixed preset (Scores + Nouls) evaluates scores on truncated and nouls on chunks."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(15)]), encoding="utf-8")

    evaluator = TypeSafeEvaluator()
    preset = PresetConfig(
        name="mixed-preset",
        title="Mixed Preset",
        description="Synthetic preset with score and noul questions",
        questions={
            "clarity": QuestionConfig(
                type="score",
                label="Clarity",
                instructions="Score clarity",
                criteria=["Low", "High"],
                weight=0.5,
            ),
            "has_tests": QuestionConfig(
                type="noul",
                label="Has Tests",
                instructions="Check test plan",
                min_threshold=0.8,
                weight=0.5,
            ),
        },
    )
    res = evaluator.evaluate_document(str(doc), preset=preset, max_chars=300, dry_run=True)

    assert res.api_calls > 1
    assert res.was_truncated is True
    assert res.mock is True


def test_api_calls_displayed_in_cli_table(tmp_path):
    """AC 4: Terminal table displays (N calls) when chunking happens."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(20)]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "design-doc", "--dry-run", "--max-chars", "300"])
    assert result.exit_code == 0
    assert "calls)" in result.output


def test_api_calls_displayed_in_cli_markdown(tmp_path):
    """AC 4: Markdown report displays *(N calls)* when chunking happens."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(20)]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "design-doc", "--dry-run", "--max-chars", "300", "--format", "markdown"])
    assert result.exit_code == 0
    assert "calls)*" in result.output


def test_api_calls_in_json_output(tmp_path):
    """AC 4: JSON report contains api_calls field."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text here for section {i}." for i in range(20)]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "design-doc", "--dry-run", "--max-chars", "300", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["api_calls"] > 1
    assert data[0]["was_truncated"] is False


def test_baseline_warns_on_truncation_mismatch(tmp_path):
    """AC 5: --baseline warns when was_truncated differs between baseline and current."""
    doc_path = str(tmp_path / "doc.md")
    preset = load_preset("design-doc")

    # Baseline had truncation (was_truncated=True)
    baseline_res = DocumentEvalResult(
        filepath=doc_path,
        filename="doc.md",
        preset_name="design-doc",
        was_truncated=True,
    )
    baseline_lookup = {doc_path: baseline_res}

    # Current has chunking without truncation (was_truncated=False)
    curr_res = DocumentEvalResult(
        filepath=doc_path,
        filename="doc.md",
        preset_name="design-doc",
        was_truncated=False,
        api_calls=2,
    )

    updated, has_regression, warning = compare_document_with_baseline(curr_res, baseline_lookup, preset)
    assert updated.baseline_diff is not None
    assert updated.baseline_diff.truncation_mismatch is True
    assert warning is not None
    assert "Truncation status differs" in warning


def test_chunk_missing_preset_noul_raises_runtime_error(tmp_path, monkeypatch):
    """Review item 1: If no chunk returns a preset Noul, raise RuntimeError naming the question."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text for section {i}." for i in range(15)]), encoding="utf-8")

    class MockAns:
        def __init__(self, val):
            self.noul = val

    class MockResp:
        def __init__(self, questions):
            # Omit 'rollback' from response
            self.nouls = {q: MockAns(0.95) for q in questions if q != "rollback"}
            self.scores = {}
            self.choices = {}
            self.usage = None
            self.model = "mock-jev"

    class MockClient:
        def system_one(self, state, questions):
            return MockResp(questions)

    evaluator = TypeSafeEvaluator(api_key="mock_key")
    monkeypatch.setattr(evaluator, "_get_client", lambda: MockClient())

    preset = load_preset("design-doc")
    with pytest.raises(RuntimeError) as exc_info:
        evaluator.evaluate_document(str(doc), preset=preset, max_chars=300)

    assert "rollback" in str(exc_info.value)
    assert "Missing evaluation result for question(s)" in str(exc_info.value)


def test_cli_chunk_missing_noul_exits_3(tmp_path, monkeypatch):
    """Review item 1: Missing Noul across chunks reports runtime error on stderr and exits 3."""
    doc = tmp_path / "long_doc.md"
    doc.write_text("\n\n".join([f"## Section {i}\nSome body text for section {i}." for i in range(15)]), encoding="utf-8")

    class MockAns:
        def __init__(self, val):
            self.noul = val

    class MockResp:
        def __init__(self, questions):
            self.nouls = {q: MockAns(0.95) for q in questions if q != "rollback"}
            self.scores = {}
            self.choices = {}
            self.usage = None
            self.model = "mock-jev"

    class MockClient:
        def system_one(self, state, questions):
            return MockResp(questions)

    from typesafe_eval import client as client_module
    monkeypatch.setattr(client_module.TypeSafeEvaluator, "_get_client", lambda self: MockClient())

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "design-doc", "--max-chars", "300", "--api-key", "test_key"])
    assert result.exit_code == 3
    assert "rollback" in (result.stderr or result.output)
    assert "Missing evaluation result" in (result.stderr or result.output)

