"""Tests for per-candidate Noul evaluation (phone, IP, URL, secrets) and decoupled masking (#40)."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from typesafe_eval.cli import main
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.sanitizer import (
    mask_sensitive_data,
    extract_phone_features,
    extract_ip_features,
    extract_url_features,
    extract_secret_features,
)


def test_phone_features():
    # Toll-free and switchboard numbers
    f_0120 = extract_phone_features("0120-123-456")
    assert f_0120["looks_like_support"] is True
    assert f_0120["country_format"] == "JP"

    f_0800 = extract_phone_features("0800-888-9999")
    assert f_0800["looks_like_support"] is True

    f_switchboard = extract_phone_features("03-3500-1111", surrounding_text="Headquarters switchboard (代表)")
    assert f_switchboard["looks_like_support"] is True

    f_us_support = extract_phone_features("1-800-555-0199", surrounding_text="US Toll Free Support")
    assert f_us_support["looks_like_support"] is True
    assert f_us_support["country_format"] == "US"

    # Personal mobile numbers
    f_090 = extract_phone_features("090-1234-5678", surrounding_text="Call Taro at his personal cell")
    assert f_090["looks_like_support"] is False

    f_080 = extract_phone_features("080-9876-5432")
    assert f_080["looks_like_support"] is False

    f_us_direct = extract_phone_features("+1-415-555-2671", surrounding_text="Direct line to John Doe")
    assert f_us_direct["looks_like_support"] is False


def test_ip_features():
    # Loopback
    f_loop_v4 = extract_ip_features("127.0.0.1")
    assert f_loop_v4["is_loopback"] is True
    assert f_loop_v4["ip_type"] == "loopback"

    f_loop_v6 = extract_ip_features("::1")
    assert f_loop_v6["is_loopback"] is True
    assert f_loop_v6["ip_type"] == "loopback"

    # RFC 5737 & RFC 3849 Documentation ranges
    f_doc1 = extract_ip_features("192.0.2.1")
    assert f_doc1["is_documentation"] is True
    assert f_doc1["ip_type"] == "documentation"

    f_doc2 = extract_ip_features("198.51.100.42")
    assert f_doc2["is_documentation"] is True

    f_doc3 = extract_ip_features("203.0.113.199")
    assert f_doc3["is_documentation"] is True

    f_doc_v6 = extract_ip_features("2001:db8::1")
    assert f_doc_v6["is_documentation"] is True

    # Private RFC 1918 ranges
    f_priv10 = extract_ip_features("10.240.12.88")
    assert f_priv10["is_private"] is True
    assert f_priv10["ip_type"] == "private"

    f_priv172 = extract_ip_features("172.16.45.10")
    assert f_priv172["is_private"] is True

    f_priv192 = extract_ip_features("192.168.100.50")
    assert f_priv192["is_private"] is True


def test_url_features():
    # Example domains RFC 2606
    f_ex1 = extract_url_features("https://example.com/api/docs")
    assert f_ex1["is_example_domain"] is True
    assert "domain" not in f_ex1

    f_ex2 = extract_url_features("https://api.example.org/v1/events")
    assert f_ex2["is_example_domain"] is True

    f_local = extract_url_features("http://localhost:3000")
    assert f_local["is_example_domain"] is True

    # Internal TLDs
    f_internal = extract_url_features("http://consul.internal:8500")
    assert f_internal["is_internal_tld"] is True
    assert f_internal["suffix_class"] == ".internal"
    assert f_internal["matched_suffix"] == ".internal"
    assert "domain" not in f_internal

    f_corp = extract_url_features("ldap://directory.corp:389")
    assert f_corp["is_internal_tld"] is True
    assert f_corp["suffix_class"] == ".corp"
    assert f_corp["matched_suffix"] == ".corp"

    f_local_tld = extract_url_features("http://payment-gateway.local/v2/charge")
    assert f_local_tld["is_internal_tld"] is True
    assert f_local_tld["suffix_class"] == ".local"

    f_intra = extract_url_features("https://wiki.intra/engineering/architecture")
    assert f_intra["is_internal_tld"] is True
    assert f_intra["suffix_class"] == ".intra"

    # Public common
    f_gh = extract_url_features("https://github.com/s-0-a-r/typesafe-eval")
    assert f_gh["is_public_common"] is True

    # When mask=False, raw domain is retained in features
    f_unmasked = extract_url_features("http://consul.internal:8500", mask=False)
    assert f_unmasked["domain"] == "consul.internal"
    assert f_unmasked["suffix_class"] == ".internal"


def test_secret_safety_constraint():
    # Safety constraint: State NEVER contains the raw secret value, fragment, or hash!
    secret_value = "super_secret_production_password_12345!"
    features = extract_secret_features(
        key_name="DB_PASSWORD",
        raw_val=secret_value,
        surrounding_text="DB_PASSWORD=super_secret_production_password_12345!",
        is_known_format=False,
    )
    # Check that raw secret, fragment, or hash is not in features
    assert secret_value not in str(features)
    assert "super_secret" not in str(features)
    assert "12345!" not in str(features)
    assert "value" not in features
    assert "raw_value" not in features
    assert "hash" not in features
    # Check metadata fields
    assert features["key_name"] == "DB_PASSWORD"
    assert features["value_length"] == len(secret_value)
    assert "lower" in features["character_classes"]
    assert "digit" in features["character_classes"]
    assert "symbol" in features["character_classes"]
    assert features["placeholder_syntax"] is False


def test_secret_placeholder_syntax_and_allowlist():
    # Template syntax is identified as placeholder
    f_tmpl = extract_secret_features("DB_PASSWORD", "${DB_PASS}")
    assert f_tmpl["placeholder_syntax"] is True

    f_bracket = extract_secret_features("password", "<your-password>")
    assert f_bracket["placeholder_syntax"] is True

    f_dummy = extract_secret_features("token", "dummy_token_123")
    assert f_dummy["placeholder_syntax"] is True


def test_decoupled_masking_no_mask_flag(tmp_path):
    # Detection and feature extraction always run, even with mask=False (--no-mask)
    raw = (
        "Contact: 090-1234-5678, "
        "Server: 10.0.0.1, "
        "Registry: http://consul.internal:8500, "
        "Email: support@gmail.com, "
        "DB_PASSWORD=hunter2"
    )
    # Masked
    sanitized, count, details = mask_sensitive_data(raw, mask=True, return_details=True)
    assert count > 0
    assert "090-1234-5678" not in sanitized
    assert "10.0.0.1" not in sanitized
    assert "http://consul.internal:8500" not in sanitized
    assert "support@gmail.com" not in sanitized
    assert "hunter2" not in sanitized
    assert len(details["redacted_phones"]) == 1
    assert len(details["redacted_ips"]) == 1
    assert len(details["redacted_urls"]) == 1
    assert len(details["redacted_emails"]) == 1
    assert len(details["redacted_secrets"]) == 1

    # Unmasked (--no-mask): raw text is preserved, count is 0, but details are fully extracted
    unmasked, count_unmasked, details_unmasked = mask_sensitive_data(raw, mask=False, return_details=True)
    assert count_unmasked == 0
    assert unmasked == raw
    assert len(details_unmasked["redacted_phones"]) == 1
    assert len(details_unmasked["redacted_ips"]) == 1
    assert len(details_unmasked["redacted_urls"]) == 1
    assert len(details_unmasked["redacted_emails"]) == 1
    assert len(details_unmasked["redacted_secrets"]) == 1


def test_support_gmail_personal_by_rule_with_no_mask(tmp_path):
    # With --no-mask, support@gmail.com is STILL decided as personal by rule!
    doc = tmp_path / "gmail_test.md"
    doc.write_text("Our support team uses support@gmail.com for help.", encoding="utf-8")

    from unittest.mock import MagicMock
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {"has_secrets": MagicMock(noul=0.01), "has_pii": MagicMock(noul=0.05)}
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    # Real evaluation (with mocked client) and mask_secrets=False
    res = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=False)
    assert len(res.email_evaluations) == 1
    assert res.email_evaluations[0].outcome == "personal"
    assert res.email_evaluations[0].decided_by == "free_mail"
    assert not res.passed_thresholds
    assert any("PII Exposure" in v for v in res.violations)
    assert res.mock is False

    # Dry-run returns mock=True with verdict N/A
    res_dry = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=False, dry_run=True)
    assert res_dry.mock is True
    assert res_dry.email_evaluations[0].outcome == "personal"
    assert res_dry.email_evaluations[0].decided_by == "free_mail"


def test_all_40_fixtures_masked_and_unmasked(tmp_path):
    # All 40 fixtures in tests/fixtures/pii_secrets match expected verdicts masked and with --no-mask
    fixtures_dir = Path("tests/fixtures/pii_secrets")
    import yaml
    labels = yaml.safe_load((fixtures_dir / "labels.yaml").read_text(encoding="utf-8"))

    evaluator = TypeSafeEvaluator()
    preset = load_preset("safety")

    for doc_item in labels["documents"]:
        path = fixtures_dir / doc_item["path"]
        expect = doc_item["expect"]

        # Run masked
        res_masked = evaluator.evaluate_document(str(path), preset=preset, mask_secrets=True, dry_run=True)
        # Run unmasked (--no-mask)
        res_unmasked = evaluator.evaluate_document(str(path), preset=preset, mask_secrets=False, dry_run=True)

        for q_id, exp_verdict in expect.items():
            def is_present(res):
                q_cfg = preset.questions[q_id]
                thresh = q_cfg.max_threshold if q_cfg.max_threshold is not None else 0.5
                has_cand = False
                if q_id == "has_pii":
                    has_cand = (
                        any(e.outcome == "personal" for e in res.email_evaluations)
                        or any(p.outcome == "personal" for p in res.phone_evaluations)
                        or any(i.outcome == "sensitive" for i in res.ip_evaluations)
                        or any(u.outcome == "sensitive" for u in res.url_evaluations)
                    )
                elif q_id == "has_secrets":
                    has_cand = any(s.outcome == "secret" for s in res.secret_evaluations)
                noul_obj = res.nouls.get(q_id)
                is_preflight = noul_obj and noul_obj.overridden_by is not None
                doc_present = noul_obj and noul_obj.probability is not None and noul_obj.probability > thresh
                return has_cand or is_preflight or doc_present

            pres_masked = is_present(res_masked)
            pres_unmasked = is_present(res_unmasked)

            if exp_verdict == "absent":
                assert not pres_masked, f"Masked {doc_item['path']} {q_id} expected absent, was present"
                assert not pres_unmasked, f"Unmasked {doc_item['path']} {q_id} expected absent, was present"
            else:
                assert pres_masked, f"Masked {doc_item['path']} {q_id} expected present, was absent"
                assert pres_unmasked, f"Unmasked {doc_item['path']} {q_id} expected present, was absent"


def test_no_raw_values_in_state_outside_text_when_masking_on(tmp_path):
    """Asserts that with masking on, no raw email, phone, IP, URL host, or secret
    value from the document appears anywhere outside the document text in the state
    passed to system_one.
    """
    import json
    from unittest.mock import MagicMock

    raw_email = "alice.smith@engineering.corp"
    raw_phone = "090-9876-5432"
    raw_ip = "10.200.4.15"
    raw_url = "https://grafana.ops.acme.internal/d/x?orgId=1"
    raw_host = "grafana.ops.acme.internal"
    raw_secret_ambiguous = "sUpEr_SeCrEt_vAlUe_9876543210"
    raw_secret_prose = "hunter2_never_reveal"

    content = f"""# Operations Runbook

