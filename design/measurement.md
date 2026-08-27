# Measured error rates

Week 12, Thursday. Precision and recall for every rule built in Phase 2.

Reproduce with `python tools/measure.py` and `python tools/measure_rules.py`.

**Nine rules were built and one had a published figure.** The answer keys for
the others have existed since the week each rule was written and nothing read
them. `measure_rules.py` reads them.

---

## The table

| Rule | Evidence | Precision | Recall | F1 |
|---|---|---|---|---|
| Region labelling | hand | **99.99%** over 7,654 lines | | |
| Page furniture | exact | 98.3% | 98.3% | 98.3% |
| Catchwords | exact | 85.7% | 100.0% | 92.3% |
| Protected spans | exact | 100.0% | 100.0% | 100.0% | ← and 0 of 337 on real verse |
| De-hyphenation | exact | 98.3% of decided | — | — |
| Paragraph reflow | derived | 99.5% of paragraphs recovered | | |
| Chapter segmentation | hand | 5 of 6 books exact | | |
| Footnotes | **none** | — | — | — |
| Digitisation apparatus | **none** | — | — | — |
| Chapter recovery from heads | hand | Oz 18/24, Treasure Island 33/34 | | |

### What the evidence column means, and why it is the important column

| | |
|---|---|
| `exact` | the fixture generator recorded the answer as it wrote it |
| `hand` | marked by a person from the source, never from this tool's output |
| `derived` | ground truth is the original file, recovered by round trip |
| `none` | no key exists; a figure here would be an assertion |

**A rule measured only against `exact` data has been measured against its
author's assumptions.** Four of the figures above are in that position. They
are enough to develop against and not enough to publish, and this file says so
rather than letting a reader assume otherwise.

The precedent is on record: the furniture detector scored **100%** on synthetic
data and then marked 63 lines of a real ballad collection as page furniture,
because the generator had been written on the assumption that refrains recur
irregularly. In fixed-stanza verse they do not.

---

## The errors, each one examined

A figure without its failures is a number, not a measurement.

### Page furniture — 1 false positive, 1 missed

Both are **known trade-offs rather than defects**, which is the useful thing to
be able to say.

```
false positive   line   1   'JANE EYRE'
missed           line 269   'B'
```

The false positive is the book title on the title page. It is a short repeated
capitalised line at a plausible interval, and it is indistinguishable from a
running head by any property the rule uses — because it is the same string.

The miss is a page number OCR'd as `B` for 8. A single character must be a real
digit to count, deliberately: without that guard a lone `I` reads as 1, and a
lone `I` is far more often the pronoun. **One page number lost is the price of
not deleting every first-person sentence at a page boundary.**

### Catchwords — 3 false positives

All three are pages whose last word coincidentally repeats the first word of
the following page:

```
line 163  '…the reckoning of that day.'
line 219  '…gave thanks, being come to safety.'
line 395  '…he departed from that place, saying nothing at all'
```

This is exactly the trap `early_modern.txt` was built to contain, and it is
**not fixable by better evidence.** A catchword is a repetition; so is a
coincidence. Nothing in the text distinguishes them, so precision here has a
ceiling below 100% and the honest response is the one already taken: catchword
removal is off unless requested, and every match is listed for review.

Recall is 100%. Given a choice, a rule that shows three extra candidates to a
reader is better than one that silently drops a real catchword.

### De-hyphenation — 174 correct of 177 decided, 3 left to the reader

```
line   78   wanted 'Rimoth-Gilead'   got 'RimothGilead'
line 1238   wanted 'silver-white'    got 'silverwhite'
line  393   wanted 'doubtfully'      got 'doubt-fully'
```

The first two are the same fault: **proper nouns and rare compounds whose left
half is not otherwise attested.** `Rimoth` appears nowhere else in the text, so
the rule concludes the word was broken rather than compounded. That reasoning
is right in general and wrong here, and it will be wrong on every place name
and personal name a text mentions once.

The third is the reverse. `doubt` and `fully` are both ordinary words, so the
compound rule keeps the hyphen — but `doubtfully` is one word and `doubt-fully`
is not a compound anyone writes. **Being built out of words is necessary for a
compound and not sufficient.**

Three errors in 177 is 98.3%, and all three are explicable rather than random,
which is the more useful property: each names a class of text that will fail,
so a user can look for it.

### Protected spans — 100% on the fixture, 0% on a book of poems

**Read the fixture figure with the failure beside it.** On
`mixed_verse.txt` the rule finds every verse line and protects no prose. On
the first real collection of poetry it met — ten metaphysical poems extracted
from PDF — it found **0 of 337**, because the extraction double-spaces the
file and the rule's window stops at blank lines, so every verse line is judged
alone. See `design/integration-failures.md`, P1.

The fixture is real *Jane Eyre* prose wrapped to 66 columns with real ballad
stanzas embedded in it, so the boundary is the only difficult part and the
fixture is nothing but boundaries. That was a deliberate choice and it left a
hole: **pure verse is where the damage is total, and no fixture contained
any.**

---

## What is deliberately not quoted

**Footnotes.** Built and validated entirely against real books — The Prince
supplies marker-and-note pairs whose numbering restarts every chapter, Romeo
and Juliet supplies 69 bracketed stage directions that must not be mistaken for
them. Both work. **No key file was ever written**, so there is no figure, and
inventing one from the tool's own output would measure only its consistency
with itself.

**Digitisation apparatus.** The Internet Archive and Google Books notices are
verbatim boilerplate reproduced identically across millions of volumes.
Matching is exact string containment, so precision is not the question being
asked.

**Page-furniture rules on real scans.** Two books. A precision figure from two
texts is a number with no interval around it, and publishing one would be worse
than publishing none.

---

## What this table is for

Not to show the rules are good. Several are measured against data that cannot
surprise them, and the table says which.

It exists so that **a reader can see which claims rest on what**, and so that
the next real text that breaks something has somewhere to be recorded. Every
figure here is reproducible from the repository by someone who does not trust
it.
