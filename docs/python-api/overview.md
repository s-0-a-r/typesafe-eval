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

print(result.model_dump())
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

---

## 5. Multi-Provider Evaluator (`TypeSafeEvaluator`)

Configure the evaluation backend explicitly using `TypeSafeEvaluator`:

```python
from typesafe_eval import TypeSafeEvaluator, load_preset

# 1. Use OpenAI Decisions API (model: gpt-6-luna)
evaluator_openai = TypeSafeEvaluator(
    provider="openai",
    model="gpt-6-luna",
    api_key="sk-...",
)
preset = load_preset("quality")
res = evaluator_openai.evaluate_document("docs/guide.md", preset=preset)
print(f"OpenAI Model: {res.model}, Composite: {res.composite_score}")

# 2. Use TypeSafe System One (Jev)
evaluator_typesafe = TypeSafeEvaluator(
    provider="typesafe",
    model="jev-1.13.0",
)
res_jev = evaluator_typesafe.evaluate_document("docs/guide.md", preset=preset)
print(f"TypeSafe Model: {res_jev.model}, Composite: {res_jev.composite_score}")
```
