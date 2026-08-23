# Design decisions

A running record of choices made and the reasoning behind them. Written as
they are made, not reconstructed afterwards.

---

## 2026-08-23 — Running-head detection: design

Phase 2, Week 2, Monday. On paper, before any code.

### The problem

Text derived from scanned or typeset pages carries **page furniture**: the
book or chapter title repeated at the top of every page, sometimes a footer,
and a page number. In a 400-page novel that is 400 spurious lines, and every
one of them corrupts word counts, collocation spans and sentence splitting.

Plain-text Project Gutenberg files have had this removed by hand already. It
appears in PDF extraction, OCR output, and archive scans, which is precisely
the material this phase exists to handle.

### Why the obvious approaches fail

Three tempting rules, each of which destroys prose:

| Rule | What it also deletes |
|---|---|
| Short lines | Dialogue, verse, exclamations, chapter titles |
| All-capital lines | Emphatic prose, inscriptions, telegrams, letters |
| Lines that repeat | Refrains, formulaic dialogue, "Yes, sir." |

The prototype script used the first two and destroyed prose on both counts;
those failures are pinned by regression tests B2 and B4. Repetition alone is
no better: a ballad refrain repeats a dozen times and is unquestionably part
of the text.

### The discriminating signal is regularity, not appearance

A running head is not a line that *looks* like a header. It is a line that
**recurs at a roughly constant interval**, because that interval is the page
length. A refrain recurs irregularly, wherever the poet chose. That difference
is measurable and is the whole basis of the detector.

### Algorithm

1. **Collect candidates.** Non-empty lines at or under `MAX_LEN` characters,
   excluding anything already labelled as a structural heading.

2. **Normalise for comparison.** Lowercase, collapse whitespace, strip
   punctuation, and **remove digits**. Digits matter: `JANE EYRE 42` and
   `JANE EYRE 43` are the same running head on consecutive pages, and would
   not group without this.

3. **Group by normalised form.** Discard groups with fewer than
   `MIN_OCCURRENCES` members.

4. **Score regularity.** For each group, take the gaps between consecutive
   occurrences and compute the coefficient of variation, the standard
   deviation divided by the mean. A running head has a low value; a refrain
   has a high one. Accept below `MAX_CV`.

5. **Corroborate against a global page length.** The modal gap across *all*
   candidate groups estimates the page length of the document. A group whose
   own gap matches that estimate is far more likely to be furniture than one
   that happens to be evenly spaced by coincidence.

6. **Handle alternation.** Books commonly put the book title on the verso and
   the chapter title on the recto, so each series recurs every *two* pages.
   A gap of either one or two page lengths is therefore acceptable.

Page numbers are a separate rule, already partly built: a standalone numeral
counts only within an ascending run, which is what stops an isolated `1847`
being deleted.

### Parameters, to be set by measurement rather than taste

| Name | Starting value | Meaning |
|---|---|---|
| `MAX_LEN` | 60 | Longest line that can be furniture |
| `MIN_OCCURRENCES` | 5 | Fewest repeats to consider |
| `MAX_CV` | 0.25 | Highest irregularity accepted |
| `PAGE_GAP_TOLERANCE` | 0.15 | How far a gap may sit from the page estimate |

**These are guesses and are written down so that they can be argued with.**
Every one must be justified against the answer keys before the stage is
considered finished. A threshold that cannot be defended by a number is a
threshold that will silently misbehave on someone else's corpus.

### What the detector must never do

Delete on its own judgement. Like every other rule here it labels; removal
follows from the user's selection. Where confidence is low it must present the
cluster for review rather than guess, because the cost of a false positive is
deleted prose and the cost of a false negative is a visible artefact the user
can see and report.

---

## 2026-08-23 — A gap that blocks the above

Writing the design surfaced something that would have been discovered a week
later and more expensively.

**There is no test data containing running heads.**

Every fixture in the repository is a Project Gutenberg text, and Gutenberg
volunteers strip page furniture by hand as part of transcription. Jane Eyre,
Romeo and Juliet and De Profundis contain no running heads, no page numbers
and no catchwords. The baseline of 99.98% is measured entirely on texts that
do not exercise the rule about to be built.

Building a detector against data that lacks the thing being detected is not
possible in any useful sense. Two consequences:

1. **A synthetic fixture is needed to develop against**, generated with known
   furniture so that ground truth is exact. This is written next.
