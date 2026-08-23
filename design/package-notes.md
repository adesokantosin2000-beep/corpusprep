# CorpusPrep v0.1.0 — working prototype

Corpus preparation for linguists. Segment a text, choose what to keep, produce
several cleaned versions, and get a log that documents every decision.

**No installation.** Pure standard library, Python 3.9+. Nothing to `pip install`.

---

## Try it

From the folder containing `corpusprep/`:

```bash
# See how a file segments. Changes nothing.
python -m corpusprep inspect CBronte_Jane.txt

# Every chapter listed rather than collapsed
python -m corpusprep inspect CBronte_Jane.txt --all

# Produce the four default variants plus the log
python -m corpusprep clean CBronte_Jane.txt --out cleaned

# Custom selection
python -m corpusprep clean CBronte_Jane.txt --out cleaned \
    --keep body,front_matter --name preface-plus-novel

# What variants exist?
python -m corpusprep list-variants
```

From Python:

```python
from corpusprep import prepare
doc, results = prepare("CBronte_Jane.txt", out_dir="cleaned")

for r in results:
    print(r.variant.name, r.stats["word_tokens"])
```

---

## The six capabilities

| Capability | Where | Notes |
|---|---|---|
| Import a Gutenberg text | `importer.py`, `formats.py` | `.txt`, `.docx`, `.epub`, `.html`. BOM, CRLF/CR/LF, UTF-8 → CP1252 → Latin-1 fallback, confidence score |
| Detect front matter | `segment.py` | Title page, preface, dedication, contents, notes — sub-segmented by heading |
| Detect licence text | `segment.py` | Sentinel markers *and* keyword-density detection for files whose markers were stripped |
| Retain or remove sections | `variants.py` | Per-region keep/drop; six labels; nothing is deleted at detection time |
| Generate cleaned versions | `variants.py` | Four built-ins plus arbitrary custom selections, all from one pass |
| Preprocessing log | `report.py` | Markdown for humans, JSON for machines |

## Region labels

```
pg_header     Project Gutenberg header block
pg_licence    PG licence text (header, footer, or unmarked block)
front_matter  Title, author, preface, dedication, contents
body          The work itself, sub-segmented by chapter
back_matter   Appendix, index, notes, colophon
unknown       Nothing matched — retained by default, never silently dropped
```

## Built-in variants

| Name | Keeps |
|---|---|
| `verbatim` | Everything. The control — measure the others against it. |
| `full` | Everything except PG apparatus |
| `body-and-front` | Front matter + body |
| `body-only` | The work alone. Usual choice for stylistic analysis. |
| `body-no-headings` | Body with `CHAPTER` lines stripped too. For word lists. |

---

## Two design rules that matter

**1. Detection never deletes.** The segmenter only *labels*. Removal happens
later, from an explicit selection. This is why the tool cannot repeat the
original script's worst failure, where a detection rule silently swallowed
prose as a side effect.

**2. Every line is accounted for.** After segmentation, each content line
belongs to exactly one region, verified by `Document.coverage_gaps()` and
reported in every log. Anything unclassified becomes `unknown`, which defaults
to *keep*. Text can only leave the corpus because you chose to remove it.

---

## Supported file formats

| Format | Status | How |
|---|---|---|
| `.txt` `.md` | ✅ | Direct decode with encoding detection |
| `.docx` | ✅ | stdlib `zipfile` + `xml.etree`; paragraph styles used to find headings |
| `.epub` | ✅ | Spine reading order followed via the OPF |
| `.html` `.htm` `.xhtml` | ✅ | stdlib `html.parser`; script/style dropped, entities decoded |
| `.pdf` | ❌ deferred | See below |
| `.doc` (Word 97-2003) | ❌ | Binary format. Re-save as `.docx`. |

**Why PDF is deliberately absent.** PDF text extraction produces hyphenated
line-breaks, hard-wrapped lines, running headers on every page and stray page
numbers — precisely the problems CorpusPrep cannot repair yet. Supporting
import before supporting repair would let people build bad corpora while
trusting the output, which is worse than declining. Add it once
de-hyphenation and reflow exist (spec §4, Group 4).

