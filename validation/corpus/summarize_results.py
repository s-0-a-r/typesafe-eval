"""Turn validate / feasibility_check JSON reports into the Markdown summary we publish.

The full reports name every document (per-document rows, worst_pair_path). Most documents are
written by individuals who did not ask to be scored, so the published summary keeps aggregates
only, and names documents only when they are public specifications (manifest_design_doc_en.json:
KEP, PEP, Rust RFC, Go proposal, Swift Evolution). Before printing, the output is checked for any
doc_id, repository, author or URL of the other documents; if one is found, nothing is printed and
the script exits 1.

Run: python summarize_results.py results/<run>/*.json > summary.md
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
HIDDEN = "(not a public specification)"


def load_manifests():
    public, private_tokens = set(), set()
    for mf in sorted(ROOT.glob("manifest_*.json")):
        if mf.name in ("manifest_all.json", "manifest_variants.json"):
            continue
        for r in json.loads(mf.read_text(encoding="utf-8")):
            if mf.name == "manifest_design_doc_en.json":
                public.add(r["doc_id"])
                continue
            for key in ("doc_id", "repo", "source_repo", "author", "url", "source_url"):
                if r.get(key):
                    private_tokens.add(str(r[key]))
    return public, private_tokens


def doc_of(path):
    parts = Path(path).parts
    return parts[-2] if len(parts) >= 2 else path


def fmt(x, digits=3):
    return "–" if x is None else (f"{x:+.{digits}f}" if isinstance(x, float) else str(x))


def ci(lo, hi):
    return "–" if lo is None or hi is None else f"[{lo:+.3f}, {hi:+.3f}]"


def verdict(p):
    return {True: "pass", False: "not met", None: "no verdict"}[p]


def validator_section(name, rep, public):
    out = [f"## {name} (preset `{rep['preset_name']}`, runs {rep['runs']})", ""]
    s = rep["summary"]
    if s["documents_evaluated"]:
        out += [f"Documents: {s['documents_evaluated']}. Absent items detected: {s['total_detected']}/"
                f"{s['total_absent_expected']}. False alarms on present items: {s['total_false_alarms']}/"
                f"{s['total_present_expected']}.", ""]
        out += ["| Question | Absent detected | Present false alarms |", "|---|---|---|"]
        for q in rep["question_stats"].values():
            if q["pairs_count"]:
                continue
            out.append(f"| {q['question_id']} | {q['detected_count']}/{q['total_absent_expected']} | "
                       f"{q['false_alarm_count']}/{q['total_present_expected']} |")
        out.append("")
        rows = [r for r in rep["presence_results"] if doc_of(r["path"]) in public]
        if rows:
            out += ["Public specifications, per document:", "", "| Document | Question | Expected | Verdict |",
                    "|---|---|---|---|"]
            out += [f"| {doc_of(r['path'])} | {r['question_id']} | {r['expected']} | {r['verdict']} |" for r in rows]
            out.append("")
    if rep["pair_group_results"]:
        out += ["| Kind | Expected | n | Mean Δ | 95% CI | Result | Worst pair |", "|---|---|---|---|---|---|---|"]
        for g in rep["pair_group_results"]:
            worst = g.get("worst_pair_path") or ""
            doc = worst[1:worst.index("]")] if worst.startswith("[") and "]" in worst else None
            worst = f"{doc} ({fmt(g.get('worst_pair_delta'))})" if doc in public else HIDDEN if worst else "–"
            out.append(f"| {g['kind']} | {g['expected']} | {g['n']} | {fmt(g['mean_delta'])} | "
                       f"{ci(g['ci_95_lower'], g['ci_95_upper'])} | {verdict(g['passed'])} | {worst} |")
        out.append("")
    if rep["criteria_results"]:
        out += ["| Criterion | Required | Actual | Result |", "|---|---|---|---|"]
        out += [f"| {c['name']} | {c['expected']} | {c['actual']} | {verdict(c['passed'])} |"
                for c in rep["criteria_results"]]
        out.append("")
    out.append(f"Overall: {verdict(rep['all_passed'])}. Incomplete pairs: {rep['incomplete_pairs_count']}, "
               f"truncated pairs: {rep['truncated_pairs_count']}.")
    return out


def feasibility_section(name, rep, public):
    g = rep["within_pair_gap"]
    out = [f"## {name} (feasibility, preset `{rep['preset']}`, runs {rep['runs']})", "",
           f"Review pairs: {rep['num_pairs']} (tuning documents {len(rep['tuning_docs'])}, "
           f"held-out {len(rep['holdout_docs'])}).",
           f"Within-pair gap: {fmt(g['mean_delta'])} {ci(g['ci95_lower'], g['ci95_upper'])}. "
           f"Between-document spread: {fmt(rep['between_doc_spread'])}.",
           f"Held-out ROC-AUC {fmt(rep['held_out_roc_auc'])}, false-alarm rate "
           f"{fmt(rep['held_out_published_false_alarm_rate'])}. Absolute gate feasible: "
           f"{'yes' if rep['absolute_gate_feasible'] else 'no'}.", "",
           "| Document type | Pairs | Mean Δ | 95% CI | Held-out AUC | False alarms | Feasible |",
           "|---|---|---|---|---|---|---|"]
    for dt, d in rep["by_doc_type"].items():
        out.append(f"| {dt} | {d['num_pairs']} | {fmt(d['mean_delta'])} | {ci(d['ci95_lower'], d['ci95_upper'])} | "
                   f"{fmt(d['held_out_roc_auc'])} | {fmt(d['held_out_false_alarm_rate'])} | "
                   f"{'yes' if d['feasible'] else 'no'} |")
    rows = [p for p in rep["pairs"] if p["doc_id"] in public]
    if rows:
        out += ["", "Public specifications, per pair:", "", "| Document | Held-out | Δ (better − worse) |", "|---|---|---|"]
        out += [f"| {p['doc_id']} | {'yes' if p['is_holdout'] else 'no'} | {fmt(p['degradation_delta'])} |" for p in rows]
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    public, private_tokens = load_manifests()
    out = ["# typesafe-eval validation summary", ""]
    for f in sys.argv[1:]:
        rep = json.loads(Path(f).read_text(encoding="utf-8"))
        section = feasibility_section if "by_doc_type" in rep else validator_section
        out += section(Path(f).stem, rep, public) + [""]
        if rep.get("mock") or rep.get("dry_run"):
            out += ["(dry run: mock scores, not a measurement)", ""]
    text = "\n".join(out)
    leaked = sorted(t for t in private_tokens if t in text)
    if leaked:
        raise SystemExit(f"refusing to print: the summary names non-public documents: {leaked[:5]}")
    print(text)


if __name__ == "__main__":
    main()
