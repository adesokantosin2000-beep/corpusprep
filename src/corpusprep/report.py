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
