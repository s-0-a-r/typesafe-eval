from typesafe_eval.presets import list_builtin_presets, load_preset

def test_list_builtin_presets():
    presets = list_builtin_presets()
    assert "quality" in presets
    assert "safety" in presets
    assert "tech-spec" in presets
    assert "design-doc" in presets
    assert "pr-description" in presets

def test_load_quality_preset():
    preset = load_preset("quality")
    assert preset.name == "quality"
    assert preset.thresholds_as_warnings is True
    assert "clarity" in preset.questions
    assert preset.questions["clarity"].type == "score"
    assert preset.questions["clarity"].weight == 1.0
    assert preset.questions["clarity"].min_threshold == 0.6
    assert "completeness" not in preset.questions
    assert "actionable" not in preset.questions
    assert "tone" in preset.questions
    assert preset.questions["tone"].type == "choice"

def test_load_design_doc_preset():
    preset = load_preset("design_doc")
    assert preset.name == "design_doc"
    assert len(preset.questions) == 10
    for q_id, q_cfg in preset.questions.items():
        assert q_cfg.type == "noul"
        assert q_cfg.min_threshold == 0.5
        assert q_cfg.weight is None

def test_load_pr_description_preset():
    preset = load_preset("pr_description")
    assert preset.name == "pr_description"
    assert len(preset.questions) == 5
    for q_id, q_cfg in preset.questions.items():
        assert q_cfg.type == "noul"
        assert q_cfg.min_threshold == 0.5
        assert q_cfg.weight is None

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

def test_preset_with_sanitizer_config(tmp_path):
    from typesafe_eval.presets import load_preset
    yaml_content = """
name: "custom_preset"
sanitizer:
  role_emails:
    - "helpdesk"
    - "ops-*"
questions:
  test_q:
    type: "noul"
    instructions: "test"
"""
    cfg_file = tmp_path / "custom.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")

    preset = load_preset(str(cfg_file))
    assert preset.sanitizer is not None
    assert preset.sanitizer.role_emails == ["helpdesk", "ops-*"]

