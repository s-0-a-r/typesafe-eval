"""Tests for evaluation result caching (Issue #112)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from typesafe_eval.cache import EvaluationCache
from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.models import DocumentEvalResult, ScoreResult
from typesafe_eval.presets import load_preset


def test_cache_compute_key_deterministic():
    cache = EvaluationCache()
    preset = load_preset("quality")
    content = "Hello world document"

    key1 = cache.compute_key(content, preset)
    key2 = cache.compute_key(content, preset)

    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex string


def test_cache_compute_key_sensitive_to_changes():
    cache = EvaluationCache()
    preset1 = load_preset("quality")
    preset2 = load_preset("safety")
    content1 = "Hello world"
    content2 = "Hello world 2"

    key_orig = cache.compute_key(content1, preset1)
    key_diff_content = cache.compute_key(content2, preset1)
    key_diff_preset = cache.compute_key(content1, preset2)

    assert key_orig != key_diff_content
    assert key_orig != key_diff_preset


def test_cache_get_set_roundtrip(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path)
    preset = load_preset("quality")
    content = "# Architectural Overview\nEverything is properly designed."

    # Cache miss
    assert cache.get(content, preset) is None

    result = DocumentEvalResult(
        filepath="/original/path/doc.md",
        filename="doc.md",
        preset_name="quality",
        composite_score=0.92,
        passed_thresholds=True,
        scores={
            "clarity": ScoreResult(
                score=2,
                max_score=2,
                normalized_score=1.0,
                confidence=0.95,
                probabilities={"2": 0.95},
            )
        },
        api_calls=2,
    )

    # Cache set
    cache.set(content, preset, result)

    # Cache hit
    cached = cache.get(content, preset)
    assert cached is not None
    assert cached.cached is True
    assert cached.api_calls == 0
    assert cached.composite_score == 0.92
    assert cached.passed_thresholds is True
    assert "clarity" in cached.scores
    assert cached.scores["clarity"].normalized_score == 1.0

    # Ensure disk storage is pristine (cached=False)
    key = cache.compute_key(content, preset)
    raw_disk_json = json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))
    assert raw_disk_json["cached"] is False


def test_cache_disabled_behavior(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path, enabled=False)
    preset = load_preset("quality")
    content = "Sample doc"

    result = DocumentEvalResult(
        filepath="sample.md",
        filename="sample.md",
        preset_name="quality",
    )

    cache.set(content, preset, result)
    assert not (tmp_path / f"{cache.compute_key(content, preset)}.json").exists()
    assert cache.get(content, preset) is None


def test_cache_corrupted_file_handling(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path)
    preset = load_preset("quality")
    content = "Some document"

    key = cache.compute_key(content, preset)
    corrupted_file = tmp_path / f"{key}.json"
    corrupted_file.write_text("invalid json content {{{", encoding="utf-8")

    # Should safely recover, remove corrupted file, and return None
    assert cache.get(content, preset) is None
    assert not corrupted_file.exists()


def test_cache_clear(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path)
    preset = load_preset("quality")

    res = DocumentEvalResult(filepath="a.md", filename="a.md", preset_name="quality")
    cache.set("doc 1", preset, res)
    cache.set("doc 2", preset, res)

    assert len(list(tmp_path.glob("*.json"))) == 2
    cleared = cache.clear()
    assert cleared == 2
    assert len(list(tmp_path.glob("*.json"))) == 0


def test_evaluator_uses_cache(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path)
    evaluator = TypeSafeEvaluator(api_key="test_key", cache=cache)

    mock_client = MagicMock()
    evaluator._client = mock_client

    preset = load_preset("quality")
    content = "Valid document for testing cache hit"

    # Pre-populate cache
    cached_entry = DocumentEvalResult(
        filepath="cached_doc.md",
        filename="cached_doc.md",
        preset_name="quality",
        composite_score=0.88,
        passed_thresholds=True,
    )
    cache.set(content, preset, cached_entry)

    # Evaluate content: should return from cache without calling mock_client
    res = evaluator.evaluate_content(
        content=content,
        preset=preset,
        filepath="/custom/path/new_name.md",
        filename="new_name.md",
    )

    assert res.cached is True
    assert res.api_calls == 0
    assert res.filepath == "/custom/path/new_name.md"
    assert res.filename == "new_name.md"
    assert mock_client.system_one.call_count == 0


def test_cli_cache_clear(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path)
    preset = load_preset("quality")
    res = DocumentEvalResult(filepath="test.md", filename="test.md", preset_name="quality")
    cache.set("cli test", preset, res)
    assert len(list(tmp_path.glob("*.json"))) == 1

    runner = CliRunner()
    result = runner.invoke(main, ["cache", "clear", "--cache-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Cleared 1 cached evaluation result(s)." in result.output
    assert len(list(tmp_path.glob("*.json"))) == 0


def test_cli_no_cache_flag(tmp_path: Path):
    test_file = tmp_path / "test.md"
    test_file.write_text("# Clean document\nNo secrets here.", encoding="utf-8")
    cache_dir = tmp_path / "cache_dir"

    runner = CliRunner()
    # Evaluate with --dry-run and --no-cache
    result = runner.invoke(
        main,
        [
            str(test_file),
            "--dry-run",
            "--no-cache",
            "--cache-dir",
            str(cache_dir),
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    # Cache directory should not contain cached json files
    assert not list(cache_dir.glob("*.json"))
