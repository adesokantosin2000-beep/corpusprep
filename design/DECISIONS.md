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

---

## 2026-08-23 — What to do when the evidence runs out

Further feedback, after the queue dropped to three items: *"even with that, it
is difficult to know the correct form of hyphenation. if hyphen is in the raw
text, it should just be retained. what is the issue here?"*

### The premise was already true, which is what made the complaint valid

When the rule cannot decide, it already keeps the hyphen. So the three
remaining items were not cases where anything was about to be damaged. They
were cases where the source form had been preserved and the reader was then
**asked about it anyway**.

That is the defect. A question whose default answer is already correct is not a
question; it is a notification dressed up as work.

### Why "always keep the hyphen" cannot be the whole rule

Worth stating plainly, because the instinct behind it is sound. At a line break
the hyphen may belong to the typesetter:

```
    ... it was an exam-
    ple of the kind ...
```

Keep that one and the corpus contains `exam-ple`, a token that exists nowhere,
where the book had `example`. A hard-wrapped novel contains hundreds. That is
the entire reason the rule exists, and it is why 177 of 180 are still decided
rather than left alone.

### But it is the right default for the remainder

Two reasons, and the second is the stronger:

1. It preserves the source, which is this package's posture everywhere else.
2. **The error it produces is visible.** `object-ionable` is obviously wrong to
   anyone scanning a word list. `crosslegged` looks like a word and survives
   proofreading unnoticed.

Given a choice between an error a researcher will catch and one they will not,
take the first every time.

### What changed

Nothing in the algorithm. The interface now reports rather than demands:

    180 found · 177 settled from this text itself · 3 kept exactly as printed

    ...they are left with the hyphen exactly as the source prints them.
    Nothing is required of you.

The review button is now secondary and reads *"Look at the 3 kept hyphens"*.
The reviewer itself says *"The hyphen is kept unless you say otherwise."*

**A tool should not ask a question it has already answered acceptably.** Review
is for the reader who wants to overrule a default, not a queue of chores
generated by the tool's own uncertainty.

---

## 2026-08-23 — A contents list read as the book

Reported from real use, from a line that survived footnote removal:
`YOUTH — Æt. 1-25—1469-94`.

That line is not a footnote, and the tool was right to leave it. Looking into
why it was there at all found something much worse.

### What was actually happening

*The Prince* opens with a 26-entry contents list. Every entry had been read as
a **one-line chapter**, and the region after them swallowed all 473 lines of
the translator's biographical introduction under the title `CHAPTER XXVI`.

So `body-only` was keeping a 1908 editorial essay and presenting it as
Machiavelli, and the segmentation showed 42 regions where there are 17.

**This is the worst failure this tool can have.** It is not a missed
transformation; it is a corpus that silently contains the wrong text.

### Two faults, compounding, neither a threshold

**1. A heading longer than 80 characters was not recognised at all.**

Six of Machiavelli's chapter titles run past that, the longest to 125
characters. Losing them broke the contents list into short runs, so the
close-packed test never saw a list.

Length was standing in for the real discriminator, which is that a heading's
title begins with a capital and does not continue into prose. A longer line is
now admitted if its title is **entirely upper case**: prose does not sustain
capitals for ninety characters, and the pattern already requires a division
word and an enumerator at the front. `Chapter 5 was the morning everything
changed for her...` is still refused.

**2. Contents entries were matched to headings by printed text.**

A contents list prints

    CHAPTER I. HOW MANY KINDS OF PRINCIPALITIES THERE ARE

while the chapter itself is headed

    CHAPTER I.

Compared as strings, 0 of 26 matched. Compared on division word and number, 12
of 26 do.

### And a third thing, which the fixture exposed

12 of 26 is 46%, below the 60% bar. Not a fault in the rule: the fixture is
truncated at Chapter XIII, so fourteen chapters genuinely are not there.

Real users load extracts constantly, so a ratio alone is too brittle. The
stronger signal costs nothing: **a real chapter heading is followed by prose.**
Twenty-six headings inside twenty-six lines is a list of chapters, not a
sequence of them, and nothing else in a book looks like that. Where the
headings leave no room for text between them, a lower duplication bar is
accepted — but some duplication is still required, so a document that is
*only* a contents list keeps it rather than being emptied.

### Result

| | Before | After |
|---|---|---|
| Regions | 42 | 17 |
| Contents list | 26 body "chapters" | one front-matter region |
| Translator's biography | body, as `CHAPTER XXVI` | front matter |
| Segmentation accuracy | 99.99% | **99.99%, unchanged** |

### What this says about the test suite

The accuracy figure did not move, because no answer key covers this file. The
suite was measuring four texts thoroughly and this one not at all, and a real
reader found in one session what 362 tests could not.

`pg1232_prince.txt` was added as a *footnote* fixture, and its segmentation was
never checked. **A fixture added to test one rule is silently exempt from every
other rule**, which is worth remembering for the next one.

---

## 2026-08-23 — The first real scan, and what it broke

A user downloaded *The New Wizard of Oz* from the Internet Archive and ran it
through the tool. `body-only` returned 41,258 tokens containing the Archive's
EPUB notice, Google's full usage guidelines, a Stanford catalogue stamp and
several pages of pure OCR noise.

This ended a blocker open since Week 2. Every previous fixture was a Gutenberg
transcription, from which volunteers remove page furniture by policy, or
something I generated.

### What raw OCR actually looks like

Nothing I had built for.

**One page per line.** 269 non-blank lines for a whole book, median length
1,080 characters, longest 2,955. Headings are buried *inside* those lines:

```
LIST OF CHAPTERS I. ThB CrCLONE I IL The Council with the Munchkins 7 II...
INTRODUCTION p^LR lore, legends, myths and fairy tales have followed chi...
```

**Three kinds of apparatus, none of them Gutenberg.** The Archive's notice,
Google's scanning notice, and a per-page OCR confidence line.

**Text damaged even where the page is legible:**

```
lived in the midst of the ^ ^'^^ great Kansas prairies, with Uncle ^y^
```

### The scanner tells you which pages are rubbish

