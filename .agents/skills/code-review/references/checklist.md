# Domain Review Checklist for `typesafe-eval`

Use this checklist during Step 2 of the code review process.

---

## 1. Safety & Sensitive Data Checks
- [ ] Does any new code or error message format print raw strings from user files? (Ensure values are masked or replaced with placeholders).
- [ ] Are HTML comments stripped only *after* sensitive data detection and masking?
- [ ] If placeholders are stripped because they were inside HTML comments, are they accounted for in chunk placement (`boundary_unplaced`)?
- [ ] Does the detection engine correctly distinguish personal free-mail addresses from role accounts?
- [ ] Is the exit code precedence (Exit Code 1 overrides Exit Code 3) strictly preserved?

## 2. CLI & Integration Contract Checks
- [ ] Does `--format json` output strictly valid JSON on `stdout`?
- [ ] Are all warnings, notices, and error logs emitted to `stderr`?
- [ ] Is `schema_version: "1.0"` included in `DocumentEvalResult` and `ValidationReport` serializations?
- [ ] Does the GitHub Action handle fork PRs and missing secrets gracefully without failing CI on exit code 3?
- [ ] Are `.pre-commit-hooks.yaml` argument lists updated if CLI options change?

## 3. Presets & Evaluation Questions
- [ ] Are questions kept clean of Goodhart gaming incentives?
- [ ] Are thresholds calibrated against the tuning set before being evaluated on the held-out set?
- [ ] Does `thresholds_as_warnings: true` prevent non-critical score threshold failures from failing CI when intended as advisory?
- [ ] Is `dry_run` mode fully supported for any new question or preset change?

## 4. Test Quality & Regressions
- [ ] Do all 40 `pii_secrets` fixtures match their expected verdicts?
- [ ] Do all 46 `confidentiality` fixtures match their expected verdicts?
- [ ] Does `.venv/bin/pytest -v` run with 100% passes and zero unhandled warnings?
- [ ] Are there tests verifying both success (exit 0) and failure (exit 1, 2, 3) paths for any new feature?
