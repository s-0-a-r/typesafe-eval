"""typesafe-eval: Fast, typed multi-dimensional document evaluation CLI using TypeSafe API (Jev)."""

from typesafe_eval.api import evaluate, evaluate_document, evaluate_documents
from typesafe_eval.cache import EvaluationCache
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ContentViolationError,
    RuntimeEvalError,
    TypeSafeEvalError,
)
from typesafe_eval.models import (
    CANDIDATE_DECISION_THRESHOLD,
    NEAR_THRESHOLD_MARGIN,
    ChoiceResult,
    DocumentEvalResult,
    NoulResult,
    PresetConfig,
    QuestionConfig,
    ScoreResult,
    ViolationItem,
)
from typesafe_eval.presets import (
    find_project_config,
    load_preset,
    load_project_config,
)

__version__ = "0.8.0"  # x-release-please-version

__all__ = [
    "__version__",
    "evaluate",
    "evaluate_document",
    "evaluate_documents",
    "TypeSafeEvaluator",
    "EvaluationCache",
    "DocumentEvalResult",
    "ViolationItem",
    "ScoreResult",
    "NoulResult",
    "ChoiceResult",
    "PresetConfig",
    "QuestionConfig",
    "load_preset",
    "load_project_config",
    "find_project_config",
    "TypeSafeEvalError",
    "ConfigurationError",
    "AuthenticationError",
    "RuntimeEvalError",
    "ContentViolationError",
    "NEAR_THRESHOLD_MARGIN",
    "CANDIDATE_DECISION_THRESHOLD",
]
