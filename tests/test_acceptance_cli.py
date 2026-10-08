"""End-to-End Real Subprocess Acceptance Criteria (AC) Verification Test Suite.

These tests execute the installed CLI, console scripts, and integration hooks
as isolated OS processes to verify real exit codes, JSON stdout streams, stderr
separation, and security boundaries.

Run specifically with:
    pytest -v -m acceptance
"""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.acceptance
def test_ac_01_version_flag():
    """AC-1: typesafe-eval --version exits 0 and prints version."""
    cp = subprocess.run(
        [sys.executable, "-m", "typesafe_eval.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    assert "typesafe-eval, version" in cp.stdout


@pytest.mark.acceptance
def test_ac_02_missing_file_exit_2(tmp_path):
    """AC-2: Missing file arguments exit 2 with error to stderr."""
    missing = tmp_path / "not_found.md"
    cp = subprocess.run(
        [sys.executable, "-m", "typesafe_eval.cli", str(missing)],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 2
    assert "Error: File not found" in cp.stderr


@pytest.mark.acceptance
def test_ac_03_invalid_preset_exit_2(tmp_path):
    """AC-3: Invalid preset names exit 2 with error to stderr."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\nClean.", encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "invalid_preset_404",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 2
    assert "Error loading preset" in cp.stderr


@pytest.mark.acceptance
def test_ac_04_clean_doc_dry_run_pass(tmp_path):
    """AC-4: Clean document dry-run exits 0, passed_thresholds=True, violations=[]."""
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean Architecture\nPublic system specification.", encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert len(data) == 1
    assert data[0]["passed_thresholds"] is True
    assert data[0]["violations"] == []
    assert data[0]["mock"] is True


@pytest.mark.acceptance
def test_ac_05_quoted_secret_masking(tmp_path):
    """AC-5: Quoted JSON/YAML secret keys masked as [SECRET_1], outcome: secret, zero raw leak."""
    doc = tmp_path / "payload.json"
    raw_secret = "ConfidentialApiKey9999!"
    doc.write_text(f'{{"api_key": "{raw_secret}"}}', encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    assert raw_secret not in cp.stdout
    assert raw_secret not in cp.stderr
    data = json.loads(cp.stdout)
    sec_evals = data[0].get("secret_evaluations", [])
    assert any(s["placeholder"] == "[SECRET_1]" and s["outcome"] == "secret" for s in sec_evals)


@pytest.mark.acceptance
def test_ac_06_slack_token_detection(tmp_path):
    """AC-6: Slack tokens detected by rule as [REDACTED_SLACK_TOKEN], outcome: secret, zero raw leak."""
    doc = tmp_path / "tokens.md"
    raw_token = "xox" + "b-1234567890-abcdefghijklmn"
    doc.write_text(f"Slack bot: {raw_token}", encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    assert raw_token not in cp.stdout
    assert raw_token not in cp.stderr
    data = json.loads(cp.stdout)
    sec_evals = data[0].get("secret_evaluations", [])
    assert any(
        s["placeholder"] == "[REDACTED_SLACK_TOKEN]"
        and s["outcome"] == "secret"
        and s["decided_by"] == "rule"
        for s in sec_evals
    )


@pytest.mark.acceptance
def test_ac_07_international_phone_pii(tmp_path):
    """AC-7: International E.164 phone numbers masked as [PHONE_1], country_format: international."""
    doc = tmp_path / "phone.md"
    raw_phone = "+44 20 7946 0991"
    doc.write_text(f"Phone: {raw_phone}", encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    assert raw_phone not in cp.stdout
    assert raw_phone not in cp.stderr
    data = json.loads(cp.stdout)
    phone_evals = data[0].get("phone_evaluations", [])
    assert any(
        p["placeholder"] == "[PHONE_1]"
        and p.get("features", {}).get("country_format") == "international"
        for p in phone_evals
    )


@pytest.mark.acceptance
def test_ac_08_missing_api_key_exit_3(tmp_path):
    """AC-8: Missing TYPESAFE_API_KEY on live evaluation returns Exit 3 with notice on stderr."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\nLive eval test.", encoding="utf-8")
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    cp = subprocess.run(
        [sys.executable, "-m", "typesafe_eval.cli", str(doc), "--preset", "safety", "--no-cache"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 3
    assert "No TypeSafe API key provided" in cp.stderr


@pytest.mark.acceptance
def test_ac_09_content_violation_exit_1(tmp_path):
    """AC-9: Content violations return Exit Code 1 with violation details on stdout."""
    doc = tmp_path / "violation.md"
    doc.write_text("# Content\nSecurity leak.", encoding="utf-8")
    code = f"""
import sys
from unittest.mock import patch
from typesafe_eval.models import DocumentEvalResult
from typesafe_eval.cli import main

def fake_eval(self, filepath, **kwargs):
    return DocumentEvalResult(
        filepath=filepath,
        filename='{doc.name}',
        preset_name='safety',
        passed_thresholds=False,
        violations=['Credential Exposure: [SECRET_1] is an exposed secret'],
    )

with patch('typesafe_eval.client.TypeSafeEvaluator.evaluate_document', fake_eval):
    sys.argv = ['typesafe-eval', '{str(doc)}', '--preset', 'safety']
    main()
"""
    cp = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert cp.returncode == 1
    assert "Credential Exposure" in cp.stdout


@pytest.mark.acceptance
def test_ac_10_exit_1_over_3_precedence(tmp_path):
    """AC-10: Precedence rule guarantees Exit 1 takes precedence over Exit 3 when violations and errors coexist."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc 1")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Doc 2")
    code = f"""
import sys
from unittest.mock import patch
from typesafe_eval.models import DocumentEvalResult
from typesafe_eval.cli import main

def fake_eval(self, filepath, **kwargs):
    if '{doc1.name}' in filepath:
        return DocumentEvalResult(
            filepath=filepath,
            filename='{doc1.name}',
            preset_name='safety',
            passed_thresholds=False,
            violations=['PII Exposure: [EMAIL_1] is an individual address'],
        )
    raise RuntimeError('Connection timeout')

with patch('typesafe_eval.client.TypeSafeEvaluator.evaluate_document', fake_eval):
    sys.argv = ['typesafe-eval', '{str(doc1)}', '{str(doc2)}', '--preset', 'safety']
    main()
"""
    cp = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert cp.returncode == 1
    assert "PII Exposure" in cp.stdout
    assert "Connection timeout" in cp.stderr


@pytest.mark.acceptance
def test_ac_11_stdout_json_purity(tmp_path):
    """AC-11: Output format json yields 100% valid JSON stream on stdout parseable by json.loads."""
    doc = tmp_path / "pure.md"
    doc.write_text("# Doc\nValid.", encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    parsed = json.loads(cp.stdout)
    assert isinstance(parsed, list)
    assert parsed[0]["schema_version"] == "1.0"


@pytest.mark.acceptance
def test_ac_12_pre_commit_hook_graceful_skip(tmp_path):
    """AC-12: typesafe-eval-hook maps Exit 3 to Exit 0 with graceful skip notice."""
    doc = tmp_path / "hook.md"
    doc.write_text("# Doc\nHook testing.", encoding="utf-8")
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    cp = subprocess.run(
        [sys.executable, "-m", "typesafe_eval.hook", str(doc)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0
    assert "skipped execution" in cp.stderr


@pytest.mark.acceptance
def test_ac_13_claude_safety_hook():
    """AC-13: Claude safety hook returns Exit 0 on clean repository."""
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    cp = subprocess.run(
        [sys.executable, "hooks/claude_safety_hook.py"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0


@pytest.mark.acceptance
def test_ac_14_scaffolding_init_command():
    """AC-14: typesafe-eval init --help exits 0 and presents all integration onboarding options."""
    cp = subprocess.run(
        [sys.executable, "-m", "typesafe_eval.cli", "init", "--help"],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    for flag in ["--pre-commit", "--claude-code", "--github-action", "--all"]:
        assert flag in cp.stdout


@pytest.mark.acceptance
def test_ac_15_offline_rules_mode(tmp_path):
    """AC-15: typesafe-eval --offline evaluates via deterministic rules without API key."""
    doc = tmp_path / "offline_clean.md"
    doc.write_text("# Offline Clean\nDocumentation text without secrets.", encoding="utf-8")
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--offline",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert len(data) == 1
    assert data[0]["passed_thresholds"] is True
    assert data[0]["api_calls"] == 0


@pytest.mark.acceptance
def test_ac_16_result_cache(tmp_path):
    """AC-16: typesafe-eval --cache serves cached results without API key and clear command works."""
    from typesafe_eval.cache import EvaluationCache
    from typesafe_eval.models import DocumentEvalResult
    from typesafe_eval.presets import load_preset

    cache_dir = tmp_path / "cache_store"
    cache = EvaluationCache(cache_dir=cache_dir)
    preset = load_preset("safety")
    content = "# Cache Document\nClean text."
    doc = tmp_path / "cached_doc.md"
    doc.write_text(content, encoding="utf-8")
    cache.set(
        content,
        preset,
        DocumentEvalResult(
            filepath=str(doc),
            filename=doc.name,
            preset_name="safety",
            passed_thresholds=True,
        ),
    )
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    cp1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--cache",
            "--cache-dir",
            str(cache_dir),
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp1.returncode == 0
    assert '"cached": true' in cp1.stdout

    cp2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            "cache",
            "clear",
            "--cache-dir",
            str(cache_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert cp2.returncode == 0
    assert "Cleared 1 cached" in cp2.stdout


@pytest.mark.acceptance
def test_ac_17_github_actions_annotations(tmp_path):
    """AC-17: typesafe-eval -f github formats violations as GitHub workflow command annotations."""
    doc = tmp_path / "github_violating.md"
    doc.write_text("# Violating Doc\nContact: user@gmail.com\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--preset",
            "safety",
            "--offline",
            "-f",
            "github",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 1
    assert "::error file=" in cp.stdout
    assert "line=2" in cp.stdout


@pytest.mark.acceptance
def test_ac_18_file_exclusions(tmp_path):
    """AC-18: typesafe-eval --exclude filters out matching glob patterns."""
    valid_doc = tmp_path / "eval_me.md"
    valid_doc.write_text("# Valid File\nClean text.", encoding="utf-8")
    draft_doc = tmp_path / "skip_me.draft.md"
    draft_doc.write_text("# Draft File\nNot ready.", encoding="utf-8")
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(tmp_path / "*.md"),
            "--exclude",
            "*.draft.md",
            "--preset",
            "safety",
            "--offline",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    filenames = [item["filename"] for item in data]
    assert "eval_me.md" in filenames
    assert "skip_me.draft.md" not in filenames


@pytest.mark.acceptance
def test_ac_19_multimodal_image_evaluation(tmp_path):
    """AC-19: typesafe-eval --include-images resolves embedded images, emits stderr advisory, and preserves stdout purity."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img = tmp_path / "diagram.png"
    img.write_bytes(png_bytes)
    doc = tmp_path / "multimodal.md"
    doc.write_text("# Architecture\n![Diagram](diagram.png)\n", encoding="utf-8")

    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "typesafe_eval.cli",
            str(doc),
            "--include-images",
            "--dry-run",
            "-f",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0
    assert "Security advisory:" in cp.stderr
    data = json.loads(cp.stdout)
    assert len(data) == 1
    assert data[0]["images_evaluated"] == 1
    assert data[0]["image_paths"] == ["diagram.png"]
