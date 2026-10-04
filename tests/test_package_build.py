"""Tests for packaging configuration and distribution file sanity."""

from pathlib import Path

import tomllib


def test_pyproject_sdist_configuration():
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    hatch_targets = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {})

    # Wheel configuration sanity
    wheel_config = hatch_targets.get("wheel", {})
    assert wheel_config.get("packages") == ["src/typesafe_eval"], (
        f"Wheel packages should be ['src/typesafe_eval'], got {wheel_config.get('packages')}"
    )

    # sdist configuration sanity
    sdist_config = hatch_targets.get("sdist", {})
    only_include = sdist_config.get("only-include", [])

    assert "src" in only_include, "sdist must include 'src'"
    assert "tests" in only_include, "sdist should include 'tests' for downstream testing"

    # Ensure heavy/internal directories are never included in only-include
    forbidden = ["validation", ".github", ".agents", "skills", "scripts", "hooks"]
    for item in forbidden:
        assert item not in only_include, f"sdist only-include must not contain '{item}'"
