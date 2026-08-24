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

---

## 2026-08-23 — Footnotes: design

Week 4, Tuesday. On paper, before any code.

### The problem, and why it is not the same as page furniture

A footnote leaves two marks on a text: a **marker** in the body, and a **body**
elsewhere.

```
    Gowden graith'd[FN#1] his horse before,      <- marker, inside a verse line
    ...
    [FN#1]  Graitih'd, girthed.                  <- body, in a block below
```

Both corrupt a corpus, and they corrupt it differently. The marker is welded to
a word, so `graith'd[FN#1]` is one token to every downstream tool and never
matches `graith'd`. The body is editorial prose by a modern scholar sitting
inside what is supposed to be a 15th-century ballad, and it inflates every
count with the wrong century's vocabulary.

**Unlike page furniture, Gutenberg preserves this.** Transcribers strip running
heads and page numbers, but they keep footnotes, because a footnote is content.
So for the first rule in this phase, real test data exists in quantity.

### The signal, again, is a content relationship

The running-head rule had to infer furniture from position, needed four
thresholds, and was wrong. The catchword rule checked a relationship and was
right. Footnotes allow the same kind of check.

**A marker is confirmed by the existence of a body carrying the same label.**
`[1]` in the text is a footnote marker if, and only if, something elsewhere
begins `[1]` and reads as a note. That pairing is verifiable rather than
estimated, so the rule rests on evidence and not on a tuned number.

### Why this matters more than it sounds

Square brackets in a literary text are crowded with things that are not
footnotes:

| Form | What it is |
|---|---|
| `[Exit.]`, `[Enter Romeo]` | Stage direction. Part of the play. |
| `[Illustration]`, `[sic]` | Editorial apparatus, but not a note. |
| `[eBook #1513]` | Gutenberg boilerplate. |
| `[1]` with no matching body | Anything at all. |

A rule that deletes bracketed things deletes stage directions, and a corpus of
drama without its stage directions is a corpus of a different work. The pairing
requirement handles every row of that table at once: none of them has a
matching body, so none of them is touched.

### Algorithm

1. **Collect candidate markers**: short bracketed labels, `[1]`, `[12]`,
   `[A]`, `[FN#1]`, `{1}`. Labels are numeric, one or two letters, or roman
   numerals. Anything longer is a word, and words are not labels.
2. **Collect candidate bodies**: lines *beginning* with such a label, or the
   `[Footnote N: ...]` form Gutenberg uses widely.
3. **Pair by label.** A marker with a body is a footnote. A body with a marker
   is a footnote body.
4. **Report the unpaired separately, and never remove them.** An unpaired
   marker is exactly the case where the tool does not know what it is looking
   at, and that is precisely when it must not act.

### Three routes, because a footnote is not obviously rubbish

Page furniture is an artefact of printing and nobody wants it. A footnote is
editorial content, and whether it belongs in the corpus depends entirely on the
research question. So removal is not the only sensible answer:

| Route | Markers | Bodies | For |
|---|---|---|---|
| `retain` | kept | kept | Default. Studying the edition. |
| `remove` | stripped | dropped | Studying the work. |
| `extract` | stripped | written to a parallel file | Studying both, separately. |

`extract` is the one that makes this worth building. It turns a contaminated
corpus into two clean ones, and the parallel file is itself a usable object: a
corpus of one editor's annotations.

### What it must not do

Guess at symbol markers. An asterisk is a footnote marker, a censorship mark, a
typographic ornament and a multiplication sign, and only the first should go.
Symbols are detected and reported but not paired, unless a body confirms them.

The default remains `retain`, since a footnote is content until the researcher
says otherwise.

---

## 2026-08-23 — Footnotes: measurement, on real text throughout

The first rule in this phase built and measured entirely against real books,
because Gutenberg keeps footnotes. Its practice is to *relocate* them, not
remove them, so the marker and body both survive transcription.

| Fixture | Kind | Result |
|---|---|---|
| `pg1232_prince.txt` | Real, translator's notes | 28 pairs, 0 unpaired |
| `romeo_juliet.txt` | Real drama, 69 stage directions | 0 found ✅ |
| `pg9405_ballads.txt` | Real verse | 1 pair, 1 unpaired label ✅ |
| `CBronte_Jane.txt` | Real prose, no notes | 0 found ✅ |

