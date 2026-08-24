# Integration failure log

Week 12, Monday. The instruction: *"Run the complete pipeline across fifteen
varied texts. Log everything that breaks."*

Nothing below is fixed. Tuesday is for that. The Week 9 reflow log was written
under the same rule and it worked: **fixing faults on the day you find them
means fixing the easy ones and quietly losing the list.**

Reproduce with `python tools/integration.py`.

---

## The run

Eleven real books. Synthetic fixtures are excluded because they were written by
the same person as the rules and cannot surprise anyone.

| text | lines | median | chapters | body % | evidence |
|---|---|---|---|---|---|
| `CBronte_Jane.txt` | 4,083 | 129 | **38 / 38** | 99.5% | division heading |
| `romeo_juliet.txt` | 249 | 44 | 29 | 62.9% | division heading |
| `pg9405_ballads.txt` | 3,212 | 32 | 1 | 100.0% | *none found* |
| `pg1232_prince.txt` | 2,000 | 68 | **12 / 12** | 76.6% | division heading |
| `pg921-images-3.epub` | 1,975 | 59 | 1 | 85.1% | *none found* |
| `mary-shelley_frankenstein.epub` | 998 | 396 | **24 / 24** | 89.0% | bare numeral |
| `king-solomons-mines.epub` | 1,711 | 154 | **20 / 20** | 98.8% | bare numeral |
| `jane-austen_emma_advanced.epub` | 2,569 | 231 | **55 / 55** | 99.9% | bare numeral |
| `newwizardoz00densgoog.epub` | 506 | 1,080 | 18 / 24 | 96.4% | running head |
| `treasureisland0000unse_k0j8.epub` | 614 | 1,363 | 25 / 34 | 99.5% | running head |

Four of six books with a known chapter count segment exactly. No region cover
gaps anywhere, and no crashes.

**The headline number is not the interesting one.** Emma at 55 of 55 and King
Solomon's Mines at 20 of 20 say the ordinary path works. What follows is what
the table does not say.

---

## I1 — Frankenstein loses the first 5,500 words of the novel

**Severity: highest found. Silent loss of primary text from a clean file.**

`body-only` keeps 89% of Frankenstein's tokens. The missing 11% is not
apparatus. It is this:

```
   11-  31  front_matter  introduction   2,259 tok  'Introduction'
   32- 144  front_matter  preface        6,184 tok  'Preface'
```

Shelley's 1831 preface is about 700 words. **A 6,184-token preface should be
suspicious on its face.** What the region actually contains is the preface, the
dedication to Godwin, the epigraph from *Paradise Lost*, and then all four of
Walton's letters — the frame narrative the novel opens with. Those letters are
the book. They are labelled front matter and dropped.

Two faults compound:

**(a) Division headings split across two lines are invisible.** The file stores
them as two lines:

```
55: 'Letter'          143: 'Chapter'
56: 'I'               144: ' I'
```

`is_chapter_heading()` needs the word and its numeral on one line, so tier 1
finds nothing in this book at all — which is why the evidence column reads
"bare numeral" rather than "division heading". This is failure **F3** from the
reflow log, logged as untested in Week 9, now observed.

**(b) The numeral tier picks one run and discards the other.** The Letters
number `I II III IV` and the chapters restart at `I`. `find_numeral_sequence`
requires ascending, so it takes the run of 24 and drops the run of 4. Nothing
records that a second sequence was seen and rejected.

**(c) A front-matter region runs to `body_start` unchecked.** Whatever sits
between a front heading and the first chapter is absorbed regardless of size or
content. There is no test that a "preface" is preface-sized.

Any one of the three would have been survivable. Together they delete Walton
from the novel without a word in the report.

---

## I2 — Treasure Island has real chapter headings and the tool never looks at them

**Severity: high. The strongest available evidence is being skipped.**

25 of 34 chapters, found via running heads. But this scan is not Oz: its
chapter headings survived OCR perfectly well. They are simply *inside* the
page line, because the file is one page per line and the heading is printed at
the top of the chapter's opening page:

```
'CHAPTER II. BLACK DOG APPEARS AND DISAPPEARS. When I got back with the basin…'
'CHAPTER IV. THE SEA CHEST. I lost no time, of course, in telling my mother…'
'CHAPTER XXXIV. AND LAST. The next morning we fell early to work…'
```

Grouping the unmatched prefixes turns up **24 such headings, numbered, in
order.** A heading with its own numeral is far better evidence than a repeated
running head, and it is currently discarded because `is_chapter_heading()`
requires the heading to be the whole line.

This is the same shape of fault as I1(a) — a heading that is not alone on its
line is not seen — and the same shape as the Week 2 discovery that page
furniture in this format is a *prefix* rather than a line. **Three times now
the page-per-line format has broken a rule that assumed one line, one thing.**

The head-chapter tier should not have been reached here at all.

---

## I3 — The head-chapter threshold loses short chapters

**Severity: medium. Known limitation, now quantified.**

