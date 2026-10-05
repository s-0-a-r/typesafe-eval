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
        assert "CHANGELOG.md" in only_include, "sdist must include 'CHANGELOG.md'"

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
        assert '"CHANGELOG.md"' in content
        assert '"validation"' not in content


def test_py_typed_marker_present():
    """Verify PEP 561 py.typed marker is present in source and package structure."""
    py_typed_path = Path(__file__).resolve().parent.parent / "src" / "typesafe_eval" / "py.typed"
    assert py_typed_path.is_file(), f"py.typed marker must exist at {py_typed_path}"


def test_release_please_and_workflow_sanity():
    """Verify release-please configuration files and release workflow definition."""
    import json

    repo_root = Path(__file__).resolve().parent.parent

    config_path = repo_root / ".release-please-config.json"
    manifest_path = repo_root / ".release-please-manifest.json"
    release_workflow = repo_root / ".github" / "workflows" / "release.yml"

    assert config_path.is_file(), ".release-please-config.json must exist"
    assert manifest_path.is_file(), ".release-please-manifest.json must exist"
    assert release_workflow.is_file(), ".github/workflows/release.yml must exist"

    import typesafe_eval

    # Verify manifest version is synchronized with __version__ and pyproject.toml
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "." in manifest
    assert manifest["."] == typesafe_eval.__version__, (
        f"Manifest version ({manifest['.']}) must match typesafe_eval.__version__ ({typesafe_eval.__version__})"
    )

    if tomllib is not None:
        with open(repo_root / "pyproject.toml", "rb") as f:
            pyproject_version = tomllib.load(f)["project"]["version"]
        assert pyproject_version == typesafe_eval.__version__, (
            f"pyproject.toml version ({pyproject_version}) must match typesafe_eval.__version__ ({typesafe_eval.__version__})"
        )

    # Verify release-please config specifies python release type
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config.get("release-type") == "python"

    # Verify release workflow has OIDC permissions for Trusted Publishing
    workflow_content = release_workflow.read_text(encoding="utf-8")
    assert "id-token: write" in workflow_content
    assert "pypa/gh-action-pypi-publish" in workflow_content
    assert "release-please-action" in workflow_content
