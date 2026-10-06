# JSON Contract (`schema_version: "1.0"`)

When executing `typesafe-eval ... -f json`, structured data is emitted strictly to `stdout`. Diagnostic warnings, progress spinners, and file-level errors are sent to `stderr`.

---

## JSON Schema Structure

```json
[
  {
    "schema_version": "1.0",
    "filepath": "docs/architecture.md",
    "filename": "architecture.md",
    "preset_name": "tech-spec",
    "passed_thresholds": false,
    "composite_score": 0.52,
    "scores": {
      "clarity": {
        "score": 0.72,
        "max_score": 1.0,
        "normalized_score": 0.72,
        "confidence": 0.89,
        "probabilities": {
          "1": 0.05,
          "2": 0.23,
          "3": 0.72
        },
        "near_threshold": false
      }
    },
    "nouls": {
      "has_test_plan": {
        "probability": 0.32,
        "overridden_by": null,
        "near_threshold": true
      }
    },
    "choices": {
      "readiness": {
        "choice": "needs_revision",
        "confidence": 0.82,
        "probabilities": {
          "ready": 0.12,
          "needs_revision": 0.82,
          "blocked": 0.06
        }
      }
    },
    "violations": [
      "has_test_plan: probability 0.32 below threshold 0.50",
      "Credential Exposure: [REDACTED_AWS_KEY] is a known aws_key credential"
    ],
    "warnings": [
      "clarity: score 0.58 below threshold 0.60 (warning)"
    ],
    "email_evaluations": [
      {
        "placeholder": "[EMAIL_1]",
        "outcome": "personal",
        "probability": 0.95,
        "decided_by": "free_mail",
        "near_threshold": false
      }
    ],
    "secret_evaluations": [
      {
        "placeholder": "[REDACTED_AWS_KEY]",
        "outcome": "secret",
        "probability": null,
        "decided_by": "rule",
        "near_threshold": false
      }
    ]
  }
]
```

---

## Field Reference

- **`schema_version`**: Version identifier for forward/backward compatibility (`"1.0"`).
- **`filepath`**: Filepath on disk or synthetic identifier.
- **`filename`**: Evaluated file basename.
- **`preset_name`**: Name of the applied evaluation preset.
- **`passed_thresholds`**: Boolean status flag. `true` only if all gate thresholds are met and zero safety violations occurred.
- **`composite_score`**: Weighted aggregate score across evaluated score/noul questions ($0.0 \dots 1.0$).
- **`scores`**: Numerical dimensions mapped to `ScoreResult` objects (including `score`, `confidence`, `probabilities`, and `near_threshold`).
- **`nouls`**: Binary decision dimensions mapped to `NoulResult` objects (including `probability` and `near_threshold`).
- **`choices`**: Categorical dimensions mapped to `ChoiceResult` objects (including `choice`, `confidence`, and `probabilities`).
- **`violations`**: Array of actionable failure strings causing non-zero exit code.
- **`warnings`**: Non-blocking observations, advisory notes, and threshold warnings.
- **`email_evaluations`**: Records each masked email and whether it was decided as personal or role.
- **`secret_evaluations`**: Records each detected secret token without exposing raw values.
