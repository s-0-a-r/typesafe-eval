# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.0] - 2026-10-05

### Added
- **Public Python API** (`typesafe_eval`):
  - Top-level programmatic evaluation functions:
    - `evaluate(content: str, preset: str | PresetConfig = "quality", ...) -> DocumentEvalResult`
    - `evaluate_document(path: str | Path, preset: str | PresetConfig = "quality", ...) -> DocumentEvalResult`
    - `evaluate_documents(paths: Sequence[str | Path], preset: str | PresetConfig = "quality", concurrency: int = 4, ...) -> list[DocumentEvalResult]`
  - Re-exported core data models and configuration discovery utilities:
    - `DocumentEvalResult`, `ScoreResult`, `NoulResult`, `ChoiceResult`, `PresetConfig`, `QuestionConfig`
    - `load_preset`, `load_project_config`, `find_project_config`
  - High-performance connection pooling via shared `TypeSafeEvaluator` instance during batch evaluations.
- **Typed Exception Hierarchy** (`typesafe_eval.exceptions`):
  - `TypeSafeEvalError` (base exception)
  - `ConfigurationError` (subclass of `ValueError`)
  - `AuthenticationError` (subclass of `ValueError`)
  - `RuntimeEvalError` (subclass of `RuntimeError`)
  - `ContentViolationError` (with structured `result` and `results` attributes for batch failure handling)
- **Strict Typing & PEP 561**:
  - `py.typed` marker file included in `src/typesafe_eval/`.
  - Configured `[tool.mypy]` with `strict = true` across the entire codebase (0 errors across 12 source files).
- **Hypothesis Property-Based Testing** (`tests/test_properties.py`):
  - Invariant verification for text chunking coverage, chunk size limits, secret/PII token leakage prevention, and score bounds/monotonicity.
- **Configuration Auto-Discovery**:
  - Automatically searches parent directories for `.typesafe-eval.yaml`, `.typesafe-eval.yml`, or `pyproject.toml` (`[tool.typesafe-eval]`).
  - Supports preset extension (`extends: quality`) and per-question overrides.
- **JSON Schema Export**:
  - New CLI command `typesafe-eval schema` to export JSON Schema for IDE validation and auto-completion.
- **Parallel Document Concurrency**:
  - Concurrency flag `-j` / `--jobs` / `--concurrency` in CLI and `evaluate_documents()` API.
  - Thread-safe execution preserving deterministic document ordering in outputs.
- **Git Diff Evaluation**:
  - `--staged` flag to evaluate only staged git documents (pre-commit gating).
  - `--since <ref>` flag to evaluate documents modified relative to a branch or commit (CI gating).
- **Advisory Thresholds**:
  - Added `advisory: bool` flag to question configurations allowing non-blocking advisory observations without tripping Exit Code 1.
- **Adversarial Security Tests**:
  - Comprehensive adversarial PII & secret edge-case test suite (`tests/test_adversarial_sanitizer.py`).

### Changed
- Preserved original document filepaths in evaluation results for both CLI and API consumers.
- Improved error handling for unreadable or missing document files in batch processing.

---

## [0.7.0] - 2026-10-04

### Added
- Rich CLI terminal rendering with formatted progress and violation summaries.
- Real CLI acceptance test runner (`scripts/verify_ac.py`) covering 14 core acceptance criteria.
- Pre-commit hook graceful skipping when `TYPESAFE_API_KEY` is unset.
- Deterministic exit code precedence (Exit Code 1 over Exit Code 3).
- Scaffolding CLI command (`typesafe-eval init`).

---

## [0.6.0] - 2026-10-03

### Added
- Support for candidate-level Noul probability queries and calibration thresholds.
- Fine-grained PII and credential classifiers with zero-raw-leakage masking guarantees.

---

## [0.5.0] - 2026-10-02

### Added
- Agent-agnostic JSON output contract (`schema_version: "1.0"`).
- Pure `stdout` JSON stream separation for seamless integration with `jq`.
- Claude Code integration plugin with PostToolUse safety hooks.
- Comprehensive autonomous agent guidance documentation (`AGENTS.md`).
