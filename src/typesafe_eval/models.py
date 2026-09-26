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

class PresetConfig(BaseModel):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Dict[str, QuestionConfig]

class ScoreResult(BaseModel):
    score: float
    max_score: float = 1.0
    normalized_score: float = 0.0
    confidence: float
    probabilities: Dict[Union[str, int], float]

class NoulResult(BaseModel):
    probability: float

class ChoiceResult(BaseModel):
    choice: str
    confidence: float
    probabilities: Dict[str, float]

class DocumentEvalResult(BaseModel):
    filepath: str
    filename: str
    preset_name: str
    scores: Dict[str, ScoreResult] = Field(default_factory=dict)
    nouls: Dict[str, NoulResult] = Field(default_factory=dict)
    choices: Dict[str, ChoiceResult] = Field(default_factory=dict)
    composite_score: Optional[float] = None
    passed_thresholds: bool = True
    violations: List[str] = Field(default_factory=list)
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    was_truncated: bool = False
    redactions_count: int = 0
    redaction_details: Optional[Dict[str, Any]] = None
