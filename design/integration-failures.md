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

## I1 — Frankenstein loses the first 5,500 words of the novel — **FIXED**

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

## I2 — Treasure Island has real chapter headings and the tool never looks at them — **FIXED**

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

## I4 — Running-head titles come back damaged — **PARTLY FIXED**

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

## I5 — `is_page_per_line` does not test what its name claims — **FIXED**

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


---

# Tuesday: what was fixed

| text | before | after |
|---|---|---|
| `mary-shelley_frankenstein.epub` | 24 chapters, 89.0% of tokens | **28 divisions, 96.1%** |
| `treasureisland0000unse_k0j8.epub` | 25 of 34 | **33 of 34** |
| everything else | unchanged | unchanged |

Four of the seven closed. **I1 and I2 turned out to be one fault wearing two
costumes**, which is why they are reported together below.

## The single cause behind I1, I2 and I1(a)

Every heading rule assumed *one line, one thing*. Three books break that
assumption in three different ways:

```
Frankenstein     'Chapter'  /  ' I'                    one heading, two lines
Treasure Island  'CHAPTER II. BLACK DOG APPEARS…'      one line, heading + page
Oz               (nothing)                             the heading is destroyed
```

Two new tiers, and the fix is the same shape in both: **stop requiring a
heading to be alone on its line.**

## Merging the two page-per-line tiers rather than choosing

The first attempt made the prefix-heading tier preempt the running-head tier,
and Treasure Island went from 25 chapters to **22 — worse than before the fix**.
The heading tier is better where headings survive and blind where they do not.

```
                 headings   head series
Treasure Island        22            25
Oz                      0            18
```

Neither is reliably the better evidence, so both run and the results merge, a
heading winning where the two coincide because it carries an explicit number.
33 of 34.

**A new tier that replaces an old one has to beat it on every text, not on the
text it was written for.** Checking that was the only reason this was caught.

### The merge window is not a constant

Merging on "within two lines" merged nothing. Treasure Island is two lines to
the page, so a heading and its first running head sit *four* lines apart. The
window is now half the median spacing between headings — wider than the offset,
narrower than a chapter, by construction rather than by tuning.

## I5: uniformity, not length

The predicate now requires the coefficient of variation of line lengths to be
at most 0.75 as well as a median of 200. **A page holds a fixed amount of type;
a paragraph holds as much as the author wrote.**

```
Treasure Island (scan)      median 1363   cv 0.34
Oz (scan)                   median 1080   cv 0.61
------------------------------------------------------
Frankenstein (paragraphs)   median  396   cv 0.88
Emma (paragraphs)           median  231   cv 1.35
Jane Eyre (paragraphs)      median  129   cv 1.23
```

The populations do not overlap on either measure. Emma and Frankenstein no
longer claim to be page images, which is the honest answer and also removes the
latent exposure logged on Monday.

## A parity fault, found because Treasure Island was added to the harness

Titles disagreed on one region:

```
python 'END OF THE FIRST DAY’S FIGHTING.'
js     "END OF THE FIRST DAY'S FIGHTING."
```

The running-head title is the most frequent spelling in its series. That series
has the phrase twice with a typographic apostrophe and twice with a straight
one, and Python's `max(set(forms), key=forms.count)` breaks the tie by **hash
order** — not merely different from JavaScript but not reproducible in Python
either. Both now take the earliest of the joint winners.

**A tie-break that is not written down is a tie-break the other implementation
cannot copy.**

The harness also now prints *which* title differs. It reported only that a
sequence mismatched, which meant diffing two engines by hand to find one
apostrophe.

## Still open, deliberately

**I3** short head series — needs corroboration, not a lower threshold. Oz
remains at 18 of 24 and there is no further evidence in that file to use.
**I6** no titled-section tier, so the ballads have no structure. This is a
missing capability and belongs in a schedule, not a fix day.
**I7** drama drops the Prologue. A default worth revisiting with a linguist
rather than settling alone.


---

# PDF pass, ten files

`python tools/pdf_triage.py FOLDER`. Three more PDFs arrived — Beowulf, *Doctor
Faustus*, and a set of metaphysical poems — and all three are verse or drama,
which is the material the untested rules were most exposed on.

| kind | n | |
|---|---|---|
| usable text | **5** | ready to clean |
| unreadable text layer | 1 | 7,205 "words", 0% letters |
| no text layer | 3 | nothing to extract |
| empty file | 1 | failed download |

**Five of ten usable**, up from two of seven. The proportion is not the finding;
the two faults below are.

---

## P1 — A rule that scores 100% found 0 of 337 verse lines — **FIXED**

**Severity: highest. Maximum possible damage, on the material the rule exists
to protect.**

`LIT 201 Recommended metaphysical poems.pdf` is ten poems. Protected spans
found **none of them**:

