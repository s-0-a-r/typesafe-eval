"""TypeSafe System One (Jev) provider implementation."""

from __future__ import annotations

import os
import time
from typing import Any

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from typesafe_eval.exceptions import AuthenticationError
from typesafe_eval.providers.base import (
    BaseDecisionProvider,
    ChoiceOutput,
    DecisionQuestion,
    DecisionResponse,
    NoulOutput,
    ScoreOutput,
    UsageInfo,
)


def _is_transient_error(exc: Exception) -> bool:
    """Checks whether an exception represents a transient 429 or 5xx API error."""
    status = getattr(exc, "status", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    if status is None and hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        status = exc.response.status_code
    if isinstance(status, int):
        return status == 429 or (500 <= status < 600)

    cls_name = type(exc).__name__
    if cls_name in ("TypeSafeRateLimitError", "TypeSafeInternalServerError"):
        return True

    err_str = str(exc)
    for code in ("429", "500", "502", "503", "504"):
        if code in err_str:
            return True
    return False


class TypeSafeProvider(BaseDecisionProvider):
    """Provider connecting to TypeSafe System One API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_attempts: int = 3,
        initial_backoff: float = 0.5,
    ) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self.model = model
        self.max_attempts = max_attempts
        self.initial_backoff = initial_backoff
        self._client: TypeSafeClient | None = None

    @property
    def default_model(self) -> str:
        return "jev-1.13.0"

    def _get_client(self) -> TypeSafeClient:
        if self._client is None:
            if not self.api_key:
                raise AuthenticationError(
                    "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
                    "or pass --api-key / specify in configuration."
                )
            self._client = TypeSafeClient(api_key=self.api_key)
        return self._client

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, DecisionQuestion],
    ) -> DecisionResponse:
        client = self._get_client()

        # Convert unified DecisionQuestion objects to TypeSafe SDK objects
        sdk_questions: dict[str, Any] = {}
        for q_id, q_def in questions.items():
            if q_def.type == "noul":
                sdk_questions[q_id] = Noul(instructions=q_def.instructions)
            elif q_def.type == "score":
                criteria_list = (
                    q_def.criteria
                    if isinstance(q_def.criteria, list)
                    else (list(q_def.criteria.values()) if isinstance(q_def.criteria, dict) else [])
                )
                sdk_questions[q_id] = Score(
                    instructions=q_def.instructions,
                    criteria=[str(c) for c in criteria_list if c is not None],
                )
            elif q_def.type == "choice":
                options_dict = (
                    q_def.criteria
                    if isinstance(q_def.criteria, dict)
                    else {str(i): str(opt) for i, opt in enumerate(q_def.criteria or [])}
                )
                sdk_questions[q_id] = Choice(
                    instructions=q_def.instructions,
                    criteria={
                        str(k): (str(v) if v is not None else str(k))
                        for k, v in options_dict.items()
                    },
                )

        # TypeSafe System One is text-only; notify and omit images if present
        call_state = dict(state)
        if call_state.pop("images", None):
            import sys

            sys.stderr.write(
                "Notice: TypeSafe System One (Jev) is text-only; embedded images were skipped.\n"
            )

        # Call with retry on transient network errors
        attempt = 0
        last_exc: Exception | None = None
        while attempt < self.max_attempts:
            attempt += 1
            try:
                raw_resp = client.system_one(state=call_state, questions=sdk_questions)
                break
            except Exception as e:
                last_exc = e
                if attempt < self.max_attempts and _is_transient_error(e):
                    time.sleep(self.initial_backoff * (2 ** (attempt - 1)))
                    continue
                raise
        else:
            if last_exc:
                raise last_exc
            raise RuntimeError("API call failed after max attempts")

        # Map response to unified DecisionResponse
        nouls = {}
        if hasattr(raw_resp, "nouls") and raw_resp.nouls:
            for nl_key, nl_val in raw_resp.nouls.items():
                nouls[nl_key] = NoulOutput(noul=nl_val.noul)

        scores = {}
        if hasattr(raw_resp, "scores") and raw_resp.scores:
            for sc_key, sc_val in raw_resp.scores.items():
                probs = (
                    {str(pk): pv for pk, pv in sc_val.probabilities.items()}
                    if getattr(sc_val, "probabilities", None)
                    else {}
                )
                scores[sc_key] = ScoreOutput(
                    score=float(sc_val.score),
                    confidence=float(getattr(sc_val, "confidence", 1.0)),
                    probabilities=probs,
                )

        choices = {}
        if hasattr(raw_resp, "choices") and raw_resp.choices:
            for ch_key, ch_val in raw_resp.choices.items():
                probs = (
                    {str(pk): pv for pk, pv in ch_val.probabilities.items()}
                    if getattr(ch_val, "probabilities", None)
                    else {}
                )
                choices[ch_key] = ChoiceOutput(
                    choice=str(ch_val.choice),
                    confidence=float(getattr(ch_val, "confidence", 1.0)),
                    probabilities=probs,
                )

        usage = None
        if hasattr(raw_resp, "usage") and raw_resp.usage:
            usage = UsageInfo(
                input_tokens=getattr(raw_resp.usage, "input_tokens", 0),
                output_tokens=getattr(raw_resp.usage, "output_tokens", 0),
            )

        resp_model = getattr(raw_resp, "model", None) or self.model or self.default_model

        return DecisionResponse(
            nouls=nouls,
            scores=scores,
            choices=choices,
            usage=usage,
            model=resp_model,
        )