The most useful thing in the file, and I had been ignoring it. Above each page
it doubts, the Archive prints:

```
The text on this page is estimated to be only 4.93% accurate
```

28 such pages, **every one under 50%, median 5.1%**, and beneath each is text
like `/ .•;?(^ V //'^i .^< .r/<vrr./;-/`.

**This is the only rule in the package that infers nothing.** Every other rule
has to work out what a line is from its shape or its neighbours. Here the
digitisation pipeline has already done the work and written the answer down,
and the tool's only job is to believe it.

The region reports the figure — `Unreadable page (4.93% accurate)` — rather
than a generic label, which meant running it *before* the generic apparatus
rule. The note and its page share a blank-delimited block, so whichever rule
runs first claims both, and the one that knows the number should win.

### Result

| | Before | After |
|---|---|---|
| `body-only` tokens | 41,258 | **39,760** |
| Archive notice, Google guidelines, catalogue stamp | in the body | removed |
| Pages the scanner calls unreadable | in the body | 28 regions, each reporting its figure |
| The story | present | present |

1,498 tokens of apparatus removed, 479 of them pure OCR noise.

### What is still wrong, and it is the bigger half

**No chapters were found.** The book's headings are inside 1,000-character
lines, and every structural rule here looks for a heading as a whole line. The
segmenter returns 23 undifferentiated `body` regions instead of 24 chapters.

This is not a small gap. It means `body-only` on a scan of this shape keeps the
title page, the introduction, the contents list and the dedication, because
none of them can be told apart from the text.

Recorded rather than fixed. It needs headings to be found *within* a line,
which is a different rule from the one that exists, and it is the right first
task for Week 12.

---

## 2026-08-23 — Page furniture is a line PREFIX in page-per-line OCR

Week 12, on paper before any code. This reframes the furniture detector rather
than extending it, so it is worth writing down first.

### What the real scan actually contains

Investigating why no chapters were found in the Internet Archive scan turned up
something more important. The capitalised runs at the start of those long lines
are not chapter headings. They recur:

```
    9 x  WONDERFUL [EMERALD CITY OF OZ]
    7 x  DISCOVERY [OF OZ THE TERRIBLE]
    6 x  THE RESCUE
    6 x  SEARCH FOR [THE WICKED WITCH]
```

**They are running heads.** And what follows each is the page number, mangled
by OCR:

```
WONDERFUL EMERALD CITY OF OZ  loi  fore I have no brains, and I c...
THE COUNCIL WITH THE MUNCHKINS  ii  *'But who was she?" asked Dorot...
SEARCH FOR THE WICKED WITCH  iii  one is a girl and another a Li...
```

`loi` is 101. `iii` is 111. `IffJ` is 108.

**92 of 269 non-blank lines carry one.** Every one of them is page furniture,
and the detector finds none of it.

### Why the existing rule cannot see them

Every furniture rule in `furniture.py` assumes furniture occupies **its own
line**. That is true of plain-text transcription, where a page break is a line
break. It is false of page-per-line OCR, where a whole page is one paragraph
and the running head is simply the first words of it.

The signal itself — regularity, and a page-number series that counts upwards —
is unchanged and still correct. What changes is where to look for it.

### The shape of the fix

Treat a **line prefix** as a furniture candidate:

1. Take the leading capitalised run of each line, up to the first ordinary word.
2. Group and score exactly as now: recurrence, interval regularity, and
   corroboration against an ascending page-number series.
3. Remove the prefix from the line rather than the line from the document.

That last point is the whole difficulty. Every existing furniture rule marks a
line for deletion; this one must edit a line in place, which is a different
operation with a different failure mode. **Deleting a whole line when the rule
is wrong loses a page; deleting a prefix when the rule is wrong loses the first
few words of a page**, which is quieter and therefore worse.

So it needs the same treatment as de-hyphenation: decide where the evidence is
strong, leave the line untouched where it is not, and report the count.

### Why this is not being built today

It changes what "furniture" means, from a set of line numbers to a set of
edits. That touches `Document`, both engines, the parity harness and the log.
It is a week's work rather than an afternoon's, and starting it at the end of a
long session is how the careful parts get skipped.

Recorded with the measurement attached so it can be picked up cold.

### Consequence for the chapter problem

The chapters cannot be found until this is done. The chapter headings in this
scan are also line prefixes, sitting where the running head would be at the
start of a chapter. Splitting the prefix off is what makes them visible, so one
change answers both.


---

## 2026-08-23 — Prefix furniture: built and measured

Built as designed the same day, which the design note had argued against. It
went quickly because the design had already separated the hard part from the
easy one.

### Result on the real scan

| | |
|---|---|
| Running heads found | **74** |
| Words removed | 408 |
| Untouched lines altered | **0** |
| Both engines agree | line and cut position, all 74 |

`body-only` with furniture removal falls from 39,760 to 39,410 tokens.
`WONDERFUL EMERALD CITY OF OZ` no longer appears anywhere; the story does.

### The guards, and why each is there

**The text must be page-per-line.** Median non-blank line length of 200
characters or more. Below that, the line-based rules are the right ones and
running this as well would edit lines for no gain. Every other fixture in the
repository is left entirely alone by this rule, and a test asserts it.

**The prefix must recur, at least three times.** This is the whole of the
safety argument. A running head opens many pages; a chapter title opens one.
`THE CYCLONE` and `AWAY TO THE SOUTH` appear once in this scan and are
untouched, while `WONDERFUL EMERALD CITY OF OZ` opens nine pages and goes.

**The file must have at least twenty lines.** A file too short to show a shape
should not be judged to have one.

### The trade this rule makes, stated plainly

Every other furniture rule marks a line for deletion. This one edits a line in
place, and the failure modes are not equivalent. **Delete a line wrongly and a
page vanishes, which a reader notices. Delete a prefix wrongly and the first
few words of a page vanish, which a reader does not.** The quieter error is the
worse one in a tool whose proposition is that its output can be audited.

That asymmetry is why the bar is three occurrences rather than two, and why the
rule refuses to run at all on text of the wrong shape.

