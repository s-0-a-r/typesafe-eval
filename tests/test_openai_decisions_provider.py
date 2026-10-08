"""Unit and integration tests for OpenAIDecisionsProvider."""

from unittest.mock import MagicMock, patch

import pytest

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.exceptions import AuthenticationError, ConfigurationError
from typesafe_eval.presets import load_preset
from typesafe_eval.providers.base import (
    ChoiceOutput,
    DecisionQuestion,
    DecisionResponse,
    NoulOutput,
    ScoreOutput,
)
from typesafe_eval.providers.factory import create_provider
from typesafe_eval.providers.openai import OpenAIDecisionsProvider


def test_openai_provider_initialization():
    provider = OpenAIDecisionsProvider(api_key="sk-mock-key", model="gpt-6-luna")
    assert provider.default_model == "gpt-6-luna"
    assert provider.model == "gpt-6-luna"
    assert provider.api_key == "sk-mock-key"


def test_openai_provider_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIDecisionsProvider(api_key=None)
    with pytest.raises(AuthenticationError, match="No OpenAI API key provided"):
        provider.decide(state={}, questions={})


def test_openai_provider_serialization_and_deserialization():
    provider = OpenAIDecisionsProvider(api_key="sk-mock-test")

    mock_resp_json = {
        "model": "gpt-6-luna",
        "usage": {"input_tokens": 150, "output_tokens": 25},
        "answers": [
            {
                "name": "has_secrets",
                "type": "predicate",
                "probability": 0.05,
            },
            {
                "name": "confidentiality_risk",
                "type": "score",
                "score": 1.0,
                "confidence": 0.95,
                "probabilities": [
                    {"value": 0, "label": "0", "probability": 0.1},
                    {"value": 1, "label": "1", "probability": 0.85},
                    {"value": 2, "label": "2", "probability": 0.05},
                ],
            },
            {
                "name": "policy_compliance",
                "type": "choice",
                "choice": "compliant",
                "confidence": 0.98,
                "probabilities": [
                    {"value": "compliant", "probability": 0.98},
                    {"value": "violating", "probability": 0.02},
                ],
            },
        ],
    }

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = mock_resp_json
    mock_http_resp.raise_for_status = MagicMock()

    questions = {
        "has_secrets": DecisionQuestion(
            type="noul",
            instructions="Does this contain secrets?",
        ),
        "confidentiality_risk": DecisionQuestion(
            type="score",
            instructions="Evaluate business risk.",
            criteria=["Low", "Medium", "High"],
        ),
        "policy_compliance": DecisionQuestion(
            type="choice",
            instructions="Assess corporate compliance.",
            criteria={"compliant": "Safe", "violating": "Unsafe"},
        ),
    }

    state = {
        "document": "This is a clean test document.",
        "filename": "test.md",
    }

    with patch("httpx.Client.post", return_value=mock_http_resp) as mock_post:
        resp = provider.decide(state=state, questions=questions)

        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        json_body = call_kwargs["json"]

        assert json_body["model"] == "gpt-6-luna"
        assert json_body["input"] == "This is a clean test document."

        # Check questions serialization
        questions_req = {q["name"]: q for q in json_body["questions"]}
        assert questions_req["has_secrets"]["type"] == "predicate"
        assert questions_req["confidentiality_risk"]["type"] == "score"
        assert len(questions_req["confidentiality_risk"]["levels"]) == 3
        assert questions_req["policy_compliance"]["type"] == "choice"
        assert len(questions_req["policy_compliance"]["choices"]) == 2

        # Check response mapping
        assert isinstance(resp, DecisionResponse)
        assert resp.model == "gpt-6-luna"
        assert resp.usage.input_tokens == 150
        assert resp.usage.output_tokens == 25

        assert isinstance(resp.nouls["has_secrets"], NoulOutput)
        assert resp.nouls["has_secrets"].noul == 0.05

        assert isinstance(resp.scores["confidentiality_risk"], ScoreOutput)
        assert resp.scores["confidentiality_risk"].score == 1.0

        assert isinstance(resp.choices["policy_compliance"], ChoiceOutput)
        assert resp.choices["policy_compliance"].choice == "compliant"


