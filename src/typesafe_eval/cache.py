"""Content-addressable evaluation result cache."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from typesafe_eval.models import DocumentEvalResult, PresetConfig


def _get_version() -> str:
    try:
        import typesafe_eval

        return getattr(typesafe_eval, "__version__", "0.8.0")
    except Exception:
        return "0.8.0"


def get_default_cache_dir() -> Path:
    """Returns the default directory for caching evaluation results."""
    env_dir = os.environ.get("TYPESAFE_CACHE_DIR")
    if env_dir:
        return Path(env_dir)

    if os.environ.get("GITHUB_ACTIONS") == "true":
        return Path(".typesafe-eval-cache")

    # Standard XDG cache directory
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        target = Path(xdg_cache) / "typesafe-eval"
    else:
        target = Path.home() / ".cache" / "typesafe-eval"

    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except OSError:
        # Fallback to local workspace cache directory if home/xdg cache is not writable
        return Path(".typesafe-eval-cache")


class EvaluationCache:
    """Local file-based content-addressable cache for document evaluations."""

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        enabled: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else get_default_cache_dir()
        self.enabled = enabled

    def compute_key(
        self,
        content: str,
        preset: PresetConfig,
        mask_secrets: bool = True,
        max_chars: int = 25000,
    ) -> str:
        """Computes a deterministic SHA-256 hash from document content, preset rules, and evaluation options."""
        preset_repr = preset.model_dump_json()
        hasher = hashlib.sha256()
        hasher.update(content.encode())
        hasher.update(b"::")
        hasher.update(preset_repr.encode())
        hasher.update(b"::")
        hasher.update(f"mask={mask_secrets}:max={max_chars}".encode())
        hasher.update(b"::")
        hasher.update(_get_version().encode())
        return hasher.hexdigest()

    def get(
        self,
        content: str,
        preset: PresetConfig,
        mask_secrets: bool = True,
        max_chars: int = 25000,
    ) -> DocumentEvalResult | None:
        """Retrieves a cached evaluation result if present and valid."""
        if not self.enabled:
            return None

        key = self.compute_key(content, preset, mask_secrets=mask_secrets, max_chars=max_chars)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.is_file():
            return None

        try:
            raw_text = cache_file.read_text(encoding="utf-8")
            result = DocumentEvalResult.model_validate_json(raw_text)
            result.cached = True
            result.api_calls = 0
            return result
        except Exception:
            # Corrupted cache file; safely remove and treat as miss
            try:
                cache_file.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def set(
        self,
        content: str,
        preset: PresetConfig,
        result: DocumentEvalResult,
        mask_secrets: bool = True,
        max_chars: int = 25000,
    ) -> None:
        """Stores an evaluation result in the cache atomically."""
        if not self.enabled:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            key = self.compute_key(content, preset, mask_secrets=mask_secrets, max_chars=max_chars)
            target_path = self.cache_dir / f"{key}.json"
            temp_path = self.cache_dir / f"{key}.tmp.{os.getpid()}"

            # Clone result to avoid mutating caller object
            res_dict = result.model_dump()
            res_dict["cached"] = False  # Stored template is pristine
            json_str = json.dumps(res_dict, ensure_ascii=False)

            temp_path.write_text(json_str, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception:
            # Cache failure must never block application execution
            pass

    def clear(self) -> int:
        """Clears all cached evaluations and returns the count of removed files."""
        if not self.cache_dir.is_dir():
            return 0

        count = 0
        try:
            for item in self.cache_dir.glob("*.json"):
                try:
                    item.unlink()
                    count += 1
                except OSError:
                    pass
            for item in self.cache_dir.glob("*.tmp.*"):
                try:
                    item.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        return count
