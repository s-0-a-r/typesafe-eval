# Validation corpus

Public documents and labels used to check the presets (#41, #42, #43). The documents are written by third parties and spread over many projects, with at most 2 documents per project or author in every cell.

## What the labels mean

This corpus measures typesafe-eval, not the documents. A label such as `risks: absent` says only that the document has no section or explicit statement about risks, so that we can check whether the tool notices. It is not a judgment of the document's quality. Many items are normally absent for a document type: an article rarely has a rollback plan, and a small bug-fix PR rarely lists breaking changes. That is expected.

Results are published per kind and document type (counts, means, CIs, detection rates). Per-document results are published only for public specifications (KEP, PEP, Rust RFC, Go proposal, Swift Evolution). `summarize_results.py` produces the published summary; the full reports stay in `results/`, which is not committed.

If you wrote one of these documents and want it removed, open an issue. We will remove it from the manifests and labels.

## Contents

| Cell | Documents | Labels |
|---|---|---|
| `article/ja` | 14 Zenn / tech blog articles, one per author | quality pairs, feasibility |
| `design_doc/en` | KEP, PEP, Rust RFC, Go proposal, Swift Evolution | `labels_design_doc_en.yaml`, `labels_tech_spec.yaml` |
| `design_doc/ja` | 5 design docs from 5 repositories | `labels_design_doc_ja.yaml`, `labels_tech_spec.yaml` |
| `pr_description/en` | 10 PR descriptions from 6 repositories | `labels_pr_en.yaml` |
| `pr_description/ja` | 8 PR descriptions from 6 repositories | `labels_pr_ja.yaml` |

Each document folder has `after.md` (the final version) and, for revision pairs, `before.md`. The only committed files derived from the documents are three paraphrases of public specifications (see `NOTICE.md`).

## Fetching the documents

The document text is not committed. Fetch it before running anything:

```sh
python fetch_documents.py   # articles and design docs from raw.githubusercontent.com, no login needed
python fetch_pr_bodies.py   # PR descriptions via the GitHub GraphQL API (needs `gh auth login`)
python build_pairs.py       # variants/, pairs.json, labels_quality_pairs.{tuning,heldout}.yaml
```

Both fetch scripts check every file against the sha256 in the manifests and stop on a mismatch, which means the source changed after the corpus was built.

## Tuning and held-out

`build_pairs.py` splits each cell by project into tuning and held-out, stratified so held-out gets its share of real review pairs. The presence labels are split the same way: edit `labels_<name>.yaml`, and `build_pairs.py` writes `labels_<name>.tuning.yaml` and `labels_<name>.heldout.yaml`. Rewording rounds use only the `.tuning.yaml` files. The held-out files run once per preset version. The gating rules are fixed in the #42 comments.

Labels were written from reading the documents before any evaluation and are not changed after seeing results. A change needs its own commit with the reason.