def test_openai_provider_backward_compat_decisions_dict():
    """Ensure backward compatibility if response uses legacy decisions dict."""
    provider = OpenAIDecisionsProvider(api_key="sk-mock-test")

    mock_resp_json = {
        "model": "gpt-6-luna",
        "decisions": {
            "has_secrets": {
                "type": "predicate",
                "probability": 0.02,
            },
        },
    }

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = mock_resp_json
    mock_http_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_http_resp):
        resp = provider.decide(
            state={"document": "doc"},
            questions={"has_secrets": DecisionQuestion(type="noul", instructions="sec?")},
        )
        assert resp.nouls["has_secrets"].noul == 0.02


def test_openai_provider_transient_error_retry():
    provider = OpenAIDecisionsProvider(api_key="sk-mock-key", initial_backoff=0.01)

    fail_resp = MagicMock()
    fail_resp.status_code = 429

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {
        "model": "gpt-6-luna",
        "decisions": {"q1": {"type": "predicate", "probability": 0.1}},
    }
    ok_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", side_effect=[fail_resp, ok_resp]) as mock_post:
        resp = provider.decide(
            state={"document": "test"},
            questions={"q1": DecisionQuestion(type="noul", instructions="test")},
        )
        assert mock_post.call_count == 2
        assert resp.nouls["q1"].noul == 0.1


def test_provider_factory():
    p_typesafe = create_provider("typesafe", api_key="ts-key")
    assert p_typesafe.default_model == "jev-1.13.0"

    p_openai = create_provider("openai", api_key="sk-key")
    assert p_openai.default_model == "gpt-6-luna"

    with pytest.raises(ConfigurationError):
        create_provider("invalid-backend")


def test_evaluator_with_openai_provider(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text("# API Spec\nInternal endpoint at https://api.internal/v1.", encoding="utf-8")

    preset = load_preset("safety")
    evaluator = TypeSafeEvaluator(
        api_key="sk-mock-eval",
        provider="openai",
        model="gpt-6-luna",
    )

    mock_resp = {
        "model": "gpt-6-luna",
        "decisions": {
            "has_secrets": {"type": "predicate", "probability": 0.02},
            "has_pii": {"type": "predicate", "probability": 0.03},
            "confidentiality_risk": {
                "type": "score",
                "score": 1.0,
                "confidence": 0.9,
                "probabilities": {"0": 0.2, "1": 0.8},
            },
            "policy_compliance": {
                "type": "choice",
                "choice": "compliant",
                "confidence": 0.95,
                "probabilities": {"compliant": 0.95},
            },
            "url_pii_1": {"type": "predicate", "probability": 0.55},  # Near threshold!
        },
    }

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = mock_resp
    mock_http_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_http_resp):
        res = evaluator.evaluate_document(str(doc), preset=preset)

        assert res.model == "gpt-6-luna"
        assert res.passed_thresholds is False  # 0.55 > 0.5 triggers violation
        assert len(res.violations) == 1
        assert "PII Exposure: [URL_1]" in res.violations[0]
        assert res.nouls["has_secrets"].probability == 0.02
        assert res.scores["confidentiality_risk"].score == 1.0

        # Candidate check: Near threshold flag
        url_evals = res.url_evaluations
        assert len(url_evals) == 1
        assert url_evals[0].probability == 0.55
        assert url_evals[0].near_threshold is True  # abs(0.55 - 0.50) <= 0.10


