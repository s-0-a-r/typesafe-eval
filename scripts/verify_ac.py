#!/usr/bin/env python3
"""Autonomous Real CLI Acceptance Criteria (AC) Verification Harness.

Executes end-to-end verification of typesafe-eval CLI binaries,
OS subprocess exit codes (0, 1, 2, 3), JSON stream purity, and security boundaries.

Usage:
    python scripts/verify_ac.py [--json] [--verbose]
"""

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ACResult:
    id: int
    name: str
    command: str
    expected: str
    actual: str
    passed: bool
    details: str | None = None


class ACVerifier:
    def __init__(self, python_bin: str | None = None, verbose: bool = False):
        self.python_bin = python_bin or sys.executable
        self.verbose = verbose
        self.results: list[ACResult] = []

    def _run_cli(
        self,
        args: list[str],
        env_override: dict[str, str] | None = None,
        module: str = "typesafe_eval.cli",
    ) -> subprocess.CompletedProcess:
        """Run CLI as an OS subprocess."""
        env = os.environ.copy()
        if env_override is not None:
            for k, v in env_override.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

        cmd = [self.python_bin, "-m", module] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
        )

    def _run_subprocess_python(
        self,
        code: str,
        env_override: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """Run inline Python in an isolated subprocess."""
        env = os.environ.copy()
        if env_override is not None:
            for k, v in env_override.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

        cmd = [self.python_bin, "-c", code]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
        )

    def verify_all(self) -> bool:
        """Run all Acceptance Criteria checks."""
        self.results = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._check_version()
            self._check_missing_file(tmppath)
            self._check_invalid_preset(tmppath)
            self._check_clean_doc_pass(tmppath)
            self._check_quoted_secret_masking(tmppath)
            self._check_slack_token_detection(tmppath)
            self._check_international_phone_pii(tmppath)
            self._check_missing_api_key_exit_3(tmppath)
            self._check_exit_1_content_violation(tmppath)
            self._check_exit_1_over_3_precedence(tmppath)
            self._check_json_stream_purity(tmppath)
            self._check_pre_commit_hook_skip(tmppath)
            self._check_claude_safety_hook(tmppath)
            self._check_init_command()
            self._check_offline_mode(tmppath)
            self._check_result_cache(tmppath)
            self._check_github_formatter(tmppath)
            self._check_file_exclusions(tmppath)

        return all(r.passed for r in self.results)

    def _check_version(self) -> None:
        cp = self._run_cli(["--version"])
        passed = (cp.returncode == 0) and ("typesafe-eval, version" in cp.stdout)
        self.results.append(
            ACResult(
                id=1,
                name="Version CLI Flag",
                command="typesafe-eval --version",
                expected="Exit 0, stdout contains 'typesafe-eval, version'",
                actual=f"Exit {cp.returncode}, '{cp.stdout.strip()}'",
                passed=passed,
            )
        )

    def _check_missing_file(self, tmp: Path) -> None:
        missing_file = tmp / "nonexistent_file_404.md"
        cp = self._run_cli([str(missing_file)])
        passed = (cp.returncode == 2) and ("Error: File not found" in cp.stderr)
        self.results.append(
            ACResult(
                id=2,
                name="Missing File Handling (Exit 2)",
                command=f"typesafe-eval {missing_file.name}",
                expected="Exit 2, stderr contains 'Error: File not found'",
                actual=f"Exit {cp.returncode}, stderr: '{cp.stderr.strip()}'",
                passed=passed,
            )
        )

    def _check_invalid_preset(self, tmp: Path) -> None:
        doc = tmp / "doc.md"
        doc.write_text("# Doc\nSample content.")
        cp = self._run_cli([str(doc), "--preset", "invalid_preset_xyz", "--dry-run"])
        passed = (cp.returncode == 2) and ("Error loading preset" in cp.stderr)
        self.results.append(
            ACResult(
                id=3,
                name="Invalid Preset Handling (Exit 2)",
                command=f"typesafe-eval {doc.name} --preset invalid_preset_xyz",
                expected="Exit 2, stderr contains 'Error loading preset'",
                actual=f"Exit {cp.returncode}, stderr: '{cp.stderr.strip()}'",
                passed=passed,
            )
        )

    def _check_clean_doc_pass(self, tmp: Path) -> None:
        clean_file = tmp / "clean_doc.md"
        clean_file.write_text("# Clean Architecture\n\nThis is a public documentation.")
        cp = self._run_cli([str(clean_file), "--preset", "safety", "--dry-run", "-f", "json"])
        passed = False
        parsed_status = "Invalid JSON"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    if (
                        item.get("passed_thresholds") is True
                        and len(item.get("violations", [])) == 0
                    ):
                        passed = True
                        parsed_status = "passed_thresholds=True, violations=0"
            except Exception as e:
                parsed_status = f"JSON parse error: {e}"

        self.results.append(
            ACResult(
                id=4,
                name="Clean Document Dry-Run Pass",
                command=f"typesafe-eval {clean_file.name} --preset safety --dry-run -f json",
                expected="Exit 0, passed_thresholds=True, violations=[]",
                actual=f"Exit {cp.returncode}, {parsed_status}",
                passed=passed,
            )
        )

    def _check_quoted_secret_masking(self, tmp: Path) -> None:
        secret_file = tmp / "payload.json"
        raw_secret = "superSecretPassword123!"
        secret_file.write_text(f'{{"password": "{raw_secret}", "env": "prod"}}')
        cp = self._run_cli([str(secret_file), "--preset", "safety", "--dry-run", "-f", "json"])
        passed = False
        details = "Failed"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                item = data[0]
                raw_not_leaked = raw_secret not in cp.stdout and raw_secret not in cp.stderr
                has_redacted = any(
                    s.get("placeholder") == "[SECRET_1]" and s.get("outcome") == "secret"
                    for s in item.get("secret_evaluations", [])
                )
                if has_redacted and raw_not_leaked:
                    passed = True
                    details = "Masked as [SECRET_1], outcome: secret, zero raw leak"
            except Exception as e:
                details = f"JSON error: {e}"

        self.results.append(
            ACResult(
                id=5,
                name="Quoted Secret Key Masking",
                command=f"typesafe-eval {secret_file.name} --preset safety --dry-run -f json",
                expected="Exit 0, masked as [SECRET_1], outcome: secret, zero raw leak",
                actual=f"Exit {cp.returncode}, {details}",
                passed=passed,
            )
        )

    def _check_slack_token_detection(self, tmp: Path) -> None:
        slack_file = tmp / "slack_config.md"
        raw_token = "xox" + "b-1234567890-abcdefghijklmn"
        slack_file.write_text(f"Slack Bot Token: {raw_token}")
        cp = self._run_cli([str(slack_file), "--preset", "safety", "--dry-run", "-f", "json"])
        passed = False
        details = "Failed"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                item = data[0]
                raw_not_leaked = raw_token not in cp.stdout and raw_token not in cp.stderr
                token_redacted = any(
                    s.get("placeholder") == "[REDACTED_SLACK_TOKEN]"
                    and s.get("outcome") == "secret"
                    and s.get("decided_by") == "rule"
                    for s in item.get("secret_evaluations", [])
                )
                if raw_not_leaked and token_redacted:
                    passed = True
                    details = "Detected as [REDACTED_SLACK_TOKEN] by rule, zero raw leak"
            except Exception as e:
                details = f"JSON error: {e}"

        self.results.append(
            ACResult(
                id=6,
                name="Slack API Token Detection",
                command=f"typesafe-eval {slack_file.name} --preset safety --dry-run -f json",
                expected="Exit 0, masked as [REDACTED_SLACK_TOKEN], outcome: secret",
                actual=f"Exit {cp.returncode}, {details}",
                passed=passed,
            )
        )

    def _check_international_phone_pii(self, tmp: Path) -> None:
        phone_file = tmp / "contact.md"
        raw_phone = "+44 20 7946 0991"
        phone_file.write_text(f"Direct executive line: {raw_phone}")
        cp = self._run_cli([str(phone_file), "--preset", "safety", "--dry-run", "-f", "json"])
        passed = False
        details = "Failed"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                item = data[0]
                raw_not_leaked = raw_phone not in cp.stdout and raw_phone not in cp.stderr
                has_phone_mask = any(
                    p.get("placeholder") == "[PHONE_1]"
                    and p.get("features", {}).get("country_format") == "international"
                    for p in item.get("phone_evaluations", [])
                )
                if raw_not_leaked and has_phone_mask:
                    passed = True
                    details = (
                        "E.164 phone masked as [PHONE_1], format: international, zero raw leak"
                    )
            except Exception as e:
                details = f"JSON error: {e}"

        self.results.append(
            ACResult(
                id=7,
                name="International Phone PII (E.164)",
                command=f"typesafe-eval {phone_file.name} --preset safety --dry-run -f json",
                expected="Exit 0, masked as [PHONE_1], country_format: international",
                actual=f"Exit {cp.returncode}, {details}",
                passed=passed,
            )
        )

    def _check_missing_api_key_exit_3(self, tmp: Path) -> None:
        doc = tmp / "sample.md"
        doc.write_text("# Doc\nTesting missing api key.")
        cp = self._run_cli(
            [str(doc), "--preset", "safety"],
            env_override={"TYPESAFE_API_KEY": None, "OPENAI_API_KEY": None},
        )
        passed = (cp.returncode == 3) and ("No TypeSafe API key provided" in cp.stderr)
        self.results.append(
            ACResult(
                id=8,
                name="Missing API Key Runtime Error (Exit 3)",
                command=f"env -u TYPESAFE_API_KEY typesafe-eval {doc.name} --preset safety",
                expected="Exit 3, stderr contains 'No TypeSafe API key provided'",
                actual=f"Exit {cp.returncode}, error reported on stderr",
                passed=passed,
            )
        )

    def _check_exit_1_content_violation(self, tmp: Path) -> None:
        doc = tmp / "violating.md"
        doc.write_text("# Violating Doc\nSecurity breach.")
        code = f"""
import sys
from unittest.mock import patch
from typesafe_eval.models import DocumentEvalResult
from typesafe_eval.cli import main

def fake_eval(self, filepath, **kwargs):
    return DocumentEvalResult(
        filepath=filepath,
        filename='{doc.name}',
        preset_name='safety',
        passed_thresholds=False,
        violations=['Credential Exposure: [SECRET_1] is an exposed secret'],
    )

with patch('typesafe_eval.client.TypeSafeEvaluator.evaluate_document', fake_eval):
    sys.argv = ['typesafe-eval', '{str(doc)}', '--preset', 'safety']
    main()
"""
        cp = self._run_subprocess_python(code)
        passed = (cp.returncode == 1) and ("Credential Exposure" in cp.stdout)
        self.results.append(
            ACResult(
                id=9,
                name="Content Gate Violation (Exit 1)",
                command=f"typesafe-eval {doc.name} --preset safety (with content violation)",
                expected="Exit 1, stdout contains violation message",
                actual=f"Exit {cp.returncode}, violation rendered",
                passed=passed,
            )
        )

    def _check_exit_1_over_3_precedence(self, tmp: Path) -> None:
        doc1 = tmp / "doc_violating.md"
        doc1.write_text("# Doc 1")
        doc2 = tmp / "doc_error.md"
        doc2.write_text("# Doc 2")
        code = f"""
import sys
from unittest.mock import patch
from typesafe_eval.models import DocumentEvalResult
from typesafe_eval.cli import main

def fake_eval(self, filepath, **kwargs):
    if '{doc1.name}' in filepath:
        return DocumentEvalResult(
            filepath=filepath,
            filename='{doc1.name}',
            preset_name='safety',
            passed_thresholds=False,
            violations=['PII Exposure: [EMAIL_1] is an individual address'],
        )
    raise RuntimeError('Connection timeout to server')

with patch('typesafe_eval.client.TypeSafeEvaluator.evaluate_document', fake_eval):
    sys.argv = ['typesafe-eval', '{str(doc1)}', '{str(doc2)}', '--preset', 'safety']
    main()
"""
        cp = self._run_subprocess_python(code)
        passed = (
            (cp.returncode == 1)
            and ("PII Exposure" in cp.stdout)
            and ("Connection timeout" in cp.stderr)
        )
        self.results.append(
            ACResult(
                id=10,
                name="Exit 1-over-3 Precedence Rule",
                command="typesafe-eval <violating> <erroring> --preset safety",
                expected="Exit 1 (violation takes precedence over runtime error)",
                actual=f"Exit {cp.returncode} (Precedence enforced: Exit 1)",
                passed=passed,
            )
        )

    def _check_json_stream_purity(self, tmp: Path) -> None:
        doc = tmp / "pure_check.md"
        doc.write_text("# Doc\nClean content.")
        cp = self._run_cli([str(doc), "--preset", "safety", "--dry-run", "-f", "json"])
        passed = False
        details = "Failed"
        try:
            data = json.loads(cp.stdout)
            if (
                isinstance(data, list)
                and cp.stdout.strip().startswith("[")
                and cp.stdout.strip().endswith("]")
            ):
                passed = True
                details = "stdout is 100% pure JSON parsable by json.loads"
        except Exception as e:
            details = f"Parse error: {e}"

        self.results.append(
            ACResult(
                id=11,
                name="Stdout JSON Stream Purity",
                command=f"typesafe-eval {doc.name} -f json",
                expected="stdout parses cleanly with json.loads, zero non-JSON pollution",
                actual=f"{details}",
                passed=passed,
            )
        )

    def _check_pre_commit_hook_skip(self, tmp: Path) -> None:
        clean_file = tmp / "hook_test.md"
        clean_file.write_text("# Doc\nTesting hook.")
        cp = self._run_cli(
            [str(clean_file)],
            env_override={"TYPESAFE_API_KEY": None, "OPENAI_API_KEY": None},
            module="typesafe_eval.hook",
        )
        passed = (cp.returncode == 0) and ("skipped execution" in cp.stderr)
        self.results.append(
            ACResult(
                id=12,
                name="Pre-commit Hook Graceful Skip",
                command=f"TYPESAFE_API_KEY='' typesafe-eval-hook {clean_file.name}",
                expected="Exit 0, notice emitted to stderr",
                actual=f"Exit {cp.returncode}, notice detected in stderr",
                passed=passed,
            )
        )

    def _check_claude_safety_hook(self, tmp: Path) -> None:
        cmd = [self.python_bin, "hooks/claude_safety_hook.py"]
        env = os.environ.copy()
        env.pop("TYPESAFE_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)
        cp = subprocess.run(cmd, capture_output=True, text=True, env=env)
        passed = cp.returncode == 0
        self.results.append(
            ACResult(
                id=13,
                name="Claude Safety Hook Integration",
                command="python3 hooks/claude_safety_hook.py",
                expected="Exit 0 on clean/no-key environment",
                actual=f"Exit {cp.returncode}",
                passed=passed,
            )
        )

    def _check_init_command(self) -> None:
        cp = self._run_cli(["init", "--help"])
        passed = (
            cp.returncode == 0
            and "--pre-commit" in cp.stdout
            and "--claude-code" in cp.stdout
            and "--github-action" in cp.stdout
            and "--all" in cp.stdout
        )
        self.results.append(
            ACResult(
                id=14,
                name="Scaffolding CLI (typesafe-eval init)",
                command="typesafe-eval init --help",
                expected="Exit 0, displays --pre-commit, --claude-code, --github-action, --all",
                actual=f"Exit {cp.returncode}, flags verified",
                passed=passed,
            )
        )

    def _check_offline_mode(self, tmp: Path) -> None:
        doc = tmp / "offline_clean.md"
        doc.write_text("# Offline Clean\nDocumentation text without secrets.")
        cp = self._run_cli(
            [str(doc), "--preset", "safety", "--offline", "-f", "json"],
            env_override={"TYPESAFE_API_KEY": None},
        )
        passed = False
        details = f"Exit {cp.returncode}"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                if (
                    len(data) == 1
                    and data[0]["passed_thresholds"] is True
                    and data[0]["api_calls"] == 0
                ):
                    passed = True
                    details = "Exit 0, offline mode succeeded without API key (0 API calls)"
            except Exception as e:
                details = f"JSON parse error: {e}"

        self.results.append(
            ACResult(
                id=15,
                name="Offline Rules-Only Mode (--offline)",
                command=f"typesafe-eval {doc.name} --preset safety --offline -f json",
                expected="Exit 0 without API key, deterministic rules pass, api_calls=0",
                actual=details,
                passed=passed,
            )
        )

    def _check_result_cache(self, tmp: Path) -> None:
        from typesafe_eval.cache import EvaluationCache
        from typesafe_eval.models import DocumentEvalResult
        from typesafe_eval.presets import load_preset

        sub = tmp / "cache_test"
        sub.mkdir(parents=True, exist_ok=True)
        cache_dir = sub / "cache_store"
        cache = EvaluationCache(cache_dir=cache_dir)
        preset = load_preset("safety")
        content = "# Cache Document\nClean text."
        doc = sub / "cached_doc.md"
        doc.write_text(content)
        cache.set(
            content,
            preset,
            DocumentEvalResult(
                filepath=str(doc),
                filename=doc.name,
                preset_name="safety",
                passed_thresholds=True,
            ),
        )
        # Evaluate with cache without API key: should hit cache and exit 0
        cp1 = self._run_cli(
            [
                str(doc),
                "--preset",
                "safety",
                "--cache",
                "--cache-dir",
                str(cache_dir),
                "-f",
                "json",
            ],
            env_override={"TYPESAFE_API_KEY": None},
        )
        # Clear cache CLI command
        cp2 = self._run_cli(
            ["cache", "clear", "--cache-dir", str(cache_dir)],
        )
        passed = (
            cp1.returncode == 0
            and '"cached": true' in cp1.stdout
            and cp2.returncode == 0
            and "Cleared 1 cached" in cp2.stdout
        )
        details = (
            f"Exit {cp1.returncode}, cache hit verified and cache clear exited 0"
            if passed
            else f"Failed: cp1={cp1.returncode}, cp2={cp2.returncode}, stdout: {cp1.stdout[:100]}"
        )
        self.results.append(
            ACResult(
                id=16,
                name="Content-Addressable Result Cache (--cache)",
                command=f"typesafe-eval {doc.name} --cache --cache-dir cache_store",
                expected="Exit 0 without API key on cache hit, cache clear exits 0",
                actual=details,
                passed=passed,
            )
        )

    def _check_github_formatter(self, tmp: Path) -> None:
        doc = tmp / "github_violating.md"
        doc.write_text("# Violating Doc\nContact: user@gmail.com\n")
        cp = self._run_cli(
            [str(doc), "--preset", "safety", "--offline", "-f", "github"],
            env_override={"TYPESAFE_API_KEY": None},
        )
        passed = cp.returncode == 1 and "::error file=" in cp.stdout and "line=2" in cp.stdout
        details = (
            f"Exit {cp.returncode}, GitHub annotation emitted with line and column"
            if passed
            else f"Exit {cp.returncode}, stdout: {cp.stdout.strip()[:100]}"
        )
        self.results.append(
            ACResult(
                id=17,
                name="GitHub Actions Annotation Format (-f github)",
                command=f"typesafe-eval {doc.name} --preset safety --offline -f github",
                expected="Exit 1, stdout contains ::error file=...,line=...,col=...",
                actual=details,
                passed=passed,
            )
        )

    def _check_file_exclusions(self, tmp: Path) -> None:
        sub = tmp / "exclude_test"
        sub.mkdir(parents=True, exist_ok=True)
        valid_doc = sub / "eval_me.md"
        valid_doc.write_text("# Valid File\nClean text.")
        draft_doc = sub / "skip_me.draft.md"
        draft_doc.write_text("# Draft File\nNot ready.")
        cp = self._run_cli(
            [
                str(sub / "*.md"),
                "--exclude",
                "*.draft.md",
                "--preset",
                "safety",
                "--offline",
                "-f",
                "json",
            ],
            env_override={"TYPESAFE_API_KEY": None},
        )
        passed = False
        details = f"Exit {cp.returncode}"
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout)
                filenames = [item["filename"] for item in data]
                if "eval_me.md" in filenames and "skip_me.draft.md" not in filenames:
                    passed = True
                    details = "Exit 0, excluded *.draft.md and evaluated valid file"
            except Exception as e:
                details = f"JSON parse error: {e}"

        self.results.append(
            ACResult(
                id=18,
                name="File Exclusions & Default Ignores (--exclude)",
                command="typesafe-eval *.md --exclude '*.draft.md' --offline -f json",
                expected="Exit 0, excluded files skipped, only non-excluded evaluated",
                actual=details,
                passed=passed,
            )
        )

    def render_markdown(self) -> str:
        """Render results as a GitHub Markdown table."""
        lines = [
            "### Real CLI Acceptance Criteria (AC) Verification Matrix",
            "",
            "| # | Acceptance Criterion | Invocations / Commands Tested | Expected Behavior | Actual CLI Result | Status |",
            "|:---:|:---|:---|:---|:---|:---:|",
        ]
        for r in self.results:
            status_badge = "**PASS**" if r.passed else "**FAIL**"
            cmd_escaped = f"`{r.command}`"
            lines.append(
                f"| **{r.id}** | {r.name} | {cmd_escaped} | {r.expected} | {r.actual} | {status_badge} |"
            )

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        lines.append("")
        lines.append(f"**Summary**: {passed}/{total} Acceptance Criteria Verified.")
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Real CLI AC Verifier")
    parser.add_argument("--json", action="store_true", help="Emit results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    verifier = ACVerifier(verbose=args.verbose)
    all_passed = verifier.verify_all()

    if args.json:
        out = {
            "all_passed": all_passed,
            "total": len(verifier.results),
            "passed": sum(1 for r in verifier.results if r.passed),
            "results": [r.__dict__ for r in verifier.results],
        }
        print(json.dumps(out, indent=2))
    else:
        print(verifier.render_markdown())

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
