# Pre-commit Hook Integration

Catch secret leaks, personal PII, and documentation regressions locally before making a Git commit.

---

## 1. Quick Setup via CLI

```bash
typesafe-eval init --pre-commit
```

This appends the recommended configuration to `.pre-commit-config.yaml`.

---

## 2. Configuration Example

Add the following to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/s-0-a-r/typesafe-eval
    rev: v1.0.0
    hooks:
      - id: typesafe-eval-safety
        name: TypeSafe Safety Check (Offline)
        entry: typesafe-eval
        args: ["--preset", "safety", "--offline"]
        types: [markdown]

      - id: typesafe-eval-quality
        name: TypeSafe Documentation Quality
        entry: typesafe-eval-hook
        args: ["--preset", "quality"]
        types: [markdown]
```

---

## 3. Dedicated Hook Entrypoint (`typesafe-eval-hook`)

`typesafe-eval-hook` is a specialized wrapper binary designed for pre-commit workflows:
- If `TYPESAFE_API_KEY` is present, it executes the full evaluation gate.
- If `TYPESAFE_API_KEY` is empty or missing, it emits an informative notice to `stderr` and exits cleanly with **Exit Code 0**, preventing git commits from being blocked on developers' machines who do not have an API key configured.
- If a content or safety violation is detected, it fails with **Exit Code 1**.
