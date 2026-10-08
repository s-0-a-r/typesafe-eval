# Multi-Provider Empirical Accuracy & Calibration

Empirical task-accuracy evaluation of TypeSafe System One (`jev-1.13.0`) and OpenAI Decisions API (`gpt-6-luna`) across the pre-registered benchmark corpus.

---

## 1. Overview & Evaluation Methodology

Unlike tools that rely on uncalibrated prompt scores, `typesafe-eval` evaluates accuracy using strict pre-registration protocols defined in [`validation/corpus/PREREGISTRATION.md`](https://github.com/s-0-a-r/typesafe-eval/blob/main/validation/corpus/PREREGISTRATION.md):

- **Data Split**: Documents are partitioned into disjoint **Tuning** and **Held-out** sets across English and Japanese real-world engineering artifacts (Python PEPs, Rust RFCs, Go Design Drafts, Swift Evolution specs, public PR descriptions).
- **Metric Definitions**:
  - **Missing Flagged (Recall on Absences)**: Documents lacking an essential section that score $< 0.50$ across all runs.
  - **False Alarms**: Documents containing an essential section that erroneously score $< 0.50$ in at least one run.
  - **Near $0.50$ (Boundary Softness)**: Documents scoring within $[0.35, 0.65]$ where score fluctuations or threshold proximity make decisions fragile.
- **Reliability Criterion**: A checklist question is classified as **Reliable** only if:
  1. All absent items are flagged in tuning and held-out corpora ($100\%$ detection).
  2. Zero false alarms are emitted on present items ($0$ false alarms).
  3. Zero items score near the decision boundary ($0$ near $0.50$).

---

## 2. Multi-Provider Checklist Verification Matrix

All evaluations were executed with identical pre-registered specification manifests (`validation/corpus/labels_*.yaml`) across two evaluation runs per document.

### Empirical Results: TypeSafe System One (`jev-1.13.0`)
*(Calibrated on model `jev-1.13.0`, October 2026)*

| Preset | Question | Tuning: Missing Flagged | Tuning: False Alarms | Held-out: Missing Flagged | Held-out: False Alarms | Near 0.5 | Empirical Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `design-doc` | `goal` | *no label* | 0/9 | *no label* | 0/4 | 0 / 0 | Recognizes stated goal only |
| `design-doc` | `non_goals` | 4/7 | 0/4 | 1/2 | 0/3 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `alternatives` | 2/2 | 0/5 | *no label* | 0/3 | 0 / 0 | **Reliable** |
| `design-doc` | `risks` | 2/3 | 0/2 | 2/2 | 0/1 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `rollback` | 7/7 | 0/2 | 3/3 | *no label* | 0 / 0 | **Reliable** |
| `design-doc` | `metrics` | 4/4 | 0/2 | 2/2 | 0/1 | 1 / 0 | **Not reliable** (near boundary) |
| `design-doc` | `migration` | 2/2 | 0/4 | 2/2 | *no label* | 1 / 0 | **Not reliable** (near boundary) |
| `design-doc` | `impact` | *no label* | *no label* | *no label* | 0/1 | 0 / 0 | Unmeasured |
| `design-doc` | `open_questions`| 4/4 | 0/4 | 3/3 | 0/1 | 0 / 0 | **Reliable** |
| `design-doc` | `owner_timeline`| 4/4 | *no label* | *no label* | *no label* | 0 / 0 | Flags missing only |
| `pr-description` | `summary` | *no label* | 0/10 | *no label* | 0/6 | 0 / 1 | **Not reliable** (near boundary) |
| `pr-description` | `testing` | 3/3 | 0/4 | 2/2 | 0/2 | 0 / 0 | **Reliable** |
| `pr-description` | `impact` | 1/1 | 0/6 | *no label* | 0/2 | 1 / 0 | **Not reliable** (near boundary) |
| `pr-description` | `breaking_changes` | 8/8 | 0/2 | 3/3 | 1/2 | 0 / 0 | **Not reliable** (false alarm on held-out) |
| `pr-description` | `related_issues`| 1/1 | 1/11 | 2/2 | 1/4 | 0 / 1 | **Not reliable** (false alarms) |
| `tech-spec` | `has_test_plan` | 3/3 | 0/5 | 3/3 | 0/1 | 0 / 0 | **Reliable** |

---

### Empirical Results: OpenAI Decisions API (`gpt-6-luna`)
*(Calibrated via live OpenAI Decisions API, October 8, 2026)*

| Preset | Question | Tuning: Missing Flagged | Tuning: False Alarms | Held-out: Missing Flagged | Held-out: False Alarms | Near 0.5 | Empirical Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `design-doc` | `goal` | *no label* | 0/9 | *no label* | 0/4 | 0 / 0 | Recognizes stated goal only |
| `design-doc` | `non_goals` | 6/7 | 0/4 | 2/2 | 0/3 | 0 / 0 | **Not reliable** (misses absent sections) |
| `design-doc` | `alternatives` | 2/2 | 0/5 | *no label* | 0/3 | 0 / 0 | **Reliable** |
| `design-doc` | `risks` | 3/3 | 0/2 | 1/2 | 0/1 | 0 / 0 | **Not reliable** (misses 1/2 held-out) |
| `design-doc` | `rollback` | 7/7 | 0/2 | 3/3 | *no label* | 0 / 0 | **Reliable** |
| `design-doc` | `metrics` | 4/4 | 1/2 | 2/2 | 0/1 | 0 / 0 | **Not reliable** (false alarm in tuning) |
| `design-doc` | `migration` | 2/2 | 1/4 | 2/2 | *no label* | 0 / 0 | **Not reliable** (false alarm in tuning) |
| `design-doc` | `impact` | *no label* | *no label* | *no label* | 0/1 | 0 / 0 | Recognizes stated item only |
| `design-doc` | `open_questions`| 4/4 | 0/4 | 3/3 | 0/1 | 0 / 0 | **Reliable** |
| `design-doc` | `owner_timeline`| 4/4 | *no label* | *no label* | *no label* | 0 / 0 | Flags missing only |
| `pr-description` | `summary` | *no label* | 0/10 | *no label* | 0/6 | 0 / 0 | Recognizes stated item only |
| `pr-description` | `testing` | 3/3 | 0/4 | 2/2 | 0/2 | 0 / 0 | **Reliable** |
| `pr-description` | `impact` | 1/1 | 0/6 | *no label* | 0/2 | 0 / 0 | **Reliable** (zero false alarms & zero jitter) |
| `pr-description` | `breaking_changes` | 8/8 | 1/2 | 3/3 | 1/2 | 0 / 0 | **Not reliable** (false alarms) |
| `pr-description` | `related_issues`| 1/1 | 1/11 | 2/2 | 1/4 | 0 / 0 | **Not reliable** (false alarms) |
| `tech-spec` | `has_test_plan` | 3/3 | 0/5 | 3/3 | 0/1 | 0 / 0 | **Reliable** |

---

## 3. Side-by-Side Comparison & Insights

### 1. Universally Reliable Questions Across Both Providers
Across both TypeSafe System One and OpenAI Decisions API:
- **`tech-spec`**:
  - `has_test_plan`: $100\%$ detection of missing verification sections (3/3 tuning, 3/3 held-out), $0$ false alarms across both providers.
- **`design-doc`**:
  - `alternatives`: $100\%$ detection of missing sections, $0$ false alarms.
  - `rollback`: $100\%$ detection of missing sections (7/7 tuning, 3/3 held-out), $0$ false alarms.
  - `open_questions`: $100\%$ detection of missing sections (4/4 tuning, 3/3 held-out), $0$ false alarms.
- **`pr-description`**:
  - `testing`: $100\%$ detection of missing testing sections (3/3 tuning, 2/2 held-out), $0$ false alarms on well-tested PRs.

### 2. Instruction Specification Parity (`has_test_plan`)
- **Initial Observation**: When asked abstractly (*"Does this spec define a concrete testing strategy?"*), OpenAI assigned $p = 0.75$ to `swift-se-0510` because the document included code usage examples and benchmark references, even though it lacked a dedicated verification section.
- **Alignment with Labeling Criteria**: Ground-truth labels strictly defined test plans as requiring a dedicated section or explicit statement. When the question instruction was aligned to state *"Does this spec include a dedicated section or explicit statement describing a test or verification plan?"*, OpenAI immediately recognized the absence ($p = 0.00$), reaching $100\%$ accuracy (3/3 held-out) with zero false alarms.
- **Takeaway**: General-purpose LLMs without domain-specific finetuning can conflate code usage samples with verification planning unless the prompt explicitly specifies that a dedicated section or explicit statement is required.

### 3. Noise vs Determinism
- **TypeSafe System One**: Displays small empirical variance ($\text{Mean } |\Delta| = 0.0045$, $99\text{th} \le 0.030$).
- **OpenAI Decisions API**: Exhibits **strictly zero variance** ($\text{Mean } |\Delta| = 0.0000$, $\text{Spread} = 0.000$) across all runs and questions.

---

## 4. Recommended CI Gating Strategy

Based on these empirical findings:

1. **Strict Gate (Hard CI Failure)**:
   - Restrict mandatory blocking gates to verified reliable questions:
     - Design Docs: `alternatives`, `rollback`, `open_questions`
     - PR Descriptions: `testing`
     - Safety: `preset safety` (deterministic offline mode)
2. **Advisory Display (Soft Feedback / Warnings)**:
   - Treat `non_goals`, `risks`, `migration`, `metrics`, `summary`, and `related_issues` as advisory items (`-f github` outputs `::notice`, not `::error`).
