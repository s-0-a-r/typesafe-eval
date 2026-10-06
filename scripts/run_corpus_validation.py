#!/usr/bin/env python3
"""Run validation corpus evaluations across all tuning and heldout specifications."""

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


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path("validation/corpus/results") / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Corpus Validation Run ({date_str}) ===")
    print(f"Output directory: {out_dir}\n")

    summary_results = []
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
            "-f",
            "json",
            "-o",
            str(json_out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"    ✔ Success (saved to {json_out.name})")
            summary_results.append((name, True, ""))
        else:
            print(f"    ✘ Return code {res.returncode}")
            if res.stderr:
                print(f"      stderr:\n{res.stderr.strip()[:400]}")
            summary_results.append((name, False, res.stderr))

    print("\n=== Validation Run Summary ===")
    for name, ok, _ in summary_results:
        status = "PASS" if ok else "NOT MET / FAIL"
        print(f"  - {name:25s}: {status}")


if __name__ == "__main__":
    main()
