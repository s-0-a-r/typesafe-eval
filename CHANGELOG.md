# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-06

### Added
- **Official Documentation Site (Material for MkDocs)**:
  - Comprehensive documentation portal hosted at GitHub Pages with responsive Material design, dark/light theme, search, and code copying.
  - Complete guides: Installation, Quickstart, CLI Reference, Python API & Types, CI Integrations (GitHub Actions, pre-commit, Claude Code), Presets, and Scientific Noise Calibration.
  - Strict documentation build validation (`mkdocs build --strict`) integrated into CI.
- **Empirical Noise Calibration Matrix & Fixture Report**:
  - Live empirical evaluation of run-to-run variance on TypeSafe System One (`jev-1.13.0`) across all 5 built-in presets (60 evaluations, 396 pairwise comparisons).
  - Confirmed 99th percentile $|\Delta| = 0.030$ and max $|\Delta| = 0.040$, validating the statistical robustness of the $\pm 0.10$ threshold safety margin.
  - Automated reusable measurement CLI script (`scripts/measure_noise.py`) and artifact export (`tests/fixtures/noise_report.json`).
- **Comprehensive Production Hardening & Acceptance**:
  - 100% pass across all 18 Real CLI Acceptance Criteria (OS subprocess execution matrix).
  - 533 unit, integration, and property-based tests passing with strict typing (PEP 561 `py.typed`, mypy strict mode).
  - Cleaned up README.md with unified feature catalog and removed temporary release sections.

---

## [0.9.0] - 2026-10-06

### Added
- **File Exclusion Patterns & Default Ignores (`--exclude` / `-e`)**:
  - Repeatable `--exclude <pattern>` / `-e <pattern>` CLI flags supporting fnmatch / glob patterns.
  - Project configuration support via `exclude: [...]` in `.typesafe-eval.yaml` and `pyproject.toml` (`[tool.typesafe-eval]`).
  - Automatic filtering of standard build, dependency, and cache directories (`.git`, `node_modules`, `.venv`, `build`, `dist`, etc.) during glob resolution and git diff filtering.
  - Programmatic support via `evaluate_documents(paths, exclude=[...])`.
- **Offline Rules-Only Mode (`--offline` / `--rules-only`)**:
  - Pure local evaluation relying on deterministic rules (known credential patterns, AWS/Slack/GitHub tokens, free-mail PII) with zero network calls and no required `TYPESAFE_API_KEY`.
  - Ambiguous candidate fallback behavior producing soft informational notices instead of runtime errors.
  - Programmatic support via `evaluate(content, offline=True)` and `evaluate_documents(paths, offline=True)`.
- **Content-Addressable Result Caching (`--cache` / `--no-cache`)**:
  - Deterministic SHA-256 caching of evaluation results based on content, preset rules, model parameters, and options.
  - Configurable cache location via `--cache-dir` or `TYPESAFE_CACHE_DIR` (default: `.typesafe-eval-cache`).
  - Cache management CLI command: `typesafe-eval cache clear`.
  - Programmatic support via `evaluate_documents(paths, cache=True, cache_dir=...)`.
- **Line & Column Mapping & GitHub Actions Annotations (`-f github`)**:
  - Exact line and 1-indexed column position tracking for PII, secrets, and structural headings (`Position`, `ViolationItem.line`, `ViolationItem.col`).
  - Native GitHub Actions workflow commands emitted to `stdout` (`::error file=...,line=...,col=...::...` and `::warning file=...,line=...,col=...::...`).
- **Expanded 18-Item Real CLI Acceptance Criteria (AC) Matrix**:
  - Full end-to-end OS subprocess execution testing all 18 criteria (`scripts/verify_ac.py` and `pytest -v -m acceptance`).
  - Coverage expanded for offline mode (AC 15), result cache (AC 16), GitHub Actions annotations (AC 17), and file exclusions (AC 18).

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
