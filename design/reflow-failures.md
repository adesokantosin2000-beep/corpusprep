# Reflow failure log

Week 9, Friday. The schedule's instruction for today was: *"Run on five
fixtures. Expect poor results. **Log every failure without fixing any of
them.**"*

That discipline is followed here. Nothing below is fixed; Week 10 is for that.
Fixing faults on the day you find them means fixing the easy ones and quietly
losing the list.

---

## How reflow is measured

Reflow has a test that needs no judgement. *Jane Eyre* is stored one line per
paragraph, so:

1. hard-wrap it to a fixed width, as a typesetter would;
2. reflow it;
3. compare with what we started from.

Ground truth is the original file. The measurement cannot flatter itself.

### A measurement fault found first

The first run reported **4.2%**. That figure was wrong, and the fault was in the
measurement rather than the rule.

Paragraphs were being compared **positionally**: paragraph 1 against paragraph
1, and so on. A single spurious split early in the file shifts every paragraph
after it, so one error makes the entire remainder read as wrong. Compared as
sets, the same output scores **96.2%**.

Both numbers describe something real — position matters if you are aligning to
an edition — but quoting 4.2% as an accuracy figure would have been badly
misleading. **An accuracy metric that collapses on a single insertion is
measuring alignment, not accuracy.**

---

## Baseline, before any hardening

Wrapping *Jane Eyre*'s first 400 paragraphs and reflowing:

| Width | Paragraphs out | Recovered exactly |
|---|---|---|
| 60 | 412 | — |
| 66 | 407 | **382 of 397 = 96.2%** |
| 72 | 411 | — |

Every width over-produces paragraphs. The count is the tell: 407 out for 400
in, so the rule is splitting where it should not.

---

## F1 — Over-splitting at false speaker turns — **FIXED, Week 10**

**Severity: high. This was the whole of the Week 9 error.**

22 spurious paragraphs, all of them fragments of correctly-joined ones:

```
want:  "If you don't sit still, you must be tied down," said Bessie. "Miss
        Abbot, lend me your garters; she would break mine directly."

got:   "If you don't sit still, you must be tied down," said Bessie.
       "Miss Abbot, lend me your garters; she would break mine directly."
```

`split_turns()` starts a new paragraph at any line beginning with a quotation
mark, on the reasoning that a typesetter often runs two speeches together.

**The reasoning is sound and the evidence is not.** In wrapped text a line
begins with a quotation mark whenever the wrap happens to fall there. The line
position is an artefact — precisely the artefact reflow exists to remove — so
using it as evidence is circular.

This is a category error rather than a threshold that needs tuning, and the fix
is not obvious: distinguishing a genuine new speech from a quotation mid-
sentence needs evidence that survives wrapping.

### Week 10: the premise was false as well as the evidence

Before looking for better evidence, the premise was worth checking. It does not
hold. **585 of *Jane Eyre*'s 4,082 paragraphs contain two or more quoted
speeches, every one printed as a single paragraph:**

```
"Where the dickens is she!" he continued. "Lizzy! Georgy! ... 
```

Typesetters mark a new speech with a paragraph break, which is a blank line,
which reflow already respects. The rule cost 22 spurious paragraphs and bought
nothing.

`split_turns` is now the identity function, kept under its own name so the
mistake stays legible instead of being quietly deleted.

---

## F2 — Whitespace is normalised, so the round trip is not byte-exact

**Severity: low, but it must be documented rather than fixed silently.**

`join()` collapses runs of spaces at the seams. Text using two spaces after a
full stop does not come back identical.

Note that `textwrap` also collapses whitespace, so the wrap half of the round
trip is lossy too. Some of what looked like reflow error was this.

Whether to preserve internal double spaces is a real question for a corpus tool
and should be answered deliberately, not by accident of implementation.

---

## F3 — Headings are recognised only when they stand alone

**Severity: medium. Untested, which is worse than failing.**

`looks_like_heading()` requires a block of exactly one line. A heading that the
typesetter wrapped onto two lines, or one sitting directly above its paragraph
with no blank line between, is not recognised and is joined into the prose.

No fixture currently exercises this. **A rule with no test is a rule with an
unknown error rate**, and it is listed here for that reason rather than because
it has been seen to fail.

---

## F4 — Indentation of the first line is preserved, of the rest discarded

**Severity: low. Possibly correct; certainly undecided.**

