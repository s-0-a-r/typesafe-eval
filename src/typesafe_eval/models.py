"""Data models and schemas for configuration and evaluation results."""

from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field

class QuestionConfig(BaseModel):
    type: Literal["score", "noul", "choice"]
    label: Optional[str] = None
    instructions: str
    criteria: Optional[Union[List[str], Dict[str, Optional[str]]]] = None
    weight: Optional[float] = None
    min_threshold: Optional[float] = None
    max_threshold: Optional[float] = None
    max_drop: Optional[float] = None
    preflight: Optional[Literal["credentials", "pii"]] = None

class SanitizerConfig(BaseModel):
    role_emails: List[str] = Field(default_factory=list)

NEAR_THRESHOLD_MARGIN: float = 0.1
CANDIDATE_DECISION_THRESHOLD: float = 0.5

class PresetConfig(BaseModel):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    sanitizer: Optional[SanitizerConfig] = None
    thresholds_as_warnings: bool = False
    questions: Dict[str, QuestionConfig]

class ScoreResult(BaseModel):
    score: float
    max_score: float = 1.0
    normalized_score: float = 0.0
    confidence: float
    probabilities: Dict[Union[str, int], float]
    near_threshold: bool = False

class NoulResult(BaseModel):
    probability: Optional[float] = None
    overridden_by: Optional[str] = None
    near_threshold: bool = False

class ChoiceResult(BaseModel):
    choice: str
    confidence: float
    probabilities: Dict[str, float]

class EmailEvaluationResult(BaseModel):
    placeholder: str
    question_id: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "role", "undecided"]
    probability: Optional[float] = None
    decided_by: Literal["model", "free_mail"]
    near_threshold: bool = False

class PhoneEvaluationResult(BaseModel):
    placeholder: str
    question_id: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["personal", "support", "undecided"]
    probability: Optional[float] = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False

class IPEvaluationResult(BaseModel):
    placeholder: str
    question_id: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: Optional[float] = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False

class URLEvaluationResult(BaseModel):
    placeholder: str
    question_id: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["sensitive", "safe", "undecided"]
    probability: Optional[float] = None
    decided_by: Literal["model", "rule"]
    near_threshold: bool = False

class SecretEvaluationResult(BaseModel):
    placeholder: str
    question_id: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["secret", "safe", "undecided"]
    probability: Optional[float] = None
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
    baseline_filepath: Optional[str] = None
    truncation_mismatch: bool = False
    questions: Dict[str, QuestionDiff] = Field(default_factory=dict)

class DocumentEvalResult(BaseModel):
    filepath: str
    filename: str
    preset_name: str
    scores: Dict[str, ScoreResult] = Field(default_factory=dict)
    nouls: Dict[str, NoulResult] = Field(default_factory=dict)
    choices: Dict[str, ChoiceResult] = Field(default_factory=dict)
    email_evaluations: List[EmailEvaluationResult] = Field(default_factory=list)
    phone_evaluations: List[PhoneEvaluationResult] = Field(default_factory=list)
    ip_evaluations: List[IPEvaluationResult] = Field(default_factory=list)
    url_evaluations: List[URLEvaluationResult] = Field(default_factory=list)
    secret_evaluations: List[SecretEvaluationResult] = Field(default_factory=list)
    composite_score: Optional[float] = None
    passed_thresholds: bool = True
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    was_truncated: bool = False
    api_calls: int = 1
    redactions_count: int = 0
    redaction_details: Optional[Dict[str, Any]] = None
    baseline_diff: Optional[BaselineDiff] = None
    mock: bool = False
