# Third-party material

The documents in this corpus are written by other people, and their text is not committed. The manifests (`manifest_*.json`) record where each one comes from (repository, path, commit, sha256), and `fetch_documents.py` / `fetch_pr_bodies.py` download them.

The only files here derived from third-party documents are four paraphrases. Each is a reworded copy of a public specification, written by Claude (Anthropic) for testing (three on 2026-09-28, kep-3140 on 2026-09-29). They keep the original structure, headings and code but change the wording of every prose sentence. They are not the authors' text and do not represent the authors' views.

| File | Derived from | License of the original |
|---|---|---|
| `variants/pep-0655/paraphrase.md` | [PEP 655](https://github.com/python/peps/blob/3e200c644bb82d34f3368ba5dd952d51bbe82d90/peps/pep-0655.rst), python/peps | Public domain or CC0-1.0, whichever is more permissive (stated in the PEP) |
| `variants/pep-0709/paraphrase.md` | [PEP 709](https://github.com/python/peps/blob/a1e917194c2fff41e4166d6b19469f4acdbe7184/peps/pep-0709.rst), python/peps | Public domain or CC0-1.0, whichever is more permissive (stated in the PEP) |
| `variants/swift-se-0510/paraphrase.md` | [SE-0510](https://github.com/swiftlang/swift-evolution/blob/d13e38d64afacd14a3e2ca21b4a613d8449703e8/proposals/0510-dictionary-mapvalues-with-keys.md), swiftlang/swift-evolution | Apache-2.0, Copyright Apple Inc. and the Swift project authors. See `LICENSES/Apache-2.0.txt`. The file is modified as described above. |
| `variants/kep-3140/paraphrase.md` | [KEP-3140](https://github.com/kubernetes/enhancements/blob/9176a2f888f38544dfbc470e7a81b3e15ab491aa/keps/sig-apps/3140-TimeZone-support-in-CronJob/README.md), kubernetes/enhancements | Apache-2.0, Copyright The Kubernetes Authors. See `LICENSES/Apache-2.0.txt`. The file is modified as described above. |
