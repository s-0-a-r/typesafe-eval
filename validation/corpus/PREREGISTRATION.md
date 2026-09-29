# Pre-registration for the v0.4.0 rewording rounds

Written after the round 0 tuning run (2026-09-29) and before any rewording, any new API call and any held-out run. The gates in the #42 comments and in `build_pairs.py` stay as they are, except for the one deviation below. Round 0 results: #41, #42, #43.

## What round 0 showed

- `quality`: shuffled, padded and removed_middle pass; unrelated_addition passes. no_headings does not meet the gate (CI upper −0.041 against < −0.1). One down pair has a delta of +0.005 and fails the pair guard.
- Presence: misses cluster on `non_goals` and `risks`, with probabilities of 0.52 to 0.79 on documents that have no such section. The model infers them instead of checking that they are stated.
- Real review pairs: the tool does not tell the revised version from the original (Δ worse − better +0.013 [−0.036, +0.062], between-document σ 0.116).

## Rules for the rounds

A round changes question wording only. The threshold stays 0.5, runs stay as in the label files, and a round is run once: no re-runs after looking at the results. At most 2 rounds (#41 allows 3). A question that has not met its criteria after 2 rounds ships as "not reliable" in the README, or is removed, as #41 and #43 say.

The rewording is the one #41 fixed in advance, applied the same way to every presence (Noul) question in `design_doc` and `pr_description`: ask whether the document states the item in its own section or paragraph, not whether it can be inferred. Questions are not tuned one by one. `clarity` is not reworded: no_headings is reported as not met, and the gate is not loosened.

A round succeeds for a label file when all of these hold on the tuning split:

1. min_detected is met.
2. No false alarms.
3. Every present item's probabilities are at least 0.15 away from 0.5 (with 2 runs, a value such as 0.54 / 0.48 is decided by noise).
4. No other question or file gets more misses or false alarms than in round 0.

## Held-out

Held-out runs once per preset version. If a file fails there, the failing items ship as "not reliable" or are removed; the same held-out set is not run a second time for that version. A later confirmatory claim needs newly collected documents.

## Deviation: pair guard tolerance for down pairs

The pair guard fails a down pair whose mean delta is ≥ 0, so a +0.005 (one scoring step) fails the whole file. Before measuring anything else, the tolerance is fixed as follows: evaluate 4 tuning documents from different score levels (including the one with the +0.005 pair) 10 times each, take the largest per-document standard deviation, multiply by 3 and round up to a multiple of 0.005. That value becomes `pair_guard_down_tolerance` for `quality` and `tech-spec`, and a down pair fails only when its mean delta is above it. This is a change after seeing results and is reported as such.

Measured on 2026-09-29 (tool 2cdcc75, HTML comments stripped), 10 runs each, clarity normalized score:

| Document | Mean | SD | Range |
|---|---|---|---|
| akaza-numeric-counter-redesign | 1.000 | 0.0000 | 1.000–1.000 |
| pr-misskey-dev-misskey-14375 | 0.878 | 0.0054 | 0.870–0.890 |
| pr-python-cpython-140234 | 0.597 | 0.0048 | 0.590–0.605 |
| pr-voicevox-voicevox-1374 | 0.619 | 0.0071 | 0.610–0.630 |

Largest SD 0.0071, times 3 is 0.0212, rounded up to **0.025**.

## Added before the rounds

- **non_goals positive controls.** The corpus had only 2 documents whose `non_goals` label is present, so a stricter wording could not show new false alarms. `build_pairs.py` inserts a short hand-written Non-goals section into public specifications (tuning: kep-3140, kep-3325, rfc-3027; held-out: pep-0655, pep-0709), labeled `non_goals: present`. `risks` still has few present labels (tuning 2, held-out 1); that is a disclosed limitation.
- **tech-spec Scores (#43).** `labels_tech_spec_pairs.{tuning,heldout}.yaml` use the same pairs as `quality`. Only removed_middle is a degradation of depth or edge-case coverage; shuffled, no_headings and padded change presentation, not content, and are reported without gating.
- **HTML comments.** The labels were written with HTML comments ignored, but the tool sent them to the model. The tool now strips them, as a rendered page would. This is a tool fix, not a rewording round. The affected tuning cells are re-measured once to see its effect.
- **A tuning paraphrase.** The paraphrase pairs are all in held-out, so the per-pair gate has never run. One hand-written paraphrase of a tuning public specification (kep-3140, Apache-2.0, listed in `NOTICE.md`) is run once with runs 10 to check the gate works before held-out. It is not rerun or rewritten after seeing its result.
- **Baseline.** A heading regex plus length heuristic is run on the same tuning data, without the API, so the tables show what an LLM adds.

## What may be claimed

- Large structural damage to a document (reordering, filler, removed content) lowers `clarity`; neutral edits do not move it. Removing headings alone has a small effect.
- The checklists point out missing standard sections, with detection and false-alarm counts from this corpus (give the counts).
- The tool does not tell whether a real review revision improved a document, and scores are not comparable across documents.
- A PR description that is still an unfilled template can score higher than the filled-in version.

## Known limitations

- `design_doc_ja` held-out has no absent labels, so it checks false alarms only. `pr_en` held-out has 2 absent labels.
- `better = after` is assumed for every review pair. In some pairs the revised version is arguably harder to read.
- `go-draft-fuzzing`'s `non_goals: absent` is arguable (one "not a requirement for the MVP" sentence). The label is not changed.
- paraphrase pairs exist only in held-out.
