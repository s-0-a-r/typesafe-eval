# Validation corpus

Public documents and labels used to check the presets (#41, #42, #43). Everything here is written by third parties, spread over many projects, with at most 2 documents per project or author in every cell. Where each document comes from is in the manifests and in `NOTICE.md`.

| Cell | Documents | Labels |
|---|---|---|
| `article/ja` | 14 Zenn / tech blog articles, one per author | quality pairs, feasibility |
| `design_doc/en` | KEP, PEP, Rust RFC, Go proposal, Swift Evolution | `labels_design_doc_en.yaml`, `labels_tech_spec.yaml` |
| `design_doc/ja` | 5 design docs from 5 repositories | `labels_design_doc_ja.yaml` |
| `pr_description/en` | 10 PR descriptions from 6 repositories | `labels_pr_en.yaml` |
| `pr_description/ja` | 8 PR descriptions from 6 repositories | `labels_pr_ja.yaml` |

Each document folder has `after.md` (the final version) and, for revision pairs, `before.md`.

## Rebuilding the files that are not committed

PR descriptions and articles without a license that clearly covers their text are not committed (see `.gitignore`). Rebuild them before running anything:

```sh
python fetch_pr_bodies.py   # PR descriptions, checked against the sha256 in the manifests
python fetch_articles.py    # articles at the recorded commits, same check
python build_pairs.py       # variants/, pairs.json, labels_quality_pairs.{tuning,heldout}.yaml
```

The fetch scripts need the GitHub CLI (`gh auth login`). They stop on a sha256 mismatch, which means the source changed after the corpus was built.

## Tuning and held-out

`build_pairs.py` splits each cell by project into tuning and held-out, stratified so held-out gets its share of real review pairs. Rewording rounds use only `labels_quality_pairs.tuning.yaml`. The held-out file runs once per preset version. The gating rules are fixed in the #42 comments.

Labels were written from reading the documents before any evaluation, and are not changed after seeing results. A change needs its own commit with the reason.
