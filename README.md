# CorpusPrep

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22083932.svg)](https://doi.org/10.5281/zenodo.22083932)

**Corpus preparation for linguists.** Prepare a source text for analysis, and
retain a record of every editorial decision taken.

AntConc and WordSmith Tools are analysis software: they assume you already have
a clean corpus. Almost nobody does. Texts arrive as Project Gutenberg files,
Word documents, PDF extractions, OCR output and web scrapes, and every
researcher rebuilds the same fragile cleaning scripts.

CorpusPrep occupies the stage before analysis. Its claim is not that it cleans
text, since a regular expression does that. It is that **every transformation
is visible, reversible and documented**, so that a reviewer can ask what you
removed and you can hand them a file.

---

## Try it

Open **[the web application](https://adesokantosin2000-beep.github.io/corpusprep/)** in
a browser. Nothing to install. Your text is processed locally and never
transmitted anywhere.

Or use the Python package, which requires no dependencies beyond the standard
library:

```bash
python -m corpusprep inspect  mytext.txt          # show how it segments
python -m corpusprep clean    mytext.txt --out cleaned
python -m corpusprep list-variants
```

---

## What it does

Every line of a document is **labelled before anything is removed**. You then
decide what constitutes your corpus, and the log records how that decision was
made.

| Region | Contains |
|---|---|
| `pg_header` | Project Gutenberg header block |
| `pg_licence` | Licence text and transcriber credits, marked or unmarked |
| `front_matter` | Title, byline, preface, contents, dramatis personae |
| `body` | The work itself, segmented by chapter, act or section |
| `back_matter` | Appendix, index, notes, colophon |
| `unknown` | Nothing matched. **Retained by default.** |

Two design rules follow from this:

**Detection never deletes.** The segmenter only labels. Removal is a separate
step driven by explicit selection, so a false positive cannot silently destroy
prose.

**Every line is accounted for.** After segmentation each content line belongs
to exactly one region, verified on every run and reported in every log. Text
can leave the corpus only because you chose to remove it.

### Currently implemented

- Front matter and back matter detection
- Chapter, book, part, act, scene, numbered section and bare numeral sequences
- Hierarchy: acts contain scenes, books contain chapters
- Table-of-contents detection, so the body does not begin inside the contents
- Gutenberg headers, licence text and transcriber notes
- TXT, Markdown, DOCX, EPUB, HTML and PDF import with encoding detection
- Markdown link targets discarded and link text kept, because a URL is not
  language: a tester's corpus was 45% URL before this existed
- Page boundaries read from a PDF rather than inferred, which turns the most
  fragile rule in the package into a fact
- Five cleaning presets, or per-section selection
- Running head, running foot and page number detection, off by default
- Catchword detection for early modern printing
- Footnote detection, with three routes: keep, remove, or extract to a
  parallel file
- De-hyphenation of words broken across a line break, with undecidable cases
  flagged rather than guessed
- A review queue: a hand-editable file, and a keyboard-driven reviewer in the
  web application, for every case the rules decline to decide
- Protected spans: verse, drama and tabular material identified before any
  reflow, so their line breaks are never treated as typesetting
- Digitisation apparatus: Internet Archive and Google Books notices, and pages
  the scanner itself reports as unreadable
- Preprocessing log in Markdown and JSON

Page furniture is detected but never removed unless asked, and the reason is
worth stating rather than assuming. It has now met two genuine library scans —
*Treasure Island* and *The New Wizard of Oz*, both Internet Archive — and works
on them. **Two books is not a sample.** No precision or recall figure is quoted
for these rules, because two texts cannot support one. What was found and why
is printed for review before anything is removed.

Those scans also settled a question a synthetic fixture could not have raised.
In a page-imaged file a line is a whole *page*, so the running head is not a
line at all but the first few words of one — and so, often, is the chapter
heading. Three separate rules had assumed one line, one thing.

Footnotes are the one rule here built and measured entirely against real books,
because Gutenberg keeps footnotes where it strips page furniture. A marker
counts as a footnote only when a note elsewhere carries the same label, so
stage directions and other bracketed material are never touched. Anything that
cannot be paired is reported and left alone by every route.

### The review queue

Every rule here refuses to guess, which is only useful if the refusals have
somewhere to go. `prepare()` writes `<name>__review.tsv` beside the output: one
tab-separated line per undecided case, hand-editable, re-importable.

```
# DECISION   TYPE     ITEM           WHY
?            hyphen   def-inite      neither form occurs elsewhere in this text
join         hyphen   sug-gest
keep         hyphen   half-broken
```

**Items are keyed by content, never by line number.** Remove a Gutenberg header
and every line below shifts, so a decision keyed on position would reattach to
the wrong word. Keying on `def-inite` survives that, and lets one decision serve
every volume of an edition.

An untouched queue changes nothing, so it is safe to generate and experiment
with. Answered, it takes de-hyphenation from 84 of 180 cases to all 180.

In the web application the same queue is keyboard-driven: `J` join, `K` keep,
`S` skip, `Esc` finish.

De-hyphenation settles almost everything without asking. Beyond checking
whether the finished word occurs elsewhere, it reads the fragments: **a compound
is built out of words and a broken word is not.** `drawing-room` is `drawing`
plus `room`; `def-inite` is `def` plus `inite`, and `inite` is not a word. A
whole book is resolved completely with no questions at all; a short extract asks
about three.

**No wordlist is bundled, deliberately.** De-hyphenation takes its evidence from
the document's own vocabulary: if `example` occurs elsewhere in this text, the
joined form is attested in this text's own spelling. A 234,000-word list of
modern English recognises only 65% of the word types in *Jane Eyre*, rejecting
`adapted` and `adding` alongside `againe` and `accurst`, so requiring dictionary
confirmation would refuse a third of the legitimate joins and fail worst on
historical material. The rule is never wrong on the cases it decides, and flags
the rest.

### Paragraph reflow: measured, and offered rather than recommended

Reflow rejoins paragraphs a typesetter broke into fixed-width lines. It is the
one stage the original assessment said could not be solved completely, and it
is off by default in every variant.

Measured by wrapping *Jane Eyre* and reflowing it, so ground truth needs no
judgement: **99.5% of paragraphs recovered exactly**, from 96.2% before
hardening. Every known limitation is enumerated in
[`design/reflow-failures.md`](design/reflow-failures.md).

The two faults that mattered were found by checking premises rather than tuning
thresholds. One rule split paragraphs at quotation marks, on the reasoning that
typesetters run two speeches together — but 585 of *Jane Eyre*'s paragraphs
contain two or more speeches, each printed as one, so the rule was deleted. The
other was that wrapping breaks on hyphens, so rejoining `white-` and `washed`
with a space produced `white- washed`, damaging every one of the 46 hyphenated
line-ends in the fixture.

No two paragraphs are ever merged. Every error is in the direction of splitting
too much, which is the safer one: a wrongly split paragraph is visible in the
output, whereas a merged boundary is lost.

**Stage order is enforced in code.** De-hyphenation runs before reflow, because
it repairs words broken across a line break and reflow removes exactly those
breaks. Run the other way round, de-hyphenation sees 0 of 180 breaks instead of
180.

### Not yet implemented

Repair of OCR characters, as opposed to identifying and reporting the damaged
pages, which is done; and structure for collections whose parts are titled but
neither numbered nor introduced by a division word.

**PDF is the one feature that needs the network**, and only in the browser:
`pdf.js` is fetched once, on demand, the first time a PDF is opened. Every
other format still runs from a single file with no connection, and the document
itself is never uploaded. The Python package reads PDFs with no network at all. These are specified in
[`design/design-spec.md`](design/design-spec.md) and scheduled in
[`design/schedule-phase2.md`](design/schedule-phase2.md). They are listed in
the application under *What this version can and cannot do*, marked as planned,
so that current limitations are available rather than discovered mid-project.
That list is collapsed by default: stating the limits is a commitment worth
keeping, and four paragraphs of it on the opening screen is not.

---

## Repository layout

```
src/corpusprep/     Python package. Standard library only.
build/              Sources for the web application.
docs/index.html     The built application. Also what GitHub Pages serves.
tests/              Test suite and fixtures.
tools/              Parity check, stress test, copy audit.
design/             Specification, schedules, operational notes.
```

### Building the web application

`docs/index.html` is generated. **Edit the sources in `build/`, not the page**,
since a hand edit to it is silently lost on the next build.

```bash
python build/build.py            # rebuild docs/index.html
python build/build.py --check    # verify the page matches its sources
```

The application is one self-contained file so it can be opened by double-click
and served from anywhere, which makes it awkward to edit at 83 KB. It is
therefore authored in three parts and concatenated: `_shell.html` for markup
and styling, `_engine.js` for the segmentation engine, `_app.js` for interface
behaviour.

The split is not only convenience. `_engine.js` is the half that must agree
with the Python package, and giving it its own file makes that boundary
visible.

### Two implementations, kept in step

The engine exists twice: in Python for scripting and batch work, and in
JavaScript so the web application loads instantly and works offline. That is a
real risk of divergence, so `tools/check_parity.py` runs the same files through
both and compares every figure.

It has already earned its place. It caught a nine-token drift on a real text
caused by JavaScript's `\w` being ASCII-only while Python's is Unicode-aware,
which was quietly splitting words such as *æsthetic* and *naïve*.

**Run it after changing either implementation.**

### Testing the interface

`tools/ui_test.js` loads `docs/index.html` into a real DOM and drives it:
fixtures are loaded, panels are checked for, and the review queue is answered by
keyboard.

It exists because the unit tests and the parity check never open the page. That
gap let through a real bug: the version constant was emitted before
`<!DOCTYPE html>`, outside the script tag, where the browser rendered it as text
and every reference to it threw. The unit test asked whether the string was
present in the file and never asked where.

**A test that asks "is it in the file?" is not a test that asks "does it run?"**

```bash
npm install jsdom
node tools/ui_test.js
```

---

## Tests

```bash
python tests/test_corpusprep.py     # 441 checks, no pytest required
python tools/check_parity.py        # Python and JavaScript must agree
python tools/measure.py             # accuracy against hand-marked keys
python tools/integration.py         # the whole pipeline over every real book
python tools/stress_test.py corpora # traffic-light report over a folder
node   tools/ui_test.js            # drives the built page in a real DOM
```

### Measured accuracy

`tools/measure.py` scores the segmenter against hand-marked answer keys in
`tests/keys/`, per content line rather than per region, because a boundary
placed ten lines wrong silently moves ten lines of prose into or out of the
corpus.

Current figure: **99.99% across 7,654 content lines, 1 misclassified.** The
single error and why it is left unfixed are recorded in
[`tests/keys/BASELINE.md`](tests/keys/BASELINE.md).

Structural segmentation is measured separately and against whole books rather
than answer keys, since a book's chapter count is a fact about the book:

| Text | Divisions found |
|---|---|
| *Jane Eyre*, *Emma*, *King Solomon's Mines* | **38/38, 55/55, 20/20** |
| *Frankenstein*, *The Prince* | **28/28, 12/12** |
| *Treasure Island* (Internet Archive scan) | 33 / 34 |
| *The New Wizard of Oz* (Internet Archive scan) | 18 / 24 |

Run it with `python tools/integration.py`. Every failure it found, including
the ones still unfixed, is in
[`design/integration-failures.md`](design/integration-failures.md).

Precision and recall for each individual rule are in
[`design/measurement.md`](design/measurement.md), reproducible with
`python tools/measure_rules.py`. That table records **what kind of evidence
each figure rests on**, because it matters more than the figure: four of the
rules are scored against fixtures generated with known answers, which is enough
to develop against and not enough to publish. Two rules have no figure at all
and the table says so rather than leaving a blank.

The keys are read from the sources, never copied from the tool's output. A key
derived from what the tool already produces measures only consistency with
itself.

The first four tests are regressions against confirmed bugs in the original
prototype script, kept so the rewrite cannot reintroduce them:

| | Bug | Test |
|---|---|---|
| B1 | Paragraphs beginning `Note:` or `Produced` were swallowed whole | `test_b1_note_paragraph_survives` |
| B2 | Emphatic capitals deleted as a running header | `test_b2_allcaps_prose_survives` |
| B3 | Chapter handling was unreachable dead code | `test_b3_chapter_headings_labelled` |
| B4 | Standalone years such as `1847` removed as page numbers | `test_b4_standalone_number_survives` |

Page furniture has its own regression set, since the rules that find it are the
ones most able to destroy prose. Each fixture is built to trap its rule rather
than flatter it: the scanned novel repeats a refrain 64 times, more often than
its 60 furniture lines, and the early modern text ends one page with a full line
of prose whose first word genuinely opens the next page.

That second fixture immediately found a fault in the first rule. The OCR
digit-lookalike table read the word `So` as the page number 50, which would have
deleted it wherever it recurred near a page break.

Then a real text broke it properly. The detector scored 100% on synthetic data
and, on the first genuine book it met, marked 63 lines of a ballad collection as
page furniture: a dialogue poem of fixed stanza length repeats `HE`, `SHE` and
two refrains thirteen times each at a perfectly constant interval. The rule had
been estimating a page length from a text with no pages, then confirming lines
against a yardstick they had set themselves.

Page numbers must now form an ascending sequence, and the page length is derived
only from them. No ascending sequence means no page structure and no detection.
**A fixture only tests the failure modes its author thought of.** Fixture
provenance and licensing are recorded in
[`tests/fixtures/SOURCES.md`](tests/fixtures/SOURCES.md).

---

## Automatic checks and pushing

Git hooks live outside the repository, so install them once per clone:

```bash
python tools/install_hooks.py
```

After that, `git commit` runs the checks and pushes for you:

| Hook | Runs | Time |
|---|---|---|
| `pre-commit` | Test suite, build check. **Blocks the commit if either fails.** | ~2 s |
| `pre-push` | Parity and accuracy. **Blocks the push if the engines have drifted.** | ~5 s |
| `post-commit` | Pushes automatically. A failed push warns but is never fatal. | |

Fast checks run on every commit; slower ones only when work leaves the machine.
Use `--no-verify` to bypass either on a particular commit.

**The hooks do not commit for you, and that is deliberate.** A timed automatic
commit would produce a history of meaningless messages and would happily record
broken states. This history is part of the project's record: it is what the
Zenodo archive preserves and what a reviewer would read. You decide when a
change is worth recording and what to call it. The hooks only remove the step
that gets forgotten, which is the one that leaves work stranded on one machine.

---

## Licence

MIT. See [`LICENSE`](LICENSE).

## Citation

Use the "Cite this repository" button, or [`CITATION.cff`](CITATION.cff)
directly. Cite a **version**, not the repository: the tool's behaviour changes
between releases, and an analysis is only reproducible against the version that
produced it.

> Adesokan, T. (2026). *CorpusPrep: corpus preparation for linguists*
> (version 0.6.0) [Computer software]. Zenodo.
> https://doi.org/10.5281/zenodo.22083932

That DOI resolves to a frozen, archived copy of `v0.6.0` and cannot move. To
refer to the software in general rather than to one version, use the concept
DOI [10.5281/zenodo.22083931](https://doi.org/10.5281/zenodo.22083931), which
always resolves to the latest release — useful in prose, wrong in a methods
section. See [`docs/CITING.md`](docs/CITING.md).

## Support

CorpusPrep is research software maintained by one person alongside other work.
Bug reports are welcome through GitHub issues. Feature requests will be read
but may not be implemented. There is no guaranteed response time.