## Tests

```bash
python tests/test_corpusprep.py
```

58 checks, no pytest required. The first four are regression tests for
confirmed bugs in the original `clean_jane_eyre.py`:

| | Bug | Test |
|---|---|---|
| B1 | Paragraphs starting `Note:` / `Produced` were swallowed whole | `test_b1_note_paragraph_survives` |
| B2 | All-caps prose deleted as a running header | `test_b2_allcaps_prose_survives` |
| B3 | Chapter-handling branch was unreachable dead code | `test_b3_chapter_headings_labelled` |
| B4 | Standalone years (`1847`) removed as page numbers | `test_b4_standalone_number_survives` |

---

## Verified on Jane Eyre

```
Source        1,022,238 chars · 4,083 lines · 188,215 tokens · 12,750 types
Detected      utf-8-sig with BOM, CRLF endings
Segmented     3 front-matter regions + 38 chapters, zero uncovered lines
body-only     187,296 tokens (-0.5%) — preface and byline removed, prose intact
```

The −0.5% is the honesty check working: a real character reduction with
almost no token loss means apparatus came out, not prose.

---

## Not yet built

De-hyphenation, paragraph reflow, running-head detection, page-number removal,
OCR repair, verse protection, batch mode, GUI. See `CorpusPrep_Design_Spec.md`
for the full plan and `CorpusPrep_Evening_Schedule.md` for the build order.

## Heading detection

Three tiers, tried in order. Only the first tier that yields results is used,
so a book with real chapter headings is never confused by stray numerals.

| Tier | Recognises | Example |
|---|---|---|
| 1. Division headings | `CHAPTER BOOK PART VOLUME CANTO SECTION LETTER ACT SCENE STAVE EPISODE FYTTE MOVEMENT INTERLUDE LECTURE SERMON TALE NIGHT` + roman numeral, digit, or spelled-out number — **case-insensitive** | `Chapter One`, `ACT II`, `Book the Third`, `Chapter 3: A Meeting` |
| 2. Numbered sections | `1. Introduction`, `2.1 Method` — needs 2+, starting at 1 | Academic papers, reports |
| 3. Bare numerals | A lone `1` / `I` on a line, **only in an ascending run from 1, 3+ long** | Novels with unlabelled chapters |

Separately, a `Key: value` block near the top is labelled `front_matter /
metadata` — this catches transcripts, article extracts and scraped pages,
and is detected even when the text has no chapter structure at all.

## Hierarchy

Acts contain scenes; books and volumes contain chapters:

```
body  chapter  ACT I                      +29w in 2 parts
body  chapter    SCENE I. A public place.  14w
body  chapter    SCENE II. A Street.       13w
```

Levels come from the division word's rank, but **only the ranks actually
present are used**, renumbered from 1. So `ACT`/`SCENE` and `BOOK`/`CHAPTER`
both give two levels, while a novel using only `CHAPTER` stays flat rather
than gaining a fake hierarchy. Numbered sections nest by dot depth
(`2.1` sits under `2.`).

Regions stay **flat and non-overlapping** in storage — that invariant is what
guarantees no line is counted twice or lost. Nesting is metadata (`level`,
`parent`). An Act's own span holds just its heading line, so its real size
comes from `Document.subtree_words()`, which sums its descendants.

## Table of contents

A contents list repeats the headings it lists, and that duplication is the
signal used to detect it — more robust than looking for the word "Contents",
which many editions omit. Without this, body would begin *inside* the contents
and the real front matter after it (dramatis personae, prologue) would be
mislabelled as body.

**The false-positive guard:** text following the enumerator must begin with a
capital. That is what separates `Chapter 1. The Beginning` from
`Section 3 of the act states that…`. Nine prose lines that look heading-ish
are in the test suite specifically to keep this honest.

## Known limits

- Front-matter headings (`PREFACE`, `CONTENTS`) must still be uppercase.
- English-only heading vocabulary.
- Speaker turns in transcripts (`INT:`, `P04:`) are not yet used as structure.
- Whole file is held in memory. Fine to ~100 MB.
