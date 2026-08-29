"""
CorpusPrep — corpus preparation for linguists.

Stdlib only; no installation required.

Quick use::

    from corpusprep import prepare
    doc, results = prepare("CBronte_Jane.txt", out_dir="cleaned")

Or from the command line::

    python -m corpusprep inspect CBronte_Jane.txt
    python -m corpusprep clean   CBronte_Jane.txt --out cleaned
"""

from __future__ import annotations

from pathlib import Path

from .document import (
    BACK_MATTER,
    BODY,
    FRONT_MATTER,
    PG_HEADER,
    PG_LICENCE,
    UNKNOWN,
    Document,
    Region,
)
from .importer import load
from .report import write as write_log
from .segment import segment
from .variants import BUILTIN, DEFAULT_SET, Variant, VariantResult, custom_variant, render, render_all

from ._version import __version__

__all__ = [
    "load", "segment", "render", "render_all", "prepare",
    "Document", "Region", "Variant", "VariantResult",
    "BUILTIN", "DEFAULT_SET", "custom_variant", "write_log", "analyse",
    "review",
    "PG_HEADER", "PG_LICENCE", "FRONT_MATTER", "BODY", "BACK_MATTER", "UNKNOWN",
]


def analyse(path: str | Path,
            decisions: dict | str | Path | None = None) -> Document:
    """Import a file, segment it, and detect page furniture.

    The single place where the two detection stages are combined, so that
    callers cannot accidentally render a document whose furniture was never
    looked for. Detection only: nothing is removed here.
    """
    from .footnotes import find_in_document as find_footnotes
    from .furniture import find_in_document
    from . import review as _review

    if decisions is not None and not isinstance(decisions, dict):
        decisions = _review.read(decisions)

    doc = segment(load(path))
    marked, candidates, page_length, catchwords = find_in_document(doc)
    doc = doc.with_furniture(marked)
    if marked:
        hits = [m for m in catchwords if m.accepted]
        doc.meta["furniture"] = {
            "lines": len(marked),
            "page_length": round(page_length, 1),
            "series": [
                {"text": c.text, "occurrences": len(c.lines), "reason": c.reason}
                for c in candidates if c.accepted
            ] + ([{
                "text": "(catchwords)",
                "occurrences": len(hits),
                "reason": f"each repeats the first word of the following page, "
                          f"on {len(hits)} of {len(catchwords)} pages",
            }] if hits else []),
        }
        doc.notes.append(
            f"{len(marked)} lines look like page furniture "
            f"(running heads or page numbers). Not removed unless requested."
        )

    from .dehyphenate import find_in_document as find_breaks
    breaks = find_breaks(doc)
    if decisions:
        doc = doc.with_decisions(decisions)
        _review.apply_to_breaks(breaks, decisions)
    doc = doc.with_hyphen_breaks(breaks)
    if breaks:
        undecided = [b for b in breaks if b.needs_review]
        doc.meta["hyphenation"] = {
            "breaks": len(breaks),
            "decided": len(breaks) - len(undecided),
            "flagged": len(undecided),
        }
        doc.notes.append(
            f"{len(breaks)} words are broken across a line break. "
            f"{len(breaks) - len(undecided)} can be resolved from this text's "
            f"own vocabulary; {len(undecided)} would need review."
        )

    from .interface import find_in_document as find_interface
    marked_ui, series = find_interface(doc)
    if marked_ui:
        doc = doc.with_interface(marked_ui)
        doc.meta["interface"] = {
            "lines": len(marked_ui),
            "series": [
                {"text": s.key, "occurrences": len(s.lines), "reason": s.reason}
                for s in series
            ],
        }
        doc.notes.append(
            f"{len(marked_ui)} lines look like interface furniture "
            f"(the labels an application printed, not text anyone wrote). "
            f"Not removed unless requested."
        )

    from .furniture import find_prefix_furniture
    edits = find_prefix_furniture(doc.lines)
    if edits:
        doc = doc.with_prefix_furniture(edits)
        doc.meta["prefix_furniture"] = {"lines": len(edits)}
        doc.notes.append(
            f"{len(edits)} lines begin with a running head welded to the page "
            f"text, as happens when each line holds a whole scanned page. "
            f"Removed only if you ask for page furniture to be dropped."
        )

    found = find_footnotes(doc)
    doc = doc.with_footnotes(found)
    paired = [f for f in found if f.paired]
    if found:
        doc.meta["footnotes"] = {
            "paired": len(paired),
            "unpaired": len(found) - len(paired),
            "lines": sum(len(f.body_lines) for f in paired),
        }
        note = f"{len(paired)} footnotes found"
        if len(found) > len(paired):
            note += (f", and {len(found) - len(paired)} bracketed labels that "
                     f"could not be paired and will not be touched")
        doc.notes.append(note + ". Retained unless you choose otherwise.")
    return doc


def prepare(
    path: str | Path,
    out_dir: str | Path | None = None,
    variants: list[str] | None = None,
    decisions: dict | str | Path | None = None,
) -> tuple[Document, list[VariantResult]]:
    """Import, segment, and render variants in one call.

    If ``out_dir`` is given, cleaned files and the preprocessing log are
    written there. The source file is never modified.
    """
    doc = analyse(path, decisions)
    results = render_all(doc, variants or DEFAULT_SET)

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(path).stem
        for r in results:
            (out_dir / f"{stem}__{r.variant.name}.txt").write_text(
                r.text, encoding="utf-8"
            )
        write_log(doc, results, out_dir, stem)

        # The queue is written whether or not anything is outstanding. A file
        # that appears only sometimes is a file nobody learns to look for.
        from . import review as _rv
        items = _rv.from_document(doc)
        if items:
            _rv.write(items, out_dir / f"{stem}__review.tsv",
                      existing=doc.decisions)

    return doc, results
