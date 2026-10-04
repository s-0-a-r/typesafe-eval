"""Tests for high-level public Python API in typesafe_eval."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import typesafe_eval
from typesafe_eval import (
    AuthenticationError,
    ConfigurationError,
    ContentViolationError,
    DocumentEvalResult,
    PresetConfig,
    QuestionConfig,
    RuntimeEvalError,
    TypeSafeEvalError,
    TypeSafeEvaluator,
    evaluate,
    evaluate_document,
    evaluate_documents,
)


def test_public_api_symbols_exported() -> None:
    """Verify that all core public API symbols are directly exported from top-level package."""
    assert hasattr(typesafe_eval, "evaluate")
    assert hasattr(typesafe_eval, "evaluate_document")
    assert hasattr(typesafe_eval, "evaluate_documents")
    assert hasattr(typesafe_eval, "DocumentEvalResult")
    assert hasattr(typesafe_eval, "PresetConfig")
    assert hasattr(typesafe_eval, "QuestionConfig")
    assert hasattr(typesafe_eval, "load_preset")
    assert hasattr(typesafe_eval, "load_project_config")
    assert hasattr(typesafe_eval, "find_project_config")
    assert hasattr(typesafe_eval, "TypeSafeEvalError")
    assert hasattr(typesafe_eval, "ConfigurationError")
    assert hasattr(typesafe_eval, "AuthenticationError")
    assert hasattr(typesafe_eval, "RuntimeEvalError")
    assert hasattr(typesafe_eval, "ContentViolationError")
    assert hasattr(typesafe_eval, "TypeSafeEvaluator")
    assert hasattr(typesafe_eval, "ScoreResult")
    assert hasattr(typesafe_eval, "NoulResult")
    assert hasattr(typesafe_eval, "ChoiceResult")
    assert hasattr(typesafe_eval, "__version__")


def test_exception_hierarchy() -> None:
    """Verify typed exception inheritance hierarchy."""
    assert issubclass(ConfigurationError, TypeSafeEvalError)
    assert issubclass(ConfigurationError, ValueError)
    assert issubclass(AuthenticationError, TypeSafeEvalError)
    assert issubclass(AuthenticationError, ValueError)
    assert issubclass(RuntimeEvalError, TypeSafeEvalError)
    assert issubclass(RuntimeEvalError, RuntimeError)
    assert issubclass(ContentViolationError, TypeSafeEvalError)


def test_evaluate_in_memory_dry_run() -> None:
    """Verify evaluate() works with in-memory string under dry_run."""
    content = "# Architecture\n\nThis is a clean technical specification for an API."
    res = evaluate(content, preset="quality", dry_run=True)

    assert isinstance(res, DocumentEvalResult)
    assert res.filename == "<memory>"
    assert res.mock is True
    assert res.passed_thresholds is True
    assert res.composite_score is not None
    assert 0.0 <= res.composite_score <= 1.0


def test_evaluate_custom_filename() -> None:
    """Verify evaluate() respects custom filename argument."""
    content = "# Auth Service\n\nToken-based authentication RFC."
    res = evaluate(content, preset="tech-spec", filename="auth_rfc.md", dry_run=True)

    assert res.filename == "auth_rfc.md"
    assert res.filepath == "auth_rfc.md"


def test_evaluate_custom_preset_config() -> None:
    """Verify evaluate() accepts a PresetConfig instance directly."""
    custom_preset = PresetConfig(
        name="custom_eval",
        title="Custom Evaluation",
        questions={
            "clarity": QuestionConfig(
                type="score",
                instructions="Assess clarity",
                criteria=["Poor", "Good", "Excellent"],
                weight=1.0,
                min_threshold=0.5,
            )
        },
    )
    content = "Sample content to evaluate."
    res = evaluate(content, preset=custom_preset, dry_run=True)

    assert res.preset_name == "custom_eval"
    assert "clarity" in res.scores


def test_evaluate_missing_api_key_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify evaluate() raises AuthenticationError when not dry_run and no API key available."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(AuthenticationError, match="No TypeSafe API key provided"):
        evaluate("Content to evaluate", preset="quality", api_key=None, dry_run=False)


def test_evaluate_invalid_content_type() -> None:
    """Verify evaluate() raises ConfigurationError when content is not str."""
    with pytest.raises(ConfigurationError, match="Expected str content"):
        evaluate(12345, preset="quality", dry_run=True)  # type: ignore[arg-type]


def test_evaluate_unknown_preset_raises_config_error() -> None:
    """Verify evaluate() raises ConfigurationError when preset cannot be resolved."""
    with pytest.raises(ConfigurationError, match="Failed to load preset"):
        evaluate("Content", preset="non_existent_preset_xyz", dry_run=True)


def test_evaluate_document_file_not_found() -> None:
    """Verify evaluate_document() raises ConfigurationError if file does not exist."""
    with pytest.raises(ConfigurationError, match="Document file not found"):
        evaluate_document("/non/existent/path/doc.md", preset="quality", dry_run=True)


def test_evaluate_document_dry_run(tmp_path: Path) -> None:
    """Verify evaluate_document() reads and evaluates file from disk."""
    doc_file = tmp_path / "spec.md"
    doc_file.write_text("# Design Spec\n\nHigh-performance document processor.", encoding="utf-8")

    res = evaluate_document(doc_file, preset="quality", dry_run=True)

    assert isinstance(res, DocumentEvalResult)
    assert res.filename == "spec.md"
    assert res.filepath == str(doc_file)
    assert res.mock is True


def test_evaluate_raise_on_violation() -> None:
    """Verify raise_on_violation=True raises ContentViolationError when thresholds fail."""
    content = "Sensitive content"
    failed_result = DocumentEvalResult(
        filepath="doc.md",
        filename="doc.md",
        preset_name="quality",
        passed_thresholds=False,
        violations=["Readability score 0.40 is below required minimum 0.70"],
    )

    with patch.object(TypeSafeEvaluator, "evaluate_content", return_value=failed_result):
        with pytest.raises(ContentViolationError) as exc_info:
            evaluate(content, preset="quality", api_key="dummy_key", raise_on_violation=True)

        err = exc_info.value
        assert len(err.violations) == 1
        assert "Readability score 0.40" in err.violations[0]
        assert err.result is not None
        assert err.result.passed_thresholds is False
        assert len(err.results) == 1
        assert err.results[0] is err.result

        # When raise_on_violation=False (default), returns the result without raising
        res = evaluate(content, preset="quality", api_key="dummy_key", raise_on_violation=False)
        assert res.passed_thresholds is False
        assert len(res.violations) == 1


def test_evaluate_documents_raise_on_violation(tmp_path: Path) -> None:
    """Verify evaluate_documents raises ContentViolationError when raise_on_violation=True."""
    p1 = tmp_path / "doc1.md"
    p1.write_text("Doc 1", encoding="utf-8")
    p2 = tmp_path / "doc2.md"
    p2.write_text("Doc 2", encoding="utf-8")

    failed_result = DocumentEvalResult(
        filepath=str(p2),
        filename=p2.name,
        preset_name="quality",
        passed_thresholds=False,
        violations=["PII exposure detected"],
    )

    with patch.object(TypeSafeEvaluator, "evaluate_content", return_value=failed_result):
        with pytest.raises(ContentViolationError) as exc_info:
            evaluate_documents(
                [p1, p2], preset="quality", api_key="dummy_key", raise_on_violation=True
            )

        assert len(exc_info.value.violations) > 0
        assert "PII exposure detected" in exc_info.value.violations[0]
        assert len(exc_info.value.results) == 2  # mocked return_value is returned for both docs


def test_evaluate_documents_concurrency(tmp_path: Path) -> None:
    """Verify evaluate_documents() runs concurrently preserving document order."""
    doc_paths: list[Path] = []
    for i in range(5):
        p = tmp_path / f"doc_{i}.md"
        p.write_text(f"# Doc {i}\n\nContent for document {i}.", encoding="utf-8")
        doc_paths.append(p)

    results = evaluate_documents(doc_paths, preset="quality", concurrency=3, dry_run=True)

    assert len(results) == 5
    for i, res in enumerate(results):
        assert res.filename == f"doc_{i}.md"
        assert res.mock is True


def test_evaluate_documents_empty_list() -> None:
    """Verify evaluate_documents() returns empty list when paths is empty."""
    results = evaluate_documents([], preset="quality", dry_run=True)
    assert results == []


def test_evaluate_documents_file_not_found(tmp_path: Path) -> None:
    """Verify evaluate_documents() raises ConfigurationError upfront if any file is missing."""
    p1 = tmp_path / "exists.md"
    p1.write_text("Hello", encoding="utf-8")
    p2 = tmp_path / "missing.md"

    with pytest.raises(ConfigurationError, match="Document file not found"):
        evaluate_documents([p1, p2], preset="quality", dry_run=True)


def test_evaluate_runtime_error_wrapped() -> None:
    """Verify unexpected evaluator errors are wrapped in RuntimeEvalError."""
    with patch.object(
        TypeSafeEvaluator, "evaluate_content", side_effect=Exception("API connection timeout")
    ):
        with pytest.raises(RuntimeEvalError, match="Evaluation failed: API connection timeout"):
            evaluate("Content", preset="quality", api_key="dummy_key", dry_run=False)
