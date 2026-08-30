# Handover — where CorpusPrep is, 29 August 2026

Point a fresh session at this file. It replaces reading the conversation.

## State

`v0.11.0` plus an unreleased body of work, all committed and pushed
(`a2c1c67`). Zenodo DOI **10.5281/zenodo.22083932** (version), `…931`
(concept).

```
tests/test_corpusprep.py     568 passed, 0 failed   (unit + CLI smoke)
tools/ui_test.js              98 passed, 0 failed   (the built page in a DOM)
build/build.py --check        page matches its sources
tools/check_parity.py         the two implementations agree
tools/measure.py              7,733 lines, 99.99%, four languages
tools/integration.py          11 real books, no crashes, no coverage gaps
```

Reads TXT, Markdown, DOCX, EPUB, HTML, PDF. `pip install -e .` works now; PDF
support is the optional extra `.[pdf]`.

## Read this before deciding anything

**Twelve faults were found on 28–29 August. Seven of them were in the layer
between the engine and the person, and the engine was right in every one.**

```
P4   the CLI never ran half the rules
P7   the interface test could not start, and had been wrong for four days
P8   a reload put the sign-in gate back up
P9   the recent-files list was three dead buttons
P10  a PDF load hung with nothing on screen
P11  the README's first command could not work
P12  a mistyped path was reported as a broken PDF, in a traceback
```

Not one was found by a test. They were found by a person reloading a page,
clicking a list, loading a PDF, pasting a command. **Measurement, parity and
the unit tests all point inward.** Nothing pointed at the first five minutes of
a stranger's experience, and that is where the faults were.

The rate matters as much as the count. Seven interface faults in one evening of
ordinary use says the surface is not quiet yet. That is an argument for
`v1.0-rc` and against `v1.0`.

## What was fixed, 28–29 August

Full write-ups in `design/integration-failures.md` (P1, P3–P12), reasoning in
`design/DECISIONS.md`.

**Engine.** P1: protected spans found 0 of 337 verse lines in a PDF of ten
poems, because extraction renders leading as whitespace and every verse line
was judged alone. P3: enjambed stanzas are judged with the poem around them
rather than by a lower threshold. P5: `Kapitel`, `Глава`, `Kapitola` were not
words the heading tier knew.

```
protected lines            before    P1 fix    P3 fix
LIT 201 metaphysical poems  0/337   276/337   302/337
Beowulf.pdf              2626/3318 2626/3318 2907/3318
pg9405_ballads.txt       1958/2533 1958/2533 2074/2533
every prose fixture             0         0         0
```

**Added.** Interface furniture, found by position rather than by word. A log
that says what it looked for when nothing fires. `docs/USING.md`. Fixtures in
German, Russian and Czech. An optional registration link. `pyproject.toml`.

**Front ends.** All seven above.

## Open faults

**P2** — a 21,581-token "Introduction" that happens to be correct. Recorded
because it cannot be told from I1 without reading the book: there is still no
check that a front-matter region is front-matter-sized.

**P6** — a method note rather than a fault. The interface rule scored 100% on
its own fixture and was wrong anyway; the test that found it took one line.
Worth reading before writing another fixture.

**A sonnet's closing couplet** — a two-line block with a 0% break rate — stays
unprotected. Below any floor, not reachable by this evidence.

## What to do next, in this order

1. **One hour of cold use.** New browser profile, fresh clone into a different
   folder, follow the README exactly as written. Record hesitations, not only
   errors — P9 was a hesitation before it was a bug. Everything found on 29
   August came from this and nothing else.
2. **Send it to the tester**, with the four questions in
   `design/tester-questions.md`. She is the
   only available source of real evidence for the two rules marked
   *Experimental*, and no amount of work here can substitute for it.
3. **Tag `v1.0-rc`.** Not `v1.0`. An rc is what you hand people before you
   promise stability.
4. Only after the rc survives contact: `v1.0`, ORCID on the Zenodo record,
   close Phase 2.

Deliberately **not** next: engine work. The rules are measured, the two
implementations agree, and every fault this session was somewhere else. A new
rule now is new surface with no evidence behind it.

## Still outstanding

- Real non-English text. The three fixtures are original prose written for the
  purpose; they prove the machinery, not the rules
- Real social data. The interface rule has met one synthetic thread: 43%
  furniture against about 3% in the corpus that prompted it
- Ask testers how many files a corpus is, before building batch
- A control in the web application to remove interface furniture; the package
  can drop it, the page only reports it
- `node_modules` is committed and not in `.gitignore`. That is what lets this
  machine work offline, and it is why a truncated jsdom went unnoticed for
  days. Whether to keep vendoring it is a decision, not a defect

## Where things are

```
docs/USING.md                    the guide for people preparing a corpus
design/integration-failures.md   every fault found, fixed and unfixed
design/measurement.md            precision/recall per rule, and what each rests on
design/DECISIONS.md              why each rule is the way it is
design/authentication.md         why there is no backend, and what was done instead
tools/integration.py             whole pipeline over every real book
tools/pdf_triage.py              which PDFs need OCR before anything else
tools/measure_rules.py           per-rule scores
tools/check_parity.py            the two engines must agree
tools/ui_test.js                 the built page, driven in a real DOM
tools/make_*_fixture*.py         generators that record the key as they write
../pdf-tests/                    copyrighted PDFs, gitignored, never commit
```

Running the tests: `python tests/test_corpusprep.py` needs nothing. `node
tools/ui_test.js` needs the vendored jsdom, which is in `node_modules` and
complete as of `be8ba02`.

`build/_engine.js` contains one literal NUL byte in the `"\0page-number"`
sentinel, around line 918. It works, but `grep` treats the file as binary and
skips it — on the half of the codebase that must be kept in step with the
other half. Write it as `\0` when something else takes you there.

## Working rules that have earned their place

- **Detection never deletes.** Rules label; removal is a separate explicit step
- **Log failures the day you find them, fix them the next day**
- **A fixture only tests the failure modes its author thought of.** Furniture
  scored 100% synthetic then destroyed 63 lines of real ballads; protected
  spans scored 100% and found 0 of 337 real verse lines; interface furniture
  scored 100% and could not tell a one-word comment from a control
- **Existence is not visibility.** A test that checks an element exists passes
  on an element nobody can see. jsdom computes no layout, so ask about
  ancestors instead
- **A test that cannot run is worse than no test.** It occupies the place where
  coverage would be and asserts nothing, and the passing count does not miss it
- **The strongest test is an invariant, not a fixture.** "The same text set two
  ways must be judged the same way" cannot be satisfied by protecting more or
  by protecting less
- **Fix the input the rule is given, not the rule.** P1 was repaired without
  touching the two-signal test or the threshold
- **Position beats vocabulary.** A running head is found by its interval, not
  its appearance; a control by where it sits, not what it says
- **Parity compares engines, not front ends.** Seven faults lived in that gap
- **A traceback is a message to whoever wrote the program.** Catch what a
  reader can cause; let a real fault keep its traceback
- **Suspect the key before the threshold**
- **Check the premise before hunting better evidence**
- **A comment cannot fail.** Assert things instead
- Copyrighted test files stay out of the repository; findings go in

## Ten PDFs tested

5 usable, 1 with a text layer containing no language (7,205 "words", 0%
letters), 3 with no text layer, 1 empty download. **Half of real PDFs cannot
be extracted at all**, which is why triage is arguably the product.
