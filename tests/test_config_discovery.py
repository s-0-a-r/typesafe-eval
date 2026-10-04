from pathlib import Path

import pytest
from click.testing import CliRunner

from typesafe_eval.cli import main
from typesafe_eval.presets import find_project_config, load_project_config


def test_find_project_config_yaml(tmp_path: Path):
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text("preset: safety\n", encoding="utf-8")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)

    found = find_project_config(start_dir=sub)
    assert found == cfg


def test_find_project_config_yml(tmp_path: Path):
    cfg = tmp_path / ".typesafe-eval.yml"
    cfg.write_text("preset: tech-spec\n", encoding="utf-8")

    found = find_project_config(start_dir=tmp_path)
    assert found == cfg


def test_find_project_config_pyproject(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\n[tool.typesafe-eval]\npreset = "safety"\n',
        encoding="utf-8",
    )

    found = find_project_config(start_dir=tmp_path)
    assert found == pyproject


def test_find_project_config_pyproject_without_tool_ignored(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\n', encoding="utf-8")

    found = find_project_config(start_dir=tmp_path)
    assert found is None


def test_find_project_config_stops_at_git(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    sub = root / "docs"
    sub.mkdir()

    # Place a config outside the repo root
    outside_cfg = tmp_path / ".typesafe-eval.yaml"
    outside_cfg.write_text("preset: safety\n", encoding="utf-8")

    found = find_project_config(start_dir=sub)
    # Should stop at repo/.git and not see outside_cfg
    assert found is None


def test_load_project_config_preset_reference(tmp_path: Path):
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text(
        "preset: safety\nthresholds_as_warnings: true\n",
        encoding="utf-8",
    )

    preset_cfg, path = load_project_config(start_dir=tmp_path)
    assert path == cfg
    assert preset_cfg is not None
    assert preset_cfg.name == "safety"
    assert preset_cfg.thresholds_as_warnings is True
    assert "has_secrets" in preset_cfg.questions


def test_load_project_config_pyproject(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.typesafe-eval]
preset = "tech-spec"
thresholds_as_warnings = true
""",
        encoding="utf-8",
    )

    preset_cfg, path = load_project_config(start_dir=tmp_path)
    assert path == pyproject
    assert preset_cfg is not None
    assert preset_cfg.name == "tech-spec"
    assert preset_cfg.thresholds_as_warnings is True


def test_load_project_config_custom_questions(tmp_path: Path):
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text(
        """
name: custom-eval
questions:
  is_clear:
    type: score
    instructions: Is this document clear?
""",
        encoding="utf-8",
    )

    preset_cfg, path = load_project_config(start_dir=tmp_path)
    assert path == cfg
    assert preset_cfg is not None
    assert preset_cfg.name == "custom-eval"
    assert "is_clear" in preset_cfg.questions


def test_load_project_config_invalid_yaml(tmp_path: Path):
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_project_config(start_dir=tmp_path)


def test_load_project_config_none(tmp_path: Path):
    cfg, path = load_project_config(start_dir=tmp_path)
    assert cfg is None
    assert path is None


def test_cli_auto_discovery(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text("preset: safety\n", encoding="utf-8")

    doc = tmp_path / "doc.md"
    doc.write_text("# Test\nContent here.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    assert '"preset_name": "safety"' in result.output


def test_cli_explicit_preset_overrides_discovery(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / ".typesafe-eval.yaml"
    cfg.write_text("preset: safety\n", encoding="utf-8")

    doc = tmp_path / "doc.md"
    doc.write_text("# Test\nContent here.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "tech-spec", "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    assert '"preset_name": "tech-spec"' in result.output
