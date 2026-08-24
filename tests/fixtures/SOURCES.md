# Fixture sources and attribution

Every text in this directory, where it came from, and on what terms it is
included. Test data with unclear provenance is a liability in research
software, and this file exists so that no fixture has to be traced back later.

---

## Real texts

### `pg9405_ballads.txt`

*The Book of Old English Ballads*, compiled by George Wharton Edwards, with an
introduction by Hamilton W. Mabie. First published 1896.

- **Source:** Project Gutenberg eBook #9405, <https://www.gutenberg.org/ebooks/9405>
- **Transcribed by:** John B. Hare and David Widger
- **Release date:** 1 December 2005
- **Status:** Public domain in the United States. The ballads themselves are
  traditional and anonymous; Edwards died in 1950 and the 1896 compilation is
  long out of copyright.
- **Modified:** Yes. The Project Gutenberg header and licence have been
  removed, and the text is truncated after the last complete ballad, *The
  Nut-brown Maid*. Nothing within the retained text has been altered.

**On the removal of the Project Gutenberg header.** Project Gutenberg's licence
offers two clean routes. Either keep the file complete with its full header and
licence attached, or remove every reference to Project Gutenberg, at which
point the underlying public-domain text carries no Project Gutenberg terms at
all. Section 1.C states that for a work unprotected by copyright, PG does "not
claim a right to prevent you from copying, distributing, performing, displaying
or creating derivative works based on the work as long as all references to
Project Gutenberg are removed."

Because this fixture is an excerpt, keeping a partial licence would have been
the worst of both. The second route was taken. Crediting Project Gutenberg
remains permitted and is done here, as PG's permissions page confirms: "No
permission is needed to credit Project Gutenberg as the source of something you
use."

**Why this text is in the repository.** It is the negative control for the page
furniture rules, and it earned its place on the day it arrived. *The Nut-brown
Maid* is a dialogue poem of fixed stanza length in which `HE`, `SHE`, and two
refrains each recur thirteen times at a perfectly constant interval. The
running-head detector marked 63 lines of it as furniture on first contact. See
`design/DECISIONS.md`.

### `pg1232_prince.txt`

*The Prince*, Niccolò Machiavelli, written 1513. English translation by W. K.
Marriott, 1908, with the translator's notes.

- **Source:** Project Gutenberg eBook #1232, <https://www.gutenberg.org/ebooks/1232>
- **Status:** Public domain. Machiavelli died in 1527; Marriott's translation
  was published in 1908 and its US copyright has long expired.
- **Modified:** Yes. Project Gutenberg header and licence removed, on the same
  reasoning as the ballads above. Truncated before Chapter XIII so that every
  retained chapter is complete.

**Why this text is in the repository.** It is the positive control for footnote
detection, and it settled a design question that no synthetic fixture would
have raised. The translator's numbering **restarts in every chapter**, so the
label `[1]` occurs fourteen times: seven markers and seven notes, in seven
different chapters. Pairing markers to notes by label alone would join a marker
in chapter two to a note belonging to chapter nine. Pairing has to be local.

### `CBronte_Jane.txt`

*Jane Eyre: An Autobiography*, Charlotte Brontë, 1847.

- **Source:** Project Gutenberg eBook #1260, <https://www.gutenberg.org/ebooks/1260>
- **Status:** Public domain. Brontë died in 1855.
- **Modified:** Yes. Project Gutenberg header and licence removed; paragraphs
  unwrapped to single lines.

### `romeo_juliet.txt`, `romeo_juliet_notes.txt`

Excerpts from *Romeo and Juliet*, William Shakespeare.

- **Source:** Project Gutenberg eBook #1513, <https://www.gutenberg.org/ebooks/1513>
- **Status:** Public domain.
- **Modified:** Excerpted for use as fixtures. `romeo_juliet_notes.txt` retains
  a transcriber's note block, which is what it exists to test.

**Also the negative control for footnote detection.** The full text carries 69
bracketed items — `[_Exeunt._]`, `[_Exit._]`, `[_They fight._]` — and not one
footnote. A rule that deleted bracketed material would strip the stage
directions, and a corpus of drama without its stage directions is a corpus of a
different work.

### `newwizardoz00densgoog.epub`

*The New Wizard of Oz*, L. Frank Baum, 1903. Scanned by Google from the
Stanford University Libraries copy, converted to EPUB by the Internet Archive.

- **Source:** Internet Archive, identifier `newwizardoz00densgoog`
- **Status:** Public domain. Baum died in 1919; the volume was published in 1903
  and its Google/Archive scan adds no copyright, as neither claims one over a
  public-domain work.
- **Modified:** No. The file is exactly as downloaded, 45 MB including page
  images.

