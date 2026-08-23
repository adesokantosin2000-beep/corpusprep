# CorpusPrep — Design Specification v0.2

**A desktop corpus preparation tool for linguists**

Author: Tosin Adesokan
Date: 29 July 2026 (v0.2 — revised after prototype)
Status: Validated in part by a working prototype

> **v0.2 changes.** A working prototype now exists (`corpusprep/`, 34 passing
> tests) covering import, segmentation, region selection, variant generation
> and logging. Two additions came out of building it: **§3a segmentation as a
> first-class step** and **§4a variant outputs**. Both changed the architecture
> rather than adding to it. §9 roadmap re-sequenced accordingly.

---

## 1. Positioning

AntConc (Laurence Anthony) and WordSmith Tools (Mike Scott) are *analysis* tools. They assume you already have a clean corpus. But almost nobody does — texts arrive as Gutenberg dumps, PDF extractions, OCR output, web scrapes, and transcription files, and every researcher rebuilds the same fragile cleaning scripts from scratch.

**CorpusPrep fills the stage before AntConc.** It is the tool you run to turn raw text into an analysis-ready corpus, with a full record of what was changed.

The competitive claim is not "it cleans text" — regex scripts do that. It is:

> **Every transformation is visible, reversible, reproducible, and documented.**

That is what makes cleaning publishable rather than embarrassing. Reviewers can ask "what did you remove?" and you can hand them a file.

### Design principles

| Principle | Implication |
|---|---|
| **Never destroy the original** | Input files are opened read-only. Output always goes to a new location. |
| **Show before you commit** | Every stage previews its effect with a diff before the batch runs. |
| **Nothing silent** | Each stage reports what it changed and how much. Anomalies are flagged, not hidden. |
| **Recipes, not code** | A cleaning configuration is a saveable, shareable, citable file. |
| **Conservative by default** | When a rule is uncertain, flag for review rather than delete. |
| **Zero-install** | Single executable, like AntConc. No Python setup, no pip. |

### Naming

Working title is *CorpusPrep*. Alternatives to consider: **TextForge**, **Cleanse**, **Prep** — or follow the AntConc convention of author-initial + function (e.g. **AdePrep**). Check for existing use in the corpus linguistics literature before committing; a name collision is expensive later.

---

## 2. What the prototype taught us

`clean_jane_eyre.py` is a sound proof of concept, and the stage-per-function structure carries directly into the new architecture. But it has failure modes that the product must not inherit. Each was reproduced and confirmed by running the actual regexes.

### Confirmed bugs

**B1 — Paragraph-swallowing boilerplate regex (severe, silent data loss)**
The pattern `^(Produced|...|Note:)[^\n]*(\n[^\n]+)*` continues consuming until a blank line. Any *novel* paragraph that begins with one of those words is deleted entirely. Tested: a three-line paragraph beginning "Note:" was removed in full, with no warning.

**B2 — All-caps prose deleted as a running header**
`^[A-Z][A-Z\s\.\,\-\']{2,55}$` matches legitimate emphatic prose, inscriptions, letters, and telegrams — all common in 19th-century novels. Combined with the `prev_blank OR next_blank` condition (which is true for nearly every isolated line), the rule is far more aggressive than intended.

**B3 — Dead code in chapter handling**
`keep_patterns` is checked before `header_patterns`, and `^CHAPTER\s+[IVXLCDM\d]+` always matches first. The chapter-header removal branch can never execute.

**B4 — Standalone-number rule removes content**
`^\s*\d{1,4}\s*$` removes any line containing only digits. In a novel that is usually a page number; in a letter, a table, a verse-numbered text, or a date on its own line, it is content. Tested: a line reading `1847` was deleted.

### Structural gaps

