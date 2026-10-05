"""Data models and schemas for configuration and evaluation results."""

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    questions: dict[str, QuestionConfig]


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


class EmailEvaluationResult(BaseModel):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "role", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "free_mail"]
    near_threshold: bool = False


class PhoneEvaluationResult(BaseModel):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "support", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class IPEvaluationResult(BaseModel):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class URLEvaluationResult(BaseModel):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


class SecretEvaluationResult(BaseModel):
    placeholder: str
    question_id: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["secret", "safe", "undecided"]
    probability: float | None = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False


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
    warnings: list[str] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    model: str | None = None
    was_truncated: bool = False
    api_calls: int = 1
    redactions_count: int = 0
    redaction_details: dict[str, Any] | None = None
    baseline_diff: BaselineDiff | None = None
    mock: bool = False
