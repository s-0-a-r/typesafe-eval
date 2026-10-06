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

## Global & Evaluation Options

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--preset` | `-p` | Built-in preset name (`quality`, `safety`, `tech-spec`, `design_doc`, `pr_description`). | Project config or `quality` |
| `--config` | `-c` | Explicit path to project config file (`.typesafe-eval.yaml`). | Auto-detected |
| `--format` | `-f` | Output presentation format: `table`, `json`, `markdown`, `github`. | `table` |
| `--out` | `-o` | Save report output to specified file path. | `None` |
| `--dry-run` | | Sanitize and preview document payload without external API evaluation. | `false` |
| `--offline` / `--rules-only` | | Run static regex rule checks offline without TypeSafe API (no API key required). | `false` |
| `--fail-on-threshold` / `--no-fail-on-threshold` | | Exit with non-zero status code (exit 1) if any threshold violation occurs. | Enabled (`true`) |
| `--baseline` | | Previous JSON report to compare against and detect score regressions. | `None` |
| `--cache` / `--no-cache` | | Enable or disable evaluation result cache. | Enabled (`true`) |
| `--cache-dir` | | Directory path for evaluation cache files. | `~/.cache/typesafe-eval` |
| `--concurrency` | `-j` | Number of worker threads for parallel file evaluation. | `4` |
| `--staged` | | Evaluate only Git staged files (useful for pre-commit hooks). | `false` |
| `--since` / `--changed-since` | | Evaluate files modified or added in Git since specified commit or branch ref. | `None` |
| `--exclude` | `-e` | Glob pattern(s) to exclude from evaluation (can be specified multiple times). | `None` |
| `--mask-secrets` / `--no-mask-secrets` | `--mask` / `--no-mask` | Automatically redact detected API keys, credentials, and PII before API call. | Enabled (`true`) |
| `--max-chars` | | Maximum character threshold before safe head/tail truncation. | `25000` |
| `--list-presets` | | List all available built-in evaluation presets and exit. | `false` |
| `--api-key` | | TypeSafe API key (falls back to `TYPESAFE_API_KEY` env). | `None` |
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

### 2. `typesafe-eval validate`
Validates a preset against labeled benchmark documents or runs section ablation studies.

```bash
typesafe-eval validate [LABELS_FILE] [OPTIONS]
```

**Options**:
- `--runs INT`: Number of evaluation runs per document/pair (default: 3).
- `-f, --format [table|json|markdown]`: Output report format. Default: `table`.
- `-o, --out PATH`: Save report output to specified file path.
- `--ablate PATH`: Generate "one section removed" variants from a markdown document split on `## ` headings.
- `--ablate-out-dir PATH`: Output directory for ablated document variants.
- `--ablate-preset TEXT`: Preset name for generated `labels.yaml` (default: `design_doc`).

### 3. `typesafe-eval schema`
Outputs the JSON Schema for `.typesafe-eval.yaml` and preset configuration files.

```bash
typesafe-eval schema [--output PATH]
```

Useful for configuring IDE schema completion in VSCode (`settings.json` via `$schema`).

### 4. `typesafe-eval cache`
Manages the local evaluation cache.

```bash
typesafe-eval cache clear [--cache-dir PATH]
```

Deletes stored evaluation cache entries.

---

## Output Formats (`-f`)

### `table` (Default)
Interactive, stylized terminal tables with colors, summary statistics, and ANSI formatting.

### `markdown`
Clean GitHub Flavored Markdown table suitable for PR comments, CI summaries, and issue bodies.

### `json`
Pure JSON stream emitted to `stdout` conforming to `schema_version: "1.0"`. File errors and diagnostic logs are directed to `stderr`.

### `github`
GitHub Actions workflow commands emitted directly to `stdout`:
```text
::error file=docs/auth.md,line=12,col=5::Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential
```
Produces inline PR annotations on modified files in GitHub Pull Request checks.
