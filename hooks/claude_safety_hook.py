#!/usr/bin/env python3
"""Claude Code PostToolUse safety evaluation hook wrapper for typesafe-eval (#35).

Maps typesafe-eval exit codes to Claude Code hook semantics:
  - Exit 1 (safety violation) -> exit 2 with violation summary on stderr (blocks/alerts Claude).
  - Exit 2 / 3 (CLI/runtime error, or missing API key) -> exit 0 (skips gracefully, never exit 2).
  - Exit 0 (clean) -> exit 0.
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


def extract_files_from_stdin() -> List[str]:
    """Extracts target markdown files from stdin (Claude Code hook JSON or text stream)."""
    if sys.stdin.isatty():
        return []
    
    try:
        raw = sys.stdin.read().strip()
    except Exception:
        return []

    if not raw:
        return []

    # 1. Try parsing Claude Code tool use JSON
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # Check tool_input
            tool_input = data.get("tool_input", {})
            if isinstance(tool_input, dict):
                for k in ("path", "file_path", "filePath", "TargetFile", "file", "target_file"):
                    val = tool_input.get(k)
                    if isinstance(val, str) and (val.endswith(".md") or val.endswith(".markdown")):
                        if Path(val).is_file():
                            return [val]

            # Check top-level keys
            for k in ("path", "file_path", "filePath", "TargetFile", "file", "target_file"):
                val = data.get(k)
                if isinstance(val, str) and (val.endswith(".md") or val.endswith(".markdown")):
                    if Path(val).is_file():
                        return [val]
    except Exception:
        pass

    # 2. Try newline-delimited file paths
    found = []
    for line in raw.splitlines():
        line = line.strip().strip("\"'")
        if (line.endswith(".md") or line.endswith(".markdown")) and Path(line).is_file():
            found.append(line)
    return found


def extract_files_from_git() -> List[str]:
    """Inspects git status/diff for changed and untracked markdown files."""
    found_files = []
    seen = set()

    def add_file(fname: str):
        cleaned = fname.strip().strip("\"'")
        if (cleaned.endswith(".md") or cleaned.endswith(".markdown")) and Path(cleaned).is_file():
            if cleaned not in seen:
                seen.add(cleaned)
                found_files.append(cleaned)

    # 1. Staged and unstaged tracked changes
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                add_file(line)
    except Exception:
        pass

    # 2. Untracked files and unstaged status
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                if len(line) > 3:
                    fname = line[3:].strip()
                    if " -> " in fname:
                        fname = fname.split(" -> ")[-1].strip()
                    add_file(fname)
    except Exception:
        pass

    return found_files


def run_hook(args: Optional[List[str]] = None) -> int:
    """Executes typesafe-eval safety preset and maps exit codes."""
    if args is None:
        args = sys.argv[1:]

    # 1. Collect markdown files to evaluate
    target_files: List[str] = []
    for a in args:
        if (a.endswith(".md") or a.endswith(".markdown")) and Path(a).is_file():
            target_files.append(a)

    if not target_files:
        target_files = extract_files_from_stdin()

    if not target_files:
        target_files = extract_files_from_git()

    if not target_files:
        # Nothing to evaluate
        return 0

    # 2. Check TYPESAFE_API_KEY
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        sys.stderr.write("typesafe-eval: TYPESAFE_API_KEY is not set; skipping Claude Code safety check.\n")
        return 0

    # 3. Locate CLI
    cli_bin = shutil.which("typesafe-eval")
    if cli_bin:
        cmd = [cli_bin, "eval", *target_files, "--preset", "safety", "-f", "json"]
    else:
        cmd = [sys.executable, "-m", "typesafe_eval.cli", "eval", *target_files, "--preset", "safety", "-f", "json"]

    # 4. Run evaluation
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        sys.stderr.write(f"typesafe-eval: execution failed ({e}); skipping hook.\n")
        return 0

    # 5. Map exit codes
    if proc.returncode == 0:
        return 0
    elif proc.returncode == 1:
        # Content / safety violation -> exit 2 with formatted stderr only when stdout is valid JSON and violations exist
        violations = []
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, list):
                for doc in data:
                    if isinstance(doc, dict):
                        fname = doc.get("filename", "document")
                        for v in doc.get("violations", []):
                            violations.append(f"{fname}: {v}")
        except Exception:
            pass

        if violations:
            sys.stderr.write("TypeSafe Safety Gate Failed:\n")
            for v in violations:
                sys.stderr.write(f"• {v}\n")
            return 2
        else:
            sys.stderr.write(
                "typesafe-eval: non-JSON output or no violations parsed on exit 1; skipping hook.\n"
            )
            return 0
    else:
        # Exit 2 or 3: tool/runtime error -> exit 0 so Claude is not falsely alerted
        sys.stderr.write(
            f"typesafe-eval: runtime error or tool error (exit code {proc.returncode}); skipping hook.\n"
        )
        return 0


if __name__ == "__main__":
    sys.exit(run_hook())
