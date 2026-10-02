"""Unit tests for v0.6.0 candidate features:
- International phone numbers (E.164) and phone support prefixes
- Candidate question batching (TypeSafeEvaluator with max_candidate_batch_size)
- Portable cross-environment baseline diff matching
- CLI init subcommand scaffolding
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from typesafe_eval.sanitizer import (
    PHONE_PATTERN,
    extract_phone_features,
    mask_sensitive_data,
    PHONE_SUPPORT_PREFIXES,
)
from typesafe_eval.models import (
    PresetConfig,
    QuestionConfig,
    DocumentEvalResult,
    NoulResult,
    ScoreResult,
)
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.baseline import compare_document_with_baseline, load_baseline
from typesafe_eval.cli import main


def test_international_phone_e164_matching():
    """Verify that E.164 international phone numbers are properly detected."""
    samples = [
        ("+44 20 7946 0958", "international"),
        ("+44-20-7946-0958", "international"),
        ("+49 30 1234567", "international"),
        ("+33 1 23 45 67 89", "international"),
        ("+81 90 1234 5678", "international"),
        ("+65 6789 0123", "international"),
        ("+1 555-123-4567", "US"),
        ("1-800-555-0199", "US"),
        ("090-1234-5678", "JP"),
        ("03-1234-5678", "JP"),
    ]
    for phone_str, expected_format in samples:
        m = PHONE_PATTERN.search(phone_str)
        assert m is not None, f"Failed to match phone: {phone_str}"
        features = extract_phone_features(phone_str)
        assert features["country_format"] == expected_format, (
            f"Expected format {expected_format} for {phone_str}, got {features['country_format']}"
        )


def test_international_phone_masking():
    """Verify that international phone numbers are masked and features extracted."""
    text = "Please reach out to our UK contact at +44 20 7946 0958 or French office at +33 1 23 45 67 89."
    masked, count, details = mask_sensitive_data(text, mask=True, return_details=True)
    assert count == 2
    assert "[PHONE_1]" in masked
    assert "[PHONE_2]" in masked
    assert "+44 20 7946 0958" not in masked
    assert "+33 1 23 45 67 89" not in masked
    assert len(details["redacted_phones"]) == 2
    formats = [p["country_format"] for p in details["redacted_phones"]]
    assert formats == ["international", "international"]


def test_international_toll_free_prefix():
    """Verify that international toll-free prefixes (+800, +1-800) are recognized as support prefixes."""
    assert "+800" in PHONE_SUPPORT_PREFIXES
    features = extract_phone_features("+800-1234-5678")
    assert features["is_support_prefix"] is True
    assert features["looks_like_support"] is True


def test_candidate_question_batching(tmp_path):
    """Verify that TypeSafeEvaluator splits candidate questions into sub-batches when exceeding batch size."""
    doc_path = tmp_path / "many_candidates.md"
    # Create text with 25 email addresses
    emails = [f"contact_{i}@personal-mail.org" for i in range(25)]
    doc_path.write_text("Here are candidate contacts:\n" + "\n".join(emails), encoding="utf-8")

    preset = PresetConfig(
        name="safety",
        version="1.0",
        questions={
            "has_pii": QuestionConfig(
                type="noul",
                instructions="Does this document expose private PII?",
                threshold=0.5,
            )
        },
    )

    evaluator = TypeSafeEvaluator(api_key="test-key", max_candidate_batch_size=10)

    # Mock client and call tracking
    mock_client = MagicMock()
    evaluator._client = mock_client

    call_records = []

    def mock_system_one(state, questions):
        call_records.append({"questions": list(questions.keys())})
        mock_resp = MagicMock()
        mock_resp.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_resp.model = "jev-test"
        mock_resp.scores = {}
        mock_resp.choices = {}
        mock_resp.nouls = {
            q_id: MagicMock(noul=0.10)
            for q_id in questions
        }
        return mock_resp

    mock_client.system_one.side_effect = mock_system_one

    result = evaluator.evaluate_document(str(doc_path), preset=preset)

    # 25 candidates with batch size 10 -> should be 3 API calls (10, 10, 5)
    assert len(call_records) == 3
    # First call includes preset question 'has_pii' + first 10 candidate questions
    assert "has_pii" in call_records[0]["questions"]
    assert len(call_records[0]["questions"]) == 11  # 1 preset + 10 candidates
    assert len(call_records[1]["questions"]) == 10
    assert len(call_records[2]["questions"]) == 5
    # Token usage accumulated across all 3 calls
    assert result.usage["input_tokens"] == 300
    assert result.usage["output_tokens"] == 30
    assert len(result.email_evaluations) == 25


def test_portable_cross_environment_baseline_matching():
    """Verify that compare_document_with_baseline matches documents across different paths (e.g. CI vs local)."""
    # Simulate a baseline recorded in CI runner
    ci_path = "/home/runner/work/repo/repo/docs/spec.md"
    baseline_doc = DocumentEvalResult(
        filepath=ci_path,
        filename="spec.md",
        preset_name="quality",
        composite_score=0.85,
        passed_thresholds=True,
        scores={
            "clarity": ScoreResult(
                score=2.0, max_score=2.0, normalized_score=1.0, confidence=0.95, probabilities={}
            )
        },
    )
    baseline_lookup = {
        ci_path: baseline_doc,
    }

    preset = PresetConfig(
        name="quality",
        version="1.0",
        questions={
            "clarity": QuestionConfig(type="score", instructions="Score clarity", max_drop=0.15)
        },
    )

    # Current local run on macOS with relative path
    local_result = DocumentEvalResult(
        filepath="docs/spec.md",
        filename="spec.md",
        preset_name="quality",
        composite_score=0.82,
        passed_thresholds=True,
        scores={
            "clarity": ScoreResult(
                score=1.8, max_score=2.0, normalized_score=0.9, confidence=0.90, probabilities={}
            )
        },
    )

    updated_result, has_regression, warning = compare_document_with_baseline(
        local_result, baseline_lookup, preset=preset
    )

    assert updated_result.baseline_diff is not None
    assert updated_result.baseline_diff.status == "compared"
    assert updated_result.baseline_diff.baseline_filepath == ci_path
    assert "clarity" in updated_result.baseline_diff.questions
    clarity_diff = updated_result.baseline_diff.questions["clarity"]
    assert clarity_diff.delta == pytest.approx(-0.1, abs=1e-4)
    assert not has_regression


def test_cli_init_subcommand(tmp_path, monkeypatch):
    """Verify that 'typesafe-eval init' creates expected configuration files."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res = runner.invoke(main, ["init", "--all"])
    assert res.exit_code == 0
    assert "✓ .pre-commit-config.yaml" in res.output
    assert "✓ hooks/hooks.json" in res.output
    assert "✓ .github/workflows/typesafe-eval.yml" in res.output

    assert (tmp_path / ".pre-commit-config.yaml").is_file()
    assert (tmp_path / "hooks" / "hooks.json").is_file()
    assert (tmp_path / ".github" / "workflows" / "typesafe-eval.yml").is_file()

    # Second invocation should recognize existing files without errors
    res2 = runner.invoke(main, ["init", "--all"])
    assert res2.exit_code == 0
    assert "already configured" in res2.output or "already exists" in res2.output