### A test that lied twice while I wrote it

The synthetic case for "a heading appearing once is never stripped" failed
twice, both times because the test data was wrong rather than the code.

First it built twelve lines, below the twenty-line floor, so the rule declined
to act and nothing was stripped. Then it built headings distinguished only by a
trailing digit — and `normalise` strips digits, deliberately, so that
`JANE EYRE 42` and `JANE EYRE 43` group as one head. Twelve "unique" headings
were one heading twelve times over.

**Both failures were the test misunderstanding a rule that was working.** Worth
recording because the instinct on a red test is to suspect the code.

### What this does not fix

The chapters are still not found. Stripping the running heads makes the chapter
titles visible in principle, but the segmenter still looks for a heading as a
whole line and these sit at the front of one. That is the next piece, and it is
now a smaller one.


---

## 2026-08-23 — Verso and recto: the half that was invisible

Chasing the missing chapters found the missing half of the running heads.

The chapter openings could not be located, so the question became where each
running-head series *begins*. Printing the line before each one showed this:

```
46 THE WONDERFUL WIZARD OF OZ  from some wild animal hidden among the trees...
54 THE WONDERFUL WIZARD OF OZ  lonely. She and Toto ate the last of their...
6o THE WONDERFUL WIZARD OF OZ  his axe at once, and, just as the two Kalidahs...
```

**The page number comes first.** Books set the book title on the verso and the
chapter title on the recto, and the page number sits on the outer edge — which
puts it *before* the title on a left-hand page and *after* it on a right-hand
one. The original Week 2 design anticipated the alternation and looked for it in
the interval between occurrences; in prefix form it changes the shape of the
line itself.

Requiring a capital at the start caught **74 and missed 88**. The invisible half
was the larger half.

### And the same OCR fault as the very first measurement

Allowing a leading number took the count to 149, leaving seven pages behind.
The cause was familiar: `normalise` removes digits so that `JANE EYRE 42` and
`JANE EYRE 43` group as one head, but OCR leaves residue a digit-strip cannot
reach. `6o` for 60 keeps its `o`; `io6` for 106 keeps `io`. Folded into the
group key, one running head becomes several, each too rare to reach the
threshold.

The page number is now captured separately and the grouping is on the title
alone. **155 heads, 895 words, and one stray occurrence of the book title left
in the whole file.**

This is the third time OCR damage has split a series that the rule was right
about. The lesson has been the same each time: **when a detector finds most of
something and misses a handful, suspect the key before the threshold.**

### Result

| | |
|---|---|
| Running heads removed | **155** |
| Words removed | 895 |
| Untouched lines altered | **0** |
| Both engines agree | line and cut position, all 155 |


---

## 2026-08-23 — Where the chapters were hiding

The goal was to find the chapters in the Internet Archive scan. They are found,
and not where anyone would look for them.

### The chapter titles are not in the text

There are no chapter headings in this book's body at all. The chapter opening
pages carry decorative drop-capitals that OCR has destroyed:

```
^^^^ Dorothy awoke ^^^|[ %, the sun was shining through the trees...
11 §W^^ little party of travel*^ ^ lers awakened the next morning...
iWwas some time before the Cowardly Lion 1 awakened...
```

`A little party of travellers awakened the next morning`. The title that should
head that page is simply absent.

**But the titles do appear — as running heads.** Every page of a chapter is
headed with that chapter's title, so the title survives dozens of times over
even though it appears nowhere as a heading.

### So a new running-head series IS a chapter boundary

Grouping the prefix edits by title and discarding the book title, which is the
verso head, gives the chapter structure directly:

```
line  58  ( 5 pages)  the council with the munchkins
line  78  ( 4 pages)  dorothy saved the scarecrow
line  98  ( 3 pages)  the road through the forest
line 122  ( 3 pages)  the rescue of the tin woodman
line 138  ( 3 pages)  the cowardly lion
...
line 446  ( 4 pages)  the dainty china country
```

**18 of the book's 24 chapters, in order, with correct titles.** Those are
Baum's actual chapter titles, recovered from a text that contains no headings.

The six missing are chapters whose head series is too short or too badly
mangled to group: Chapter 1 appears as `THE CYCLONE 3` and `THE CYCLONE 5`,
only twice, below the threshold.

### Why this is worth more than a heading rule

A heading rule reads what the typesetter wrote once. This reads what the
typesetter repeated on every page, which in a damaged scan is far more evidence
and survives far more damage. **The redundancy of print is a resource, and OCR
destroys it unevenly rather than uniformly.**

### The fourth OCR merge

Getting from 155 heads to 162 needed near-duplicate merging on the prefix
groups, which the line rule has had since Week 2: `WIZARB>` for WIZARD,
`W0NBERFUL` for WONDERFUL, `QZ` for OZ, `DOROXrHY` for DOROTHY.

**Four times now a rule has been right and its groups have been split by OCR.**
The reflex should be automatic by this point: when a detector finds most of
something and misses a scattering, look at the key before the threshold.

### Not yet built into the segmenter

Deriving regions from head series would touch `Document`, both engines, the
parity harness and the log, and this has been a long day. The measurement is
recorded so it can be picked up cold.


---

## 2026-08-24 — Chapters from running heads: built

Yesterday's finding turned into a fourth heading tier. Three faults came out of
it, and as usual they are worth more than the feature.

### Telling a chapter title from the book title

Both are running heads. The book title is also the more frequent, so counting
settles nothing. The difference is structural:

> A chapter's series occupies a contiguous stretch and **no two chapters
> overlap**. The book title runs the length of the volume and therefore
> overlaps every chapter there is.

So the most-entangled series is dropped repeatedly until the survivors are
mutually disjoint. On the Oz scan that removes `THE WONDERFUL WIZARD OF OZ`,
which overlaps eighteen others, and then `THE WONDERFUL`, a truncated variant
overlapping twelve. **Neither is special-cased and no stop-word list exists;
both fail the same test.** Seventeen disjoint series remain, in order.

That is the whole discriminator. No threshold, no list of book titles, nothing
to tune.

