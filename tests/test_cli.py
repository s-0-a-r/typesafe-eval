from click.testing import CliRunner
from typesafe_eval.cli import main

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.3.0" in result.output

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
    assert "TypeSafe Evaluation Report" in result.output
    assert "PASS" in result.output

def test_cli_json_format(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nThis is a sample document for evaluation.", encoding="utf-8")
    
    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run", "--format", "json"])
    assert result.exit_code == 0
    assert '"preset_name": "quality"' in result.output
    assert '"composite_score"' in result.output
