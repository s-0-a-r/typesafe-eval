"""Evaluation engine wrapping TypeSafe System One API client."""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal

from typesafe_sdk import TypeSafeClient, Choice, Noul, Score, TypeSafeError

from typesafe_eval.models import (
    PresetConfig,
    DocumentEvalResult,
    ScoreResult,
    NoulResult,
    ChoiceResult,
    EmailEvaluationResult,
    PhoneEvaluationResult,
    IPEvaluationResult,
    URLEvaluationResult,
    SecretEvaluationResult,
    NEAR_THRESHOLD_MARGIN,
    CANDIDATE_DECISION_THRESHOLD,
)
from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

def _is_candidate_near_threshold(decided_by: str, prob: Optional[float]) -> bool:
    """Returns True if candidate outcome was model-decided and within margin of decision threshold."""
    if decided_by == "model" and prob is not None:
        return abs(prob - CANDIDATE_DECISION_THRESHOLD) <= NEAR_THRESHOLD_MARGIN + 1e-9
    return False

def _find_preflight_question(preset: PresetConfig, target: str) -> Optional[str]:
    """Finds the question ID mapped to a pre-flight scanner category."""
    for q_id, q_cfg in preset.questions.items():
        if q_cfg.preflight == target:
            return q_id
    if target == "credentials" and "has_secrets" in preset.questions:
        return "has_secrets"
    return None

