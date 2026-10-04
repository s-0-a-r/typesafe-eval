"""Unit tests for Issue #35: Agent integrations (Claude Code plugin, AGENTS.md, skill, hook)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from hooks.claude_safety_hook import (
    extract_files_from_stdin,
    run_hook,
)

REPO_ROOT = Path(__file__).parent.parent


def test_hooks_json_validity():
    """Verify hooks/hooks.json exists and is valid Claude Code hook config."""
    hook_cfg_file = REPO_ROOT / "hooks" / "hooks.json"
    assert hook_cfg_file.is_file(), "hooks/hooks.json must exist"

    with open(hook_cfg_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "hooks" in data
    hooks = data["hooks"]
    assert "PostToolUse" in hooks
    post_tool_use = hooks["PostToolUse"]
    assert isinstance(post_tool_use, list)
    assert len(post_tool_use) >= 1

    entry = post_tool_use[0]
    assert entry.get("matcher") == "Write|Edit"
    assert "claude_safety_hook.py" in entry.get("command", "")


def test_skill_md_content_and_guidance_rules():
    """Verify skills/typesafe-eval/SKILL.md exists and contains the 4 mandatory rules."""
    skill_file = REPO_ROOT / "skills" / "typesafe-eval" / "SKILL.md"
    assert skill_file.is_file(), "skills/typesafe-eval/SKILL.md must exist"

    content = skill_file.read_text(encoding="utf-8")
    assert "name: typesafe-eval" in content
    assert "safety" in content
    assert "quality" in content
    assert "tech-spec" in content
    assert "1.0" in content

    # 4 Mandatory Guidance Rules
    # Rule 1: loop target / cap rounds
    assert "loop target" in content.lower()
    assert "2 rounds" in content
    # Rule 2: language caveat
    assert "language caveat" in content.lower()
    assert "English" in content
    # Rule 3: near-threshold results are soft
    assert "near-threshold" in content.lower() or "near_threshold" in content
    assert "soft" in content.lower()
    # Rule 4: never pass API key through agent
    assert "never pass api key" in content.lower()


def test_agents_md_content_and_guidance_rules():
    """Verify AGENTS.md exists in repo root and contains agent guidance & 4 rules."""
    agents_file = REPO_ROOT / "AGENTS.md"
    assert agents_file.is_file(), "AGENTS.md must exist in repo root"

    content = agents_file.read_text(encoding="utf-8")
    # Exit codes
    assert "0" in content and "1" in content and "2" in content and "3" in content
    assert "Precedence Rule" in content

    # Contract & Candidate evaluation
    assert "violations" in content
    assert "email_evaluations" in content
    assert "secret_evaluations" in content

    # 4 Mandatory Guidance Rules
    # Rule 1: loop target / cap rounds
    assert "loop target" in content.lower()
    assert "2 rounds" in content
    # Rule 2: language caveat
    assert "language caveat" in content.lower()
    assert "English" in content
    # Rule 3: near-threshold results are soft
    assert "near-threshold" in content.lower() or "near_threshold" in content
    assert "soft" in content.lower()
    # Rule 4: never pass API key through agent
    assert "never pass api key" in content.lower()


def test_hook_stdin_json_extraction(tmp_path: Path, monkeypatch):
    """extract_files_from_stdin extracts target path from Claude Code hook JSON."""
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec", encoding="utf-8")

    hook_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "path": str(doc),
                "content": "# Spec",
            },
        }
    )

    monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: False, read=lambda: hook_payload))
    found = extract_files_from_stdin()
    assert found == [str(doc)]


def test_hook_exit_code_0_clean(tmp_path: Path, monkeypatch):
    """Clean evaluation (exit 0) maps to exit 0."""
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean doc", encoding="utf-8")

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    mock_proc = MagicMock(returncode=0, stdout="[]", stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        ret = run_hook(args=[str(doc)])
        assert ret == 0


def test_hook_exit_code_1_maps_to_2_with_stderr(tmp_path: Path, monkeypatch, capsys):
    """Content violation (exit 1) maps to exit 2 with violations on stderr for Claude."""
    doc = tmp_path / "violation.md"
    doc.write_text("# Leak\nDB_PASSWORD=secret", encoding="utf-8")

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    mock_json_out = json.dumps(
        [
            {
                "filename": doc.name,
                "violations": ["Credential Exposure: [SECRET_1] is exposed"],
            }
        ]
    )
    mock_proc = MagicMock(returncode=1, stdout=mock_json_out, stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        ret = run_hook(args=[str(doc)])
        assert ret == 2  # Must be 2 for Claude Code blocking hook

    captured = capsys.readouterr()
    assert "TypeSafe Safety Gate Failed" in captured.err
    assert "Credential Exposure: [SECRET_1] is exposed" in captured.err


def test_hook_missing_api_key_exits_0(tmp_path: Path, monkeypatch, capsys):
    """Missing TYPESAFE_API_KEY must exit 0 and NEVER exit 2."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Test", encoding="utf-8")

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    ret = run_hook(args=[str(doc)])
    assert ret == 0  # Graceful skip, never 2

    captured = capsys.readouterr()
    assert "TYPESAFE_API_KEY is not set" in captured.err


def test_hook_runtime_error_3_maps_to_0(tmp_path: Path, monkeypatch, capsys):
    """Runtime / tool error (exit 3 or 2) maps to exit 0 and NEVER exit 2."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Test", encoding="utf-8")

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    mock_proc = MagicMock(returncode=3, stdout="", stderr="API Connection Timeout")
    with patch("subprocess.run", return_value=mock_proc):
        ret = run_hook(args=[str(doc)])
        assert ret == 0  # Graceful skip, never 2

    captured = capsys.readouterr()
    assert "runtime error or tool error" in captured.err
