# CorpusPrep Phase 2: Text Reconstruction

**The hard stages.** Page furniture, de-hyphenation, paragraph reflow.

**The dates in this file are void.** It was written as a forecast on the
assumption that the phase would start on 1 September 2026 and run to early
December. The work was in fact done between 23 and 28 August 2026, so every
calendar date below is wrong by months and every one was met early.

They are left in place rather than deleted, because the *sequence* is the part
worth keeping and it held: protected spans before reflow, measurement before
hardening, integration before PDF. Read the week numbers as an ordering and
ignore the dates.

Cadence as planned: five weekday evenings, two hours each. Milestone-driven,
no fixed deadline.

What actually happened, from the tag history:

| Planned | Actually |
|---|---|
| Weeks 2–4, September, page furniture | 23–24 August |
| Week 5, late September, de-hyphenation | 24 August |
| Weeks 8–11, October–November, reflow | 24 August |
| Week 12, late November, integration | 24 August |
| Week 13, late November, PDF | 25–27 August |
| Week 14, early December, close the phase | still open |

---

## Where this phase begins

Phase 1 is complete and exceeded its scope. The engine, the segmenter, the
web application, multi-format import and the test suite all exist. What
remains is the work identified at the outset as genuinely difficult.

| Built | Remaining |
|---|---|
| Encoding detection | Mojibake repair, Unicode normalisation |
| Gutenberg apparatus, licence, transcriber notes | Custom markers |
| Structural segmentation with hierarchy | Page furniture detection |
| Contents-list detection | De-hyphenation |
| TXT, DOCX, EPUB, HTML import | Paragraph and dialogue reflow |
| Variants, logging, web interface | OCR repair, structural tagging, PDF |

Four of the specification's nineteen cleaning stages are implemented. This
phase adds seven of the remaining fifteen, and they are the seven that matter
most, because PDF support and OCR repair both wait behind them.

### A caution carried forward

Reflow was described in the original assessment as the one stage that cannot
be solved completely. Nothing since has changed that. Weeks 8 to 11 are
budgeted accordingly, and the acceptance criterion is deliberately not
"correct" but **"accurate, with the remainder flagged rather than guessed."**

---

## Working rules

These carried Phase 1 and are unchanged.

1. **End every evening with something that runs.** Commit or stash. Evening
   work cannot afford to spend the first forty minutes rebuilding context.
2. **Fridays are for integration, not new logic.** Review, test, tidy, record.
3. **A missed evening shifts the plan; it is not made up.** Two-hour sessions
   work because they are two hours.
4. **First ten minutes: read yesterday's note. Last ten: write tomorrow's.**
5. **Parity is not optional.** Any change to the engine must be mirrored in
   the web application, and `check_parity.py` must pass before the week closes.
6. **Every new detection rule arrives with a false-positive test.** The rule
   that finds page numbers must also prove it leaves `1847` alone.

---

# WEEK 1 · 1 to 4 September · Reacquaintance and instrumentation

Four evenings. The month away means the first task is to rebuild your own
understanding of the code, not to extend it.

| Evening | Task | Complete when |
|---|---|---|
| **Tue 1 Sep** | Read `segment.py` end to end without changing it. Write a one-page summary of how a line becomes a labelled region. | The summary exists and matches the code. |
| **Wed 2 Sep** | Run the suite and the parity check. Clean three texts you have not used before. Record anything surprising. | Failure list written. |
| **Thu 3 Sep** | Build a measurement harness: given a text and a hand-marked answer key, report precision and recall per rule. | Harness runs on one hand-marked file. |
| **Fri 4 Sep** | Hand-mark two texts as answer keys. Tedious, and the foundation of everything that follows. | Two keys in `tests/keys/`. |

> **Why measurement first.** Every stage in this phase is a detector, and a
> detector without a measured error rate is an opinion. From here on, "it works"
> means a number.

---

# WEEK 2 · 7 to 11 September · Page furniture, part one

The first statistical detector. Running heads are found by recurrence and
spacing, not by appearance.

| Evening | Task | Complete when |
|---|---|---|
| **Mon 7 Sep** | Design on paper. What counts as a short line? How is similarity measured between two candidate heads? What does regular spacing mean numerically? | Algorithm written in `DECISIONS.md`. No code. |
| **Tue 8 Sep** | Collect all short lines. Normalise them (case, digits, punctuation) so that "JANE EYRE 42" and "JANE EYRE 43" compare as equal. | Normalised candidates printed. |
| **Wed 9 Sep** | Cluster by similarity. Count occurrences per cluster. | Clusters printed with frequencies. |
| **Thu 10 Sep** | Score by interval regularity. A cluster recurring every forty lines is furniture; one recurring three times at random is not. | Score separates the two by inspection. |
| **Fri 11 Sep** | Measure against the answer keys. Record precision and recall before tuning anything. | First numbers recorded. |

