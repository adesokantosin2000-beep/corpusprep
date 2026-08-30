# Using CorpusPrep

For people preparing a corpus, not for people maintaining the tool. If you want
to know how a rule works, read `design/DECISIONS.md`. If you want to know what
to run and which file to keep, you are in the right place.

---

## What this tool is for

A digitised book is not only the book. It carries the apparatus that came with
it: a Project Gutenberg header and licence, an editor's introduction, running
heads repeated at the top of every page, page numbers, footnote markers, words
broken across line ends by a typesetter, paragraphs chopped into fixed-width
lines.

None of that was written by the author, and all of it lands in your word
counts. A collocation span that crosses a page number is measuring the printer.

CorpusPrep finds that apparatus, tells you what it found and why, and gives you
the text with it removed — **as a separate file, with the original untouched.**

## What it is not for

- It does not correct OCR errors.
- It does not tag, lemmatise or parse.
- It does not judge whether a text is worth studying.
- It will not clean born-digital text — tweets, comments, transcripts. There is
  a rule for interface labels (`Like`, `Reply`), and beyond that a file with no
  printing apparatus has nothing here to remove. The log will say so plainly.

---

## The five minutes that matter

```bash
pip install -e .                          # from the CorpusPrep folder, once
pip install -e ".[pdf]"                   # only if you will read PDFs

corpusprep inspect  mybook.txt            # what did it find?
corpusprep clean    mybook.txt --out cleaned
```

If you would rather not install anything, the package still runs from the
folder — it lives in `src/`, so Python needs telling where to look:

```powershell
$env:PYTHONPATH="src"; python -m corpusprep inspect mybook.txt
```

`inspect` prints the structure it found and changes nothing. **Read it before
you clean.** `clean` writes one file per variant into `cleaned/`, plus a log.

Then open `cleaned/mybook_log.md` and read section 4. It lists every region
removed and the evidence for removing it. If a region you wanted is missing,
that is where you will see it.

---

## Which file do I keep?

`clean` writes several versions of your text. They differ in **how much of the
book that is not the work** they keep.

| File | What it is | Keep it when |
|---|---|---|
| `__verbatim` | Nothing removed. Encoding and line endings normalised only. | Always — it is your baseline. Every figure in the log is measured against it. |
| `__full` | The Gutenberg header and licence removed. Everything the book itself contains is kept, including the editor's introduction and any appendices. | You want the whole edition, minus the digitisation apparatus. |
| `__body-and-front` | Also drops back matter. Keeps front matter. | The author's own preface or dedication counts as authorial text for your question. |
| `__body-only` | **The work itself.** Front matter, back matter and Gutenberg apparatus all removed. | Stylistic analysis, authorship work, anything where an editor's prose would contaminate the measurement. This is the usual choice. |
| `__body-no-headings` | `body-only` with the `Chapter I` lines themselves also removed. | Word lists and frequency counts, where forty repetitions of "chapter" would skew the data. |

### `body-only` in one sentence

**Everything the author wrote for this work, and nothing else.**

An editor's introduction is not it. A translator's note is not it. A publisher's
advertisement bound in at the back is not it. A preface *by the author* is a
judgement call, and `body-and-front` is there for when you decide it counts.

### The one thing to check before trusting `body-only`

Look at the token figure in section 3 of the log.

- **Characters down a lot, tokens down barely at all** — apparatus was removed.
  This is what you want.
- **Tokens down more than a few per cent** — something substantial was dropped.
  Open section 4 and read what. It may be right; it may be a novel's opening
  chapters sitting inside a region labelled "Preface". That exact fault has
  happened here and is written up as I1 in `design/integration-failures.md`.

---

## How much to trust each rule

Three levels, used throughout this guide and in the capability list on the web
page. They describe **the evidence behind a rule**, not how well it is written.

| | |
|---|---|
| **Supported** | Implemented, and measured against material the rule's author did not write — real books, hand-marked keys, or a round trip whose ground truth is the original file. |
| **Experimental** | Implemented and working, but validated only against material made for the purpose. It may be right; nobody outside this repository has shown that yet. Treat its output as a proposal and read the log. |
| **Future work** | Not implemented. The report says so when it meets one. |

Each rule below carries its level. The levels come from the evidence column
in `design/measurement.md`, not from anyone's confidence.

## What each rule looks for

Each of these is **detection**. Nothing is deleted because a rule fired; the
variant you choose decides that, and the log records it.

**Regions.** *(Supported — 99.99% over 7,733 hand-marked lines.)* Every line is labelled: Gutenberg header, front matter, body, back
matter, Gutenberg licence. The guarantee is that every line belongs to exactly
one region, so nothing can vanish except by a choice you made.

**Chapters.** *(Supported in English; experimental elsewhere.)* Headings such as `Chapter I`, `Kapitel I`, `Глава I`, `Book the
Third`, `ACT II`, and bare ascending numerals standing alone. A book with no
divisions is not a defective book; the log will say none were found. Measured
against real books: 38 of 38 divisions in *Jane Eyre*, 55 of 55 in *Emma*.
Outside English the division words come from a fixed list — see the language
question below.

