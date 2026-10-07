"""Evaluation engine wrapping TypeSafe System One API client."""

import os
import re
import threading
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any, Literal, cast

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from typesafe_eval.cache import EvaluationCache
from typesafe_eval.exceptions import AuthenticationError
from typesafe_eval.models import (
    CANDIDATE_DECISION_THRESHOLD,
    NEAR_THRESHOLD_MARGIN,
    ChoiceResult,
    DocumentEvalResult,
    EmailEvaluationResult,
    IPEvaluationResult,
    NoulResult,
    PhoneEvaluationResult,
    PresetConfig,
    ScoreResult,
    SecretEvaluationResult,
    URLEvaluationResult,
)
from typesafe_eval.providers import (
    BaseDecisionProvider,
    DecisionQuestion,
    create_provider,
)
from typesafe_eval.providers.typesafe import TypeSafeProvider
from typesafe_eval.sanitizer import (
    chunk_text,
    guard_document_length,
    mask_sensitive_data,
    strip_html_comments,
)


def _is_candidate_near_threshold(decided_by: str, prob: float | None) -> bool:
    """Returns True if candidate outcome was model-decided and within margin of decision threshold."""
    if decided_by == "model" and prob is not None:
        return abs(prob - CANDIDATE_DECISION_THRESHOLD) <= NEAR_THRESHOLD_MARGIN + 1e-9
    return False


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


def _in_chunk_helper(
    placeholder: str,
    text: str,
    unplaced: AbstractSet[str],
    item_in_text_fn: Callable[[str, str], bool],
) -> bool:
    """True if the placeholder is in text, or found in no chunk (then treated as present in every chunk)."""
    return placeholder in unplaced or item_in_text_fn(placeholder, text)


def _call_system_one_with_retry(
    client: Any,
    state: dict[str, Any],
    questions: dict[str, Any],
    max_attempts: int = 3,
    initial_backoff: float = 0.5,
) -> Any:
    """Calls provider.decide or client.system_one retrying transient 429 and 5xx errors with exponential backoff."""
    if isinstance(client, BaseDecisionProvider):
        unified_q: dict[str, DecisionQuestion] = {}
        for q_id, q_obj in questions.items():
            if isinstance(q_obj, DecisionQuestion):
                unified_q[q_id] = q_obj
            elif isinstance(q_obj, Noul):
                unified_q[q_id] = DecisionQuestion(
                    type="noul", instructions=str(q_obj.instructions)
                )
            elif isinstance(q_obj, Score):
                raw_crit = q_obj.criteria if hasattr(q_obj, "criteria") else None
                score_crit: list[str] | None = (
                    [str(c) for c in raw_crit] if isinstance(raw_crit, list) else None
                )
                unified_q[q_id] = DecisionQuestion(
                    type="score",
                    instructions=str(q_obj.instructions),
                    criteria=score_crit,
                )
            elif isinstance(q_obj, Choice):
                raw_choice_crit = q_obj.criteria if hasattr(q_obj, "criteria") else None
                choice_crit: dict[str, str | None] | None = None
                if isinstance(raw_choice_crit, dict):
                    choice_crit = {
                        str(k): (str(v) if v is not None else None)
                        for k, v in raw_choice_crit.items()
                    }
                unified_q[q_id] = DecisionQuestion(
                    type="choice", instructions=str(q_obj.instructions), criteria=choice_crit
                )
            else:
                unified_q[q_id] = DecisionQuestion(
                    type="noul", instructions=str(getattr(q_obj, "instructions", str(q_obj)))
                )
        return client.decide(state=state, questions=unified_q)

    # Legacy client or MagicMock
    sdk_questions: dict[str, Any] = {}
    for q_id, q_obj in questions.items():
        if isinstance(q_obj, DecisionQuestion):
            if q_obj.type == "noul":
                sdk_questions[q_id] = Noul(instructions=q_obj.instructions)
            elif q_obj.type == "score":
                criteria_list = (
                    q_obj.criteria
                    if isinstance(q_obj.criteria, list)
                    else (list(q_obj.criteria.values()) if isinstance(q_obj.criteria, dict) else [])
                )
                sdk_questions[q_id] = Score(
                    instructions=q_obj.instructions,
                    criteria=[str(c) for c in criteria_list if c is not None],
                )
            elif q_obj.type == "choice":
                options_dict = (
                    q_obj.criteria
                    if isinstance(q_obj.criteria, dict)
                    else {str(i): str(opt) for i, opt in enumerate(q_obj.criteria or [])}
                )
                sdk_questions[q_id] = Choice(
                    instructions=q_obj.instructions,
                    criteria={
                        str(k): (str(v) if v is not None else str(k))
                        for k, v in options_dict.items()
                    },
                )
        else:
            sdk_questions[q_id] = q_obj

    attempt = 0
    while True:
        try:
            attempt += 1
            return client.system_one(state=state, questions=sdk_questions)
        except Exception as e:
            if attempt < max_attempts and _is_transient_error(e):
                import time

                time.sleep(initial_backoff * (2 ** (attempt - 1)))
                continue
            raise


def _find_preflight_question(preset: PresetConfig, target: str) -> str | None:
    """Finds the question ID mapped to a pre-flight scanner category."""
    for q_id, q_cfg in preset.questions.items():
        if q_cfg.preflight == target:
            return q_id
    if target == "credentials" and "has_secrets" in preset.questions:
        return "has_secrets"
    if target == "pii" and "has_pii" in preset.questions:
        return "has_pii"
    return None


DEFAULT_CANDIDATE_BATCH_SIZE = 15


