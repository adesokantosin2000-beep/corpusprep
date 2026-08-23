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
    "BUILTIN", "DEFAULT_SET", "custom_variant", "write_log",
    "PG_HEADER", "PG_LICENCE", "FRONT_MATTER", "BODY", "BACK_MATTER", "UNKNOWN",
]


def prepare(
    path: str | Path,
    out_dir: str | Path | None = None,
    variants: list[str] | None = None,
) -> tuple[Document, list[VariantResult]]:
    """Import, segment, and render variants in one call.

    If ``out_dir`` is given, cleaned files and the preprocessing log are
    written there. The source file is never modified.
    """
    doc = segment(load(path))
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
