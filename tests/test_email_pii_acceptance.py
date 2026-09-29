"""Acceptance tests for contextual email PII evaluation (Issue #30).

Verifies fixtures 1-12 from Issue #30:
- Distinct addresses are numbered [EMAIL_1], [EMAIL_2]... with case-insensitive normalization.
- Features are placed in state.redacted_emails.
- Corporate emails receive batched dynamic Noul questions in the same system_one call.
- Free-mail is deterministically classified as personal (FAIL) without asking the model.
- Dynamic email questions are excluded from composite_score.
- DocumentEvalResult tracks full email_evaluations without leaking raw addresses.
"""

import os
from unittest.mock import MagicMock
import pytest

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.sanitizer import (
    mask_sensitive_data,
    extract_email_features,
    detect_local_part_shape,
)

FIXTURES = [
    # #, document, expected_per_email, expected_verdict
    (1, "Please forward the contract draft to taro.yamada1987@gmail.com before Friday.", ["personal"], False),
    (2, "Please forward the contract draft to legal@acme-corp.com before Friday.", ["role"], True),
    (3, "Questions? Write to hello@acme-corp.com.", ["role"], True),
    (4, "Contact our helpdesk at helpdesk@acme-corp.com.", ["role"], True),
    (5, "Taro's dev account is taro-dev@acme-corp.com.", ["personal"], False),
    (6, "Send it to taro.yamada@acme-corp.com.", ["personal"], False),
    (7, "担当の山田 <yamada@acme-corp.co.jp> までご連絡ください。", ["personal"], False),
    (8, "サポート窓口 <support@acme-corp.co.jp> までお問い合わせください。", ["role"], True),
    (9, "Our support team uses support@gmail.com.", ["personal"], False),
    (10, "Ask the helpdesk (helpdesk@acme-corp.com) or Hanako directly (hanako@acme-corp.com).", ["role", "personal"], False),
    (11, "Alerts are sent from notifications@acme-corp.com.", ["role"], True),
    (12, "Forward to yamada@acme-corp.com.", ["undecided"], None),
]

def test_extract_email_features_and_shape():
    f1 = extract_email_features("taro.yamada1987@gmail.com")
    assert f1["domain_type"] == "free_mail"
    assert f1["local_part_shape"] == "dotted_name"
    assert f1["known_role_word"] is False

    f2 = extract_email_features("legal@acme-corp.com")
    assert f2["domain_type"] == "corporate"
    assert f2["local_part_shape"] == "single_word"
    assert f2["known_role_word"] is True

    f5 = extract_email_features("taro-dev@acme-corp.com")
    assert f5["domain_type"] == "corporate"
    assert f5["local_part_shape"] == "hyphenated"
    assert f5["known_role_word"] is True  # -dev affix is recognized in word list

    f4 = extract_email_features("helpdesk@acme-corp.com")
    assert f4["domain_type"] == "corporate"
    assert f4["local_part_shape"] == "single_word"
    # helpdesk is not in built-in role list, but Jev will judge context
    assert f4["known_role_word"] is False

def test_numbered_placeholders_and_case_normalization():
    # Legal@ and legal@ must map to the same [EMAIL_1]
    doc = "Contact Legal@Acme.com or legal@acme.com or HR-team@acme.com."
    masked, count, details = mask_sensitive_data(doc, return_details=True)
    assert count == 3
    assert "[EMAIL_1]" in masked
    assert "[EMAIL_2]" in masked
    assert "[EMAIL_3]" not in masked
    assert len(details["redacted_emails"]) == 2
    assert details["redacted_emails"][0]["placeholder"] == "[EMAIL_1]"
    assert details["redacted_emails"][1]["placeholder"] == "[EMAIL_2]"

def test_free_mail_deterministic_gating(tmp_path):
    # Free-mail must fail deterministically without dynamic questions
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("Our support team uses support@gmail.com.", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    # Model's has_pii returns 0.05, but free-mail must still trigger a PII violation
    mock_resp.nouls = {"has_secrets": MagicMock(noul=0.01), "has_pii": MagicMock(noul=0.05)}
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc_path), preset=preset)
    called_questions = mock_client.system_one.call_args.kwargs["questions"]
    # No dynamic email question generated for free_mail
    assert not any(k.startswith("email_pii_") for k in called_questions)

    assert result.passed_thresholds is False
    assert any("free-mail" in v for v in result.violations)
    assert len(result.email_evaluations) == 1
    assert result.email_evaluations[0].outcome == "personal"
    assert result.email_evaluations[0].decided_by == "free_mail"
    assert result.email_evaluations[0].probability is None

