#!/usr/bin/env python3
"""Run validation corpus evaluations across all tuning and heldout specifications."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TARGET_SPECS = [
    ("tech_spec_tuning", "validation/corpus/labels_tech_spec.tuning.yaml", 2),
    ("tech_spec_heldout", "validation/corpus/labels_tech_spec.heldout.yaml", 2),
    ("design_doc_en_tuning", "validation/corpus/labels_design_doc_en.tuning.yaml", 2),
    ("design_doc_en_heldout", "validation/corpus/labels_design_doc_en.heldout.yaml", 2),
    ("design_doc_ja_tuning", "validation/corpus/labels_design_doc_ja.tuning.yaml", 2),
    ("design_doc_ja_heldout", "validation/corpus/labels_design_doc_ja.heldout.yaml", 2),
    ("pr_en_tuning", "validation/corpus/labels_pr_en.tuning.yaml", 2),
    ("pr_en_heldout", "validation/corpus/labels_pr_en.heldout.yaml", 2),
    ("pr_ja_tuning", "validation/corpus/labels_pr_ja.tuning.yaml", 2),
    ("pr_ja_heldout", "validation/corpus/labels_pr_ja.heldout.yaml", 2),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run validation corpus evaluations")
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "typesafe", "jev"],
        default="auto",
        help="Evaluation provider (default: auto)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model override (e.g. gpt-6-luna or jev-1.13.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation in dry-run mode using mock results",
    )
    args = parser.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d")
    folder_suffix = f"_{args.provider}" if args.provider != "auto" else ""
    out_dir = Path("validation/corpus/results") / f"{date_str}{folder_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Corpus Validation Run ({date_str}) ===")
    print(f"Provider: {args.provider} (model: {args.model or 'default'})")
    print(f"Output directory: {out_dir}\n")

    summary_results: list[tuple[str, bool, int, str]] = []
    py_exec = sys.executable

    for name, spec_path, runs in TARGET_SPECS:
        if not Path(spec_path).exists():
            print(f"Skipping {name}: {spec_path} does not exist.")
            continue

        json_out = out_dir / f"{name}.json"
        print(f"--> Validating {name} ({spec_path}, runs={runs})...")
        cmd = [
            py_exec,
            "-m",
            "typesafe_eval.cli",
            "validate",
            spec_path,
            "--runs",
            str(runs),
            "--provider",
            args.provider,
            "-f",
            "json",
            "-o",
            str(json_out),
        ]
        if args.model:
            cmd.extend(["--model", args.model])
        if args.dry_run:
            cmd.append("--dry-run")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"    ✔ Success (saved to {json_out.name})")
            summary_results.append((name, True, 0, ""))
        else:
            print(f"    ✘ Return code {res.returncode}")
            if res.stderr:
                print(f"      stderr:\n{res.stderr.strip()[:400]}")
            summary_results.append((name, False, res.returncode, res.stderr))

    print("\n=== Validation Run Summary ===")
    for name, ok, code, _ in summary_results:
        status = "PASS" if ok else f"NOT MET / FAIL (exit {code})"
        print(f"  - {name:25s}: {status}")

    exit_codes = [code for _, _, code, _ in summary_results]
    if any(code == 1 for code in exit_codes):
        sys.exit(1)
    elif any(code == 2 for code in exit_codes):
        sys.exit(2)
    elif any(code != 0 for code in exit_codes):
        sys.exit(3)


if __name__ == "__main__":
    main()
