# TypeSafe-Eval

[![CI](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/typesafe-eval.svg)](https://pypi.org/project/typesafe-eval/)
[![Python versions](https://img.shields.io/pypi/pyversions/typesafe-eval.svg)](https://pypi.org/project/typesafe-eval/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Fast, typed multi-dimensional document evaluation CLI and Python library powered by TypeSafe System One (Jev).**

---

## What is TypeSafe-Eval?

`typesafe-eval` evaluates technical documents, architecture proposals (RFCs), design docs, PR descriptions, and documentation files across multiple dimensions. It enforces strict safety gating (PII redaction, secret scanning) and quality standards both locally and in CI/CD pipelines.

```
Document Markdown
       │
       ▼
┌──────────────────────────────────────────────┐
│  typesafe-eval Local Pre-strip & Sanitizer   │
│  • Redact secrets (AWS, Slack, GitHub, etc.) │
│  • Mask PII emails & phone numbers           │
│  • Strip prose HTML comments                 │
└──────────────────────┬───────────────────────┘
                       │ Sanitized Payload
                       ▼
┌──────────────────────────────────────────────┐
│  TypeSafe System One (Jev-1.13.0) API        │
│  • Multi-dimensional parallel scoring        │
│  • Noul calibrated classification            │
└──────────────────────┬───────────────────────┘
                       │
       ▼               ▼               ▼
   Exit Code      Terminal / JSON    GitHub PR
   Contract       Streams (`jq`)    Annotations
```

---

## Key Highlights

- ⚡ **High-Throughput Batching**: Scores 13 multi-dimensional questions in a single batched API call (~1.1s total turnaround).
- 🛡️ **Zero-Leak Safety Sanitization**: Client-side regex and contextual masking of secrets (AWS, GitHub, Slack tokens) and personal email/phone PII before network transmission.
- 🚦 **Exit Code Contract (1-over-3 Precedence)**: Content/gate violations (`1`) always take precedence over runtime/network errors (`3`), preventing accidental CI passes.
- 🤖 **Agent-First Design**: Formatted for autonomous coding agents (Codex, Claude Code, Copilot, Antigravity CLI) with clean `schema_version: "1.0"` stdout JSON streams.
- 🗄️ **Content-Addressable Result Caching**: SHA-256 caching (`--cache`) avoids re-evaluating unchanged documents.
- 📴 **Deterministic Offline Mode**: `--offline` gating using client-side rules with 0 API calls.
- 🐍 **Type-Safe Public Python API**: Fully typed `evaluate()`, `evaluate_document()`, and `evaluate_documents()` with PEP 561 `py.typed` compliance.

---

## Quick Example

```bash
# Evaluate documentation with the safety preset
typesafe-eval docs/*.md --preset safety

# Structured JSON stream for automation and agents
typesafe-eval docs/*.md --preset quality -f json

# Offline dry-run with zero external network calls
typesafe-eval docs/*.md --preset safety --offline
```

---

## Next Steps

- [Installation](getting-started/installation.md): Install the CLI or Python library.
- [Quickstart Guide](getting-started/quickstart.md): Learn the basics in 5 minutes.
- [Evaluation Presets](presets/overview.md): Explore safety, quality, tech-spec, and custom presets.
- [Python API](python-api/overview.md): Integrate evaluations directly into your Python codebase.
- [Agent Integration](agents/guidance.md): Best practices and operational boundaries for AI coding agents.
