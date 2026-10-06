# Quality Preset (`quality`)

The `quality` preset evaluates general documentation, guides, READMEs, and technical articles for clarity, completeness, and practical utility.

---

## Dimensions Evaluated

| Dimension | Description | Threshold | Type |
| :--- | :--- | :---: | :---: |
| `readability` | Is the writing clear, concise, and easy to parse? | $\ge 0.50$ | Gate |
| `structure` | Does the document have well-organized headings, sections, and flow? | $\ge 0.50$ | Gate |
| `completeness` | Does the document provide sufficient context without critical gaps? | $\ge 0.50$ | Gate |
| `actionability` | Can the reader take immediate action or run the code successfully? | $\ge 0.50$ | Gate |
| `composite_score` | Weighted composite score across all quality dimensions. | $\ge 0.60$ | Gate |

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
    "filename": "docs/architecture.md",
    "passed_thresholds": true,
    "composite_score": 0.88,
    "scores": {
      "readability": 0.92,
      "structure": 0.85,
      "completeness": 0.84,
      "actionability": 0.90
    },
    "violations": [],
    "advisory_notes": []
  }
]
```

---

## Near-Threshold Observations

When scores fall within $\pm 0.10$ of the decision boundary ($0.40 \le p \le 0.60$), `typesafe-eval` annotates them with `near_threshold: true`.
Autonomous agents and human reviewers should treat near-threshold scores as soft observations rather than hard failures, considering run-to-run variance (see [Noise Calibration](../science/noise-calibration.md)).
