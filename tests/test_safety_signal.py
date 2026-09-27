from unittest.mock import MagicMock
from click.testing import CliRunner
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.cli import main
from typesafe_eval.models import NoulResult, ScoreResult, ChoiceResult, PresetConfig, QuestionConfig

def test_deterministic_credential_override(tmp_path):
    doc = tmp_path / "secret.txt"
    doc.write_text("Here is sk-abcdef1234567890abcdef123456 confidential data", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    
    # Mock TypeSafe client response where Jev returned 0.38 for has_secrets
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=1.5, confidence=0.9, probabilities={})}
    mock_resp.nouls = {"has_secrets": MagicMock(noul=0.38), "has_pii": MagicMock(noul=0.15)}
    mock_resp.choices = {"policy_compliance": MagicMock(choice="violating", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    # State passed to Jev should include redactions
    state_arg = mock_client.system_one.call_args.kwargs["state"]
    assert "redactions" in state_arg
    assert state_arg["redactions"]["credentials"] >= 1

    # Model probability is preserved (Issue #7, #8, #19)
    assert result.nouls["has_secrets"].probability == 0.38
    assert result.nouls["has_secrets"].overridden_by == "preflight_scan"

    # Pre-flight scan enforces failure and transparently mentions model score
    assert not result.passed_thresholds
    assert any("detected by pre-flight scan (model: 0.38)" in v for v in result.violations)
    assert result.redaction_details["credentials"] >= 1

def test_preflight_override_when_model_absent(tmp_path):
    doc = tmp_path / "secret_unanswered.txt"
    doc.write_text("Here is sk-abcdef1234567890abcdef123456 confidential data", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {}
    mock_resp.nouls = {}  # Jev did not return has_secrets
    mock_resp.choices = {}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    # Pre-flight scan registers override with probability=None (Issue #19)
    assert result.nouls["has_secrets"].probability is None
    assert result.nouls["has_secrets"].overridden_by == "preflight_scan"
    assert not result.passed_thresholds
    assert any("detected by pre-flight scan" in v for v in result.violations)

def test_custom_preset_preflight_override(tmp_path):
    doc = tmp_path / "custom_secret.txt"
    doc.write_text("API token: apikey_1234567890abcdef123456", encoding="utf-8")

    preset = PresetConfig(
        name="custom_security",
        questions={
            "custom_secret_check": QuestionConfig(
                type="noul",
                label="Custom Secret Check",
                instructions="Check for secrets",
                preflight="credentials",
                max_threshold=0.2,
            )
        }
    )
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.nouls = {"custom_secret_check": MagicMock(noul=0.10)}
    mock_resp.scores = {}
    mock_resp.choices = {}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    res = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)
    assert not res.passed_thresholds
    assert res.nouls["custom_secret_check"].probability == 0.10
    assert res.nouls["custom_secret_check"].overridden_by == "preflight_scan"
    assert any("1 credential(s) detected by pre-flight scan (model: 0.10)" in v for v in res.violations)

def test_cli_no_mask_flag(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nSample content with apikey_1234567890abcdef123456.", encoding="utf-8")

    runner = CliRunner()
    # Default (masking enabled): output shows (N masked) indicator
    result_default = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run"])
    assert result_default.exit_code == 0
    assert "masked" in result_default.output

    # With --no-mask: output does not show masked indicator
    result_no_mask = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run", "--no-mask"])
    assert result_no_mask.exit_code == 0
    assert "masked" not in result_no_mask.output

def test_context_free_email_classification_regression(tmp_path):
    doc_personal = tmp_path / "personal.txt"
    doc_personal.write_text("Please forward the contract draft to taro.yamada1987@gmail.com for review.", encoding="utf-8")
    doc_role = tmp_path / "role.txt"
    doc_role.write_text("Please forward the contract draft to billing@company.com for review.", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {"has_secrets": MagicMock(noul=0.01), "has_pii": MagicMock(noul=0.15)}
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    # Evaluate personal email
    r_pers = evaluator.evaluate_document(str(doc_personal), preset=preset, mask_secrets=True)
    state_pers = mock_client.system_one.call_args.kwargs["state"]
    assert "[REDACTED_PERSONAL_EMAIL]" in state_pers["document"]
    assert state_pers["redactions"]["pii_personal"] == 1
    assert state_pers["redactions"]["pii_role"] == 0

    # Evaluate role email
    r_role = evaluator.evaluate_document(str(doc_role), preset=preset, mask_secrets=True)
    state_role = mock_client.system_one.call_args.kwargs["state"]
    assert "[REDACTED_ROLE_EMAIL]" in state_role["document"]
    assert state_role["redactions"]["pii_personal"] == 0
    assert state_role["redactions"]["pii_role"] == 1


def test_example_key_evaluation_regression(tmp_path):
    doc = tmp_path / "readme.md"
    doc.write_text(
        "## Setup\n\n```bash\nexport TYPESAFE_API_KEY=apikey_your_api_key_here_1234567890\n```\n",
        encoding="utf-8",
    )
    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.scores = {"confidentiality_risk": MagicMock(score=0.1, confidence=0.9, probabilities={})}
    mock_resp.nouls = {"has_secrets": MagicMock(noul=0.04), "has_pii": MagicMock(noul=0.01)}
    mock_resp.choices = {"policy_compliance": MagicMock(choice="compliant", confidence=0.9, probabilities={})}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)

    state_arg = mock_client.system_one.call_args.kwargs["state"]
    assert "[EXAMPLE_API_KEY]" in state_arg["document"]
    assert "apikey_your_api_key_here_1234567890" not in state_arg["document"]
    assert state_arg["redactions"]["examples"] == 1
    assert state_arg["redactions"]["credentials"] == 0

    assert result.nouls["has_secrets"].overridden_by is None
    assert result.passed_thresholds


def test_overridden_question_composite_contribution(tmp_path):
    # Issue #24: Overridden questions must contribute their model probability to the composite score
    doc = tmp_path / "secret.txt"
    doc.write_text("API token: apikey_1234567890abcdef123456", encoding="utf-8")

    preset = PresetConfig(
        name="custom_weighted",
        questions={
            "leak": QuestionConfig(
                type="noul",
                label="Leak",
                instructions="Check for secrets",
                preflight="credentials",
                weight=0.5,
                max_threshold=0.2,
            ),
            "clarity": QuestionConfig(
                type="score",
                label="Clarity",
                instructions="Clarity",
                weight=0.5,
                min_threshold=0.6,
            ),
        },
    )
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    # Leak model probability: 0.10, Clarity normalized score: 0.80 (score 1.6 / 2.0)
    mock_resp.nouls = {"leak": MagicMock(noul=0.10)}
    mock_resp.scores = {"clarity": MagicMock(score=1.6, confidence=0.9, probabilities={})}
    mock_resp.choices = {}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    result = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)
    # The preflight override fails the gate
    assert not result.passed_thresholds
    assert result.nouls["leak"].overridden_by == "preflight_scan"
    assert result.nouls["leak"].probability == 0.10
    # Composite must include leak (0.10 * 0.5 + 0.80 * 0.5 = 0.45)
    assert result.composite_score is not None
    assert abs(result.composite_score - 0.45) < 1e-4


def test_custom_preset_pii_preflight_override(tmp_path):
    # Issue #25: preflight: pii triggers override on personal emails, but not on role emails
    doc_personal = tmp_path / "personal.txt"
    doc_personal.write_text("Contact user at hanako.suzuki@gmail.com", encoding="utf-8")

    doc_role = tmp_path / "role.txt"
    doc_role.write_text("Contact team at support@company.com", encoding="utf-8")

    preset = PresetConfig(
        name="custom_pii_guard",
        questions={
            "pii_gate": QuestionConfig(
                type="noul",
                label="PII Check",
                instructions="Check for PII",
                preflight="pii",
                max_threshold=0.3,
            )
        },
    )
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.nouls = {"pii_gate": MagicMock(noul=0.05)}
    mock_resp.scores = {}
    mock_resp.choices = {}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    # Personal email: triggers preflight override
    res_pers = evaluator.evaluate_document(str(doc_personal), preset=preset, mask_secrets=True)
    assert not res_pers.passed_thresholds
    assert res_pers.nouls["pii_gate"].overridden_by == "preflight_scan"
    assert any("personal PII item(s) detected by pre-flight scan" in v for v in res_pers.violations)

    # Role email: does NOT trigger preflight override
    res_role = evaluator.evaluate_document(str(doc_role), preset=preset, mask_secrets=True)
    assert res_role.passed_thresholds
    assert res_role.nouls["pii_gate"].overridden_by is None


def test_evaluator_with_preset_custom_role_emails(tmp_path):
    from typesafe_eval.models import SanitizerConfig

    doc = tmp_path / "contact.txt"
    doc.write_text("Escalate to incident-commander@company.com or duty-lead@company.com", encoding="utf-8")

    preset = PresetConfig(
        name="custom_ops_audit",
        sanitizer=SanitizerConfig(role_emails=["incident-*", "*-lead"]),
        questions={
            "check": QuestionConfig(
                type="noul",
                label="Check",
                instructions="Check",
                preflight="pii",
                max_threshold=0.3,
            )
        },
    )
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.nouls = {"check": MagicMock(noul=0.01)}
    mock_resp.scores = {}
    mock_resp.choices = {}
    mock_resp.usage = None
    mock_resp.model = "mock-jev"
    mock_client.system_one.return_value = mock_resp
    evaluator._client = mock_client

    res = evaluator.evaluate_document(str(doc), preset=preset, mask_secrets=True)
    # Both emails match custom role patterns, so pii_role == 2, pii_personal == 0
    state = mock_client.system_one.call_args.kwargs["state"]
    assert state["redactions"]["pii_role"] == 2
    assert state["redactions"]["pii_personal"] == 0
    assert res.nouls["check"].overridden_by is None
    assert res.passed_thresholds



