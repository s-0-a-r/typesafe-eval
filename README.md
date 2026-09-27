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
  - Context length guard with safe head-tail truncation to prevent context overflows.
- **Multiple Output Formats**: Rich interactive terminal tables, JSON (for pipelines/APIs), and Markdown reports (for GitHub PRs/issues).
- **CI/CD Ready**: Automatic non-zero exit codes when documents fail minimum quality or maximum risk thresholds.

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

- `scores`: Map of score questions with `score`, `max_score`, `normalized_score`, and `confidence`.
- `nouls`: Map of noul questions with calibrated probability and override transparency:
  - `probability`: Calibrated probability returned by the model (`null` if omitted or uncalled).
  - `overridden_by`: Set to `"preflight_scan"` when deterministic regex pre-flight masking caught exposed credentials (for questions bound to `preflight: credentials`) or personal PII (for `preflight: pii`, ignoring generic role emails like `support@company.com`). Overridden questions continue to contribute their model probability to `composite_score` when present, while independently failing the evaluation gate.
- `choices`: Map of choice questions with selected `choice` and `confidence`.
- `passed_thresholds`: Boolean indicating whether all score/risk gates and pre-flight scans passed.
- `violations`: List of descriptive failure messages explaining any gate violations or pre-flight overrides.

### 5. Dry-Run Mode (Validation without Calling API)
```bash
typesafe-eval docs/*.md --dry-run
```

### 6. List Built-in Presets
```bash
typesafe-eval --list-presets
```

---

## ⚙️ Custom YAML Configuration

You can create project-specific evaluation dimensions by creating a YAML file (e.g. `eval_rules.yaml`):

```yaml
name: "proposal-eval"
title: "Project Proposal Evaluation"
description: "Evaluates business feasibility, ROI clarity, and risk."
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
