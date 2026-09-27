"""Tests for per-candidate Noul evaluation (phone, IP, URL, secrets) and decoupled masking (#40)."""

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

    f_ex2 = extract_url_features("https://api.example.org/v1/events")
    assert f_ex2["is_example_domain"] is True

    f_local = extract_url_features("http://localhost:3000")
    assert f_local["is_example_domain"] is True

    # Internal TLDs
    f_internal = extract_url_features("http://consul.internal:8500")
    assert f_internal["is_internal_tld"] is True

    f_corp = extract_url_features("ldap://directory.corp:389")
    assert f_corp["is_internal_tld"] is True

    f_local_tld = extract_url_features("http://payment-gateway.local/v2/charge")
    assert f_local_tld["is_internal_tld"] is True

    f_intra = extract_url_features("https://wiki.intra/engineering/architecture")
    assert f_intra["is_internal_tld"] is True

    # Public common
    f_gh = extract_url_features("https://github.com/s-0-a-r/typesafe-eval")
    assert f_gh["is_public_common"] is True


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

    evaluator = TypeSafeEvaluator()
    preset = load_preset("safety")

    # Dry-run with mask_secrets=False
    res = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=False, dry_run=True)
    assert len(res.email_evaluations) == 1
    assert res.email_evaluations[0].outcome == "personal"
    assert res.email_evaluations[0].decided_by == "free_mail"
    assert not res.passed_thresholds
    assert any("PII Exposure" in v for v in res.violations)


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
            prob_masked = res_masked.nouls[q_id].probability
            prob_unmasked = res_unmasked.nouls[q_id].probability

            if exp_verdict == "absent":
                assert prob_masked < 0.5, f"Masked {doc_item['path']} {q_id} expected absent (<0.5), got {prob_masked}"
                assert prob_unmasked < 0.5, f"Unmasked {doc_item['path']} {q_id} expected absent (<0.5), got {prob_unmasked}"
            else:
                assert prob_masked >= 0.5, f"Masked {doc_item['path']} {q_id} expected present (>=0.5), got {prob_masked}"
                assert prob_unmasked >= 0.5, f"Unmasked {doc_item['path']} {q_id} expected present (>=0.5), got {prob_unmasked}"