---

# WEEK 3 · 14 to 18 September · Page furniture, part two

| Evening | Task | Complete when |
|---|---|---|
| **Mon 14 Sep** | Tune thresholds against the keys. Record each value and the reason for it. | Thresholds justified, not merely chosen. |
| **Tue 15 Sep** | Wrap as `furniture.running_heads` with a `confirm` option and a `preview()` that lists matches without removing them. | Preview lists matches, removes nothing. |
| **Wed 16 Sep** | `furniture.page_numbers`, requiring a monotonic sequence rather than a bare integer. | `1847` alone survives; a real page run does not. |
| **Thu 17 Sep** | Sequence edge cases: roman numerals, per-chapter restarts, gaps from missing pages. | Edge-case fixtures pass. |
| **Fri 18 Sep** | Mirror both rules in the web application. Run parity. Tag `v0.3`. | Parity passes, tagged. |

---

# WEEK 4 · 21 to 25 September · Furniture completion and review

| Evening | Task | Complete when |
|---|---|---|
| **Mon 21 Sep** | `furniture.catchwords` for early modern printing. | Works on an early modern fixture. |
| **Tue 22 Sep** | Footnote markers: detect, then offer removal, retention, or extraction to a parallel file. | Three routes work. |
| **Wed 23 Sep** | Surface furniture in the interface. These rules remove far more than segmentation does, so the review queue matters more here. | Matches listed before removal. |
| **Thu 24 Sep** | Regression tests for the whole furniture group, including false-positive cases. | Suite green. |
| **Fri 25 Sep** | **Milestone review.** Precision and recall recorded for every furniture rule. Update the specification against reality. | Numbers in `DECISIONS.md`. |

**Four weeks in. Page furniture is complete and measured.**

---

# WEEK 5 · 28 September to 2 October · De-hyphenation

| Evening | Task | Complete when |
|---|---|---|
| **Mon 28 Sep** | Source a wordlist. **Check its licence before writing any code**; several common lists cannot be redistributed, which would compromise your release. | Licence recorded in `DECISIONS.md`. |
| **Tue 29 Sep** | Detect line-break hyphens. Join naively. | `exam-\nple` becomes `example`. |
| **Wed 30 Sep** | Validate against the wordlist: join only where the joined form is known and the split form is not. | False joins eliminated. |
| **Thu 1 Oct** | Ambiguity detection. `re-form` and `reform` are both words; flag rather than choose. | Ambiguous cases reach a flag list. |
| **Fri 2 Oct** | Review-queue file format, readable and re-importable. | Round trip works. |

---

# WEEK 6 · 5 to 9 October · Review workflow

The review queue is not a side feature. It is what allows every uncertain
rule in this phase to defer to the researcher rather than guess.

| Evening | Task | Complete when |
|---|---|---|
| **Mon 5 Oct** | Read decisions back in and apply them. | Accept and reject both work. |
| **Tue 6 Oct** | Persist decisions per corpus so a re-run does not ask twice. | Second run asks nothing. |
| **Wed 7 Oct** | Review queue in the web interface. Keyboard-driven, so two hundred items take two minutes. | Queue usable by keyboard alone. |
| **Thu 8 Oct** | Test on a genuinely hyphen-heavy text. | Type count falls measurably. |
| **Fri 9 Oct** | Mirror to the web application, parity, tag `v0.4`. | Parity passes, tagged. |

---

# WEEK 7 · 12 to 16 October · Rest week

No scheduled work. Permitted: reading, collecting fixtures, drafting the tool
paper outline. **No feature work.**

Take it even if you feel able to continue. The failure point in a schedule
like this is not week three; it is week eleven, in the middle of reflow.

---

# WEEKS 8 to 11 · 19 October to 13 November · Reflow

Four weeks. It will need them. Reflow is the reason this phase is long.

### Week 8 · 19 to 23 October · Protected spans first

You cannot safely rejoin lines until you know which lines must never be
rejoined. Verse, drama and tabular material come first.

- **Mon** Design verse detection on paper: line-length variance, indentation, stanza spacing.
- **Tue** Line-length variance detector. Prose wraps to a consistent width; verse does not.
- **Wed** Indentation-pattern detector.
- **Thu** Combine into `detect.protected_spans`, populating `Document.protected`.
- **Fri** Measure against a verse text and a drama text. Record precision and recall.

### Week 9 · 26 to 30 October · Paragraph reflow

