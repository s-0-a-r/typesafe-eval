from unittest.mock import MagicMock
from click.testing import CliRunner
from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.cli import main
from typesafe_eval.models import NoulResult, ScoreResult, ChoiceResult

def test_deterministic_credential_override(tmp_path):
    doc = tmp_path / "secret.txt"
    doc.write_text("Here is sk-abcdef1234567890abcdef123456 confidential data", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(api_key="mock-key")
    
    # Mock TypeSafe client response where Jev under-scored has_secrets (e.g. 0.38)
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

    # has_secrets should be deterministically overridden to 1.0
    assert result.nouls["has_secrets"].probability == 1.0
    assert not result.passed_thresholds
    assert any("Credential Exposure" in v for v in result.violations)
    assert result.redaction_details["credentials"] >= 1

def test_cli_no_mask_flag(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("# Test Document\nSample content with apikey_1234567890abcdef123456.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(doc), "--preset", "quality", "--dry-run", "--no-mask"])
    assert result.exit_code == 0
    assert "TypeSafe Evaluation Report" in result.output
