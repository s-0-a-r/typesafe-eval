import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from typesafe_eval.cli import get_git_changed_files, main


@pytest.fixture
def temp_git_repo(tmp_path: Path, monkeypatch):
    """Initializes a temporary git repository with initial commit."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    repo = tmp_path / "repo"
    repo.mkdir()

    env = dict(subprocess.os.environ)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"

    def run_git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

    run_git("init")
    f1 = repo / "doc1.md"
    f1.write_text("# Doc 1\nInitial content.", encoding="utf-8")
    run_git("add", "doc1.md")
    run_git("commit", "-m", "Initial commit")

    return repo, run_git


def test_get_git_changed_files_staged(temp_git_repo, monkeypatch):
    repo, run_git = temp_git_repo
    monkeypatch.chdir(repo)

    f2 = repo / "doc2.md"
    f2.write_text("# Doc 2\nNew content.", encoding="utf-8")
    f3 = repo / "doc3.md"
    f3.write_text("# Doc 3\nUnstaged content.", encoding="utf-8")

    # Stage only doc2.md
    run_git("add", "doc2.md")

    changed = get_git_changed_files(staged=True)
    assert len(changed) == 1
    assert Path(changed[0]).name == "doc2.md"


def test_get_git_changed_files_since(temp_git_repo, monkeypatch):
    repo, run_git = temp_git_repo
    monkeypatch.chdir(repo)

    f2 = repo / "doc2.md"
    f2.write_text("# Doc 2\nCommit 2 content.", encoding="utf-8")
    run_git("add", "doc2.md")
    run_git("commit", "-m", "Second commit")

    changed = get_git_changed_files(since="HEAD~1")
    assert len(changed) == 1
    assert Path(changed[0]).name == "doc2.md"


def test_get_git_changed_files_not_git_repo(tmp_path: Path, monkeypatch):
    non_repo = tmp_path / "empty"
    non_repo.mkdir()
    monkeypatch.chdir(non_repo)

    with pytest.raises(RuntimeError, match="Not a git repository"):
        get_git_changed_files(staged=True)


def test_cli_staged_evaluates_only_staged(temp_git_repo, monkeypatch):
    repo, run_git = temp_git_repo
    monkeypatch.chdir(repo)

    f2 = repo / "doc2.md"
    f2.write_text("# Doc 2\nStaged file.", encoding="utf-8")
    f3 = repo / "doc3.md"
    f3.write_text("# Doc 3\nUnstaged file.", encoding="utf-8")

    run_git("add", "doc2.md")

    runner = CliRunner()
    result = runner.invoke(main, ["--staged", "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["filename"] == "doc2.md"


def test_cli_staged_no_changes_exit_0(temp_git_repo, monkeypatch):
    repo, _ = temp_git_repo
    monkeypatch.chdir(repo)

    runner = CliRunner()
    result = runner.invoke(main, ["--staged", "--dry-run"])
    assert result.exit_code == 0
    assert "No modified or staged files matched evaluation criteria" in result.stdout


def test_cli_staged_with_pattern_filter(temp_git_repo, monkeypatch):
    repo, run_git = temp_git_repo
    monkeypatch.chdir(repo)

    doc = repo / "notes.txt"
    doc.write_text("Text note.", encoding="utf-8")
    md = repo / "guide.md"
    md.write_text("# Guide\nMarkdown guide.", encoding="utf-8")

    run_git("add", "notes.txt", "guide.md")

    runner = CliRunner()
    # Pattern only includes *.md
    result = runner.invoke(main, ["*.md", "--staged", "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["filename"] == "guide.md"


def test_cli_git_error_exit_2(tmp_path: Path, monkeypatch):
    non_repo = tmp_path / "not_git"
    non_repo.mkdir()
    monkeypatch.chdir(non_repo)

    runner = CliRunner()
    result = runner.invoke(main, ["--staged"])
    assert result.exit_code == 2
    assert "Git Error:" in (result.stderr or result.stdout)


def test_cli_staged_no_changes_json_pure(temp_git_repo, monkeypatch):
    repo, _ = temp_git_repo
    monkeypatch.chdir(repo)

    runner = CliRunner()
    result = runner.invoke(main, ["--staged", "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    # stdout must be valid JSON array parsable by jq
    data = json.loads(result.stdout)
    assert data == []


def test_cli_staged_no_changes_json_with_out(temp_git_repo, monkeypatch):
    repo, _ = temp_git_repo
    monkeypatch.chdir(repo)
    out_file = repo / "out.json"

    runner = CliRunner()
    result = runner.invoke(main, ["--staged", "--dry-run", "-f", "json", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data == []


def test_cli_staged_filters_binary_and_non_doc_files(temp_git_repo, monkeypatch):
    repo, run_git = temp_git_repo
    monkeypatch.chdir(repo)

    # Stage a python file and a binary file
    py_file = repo / "script.py"
    py_file.write_text("print('hello')", encoding="utf-8")
    bin_file = repo / "image.png"
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    run_git("add", "script.py", "image.png")

    runner = CliRunner()
    # Without explicit file args, typesafe-eval filters to docs and sees 0 doc files
    result = runner.invoke(main, ["--staged", "--dry-run", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == []
