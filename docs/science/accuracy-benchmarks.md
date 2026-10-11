# Multi-Provider Empirical Accuracy & Calibration

Empirical task-accuracy evaluation of TypeSafe System One (`jev-1.13.0`) and OpenAI Decisions API (`gpt-6-luna`) across the pre-registered benchmark corpus, compared against a non-LLM heading keyword baseline (`baseline_heuristic.py`).

---

## 1. Overview & Evaluation Methodology

Unlike tools that rely on uncalibrated prompt scores, `typesafe-eval` evaluates accuracy using strict pre-registration protocols defined in [`validation/corpus/PREREGISTRATION.md`](https://github.com/s-0-a-r/typesafe-eval/blob/main/validation/corpus/PREREGISTRATION.md):

- **Data Split**: Documents are partitioned into disjoint **Tuning** and **Held-out** sets across English and Japanese real-world engineering artifacts (Python PEPs, Rust RFCs, Go Design Drafts, Swift Evolution specs, public PR descriptions).
- **Metric Definitions**:
  - **Missing Flagged (Recall on Absences)**: Documents lacking an essential section that score $< 0.50$ across all runs.
  - **False Alarms**: Documents containing an essential section that erroneously score $< 0.50$ in at least one run.
  - **Near $0.50$ (Boundary Softness)**: Documents scoring within $[0.35, 0.65]$ where score fluctuations or threshold proximity make decisions fragile.
- **Reliability Criterion**: A checklist question is classified as **Reliable** on a split only if:
  1. All absent items are flagged ($100\%$ recall on absences in that split).
  2. Zero false alarms are emitted on present items ($0$ false alarms).
  3. Zero items score near the decision boundary ($0$ near $0.50$).
- **Sample Size Limitation**: The corpus contains small numbers of labeled documents (e.g., 3 absent specs for `tech-spec`, 2–3 absent documents for design docs). Passing a small test ($N=3$) confirms basic functionality, but **does not constitute statistical proof that the prompt cannot fail** on broader document sets.

---

## 2. Multi-Provider Checklist Verification Matrix

All evaluations were executed with identical pre-registered specification manifests (`validation/corpus/labels_*.yaml`) across two evaluation runs per document.

### Empirical Results: TypeSafe System One (`jev-1.13.0`)
*(Calibrated on model `jev-1.13.0`, October 2026)*

| Preset | Question | Tuning: Missing Flagged | Tuning: False Alarms | Held-out: Missing Flagged | Held-out: False Alarms | Near 0.5 | Empirical Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `design-doc` | `goal` | *no label* | 0/9 | *no label* | 0/4 | 0 / 0 | Recognizes stated goal only |
| `design-doc` | `non_goals` | 4/7 | 0/4 | 1/2 | 0/3 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `alternatives` | 2/2 | 0/5 | *no label* | 0/3 | 0 / 0 | **Reliable on corpus** ($N=2$) |
| `design-doc` | `risks` | 2/3 | 0/2 | 2/2 | 0/1 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `rollback` | 7/7 | 0/2 | 3/3 | *no label* | 0 / 0 | **Reliable on corpus** ($N=3$) |
| `design-doc` | `metrics` | 4/4 | 0/2 | 2/2 | 0/1 | 1 / 0 | **Not reliable** (near boundary) |
| `design-doc` | `migration` | 2/2 | 0/4 | 2/2 | *no label* | 1 / 0 | **Not reliable** (near boundary) |
| `design-doc` | `impact` | *no label* | *no label* | *no label* | 0/1 | 0 / 0 | Unmeasured |
| `design-doc` | `open_questions`| 4/4 | 0/4 | 3/3 | 0/1 | 0 / 0 | **Reliable on corpus** ($N=3$) |
| `design-doc` | `owner_timeline`| 4/4 | *no label* | *no label* | *no label* | 0 / 0 | Flags missing only |
| `pr-description` | `summary` | *no label* | 0/10 | *no label* | 0/6 | 0 / 1 | **Not reliable** (near boundary) |
| `pr-description` | `testing` | 3/3 | 0/4 | 2/2 | 0/2 | 0 / 0 | **Reliable on corpus** ($N=2$) |
| `pr-description` | `impact` | 1/1 | 0/6 | *no label* | 0/2 | 1 / 0 | **Not reliable** (near boundary) |
| `pr-description` | `breaking_changes` | 8/8 | 0/2 | 3/3 | 1/2 | 0 / 0 | **Not reliable** (false alarm on held-out) |
| `pr-description` | `related_issues`| 1/1 | 1/11 | 2/2 | 1/4 | 0 / 1 | **Not reliable** (false alarms) |
| `tech-spec` | `has_test_plan` | 3/3 | 0/5 | 3/3 | 0/1 | 0 / 0 | **Reliable on corpus** ($N=3$) |

---

### Empirical Results: OpenAI Decisions API (`gpt-6-luna`)
*(Calibrated via live OpenAI Decisions API, October 8, 2026)*

| Preset | Question | Tuning: Missing Flagged | Tuning: False Alarms | Held-out: Missing Flagged | Held-out: False Alarms | Near 0.5 | Empirical Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `design-doc` | `goal` | *no label* | 0/9 | *no label* | 0/4 | 0 / 0 | Recognizes stated goal only |
| `design-doc` | `non_goals` | 6/7 | 0/4 | 2/2 | 0/3 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `alternatives` | 2/2 | 0/5 | *no label* | 0/3 | 0 / 0 | **Reliable on corpus** ($N=2$) |
| `design-doc` | `risks` | 3/3 | 0/2 | 1/2 | 0/1 | 0 / 0 | **Not reliable** (misses 1/2 held-out) |
| `design-doc` | `rollback` | 7/7 | 0/2 | 3/3 | *no label* | 0 / 0 | **Reliable on corpus** ($N=3$) |
| `design-doc` | `metrics` | 4/4 | 1/2 | 2/2 | 0/1 | 0 / 0 | **Not reliable** (false alarm in tuning) |
| `design-doc` | `migration` | 2/2 | 1/4 | 2/2 | *no label* | 0 / 0 | **Not reliable** (false alarm in tuning) |
| `design-doc` | `impact` | *no label* | *no label* | *no label* | 0/1 | 0 / 0 | Recognizes stated item only |
| `design-doc` | `open_questions`| 4/4 | 0/4 | 3/3 | 0/1 | 0 / 0 | **Reliable on corpus** ($N=3$) |
| `design-doc` | `owner_timeline`| 4/4 | *no label* | *no label* | *no label* | 0 / 0 | Flags missing only |
| `pr-description` | `summary` | *no label* | 0/10 | *no label* | 0/6 | 0 / 0 | Recognizes stated item only |
| `pr-description` | `testing` | 3/3 | 0/4 | 2/2 | 0/2 | 0 / 0 | **Reliable on corpus** ($N=2$) |
| `pr-description` | `impact` | 1/1 | 0/6 | *no label* | 0/2 | 0 / 0 | **Reliable on corpus** ($N=1$) |
| `pr-description` | `breaking_changes` | 8/8 | 1/2 | 3/3 | 1/2 | 0 / 0 | **Not reliable** (false alarms) |
| `pr-description` | `related_issues`| 1/1 | 1/11 | 2/2 | 1/4 | 0 / 0 | **Not reliable** (false alarms) |
| `tech-spec` | `has_test_plan` | 3/3 | 0/5 | 3/3* | 0/1 | 0 / 0 | **Post-hoc adjusted** (see Caveat below) |

*\*Note on `tech-spec: has_test_plan` for OpenAI*: Under the original pre-registered prompt, OpenAI missed `swift-se-0510` in held-out ($p=0.75$, 2/3 flagged). When the prompt was adjusted post-hoc to require an explicit dedicated section, `swift-se-0510` moved to $p=0.00$. Under pre-registration rules, this result is an in-sample tuning observation, not a pre-registered held-out validation.

---

## 3. Heuristic Baseline Comparison: What Does an LLM Actually Add?

To answer whether an LLM is necessary for checklist gating or if a simple regular expression suffices, we compare the LLM results against `baseline_heuristic.py` (a zero-API-call script that inspects Markdown headings for standard keywords and length):

| Preset / Split | Checklist Item | Heuristic Regex (Absent Detected) | Heuristic Regex (False Alarms) | LLM Decisions API (Absent Detected) | LLM Decisions API (False Alarms) | Analysis: Value Added by LLM |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `tech-spec` held-out | `has_test_plan` | **3/3** | **0/1** | **3/3\*** | **0/1** | **None on structured docs**: Simple keyword heading regex matches LLM performance on specs with canonical headings. |
| `design-doc` held-out | `rollback` | **3/3** | **0/0** | **3/3** | **0/0** | **None on structured docs**: Standard rollback headings are matched equally well by keyword regex. |
| `design-doc` held-out | `alternatives` | *no label* | **0/3** | *no label* | **0/3** | **None on structured docs**: Regex produces zero false alarms on standard headings. |
| `pr-description` held-out | `testing` | **1/1** | **1/1** (50% error) | **2/2** | **0/2** (0% error) | **Significant**: PR descriptions frequently explain testing in bullet points or inline prose without explicit `# Testing` headings. Regex emits false alarms; LLM correctly understands context. |
| `design-doc_ja` held-out | `open_questions` | *no label* | **1/1** (false alarm) | *no label* | **0/1** (clean pass) | **Moderate**: Regex fails on Japanese synonym/phrasing variations; LLM accurately interprets conversational Japanese headings. |
| `design-doc` held-out | `non_goals` | 2/2 | 0/2 | 2/2 | 0/3 | **Neither is reliable**: Conceptual presence (determining if scope is truly defined vs. mentioned) is uncalibrated on both regex and LLM. |
| `design-doc` held-out | `risks` | 2/2 | 0/0 | 1/2 | 0/1 | **Neither is reliable**: LLM actually missed 1 held-out risk section that regex captured by keyword. |

### Key Takeaway on LLMs vs. Grep:
1. **On Structured Specifications (PEPs, RFCs, Architecture Docs)**: Documents adhering to standard heading templates (e.g. `## Alternatives`, `## Rollback Plan`) do not strictly require an LLM for presence verification; a simple regex heuristic performs almost identically at zero latency and zero token cost.
2. **On Unstructured Prose & PR Descriptions**: The LLM provides genuine value in informal text (such as pull request descriptions or freeform RFCs), where testing strategies and design discussions are written in prose rather than standardized markdown headings. Grep produces false alarms in these contexts, whereas the LLM reliably understands semantic intent.
3. **On Nuanced Presence Checks (`non_goals`, `risks`)**: Neither LLMs nor keyword heuristics currently achieve reliable detection without human oversight.

---

## 4. Preregistration Integrity & Scientific Caveats

1. **`has_test_plan` Prompt Adjustment**:
   - On 2026-10-08, `swift-se-0510` in `labels_tech_spec.heldout.yaml` scored $p=0.75$ on OpenAI. The prompt was revised to clarify that a dedicated section or explicit statement is required.
   - Because this adjustment occurred after observing the held-out failure, it represents **post-hoc alignment**. Per [`PREREGISTRATION.md`](https://github.com/s-0-a-r/typesafe-eval/blob/main/validation/corpus/PREREGISTRATION.md), true held-out confirmation requires testing on newly collected specifications.
2. **Small Sample Sizes**:
   - Absent sample sizes in the corpus range from $N=2$ to $N=7$ per question. Users must treat "Reliable" designations as indicators that a question survived initial testing, not as an asymptotic guarantee of 100% accuracy.
3. **Language Scope**:
   - Evaluated corpora are predominantly English. Non-English (Japanese) evaluations are preliminary and limited to small fixture sets.

---

## 5. Recommended CI Gating Strategy

1. **Hard CI Gating (Block on Failure)**:
   - Use deterministic offline safety checks (`--preset safety --offline`) to block exposed credentials, personal mobile numbers, and personal emails.
   - For architecture design docs, gate only on universally reliable items (`alternatives`, `rollback`, `open_questions`).
2. **Advisory Display (Warnings Only)**:
   - Treat `non_goals`, `risks`, `migration`, `metrics`, and PR `summary` as advisory notices for human reviewers rather than hard gating failures.