- **Mon** Basic unwrap: join lines within a paragraph, keep blank-line breaks.
- **Tue** Respect protected spans. This is why week 8 came first.
- **Wed** Chapter headings, section breaks, epigraphs, block quotations.
- **Thu** `reflow.dialogue`: preserve quotation and speaker-turn boundaries.
- **Fri** Run on five fixtures. Expect poor results. **Log every failure without fixing any of them.**

### Week 10 · 2 to 6 November · Hardening

- **Mon to Thu** Work the failure log, hardest first. Accept that some cases cannot be resolved; route them to flags.
- **Fri** Measure. Compare against week 9. Record the improvement.

### Week 11 · 9 to 13 November · Reflow completion

- **Mon** Interaction between reflow and de-hyphenation. Order matters and the pipeline must enforce it.
- **Tue** Reflow in the web application.
- **Wed** Parity across every fixture.
- **Thu** Regression tests, including verse and drama preservation.
- **Fri** Tag `v0.5`. Write an honest account of reflow's known limits for the documentation.

> **Set the expectation now.** Reflow will not reach complete accuracy. A tool
> that reports "thirty line breaks are uncertain" is more useful, and more
> publishable, than one that silently guesses. Build towards the former.

---

# WEEK 12 · 16 to 20 November · Integration

| Evening | Task | Complete when |
|---|---|---|
| **Mon** | Run the complete pipeline across fifteen varied texts. Log everything that breaks. | Failure log complete. |
| **Tue** | Fix the highest-impact failures. | Top five resolved. |
| **Wed** | Stage ordering: encoding, apparatus, furniture, de-hyphenation, reflow, whitespace. Enforce dependencies in code, not in documentation. | Wrong order is refused with an explanation. |
| **Thu** | Full measurement pass. Precision and recall for every rule in the phase. | Table complete. |
| **Fri** | Tag `v0.6`. | Tagged. |

---

# WEEK 13 · 23 to 27 November · PDF

Now, and not before. The stages that make PDF text usable exist.

| Evening | Task | Complete when |
|---|---|---|
| **Mon** | Add `pypdf` or `pdfplumber` to the Python package. Extraction only. | Text comes out of a PDF. |
| **Tue** | Run extracted PDF text through the full pipeline. Measure how much the reconstruction stages repair. | Before and after figures recorded. |
| **Wed** | Decide honestly whether the result is good enough to offer. **If it is not, keep refusing PDF and say why.** | Decision recorded with evidence. |
| **Thu** | If proceeding: PDF in the web application via pdf.js, accepting the loss of the single-file property. | Works, or deferred with reasons. |
| **Fri** | Tests and parity. | Green. |

---

# WEEK 14 · 30 November to 4 December · Close the phase

| Evening | Task | Complete when |
|---|---|---|
| **Mon** | Update the specification. Mark implemented stages; revise anything reality contradicted. | Specification current. |
| **Tue** | Update the capability list in the interface. Move four items from planned to available. | Interface honest again. |
| **Wed** | Bundled profiles: Gutenberg prose, Gutenberg verse, drama, PDF extraction, OCR. | Profiles tested. |
| **Thu** | Full regression, full parity, full measurement. | All green. |
| **Fri** | **Tag `v1.0-rc`.** Write the phase report: what was built, what was measured, what remains. | Report written. |

---

## What this phase delivers

| | Before | After |
|---|---|---|
| Cleaning stages implemented | 4 of 19 | 11 of 19 |
| Text types handled well | Gutenberg prose and drama | Adds PDF, OCR and hard-wrapped sources |
| Detection rules with measured error rates | 0 | 7 |
| Reflow | none | high accuracy, remainder flagged |

## Realistic assessment

| | |
|---|---|
| Scheduled hours | ~130 across 13 working weeks |
| Probability of completing by early December | **40%** — written in advance; the work was done by 28 August, so the estimate was pessimistic by a factor no forecast should be trusted across |
| Probability by end of January | 75% |

The uncertainty is concentrated in weeks 8 to 11. If reflow overruns,
everything after it shifts. That is expected rather than a failure.

**If you fall behind, cut in this order:** catchwords, footnote extraction,
PDF, dialogue reflow. **Never cut:** the measurement harness, the review
queue, or the false-positive tests. Those three are what keep the tool
trustworthy, and trustworthiness is the entire proposition.

---

## After this phase

Two candidates, and they are not equal.

**External validation.** Three to five colleagues with genuinely messy
corpora. Everything to this point is your judgement about what corpus
cleaning requires; that week is the first evidence. It was deferred out of
this phase by choice, so it should be the immediate successor to it.

**The tool paper.** Four to six weeks of evenings. The measurement work in
this phase produces exactly the evaluation section such a paper needs, which
is a strong argument for writing it while the numbers are fresh.
