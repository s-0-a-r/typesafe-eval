# Quality Preset (`quality`)

The `quality` preset evaluates general documentation, guides, READMEs, and technical articles for clarity, completeness, and practical utility.

---

## Dimensions Evaluated

| Dimension | Description | Threshold | Type | Role |
| :--- | :--- | :---: | :---: | :---: |
| `clarity` | How clear, well-structured, and easy to follow is this document? | $\ge 0.60$ | Score | Warning (advisory) |
| `tone` | What is the primary stylistic tone of this document? (`professional`, `informal`, `inconsistent`) | N/A | Choice | Informational |

> [!NOTE]
> In the built-in `quality` preset, `thresholds_as_warnings: true` is configured. Clarity threshold regressions emit non-blocking warnings rather than causing immediate gate failures.

---

## Usage Example

```bash
typesafe-eval docs/*.md --preset quality
```

Sample JSON response:
```json
[
  {
    "schema_version": "1.0",
    "filepath": "docs/architecture.md",
    "filename": "architecture.md",
    "preset_name": "quality",
    "passed_thresholds": true,
    "composite_score": 0.85,
    "scores": {
      "clarity": {
        "score": 0.85,
        "max_score": 1.0,
        "normalized_score": 0.85,
        "confidence": 0.92,
        "probabilities": {
          "1": 0.02,
          "2": 0.13,
          "3": 0.85
        },
        "near_threshold": false
      }
    },
    "choices": {
      "tone": {
        "choice": "professional",
        "confidence": 0.95,
        "probabilities": {
          "professional": 0.95,
          "informal": 0.04,
          "inconsistent": 0.01
        }
      }
    },
    "violations": [],
    "warnings": []
  }
]
```

---

## Near-Threshold Observations

When scores fall within $\pm 0.10$ of the decision boundary ($0.40 \le p \le 0.60$), `typesafe-eval` annotates them with `near_threshold: true`.
Autonomous agents and human reviewers should treat near-threshold scores as soft observations rather than hard failures, considering run-to-run variance (see [Noise Calibration](../science/noise-calibration.md)).
