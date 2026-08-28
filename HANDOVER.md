# Handover — where CorpusPrep is, 27 August 2026

Point a fresh session at this file. It replaces reading the conversation.

## State

`v0.11.0`. 474 tests, parity holds, region labelling 99.99% over 7,654 lines.
Zenodo DOI **10.5281/zenodo.22083932** (version), `…931` (concept).

**Commits are unpushed.** Run `git push && git push --tags` first.

Reads TXT, Markdown, DOCX, EPUB, HTML, PDF. Python package and a single-file
web app that agree on every rule (`tools/check_parity.py`).

## The one open fault, and it is serious

**P1 in `design/integration-failures.md`.** Protected spans found **0 of 337**
verse lines in a PDF of ten metaphysical poems. The rule is right about the
text and never sees it: PDF extraction double-spaces the file (55% blank
lines) and `protect.find()` stops its window at a blank line, so every verse
line is judged alone. `break_profile` agrees it is verse — 69% against a 45%
threshold.

Turn on reflow and every line break in ten poems is destroyed, which is the
exact damage the rule exists to prevent. Beowulf, at 5% blank lines, loses 21%
to the same cause.

Likely fix: a blank line is a structural boundary **only when blank lines are
not the norm**. At high, uniform density they are line spacing, not structure.
Not attempted.

## Everything else outstanding

Task list, roughly in order:

1. **Fix P1** (above)
2. **User documentation** — the largest gap before 1.0. The README is for
   developers; nothing tells a linguist what `body-only` means
3. **Non-English validation** — every measured number is English literary
   prose. One German, one Cyrillic, one diacritics-heavy text would close it
4. Say something useful when no rules apply (a tester cleaned Instagram
   comments, got 0 tokens removed and only "no structural headings found")
5. Interface furniture rule — `Like`, `Reply`, `N likes` recur like running
   heads; ~3% of that tester's corpus after URLs were removed
6. Ask that tester the four questions in task #12 before building for her
7. Ask testers how many files a corpus is, before building batch
8. ORCID on the Zenodo record; strip the stale dates from
   `design/schedule-phase2.md`
9. Close Phase 2, tag `v1.0-rc`

## Where things are

```
design/integration-failures.md   every fault found, fixed and unfixed
design/measurement.md            precision/recall per rule, and what each rests on
design/DECISIONS.md              why each rule is the way it is
tools/integration.py             whole pipeline over every real book
tools/pdf_triage.py              which PDFs need OCR before anything else
tools/measure_rules.py           per-rule scores
tools/check_parity.py            the two engines must agree
../pdf-tests/                    copyrighted PDFs, gitignored, never commit
```

## Working rules that have earned their place

- **Detection never deletes.** Rules label; removal is a separate explicit step
- **Log failures the day you find them, fix them the next day.** Fixing on the
  day means fixing the easy ones and losing the list
- **A fixture only tests the failure modes its author thought of.** Furniture
  scored 100% synthetic then destroyed 63 lines of real ballads; protected
  spans score 100% and found 0 of 337 real verse lines
- **Suspect the key before the threshold.** Five times a rule has been right
  and had its groups split by OCR damage
- **Check the premise before hunting better evidence**
- **A comment cannot fail.** Assert things instead
- Copyrighted test files stay out of the repository; findings go in

## Ten PDFs tested

5 usable, 1 with a text layer containing no language (7,205 "words", 0%
letters), 3 with no text layer, 1 empty download. **Half of real PDFs cannot
be extracted at all**, which is why triage is arguably the product.
