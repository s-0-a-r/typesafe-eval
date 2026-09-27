from typesafe_eval.presets import list_builtin_presets, load_preset

def test_list_builtin_presets():
    presets = list_builtin_presets()
    assert "quality" in presets
    assert "safety" in presets
    assert "tech-spec" in presets

def test_load_quality_preset():
    preset = load_preset("quality")
    assert preset.name == "quality"
    assert "clarity" in preset.questions
    assert preset.questions["clarity"].type == "score"
    assert "actionable" in preset.questions
    assert preset.questions["actionable"].type == "noul"
    assert "tone" in preset.questions
    assert preset.questions["tone"].type == "choice"

def test_preflight_validation():
    import pytest
    from pydantic import ValidationError
    from typesafe_eval.models import QuestionConfig

    # Valid values
    q_cred = QuestionConfig(type="noul", instructions="test", preflight="credentials")
    assert q_cred.preflight == "credentials"

    q_pii = QuestionConfig(type="noul", instructions="test", preflight="pii")
    assert q_pii.preflight == "pii"

    q_none = QuestionConfig(type="noul", instructions="test")
    assert q_none.preflight is None

    # Invalid preflight typo should raise ValidationError
    with pytest.raises(ValidationError):
        QuestionConfig(type="noul", instructions="test", preflight="credential")

    with pytest.raises(ValidationError):
        QuestionConfig(type="noul", instructions="test", preflight="passwords")