### Fault 1 — the tier quietly deleted chapter one

The first run passed every apparatus test and lost the opening of the book.

`body_start` is the first heading found. Chapter 1 is headed `THE CYCLONE` on
only two surviving pages, below the threshold, so the first series found was
chapter 2 — and everything before it, including the Kansas prairies and the
cyclone itself, was relabelled front matter and dropped from `body-only`.

**A tier whose known weakness is missing series cannot be trusted to say that
nothing precedes the first series it found.** The run-up is now kept as body
under the title `(opening, chapter not identified)`, which states exactly what
is and is not known. Carrying a preface into the body is visible in the output;
losing a chapter is not.

It was caught only because an existing test asserted `"Kansas prairies" in out`
rather than merely asserting the boilerplate had gone. **A test that checks
only that the bad thing left will pass when the good thing leaves with it.**

### Fault 2 — the parity harness agreed about nothing

The prefix rule gained near-duplicate merging in Python. The JS engine went a
full day without it, 162 heads against 155, and `check_parity.py` reported
agreement the whole time.

Not a bug in the comparison this time. **No fixture in the harness was
page-per-line, so neither engine ever ran the rule.** Agreement on code that
does not execute is not agreement.

Both scans are now in the harness. They are slow and they are worth it.

### Fault 3 — three words that were not words

Adding Frankenstein to the harness immediately produced a mismatch: 78,724
tokens in Python, 78,727 in JavaScript.

Its footnote backlinks are an arrow followed by a VARIATION SELECTOR. The JS
pattern was `[\p{L}\p{M}]+`, which lets a token *begin* with a combining mark,
so each selector counted as a word. A token must now begin with a letter.

The mirror-image fault sat in Python, unnoticed because no fixture triggered
it: `[^\W\d_]+` excludes combining marks entirely, so `café` written as `e`
plus a combining acute tokenised as two words. Both engines now normalise to
NFC before counting. **The text is not touched; only the counting is.**

Two implementations of the same rule disagreeing in opposite directions is the
argument for keeping both.

### Where it does not fire

Frankenstein is genuinely page-per-line — median line 396 characters — so the
rule runs on it and returns nothing: no running heads, and the book segments on
its own numerals as it always did, 24 chapters. Regression-tested explicitly,
because a heading rule that invents chapters is worse than one that finds none.


---

## 2026-08-24 — Nothing is reported before the button is pressed

Two things reported from use, and the first is the more interesting.

### A number that looks like an outcome is an outcome

After loading a file the page reported, beside an unpressed Clean button:

```
Segmentation summary
  41 sections · 8 to be removed
  Words broken across lines — 180 found · 177 settled from this text itself
  [ Look at the 3 kept hyphens ]
```

Every figure there is *detection*, not cleaning, and every one is true whether
the button is pressed or not. The defence is technically sound and it misses
the point: **the reader cannot tell the difference, and the whole proposition
of this tool is that they decide what happens and then see what happened.**
Announcing the result first makes the button look decorative.

So the counts wait. What stays is what is needed in order to choose — the
structure, the section list, the options themselves — and what goes is every
figure describing an outcome: how many sections would be removed, how many
breaks were found, how many were settled, the review queue and its size.

A section outside the current selection is now dimmed rather than struck
through. Struck-out text before the button is pressed states an outcome that
has not happened; dimming states a selection, which is what it is.

This is the same distinction the package has held everywhere else and had not
applied to its own interface. Detection labels; removal is a separate, explicit
step. **The reporting has to obey that too, or the guarantee is only true
underneath.**

### The page stops answering and does not say so

Cleaning is synchronous. A Gutenberg novel takes about 40 ms; the 45 MB
Internet Archive scans take several seconds, during which the page does not
respond and nothing indicates why. That is indistinguishable from a broken
button.

The button now shows a working state, and `runClean` yields before starting so
the browser can paint it. **Two yields, not one:** the class change and the
paint are separate frames, and a single `setTimeout` can land between them,
which showed the spinner only after the work had already finished.

`MIN_BUSY_MS = 700` is a floor rather than a delay. Without it the indicator
flashes and is missed on small files. With it, anything slower than 700 ms
shows for exactly as long as it actually takes — the tool never pretends to be
busy, and never fails to say when it is.

A fixed three-second wait was the request and would have been the wrong build:
it spends the reader's time on every run of every file to reassure them once.


### The same fault twice, in the same afternoon

The first attempt gated the hyphen panel and the summary, and left the footnote
and page-furniture panels reporting theirs. Reported straight back: *"the
results is still there before I clicked clean."*

Correct, and the reason is worth naming. **The fix was applied to the panels I
happened to be looking at rather than to the rule.** The rule is that no panel
reports a finding before the button is pressed, and it should have been checked
against every panel at once — which is now what the interface test does, by
searching the whole segmentation view for outcome language rather than
inspecting one panel.

### The one real objection, and why it was overridden anyway

The page-furniture panel carried this reasoning in its own comment:

> Shown whether or not the reader intends to remove it. A detector that acts
> silently cannot be checked, and the cost of a wrong removal here is deleted
> prose. The reasoning is printed in full so that a mistaken judgement is
> visible **before** it is acted on rather than discovered afterwards.

That is a real safety argument and holding the table back appears to weaken it.
It does not, for two reasons: furniture removal is off unless the reader turns
it on, and cleaning writes nothing to disk. The evidence is still visible before
anything leaves the tool — just not before the first run rather than not before
export.

Recorded rather than quietly reversed, because the argument was sound when it
was written and the constraint that overrode it is a different one.


---

## 2026-08-24 — Less on the screen

Reported: the explanations of what the tool does and will do look bad, remove
them.

The opening screen carried a paragraph of positioning, a four-step diagram of
the pipeline, a capabilities list including everything not yet built, and a
closing instruction. **All of it is read once and then is furniture**, which is
a word this project ought to have recognised sooner.

