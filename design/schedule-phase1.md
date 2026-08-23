# CorpusPrep — Evening Build Schedule

**Start:** Tuesday 1 September 2026
**Cadence:** 5 weekday evenings × 2 hours = 10 hrs/week
**Target:** Working CLI, released. Milestone-driven, no hard deadline.
**Projected completion:** Weeks 17–18 → early-to-mid January 2027

> **Revised 29 July 2026.** A working prototype now exists in `corpusprep/`
> — import, segmentation, licence detection, region selection, variant
> generation, logging, CLI, 34 passing tests. Weeks 1–4 below are rewritten:
> you now start by *hardening and extending* working code rather than from an
> empty repo. That saves roughly two weeks and, more importantly, means
> evening one is real work instead of scaffolding.

---

## How to use this

Each evening has **one task that ends in something working**. That's the organising rule, and it's the difference between a plan that survives to November and one that dies in week 5.

### Six rules

1. **Never end an evening mid-refactor.** Commit working code or `git stash`. Evening work loses the mental stack overnight — you cannot afford to spend the first 40 minutes of Wednesday rebuilding Tuesday's context.
2. **Fridays are light by design.** Integration, review, tidying, notes. Never start hard new logic on a Friday.
3. **Miss an evening? Shift, don't double up.** Two-hour sessions work because they're two hours. A four-hour make-up session on Thursday buys you a skipped Friday and a resentful Saturday.
4. **First 10 minutes: read your last note. Last 10 minutes: write tomorrow's.** Non-negotiable. This is what makes 2-hour sessions productive instead of 2-hour warm-ups.
5. **The 15-minute rule.** On evenings you can't face it, sit down for 15 minutes with permission to stop. You'll usually continue. When you don't, you've kept the chain.
6. **Keep `DECISIONS.md`.** One line whenever you choose between two approaches, with why. In February you will not remember, and this is also raw material for the tool paper.

### A warning about your chosen cadence

Five evenings a week with no built-in slack is the highest-burnout option of the three. I've mitigated it two ways: Fridays are deliberately soft, and **weeks 7 and 14 are full rest weeks with no scheduled work**. Take them even if you feel fine — especially if you feel fine. The failure mode isn't week 3, it's week 9 when the reflow logic won't behave and you've had no break since August.

---

# PHASE 1 — HARDEN THE PROTOTYPE (Weeks 1–3)

*Starting point: `corpusprep/` v0.1.0, 34 tests passing.*
*Goal: the same behaviour, but composable, profile-driven, and proven on more than one text.*

## Week 1 · 1–4 Sep · Own the code, then break it

| Evening | Task | Done when |
|---|---|---|
| **Tue 1 Sep** | Git init, `pyproject.toml`, venv. **Read every line of the prototype** and change three things you disagree with. | Repo initialised, tests still green, first commit is yours. |
| **Wed 2 Sep** | Collect 6 varied real texts as fixtures: a marked PG file, a stripped one, a verse text, a drama text, an OCR extract, a non-English text. | Fixtures in `tests/fixtures/`. |
| **Thu 3 Sep** | Run `inspect` on all six. **Log every failure without fixing anything.** | Written failure list. |
| **Fri 4 Sep** | Triage the list: which are segmentation bugs, which are missing features, which are acceptable limits? | Triaged, added to `DECISIONS.md`. |

> **Why start by attacking it:** the prototype is validated on two texts. Its real error rate is unknown. Finding that out in week 1 is cheap; finding out in week 12 is not.

## Week 2 · 7–11 Sep · Fix, and add the Stage abstraction

| Evening | Task | Done when |
|---|---|---|
| **Mon 7 Sep** | Fix the top 2 segmentation bugs from Thursday's list. | Fixtures pass, regression tests added. |
| **Tue 8 Sep** | Fix the next 2. | Same. |
| **Wed 9 Sep** | `core/stage.py` — `Stage` ABC, `StageReport`, `preview()` / `apply()` split. | Interface defined, one stage implements it. |
| **Thu 10 Sep** | Retro-fit segmentation and whitespace as Stages behind a `Pipeline`. | CLI still works, now via Pipeline. |
| **Fri 11 Sep** | Integration + commit. Tag `v0.2`. | Green, tagged. |

## Week 3 · 14–18 Sep · Profiles, encoding, golden tests