Contact: {raw_email}
Emergency: {raw_phone}
Internal IP: {raw_ip}
Dashboard: {raw_url}
API: api_key: {raw_secret_ambiguous}
Legacy note: the password is {raw_secret_prose}
"""
    doc = tmp_path / "runbook.md"
    doc.write_text(content, encoding="utf-8")

    evaluator = TypeSafeEvaluator(api_key="mock-key")
    preset = load_preset("safety")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {
        "has_secrets": MagicMock(noul=0.1),
        "has_pii": MagicMock(noul=0.1),
        "email_pii_1": MagicMock(noul=0.8),
        "phone_pii_1": MagicMock(noul=0.8),
        "ip_pii_1": MagicMock(noul=0.8),
        "url_pii_1": MagicMock(noul=0.8),
        "secret_1": MagicMock(noul=0.8),
    }
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    call_args = mock_client.system_one.call_args
    state = call_args.kwargs["state"]
    questions = call_args.kwargs["questions"]

    # 1. Inside document text: placeholders should replace sensitive data
    masked_text = state["document"]
    assert raw_email not in masked_text
    assert raw_phone not in masked_text
    assert raw_ip not in masked_text
    assert raw_url not in masked_text
    assert raw_host not in masked_text
    assert raw_secret_ambiguous not in masked_text

    # 2. Outside document text: state (excluding "document") and questions must NOT contain
    # any raw email, phone, IP, URL host, or secret value.
    state_outside_text = {k: v for k, v in state.items() if k != "document"}
    state_serialized = json.dumps(state_outside_text)
    questions_serialized = json.dumps({k: q.instructions for k, q in questions.items()})

    sensitive_tokens = [
        raw_email,
        "alice.smith",
        raw_phone,
        "9876-5432",
        raw_ip,
        raw_host,
        "grafana.ops.acme",
        "ops.acme.internal",
        raw_secret_ambiguous,
        raw_secret_prose,
    ]

    for token in sensitive_tokens:
        assert token not in state_serialized, f"Sensitive token '{token}' leaked into state outside text: {state_serialized}"
        assert token not in questions_serialized, f"Sensitive token '{token}' leaked into question instructions: {questions_serialized}"

    # 3. Verify URL feature structure has derived features only (no domain)
    assert "redacted_urls" in state
    assert len(state["redacted_urls"]) == 1
    url_feat = state["redacted_urls"][0]
    assert "domain" not in url_feat
    assert url_feat["is_internal_tld"] is True
    assert url_feat["suffix_class"] == ".internal"
    assert url_feat["is_example_domain"] is False


def test_chunking_candidate_questions_per_call_masked_and_unmasked(tmp_path):
    """B1: Masked behaviour must not change, and unmasked must match question sets per call."""
    from types import SimpleNamespace as NS

    class RecordingFakeClient:
        def __init__(self):
            self.calls = []
            self.states = []
        def system_one(self, state, questions):
            self.calls.append(sorted(list(questions.keys())))
            self.states.append(state)
            scores = {q: NS(score=0, confidence=0.9, probabilities={}) for q in questions if q == "confidentiality_risk"}
            choices = {q: NS(choice="compliant", confidence=0.9, probabilities={}) for q in questions if q == "policy_compliance"}
            nouls = {q: NS(noul=0.1) for q in questions if q not in ("confidentiality_risk", "policy_compliance")}
            return NS(usage=None, model="fake", scores=scores, choices=choices, nouls=nouls)

    doc = tmp_path / "long_doc.md"
    doc.write_text(
        "Contact taro.yamada@acme-corp.com or call +1-415-555-2671.\n\n"
        + "A" * 30000 + "\n\n"
        + "Visit http://internal-dashboard.corp.acme/metrics for details.\n\n"
        + "B" * 30000 + "\n\n",
        encoding="utf-8"
    )

    safety = load_preset("safety")
    expected_calls = [
        ["confidentiality_risk", "policy_compliance"],
        ["email_pii_1", "has_pii", "has_secrets", "phone_pii_1"],
        ["has_pii", "has_secrets", "url_pii_1"],
        ["has_pii", "has_secrets"],
    ]

    # 1. Masked
    ev_masked = TypeSafeEvaluator(api_key="mock")
    fake_masked = RecordingFakeClient()
    ev_masked._client = fake_masked
    ev_masked.evaluate_document(str(doc), preset=safety, mask_secrets=True, max_chars=25000)
    assert fake_masked.calls == expected_calls

    # 2. Unmasked
    ev_unmasked = TypeSafeEvaluator(api_key="mock")
    fake_unmasked = RecordingFakeClient()
    ev_unmasked._client = fake_unmasked
    ev_unmasked.evaluate_document(str(doc), preset=safety, mask_secrets=False, max_chars=25000)
    assert fake_unmasked.calls == expected_calls

    # 3. Verify internal raw mapping does not leak into state, and email/phone don't leak outside text
    for st in fake_unmasked.states:
        outside_text = {k: v for k, v in st.items() if k != "document"}
        assert "_raw_mapping" not in outside_text
        serialized = json.dumps(outside_text)
        assert "taro.yamada@acme-corp.com" not in serialized
        assert "taro.yamada" not in serialized
        assert "+1-415-555-2671" not in serialized
        assert "415-555-2671" not in serialized


def test_long_document_unmasked_candidate_evaluation_email_and_url(tmp_path):
    """B1: ~50k doc with corporate personal address or internal URL fails with outcome personal/sensitive both masked and unmasked."""
    from types import SimpleNamespace as NS

    class MockClient:
        def __init__(self, target_prefix):
            self.target_prefix = target_prefix
            self.calls = []
        def system_one(self, state, questions):
            self.calls.append(list(questions.keys()))
            scores = {q: NS(score=0, confidence=0.9, probabilities={}) for q in questions if q == "confidentiality_risk"}
            choices = {q: NS(choice="compliant", confidence=0.9, probabilities={}) for q in questions if q == "policy_compliance"}
            nouls = {
                q: NS(noul=0.95 if q.startswith(self.target_prefix) else 0.05)
                for q in questions if q not in ("confidentiality_risk", "policy_compliance")
            }
            return NS(usage=None, model="fake", scores=scores, choices=choices, nouls=nouls)

    safety = load_preset("safety")

    # Email test
    doc_email = tmp_path / "long_email.md"
    doc_email.write_text("Contact taro.yamada@acme-corp.com for access.\n\n" + ("filler paragraph text.\n\n" * 2000), encoding="utf-8")
    for mask in (True, False):
        ev = TypeSafeEvaluator(api_key="mock")
        ev._client = MockClient(target_prefix="email_pii")
        res = ev.evaluate_document(str(doc_email), preset=safety, mask_secrets=mask)
        assert res.passed_thresholds is False, f"Expected FAIL for mask={mask}"
        assert len(res.email_evaluations) == 1
        assert res.email_evaluations[0].outcome == "personal"
        assert res.email_evaluations[0].probability == 0.95

    # Internal URL test
    doc_url = tmp_path / "long_url.md"
    doc_url.write_text("Visit http://internal-dashboard.corp.acme/metrics for access.\n\n" + ("filler paragraph text.\n\n" * 2000), encoding="utf-8")
    for mask in (True, False):
        ev = TypeSafeEvaluator(api_key="mock")
        ev._client = MockClient(target_prefix="url_pii")
        res = ev.evaluate_document(str(doc_url), preset=safety, mask_secrets=mask)
        assert res.passed_thresholds is False, f"Expected FAIL for mask={mask}"
        assert len(res.url_evaluations) == 1
        assert res.url_evaluations[0].outcome == "sensitive"
        assert res.url_evaluations[0].probability == 0.95