Now: one heading, one sentence, and where to put the file. The capabilities
list is kept behind a closed disclosure rather than deleted, because listing
what is *not* implemented is a commitment made deliberately — a researcher
should meet the limits before choosing the tool, not halfway through a project.
That commitment survives one click. Four paragraphs of it on first sight does
not survive contact with a user.

The option panels were the same fault at smaller scale. Each carried a
paragraph explaining the reasoning behind its rule:

> A line break inside a word is always an artefact, but the hyphen may be real:
> to-morrow is a word and tomorrow is a different one. Each case is settled
> from the surrounding text — whether the finished word appears elsewhere, and
> whether both halves are words in their own right, since a compound is built
> out of words and a broken word is not.

Accurate, and it sits above a checkbox. Cut to two lines. **The reasoning
belongs in the log, which is written for exactly this purpose and which the
reader reaches when they want it, rather than beside a control they are trying
to use.**

Dead CSS for the removed markup was deleted rather than left. In a single-file
application every unused rule is weight on every load and a trap for whoever
reads it next.


---

## 2026-08-24 — The capability list was three releases out of date

Asked, on reading the list in the interface: *"have we not done all of them?"*

Mostly yes. Of the four items marked **planned**:

| Listed as planned | Actually |
|---|---|
| Identifies page numbers, headers and footers | shipped in v0.3.0 |
| Rejoins hyphenated line breaks | shipped in v0.4.0 |
| Reflows hard-wrapped paragraphs | shipped in v0.5.0 |
| Cleans OCR artefacts | genuinely not implemented |

And six capabilities built since were not listed at all: footnotes, catchwords,
digitisation apparatus, protected spans, the review queue, chapter recovery
from running heads.

Worse than the count, the description was wrong in a way that mattered:

> Rejoins hyphenated line breaks — **wordlist-validated** de-hyphenation

A bundled wordlist is precisely the approach that was tried, measured and
rejected: 234,000 words of modern English recognise only 65% of the word types
in *Jane Eyre*, so requiring dictionary confirmation refuses a third of the
legitimate joins and fails worst on exactly the historical material this tool
is for. The interface was advertising the discarded design.

### The point

**This list exists to be honest about limits, and it went stale in the
direction that flatters.** Under-claiming is the safer direction and it is
still a false statement about the present, and it was found by a user reading
the screen rather than by anything in the repository.

So it is checked now. `tools/ui_test.js` asserts that each shipped capability
is not still marked planned, and that PDF and OCR repair still are. Both
directions, because both mislead: one hides work, the other invites a
researcher to start something the tool cannot finish.

**A capability list that is not maintained is worse than none**, because it is
read as a claim about the present rather than a note about the past.


---

## 2026-08-24 — Stage order: the task as scheduled could not be done

Week 12, Wednesday. The instruction was *"enforce dependencies in code, not in
documentation"*, complete when *"wrong order is refused with an explanation"*.

**There is nothing to refuse.** `Variant` has no ordering field and there is no
pipeline configuration anywhere; the stages are five statements in one
function. A user cannot express a wrong order, so a runtime guard would be
protecting against a thing that cannot happen.

The risk is real but it is somewhere else: **a future edit moving the
statements.** Which is exactly what happened. The Week 9 commit shipped reflow
before de-hyphenation, dissolved the line breaks de-hyphenation exists to
repair, and recovered 81 of 166 broken words instead of 162. Nothing failed,
and the comment saying *must run before* was already in the file.

**A comment cannot fail.** That is the whole lesson, and it is why the
scheduled task was worth redefining rather than skipping.

### What was built instead

`STAGE_ORDER` in `variants.py` names the five stages with the reason each sits
where it does. Both engines carry a marker at each stage, and the test asserts
that the markers appear in the declared order — in Python and in JavaScript.

A second test measures the cost rather than asserting it: it runs reflow first
and counts how many breaks survive for de-hyphenation to find. Almost none do.
That is the test that would have caught Week 9.

### The guard was checked by breaking it

A test that has never failed is a test nobody has verified. Reordering the
markers in Python fails the Python check; reordering them in JavaScript fails
the JavaScript check; restoring both passes. Recorded because the temptation
with a structural check is to write it, watch it pass, and assume it works.


---

## 2026-08-25 — PDF, and a failure mode that was not in the design

Reprioritised on the user's argument, which was the right one: **OCR text lives
in PDFs.** The two EPUB scans were the exception, and a researcher with a
folder of PDFs currently cannot use this tool at all.

Three real PDFs, three different outcomes, and the important one was not among
the three I predicted.

### The design said there were three kinds of PDF

    text     a usable text layer
    ocr      a text layer written by OCR over page images
    image    no text layer; nothing to extract

**There is a fourth, and it is the dangerous one.** Sinclair's *Basic Text
Processing* (1991), a 25-page scan: extraction succeeds, raises nothing, and
returns **930 non-blank lines in which every character is byte 0x01**. The
fonts are subsetted — `AAAAAB+font000000002f28b5b2` — with broken character
maps, so the glyph codes never become letters.

A check of the form *did we get any text?* answers **yes, 930 lines**, and
hands the researcher a corpus of control characters.

That is exactly the silent failure this package exists to prevent, and it
appeared within an hour of PDF work beginning. **The test is not whether text
came out. It is whether what came out is language:**

    if the extracted text contains almost no letters, the extraction failed,
    however much of it there is.

`MIN_LETTER_RATIO = 0.35`. Prose runs 70–80% letters; the Sinclair file scores
0.0%. Nothing observed sits between, so the threshold is set clear of both
rather than tuned — and low rather than high, because the cost of a false alarm
is a message and the cost of a miss is a corpus of control characters.

The ratio is Unicode-aware. An ASCII-only test would report a perfectly good
Yoruba or Polish extraction as broken.

### Refused, not returned empty

`UnreadablePDF` is raised rather than a Document with no lines being returned,
because **a Document with no lines looks like a very short book.** The caller
has to be made to notice; that is the entire point of the class.

### The gift of the format

Every other input forces the furniture rules to infer where pages begin, from
an ascending run of page numbers. That inference is the most fragile thing in
the package and it is what destroyed 63 lines of a ballad collection in Week 2.

