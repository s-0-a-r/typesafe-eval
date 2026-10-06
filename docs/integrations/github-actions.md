# GitHub Actions Integration

Automate documentation gating and security scanning in your pull request workflows.

---

## 1. Quick Setup via CLI

Generate a ready-to-use GitHub Actions workflow:

```bash
typesafe-eval init --github-action
```

This creates `.github/workflows/typesafe-eval.yml`.

---

## 2. Using the Official GitHub Action

Add a step in `.github/workflows/docs-gate.yml`:

```yaml
name: Documentation Safety & Quality Gate

on:
  pull_request:
    paths:
      - "docs/**"
      - "**/*.md"

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install typesafe-eval
        run: pip install typesafe-eval

      - name: Run Safety & Quality Checks
        env:
          TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
        run: |
          typesafe-eval --since origin/main --preset safety -f github
          typesafe-eval --since origin/main --preset quality -f github
```

---

## 3. Inline PR Annotations (`-f github`)

When using `-f github`, `typesafe-eval` formats violations as GitHub Actions commands:

```text
::error file=docs/architecture.md,line=45,col=12::Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential
```

These appear as **inline code annotations** in the GitHub Pull Request "Files Changed" diff view, pin-pointing the exact line and column of the violation.

---

## 4. Offline CI Check (Zero API Costs)

To run secret scanning and PII checks in CI without providing an external API key:

```yaml
      - name: Offline Safety Check
        run: |
          typesafe-eval --since origin/main --preset safety --offline -f github
```
