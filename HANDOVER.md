# Handover — where CorpusPrep is, 28 August 2026

Point a fresh session at this file. It replaces reading the conversation.

## State

`v0.11.0`, with an unreleased body of work on top. 538 tests, parity holds,
region labelling 99.99% over 7,733 lines across five languages.
Zenodo DOI **10.5281/zenodo.22083932** (version), `…931` (concept).

`main` is pushed — local and `origin/main` were at the same commit before this
session's work, which is **uncommitted**. The tags were not verified from here;
`git push --tags` is a no-op if they are already up.

Reads TXT, Markdown, DOCX, EPUB, HTML, PDF. Python package and a single-file
web app that agree on every rule (`tools/check_parity.py`).

## What changed on 28 August

Five faults fixed, three of them silent, and two rules added. Full write-ups in
`design/integration-failures.md` (P1, P3–P6) and `design/DECISIONS.md`.

**P1 — protected spans found 0 of 337 verse lines in a PDF of ten poems.** PDF
extraction renders leading as whitespace, 55% of that file is blank lines, and
every rule here treats a blank line as a boundary, so each verse line was
judged alone. Blank lines are now read as line spacing when they are the norm —
≥40% of the file, ≥80% of text lines standing alone — and removed before the
rule runs. Runs longer than the modal one survive as boundaries; delete every
blank and one seed protects the whole file, prose included.

**P3 — enjambed stanzas under the threshold.** Now judged with the poem around
them: half the threshold plus a firmly protected neighbour. The threshold is
untouched, because 45% is what holds wrapped prose at 3%.

```
protected lines            before    P1 fix    P3 fix
LIT 201 metaphysical poems  0/337   276/337   302/337
Beowulf.pdf              2626/3318 2626/3318 2907/3318
pg9405_ballads.txt       1958/2533 1958/2533 2074/2533
mixed_verse.txt            52/246    52/246    52/246
every prose fixture             0         0         0
```

**P4 — the command line never ran half the rules.** `clean` and `inspect`
called `segment(load())`, not `analyse()`, so page furniture, catchwords,
hyphen breaks and footnotes were never looked for. Every CLI log ever written
understated the file, and `--drop-furniture` removed nothing.

**P5 — every division word was English.** A German, Russian or Czech book
segmented as one undivided body while the log said "no structural headings
found".

**Interface furniture, added.** `Like`, `Reply`, `2 likes` — found by position,
not vocabulary. Detection only; no built-in variant removes them.

**A log that speaks when nothing fires, added.** The empty run now names each
rule and why it declined.

## The open faults

**P6 is a method note, not a fault.** Read it: the interface rule scored 100%
on its own fixture and was wrong anyway, and the test that found it took one
line to write.

**P2 — a 21,581-token "Introduction", and this time it is correct.** Recorded
because it cannot be distinguished from I1 without reading the book. There is
still no check that a front-matter region is front-matter-sized.

**A sonnet's closing couplet** — a two-line block with a 0% break rate — is
still unprotected. Below any floor, and not reachable by this evidence.

## Everything else outstanding

1. **Real non-English text.** The three fixtures are original synthetic prose
   and prove the mechanics, not the rules. A German novel from a real scan is
   the test that matters and is not in this repository. Every *measured*
   figure is still English literary prose
2. **Real social data for the interface rule.** It has met one corpus shape and
   that shape is synthetic: 43% furniture against about 3% in the corpus that
   prompted it
3. A control in the web application to remove interface furniture. It is
   detected and reported there, but only the package can drop it
4. Ask that tester the four questions in task #12 before building more for her
5. Ask testers how many files a corpus is, before building batch
6. ORCID on the Zenodo record
7. Commit and tag. `CHANGELOG.md` has the work under `[Unreleased]`; releases
   0.7.0–0.11.0 were backfilled from the tag history on 28 August and are
   terser than the entries around them
8. Close Phase 2, tag `v1.0-rc`

## Where things are

```
docs/USING.md                    the guide for people preparing a corpus
design/integration-failures.md   every fault found, fixed and unfixed
design/measurement.md            precision/recall per rule, and what each rests on
design/DECISIONS.md              why each rule is the way it is
tools/integration.py             whole pipeline over every real book
tools/pdf_triage.py              which PDFs need OCR before anything else
tools/measure_rules.py           per-rule scores
tools/check_parity.py            the two engines must agree
tools/make_*_fixture*.py         generators that record the key as they write
../pdf-tests/                    copyrighted PDFs, gitignored, never commit
```

`build/_engine.js` contains one literal NUL byte, in the `"\0page-number"`
sentinel around line 918. It works, but it makes `grep` treat the file as
binary and skip it — on the half of the codebase that must be kept in step with
the other half. Write it as `\0` when something else takes you there.

`tools/ui_test.js` cannot run here: `node_modules` holds jsdom's dependencies
but not jsdom itself, and this machine has no network to reinstall it. The
parity check covers the engine; `ui_test.js` covers the interface, and that
half is currently unrun.

## Working rules that have earned their place

- **Detection never deletes.** Rules label; removal is a separate explicit step
- **Log failures the day you find them, fix them the next day.** Fixing on the
  day means fixing the easy ones and losing the list
- **A fixture only tests the failure modes its author thought of.** Furniture
  scored 100% synthetic then destroyed 63 lines of real ballads; protected
  spans scored 100% and found 0 of 337 real verse lines; interface furniture
  scored 100% and could not tell a one-word comment from a control
- **The strongest test is an invariant, not a fixture.** "The same text set two
  ways must be judged the same way" cannot be satisfied by protecting more or
  by protecting less, and does not need maintaining as the rule changes
- **Fix the input the rule is given, not the rule.** P1 was repaired without
  touching the two-signal test or the threshold
- **Position beats vocabulary.** Twice now: a running head is found by its
  interval, not its appearance; a control by where it sits, not what it says
- **Parity compares engines, not front ends.** P4 lived in the gap
- **Suspect the key before the threshold.** Five times a rule has been right
  and had its groups split by OCR damage
- **Check the premise before hunting better evidence**
- **A comment cannot fail.** Assert things instead
- Copyrighted test files stay out of the repository; findings go in

## Ten PDFs tested

5 usable, 1 with a text layer containing no language (7,205 "words", 0%
letters), 3 with no text layer, 1 empty download. **Half of real PDFs cannot
be extracted at all**, which is why triage is arguably the product.
