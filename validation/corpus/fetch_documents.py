"""Fetch the article and design-doc pairs listed in the manifests.

The documents are written by other people, so their text is not committed. This script rebuilds them
from the source repositories at the recorded commits:
- before = the file at before_sha (before_path when the file was renamed), after = the file at after_sha
Both are saved with LF line endings to <doc_type>/<lang>/<doc_id>/{before,after}.md and checked against
the sha256 recorded in the manifest. A mismatch (for example a rewritten history) is reported and not written.

Files are read from raw.githubusercontent.com, so no GitHub login is needed.
Run: python fetch_documents.py [--force]
Then run fetch_pr_bodies.py for the PR descriptions, and build_pairs.py to rebuild the synthetic variants.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
MANIFESTS = ["manifest_article_ja.json", "manifest_design_doc_en.json", "manifest_design_doc_ja.json"]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(repo, path, ref):
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    with urllib.request.urlopen(url, timeout=30) as res:
        return res.read().decode("utf-8").replace("\r\n", "\n")


def main():
    force = "--force" in sys.argv
    failed = 0
    for mf in MANIFESTS:
        for r in json.loads((ROOT / mf).read_text(encoding="utf-8")):
            repo = r.get("repo") or r["source_repo"]
            d = ROOT / r["doc_type"] / r["lang"] / r["doc_id"]
            try:
                before = fetch(repo, r.get("before_path") or r["path"], r["before_sha"])
                after = fetch(repo, r["path"], r["after_sha"])
            except Exception as e:
                print(f"FAIL {r['doc_id']}: {e}")
                failed += 1
                continue
            ok = sha(before) == r["sha256_before"] and sha(after) == r["sha256_after"]
            if not ok and not force:
                print(f"CHANGED {r['doc_id']}: the fetched text differs from the corpus (use --force to write anyway)")
                failed += 1
                continue
            d.mkdir(parents=True, exist_ok=True)
            (d / "before.md").write_text(before, encoding="utf-8", newline="\n")
            (d / "after.md").write_text(after, encoding="utf-8", newline="\n")
            print(f"{'ok' if ok else 'FORCED'} {r['doc_id']}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
