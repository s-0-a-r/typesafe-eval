"""Provider factory for decision engines."""

from __future__ import annotations

import os
from typing import Literal

from typesafe_eval.exceptions import ConfigurationError
from typesafe_eval.providers.base import BaseDecisionProvider
from typesafe_eval.providers.openai import OpenAIDecisionsProvider
from typesafe_eval.providers.typesafe import TypeSafeProvider

ProviderName = Literal["auto", "openai", "typesafe", "jev"]


def create_provider(
    provider: str = "auto",
    model: str | None = None,
    api_key: str | None = None,
) -> BaseDecisionProvider:
    """Instantiates the appropriate decision provider based on config or environment."""
    provider_norm = provider.lower().strip()

    if provider_norm == "auto":
        # If OPENAI_API_KEY is present and TYPESAFE_API_KEY is not, auto-select OpenAI
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_typesafe = bool(os.environ.get("TYPESAFE_API_KEY") or api_key)

        if has_openai and not has_typesafe:
            return OpenAIDecisionsProvider(api_key=api_key, model=model)
        # Default to TypeSafe System One for full backwards compatibility
        return TypeSafeProvider(api_key=api_key, model=model)

    if provider_norm == "openai":
        return OpenAIDecisionsProvider(api_key=api_key, model=model)

    if provider_norm in ("typesafe", "jev"):
        return TypeSafeProvider(api_key=api_key, model=model)

    raise ConfigurationError(
        f"Unknown provider '{provider}'. Supported providers are: 'auto', 'openai', 'typesafe' (or 'jev')."
    )