Oz finds 18 of 24, Treasure Island 25 of 34. In both, the misses are chapters
whose running-head series has fewer than `PREFIX_MIN_OCCURRENCES` surviving
members:

```
n=2  at [40, 44]   the old sea dog at the        (Treasure Island, ch. 1)
n=2  at [384, 392] how i began my sea adventure  (ch. 22)
n=2  at [396, 404] the ebb tide runs             (ch. 23)
```

Lowering the threshold is the obvious move and is probably wrong: 3 is already
low, and 2 admits any phrase that happens to open two pages. The better
question is whether a series of 2 can be *corroborated* — by a numbered heading
in the same place, which for Treasure Island exists (I2), or by the gap between
its neighbours matching the pattern of the surrounding chapters.

**Note that the `(opening, chapter not identified)` guard held.** Treasure
Island's chapters 1 and 2 are missing from the chapter list but present in the
body, which is the behaviour built yesterday and the reason this is a medium
rather than another I1.

---

## I4 — Running-head titles come back damaged

**Severity: low, but it is what the user sees.**

```
'SILVER’S. EMBASSY.'        stray full stop
'THE ATTACK,'               comma for a full stop
'THE TREASURE'              period lost
'GO TO BRISTOL.'            truncated: "I GO TO BRISTOL"
'THE OLD SEA DOG AT THE'    truncated at the opening quotation mark
```

The last two are the `PREFIX` pattern's doing, not OCR. Its character class
excludes `"` and `“`, so `THE OLD SEA DOG AT THE “ADMIRAL BENBOW.”` stops dead
at the quote mark. Truncation is harmless for *grouping*, since it truncates
consistently, and produces a visibly wrong title.

---

## I5 — `is_page_per_line` does not test what its name claims

**Severity: medium. No damage observed; the exposure is real.**

The test is "median non-blank line is at least 200 characters". Emma is stored
one *paragraph* per line, median 231, and passes:

```
jane-austen_emma_advanced.epub    median 231   page-per-line: yes
```

Nothing went wrong, because the prefix rule additionally requires a capitalised
prefix recurring three times and Emma has none, and because the numeral tier
fired before the head-chapter tier was reached. **Both of those are luck rather
than design.** A paragraph-per-line book that opens several paragraphs with the
same capitalised phrase would have text removed from the front of its lines.

The name asserts a fact about pagination that the predicate does not establish.
Genuine page-per-line files here have medians of 1,080 and 1,363 — five times
Emma's — so the two populations are far apart and the constant is merely set in
the wrong place. That is worth knowing before someone trusts the name.

---

## I6 — Two books produce no structure at all

**Severity: medium. Correct behaviour, insufficient capability.**

`pg9405_ballads.txt` and `pg921-images-3.epub` both fall through every tier and
are kept whole as `(whole text)` at confidence 0.4.

For the ballads this is right and known: each ballad has a title and no
division word, no numeral, and no running head. Nothing in the current tier
list can see it. The tool declines to guess, which is the correct posture, and
the result is a 17,000-word corpus with no internal structure.

A titled-section tier — a run of similar short lines separated by comparable
intervals — would cover this and a large class of poetry collections, essay
volumes and short-story collections. It does not exist.

---

## I7 — Drama drops the Prologue

**Severity: low. A judgement, not a bug, and it should be recorded as one.**

Romeo and Juliet keeps 62.9% of tokens. The drop is almost entirely correct —
PG header 140, licence 97, contents 156 — but includes:

```
   64 tok  front_matter/dramatis_personæ
   34 tok  front_matter/the_prologue
```

The Prologue is Shakespeare's text, spoken by the Chorus, and belongs to the
play. Dramatis Personae is arguable and depends on the research question.
Neither is apparatus in the sense the PG licence is.

**Both are visible in the region list and can be re-included by the user**, so
nothing is lost silently. Logged because a default that removes primary text
deserves to be a decision rather than an accident.

---

## What is not wrong

Recorded because these were the plausible failure modes:

- **No crashes.** Eleven books, three container formats, two 45 MB scans.
- **No region cover gaps anywhere.** The invariant held on every text.
- **No text removed from the ordinary cases.** Emma keeps 99.9%, Jane Eyre
  99.5%, Treasure Island 99.5%.
- **The negative controls stayed negative.** No prefix furniture found in any
  of the six books that have none, including the two with long lines.
- **Nothing was invented.** Every book that could not be segmented said so.

---

## Ranked for Tuesday

Highest impact first, which is not the order they were found in:

| | Fault | Why first |
|---|---|---|
| 1 | **I1** Frankenstein's letters | Silent loss of primary text |
| 2 | **I2** headings inside page lines | Best evidence unused; fixes 9 chapters |
| 3 | **I1(a)** two-line division headings | Shared cause with I1 and I2 |
| 4 | **I5** `is_page_per_line` | Latent, and cheap to make honest |
| 5 | **I3** short head series | Needs corroboration, not a lower threshold |

I4, I6 and I7 are below the line. I6 is a missing capability rather than a
fault and should be scheduled deliberately, not squeezed into a fix day.
