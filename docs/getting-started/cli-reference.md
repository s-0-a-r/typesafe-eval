# CLI Reference

Full reference for the `typesafe-eval` command-line interface.

---

## Synopsis

```bash
typesafe-eval [OPTIONS] [FILES]...
typesafe-eval init [INIT-OPTIONS]
typesafe-eval schema [OPTIONS]
typesafe-eval cache clear [OPTIONS]
```

---

## Global Options

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--preset` | `-p` | Built-in preset name or path to a YAML configuration file. | `quality` |
| `--config` | `-c` | Explicit path to project config file (`.typesafe-eval.yaml`). | Auto-detected |
| `--format` | `-f` | Output format: `rich`, `plain`, `json`, `github`. | `rich` |
| `--dry-run` | | Sanitize and preview document payload without external API evaluation. | `false` |
| `--offline` | | Run deterministic rules only (0 external API calls). | `false` |
| `--cache` / `--no-cache` | | Enable or disable SHA-256 content-addressable result caching. | Enabled |
| `--cache-dir` | | Directory path for evaluation cache files. | `~/.cache/typesafe-eval` |
| `--concurrency` | `-j` | Number of worker threads for parallel file evaluation. | `1` |
| `--staged` | | Evaluate only Git staged files (useful for pre-commit hooks). | `false` |
| `--since` | | Evaluate only markdown files modified since branch/commit ref. | None |
| `--exclude` | `-e` | Glob pattern(s) to exclude from evaluation (can be specified multiple times). | None |
| `--no-mask` | | Disable PII email/secret masking before sending to API (caution). | `false` |
| `--keep-comments` | | Disable stripping of regular prose HTML comments before evaluation. | `false` |
| `--api-key` | | Explicit TypeSafe API key (overrides `TYPESAFE_API_KEY` env). | None |
| `--api-base-url` | | Base URL for the TypeSafe System One API. | Production API |
| `--version` | `-v` | Display CLI version and exit. | |
| `--help` | `-h` | Show help message and exit. | |

---

## Subcommands

### 1. `typesafe-eval init`
Scaffolds workflow templates and configuration files into the current workspace.

```bash
typesafe-eval init [OPTIONS]
```

**Options**:
- `--pre-commit`: Generate `.pre-commit-config.yaml` with `typesafe-eval-hook`.
- `--claude-code`: Generate Claude Code safety filter hook configuration in `.claude/hooks/`.
- `--github-action`: Generate `.github/workflows/typesafe-eval.yml`.
- `--all`: Scaffold all supported templates and `.typesafe-eval.yaml`.
- `--force`: Overwrite existing target files.

### 2. `typesafe-eval schema`
Outputs the JSON Schema for `.typesafe-eval.yaml` and preset configuration files.

```bash
typesafe-eval schema [--output PATH]
```

Useful for configuring IDE schema completion in VSCode (`settings.json` via `$schema`).

### 3. `typesafe-eval cache`
Manages the local evaluation cache.

```bash
typesafe-eval cache clear [--cache-dir PATH]
```

Deletes stored evaluation cache entries.

---

## Output Formats (`-f`)

### `rich` (Default)
Interactive, stylized terminal tables with colors, spinners, and ANSI formatting.

### `plain`
Clean, plain text tables suitable for simple shell output and non-ANSI terminals.

### `json`
Pure JSON stream emitted to `stdout` conforming to `schema_version: "1.0"`. File errors and diagnostic logs are directed to `stderr`.

### `github`
GitHub Actions workflow commands emitted directly to `stdout`:
```text
::error file=docs/auth.md,line=12,col=5::Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential
```
Produces inline PR annotations on modified files in GitHub Pull Request checks.
