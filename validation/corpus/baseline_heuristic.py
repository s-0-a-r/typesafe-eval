"""Non-LLM baseline for the tuning tables (see PREREGISTRATION.md). No API calls.

- Presence labels: an item is "present" when a heading (Markdown `#`, reStructuredText underline, or a line that is
  only bold text) contains one of the fixed keywords below. related_issues also counts an issue reference
  (`#123`, `Fixes`, `Closes`, an issues/ or pull/ URL). summary counts any paragraph before the first heading or
  under a Summary-like heading.
- Synthetic pairs: a diff rule on the two versions. "down" when the heading count drops, or the length changes
  by more than 10%; otherwise "neutral". It uses the reference version, which the tool does not.

The keywords were fixed once, from the question names, and are not tuned. The point is to show which gates a
trivial rule already passes, so the tables show what the LLM adds.

Usage: python baseline_heuristic.py labels_<name>.tuning.yaml [...]
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent

KEYWORDS = {
    "goal": ["goal", "motivation", "summary", "abstract", "introduction", "目的", "目標", "背景", "概要"],
    "non_goals": ["non-goal", "non goal", "out of scope", "scope", "スコープ外", "対象外", "やらないこと", "非目標"],
    "alternatives": ["alternative", "rejected", "considered", "代替", "検討した", "比較", "他の案"],
    "risks": ["risk", "drawback", "concern", "caveat", "リスク", "懸念", "注意"],
    "rollback": ["rollback", "roll back", "downgrade", "disable", "ロールバック", "切り戻し", "無効化"],
    "metrics": ["metric", "success", "measure", "slo", "sli", "指標", "計測", "成功"],
    "migration": ["migration", "upgrade", "compatibility", "移行", "互換"],
    "open_questions": ["open question", "unresolved", "future", "未解決", "課題", "今後"],
    "owner_timeline": ["timeline", "schedule", "milestone", "owner", "implementation history", "スケジュール", "担当", "マイルストーン"],
    "summary": ["summary", "description", "overview", "what", "概要", "説明", "変更内容"],
    "testing": ["test", "verification", "how to test", "テスト", "確認", "動作確認", "検証"],
    "impact": ["impact", "affect", "user-facing", "影響"],
    "breaking_changes": ["breaking", "破壊的", "互換性"],
    "related_issues": ["related", "issue", "fixes", "closes", "関連", "イシュー"],
    "has_test_plan": ["test plan", "testing", "test", "verification", "テスト", "検証"],
}
ISSUE_REF = re.compile(r"(?:^|\s)#\d+\b|\b(?:fixes|closes|resolves)\b|/(?:issues|pull)/\d+", re.I)


def headings(text):
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#"):
            out.append(s.lstrip("#").strip())
        elif i + 1 < len(lines) and s and re.fullmatch(r"[=\-~^]{3,}", lines[i + 1].strip()):
            out.append(s)
        elif re.fullmatch(r"\*\*[^*]+\*\*:?", s):
            out.append(s.strip("*: "))
    return out


def has_item(text, q):
    hs = [h.lower() for h in headings(text)]
    if any(k in h for h in hs for k in KEYWORDS[q]):
        return True
    if q == "related_issues" and ISSUE_REF.search(text):
        return True
    if q == "summary":
        body = text.split("\n#", 1)[0].strip()
        return len(body) > 40
    return False


def presence(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    det = absent = fa = present = 0
    per_q = {}
    for d in doc["documents"]:
        text = (ROOT / d["path"]).read_text(encoding="utf-8")
        for q, exp in d["expect"].items():
            hit = has_item(text, q)
            s = per_q.setdefault(q, [0, 0, 0, 0])
            if exp == "absent":
                absent += 1; s[1] += 1
                if not hit:
                    det += 1; s[0] += 1
            else:
                present += 1; s[3] += 1
                if not hit:
                    fa += 1; s[2] += 1
    print(f"## {path.stem} (baseline)\n\nAbsent detected {det}/{absent}, false alarms {fa}/{present}, "
          f"min_detected {doc['criteria']['min_detected']}.\n")
    print("| Question | Absent detected | Present false alarms |\n|---|---|---|")
    for q, (d_, a, f, p) in per_q.items():
        print(f"| {q} | {d_}/{a} | {f}/{p} |")
    print()


def pairs(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_kind = {}
    for p in doc["pairs"]:
        b = (ROOT / p["before"]).read_text(encoding="utf-8")
        a = (ROOT / p["after"]).read_text(encoding="utf-8")
        down = len(headings(a)) < len(headings(b)) or abs(len(a) - len(b)) > 0.1 * len(b)
        exp = next(iter(p["expect"].values()))
        k = by_kind.setdefault(p["kind"], [exp, 0, 0])
        k[1] += 1
        k[2] += (down if exp == "down" else not down)
    print(f"## {path.stem} (baseline diff rule)\n\n| Kind | Expected | Pairs | Rule agrees |\n|---|---|---|---|")
    for kind, (exp, n, ok) in by_kind.items():
        print(f"| {kind} | {exp} | {n} | {ok}/{n} |")
    print()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for f in sys.argv[1:]:
        p = Path(f)
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        (pairs if "pairs" in doc else presence)(p)


if __name__ == "__main__":
    main()
