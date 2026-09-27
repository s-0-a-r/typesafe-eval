"""Evaluation engine wrapping TypeSafe System One API client."""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from typesafe_sdk import TypeSafeClient, Choice, Noul, Score, TypeSafeError

from typesafe_eval.models import (
    PresetConfig,
    DocumentEvalResult,
    ScoreResult,
    NoulResult,
    ChoiceResult,
    EmailEvaluationResult,
)
from typesafe_eval.sanitizer import mask_sensitive_data, guard_document_length

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

        # 1. Sanitize
        redaction_count = 0
        redaction_details: Dict[str, Any] = {}
        content = raw_content
        if mask_secrets:
            custom_roles = preset.sanitizer.role_emails if preset.sanitizer else None
            content, redaction_count, redaction_details = mask_sensitive_data(
                content, return_details=True, custom_role_patterns=custom_roles
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

        # Dynamic per-email Noul questions for corporate domains (batched)
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

        # 5. Call TypeSafe System One (Jev)
        client = self._get_client()
        state: Dict[str, Any] = {
            "document": content,
            "filename": path.name,
        }
        if redaction_details and (redaction_details.get("total", 0) > 0 or redaction_details.get("examples", 0) > 0):
            state["redactions"] = {
                "credentials": redaction_details.get("credentials", 0),
                "pii": redaction_details.get("pii", 0),
                "pii_personal": redaction_details.get("pii_personal", 0),
                "pii_role": redaction_details.get("pii_role", 0),
                "examples": redaction_details.get("examples", 0),
            }
        if redacted_emails:
            state["redacted_emails"] = redacted_emails
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

        # Evaluate and aggregate emails
        email_evaluations: List[EmailEvaluationResult] = []
        email_violations: List[str] = []

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
                    outcome = "personal" if prob >= 0.5 else "role"

                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome,
                        probability=prob,
                        decided_by="model",
                    )
                )
                if outcome == "personal":
                    prob_str = f" (model: {prob:.2f})" if prob is not None else ""
                    email_violations.append(
                        f"PII Exposure: {placeholder} is an individual address{prob_str}"
                    )

        # Deterministic pre-flight enforcement for credentials & PII:
        # If pre-flight masking detected credentials or personal PII, record the override
        # on the configured target question without overwriting the model's raw probability.
        cred_q_id = _find_preflight_question(preset, "credentials")
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0

        if mask_secrets and cred_count > 0 and cred_q_id:
            if cred_q_id in nouls:
                nouls[cred_q_id].overridden_by = "preflight_scan"
            else:
                nouls[cred_q_id] = NoulResult(
                    probability=None,
                    overridden_by="preflight_scan",
                )

        pii_q_id = _find_preflight_question(preset, "pii")
        pii_count = redaction_details.get("pii_personal", 0) if redaction_details else 0

        if mask_secrets and pii_count > 0 and pii_q_id:
            if pii_q_id in nouls:
                nouls[pii_q_id].overridden_by = "preflight_scan"
            else:
                nouls[pii_q_id] = NoulResult(
                    probability=None,
                    overridden_by="preflight_scan",
                )

        # 7. Compute deterministic composite score and threshold check
        composite_score, passed, violations = self._evaluate_thresholds_and_composite(
            preset=preset,
            scores=scores,
            nouls=nouls,
            choices=choices,
            redaction_details=redaction_details,
        )

        if email_violations:
            violations.extend(email_violations)
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
            composite_score=composite_score,
            passed_thresholds=passed,
            violations=violations,
            usage=usage_dict,
            model=response.model,
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
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0

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
                    passed = False
                    label = q_cfg.label or q_id
                    violations.append(
                        f"{label}: score {val:.2f} is below required minimum {q_cfg.min_threshold:.2f}"
                    )
                if q_cfg.max_threshold is not None and val > q_cfg.max_threshold:
                    passed = False
                    label = q_cfg.label or q_id
                    violations.append(
                        f"{label}: risk {val:.2f} exceeds allowed maximum {q_cfg.max_threshold:.2f}"
                    )

        composite = (weighted_sum / total_weight) if total_weight > 0 else None
        return composite, passed, violations

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

        cred_q_id = _find_preflight_question(preset, "credentials")
        cred_count = redaction_details.get("credentials", 0) if redaction_details else 0
        if cred_count > 0 and cred_q_id and cred_q_id in nouls:
            nouls[cred_q_id].overridden_by = "preflight_scan"

        pii_q_id = _find_preflight_question(preset, "pii")
        pii_count = redaction_details.get("pii_personal", 0) if redaction_details else 0
        if pii_count > 0 and pii_q_id and pii_q_id in nouls:
            nouls[pii_q_id].overridden_by = "preflight_scan"

        email_evaluations: List[EmailEvaluationResult] = []
        email_violations: List[str] = []
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
                email_violations.append(
                    f"PII Exposure: {placeholder} is an individual address (free-mail)"
                )
            else:
                mock_prob = 0.10 if (feature.get("known_role_word") or feature.get("matches_custom_role")) else 0.80
                outcome: Literal["personal", "role", "undecided"] = "personal" if mock_prob >= 0.5 else "role"
                email_evaluations.append(
                    EmailEvaluationResult(
                        placeholder=placeholder,
                        question_id=q_id,
                        features=feature,
                        outcome=outcome,
                        probability=mock_prob,
                        decided_by="model",
                    )
                )
                if outcome == "personal":
                    email_violations.append(
                        f"PII Exposure: {placeholder} is an individual address (model: {mock_prob:.2f})"
                    )

        composite, passed, violations = self._evaluate_thresholds_and_composite(
            preset, scores, nouls, choices, redaction_details=redaction_details
        )
        if email_violations:
            violations.extend(email_violations)
            passed = False

        return DocumentEvalResult(
            filepath=filepath,
            filename=path.name,
            preset_name=preset.name,
            scores=scores,
            nouls=nouls,
            choices=choices,
            email_evaluations=email_evaluations,
            composite_score=composite,
            passed_thresholds=passed,
            violations=violations,
            usage={"input_tokens": 120, "output_tokens": 30},
            model="mock-jev",
            was_truncated=was_truncated,
            redactions_count=redaction_count,
            redaction_details=redaction_details,
        )
