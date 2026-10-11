# Technical Specification Preset (`tech-spec`)

The `tech-spec` preset evaluates architecture proposals, Request for Comments (RFCs), and detailed engineering designs against rigorous engineering criteria.

---

## Core Focus: Empirical Feasibility

Based on corpus empirical validation across engineering RFCs, `tech-spec` focuses on dimensions evaluated across held-out sets (with post-hoc calibration noted for OpenAI Decisions API on `swift-se-0510`; see [Accuracy Benchmarks](../science/accuracy-benchmarks.md)):

| Dimension | Description | Threshold | Type | Operational Role |
| :--- | :--- | :---: | :---: | :---: |
| `has_test_plan` | Does this spec include a dedicated section or explicit statement describing a test or verification plan? | $\ge 0.50$ | Noul | **Hard Gate** |
| `readiness` | What is the implementation readiness of this technical specification? (`ready`, `needs_revision`, `blocked`) | N/A | Choice | Informational |

---

## Example Invocations

```bash
# Check all RFC documents
typesafe-eval rfc/*.md --preset tech-spec

# Check with staged git pre-commit gating
typesafe-eval --staged --preset tech-spec
```

---

## Why Readiness Is An Unmeasured Choice

Corpus validation on real engineering proposals showed that while binary verification strategy (`has_test_plan`) can be reliably detected and gated from headings and content structure, overall implementation readiness is contextual.

`readiness` is modeled as a categorical `choice` dimension (`ready`, `needs_revision`, `blocked`) to provide engineering insights to reviewers and autonomous agents without triggering brittle gate failures.