- **No encoding detection.** Hardcoded UTF-8 crashes on Latin-1 and Windows-1252 sources, which are the majority of older archive files.
- **No de-hyphenation.** `exam-\nple` survives into the corpus and inflates the type count with junk types. This is the single biggest quality problem in PDF- and OCR-derived corpora.
- **No line unwrapping.** Output remains hard-wrapped at ~70 characters. Sentence splitters and some collocation span calculations behave differently on hard-wrapped text.
- **Indentation destroyed.** `line.strip()` plus internal-space collapsing flattens verse, drama, and any aligned material. Fatal for poetry corpora.
- **No report.** After a run you cannot say what was removed, so you cannot defend the corpus in a methods section.
- **Hardcoded paths, single file.** No batch, no reuse.

**Design conclusion:** replace pure-regex heuristics with **statistical detection plus human confirmation** wherever the target is repetitive structure (headers, footers, page furniture). A running head is not "a line that looks like a title" — it is *a short line that recurs many times at regular intervals*. That is measurable, and far safer.

---

## 3. Architecture

Strict separation between engine and interface. The engine never imports GUI code, which keeps it testable, scriptable, and reusable.

```
corpusprep/
├── core/                    # Pure Python. No GUI dependency.
│   ├── document.py          # Document: text + provenance + metadata
│   ├── pipeline.py          # Pipeline: ordered stages, execution, rollback
│   ├── stage.py             # Stage ABC + StageReport
│   ├── detect.py            # Encoding, source-type, and structure detection
│   ├── profile.py           # Recipe load/save (JSON)
│   ├── report.py            # Statistics, diffs, audit log
│   └── stages/              # One module per cleaning operation
│       ├── encoding.py
│       ├── boilerplate.py
│       ├── furniture.py     # Page numbers, running heads, catchwords
│       ├── hyphenation.py
│       ├── reflow.py
│       ├── markup.py        # HTML/XML/OCR artifacts
│       ├── whitespace.py
│       └── annotate.py      # Structural tagging, metadata headers
├── cli/
│   └── __main__.py          # Headless batch runner
├── gui/
│   ├── app.py
│   ├── panels/              # FileList, PipelineEditor, PreviewPane, LogPane
│   └── widgets/             # DiffView, StageCard, ProgressBar
└── resources/
    ├── profiles/            # Bundled recipes
    └── wordlists/           # For de-hyphenation validation
```

### The Stage contract

Every cleaning operation implements one interface. This is the core abstraction — get it right and everything else composes.

```python
class Stage(ABC):
    id: str                # "furniture.running_heads"
    label: str             # "Remove running headers"
    description: str       # Shown in GUI tooltip
    params: dict           # User-configurable, JSON-serialisable

    @abstractmethod
    def apply(self, doc: Document) -> StageResult:
        """Return a NEW Document plus a report. Must not mutate input."""

    def preview(self, doc: Document, limit: int = 50) -> list[Change]:
        """Return proposed changes WITHOUT applying them."""
```

```python
@dataclass
class StageResult:
    document: Document
    report: StageReport      # chars_removed, lines_removed, changes[], warnings[]
```

Three consequences worth noting:

1. `apply` returning a new `Document` makes undo free — keep the previous object.
2. `preview` being separate from `apply` is what enables the confirm-before-delete workflow.
3. Because stages are data-driven (`params` is a plain dict), a pipeline serialises to JSON with no custom encoder.

### Document

```python
@dataclass
class Document:
    text: str
    source_path: Path
    encoding: str            # As detected
    metadata: dict           # Title, author, date, genre — for corpus headers
    protected: list[Span]    # Regions no stage may modify (verse, tables, quotes)
    history: list[StageReport]
```

`protected` is important and non-obvious. Verse blocks, tabular data, and drama speech prefixes must survive whitespace normalisation and reflow. Detecting them **once**, up front, and then having every stage respect the spans is far more reliable than teaching each stage to recognise verse independently.

---

---

## 3a. Segmentation — the step before cleaning

