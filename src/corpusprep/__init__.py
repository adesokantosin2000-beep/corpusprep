"""
CorpusPrep — corpus preparation for linguists.

Prototype v0.1.0. Stdlib only; no installation required.

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

__version__ = "0.1.0"

__all__ = [
    "load", "segment", "render", "render_all", "prepare",
    "Document", "Region", "Variant", "VariantResult",
    "BUILTIN", "DEFAULT_SET", "custom_variant", "write_log", "analyse",
    "PG_HEADER", "PG_LICENCE", "FRONT_MATTER", "BODY", "BACK_MATTER", "UNKNOWN",
]


def analyse(path: str | Path) -> Document:
    """Import a file, segment it, and detect page furniture.

    The single place where the two detection stages are combined, so that
    callers cannot accidentally render a document whose furniture was never
    looked for. Detection only: nothing is removed here.
    """
    from .footnotes import find_in_document as find_footnotes
    from .furniture import find_in_document

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
) -> tuple[Document, list[VariantResult]]:
    """Import, segment, and render variants in one call.

    If ``out_dir`` is given, cleaned files and the preprocessing log are
    written there. The source file is never modified.
    """
    doc = analyse(path)
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

    return doc, results
