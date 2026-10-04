"""Tests for packaging configuration and distribution file sanity."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


def test_pyproject_sdist_configuration():
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    if tomllib is not None:
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
        assert "scripts" in only_include, "sdist must include 'scripts' for test dependencies"
        assert "hooks" in only_include, "sdist must include 'hooks' for test dependencies"

        # Ensure heavy/internal directories are never included in only-include
        forbidden = ["validation", ".github", ".agents", "skills"]
        for item in forbidden:
            assert item not in only_include, f"sdist only-include must not contain '{item}'"
    else:
        # Fallback raw text parsing if toml parser is not installed
        content = pyproject_path.read_text(encoding="utf-8")
        assert "[tool.hatch.build.targets.sdist]" in content
        assert '"src"' in content
        assert '"tests"' in content
        assert '"validation"' not in content
