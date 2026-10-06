# typesafe-eval

[![CI](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/s-0-a-r/typesafe-eval)](https://github.com/s-0-a-r/typesafe-eval/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Fast, typed, multi-dimensional document evaluation CLI and CI gate powered by the **TypeSafe System One API** (model: `jev-1.13.0`).

---

## ✨ What typesafe-eval Adds

`typesafe-eval` is an evaluation harness and CI gate that wraps TypeSafe System One. It adds:

- **Context-Aware Masking & Candidate Evaluation**: Deterministic regex rules combined with candidate-level feature extraction (for emails, phone numbers, IP addresses, internal URLs, and secrets). Detection and feature extraction always run even when `--no-mask` is passed.
- **Offline Rules-Only Mode (`--offline`)**: Zero-network local evaluation relying strictly on deterministic safety and credential rules without requiring external API keys.
- **Content-Addressable Result Caching (`--cache`)**: SHA-256 content-hash caching to eliminate redundant evaluations in local iterative development and CI re-runs, with `typesafe-eval cache clear`.
- **Validation & Calibration Harness (`validate`)**: Built-in test runner for evaluating presets against ground-truth document sets and ablation variants (`labels.yaml`) to verify calibration, detection rates, and regression directions.
- **Baseline Regression Detection (`--baseline`)**: Flags score drops larger than the measured noise between revisions, detecting subtle quality degradation against previous runs.
- **File Exclusion Patterns & Default Ignores (`--exclude`)**: Exclude specific files or glob patterns, with automatic skipping of standard build and dependency directories (`.git`, `node_modules`, `.venv`, etc.).
- **Line & Column Position Mapping (`-f github`)**: Pinpoint exact line and column locations for violations and emit native GitHub Actions workflow commands for PR inline annotations.
- **Programmatic Python API & Strict Typing**: Direct programmatic access via `import typesafe_eval` (`evaluate()`, `evaluate_document()`, `evaluate_documents()`), typed exceptions, and PEP 561 `py.typed` compliance.
- **Configuration Auto-Discovery**: Automatic upward discovery of `.typesafe-eval.yaml`, `.typesafe-eval.yml`, or `pyproject.toml` (`[tool.typesafe-eval]`).
- **Parallel Document Concurrency (`-j` / `--concurrency`)**: Accelerated evaluations using thread pools while preserving strict document ordering in outputs.
- **Git Diff Evaluation (`--staged` / `--since`)**: Zero-noise gating for pre-commit hooks and CI pull request workflows by evaluating only modified markdown documents.
- **Measured Built-in Checklists**: Presence checklists (`design-doc`, `pr-description`) measured on a corpus of public design documents and pull requests, with counts per question and the questions that are not reliable listed.
- **Long Document Chunking**: Overlapping window chunking for presence questions (`Noul`) to prevent middle-truncation false degradation while keeping token budgets safe.
- **CI/CD Integration & Precedence Exit Codes**: Deterministic exit codes (`0` pass, `1` violation, `2` usage error, `3` runtime error) where violations strictly take precedence over runtime errors.
- **Agent Integrations**: Native skills and pre-commit/safety hooks for autonomous coding agents (Google Antigravity CLI, Claude Code, OpenAI Codex).
- **Custom YAML Presets**: Define project-specific evaluation criteria, custom weights, role patterns, and thresholds.

### TypeSafe System One API Properties
The underlying evaluation engine is powered by the [TypeSafe System One API](https://docs.typesafe.ai/) (`jev-1.13.0`):
- **Typed Judgments**: Calibrated probabilities (`Noul`), multi-level rubrics (`Score`), and categorical decisions (`Choice`).
- **Batched Parallel Questions**: Evaluates all questions in a single API request per document/chunk, avoiding redundant document re-transmissions (~3.8× lower token cost for 4 questions; around 10–12× with 13 questions per [TypeSafe's benchmark](https://docs.typesafe.ai/cookbooks/parallel_questions)).

---

## 🚫 Non-Goals

- **Not a replacement for human review**: `typesafe-eval` acts as an automated sanity gate and regression check in CI/CD. It catches missing sections, exposed credentials, PII, and structure degradation, but does not substitute for deep human architectural or editorial review.
- **Not a secret scanner**: The credential detection in `typesafe-eval` is designed to prevent accidental leakage in evaluated texts and enforce basic hygiene. It does not scan git commit history, binary artifacts, or deep repository revisions. Pair it with dedicated tools like `gitleaks` in CI.
- **No absolute quality score**: Single composite scores (e.g. "this document is 82% good") do not provide a reliable absolute pass/fail quality gate across diverse writing styles and document domains. `typesafe-eval` focuses on regression detection (`--baseline`) and checklist presence verification rather than claiming an absolute quality verdict.

---

## 📦 Built-in Presets & Calibration Status

| Preset | Purpose | Questions | Calibration / Measurement Status |
| :--- | :--- | :--- | :--- |
| `design-doc` | Review checklist for system design docs | 10 presence Nouls (`goal`, `rollback`, `metrics`, etc.) | Measured on public design documents, EN and JA (tuning 12, held-out 6, [counts](#checklist-counts)). Reliable: `alternatives`, `rollback`, `open_questions`; `goal` for recognizing a stated goal only; `owner_timeline` for flagging a missing one only. **Not reliable**: `non_goals`, `risks`, `migration`, `metrics`. `impact` is not measured. |
| `safety` | Content safety, PII, credentials, confidentiality | `has_secrets`, `has_pii`, `confidentiality_risk`, `policy_compliance` | Measured on fixtures ([pii_secrets](tests/fixtures/pii_secrets/labels.yaml), [confidentiality](tests/fixtures/confidentiality/labels.yaml)):<br>• `pii_secrets` (40 docs, #40): all 40 document verdicts correct, masked and `--no-mask`, 3 runs (validate: min_detected 23, max_false_alarms 0 met).<br>• `confidentiality` (46 docs, #53): 32/32 harmless below the threshold (max 0.31) and 14/14 confidential above (min 0.66), masked and `--no-mask`, 3 runs. |
| `pr-description` | Checklist for pull request descriptions | 5 presence Nouls (`summary`, `testing`, `impact`, etc.) | Measured on public pull requests, EN and JA (tuning 12, held-out 6, [counts](#checklist-counts)). Reliable: `testing`. **Not reliable**: `summary`, `impact`, `breaking_changes`, `related_issues`. |
| `quality` | Readability & structure regression detection | `clarity` (Score), `tone` (Choice) | `clarity` measured on edited pairs of public specifications, PR descriptions and articles (tuning 51 pairs, held-out 84, runs 3). Lowers the score as expected: shuffled sentences (held-out −0.524), filler (−0.353). Does not move it: unrelated additions (−0.005), paraphrases (within ±0.004). **Not met**: removing content (−0.177, CI upper −0.096 against a gate of −0.1; passed on tuning), removing headings (−0.061), and swapping sections is not shown to be neutral (CI [−0.166, +0.031]). **Does not tell a real review revision from the original** (Δ +0.013 [−0.036, +0.062] against a between-document σ of 0.116), and scores are not comparable across documents; an unfilled PR template can score higher than the filled-in version. `tone`: no labels, not measured. Use with `--baseline`. |
| `tech-spec` | Test / verification plan check for technical specs | `has_test_plan` (Noul), `readiness` (Choice) | `has_test_plan`: reliable on the corpus (tuning 8, held-out 4, [counts](#checklist-counts)). `readiness`: no labels, **not measured**. Its answers depend on the other questions in the request: with the four-question preset it answered ready 162 / needs_revision 158 over the pair runs; with the reduced preset, ready 19 / needs_revision 5 over the presence runs. The Scores `technical_depth` and `edge_case_coverage` were removed in v0.4.0: removing content from a spec did not lower them enough (−0.107 and −0.037 against a gate of −0.1 at the CI upper bound). With one Noul left, the composite score equals `has_test_plan`. |

### Checklist counts

Measured with the v0.4.0 wording (`design-doc` and `pr-description` as of commit d0efa2a, `tech-spec` as of 0a56f28). The corpus, its labels and the rules the numbers were read by are in [validation/corpus](validation/corpus/README.md) and [PREREGISTRATION.md](validation/corpus/PREREGISTRATION.md). The tuning set was used to choose the wording; the held-out set was run once afterwards. Each document was evaluated twice.

"Missing flagged" counts documents without the item that scored below 0.5 in both runs. "False alarms" counts documents with the item that scored below 0.5 in at least one run. "Near 0.5" counts documents with the item that passed but scored within 0.5 ± 0.15, where a rerun can flip the result. A question is not reliable when any of the three shows up in either set. The counts are small, so a reliable question has only passed a small test, not shown that it cannot fail.

| Preset | Question | Tuning: missing flagged | Tuning: false alarms | Held-out: missing flagged | Held-out: false alarms | Near 0.5 (tuning / held-out) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `design-doc` | `goal` | no label | 0/9 | no label | 0/4 | 0 / 0 | recognizes a stated goal |
| `design-doc` | `non_goals` | 4/7 | 0/4 | 1/2 | 0/3 | 0 / 0 | not reliable |
| `design-doc` | `alternatives` | 2/2 | 0/5 | no label | 0/3 | 0 / 0 | reliable |
| `design-doc` | `risks` | 2/3 | 0/2 | 2/2 | 0/1 | 0 / 0 | not reliable |
| `design-doc` | `rollback` | 7/7 | 0/2 | 3/3 | no label | 0 / 0 | reliable |
| `design-doc` | `metrics` | 4/4 | 0/2 | 2/2 | 0/1 | 1 / 0 | not reliable |
| `design-doc` | `migration` | 2/2 | 0/4 | 2/2 | no label | 1 / 0 | not reliable |
| `design-doc` | `impact` | no label | no label | no label | 0/1 | 0 / 0 | not measured |
| `design-doc` | `open_questions` | 4/4 | 0/4 | 3/3 | 0/1 | 0 / 0 | reliable |
| `design-doc` | `owner_timeline` | 4/4 | no label | no label | no label | 0 / 0 | flags a missing one |
| `pr-description` | `summary` | no label | 0/10 | no label | 0/6 | 0 / 1 | not reliable |
| `pr-description` | `testing` | 3/3 | 0/4 | 2/2 | 0/2 | 0 / 0 | reliable |
| `pr-description` | `impact` | 1/1 | 0/6 | no label | 0/2 | 1 / 0 | not reliable |
| `pr-description` | `breaking_changes` | 8/8 | 0/2 | 3/3 | 1/2 | 0 / 0 | not reliable |
| `pr-description` | `related_issues` | 1/1 | 1/11 | 2/2 | 1/4 | 0 / 1 | not reliable |
| `tech-spec` | `has_test_plan` | 3/3 | 0/5 | 3/3 | 0/1 | 0 / 0 | reliable |

The `non_goals` rows include hand-written Non-goals sections inserted into public specifications as positive controls (3 tuning, 2 held-out); all scored 0.99. The tuning `related_issues` false alarm is a pull request whose only reference is a link to another pull request; the question names issues, tickets, design docs and discussions, not pull requests.

### Language Support & Non-English Accuracy

TypeSafe System One is trained primarily on English. As noted in TypeSafe's documentation, accuracy and calibration can be lower on non-English texts.

In our measured Japanese fixtures compared to English:
- **Design Doc Checklist (`design-doc`)**:
  - On the corpus, the Japanese tuning documents (4) flagged 15 of 16 missing items with no false alarm, and the English ones flagged 14 of 17. The Japanese held-out set has one document and no missing item, so this is not a claim about Japanese in particular.
  - On the earlier single-section ablation fixtures (11 documents each), EN caught 7/10 removed sections and JA 6/10, with 0/100 false alarms in both.
- **PR Description Checklist (`pr-description`)**:
  - Three of the four held-out failures are on Japanese pull requests, two of them on the same one.
- **PII & Confidentiality (`safety`)**:
  - Only 1 of the 40 `pii_secrets` fixtures and 3 of the 46 `confidentiality` fixtures are Japanese, so there is no Japanese accuracy figure for PII.
- **Long Document Truncation & Chunking**:
  - English 30.8k doc: middle rollback dropped to 0.58 with truncation, restored to **0.98** with chunking.
  - Japanese 32.4k doc: middle rollback dropped to 0.79 with truncation, restored to **0.98** with chunking.

---

## 🚀 Installation

### Using pip:
```bash
pip install git+https://github.com/s-0-a-r/typesafe-eval.git
```

### From source:
```bash
git clone https://github.com/s-0-a-r/typesafe-eval.git
cd typesafe-eval
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 🔑 Authentication

Set your TypeSafe API key in the environment:
```bash
export TYPESAFE_API_KEY="your_api_key_here"
```

Or pass it directly via `--api-key`.

---

## 📖 Usage Examples

### 1. Evaluate Documents with Built-in Preset
```bash
# Evaluate design documents using the design-doc checklist
typesafe-eval docs/design/*.md --preset design-doc

# Alias command is also available:
jev-eval docs/design/*.md --preset design-doc
```

### 2. Screen for Sensitive Information & Policy Violations (`safety`)
```bash
typesafe-eval specs/*.txt --preset safety
```

> [!IMPORTANT]
> **Pre-Flight Gate, Not a Secret Scanner**: `has_secrets` and regex masking serve as a pre-flight safety gate to prevent credentials from leaking in evaluated document payloads. It is **not** a secret scanner: it does not inspect git history, commits, or binary files. We strongly recommend pairing `typesafe-eval` with dedicated scanners like [gitleaks](https://github.com/gitleaks/gitleaks) or [trufflehog](https://github.com/trufflesecurity/trufflehog) in your CI pipeline.

#### Context-Aware PII and Secrets Evaluation (v0.4.0)
`typesafe-eval` utilizes a candidate-level context-aware evaluation architecture:
1. **Numbered Placeholders**: Replaces detected candidates with numbered placeholders (`[EMAIL_n]`, `[PHONE_n]`, `[IP_n]`, `[URL_n]`, `[SECRET_n]`).
2. **Metadata in State**: Extracts objective structural features into `state` (e.g. `state.redacted_emails`, `state.redacted_phones`, `state.redacted_ips`, `state.redacted_urls`, `state.redacted_secrets`).
3. **Strict Safety Constraint**: `state.redacted_secrets` NEVER contains raw secret values, value fragments, or hashes—only non-sensitive metadata (key name, value length, character classes, syntax flags, location).
4. **Rule-Based Fast Paths**:
   - **Known Credential Formats** (AWS `AKIA…`, GitHub `ghp_…`, Slack `xox…`, private keys, live API keys): FAIL deterministically by code (`decided_by: "rule"`). Jev is not asked. Known documentation example keys (e.g. `AKIAIOSFODNN7EXAMPLE`) are allowed and PASS by code.
   - **Template & Example Placeholders**: Values matching placeholder syntax (`${…}`, `<…>`, `xxx`, `changeme`) PASS deterministically by code.
   - **Documentation & Loopback IPs**: Documentation ranges (RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`; RFC 3849: `2001:db8::/32`) and loopback (`127.0.0.1`, `::1`) PASS by code as non-sensitive.
   - **Example & Public Domains**: Example domains (RFC 2606: `example.com`, `example.org`, `example.net`, `.test`, `.example`, `localhost`) and public platforms (e.g. `github.com`) PASS by code.
   - **Free-mail Addresses**: Free-mail providers (`gmail.com`, `yahoo.com`, `icloud.com`, etc.) deterministically fail as personal PII (`decided_by: "free_mail"`).
5. **Parallel Per-Candidate Evaluation**: Ambiguous candidates (e.g. corporate emails, private IPs, internal TLDs like `.internal`/`.corp`, switchboard vs personal phones, ambiguous `key=val` secrets) are evaluated via parallel `Noul` questions, allowing the model to make contextual determinations based on surrounding document text.
6. **Decoupled Detection from Masking**:
   - Detection, feature extraction, and candidate questions **always run**, even when `--no-mask` is passed (including for long, chunked documents).
   - `--no-mask` controls only whether sensitive values are substituted in the document text sent to the API.
   - With `--no-mask`, deterministic rules still apply (e.g. `support@gmail.com` and exposed credentials still fail by rule).
7. **HTML Comments Stripped**:
   - Detection and masking occur across the full raw document, including within HTML comments (`<!-- ... -->`). HTML comments are stripped before sending text to the model, matching how rendered Markdown displays the document while ensuring secrets and PII in comments are detected. Comments inside fenced code blocks and inline code spans are preserved.

#### Known Limitations
- **Context-Free Isolated Addresses**: When an address appears without surrounding context (e.g. `Forward to yamada@acme-corp.com`), the model relies solely on structural features. Accuracy may vary when neither role keywords nor individual context are present.

### 3. Evaluate Technical Specs (`tech-spec`)
```bash
typesafe-eval rfc/*.md --preset tech-spec --format markdown --out eval_report.md
```

### 4. Output as JSON for Pipeline / Tooling Integration
```bash
typesafe-eval docs/memo.md --preset quality --format json
```

#### JSON Contract & Result Schema

`typesafe-eval` guarantees a stable JSON contract with explicit schema versioning across both `eval` and `validate` commands:
- `schema_version`: String contract version identifier (`"1.0"`).
- **Pipelining Guarantee**: Any file-level or evaluation errors are routed exclusively to `stderr` (`<path>: <error>`). `stdout` remains a clean, valid JSON stream suitable for piping directly to `jq` or downstream tools (e.g. `typesafe-eval docs/*.md -f json | jq '.[] | select(.passed_thresholds == false)'`).
- **Strict Privacy Guarantee**: Evaluated outputs and JSON results never expose raw secret values, credential fragments, or unredacted passwords—only non-sensitive structural metadata and sanitized placeholders.

When exporting results with `--format json`, each document evaluation result contains:

- `schema_version`: Contract schema version (`"1.0"`).
- `filepath` / `filename`: Evaluated file path and name.
- `preset_name`: Applied preset or custom config name.
- `composite_score`: Weighted overall score (0.0 to 1.0) when scores or nouls are present.
- `passed_thresholds`: Primary gate boolean (`true` if all score/risk gates and pre-flight scans passed; `false` otherwise).
- `mock`: Boolean indicating whether `--dry-run` was used without calling the API (`true` in dry-run, `false` otherwise).
- `api_calls`: Number of API calls made for evaluating the document (1 for standard documents, >1 when chunking long documents).
- `was_truncated`: Boolean indicating whether the document text was truncated due to length.
- `scores`: Map of score questions with `score`, `max_score`, `normalized_score`, `confidence`, and `near_threshold`.
- `nouls`: Map of noul questions with calibrated probability, override transparency, and `near_threshold`:
  - `probability`: Calibrated probability returned by the model (`null` only when the model did not return a question that the preflight scan overrode, so `overridden_by` is also set; any other question missing from the API response raises an error).
  - `overridden_by`: Set to `"preflight_scan"` when deterministic rules caught credentials or personal PII.
  - `near_threshold`: Boolean indicating whether the probability is within ±0.1 of its threshold.
- `choices`: Map of choice questions with selected `choice` and `confidence`.
- `email_evaluations`: List of evaluated email candidates with placeholder, question ID, structural features, outcome (`personal` or `role`), decision source (`rule`, `free_mail`, or `model`), and `near_threshold`.
- `phone_evaluations`: List of evaluated phone numbers with placeholder, structural features, outcome, decision source, and `near_threshold`.
- `ip_evaluations`: List of evaluated IP addresses with placeholder, structural features, outcome, decision source, and `near_threshold`.
- `url_evaluations`: List of evaluated URLs with placeholder, structural features, outcome, decision source, and `near_threshold`.
- `secret_evaluations`: List of evaluated secrets with placeholder, non-sensitive structural metadata (never raw values), outcome, decision source, and `near_threshold`.
- `violations`: List of descriptive failure messages explaining any gate violations or pre-flight overrides. Key field for automated triage and failure reporting.
- `warnings`: List of non-fatal threshold warnings (e.g. when `thresholds_as_warnings: true`).
- `baseline_diff`: When `--baseline` is used, contains comparison status (`compared` or `new`), truncation mismatch flag, and per-question deltas (`diff`, `max_drop`, `passed`).

### 5. List Built-in Presets
```bash
typesafe-eval --list-presets
```

### 6. Dry-Run Mode (Validation without Calling API)
```bash
typesafe-eval docs/*.md --dry-run
```
In dry-run mode:
- Terminal tables and Markdown reports clearly display `(MOCK)` in headers, and status is shown as `Verdict: N/A (MOCK)`.
- JSON output includes `"mock": true` for every evaluated document, with `violations: []` and `warnings: []`.
- Exits with code `0` for valid inputs across all presets, without making any external API calls. Usage errors still exit with code `2`, and file errors exit with code `3`.

### 7. Baseline Regression Detection (`--baseline`)
A fixed absolute threshold cannot reliably catch subtle quality degradation between document edits. `typesafe-eval` provides `--baseline` mode to detect score drops against previous evaluation results:

```bash
# Save baseline evaluation to JSON
typesafe-eval docs/*.md --preset quality --format json --out baseline.json

# Check modified documents against previous baseline
typesafe-eval docs/*.md --preset quality --baseline baseline.json
```

- **Regression Thresholds**: A question whose score or probability drops by more than its threshold triggers a regression violation (exit 1). The default threshold is `0.10`, overridable per question in custom YAML via `max_drop`.
- **Empirical Noise Calibration**: In noise measurements across 3 documents × 4 runs on all 5 built-in presets (60 evaluations, 396 pairwise comparisons evaluated against TypeSafe System One API `jev-1.13.0` via `scripts/measure_noise.py` with `cache=False`):
  - `quality`: 99th percentile |Δ| = `0.005`, max = `0.005` (mean |Δ| = `0.0008`)
  - `safety`: 99th percentile |Δ| = `0.030`, max = `0.030` (mean |Δ| = `0.0038`)
  - `tech-spec`: 99th percentile |Δ| = `0.020`, max = `0.020` (mean |Δ| = `0.0111`)
  - `design-doc`: 99th percentile |Δ| = `0.020`, max = `0.020` (mean |Δ| = `0.0021`)
  - `pr-description`: 99th percentile |Δ| = `0.040`, max = `0.040` (mean |Δ| = `0.0086`)
  - Overall 99th percentile across all presets is `0.030` (overall mean `0.0045`, max `0.040`), confirming that the default `0.10` threshold provides a robust statistical buffer (>2.5× to 3× empirical noise) against false regression alerts.
- **Truncation Guard**: If document truncation status differs between the baseline and current run (`was_truncated` mismatch), a warning is emitted on `stderr` because truncation shifts presence probabilities.
- **Diff Output**: Terminal tables, Markdown reports, and JSON exports display previous value, current value, and Δ (`prev: X (Δ -Y)`). Documents missing from the baseline are evaluated normally and marked `new`.
- **Input Validation**: Dry-run baselines (containing documents with `mock: true`) and baselines from another preset are rejected with a usage error (exit code 2).

### 8. Near-Threshold Indication (`near_threshold`)
Because run-to-run noise is up to about 0.030–0.040, values near a threshold (such as 0.51 against a threshold of 0.50) can flip between runs. `typesafe-eval` identifies borderline scores without affecting gate results or exit codes:

- **Questions & Candidates**: Covers both preset question scores/nouls (evaluated against `min_threshold` or `max_threshold`) and model-evaluated PII/secret candidates (`email_evaluations`, `phone_evaluations`, `ip_evaluations`, `url_evaluations`, `secret_evaluations` evaluated against candidate cutoff `0.5`, `CANDIDATE_DECISION_THRESHOLD = 0.5`). Candidates decided deterministically by rule stay `near_threshold: false`.
- **JSON Output**: Any question or candidate whose score or probability is within **±0.1** of its threshold gets `near_threshold: true` in JSON exports (`false` otherwise).
- **Table and Markdown Reports**: Near-threshold question values are marked with `~` (e.g. `51% ~`). Documents with near-threshold candidates display an explanatory line using placeholders: `~ near threshold: [EMAIL_1] personal (p=0.60), [URL_2] safe (p=0.46)`.
- **Constant Margin**: The margin (`0.1`) is a constant (`NEAR_THRESHOLD_MARGIN = 0.1`).
- **No Exit Code Change**: `near_threshold` is purely informational. A passing score near threshold still passes (exit code 0), and a failing score still fails (exit code 1).

### 9. Long Document Chunking for Presence Questions (v0.4.0)
When documents exceed `max_chars` (default: 25,000 characters, ~6,000–8,000 tokens), dropping the middle via truncation causes presence questions (such as checking whether a design doc contains a rollback plan) to suffer significant false degradation.

- **Overlapping Chunks for Noul**: For `Noul` presence questions, documents over `max_chars` are split into overlapping chunks (each within the character budget with 2,000-character overlap). Each chunk is evaluated, and the question takes the maximum probability across all chunks ("present if it is anywhere").
  > [!NOTE]
  > "Max over chunks" assumes a presence-style Noul ("is X anywhere in the document"). A custom Noul about the whole document (e.g. "Is the whole document written in English?") would be distorted when chunked, so custom configurations should use a `Score` or keep documents under `max_chars` for such questions.
- **API Calls Display**: The number of API calls per document is explicitly tracked and displayed in terminal tables (`(N calls)`), Markdown reports (`*(N calls)*`), and JSON exports (`api_calls: N`).
- **Baseline Truncation Warning**: `--baseline` warns when `was_truncated` differs between the baseline and current evaluation.

#### Known Limitation: Scores and Choices Are Not Chunked
- **Scores and Choices**: `Score` and `Choice` questions evaluate overall document quality or categorical choices where taking a `max` across slices would distort the metric. Therefore, Scores and Choices are **not** chunked; they retain head/tail truncation and keep `was_truncated: true`.
- If a document exceeds `max_chars`, only `Noul` presence questions are evaluated across overlapping chunks. Scores and Choices are evaluated on the head-and-tail truncated document with the middle dropped.

### 10. File Exclusions & Default Ignores (`--exclude`)
Exclude specific files, subdirectories, or glob patterns from evaluation:

```bash
# Exclude draft documents and templates
typesafe-eval docs/**/*.md --exclude "*.draft.md" -e "docs/templates/**"
```

- **Project Config Exclusions**: Set `exclude` patterns in `.typesafe-eval.yaml` or `pyproject.toml` (`[tool.typesafe-eval]`):
  ```yaml
  preset: quality
  exclude:
    - "*.draft.md"
    - "templates/**"
    - "archived/*.md"
  ```
- **Default Ignores**: Standard dependency, build, and cache directories (`.git`, `node_modules`, `.venv`, `venv`, `env`, `.env`, `__pycache__`, `.pytest_cache`, `.typesafe-eval-cache`, `.mypy_cache`, `.ruff_cache`, `build`, `dist`) are automatically skipped during glob resolution and git diff file matching.
- **Explicit Override**: Explicitly providing a non-glob path (e.g. `typesafe-eval node_modules/pkg/readme.md`) evaluates the file directly.
- **Python API Support**: `evaluate_documents(paths, preset="quality", exclude=["*.draft.md"])`.

### 11. Offline Rules-Only Mode (`--offline`)
Run deterministic safety, credential, and PII checks locally with zero external API calls:

```bash
typesafe-eval docs/*.md --preset safety --offline
```

- **Zero API Invocations**: Local evaluation relies strictly on rule-based patterns (known AWS/Slack/GitHub tokens, private keys, free-mail PII, phone numbers, private IPs) without contacting the TypeSafe System One API.
- **No API Key Required**: Fully functional in air-gapped environments, sandbox runners, or fork PRs without `TYPESAFE_API_KEY`.
- **Deterministic Gates**: Known credentials and individual free-mail addresses fail deterministically (exit code 1). Documents with ambiguous candidates that would normally query the model pass with contextual notices instead of failing.
- **Python API Support**: `evaluate(content, preset="safety", offline=True)` or `evaluate_documents(paths, offline=True)`.

### 12. Content-Addressable Result Caching (`--cache`)
Avoid redundant API calls and accelerate iterative local evaluations and CI workflows:

```bash
# Enable SHA-256 result caching
typesafe-eval docs/*.md --preset quality --cache

# Specify a custom cache directory (default: .typesafe-eval-cache)
typesafe-eval docs/*.md --preset quality --cache --cache-dir /tmp/my-eval-cache

# Clear the cached results
typesafe-eval cache clear
```

- **Content-Addressable Invalidation**: Cache keys are derived from document content SHA-256, active preset/config definition, model parameters, and options. Changing either document contents or preset rules automatically invalidates the entry.
- **CLI Subcommand**: Manage and prune cached artifacts via `typesafe-eval cache clear` (supports `--cache-dir`).
- **Python API Support**: `evaluate_documents(paths, preset="quality", cache=True, cache_dir=".typesafe-eval-cache")`.

### 13. GitHub Actions Workflow Annotations (`-f github`)
Generate native GitHub Actions workflow commands to display line-and-column inline annotations directly on pull request file diffs:

```bash
typesafe-eval docs/*.md --preset safety --format github
```

- **Workflow Command Syntax**: Emits standard GitHub Actions commands to `stdout`:
  ```
  ::error file=docs/auth.md,line=4,col=13::Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential
  ::warning file=docs/guide.md,line=12,col=1::Readability: Score 0.45 fell below threshold 0.60
  ```
- **Line & Column Precision**: Resolves exact line and 1-indexed column coordinates for redacted PII, exposed credentials, and document headings.
- **CI Native**: Clean `stdout` stream easily integrated into GitHub Actions workflow steps without custom comment scrapers.

### 14. Validation Command & Ablation Helper (`validate`)
`typesafe-eval validate` runs presets over fixed test documents defined in a `labels.yaml` file to verify preset calibration, detection rates, false alarms, and regression direction:

```bash
# Validate against fixed labels specification
typesafe-eval validate labels.yaml --runs 3

# Generate "one section removed" ablation variants and starter labels.yaml from a Markdown document:
typesafe-eval validate --ablate docs/design.md --ablate-preset design-doc
```

#### Labels File Format (`labels.yaml`)
```yaml
preset: design_doc          # or config: path/to/custom.yaml
runs: 3
criteria:
  min_detected: 9           # minimum required detections across absent expectations
  max_false_alarms: 0       # maximum allowed false alarms across present expectations
  max_neutral_delta: 0.05   # maximum allowed mean delta for neutral pairs
  min_degradation_drop: 0.1 # minimum required drop for degraded pairs
  group_by: kind            # optional: "kind" or "pair" (default: "pair")
  degradation_ci_upper_max: -0.1 # optional: upper 95% CI bound must be < this value for down groups
  neutral_ci_abs_max: 0.05       # optional: max(|lower|, |upper|) <= this value for neutral groups
  min_group_size: 6              # optional: groups with fewer pairs report numbers with passed: null and do not gate (default: 6)
  pair_guard_neutral_abs_max: 0.10 # optional: every neutral pair's |mean delta| <= this, every down pair's mean delta <= pair_guard_down_tolerance
  pair_guard_down_tolerance: 0.0   # optional: maximum mean delta allowed for a down pair in pair guard check (default: 0.0)
  report_only_kinds: [exploratory] # optional: list of kinds that are reported but do not gate
  per_pair_kinds: [paraphrase]   # optional: kinds evaluated per-pair on their own run CI inside group_by: kind
documents:
  - path: fixtures/design_doc/en.md
    expect: {goal: present, rollback: present, migration: present}
  - path: fixtures/design_doc/en_without_rollback.md
    expect: {rollback: absent}
pairs:
  - before: fixtures/quality/a.md
    after: fixtures/quality/a_shuffled.md
    expect: {clarity: down}
    kind: shuffle           # optional: pair group kind
    doc_id: doc_a           # optional: document identifier
    runs: 3                 # optional: per-pair run override
  - before: fixtures/quality/a.md
    after: fixtures/quality/a_paraphrased.md
    expect: {clarity: neutral}
    kind: paraphrase
    doc_id: doc_a
    runs: 10
```

### 15. Programmatic Python API

`typesafe-eval` can be integrated directly into Python applications, build scripts, or agent workflows:

```python
import typesafe_eval
from typesafe_eval import evaluate, evaluate_document, evaluate_documents
from typesafe_eval.exceptions import ContentViolationError, TypeSafeEvalError

# 1. In-memory content evaluation
result = evaluate(
    content="# Architecture\n\nSystem specification...",
    preset="tech-spec",
)
print(f"Passed: {result.passed_thresholds}, Score: {result.composite_score}")

# 2. File evaluation from disk
doc_result = evaluate_document(
    "docs/architecture.md",
    preset="quality",
    raise_on_violation=True,  # Raises ContentViolationError if gates fail
)

# 3. Parallel multi-document batch evaluation
batch_results = evaluate_documents(
    ["rfc/001.md", "rfc/002.md", "rfc/003.md"],
    preset="tech-spec",
    concurrency=4,
)
for res in batch_results:
    print(f"{res.filename}: {res.passed_thresholds}")
```

#### Typed Exceptions
All library errors inherit from `TypeSafeEvalError`:
- `ConfigurationError`: Invalid preset, bad document paths, or missing options.
- `AuthenticationError`: Missing or invalid `TYPESAFE_API_KEY`.
- `RuntimeEvalError`: Unrecoverable network or API failures.
- `ContentViolationError`: Raised when `raise_on_violation=True` and content fails safety or quality thresholds. Contains `.result` (single failure) and `.results` (list of failed results in batch operations).

### 16. Exit Codes & CI Integration

`typesafe-eval` returns distinct exit codes to allow CI pipelines and automated agents to distinguish quality/safety violations from system or configuration failures:

| Code | Meaning |
| :---: | :--- |
| `0` | All evaluated documents passed (also returned when threshold violations exist but `--no-fail-on-threshold` is set, and no runtime errors occurred). |
| `1` | At least one threshold violation occurred across evaluated documents (with `--fail-on-threshold`, which is enabled by default). |
| `2` | Usage or configuration error: no files specified, no files matched pattern, preset/config loading failure, or invalid CLI options. |
| `3` | Runtime error: TypeSafe API failure, network issue, missing or invalid `TYPESAFE_API_KEY`, question missing from API response, or file read error during evaluation. |

#### Precedence Rule (1 over 3)
When evaluating multiple files, evaluation continues across all remaining files even if an individual file encounters a runtime error. Errored files are reported on `stderr` (`<file>: <error>`), while successfully evaluated files are included in the normal output (table, JSON, or Markdown).

If **any** evaluated file has a threshold violation, the CLI exits with **code 1**, even if other files encountered runtime errors. A detected violation is certain and is not masked by subsequent runtime errors. Code 3 is returned only when runtime errors occur and **no** threshold violations were detected. Code 2 is determined before evaluation starts, so it never overlaps.

### 17. Output Formats (Table, Markdown, JSON, GitHub Annotations)
- **Table**: Interactive Rich terminal table with color-coded score badges, candidate near-threshold indicators, and violation panels.
- **Markdown**: Formatted table for GitHub Actions PR comments or issue updates (`--format markdown`).
- **JSON**: Machine-readable structured array for pipelines, baseline saves, and downstream tools (`--format json`).
- **GitHub Annotations**: Workflow command format for GitHub Actions inline PR diff annotations (`--format github`).

### 18. Pre-commit Hook & GitHub Action

#### Pre-commit Hook
Integrate `typesafe-eval` into your local git workflow via `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/s-0-a-r/typesafe-eval
    rev: v0.5.1
    hooks:
      - id: typesafe-eval
        args: ["--preset", "safety"]
```

#### GitHub Action
Automate document evaluation in CI using the composite action (`action.yml`):

```yaml
name: Document Evaluation
on: [push, pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install typesafe-eval
        run: pip install typesafe-eval
      - name: Run typesafe-eval Action
        uses: s-0-a-r/typesafe-eval@v0.5.1
        with:
          api-key: ${{ secrets.TYPESAFE_API_KEY }}
          preset: 'safety'
          files: '**/*.md'
```

#### Hosted Runners & Exit Code 3 Skip Behavior
On public repositories or fork PRs, runners without access to `TYPESAFE_API_KEY` (e.g. pre-commit.ci, fork pull requests) encounter exit code 3 (runtime/missing secret):
- The GitHub Action recognizes exit code 3 and **skips gracefully** (exit code 0 with an informative notice) to prevent blocking untrusted fork PRs.
- Actual content or security violations (exit code 1) **always fail the build**, enforcing strict quality and privacy guarantees.

### 19. Agent Integrations (Claude Code, Antigravity CLI, Codex)

`typesafe-eval` is designed to be agent-native, providing first-class integration for autonomous coding agents:

#### Claude Code Plugin (Skill + Safety Hook)
- **Skill**: Located at [`skills/typesafe-eval/SKILL.md`](skills/typesafe-eval/SKILL.md), guiding Claude Code on preset selection, interpreting the JSON contract, and adhering to evaluation boundaries.
- **Hook**: Configured in [`hooks/hooks.json`](hooks/hooks.json) via a `PostToolUse` matcher on `Write|Edit` that executes [`hooks/claude_safety_hook.py`](hooks/claude_safety_hook.py).
- **Exit Code Mapping**:
  - `Exit 1` (content violation) → mapped to `Exit 2` with violations on `stderr`, actively prompting Claude to resolve the security issue before completing the task.
  - `Exit 2/3` (tool/runtime error, or missing `TYPESAFE_API_KEY`) → mapped to `Exit 0`, ensuring Claude is never blocked when the external API key is unset.

#### AGENTS.md Guidance
A copy-pasteable repository guide is maintained in [`AGENTS.md`](AGENTS.md) for AI coding assistants (Google Antigravity CLI, OpenAI Codex, GitHub Copilot, Cursor, Aider). It outlines command invocations, exit code handling, and the 4 mandatory guidance rules:
1. **Don't make scores a loop target**: Cap revision loops at 2 rounds maximum; avoid butchering natural prose to game scores.
2. **Language caveat**: TypeSafe System One (Jev) accuracy is calibrated for English text.
3. **Near-threshold results are soft**: Borderline results (`near_threshold: true`, within ±0.10) are advisory and should be surfaced with probability ranges.
4. **Never pass API key through the agent**: Read `TYPESAFE_API_KEY` from the environment; never request keys in chat or pass them in arguments.

#### Antigravity Code Review Skill (`/boost`)
- **Workspace Skill**: Located at [`.agents/skills/code-review/SKILL.md`](.agents/skills/code-review/SKILL.md) and automatically discovered by Google Antigravity CLI.
- **Deep `/boost` Routine**: Guides autonomous agents to conduct multi-perspective reviews across 4 core pillars (Safety & Redaction, Contract & Streams, Evaluator Integrity & Rules, and Test Rigor).
- **Checklist**: Accompanied by a repository-specific [Domain Review Checklist](.agents/skills/code-review/references/checklist.md).

---

## ⚙️ Custom YAML Configuration

You can create project-specific evaluation dimensions by creating a YAML file (e.g. `eval_rules.yaml`):

```yaml
name: "proposal-eval"
title: "Project Proposal Evaluation"
description: "Evaluates business feasibility, ROI clarity, and risk."
sanitizer:
  role_emails:
    - "helpdesk"
    - "*-team"
    - "ops-*"
    - "contact-*"
questions:
  business_clarity:
    type: score
    label: "Business Clarity"
    instructions: "How clearly does the document describe the user problem and proposed solution?"
    criteria:
      - "Vague problem statement without clear target user"
      - "Identifies problem and solution but lacks market context"
      - "Crystal clear user pain point, proposed solution, and success metrics"
    weight: 0.5
    min_threshold: 0.7

  roi_justification:
    type: score
    label: "ROI Justification"
    instructions: "How compelling is the expected return on investment or resource efficiency?"
    criteria:
      - "No quantitative estimates or resource plans"
      - "Estimated effort, but returns/impact are speculative"
      - "Grounded cost-benefit analysis with concrete milestones"
    weight: 0.3
    min_threshold: 0.5

  has_security_review:
    type: noul
    label: "Security Review"
    instructions: "Does the document mention security review or privacy compliance?"
    weight: 0.2
    min_threshold: 0.5

  decision:
    type: choice
    label: "Recommendation"
    instructions: "What is the recommended next action for this proposal?"
    criteria:
      approve: "Ready for stakeholder review"
      revise: "Requires revision on business case or architecture"
      reject: "Not feasible in current scope"
```

Run with:
```bash
typesafe-eval proposals/*.md --config eval_rules.yaml
```

---

## 🧪 Testing

### Unit & Integration Suite
Run the full pytest suite:

```bash
pytest
```

### Mandatory Real CLI Acceptance Matrix (18 Items)
Autonomous agents and releases must verify all 18 Acceptance Criteria via real OS subprocess execution before opening PRs or merging releases:

```bash
# Standalone markdown/JSON acceptance matrix verification
python scripts/verify_ac.py

# Or via pytest acceptance marker
pytest -v -m acceptance
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
