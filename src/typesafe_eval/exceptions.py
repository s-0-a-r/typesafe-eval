"""Typed exception hierarchy for typesafe-eval."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typesafe_eval.models import DocumentEvalResult


class TypeSafeEvalError(Exception):
    """Base exception for all typesafe-eval errors."""


class ConfigurationError(TypeSafeEvalError, ValueError):
    """Raised when configuration, preset, or file arguments are invalid or missing."""


class AuthenticationError(TypeSafeEvalError, ValueError):
    """Raised when the TypeSafe API key is missing or invalid."""


class RuntimeEvalError(TypeSafeEvalError, RuntimeError):
    """Raised when an unrecoverable runtime evaluation or API error occurs."""


class ContentViolationError(TypeSafeEvalError):
    """Raised when evaluated content fails configured safety, quality, or threshold gates."""

    def __init__(
        self,
        message: str,
        violations: list[str] | None = None,
        result: DocumentEvalResult | None = None,
    ) -> None:
        super().__init__(message)
        self.violations: list[str] = violations or []
        self.result: DocumentEvalResult | None = result


__all__ = [
    "TypeSafeEvalError",
    "ConfigurationError",
    "AuthenticationError",
    "RuntimeEvalError",
    "ContentViolationError",
]
