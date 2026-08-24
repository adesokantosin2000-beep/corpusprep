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

## F1 — Over-splitting at false speaker turns

**Severity: high. This is the whole of the current error.**

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

## F5 — No interaction with de-hyphenation has been tested

**Severity: unknown, which is the reason it is listed.**

A word broken across a line break sits exactly where reflow joins. Run in the
wrong order the two rules could produce `exam- ple` with a space, or silently
consume each other's work. The schedule puts this in Week 11 and it has not
been looked at.

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
