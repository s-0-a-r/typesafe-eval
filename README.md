# typesafe-eval

[![CI](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://s-0-a-r.github.io/typesafe-eval/)
[![Release](https://img.shields.io/github/v/release/s-0-a-r/typesafe-eval)](https://github.com/s-0-a-r/typesafe-eval/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Fast, typed, multi-dimensional document evaluation CLI and CI quality gate powered by the **OpenAI Decisions API** (`gpt-6-luna`) and **TypeSafe System One API** (`jev-1.13.0`).

> 📖 **Online Documentation**: [https://s-0-a-r.github.io/typesafe-eval/](https://s-0-a-r.github.io/typesafe-eval/)

---

## ⚖️ Empirical Reliability & Decision Boundaries

Unlike typical LLM document evaluation tools that produce uncalibrated scores, `typesafe-eval` separates **tuning** from **held-out** corpora, pre-registers evaluation rounds and pass criteria ([PREREGISTRATION.md](validation/corpus/PREREGISTRATION.md)), and explicitly documents where evaluation succeeds and where it fails.

### Built-in Presets & Calibration Status

| Preset | Target Scope | Primary Checks | Empirical Reliability Status |
| :--- | :--- | :--- | :--- |
| `safety` | Secret & PII Gating | Credentials, personal emails (free-mail vs. role), phone numbers, private IPs, sensitive URLs | **Deterministic Offline Rules**: Zero API calls required. Differentiates Japanese mobile numbers (`090`/`080`/`070`) from toll-free lines (`0120`/`0570`) and corporate switchboards (`03` + 代表), and permits Japanese department roles (`jinji@`, `keiri@`, `somu@`, etc.) while catching personal free-mail (`yahoo.co.jp`, `gmail.com`). |
| `tech-spec` | RFCs & Specifications | Verification plan (`has_test_plan`), engineering readiness (`readiness`) | **Selective (Small Sample N=3)**: Flags 3 of 3 absent specs on corpus. TypeSafe (`jev-1.13.0`) confirmed; OpenAI (`gpt-6-luna`) adjusted post-hoc on `swift-se-0510` (see Accuracy Benchmarks). `readiness` is an unmeasured categorical choice. |
| `design-doc` | System Architecture | Section presence checklist (goals, alternatives, rollbacks, failure modes) | **Selective (Small Sample N=2–3)**: `alternatives`, `rollback`, and `open_questions` are reliable on corpus. `goal` and `owner_timeline` are one-way only. **Not reliable**: `non_goals`, `risks`, `migration`, `metrics`. |
| `quality` | Structural Regression | Clarity score (`clarity`), stylistic tone (`tone`) | **Limited**: Suited for `--baseline` detecting major degradation (text corruption, sentence shuffling). **Cannot differentiate real human review revisions from original drafts** ($\Delta = +0.013$ against between-document $\sigma = 0.116$). Absolute scores cannot be compared across different documents. |
| `pr-description` | Pull Request Summaries | PR checklist (summary, testing strategy, impact, breaking changes) | **Selective**: `testing` is reliable on corpus ($N=2$). `summary`, `impact`, `breaking_changes`, and `related_issues` are advisory / not reliable. |

> 📊 **Accuracy Tables & Regex Comparison**: See [Multi-Provider Empirical Accuracy](docs/science/accuracy-benchmarks.md) for exact precision/recall counts and a side-by-side comparison with simple keyword regex (`baseline_heuristic.py`).

---

## 🎯 Recommended Practical Scenarios (When to Use)

Focus your CI/CD gates strictly on the empirically verified capabilities:

### 1. Pre-Commit Gate for Document Leak Prevention (Immediate Value)
Run deterministic, offline safety gating without needing an API key:
```bash
# In pre-commit hooks or local gating: zero network calls, instant execution
typesafe-eval --staged --preset safety --offline
```
- **Catches**: AWS/GitHub/Slack credentials, free-mail personal addresses (`@gmail.com`, `@yahoo.co.jp`), private IPs, and personal mobile numbers.
- **Passes**: Toll-free support numbers (`0120`, `0570`, `1-800`), switchboard desks with context (`03` + 代表), and corporate department roles (`jinji@`, `ops@`, `support@`).

### 2. Architecture & Design Doc CI Checklist
Automate structural sanity checks on architecture proposals:
```bash
# Gate pull requests touching technical designs
typesafe-eval docs/design/*.md --preset design-doc -f github
```
- **Enforce as Hard Blockers**: `alternatives`, `rollback`, and `open_questions` (verified detection on corpus). Note: on documents with canonical headers, keyword regex achieves similar recall; the LLM adds value primarily on non-standard headings.
- **Treat as Advisory**: Flag missing `risks`, `metrics`, or `migration` for human reviewer attention, but avoid hard-failing builds on them.

### 3. Engineering RFC Test Plan Enforcement
Ensure technical specifications include a verifiable testing strategy:
```bash
typesafe-eval rfc/*.md --preset tech-spec
```
- Reliably detects missing test/verification plans (flagged 3 of 3 absent specs on corpus). Note: on specifications with standard markdown headings, a simple keyword regex matches LLM detection at zero cost; the LLM provides value primarily when testing strategies are described in freeform prose.

### 4. Regression Detection Between Document Revisions
Detect structural degradation between document versions without comparing absolute numbers:
```bash
# Save baseline from main branch, then evaluate feature branch
typesafe-eval docs/*.md --preset quality --baseline baseline.json
```
- Flags significant score drops larger than the empirical measurement noise.

### 🚫 Anti-Patterns (When NOT to Use)
- **Do NOT gate PR merges on unverified checklist items** (e.g. `pr-description: summary`, `design-doc: risks`).
- **Do NOT use single composite scores as an absolute quality pass/fail gate** across diverse documents.
- **Do NOT run autonomous agents in score-maximizing rewrite loops** (capped at 2 rounds maximum; Goodhart's law degrades natural writing when optimizing solely for numeric metrics).

---

## ⚡ Quick Command Invocations

```bash
# Run safety check with deterministic offline rules (zero API calls)
typesafe-eval docs/*.md --preset safety --offline

# Evaluate technical RFC with OpenAI Decisions API (gpt-6-luna)
typesafe-eval rfc/*.md --preset tech-spec --provider openai

# Evaluate only git staged documents (pre-commit gating)
typesafe-eval --staged --preset safety

# Evaluate modified documents since a git commit or branch
typesafe-eval --since origin/main --preset tech-spec

# Multimodal evaluation: analyze markdown diagrams alongside prose
typesafe-eval rfc/*.md --preset tech-spec --provider openai --include-images

# Enable content-addressable result caching for fast iterative runs
typesafe-eval docs/*.md --preset quality --cache

# Output pure JSON stream for jq or automated pipeline integration
typesafe-eval docs/*.md --preset quality -f json | jq '.[] | select(.passed_thresholds == false)'

# GitHub Actions workflow annotations for inline PR diff markers
typesafe-eval docs/*.md --preset safety -f github

# Dry-run validation (validates files and presets without external API calls)
typesafe-eval docs/*.md --dry-run
```

---

## 🔌 Multi-Provider Architecture & Configuration

`typesafe-eval` provides a unified type-safe interface across decision engines:

| Decision Gate | Schema Type | OpenAI Decisions API (`POST /v1/decisions`) | TypeSafe System One (Jev) | `typesafe-eval` Result |
| :--- | :--- | :--- | :--- | :--- |
| **Boolean Probability** | True/False $p \in [0, 1]$ | `predicate` | `Noul` | `NoulResult` (Threshold & Near-Threshold) |
| **Ordered Rubric** | Multi-level criteria | `score` | `Score` | `ScoreResult` (Normalized score) |
| **Categorical Choice** | Mutually exclusive | `choice` | `Choice` | `ChoiceResult` (Selected option & distribution) |

### Provider Resolution & Authentication

By default (`--provider auto`), `typesafe-eval` selects the provider based on your environment:
1. If `OPENAI_API_KEY` is set: uses **OpenAI Decisions API** (`gpt-6-luna`).
2. If `TYPESAFE_API_KEY` is set: uses **TypeSafe System One** (`jev-1.13.0`).

```bash
# Authentication via environment variables
export OPENAI_API_KEY="sk-..."
export TYPESAFE_API_KEY="your_typesafe_key"
```

### Project Configuration (`.typesafe-eval.yaml` & `pyproject.toml`)

Configure project defaults in `.typesafe-eval.yaml`:

```yaml
preset: tech-spec
provider: openai
model: gpt-6-luna
```

Or in `pyproject.toml`:

```toml
[tool.typesafe-eval]
preset = "tech-spec"
provider = "openai"
model = "gpt-6-luna"
```

---

## 🛠 Core Capabilities

- **Pre-Flight Candidate Masking & Zero Raw Leakage**: Credentials, emails, and phone numbers are redacted into safe placeholders (`[SECRET_1]`, `[EMAIL_1]`) *before* transmission. Raw values never enter prompt payloads or result logs.
- **Offline Rules-Only Mode (`--offline`)**: Gating runs 100% locally using regex rules and structural heuristic feature extractors without requiring network or API keys.
- **Multimodal Evaluation (`--include-images`)**: Evaluates embedded Markdown/HTML diagrams and architecture charts alongside prose via OpenAI Decisions API (`gpt-6-luna`).
- **Long Document Chunking**: Automatically segments long documents with overlapping token windows for presence questions (`Noul`), preventing middle-truncation false negatives.
- **Result Caching (`--cache`)**: SHA-256 content-addressable cache avoids re-evaluating unmodified files. Clear anytime with `typesafe-eval cache clear`.
- **Exit Code Contract (1-over-3 Precedence)**:
  - `0`: All documents passed.
  - `1`: Content / security violation detected.
  - `2`: CLI usage or configuration error.
  - `3`: Runtime / API error (missing key, timeout).
  - *Precedence*: If any document violates a content gate, exit code is always **`1`**, ensuring runtime errors never mask security leaks.

### Programmatic Python API

```python
from typesafe_eval import evaluate, evaluate_document, evaluate_documents

# In-memory document evaluation
result = evaluate(
    content="# Architecture\n\n## Verification Plan\nUnit and integration tests...",
    preset="tech-spec",
)
print(f"Passed: {result.passed_thresholds}, Score: {result.composite_score}")

# Evaluate file with exception on violation
doc_result = evaluate_document("rfc/001.md", preset="tech-spec", raise_on_violation=True)

# Parallel batch evaluation
results = evaluate_documents(["rfc/001.md", "rfc/002.md"], preset="tech-spec", concurrency=4)
```

---

## 🚫 Non-Goals & Boundaries

- **Not a replacement for human review**: `typesafe-eval` acts as an automated sanity and regression gate. It does not replace deep architectural debate or editorial judgment.
- **Not a git history secret scanner**: Evaluates document payloads at review time. It does not inspect git commits or binary blobs. Pair it with dedicated tools like [gitleaks](https://github.com/gitleaks/gitleaks).
- **No absolute cross-document quality score**: Composite numbers do not represent an absolute verdict across different authors or topics. Use `--baseline` to detect relative regression.

---

## 🤖 Agent Guidance & Verification Contract

- **Agent Guidance (`AGENTS.md`)**: Autonomous coding assistants (Claude Code, Google Antigravity CLI, OpenAI Codex) operating in repositories with `typesafe-eval` must follow the instructions in [`AGENTS.md`](AGENTS.md).
- **Antigravity Code Review Skill (`/boost`)**: Automated review routine located at [`.agents/skills/code-review/`](.agents/skills/code-review/) covering Safety & Redaction, Contract & Stream purity, and Evaluator Integrity.
- **Mandatory Acceptance Criteria Verification**: Autonomous agents and releases must verify all 19 real CLI acceptance criteria via OS subprocess execution before merging:
  ```bash
  python scripts/verify_ac.py
  ```

---

## 🧪 Testing

```bash
# Run pytest test suite
pytest

# Verify Acceptance Criteria matrix
python scripts/verify_ac.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