### Real text settled a design question I had got wrong

The design said to "pair by label". Machiavelli's translator restarts the
numbering **in every chapter**, so `[1]` occurs fourteen times: seven markers
and seven notes, spread across seven chapters.

Pairing globally by label would have joined a marker in chapter two to a note
belonging to chapter nine, and the extracted file would have been confidently,
invisibly wrong — every note attached to the wrong sentence. Nothing would have
looked broken.

Pairing now walks the document in order and consumes the most recent unclaimed
marker, which resolves this without needing to know where the chapters are.
**A synthetic fixture would not have raised it**, because I would have numbered
the notes straight through.

### The unpaired case, found in real verse

The ballads contain the line:

```
That day made many [a] fatherlesse child,
```

That `[a]` is editorial, and nothing answers it. It is reported as an unmatched
label and **no route removes it**, including `remove`. An unpaired marker is
precisely the case where the tool does not know what it is looking at, which is
exactly when it must not act.

### What removal is worth

On *The Prince*, the `remove` route takes the corpus from 19,935 to 19,285
tokens. Those 650 tokens are a 1908 translator's prose sitting inside a 1513
Italian political treatise, and they were contaminating every frequency count
with the wrong century and the wrong author.

The marker comes off the word and leaves the word: `intrattenere[2]` becomes
`intrattenere`, which now matches the other occurrences of the same word. That
is the quieter half of the damage and probably the more common one.

---

## 2026-08-23 — De-hyphenation: the wordlist question, answered with numbers

Week 5, Monday. The schedule's instruction was to source a wordlist and check
its licence before writing any code, on the grounds that several common lists
cannot be redistributed.

### The licences are fine, and that turns out not to be the point