| Evening | Task | Done when |
|---|---|---|
| **Mon 14 Sep** | `core/profile.py` — pipeline + variant set as saveable JSON. | Round-trip test passes. |
| **Tue 15 Sep** | Swap the stdlib encoding fallback for `charset-normalizer` **behind the existing adapter**. Add `ftfy` mojibake repair. | Mojibake fixture round-trips; stdlib path still works as fallback. |
| **Wed 16 Sep** | Golden-file test harness with readable diffs. | Harness catches a deliberately broken stage. |
| **Thu 17 Sep** | Convert the 34 ad-hoc checks to golden tests. | Full suite green under pytest. |
| **Fri 18 Sep** | **MILESTONE REVIEW.** Tag `v0.3`. Update the design spec against reality. | Spec updated, tagged. |

**End of Phase 1 — ~30 hours in, and you're where the old plan had you at week 6.**

---

# PHASE 2 — THE HARD STAGES (Weeks 4–12)

*This is the phase that makes the tool worth using. It is also where the schedule will slip. Expect it.*

> **Two weeks earlier than the original plan** — Phase 2 now starts on 21 September. The week numbers below shift by one against the dates in the original draft; the dates shown are correct.

## Week 4 · 21–25 Sep · Running-head detection

| Evening | Task | Done when |
|---|---|---|
| **Mon 28 Sep** | **Paper only, no code.** Design the detection algorithm. What is a "short line"? How is similarity measured? What does interval-regularity mean numerically? | Written algorithm in `DECISIONS.md`. |
| **Tue 29 Sep** | Line normalisation + similarity clustering of short lines. | Clusters printed for Jane Eyre. |
| **Wed 30 Sep** | Frequency filtering — cluster size thresholds. | Noise clusters eliminated. |
| **Thu 1 Oct** | Interval-regularity scoring. *A cluster recurring every ~40 lines is furniture; one recurring 3 times randomly is not.* | Score separates the two by hand-inspection. |
| **Fri 2 Oct** | Tune thresholds against 3 different PG files. Record chosen values and why. | Thresholds justified in notes. |

## Week 6 · 5–9 Oct · Furniture stages

| Evening | Task | Done when |
|---|---|---|
| **Mon 5 Oct** | `furniture.running_heads` stage wrapping the detector. `confirm` param; `preview()` returns the match list. | Preview lists matches without deleting. |
| **Tue 6 Oct** | `furniture.page_numbers` — **require monotonic sequence** (fixes bug B4). | Isolated `1847` in prose survives; real page runs don't. |
| **Wed 7 Oct** | Sequence edge cases: roman numerals, per-chapter restarts, gaps from missing pages. | Edge-case fixtures pass. |
| **Thu 8 Oct** | `furniture.catchwords`. | Works on an early-modern fixture. |
| **Fri 9 Oct** | Golden tests for the whole furniture group. Tag `v0.2`. | Suite green, tagged. |

## Week 7 · 12–16 Oct · **REST WEEK**

No scheduled work. If you're itching, permitted activities: read other people's cleaning code, collect messy corpora for fixtures, write the tool-paper outline. **No feature work.**

## Week 8 · 19–23 Oct · De-hyphenation

| Evening | Task | Done when |
|---|---|---|
| **Mon 19 Oct** | Source a wordlist. **Check the licence** — some are non-redistributable, which would poison your release. Decide and record. | Wordlist chosen, licence noted. |
| **Tue 20 Oct** | Line-break hyphen detection + naive joining. | `exam-\nple` → `example`. |
| **Wed 21 Oct** | Wordlist validation: join only when the joined form is known and the split form isn't. | False joins eliminated on fixture. |
| **Thu 22 Oct** | Ambiguity detection (`re-form` / `reform`) → flag, never guess. | Ambiguous cases land in a flag list. |
| **Fri 23 Oct** | Review-queue file format (CLI version: a readable decisions file). | `*_review.txt` generated and legible. |

## Week 9 · 26–30 Oct · Review workflow + hyphenation polish

| Evening | Task | Done when |
|---|---|---|
| **Mon 26 Oct** | Read a decisions file back in; apply accept/reject. | Round-trip works. |
| **Tue 27 Oct** | Persist decisions per-corpus so re-runs don't re-ask. | Second run asks nothing. |
| **Wed 28 Oct** | Test de-hyphenation on a genuinely hyphen-heavy PDF-extracted text. | Type count drops measurably. |
| **Thu 29 Oct** | Fix what Wednesday broke. | Suite green. |
| **Fri 30 Oct** | Golden tests. Tag `v0.3`. | Tagged. |

## Weeks 10–12 · 2–20 Nov · Reflow *(the monster)*

Three full weeks. It will need them.

**Week 10 (2–6 Nov) — Protected spans first.** You cannot reflow safely until you know what not to touch.