class TypeSafeEvaluator:
    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "auto",
        model: str | None = None,
        max_candidate_batch_size: int = DEFAULT_CANDIDATE_BATCH_SIZE,
        cache: EvaluationCache | None = None,
        enable_cache: bool = False,
        cache_dir: Path | str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or (
            os.environ.get("OPENAI_API_KEY")
            if provider == "openai"
            else os.environ.get("TYPESAFE_API_KEY")
        )
        self.max_candidate_batch_size = max(1, max_candidate_batch_size)
        if cache is not None:
            self.cache: EvaluationCache | None = cache
        elif enable_cache:
            self.cache = EvaluationCache(cache_dir=cache_dir, enabled=True)
        else:
            self.cache = None
        self._provider: BaseDecisionProvider | None = None
        self._client: Any | None = None
        self._lock = threading.RLock()

    def _default_get_client(self) -> Any:
        with self._lock:
            if self._client is None:
                if not self.api_key:
                    raise AuthenticationError(
                        "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
                        "or pass --api-key / specify in configuration."
                    )
                self._client = TypeSafeClient(api_key=self.api_key)
            return self._client

    _get_client = _default_get_client

    def _get_provider(self) -> BaseDecisionProvider:
        with self._lock:
            # Check if mock client was injected into self._client
            if self._client is not None and not isinstance(self._client, BaseDecisionProvider):
                prov = TypeSafeProvider(api_key=self.api_key, model=self.model)
                prov._client = self._client
                return prov

            # Check if _get_client was monkeypatched on class or instance
            if (
                type(self)._get_client is not TypeSafeEvaluator._default_get_client
                or "_get_client" in self.__dict__
            ):
                try:
                    c = self._get_client()
                    if c is not None and not isinstance(c, BaseDecisionProvider):
                        prov = TypeSafeProvider(api_key=self.api_key, model=self.model)
                        prov._client = c
                        return prov
                except Exception:
                    pass

            if self._provider is None:
                self._provider = create_provider(
                    provider=self.provider,
                    model=self.model,
                    api_key=self.api_key,
                )
            return self._provider

    def evaluate_document(
        self,
        filepath: str | Path,
        preset: PresetConfig,
        mask_secrets: bool = True,
        max_chars: int = 25000,
        dry_run: bool = False,
        offline: bool = False,
    ) -> DocumentEvalResult:
        """Evaluates a single document file against the specified preset."""
        path = Path(filepath)
        raw_content = path.read_text(encoding="utf-8")
        return self.evaluate_content(
            content=raw_content,
            preset=preset,
            filename=path.name,
            filepath=str(path),
            mask_secrets=mask_secrets,
            max_chars=max_chars,
            dry_run=dry_run,
            offline=offline,
        )

    def evaluate_content(
        self,
        content: str,
        preset: PresetConfig,
        filename: str = "<memory>",
        filepath: str | Path = "<memory>",
        mask_secrets: bool = True,
        max_chars: int = 25000,
        dry_run: bool = False,
        offline: bool = False,
    ) -> DocumentEvalResult:
        """Evaluates in-memory document content against the specified preset."""
        if self.cache and self.cache.enabled and not dry_run and not offline:
            cached_result = self.cache.get(
                content, preset, mask_secrets=mask_secrets, max_chars=max_chars
            )
            if cached_result is not None:
                cached_result.filepath = str(filepath)
                cached_result.filename = filename
                return cached_result

        raw_content = content

        # 1. Sanitize (detection & feature extraction run on raw_content before stripping HTML comments)
        custom_roles = preset.sanitizer.role_emails if preset.sanitizer else None
        sanitized_content, redaction_count, redaction_details = mask_sensitive_data(
            raw_content, mask=mask_secrets, return_details=True, custom_role_patterns=custom_roles
        )
        content = strip_html_comments(sanitized_content)
        raw_mapping: dict[str, list[str]] = (
            redaction_details.pop("_raw_mapping", {}) if redaction_details else {}
        )

        _raw_token_cache: dict[str, set[str]] = {}

        def _raw_tokens_in(text: str) -> set[str]:
            # Re-run the same detector on the chunk so a raw value matches only as a whole detected token.
            if text not in _raw_token_cache:
                _, _, chunk_details = mask_sensitive_data(
                    text, mask=False, return_details=True, custom_role_patterns=custom_roles
                )
                _raw_token_cache[text] = {
                    raw for vals in chunk_details.get("_raw_mapping", {}).values() for raw in vals
                }
            return _raw_token_cache[text]

        def _item_in_text(placeholder: str, text: str) -> bool:
            if mask_secrets:
                return placeholder in text
            raw_occurrences = raw_mapping.get(placeholder, [])
            if raw_occurrences:
                return any(raw in _raw_tokens_in(text) for raw in raw_occurrences)
            return placeholder in text

        all_detected_placeholders = [
            item["placeholder"]
            for item in (
                (redaction_details.get("redacted_emails", []) if redaction_details else [])
                + (redaction_details.get("redacted_phones", []) if redaction_details else [])
                + (redaction_details.get("redacted_ips", []) if redaction_details else [])
                + (redaction_details.get("redacted_urls", []) if redaction_details else [])
                + (redaction_details.get("redacted_secrets", []) if redaction_details else [])
            )
            if item.get("placeholder")
        ]

        comment_stripped_placeholders = frozenset(
            p
            for p in all_detected_placeholders
            if _item_in_text(p, sanitized_content) and not _item_in_text(p, content)
        )

        # 2. Build candidate specs (dynamic per-candidate Noul questions)
        candidate_specs: list[tuple[str, str, Noul]] = []

        redacted_emails = redaction_details.get("redacted_emails", []) if redaction_details else []
        for feature in redacted_emails:
            if feature.get("domain_type") == "corporate":
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("EMAIL_", "")
                q_id = f"email_pii_{num_suffix}"
                candidate_specs.append(
                    (
                        placeholder,
                        q_id,
                        Noul(
                            instructions=(
                                f"Is {placeholder} an address of an individual person (not a shared role, team, or system mailbox)? "
                                f"Use the surrounding text and state.redacted_emails."
                            )
                        ),
                    )
                )

        redacted_phones = redaction_details.get("redacted_phones", []) if redaction_details else []
        for feature in redacted_phones:
            if not feature.get("is_support_prefix"):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("PHONE_", "")
                q_id = f"phone_pii_{num_suffix}"
                candidate_specs.append(
                    (
                        placeholder,
                        q_id,
                        Noul(
                            instructions=(
                                f"Is {placeholder} a private or personal phone number of an individual (not a shared corporate switchboard, toll-free number, or customer support line)? "
                                f"Use the surrounding text and state.redacted_phones."
                            )
                        ),
                    )
                )

        redacted_ips = redaction_details.get("redacted_ips", []) if redaction_details else []
        for feature in redacted_ips:
            if not feature.get("is_documentation") and not feature.get("is_loopback"):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("IP_", "")
                q_id = f"ip_pii_{num_suffix}"
                candidate_specs.append(
                    (
                        placeholder,
                        q_id,
                        Noul(
                            instructions=(
                                f"Is {placeholder} an internal, production, or sensitive IP address (not a documentation or public dummy IP)? "
                                f"Use the surrounding text and state.redacted_ips."
                            )
                        ),
                    )
                )

        redacted_urls = redaction_details.get("redacted_urls", []) if redaction_details else []
        for feature in redacted_urls:
            if (
                not feature.get("is_example_domain")
                and not feature.get("is_public_common")
                and not feature.get("is_loopback")
                and not feature.get("is_documentation")
            ):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("URL_", "")
                q_id = f"url_pii_{num_suffix}"
                candidate_specs.append(
                    (
                        placeholder,
                        q_id,
                        Noul(
                            instructions=(
                                f"Is {placeholder} an internal, non-public, or sensitive endpoint or infrastructure URL (not a public internet service or example URL)? "
                                f"Use the surrounding text and state.redacted_urls."
                            )
                        ),
                    )
                )

        redacted_secrets = (
            redaction_details.get("redacted_secrets", []) if redaction_details else []
        )
        for feature in redacted_secrets:
            if not feature.get("is_known_format") and not feature.get("placeholder_syntax"):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("SECRET_", "")
                q_id = f"secret_{num_suffix}"
                candidate_specs.append(
                    (
                        placeholder,
                        q_id,
                        Noul(
                            instructions=(
                                f"Is the value represented by {placeholder} an actual secret, credential, or password (not an example, placeholder, or template)? "
                                f"Use the surrounding text and state.redacted_secrets."
                            )
                        ),
                    )
                )

        # 3. Length check & chunking determination
        is_long = len(content) > max_chars
        has_nouls = any(q.type == "noul" for q in preset.questions.values())
        has_scores_or_choices = any(
            q.type in ("score", "choice") for q in preset.questions.values()
        )
        has_nouls_or_candidates = has_nouls or bool(candidate_specs)

        if is_long:
            if has_scores_or_choices and has_nouls_or_candidates:
                chunks = chunk_text(content, max_chars=max_chars, overlap=2000)
                content_truncated, _ = guard_document_length(content, max_chars=max_chars)
                api_calls = 1 + len(chunks)
                was_truncated = True
            elif has_nouls_or_candidates:
                chunks = chunk_text(content, max_chars=max_chars, overlap=2000)
                content_truncated = content
                api_calls = len(chunks)
                was_truncated = False
            else:
                chunks = []
                content_truncated, was_truncated = guard_document_length(
                    content, max_chars=max_chars
                )
                api_calls = 1
        else:
            chunks = [content]
            content_truncated = content
            api_calls = 1
            was_truncated = False

        # 4. Dry run & offline bypass
        if dry_run:
            return self._build_mock_result(
                filepath=str(filepath),
                preset=preset,
                was_truncated=was_truncated,
                api_calls=api_calls,
                redaction_count=redaction_count,
                redaction_details=redaction_details,
                filename=filename,
                content=raw_content,
            )

        if offline:
            return self._build_offline_result(
                filepath=str(filepath),
                preset=preset,
                was_truncated=was_truncated,
                redaction_count=redaction_count,
                redaction_details=redaction_details,
                filename=filename,
                content=raw_content,
            )

        # 5. Build SDK questions
        sdk_score_choice_questions: dict[str, Any] = {}
        sdk_preset_noul_questions: dict[str, Any] = {}
        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score":
                criteria_list = (
                    list(q_cfg.criteria)
                    if isinstance(q_cfg.criteria, list)
                    else ["Low", "Medium", "High"]
                )
                sdk_score_choice_questions[q_id] = Score(
                    instructions=q_cfg.instructions,
                    criteria=criteria_list,
                )
            elif q_cfg.type == "noul":
                sdk_preset_noul_questions[q_id] = Noul(
                    instructions=q_cfg.instructions,
                )
            elif q_cfg.type == "choice":
                # Ensure criteria is dict
                criteria = q_cfg.criteria
                if isinstance(criteria, list):
                    criteria = dict.fromkeys(criteria)
                sdk_score_choice_questions[q_id] = Choice(
                    instructions=q_cfg.instructions,
                    criteria=cast(Any, criteria),
                )

        # 5. Call Decision Provider (TypeSafe System One or OpenAI Decisions)
        client = self._get_provider()
        total_input_tokens = 0
        total_output_tokens = 0
        model_name = getattr(client, "default_model", "type-safe-one")

        scores: dict[str, ScoreResult] = {}
        nouls: dict[str, NoulResult] = {}
        choices: dict[str, ChoiceResult] = {}
        candidate_prob_map: dict[str, list[float]] = {}
        preset_noul_probs: dict[str, list[float]] = {q_id: [] for q_id in sdk_preset_noul_questions}

        # Placeholders found in no chunk; filled once before the chunk loop, then treated as present in every chunk.
        unplaced: frozenset[str] = frozenset()

        def _in_chunk(placeholder: str, text: str) -> bool:
            return _in_chunk_helper(
                placeholder, text, unplaced | comment_stripped_placeholders, _item_in_text
            )

        def _make_state(doc_text: str, is_full: bool = True) -> dict[str, Any]:
            st: dict[str, Any] = {
                "document": doc_text,
                "filename": filename,
            }
            if is_full:
                if redaction_details and (
                    redaction_details.get("total", 0) > 0
                    or redaction_details.get("examples", 0) > 0
                ):
                    st["redactions"] = {
                        "credentials": redaction_details.get("credentials", 0),
                        "pii": redaction_details.get("pii_personal", 0),
                        "pii_personal": redaction_details.get("pii_personal", 0),
                        "pii_role": redaction_details.get("pii_role", 0),
                        "examples": redaction_details.get("examples", 0),
                    }
                if redacted_emails:
                    st["redacted_emails"] = redacted_emails
                if redacted_phones:
                    st["redacted_phones"] = redacted_phones
                if redacted_ips:
                    st["redacted_ips"] = redacted_ips
                if redacted_urls:
                    st["redacted_urls"] = redacted_urls
                if redacted_secrets:
                    st["redacted_secrets"] = redacted_secrets
            else:
                chunk_em = [f for f in redacted_emails if _in_chunk(f["placeholder"], doc_text)]
                chunk_ph = [f for f in redacted_phones if _in_chunk(f["placeholder"], doc_text)]
                chunk_ip = [f for f in redacted_ips if _in_chunk(f["placeholder"], doc_text)]
                chunk_ur = [f for f in redacted_urls if _in_chunk(f["placeholder"], doc_text)]
                chunk_sec = [f for f in redacted_secrets if _in_chunk(f["placeholder"], doc_text)]
                if chunk_em:
                    st["redacted_emails"] = chunk_em
                if chunk_ph:
                    st["redacted_phones"] = chunk_ph
                if chunk_ip:
                    st["redacted_ips"] = chunk_ip
                if chunk_ur:
                    st["redacted_urls"] = chunk_ur
                if chunk_sec:
                    st["redacted_secrets"] = chunk_sec
            return st

        if not is_long:
            st = _make_state(content, is_full=True)
            batch_size = self.max_candidate_batch_size
            candidate_batches = [
                candidate_specs[i : i + batch_size]
                for i in range(0, len(candidate_specs), batch_size)
            ] or [[]]

            first_questions = {**sdk_score_choice_questions, **sdk_preset_noul_questions}
            for _, q_id, q_obj in candidate_batches[0]:
                first_questions[q_id] = q_obj

            response = _call_system_one_with_retry(client, state=st, questions=first_questions)
            if response.usage:
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens
            if response.model:
                model_name = response.model

            cred_q_id = _find_preflight_question(preset, "credentials")
            cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
            is_cred_override = cred_count > 0 and cred_q_id

            pii_q_id = _find_preflight_question(preset, "pii")
            pii_count = (
                redaction_details.get("by_type", {}).get("email_free_mail", 0)
                if redaction_details
                else 0
            )
            is_pii_override = pii_count > 0 and pii_q_id

            missing_questions = []
            for q_id, q_cfg in preset.questions.items():
                if q_cfg.type == "score":
                    if q_id in response.scores:
                        ans = response.scores[q_id]
                        num_levels = len(q_cfg.criteria) if q_cfg.criteria else 3
                        max_score = float(max(num_levels - 1, 1))
                        norm_score = min(max(ans.score / max_score, 0.0), 1.0)
                        scores[q_id] = ScoreResult(
                            score=ans.score,
                            max_score=max_score,
                            normalized_score=norm_score,
                            confidence=ans.confidence,
                            probabilities={str(k): v for k, v in ans.probabilities.items()}
                            if ans.probabilities
                            else {},
                        )
                    else:
                        missing_questions.append(q_id)
                elif q_cfg.type == "noul":
                    if q_id in response.nouls:
                        nouls[q_id] = NoulResult(
                            probability=response.nouls[q_id].noul,
                        )
                    elif (is_cred_override and q_id == cred_q_id) or (
                        is_pii_override and q_id == pii_q_id
                    ):
                        nouls[q_id] = NoulResult(
                            probability=None,
                            overridden_by="preflight_scan",
                        )
                    else:
                        missing_questions.append(q_id)
                elif q_cfg.type == "choice":
                    if q_id in response.choices:
                        ans = response.choices[q_id]
                        choices[q_id] = ChoiceResult(
                            choice=ans.choice,
                            confidence=ans.confidence,
                            probabilities={str(k): v for k, v in ans.probabilities.items()}
                            if ans.probabilities
                            else {},
                        )
                    else:
                        missing_questions.append(q_id)

            for _, q_id, _ in candidate_batches[0]:
                if q_id in response.nouls:
                    candidate_prob_map[q_id] = [response.nouls[q_id].noul]
                else:
                    missing_questions.append(q_id)

            # Evaluate any remaining candidate batches
            for sub_batch in candidate_batches[1:]:
                sub_questions = {q_id: q_obj for _, q_id, q_obj in sub_batch}
                sub_resp = _call_system_one_with_retry(client, state=st, questions=sub_questions)
                if sub_resp.usage:
                    total_input_tokens += sub_resp.usage.input_tokens
                    total_output_tokens += sub_resp.usage.output_tokens
                for _, q_id, _ in sub_batch:
                    if q_id in sub_resp.nouls:
                        candidate_prob_map[q_id] = [sub_resp.nouls[q_id].noul]
                    else:
                        missing_questions.append(q_id)

            if missing_questions:
                q_names = ", ".join(f"'{q}'" for q in missing_questions)
                raise RuntimeError(f"Missing evaluation result for question(s) {q_names}")
        else:
            cred_q_id = _find_preflight_question(preset, "credentials")
            cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
            is_cred_override = cred_count > 0 and cred_q_id

            pii_q_id = _find_preflight_question(preset, "pii")
            pii_count = (
                redaction_details.get("by_type", {}).get("email_free_mail", 0)
                if redaction_details
                else 0
            )
            is_pii_override = pii_count > 0 and pii_q_id

            if has_scores_or_choices:
                st_trunc = _make_state(content_truncated, is_full=True)
                resp_sc = _call_system_one_with_retry(
                    client, state=st_trunc, questions=sdk_score_choice_questions
                )
                if resp_sc.usage:
                    total_input_tokens += resp_sc.usage.input_tokens
                    total_output_tokens += resp_sc.usage.output_tokens
                if resp_sc.model:
                    model_name = resp_sc.model
                missing_score_choice = []
                for q_id, q_cfg in preset.questions.items():
                    if q_cfg.type == "score":
                        if q_id in resp_sc.scores:
                            ans = resp_sc.scores[q_id]
                            num_levels = len(q_cfg.criteria) if q_cfg.criteria else 3
                            max_score = float(max(num_levels - 1, 1))
                            norm_score = min(max(ans.score / max_score, 0.0), 1.0)
                            scores[q_id] = ScoreResult(
                                score=ans.score,
                                max_score=max_score,
                                normalized_score=norm_score,
                                confidence=ans.confidence,
                                probabilities={str(k): v for k, v in ans.probabilities.items()}
                                if ans.probabilities
                                else {},
                            )
                        else:
                            missing_score_choice.append(q_id)
                    elif q_cfg.type == "choice":
                        if q_id in resp_sc.choices:
                            ans = resp_sc.choices[q_id]
                            choices[q_id] = ChoiceResult(
                                choice=ans.choice,
                                confidence=ans.confidence,
                                probabilities={str(k): v for k, v in ans.probabilities.items()}
                                if ans.probabilities
                                else {},
                            )
                        else:
                            missing_score_choice.append(q_id)
                if missing_score_choice:
                    q_names = ", ".join(f"'{q}'" for q in missing_score_choice)
                    raise RuntimeError(f"Missing evaluation result for question(s) {q_names}")
            if chunks:
                all_redacted = (
                    redacted_emails
                    + redacted_phones
                    + redacted_ips
                    + redacted_urls
                    + redacted_secrets
                )
                unplaced = frozenset(
                    p
                    for p in (item.get("placeholder") for item in all_redacted)
                    if p and not any(_item_in_text(p, chk) for chk in chunks)
                )

                n_chunks = len(chunks)
                for chunk_idx, chunk_text_part in enumerate(chunks, start=1):
                    chunk_st = _make_state(chunk_text_part, is_full=False)
                    chunk_candidates = [
                        (placeholder, q_id, q_obj)
                        for placeholder, q_id, q_obj in candidate_specs
                        if _in_chunk(placeholder, chunk_text_part)
                    ]
                    batch_size = self.max_candidate_batch_size
                    chunk_batches = [
                        chunk_candidates[i : i + batch_size]
                        for i in range(0, len(chunk_candidates), batch_size)
                    ] or [[]]

                    chunk_questions = dict(sdk_preset_noul_questions)
                    for _, q_id, q_obj in chunk_batches[0]:
                        chunk_questions[q_id] = q_obj

                    if chunk_questions:
                        resp_chk = _call_system_one_with_retry(
                            client, state=chunk_st, questions=chunk_questions
                        )
                        if resp_chk.usage:
                            total_input_tokens += resp_chk.usage.input_tokens
                            total_output_tokens += resp_chk.usage.output_tokens
                        if resp_chk.model:
                            model_name = resp_chk.model

                        missing_chunk_questions = []
                        for q_id in chunk_questions:
                            if (is_cred_override and q_id == cred_q_id) or (
                                is_pii_override and q_id == pii_q_id
                            ):
                                continue
                            if q_id not in resp_chk.nouls:
                                missing_chunk_questions.append(q_id)

                        if missing_chunk_questions:
                            q_names = ", ".join(f"'{q}'" for q in missing_chunk_questions)
                            raise RuntimeError(
                                f"Missing evaluation result for question(s) {q_names} in chunk {chunk_idx}/{n_chunks}"
                            )

                        for q_id in sdk_preset_noul_questions:
                            if q_id in resp_chk.nouls:
                                preset_noul_probs[q_id].append(resp_chk.nouls[q_id].noul)
                        for _, q_id, _ in chunk_batches[0]:
                            if q_id in resp_chk.nouls:
                                candidate_prob_map.setdefault(q_id, []).append(
                                    resp_chk.nouls[q_id].noul
                                )

                    # Subsequent candidate batches in this chunk
                    for sub_batch in chunk_batches[1:]:
                        sub_questions = {q_id: q_obj for _, q_id, q_obj in sub_batch}
                        sub_resp = _call_system_one_with_retry(
                            client, state=chunk_st, questions=sub_questions
                        )
                        if sub_resp.usage:
                            total_input_tokens += sub_resp.usage.input_tokens
                            total_output_tokens += sub_resp.usage.output_tokens
                        missing_sub = []
                        for _, q_id, _ in sub_batch:
                            if q_id in sub_resp.nouls:
                                candidate_prob_map.setdefault(q_id, []).append(
                                    sub_resp.nouls[q_id].noul
                                )
                            else:
                                missing_sub.append(q_id)
                        if missing_sub:
                            q_names = ", ".join(f"'{q}'" for q in missing_sub)
                            raise RuntimeError(
                                f"Missing evaluation result for question(s) {q_names} in chunk {chunk_idx}/{n_chunks}"
                            )

                never_asked = [
                    q_id for _, q_id, _ in candidate_specs if q_id not in candidate_prob_map
                ]
                if never_asked:
                    q_names = ", ".join(f"'{q}'" for q in never_asked)
                    raise RuntimeError(
                        f"Candidate question(s) {q_names} were not asked in any of {n_chunks} chunks"
                    )

                for q_id in sdk_preset_noul_questions:
                    probs = preset_noul_probs.get(q_id, [])
                    if probs:
                        nouls[q_id] = NoulResult(probability=max(probs))
                    elif (is_cred_override and q_id == cred_q_id) or (
                        is_pii_override and q_id == pii_q_id
                    ):
                        nouls[q_id] = NoulResult(probability=None, overridden_by="preflight_scan")
                    else:
                        nouls[q_id] = NoulResult(probability=None)

        email_violations: list[str] = []
        phone_violations: list[str] = []
        ip_violations: list[str] = []
        url_violations: list[str] = []
        secret_violations: list[str] = []

        # Emails
        email_evaluations: list[EmailEvaluationResult] = []
        for feature in redacted_emails:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("EMAIL_", "")
            q_id = f"email_pii_{num_suffix}"

            if feature.get("domain_type") == "free_mail":
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="personal",
                        probability=None,
                        decided_by="free_mail",
                    )
                )
                email_violations.append(
                    f"PII Exposure: {placeholder} is an individual address (free-mail)"
                )
            else:
                prob = max(candidate_prob_map[q_id]) if candidate_prob_map.get(q_id) else None
                outcome: Literal["personal", "role", "undecided"] = "undecided"
                if prob is not None:
                    outcome = "personal" if prob >= CANDIDATE_DECISION_THRESHOLD else "role"

                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome,
                        probability=prob,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", prob),
                    )
                )
                if outcome == "personal":
                    prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                    email_violations.append(
                        f"PII Exposure: {placeholder} is an individual address{prob_str}"
                    )

        # Phones
        phone_evaluations: list[PhoneEvaluationResult] = []
        for feature in redacted_phones:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("PHONE_", "")
            q_id = f"phone_pii_{num_suffix}"
            prob = max(candidate_prob_map[q_id]) if candidate_prob_map.get(q_id) else None
            outcome_phone: Literal["personal", "support", "undecided"] = "undecided"
            decided_by_phone: Literal["model", "rule"] = "model"
            if feature.get("is_support_prefix"):
                outcome_phone = "support"
                decided_by_phone = "rule"
            elif prob is not None:
                outcome_phone = "personal" if prob >= CANDIDATE_DECISION_THRESHOLD else "support"
            elif feature.get("looks_like_support"):
                outcome_phone = "support"
            else:
                outcome_phone = "personal"

            phone_evaluations.append(
                PhoneEvaluationResult(
                    placeholder=placeholder,
                    question_id=q_id if decided_by_phone == "model" else None,
                    features=feature,
                    outcome=outcome_phone,
                    probability=prob,
                    decided_by=decided_by_phone,
                    near_threshold=_is_candidate_near_threshold(decided_by_phone, prob),
                )
            )
            if outcome_phone == "personal":
                prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                phone_violations.append(
                    f"PII Exposure: {placeholder} is an individual phone number{prob_str}"
                )

        # IPs
        ip_evaluations: list[IPEvaluationResult] = []
        for feature in redacted_ips:
            placeholder = feature["placeholder"]
            if feature.get("is_documentation") or feature.get("is_loopback"):
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            else:
                num_suffix = placeholder.strip("[]").replace("IP_", "")
                q_id = f"ip_pii_{num_suffix}"
                prob = max(candidate_prob_map[q_id]) if candidate_prob_map.get(q_id) else None
                outcome_ip: Literal["sensitive", "safe", "undecided"] = "undecided"
                if prob is not None:
                    outcome_ip = "sensitive" if prob >= CANDIDATE_DECISION_THRESHOLD else "safe"
                elif feature.get("is_private"):
                    outcome_ip = "sensitive"
                else:
                    outcome_ip = "safe"

                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome_ip,
                        probability=prob,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", prob),
                    )
                )
                if outcome_ip == "sensitive":
                    prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                    ip_violations.append(
                        f"PII Exposure: {placeholder} is an internal/sensitive IP address{prob_str}"
                    )

        # URLs
        url_evaluations: list[URLEvaluationResult] = []
        for feature in redacted_urls:
            placeholder = feature["placeholder"]
            if (
                feature.get("is_example_domain")
                or feature.get("is_public_common")
                or feature.get("is_loopback")
                or feature.get("is_documentation")
            ):
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            else:
                num_suffix = placeholder.strip("[]").replace("URL_", "")
                q_id = f"url_pii_{num_suffix}"
                prob = max(candidate_prob_map[q_id]) if candidate_prob_map.get(q_id) else None
                outcome_url: Literal["sensitive", "safe", "undecided"] = "undecided"
                if prob is not None:
                    outcome_url = "sensitive" if prob >= CANDIDATE_DECISION_THRESHOLD else "safe"
                elif feature.get("is_internal_tld"):
                    outcome_url = "sensitive"
                else:
                    outcome_url = "safe"

                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome_url,
                        probability=prob,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", prob),
                    )
                )
                if outcome_url == "sensitive":
                    prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                    url_violations.append(
                        f"PII Exposure: {placeholder} is an internal/sensitive URL{prob_str}"
                    )

        # Secrets
        secret_evaluations: list[SecretEvaluationResult] = []
        for feature in redacted_secrets:
            placeholder = feature["placeholder"]
            if feature.get("is_known_format"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="secret",
                        probability=None,
                        decided_by="rule",
                    )
                )
                secret_violations.append(
                    f"Credential Exposure: {placeholder} is a known format secret"
                )
            elif feature.get("placeholder_syntax"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            else:
                num_suffix = placeholder.strip("[]").replace("SECRET_", "")
                q_id = f"secret_{num_suffix}"
                prob = max(candidate_prob_map[q_id]) if candidate_prob_map.get(q_id) else None
                outcome_sec: Literal["secret", "safe", "undecided"] = "undecided"
                if prob is not None:
                    outcome_sec = "secret" if prob >= CANDIDATE_DECISION_THRESHOLD else "safe"
                elif feature.get("near_example_words"):
                    outcome_sec = "safe"
                else:
                    outcome_sec = "secret"

                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome_sec,
                        probability=prob,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", prob),
                    )
                )
                if outcome_sec == "secret":
                    prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                    secret_violations.append(
                        f"Credential Exposure: {placeholder} is an exposed secret{prob_str}"
                    )

        # Preflight overrides for credentials & PII
        cred_q_id = _find_preflight_question(preset, "credentials")
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
        if cred_count > 0 and cred_q_id:
            if cred_q_id in nouls:
                nouls[cred_q_id].overridden_by = "preflight_scan"
            else:
                nouls[cred_q_id] = NoulResult(
                    probability=None,
                    overridden_by="preflight_scan",
                )

        pii_q_id = _find_preflight_question(preset, "pii")
        pii_count = (
            redaction_details.get("by_type", {}).get("email_free_mail", 0)
            if redaction_details
            else 0
        )
        if pii_count > 0 and pii_q_id:
            if pii_q_id in nouls:
                nouls[pii_q_id].overridden_by = "preflight_scan"
            else:
                nouls[pii_q_id] = NoulResult(
                    probability=None,
                    overridden_by="preflight_scan",
                )

        # 7. Compute deterministic composite score and threshold check
        composite_score, passed, violations, warnings = self._evaluate_thresholds_and_composite(
            preset=preset,
            scores=scores,
            nouls=nouls,
            choices=choices,
            redaction_details=redaction_details,
        )

        boundary_unplaced = unplaced - comment_stripped_placeholders
        if boundary_unplaced:
            warnings.append(
                f"{len(boundary_unplaced)} redacted item(s) ({', '.join(sorted(boundary_unplaced))}) were not found in any of "
                f"{len(chunks)} chunks and were treated as present in every chunk; "
                f"any candidate probabilities for them may be less reliable."
            )

        has_sec_check = bool(
            _find_preflight_question(preset, "credentials") or "has_secrets" in preset.questions
        )
        has_pii_check = bool(
            _find_preflight_question(preset, "pii") or "has_pii" in preset.questions
        )

        if has_sec_check and secret_violations:
            violations.extend(secret_violations)
            passed = False
        if has_pii_check:
            all_pii_violations = (
                email_violations + phone_violations + ip_violations + url_violations
            )
            if all_pii_violations:
                violations.extend(all_pii_violations)
                passed = False

        usage_dict = None
        if total_input_tokens > 0 or total_output_tokens > 0:
            usage_dict = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        eval_result = DocumentEvalResult(
            filepath=str(filepath),
            filename=filename,
            preset_name=preset.name,
            scores=scores,
            nouls=nouls,
            choices=choices,
            email_evaluations=email_evaluations,
            phone_evaluations=phone_evaluations,
            ip_evaluations=ip_evaluations,
            url_evaluations=url_evaluations,
            secret_evaluations=secret_evaluations,
            composite_score=composite_score,
            passed_thresholds=passed,
            violations=violations,
            warnings=warnings,
            usage=usage_dict,
            model=model_name,
            was_truncated=was_truncated,
            api_calls=api_calls,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
        )

        if self.cache and self.cache.enabled and not dry_run and not offline:
            self.cache.set(
                content,
                preset,
                eval_result,
                mask_secrets=mask_secrets,
                max_chars=max_chars,
            )

        return eval_result

    def _evaluate_thresholds_and_composite(
        self,
        preset: PresetConfig,
        scores: dict[str, ScoreResult],
        nouls: dict[str, NoulResult],
        choices: dict[str, ChoiceResult],
        redaction_details: dict[str, Any] | None = None,
    ) -> tuple[float | None, bool, list[str], list[str]]:
        total_weight = 0.0
        weighted_sum = 0.0
        passed = True
        violations = []
        warnings = []
        is_warning_only = bool(preset.thresholds_as_warnings)

        for q_id, q_cfg in preset.questions.items():
            val = None
            if q_cfg.type == "score" and q_id in scores:
                val = scores[q_id].normalized_score
            elif q_cfg.type == "noul" and q_id in nouls:
                val = nouls[q_id].probability

            # Weighted score calculation: contributes whenever model probability is present
            if val is not None and q_cfg.weight is not None and q_cfg.weight > 0:
                weighted_sum += val * q_cfg.weight
                total_weight += q_cfg.weight

            # Near-threshold detection (Issue #44)
            is_near = False
            if val is not None:
                if (
                    q_cfg.min_threshold is not None
                    and abs(val - q_cfg.min_threshold) <= NEAR_THRESHOLD_MARGIN + 1e-9
                ):
                    is_near = True
                if (
                    q_cfg.max_threshold is not None
                    and abs(val - q_cfg.max_threshold) <= NEAR_THRESHOLD_MARGIN + 1e-9
                ):
                    is_near = True

            if q_cfg.type == "score" and q_id in scores:
                scores[q_id].near_threshold = is_near
            elif q_cfg.type == "noul" and q_id in nouls:
                nouls[q_id].near_threshold = is_near

            is_advisory = is_warning_only or bool(q_cfg.advisory)

            # Pre-flight scan override violation check
            if (
                q_cfg.type == "noul"
                and q_id in nouls
                and nouls[q_id].overridden_by == "preflight_scan"
            ):
                label = q_cfg.label or q_id
                is_pii = q_cfg.preflight == "pii" or q_id == "has_pii"
                target_count = (
                    (
                        redaction_details.get("by_type", {}).get("email_free_mail", 0)
                        if is_pii
                        else redaction_details.get("credentials", 0)
                    )
                    if redaction_details
                    else 0
                )
                item_name = "personal PII item(s)" if is_pii else "credential(s)"
                model_str = f" (model: {val:.2f})" if val is not None else ""
                msg = f"{label}: {target_count} {item_name} detected by pre-flight scan{model_str}"
                if is_advisory:
                    warnings.append(f"{msg} (warning)")
                else:
                    passed = False
                    violations.append(msg)
            elif val is not None:
                # Threshold verification
                if q_cfg.min_threshold is not None and val < q_cfg.min_threshold:
                    label = q_cfg.label or q_id
                    if is_advisory:
                        warnings.append(
                            f"{label}: score {val:.2f} is below minimum {q_cfg.min_threshold:.2f} (warning)"
                        )
                    else:
                        passed = False
                        violations.append(
                            f"{label}: score {val:.2f} is below required minimum {q_cfg.min_threshold:.2f}"
                        )
                if q_cfg.max_threshold is not None and val > q_cfg.max_threshold:
                    label = q_cfg.label or q_id
                    if is_advisory:
                        warnings.append(
                            f"{label}: risk {val:.2f} exceeds maximum {q_cfg.max_threshold:.2f} (warning)"
                        )
                    else:
                        passed = False
                        violations.append(
                            f"{label}: risk {val:.2f} exceeds allowed maximum {q_cfg.max_threshold:.2f}"
                        )

        composite = (weighted_sum / total_weight) if total_weight > 0 else None
        return composite, passed, violations, warnings

    def _build_mock_result(
        self,
        filepath: str,
        preset: PresetConfig,
        was_truncated: bool,
        api_calls: int = 1,
        redaction_count: int = 0,
        redaction_details: dict[str, Any] | None = None,
        filename: str | None = None,
        content: str | None = None,
    ) -> DocumentEvalResult:
        """Returns mock evaluation result for dry-run or testing."""
        scores = {}
        nouls = {}
        choices = {}
        path = Path(filepath)
        doc_filename = filename or path.name
        if content is not None:
            raw_content = content
        else:
            raw_content = path.read_text(encoding="utf-8") if path.is_file() else ""

        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score":
                scores[q_id] = ScoreResult(
                    score=1.70,
                    max_score=2.0,
                    normalized_score=0.85,
                    confidence=0.90,
                    probabilities={"0": 0.05, "1": 0.20, "2": 0.75},
                )
            elif q_cfg.type == "noul":
                nouls[q_id] = NoulResult(probability=0.78)
            elif q_cfg.type == "choice":
                default_choice = (
                    list(q_cfg.criteria.keys())[0]
                    if isinstance(q_cfg.criteria, dict)
                    else (q_cfg.criteria[0] if q_cfg.criteria else "default")
                )
                choices[q_id] = ChoiceResult(
                    choice=str(default_choice),
                    confidence=0.95,
                    probabilities={str(default_choice): 0.95, "other": 0.05},
                )

        email_evaluations: list[EmailEvaluationResult] = []
        phone_evaluations: list[PhoneEvaluationResult] = []
        ip_evaluations: list[IPEvaluationResult] = []
        url_evaluations: list[URLEvaluationResult] = []
        secret_evaluations: list[SecretEvaluationResult] = []
        extra_violations: list[str] = []

        # Emails
        redacted_emails = redaction_details.get("redacted_emails", []) if redaction_details else []
        for feature in redacted_emails:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("EMAIL_", "")
            q_id = f"email_pii_{num_suffix}"
            if feature.get("domain_type") == "free_mail":
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="personal",
                        probability=None,
                        decided_by="free_mail",
                    )
                )
                extra_violations.append(
                    f"PII Exposure: {placeholder} is an individual address (free-mail)"
                )
            else:
                mock_prob = (
                    0.10
                    if (feature.get("known_role_word") or feature.get("matches_custom_role"))
                    else 0.80
                )
                outcome_em: Literal["personal", "role", "undecided"] = (
                    "personal" if mock_prob >= CANDIDATE_DECISION_THRESHOLD else "role"
                )
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome_em,
                        probability=mock_prob,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", mock_prob),
                    )
                )
                if outcome_em == "personal":
                    extra_violations.append(
                        f"PII Exposure: {placeholder} is an individual address (model: {mock_prob:.2f})"
                    )

        # Phones
        redacted_phones = redaction_details.get("redacted_phones", []) if redaction_details else []
        for feature in redacted_phones:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("PHONE_", "")
            q_id = f"phone_pii_{num_suffix}"
            if feature.get("is_support_prefix"):
                phone_evaluations.append(
                    PhoneEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="support",
                        probability=None,
                        decided_by="rule",
                    )
                )
            elif feature.get("looks_like_support"):
                phone_evaluations.append(
                    PhoneEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="support",
                        probability=0.10,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.10),
                    )
                )
            else:
                phone_evaluations.append(
                    PhoneEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="personal",
                        probability=0.85,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.85),
                    )
                )
                extra_violations.append(
                    f"PII Exposure: {placeholder} is an individual phone number (model: 0.85)"
                )

        # IPs
        redacted_ips = redaction_details.get("redacted_ips", []) if redaction_details else []
        for feature in redacted_ips:
            placeholder = feature["placeholder"]
            if feature.get("is_documentation") or feature.get("is_loopback"):
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            elif feature.get("is_private"):
                num_suffix = placeholder.strip("[]").replace("IP_", "")
                q_id = f"ip_pii_{num_suffix}"
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="sensitive",
                        probability=0.85,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.85),
                    )
                )
                extra_violations.append(
                    f"PII Exposure: {placeholder} is an internal/sensitive IP address (model: 0.85)"
                )
            else:
                num_suffix = placeholder.strip("[]").replace("IP_", "")
                q_id = f"ip_pii_{num_suffix}"
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="safe",
                        probability=0.08,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.08),
                    )
                )

        # URLs
        redacted_urls = redaction_details.get("redacted_urls", []) if redaction_details else []
        for feature in redacted_urls:
            placeholder = feature["placeholder"]
            if (
                feature.get("is_example_domain")
                or feature.get("is_public_common")
                or feature.get("is_loopback")
                or feature.get("is_documentation")
            ):
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            elif feature.get("is_internal_tld"):
                num_suffix = placeholder.strip("[]").replace("URL_", "")
                q_id = f"url_pii_{num_suffix}"
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="sensitive",
                        probability=0.88,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.88),
                    )
                )
                extra_violations.append(
                    f"PII Exposure: {placeholder} is an internal/sensitive URL (model: 0.88)"
                )
            else:
                num_suffix = placeholder.strip("[]").replace("URL_", "")
                q_id = f"url_pii_{num_suffix}"
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="safe",
                        probability=0.08,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.08),
                    )
                )

        # Secrets
        has_prose_secret = bool(re.search(r"password\s+is\s+[^\s.,]+", raw_content, re.IGNORECASE))
        redacted_secrets = (
            redaction_details.get("redacted_secrets", []) if redaction_details else []
        )
        for feature in redacted_secrets:
            placeholder = feature["placeholder"]
            if feature.get("is_known_format"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="secret",
                        probability=None,
                        decided_by="rule",
                    )
                )
                extra_violations.append(
                    f"Credential Exposure: {placeholder} is a known format secret"
                )
            elif feature.get("placeholder_syntax"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=None,
                        features=feature,
                        outcome="safe",
                        probability=None,
                        decided_by="rule",
                    )
                )
            elif feature.get("near_example_words"):
                num_suffix = placeholder.strip("[]").replace("SECRET_", "")
                q_id = f"secret_{num_suffix}"
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="safe",
                        probability=0.10,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.10),
                    )
                )
            else:
                num_suffix = placeholder.strip("[]").replace("SECRET_", "")
                q_id = f"secret_{num_suffix}"
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome="secret",
                        probability=0.88,
                        decided_by="model",
                        near_threshold=_is_candidate_near_threshold("model", 0.88),
                    )
                )
                extra_violations.append(
                    f"Credential Exposure: {placeholder} is an exposed secret (model: 0.88)"
                )

        cred_q_id = _find_preflight_question(preset, "credentials")
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
        if cred_count > 0 and cred_q_id and cred_q_id in nouls:
            nouls[cred_q_id].overridden_by = "preflight_scan"

        pii_q_id = _find_preflight_question(preset, "pii")
        pii_count = (
            redaction_details.get("by_type", {}).get("email_free_mail", 0)
            if redaction_details
            else 0
        )
        if pii_count > 0 and pii_q_id and pii_q_id in nouls:
            nouls[pii_q_id].overridden_by = "preflight_scan"

        has_prose_pii = bool(
            re.search(r"\b(Taro Yamada|Hanako Tanaka|Jane Doe|John Doe)\b", raw_content)
        )
        if "has_secrets" in nouls:
            nouls["has_secrets"].probability = 0.90 if has_prose_secret else 0.05
        if "has_pii" in nouls:
            nouls["has_pii"].probability = 0.90 if has_prose_pii else 0.05

        composite, _, _, _ = self._evaluate_thresholds_and_composite(
            preset, scores, nouls, choices, redaction_details=redaction_details
        )

        return DocumentEvalResult(
            filepath=filepath,
            filename=doc_filename,
            preset_name=preset.name,
            scores=scores,
            nouls=nouls,
            choices=choices,
            email_evaluations=email_evaluations,
            phone_evaluations=phone_evaluations,
            ip_evaluations=ip_evaluations,
            url_evaluations=url_evaluations,
            secret_evaluations=secret_evaluations,
            composite_score=composite,
            passed_thresholds=True,
            violations=[],
            warnings=[],
            usage={"input_tokens": 120 * api_calls, "output_tokens": 30 * api_calls},
            model=self.model or ("mock-openai" if self.provider == "openai" else "mock-jev"),
            was_truncated=was_truncated,
            api_calls=api_calls,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
            mock=True,
        )

    def _build_offline_result(
        self,
        filepath: str,
        preset: PresetConfig,
        was_truncated: bool,
        redaction_count: int,
        redaction_details: dict[str, Any] | None,
        filename: str | None = None,
        content: str | None = None,
    ) -> DocumentEvalResult:
        """Constructs an offline evaluation result using only local regex rules and sanitization."""
        doc_filename = filename or Path(filepath).name
        email_evaluations: list[EmailEvaluationResult] = []
        secret_evaluations: list[SecretEvaluationResult] = []
        phone_evaluations: list[PhoneEvaluationResult] = []
        ip_evaluations: list[IPEvaluationResult] = []
        url_evaluations: list[URLEvaluationResult] = []
        violations: list[str] = []
        warnings: list[str] = []

        redacted_emails = redaction_details.get("redacted_emails", []) if redaction_details else []
        for feature in redacted_emails:
            placeholder = feature["placeholder"]
            if feature.get("domain_type") == "free_mail":
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="personal",
                        decided_by="free_mail",
                    )
                )
                violations.append(
                    f"PII Exposure: {placeholder} is an individual address (free-mail)"
                )
            elif feature.get("known_role_word") or feature.get("matches_custom_role"):
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="role",
                        decided_by="free_mail",
                    )
                )
            else:
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="undecided",
                        decided_by="model",
                    )
                )

        redacted_secrets = (
            redaction_details.get("redacted_secrets", []) if redaction_details else []
        )
        for feature in redacted_secrets:
            placeholder = feature["placeholder"]
            if feature.get("is_known_format"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="secret",
                        decided_by="rule",
                    )
                )
            elif feature.get("placeholder_syntax"):
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="safe",
                        decided_by="rule",
                    )
                )
            else:
                secret_evaluations.append(
                    SecretEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="undecided",
                        decided_by="rule",
                    )
                )

        redacted_phones = redaction_details.get("redacted_phones", []) if redaction_details else []
        for feature in redacted_phones:
            placeholder = feature["placeholder"]
            if feature.get("is_support_prefix") or feature.get("looks_like_support"):
                phone_evaluations.append(
                    PhoneEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="support",
                        decided_by="rule",
                    )
                )
            else:
                phone_evaluations.append(
                    PhoneEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="personal",
                        decided_by="rule",
                    )
                )
                violations.append(f"PII Exposure: {placeholder} is an individual phone number")

        redacted_ips = redaction_details.get("redacted_ips", []) if redaction_details else []
        for feature in redacted_ips:
            placeholder = feature["placeholder"]
            if feature.get("is_documentation") or feature.get("is_loopback"):
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="safe",
                        decided_by="rule",
                    )
                )
            elif feature.get("is_private"):
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="sensitive",
                        decided_by="rule",
                    )
                )
                violations.append(
                    f"PII Exposure: {placeholder} is an internal/sensitive IP address"
                )
            else:
                ip_evaluations.append(
                    IPEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="safe",
                        decided_by="rule",
                    )
                )

        redacted_urls = redaction_details.get("redacted_urls", []) if redaction_details else []
        for feature in redacted_urls:
            placeholder = feature["placeholder"]
            if (
                feature.get("is_example_domain")
                or feature.get("is_public_common")
                or feature.get("is_loopback")
                or feature.get("is_documentation")
            ):
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="safe",
                        decided_by="rule",
                    )
                )
            elif feature.get("is_internal_tld"):
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="sensitive",
                        decided_by="rule",
                    )
                )
                violations.append(f"PII Exposure: {placeholder} is an internal/sensitive URL")
            else:
                url_evaluations.append(
                    URLEvaluationResult(
                        placeholder=placeholder,
                        features=feature,
                        outcome="safe",
                        decided_by="rule",
                    )
                )

        if redaction_details and "rule_violations" in redaction_details:
            for rv in redaction_details["rule_violations"]:
                if rv not in violations:
                    violations.append(rv)

        passed = len(violations) == 0

        return DocumentEvalResult(
            filepath=filepath,
            filename=doc_filename,
            preset_name=preset.name,
            scores={},
            nouls={},
            choices={},
            email_evaluations=email_evaluations,
            phone_evaluations=phone_evaluations,
            ip_evaluations=ip_evaluations,
            url_evaluations=url_evaluations,
            secret_evaluations=secret_evaluations,
            composite_score=None,
            passed_thresholds=passed,
            violations=violations,
            warnings=warnings,
            usage={"input_tokens": 0, "output_tokens": 0},
            model="offline-rules",
            was_truncated=was_truncated,
            api_calls=0,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
            mock=False,
        )
