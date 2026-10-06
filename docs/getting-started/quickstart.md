# Quickstart

Get up and running with `typesafe-eval` in less than 5 minutes.

---

## 1. Scaffold Configuration (`typesafe-eval init`)

Run the scaffolding wizard to generate standard pre-commit hooks, GitHub Actions workflows, or configuration files:

```bash
# Set up pre-commit gating and GitHub Actions CI workflow
typesafe-eval init --pre-commit --github-action

# Or configure all supported integrations at once
typesafe-eval init --all
```

This creates:
- `.typesafe-eval.yaml` (Project configuration and threshold overrides)
- `.pre-commit-config.yaml` (Pre-commit hook entry)
- `.github/workflows/typesafe-eval.yml` (Automated CI evaluation workflow)

---

## 2. Basic Evaluation

Run your first evaluation against a markdown file:

```bash
typesafe-eval README.md --preset quality
```

The command displays an interactive terminal table with dimension scores, threshold pass/fail states, and advisory observations.

---

## 3. Safety Checking (PII & Secret Scanning)

To verify that documentation files contain no exposed credentials, API keys, or personal contact PII:

```bash
typesafe-eval docs/*.md --preset safety
```

### Deterministic Offline Safety
You can run safety checks completely offline without network access or API credentials:

```bash
typesafe-eval docs/*.md --preset safety --offline
```

In offline mode:
- Known regex patterns (AWS keys, Slack tokens, GitHub tokens, private IPv4 addresses, international phone numbers) are evaluated locally.
- Contact email domains are checked against free-mail providers (Gmail, Yahoo, Outlook, etc.).
- Exactly 0 external API calls are made.

---

## 4. Structured Output for Agents & Scripts

Use `-f json` to stream pure JSON to `stdout` for piping into `jq` or autonomous agent consumers:

```bash
typesafe-eval docs/*.md --preset safety -f json | jq '.[].violations'
```

Stderr contains status notices, while stdout is strictly formatted according to `schema_version: "1.0"`.

---

## 5. Caching & Parallelism

For fast execution across large repositories:

```bash
# Parallel evaluation with 4 worker threads and SHA-256 result caching
typesafe-eval docs/**/*.md --preset quality -j 4 --cache
```

If document content has not changed, the cached result is returned instantly without API calls.
