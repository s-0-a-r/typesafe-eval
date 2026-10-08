"""High-level public Python API for typesafe-eval."""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ContentViolationError,
    RuntimeEvalError,
    TypeSafeEvalError,
)
from typesafe_eval.models import DocumentEvalResult, PresetConfig
from typesafe_eval.presets import is_path_excluded, load_preset, load_project_config


def _resolve_preset(
    preset: str | PresetConfig | None = "quality",
    project_root: str | Path | None = None,
) -> PresetConfig:
    """Resolves a preset string, PresetConfig, or project configuration."""
    if isinstance(preset, PresetConfig):
        return preset

    if preset is None or preset == "default":
        start_dir = Path(project_root) if project_root else None
        try:
            discovered_cfg, _ = load_project_config(start_dir=start_dir)
            if discovered_cfg is not None:
                return discovered_cfg
        except Exception as e:
            raise ConfigurationError(f"Error loading discovered project configuration: {e}") from e
        preset = "quality"

    try:
        return load_preset(preset)
    except Exception as e:
        raise ConfigurationError(f"Failed to load preset '{preset}': {e}") from e


def evaluate(
    content: str,
    preset: str | PresetConfig = "quality",
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    filename: str = "<memory>",
    filepath: str | Path | None = None,
    project_root: str | Path | None = None,
    evaluator: TypeSafeEvaluator | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> DocumentEvalResult:
    """Evaluates raw in-memory content against a specified preset."""
    if not isinstance(content, str):
        raise ConfigurationError(f"Expected str content, got {type(content).__name__}")

    preset_cfg = _resolve_preset(preset, project_root=project_root)

    resolved_api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not dry_run and not offline and not resolved_api_key:
        raise AuthenticationError(
            "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
            "or pass api_key=..."
        )

    resolved_filepath = str(filepath) if filepath is not None else filename
    active_evaluator = evaluator or TypeSafeEvaluator(
        api_key=resolved_api_key, enable_cache=cache, cache_dir=cache_dir
    )
    try:
        result = active_evaluator.evaluate_content(
            content=content,
            preset=preset_cfg,
            filename=filename,
            filepath=resolved_filepath,
            mask_secrets=mask_secrets,
            max_chars=max_chars,
            dry_run=dry_run,
            offline=offline,
            include_images=include_images,
            max_images_per_doc=max_images_per_doc,
        )
    except TypeSafeEvalError:
        raise
    except Exception as e:
        raise RuntimeEvalError(f"Evaluation failed: {e}") from e

    if raise_on_violation and not result.passed_thresholds:
        raise ContentViolationError(
            f"Content violation in '{filename}': {'; '.join(result.violations)}",
            violations=result.violations,
            result=result,
            results=[result],
        )

    return result


def evaluate_document(
    path: str | Path,
    preset: str | PresetConfig = "quality",
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    project_root: str | Path | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> DocumentEvalResult:
    """Evaluates a single document file from disk against a specified preset."""
    doc_path = Path(path)
    if not doc_path.is_file():
        raise ConfigurationError(f"Document file not found: {path}")

    try:
        content = doc_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ConfigurationError(f"Failed to read file '{path}': {e}") from e

    return evaluate(
        content=content,
        preset=preset,
        api_key=api_key,
        dry_run=dry_run,
        offline=offline,
        cache=cache,
        cache_dir=cache_dir,
        mask_secrets=mask_secrets,
        max_chars=max_chars,
        raise_on_violation=raise_on_violation,
        filename=doc_path.name,
        filepath=str(doc_path),
        project_root=project_root or doc_path.parent,
        include_images=include_images,
        max_images_per_doc=max_images_per_doc,
    )


def evaluate_documents(
    paths: Sequence[str | Path],
    preset: str | PresetConfig = "quality",
    *,
    exclude: Sequence[str] | None = None,
    concurrency: int = 4,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    project_root: str | Path | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> list[DocumentEvalResult]:
    """Evaluates multiple document files concurrently preserving input order."""
    if not paths:
        return []

    preset_cfg = _resolve_preset(preset, project_root=project_root)

    resolved_api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not dry_run and not offline and not resolved_api_key:
        raise AuthenticationError(
            "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
            "or pass api_key=..."
        )

    # Combine exclusion patterns from argument and preset configuration
    combined_excludes = list(exclude or []) + (preset_cfg.exclude or [])
    root = Path(project_root) if project_root else Path.cwd()

    # Validate all file paths upfront (skipping excluded)
    resolved_paths: list[Path] = []
    for p in paths:
        doc_path = Path(p)
        if combined_excludes and is_path_excluded(doc_path, combined_excludes, root=root):
            continue
        if not doc_path.is_file():
            raise ConfigurationError(f"Document file not found: {p}")
        resolved_paths.append(doc_path)

    if not resolved_paths:
        return []

    # Shared evaluator for connection pooling across threads
    shared_evaluator = TypeSafeEvaluator(
        api_key=resolved_api_key, enable_cache=cache, cache_dir=cache_dir
    )

    def _eval_single(doc_p: Path) -> DocumentEvalResult:
        try:
            content = doc_p.read_text(encoding="utf-8")
        except Exception as e:
            raise ConfigurationError(f"Failed to read file '{doc_p}': {e}") from e

        return evaluate(
            content=content,
            preset=preset_cfg,
            api_key=resolved_api_key,
            dry_run=dry_run,
            offline=offline,
            cache=cache,
            cache_dir=cache_dir,
            mask_secrets=mask_secrets,
            max_chars=max_chars,
            raise_on_violation=False,
            filename=doc_p.name,
            filepath=str(doc_p),
            project_root=project_root or doc_p.parent,
            evaluator=shared_evaluator,
            include_images=include_images,
            max_images_per_doc=max_images_per_doc,
        )

    concurrency = max(1, concurrency)
    if concurrency == 1 or len(resolved_paths) == 1:
        results = [_eval_single(p) for p in resolved_paths]
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(resolved_paths))) as executor:
            results = list(executor.map(_eval_single, resolved_paths))

    if raise_on_violation:
        violated = [r for r in results if not r.passed_thresholds]
        if violated:
            all_violations = [v for r in violated for v in r.violations]
            raise ContentViolationError(
                f"{len(violated)} document(s) failed gates: {'; '.join(all_violations)}",
                violations=all_violations,
                result=violated[0] if len(violated) == 1 else None,
                results=violated,
            )

    return results


__all__ = [
    "evaluate",
    "evaluate_document",
    "evaluate_documents",
]
