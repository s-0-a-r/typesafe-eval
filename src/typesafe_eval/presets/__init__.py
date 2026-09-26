"""Preset loader and custom configuration parser."""

import os
from pathlib import Path
from typing import Dict, List
import yaml

from typesafe_eval.models import PresetConfig

BUILTIN_PRESETS_DIR = Path(__file__).parent

def list_builtin_presets() -> List[str]:
    """Returns list of built-in preset names."""
    presets = []
    for file in BUILTIN_PRESETS_DIR.glob("*.yaml"):
        presets.append(file.stem.replace("_", "-"))
    return sorted(presets)

def load_preset(name_or_path: str) -> PresetConfig:
    """Loads a preset configuration by name (builtin) or file path."""
    path = Path(name_or_path)
    
    # Check if direct file path exists
    if path.exists():
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return PresetConfig.model_validate(raw_data)

    # Check built-in presets
    norm_name = name_or_path.lower().replace("-", "_")
    builtin_path = BUILTIN_PRESETS_DIR / f"{norm_name}.yaml"
    if builtin_path.exists():
        raw_data = yaml.safe_load(builtin_path.read_text(encoding="utf-8"))
        return PresetConfig.model_validate(raw_data)

    available = ", ".join(list_builtin_presets())
    raise FileNotFoundError(
        f"Preset '{name_or_path}' not found. Available built-ins: {available}, or supply a valid YAML file path."
    )
