# AGENTS.md — Guidance for Autonomous Coding Agents

This guide provides instructions and operational boundaries for AI coding assistants (OpenAI Codex, GitHub Copilot, Google Antigravity CLI, Claude Code, Cursor, Aider) operating in repositories that use `typesafe-eval`.

> 📖 **Online Documentation**: [https://s-0-a-r.github.io/typesafe-eval/agents/guidance/](https://s-0-a-r.github.io/typesafe-eval/agents/guidance/)

---

## 1. Quick Command Invocations

Always invoke `typesafe-eval` with the appropriate preset:

```bash
# Safety check (PII, credentials, secret exposure)
typesafe-eval docs/*.md --preset safety

# Documentation quality check
typesafe-eval docs/*.md --preset quality

# Technical specification / RFC check
typesafe-eval rfc/*.md --preset tech-spec

# Structured JSON output for agent consumption
typesafe-eval docs/*.md --preset quality -f json

# Evaluate only git staged files (pre-commit gating)
typesafe-eval --staged

# Evaluate files modified since branch/commit
typesafe-eval --since origin/main

# Parallel document evaluation (concurrency)
typesafe-eval docs/*.md -j 8

# Multi-provider evaluation (OpenAI Decisions API with gpt-6-luna)
typesafe-eval docs/*.md --preset quality --provider openai

# Exclude files or patterns
typesafe-eval docs/*.md --exclude "*.draft.md" -e "docs/templates/**"

# Offline / rules-only mode (zero API calls, deterministic rules only)
typesafe-eval docs/*.md --preset safety --offline

# Dry-run validation (does not require external API call)
typesafe-eval docs/*.md --dry-run
```

---

## 2. Evaluation Presets

| Preset | Purpose | Primary Checks |
| :--- | :--- | :--- |
| `safety` | PII & Secret gating | Credentials, personal emails (free-mail vs role), phone numbers, private IPs, sensitive URLs |
| `quality` | Document quality | Readability, structural clarity, completeness, actionable takeaways |
| `tech-spec` | Architecture & RFCs | Technical rigor, system design clarity, failure mode analysis, edge cases |
| Custom (`-c`) | Domain-specific | Custom rules, customized thresholds, custom role email patterns |

---

## 3. Exit Code Contract

`typesafe-eval` returns deterministic exit codes to enable agent branching:

| Exit Code | Classification | Meaning | Agent Action |
| :---: | :--- | :--- | :--- |
| **`0`** | Success | All documents passed gates, or clean dry-run. | Proceed with task. |
| **`1`** | Content Violation | At least one gate or security violation occurred. | Inspect `violations` and fix the document. |
| **`2`** | Usage / Config Error | Invalid arguments, non-existent files, or syntax error. | Check command options and file paths. |
| **`3`** | Runtime Error | Network timeout, API error, or missing `TYPESAFE_API_KEY`. | Skip or alert user to check environment; do not modify document. |

### Precedence Rule (1 over 3)
If multiple files are evaluated and any file fails a content/safety gate, `typesafe-eval` returns **exit code 1**, even if other files encountered runtime errors. A detected violation is never masked by a runtime error.

---

## 4. Reading JSON Output (`schema_version: "1.0"`)

Parse the JSON output from `stdout` (`typesafe-eval ... -f json`):

```json
[
  {
    "schema_version": "1.0",
    "filename": "auth.md",
    "passed_thresholds": false,
    "composite_score": 0.52,
    "violations": [
      "Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential",
      "PII Exposure: [EMAIL_1] is an individual address (free-mail)"
    ],
    "email_evaluations": [
      {
        "placeholder": "[EMAIL_1]",
        "outcome": "personal",
        "decided_by": "free_mail"
      }
    ],
    "secret_evaluations": [
      {
        "placeholder": "[REDACTED_AWS_KEY]",
        "outcome": "secret",
        "decided_by": "rule"
      }
    ]
  }
]
```

- **`passed_thresholds`**: Boolean status flag.
- **`violations`**: Array of actionable failure messages.
- **`email_evaluations`**: Differentiates personal contact emails (`personal`) from shared organizational mailboxes (`role`).
- **`secret_evaluations`**: Identifies exposed credentials by rule or contextual model determination without exposing raw values.
- **Stderr Separation**: File errors and tool warnings are emitted to `stderr`; `stdout` is always a clean JSON stream suitable for `jq` or JSON parsers.

---

## 5. The 4 Mandatory Guidance Rules

All autonomous agents must abide by the following 4 rules:

1. **Don't make scores a loop target**:
   - Cap automated revision loops at **2 rounds maximum**.
   - Do not distort, degrade, or over-optimize natural writing just to chase higher numeric scores (Goodhart's Law). Address specific items listed in `violations`, then finalize your edit.

2. **Language caveat**:
   - TypeSafe System One (Jev) is calibrated for **English** documentation.
   - On non-English text, treat borderline scores or low confidence with caution and inform the user.

3. **Near-threshold results are soft**:
   - Questions and candidates marked with `near_threshold: true` fall within ±0.10 of the decision boundary.
   - Report the calibrated probability range (e.g. `p = 0.48–0.60`) to the user as a contextual observation rather than an absolute failure.

4. **Never pass API key through the agent**:
   - The CLI reads `TYPESAFE_API_KEY` or `OPENAI_API_KEY` directly from the environment.
   - Never ask the user to provide an API key in conversational chat, and never hardcode or echo credentials in commands or scripts.

---

## 6. Antigravity Code Review Skill (`/boost`)

For Google Antigravity CLI agents reviewing code changes, diffs, or pull requests in this repository, an automated workspace review skill is provided at `.agents/skills/code-review/`.

When conducting code reviews, agents should invoke the **`/boost`** review routine to evaluate changes across the 5 core pillars:
1. **Safety & Redaction**: Zero raw secret/email leaks, Exit 1-over-3 precedence, and pre-strip comment detection.
2. **Contract & Stream**: Exit codes 0/1/2/3, stdout JSON purity for `jq`, and `schema_version: "1.0"`.
3. **Evaluator Integrity**: The 4 mandatory guidance rules, Goodhart's law defense, chunking & unplaced items.
4. **Test & Implementation**: 100% pytest pass rate, mock/real parity, and strict typing.
5. **Real CLI Acceptance Verification**: End-to-end OS subprocess execution against acceptance criteria matrix.

---

## 7. Mandatory Autonomous AC Verification

All autonomous agents (and developers) operating in this repository **must verify actual Acceptance Criteria (AC)** before finalizing feature implementations, opening pull requests, or initiating release workflows.

### Autonomous Verification Contract
- **Unit Tests Alone Are Insufficient**: Mock-only tests (e.g. `CliRunner` with monkeypatch) do not satisfy acceptance. Real CLI entrypoints (`typesafe-eval`, `typesafe-eval-hook`, `hooks/claude_safety_hook.py`) must be executed as OS subprocesses.
- **Verification Command**:
  ```bash
  # Standalone markdown/JSON acceptance matrix runner
  python scripts/verify_ac.py

  # Or pytest acceptance marker
  pytest -v -m acceptance
  ```
- **PR Inclusion**: Agents must execute `python scripts/verify_ac.py` and attach the generated Acceptance Criteria Verification Matrix table into the PR description.
- **Zero Regression Rule**: 100% of acceptance criteria (all 18 items) must report `**PASS**`. Any failure blocks review approval and release.

---

## 8. Mandatory Release Branch Workflow

All autonomous coding agents operating in this repository **must follow the release branch development lifecycle**:

### The Branching Contract
1. **Never Branch Directly from `main` for Development**:
   - Development branches (`feat/*`, `fix/*`, `chore/*`, `refactor/*`) must branch from the active release branch (`release/v<version>`, e.g. `release/v0.8.0`).
2. **Never Target `main` for Feature PRs**:
   - Pull requests for feature work, fixes, and refactoring must target `base: release/v<version>`.
   - Direct PRs to `main` from non-release branches are strictly prohibited and automatically blocked by CI (`.github/workflows/branch_policy.yml`).
3. **Release Promotion**:
   - Only release branches (`release/v*`) may target `main` when initiating the final release PR.
