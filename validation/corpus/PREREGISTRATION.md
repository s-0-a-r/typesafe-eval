# Pre-registration for the v0.4.0 rewording rounds

Written after the round 0 tuning run (2026-09-29) and before any rewording, any new API call and any held-out run. The gates in the #42 comments and in `build_pairs.py` stay as they are, except for the one deviation below. Round 0 results: #41, #42, #43. Public specifications (KEP, PEP, Rust RFC, Go proposal, Swift Evolution) are named; other documents are referred to by label file, split and a letter (for example "pr_ja tuning doc A"), because their authors did not ask to be scored (`README.md`).

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

## Round 1 (written before running it)

This section was added with the rewording itself, before any round 1 call.

**The wording.** One suffix is appended, unchanged, to the `instructions` of every Noul question in `design_doc` (10) and `pr_description` (5):

> Answer yes only if the document states what the question asks outright, in a section, paragraph or line of its own, or in a sentence that says it. Do not answer yes because it could be inferred from text that is about something else.

It is wider than the "own section or paragraph" of #41 on purpose. The labels were written to the rule "stated explicitly", and some present labels rest on less than a section: `go-draft-fuzzing`'s `metrics` on one sentence, and several `related_issues` on a single line with a link or "Fixes #N". A section-or-paragraph wording would turn those into new false alarms that the labels do not support.

Considered and not used:
- naming a "metadata field" (KEP front matter for `owner_timeline`): `owner_timeline` has no present label in tuning, so the effect could not be checked;
- "A statement that there is none counts.": `breaking_changes` already asks "whether there are";
- "parts written for another purpose" in the second sentence: what a section was written for is not visible in the text. A KEP "What are other known failure modes?" answer would count as written for risks. "About something else" asks what the text is about, which can be checked against the document;
- "list item" and "link": bare links and "Fixes #N" already score 0.90 to 0.98 for `related_issues` in round 0b, and "list item" would make one bullet in a list of design decisions easier to take as a non-goal.

**How round 1 is read.**
- Files: `labels_{pr_en,pr_ja,design_doc_en,design_doc_ja}.tuning.yaml`, once each. `tech_spec` and `quality` are not rerun; their questions do not change.
- Criterion 4 compares with round 0b (`results/2026-09-29b/`, the same tool after the fixes above), not round 0. It counts misses and false alarms per (file, question). A lower probability without a changed verdict is not worse. A question with no items in a file cannot be worse there.
- A present item that fails criterion 3 makes its question "not met" in that preset version.
- Criterion 3 already fails in round 0b for four present items: pr_en tuning doc A `related_issues` 0.56 / 0.59, pr_ja tuning doc A `testing` 0.61 / 0.61, `kep-3325` `migration` 0.60 / 0.59, `go-draft-fuzzing` `metrics` 0.61 / 0.56. Round 1 is read against these.
- `kep-3325` `risks` (absent) is at 0.49 / 0.49 in round 0b, within noise of the threshold. Any wording can move it. If it becomes a miss, it counts as worse under criterion 4; it is not explained away afterwards.
- The preset version is the commit that adds this section. The run log records that commit and the sha256 of both preset files.

**If a round 2 is needed.** The change again applies to every Noul question in both presets, all four files are rerun, and criterion 4 still compares with round 0b. A file that passed in round 1 is not frozen while the others are reworded.

## Round 1 result, and the held-out run (written before running it)

Round 1 ran once on 2026-09-29 (tool d0efa2a, `results/2026-09-29c/`). Against round 0b:

| File | 1. min_detected | 2. False alarms | 3. Margin 0.15 | 4. Not worse | Result |
|---|---|---|---|---|---|
| design_doc_ja | 15/16 (13) | 0 | met | met | met |
| pr_ja | 3/3 (3) | 0 | pr_ja tuning doc B `impact` 0.65 / 0.63 | met | not met |
| pr_en | 10/10 (9) | 1: pr_en tuning doc A `related_issues` 0.53 / 0.48 | not met | not met | not met |
| design_doc_en | 14/17 (16) | 0 | `kep-3325` `migration`, `go-draft-fuzzing` `metrics` | `kep-3325` `risks` became a miss (0.64 / 0.65) | not met |

The three non_goals positive controls stay at 0.99. Misses fell from 8 to 4, false alarms rose from 0 to 1.

**No round 2.** The rules allow one more round, but it has to be one uniform change to every question. The remaining failures need opposite changes: pr_en tuning doc A needs a looser reading (its only reference is a line linking another pull request, and the `related_issues` question lists issues, tickets, design docs and discussions but not pull requests), while `design_doc_en` needs two of its three misses to go below 0.5 at once. Round 1 moved them by 0.02 to 0.09, and one moved the wrong way. A stricter change could not do that, and a looser one would undo `design_doc_ja`. Fixing `related_issues` means changing that one question, which these rules do not allow; it goes to v0.5. The preset version shipped in v0.4.0 is d0efa2a.