**This is the structural change in v0.2.** The v0.1 design went straight from
raw text to cleaning stages that stripped material by pattern. That is what
made the original script dangerous: a rule that *identifies* is also a rule
that *deletes*, so a false positive is silent data loss.

The prototype separates the two:

```
import → SEGMENT (label only) → SELECT (user chooses) → CLEAN → RENDER
```

Segmentation assigns every line to exactly one labelled `Region`:

| Label | Contains |
|---|---|
| `pg_header` | Project Gutenberg header block |
| `pg_licence` | Licence text — marked or unmarked |
| `front_matter` | Title, byline, preface, dedication, contents, editorial notes |
| `body` | The work, sub-segmented by chapter |
| `back_matter` | Appendix, index, notes, colophon |
| `unknown` | Nothing matched — **retained by default** |

Three properties make this safe, and all three are tested:

1. **Detection cannot delete.** The segmenter only labels. Removal is a
   separate step driven by explicit selection.
2. **Total coverage.** Every content line belongs to a region;
   `coverage_gaps()` verifies it and the log reports it. Unmatched text
   becomes `unknown` and is kept.
3. **Precedence-based overlap resolution.** When two rules claim the same
   lines, Gutenberg apparatus outranks body. A licence block inside a
   chapter's range is still licence text. A region split this way is emitted
   as two regions rather than silently absorbing the intruder.

### Licence detection without markers

Many circulating files have had their PG sentinels stripped — including the
Jane Eyre file in this project, which contains no PG markers at all. So marker
detection cannot be the only mechanism.

The fallback scores each blank-line-delimited block against a list of PG legal
phrases and requires **two or more distinct phrases plus the word
"gutenberg"**. A novel discussing copyright, the public domain, or a trademark
dispute scores at most one and is never flagged. Tested both ways.

---



Ordering matters — several stages depend on earlier ones having run.

### Group 1 — Ingest and repair (always runs)

| Stage | Function |
|---|---|
| `encoding.detect` | `charset-normalizer` detection, BOM stripping, confidence score. Prompts if confidence is low rather than guessing. |
| `encoding.repair` | Mojibake repair via `ftfy` (`â€™` → `’`). |
| `encoding.normalise` | Unicode NFC. Optional NFKC (warn: NFKC is lossy for typographic distinctions). |

### Group 2 — Structural stripping

| Stage | Function |
|---|---|
| `boilerplate.gutenberg` | PG header/footer, all marker variants including the pre-2006 "small print" forms. |
| `boilerplate.custom` | User-supplied start/end markers for institutional archives. |
| `markup.html` | Tag stripping with entity resolution; optional tag→structure mapping. |
| `markup.ocr` | Common OCR artifacts: `rn`→`m` candidates, stray `|`, `[Illustration]` blocks — **flagged for review, never auto-applied**. |

### Group 3 — Page furniture *(the differentiating stage)*

Detection is statistical, not pattern-based:

- **Running heads/feet** — Collect all short lines (< 60 chars). Cluster by normalised similarity. A cluster with high frequency *and* roughly regular line-interval spacing is page furniture. A cluster appearing three times irregularly is not. Threshold user-adjustable; matches always previewed as a list before removal.
- **Page numbers** — Only remove a standalone integer when it sits inside a detected furniture zone **and** forms a monotonic sequence with its neighbours. This directly fixes bug B4: an isolated `1847` in prose has no sequence and survives.
- **Catchwords** — Last word of a page repeated as first word of the next (common in early modern printing).
- **Footnote markers** — Detect, then offer three routes: remove, retain inline, or extract to a parallel file.

### Group 4 — Text reconstruction *(highest linguistic value)*

| Stage | Function |
|---|---|
| `hyphenation.dejoin` | Rejoin `word-\nbreak`. Validated against a wordlist: if the joined form is a known word and the hyphenated form is not, join; if both are plausible (`re-form` / `reform`), flag for review. Never guesses silently. |
| `reflow.paragraphs` | Convert hard-wrapped lines to logical paragraphs. Respects `protected` spans, so verse and drama keep their line breaks. |
| `reflow.dialogue` | Preserve quotation and speaker-turn boundaries during reflow. |

