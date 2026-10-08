"""Unit and regression tests for Japanese safety, PII, and secret fixtures."""

from pathlib import Path

import yaml

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.sanitizer import (
    extract_email_features,
    extract_phone_features,
)


def test_japanese_phone_features_and_shape():
    """Verify Japanese mobile phones vs support/switchboard numbers."""
    # Mobile phones (personal PII)
    m1 = extract_phone_features("090-9876-5432")
    assert m1["is_mobile"] is True
    assert m1["is_support_prefix"] is False
    assert m1["country_format"] == "JP"

    m2 = extract_phone_features("080-1111-2222")
    assert m2["is_mobile"] is True
    assert m2["is_support_prefix"] is False
    assert m2["country_format"] == "JP"

    m3 = extract_phone_features("070-5555-1234")
    assert m3["is_mobile"] is True
    assert m3["is_support_prefix"] is False
    assert m3["country_format"] == "JP"

    # Support / Switchboard lines (non-PII)
    tollfree = extract_phone_features("0120-123-456")
    assert tollfree["is_support_prefix"] is True

    navidial = extract_phone_features("0570-00-1122")
    assert navidial["is_support_prefix"] is True

    corp = extract_phone_features(
        "03-5555-0100", surrounding_text="本社代表電話番号: 03-5555-0100（代表窓口）"
    )
    assert corp["is_support_prefix"] is False
    assert corp["near_support_keyword"] is True
    assert corp["looks_like_support"] is True


def test_japanese_email_features_and_roles():
    """Verify Japanese role email patterns vs personal emails."""
    # Free-mail personal
    em_free = extract_email_features("taro.yamada@gmail.com")
    assert em_free["domain_type"] == "free_mail"

    # Known role words in Japanese enterprise
    for role_addr in [
        "jinji@acme-corp.co.jp",
        "keiri@acme-corp.co.jp",
        "somu@company.jp",
        "eigyo@corp.co.jp",
    ]:
        features = extract_email_features(role_addr)
        assert features["known_role_word"] is True
        assert features["domain_type"] == "corporate"

    # Individual corporate name
    em_indiv = extract_email_features("yamada.taro@acme-corp.co.jp")
    assert em_indiv["known_role_word"] is False
    assert em_indiv["local_part_shape"] == "dotted_name"


def test_japanese_safety_fixtures_offline_evaluation():
    """Verify that all Japanese safety fixtures match their ground-truth labels in offline mode."""
    fixtures_dir = Path("tests/fixtures/safety_ja")
    assert (fixtures_dir / "labels.yaml").exists()

    labels = yaml.safe_load((fixtures_dir / "labels.yaml").read_text(encoding="utf-8"))
    evaluator = TypeSafeEvaluator()
    preset = load_preset("safety")

    for doc_item in labels["documents"]:
        doc_path = fixtures_dir / doc_item["path"]
        expected = doc_item["expect"]

        res = evaluator.evaluate_document(doc_path, preset=preset, mask_secrets=True, offline=True)

        has_pii_exp = expected.get("has_pii")
        has_sec_exp = expected.get("has_secrets")

        actual_pii_personal = any(e.outcome == "personal" for e in res.email_evaluations) or any(
            p.outcome == "personal" for p in res.phone_evaluations
        )
        actual_secret = any(s.outcome == "secret" for s in res.secret_evaluations)

        if has_pii_exp == "present":
            assert actual_pii_personal is True, f"Expected personal PII in {doc_item['path']}"
            assert res.passed_thresholds is False
        elif has_pii_exp == "absent":
            assert actual_pii_personal is False, f"Expected no personal PII in {doc_item['path']}"

        if has_sec_exp == "present":
            assert actual_secret is True, f"Expected secret in {doc_item['path']}"
            assert res.passed_thresholds is False
        elif has_sec_exp == "absent":
            assert actual_secret is False, f"Expected no secret in {doc_item['path']}"
