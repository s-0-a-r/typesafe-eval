import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class QuestionConfig(BaseModel):
    type: Literal["score", "noul", "choice"]
    label: str | None = None
    instructions: str
    criteria: list[str] | dict[str, str | None] | None = None
    weight: float | None = None
    min_threshold: float | None = None
    max_threshold: float | None = None
    max_drop: float | None = None
    preflight: Literal["credentials", "pii"] | None = None
    advisory: bool = False


class SanitizerConfig(BaseModel):
    role_emails: list[str] = Field(default_factory=list)


NEAR_THRESHOLD_MARGIN: float = 0.1
CANDIDATE_DECISION_THRESHOLD: float = 0.5


class PresetConfig(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    sanitizer: SanitizerConfig | None = None
    thresholds_as_warnings: bool = False
    exclude: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    include_images: bool = False
    max_images_per_doc: int = 5
    questions: dict[str, QuestionConfig]

    @model_validator(mode="before")
    @classmethod
    def _normalize_provider(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "default_provider" in data and not data.get("provider"):
                data["provider"] = data["default_provider"]
            if "default_model" in data and not data.get("model"):
                data["model"] = data["default_model"]
        return data


class ScoreResult(BaseModel):
    score: float
    max_score: float = 1.0
    normalized_score: float = 0.0
    confidence: float
    probabilities: dict[str | int, float]
    near_threshold: bool = False


class NoulResult(BaseModel):
    probability: float | None = None
    overridden_by: str | None = None
    near_threshold: bool = False


class ChoiceResult(BaseModel):
    choice: str
    confidence: float
    probabilities: dict[str, float]


class _PositionMixin(BaseModel):
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _extract_positions(cls, data: Any) -> Any:
        if isinstance(data, dict):
            features = data.get("features", {})
            if isinstance(features, dict):
                for k in ("line", "column", "end_line", "end_column"):
                    if data.get(k) is None and features.get(k) is not None:
                        data[k] = features[k]
        return data


class EmailEvaluationResult(_PositionMixin):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "role", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "free_mail"]
    near_threshold: bool = False


class PhoneEvaluationResult(_PositionMixin):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "support", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class IPEvaluationResult(_PositionMixin):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class URLEvaluationResult(_PositionMixin):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class SecretEvaluationResult(_PositionMixin):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["secret", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class ViolationItem(BaseModel):
    message: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    rule: str | None = None
    level: Literal["error", "warning"] = "error"


class QuestionDiff(BaseModel):
    previous: float
    current: float
    delta: float
    max_drop: float
    regressed: bool


class BaselineDiff(BaseModel):
    status: Literal["compared", "new"]
    baseline_filepath: str | None = None
    truncation_mismatch: bool = False
    questions: dict[str, QuestionDiff] = Field(default_factory=dict)


class DocumentEvalResult(BaseModel):
    schema_version: str = "1.0"
    filepath: str
    filename: str
    preset_name: str
    scores: dict[str, ScoreResult] = Field(default_factory=dict)
    nouls: dict[str, NoulResult] = Field(default_factory=dict)
    choices: dict[str, ChoiceResult] = Field(default_factory=dict)
    email_evaluations: list[EmailEvaluationResult] = Field(default_factory=list)
    phone_evaluations: list[PhoneEvaluationResult] = Field(default_factory=list)
    ip_evaluations: list[IPEvaluationResult] = Field(default_factory=list)
    url_evaluations: list[URLEvaluationResult] = Field(default_factory=list)
    secret_evaluations: list[SecretEvaluationResult] = Field(default_factory=list)
    composite_score: float | None = None
    passed_thresholds: bool = True
    violations: list[str] = Field(default_factory=list)
    structured_violations: list[ViolationItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    model: str | None = None
    was_truncated: bool = False
    api_calls: int = 1
    redactions_count: int = 0
    redaction_details: dict[str, Any] | None = None
    baseline_diff: BaselineDiff | None = None
    mock: bool = False
    cached: bool = False
    images_evaluated: int = 0
    image_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _populate_structured_violations(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("structured_violations"):
                violations = data.get("violations", [])
                warnings = data.get("warnings", [])
                coords: dict[str, dict[str, int | None]] = {}
                for key in (
                    "secret_evaluations",
                    "email_evaluations",
                    "phone_evaluations",
                    "ip_evaluations",
                    "url_evaluations",
                ):
                    items = data.get(key, [])
                    for it in items:
                        if isinstance(it, dict):
                            ph = it.get("placeholder")
                            if ph:
                                coords[ph] = {
                                    "line": it.get("line"),
                                    "column": it.get("column"),
                                    "end_line": it.get("end_line"),
                                    "end_column": it.get("end_column"),
                                }
                        elif hasattr(it, "placeholder"):
                            coords[it.placeholder] = {
                                "line": getattr(it, "line", None),
                                "column": getattr(it, "column", None),
                                "end_line": getattr(it, "end_line", None),
                                "end_column": getattr(it, "end_column", None),
                            }

                structured: list[dict[str, Any]] = []
                for v in violations:
                    msg = str(v)
                    m = re.search(
                        r"(\[(?:SECRET|EMAIL|PHONE|IP|URL)_[0-9]+\]|\[REDACTED_[A-Z0-9_]+\])",
                        msg,
                    )
                    coord = coords.get(m.group(1), {}) if m else {}
                    structured.append(
                        {
                            "message": msg,
                            "line": coord.get("line"),
                            "column": coord.get("column"),
                            "end_line": coord.get("end_line"),
                            "end_column": coord.get("end_column"),
                            "level": "error",
                        }
                    )

                for w in warnings:
                    msg = str(w)
                    m = re.search(
                        r"(\[(?:SECRET|EMAIL|PHONE|IP|URL)_[0-9]+\]|\[REDACTED_[A-Z0-9_]+\])",
                        msg,
                    )
                    coord = coords.get(m.group(1), {}) if m else {}
                    structured.append(
                        {
                            "message": msg,
                            "line": coord.get("line"),
                            "column": coord.get("column"),
                            "end_line": coord.get("end_line"),
                            "end_column": coord.get("end_column"),
                            "level": "warning",
                        }
                    )
                data["structured_violations"] = structured
        return data