The joined paragraph keeps the indentation of its first line. For a block
quotation indented throughout, that is right. For a paragraph whose first line
is indented as a paragraph opener, it preserves a typesetting convention into
what is meant to be clean text.

---

## F5 — Interaction with de-hyphenation — **FIXED, Week 10**

**Severity: was unknown. It turned out to be the second largest error.**

Listed in Week 9 as untested, and testing it found real damage. Wrapping breaks
on hyphens, so `white-washed` becomes `white-` and `washed`. Reflow joined the
seam with a space and produced **`white- washed`**: a space that was never in
the book, splitting a compound in two. **46 lines of the fixture ended in a
hyphen, and every one was damaged.**

A line ending in a word-hyphen is now joined tight. A dash keeps its space,
using the same distinction de-hyphenation makes: a hyphen attached to a word is
hyphenation, a hyphen preceded by whitespace is punctuation.

Reflow does not decide the hyphen's fate, only that no space belongs at the
seam. Whether `white-washed` should become `whitewashed` remains
de-hyphenation's question, asked separately.

---

## What is not wrong

Worth recording, because these were the expected failure modes:

- **Protected spans hold.** No verse passage was joined in any run.
- **Unwrapped text is untouched.** A file that is already one line per
  paragraph is returned unchanged rather than mangled.
- **Blank-line paragraph breaks survive.** No two paragraphs were merged. The
  error is entirely in the other direction.

Over-splitting is also the safer failure: a paragraph wrongly split is visible
in the output and can be rejoined, whereas two paragraphs wrongly merged lose
the boundary permanently.


---

## Week 10 result

| | Week 9 | Week 10 |
|---|---|---|
| Paragraphs recovered | 96.2% | **99.5%** |
| Spurious paragraphs | 22 | **2** |
| Paragraph count (width 60) | 412 for 400 | **400 for 400** |

Two faults fixed, F1 and F5, and neither by tuning: one rule was built on a
false premise and was deleted, the other was a missing distinction the
de-hyphenation rule already knew how to make.

### The two remaining differences are not errors

At width 60 the only two paragraphs that differ are:

```
source:  a tiresome, ill- conditioned child
output:  a tiresome, ill-conditioned child
```

The Gutenberg transcription itself contains `ill- conditioned` and
`window- sill`, with a space after the hyphen. Reflow produces the tighter
form, which is almost certainly what the book prints.

**Recorded rather than claimed as 100%.** The output differs from the input,
and a tool whose proposition is fidelity to the source should say so, even when
the difference is an improvement.

### Still open

**F2** whitespace normalisation — no double spaces exist in this text, so it
remains undecided rather than resolved. **F3** headings wrapped onto two lines,
still untested. **F4** first-line indentation, still an undecided default.


---

## Week 11 — ordering, and two more faults

### The stage order is a dependency, not a preference

De-hyphenation **must** run before reflow. It repairs words broken across a
line break, and reflow removes exactly those breaks.

The pipeline had them the wrong way round, shipped in the Week 9 commit:

| Order | Breaks de-hyphenation could see | Words recovered |
|---|---|---|
| reflow, then de-hyphenate | **0 of 180** | 81 of 166 |
| de-hyphenate, then reflow | 180 of 180 | **162 of 166** |

Reflow consumed the evidence entirely. The order is now fixed in the renderer
in both implementations, with the reason written beside it rather than in
documentation a later edit can quietly contradict.

### More evidence is not always more evidence

Fixing the order alone changed nothing: still 81 of 166. A second fault sat
underneath.

`render()` was passing the whole document's vocabulary to de-hyphenation as
"extra evidence". **The document contains the broken fragments.** Each fragment
was therefore counted twice while the fragment discount subtracts it once, so
`inite` was promoted to a real word and the break read as a compound.

It turned **171 joins into 84**, and 6 kept hyphens into 96.

`extra_vocab` is for a wordlist from *outside* the document, and the parameter
now says so. A word attested only in a region the reader chose to delete is not
part of the corpus being produced anyway.

### A test that passed for the wrong reason

`test_real_compounds_keep_their_hyphen` had been passing throughout. The
poisoned vocabulary made the rule keep *everything*, so the compounds survived
by accident — and so did the test. Removing the fault broke it.

**A test can be green because the code is right or because two faults cancel.**
Only changing something tells you which.
