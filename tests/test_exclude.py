"""Tests for file exclusion patterns (--exclude), PresetConfig exclude, and default directory ignores."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from typesafe_eval.api import evaluate_documents
from typesafe_eval.cli import main
from typesafe_eval.models import PresetConfig
from typesafe_eval.presets import (
    DEFAULT_IGNORE_DIRS,
    is_default_ignored,
    is_path_excluded,
    load_project_config,
)

runner = CliRunner()


def test_default_ignore_dirs():
    """Verify standard dependency, build, and cache dirs are included in DEFAULT_IGNORE_DIRS."""
    expected = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".typesafe-eval-cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
    assert expected.issubset(DEFAULT_IGNORE_DIRS)


def test_is_default_ignored():
    """Verify is_default_ignored identifies paths containing default ignored directories."""
    assert is_default_ignored(Path("node_modules/package/README.md"))
    assert is_default_ignored(Path(".git/HEAD"))
    assert is_default_ignored(Path(".venv/lib/python3.10/site-packages/doc.md"))
    assert is_default_ignored(Path("src/__pycache__/module.cpython-310.pyc"))
    assert is_default_ignored(Path("build/docs/index.md"))
    assert is_default_ignored(Path("dist/package-0.1.0.tar.gz"))
    assert is_default_ignored(Path(".typesafe-eval-cache/ab/cd1234.json"))

    # Valid files must NOT be ignored
    assert not is_default_ignored(Path("docs/architecture.md"))
    assert not is_default_ignored(Path("README.md"))
    assert not is_default_ignored(Path("src/typesafe_eval/api.py"))


def test_is_path_excluded():
    """Verify path exclusion with various glob and directory patterns."""
    cwd = Path.cwd()

    # Pattern matching by filename
    assert is_path_excluded(cwd / "docs" / "guide.draft.md", ["*.draft.md"])
    assert not is_path_excluded(cwd / "docs" / "guide.final.md", ["*.draft.md"])

    # Directory patterns
    assert is_path_excluded(cwd / "templates" / "template.md", ["templates/**"])
    assert is_path_excluded(cwd / "templates" / "template.md", ["templates/*"])
    assert is_path_excluded(cwd / "templates" / "sub" / "template.md", ["templates/**"])
    assert is_path_excluded(cwd / "docs" / "templates" / "t1.md", ["docs/templates/*"])

    # No exclusions
    assert not is_path_excluded(cwd / "docs" / "api.md", [])
    assert not is_path_excluded(cwd / "docs" / "api.md", ["*.txt", "build/*"])


def test_cli_exclude_single_pattern(tmp_path: Path):
    """Test CLI --exclude filtering out matched files."""
    f1 = tmp_path / "valid.md"
    f1.write_text("# Valid Document\nClear content here.", encoding="utf-8")
    f2 = tmp_path / "wip.draft.md"
    f2.write_text("# Draft Document\nUnfinished text.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            str(tmp_path / "*.md"),
            "--exclude",
            "*.draft.md",
            "--offline",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "valid.md" in result.output
    assert "wip.draft.md" not in result.output


def test_cli_exclude_multiple_patterns(tmp_path: Path):
    """Test CLI repeatable -e / --exclude flags."""
    f1 = tmp_path / "keep.md"
    f1.write_text("# Keep This\nGood documentation.", encoding="utf-8")
    f2 = tmp_path / "skip1.tmp.md"
    f2.write_text("# Skip 1\nTemporary.", encoding="utf-8")
    f3 = tmp_path / "skip2.draft.md"
    f3.write_text("# Skip 2\nDraft.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            str(tmp_path / "*.md"),
            "-e",
            "*.tmp.md",
            "-e",
            "*.draft.md",
            "--offline",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "keep.md" in result.output
    assert "skip1.tmp.md" not in result.output
    assert "skip2.draft.md" not in result.output


def test_cli_exclude_all_exits_cleanly(tmp_path: Path):
    """When all files match exclude patterns, exit code should be 0 (empty result), not 2."""
    f = tmp_path / "only.draft.md"
    f.write_text("# Only Draft\nDraft notes.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            str(tmp_path / "*.md"),
            "--exclude",
            "*.draft.md",
            "--offline",
        ],
    )
    assert result.exit_code == 0
    assert "No files matched evaluation criteria" in result.output


def test_cli_default_ignore_during_glob(tmp_path: Path):
    """Glob evaluation should automatically skip default ignored directories."""
    valid_doc = tmp_path / "doc.md"
    valid_doc.write_text("# Project Doc\nValid content.", encoding="utf-8")

    node_modules_dir = tmp_path / "node_modules" / "pkg"
    node_modules_dir.mkdir(parents=True)
    ignored_doc = node_modules_dir / "readme.md"
    ignored_doc.write_text("# Package Readme\nThird-party.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            str(tmp_path / "**" / "*.md"),
            "--offline",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "doc.md" in result.output
    assert "readme.md" not in result.output


def test_cli_explicit_ignored_file_is_evaluated(tmp_path: Path):
    """If a user explicitly targets a file inside node_modules directly without glob, it should be evaluated."""
    pkg_dir = tmp_path / "node_modules" / "pkg"
    pkg_dir.mkdir(parents=True)
    target_doc = pkg_dir / "target.md"
    target_doc.write_text("# Specific Document\nExplicitly evaluated.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            str(target_doc),
            "--offline",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "target.md" in result.output


def test_preset_config_exclude_field(tmp_path: Path):
    """PresetConfig supports exclude field and loads from yaml configuration."""
    cfg_file = tmp_path / ".typesafe-eval.yaml"
    cfg_data = {
        "preset": "quality",
        "exclude": ["*.generated.md", "drafts/**"],
    }
    cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

    loaded_cfg, loaded_path = load_project_config(start_dir=tmp_path)
    assert isinstance(loaded_cfg, PresetConfig)
    assert loaded_path == cfg_file
    assert loaded_cfg.exclude == ["*.generated.md", "drafts/**"]


def test_cli_reads_config_exclude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """CLI automatically respects exclude patterns from discovered project config."""
    monkeypatch.chdir(tmp_path)

    cfg_file = tmp_path / ".typesafe-eval.yaml"
    cfg_data = {
        "preset": "quality",
        "exclude": ["*.skip.md"],
    }
    cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

    f1 = tmp_path / "doc.md"
    f1.write_text("# Real Doc\nReal content.", encoding="utf-8")
    f2 = tmp_path / "test.skip.md"
    f2.write_text("# Skip Doc\nSkip content.", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            "*.md",
            "--offline",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "doc.md" in result.output
    assert "test.skip.md" not in result.output


def test_api_evaluate_documents_exclude(tmp_path: Path):
    """evaluate_documents filters out excluded files and handles empty results."""
    f1 = tmp_path / "a.md"
    f1.write_text("# Doc A\nContent.", encoding="utf-8")
    f2 = tmp_path / "b.draft.md"
    f2.write_text("# Doc B\nDraft.", encoding="utf-8")

    results = evaluate_documents(
        [f1, f2],
        preset="quality",
        exclude=["*.draft.md"],
        offline=True,
    )
    assert len(results) == 1
    assert results[0].filename == "a.md"

    # All excluded
    results_empty = evaluate_documents(
        [f2],
        preset="quality",
        exclude=["*.draft.md"],
        offline=True,
    )
    assert results_empty == []
