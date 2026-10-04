"""Preset loader and custom configuration parser."""

from pathlib import Path

import yaml

from typesafe_eval.models import PresetConfig

BUILTIN_PRESETS_DIR = Path(__file__).parent


def list_builtin_presets() -> list[str]:
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


def find_project_config(start_dir: Path | None = None) -> Path | None:
    """Traverses upward from start_dir to find a project config file (.typesafe-eval.yaml/yml or pyproject.toml)."""
    current = (start_dir or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        for candidate in (".typesafe-eval.yaml", ".typesafe-eval.yml"):
            cfg_path = directory / candidate
            if cfg_path.is_file():
                return cfg_path

        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            try:
                try:
                    import tomllib
                except ImportError:
                    import tomli as tomllib  # type: ignore

                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                if "tool" in data and "typesafe-eval" in data["tool"]:
                    return pyproject
            except Exception:
                pass

        if (directory / ".git").exists():
            break

    return None


def load_project_config(start_dir: Path | None = None) -> tuple[PresetConfig | None, Path | None]:
    """Finds and loads project configuration. Returns (PresetConfig, Path) or (None, None)."""
    cfg_path = find_project_config(start_dir)
    if cfg_path is None:
        return None, None

    if cfg_path.name == "pyproject.toml":
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore

        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        tool_cfg = data.get("tool", {}).get("typesafe-eval")
        if not isinstance(tool_cfg, dict):
            return None, None
        cfg_dict = dict(tool_cfg)
    else:
        raw_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            raise ValueError(f"Invalid configuration file: {cfg_path} must be a YAML mapping")
        cfg_dict = dict(raw_data)

    base_preset_name = cfg_dict.pop("preset", None)
    if base_preset_name:
        base_cfg = load_preset(base_preset_name)
        merged = base_cfg.model_dump()
        for k in ("name", "title", "description", "thresholds_as_warnings"):
            if k in cfg_dict:
                merged[k] = cfg_dict[k]
        if "sanitizer" in cfg_dict:
            merged["sanitizer"] = cfg_dict["sanitizer"]
        if "questions" in cfg_dict and isinstance(cfg_dict["questions"], dict):
            for q_id, q_val in cfg_dict["questions"].items():
                if q_id in merged["questions"] and isinstance(q_val, dict):
                    merged["questions"][q_id].update(q_val)
                else:
                    merged["questions"][q_id] = q_val
        return PresetConfig.model_validate(merged), cfg_path

    if "name" not in cfg_dict:
        cfg_dict["name"] = cfg_path.stem
    return PresetConfig.model_validate(cfg_dict), cfg_path