**Page furniture.** *(Experimental — 98.3% against a synthetic scan.)*
Running heads and page numbers, found by the *interval* at
which they recur — a page is a fixed amount of type, so a running head repeats
regularly and a refrain does not. It needs an ascending page-number sequence
before it will claim your text is page-imaged at all.

The measured figure comes from a fixture this project generated. It has met
real scans — it recovered 18 of 24 chapters in one and 33 of 34 in another —
but it has no hand-marked figure against real material, which is why no
built-in variant removes what it finds.

**Catchwords.** *(Experimental — 85.7% precision against a synthetic
fixture.)* The first word of the next page, printed at the foot of this one.
Common in early modern books. Three false positives in the only measurement
that exists, so read them before removing them.

**Footnotes.** *(Implemented; no answer key exists, so there is no figure —
a number here would be an assertion.)* Markers and their bodies. Footnotes are *content*, not printing
debris, so they are kept by default. Whether an editor's note belongs in your
corpus depends on your question.

**Hyphen breaks.** *(Supported — 98.3% of the breaks it decided, and it
declines the rest rather than guessing.)* Words a typesetter split across a
line: `white-` / `washed`.
The tool joins the ones its own vocabulary can settle and **flags the rest for
you** rather than guessing.

**Protected spans.** *(Supported — 100% on two fixtures, and 302 of 337 verse
lines in a real PDF of ten poems.)* Verse, drama and tabular material, whose line breaks are
part of the composition. These are marked so that reflow never touches them.
The question asked is not "is this poetry" but "who broke this line — the
author or the margin".

**Reflow.** *(Supported — 99.5% of paragraphs recovered exactly in a round
trip whose ground truth is the original file.)* Rejoins paragraphs that were
broken into fixed-width lines. Off
unless you ask for it. It leaves anything it is unsure of exactly as it was.

**Interface furniture.** *(Experimental.)* `Like`, `Reply`, `2 likes`,
`View replies (4)` — labels an application printed around text a person wrote.
Found by position rather than by word, because every one of those words is
ordinary English: a control sits after the text of a record, a comment does
not. Nothing is claimed unless the file itself looks like a scraped feed.

**It has been validated against one synthetic thread and nothing else.** That
thread was written for the purpose and is 43% furniture, against about 3% in
the real corpus that prompted the rule, which cannot be shared. So the 100% in
the measurement table means the rule does not eat the comments in a file shaped
like that one, and does not yet mean anything about yours. It is detected and
reported; no built-in variant removes it. Read the table in the log before you
turn removal on, and tell us what it got wrong.

---

## Reading the log

The log is written to be quoted in a methods section. It records the tool
version, the encoding, every region and the evidence for its label, and what
each variant removed.

Two lines are worth understanding:

> ✅ Every line is covered by exactly one region.

Nothing was lost by accident. If this says otherwise, do not use the output —
report it.

> *N* lines look like page furniture. **Detected, not removed.**

The tool found them and left them alone. They go only if you ask.

---

## Frequently the real question

**"It removed nothing. Is it broken?"**
Probably not. The log now lists what each rule looked for and why it declined.
Born-digital text has no printing apparatus, and a clean Gutenberg plain-text
file has often had its furniture removed by hand already.

**"Can I trust it on a language other than English?"** *(Partly. Experimental
outside English.)*
Region labelling, encoding, tokenising and the line-break rules do not depend
on the language and score 100% on the German, Russian and Czech fixtures.

Two qualifications, both real. **Those fixtures are original prose written for
this project**, not real books — they show that the machinery survives
umlauts, Cyrillic and Czech diacritics, and nothing about real literary
corpora. And **chapter headings work from a fixed list of division words**,
which is only as wide as the list: `Kapitel`, `Глава`, `Kapitola` and their
neighbours are recognised, and a language whose word is absent yields no
structure, with the report saying so. That is safe but unhelpful, and if it
happens to you it is worth reporting — a word is a one-line fix.

Every figure measured against material this project did not write still comes
from English literary prose.

**"My PDF produced nonsense."**
Run `python tools/pdf_triage.py` first. Of ten real PDFs tested here, five were
usable, three had no text layer at all, one had a text layer containing no
language, and one was an empty download. Half of real PDFs cannot be extracted
without OCR, and no cleaning rule can repair that.

**"Can I remove the running heads?"**
Yes, but read the furniture table in the log first. No built-in variant removes
them, because the detector has been measured mostly against synthetic text and
a rule that has never met your scan should not delete your prose on its own
authority.

**"Which file do I cite?"**
Cite the log. It names the tool version and every decision, so someone else can
reproduce your corpus from your source file.

---

## Future work

Not implemented, and the tool will tell you when it meets one rather than
guessing:

- **OCR character repair.** Broken ligatures, stray marks and mis-scanned
  characters. Damaged pages are identified and reported, not corrected.
- **Titled sections without numbering.** A collection whose parts are titled
  but neither numbered nor introduced by a division word yields no structure,
  and the report says so.
- **Batch processing.** One file at a time, deliberately, until we know from
  users how large a corpus actually is.

## Getting it wrong safely

The original file is never modified. Every output is a new file. If a variant
removed something it should not have, the log tells you which region and which
lines, and `verbatim` still has it.

The design rule behind all of this: **detection never deletes**, and anything
the tool is unsure of is flagged rather than guessed.
