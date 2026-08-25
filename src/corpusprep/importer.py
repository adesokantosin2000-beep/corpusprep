"""
corpusprep.importer
===================

Import a text file into a Document, handling the things that break naive
loaders: byte-order marks, mixed line endings, and non-UTF-8 encodings.

Encoding detection sits behind ``detect_encoding`` so the backend can later be
swapped for charset-normalizer without touching anything else. The stdlib
fallback chain below is deliberate — it means the tool runs on a bare Python
install with no pip step, which matters for a first release.
"""

from __future__ import annotations

import codecs
from pathlib import Path

from .document import Document
from .formats import UnsupportedFormat, extract, is_container  # noqa: F401

#: Tried in order. utf-8-sig first so a BOM is consumed rather than becoming
#: a stray U+FEFF at the start of the first token.
FALLBACK_CHAIN = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

BOM_TABLE = [
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
]


def detect_encoding(raw: bytes) -> tuple[str, bool, float]:
    """Return (encoding, had_bom, confidence).

    Confidence is crude but honest: 1.0 for a BOM (unambiguous), 0.9 for
    clean UTF-8 (multi-byte sequences are self-validating), 0.5 for a
    successful fallback decode, which could still be the wrong codepage.
    """
    for bom, enc in BOM_TABLE:
        if raw.startswith(bom):
            return enc, True, 1.0

    try:
        raw.decode("utf-8")
        return "utf-8", False, 0.9
    except UnicodeDecodeError:
        pass

    for enc in FALLBACK_CHAIN:
        try:
            raw.decode(enc)
            return enc, False, 0.5
        except UnicodeDecodeError:
            continue

    return "latin-1", False, 0.2  # latin-1 cannot fail; last resort


def detect_newline(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    cr = raw.count(b"\r") - crlf
    if crlf >= lf and crlf >= cr:
        return "\r\n"
    if cr > lf:
        return "\r"
    return "\n"


def load(path: str | Path) -> Document:
    """Read a file into a Document with normalised line endings.

    Plain text is decoded directly. Container formats (.docx, .epub, .html)
    are unpacked first by :mod:`corpusprep.formats`, which emits one line per
    paragraph so the segmenter sees the same shape it would from a .txt file.

    Line endings are normalised to ``\\n`` internally and the original is
    recorded, so output can either preserve or normalise them by choice
    rather than by accident.
    """
    path = Path(path)

    if path.suffix.lower() == ".pdf":
        return _load_pdf(path)

    if is_container(path):
        return _load_container(path)

    raw = path.read_bytes()

    encoding, had_bom, confidence = detect_encoding(raw)
    newline = detect_newline(raw)
    text = raw.decode(encoding, errors="replace")

    # Strip any BOM the codec didn't consume (e.g. utf-8 read without -sig).
    if text.startswith("﻿"):
        text = text.lstrip("﻿")
        had_bom = True

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    doc = Document(
        source_path=path,
        lines=lines,
        encoding=encoding,
        had_bom=had_bom,
        newline=newline,
        meta={
            "encoding_confidence": confidence,
            "source_bytes": len(raw),
            "replacement_chars": text.count("�"),
        },
    )

    if confidence < 0.6:
        doc = doc.with_note(
            f"Encoding detected as {encoding} with low confidence "
            f"({confidence:.1f}). Check output for mojibake."
        )
    if doc.meta["replacement_chars"]:
        doc = doc.with_note(
            f"{doc.meta['replacement_chars']} undecodable byte(s) replaced "
            f"with U+FFFD. The source file may be damaged."
        )
    return doc


class UnreadablePDF(ValueError):
    """A PDF this tool cannot read, with the reason attached.

    Raised rather than returned as an empty Document, because a Document with
    no lines looks like a very short book. **The caller must be forced to
    notice**, which is the whole reason this class exists: the failure it
    guards against is a PDF that extracts 930 lines of byte 0x01 and passes
    every check that asks only whether text came out.
    """

    def __init__(self, extraction):
        super().__init__(extraction.note)
        self.extraction = extraction


def _load_pdf(path: Path) -> Document:
    """Load a PDF, refusing it with an explanation when it cannot be read."""
    from . import pdf as _pdf

    e = _pdf.extract(path)
    if not e.usable:
        raise UnreadablePDF(e)

    doc = Document(
        source_path=path,
        lines=e.lines,
        encoding=f"utf-8 (from pdf, {e.kind})",
        had_bom=False,
        newline="\n",
        meta={
            "encoding_confidence": 1.0,
            "source_bytes": path.stat().st_size,
            "replacement_chars": 0,
            "container": "pdf",
            "pdf_kind": e.kind,
            "pdf_pages": e.pages,
            "pdf_letter_ratio": round(e.letter_ratio, 4),
            # The one thing PDF gives that no other format does. Every other
            # input makes the furniture rules infer page boundaries from an
            # ascending run of page numbers; here they are stated.
            "page_starts": e.page_starts,
            "note": e.note,
        },
    )
    return doc


def _load_container(path: Path) -> Document:
    """Load .docx / .epub / .html by extracting text first.

    Container formats carry their own encoding declaration internally (all
    three are UTF-8 by specification), so encoding detection does not apply —
    confidence is recorded as 1.0 and the container type is noted.
    """
    text, meta = extract(path)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    doc = Document(
        source_path=path,
        lines=lines,
        encoding=f"utf-8 (from {meta.get('container', 'container')})",
        had_bom=False,
        newline="\n",
        meta={
            "encoding_confidence": 1.0,
            "source_bytes": path.stat().st_size,
            "replacement_chars": text.count("�"),
            **meta,
        },
    )

    doc = doc.with_note(
        f"Text extracted from {meta.get('container', '?')}. "
        f"Formatting, images and footnotes were discarded; paragraph "
        f"structure was preserved."
    )
    if doc.meta["replacement_chars"]:
        doc = doc.with_note(
            f"{doc.meta['replacement_chars']} character(s) could not be "
            f"decoded from the container."
        )
    return doc