```
as extracted (a blank line between every verse line):    0 of 337
with the blank lines removed:                          337 of 337
```

The rule is not wrong about this text. It is completely right and never gets
to look at it.

PDF extraction double-spaces the file — 55% of its lines are whitespace-only —
and `find()` stops its window at a blank line in each direction. So **every
verse line is judged alone, on a single data point**, and a single line is
never enough evidence. `break_profile` agrees the text is verse: 69% of lines
break deliberately, against a threshold of 45%.

### The fix for one input shape is the fault for another

The window stops at blank lines *deliberately*, and the reasoning is written
out in the source:

> Without this an eight-line stanza sitting between two paragraphs is judged
> mostly on the paragraphs, and enjambed verse is lost entirely. That is a
> windowing fault, not a threshold that needs loosening.

That was right, and it is what breaks here. A blank line is a structural
boundary **only when blank lines are not the norm**. At 55% density, uniformly
alternating, they are line spacing.

### Why this is the worst fault found so far

Turn on reflow and every line break in ten poems is destroyed. That is the
precise damage protected spans exist to prevent, and the fixture that scores
100% on it is `mixed_verse.txt` — real prose with real verse embedded.

Its own note explains the choice:

> A fixture of pure verse and one of pure prose would both be passed by a
> detector that guessed the same answer for every line. **The boundary is the
> only difficult part**, so this fixture is nothing but boundaries.

Right about the fixture, wrong about the world. **A book of poems is pure
verse, and pure verse is where the damage is total.**

Not confined to the extreme case. Beowulf, at 5% blank lines, protects 2,627
of a possible 3,318 — losing 21% to the same cause without anything looking
wrong.

### The fix, 28 August

**A blank line is a structural boundary only when blank lines are not the
norm.** `spacing_run()` decides that before the rule runs; `_despace()` removes
the leading; the spans come back in the caller's line numbers. The rule itself
is untouched — it now sees the text as it was set rather than as it was
extracted.

Two tests, and the second is what makes it safe:

```
blank lines           >= 40% of the file
text lines standing alone   >= 80% of them
```

Density alone would misread a poem printed as three-line stanzas with
three-line gaps, which is 50% blank and every blank of it structure. Requiring
that text lines stand *alone* is what separates leading from a stanza break.

**Blank runs longer than the modal run survive.** This is not a detail. Delete
every blank and one protected seed extends over the whole file, taking the
prose with it — the one error this rule must never make. In the poems the
leading is one blank and a stanza break is two, and only the leading goes.

```
                            before   after
LIT 201 metaphysical poems    0/337  276/337
mixed_verse.txt               52/246   52/246
Beowulf.pdf                2626/3318 2626/3318
Doctor Faustus             5995/5995 5995/5995
pg9405_ballads.txt         1958/2533 1958/2533
Jane Eyre, Emma, Frankenstein,
The Prince, Treasure Island,
King Solomon's Mines, Oz         0        0
```

Every prose file stayed at zero, and one fixture besides the poems moved:
`drama_with_contents.txt`, a segmentation skeleton of one speech per line, now
reads as fully protected drama. It is one-line blocks, which reflow leaves
alone in either case, so nothing downstream changes — but it is the shape to
watch, because a file of short one-line entries now compacts into one block.

`tests/fixtures/double_spaced_verse.txt` is the fixture the failure earned:
Donne between hard-wrapped Jane Eyre, set one line to a blank throughout. Its
key was written by the generator, not by running the detector.

The strongest test is not that fixture but the invariant behind it —
`test_double_spacing_does_not_change_the_answer` doubles `mixed_verse.txt` and
requires the same verdict on every line. It cannot be satisfied by protecting
more, or by protecting less.

### What the remaining 61 lines are

Worth separating, because they are two different things:

```
337 text lines
  276  protected
   35  cover, contents, poem titles, bylines — correctly not protected
   26  real verse, missed
```

The 26 are four stanzas scoring 38–40% against the 45% threshold, logged below
as P3. They are not a spacing fault; single-spaced, they miss too.

**Beowulf did not move.** At 5% blank lines it is nowhere near the density
test, and rightly so. Its 21% is the same *symptom* from a different cause and
is not addressed here.

---

## P2 — A 21,581-token "Introduction", and this time it is correct

**Severity: none observed. Recorded because it cannot be distinguished from
I1 without reading the book.**

*Doctor Faustus* keeps 56% of its tokens under `body-only`. The missing 44% is
one region:

```
front_matter  introduction  21,581 tok  'Introduction'
```

An editor's introduction to a Marlowe edition, and a researcher studying
Marlowe's language should drop it. The tool is right.

