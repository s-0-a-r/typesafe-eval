#!/usr/bin/env python3
"""Feasibility check script for quality preset regression detection.

Per Issue #42:
- Compares within-pair gap (Δ between before/after or original/degraded) to between-document spread.
- Checks whether within-pair gap is clearly larger than between-document spread.
- Evaluates ROC-AUC and false alarm rates for absolute threshold feasibility.

Usage:
    # Run with synthetic degradations on sample docs (dry-run):
    python scripts/feasibility_check.py --doc fixtures/checklists/design_doc/en.md --dry-run

    # Run with a pairs JSON file:
    python scripts/feasibility_check.py --pairs pairs.json [--dry-run] [--runs 3] [--out results.json]
"""

import argparse
import json
import math
import random
import re
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from typesafe_eval.client import TypeSafeEvaluator
from typesafe_eval.presets import load_preset
from typesafe_eval.models import DocumentEvalResult

SEED = 20260927
FILLER = (
    "This section highlights essential operational context and prerequisites. "
    "There are multiple ways to interpret this, and outcomes depend heavily on implementation specifics. "
    "Extensive experimentation may be required before confirming edge case behavior."
)


def split_frontmatter(text: str) -> Tuple[str, str]:
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return (m.group(0), text[m.end():]) if m else ("", text)


def extract_blocks(body: str) -> List[str]:
    """Split markdown into paragraph/code blocks."""
    out, cur, in_code = [], [], False
    for line in body.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and line.strip() == "" and cur:
            out.append("\n".join(cur))
            cur = []
        elif in_code or line.strip():
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def make_shuffled(text: str) -> str:
    front, body = split_frontmatter(text)
    bs = extract_blocks(body)
    random.Random(SEED).shuffle(bs)
    return front + "\n\n".join(bs)


def make_no_headings(text: str) -> str:
    front, body = split_frontmatter(text)
    bs = extract_blocks(body)
    cleaned = []
    for b in bs:
        if b.startswith("```"):
            cleaned.append(b)
        else:
            lines = [l for l in b.split("\n") if not l.strip().startswith("#")]
            if lines:
                cleaned.append("\n".join(lines))
    return front + "\n\n".join(cleaned)


def make_padded(text: str) -> str:
    front, body = split_frontmatter(text)
    bs = extract_blocks(body)
    padded_blocks = [b if b.startswith("```") else f"{b}\n\n{FILLER}" for b in bs]
    return front + "\n\n".join(padded_blocks)


