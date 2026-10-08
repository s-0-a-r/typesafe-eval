# Custom Presets & Project Configuration

You can customize thresholds, define project-specific evaluation questions, and set repository-wide exclusion rules using YAML configuration files.

---

## Project Configuration: `.typesafe-eval.yaml`

Place a `.typesafe-eval.yaml` (or `.typesafe-eval.json`) file in your repository root. It will be discovered automatically by `typesafe-eval` on every execution.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/s-0-a-r/typesafe-eval/main/schemas/preset-schema.json

# Default preset to use if -p is omitted
default_preset: quality

# Patterns to exclude from evaluation across the repository
exclude:
  - "**/*.draft.md"
  - "docs/archive/**"
  - "node_modules/**"
  - "vendor/**"

# Global threshold overrides
thresholds:
  readability: 0.60
  structure: 0.55

# Allowed role email addresses (bypass PII violation)
allowed_role_emails:
  - "support@mycompany.internal"
  - "devops@mycompany.internal"

# Multimodal evaluation settings (OpenAI Decisions API)
include_images: true
max_images_per_doc: 5
```

---

## Defining a Custom Preset (`custom-preset.yaml`)

You can create completely custom evaluation rules conforming to the `PresetConfig` schema:

```yaml
name: "security-audit"
title: "Security and Compliance Audit"
description: "Rigorous internal security check"
thresholds_as_warnings: false

questions:
  architecture_threat_model:
    type: score
    label: "Threat Modeling"
    instructions: "Does the document analyze potential attack vectors and trust boundaries?"
    criteria:
      - "No mention of security implications or attack surfaces"
      - "Identifies potential risks but lacks mitigation architecture"
      - "Comprehensive threat model with well-defined mitigation strategies"
    weight: 1.0
    min_threshold: 0.65
    advisory: false

  data_retention:
    type: noul
    label: "Data Retention & Deletion"
    instructions: "Does the proposal specify a concrete data retention and deletion schedule?"
    weight: 1.0
    min_threshold: 0.50
    advisory: true

sanitizer:
  role_emails:
    - "security@mycompany.internal"
    - "compliance@mycompany.internal"
```

Run with your custom preset:

```bash
typesafe-eval docs/security-review.md --preset ./custom-preset.yaml
```

---

## JSON Schema Validation in IDEs

Generate the JSON Schema for code completion and validation:

```bash
typesafe-eval schema --output .typesafe-eval.schema.json
```

In `.vscode/settings.json`:
```json
{
  "yaml.schemas": {
    "./.typesafe-eval.schema.json": ".typesafe-eval.yaml"
  }
}
```