But this is the **same shape** as the Frankenstein fault, where a
6,184-token "Preface" turned out to contain the opening of the novel. The
difference between the two is not visible in the output, and **nothing in the
tool distinguishes them.** There is still no check that a front-matter region
is front-matter-sized; it simply happened to be correct here.

Recorded so that the next large front-matter region is inspected rather than
trusted.


---

## P3 — Enjambed verse sits just under the threshold — **FIXED**

**Severity: moderate. Real verse left unprotected, but visibly and in whole
stanzas rather than silently.**

With P1 fixed, four stanzas in the metaphysical poems are still missed:

```
line  97   5 lines   40%
line 119   5 lines   40%
line 504   8 lines   38%
line 640   8 lines   38%
                     threshold 45%
```

All four rhyme *abab* with the odd lines unpunctuated, so only the even breaks
carry both signals. Half of 100% is 50%, and the last line of a block scores
nothing because nothing follows it to vouch for the break — which is what puts
an eight-line stanza at 38%.

**Do not answer this by lowering the threshold.** 45% is what keeps wrapped
prose at 3%, and prose protected is the unrecoverable error.

The evidence not being used is the *neighbouring stanzas*. Each of these sits
in a poem whose other stanzas clear the threshold comfortably, and the window
stops at the block edge by design (see P1). A passage-level second pass —
extend a protected span to the adjacent blocks of the same poem — would use
that evidence without touching the threshold. Not attempted.

This is also the likeliest shape of Beowulf's missing 21%.

### The fix, 28 August

A stanza is judged with the poem around it. A block that cannot carry itself is
protected if it clears **half** the threshold and has a firmly protected block
beside it. The threshold is untouched.

```
                            before   P1 fix    P3 fix
LIT 201 metaphysical poems    0/337  276/337   302/337
Beowulf.pdf                2626/3318 2626/3318 2907/3318
pg9405_ballads.txt         1958/2533 1958/2533 2074/2533
mixed_verse.txt              52/246   52/246    52/246
every prose fixture               0        0         0
```

Beowulf's loss falls from 21% to 12%. The poems' remaining 35 lines are 33 of
cover, contents, titles and bylines — which must not be protected — and one
two-line closing couplet whose own rate is 0%, below any floor.

**The guard is what makes it safe, and the first attempt did not have it.**
Corroboration first vouched from the per-line judgements, which include lines
that never become a span. A lone flagged line in hard-wrapped *Jane Eyre*
seeded the block beside it, which seeded the next: three paragraphs protected,
reflow recovery down from 99.5% to 98.5%, caught by the round-trip test. A
voucher must now be most of a block and at least a span's worth. Seeded once
from the primary rule and never iterated, or one stanza would carry protection
to the end of the file.


---

## P4 — The command line never ran half the rules — **FIXED**

**Severity: high, and invisible. Every log the CLI ever wrote understated what
was in the file.**

`cmd_clean` and `cmd_inspect` called `segment(load(path))` rather than
`analyse()`. Everything that runs after segmentation — page furniture,
catchwords, hyphen breaks, footnotes — was never looked for, so:

- the log's furniture section was absent, which reads as "none found"
- `drop_furniture` removed nothing, because nothing had been marked
- the web application, which always ran the full pass, disagreed with the
  command line about the same file

`analyse()`'s own docstring says it exists so that "callers cannot accidentally
render a document whose furniture was never looked for", and the package's own
front end was that caller.

**`check_parity.py` could not have caught this.** It compares the two engines,
and both engines were right. The fault was in a front end, and nothing compares
front ends. Found only because a new rule was wired in and did not appear in
the CLI's output.

---

## P5 — Every division word was English — **FIXED**

**Severity: moderate, and silent in the worst way.**

`Kapitel`, `Глава`, `Kapitola` were not words the heading tier had been told
about, so a German, Russian or Czech book segmented as one undivided body. The
log then said *no structural headings found*, which reads as a fact about the
book rather than about the tool.

Fixed by widening the wordlist, with fixtures in three languages
(`tools/make_multilingual_fixtures.py`) whose keys are recorded as the
generator writes them. Region labelling was already language-independent and
scores 100% on all three; measurement now covers 7,733 content lines.

**A wordlist is only as wide as whoever wrote it.** This does not make the
package multilingual. It stops it being confidently wrong about three more
languages than before, and the remaining exposure is stated in `docs/USING.md`
rather than left for a user to discover.

---

## P6 — Interface furniture, and the fixture that nearly hid its fault

**Severity: none outstanding. Recorded for the method.**

The new rule scored 100% on its own generated fixture. It was wrong anyway, and
a test written afterwards found it in one line: a one-word comment sitting
directly above the controls — `Same`, then `Like`, then `Reply` — is inside the
trailing run of every record it appears in, and no amount of counting
afterwards can tell it from a control, because by then it looks exactly like
one.

