"""Unit and integration tests for v0.5.1 reliability and safety improvements.

Covers:
1. JSON/YAML quoted key secret detection, changeme placeholder, Slack tokens, colon spacing, URL trailing symbol exclusion.
2. Core evaluation engine: _find_preflight_question pii fallback, support phone prefix LLM skip, long document chunking with candidate_specs when preset has no nouls.
3. Reporter: format_score_badge inverted colors for max_threshold risk questions.
4. CLI: Exit 2 detection when explicit non-existent file paths are specified.
5. Pre-commit hook: typesafe-eval-hook exit 3 skip wrapper and README repo URLs.
6. Claude Safety Hook: exit 2 only on valid JSON with violations, and git diff/status merging.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hooks.claude_safety_hook import extract_files_from_git, run_hook
from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator, _find_preflight_question
from typesafe_eval.hook import pre_commit_main
from typesafe_eval.models import PresetConfig, QuestionConfig
from typesafe_eval.presets import load_preset
from typesafe_eval.reporter import format_score_badge
from typesafe_eval.sanitizer import (
    PLACEHOLDER_SUBSTRINGS,
    URL_PATTERN,
    extract_url_features,
    mask_sensitive_data,
)

# ============================================================================
# Task 1: Sanitizer & Credential / Secret Detection
# ============================================================================


def test_quoted_json_yaml_keys_detected():
    """Double-quoted and single-quoted keys in JSON/YAML are detected with colon space preserved."""
    json_text = '{"password": "secretPassword123!", "other": 1}'
    masked, count, details = mask_sensitive_data(json_text, return_details=True)
    assert count == 1
    assert '"password": [SECRET_1]' in masked
    assert "secretPassword123!" not in masked
    assert details["credentials"] == 0  # ambiguous secret is model-decided
    assert len(details["redacted_secrets"]) == 1
    assert details["redacted_secrets"][0]["key_name"] == "password"

    yaml_text = "'api_key': 'super_secret_token_abc'\n"
    masked_yaml, count_yaml, _ = mask_sensitive_data(yaml_text, return_details=True)
    assert count_yaml == 1
    assert "'api_key': [SECRET_1]" in masked_yaml
    assert "super_secret_token_abc" not in masked_yaml

    unquoted_text = "password: my_secret_pass"
    masked_unq, _, _ = mask_sensitive_data(unquoted_text, return_details=True)
    assert "password: [SECRET_1]" in masked_unq


def test_changeme_placeholder_substring():
    """'changeme' in PLACEHOLDER_SUBSTRINGS neutralizes credentials into example tokens."""
    assert "changeme" in PLACEHOLDER_SUBSTRINGS

    text = "Config: password=changeme_12345"
    masked, count, details = mask_sensitive_data(text, return_details=True)
    assert count == 0  # Neutralized
    assert details["examples"] == 1
    assert "password=[SECRET_1]" in masked
    assert details["redacted_secrets"][0]["outcome"] == "safe"
    assert details["redacted_secrets"][0]["decided_by"] == "rule"


def test_slack_token_detection():
    """Slack token pattern matches xoxb, xoxp, xoxa, xoxr, xoxs tokens deterministically."""
    tokens = [
        f"{prefix}-" + "1" * 10 + "-" + "2" * 13 + "-" + "a" * 16
        for prefix in ("xoxb", "xoxp", "xoxa", "xoxr", "xoxs")
    ]
    for tok in tokens:
        raw = f"Slack auth token: {tok}."
        masked, count, details = mask_sensitive_data(raw, return_details=True)
        assert count == 1
        assert tok not in masked
        assert "[REDACTED_SLACK_TOKEN]" in masked
        assert details["credentials"] == 1
        assert details["by_type"].get("slack_token") == 1
        assert any("slack_token" in v for v in details["rule_violations"])


def test_url_pattern_excludes_trailing_punctuation():
    """URL regex and feature extraction exclude trailing punctuation: ., ,, ], ), >."""
    sample = (
        "Check https://internal.example.corp/api/v1. "
        "Also see https://dashboard.example.corp/home, then [https://metrics.example.corp/live] "
        "and (https://status.example.corp/health). Finally <https://secure.example.corp/login>."
    )
    matches = URL_PATTERN.findall(sample)
    assert "https://internal.example.corp/api/v1" in matches
    assert "https://dashboard.example.corp/home" in matches
    assert "https://metrics.example.corp/live" in matches
    assert "https://status.example.corp/health" in matches
    assert "https://secure.example.corp/login" in matches
    for m in matches:
        assert not m.endswith((".", ",", "]", ")", ">"))

    feat = extract_url_features("https://internal.corp/status.")
    assert feat["is_internal_tld"] is True

    masked, count, _ = mask_sensitive_data(
        "Visit https://internal.corp/admin.", return_details=True
    )
    assert count == 1
    assert "[URL_1]." in masked  # The period stays outside the placeholder


# ============================================================================
# Task 2: Core Evaluation Engine
# ============================================================================


def test_find_preflight_question_pii_fallback():
    """_find_preflight_question falls back to has_pii when target is pii."""
    preset_with_has_pii = PresetConfig(
        name="test_preset",
        questions={
            "has_pii": QuestionConfig(type="noul", label="PII", instructions="Check PII"),
        },
    )
    assert _find_preflight_question(preset_with_has_pii, "pii") == "has_pii"

    preset_explicit = PresetConfig(
        name="test_preset",
        questions={
            "custom_pii": QuestionConfig(
                type="noul", label="PII", instructions="Check PII", preflight="pii"
            ),
            "has_pii": QuestionConfig(type="noul", label="PII", instructions="Check PII"),
        },
    )
    assert _find_preflight_question(preset_explicit, "pii") == "custom_pii"


def test_support_phone_prefix_skips_llm(tmp_path):
    """Support phone prefix (0120, 1-800) is evaluated by rule and not sent to LLM candidate_specs."""
    doc = tmp_path / "phone_doc.md"
    doc.write_text(
        "Call toll-free 0120-123-456 or US 1-800-555-0199 for assistance.", encoding="utf-8"
    )

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {
        "confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})
    }
    mock_resp.nouls = {
        "has_secrets": MagicMock(noul=0.01),
        "has_pii": MagicMock(noul=0.05),
    }
    mock_resp.choices = {
        "policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})
    }
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset)
    called_questions = mock_client.system_one.call_args.kwargs["questions"]
    assert not any(k.startswith("phone_pii_") for k in called_questions)

    assert len(result.phone_evaluations) == 2
    for pe in result.phone_evaluations:
        assert pe.outcome == "support"
        assert pe.decided_by == "rule"
        assert pe.probability is None


def test_long_document_candidate_chunking_without_nouls(tmp_path):
    """Long document (>25k chars) with candidate_specs chunks and evaluates candidates even when preset has no nouls."""
    from types import SimpleNamespace as NS

    # Create a preset with score and choice only (NO noul questions)
    preset_no_nouls = PresetConfig(
        name="score_only_preset",
        questions={
            "quality_score": QuestionConfig(
                type="score",
                label="Quality",
                instructions="Rate quality",
                criteria=["Low", "Med", "High"],
                min_threshold=0.5,
            ),
            "compliance_choice": QuestionConfig(
                type="choice",
                label="Compliance",
                instructions="Compliance check",
                criteria=["compliant", "non-compliant"],
            ),
        },
    )

    FILL = "This is a detailed architectural section of the document.\n\n" * 600  # ~35k chars
    doc = tmp_path / "long_doc.md"
    doc.write_text(
        FILL + 'db_password: "actual_production_secret_pass!"\n\n' + FILL, encoding="utf-8"
    )

    evaluator = TypeSafeEvaluator(api_key="mock-key")

    class RecordingFakeClient:
        def __init__(self):
            self.calls = []

        def system_one(self, state, questions):
            self.calls.append(sorted(list(questions.keys())))
            scores = {"quality_score": NS(score=2, confidence=0.9, probabilities={})}
            choices = {
                "compliance_choice": NS(choice="compliant", confidence=0.9, probabilities={})
            }
            nouls = {q: NS(noul=0.92) for q in questions if q.startswith("secret_")}
            return NS(usage=None, model="mock-jev", scores=scores, choices=choices, nouls=nouls)

    client = RecordingFakeClient()
    evaluator._client = client

    res = evaluator.evaluate_document(str(doc), preset=preset_no_nouls)
    assert res.api_calls > 1
    assert len(client.calls) >= 2
    assert ["compliance_choice", "quality_score"] in client.calls
    assert ["secret_1"] in client.calls
    # Candidate question secret_1 was asked and evaluated
    assert len(res.secret_evaluations) == 1
    assert res.secret_evaluations[0].outcome == "secret"
    assert res.secret_evaluations[0].probability == 0.92


# ============================================================================
# Task 3: Terminal Display Score Badge Inversion
# ============================================================================


def test_format_score_badge_inversion():
    """format_score_badge inverts green/red threshold logic when invert=True."""
    # Standard (quality/compliance: higher is better)
    assert "green" in format_score_badge(0.85, invert=False)
    assert "yellow" in format_score_badge(0.60, invert=False)
    assert "red" in format_score_badge(0.20, invert=False)

    # Inverted (risk/exposure: lower is better/safer)
    assert "green" in format_score_badge(0.20, invert=True)  # <= 0.25 is safe/green
    assert "yellow" in format_score_badge(0.40, invert=True)  # <= 0.50 is yellow
    assert "red" in format_score_badge(0.85, invert=True)  # > 0.50 is dangerous/red


# ============================================================================
# Task 4: CLI Exit 2 for Non-existent Files
# ============================================================================


def test_cli_exit_2_on_non_existent_explicit_path(tmp_path):
    """Passing a non-existent explicit path results in error output on stderr and exit code 2."""
    runner = CliRunner()
    result = runner.invoke(main, ["eval", "does_not_exist_file.md", "--preset", "safety"])
    assert result.exit_code == 2
    assert "File not found: does_not_exist_file.md" in (result.stderr or result.output)

    # Existing file mixed with non-existent file must also trigger exit code 2
    existing = tmp_path / "exists.md"
    existing.write_text("# Hello", encoding="utf-8")
    result_mixed = runner.invoke(main, ["eval", str(existing), "missing_partner.md"])
    assert result_mixed.exit_code == 2
    assert "File not found: missing_partner.md" in (result_mixed.stderr or result_mixed.output)


# ============================================================================
# Task 5: Pre-commit Hook Wrapper & README
# ============================================================================


def test_pre_commit_hook_exit_3_skipped_as_0(capsys):
    """pre_commit_main catches exit code 3 and converts it to exit code 0."""
    with patch("typesafe_eval.hook.main", side_effect=SystemExit(3)):
        with pytest.raises(SystemExit) as excinfo:
            pre_commit_main()
        assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "skipped execution due to missing secret or runtime unavailable" in captured.err

    # Other exit codes are preserved
    for code in (0, 1, 2):
        with patch("typesafe_eval.hook.main", side_effect=SystemExit(code)):
            with pytest.raises(SystemExit) as excinfo:
                pre_commit_main()
            assert excinfo.value.code == code


def test_readme_urls_fixed():
    """README.md contains s-0-a-r instead of typesafe-ai in URLs."""
    readme_path = Path(__file__).parent.parent / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    assert "typesafe-ai" not in text
    assert "s-0-a-r/typesafe-eval" in text


# ============================================================================
# Task 6: Claude Safety Hook Hardening
# ============================================================================


def test_claude_hook_exit_1_requires_valid_json_with_violations(tmp_path, monkeypatch, capsys):
    """exit code 1 exits 2 only if stdout is valid JSON with violations; otherwise exits 0."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc", encoding="utf-8")

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    # Case A: Valid JSON with violations -> exit 2
    valid_proc = MagicMock(
        returncode=1,
        stdout=json.dumps([{"filename": "doc.md", "violations": ["PII Exposure: [EMAIL_1]"]}]),
        stderr="",
    )
    with patch("subprocess.run", return_value=valid_proc):
        assert run_hook(args=[str(doc)]) == 2

    # Case B: Python traceback / non-JSON output on exit 1 -> exit 0 (skips gracefully)
    traceback_proc = MagicMock(
        returncode=1,
        stdout="Traceback (most recent call last):\n  File 'cli.py', line 42, in <module>\n",
        stderr="Error occurred",
    )
    with patch("subprocess.run", return_value=traceback_proc):
        assert run_hook(args=[str(doc)]) == 0

    # Case C: Valid JSON but empty violations -> exit 0
    empty_violations_proc = MagicMock(
        returncode=1,
        stdout=json.dumps([{"filename": "doc.md", "violations": []}]),
        stderr="",
    )
    with patch("subprocess.run", return_value=empty_violations_proc):
        assert run_hook(args=[str(doc)]) == 0


def test_extract_files_from_git_merges_diff_and_status(tmp_path, monkeypatch):
    """extract_files_from_git returns both tracked diff files and untracked status files."""
    tracked_file = tmp_path / "tracked.md"
    tracked_file.write_text("# Tracked", encoding="utf-8")
    untracked_file = tmp_path / "untracked.md"
    untracked_file.write_text("# Untracked", encoding="utf-8")

    def mock_subprocess_run(cmd, *args, **kwargs):
        if cmd[1] == "diff":
            return MagicMock(returncode=0, stdout=str(tracked_file) + "\n")
        elif cmd[1] == "status":
            return MagicMock(returncode=0, stdout=f"?? {untracked_file}\n")
        return MagicMock(returncode=1, stdout="")

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        found = extract_files_from_git()
        assert str(tracked_file) in found
        assert str(untracked_file) in found
