# Python API Reference & Types

Type annotations and data structures for `typesafe-eval`.

---

## 1. Core Evaluation Functions

### `evaluate()`
```python
def evaluate(
    content: str,
    preset: str | PresetConfig = "quality",
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    filename: str = "<memory>",
    filepath: str | Path | None = None,
    project_root: str | Path | None = None,
    evaluator: TypeSafeEvaluator | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> DocumentEvalResult: ...
```

### `evaluate_document()`
```python
def evaluate_document(
    path: Path | str,
    preset: str | PresetConfig = "quality",
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    project_root: str | Path | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> DocumentEvalResult: ...
```

### `evaluate_documents()`
```python
def evaluate_documents(
    paths: Sequence[str | Path],
    preset: str | PresetConfig = "quality",
    *,
    exclude: Sequence[str] | None = None,
    concurrency: int = 4,
    api_key: str | None = None,
    dry_run: bool = False,
    offline: bool = False,
    cache: bool = True,
    cache_dir: Path | str | None = None,
    mask_secrets: bool = True,
    max_chars: int = 120_000,
    raise_on_violation: bool = False,
    project_root: str | Path | None = None,
    include_images: bool | None = None,
    max_images_per_doc: int | None = None,
) -> list[DocumentEvalResult]: ...
```

---

## 2. Result Data Models

### `DocumentEvalResult`
The unified evaluation result structure returned for every evaluated document (Pydantic v2 `BaseModel`).

| Field | Type | Description |
| :--- | :--- | :--- |
| `schema_version` | `str` | Always `"1.0"`. |
| `filepath` | `str` | Resolved filesystem path or synthetic identifier. |
| `filename` | `str` | Basename of the document. |
| `preset_name` | `str` | Name of the evaluated preset. |
| `passed_thresholds` | `bool` | `True` if all gates passed and zero safety violations occurred. |
| `composite_score` | `float \| None` | Weighted overall score ($0.0 \dots 1.0$). |
| `scores` | `dict[str, ScoreResult]` | Numerical score evaluations. |
| `nouls` | `dict[str, NoulResult]` | Calibrated binary decision evaluations. |
| `choices` | `dict[str, ChoiceResult]` | Categorical choice evaluations. |
| `violations` | `list[str]` | Human-readable gate violation descriptions. |
| `warnings` | `list[str]` | Non-blocking advisory observations and warnings. |
| `secret_evaluations` | `list[SecretEvaluationResult]` | Masked secret detection records. |
| `email_evaluations` | `list[EmailEvaluationResult]` | Masked email categorization records. |
| `phone_evaluations` | `list[PhoneEvaluationResult]` | Masked phone detection records. |
| `ip_evaluations` | `list[IPEvaluationResult]` | Masked IP detection records. |
| `url_evaluations` | `list[URLEvaluationResult]` | Masked URL detection records. |
| `images_evaluated` | `int` | Number of resolved markdown images evaluated (default 0). |
| `image_paths` | `list[str]` | Paths or source URIs of resolved images sent for evaluation. |

Methods:
- `model_dump() -> dict[str, Any]`: Returns a JSON-serializable dictionary conforming to `schema_version: "1.0"`.
- `model_dump_json() -> str`: Serializes model directly to a JSON string.

---

## 3. Decision Constants

```python
from typesafe_eval import CANDIDATE_DECISION_THRESHOLD, NEAR_THRESHOLD_MARGIN

print(CANDIDATE_DECISION_THRESHOLD)  # 0.50
print(NEAR_THRESHOLD_MARGIN)  # 0.10
```
