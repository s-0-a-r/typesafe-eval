"""Unit tests for Issue #34: JSON contract, exit codes, pre-commit hook, and GitHub Action."""

import json
from pathlib import Path
import yaml
from click.testing import CliRunner
import pytest

from typesafe_eval.cli import main
from typesafe_eval.models import DocumentEvalResult, ScoreResult, NoulResult, ChoiceResult
from typesafe_eval.validator import ValidationReport


REPO_ROOT = Path(__file__).parent.parent


def test_schema_version_in_models():
    """DocumentEvalResult and ValidationReport must declare schema_version == '1.0'."""
    doc_res = DocumentEvalResult(
        filepath="doc.md",
        filename="doc.md",
        preset_name="safety",
    )
    dumped_doc = doc_res.model_dump()
    assert dumped_doc.get("schema_version") == "1.0"
    json_doc = json.loads(doc_res.model_dump_json())
    assert json_doc.get("schema_version") == "1.0"

    val_rep = ValidationReport(
        preset_name="safety",
        runs=1,
        summary={"total": 1},
    )
    dumped_val = val_rep.model_dump()
    assert dumped_val.get("schema_version") == "1.0"
    json_val = json.loads(val_rep.model_dump_json())
    assert json_val.get("schema_version") == "1.0"


def test_cli_eval_json_output_contract(tmp_path: Path):
    """CLI eval -f json outputs schema_version and key contract fields in stdout."""
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nPublic content here.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "-f", "json", "--dry-run"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 1
    doc_entry = data[0]

    # Contract guarantees
    assert doc_entry["schema_version"] == "1.0"
    assert "passed_thresholds" in doc_entry
    assert "violations" in doc_entry
    assert "warnings" in doc_entry
    assert "scores" in doc_entry
    assert "nouls" in doc_entry
    assert "choices" in doc_entry
    assert "email_evaluations" in doc_entry
    assert doc_entry["mock"] is True


def test_cli_validate_json_output_contract(tmp_path: Path):
    """CLI validate -f json outputs schema_version and key contract fields in stdout."""
    doc = tmp_path / "valid_doc.md"
    doc.write_text("# Documentation\nValid content.\n", encoding="utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_file.write_text(
        f"""preset: safety
documents:
  - path: {doc.name}
    expect:
      has_secrets: absent
      has_pii: absent
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "-f", "json", "--dry-run"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    assert data["schema_version"] == "1.0"
    assert "summary" in data
    assert "presence_results" in data
    assert "unplaced_warnings" in data
    assert data["mock"] is True


def test_cli_json_stream_purity_with_file_error(tmp_path: Path, monkeypatch):
    """Stdout remains a clean, valid JSON stream for jq while errors route to stderr (#36)."""
    good_doc = tmp_path / "good.md"
    good_doc.write_text("# Good Document\nValid content.", encoding="utf-8")
    bad_doc = tmp_path / "bad.md"
    bad_doc.write_text("# Bad Document\nWill fail during eval.", encoding="utf-8")

    from typesafe_eval.client import TypeSafeEvaluator

    orig_eval = TypeSafeEvaluator.evaluate_document

    def mock_eval(self, filepath=None, *args, **kwargs):
        if "bad.md" in str(filepath):
            raise RuntimeError("Synthetic evaluation failure on bad.md")
        return orig_eval(self, filepath=filepath, *args, **kwargs)

    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)

    runner = CliRunner()
    result = runner.invoke(main, [str(good_doc), str(bad_doc), "-f", "json", "--dry-run"])
    assert result.exit_code == 3

    # Stderr has the error message
    assert "Synthetic evaluation failure on bad.md" in (result.stderr or result.output)

    # Stdout MUST be valid JSON parsable by jq
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["filename"] == "good.md"
    assert parsed[0]["schema_version"] == "1.0"


def test_json_output_never_exposes_raw_secrets(tmp_path: Path):
    """Raw secrets must never appear in JSON output or feature metadata."""
    raw_secret = "AKIA1234567890ABCDEF"
    doc = tmp_path / "credentials.md"
    doc.write_text(f"# Sensitive\nAWS key: {raw_secret}\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "safety", "-f", "json", "--dry-run"])
    assert result.exit_code == 0

    stdout_text = result.stdout
    # Raw credential string MUST NOT appear anywhere in the JSON output stream
    assert raw_secret not in stdout_text

    data = json.loads(stdout_text)
    assert data[0]["schema_version"] == "1.0"
    assert data[0]["redactions_count"] >= 1


def test_pre_commit_hooks_yaml_structure():
    """Verify .pre-commit-hooks.yaml exists and matches contract specifications."""
    hook_file = REPO_ROOT / ".pre-commit-hooks.yaml"
    assert hook_file.is_file(), ".pre-commit-hooks.yaml must exist in repo root"

    with open(hook_file, "r", encoding="utf-8") as f:
        hooks = yaml.safe_load(f)

    assert isinstance(hooks, list)
    assert len(hooks) >= 1

    hook = next((h for h in hooks if h.get("id") == "typesafe-eval"), None)
    assert hook is not None, "Hook with id 'typesafe-eval' must be present"
    assert hook["name"] == "typesafe-eval"
    assert "TypeSafe System One" in hook["description"]
    assert hook["entry"] in ("typesafe-eval-hook", "typesafe-eval")
    assert hook["language"] == "python"
    assert hook["types"] == ["markdown"]
    assert hook["args"] == ["--preset", "safety"]
    assert hook["require_serial"] is True


def test_action_yml_structure():
    """Verify action.yml exists, is valid YAML, and handles exit codes 1 and 3."""
    action_file = REPO_ROOT / "action.yml"
    assert action_file.is_file(), "action.yml must exist in repo root"

    with open(action_file, "r", encoding="utf-8") as f:
        action = yaml.safe_load(f)

    assert isinstance(action, dict)
    assert "name" in action
    assert "description" in action

    # Inputs verification
    inputs = action.get("inputs", {})
    assert "api-key" in inputs
    assert inputs["api-key"].get("required") is False
    assert "preset" in inputs
    assert inputs["preset"].get("default") == "safety"
    assert "files" in inputs
    assert inputs["files"].get("default") == "**/*.md"

    # Runs composite verification
    runs = action.get("runs", {})
    assert runs.get("using") == "composite"
    steps = runs.get("steps", [])
    assert len(steps) >= 1

    # Check script contents for exit code handling (code 1 fails, code 3 skips)
    combined_scripts = "\n".join(s.get("run", "") for s in steps)
    assert "EXIT_CODE" in combined_scripts
    assert "exit 1" in combined_scripts
    # Exit code 3 skip behavior
    assert "exit 0" in combined_scripts
    assert "3" in combined_scripts
