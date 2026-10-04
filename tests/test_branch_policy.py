"""Tests for branch policy enforcement and release branch workflow."""

import subprocess
import sys

from scripts.check_branch_policy import validate_branch_policy


def test_feature_to_main_rejected():
    valid, msg = validate_branch_policy("main", "feat/my-feature")
    assert not valid
    assert "Direct pull requests to 'main' from 'feat/my-feature' are forbidden" in msg


def test_fix_to_main_rejected():
    valid, msg = validate_branch_policy("main", "fix/some-bug")
    assert not valid
    assert "Direct pull requests to 'main' from 'fix/some-bug' are forbidden" in msg


def test_release_to_main_allowed():
    valid, msg = validate_branch_policy("main", "release/v0.7.0")
    assert valid
    assert "Valid release promotion" in msg


def test_feature_to_release_allowed():
    valid, msg = validate_branch_policy("release/v0.7.0", "feat/my-feature")
    assert valid
    assert "Valid development pull request" in msg


def test_main_to_release_rejected():
    valid, msg = validate_branch_policy("release/v0.7.0", "main")
    assert not valid
    assert "Cannot merge 'main' into release branch" in msg


def test_cli_invocation_rejected():
    res = subprocess.run(
        [sys.executable, "scripts/check_branch_policy.py", "--base", "main", "--head", "feat/test"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "forbidden" in res.stdout


def test_cli_invocation_allowed():
    res = subprocess.run(
        [
            sys.executable,
            "scripts/check_branch_policy.py",
            "--base",
            "release/v0.7.0",
            "--head",
            "feat/test",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Valid development pull request" in res.stdout