2. **Synthetic data cannot validate the detector.** Tuned against a generator,
   the thresholds would learn that generator's regularities, which are cleaner
   than any real scan. Real OCR or PDF-derived text is required before the
   figures mean anything.

Recorded as a blocker rather than worked around. The realistic sources are a
PDF extraction of a public-domain scan, or an Internet Archive OCR text, and
obtaining one is now the first task of Week 2 rather than the last.

---

## 2026-08-23 — Furniture is line-level, not a region

A second thing the design step surfaced, and one that would have caused an
awkward rewrite if found during implementation.

Page furniture cannot be a region label. Regions are contiguous and
non-overlapping, and every line belongs to exactly one; that invariant is what
guarantees nothing is lost. But a running head sits **inside** a chapter, every
thirty-odd lines. Labelling it as a region would shatter one chapter into
hundreds of fragments and destroy the structure the segmenter exists to find.

So furniture is **orthogonal to segmentation**: a per-line property, not a
region. A line can be body *and* furniture at once, and it is removed on the
strength of the second while the first still describes where it sits.

Consequences:

- `Document` gains a set of furniture line numbers, separate from `regions`.
- The region cover stays complete and non-overlapping, unchanged.
- Rendering removes a line if its region is dropped **or** it is marked as
  furniture.
- Measurement needs its own mechanism. `tools/measure.py` scores region labels;
  furniture needs a per-line binary judgement, so answer keys carry it in a
  separate `.furniture` file listing the line ranges that are furniture.

This is the same separation that has held throughout: detection records a
judgement, and removal is a later, explicit step that reads it.

---

## 2026-08-23 — Running-head detection: first measurement

Implemented as designed, then measured. Three failures came out of the first
run, and each was worth more than the passing figure.

**First run: 60 furniture lines found, 0 of them correct in the sense that
mattered.** Both running-head series were rejected as irregular, at CV 0.33 and
0.34 against a limit of 0.25.

The tempting response was to raise the limit. That would have been wrong: a
looser limit admits refrains, which is the failure the whole design exists to
avoid. Inspecting the groups showed the actual cause. OCR corrupts roughly one
head in ten, so `JANE EYRE` appears fourteen times and `IANE EYRE` once. The
corrupted instance is missing from its series, the gap it leaves is double the
normal one, and that single outlier inflates the irregularity score past the
threshold.

The series had been split, so the fix was to reassemble it: near-duplicate
groups are folded into the larger series they resemble, one-directionally so
that two genuine heads of similar size are never merged. **A threshold problem
and a data problem look identical from the outside, and only inspection tells
them apart.**

**Second run: 96.7% precision and recall.** Four errors, all instructive.

Two false positives, lines 1 and 9: `JANE EYRE` on the title page, and the
imprint date `1847`. The title page carries the book's title, which is
character-for-character the running head, and a bare year, which looks exactly
like a page number. Searched whole, a scanned novel has its title page deleted.
Furniture is a property of the printed page body, so the search is now
restricted to body regions.

Two misses, lines 106 and 269: `l3` and `l8`. The scanner read 13 and 18 with a
lowercase L for the 1. After digit-stripping, `l3` leaves the letter `l` rather
than nothing, so it never joined the page-number series. Page numbers are now
recognised through common digit lookalikes, with the guard that a
single-character line must be a real digit, since a lone `I` is far more often
a pronoun or a roman numeral than a page number.

**Third run: 100% precision and recall.** 60 of 60 furniture lines, no prose
touched, on a fixture where the refrain repeats 64 times, more often than the
furniture itself.

### What that figure is worth

**Not much on its own, and it should not be quoted without this paragraph.**
The fixture is synthetic and I wrote the generator. Reaching 100% against it
demonstrates that the algorithm handles the failure modes I thought to build
in, and nothing more. Real scans are messier in ways no generator anticipates:
inconsistent page lengths across signatures, heads that change at every chapter,
footnote blocks, columns, plates and inserted illustrations.

The parameters remain guesses that survived one artificial test. They are
recorded in `furniture.py` so they can be argued with, and they must be
re-measured against real OCR or PDF-derived text before any of this is trusted.
That remains the outstanding blocker from earlier today.

---

## 2026-08-23 — Catchwords: design

Week 4, Monday. On paper, before any code.

### What a catchword is

In books printed between roughly 1500 and 1800, the last line of each page
carries, set to the right, the first word of the following page. The compositor
put it there so the binder could confirm the sheets were gathered in order.

