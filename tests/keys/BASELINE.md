# Segmentation baseline

Recorded 23 August 2026, before any Phase 2 work.

Measured by `python tools/measure.py` against the hand-marked keys in
this folder. Scoring is per content line, so a boundary placed wrongly
counts against every line it displaces.

| Text | Lines scored | Correct | Accuracy | Errors |
|---|---|---|---|---|
| `CBronte_Jane.txt` | 4,082 | 4,082 | 100.0% | 0 |
| `pg921-images-3.epub` | 1,969 | 1,968 | 99.9% | 1 |
| `romeo_juliet.txt` | 177 | 177 | 100.0% | 0 |

**Overall: 99.98% across 6,228 content lines, 1 misclassified.**

## Known errors at baseline

**`pg921-images-3.epub` line 23, `DE PROFUNDIS`.** The work's title is
labelled `body` rather than `front_matter`. De Profundis is a single
continuous letter with no chapter divisions, so the segmenter takes its
documented fallback and treats everything from the start of content as
body. The title line is swept in with it.

This is a limitation rather than a defect: with no structural heading to
anchor on, there is nothing to separate a title from the first line of
prose. A rule guessing that a short standalone opening line is a title
would be plausible and is exactly the kind of speculative detector that
produces false positives elsewhere. It is left unfixed deliberately, to
be decided on evidence during Phase 2 rather than tuned against the
first example encountered.

## How to use this

Every stage added in Phase 2 must be measured against these same keys.
A stage that improves one text while quietly degrading another is a
regression, and only a fixed baseline makes that visible.

When a stage changes what a correct answer looks like, update the keys
and say so here. Do not silently re-baseline: the point of the figure
is that it can be compared across months.
