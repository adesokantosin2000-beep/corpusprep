# CorpusPrep

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
- TXT, DOCX, EPUB and HTML import with encoding detection
- Five cleaning presets, or per-section selection
- Preprocessing log in Markdown and JSON

### Not yet implemented

Page numbers, running headers and footers, OCR repair, de-hyphenation,
paragraph reflow, PDF import. These are specified in
[`design/design-spec.md`](design/design-spec.md) and scheduled in
[`design/schedule-phase2.md`](design/schedule-phase2.md). They are listed in
the application interface, marked as planned, so that current limitations are
visible rather than discovered mid-project.

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

---

## Tests

```bash
python tests/test_corpusprep.py     # 125 checks, no pytest required
python tools/check_parity.py        # Python and JavaScript must agree
python tools/stress_test.py corpora # traffic-light report over a folder
```

The first four tests are regressions against confirmed bugs in the original
prototype script, kept so the rewrite cannot reintroduce them:

| | Bug | Test |
|---|---|---|
| B1 | Paragraphs beginning `Note:` or `Produced` were swallowed whole | `test_b1_note_paragraph_survives` |
| B2 | Emphatic capitals deleted as a running header | `test_b2_allcaps_prose_survives` |
| B3 | Chapter handling was unreachable dead code | `test_b3_chapter_headings_labelled` |
| B4 | Standalone years such as `1847` removed as page numbers | `test_b4_standalone_number_survives` |

---

## Licence

MIT. See [`LICENSE`](LICENSE).

## Citation

See [`CITATION.cff`](CITATION.cff), or use the "Cite this repository" button.

## Support

CorpusPrep is research software maintained by one person alongside other work.
Bug reports are welcome through GitHub issues. Feature requests will be read
but may not be implemented. There is no guaranteed response time.
