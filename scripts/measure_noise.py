#!/usr/bin/env python3
"""Empirical Noise & Calibration Measurement for typesafe-eval presets.

Evaluates test documents across multiple runs to measure run-to-run variation:
- Mean absolute difference (|Δ|)
- 99th percentile |Δ|
- Maximum |Δ|
- Consistency across question types (Score, Noul)
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from typesafe_eval.api import evaluate

DEFAULT_PRESETS_AND_DOCS = [
    (
        "quality",
        [
            "tests/fixtures/design_doc/en.md",
            "tests/fixtures/confidentiality/harmless_email_01.md",
            "validation/corpus/variants/akaza-numeric-counter-redesign/unrelated_addition.md",
        ],
    ),
    (
        "safety",
        [
            "tests/fixtures/pii_secrets/phone_01.md",
            "tests/fixtures/confidentiality/harmless_secret_01.md",
            "tests/fixtures/confidentiality/confidential_01.md",
        ],
    ),
    (
        "tech-spec",
        [
            "tests/fixtures/design_doc/en.md",
            "tests/fixtures/design_doc/en_without_rollback.md",
            "validation/corpus/variants/pep-0709/unrelated_addition.md",
        ],
    ),
    (
        "design-doc",
        [
            "tests/fixtures/design_doc/en.md",
            "tests/fixtures/design_doc/ja.md",
            "tests/fixtures/design_doc/en_without_metrics.md",
        ],
    ),
    (
        "pr-description",
        [
            "validation/corpus/variants/pr-kufu-smarthr-ui-5622/unrelated_addition.md",
            "validation/corpus/variants/pr-grafana-grafana-112058/unrelated_addition.md",
            "tests/fixtures/design_doc/en.md",
        ],
    ),
]


def percentile_99(values: list[float]) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * 0.99
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values_sorted[int(k)]
    d0 = values_sorted[int(f)] * (c - k)
    d1 = values_sorted[int(c)] * (k - f)
    return d0 + d1


def measure_noise(
    runs: int = 5,
    presets: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("Error: TYPESAFE_API_KEY environment variable required.", file=sys.stderr)
        sys.exit(3)

    target_configs = [
        (preset, docs)
        for preset, docs in DEFAULT_PRESETS_AND_DOCS
        if presets is None or preset in presets
    ]

    results_by_preset: dict[str, dict[str, Any]] = {}
    all_overall_deltas: list[float] = []

    for preset_name, doc_paths in target_configs:
        print(f"\nEvaluating preset: {preset_name} ({len(doc_paths)} docs x {runs} runs)...")
        preset_deltas: list[float] = []
        question_deltas: dict[str, list[float]] = defaultdict(list)

        for doc_path_str in doc_paths:
            path = Path(doc_path_str)
            if not path.exists():
                print(f"Warning: file {path} not found, skipping.", file=sys.stderr)
                continue
            content = path.read_text(encoding="utf-8")

            # Collect measurements across N runs
            run_results = []
            for _ in range(runs):
                res = evaluate(content, preset=preset_name, api_key=api_key, mask_secrets=True)
                run_results.append(res)
                print(".", end="", flush=True)

            # Extract metric values for pairwise comparison
            # Each question score or probability
            for r1, r2 in itertools.combinations(run_results, 2):
                # Composite score
                if r1.composite_score is not None and r2.composite_score is not None:
                    delta = abs(r1.composite_score - r2.composite_score)
                    preset_deltas.append(delta)
                    all_overall_deltas.append(delta)
                    question_deltas["composite_score"].append(delta)

                # Question scores
                for q_id, s1 in r1.scores.items():
                    if q_id in r2.scores:
                        s2 = r2.scores[q_id]
                        delta = abs(s1.normalized_score - s2.normalized_score)
                        preset_deltas.append(delta)
                        all_overall_deltas.append(delta)
                        question_deltas[q_id].append(delta)

                # Question nouls
                for q_id, n1 in r1.nouls.items():
                    if q_id in r2.nouls:
                        n2 = r2.nouls[q_id]
                        if n1.probability is not None and n2.probability is not None:
                            delta = abs(n1.probability - n2.probability)
                            preset_deltas.append(delta)
                            all_overall_deltas.append(delta)
                            question_deltas[q_id].append(delta)

        if preset_deltas:
            results_by_preset[preset_name] = {
                "num_comparisons": len(preset_deltas),
                "mean_delta": sum(preset_deltas) / len(preset_deltas),
                "max_delta": max(preset_deltas),
                "p99_delta": percentile_99(preset_deltas),
                "questions": {
                    q: {
                        "count": len(d_list),
                        "mean": sum(d_list) / len(d_list),
                        "max": max(d_list),
                        "p99": percentile_99(d_list),
                    }
                    for q, d_list in question_deltas.items()
                },
            }

    overall_summary = {
        "runs": runs,
        "total_pairwise_comparisons": len(all_overall_deltas),
        "overall_mean_delta": sum(all_overall_deltas) / len(all_overall_deltas)
        if all_overall_deltas
        else 0.0,
        "overall_max_delta": max(all_overall_deltas) if all_overall_deltas else 0.0,
        "overall_p99_delta": percentile_99(all_overall_deltas) if all_overall_deltas else 0.0,
        "presets": results_by_preset,
    }
    return overall_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure empirical noise on typesafe-eval presets")
    parser.add_argument(
        "--runs", type=int, default=5, help="Number of runs per document (default: 5)"
    )
    parser.add_argument("--preset", type=str, nargs="*", help="Specific presets to test")
    parser.add_argument("--out", type=str, help="Output JSON path")
    args = parser.parse_args()

    results = measure_noise(runs=args.runs, presets=args.preset)

    print("\n\n=== Empirical Noise Measurement Summary ===")
    print(f"Total pairwise comparisons: {results['total_pairwise_comparisons']}")
    print(f"Overall Mean |Δ|: {results['overall_mean_delta']:.4f}")
    print(f"Overall 99th percentile |Δ|: {results['overall_p99_delta']:.4f}")
    print(f"Overall Max |Δ|: {results['overall_max_delta']:.4f}")
    print("\nPreset Breakdown:")
    for p_name, p_data in results["presets"].items():
        print(
            f"  - {p_name:14s}: Mean={p_data['mean_delta']:.4f}, "
            f"P99={p_data['p99_delta']:.4f}, Max={p_data['max_delta']:.4f} "
            f"(n={p_data['num_comparisons']})"
        )

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    main()
