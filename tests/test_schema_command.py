import json

from click.testing import CliRunner

from typesafe_eval.cli import main


def test_schema_command_default_preset():
    runner = CliRunner()
    result = runner.invoke(main, ["schema"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["title"] == "TypeSafeEvalPresetConfig"
    assert "$defs" in data
    assert "QuestionConfig" in data["$defs"]
    assert "advisory" in data["$defs"]["QuestionConfig"]["properties"]


def test_schema_command_labels_type():
    runner = CliRunner()
    result = runner.invoke(main, ["schema", "--type", "labels"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["title"] == "TypeSafeEvalValidationLabels"
    assert "properties" in data
    assert "documents" in data["properties"]
    assert "pairs" in data["properties"]


def test_schema_command_output_file(tmp_path):
    out_file = tmp_path / "nested" / "sub" / "preset_schema.json"
    runner = CliRunner()
    result = runner.invoke(main, ["schema", "--out", str(out_file), "--indent", "4"])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data["title"] == "TypeSafeEvalPresetConfig"
    # Verify 4-space indent
    assert '    "title": "TypeSafeEvalPresetConfig"' in content
