"""
corpusprep.report
=================

Preprocessing log. Two formats from one run:

* ``.md`` — human-readable, meant to be readable by a supervisor or reviewer
  and quotable in a methods section.
* ``.json`` — machine-readable, so a later run can be compared automatically.

The token/type figures are the honesty check. A variant that removes 3% of
characters but almost no word tokens has removed apparatus, not prose. A large
token drop means something went wrong, and it shows up here rather than three
months later in your results.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ._version import __version__
from .document import Document
from .variants import VariantResult

LABEL_ORDER = ["pg_header", "front_matter", "body", "back_matter", "pg_licence", "unknown"]


def _pct(part: float, whole: float) -> str:
    if not whole:
        return "n/a"
    return f"{100.0 * part / whole:+.1f}%"


def segmentation_table(doc: Document) -> str:
    rows = [
        "| # | Label | Kind | Title | Lines | Words | Conf |",
        "|---|-------|------|-------|-------|-------|------|",
    ]
    from .document import count_tokens_types

    for i, r in enumerate(doc.regions, 1):
        tokens, _ = count_tokens_types(doc.region_text(r))
        title = (r.title[:40] + "…") if len(r.title) > 40 else r.title
        rows.append(
            f"| {i} | {r.label} | {r.kind} | {title or '(untitled)'} | "
            f"{r.start + 1}–{r.end} | {tokens:,} | {r.confidence:.2f} |"
        )
    return "\n".join(rows)


def no_op_notes(doc: Document, results: list[VariantResult]) -> list[str]:
    """What to say when every rule declined.

    A tester cleaned a corpus of Instagram comments and the log told her two
    things: that 0 tokens had been removed, and that no structural headings
    were found. Both were true and neither was useful. She could not tell
    whether the tool had examined her text and found nothing to do, or failed
    to read it at all.

    **Silence is not a result.** Each rule that declined says something about
    the text, and it is cheap to say it. Returns an empty list when at least
    one rule fired, because then the report already has content.
    """
    from .protect import is_wrapped

    if doc.interface or doc.furniture or doc.hyphen_breaks:
        # Something was found, even if no variant asked for it to go. Finding
        # is a result; the catalogue below is for the case where there is none.
        return []

    did_something = any(
        r.dropped
        or r.stats.get("furniture_removed")
        or r.stats.get("running_heads_stripped")
        or r.stats.get("footnote_lines_removed")
        or r.stats.get("hyphens_joined")
        or r.stats.get("hyphens_flagged")
        or r.stats.get("paragraphs_joined")
        for r in results
    )
    if did_something:
        return []

    lines = [l for l in doc.lines if l.strip()]
    med = 0
    if lines:
        widths = sorted(len(l.rstrip()) for l in lines)
        med = widths[len(widths) // 2]

    notes = []
    labels = {r.label for r in doc.regions}
    if "pg_header" not in labels and "pg_licence" not in labels:
        notes.append("**No Project Gutenberg apparatus.** The header and "
                     "licence blocks are matched verbatim, so this means the "
                     "file did not come from Gutenberg, or came from it "
                     "already stripped.")
    notes.append("**No structural headings.** Nothing matched `Chapter`, "
                 "`Book`, `Part`, `Act`, `Scene`, `Letter`, a roman numeral "
                 "or a bare ascending numeral standing on its own line. A "
                 "text with no divisions is not a defective text; it means "
                 "`body-only` and `verbatim` are necessarily the same file.")
    if not doc.meta.get("furniture"):
        notes.append("**No page furniture.** Running heads are found by their "
                     "*interval*, which requires an ascending page-number "
                     "sequence to establish a page length. Born-digital text "
                     "has no pages, so this rule can never fire on it.")
    if not is_wrapped(doc.lines):
        notes.append(f"**Nothing to rejoin.** The text is not hard-wrapped "
                     f"(median line {med} characters, one line per "
                     f"paragraph), so reflow and protected spans had no "
                     f"question to answer.")
    else:
        notes.append(f"**Nothing to rejoin.** Lines are short (median {med} "
                     f"characters), which is the shape wrapped text has, but "
                     f"no block looked like one paragraph broken across "
                     f"several lines. Short lines that are each a whole "
                     f"utterance — a comment, a caption, a line of a "
                     f"transcript — are not wrapped, and rejoining them would "
                     f"be damage.")
    notes.append("**No word broken across a line.** De-hyphenation looks for "
                 "a word ending in a hyphen at a line end; there were none.")
    return notes


def build_markdown(doc: Document, results: list[VariantResult]) -> str:
    src = doc.stats()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    a = lines.append

    a("# CorpusPrep: Preprocessing Log")
    a("")
    a(f"**Source:** `{doc.source_path.name}`  ")
    a(f"**Generated:** {now}  ")
    a(f"**Encoding detected:** {doc.encoding} "
      f"(confidence {doc.meta.get('encoding_confidence', 0):.1f})"
      f"{', BOM stripped' if doc.had_bom else ''}  ")
    a(f"**Line endings:** {doc.newline!r} → normalised to `\\n`  ")
    a("")
    a("## 1. Source")
    a("")
    a(f"- Characters: {src['characters']:,}")
    a(f"- Lines: {src['lines']:,}")
    a(f"- Word tokens: {src['word_tokens']:,}")
    a(f"- Word types: {src['word_types']:,}")
    a("")

    quiet = no_op_notes(doc, results)
    if quiet:
        a("## Nothing was removed, and here is what was looked for")
        a("")
        a("Every rule in this tool examined the text and declined. That is a "
          "result, not a failure — but it is only useful if you can see what "
          "was asked.")
        a("")
        for n in quiet:
            a(f"- {n}")
        a("")
        a("**What this means for your corpus.** The rules here are built for "
          "printed books turned into text: Gutenberg files, PDF extractions, "
          "library scans. Their apparatus — running heads, page numbers, "
          "editorial front matter, hyphens at line ends — is what there is to "
          "remove. Text that was born digital has none of it, and the honest "
          "answer is that your file is already as clean as this tool can make "
          "it.")
        a("")
        a("If your material carries a different kind of apparatus — interface "
          "labels, timestamps, usernames, boilerplate that repeats — that is "
          "worth reporting, because it is the sort of thing a rule can be "
          "built for and none of the rules here were.")
        a("")

    if doc.notes:
        a("### Import warnings")
        a("")
        for n in doc.notes:
            a(f"- ⚠ {n}")
        a("")

    a("## 2. Segmentation")
    a("")
    a(segmentation_table(doc))
    a("")

    counts: dict[str, int] = {}
    for r in doc.regions:
        counts[r.label] = counts.get(r.label, 0) + 1
    a("**Regions found:** " + ", ".join(
        f"{counts[l]} × {l}" for l in LABEL_ORDER if l in counts
    ))
    a("")

    gaps = doc.coverage_gaps()
    if gaps:
        a(f"⚠ **{len(gaps)} uncovered line range(s)**. This indicates a fault in segmentation: "
          f"{gaps[:5]}")
    else:
        a("✅ Every line is covered by exactly one region. No text can be lost "
          "except by explicit selection.")
    a("")

    fx = doc.meta.get("furniture")
    if fx:
        a("### Page furniture")
        a("")
        a(f"{fx['lines']} lines look like running heads or page numbers, on an "
          f"estimated page length of {fx['page_length']:g} lines.")
        a("")
        a("| Recurring line | Times | Why it was judged furniture |")
        a("|----------------|-------|------------------------------|")
        for s in fx["series"]:
            a(f"| `{s['text'][:34]}` | {s['occurrences']} | {s['reason']} |")
        a("")
        a("**Detected, not removed.** Furniture is stripped only by a variant "
          "with `drop_furniture` enabled, and no built-in variant enables it. "
          "The rule requires an ascending page-number sequence before it will "
          "claim a text is page-imaged at all, so a text without page numbers "
          "yields nothing.")
        a("")

    ui = doc.meta.get("interface")
    if ui:
        a("### Interface furniture")
        a("")
        a(f"{ui['lines']} lines look like labels an application printed rather "
          f"than text anyone wrote.")
        a("")
        a("| Control | Times | Why it was judged furniture |")
        a("|---------|-------|------------------------------|")
        for series in ui["series"]:
            a(f"| `{series['text'][:34]}` | {series['occurrences']} | "
              f"{series['reason']} |")
        a("")
        a("**Detected, not removed.** These lines go only if a variant sets "
          "`drop_interface`, and no built-in variant does. Every word here is "
          "ordinary English — `Like`, `Reply`, `Share` — so the rule refuses "
          "to fire at all unless the file itself is shaped like a scraped "
          "feed, and even then it takes only lines that sit *after* the text "
          "of a record rather than among it. Read the table before you turn "
          "removal on.")
        a("")

    a("## 3. Variants produced")
    a("")
    a("| Variant | Chars | Tokens | Types | vs verbatim (tokens) | Regions dropped |")
    a("|---------|-------|--------|-------|----------------------|-----------------|")
    for r in results:
        s = r.stats
        delta = (
            _pct(s["word_tokens"] - r.baseline["word_tokens"], r.baseline["word_tokens"])
            if r.baseline else "n/a"
        )
        a(f"| `{r.variant.name}` | {s['characters']:,} | {s['word_tokens']:,} | "
          f"{s['word_types']:,} | {delta} | {s['regions_dropped']} |")
    a("")

    a("## 4. What each variant removed")
    a("")
    for r in results:
        a(f"### `{r.variant.name}`")
        a("")
        a(f"*{r.variant.description}*")
        a("")
        if not r.dropped:
            a("Nothing removed.")
        else:
            a("| Removed region | Lines | Why it was identified |")
            a("|----------------|-------|------------------------|")
            for d in r.dropped:
                title = d.title or d.kind
                a(f"| {d.label}: {title[:38]} | {d.start + 1}–{d.end} | {d.evidence} |")
        if r.variant.drop_headings:
            a("")
            a("Chapter heading lines were also stripped.")
        if r.variant.drop_furniture:
            a("")
            a(f"{r.stats.get('furniture_removed', 0)} page furniture lines were "
              f"also removed from the regions kept above.")
        a("")

    a("## 5. Reproducing this run")
    a("")
    a("```")
    a(f"python -m corpusprep clean {doc.source_path.name} \\")
    a(f"    --variants {','.join(r.variant.name for r in results)}")
    a("```")
    a("")
    a("---")
    a("")
    a("*Interpretation note: a large character drop with a near-zero token drop "
      "means apparatus was removed, not prose. A token drop above a few percent "
      "in `body-only` is worth investigating before using the corpus.*")

    return "\n".join(lines)


def build_json(doc: Document, results: list[VariantResult]) -> dict:
    return {
        "tool": "corpusprep",
        "version": __version__,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "path": str(doc.source_path),
            "name": doc.source_path.name,
            "encoding": doc.encoding,
            "encoding_confidence": doc.meta.get("encoding_confidence"),
            "had_bom": doc.had_bom,
            "newline": doc.newline,
            "stats": doc.stats(),
            "notes": doc.notes,
        },
        "regions": [
            {
                "label": r.label,
                "kind": r.kind,
                "title": r.title,
                "start_line": r.start + 1,
                "end_line": r.end,
                "n_lines": r.n_lines,
                "confidence": r.confidence,
                "evidence": r.evidence,
            }
            for r in doc.regions
        ],
        "coverage_gaps": doc.coverage_gaps(),
        "interface": {
            "detected_lines": sorted(doc.interface),
            **(doc.meta.get("interface") or {}),
        },
        # Present and non-empty exactly when every rule declined, so a later
        # comparison can tell "nothing to do" from "did not run".
        "no_op_notes": no_op_notes(doc, results),
        # Line numbers, not a region list: furniture is a per-line property
        # that sits inside regions rather than beside them.
        "furniture": {
            "detected_lines": sorted(doc.furniture),
            **(doc.meta.get("furniture") or {}),
        },
        "variants": [
            {
                "config": r.variant.to_dict(),
                "stats": r.stats,
                "dropped_regions": [
                    {
                        "label": d.label,
                        "title": d.title,
                        "start_line": d.start + 1,
                        "end_line": d.end,
                        "evidence": d.evidence,
                    }
                    for d in r.dropped
                ],
            }
            for r in results
        ],
    }


def write(doc: Document, results: list[VariantResult], out_dir: Path, stem: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{stem}_log.md"
    js_path = out_dir / f"{stem}_log.json"
    md_path.write_text(build_markdown(doc, results), encoding="utf-8")
    js_path.write_text(
        json.dumps(build_json(doc, results), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return md_path, js_path
