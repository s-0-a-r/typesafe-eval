# Exit Code Contract & Precedence

`typesafe-eval` returns deterministic process exit codes to enable robust branching in CI pipelines and autonomous agent execution loops.

---

## Exit Codes

| Exit Code | Classification | Meaning | Agent Action |
| :---: | :--- | :--- | :--- |
| **`0`** | **Success** | All documents passed thresholds, or clean dry-run. | Proceed with task or merge PR. |
| **`1`** | **Content Violation** | At least one gate or security violation occurred. | Inspect `violations` and fix the document. |
| **`2`** | **Usage / Config Error** | Invalid arguments, non-existent files, or YAML syntax error. | Check command options and file paths. |
| **`3`** | **Runtime Error** | Network timeout, API error, or missing `TYPESAFE_API_KEY`. | Skip or alert user to check environment; do not modify document. |

---

## The Precedence Rule: Exit 1 over Exit 3

When evaluating multiple files in a batch, it is possible for one file to fail a content gate while another file encounters a network timeout or API error.

In `typesafe-eval`, **Exit Code 1 takes strict precedence over Exit Code 3**:
```
Violation Detected? ───► YES ───► Exit 1 (Always!)
         │
         ▼ NO
Runtime Error?     ───► YES ───► Exit 3
         │
         ▼ NO
Usage/Config Error ───► YES ───► Exit 2
         │
         ▼ NO
                   ───► Exit 0
```

### Why This Matters
If a document contains an exposed AWS secret key, a subsequent API timeout on another document must **never** mask the security violation. The build must fail with code `1` so security gates cannot be bypassed by transient errors.
