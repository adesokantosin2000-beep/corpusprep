# Changelog

## [Unreleased]

Six faults, four of them silent, two rules the tool did not have, and a
stabilisation pass over the parts that could not report on themselves.

### Fixed
- **Protected spans found 0 of 337 verse lines in a PDF of ten poems** (P1).
  Extraction puts a blank line between every line of the file; every verse line
  was judged alone, and one line is never enough evidence. Blank lines are now
  read as line spacing rather than structure when they are the norm — at least
  40% of the file, with at least 80% of text lines standing alone — and removed
  before the rule runs. Runs longer than the modal one survive as boundaries,
  or a single seed would extend across the whole file and protect the prose
  with the verse
- **Enjambed verse sitting under the threshold** (P3). A stanza rhyming *abab*
  with the odd lines unpunctuated carries only half its breaks and scores
  38–40% against a 45% threshold. It is now judged with the poem around it: a
  block clearing half the threshold is protected when a firmly protected block
  sits beside it, and the threshold is untouched. The first attempt vouched
  from lone per-line judgements and protected three paragraphs of *Jane Eyre*;
  a voucher must be most of a block, and the pass is never iterated
- **The command line never ran half the rules** (P4). `clean` and `inspect`
  used `segment(load())`, so page furniture, catchwords, hyphen breaks and
  footnotes were never looked for. The log omitted them, which reads as "none
  found", and `--drop-furniture` removed nothing because nothing had been
  marked. The web application always ran the full pass, so the two front ends
  disagreed about the same file. `check_parity.py` could not see it: it
  compares engines, and both engines were right
- **The interface test could not run, and had been wrong for four days** (P7).
  `node_modules/jsdom` was committed with 161 of its 657 files, no
  `package.json`, and `Document.js` truncated at 16,384 bytes, so
  `tools/ui_test.js` exited with "jsdom not installed" and half the test
  surface reported nothing. Completing the vendored copy at the same version
  turned it on, and it immediately failed: it asserted that PDF reading was
  still *planned*, four days after PDF reading shipped. The capability list was
  right and the test was stale — in the opposite direction to the staleness it
  was written to prevent
- **A reload put the sign-in gate back up** (P8). Reported as "it logs the
  users out"; it never did. The startup block filled the sign-in fields from
  local storage and stopped, so `USER` stayed null and the gate reappeared with
  the name already typed. The cost was not the second click: a reader who then
  took the "Continue without signing in" door wrote every subsequent log
  without its **Prepared by** line, which is the line that makes the log
  citable. The session is now restored, with a **Sign out** control so the gate
  stays reachable on a shared machine
- **The recent-files list was three dead buttons** (P9). Each entry carried
  the tooltip "Reopen this file from disk to load it again" and no click
  handler anywhere in the file, and no entry could be removed. A browser cannot
  reopen a file by name — nothing was ever held but the name and a token count
  — so the button now opens the file picker and the tooltip says so. Each entry
  also gets a remove control: a filename can itself be sensitive, and a reader
  on a shared machine needs to be able to take it off the screen
- **"I loaded a PDF and it's hanging"** (P10). Two faults under one word.
  Reading a file happened in silence, so a slow read and a dead one looked
  identical; the page now names the file, its size, and why a PDF takes
  longer. And the pdf.js download had no deadline — `onerror` fires when a
  request fails, not when it stalls, so a captive portal or a black-holing
  proxy left a promise that never settled and a page that waited for ever.
  `PDFJS_TIMEOUT_MS` is twenty seconds, and the message names the likely cause.
  **It was never the size of the book:** the engine is linear, and 16 MB — six
  teen novels in one file — segments in 3.4 seconds
- **Every division word was English** (P5). `Kapitel`, `Глава` and `Kapitola`
  were not words the heading tier knew, so a German, Russian or Czech book
  segmented as one undivided body while the log said "no structural headings
  found" — a sentence that reads as a fact about the book

```
protected lines            before    P1 fix    P3 fix
LIT 201 metaphysical poems  0/337   276/337   302/337
Beowulf.pdf              2626/3318 2626/3318 2907/3318
pg9405_ballads.txt       1958/2533 1958/2533 2074/2533
mixed_verse.txt            52/246    52/246    52/246
every prose fixture             0         0         0
```

