# Design Doc & PR Description Presets

Presets tailored for everyday product/system design documents and Git pull requests.

---

## 1. Design Doc Preset (`design-doc`)

Used for product requirement documents (PRDs) and engineering design documents.

### Evaluated Dimensions

- **`has_goals`** (Gate, $\ge 0.50$): Clear problem statement and desired outcomes.
- **`has_rollback_plan`** (Gate, $\ge 0.50$): Explicit migration, rollback, or operational risk mitigation strategy.
- **`has_alternatives_considered`** (Gate, $\ge 0.50$): Discussion of trade-offs and alternative approaches rejected.
- **`has_open_questions`** (Gate, $\ge 0.50$): Unresolved items, risks, and next investigation steps.
- **`has_non_goals`** (Advisory): Scope boundaries.

```bash
typesafe-eval designs/*.md --preset design-doc
```

---

## 2. PR Description Preset (`pr-description`)

Used in GitHub Actions to check Pull Request descriptions and merge bodies.

### Evaluated Dimensions

- **`has_testing_details`** (Gate, $\ge 0.50$): How the changes were tested (unit tests, manual testing, reproduction steps).
- **`has_context_or_why`** (Gate, $\ge 0.50$): Links to issue, motivation, or design rationale.
- **`has_visuals_or_repro`** (Advisory): Screenshots, terminal outputs, or before/after diffs when UI is touched.
- **`has_risk_assessment`** (Advisory): Discussion of deployment blast radius or migration notes.

```bash
typesafe-eval pr_body.md --preset pr-description -f github
```

---

## Advisory Items in CI

When using `design-doc` or `pr-description` in GitHub Actions, missing advisory items (such as `has_non_goals` or `has_visuals_or_repro`) generate a GitHub Actions `::notice` rather than failing the build (`::error`), giving reviewers transparency without blocking simple PRs.
