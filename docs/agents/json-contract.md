# JSON Contract (`schema_version: "1.0"`)

When executing `typesafe-eval ... -f json`, structured data is emitted strictly to `stdout`. Diagnostic warnings, progress spinners, and file-level errors are sent to `stderr`.

---

## JSON Schema Structure

```json
[
  {
    "schema_version": "1.0",
    "filename": "docs/architecture.md",
    "passed_thresholds": false,
    "composite_score": 0.52,
    "scores": {
      "has_test_plan": 0.32,
      "architecture_rigor": 0.78
    },
    "violations": [
      "has_test_plan: score 0.32 below threshold 0.50",
      "Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential"
    ],
    "advisory_notes": [
      "failure_modes: score 0.44 below advisory threshold 0.50 (Advisory)"
    ],
    "email_evaluations": [
      {
        "placeholder": "[EMAIL_1]",
        "outcome": "personal",
        "decided_by": "free_mail"
      }
    ],
    "secret_evaluations": [
      {
        "placeholder": "[REDACTED_AWS_KEY]",
        "outcome": "secret",
        "decided_by": "rule"
      }
    ],
    "near_threshold_dimensions": [
      "failure_modes"
    ]
  }
]
```

---

## Field Reference

- **`schema_version`**: Version identifier for forward/backward compatibility (`"1.0"`).
- **`filename`**: Evaluated file path.
- **`passed_thresholds`**: Boolean status flag. `true` only if all gate thresholds are met and 0 safety violations occurred.
- **`composite_score`**: Weighted aggregate score across all evaluated dimensions.
- **`violations`**: Array of actionable failure strings.
- **`advisory_notes`**: Non-blocking observations.
- **`email_evaluations`**: Records each masked email and whether it was decided as personal or role.
- **`secret_evaluations`**: Records each detected secret token without exposing raw values.
- **`near_threshold_dimensions`**: List of dimensions falling within $\pm 0.10$ of their threshold.