```
    ... and so he departed from that place, saying
    nothing of what he had seen. The night was
                                              And
    ----------------------------------------- page break
    And in the morning there came a messenger ...
```

Anyone working with EEBO or ECCO transcriptions meets one on every page. Left
in, a 300-page book gains 300 spurious tokens, every one of them a real word
duplicated at a sentence boundary, which is worse than a page number because it
looks like ordinary text to every downstream tool.

### Why this rule is unlike the running-head rule

The running-head detector had to infer furniture from **position**, because a
running head is otherwise indistinguishable from a chapter title. Regularity was
the only signal available, which is why it needed thresholds, and why those
thresholds are still guesses.

A catchword carries its own proof. It is **the first word of the next page**,
and that relationship can be checked directly rather than estimated. The
evidence is a content match, not a statistical tendency.

This matters for how much the rule can be trusted: it has one real parameter
rather than four, and its central test cannot be satisfied by coincidence in the
way an evenly spaced refrain can satisfy a regularity test.

### Algorithm

The page-number series found by the running-head detector already marks where
pages end, so the page boundaries come free.

For each detected page-number line:

1. Walk **backwards**, skipping blanks and other furniture, to the last line of
   the page. Call it `C`.
2. Walk **forwards**, skipping blanks, running heads and page numbers, to the
   first real line of the next page. Call it `N`.
3. Accept `C` as a catchword when **`N` begins with exactly the words of `C`**.

Then corroborate across the document, because one match is coincidence and
thirty is a printing convention.

### The one guard that matters

`C` must be **short**: at most `CATCHWORD_MAX_WORDS` words and
`CATCHWORD_MAX_LEN` characters.

Without it the rule deletes prose. A page can legitimately end with a full line
whose last word opens the next page, and in verse with a refrain this happens
often. A catchword is a fragment set alone on its own line; a line of prose that
happens to repeat is not one, however well it matches. **The length guard is
what separates the printing convention from the coincidence**, and it is the
only place this rule can destroy text.

### Parameters

| Name | Starting value | Meaning |
|---|---|---|
| `CATCHWORD_MAX_WORDS` | 3 | Longest catchword accepted |
| `CATCHWORD_MAX_LEN` | 30 | Longest catchword in characters |
| `CATCHWORD_MIN_PAGES` | 4 | Fewest matching pages before the rule fires |
| `CATCHWORD_MIN_RATIO` | 0.35 | Share of pages that must match |

Four again, but three of them exist only to decide whether the book uses
catchwords at all. Once that is established, the per-line decision rests on the
content match alone.

### What it must not do

Fire on a modern book. A text with no catchwords must produce an empty set, and
the ratio test is what guarantees that: isolated coincidental matches never
reach the threshold. **A rule that finds nothing on a text that contains nothing
is the result to check first**, and it is easier to get wrong than it looks,
because a rule that fires on 2 pages in 300 still reads as "working" in a
summary count.

---

## 2026-08-23 — Catchwords: measurement, and a bug in the shipped detector

18 of 18 catchwords, no false positives, and zero found on all three modern
fixtures. The trap survived, as did the two pages with no catchword.

But the number worth recording is not that one.

### The new fixture found a bug in the rule committed this morning

The first run examined **zero page boundaries**, because the page-number series
was rejected as irregular. Its gaps read `[25, 23, 2, 27, ...]`, and a gap of 2
is impossible between consecutive page numbers.

The cause was the OCR digit-lookalike table added this morning. It maps `S` to
5 and `o` to 0, so **the word `So` translates to `50` and passes as a page
number.** `Bo` becomes 80, `lo` becomes 10. The early modern fixture has `So`
as a catchword, which is how it surfaced.

This is a live fault in code already committed, not an artefact of the new
fixture. Any text where a short word such as `So` recurs near the page interval
would have had that word deleted as a page number, silently.

The guard: **at least half the characters must already be real digits.**
Substitution models OCR corrupting a digit or two inside a number. It must not
be allowed to manufacture a number out of a word. `l3` keeps one real digit of
two and passes; `So` has none and does not.

### Why the running-head fixture did not catch this

It contains no short capitalised words that translate to digits. Its refrain,
dialogue and emphatic capitals were chosen to attack the *length* and
*repetition* rules, which were the failure modes I had in mind at the time.

