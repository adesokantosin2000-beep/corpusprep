# Changelog

## [0.6.0] - 2026-08-24

Integration across eleven real books, and the fault it found.

Measured on the works themselves: Jane Eyre 38/38 divisions, Emma 55/55,
King Solomon's Mines 20/20, The Prince 12/12, Frankenstein 28/28,
Treasure Island 33/34, *The New Wizard of Oz* 18/24.

### Fixed
- **Frankenstein lost the first 5,500 words of the novel.** Walton's four
  letters sat inside a region labelled Preface — 6,184 tokens, where Shelley's
  preface is about 700 — and were dropped from `body-only`. Three faults
  compounded: division headings split across two lines were invisible, the
  numeral tier took the run of 24 chapters and discarded the run of 4 letters
  without recording it, and a front-matter region absorbed everything up to the
  first chapter unchecked
- Chapter headings welded to the front of a page in page-per-line scans were
  discarded. Treasure Island's 24 numbered headings were being ignored in
  favour of weaker evidence
- `is_page_per_line` tested only that lines were long, which is equally true of
  a file stored one paragraph per line. It now requires uniformity as well: a
  page holds a fixed amount of type, a paragraph holds as much as the author
  wrote
- The running-head pattern stopped at a quotation mark, truncating titles such
  as `THE OLD SEA DOG AT THE “ADMIRAL BENBOW.”`
- A tie in the "most frequent spelling" vote for a running-head title was
  broken by Python's set hash order — not reproducible even in Python, and
  different from the JavaScript engine. Both now take the earliest joint winner
- A word token could begin with a combining mark in JavaScript, so variation
  selectors counted as words; Python excluded marks entirely, so a decomposed
  `café` counted as two. Both now require a leading letter and normalise to NFC

### Added
- Chapter recovery from running heads, for scans where OCR destroyed every
  heading. The book title is separated from the chapter titles structurally —
  chapters do not overlap each other and the book title overlaps them all —
  with no threshold and no stop-word list
- Division headings whose word and numeral sit on separate lines
- `tools/integration.py`, the whole pipeline over every real text in one table
- Fixtures: *Treasure Island* and *King Solomon's Mines* and *Emma*,
  and *Frankenstein* as the negative control for the page-per-line rules
- The parity harness now reports *which* region title differs, and covers both
  scans. It had reported agreement for a day while one engine ran a rule the
  other did not, because no fixture exercised it

### Known limits
- *The New Wizard of Oz* recovers 18 of 24 chapters. The remainder have running
  head series too short or too damaged to group, and the file contains no other
  evidence
- Books whose sections are titled but neither numbered nor prefixed by a
  division word produce no structure. The whole text is kept as body and the
  report says so
- Drama places the Prologue in front matter

## [0.5.0] - 2026-08-23

Paragraph reflow, the stage the original assessment said could not be solved
completely. 99.5% of *Jane Eyre*'s paragraphs recovered from a hard-wrapped
copy, with the remainder reported rather than guessed. Stage order enforced in
code: de-hyphenation must precede reflow, because reflow consumes the evidence
de-hyphenation depends on.

## [0.4.0] - 2026-08-23

Footnote detection with three routes (keep, remove, extract), de-hyphenation
taking its evidence from the document's own vocabulary rather than a bundled
wordlist, and the review queue for cases the rules cannot settle.

## [0.3.0] - 2026-08-23

Page furniture: running heads, page numbers and catchwords, detected by
regularity rather than appearance, and never removed without being asked.

## [0.2.0] - 2026-08-23

First release with a graphical interface.

### Added
- Web application: single self-contained HTML file, runs offline, no upload
- Sign-in with session persistence held locally on the user's machine
- Explicit cleaning step. Loading a file segments and displays it; no output
  is produced until requested
- DOCX, EPUB and HTML import, standard library only
- Region hierarchy: acts contain scenes, books contain chapters
- Table-of-contents detection by entry density and repetition
- Transcriber and producer credit detection
- Parity harness comparing the Python and JavaScript implementations

### Fixed
- Heading matching was case-sensitive, so `Chapter 1` failed where `CHAPTER 1`
  worked. This silently affected the majority of real books
- Contents detection used a count ratio that sat exactly on its boundary for
  drama, where the contents mirrors the body one for one. Replaced with entry
  density
- Transcriber note patterns matched only the straight apostrophe, while
  Gutenberg uses the typographic form almost universally
- JavaScript tokeniser split non-ASCII words because `\w` is ASCII-only there.
  Found by the parity check as a nine-token drift on De Profundis
- The tail of a region split by an interruption inherited the original's title

## [0.1.0] - 2026-07-29

Initial prototype: segmentation engine, variant outputs, preprocessing log,
command-line interface.