### Group 5 — Normalisation

| Stage | Function |
|---|---|
| `whitespace.normalise` | Trailing space, tabs, blank-line runs. Indentation preserved inside protected spans. |
| `whitespace.punctuation` | Curly→straight quotes, dash normalisation. **Off by default** — many research questions depend on these distinctions. |
| `case.preserve` | No-op guard; exists to make explicit that CorpusPrep never lowercases. Casing is the analysis tool's decision, not the cleaner's. |

### Group 6 — Output annotation

| Stage | Function |
|---|---|
| `annotate.structure` | Optional `<chapter>`, `<p>`, `<head>` tags for corpus tools that consume them. |
| `annotate.header` | Prepend a metadata header (COCA-style or TEI-lite). |

---

---

## 4a. Variant outputs — several corpora from one source

**Second v0.2 addition.** A cleaning tool that emits one file forces an
irreversible choice at the worst moment: before you know whether the choice
matters. Emitting several costs almost nothing — segmentation has already been
done — and turns "did removing the preface affect my results?" from a
re-run into a comparison.

A **Variant** is a named region selection plus normalisation options. Built-ins:

| Variant | Keeps | For |
|---|---|---|
| `verbatim` | Everything | **The control.** Same encoding and line endings, nothing removed. Every other variant reports its delta against this. |
| `full` | All but PG apparatus | General use |
| `body-and-front` | Front matter + body | When the author's preface counts as authorial text |
| `body-only` | The work alone | Standard for stylistic analysis |
| `body-no-headings` | Body minus `CHAPTER` lines | Word lists and frequency counts |

Plus arbitrary custom selections (`--keep body,front_matter`).

**Why `verbatim` earns its place:** it makes every other number interpretable.
On Jane Eyre, `body-only` loses 0.5% of tokens against verbatim — consistent
with removing an 817-word preface and a byline, and inconsistent with having
eaten prose. Without the baseline that figure means nothing.

### The interpretation rule

> A large character drop with a near-zero token drop means **apparatus** was
> removed. A token drop of more than a few percent in `body-only` means
> **investigate before using the corpus.**

This single heuristic is what makes the log actionable rather than decorative.

---

## 5. Interface

Three-pane layout, following the AntConc convention that researchers already know.

