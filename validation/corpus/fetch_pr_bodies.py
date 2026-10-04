"""Fetch the PR description pairs listed in manifest_pr_description_{en,ja}.json.

PR bodies are not committed (their license is unclear). This script rebuilds them:
- before = the original body (the oldest userContentEdit, recorded at the PR's creation time)
- after  = the current body
Both are saved with LF line endings to pr_description/<lang>/<doc_id>/{before,after}.md and
checked against the sha256 recorded in the manifest. A mismatch means the author edited the
PR (or deleted an edit) after the corpus was built; the pair is then reported and not written.

Requires the GitHub CLI (`gh auth login`). Run: python fetch_pr_bodies.py [--force]
Afterwards run build_pairs.py to rebuild the synthetic variants.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
QUERY = """query($owner:String!,$name:String!,$num:Int!){ repository(owner:$owner,name:$name){
  pullRequest(number:$num){ createdAt body userContentEdits(first:100){ nodes{ editedAt diff } } } } }"""


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(repo, num):
    owner, name = repo.split("/")
    gh_bin = shutil.which("gh") or "/usr/local/bin/gh"
    out = subprocess.run(
        [
            gh_bin,
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"num={num}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    pr = json.loads(out.stdout)["data"]["repository"]["pullRequest"]
    nodes = pr["userContentEdits"]["nodes"]  # newest first
    if not nodes:
        raise RuntimeError("no edit history")
    orig = nodes[-1]
    if orig["diff"] is None or orig["editedAt"] != pr["createdAt"]:
        raise RuntimeError("the original body is no longer in the edit history")
    lf = lambda t: t.replace("\r\n", "\n")
    return lf(orig["diff"]), lf(pr["body"])


def main():
    force = "--force" in sys.argv
    failed = 0
    for lang in ("en", "ja"):
        for r in json.loads(
            (ROOT / f"manifest_pr_description_{lang}.json").read_text(encoding="utf-8")
        ):
            d = ROOT / "pr_description" / lang / r["doc_id"]
            try:
                before, after = fetch(r["repo"], r["pr_number"])
            except Exception as e:
                print(f"FAIL {r['doc_id']}: {e}")
                failed += 1
                continue
            ok = sha(before) == r["sha256_before"] and sha(after) == r["sha256_after"]
            if not ok and not force:
                print(
                    f"CHANGED {r['doc_id']}: the fetched text differs from the corpus (use --force to write anyway)"
                )
                failed += 1
                continue
            d.mkdir(parents=True, exist_ok=True)
            (d / "before.md").write_text(before, encoding="utf-8", newline="\n")
            (d / "after.md").write_text(after, encoding="utf-8", newline="\n")
            print(f"{'ok' if ok else 'FORCED'} {r['doc_id']}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