| List | Terms |
|---|---|
| 12dicts | Public domain |
| Moby | Public domain |
| SCOWL | Permissive; use, copy, modify, distribute and sell, without fee |
| web2 (Webster's 2nd) | Public domain |

No blocker. So the real question is not whether a wordlist *may* be used, but
whether it *should* be, and that is answerable by measurement.

### A modern wordlist is unfit for this job

Coverage of a 234,000-word list (web2) against the actual fixtures:

| Text | Word types | Recognised |
|---|---|---|
| Ballads, 1400s–1800s | 3,477 | **62.2%** |
| *The Prince*, trans. 1908 | 2,995 | **66.9%** |
| *Jane Eyre*, 1847 | 13,407 | **65.3%** |

A third of the vocabulary of *Jane Eyre* is unknown to it. The rejected words
are not only archaic spellings like `againe`, `accurst` and `adoe`; they
include `adapted`, `adding`, `additions` and `adventures`, because the list
omits inflected forms.

A rule that joined a hyphen only when the joined form is "a known word" would
therefore **refuse a third of the legitimate joins**, and would fail worst on
exactly the historical material this tool exists to serve.

### The document's own vocabulary is better evidence

If `example` occurs elsewhere in *this* text, then the joined form is attested
in this text's own orthography, spelling conventions, dialect, proper nouns and
technical vocabulary. No external list can match that, and no licence question
arises because nothing is bundled.

**Decision: no wordlist is shipped.** Evidence comes from the text itself. A
user may supply their own list as an optional tiebreaker, and the default
behaviour does not depend on one.

### Rejoining the line and removing the hyphen are two different decisions

This is the part the schedule's framing obscured. A line break in the middle of
a word is **always** an artefact of typesetting. The hyphen may be entirely
real:

```
    to-           ->   to-morrow      (a real 19th-century compound)
    morrow             tomorrow       (wrong: invents a modern word)
```

*Jane Eyre* contains 1,146 hyphenated compounds, `to-night` 42 times,
`drawing-room` 26, `to-morrow` 25. Joining those blindly corrupts real words.

So the two decisions are separated. The fragments are always rejoined onto one
line, because that break is certainly spurious. Whether the hyphen survives is
then decided on evidence:

| Evidence in the same document | Action |
|---|---|
| `example` attested elsewhere | join, drop the hyphen |
| `to-morrow` attested elsewhere | join, keep the hyphen |
| both attested | rejoin, keep hyphen, **flag** |
| neither attested | rejoin, keep hyphen, **flag** |

Keeping the hyphen when uncertain preserves the source exactly, which is
visible and reversible. Dropping it invents a word silently.

### A guard that only real text would have suggested

*Jane Eyre* has 143 lines ending in a hyphen, and **not one is hyphenation**:

```
    ... to the North Cape -
    ... and said at once -
```

They are dashes used as punctuation. The discriminator is that a hyphenation
hyphen is **attached to the word**, while a dash is preceded by whitespace.
Without that guard, all 143 would have been mangled, joining `Cape` to the
first word of the next line.

---

## 2026-08-23 — De-hyphenation: measurement

The fixture is **synthetic damage applied to real prose**: *Jane Eyre*
hard-wrapped to 64 columns, with 180 words broken across lines, 9 of them at
their own compound hyphen, plus 23 trailing dashes that must be left alone.
The vocabulary and the compound habits are Brontë's; only the line breaks are
invented, which matters because the whole question is whether real vocabulary
supplies enough evidence.

### Detection

| | |
|---|---|
| Broken words found | **180 of 180** |
| Dashes wrongly treated as hyphenation | **0 of 23** |
| Words left split after repair | **0** |

### Resolution

The number that matters is not how often it acts but whether it is right when
it does.

| Evidence available | Decides | Correct when it decides |
|---|---|---|
| The fixture's own vocabulary | 84 of 180 | **84 of 84 — 100%** |
| The whole novel's vocabulary | 180 of 180 | **180 of 180 — 100%** |

**Never wrong when it acts; silent about the rest.** All 9 real compounds keep
their hyphen in both conditions: `half-comprehended` never becomes
`halfcomprehended`.

The gap between the two rows is the honest limitation. A short text does not
contain enough of its own vocabulary to resolve every break, and the correct
response is to flag, not to guess. Supplying the full novel closes the gap
entirely, which is what happens in real use, where the document *is* the whole
book.

For comparison, the 234,000-word modern list decides more of the short case but
gets 16 of them wrong. The document's own vocabulary was never wrong.

### A bug worth recording: consecutive broken lines

The first implementation left **23 of 180 words still split**. Hard-wrapped
text frequently breaks words on adjacent lines, and merging line 31 into 32
consumed line 32's own break without repairing it, so every second break in a
run was skipped.

The repair now keeps absorbing while the line it has just built still ends in a
break. It was visible only because the test asked whether *any* word remained
split, rather than whether the joins performed were correct. **The first
question is the useful one**, and it is easy to write the second by accident.

---

## 2026-08-23 — The review queue: design

Week 6. The schedule calls this "not a side feature", and it is right: every
uncertain rule in this phase defers to the researcher, and until now there has
been nowhere for those deferrals to go. De-hyphenation currently flags 96 cases
on one short fixture and there is no way to answer them.

### Identity is the hard part, and line numbers are the wrong answer

The obvious key for a queue item is its line number. That breaks immediately.
Remove the Gutenberg header and every line number below it shifts, so a saved
decision would silently attach to the wrong word. Re-import a corrected source
and the same thing happens.

**The key must be the content, not the position.** A flagged break is
identified by the thing actually in question: `def-inite`. That key is stable
under every transformation that moves lines around, and it has a second
property worth more than stability.

**Decisions become reusable across documents.** A researcher preparing forty
volumes of the same edition answers `to-morrow` once. The same key appears in
volume two and is already answered. A line-number key could never do that.

The cost is that a genuinely ambiguous form must be decided the same way
everywhere in a corpus, which for a hyphen is almost always what is wanted.

### The format has to be hand-editable

A queue nobody opens is a queue nobody uses. So: tab-separated, one decision per
line, comments with `#`, and a header explaining the choices. It opens in a text
editor, in Excel, and in `awk`. It is the same reasoning as the answer keys, and
those have already proved they get read.

```
# DECISION   TYPE     ITEM           WHY
?            hyphen   def-inite      neither form occurs elsewhere in this text
join         hyphen   sug-gest       (answered: write "suggest")
keep         hyphen   half-broken    (answered: keep the hyphen)
```

`?` means undecided, and the tool keeps asking. Anything else is an answer.
A bare word in the decision column means "use exactly this", which is the escape
hatch for cases the tool's two options do not cover.

### What must be true afterwards

1. **Round trip.** Write a queue, read it back, get the same items.
2. **A second run asks nothing.** Once answered, an item never returns.
3. **An unanswered queue changes nothing.** Importing a file of `?` must leave
   output byte-identical, or the queue is not safe to experiment with.
4. **Decisions never invent behaviour.** An answer of `join` produces exactly
   what the tool would have produced had it been confident. The queue supplies
   the missing confidence; it does not add a new transformation.

### Why not make the tool guess and let the user correct afterwards

Because the errors would be invisible. A silently joined `half-comprehended`
looks like a word, and nobody proofreads a 200,000-word corpus. The whole value
of this tool is that its uncertainty is legible, and a review queue is what
uncertainty looks like when it is written down.

---

## 2026-08-23 — The review queue: built and measured

All four required properties hold, and each is a test rather than a claim.

| Property | Result |
|---|---|
| Round trip: write, read, same items | 95 items out, 95 back |
| A second run asks nothing | 0 outstanding once answered |
| An unanswered queue changes nothing | output byte-identical |
| Decisions survive lines moving | key is content, verified by shifting the file |

96 flagged breaks collapse to **95 queue items**, because the same broken word
recurs and is one question, not several.

### The number that closes the loop

Answered on its merits, the queue takes de-hyphenation from **84 of 180 to 180
of 180**, with the 9 real compounds keeping their hyphens. The rule alone is
never wrong but often silent; the rule plus a reviewer is complete. That is the
division of labour the whole phase was designed around, and this is the first
point at which it actually works end to end.

### Keyboard, not mouse

The interface answers one item at a time: `J` joins, `K` keeps the hyphen, `S`
skips, `←` goes back, `Esc` finishes. Two hundred items answered by mouse is a
job nobody completes, and an unfinished review is the same as no review.

Decisions are per-document and start empty. Carrying them between texts would
apply one book's judgements to another without asking, which is exactly the
kind of silent action this tool exists to avoid. The queue file is how they
travel deliberately.

### The queue is written even when nothing is outstanding

`prepare()` always writes it. A file that appears only sometimes is a file
nobody learns to look for, and the record of what *was* decided is worth as
much as the list of what remains.

---

## 2026-08-23 — Protected spans: the schedule's proposed signal does not work

Week 8. Reflow cannot start until we know which lines must never be rejoined,
so this comes first.

The schedule's plan for Tuesday was a **line-length variance detector**, on the
premise that "prose wraps to a consistent width; verse does not". Measured
against the fixtures, that premise is false.

| Text | Kind | Length CV |
|---|---|---|
| Ballads | verse | 0.31 |
| *Romeo and Juliet* | drama | 0.43 |
| Hard-wrapped *Jane Eyre* | prose | **0.27** |
| *The Prince* | prose | **0.21** |
| Unwrapped *Jane Eyre* | prose | **1.23** |

Verse sits at 0.31 and hard-wrapped prose at 0.27. There is no threshold
between them. Worse, the highest variance in the set belongs to **prose**:
unwrapped paragraphs run from a few characters to 2,410, so the proposed rule
would rank ordinary novel prose as the most verse-like text available.

The premise was right about hard-wrapped prose and wrong about the comparison
class.

### The question is not the genre. It is who broke the line

A useful reframing, and it removes the need to classify texts at all:

- A line broken **by a typesetter** stops mid-phrase and continues in lower
  case, because the break fell wherever the margin was.
- A line broken **by the author** stops at a phrase boundary and the next line
  opens with a capital, because the break is part of the composition.

Measured as *"this line ends on punctuation and the next begins with a
capital"*:

| Text | Kind | Authorial breaks |
|---|---|---|
| Ballads | verse | **60%** |
| *Romeo and Juliet* | drama | **77%** |
| Hard-wrapped *Jane Eyre* | prose | **3%** |
| *The Prince* | prose | **3%** |

A twentyfold separation, from two signals that cost nothing to compute. Neither
works alone: line-initial capitals alone would catch every sentence start, and
line-final punctuation alone scores 95% on unwrapped prose, where every line is
a whole paragraph. Together they describe the break rather than the text.

### Protection must be per span, not per document

A novel contains a quoted ballad; a play contains prose scenes; a treatise
contains a table. Classifying a whole document would protect all of it or none.

So the rate is computed in a **local window**, and a run of lines whose breaks
are mostly authorial becomes a protected span. Everything outside is available
for reflow. That is also why the fixture for this has to be a mixed document:
a test on pure verse and pure prose would pass without ever exercising the
boundary, which is the only part that is hard.

### Unwrapped text needs neither protecting nor reflowing

*Jane Eyre* as stored here has one line per paragraph and a 95th-percentile
line length of 888 characters. There is nothing to rejoin. Detecting that first
avoids answering a question the document never asked.

---

## 2026-08-23 — Protected spans: measurement

| Fixture | Kind | Protected | Correct |
|---|---|---|---|
| `mixed_verse.txt` | 5 verse passages in wrapped prose | 52 of 52 lines, 5 spans | **100% precision, 100% recall** |
| `hyphenated.txt` | wrapped prose | 0% | ✅ |
| `CBronte_Jane.txt` | unwrapped prose | 0% | ✅ |
| `pg9405_ballads.txt` | verse | 89% | ✅ |
| `romeo_juliet.txt` | drama | 66% | ✅ |
| `pg1232_prince.txt` | prose | 1% | see below |

Two structural faults were found by measurement, and neither was a threshold.

### The window must stop at blank lines

Recall started at **73%**: one eight-line stanza was missed entirely. It is
enjambed ballad verse, where alternate lines run on without punctuation, so its
own evidence is thin — and the ±6 line window reached across the blank lines
into the surrounding paragraphs, which then outvoted it.

**A blank line is a structural boundary, and evidence from the block on the
other side is not evidence about this one.** Confining the window raised recall
to 92% and drama from 38% to 66%. Loosening `MIN_RATE` would have "fixed" the
same symptom by starting to protect prose, which is the one error this rule must
never make.

### A stanza cannot be half-protected

The remaining misses were all final lines of passages, which is structural
rather than accidental: the last line of a block has nothing after it to vouch
for its break, so it is always the weakest evidence in the passage.

Once a span is found it is extended to its enclosing blank-delimited block.
Protecting five lines of a stanza and reflowing the other three is not a partial
success but a corruption. That took recall to **100%**.

### A duplicate-span bug the extension introduced

Extending to block boundaries let two separate seeds land on the same block, so
*The Prince* reported the same passage twice and double-counted its lines.
Overlapping spans are now merged. **A fix that changes what a span means will
usually break something about how spans are counted**, and printing them was
what showed it.

### The apparent false positive is not one

The 1% in *The Prince* is two bibliographies:

```
Editions. Aldo, Venice, 1546; della Tertina, 1550; Cambiagi, Flore
6 vols., 1782-5; dei Classici, Milan, 10 1813; Silvestri, 9 vols.,
```

Not verse, but line-structured reference material that a reflow would also
destroy. `design-spec.md` lists tabular material among the protected
categories, so this is the rule working, not failing. Left as it is.

---

## 2026-08-23 — Reflow: baseline, and a measurement that lied

Week 9. The schedule's instruction for Friday was to run reflow on the fixtures,
expect poor results, and **log every failure without fixing any of them**. That
discipline is followed: the faults are in `design/reflow-failures.md` and none
is fixed. Fixing on the day you find them means fixing the easy ones and quietly
losing the list.

### The measurement lied before the rule did

The first run reported **4.2% accuracy**. That number was wrong.

Paragraphs were compared **positionally**, first against first and so on. A
single spurious split early in the file shifts every paragraph after it, so one
error made the whole remainder read as failure. Compared as sets, the same
output scores **96.2%**.

Both numbers measure something real, and position matters if you are aligning
to a printed edition. But quoting 4.2% as an accuracy figure would have been
badly misleading, and I nearly did. **A metric that collapses on a single
insertion is measuring alignment, not accuracy**, and the difference is
twenty-two fold here.

### The one real fault is circular evidence

All 22 spurious paragraphs come from `split_turns()`, which starts a new
paragraph at any line beginning with a quotation mark.

The reasoning is sound: typesetters do run two speeches together. The evidence
is not. **In wrapped text a line begins with a quotation mark whenever the wrap
happens to fall there.** Line position is an artefact, and it is precisely the
artefact reflow exists to remove, so using it as evidence is circular.

That makes it a category error rather than a threshold to tune, and the fix is
genuinely unobvious: telling a new speech from a mid-sentence quotation needs
evidence that survives wrapping. Left for Week 10, as scheduled.

### Reflow is offered, not recommended

Off by default, and more emphatically than the other stages. It is the one
stage the original assessment said could not be solved completely, it measures
96.2% rather than 100%, and its known faults are enumerated in a file the user
can read. A tool that reports "these thirty joins are uncertain" is more useful
than one that silently guesses, and that remains the target.

### What did not go wrong

Protected spans held: no verse passage was joined in any run. Unwrapped text
was returned unchanged rather than mangled. And **no two paragraphs were ever
merged** — every error is in the direction of splitting too much, which is the
safer one, since a wrongly split paragraph is visible and repairable whereas a
merged boundary is gone.

---

## 2026-08-23 — De-hyphenation: 96 questions was a failure, not a feature

User feedback after the first hands-on test of the review queue: *"the aim of
this software is to make things easy... the engine should have better logic to
act on its own... read the sentence to know which one. the context will tell
you."*

Correct, and the criticism lands on a real defect. The extract produced **96
questions**, and a tool that asks a linguist 96 questions about one short text
has not done its job.

### Two things were true at once

Measured on a **whole book**, which is the normal case, the old rule already
decided all 180 breaks correctly and asked nothing. The 96 questions came from
a 260-paragraph extract, where a word's only occurrence often *is* the broken
one, so "does the finished word appear elsewhere?" has no answer.

That explains the number without excusing it. Researchers load chapters and
extracts constantly.

### The evidence that was going unused

**A compound is built out of words. A broken word is not.**

`drawing-room` is `drawing` plus `room`. `def-inite` is `def` plus `inite`, and
`inite` is not a word in any text. The fragments themselves carry the answer,
and the rule was ignoring them.

The asymmetry is what makes it reliable: **a compound's left half is always a
real word.** So an unattested left fragment cannot be a compound. That single
observation settles `impio-us`, `geni-us` and `fav-our`, each of which has a
perfectly good word on the right and would otherwise read as a compound.

One more rule for short unattested tails, `-ed` and `-ly`. Length alone would
be wrong, since `check-in` and `set-up` are real compounds with two-letter
halves — but `in` and `up` are ordinary words, so they are attested and never
reach that branch. **Only a tail that is both short and absent from the
document is a bound morpheme.**

### A circularity that had to be fixed first

Asking "is `inite` a word here?" against the document's vocabulary answers
*yes*, because the broken fragment is sitting in the text being searched. The
vocabulary is now counted rather than collected, so a form is attested only if
it occurs more often than it occurs as a fragment.

### Result

| | Questions asked | Correct |
|---|---|---|
| Whole book, before | 0 | 180/180 |
| Whole book, now | **0** | **180/180** |
| Extract, before | **96** | 84/84 decided |
| Extract, now | **3** | 174/177 decided |

The three remaining are `cross-legged`, `half-comprehended` and
`object-ionable`, where the left half is a word and the right half is
substantial but unattested. Two are compounds and one is a broken word, and a
reader has to think about them too.

The extract costs about three errors for the ninety-three questions it no
longer asks. On a whole book it costs nothing, because there is nothing left to
trade.

### A test that was enforcing the bad behaviour

Three tests failed on the improvement, all asserting the queue held *more than
ten* items. They had quietly encoded the thing the user objected to. **A test
that demands a long review queue fails on the day the tool gets better**, which
is exactly what happened.
