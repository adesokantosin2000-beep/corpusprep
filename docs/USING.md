---
layout: doc
title: "Using CorpusPrep"
description: >-
  How to prepare a corpus with CorpusPrep: what each cleaning preset retains, how to read the preprocessing log, which rules are measured and which are experimental, and where the tool is weakest.
---

# Using CorpusPrep

This guide is for people preparing a corpus. If you want to know how a rule
works internally, read `design/DECISIONS.md`. If you want to know what to run
and which output file to keep, read on.

---

## What this tool is for

A digitised book carries material that came with the digitisation rather than
with the work: a Project Gutenberg header and licence, an editor's introduction,
running heads at the top of every page, page numbers, footnote markers, words
broken across line ends by a typesetter, and paragraphs chopped into
fixed-width lines.

None of that was written by the author, and all of it lands in your word counts.
A collocation span that crosses a page number is measuring the printer rather
than the text.

CorpusPrep locates that material, reports what it found and on what evidence,
and writes the text without it to a new file. The original is not modified.

## What it does not do

- It does not correct OCR errors.
- It does not tag, lemmatise or parse.
- It does not judge whether a text is worth studying.
- It is of limited use on born-digital text such as tweets, comments and
  transcripts. There is one rule for interface labels like `Like` and `Reply`.
  Beyond that, a file with no printing apparatus has nothing here to remove,
  and the log will say so.

---

## Installing and running it

```bash
pip install -e .                          # from the CorpusPrep folder, once
pip install -e ".[pdf]"                   # only if you will read PDFs

corpusprep inspect  mybook.txt            # report what it found
corpusprep clean    mybook.txt --out cleaned
```

If you would rather not install anything, the package can be run from the
folder. It lives in `src/`, so Python has to be told where to look:

```powershell
$env:PYTHONPATH="src"; python -m corpusprep inspect mybook.txt
```

`inspect` prints the structure it found and changes nothing. Read it before you
clean. `clean` writes one file per variant into `cleaned/`, together with a log.

Then open `cleaned/mybook_log.md` and read section 4. It lists every region
removed and the evidence for removing it. If a region you wanted to keep is
missing, section 4 is where you will see that.

---

## Which file do I keep?

`clean` writes several versions of your text. They differ in how much of the
material that is not the work itself they retain.

| File | What it is | Keep it when |
|---|---|---|
| `__verbatim` | Nothing removed. Encoding and line endings normalised only. | Always. It is your baseline, and every figure in the log is measured against it. |
| `__full` | The Gutenberg header and licence removed. Everything the book itself contains is kept, including the editor's introduction and any appendices. | You want the whole edition without the digitisation apparatus. |
| `__body-and-front` | Also drops back matter. Keeps front matter. | The author's own preface or dedication counts as authorial text for your question. |
| `__body-only` | The work itself. Front matter, back matter and Gutenberg apparatus all removed. | Stylistic analysis, authorship work, or any question where an editor's prose would contaminate the measurement. This is the usual choice. |
| `__body-no-headings` | `body-only` with the `Chapter I` lines also removed. | Word lists and frequency counts, where forty repetitions of "chapter" would skew the data. |

### What body-only means

Everything the author wrote for this work, and nothing else. An editor's
introduction does not qualify. Neither does a translator's note, or a
publisher's advertisement bound in at the back. A preface written by the author
is a judgement call, and `body-and-front` exists for when you decide it counts.

### Checking body-only before you trust it

Look at the token figure in section 3 of the log.

If characters are down substantially and tokens are down barely at all,
apparatus was removed and the result is what you wanted.

If tokens are down by more than a few per cent, something substantial was
dropped. Open section 4 and read what it was. It may be correct. It may also be
a novel's opening chapters sitting inside a region labelled "Preface", a fault
that has occurred here and is written up as I1 in
`design/integration-failures.md`.

---

## Evidence levels

Three levels are used in this guide and in the capability list on the web page.
They describe the evidence behind a rule rather than how well it is written.

| | |
|---|---|
| **Supported** | Implemented, and measured against material the rule's author did not write: real books, hand-marked keys, or a round trip whose ground truth is the original file. |
| **Experimental** | Implemented and working, but validated only against material made for the purpose. It may well be correct; nobody outside this repository has shown that yet. Treat its output as a proposal and read the log. |
| **Future work** | Not implemented. The report says so when it meets a case that would need it. |

Each rule below carries its level. The levels are taken from the evidence
column in `design/measurement.md` rather than from anyone's confidence.

## What each rule looks for

Every rule below performs detection only. Nothing is deleted because a rule
fired. The variant you choose decides that, and the log records it.

**Regions.** *(Supported, 99.99% over 7,733 hand-marked lines.)* Every line is
labelled as Gutenberg header, front matter, body, back matter or Gutenberg
licence. Every line belongs to exactly one region, so nothing can disappear
except through a choice you made.

**Chapters.** *(Supported in English, experimental elsewhere.)* Headings such as
`Chapter I`, `Kapitel I`, `Глава I`, `Book the Third`, `ACT II`, and bare
ascending numerals standing alone. A book with no divisions is not a defective
book, and the log will say that none were found. Measured against real books: 38
of 38 divisions in *Jane Eyre*, 55 of 55 in *Emma*. Outside English the division
words come from a fixed list. See the question about other languages below.