**A PDF states it.** `page_starts` is recorded on the Document. The Fagunwa
file puts its page number on the *first* line of each page — `v`, `vi`, `3`,
`4`, `5` — so with the boundaries known, the tool can *verify* a page-number
series rather than infer one. Not yet used by the rules; recorded as the next
PDF task, because it turns a guess into a fact.

### One dependency, optional

`pypdf` is the first dependency this package has taken, and zero dependencies
was a real selling point. It is imported lazily and its absence produces an
instruction rather than a traceback, so everything except PDF still runs on the
standard library alone.

### The web application is deliberately left alone

PDF in the browser needs `pdf.js`, which is large and normally loaded from a
CDN, so the app would stop being one self-contained offline file. The research
value is in the Python package and arrives today; the single-file property
survives until there is evidence anyone needs PDF in the browser.

### A stale refusal, found on the way

`formats.py` still refused PDFs with advice to export them to `.docx` first,
citing limitations — hyphenation and reflow — that were fixed three releases
ago. Nothing reaches that message any more, and **a refusal naming a
limitation the tool no longer has is worse than no message at all.** Same fault
as the capability list, in a different file.

### The fixtures are not in the repository, deliberately

All three PDFs are in copyright and came from a shadow library. They are used
locally and kept outside the repository, which is public, MIT-licensed and
attached to a name that is about to appear on a thesis. **The findings are
committed; the files are not.** Public-domain PDFs with the same properties are
needed before any of this can be regression-tested, and the Internet Archive
has scans with the same broken-font problem.


---

## 2026-08-25 — Furniture from a stated boundary rather than a guessed one

Four more PDFs arrived, and the distribution is the finding before any rule is
written:

| kind | n |
|---|---|
| usable text | **2** |
| unreadable text layer | 1 |
| no text layer at all | 3 |
| empty file | 1 |

**Five of seven PDFs cannot be extracted.** Checked against a second library
before trusting it — `pypdf` and `pdfplumber` both return zero characters on
the image-only three, one image per page. Telling a researcher to re-OCR a file
whose text was extractable would be a serious false refusal, and that was worth
two minutes to rule out.

This reframes what PDF support is *for*. The assumption was extraction. On this
sample the more useful service is **triage**: telling a researcher in seconds
which of their files need OCR before they lose an afternoon to one.

### The rule the other ones wish they were

Barthes' *The Death of the Author*, an 8-page extract, carries a running head
on every page, alternating verso and recto:

```
The Death of the Author I 143      recto: essay title, page number
144 I IMAGE - MUSIC - TEXT         verso: page number, book title
```

`find()` detects **none of them.** Eight pages gives too few repeats to clear
`MIN_OCCURRENCES`, and with no ascending numeral series it cannot estimate a
page length either.

The information was in the file the whole time. **Every other format forces
this package to reconstruct page boundaries from the text; a PDF states them.**
So `find_edge_furniture` asks only *does this line open or close many pages* —
no coefficient of variation, no page-length estimate, and no threshold that has
to be defended against fixed-stanza verse. The inference that destroyed 63
lines of a ballad collection in Week 2 is simply not performed.

**7 of 8 page heads found, against 0.**

Where boundaries are stated they are used *instead of* inference, not alongside
it. A fact does not need corroboration from a guess, and running both would
reintroduce the risk for the sake of a handful of extra lines.

### The fifth time, in a rule written after noticing the fourth

The first version found nothing on Barthes either, because OCR damage split
both series into groups of one:

```
the death of the author i     p3, p5
the death of the a uthor i    p7      A.uthor
i image music text            p4
i image mu ic text            p6      MU~IC
i imagb music tbxt            p8      IMAGB, TBXT
```

This is the **fifth** time a rule has been right and had its groups split by
OCR — and the second time in a rule written *after* the note saying the reflex
should be automatic by now. Writing it down is evidently not the same as
having learnt it.

### Two things about clustering that were not obvious

**Damaged copies drift further from each other than from the clean form.**

```
i image music text  vs  i image mu ic text   0.944
i image music text  vs  i imagb music tbxt   0.889
i image mu ic text  vs  i imagb music tbxt   0.833   <- below threshold
```

Comparing every candidate against a seed under-merges, because two damaged
variants may fail to resemble each other while both resemble the original.
Linkage through *any* member is required.

**And one pass is not enough.** Seeded on `i imagb music tbxt`, the scan
reaches `i image music text` at 0.889 but has already passed `i image mu ic
text` at 0.833 — which becomes reachable at 0.944 only once the first has
joined. Sweeping until a pass adds nothing is what makes this single linkage
rather than a seeded comparison.

No size guard here, unlike the line rule. That guard stops two genuinely
distinct heads of similar frequency merging, and it is unnecessary when every
candidate already sits at a stated page boundary — with it, nothing merges at
all, since all five groups have one or two members.

### The fixture invented a failure that no page has

Two faults in the test, both mine, both worth recording because they are the
fixture trap running backwards.

Body lines written as `body line {i}.{j}` all normalise to `body line`, digits
being stripped by design — so every page ended with an identical string and the
rule correctly reported eight running *feet*. Real pages do not end in a fixed
template. The fixture manufactured a failure, and it took a minute to see that
the rule was right and the data was wrong.

Then, damaging a *recto* page with a *verso* head, which is not a thing a
scanner does, and which quietly moved a page between series.

### Known imprecision, recorded rather than special-cased

