# Technical Specification Preset (`tech-spec`)

The `tech-spec` preset evaluates architecture proposals, Request for Comments (RFCs), and detailed engineering designs against rigorous engineering criteria.

---

## Core Focus: Empirical Feasibility

Based on corpus empirical validation across engineering RFCs, `tech-spec` focuses on dimensions proven to achieve 100% detection and 0% false alarm rates:

| Dimension | Description | Threshold | Operational Role |
| :--- | :--- | :---: | :---: |
| `has_test_plan` | Does the specification include an actionable test and verification plan? | $\ge 0.50$ | **Hard Gate** |
| `architecture_rigor` | Is the system design technically concrete and thoroughly described? | $\ge 0.50$ | **Hard Gate** |
| `failure_modes` | Are failure modes, fallback mechanisms, or error handling analyzed? | $\ge 0.50$ | Advisory |
| `edge_cases` | Are edge cases and scaling boundaries addressed? | $\ge 0.50$ | Advisory |

---

## Example Invocations

```bash
# Check all RFC documents
typesafe-eval rfc/*.md --preset tech-spec

# Check with staged git pre-commit gating
typesafe-eval --staged --preset tech-spec
```

---

## Why Failure Modes & Edge Cases Are Advisory

Corpus validation on real engineering proposals showed that while `has_test_plan` and structural architecture can be reliably detected from headings and content structure, sections addressing specific edge cases or non-goals often use varied phrasing or are integrated directly into narrative architecture paragraphs.

Marking them as `advisory: true` prevents CI breakage for valid, concise specifications while still alerting architects to consider explicit failure mode sections.
