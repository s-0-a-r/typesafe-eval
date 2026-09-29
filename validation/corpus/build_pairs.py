"""Build the #42 / #43 pair files from the collected corpus.

Outputs (next to this script):
- manifest_all.json: every saved document with project, split (tuning / heldout) and exclusion reason
- pairs.json: real review pairs for scripts/feasibility_check.py --pairs (better: after). Pairs whose changed
  lines are under 5% of the longer version are left out (the edit is too small to say which is clearer)
- labels_quality_pairs.{heldout,tuning}.yaml: validate pairs (synthetic degradations: down; synthetic neutral
  edits, hand-written paraphrases and real correctness-only pairs: neutral). tuning uses 2 documents per cell
- labels_tech_spec_pairs.{heldout,tuning}.yaml: the same pairs for the tech-spec Scores (#43)
- variants/: the synthetic variant files
- labels_<name>.{tuning,heldout}.yaml: the presence labels (labels_<name>.yaml) split the same way, so
  #41 keeps a held-out set too. min_detected is recomputed per file. labels_design_doc_en also gets the
  non_goals positive controls (NON_GOALS_CONTROLS)
"""

import difflib
import hashlib
import json
import math
import random
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
MAX_CHARS = 25000
HELDOUT_FRACTION = 0.3
SEED = 20260928
MAX_PER_PROJECT = 2  # at most 2 documents per project (author / repository) in every cell
MIN_CHANGED_LINES = 0.05
# presence label files and the share of absent items that must be detected (#41)
PRESENCE_LABELS = {"labels_pr_en": 0.9, "labels_pr_ja": 0.8, "labels_design_doc_en": 0.9,
                   "labels_design_doc_ja": 0.8, "labels_tech_spec": 1.0}

FILLER = {
    "en": (
        "This section highlights essential operational context and prerequisites. "
        "There are multiple ways to interpret this, and outcomes depend heavily on implementation specifics. "
        "Extensive experimentation may be required before confirming edge case behavior."
    ),
    "ja": (
        "ここはとても大事なポイントなので、しっかり押さえておきたいところです。"
        "いろいろな考え方があると思いますが、結局は状況によって変わってくるのかなと思います。"
        "とはいえ、やってみないと分からない部分も多いので、まずは試してみるのがいいかもしれません。"
    ),
}
# An unrelated but well-formed paragraph for the "unrelated addition" neutral edit.
UNRELATED = {
    "en": (
        "## Acknowledgements\n\n"
        "Thanks to everyone who reviewed earlier drafts of this document and left comments on the discussion thread."
    ),
    "ja": (
        "## 謝辞\n\n"
        "この文書の初期の版にコメントをくださった皆さんに感謝します。議論のスレッドでの指摘はどれも参考になりました。"
    ),
}


def load_rows():
    rows = []
    for mf in sorted(ROOT.glob("manifest_*.json")):
        if mf.name in ("manifest_all.json", "manifest_variants.json"):  # outputs of this script
            continue
        for r in json.loads(mf.read_text(encoding="utf-8")):
            folder = ROOT / r["doc_type"] / r["lang"] / r["doc_id"]
            if not (folder / "after.md").is_file():
                continue  # trivial rows without files
            r["folder"] = str(folder.relative_to(ROOT))
            r["has_before"] = (folder / "before.md").is_file()
            r["source_doc"] = r["doc_id"]
            r["project"] = (r.get("repo") or r.get("source_repo")).lower()
            r.setdefault("edit_source", "unknown")
            rows.append(r)
    return rows


def check_projects(rows):
    counts = {}
    for r in rows:
        key = (r["doc_type"], r["lang"], r["project"])
        counts[key] = counts.get(key, 0) + 1
    over = {k: n for k, n in counts.items() if n > MAX_PER_PROJECT}
    if over:
        raise SystemExit(f"more than {MAX_PER_PROJECT} documents per project: {over}")
    return counts


def changed_line_ratio(r):
    before = (ROOT / r["folder"] / "before.md").read_text(encoding="utf-8").splitlines()
    after = (ROOT / r["folder"] / "after.md").read_text(encoding="utf-8").splitlines()
    changed = sum(1 for op in difflib.ndiff(before, after) if op[:1] in "+-")
    return round(changed / max(len(before), len(after), 1), 3)