- Mon: Design verse/protected-span detection on paper. Indentation patterns, line-length variance, rhyme-position heuristics.
- Tue: Line-length variance detector — prose wraps to a consistent width, verse doesn't.
- Wed: Indentation-pattern detector.
- Thu: Combine into `detect.protected_spans`. Populate `Document.protected`.
- Fri: Test against a Gutenberg *verse* text and a drama text. Tune.

**Week 11 (9–13 Nov) — Paragraph reflow.**

- Mon: Basic unwrap — join lines within a paragraph, keep blank-line breaks.
- Tue: Respect protected spans (this is why week 10 came first).
- Wed: Chapter headings, section breaks, epigraphs.
- Thu: `reflow.dialogue` — preserve quotation and speaker-turn boundaries.
- Fri: Test on 5 fixtures. Expect ugliness. Log every failure without fixing.

**Week 12 (16–20 Nov) — Reflow hardening.**

- Mon–Thu: Work the failure log from Friday, hardest first. **Accept that some cases are unsolvable** — route them to flags rather than fighting them.
- Fri: Golden tests. Tag `v0.4`. Honest write-up of reflow's known limits, for the docs.

> **Set expectations now:** reflow will never be perfect. The goal is *high accuracy plus honest flagging of the rest.* A tool that says "I'm unsure about these 30 line breaks" is more useful, and more publishable, than one that silently guesses.

## Week 13 · 23–27 Nov · Integration

| Evening | Task | Done when |
|---|---|---|
| **Mon–Tue** | Run the full 19-stage pipeline end-to-end on 10 varied corpora. Log everything that breaks. | Failure log complete. |
| **Wed–Thu** | Fix the top failures. | Top 5 fixed. |
| **Fri** | Full suite, full report, tag `v0.5`. | Tagged. |

## Week 14 · 30 Nov – 4 Dec · **REST WEEK**

Second mandatory break. You're 130 hours in and about to enter the release run.

---

# PHASE 3 — RELEASE (Weeks 15–20)

## Week 15 · 7–11 Dec · Remaining stages

Mon: `markup.html` · Tue: `markup.ocr` (**flag-only, never auto-apply**) · Wed: `annotate.structure` · Thu: `annotate.header` · Fri: tests, tag `v0.6`.

## Week 16 · 14–18 Dec · Profiles + batch

Mon–Wed: Author and test the bundled profiles — Gutenberg prose, Gutenberg verse, PDF extraction, OCR/historical. Thu: Batch mode across a folder. Fri: Per-file traffic-light summary (green/amber/red on token loss). Tag `v0.7`.

## Weeks 17–18 · 21 Dec – 1 Jan · **HOLIDAY — schedule assumes zero work**

Christmas and New Year fall exactly here. Don't fight it. If you work, treat it as bonus; the plan doesn't depend on it. **Resume 4 January.**

## Week 19 · 4–8 Jan · External validation

Mon: Package for install (`pipx`, `pip install -e`). Tue: Write the quick-start doc. Wed: **Send to 3 colleagues with messy corpora.** Thu–Fri: Watch what they do, fix what confuses them.

> **This is the most important week in the schedule.** Everything before it is your opinion about what corpus cleaning needs. This week is the first evidence.

## Week 20 · 11–15 Jan · v1.0

Mon–Tue: Act on feedback. Wed: README, licence, examples. Thu: Repo public, release notes. Fri: **Tag `v1.0`.** Announce on Corpora-List.

---

## Reality check

| | |
|---|---|
| Scheduled hours to v1.0 | ~180 (20 weeks, minus 2 rest weeks and 2 holiday weeks) |
| Probability of hitting mid-January | **~40%** |
| Probability of hitting end of February | ~75% |

The gap is reflow. If weeks 10–12 overrun — and they usually do — everything shifts. That's expected, not failure. The schedule's job is sequencing, not prophecy.

**If you fall behind, cut in this order:** catchwords → OCR artifacts → structure annotation → dialogue reflow. Never cut: the report, the tests, or week 19.

---

## After v1.0

Decide then, not now, with real usage data in hand:

- **GUI** (weeks 21–34) — only if colleagues actually ask for it. Build UI for the 6–7 stages they use, not all 19.
- **Tool paper** — 4–6 weeks of evenings. Highest return on academic credibility, and the thing that gives you institutional cover to keep maintaining this in year three.
- **v2 features** — deduplication, TEI export, parallel alignment. All deferrable.

My honest recommendation: **paper before GUI.** The paper is fewer hours, longer-lived, and makes the GUI easier to justify later.