def test_openai_provider_choice_with_none_descriptions():
    """Verify that choice options with None values (dict.fromkeys) are not dropped."""
    provider = OpenAIDecisionsProvider(api_key="sk-test")
    questions = {
        "format": DecisionQuestion(
            type="choice",
            instructions="Select format",
            criteria={"json": None, "yaml": None},
        )
    }
    mock_resp = {
        "model": "gpt-6-luna",
        "decisions": {"format": {"type": "choice", "choice": "json", "confidence": 0.99}},
    }
    mock_http_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    mock_http_resp.json.return_value = mock_resp

    with patch("httpx.Client.post", return_value=mock_http_resp) as mock_post:
        resp = provider.decide(state={"document": "test"}, questions=questions)
        call_json = mock_post.call_args.kwargs["json"]
        opts = call_json["questions"][0]["choices"]
        assert len(opts) == 2
        assert opts[0] == {"value": "json", "description": "json"}
        assert opts[1] == {"value": "yaml", "description": "yaml"}
        assert resp.choices["format"].choice == "json"


def test_cli_openai_missing_key_exit_3(tmp_path):
    """AC parity: Missing OPENAI_API_KEY returns Exit 3 (Runtime Error)."""
    from click.testing import CliRunner

    from typesafe_eval.cli import main

    doc = tmp_path / "test.md"
    doc.write_text("# Hello\nWorld", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(doc), "--preset", "safety", "--provider", "openai"],
        env={"OPENAI_API_KEY": ""},
    )
    assert result.exit_code == 3
    assert "No OpenAI API key provided" in (result.stderr or result.output)


def test_openai_provider_multimodal_payload():
    """Verify OpenAIDecisionsProvider encodes images into input_text and input_image array."""
    from typesafe_eval.images import ExtractedImage

    provider = OpenAIDecisionsProvider(api_key="sk-mock-key")
    mock_resp = {
        "model": "gpt-6-luna",
        "answers": [
            {"name": "diagram_consistent", "type": "predicate", "probability": 0.95}
        ],
    }
    mock_http_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    mock_http_resp.json.return_value = mock_resp

    test_image = ExtractedImage(
        source="diagram.png",
        path=None,
        data_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        alt_text="Architecture",
        mime_type="image/png",
        byte_size=68,
    )

    state = {
        "document": "# System Architecture\nSee architecture below.",
        "images": [test_image],
    }
    questions = {
        "diagram_consistent": DecisionQuestion(
            type="noul",
            instructions="Does the diagram match the text?",
        )
    }

    with patch("httpx.Client.post", return_value=mock_http_resp) as mock_post:
        resp = provider.decide(state=state, questions=questions)
        call_json = mock_post.call_args.kwargs["json"]

        assert isinstance(call_json["input"], list)
        assert len(call_json["input"]) == 2
        assert call_json["input"][0] == {
            "type": "input_text",
            "text": "# System Architecture\nSee architecture below.",
        }
        assert call_json["input"][1] == {
            "type": "input_image",
            "image_url": test_image.data_url,
        }
        assert resp.nouls["diagram_consistent"].noul == 0.95


def test_typesafe_provider_skips_images_with_notice(capsys):
    """Verify TypeSafeProvider emits notice on stderr and strips images from state."""
    from typesafe_eval.images import ExtractedImage
    from typesafe_eval.providers.typesafe import TypeSafeProvider

    provider = TypeSafeProvider(api_key="ts-mock-key")
    mock_sdk_client = MagicMock()
    mock_sdk_client.system_one.return_value = MagicMock(
        nouls={"q1": MagicMock(noul=0.1)},
        scores={},
        choices={},
    )
    provider._client = mock_sdk_client

    test_image = ExtractedImage(
        source="img.png",
        path=None,
        data_url="data:image/png;base64,abc",
    )
    state = {
        "document": "Test doc",
        "images": [test_image],
    }
    questions = {
        "q1": DecisionQuestion(type="noul", instructions="test")
    }

    resp = provider.decide(state=state, questions=questions)
    assert resp.nouls["q1"].noul == 0.1

    # Verify images was removed from state before calling SDK client
    called_state = mock_sdk_client.system_one.call_args.kwargs["state"]
    assert "images" not in called_state
    assert called_state["document"] == "Test doc"

    # Verify stderr notice was emitted
    captured = capsys.readouterr()
    assert "Notice: TypeSafe System One (Jev) is text-only; embedded images were skipped." in captured.err
