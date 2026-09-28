"""Fetch the article pairs listed in manifest_article_ja.json whose text is not committed.

Articles are committed only when their repository's license clearly covers the text (COMMITTED_LICENSES).
The others are rebuilt by this script from the repository at the recorded commits:
- before = the file at before_sha, after = the file at after_sha
Both are saved with LF line endings to article/ja/<doc_id>/{before,after}.md and checked against the
sha256 recorded in the manifest. A mismatch (for example a rewritten history) is reported and not written.

Requires the GitHub CLI (`gh auth login`). Run: python fetch_articles.py [--force] [--all]
--all also fetches the committed articles, to check them against the manifest.
Afterwards run build_pairs.py to rebuild the synthetic variants.
"""

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
COMMITTED_LICENSES = {"CC-BY-4.0", "MIT", "Unlicense"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(repo, path, ref):
    out = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}"],
                         check=True, capture_output=True, text=True)
    return base64.b64decode(json.loads(out.stdout)["content"]).decode("utf-8").replace("\r\n", "\n")


def main():
    force = "--force" in sys.argv
    everything = "--all" in sys.argv
    failed = 0
    for r in json.loads((ROOT / "manifest_article_ja.json").read_text(encoding="utf-8")):
        if r["license"] in COMMITTED_LICENSES and not everything:
            continue
        d = ROOT / "article" / "ja" / r["doc_id"]
        try:
            before = fetch(r["repo"], r["path"], r["before_sha"])
            after = fetch(r["repo"], r["path"], r["after_sha"])
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