class TypeSafeEvaluator:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self._client: Optional[TypeSafeClient] = None

    def _get_client(self) -> TypeSafeClient:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "No TypeSafe API key provided. Set the TYPESAFE_API_KEY environment variable "
                    "or pass --api-key / specify in configuration."
                )
            self._client = TypeSafeClient(api_key=self.api_key)
        return self._client

    def evaluate_document(
        self,
        filepath: str,
        preset: PresetConfig,
        mask_secrets: bool = True,
        max_chars: int = 25000,
        dry_run: bool = False,
    ) -> DocumentEvalResult:
        """Evaluates a single document against the specified preset."""
        path = Path(filepath)
        raw_content = path.read_text(encoding="utf-8")

        # 1. Sanitize (detection & feature extraction always run; mask controls substitution)
        custom_roles = preset.sanitizer.role_emails if preset.sanitizer else None
        content, redaction_count, redaction_details = mask_sensitive_data(
            raw_content, mask=mask_secrets, return_details=True, custom_role_patterns=custom_roles
        )

        # 2. Length check & truncation guard
        content, was_truncated = guard_document_length(content, max_chars=max_chars)

        # 3. Dry run bypass
        if dry_run:
            return self._build_mock_result(
                filepath=filepath,
                preset=preset,
                was_truncated=was_truncated,
                redaction_count=redaction_count,
                redaction_details=redaction_details,
            )

        # 4. Build SDK questions
        sdk_questions: Dict[str, Any] = {}
        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score":
                sdk_questions[q_id] = Score(
                    instructions=q_cfg.instructions,
                    criteria=q_cfg.criteria if q_cfg.criteria else ["Low", "Medium", "High"],
                )
            elif q_cfg.type == "noul":
                sdk_questions[q_id] = Noul(
                    instructions=q_cfg.instructions,
                )
            elif q_cfg.type == "choice":
                # Ensure criteria is dict
                criteria = q_cfg.criteria
                if isinstance(criteria, list):
                    criteria = {item: None for item in criteria}
                sdk_questions[q_id] = Choice(
                    instructions=q_cfg.instructions,
                    criteria=criteria,
                )

        # Dynamic per-candidate Noul questions
        redacted_emails = redaction_details.get("redacted_emails", []) if redaction_details else []
        for feature in redacted_emails:
            if feature.get("domain_type") == "corporate":
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("EMAIL_", "")
                q_id = f"email_pii_{num_suffix}"
                sdk_questions[q_id] = Noul(
                    instructions=(
                        f"Is {placeholder} an address of an individual person (not a shared role, team, or system mailbox)? "
                        f"Use the surrounding text and state.redacted_emails."
                    )
                )

        redacted_phones = redaction_details.get("redacted_phones", []) if redaction_details else []
        for feature in redacted_phones:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("PHONE_", "")
            q_id = f"phone_pii_{num_suffix}"
            sdk_questions[q_id] = Noul(
                instructions=(
                    f"Is {placeholder} a private or personal phone number of an individual (not a shared corporate switchboard, toll-free number, or customer support line)? "
                    f"Use the surrounding text and state.redacted_phones."
                )
            )

        redacted_ips = redaction_details.get("redacted_ips", []) if redaction_details else []
        for feature in redacted_ips:
            if not feature.get("is_documentation") and not feature.get("is_loopback"):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("IP_", "")
                q_id = f"ip_pii_{num_suffix}"
                sdk_questions[q_id] = Noul(
                    instructions=(
                        f"Is {placeholder} an internal, production, or sensitive IP address (not a documentation or public dummy IP)? "
                        f"Use the surrounding text and state.redacted_ips."
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
                sdk_questions[q_id] = Noul(
                    instructions=(
                        f"Is {placeholder} an internal, non-public, or sensitive endpoint or infrastructure URL (not a public internet service or example URL)? "
                        f"Use the surrounding text and state.redacted_urls."
                    )
                )

        redacted_secrets = redaction_details.get("redacted_secrets", []) if redaction_details else []
        for feature in redacted_secrets:
            if not feature.get("is_known_format") and not feature.get("placeholder_syntax"):
                placeholder = feature["placeholder"]
                num_suffix = placeholder.strip("[]").replace("SECRET_", "")
                q_id = f"secret_{num_suffix}"
                sdk_questions[q_id] = Noul(
                    instructions=(
                        f"Is the value represented by {placeholder} an actual secret, credential, or password (not an example, placeholder, or template)? "
                        f"Use the surrounding text and state.redacted_secrets."
                    )
                )

        # 5. Call TypeSafe System One (Jev)
        client = self._get_client()
        state: Dict[str, Any] = {
            "document": content,
            "filename": path.name,
        }
        if redaction_details and (redaction_details.get("total", 0) > 0 or redaction_details.get("examples", 0) > 0):
            state["redactions"] = {
                "credentials": redaction_details.get("credentials", 0),
                "pii": redaction_details.get("pii_personal", 0),
                "pii_personal": redaction_details.get("pii_personal", 0),
                "pii_role": redaction_details.get("pii_role", 0),
                "examples": redaction_details.get("examples", 0),
            }
        if redacted_emails:
            state["redacted_emails"] = redacted_emails
        if redacted_phones:
            state["redacted_phones"] = redacted_phones
        if redacted_ips:
            state["redacted_ips"] = redacted_ips
        if redacted_urls:
            state["redacted_urls"] = redacted_urls
        if redacted_secrets:
            # STRICT SAFETY: contains only metadata, never the raw secret value or hash
            state["redacted_secrets"] = redacted_secrets

        response = client.system_one(state=state, questions=sdk_questions)

        # 6. Parse answers
        scores: Dict[str, ScoreResult] = {}
        nouls: Dict[str, NoulResult] = {}
        choices: Dict[str, ChoiceResult] = {}

        for q_id, q_cfg in preset.questions.items():
            if q_cfg.type == "score" and q_id in response.scores:
                ans = response.scores[q_id]
                num_levels = len(q_cfg.criteria) if q_cfg.criteria else 3
                max_score = float(max(num_levels - 1, 1))
                norm_score = min(max(ans.score / max_score, 0.0), 1.0)
                scores[q_id] = ScoreResult(
                    score=ans.score,
                    max_score=max_score,
                    normalized_score=norm_score,
                    confidence=ans.confidence,
                    probabilities={str(k): v for k, v in ans.probabilities.items()} if ans.probabilities else {},
                )
            elif q_cfg.type == "noul" and q_id in response.nouls:
                ans = response.nouls[q_id]
                nouls[q_id] = NoulResult(
                    probability=ans.noul,
                )
            elif q_cfg.type == "choice" and q_id in response.choices:
                ans = response.choices[q_id]
                choices[q_id] = ChoiceResult(
                    choice=ans.choice,
                    confidence=ans.confidence,
                    probabilities={str(k): v for k, v in ans.probabilities.items()} if ans.probabilities else {},
                )

        email_violations: List[str] = []
        phone_violations: List[str] = []
        ip_violations: List[str] = []
        url_violations: List[str] = []
        secret_violations: List[str] = []

        # Emails
        email_evaluations: List[EmailEvaluationResult] = []
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
                prob = None
                if q_id in response.nouls:
                    prob = response.nouls[q_id].noul
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
        phone_evaluations: List[PhoneEvaluationResult] = []
        for feature in redacted_phones:
            placeholder = feature["placeholder"]
            num_suffix = placeholder.strip("[]").replace("PHONE_", "")
            q_id = f"phone_pii_{num_suffix}"
            prob = response.nouls[q_id].noul if q_id in response.nouls else None
            outcome: Literal["personal", "support", "undecided"] = "undecided"
            decided_by: Literal["model", "rule"] = "model"
            if feature.get("is_support_prefix"):
                outcome = "support"
                decided_by = "rule"
            elif prob is not None:
                outcome = "personal" if prob >= CANDIDATE_DECISION_THRESHOLD else "support"
            elif feature.get("looks_like_support"):
                outcome = "support"
            else:
                outcome = "personal"

            phone_evaluations.append(
                PhoneEvaluationResult(
                    placeholder=placeholder,
                    question_id=q_id if decided_by == "model" else None,
                    features=feature,
                    outcome=outcome,
                    probability=prob,
                    decided_by=decided_by,
                    near_threshold=_is_candidate_near_threshold(decided_by, prob),
                )
            )
            if outcome == "personal":
                prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                phone_violations.append(
                    f"PII Exposure: {placeholder} is an individual phone number{prob_str}"
                )

        # IPs
        ip_evaluations: List[IPEvaluationResult] = []
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
                prob = response.nouls[q_id].noul if q_id in response.nouls else None
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
        url_evaluations: List[URLEvaluationResult] = []
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
                prob = response.nouls[q_id].noul if q_id in response.nouls else None
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
        secret_evaluations: List[SecretEvaluationResult] = []
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
                prob = response.nouls[q_id].noul if q_id in response.nouls else None
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
        pii_count = redaction_details.get("pii_personal", 0) if redaction_details else 0
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

        has_sec_check = bool(_find_preflight_question(preset, "credentials") or "has_secrets" in preset.questions)
        has_pii_check = bool(_find_preflight_question(preset, "pii") or "has_pii" in preset.questions)

        if has_sec_check and secret_violations:
            violations.extend(secret_violations)
            passed = False
        if has_pii_check:
            all_pii_violations = email_violations + phone_violations + ip_violations + url_violations
            if all_pii_violations:
                violations.extend(all_pii_violations)
                passed = False

        usage_dict = None
        if response.usage:
            usage_dict = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

        return DocumentEvalResult(
            filepath=filepath,
            filename=path.name,
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
            model=response.model or "type-safe-one",
            was_truncated=was_truncated,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
        )

    def _evaluate_thresholds_and_composite(
        self,
        preset: PresetConfig,
        scores: Dict[str, ScoreResult],
        nouls: Dict[str, NoulResult],
        choices: Dict[str, ChoiceResult],
        redaction_details: Optional[Dict[str, Any]] = None,
    ):
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
                if q_cfg.min_threshold is not None and abs(val - q_cfg.min_threshold) <= NEAR_THRESHOLD_MARGIN + 1e-9:
                    is_near = True
                if q_cfg.max_threshold is not None and abs(val - q_cfg.max_threshold) <= NEAR_THRESHOLD_MARGIN + 1e-9:
                    is_near = True

            if q_cfg.type == "score" and q_id in scores:
                scores[q_id].near_threshold = is_near
            elif q_cfg.type == "noul" and q_id in nouls:
                nouls[q_id].near_threshold = is_near

            # Pre-flight scan override violation check
            if q_cfg.type == "noul" and q_id in nouls and nouls[q_id].overridden_by == "preflight_scan":
                passed = False
                label = q_cfg.label or q_id
                target_count = (
                    redaction_details.get("pii_personal", 0)
                    if q_cfg.preflight == "pii"
                    else redaction_details.get("credentials", 0)
                ) if redaction_details else 0
                item_name = "personal PII item(s)" if q_cfg.preflight == "pii" else "credential(s)"
                model_str = f" (model: {val:.2f})" if val is not None else ""
                violations.append(
                    f"{label}: {target_count} {item_name} detected by pre-flight scan{model_str}"
                )
            elif val is not None:
                # Threshold verification
                if q_cfg.min_threshold is not None and val < q_cfg.min_threshold:
                    label = q_cfg.label or q_id
                    if is_warning_only:
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
                    if is_warning_only:
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
        redaction_count: int,
        redaction_details: Optional[Dict[str, Any]] = None,
    ) -> DocumentEvalResult:
        """Returns mock evaluation result for dry-run or testing."""
        scores = {}
        nouls = {}
        choices = {}
        path = Path(filepath)
        content = path.read_text(encoding="utf-8") if path.is_file() else ""

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

        email_evaluations: List[EmailEvaluationResult] = []
        phone_evaluations: List[PhoneEvaluationResult] = []
        ip_evaluations: List[IPEvaluationResult] = []
        url_evaluations: List[URLEvaluationResult] = []
        secret_evaluations: List[SecretEvaluationResult] = []
        extra_violations: List[str] = []

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
                mock_prob = 0.10 if (feature.get("known_role_word") or feature.get("matches_custom_role")) else 0.80
                outcome_em: Literal["personal", "role", "undecided"] = "personal" if mock_prob >= CANDIDATE_DECISION_THRESHOLD else "role"
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
        has_prose_secret = bool(re.search(r"password\s+is\s+[^\s.,]+", content, re.IGNORECASE))
        redacted_secrets = redaction_details.get("redacted_secrets", []) if redaction_details else []
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

        has_any_secret_violation = any(s.outcome == "secret" for s in secret_evaluations) or has_prose_secret
        has_any_pii_violation = (
            any(e.outcome == "personal" for e in email_evaluations)
            or any(p.outcome == "personal" for p in phone_evaluations)
            or any(i.outcome == "sensitive" for i in ip_evaluations)
            or any(u.outcome == "sensitive" for u in url_evaluations)
        )

        cred_q_id = _find_preflight_question(preset, "credentials")
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
        if cred_count > 0 and cred_q_id and cred_q_id in nouls:
            nouls[cred_q_id].overridden_by = "preflight_scan"

        pii_q_id = _find_preflight_question(preset, "pii")
        pii_count = redaction_details.get("pii_personal", 0) if redaction_details else 0
        if pii_count > 0 and pii_q_id and pii_q_id in nouls:
            nouls[pii_q_id].overridden_by = "preflight_scan"

        has_prose_pii = bool(re.search(r"\b(Taro Yamada|Hanako Tanaka|Jane Doe|John Doe)\b", content))
        if "has_secrets" in nouls:
            nouls["has_secrets"].probability = 0.90 if has_prose_secret else 0.05
        if "has_pii" in nouls:
            nouls["has_pii"].probability = 0.90 if has_prose_pii else 0.05

        composite, passed, violations, warnings = self._evaluate_thresholds_and_composite(
            preset, scores, nouls, choices, redaction_details=redaction_details
        )
        has_sec_check = bool(_find_preflight_question(preset, "credentials") or "has_secrets" in preset.questions)
        has_pii_check = bool(_find_preflight_question(preset, "pii") or "has_pii" in preset.questions)

        if has_sec_check and any(s.outcome == "secret" for s in secret_evaluations):
            violations.extend([v for v in extra_violations if "Credential" in v])
            passed = False
        if has_pii_check and has_any_pii_violation:
            violations.extend([v for v in extra_violations if "PII" in v])
            passed = False

        return DocumentEvalResult(
            filepath=filepath,
            filename=path.name,
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
            passed_thresholds=passed,
            violations=violations,
            warnings=warnings,
            usage={"input_tokens": 120, "output_tokens": 30},
            model="mock-jev",
            was_truncated=was_truncated,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
        )