**Page furniture.** *(Experimental, 98.3% against a synthetic scan.)* Running
heads and page numbers, identified by the interval at which they recur. A page
holds a fixed amount of type, so a running head repeats at a regular interval
and a refrain does not. The rule requires an ascending page-number sequence
before it will treat your text as page-imaged at all.

The measured figure comes from a fixture this project generated. The rule has
met real scans, recovering 18 of 24 chapters in one and 33 of 34 in another, but
it has no hand-marked figure against real material. That is why no built-in
variant removes what it finds.

**Catchwords.** *(Experimental, 85.7% precision against a synthetic fixture.)*
The first word of the next page, printed at the foot of this one. Common in
early modern books. Three false positives in the only measurement that exists,
so read them before removing them.

**Footnotes.** *(Implemented. No answer key exists, so there is no figure, and a
number here would be an assertion.)* Markers and their bodies. Footnotes are
content rather than printing debris, so they are kept by default. Whether an
editor's note belongs in your corpus depends on your question.

**Hyphen breaks.** *(Supported, 98.3% of the breaks it decided, and it declines
the rest rather than guessing.)* Words a typesetter split across a line, such as
`white-` followed by `washed`. The tool joins those its vocabulary can settle
and flags the remainder for you.

**Protected spans.** *(Supported, 100% on two fixtures, and 302 of 337 verse
lines in a real PDF of ten poems.)* Verse, drama and tabular material, whose
line breaks form part of the composition. These are marked so that reflow never
touches them. The question the rule asks is not whether something is poetry but
whether the author or the margin broke the line.

**Reflow.** *(Supported, 99.5% of paragraphs recovered exactly in a round trip
whose ground truth is the original file.)* Rejoins paragraphs that were broken
into fixed-width lines. Off unless you ask for it, and it leaves anything it is
unsure of exactly as it was.

**Interface furniture.** *(Experimental.)* Labels an application printed around
text a person wrote, such as `Like`, `Reply`, `2 likes` and
`View replies (4)`. Found by position rather than by word, because all of those
words are ordinary English. A control sits after the text of a record; a comment
does not. Nothing is claimed unless the file itself has the shape of a scraped
feed.

This rule has been validated against one synthetic thread and nothing else.
That thread was written for the purpose and is 43% furniture, against roughly 3%
in the real corpus that prompted the rule, which cannot be shared. So the 100%
figure in the measurement table means only that the rule does not remove the
comments in a file shaped like that one. It does not yet mean anything about
yours. Interface furniture is detected and reported, and no built-in variant
removes it. Read the table in the log before you turn removal on, and please
report anything it gets wrong.

---

## Reading the log

The log is written to be quoted in a methods section. It records the tool
version, the encoding, every region and the evidence for its label, and what
each variant removed.

Two lines are worth understanding.

> Every line is covered by exactly one region.

Nothing was lost by accident. If the log says otherwise, do not use the output.
Please report it instead.

> *N* lines look like page furniture. Detected, not removed.

The tool found them and left them in place. They are removed only if you ask.

---

## Common questions

**It removed nothing. Is it broken?**
Probably not. The log lists what each rule looked for and why it declined.
Born-digital text has no printing apparatus, and a clean Gutenberg plain-text
file has often had its furniture removed by hand already.

**Can I trust it on a language other than English?** *(Partly. Experimental
outside English.)*
Region labelling, encoding, tokenising and the line-break rules do not depend on
the language, and they score 100% on the German, Russian and Czech fixtures.

Two qualifications apply, and both are real. Those fixtures are original prose
written for this project rather than real books, so they show that the machinery
survives umlauts, Cyrillic and Czech diacritics and nothing about real literary
corpora in those languages. And chapter headings work from a fixed list of
division words, which is only as wide as the list. `Kapitel`, `Глава`,
`Kapitola` and their neighbours are recognised. A language whose word is absent
yields no structure, and the report says so, which is safe but unhelpful. If
that happens to you it is worth reporting, because adding a word is a one-line
change.

Every figure measured against material this project did not write still comes
from English literary prose.

**My PDF produced nonsense.**
Run `python tools/pdf_triage.py` first. Of ten real PDFs tested here, five were
usable, three had no text layer at all, one had a text layer containing no
language, and one was an empty download. Half of real PDFs cannot be extracted
without OCR, and no cleaning rule can repair that.

**Can I remove the running heads?**
Yes, but read the furniture table in the log first. No built-in variant removes
them, because the detector has been measured mostly against synthetic text, and
a rule that has never met your scan should not delete your prose on its own
authority.

**Which file do I cite?**
Cite the log. It names the tool version and every decision, so that someone else
can reproduce your corpus from your source file.

---

## Future work

The following are not implemented. The tool reports when it meets a case that
would need one, rather than guessing.

- **OCR character repair.** Broken ligatures, stray marks and mis-scanned
  characters. Damaged pages are identified and reported, not corrected.
- **Titled sections without numbering.** A collection whose parts are titled but
  neither numbered nor introduced by a division word yields no structure, and
  the report says so.
- **Batch processing.** One file at a time, deliberately, until we know from
  users how large a corpus usually is.

## If a variant removes too much

The original file is never modified, and every output is a new file. If a
variant removed something it should not have, the log names the region and the
lines, and the `verbatim` output still contains them.

The design rule behind all of this is that detection never deletes, and that
anything the tool is unsure of is flagged rather than guessed.