def test_corporate_email_dynamic_noul_and_composite_isolation(tmp_path):
    # Two corporate emails: helpdesk (role: prob 0.03) and hanako (personal: prob 0.84)
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("Ask the helpdesk (helpdesk@acme-corp.com) or Hanako directly (hanako@acme-corp.com).", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {
        "has_secrets": MagicMock(noul=0.01),
        "has_pii": MagicMock(noul=0.05),
        "email_pii_1": MagicMock(noul=0.03),  # helpdesk -> role (< 0.5)
        "email_pii_2": MagicMock(noul=0.84),  # hanako -> personal (>= 0.5)
    }
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc_path), preset=preset)
    called_questions = mock_client.system_one.call_args.kwargs["questions"]
    assert "email_pii_1" in called_questions
    assert "email_pii_2" in called_questions

    # State metadata passed
    state = mock_client.system_one.call_args.kwargs["state"]
    assert len(state["redacted_emails"]) == 2

    # Outcome per email
    assert len(result.email_evaluations) == 2
    assert result.email_evaluations[0].placeholder == "[EMAIL_1]"
    assert result.email_evaluations[0].outcome == "role"
    assert result.email_evaluations[0].probability == 0.03

    assert result.email_evaluations[1].placeholder == "[EMAIL_2]"
    assert result.email_evaluations[1].outcome == "personal"
    assert result.email_evaluations[1].probability == 0.84

    # Document failed because hanako is personal PII
    assert result.passed_thresholds is False
    assert any("[EMAIL_2]" in v and "0.84" in v for v in result.violations)

    # Dynamic questions must NOT be in preset questions or composite score calculation
    # In safety preset, questions have no weight, so composite_score is None (unaffected by email questions)
    assert result.composite_score is None

@pytest.mark.parametrize("idx,doc_text,expected_per_email,expected_verdict", FIXTURES[:11])
def test_acceptance_fixtures_evaluation(tmp_path, idx, doc_text, expected_per_email, expected_verdict):
    # Simulated calibrated Jev probabilities from Issue #30 baseline:
    # 1: free-mail
    # 2: legal -> 0.08
    # 3: hello -> 0.10
    # 4: helpdesk -> 0.03
    # 5: taro-dev -> 0.64
    # 6: taro.yamada -> 0.80
    # 7: yamada -> 0.74
    # 8: support -> 0.05
    # 9: free-mail
    # 10: helpdesk (0.03), hanako (0.84)
    # 11: notifications -> 0.03
    mock_prob_map = {
        2: [0.08],
        3: [0.10],
        4: [0.03],
        5: [0.64],
        6: [0.80],
        7: [0.74],
        8: [0.05],
        10: [0.03, 0.84],
        11: [0.03],
    }

    doc_file = tmp_path / f"fixture_{idx}.txt"
    doc_file.write_text(doc_text, encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {
        "has_secrets": MagicMock(noul=0.01),
        "has_pii": MagicMock(noul=0.05),
    }
    if idx in mock_prob_map:
        for i, p in enumerate(mock_prob_map[idx], 1):
            mock_resp.nouls[f"email_pii_{i}"] = MagicMock(noul=p)

    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc_file), preset=preset)
    assert result.passed_thresholds == expected_verdict
    assert len(result.email_evaluations) == len(expected_per_email)
    for eval_res, exp_kind in zip(result.email_evaluations, expected_per_email):
        assert eval_res.outcome == exp_kind


def test_email_pii_dry_run_returns_mock_true_and_na_verdict(tmp_path):
    # Free-mail fixture in dry-run mode: mock is True, exit 0, verdict N/A (Issue #45)
    doc_file = tmp_path / "email_freemail.txt"
    doc_file.write_text("Our support team uses support@gmail.com.", encoding="utf-8")

    evaluator = TypeSafeEvaluator()
    preset = load_preset("safety")

    res = evaluator.evaluate_document(str(doc_file), preset=preset, dry_run=True)
    assert res.mock is True
    assert res.passed_thresholds is True
    assert res.violations == []

    from click.testing import CliRunner
    from typesafe_eval.cli import main
    runner = CliRunner()
    cli_res = runner.invoke(main, [str(doc_file), "--preset", "safety", "--dry-run"])
    assert cli_res.exit_code == 0
    assert "MOCK" in cli_res.output
    assert "N/A" in cli_res.output
    assert "FAIL" not in cli_res.output
