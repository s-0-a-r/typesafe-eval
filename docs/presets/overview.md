# Evaluation Presets Overview

Presets in `typesafe-eval` define what dimensions, questions, and thresholds to evaluate for a given document type.

---

## Built-In Presets

| Preset | Target Documents | Primary Focus | Gating Strictness |
| :--- | :--- | :--- | :--- |
| [`safety`](safety.md) | All markdown & documentation files | PII, secrets, private IPs, credentials | Strict (blocks CI on any violation) |
| [`quality`](quality.md) | User docs, tutorials, guides | Readability, clarity, completeness, actionability | Threshold gating on composite score & key dimensions |
| [`tech-spec`](tech-spec.md) | Technical architecture, RFCs | System design, test plan, architecture tradeoffs | Rigorous architecture gating |
| [`design-doc`](design-doc-and-pr.md) | Product & engineering design docs | Goals, alternatives, rollbacks, open questions | Hybrid (core gates + advisory observations) |
| [`pr-description`](design-doc-and-pr.md) | GitHub / GitLab pull requests | Why, testing details, screenshots, risks | Core testing gating + advisory checklist |

---

## Gating vs Advisory Dimensions

In `typesafe-eval`, preset dimensions are split into two operational classifications:

### 1. Hard Gating Dimensions (`advisory: false` or omitted)
- Must pass the defined threshold.
- If the evaluated score fails the threshold or a safety rule triggers, the CLI exits with **Exit Code 1** (blocking CI pipelines).

### 2. Advisory Dimensions (`advisory: true`)
- Dimensions that provide valuable guidance to authors and autonomous agents, but whose absence should not hard-fail a CI build.
- Results are reported in the CLI output with an `(Advisory)` badge and in JSON results under `advisory_notes`.
- Fulfills the principle that subjective or document-type-dependent dimensions (e.g., non-goals in simple PRs, or edge risks in minor docs) do not cause false CI failures.

---

## Using Presets

```bash
# Specify preset by name
typesafe-eval rfc/*.md --preset tech-spec

# Evaluate with custom local YAML definition
typesafe-eval docs/*.md --preset ./custom-rules.yaml
```