The recto group has four members and one of them is page 2's `The Death of the
Author` — the essay's actual title on its opening page, not a running head. It
is 0.958 similar to the head and merges. One line, reported for review, and
furniture removal is off unless requested. Left as it is: a guard for "titles
on opening pages" would be a rule about position guessing at intent, which is
the kind of thing this package has been wrong about before.


---

## 2026-08-25 — A corpus that was 45% URL

A tester cleaned an Instagram comment thread and reported that nothing much
changed. It was the most useful thing anyone has reported.

Her file, exported through a Markdown converter:

```
[bymiracohen](https://www.instagram.com/bymiracohen/)
 [9 w](https://www.instagram.com/p/C6-u-LzNtxQ/c/18439282027191808/)
Love what you're creating 🌍 fellow AI here navigating the world
```

Her twelve most frequent words:

```
https · www · instagram · com · c · gram · p · u · lzntxq ·
shudu · explore · tags
```

**Not one of them was typed by a human.** `lzntxq` is a fragment of the post's
URL. After the link targets go: `that`, `shudu`, `ai`, `we`, `black` — which
is her actual data, and `black` and `ai` are precisely what a study of that
thread would be about.

**45% of the file was inside URLs.**

### Not a new domain. A missing reader.

The first reading of this was "social media is out of scope", and that was
wrong. `extract_html` has discarded tags since the beginning, on the grounds
that markup is not language. Markdown is markup with a friendlier face.
**A tool that reads HTML and not Markdown has a gap rather than a boundary.**

Worse: the file picker already offered `.md`. The application advertised a
format it did not read, so the file loaded as plain text and every character
of every link target became a word. **Offering a format and not reading it is
worse than refusing it**, because the failure is silent and the user concludes
the tool does nothing.

Link *text* is kept and the target discarded. `[@shudu.gram](https://…)`
becomes `@shudu.gram`: the handle is something a person wrote and may well be
the object of study, while the URL is scaffolding the converter added.

### The reader renamed someone

The first version treated `_` like `*` and turned `@michaelaseewald_v24` into
`@michaelaseewaldv24` — silently renaming a person while removing 46% of the
file it was meant to clean.

CommonMark forbids intraword `_` for exactly this reason: `snake_case`.
Usernames, hashtags and file paths are full of underscores, and **social media
is precisely where this reader is most needed**, so the one place the rule
matters is the one place it was wrong.

### The harness agreed about a reader neither engine had run

Adding the fixture produced a 65-token difference, which was not engine drift:
`check_parity.py` keeps its *own* list of container extensions and nobody
updated it, so it read `.md` as plain text on the JS side only. A third list
of extensions, after `formats.SUPPORTED` and `is_container`.

Fixing that revealed a second fault underneath. Markdown was then classed with
docx, epub and html as needing a DOM — and with jsdom absent it was **skipped
entirely**, so the harness printed PASS on a check that had not run. Markdown
is regular expressions and needs no DOM.

*"Needs extraction"* and *"needs a DOM"* are different questions, and
conflating them hid the very thing being added. **This is the second time in
three days that the parity harness has reported agreement on code it never
executed.**


---

## 2026-08-25 — PDF in the browser, and the property it costs

The Python package has read PDFs since this morning. The web application is
where testers actually work, and it could not open one at all.

### What it costs, stated plainly

`pdf.js` is fetched from a CDN. **This is the first external dependency the
application has ever had**, and "runs offline from one file" was a real claim,
not decoration.

It is loaded **lazily**, only when a PDF is opened. TXT, Markdown, DOCX, EPUB
and HTML are unchanged: one file, no network, nothing fetched. The honest
statement is no longer *this works offline* but *this works offline unless you
open a PDF*, and the interface now says exactly that.

**The privacy claim survives intact and the distinction matters.** pdf.js is
downloaded *to* the browser; the document is not uploaded anywhere. A reader
who cannot use the network at all still has every other format, and the Python
package reads PDFs without it.

### The two engines cannot agree, for the first time

Python reads PDFs with `pypdf`, the browser with `pdf.js`. Different libraries,
different text from the same file. **The parity harness therefore excludes PDF
input**, and says why rather than quietly passing.

That is a real gap in a check this project leans on, so something has to stand
in its place. What is compared instead is the *judgement*: both engines must
classify a PDF usable or unusable by the same three numbers. A browser
accepting a file the package refuses would hand a researcher a corpus of
control characters from one and an explanation from the other — which is worse
than either being wrong alone.

`test_both_engines_judge_pdfs_by_the_same_numbers` reads the constants out of
the JavaScript source and compares them to the Python ones. Crude, and it
fails if either drifts.

### Line reconstruction

`pdf.js` returns positioned fragments, not lines. They are grouped by the
vertical coordinate of each item's transform, rounded, so a line of type
becomes a line of text — and page order is top-down rather than the order the
fragments happen to appear in the content stream.

### Two constants that were nearly wrong

`MAX_LEN` and `NEAR_DUPLICATE` do not exist in the JavaScript engine; they are
`FURN_MAX_LEN` and `FURN_NEAR_DUPLICATE`. Mirroring the Python names produced
a `ReferenceError` on the first run, which is the good failure — a silent
`undefined` comparison would have accepted every line as furniture.

---

## 2026-08-28 — A blank line means something only when it is not the norm

### The problem

Every rule in this package that looks at layout treats a blank line as a
boundary. That is right for a file a person typed and wrong for a file a PDF
produced, where the extractor renders the leading between lines as whitespace
and 55% of the file is blank.

The cost was P1: protected spans found 0 of 337 verse lines in a book of poems,
because each line was judged alone and one line is never enough evidence.

### The decision

Classify the blanks before reading them, at the point of use, and leave the
rules alone.

```
blank lines >= 40% of the file          density
text lines standing alone >= 80%        uniformity
```

Both are required. Density alone misreads three-line stanzas with three-line
gaps, which are 50% blank and wholly structural. **Uniformity is the real
signal**: leading falls between every line, a stanza break does not.

### Why the modal run survives and the rest do not

The obvious move — delete every blank line — is wrong, and the poems show why.
The leading is one blank; a stanza break is two. Delete both and the file
becomes a single block, one protected seed extends across all of it, and the
prose is protected along with the verse. So only runs of the *modal* length go,
and anything longer is kept as one blank line: still a boundary, just a
narrower one.

### Where it does not apply

Deliberately at the point of use in `protect.py`, not in the importer. Changing
the file on the way in would mean every later rule, every line number in every
report, and the user's own view of their text all disagreeing with the file
they supplied. The provenance of a line number is worth more than the
convenience.

### What it does not fix

Beowulf, at 5% blank lines, is nowhere near the density test and did not move.
Its missing 21% is the same symptom from a different cause — see P3.

---

## 2026-08-28 — A stanza is judged with the poem around it

### The problem

P3: verse rhyming *abab* with the odd lines unpunctuated carries only half its
breaks, and a block's last line carries none, because nothing follows it to
vouch for the break. An eight-line stanza scores 38% against a 45% threshold
while the stanzas either side of it are protected.

### Why not lower the threshold

45% is the number that holds hard-wrapped prose at 3%. Prose protected is the
error that cannot be recovered from: the paragraph is left in fragments and
nothing in the output shows it happened. A threshold that admits this stanza
admits prose somewhere else, and the somewhere else will not be noticed.

### The decision

Use the evidence that was going unused — the neighbouring block. A block that
cannot carry itself is protected when it clears **half** the threshold and sits
beside a firmly protected block. One side is enough: the first stanza of a poem
has its title above it and the rest of the poem below.

### The guard, which the first attempt lacked

Corroboration vouched from the per-line judgements, which include lines that
never become a span. A lone flagged line in wrapped *Jane Eyre* seeded the
block beside it, which seeded the next — three paragraphs protected, and the
reflow round trip fell from 99.5% to 98.5%.

**A voucher must be most of a block and at least a span's worth.** And the pass
is seeded once from what the primary rule found, never iterated: a block
protected by corroboration does not go on to corroborate the next, or one
stanza would carry protection to the end of the file.

That the round-trip test caught it is the argument for having a measurement
whose ground truth needs no judgement.

---

## 2026-08-28 — Interface furniture: position, not vocabulary

### The problem

A tester's corpus of comments was 45% URL by character; with those gone, about
3% was `Like`, `Reply`, `2 likes`, `View replies (4)`. That is apparatus in
exactly the sense a running head is apparatus, and nothing here removed it.

### Why the obvious rule is wrong

A list of words. Every one of them is ordinary English, and a novel contains
the line `Reply.` in dialogue. This package has already learned twice that
short lines and repeated lines both destroy prose; that is why page furniture
is found by its *interval* rather than its appearance.

### The discriminating signal

**An interface prints its controls after the thing they act on.** A control
sits in the tail of its record with nothing but other controls behind it. A
one-word comment sits at the head, however often it repeats.

Three guards, each earned:

1. **Licensed by the document, not the line.** Nothing is called interface
   furniture until the file looks like a scraped feed — handles, relative
   timestamps, at least five records. The same shape as the ascending
   page-number sequence page furniture requires before it will speak.
2. **A record is never all controls.** Something was commented on, so the
   trailing run stops before it eats the last line of the body. Without this a
   one-word comment above the controls is indistinguishable from one, and the
   fixture did not contain that shape.
3. **Company admits the occasional label.** `See translation` ends five records
   in forty and cannot clear the share on its own. It is admitted because every
   time it appears it appears beside a control that ends most of them — which a
   comment never does, being the thing those controls come after.

### What it does not establish

The fixture is synthetic and 43% furniture, against about 3% in the corpus that
prompted it. The precision figure means the rule does not eat the comments in a
file shaped like this one. It says nothing yet about a file shaped like hers.

---

## 2026-08-28 — Saying something when every rule declines

A tester cleaned Instagram comments and the log told her two things: 0 tokens
removed, and no structural headings found. Both true; neither useful. She could
not tell whether the tool had examined her text and found nothing to do, or
failed to read it at all.

**Silence is not a result.** When nothing fires, the log now names each rule,
what it looked for, and why it declined — and says plainly that these rules are
built for printed books, so a born-digital file has nothing here to remove.
That is a better answer than a zero, and it is the answer that tells her what
is worth reporting back.

The catalogue appears only in the empty case. A run with results already has
content, and repeating it there would be noise.

---

## 2026-08-28 — Division words outside English

Every measured number in this package is English literary prose, and the
division wordlist was the sharpest edge of that. A German novel segmented as
one undivided body — not because the heading tier was uncertain, but because
`Kapitel` was not a word it had ever been told about. The failure is silent in
the worst way: the log says "no structural headings found", which reads as a
fact about the book.

Widened from the three fixtures and the obvious cognates. **A wordlist is only
as wide as whoever wrote it**, so this is not multilingual support; it is three
fewer languages the tool is confidently wrong about. The limit is now stated in
`docs/USING.md`, where a user meets it before it costs them anything, rather
than left to be discovered.

Region labelling, encoding, tokenising and the line-break rules needed no
change: they were language-independent already, and the three fixtures score
100% on region labelling.

---

## 2026-08-29 — The recent-files list is switched off

### What it was

A filename and a token count for the last six files opened, so a returning
reader recognises what they worked on.

### Why it goes

**It cannot do the thing everyone expects of it.** A browser cannot read a file
again without the reader choosing it, and nothing here ever held the file. Two
rounds of fixing narrowed the gap — the button opens the file picker now, and
the entry can be removed — without closing it, because the gap is structural.
Every reader will click it expecting their cleaned text and every one of them
will be disappointed.

**The deciding argument is the storage, not the disappointment.** This was the
only place in the tool that kept anything about the reader's corpus. A filename
can be an informant's pseudonym or an unpublished title, and it was sitting in
browser storage on what may well be a shared machine, in a tool whose whole
proposition is that the reader's material stays under their control. That is a
real liability bought for a memory aid.

### Hidden, not deleted

`RECENT_LIST` in `build/_app.js`. The code, the markup, the CSS and the tests
all remain; the flag is the only thing between them and a working list.

**Off means purged, not merely hidden.** Nothing new is recorded, and names
already on a reader's machine are removed the next time they open the page.
Hiding the panel and leaving the names behind would keep the liability and
lose the feature, which is the worst of both.

The tests cover both states — off, and switched back on. A hidden feature
without a test rots quietly and comes back broken.

### What would bring it back

Remembering a file's *settings*, so that re-choosing it returns the reader to
their preset and their section selections. Then recognising the name is worth
something, because acting on the recognition costs one click instead of ten.
Recognition alone was not worth a filename in storage.