def compute_roc_auc(pos_scores: List[float], neg_scores: List[float]) -> float:
    """Computes ROC-AUC treating pos_scores as positive class (higher is better)."""
    if not pos_scores or not neg_scores:
        return 0.5
    # Wilcoxon-Mann-Whitney statistic
    all_scores = [(s, 1) for s in pos_scores] + [(s, 0) for s in neg_scores]
    all_scores.sort(key=lambda x: x[0])
    
    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    
    rank_sum_pos = 0.0
    i = 0
    while i < len(all_scores):
        j = i
        while j < len(all_scores) and all_scores[j][0] == all_scores[i][0]:
            j += 1
        # average rank for ties (1-based ranks)
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            if all_scores[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j

    u = rank_sum_pos - (n_pos * (n_pos + 1)) / 2.0
    return round(u / (n_pos * n_neg), 4)


def compute_ci95(values: List[float]) -> Tuple[float, float, float]:
    """Returns (mean, lower_95_ci, upper_95_ci)."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    mean_val = statistics.mean(values)
    if n < 2:
        return mean_val, mean_val, mean_val
    std_val = statistics.stdev(values)
    se = std_val / math.sqrt(n)
    margin = 1.96 * se
    return round(mean_val, 4), round(mean_val - margin, 4), round(mean_val + margin, 4)


def evaluate_text(
    evaluator: TypeSafeEvaluator,
    preset: Any,
    text: str,
    doc_name: str,
    runs: int,
    dry_run: bool,
) -> float:
    """Evaluates text across runs and returns median clarity score."""
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
        tf.write(text)
        temp_path = tf.name

    scores = []
    try:
        for _ in range(runs):
            if dry_run:
                res = evaluator._build_mock_result(
                    filepath=temp_path,
                    preset=preset,
                    was_truncated=False,
                    redaction_count=0,
                )
            else:
                res = evaluator.evaluate_document(filepath=temp_path, preset=preset)
            
            clarity = res.scores["clarity"].normalized_score if "clarity" in res.scores else 0.0
            scores.append(clarity)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    return statistics.median(scores) if scores else 0.0


def run_feasibility(
    pairs_file: Optional[Path] = None,
    doc_paths: Optional[List[Path]] = None,
    preset_name: str = "quality",
    runs: int = 3,
    dry_run: bool = False,
) -> Dict[str, Any]:
    preset = load_preset(preset_name)
    evaluator = TypeSafeEvaluator()

    pairs: List[Dict[str, Any]] = []

    # 1. Load explicit pairs if provided
    if pairs_file and pairs_file.is_file():
        raw_data = json.loads(pairs_file.read_text(encoding="utf-8"))
        for item in raw_data:
            before_text = (
                Path(item["before"]).read_text(encoding="utf-8")
                if "before" in item and Path(item["before"]).is_file()
                else item.get("before_text", "")
            )
            after_text = (
                Path(item["after"]).read_text(encoding="utf-8")
                if "after" in item and Path(item["after"]).is_file()
                else item.get("after_text", "")
            )
            pairs.append({
                "id": item.get("id", f"pair_{len(pairs)}"),
                "before_text": before_text,
                "after_text": after_text,
                "doc_type": item.get("doc_type", "generic"),
            })

    # 2. Or generate synthetic degradation pairs from doc_paths
    if doc_paths:
        for dp in doc_paths:
            if not dp.is_file():
                continue
            orig_text = dp.read_text(encoding="utf-8")
            base_id = dp.stem
            # degradations
            for deg_name, deg_fn in [
                ("shuffled", make_shuffled),
                ("no_headings", make_no_headings),
                ("padded", make_padded),
            ]:
                deg_text = deg_fn(orig_text)
                pairs.append({
                    "id": f"{base_id}_{deg_name}",
                    "before_text": orig_text,      # original (good)
                    "after_text": deg_text,        # degraded (bad)
                    "doc_type": deg_name,
                })

    if not pairs:
        raise ValueError("No review pairs or documents provided to feasibility check.")

    pair_results = []
    original_scores = []
    degraded_scores = []
    deltas = []

    for p in pairs:
        s_orig = evaluate_text(evaluator, preset, p["before_text"], f"{p['id']}_orig", runs, dry_run)
        s_deg = evaluate_text(evaluator, preset, p["after_text"], f"{p['id']}_deg", runs, dry_run)
        delta = s_deg - s_orig  # expected to be negative for degradations

        original_scores.append(s_orig)
        degraded_scores.append(s_deg)
        deltas.append(delta)

        pair_results.append({
            "id": p["id"],
            "doc_type": p["doc_type"],
            "original_clarity": s_orig,
            "degraded_clarity": s_deg,
            "delta": round(delta, 4),
        })

    # Statistics
    mean_delta, ci95_lower, ci95_upper = compute_ci95(deltas)
    between_doc_spread = statistics.stdev(original_scores) if len(original_scores) > 1 else 0.001
    gap_to_spread_ratio = abs(mean_delta) / between_doc_spread if between_doc_spread > 0 else 0.0

    # Feasibility checks
    within_pair_clearly_larger = gap_to_spread_ratio >= 1.5
    auc = compute_roc_auc(original_scores, degraded_scores)

    # False alarm on published (original) docs if threshold is median of degraded
    threshold_candidate = statistics.median(degraded_scores) if degraded_scores else 0.5
    false_alarms = sum(1 for s in original_scores if s <= threshold_candidate)
    false_alarm_rate = round(false_alarms / len(original_scores), 4) if original_scores else 0.0

    report = {
        "num_pairs": len(pairs),
        "preset": preset_name,
        "runs": runs,
        "dry_run": dry_run,
        "within_pair_gap": {
            "mean_delta": mean_delta,
            "ci95_lower": ci95_lower,
            "ci95_upper": ci95_upper,
        },
        "between_doc_spread": round(between_doc_spread, 4),
        "gap_to_spread_ratio": round(gap_to_spread_ratio, 2),
        "within_pair_clearly_larger": within_pair_clearly_larger,
        "roc_auc": auc,
        "candidate_threshold": round(threshold_candidate, 4),
        "published_false_alarm_rate": false_alarm_rate,
        "absolute_gate_feasible": (auc >= 0.75 and false_alarm_rate <= 0.10 and within_pair_clearly_larger),
        "pairs": pair_results,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Feasibility check for quality regression detection (#42)")
    parser.add_argument("--pairs", type=Path, help="JSON file with pairs to evaluate")
    parser.add_argument("--doc", action="append", type=Path, help="Document(s) to generate degradations for")
    parser.add_argument("--preset", default="quality", help="Preset name (default: quality)")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per doc (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Use mock evaluation without API calls")
    parser.add_argument("--out", type=Path, help="Path to save JSON output")

    args = parser.parse_args()

    doc_paths = args.doc or []
    if not args.pairs and not doc_paths:
        # Default fallback to design_doc fixtures if present
        default_doc = Path("tests/fixtures/design_doc/en.md")
        if default_doc.is_file():
            doc_paths = [default_doc]
        else:
            parser.error("Either --pairs or at least one --doc must be specified.")

    report = run_feasibility(
        pairs_file=args.pairs,
        doc_paths=doc_paths,
        preset_name=args.preset,
        runs=args.runs,
        dry_run=args.dry_run,
    )

    print("=== Feasibility Check Summary (Issue #42) ===")
    print(f"Evaluated Pairs: {report['num_pairs']}")
    print(f"Mean Δ (within-pair): {report['within_pair_gap']['mean_delta']} "
          f"[95% CI: {report['within_pair_gap']['ci95_lower']}, {report['within_pair_gap']['ci95_upper']}]")
    print(f"Between-document spread (σ): {report['between_doc_spread']}")
    print(f"Gap / Spread Ratio: {report['gap_to_spread_ratio']} "
          f"({'Clearly larger (≥1.5)' if report['within_pair_clearly_larger'] else 'Not clearly larger (<1.5)'})")
    print(f"ROC-AUC: {report['roc_auc']} (Threshold: ≥ 0.75)")
    print(f"Published False Alarm Rate: {report['published_false_alarm_rate'] * 100:.1f}% (Threshold: ≤ 10%)")
    print(f"Absolute Gate Feasible: {'YES' if report['absolute_gate_feasible'] else 'NO (Spotting regressions only)'}")

    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Detailed results saved to {args.out}")


if __name__ == "__main__":
    main()