def is_review_pair(r):
    return (not r["excluded"] and r["has_before"] and r.get("pair_kind", "").split()[0] == "clarity"
            and r["changed_line_ratio"] >= MIN_CHANGED_LINES)


def assign_split(rows):
    """Split by project, so two documents of one project never end up on both sides.

    Stratified: projects with a real review pair and projects without one are split separately, so
    held-out gets its share of review pairs. A cell with 7 or more review pairs keeps at least 3 in
    held-out (feasibility reports AUC per document type) and at least 4 in tuning.
    """
    strata = {}
    for r in rows:
        key = (r["doc_type"], r["lang"])
        strata.setdefault(key, {})
        strata[key].setdefault(r["project"], []).append(r)
    split = {}
    for cell, projects in sorted(strata.items()):
        by_stratum = {True: {}, False: {}}
        for proj, rs in projects.items():
            by_stratum[any(is_review_pair(r) for r in rs)][proj] = rs
        for has_pair, group in by_stratum.items():
            n = sum(len(rs) for rs in group.values())
            target = max(1, round(n * HELDOUT_FRACTION)) if n >= 2 else 0
            if has_pair and n >= 7:
                target = max(target, 3)
            held = 0
            for proj in sorted(group, key=lambda p: hashlib.sha256(f"{SEED}:{p}".encode()).hexdigest()):
                side = "heldout" if held < target else "tuning"
                if side == "heldout":
                    held += len(group[proj])
                for r in group[proj]:
                    split[r["source_doc"]] = side
    for r in rows:
        r["split"] = split[r["source_doc"]]


def split_frontmatter(text):
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return (m.group(0), text[m.end():]) if m else ("", text)


def blocks(body):
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


def is_heading(b):
    return b.lstrip().startswith("#")


def shuffled(body, lang):
    bs = blocks(body)
    random.Random(SEED).shuffle(bs)
    return "\n\n".join(bs)


def no_headings(body, lang):
    out = []
    for b in blocks(body):
        if b.startswith("```"):
            out.append(b)
            continue
        lines = [l for l in b.split("\n") if not l.lstrip().startswith("#")]
        if lines:
            out.append("\n".join(lines))
    return "\n\n".join(out)


def padded(body, lang):
    return "\n\n".join(b if b.startswith("```") else f"{b}\n\n{FILLER[lang]}" for b in blocks(body))


