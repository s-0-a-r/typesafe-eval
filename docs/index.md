# TypeSafe-Eval

[![CI](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/s-0-a-r/typesafe-eval)](https://github.com/s-0-a-r/typesafe-eval/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Fast, typed multi-dimensional document evaluation CLI and Python library powered by the OpenAI Decisions API (`gpt-6-luna`) and TypeSafe System One (`jev-1.13.0`).**

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
│  Multi-Provider Decision Engine              │
│  • OpenAI Decisions API (gpt-6-luna)         │
│  • TypeSafe System One (jev-1.13.0)          │
│  • Deterministic Offline Rule Evaluator      │
└──────────────────────┬───────────────────────┘
                       │
       ▼               ▼               ▼
   Exit Code      Terminal / JSON    GitHub PR
   Contract       Streams (`jq`)    Annotations
```

---

## Key Highlights

- ⚡ **Multi-Provider Decision Engine**: Seamless support for **OpenAI Decisions API** (`gpt-6-luna`) and **TypeSafe System One** (`jev-1.13.0`), with automatic environment detection and per-project YAML configuration.
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
