# Git Diff & CI Gating

Save token costs and accelerate CI pipelines by evaluating only changed files.

---

## 1. Evaluating Staged Files (`--staged`)

In local git development, inspect only the files currently staged for commit:

```bash
typesafe-eval --staged --preset safety
```

This queries `git diff --cached --name-only --diff-filter=ACM` and automatically passes only existing markdown documents to the evaluation engine.

---

## 2. Evaluating Branch Diffs (`--since`)

In CI pull requests or feature branch workflows, evaluate only markdown files modified compared to a target branch or commit ref:

```bash
# Evaluate files changed since origin/main
typesafe-eval --since origin/main --preset quality

# Evaluate files changed between two commit hashes
typesafe-eval --since HEAD~3 --preset tech-spec
```

---

## 3. Exclusion Rules (`--exclude` / `-e`)

Skip draft files, templates, or vendor directories:

```bash
typesafe-eval docs/**/*.md --exclude "*.draft.md" -e "docs/templates/**"
```

Patterns can also be permanently specified in `.typesafe-eval.yaml`:

```yaml
exclude:
  - "**/*.draft.md"
  - "docs/templates/**"
  - "node_modules/**"
  - ".venv/**"
```
