# Public Python API Overview

`typesafe-eval` exposes a clean, fully typed Python library interface marked with PEP 561 `py.typed`.

---

## 1. Top-Level Imports

All public functions, models, and exceptions can be imported directly from `typesafe_eval`:

```python
from typesafe_eval import (
    evaluate,
    evaluate_document,
    evaluate_documents,
    TypeSafeEvaluator,
    EvaluationCache,
    DocumentEvalResult,
    TypeSafeEvalError,
    ContentViolationError,
    AuthenticationError,
    ConfigurationError,
    RuntimeEvalError,
)
```

---

## 2. Quick In-Memory Evaluation (`evaluate()`)

Evaluate in-memory text or markdown content:

```python
from typesafe_eval import evaluate

markdown_text = """
# System Architecture
This document details our caching architecture.
## Testing Strategy
All units are verified with pytest and mock servers.
"""

result = evaluate(
    content=markdown_text,
    preset="tech-spec",
    filename="virtual_doc.md",
)

if result.passed_thresholds:
    print(f"Passed! Composite score: {result.composite_score}")
else:
    print(f"Failed violations: {result.violations}")
```

---

## 3. Evaluating Files (`evaluate_document()`)

Evaluate a local file with path resolution, caching, and redaction:

```python
from pathlib import Path
from typesafe_eval import evaluate_document

result = evaluate_document(
    path=Path("docs/architecture.md"),
    preset="quality",
    cache=True,
)

print(result.to_dict())
```

---

## 4. Parallel File Evaluation (`evaluate_documents()`)

Evaluate multiple documents concurrently using worker threads:

```python
from pathlib import Path
from typesafe_eval import evaluate_documents

files = list(Path("docs").glob("*.md"))

results = evaluate_documents(
    paths=files,
    preset="safety",
    concurrency=4,
    cache=True,
)

for r in results:
    status = "PASS" if r.passed_thresholds else "FAIL"
    print(f"[{status}] {r.filename}: {len(r.violations)} violations")
```
