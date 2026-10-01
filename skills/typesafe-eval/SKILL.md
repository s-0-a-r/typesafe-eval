---
name: typesafe-eval
description: Fast, typed multi-dimensional document evaluation CLI powered by TypeSafe System One (Jev)
---

# TypeSafe Document Evaluation Skill

This skill guides AI agents on running `typesafe-eval` to evaluate, gate, and improve Markdown and technical documentation.

---

## 1. When to Run Which Preset

Select the preset matching the document's purpose and lifecycle stage:

| Preset | Target Documents | Evaluated Dimensions |
| :--- | :--- | :--- |
| **`safety`** | All documentation, PRs, public releases, operational memos | Credential exposure, PII (personal emails, phone numbers, sensitive internal IPs/URLs), confidentiality risk |
| **`quality`** | General docs, user guides, developer onboarding, knowledge base | Structural clarity, completeness, logical cohesion, actionable next steps |
| **`tech-spec`** | Engineering RFCs, technical designs, architecture proposals | Technical depth, architecture feasibility, edge case analysis, failure modes |
| **Custom YAML** (`--config <path>`) | Project-specific guidelines or regulatory requirements | Domain-tailored criteria, custom role patterns, specialized weights |

### Running Presets

```bash
# Security & PII pre-release check
typesafe-eval docs/*.md --preset safety

# Technical design spec evaluation
typesafe-eval rfc/*.md --preset tech-spec

# Structured JSON export for agent parsing
typesafe-eval docs/*.md --preset quality -f json
```

---

## 2. Reading the JSON Contract (`schema_version: "1.0"`)

When executing with `-f json`, `stdout` outputs a structured array adhering to schema `"1.0"`:

```json
[
  {
    "schema_version": "1.0",
    "filename": "design.md",
    "passed_thresholds": false,
    "composite_score": 0.65,
    "violations": [
      "Technical Depth: architecture completeness below threshold 0.70"
    ],
    "warnings": [],
    "scores": { ... },
    "nouls": { ... },
    "choices": { ... },
    "email_evaluations": [ ... ],
    "secret_evaluations": [ ... ],
    "mock": false
  }
]
```

### Key Contract Fields to Inspect
- **`passed_thresholds`**: Boolean gate (`true` if passed, `false` if any threshold or security gate failed).
- **`violations`**: Array of human-readable violation messages explaining why the document failed.
- **`email_evaluations` / `secret_evaluations`**: Evaluated sensitive candidates with objective features, outcomes (`personal` vs `role`, `secret` vs `safe`), and `decided_by` source (`rule`, `free_mail`, or `model`).
- **`scores` / `nouls` / `choices`**: Per-dimension calibrated probabilities, scores, and confidence levels.
- **Pipelining Guarantee**: Tool and file errors are emitted exclusively on `stderr`. `stdout` is guaranteed clean JSON suitable for piping to `jq` or direct JSON parsing.
- **Privacy Guarantee**: JSON outputs never expose raw secrets or unredacted passwords.

---

## 3. The 4 Mandatory Guidance Rules

When interacting with documents and evaluation results, agents must strictly follow these 4 rules:

1. **Don't make scores a loop target**:
   - Cap automated revision loops at **2 rounds maximum**.
   - Do not butcher or over-optimize natural, communicative prose just to artificially game numeric scores (Goodhart's Law). Fix concrete gaps identified in `violations`, then stop.

2. **Language caveat**:
   - TypeSafe System One (Jev) calibration and accuracy are optimized for **English** documentation.
   - For non-English documents, treat low confidence or borderline scores as advisory rather than definitive.

3. **Near-threshold results are soft**:
   - When `near_threshold: true` is reported on a question or candidate (within ±0.10 of threshold), treat the result as soft and contextual.
   - Present the calibrated probability range (e.g. `p = 0.45–0.62`) to the user as a point for human judgment rather than a deterministic failure.

4. **Never pass API key through the agent**:
   - Always read `TYPESAFE_API_KEY` from the execution environment.
   - Never ask the user to type secret API keys into conversational prompts, and never pass keys via command-line arguments.
