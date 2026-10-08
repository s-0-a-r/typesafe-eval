import fnmatch
import sys
from pathlib import Path

import yaml

from typesafe_eval.models import PresetConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

BUILTIN_PRESETS_DIR = Path(__file__).parent

DEFAULT_IGNORE_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".typesafe-eval-cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
)


def is_default_ignored(path: Path) -> bool:
    """Returns True if the path contains standard dependency, build, or cache directories."""
    return any(part in DEFAULT_IGNORE_DIRS for part in path.parts)


def is_path_excluded(path: Path, patterns: list[str], root: Path | None = None) -> bool:
    """Returns True if the path matches any of the given glob or directory exclusion patterns."""
    if not patterns:
        return False

    base_root = root or Path.cwd()
    try:
        rel_path = path.relative_to(base_root)
        rel_str = str(rel_path).replace("\\", "/")
    except ValueError:
        rel_str = str(path).replace("\\", "/")

    abs_str = str(path.resolve()).replace("\\", "/")
    file_name = path.name

    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        clean_pat = pat.replace("\\", "/").rstrip("/")

        # Direct filename match (e.g. "*.draft.md")
        if fnmatch.fnmatch(file_name, pat):
            return True

        # Relative or absolute path match
        if fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(abs_str, pat):
            return True

        # Leading slash normalization
        if fnmatch.fnmatch(f"/{rel_str}", pat):
            return True

        # Directory / prefix match (e.g. "templates" or "docs/templates")
        if rel_str == clean_pat or rel_str.startswith(f"{clean_pat}/"):
            return True
        if fnmatch.fnmatch(rel_str, f"{clean_pat}/*") or fnmatch.fnmatch(
            rel_str, f"*/{clean_pat}/*"
        ):
            return True

    return False


__all__ = [
    "PresetConfig",
    "BUILTIN_PRESETS_DIR",
    "DEFAULT_IGNORE_DIRS",
    "is_default_ignored",
    "is_path_excluded",
    "list_builtin_presets",
    "load_preset",
    "find_project_config",
    "load_project_config",
]


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
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        tool_section = data.get("tool")
        tool_cfg = tool_section.get("typesafe-eval") if isinstance(tool_section, dict) else None
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
        for k in (
            "name",
            "title",
            "description",
            "thresholds_as_warnings",
            "exclude",
            "provider",
            "model",
            "default_provider",
            "default_model",
            "include_images",
            "max_images_per_doc",
        ):
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
