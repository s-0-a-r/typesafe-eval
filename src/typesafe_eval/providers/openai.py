"""OpenAI Decisions API provider implementation using lightweight httpx."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx

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


class OpenAIDecisionsProvider(BaseDecisionProvider):
    """Provider connecting to OpenAI Decisions API (POST /v1/decisions)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_attempts: int = 3,
        initial_backoff: float = 0.5,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL") or self.default_model
        raw_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.base_url = raw_base_url.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.initial_backoff = initial_backoff
        self._http_client: httpx.Client | None = None
        self._lock = threading.Lock()

    @property
    def default_model(self) -> str:
        return "gpt-6-luna"

    def _get_http_client(self) -> httpx.Client:
        with self._lock:
            if self._http_client is None:
                if not self.api_key:
                    raise AuthenticationError(
                        "No OpenAI API key provided. Set the OPENAI_API_KEY environment variable "
                        "or pass --api-key / specify in configuration."
                    )
                self._http_client = httpx.Client(
                    base_url=self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "typesafe-eval/1.1.0 (OpenAI-Decisions-Client)",
                    },
                    timeout=self.timeout,
                )
            return self._http_client

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, DecisionQuestion],
    ) -> DecisionResponse:
        if not self.api_key:
            raise AuthenticationError(
                "No OpenAI API key provided. Set the OPENAI_API_KEY environment variable "
                "or pass --api-key / specify in configuration."
            )
        if not questions:
            return DecisionResponse(
                model=self.model,
                nouls={},
                scores={},
                choices={},
                usage=UsageInfo(input_tokens=0, output_tokens=0),
            )

        client = self._get_http_client()

        # Build state context input string
        # Standard state keys: 'document', 'document_truncated', 'raw_document'
        input_text = state.get("document") or state.get("document_truncated") or ""

        # Serialize questions to OpenAI Decisions API format
        questions_payload: list[dict[str, Any]] = []
        for q_id, q_def in questions.items():
            if q_def.type == "noul":
                questions_payload.append(
                    {
                        "name": q_id,
                        "type": "predicate",
                        "instructions": q_def.instructions,
                    }
                )
            elif q_def.type == "score":
                if isinstance(q_def.criteria, dict):
                    levels = [
                        {"label": str(k), "description": str(v if v is not None else k)}
                        for k, v in q_def.criteria.items()
                    ]
                elif isinstance(q_def.criteria, list):
                    levels = [
                        {"label": str(idx), "description": str(desc)}
                        for idx, desc in enumerate(q_def.criteria)
                        if desc is not None
                    ]
                else:
                    levels = []
                questions_payload.append(
                    {
                        "name": q_id,
                        "type": "score",
                        "instructions": q_def.instructions,
                        "levels": levels,
                    }
                )
            elif q_def.type == "choice":
                if isinstance(q_def.criteria, dict):
                    choice_items = [
                        {"value": str(k), "description": str(v if v is not None else k)}
                        for k, v in q_def.criteria.items()
                    ]
                elif isinstance(q_def.criteria, list):
                    choice_items = [
                        {"value": str(item), "description": str(item)}
                        for item in q_def.criteria
                        if item is not None
                    ]
                else:
                    choice_items = []
                questions_payload.append(
                    {
                        "name": q_id,
                        "type": "choice",
                        "instructions": q_def.instructions,
                        "choices": choice_items,
                    }
                )

        # Build state context input (text-only string or multimodal parts array)
        # Standard state keys: 'document', 'document_truncated', 'raw_document'
        input_text = state.get("document") or state.get("document_truncated") or ""
        images = state.get("images") or []

        if images:
            multimodal_parts: list[dict[str, Any]] = [{"type": "input_text", "text": input_text}]
            for img in images:
                if hasattr(img, "data_url"):
                    data_url = img.data_url
                elif isinstance(img, dict) and "data_url" in img:
                    data_url = img["data_url"]
                elif isinstance(img, str):
                    data_url = img
                else:
                    continue
                multimodal_parts.append(
                    {
                        "type": "input_image",
                        "image_url": data_url,
                    }
                )
            input_payload: Any = multimodal_parts
        else:
            input_payload = input_text

        request_body: dict[str, Any] = {
            "model": self.model,
            "input": input_payload,
            "questions": questions_payload,
        }

        # Execute HTTP request with exponential backoff on transient errors
        attempt = 0
        last_exc: Exception | None = None
        raw_json: dict[str, Any] | None = None

        while attempt < self.max_attempts:
            attempt += 1
            try:
                response = client.post("/decisions", json=request_body)
                if response.status_code in (401, 403):
                    raise AuthenticationError(
                        f"OpenAI API authentication failed (HTTP {response.status_code}): {response.text}"
                    )
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < self.max_attempts:
                        time.sleep(self.initial_backoff * (2 ** (attempt - 1)))
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                raw_json = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_exc = net_err
                if attempt < self.max_attempts:
                    time.sleep(self.initial_backoff * (2 ** (attempt - 1)))
                    continue
                raise RuntimeError(
                    f"OpenAI API network failure after {self.max_attempts} attempts: {net_err}"
                ) from net_err
            except httpx.HTTPStatusError as status_err:
                raise RuntimeError(
                    f"OpenAI API error ({status_err.response.status_code}): {status_err.response.text}"
                ) from status_err

        if raw_json is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("OpenAI Decisions API call failed unexpectedly")

        # Parse decisions / answers from response
        answers_list: list[dict[str, Any]] = []
        if "answers" in raw_json and isinstance(raw_json["answers"], list):
            answers_list = raw_json["answers"]
        elif "decisions" in raw_json:
            raw_dec = raw_json["decisions"]
            if isinstance(raw_dec, dict):
                for q_id_key, q_val_obj in raw_dec.items():
                    if isinstance(q_val_obj, dict):
                        item = dict(q_val_obj)
                        item.setdefault("name", q_id_key)
                        answers_list.append(item)
            elif isinstance(raw_dec, list):
                answers_list = raw_dec

        nouls: dict[str, NoulOutput] = {}
        scores: dict[str, ScoreOutput] = {}
        choices: dict[str, ChoiceOutput] = {}

        for q_val in answers_list:
            q_id = str(q_val.get("name") or q_val.get("id") or "")
            if not q_id:
                continue
            expected_type = questions[q_id].type if q_id in questions else None
            dec_type = q_val.get("type")

            if expected_type == "noul" or (
                expected_type is None and (dec_type == "predicate" or "probability" in q_val)
            ):
                prob = float(q_val.get("probability", 0.0))
                nouls[q_id] = NoulOutput(noul=prob)
            elif expected_type == "score" or (
                expected_type is None and (dec_type == "score" or "score" in q_val)
            ):
                sc = float(q_val.get("score", 0.0))
                conf = float(q_val.get("confidence", 1.0))
                raw_probs = q_val.get("probabilities", {})
                probs: dict[str, float] = {}
                if isinstance(raw_probs, list):
                    for p_elem in raw_probs:
                        if isinstance(p_elem, dict):
                            label_key = str(
                                p_elem.get("label")
                                if p_elem.get("label") is not None
                                else p_elem.get("value", "")
                            )
                            probs[label_key] = float(p_elem.get("probability", 0.0))
                elif isinstance(raw_probs, dict):
                    probs = {str(pk): float(pv) for pk, pv in raw_probs.items()}
                scores[q_id] = ScoreOutput(score=sc, confidence=conf, probabilities=probs)
            elif expected_type == "choice" or (
                expected_type is None and (dec_type == "choice" or "choice" in q_val)
            ):
                ch = str(q_val.get("choice", ""))
                conf = float(q_val.get("confidence", 1.0))
                raw_probs = q_val.get("probabilities", {})
                probs = {}
                if isinstance(raw_probs, list):
                    for p_elem in raw_probs:
                        if isinstance(p_elem, dict):
                            val_key = str(
                                p_elem.get("value")
                                if p_elem.get("value") is not None
                                else p_elem.get("label", "")
                            )
                            probs[val_key] = float(p_elem.get("probability", 0.0))
                elif isinstance(raw_probs, dict):
                    probs = {str(pk): float(pv) for pk, pv in raw_probs.items()}
                choices[q_id] = ChoiceOutput(choice=ch, confidence=conf, probabilities=probs)

        # Parse usage
        usage = None
        raw_usage = raw_json.get("usage")
        if isinstance(raw_usage, dict):
            usage = UsageInfo(
                input_tokens=int(
                    raw_usage.get("input_tokens", 0) or raw_usage.get("prompt_tokens", 0)
                ),
                output_tokens=int(
                    raw_usage.get("output_tokens", 0) or raw_usage.get("completion_tokens", 0)
                ),
            )

        resp_model = raw_json.get("model") or self.model or self.default_model

        return DecisionResponse(
            nouls=nouls,
            scores=scores,
            choices=choices,
            usage=usage,
            model=resp_model,
        )
