"""Base provider interface and data models for decision engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class DecisionQuestion:
    """Represents a discrete question for the decision engine."""

    type: Literal["noul", "score", "choice"]
    instructions: str
    criteria: list[str] | dict[str, str | None] | None = None


@dataclass
class UsageInfo:
    """Token usage reporting."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class NoulOutput:
    """Boolean probability output."""

    noul: float


@dataclass
class ScoreOutput:
    """Ordered rubric score output."""

    score: float
    confidence: float = 1.0
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass
class ChoiceOutput:
    """Categorical choice output."""

    choice: str
    confidence: float = 1.0
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass
class DecisionResponse:
    """Unified response from a decision provider."""

    nouls: dict[str, NoulOutput] = field(default_factory=dict)
    scores: dict[str, ScoreOutput] = field(default_factory=dict)
    choices: dict[str, ChoiceOutput] = field(default_factory=dict)
    usage: UsageInfo | None = None
    model: str | None = None


class BaseDecisionProvider(ABC):
    """Abstract base class for all decision evaluation providers."""

    @abstractmethod
    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, DecisionQuestion],
    ) -> DecisionResponse:
        """Evaluates questions against given state context."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Returns the default model name for this provider."""
        pass
