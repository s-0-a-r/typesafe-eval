# typesafe-eval

[![CI](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/s-0-a-r/typesafe-eval/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/s-0-a-r/typesafe-eval)](https://github.com/s-0-a-r/typesafe-eval/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Fast, typed, multi-dimensional document evaluation CLI powered by the **TypeSafe System One API** (model: `jev-1.13.0`).

---

## ✨ Features

- **Typed System One Judgments**: Uses TypeSafe primitives (`Score`, `Noul`, `Choice`) to evaluate documents with calibrated probabilities and confidence scores.
- **Batched Single-Call Evaluation**: Packs all dimension questions for a document into a single API call. Splitting them re-sends the document once per question, so token cost grows roughly with the number of questions (~3.8× lower token cost and ~4× lower latency for 4-question built-in presets; around 10–12× with 13 questions, as shown in [TypeSafe's parallel questions benchmark](https://docs.typesafe.ai/cookbooks/parallel_questions)).
- **Built-in & Custom Presets**:
  - `quality`: Clarity, completeness, actionability, and tone.
  - `safety`: PII, exposed credentials, confidentiality risk, policy compliance.
  - `tech-spec`: Technical depth, failure mode coverage, test planning, implementation readiness.
  - Custom YAML: Define your own criteria with custom weights and thresholds.
- **Deterministic Composite Scoring**: Code owns the workflow. Composite scores and pass/fail gate checks are synthesized in Python, not hallucinated by generative models.
- **Data Protection & Guardrails**:
  - Automatic pre-flight regex masking for API keys, bearer tokens, and emails.
  - Context length guard and overlapping chunking for long documents to preserve presence detection without token overflow.
- **Multiple Output Formats**: Rich interactive terminal tables, JSON (for pipelines/APIs), and Markdown reports (for GitHub PRs/issues).
- **CI/CD Ready**: Distinct exit codes (`0` pass, `1` violation, `2` usage/config error, `3` runtime error) with precedence of violations over runtime errors.

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
# Evaluate all Markdown files in docs/ using the quality preset
typesafe-eval docs/*.md --preset quality

# Alias command is also available:
jev-eval docs/*.md --preset quality
```

### 2. Screen for Sensitive Information & Policy Violations
```bash
typesafe-eval specs/*.txt --preset safety
```

### 3. Evaluate Architecture Specs / PR Descriptions
```bash
typesafe-eval rfc/*.md --preset tech-spec --format markdown --out eval_report.md
```

### 4. Output as JSON for Pipeline / Tooling Integration
```bash
typesafe-eval docs/memo.md --preset quality --format json
```

#### JSON Output & Result Schema

When exporting results with `--format json`, each document evaluation result contains:

- `scores`: Map of score questions with `score`, `max_score`, `normalized_score`, `confidence`, and `near_threshold`.
- `nouls`: Map of noul questions with calibrated probability, override transparency, and `near_threshold`:
  - `probability`: Calibrated probability returned by the model (`null` if omitted or uncalled).
  - `overridden_by`: Set to `"preflight_scan"` when deterministic regex pre-flight masking caught exposed credentials (for questions bound to `preflight: credentials`) or personal PII (for `preflight: pii`, ignoring generic role emails like `support@company.com`). Overridden questions continue to contribute their model probability to `composite_score` when present, while independently failing the evaluation gate.
  - `near_threshold`: Boolean indicating whether the probability is within ±0.1 of its threshold.
- `choices`: Map of choice questions with selected `choice` and `confidence`.
- `email_evaluations`: List of evaluated email addresses with placeholder, question ID, structural features, outcome (`personal` or `role`), and decision source (`model` or `free_mail`).
- `passed_thresholds`: Boolean indicating whether all score/risk gates and pre-flight scans passed.
- `violations`: List of descriptive failure messages explaining any gate violations or pre-flight overrides.

### 5. Context-Aware PII and Secrets Evaluation (v0.4.0)

`typesafe-eval` utilizes a candidate-level context-aware evaluation architecture for PII and secrets:
1. **Numbered Placeholders**: Replaces detected candidates with numbered placeholders (`[EMAIL_n]`, `[PHONE_n]`, `[IP_n]`, `[URL_n]`, `[SECRET_n]`).
2. **Metadata in State**: Extracts objective structural features into `state` (e.g., `state.redacted_emails`, `state.redacted_phones`, `state.redacted_ips`, `state.redacted_urls`, `state.redacted_secrets`).
3. **Strict Safety Constraint**: `state.redacted_secrets` NEVER contains raw secret values, value fragments, or hashes—only non-sensitive metadata (key name, value length, character classes, syntax flags, location).
4. **Rule-Based Fast Paths**:
   - **Known Credential Formats** (AWS `AKIA…`, GitHub `ghp_…`, Slack `xox…`, private keys, live API keys): FAIL deterministically by code (`decided_by: "rule"`). Jev is not asked. Known documentation example keys (e.g. `AKIAIOSFODNN7EXAMPLE`) are allowed and PASS by code.
   - **Template & Example Placeholders**: Values matching placeholder syntax (`${…}`, `<…>`, `xxx`, `changeme`) PASS deterministically by code.
   - **Documentation & Loopback IPs**: Documentation ranges (RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`; RFC 3849: `2001:db8::/32`) and loopback (`127.0.0.1`, `::1`) PASS by code as non-sensitive.
   - **Example & Public Domains**: Example domains (RFC 2606: `example.com`, `example.org`, `example.net`, `.test`, `.example`, `localhost`) and public platforms (e.g. `github.com`) PASS by code.
   - **Free-mail Addresses**: Free-mail providers (`gmail.com`, `yahoo.com`, `icloud.com`, etc.) deterministically fail as personal PII (`decided_by: "free_mail"`).
5. **Parallel Per-Candidate Evaluation**: Ambiguous candidates (e.g. corporate emails, private IPs, internal TLDs like `.internal`/`.corp`, switchboard vs personal phones, ambiguous `key=val` secrets) are evaluated via parallel `Noul` questions, allowing the model to make contextual determinations based on surrounding document text.
6. **Decoupled Detection from Masking**:
   - Detection, feature extraction, and candidate questions **always run**, even when `--no-mask` is passed.
   - `--no-mask` controls only whether sensitive values are substituted in the document text sent to the API.
   - With `--no-mask`, deterministic rules still apply (e.g. `support@gmail.com` and exposed credentials still fail by rule).

> [!TIP]
> **CI Recommendation**: `typesafe-eval` is designed for semantic context evaluation and policy compliance. For deep commit-history and repository-level secret scanning, we recommend pairing `typesafe-eval` with dedicated scanners like [gitleaks](https://github.com/gitleaks/gitleaks) in your CI pipeline.

#### Known Limitations
- **Context-Free Isolated Addresses**: When an address appears without surrounding context (e.g. `Forward to yamada@acme-corp.com`), the model relies solely on structural features. Accuracy may vary when neither role keywords nor individual context are present.

### 6. Dry-Run Mode (Validation without Calling API)
```bash
typesafe-eval docs/*.md --dry-run
```

### 7. List Built-in Presets
```bash
typesafe-eval --list-presets
```

### 8. Exit Codes & CI Integration

`typesafe-eval` returns distinct exit codes to allow CI pipelines and automated agents to distinguish quality/safety violations from system or configuration failures:

| Code | Meaning |
| :---: | :--- |
| `0` | All evaluated documents passed (also returned when threshold violations exist but `--no-fail-on-threshold` is set, and no runtime errors occurred). |
| `1` | At least one threshold violation occurred across evaluated documents (with `--fail-on-threshold`, which is enabled by default). |
| `2` | Usage or configuration error: no files specified, no files matched pattern, preset/config loading failure, or invalid CLI options. |
| `3` | Runtime error: TypeSafe API failure, network issue, missing or invalid `TYPESAFE_API_KEY`, or file read error during evaluation. |

#### Precedence Rule (1 over 3)
When evaluating multiple files, evaluation continues across all remaining files even if an individual file encounters a runtime error. Errored files are reported on `stderr` (`<file>: <error>`), while successfully evaluated files are included in the normal output (table, JSON, or Markdown).

If **any** evaluated file has a threshold violation, the CLI exits with **code 1**, even if other files encountered runtime errors. A detected violation is certain and is not masked by subsequent runtime errors. Code 3 is returned only when runtime errors occur and **no** threshold violations were detected. Code 2 is determined before evaluation starts, so it never overlaps.

### 9. Validation Command & Ablation Helper (`validate`)

`typesafe-eval validate` runs presets over fixed test documents defined in a `labels.yaml` file to verify preset calibration, detection rates, false alarms, and regression direction:

```bash
# Validate against fixed labels specification
typesafe-eval validate labels.yaml --runs 3

# Generate "one section removed" ablation variants and starter labels.yaml from a Markdown document:
typesafe-eval validate --ablate docs/design.md --ablate-preset design_doc
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
documents:
  - path: fixtures/design_doc/en.md
    expect: {goal: present, rollback: present, migration: present}
  - path: fixtures/design_doc/en_without_rollback.md
    expect: {rollback: absent}
pairs:
  - before: fixtures/quality/a.md
    after: fixtures/quality/a_shuffled.md
    expect: {clarity: down}
  - before: fixtures/quality/a.md
    after: fixtures/quality/a_paraphrased.md
    expect: {clarity: neutral}
```

### 10. Baseline Regression Detection (`--baseline`)

A fixed absolute threshold cannot reliably catch subtle quality degradation between document edits. `typesafe-eval` provides `--baseline` mode to detect score drops against previous evaluation results:

```bash
# Save baseline evaluation to JSON
typesafe-eval docs/*.md --preset quality --format json --out baseline.json

# Check modified documents against previous baseline
typesafe-eval docs/*.md --preset quality --baseline baseline.json
```

- **Regression Thresholds**: A question whose score or probability drops by more than its threshold triggers a regression violation (exit 1). The default threshold is `0.10`, overridable per question in custom YAML via `max_drop`.
- **Empirical Noise Calibration**: In noise measurements across 3 documents × 10 runs on each built-in preset (90 evaluations, 1,215 pairwise comparisons), run-to-run noise was:
  - `quality`: 99th percentile |Δ| = `0.020`, max = `0.020`
  - `safety`: 99th percentile |Δ| = `0.030`, max = `0.040`
  - `tech-spec`: 99th percentile |Δ| = `0.030`, max = `0.050`
  - Overall 99th percentile is `0.030` (max `0.050`), confirming that the default `0.10` threshold provides a safe buffer (>3× empirical noise) against false regression alerts.
- **Truncation Guard**: If document truncation status differs between the baseline and current run (`was_truncated` mismatch), a warning is emitted on `stderr` because truncation shifts presence probabilities.
- **Diff Output**: Terminal tables, Markdown reports, and JSON exports display previous value, current value, and Δ (`prev: X (Δ -Y)`). Documents missing from the baseline are evaluated normally and marked `new`.

### 11. Near-Threshold Indication (`near_threshold`)

Because run-to-run noise is up to about 0.055, values near a threshold (such as 0.51 against a threshold of 0.50) can flip between runs. `typesafe-eval` identifies borderline scores without affecting gate results or exit codes:

- **Questions & Candidates**: Covers both preset question scores/nouls (evaluated against `min_threshold` or `max_threshold`) and model-evaluated PII/secret candidates (`email_evaluations`, `phone_evaluations`, `ip_evaluations`, `url_evaluations`, `secret_evaluations` evaluated against the candidate cutoff `0.5`, `CANDIDATE_DECISION_THRESHOLD = 0.5`). Candidates decided deterministically by rule stay `near_threshold: false`.
- **JSON Output**: Any question or candidate whose score or probability is within **±0.1** of its threshold gets `near_threshold: true` in JSON exports (`false` otherwise).
- **Table and Markdown Reports**: Near-threshold question values are marked with `~` (e.g. `51% ~`). Documents with near-threshold candidates display an explanatory line using placeholders: `~ near threshold: [EMAIL_1] personal (p=0.60), [URL_2] safe (p=0.46)`.
- **Constant Margin**: The margin (`0.1`) is a constant (`NEAR_THRESHOLD_MARGIN = 0.1`). It is not a CLI option in v0.4.0.
- **No Exit Code Change**: `near_threshold` is purely informational. A passing score near threshold still passes (exit code 0), and a failing score still fails (exit code 1).

### 12. Long Document Chunking for Presence Questions (v0.4.0)

When documents exceed `max_chars` (default: 25,000 characters, ~6,000–8,000 tokens), dropping the middle via truncation causes presence questions (such as checking whether a design doc contains a rollback plan) to suffer significant false degradation.

- **Overlapping Chunks for Noul**: For `Noul` presence questions, documents over `max_chars` are split into overlapping chunks (each within the character budget with 2,000-character overlap). Each chunk is evaluated, and the question takes the maximum probability across all chunks ("present if it is anywhere").
  > [!NOTE]
  > "Max over chunks" assumes a presence-style Noul ("is X anywhere in the document"). A custom Noul about the whole document (e.g. "Is the whole document written in English?") would be distorted when chunked, so custom configurations should use a `Score` or keep documents under `max_chars` for such questions.
- **API Calls Display**: The number of API calls per document is explicitly tracked and displayed in terminal tables (`(N calls)`), Markdown reports (`*(N calls)*`), and JSON exports (`api_calls: N`).
- **Baseline Truncation Warning**: `--baseline` warns when `was_truncated` differs between the baseline and current evaluation.

#### Known Limitation: Scores and Choices Are Not Chunked
- **Scores and Choices**: `Score` and `Choice` questions evaluate overall document quality or categorical choices where taking a `max` across slices would distort the metric. Therefore, Scores and Choices are **not** chunked; they retain head/tail truncation and keep `was_truncated: true`.

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

```bash
pytest
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
