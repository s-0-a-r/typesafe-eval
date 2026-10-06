# Python API Reference & Types

Type annotations and data structures for `typesafe-eval`.

---

## 1. Core Evaluation Functions

### `evaluate()`
```python
def evaluate(
    content: str,
    preset: str | PresetConfig = "quality",
    filename: str = "<memory>",
    api_key: str | None = None,
    api_base_url: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask: bool = True,
    strip_prose_comments: bool = True,
) -> DocumentEvalResult: ...
```

### `evaluate_document()`
```python
def evaluate_document(
    path: Path | str,
    preset: str | PresetConfig = "quality",
    api_key: str | None = None,
    api_base_url: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask: bool = True,
    strip_prose_comments: bool = True,
) -> DocumentEvalResult: ...
```

### `evaluate_documents()`
```python
def evaluate_documents(
    paths: Sequence[Path | str],
    preset: str | PresetConfig = "quality",
    concurrency: int = 1,
    api_key: str | None = None,
    api_base_url: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask: bool = True,
    strip_prose_comments: bool = True,
) -> list[DocumentEvalResult]: ...
```

---

## 2. Result Data Models

### `DocumentEvalResult`
The unified evaluation result structure returned for every evaluated document.

| Field | Type | Description |
| :--- | :--- | :--- |
| `schema_version` | `str` | Always `"1.0"`. |
| `filename` | `str` | Relative or absolute path of the document. |
| `passed_thresholds` | `bool` | `True` if all gates passed and zero safety violations occurred. |
| `composite_score` | `float` | Weighted overall score ($0.0 \dots 1.0$). |
| `scores` | `dict[str, float]` | Dimension score map. |
| `violations` | `list[str]` | Human-readable gate violation descriptions. |
| `advisory_notes` | `list[str]` | Non-blocking observations. |
| `secret_evaluations` | `list[ViolationItem]` | Masked secret detection records. |
| `email_evaluations` | `list[ViolationItem]` | Masked email categorization records. |
| `near_threshold_dimensions` | `list[str]` | Dimensions within $\pm 0.10$ of the decision boundary. |

Methods:
- `to_dict() -> dict[str, Any]`: Returns a JSON-serializable dictionary conforming to `schema_version: "1.0"`.

---

## 3. Decision Constants

```python
from typesafe_eval import CANDIDATE_DECISION_THRESHOLD, NEAR_THRESHOLD_MARGIN

print(CANDIDATE_DECISION_THRESHOLD)  # 0.50
print(NEAR_THRESHOLD_MARGIN)  # 0.10
```
