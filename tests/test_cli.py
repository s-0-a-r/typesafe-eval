from click.testing import CliRunner
from typesafe_eval.cli import main

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.4.0" in result.output

def test_cli_list_presets():
    runner = CliRunner()
    result = runner.invoke(main, ["--list-presets"])
    assert result.exit_code == 0
    assert "quality" in result.output
    assert "safety" in result.output
    assert "tech-spec" in result.output

def test_cli_dry_run(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nThis is a sample document for evaluation.", encoding="utf-8")
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run"])
    assert result.exit_code == 0
    assert "TypeSafe Evaluation Report (MOCK)" in result.output
    assert "N/A" in result.output
    assert "PASS" not in result.output
    assert "FAIL" not in result.output

def test_cli_json_format(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nThis is a sample document for evaluation.", encoding="utf-8")
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run", "--format", "json"])
    assert result.exit_code == 0
    assert '"preset_name": "quality"' in result.output
    assert '"composite_score"' in result.output
    assert '"mock": true' in result.output


import json
from pathlib import Path
from typesafe_eval.models import DocumentEvalResult

def _make_mock_result(filepath: str, passed: bool = True, violations: list = None) -> DocumentEvalResult:
    p = Path(filepath)
    return DocumentEvalResult(
        filepath=filepath,
        filename=p.name,
        preset_name="quality",
        passed_thresholds=passed,
        violations=violations or ([] if passed else ["Minimum score threshold failed"]),
    )

def test_cli_exit_code_0_all_pass(tmp_path, monkeypatch):
    doc = tmp_path / "valid.md"
    doc.write_text("# Valid Document\nClean content.", encoding="utf-8")
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_mock_result(str(doc), passed=True),
    )
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality"])
    assert result.exit_code == 0
    assert "PASS" in result.output

def test_cli_exit_code_1_violations_only(tmp_path, monkeypatch):
    doc = tmp_path / "violating.md"
    doc.write_text("# Violating Document\nBad content.", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_mock_result(str(doc), passed=False, violations=["Score below min_threshold 0.7"]),
    )
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality"])
    assert result.exit_code == 1
    assert "Score below min_threshold 0.7" in result.output

def test_cli_exit_code_1_violation_and_error_mixed(tmp_path, monkeypatch):
    doc1 = tmp_path / "violating.md"
    doc1.write_text("# Violating Doc", encoding="utf-8")
    doc2 = tmp_path / "error.md"
    doc2.write_text("# Error Doc", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    def mock_eval(self, filepath, **kwargs):
        if "violating" in filepath:
            return _make_mock_result(filepath, passed=False, violations=["Critical quality violation"])
        raise RuntimeError("Connection reset by peer")
        
    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc1), str(doc2), "--preset", "quality"])
    # Precedence: violation (1) over error (3)
    assert result.exit_code == 1
    # Violating file's result is in the output
    assert "violating.md" in result.output
    assert "Critical quality violation" in result.output
    # Errored file is reported on stderr
    assert "error.md: Connection reset by peer" in (result.stderr or result.output)

def test_cli_exit_code_2_no_files():
    runner = CliRunner()
    # No arguments specified
    result = runner.invoke(main, [])
    assert result.exit_code == 2
    assert "No files or file patterns specified" in (result.stderr or result.output)
    
    # Pattern matching no files
    result_glob = runner.invoke(main, ["nonexistent_path_xyz_*.md"])
    assert result_glob.exit_code == 2
    assert "No valid files matched the pattern" in (result_glob.stderr or result_glob.output)

def test_cli_exit_code_2_preset_load_failure(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test", encoding="utf-8")
    runner = CliRunner()
    
    # Nonexistent preset
    result_preset = runner.invoke(main, [str(doc), "--preset", "nonexistent_preset"])
    assert result_preset.exit_code == 2
    assert "Error loading preset" in (result_preset.stderr or result_preset.output)
    
    # Nonexistent config file
    result_config = runner.invoke(main, [str(doc), "--config", str(tmp_path / "missing.yaml")])
    assert result_config.exit_code == 2

def test_cli_exit_code_3_errors_only(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API rate limit exceeded")),
    )
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality"])
    assert result.exit_code == 3
    assert f"{doc}: API rate limit exceeded" in (result.stderr or result.output)

def test_cli_exit_code_0_violations_with_no_fail_on_threshold(tmp_path, monkeypatch):
    doc = tmp_path / "violating.md"
    doc.write_text("# Violating", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: _make_mock_result(str(doc), passed=False, violations=["Threshold failed"]),
    )
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--no-fail-on-threshold"])
    assert result.exit_code == 0
    assert "FAIL" in result.output

def test_cli_exit_code_3_errors_with_no_fail_on_threshold(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    monkeypatch.setattr(
        TypeSafeEvaluator,
        "evaluate_document",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Network unreachable")),
    )
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--no-fail-on-threshold"])
    assert result.exit_code == 3
    assert f"{doc}: Network unreachable" in (result.stderr or result.output)

def test_cli_continue_on_file_error_json_format(tmp_path, monkeypatch):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc 1", encoding="utf-8")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Doc 2", encoding="utf-8")
    
    from typesafe_eval.client import TypeSafeEvaluator
    def mock_eval(self, filepath, **kwargs):
        if "doc1" in filepath:
            return _make_mock_result(filepath, passed=True)
        raise RuntimeError("Disk read error")
        
    monkeypatch.setattr(TypeSafeEvaluator, "evaluate_document", mock_eval)
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc1), str(doc2), "--format", "json"])
    assert result.exit_code == 3  # error occurred and no threshold violations
    
    # stdout contains json with only doc1
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["filename"] == "doc1.md"
    # stderr contains doc2 error
    assert f"{doc2}: Disk read error" in (result.stderr or result.output)


def test_cli_dry_run_file_read_error_exits_3(tmp_path):
    """S4: dry-run exits 3 when a file cannot be read (e.g. invalid UTF-8 bytes)."""
    bad_doc = tmp_path / "bad.md"
    bad_doc.write_bytes(b"\x80\x81\x82 invalid utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(bad_doc), "--dry-run"])
    assert result.exit_code == 3
    assert "codec can't decode byte" in (result.stderr or result.output)


def test_cli_max_chars_range(tmp_path):
    """--max-chars with 0 or negative values must fail usage validation (exit 2)."""
    doc = tmp_path / "test.md"
    doc.write_text("# Test document\nContent", encoding="utf-8")

    runner = CliRunner()
    for val in ["0", "-1", "-100"]:
        res = runner.invoke(main, [str(doc), "--max-chars", val])
        assert res.exit_code == 2
        assert "is not in the range" in (res.stderr or res.output)


def test_validate_dry_run_file_read_error_exits_3(tmp_path):
    """validate --dry-run exits 3 when a document cannot be read (e.g. invalid UTF-8 bytes)."""
    bad_doc = tmp_path / "bad.md"
    bad_doc.write_bytes(b"\x80\x81\x82 invalid utf-8")

    labels_file = tmp_path / "labels.yaml"
    labels_content = f"""preset: quality
documents:
  - path: {bad_doc.name}
    expect:
      clarity: present
"""
    labels_file.write_text(labels_content, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(labels_file), "--dry-run"])
    assert result.exit_code == 3


