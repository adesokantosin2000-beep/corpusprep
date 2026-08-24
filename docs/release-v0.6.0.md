# v0.6.0 — Integration

*24 August 2026*

The first release measured against a body of real books rather than against
fixtures written alongside the rules. Eleven texts, four file formats, two
genuine library scans.

It found that the previous release was silently deleting 5,500 words from
*Frankenstein*.

---

## Measured

Division counts taken from the works themselves, not from any output of this
software. Reproduce with `python tools/integration.py`.

| Text | Source | Divisions found |
|---|---|---|
| *Jane Eyre* | Gutenberg | **38 / 38** |
| *Emma* | Standard Ebooks | **55 / 55** |
| *King Solomon's Mines* | Standard Ebooks | **20 / 20** |
| *Frankenstein* | Standard Ebooks | **28 / 28** |
| *The Prince* | Gutenberg | **12 / 12** |
| *Treasure Island* | Internet Archive scan | 33 / 34 |
| *The New Wizard of Oz* | Internet Archive scan | 18 / 24 |

Region labelling remains 99.99% accurate over 7,654 hand-marked content lines.
No region cover gaps on any text, no crashes, and no loss of body text in any
of the clean cases: Emma retains 99.9% of its tokens, Jane Eyre 99.5%,
Treasure Island 99.5%.

---

## The fault worth reading about

`body-only` kept 89% of *Frankenstein*'s tokens. The missing 11% was not
apparatus. It was Walton's four letters — the frame narrative the novel opens
with — sitting inside a region labelled **Preface**:

```
   32- 144  front_matter  preface   6,184 tokens  'Preface'
```

Shelley's preface is about 700 words. **A 6,184-token preface should be
suspicious on its face**, and nothing in the tool was in a position to notice.

Three faults compounded, and any one alone would have been survivable:

1. The file stores headings on two lines — `Chapter` then `I` — and the heading
   rule required both on one, so the book had no division headings at all as
   far as that tier was concerned.
2. The fallback numeral tier saw two sequences, `I–IV` for the letters and
   `I–XXIV` for the chapters, took the longer, and discarded the other without
   recording that it had seen one.
3. A front-matter region runs to the first chapter absorbing whatever lies
   between, with no test that a preface is preface-sized.

Fixed. 28 divisions, 96.1% of tokens, and a regression test that reads the
letters back out of the body.

---

## Headings do not have to be alone on their line

The same assumption broke three ways across three books:

```
Frankenstein     'Chapter' / ' I'                  one heading, two lines
Treasure Island  'CHAPTER II. BLACK DOG APPEARS…'  one line, heading + page
Oz               (nothing)                         the heading is destroyed
```

*Treasure Island*'s headings survived OCR perfectly. They were simply inside
the page line, because the file holds one page per line — and 24 numbered
headings were being discarded in favour of weaker evidence.

Two new tiers handle the first two cases. The third has no heading to find at
all: every chapter of the Oz scan opens on a decorative drop-capital that OCR
destroys along with the title. Its chapters are recovered from the **running
heads** instead, which survive because they are reprinted on every page.

Separating the chapter titles from the book title needs no threshold and no
list of stop-words. Both are running heads and the book title is the more
frequent, so counting is useless; but chapters do not overlap each other and
the book title overlaps every chapter there is.

---

## A mistake that nearly shipped

The first version of the heading fix made the new tier *replace* the
running-head tier. Treasure Island went from 25 chapters to **22 — worse than
before the fix.**

```
                 headings   head series
Treasure Island        22            25
Oz                      0            18
```

Neither kind of evidence is reliably the better one. Both now run and the
results merge, a heading winning where the two coincide because it carries an
explicit number. 33 of 34.

**A new tier that replaces an old one has to beat it on every text, not on the
text it was written for.**

---

## Also fixed

- `is_page_per_line` tested only that lines were long, which is equally true of
  a file stored one paragraph per line — Emma passed it. It now requires
  uniformity as well: a page holds a fixed amount of type, a paragraph holds as
  much as the author wrote.
- A word token could begin with a combining mark in the JavaScript engine, so
  variation selectors counted as words. Python excluded marks entirely, so a
  decomposed `café` counted as two. Both now require a leading letter and
  normalise to NFC.
- A tie in the vote for a running-head's spelling was broken by Python's set
  hash order — not merely different from JavaScript, but not reproducible in
  Python either.
- The running-head pattern stopped dead at a quotation mark, truncating
  `THE OLD SEA DOG AT THE “ADMIRAL BENBOW.”`

---

## Known limits

Stated in full in `design/integration-failures.md`, which was written before
the fixes and still lists what was not fixed.

- *The New Wizard of Oz* recovers 18 of 24 chapters. The remaining series are
  too short or too damaged to group, and the file holds no other evidence.
- Books whose sections are titled but neither numbered nor introduced by a
  division word produce no structure. The whole text is kept as body and the
  report says so.
- Drama places the Prologue in front matter, which is a defensible default and
  a debatable one.
- PDF input is not implemented.

Precision and recall for the individual page-furniture rules are **not** quoted
here. They rest on two scans, which is too small a sample to publish a figure
from.

---

## Verification

Every claim above is reproducible from the repository:

```
python tests/test_corpusprep.py     # 441 tests
python tools/measure.py             # accuracy against hand-marked keys
python tools/integration.py         # the table at the top of this page
python tools/check_parity.py        # Python and JavaScript agree, 16 files
node   tools/ui_test.js             # 24 checks against the built page in a DOM
```

Install with `pip install -e .`, or open
[the web application](https://adesokantosin2000-beep.github.io/corpusprep/),
which runs entirely in the browser and uploads nothing.