```
┌──────────────────────────────────────────────────────────────────────┐
│  File  Pipeline  Profile  Help                                       │
├───────────────┬──────────────────────────┬───────────────────────────┤
│  CORPUS       │  PIPELINE                │  PREVIEW                  │
│               │                          │                           │
│ ☑ jane.txt    │ ☑ 1. Detect encoding     │ [Raw │ Cleaned │ Diff]    │
│ ☑ wuther.txt  │ ☑ 2. Gutenberg boiler.   │                           │
│ ☑ middle.txt  │ ☑ 3. Running heads  ⚙    │  - JANE EYRE              │
│ ☐ poems.txt   │ ☑ 4. Page numbers   ⚙    │    Chapter I              │
│               │ ☑ 5. De-hyphenate  ⚠ 12  │  + There was no possib-   │
│  [+ Add]      │ ☑ 6. Reflow              │    ility of taking...     │
│  [Folder…]    │ ☐ 7. Normalise quotes    │                           │
│               │                          │  ⚠ 12 items need review   │
│  4 files      │  [+ Add stage]           │     [Review now]          │
│  2.1 MB       │  Profile: Gutenberg ▾    │                           │
├───────────────┴──────────────────────────┴───────────────────────────┤
│  LOG   Stage 3: removed 412 lines matching 2 header clusters         │
│        Stage 5: joined 289 hyphens, 12 ambiguous → review            │
├──────────────────────────────────────────────────────────────────────┤
│  Output: ./cleaned/    [Dry run]  [Clean 4 files]                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Interaction rules

- **Diff is the primary view.** Users judge a cleaning tool by what it removed, so removal is what the interface shows first.
- **Warnings are actionable.** `⚠ 12` opens a review queue where each ambiguous case is accepted or rejected individually. Decisions are remembered per-corpus.
- **Dry run is prominent.** Full report, no files written.
- **Stage reordering by drag.** Dependencies enforced — reflow cannot precede de-hyphenation, and the UI blocks it with an explanation rather than failing at runtime.
- **Profile dropdown always visible.** Switching recipes is the most frequent action after the first session.

---

## 6. Profiles

A profile is the reproducibility unit and the feature most likely to drive adoption. Researchers can attach one to a paper, and a reader can reproduce the corpus exactly.

```json
{
  "name": "Project Gutenberg — 19th c. prose",
  "version": "1.0",
  "author": "T. Adesokan",
  "created": "2026-07-25",
  "stages": [
    {"id": "encoding.detect", "params": {"fallback": "utf-8"}},
    {"id": "boilerplate.gutenberg", "params": {"strict": true}},
    {"id": "furniture.running_heads",
     "params": {"min_repeats": 5, "max_length": 60, "confirm": true}},
    {"id": "furniture.page_numbers", "params": {"require_sequence": true}},
    {"id": "hyphenation.dejoin",
     "params": {"wordlist": "en_GB", "ambiguous": "review"}},
    {"id": "reflow.paragraphs", "params": {"preserve_verse": true}},
    {"id": "whitespace.normalise", "params": {"max_blank_lines": 1}}
  ]
}
```

Ship with tested profiles for: Project Gutenberg prose, Gutenberg verse, PDF extraction, OCR/historical, web scrape, and transcription. These are the tool's accumulated expertise — the reason someone uses CorpusPrep instead of writing their own regexes.

---

## 7. Reporting

Every run produces a report next to the output. This is what makes the corpus defensible.

```
CorpusPrep Cleaning Report
Generated: 2026-07-25 14:32  ·  Profile: Gutenberg 19th c. prose v1.0
Source: jane_eyre_raw.txt (1,047,382 chars, detected UTF-8, confidence 1.00)
Output: jane_eyre_clean.txt (1,021,558 chars)

Stage                     Removed      Modified    Flagged
─────────────────────────────────────────────────────────
Gutenberg boilerplate      18,204 ch          0          0
Running headers               412 ln          0          0
Page numbers                  387 ln          0          0
De-hyphenation                  0            289        12
Paragraph reflow                0         14,203         0
Whitespace                  6,932 ch          0          0

Net change: -2.5% characters, -0.0% word tokens
Word tokens: 187,432 → 187,401  (-31)
Word types:   14,220 →  13,908  (-312, de-hyphenation)