The generator had not produced that shape because its comments were long. **A
fixture only tests the failure modes its author thought of** — the third time
that sentence has been written in this file.

The fix is a structural fact rather than a threshold: a record is never all
controls, because something was commented on, so the trailing run stops before
it eats the last line of the body.


---

## P7 — The interface test could not run, and had been wrong for four days — **FIXED**

**Severity: high. Half the test surface reported nothing, and what it would
have reported was a contradiction of the shipped product.**

`tools/ui_test.js` exited with `jsdom not installed` on the development
machine. The cause was not a missing install. `node_modules` is committed to
the repository so the machine can work offline, and the commit of jsdom was
partial:

```
files in node_modules/jsdom, committed   161
files in a complete jsdom 30.0.1         657
package.json                             absent
lib/generated/idl/Document.js            truncated at exactly 16,384 bytes
```

Every dependency in `node_modules` is at the version a fresh `npm install
jsdom` produces today — tough-cookie 6.0.2, whatwg-url 17.1.0, parse5 8.0.1,
undici 8.10.0 and the rest all match. Only jsdom's own tree was cut short.
Without `package.json`, Node cannot resolve `require('jsdom')` at all, so the
first symptom hid the second.

Repaired by completing the same vendored copy at the same version. Nothing
else in `node_modules` changed; one file's contents changed
(`Document.js`, 16,384 → 147,768 bytes) and 496 were added.

### What the test said once it could speak

```
39 passed, 1 failed
FAIL  "reads pdf" is honestly marked planned    claimed as available
```

**The assertion was wrong, and the product was right.** PDF reading shipped in
`v0.8.0` on 25 August and in the browser in `v0.11.0`; the capability list said
so correctly, and the test still demanded it be marked *planned*. It had been
failing since the day PDF support landed and nobody knew, because the runner
could not start.

The irony is exact. That check exists because the capability list once carried
three shipped features as planned — *"it went stale in the direction that
flatters"*, says the comment above it. The test then went stale in the
opposite direction and would have held the list back to a claim that was no
longer true.

**A test that cannot run is worse than no test.** It occupies the place where
coverage would be and asserts nothing, and the summary line that says how many
tests passed does not count it.

### The gap this sits in

`check_parity.py` compares the two engines. `test_corpusprep.py` exercises the
Python package. Neither touches a front end, which is where P4 lived and where
this lived. Two of the seven faults in this file are front-end faults found by
accident.

Both front ends now have a runnable test: `tools/ui_test.js` for the page, and
`test_cli_clean_runs_every_rule` for the command line — the latter verified by
reverting the P4 fix and confirming it fails.


---

## P8 — A reload put the sign-in gate back up — **FIXED**

**Severity: moderate, and mislabelled by its symptom. Reported as an
annoyance; it was a provenance fault.**

*"When I reload, it logs the users out."*

It never logged anyone out. Nothing was lost. The startup block read the saved
user out of local storage, filled the sign-in fields with it, and stopped:

```js
if (s.user) { $("#g-name").value = s.user.name || "";
              $("#g-inst").value = s.user.inst || ""; }
```

The gate stayed up with the name already typed in and `USER` still `null`.
Driven in a real DOM across two visits sharing one storage:

```
1. sign in           USER = A Reader     gate hidden
2. reload            USER = null         gate shown, name field pre-filled
   still in storage: {name: "A Reader", inst: "Somewhere"}
```

### Why this is not a cosmetic fault

`USER` is what stamps **Prepared by:** onto every preprocessing log. That line
is the reason the sign-in exists — `design/authentication.md` says so plainly:
*"for a research tool that provenance line is worth more than the login screen
itself: it makes the log a document someone can cite."*

A reader who reloads and takes the "Continue without signing in" door — the
faster of the two, and the obvious one when you have already signed in once —
writes every subsequent log without that line, and nothing tells them. The
symptom is a second click. The cost is unattributed logs.

### The fix, and the door it had to keep open

One line restores the session rather than the form. A `signedOut` flag and a
**Sign out** control in the header keep the gate reachable, which matters on a
shared machine: without them, signing in once would hide the door for good.

Skipping the sign-in records `signedOut` but does **not** erase the remembered
user, so going through that door on a borrowed machine does not cost the owner
their name.

Eleven checks in `tools/ui_test.js` cover the whole cycle — sign in, reload,
sign out, reload, skip — verified by reverting the fix and confirming two of
them fail.

### Where it hid

The same place as P4 and P7: a front end. The unit tests exercise the package,
which has no session; the parity check compares engines, which have no
session. `ui_test.js` opens the page — but it opened it *once*, and this fault
only exists on the second visit. A test that never reloads cannot see a
restore fault.

**Three of the eight faults in this file are front-end faults, and all three
were found by a person rather than by a test.**