def removed_middle(body, lang):
    """Remove the middle third of non-heading blocks (the "removed steps" degradation)."""
    bs = blocks(body)
    idx = [i for i, b in enumerate(bs) if not is_heading(b)]
    if len(idx) < 6:
        return None
    drop = set(idx[len(idx) // 3: 2 * len(idx) // 3])
    return "\n\n".join(b for i, b in enumerate(bs) if i not in drop)


def swap_sections(body, lang):
    """Swap the last two sections at the top heading level (neutral: independent sections)."""
    lines = body.split("\n")
    levels = [len(m.group(1)) for l in lines if (m := re.match(r"^(#{1,3}) ", l))]
    if not levels:
        return None
    top = min(levels)
    starts = [i for i, l in enumerate(lines) if re.match(rf"^#{{{top}}} ", l)]
    if len(starts) < 3:
        return None
    a, b = starts[-2], starts[-1]
    return "\n".join(lines[:a] + lines[b:] + [""] + lines[a:b])


def unrelated_addition(body, lang):
    return body.rstrip("\n") + "\n\n" + UNRELATED[lang] + "\n"


# Positive controls for the design-doc non_goals question (#41). The corpus has only 2 documents whose
# non_goals label is present, so a rewording that makes the question stricter could not show new false alarms.
# Each control is a public specification with a short hand-written Non-goals section inserted (text written for
# this corpus, consistent with the document's own scope). Labeled non_goals: present before any evaluation of it.
# (pattern, insert "before" / "after" the match, text)
NON_GOALS_CONTROLS = {
    "kep-3140": (r"^### Non-Goals\n", "after",
                 "\n- Changing the behavior of CronJobs that do not set `.spec.timeZone`; they keep using the time zone\n"
                 "  of kube-controller-manager.\n"
                 "- Shipping or updating a time zone database outside the one embedded in the Go binary.\n"),
    "kep-3325": (r"^### Non-Goals\n", "after",
                 "\n- Adding a resource that stores users or groups in the cluster.\n"
                 "- Changing how authenticators produce user attributes; the endpoint only reports what authentication\n"
                 "  already returned.\n"),
    "rfc-3027": (r"^## Guide-level explanation\n", "before",
                 "## Non-goals\n\n"
                 "- Changing lifetime extension for expressions that are not promoted.\n"
                 "- Adding new syntax for requesting promotion explicitly.\n\n"),
    "pep-0655": (r"^Rationale\n=+\n", "before",
                 "Non-goals\n=========\n\n"
                 "- Enforcing required keys at runtime; checking stays the job of static type checkers.\n"
                 "- Changing the meaning of ``total`` for TypedDicts that do not use the new qualifiers.\n\n\n"),
    "pep-0709": (r"^Rationale\n=+\n", "before",
                 "Non-goals\n=========\n\n"
                 "- Inlining generator expressions; they keep their own frame.\n"
                 "- Changing the scoping rules of comprehensions as seen by Python code.\n\n\n"),
}


def insert_non_goals(text, pattern, where, section):
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit(f"non_goals control: pattern {pattern!r} not found")
    at = m.end() if where == "after" else m.start()
    return text[:at] + section + text[at:]


DOWN = {"shuffled": shuffled, "no_headings": no_headings, "padded": padded, "removed_middle": removed_middle}
NEUTRAL = {"swap_sections": swap_sections, "unrelated_addition": unrelated_addition}


def main():
    rows = load_rows()
    for r in rows:
        sizes = [len((ROOT / r["folder"] / "after.md").read_text(encoding="utf-8"))]
        if r["has_before"]:
            sizes.append(len((ROOT / r["folder"] / "before.md").read_text(encoding="utf-8")))
        r["max_chars"] = max(sizes)
        r["excluded"] = "over 25000 chars (Scores are not chunked, #46)" if r["max_chars"] > MAX_CHARS else None
    project_counts = check_projects(rows)
    for r in rows:
        r["changed_line_ratio"] = changed_line_ratio(r) if r["has_before"] else None
    assign_split([r for r in rows if not r["excluded"]])
    for r in rows:
        r.setdefault("split", "excluded")

    pairs = []
    for r in rows:
        if r["excluded"] or not r["has_before"] or r.get("pair_kind", "").split()[0] != "clarity":
            continue
        if r["changed_line_ratio"] < MIN_CHANGED_LINES:
            r["review_pair_excluded"] = f"changed lines {r['changed_line_ratio']} < {MIN_CHANGED_LINES}"
            continue
        pairs.append({
            "id": r["doc_id"], "doc_id": r["source_doc"], "doc_type": r["doc_type"], "lang": r["lang"],
            "split": r["split"], "better": "after", "edit_source": r["edit_source"],
            "before": f"{r['folder']}/before.md", "after": f"{r['folder']}/after.md",  # relative to corpus/
        })

    def pick_bases(split):
        bases = {}
        for r in rows:
            if r["excluded"] or r["split"] != split:
                continue
            bases[r["source_doc"]] = r
        return bases

    def make_pairs(bases):
        vpairs, skipped = [], []
        for src, r in sorted(bases.items()):
            after = ROOT / r["folder"] / "after.md"
            front, body = split_frontmatter(after.read_text(encoding="utf-8"))
            vdir = ROOT / "variants" / src
            vdir.mkdir(parents=True, exist_ok=True)
            for expected, fns in (("down", DOWN), ("neutral", NEUTRAL)):
                for name, fn in fns.items():
                    p = vdir / f"{name}.md"
                    out = fn(body, r["lang"])
                    if out is None or out.strip() == body.strip():
                        p.unlink(missing_ok=True)
                        continue
                    text = front + out
                    if len(text) > MAX_CHARS:
                        p.unlink(missing_ok=True)
                        skipped.append({"source_doc": src, "kind": name, "chars": len(text),
                                        "reason": "variant over 25000 chars; both sides would not be compared whole"})
                        continue
                    p.write_text(text, encoding="utf-8")
                    vpairs.append({"before": str(after.relative_to(ROOT)), "after": str(p.relative_to(ROOT)),
                                   "kind": name, "doc_id": src, "expect": {"clarity": expected}})
            # hand-written paraphrase (neutral), kept in variants/ and never regenerated
            para = vdir / "paraphrase.md"
            if para.is_file():
                vpairs.append({"before": str(after.relative_to(ROOT)), "after": str(para.relative_to(ROOT)),
                               "kind": "paraphrase", "doc_id": src, "runs": 10, "expect": {"clarity": "neutral"}})
        # real correctness-only review pairs: reported, never gating (a real fix may move clarity)
        for r in rows:
            if (not r["excluded"] and r["source_doc"] in bases and r["has_before"]
                    and r.get("pair_kind") == "correctness"):
                vpairs.append({"before": f"{r['folder']}/before.md", "after": f"{r['folder']}/after.md",
                               "kind": "real_correctness", "doc_id": r["source_doc"], "expect": {"clarity": "neutral"}})
        return vpairs, skipped

    # tuning: two documents per (doc_type, lang) cell from different projects, chosen by hash so the choice is fixed
    tuning_all = pick_bases("tuning")
    tuning = {}
    by_cell = {}
    for src, r in tuning_all.items():
        by_cell.setdefault((r["doc_type"], r["lang"]), []).append(src)
    for cell, srcs in sorted(by_cell.items()):
        seen = set()
        for src in sorted(srcs, key=lambda d: hashlib.sha256(f"{SEED}:tune:{d}".encode()).hexdigest()):
            proj = tuning_all[src]["project"]
            if proj in seen or len(seen) == 2:
                continue
            seen.add(proj)
            tuning[src] = tuning_all[src]
    for r in rows:
        r["tuning_variant_base"] = r["source_doc"] in tuning and tuning[r["source_doc"]] is r

    criteria = {
        # #42 criterion 4, fixed before any held-out run (see the #42 comment)
        "group_by": "kind",
        "degradation_ci_upper_max": -0.1,
        "neutral_ci_abs_max": 0.05,
        "min_group_size": 6,
        "pair_guard_neutral_abs_max": 0.10,
        # 3 x the largest per-document sd over 10 repeat runs, rounded up to 0.005 (PREREGISTRATION.md)
        "pair_guard_down_tolerance": 0.025,
        "report_only_kinds": ["real_correctness"],
        "per_pair_kinds": ["paraphrase"],  # n=3, runs=10, each pair gated on its own run CI
    }
    outputs = {}
    for split, bases in (("heldout", pick_bases("heldout")), ("tuning", tuning)):
        vpairs, skipped = make_pairs(bases)
        outputs[split] = (vpairs, skipped, sorted(bases))
        hdr = (f"# Built by build_pairs.py on 2026-09-28. split: {split} ({len(bases)} base documents, split by project).\n"
               "# down = synthetic degradation of the base; neutral = synthetic neutral edit, hand-written paraphrase\n"
               "# (Claude, runs 10) or a real correctness-only review pair (report only).\n"
               "# Variants over 25000 chars are left out; see manifest_variants.json.\n")
        doc = {"preset": "quality", "runs": 3, "criteria": criteria, "pairs": vpairs}  # split is in the header
        (ROOT / f"labels_quality_pairs.{split}.yaml").write_text(
            hdr + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (ROOT / "labels_quality_pairs.yaml").unlink(missing_ok=True)

    # tech-spec Scores (#43) on the same pairs. Only removing content is a degradation of depth or edge-case
    # coverage; reordering, dropping headings and filler change presentation, not content, so they are reported
    # but do not gate. Neutral edits keep the same expectation as for clarity.
    ts_criteria = dict(criteria, report_only_kinds=["real_correctness", "shuffled", "no_headings", "padded"])
    for split, (vpairs, _, bases) in outputs.items():
        ts_pairs = [dict(v, expect={q: ("down" if v["kind"] == "removed_middle" else v["expect"]["clarity"])
                                    for q in ("technical_depth", "edge_case_coverage")}) for v in vpairs]
        hdr = (f"# Built by build_pairs.py. split: {split} ({len(bases)} base documents). tech-spec Scores on the\n"
               "# labels_quality_pairs pairs: removed_middle is down; shuffled, no_headings and padded are report only.\n")
        doc = {"preset": "tech-spec", "runs": 3, "criteria": ts_criteria, "pairs": ts_pairs}
        (ROOT / f"labels_tech_spec_pairs.{split}.yaml").write_text(
            hdr + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    split_of = {f"{r['folder']}/after.md": r["split"] for r in rows}
    by_doc = {r["source_doc"]: r for r in rows if not r["excluded"]}
    controls = []
    for src, (pattern, where, section) in NON_GOALS_CONTROLS.items():
        r = by_doc[src]
        after = ROOT / r["folder"] / "after.md"
        p = ROOT / "variants" / src / "non_goals_inserted.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(insert_non_goals(after.read_text(encoding="utf-8"), pattern, where, section), encoding="utf-8")
        path = str(p.relative_to(ROOT))
        split_of[path] = r["split"]
        controls.append({"path": path, "expect": {"non_goals": "present"}})
    for name, ratio in PRESENCE_LABELS.items():
        src = yaml.safe_load((ROOT / f"{name}.yaml").read_text(encoding="utf-8"))
        if name == "labels_design_doc_en":
            src["documents"] = src["documents"] + controls
        for split in ("tuning", "heldout"):
            docs = [d for d in src["documents"] if split_of[d["path"]] == split]
            absent = sum(v == "absent" for d in docs for v in d["expect"].values())
            present = sum(v == "present" for d in docs for v in d["expect"].values())
            doc = dict(src, documents=docs)
            doc["criteria"] = dict(src["criteria"], min_detected=math.ceil(ratio * absent))
            hdr = (f"# Built by build_pairs.py from {name}.yaml (edit that file, not this one). split: {split}.\n"
                   f"# {len(docs)} documents, {absent} absent / {present} present labels. "
                   f"min_detected = ceil({ratio} x absent).\n"
                   + ("# Includes the non_goals positive controls (variants/*/non_goals_inserted.md, NON_GOALS_CONTROLS).\n"
                      if name == "labels_design_doc_en" else ""))
            (ROOT / f"{name}.{split}.yaml").write_text(
                hdr + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    (ROOT / "manifest_all.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "manifest_variants.json").write_text(json.dumps(
        {k: {"bases": v[2], "skipped": v[1]} for k, v in outputs.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")

    for (dt, lang, proj), n in sorted(project_counts.items()):
        print(f"  {dt:15} {lang}  {proj:45} {n}")
    cells = {}
    for r in rows:
        k = (r["doc_type"], r["lang"])
        c = cells.setdefault(k, {"docs": set(), "heldout": set(), "excluded": 0})
        c["docs"].add(r["source_doc"])
        if r["split"] == "heldout":
            c["heldout"].add(r["source_doc"])
        if r["excluded"]:
            c["excluded"] += 1
    for k, c in sorted(cells.items()):
        n_pairs = sum(1 for p in pairs if (p["doc_type"], p["lang"]) == k)
        print(f"{k[0]:15} {k[1]}  source docs {len(c['docs']):2}  heldout {len(c['heldout']):2}  "
              f"excluded files {c['excluded']}  review pairs {n_pairs}")
    print("review pairs total", len(pairs), " heldout", sum(p["split"] == "heldout" for p in pairs),
          " ai_assisted", sum(p["edit_source"] == "ai_assisted" for p in pairs))
    print("left out of pairs.json:", [(r["doc_id"], r["review_pair_excluded"]) for r in rows if r.get("review_pair_excluded")])
    for split, (vpairs, skipped, bases) in outputs.items():
        kinds = {}
        for v in vpairs:
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
        print(f"{split}: bases {len(bases)}  pairs {len(vpairs)}  {kinds}  skipped {[(s['source_doc'], s['kind']) for s in skipped]}")


if __name__ == "__main__":
    main()
