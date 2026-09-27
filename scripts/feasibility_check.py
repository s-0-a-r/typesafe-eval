#!/usr/bin/env python3
"""Feasibility check script for quality preset regression detection.

Per Issue #42:
- Compares within-pair gap (Δ between before/after or original/degraded) to between-document spread.
- Checks whether within-pair gap is clearly larger than between-document spread (computed over distinct documents).
- Splits by document into a tuning set and a held-out set (by doc_id, never by pair).
- Chooses the candidate threshold on the tuning set.
- Evaluates ROC-AUC and published false-alarm rate on the held-out set (better vs worse).
- Groups results by document type (doc_type separate from degradation variant).

Usage:
    # Run with synthetic degradations on sample docs (dry-run):
    python scripts/feasibility_check.py --doc tests/fixtures/design_doc/en.md --doc tests/fixtures/design_doc/ja.md --dry-run

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


def infer_doc_type(path_or_name: str, default: str = "generic") -> str:
    lower = path_or_name.lower()
    if "design_doc" in lower or "designdoc" in lower:
        return "design_doc"
    if "pr_description" in lower or "prdescription" in lower:
        return "pr_description"
    if "article" in lower or "zenn" in lower:
        return "article"
    return default


def run_feasibility(
    pairs_file: Optional[Path] = None,
    doc_paths: Optional[List[Path]] = None,
    default_doc_type: str = "generic",
    preset_name: str = "quality",
    runs: int = 3,
    holdout_fraction: float = 0.3,
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
            doc_id = item.get("doc_id", item.get("id", f"doc_{len(pairs)}"))
            doc_type = item.get("doc_type", infer_doc_type(str(doc_id), default_doc_type))
            better = item.get("better", "after")  # default for review pairs is 'after'

            pairs.append({
                "id": item.get("id", f"pair_{len(pairs)}"),
                "doc_id": doc_id,
                "doc_type": doc_type,
                "better": better,
                "before_text": before_text,
                "after_text": after_text,
                "degradation": item.get("degradation", None),
            })

    # 2. Or generate synthetic degradation pairs from doc_paths
    if doc_paths:
        for dp in doc_paths:
            if not dp.is_file():
                continue
            orig_text = dp.read_text(encoding="utf-8")
            base_id = dp.stem
            doc_type = infer_doc_type(str(dp), default_doc_type)

            for deg_name, deg_fn in [
                ("shuffled", make_shuffled),
                ("no_headings", make_no_headings),
                ("padded", make_padded),
            ]:
                deg_text = deg_fn(orig_text)
                pairs.append({
                    "id": f"{base_id}_{deg_name}",
                    "doc_id": base_id,
                    "doc_type": doc_type,
                    "better": "before",  # original is 'before', which is better
                    "before_text": orig_text,
                    "after_text": deg_text,
                    "degradation": deg_name,
                })

    if not pairs:
        raise ValueError("No review pairs or documents provided to feasibility check.")

    # Distinct documents and train/test split by document ID (never by pair)
    distinct_doc_ids = sorted(list({p["doc_id"] for p in pairs}))
    rng = random.Random(SEED)
    shuffled_doc_ids = list(distinct_doc_ids)
    rng.shuffle(shuffled_doc_ids)

    if len(distinct_doc_ids) >= 2 and holdout_fraction > 0:
        n_holdout = max(1, int(round(len(distinct_doc_ids) * holdout_fraction)))
        n_holdout = min(n_holdout, len(distinct_doc_ids) - 1)
        holdout_doc_ids = set(shuffled_doc_ids[:n_holdout])
        tuning_doc_ids = set(shuffled_doc_ids[n_holdout:])
    else:
        tuning_doc_ids = set(distinct_doc_ids)
        holdout_doc_ids = set(distinct_doc_ids)

    # Evaluate pairs
    evaluated_pairs = []
    for p in pairs:
        s_before = evaluate_text(evaluator, preset, p["before_text"], f"{p['id']}_before", runs, dry_run)
        s_after = evaluate_text(evaluator, preset, p["after_text"], f"{p['id']}_after", runs, dry_run)
        delta_after_minus_before = s_after - s_before

        if p["better"] == "after":
            better_score = s_after
            worse_score = s_before
            degradation_delta = s_before - s_after  # <= 0 if worse is lower
        else:
            better_score = s_before
            worse_score = s_after
            degradation_delta = s_after - s_before  # <= 0 if worse is lower

        evaluated_pairs.append({
            "id": p["id"],
            "doc_id": p["doc_id"],
            "doc_type": p["doc_type"],
            "better": p["better"],
            "degradation": p.get("degradation"),
            "is_holdout": p["doc_id"] in holdout_doc_ids,
            "before_score": s_before,
            "after_score": s_after,
            "better_score": better_score,
            "worse_score": worse_score,
            "delta": round(delta_after_minus_before, 4),
            "degradation_delta": round(degradation_delta, 4),
        })

    # Item (2): Compute spread over distinct documents (one mean score per document)
    doc_better_means = []
    for d in distinct_doc_ids:
        scores_for_doc = [p["better_score"] for p in evaluated_pairs if p["doc_id"] == d]
        if scores_for_doc:
            doc_better_means.append(statistics.mean(scores_for_doc))

    if len(doc_better_means) > 1:
        between_doc_spread = statistics.stdev(doc_better_means)
    else:
        between_doc_spread = 0.0

    all_deg_deltas = [p["degradation_delta"] for p in evaluated_pairs]
    mean_delta, ci95_lower, ci95_upper = compute_ci95(all_deg_deltas)
    gap_to_spread_ratio = (
        round(abs(mean_delta) / between_doc_spread, 2)
        if between_doc_spread > 0
        else None
    )
    within_pair_clearly_larger = bool(gap_to_spread_ratio is not None and gap_to_spread_ratio >= 1.5)

    # Item (3): Split by document into tuning and held-out
    tuning_pairs = [p for p in evaluated_pairs if p["doc_id"] in tuning_doc_ids]
    holdout_pairs = [p for p in evaluated_pairs if p["doc_id"] in holdout_doc_ids]

    # Choose threshold on tuning (median of worse/degraded scores)
    tuning_worse_scores = [p["worse_score"] for p in tuning_pairs]
    candidate_threshold = statistics.median(tuning_worse_scores) if tuning_worse_scores else 0.5

    # Report AUC and published false-alarm rate on held-out
    held_out_better = [p["better_score"] for p in holdout_pairs]
    held_out_worse = [p["worse_score"] for p in holdout_pairs]
    held_out_auc = compute_roc_auc(held_out_better, held_out_worse)

    false_alarms = sum(1 for s in held_out_better if s <= candidate_threshold)
    held_out_fa_rate = round(false_alarms / len(held_out_better), 4) if held_out_better else 0.0

    # Group by document type
    by_doc_type = {}
    distinct_doc_types = sorted(list({p["doc_type"] for p in evaluated_pairs}))
    for dt in distinct_doc_types:
        dt_pairs = [p for p in evaluated_pairs if p["doc_type"] == dt]
        dt_tuning = [p for p in dt_pairs if p["doc_id"] in tuning_doc_ids]
        dt_holdout = [p for p in dt_pairs if p["doc_id"] in holdout_doc_ids]

        dt_deltas = [p["degradation_delta"] for p in dt_pairs]
        dt_mean_d, dt_ci_l, dt_ci_u = compute_ci95(dt_deltas)

        dt_thresh = (
            statistics.median([p["worse_score"] for p in dt_tuning])
            if dt_tuning
            else candidate_threshold
        )
        dt_ho_better = [p["better_score"] for p in dt_holdout]
        dt_ho_worse = [p["worse_score"] for p in dt_holdout]
        dt_auc = compute_roc_auc(dt_ho_better, dt_ho_worse) if dt_holdout else 0.5
        dt_fa = sum(1 for s in dt_ho_better if s <= dt_thresh)
        dt_fa_rate = round(dt_fa / len(dt_ho_better), 4) if dt_ho_better else 0.0

        by_doc_type[dt] = {
            "num_pairs": len(dt_pairs),
            "mean_delta": dt_mean_d,
            "ci95_lower": dt_ci_l,
            "ci95_upper": dt_ci_u,
            "candidate_threshold": round(dt_thresh, 4),
            "held_out_roc_auc": dt_auc,
            "held_out_false_alarm_rate": dt_fa_rate,
            "feasible": (dt_auc >= 0.75 and dt_fa_rate <= 0.10),
        }

    return {
        "num_pairs": len(evaluated_pairs),
        "num_distinct_docs": len(distinct_doc_ids),
        "tuning_docs": sorted(list(tuning_doc_ids)),
        "holdout_docs": sorted(list(holdout_doc_ids)),
        "preset": preset_name,
        "runs": runs,
        "dry_run": dry_run,
        "within_pair_gap": {
            "mean_delta": mean_delta,
            "ci95_lower": ci95_lower,
            "ci95_upper": ci95_upper,
        },
        "between_doc_spread": round(between_doc_spread, 4),
        "gap_to_spread_ratio": gap_to_spread_ratio,
        "within_pair_clearly_larger": within_pair_clearly_larger,
        "tuning_candidate_threshold": round(candidate_threshold, 4),
        "held_out_roc_auc": held_out_auc,
        "held_out_published_false_alarm_rate": held_out_fa_rate,
        "absolute_gate_feasible": (held_out_auc >= 0.75 and held_out_fa_rate <= 0.10 and within_pair_clearly_larger),
        "by_doc_type": by_doc_type,
        "pairs": evaluated_pairs,
    }


def main():
    parser = argparse.ArgumentParser(description="Feasibility check for quality regression detection (#42)")
    parser.add_argument("--pairs", type=Path, help="JSON file with pairs to evaluate")
    parser.add_argument("--doc", action="append", type=Path, help="Document(s) to generate degradations for")
    parser.add_argument("--doc-type", default="generic", help="Default doc_type for documents (default: generic)")
    parser.add_argument("--preset", default="quality", help="Preset name (default: quality)")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per doc (default: 3)")
    parser.add_argument("--holdout-fraction", type=float, default=0.3, help="Fraction of documents in holdout set")
    parser.add_argument("--dry-run", action="store_true", help="Use mock evaluation without API calls")
    parser.add_argument("--out", type=Path, help="Path to save JSON output")

    args = parser.parse_args()

    doc_paths = args.doc or []
    if not args.pairs and not doc_paths:
        default_doc = Path("tests/fixtures/design_doc/en.md")
        if default_doc.is_file():
            doc_paths = [default_doc]
        else:
            parser.error("Either --pairs or at least one --doc must be specified.")

    report = run_feasibility(
        pairs_file=args.pairs,
        doc_paths=doc_paths,
        default_doc_type=args.doc_type,
        preset_name=args.preset,
        runs=args.runs,
        holdout_fraction=args.holdout_fraction,
        dry_run=args.dry_run,
    )

    print("=== Feasibility Check Summary (Issue #42) ===")
    print(f"Evaluated Pairs: {report['num_pairs']} (across {report['num_distinct_docs']} distinct documents)")
    print(f"Tuning Docs: {len(report['tuning_docs'])}, Held-out Docs: {len(report['holdout_docs'])}")
    print(f"Mean Δ (within-pair): {report['within_pair_gap']['mean_delta']} "
          f"[95% CI: {report['within_pair_gap']['ci95_lower']}, {report['within_pair_gap']['ci95_upper']}]")
    print(f"Between-document spread (σ): {report['between_doc_spread']}")
    ratio_str = f"{report['gap_to_spread_ratio']}" if report['gap_to_spread_ratio'] is not None else "N/A"
    print(f"Gap / Spread Ratio: {ratio_str} "
          f"({'Clearly larger (≥1.5)' if report['within_pair_clearly_larger'] else 'Not clearly larger (<1.5)'})")
    print(f"Tuning Candidate Threshold: {report['tuning_candidate_threshold']}")
    print(f"Held-out ROC-AUC (better vs worse): {report['held_out_roc_auc']} (Target: ≥ 0.75)")
    print(f"Held-out Published False Alarm Rate: {report['held_out_published_false_alarm_rate'] * 100:.1f}% (Target: ≤ 10%)")
    print(f"Absolute Gate Feasible: {'YES' if report['absolute_gate_feasible'] else 'NO (Spotting regressions only)'}")

    if report["by_doc_type"]:
        print("\n--- By Document Type ---")
        for dt, dt_stats in report["by_doc_type"].items():
            print(f"• {dt} ({dt_stats['num_pairs']} pairs): "
                  f"Mean Δ: {dt_stats['mean_delta']} [95% CI: {dt_stats['ci95_lower']}, {dt_stats['ci95_upper']}] | "
                  f"Threshold: {dt_stats['candidate_threshold']} | "
                  f"Held-out AUC: {dt_stats['held_out_roc_auc']} | "
                  f"False Alarm: {dt_stats['held_out_false_alarm_rate'] * 100:.1f}% | "
                  f"Feasible: {'YES' if dt_stats['feasible'] else 'NO'}")

    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nDetailed results saved to {args.out}")


if __name__ == "__main__":
    main()