⚠ 12 items flagged for review — see jane_eyre_review.txt
```

The token/type figures are the honesty check. A cleaning run that removes 2.5% of characters but almost no word tokens has removed furniture, not prose — exactly what you want to be able to demonstrate. A large token drop means something went wrong, and the report surfaces it immediately rather than after analysis.

---

## 8. Technical decisions

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem, and you already work in it. |
| GUI | **PySide6** (Qt) | Official Qt binding, **LGPL** — permissive enough to distribute a closed or open binary. PyQt is GPL and would force your whole app to GPL. Tkinter looks dated next to AntConc. |
| Encoding | `charset-normalizer` | Actively maintained, MIT, and the default backend for `requests`. See note below — `chardet` 7.0 benchmarks better but carries licensing risk. |
| Mojibake | `ftfy` | Mature, well-tested, no real competitor. |
| Regex | `regex` module | Unicode property support (`\p{L}`) that stdlib `re` lacks — matters for non-English corpora. |
| Diff | stdlib `difflib` | Adequate for the sizes involved. |
| Tagging (later) | `spaCy` | Optional dependency; keep the core install light. |
| Packaging | PyInstaller (`--onefile`) | Matches AntConc's zero-install distribution. |
| Tests | `pytest` + golden files | Fixture corpora with hand-verified expected output. |

**On performance:** hold whole files in memory. A 100 MB corpus is unusual and modern machines handle it. Stream only if profiling shows a real problem — premature streaming would complicate every stage for no benefit.

**On licensing — two live issues:**

*GUI.* The PySide6-vs-PyQt distinction is the one decision here that is expensive to reverse. PySide6 is LGPL; PyQt is GPL or commercial. Choosing PyQt now and wanting a non-GPL release later means rewriting the entire UI layer.

*Encoding detection.* `chardet` 7.0 (2026) was rewritten with AI assistance and relicensed from LGPL-2.1 to MIT. It now benchmarks substantially faster and more accurate than `charset-normalizer`. However, the relicensing is disputed — the original author contests the maintainer's right to relicense, and the copyright claim itself is questioned given the code was largely LLM-generated. For software you intend to distribute to universities, an unresolved licence dispute in a dependency is a liability disproportionate to the performance gain. **Recommendation: use `charset-normalizer` now; revisit if the dispute resolves.** Keep detection behind a thin adapter in `detect.py` so swapping the backend is a one-file change.

---

## 9. Roadmap

> **Phase 0 — DONE (prototype, 29 July 2026).** `Document`, `Region`,
> segmentation, licence detection, region selection, variant rendering,
> Markdown + JSON logging, CLI (`inspect` / `clean` / `list-variants`),
> 34 passing tests. Verified on Jane Eyre and on a synthetic marked-up
> Gutenberg fixture. This collapses most of the original Phase 1.

**Phase 1 — Engine hardening (weeks 1–2, was 1–3)**
Retro-fit the `Stage` abstraction over the working segmenter, add `Pipeline`
and `StageReport`, add profiles as saveable JSON, convert the ad-hoc tests to
golden-file tests. *Deliverable: the prototype's behaviour, properly composable.*

**Phase 2 — The hard stages (weeks 4–6)**
Statistical furniture detection. De-hyphenation with wordlist validation. Reflow with protected spans. *This is the phase that makes the tool worth using — budget accordingly and expect it to overrun.*

**Phase 3 — GUI (weeks 7–10)**
Three-pane shell, pipeline editor, diff preview, review queue, log.

**Phase 4 — Polish (weeks 11–12)**
Profile manager, bundled profiles, report generation, PyInstaller builds for Windows and macOS.

**Phase 5 — Release**
Documentation, a worked tutorial, sample corpora. Announce on Corpora-List and the AntConc/CL community channels — that is where the users are.

**Deferred to v2:** language detection, parallel-corpus alignment, TEI import/export, deduplication across a corpus, plugin API for custom stages.

---

## 10. Open questions

1. **Name and licence.** Open source (builds academic credibility and citations) or free-but-closed (AntConc's model)? This affects the PySide6 decision only mildly, but affects everything else.
2. **Scope boundary.** Does CorpusPrep stop at clean text, or also handle corpus *assembly* — metadata management, sub-corpus definition, file organisation? Assembly is a genuine unmet need but roughly doubles the project.
3. **Non-English support.** Designing for it from the start (Unicode properties, per-language wordlists, script-aware reflow) costs little now and is painful to retrofit. Recommend building it in.
4. **Validation partner.** The fastest route to credibility is a colleague with a messy real corpus who will use Phase 2 and complain loudly. Worth lining up now.

---

## 11. Immediate next step

Refactor `clean_jane_eyre.py` into the `Stage` interface — same logic, new shape — and run it on Jane Eyre to confirm the architecture holds before building anything further. That is a day's work and it de-risks the whole design.