**A fixture only tests the failure modes its author thought of.** The second
fixture found the first fixture's blind spot, and there is no reason to think
a third would not find another. This is the concrete argument for why real EEBO
and OCR text is still required, rather than a caveat repeated out of caution.

### The parity harness had the same shape of flaw, again

It was comparing the merged furniture set. Two rules disagreeing in opposite
directions would cancel out in a union and read as agreement. Catchwords are
now compared as their own field.

---

## 2026-08-23 — The first real text breaks the detector

The outstanding blocker was real page-imaged data. Project Gutenberg turns out
not to supply it, and to explain why is worth more than the search took.

### Gutenberg cannot validate this rule, confirmed three ways

1. The Distributed Proofreaders documentation states that `[pg n]` markers are
   converted to anchors and **removed from the plain-text flow**.
2. PG eBook #55002, whose transcriber's note discusses pagination directly,
   contains **zero bare page-number lines**.
3. Its HTML edition carries page anchors with **no visible text**.

Page furniture is removed during transcription, by policy. That closes the
question: no amount of searching Gutenberg will produce a positive example.

### What it can supply is a negative control, and that broke everything

*The Book of Old English Ballads* (PG #9405) was added as a real text on which
the detector should find nothing.

**It marked 63 lines of verse as furniture.**

*The Nut-brown Maid* is a dialogue poem of fixed stanza length. `HE`, `SHE`,
and two refrains each recur thirteen times, every 32 lines, at a coefficient of
variation of **0.00**. Perfectly regular — more regular than any real running
head, which drifts as paragraphs break.

### The flaw was circular reasoning, and it was in the design

`estimate_page_length` took the most regular series *of any kind* as the page
length. In a text with no pages, the most regular series is the refrain. The
refrain therefore set the yardstick and was then measured against it, and of
course it passed.

**The rule had no independent evidence that the document had pages at all.**

The synthetic fixture concealed this because I wrote its refrain to recur at
`randint(6, 20)` — irregularly. That encoded my assumption. Real verse in fixed
stanzas is metronomic, and the assumption was simply wrong.

### The fix: page numbers must count upwards

A page number is the one candidate that carries evidence a refrain cannot
imitate. It is part of an **ascending sequence**. So:

1. A numeric series is restricted to its longest ascending run before it counts
   as page numbers at all. Gaps are allowed, for missing and misread pages;
   going backwards is not.
2. The page length is derived **only** from that series.
3. **No ascending page-number sequence means no page structure**, and no
   running head can be corroborated. The detector returns nothing and says why.

This was in the Week 3 plan as "requiring a monotonic sequence rather than a
bare integer" and was never implemented. The synthetic fixture passed without
it, so nothing forced the issue.

### After the fix

| Fixture | Kind | Furniture found | Correct |
|---|---|---|---|
| `pg9405_ballads.txt` | Real verse, heavy refrains | 0 | ✅ |
| `CBronte_Jane.txt` | Real prose | 0 | ✅ |
| `romeo_juliet.txt` | Real drama | 0 | ✅ |
| `pg_marked.txt` | Gutenberg apparatus | 0 | ✅ |
| `scanned_novel.txt` | Synthetic, page-imaged | 59 of 60 | 100% precision |
| `early_modern.txt` | Synthetic, catchwords | 62 + 18 catchwords | 100% |

Recall on the scanned novel fell from 60 to 59, and the lost line is a correct
refusal. Page 8 is scanned as a lone `B`, and a single character must be a real
digit to count as a page number, because a lone `B` is far more often a letter.
**A miss leaves a visible artefact the user can report; a false positive deletes
prose.** The trade is the right way round and is left as it is.

### A fixture bug, found by the same test

Two further lines were initially missed, and the fault was in my generator.
It built `l3` by prefixing a letter to `3`, which **invents a digit**: the line
then reads as 13 sitting between 2 and 4. Real OCR misreads the `1` already
present in `13`; it does not hallucinate one. The ascending-run test was right
to reject an impossible sequence. The generator now corrupts a digit that is
already there.

### What this episode is worth

The detector scored 100% on synthetic data and failed on the first real text it
ever saw. That is the entire argument for real fixtures, made concrete, and it
is a better result than another passing number would have been.

It also sharpens what remains outstanding. Gutenberg is settled and closed. The
open requirement is now specifically **OCR or PDF-derived text for running
heads, and an EEBO or ECCO transcription for catchwords.**