### Added
- **Interface furniture**: `Like`, `Reply`, `2 likes`, `View replies (4)` —
  the labels an application printed around text a person wrote. Found by
  position rather than vocabulary, because every one of those words is ordinary
  English: a control sits in the tail of its record, a one-word comment sits at
  the head. Detected only when the file itself looks like a scraped feed, and
  removed only by a variant setting `drop_interface`, which no built-in variant
  does
- **A log that speaks when nothing fires.** A run that removes nothing now
  names each rule, what it looked for and why it declined, and says that these
  rules are built for printed books — instead of reporting a zero
- **An optional registration link**, on the sign-in card and under the
  capability list. `REGISTER_URL` in `build/_app.js`, empty by default: with
  nothing set, nothing renders, so a fork does not point its users at somebody
  else's form. It is a link and stays one — the page transmits nothing, the URL
  is never prefilled with what the reader typed, and `tools/ui_test.js` asserts
  both, along with the absence of any `fetch`, `XMLHttpRequest`, `sendBeacon`
  or submitting form anywhere in the page
- **`docs/USING.md`**, for people preparing a corpus rather than maintaining
  the tool: what each variant means, which file to keep, how to read the log,
  what the tool will not do, and where it is weakest
- Fixtures in German, Russian and Czech with region keys; measurement now
  covers 7,733 content lines at 99.99%
- `tools/make_interface_fixture.py`, `tools/make_multilingual_fixtures.py`
- `tests/fixtures/double_spaced_verse.txt` and its key: Donne between
  hard-wrapped *Jane Eyre*, set one line to a blank throughout
- `test_double_spacing_does_not_change_the_answer`, which doubles
  `mixed_verse.txt` and requires the same verdict on every line — an invariant
  that cannot be satisfied by protecting more, or by protecting less
- Parity compares interface furniture as well; `measure_rules.py` scores
  protected spans over both verse fixtures, so the headline 100% is answerable
  for the shape that broke it

### Changed
- The capability list now names the division words of other languages, the
  interface-furniture rule, and what the empty-run log says. Page furniture and
  catchwords now state that their measured figures come from generated
  fixtures rather than hand-marked real ones — **a wording change, not a
  behaviour change**: neither rule is altered, and neither was ever removed by
  a preset
- `docs/USING.md` labels every rule *Supported*, *Experimental* or *Future
  work* by the evidence behind it, and says what each figure rests on

### Removed
- **The recent-files list is switched off** (`RECENT_LIST` in
  `build/_app.js`). It could not reopen a file — a browser cannot read one
  again without the reader choosing it — and it was the only place in the tool
  that kept anything about the reader's corpus, where a filename can be an
  informant's pseudonym. Hidden rather than deleted, with the code and its
  tests intact behind one flag, and names already stored on a reader's machine
  are purged rather than merely hidden

### Known
- The interface rule has met one corpus shape, and that shape is synthetic:
  43% furniture, against about 3% in the corpus that prompted it
- Chapter headings outside English work through a wordlist, which is only as
  wide as whoever wrote it
- A sonnet's closing couplet, set off as a two-line block with a 0% break rate,
  is still unprotected. Below any floor; not reachable by this evidence
- The web application detects interface furniture and reports it, but does not
  yet offer a control to remove it
- `node_modules` is committed to the repository, which is what lets the
  development machine work offline, and is not listed in `.gitignore`.
  Completing jsdom adds 496 files to the next commit. Whether to keep vendoring
  it is a decision, not a defect

## [0.11.0] - 2026-08-27

- Read PDFs in the browser, and say what that costs

## [0.10.0] - 2026-08-27

- Read Markdown, because a tester's corpus was 45% URL

## [0.9.0] - 2026-08-27

- Take page boundaries from the file instead of guessing them

## [0.8.0] - 2026-08-25

- Read PDFs, and refuse the ones that only look readable
- Add `tools/pdf_triage.py`: which files need OCR before anything else

## [0.7.0] - 2026-08-25

- Measure every rule, and say what each figure rests on
  (`tools/measure_rules.py`)
- Assert the stage order instead of commenting it

> The five entries above were reconstructed on 28 August from the tag history.
> They were written after the fact and are terser than the entries around them,
> which is the cost of letting a changelog fall five releases behind. Detail
> for these releases lives in the commits and in `design/`.

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