**From files to questions.** The four criteria decide whether a file passed. What the README says about each question comes from all tuning files of its preset together, because a preset ships one wording for both languages: a question is reliable when it has no miss, no false alarm and no present item inside 0.5 ± 0.15 in any of them. On round 1:

- `design_doc`: reliable `alternatives`, `rollback`, `open_questions`; `goal` recognizes a stated goal but has no absent label; `owner_timeline` flags a missing owner or timeline but has no present label; not reliable `non_goals` (3 of 7 missed), `risks` (1 of 3), `migration`, `metrics` (criterion 3); `impact` has no tuning label and is not evaluated.
- `pr_description`: reliable `testing`, `breaking_changes`; `summary` recognizes a summary but has no absent label; not reliable `related_issues` (1 false alarm), `impact` (criterion 3).

`design_doc_ja` passing is reported as counts (4 documents, 15 of 16 absent items flagged, no false alarm). It licenses no Japanese-specific claim: its held-out set has no absent label.

**The held-out run.** Once, on d0efa2a, for `labels_{design_doc_en,design_doc_ja,pr_en,pr_ja}.heldout.yaml`. What they contain:

| File | Documents | Absent | Present |
|---|---|---|---|
| design_doc_en | 5 | 14 | 9 (2 non_goals controls) |
| design_doc_ja | 1 | 0 | 5 |
| pr_en | 3 | 2 | 10 |
| pr_ja | 3 | 5 | 6 |

- Held-out only confirms. A question that is reliable on tuning becomes not reliable if held-out shows a miss, a false alarm or a present item inside 0.5 ± 0.15. A question that is not reliable on tuning is not promoted by held-out.
- The wording of v0.4.0 does not change after held-out. What it shows goes to v0.5.
- The README gives counts, not "confirmed": documents, absent items flagged, false alarms, present items inside 0.5 ± 0.15, per question and split.
- `design_doc_ja` held-out checks recognition of present items only.
- Present probabilities fell by 0.03 to 0.10 from round 0b to round 1 (for example `pr_en` `summary`), so held-out may show criterion 3 failures on questions that are reliable on tuning. They are reported as they come.

## Held-out result

Run once on 2026-09-29 15:26 (tool d0efa2a, after this file's round 1 section was pushed at 15:25), `results/2026-09-29d/`.

| File | Absent flagged | False alarms | Near 0.5 (present) |
|---|---|---|---|
| design_doc_en | 13/14 | 0 | 0 |
| design_doc_ja | no absent label | 0 | 0 |
| pr_en | 2/2 | 0 | 1: pr_en held-out doc A `related_issues` 0.57 / 0.55 |
| pr_ja | 5/5 | 2: pr_ja held-out doc A `related_issues` 0.45 / 0.45, pr_ja held-out doc B `breaking_changes` 0.48 / 0.45 | 1: pr_ja held-out doc B `summary` 0.65 / 0.62 |

The one miss is `pep-0709` `non_goals` (0.77 / 0.76). Both non_goals controls score 0.99.

Applying the rules above, held-out demotes two questions that were reliable on tuning: `pr_description` `summary` (criterion 3) and `breaking_changes` (a false alarm). It confirms the problems already found for `related_issues` and `non_goals`. Nothing else changes. The README lists every question with its counts.

## Held-out

Held-out runs once per preset version. If a file fails there, the failing items ship as "not reliable" or are removed; the same held-out set is not run a second time for that version. A later confirmatory claim needs newly collected documents.

## Deviation: pair guard tolerance for down pairs

The pair guard fails a down pair whose mean delta is ≥ 0, so a +0.005 (one scoring step) fails the whole file. Before measuring anything else, the tolerance is fixed as follows: evaluate 4 tuning documents from different score levels (including the one with the +0.005 pair) 10 times each, take the largest per-document standard deviation, multiply by 3 and round up to a multiple of 0.005. That value becomes `pair_guard_down_tolerance` for `quality` and `tech-spec`, and a down pair fails only when its mean delta is above it. This is a change after seeing results and is reported as such.

Measured on 2026-09-29 (tool 2cdcc75, HTML comments stripped), 10 runs each, clarity normalized score:

| Document | Mean | SD | Range |
|---|---|---|---|
| design_doc_ja tuning doc A | 1.000 | 0.0000 | 1.000–1.000 |
| pr_ja tuning doc A | 0.878 | 0.0054 | 0.870–0.890 |
| pr_en tuning doc B | 0.597 | 0.0048 | 0.590–0.605 |
| pr_ja tuning doc C | 0.619 | 0.0071 | 0.610–0.630 |

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
