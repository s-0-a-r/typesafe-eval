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