**The first genuinely scanned book this tool has ever been given**, and the one
that ended a blocker open since Week 2. Every previous fixture was either a
Gutenberg transcription, from which volunteers remove page furniture by policy,
or something I generated.

It contains, in one file: the Internet Archive's EPUB notice, Google's full
scanning notice and usage guidelines, a Stanford library catalogue stamp, 28
pages the scanner itself reports as unreadable — median **5.1% accurate** — and
a book whose text is one page per line with the headings buried inside them.

### `mary-shelley_frankenstein.epub`

*Frankenstein; or, The Modern Prometheus*, Mary Shelley, 1818.

- **Status:** Public domain. Shelley died in 1851.
- **Modified:** No.

**The negative control for the prefix rule, and it matters.** This file is
page-per-line like the Oz scan — median line 396 characters — so the
running-head prefix rule *runs* on it. It has no running heads, and the rule
correctly makes **zero** edits. Without a file of this shape carrying no
furniture, that guard would be asserted rather than tested.

It also segments correctly without help: 24 chapters, found because its
headings sit on their own lines as `Chapter` / `I`.

### `pg921-images-3.epub`

- **Source:** Project Gutenberg eBook #921, <https://www.gutenberg.org/ebooks/921>
- **Status:** Public domain.
- **Modified:** No. Retained complete and unaltered, including its Project
  Gutenberg header and full licence, which is what makes it the fixture for
  real Gutenberg apparatus detection. Redistributed under the terms of the
  licence it carries.

---

## Synthetic texts

Written for this project. No copyright question arises, but a different caution
does: **synthetic data cannot validate a detector, only develop it against.**
A generator encodes its author's assumptions, and a rule tuned against one
learns those assumptions rather than reality.

That is not a theoretical worry. The running-head detector scored 100% on
`scanned_novel.txt` and then failed on the first real text it met, because the
generator had been written on the assumption that refrains recur irregularly.
In fixed-stanza verse they do not.

| File | Generated by | Tests |
|---|---|---|
| `scanned_novel.txt` | `tools/make_furniture_fixture.py` (seed 1847) | Running heads and page numbers |
| `early_modern.txt` | `tools/make_catchword_fixture.py` (seed 1603) | Catchwords |
| `hyphenated.txt` | `tools/make_hyphen_fixture.py` (seed 1847) | De-hyphenation |
| `mixed_verse.txt` | `tools/make_mixed_fixture.py` (seed 1847) | Protected spans |
| `scan_apparatus.txt` | Hand-written from a real scan | Digitisation notices |
| `pg_marked.txt` | Hand-written | Gutenberg marker detection |
| `drama_with_contents.txt` | Hand-written | Contents-list detection |
| `book_chapter_nesting.txt` | Hand-written | Region hierarchy |
| `sample.docx`, `sample.epub`, `sample.html` | `tools/` | Format import |

`hyphenated.txt` is a different kind of fixture and a better one: **synthetic
damage applied to real prose.** It is `CBronte_Jane.txt` hard-wrapped to 64
columns with words broken across the line breaks. The vocabulary, spelling and
compound habits are Brontë's, and only the breaks are invented. That matters
because the de-hyphenation rule draws its evidence from the document's own
vocabulary, so it has to be tested against a real one.

`mixed_verse.txt` is the same kind of fixture and for the same reason: real
*Jane Eyre* prose hard-wrapped to 66 columns with real ballad stanzas embedded
in it. A fixture of pure verse and one of pure prose would both be passed by a
detector that guessed the same answer for every line. **The boundary is the only
difficult part**, so this fixture is nothing but boundaries.

All generators are deterministic and seeded, so a fixture and its answer key
can never drift apart. Regenerate with the command in each script's docstring.

---

## Still needed

**Real footnote data exists and is used**, unlike page furniture. Gutenberg
keeps footnotes, because a footnote is content; its practice is to relocate
them rather than remove them. `pg1232_prince.txt` supplies real marker-and-note
pairs and `romeo_juliet.txt` supplies the bracketed material that must not be
mistaken for them.

**Real page-imaged text.** No fixture here contains genuine running heads,
because Project Gutenberg's volunteers remove page furniture during
transcription. This was confirmed three ways: the Distributed Proofreaders
documentation states that page markers are removed from the plain-text flow;
PG eBook #55002, whose transcriber's note discusses pagination, contains no
bare page-number lines; and its HTML edition carries page anchors with no
visible text.

So Project Gutenberg can supply excellent negative controls, and cannot supply
a positive one. Real OCR or PDF-derived text, or an EEBO or ECCO transcription
for catchwords, is still required before the measured figures mean anything
outside this repository.
