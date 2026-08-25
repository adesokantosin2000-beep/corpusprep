"""
corpusprep.pdf
==============

Text extraction from PDF, and — more importantly — an honest account of when
it has failed.

**A PDF is not a text format.** It describes marks on a page. Whether any of
those marks can be read back as characters depends on what the producer chose
to embed, and there are four distinct outcomes rather than the obvious two:

    text        a usable text layer. Extraction returns language.
    ocr         a text layer written by OCR over page images. Usable, noisy.
    unmapped    a text layer that extracts without error and contains no
                readable characters at all.
    image       no text layer. Nothing to extract.

**The third is the one that matters, and it was not in the design.** It was
found on the first real PDF this package was given: Sinclair's *Basic Text
Processing* (1991), a 25-page scan. Extraction succeeded, threw nothing, and
returned 930 non-blank lines in which every single character was byte 0x01.
The fonts are subsetted and their ToUnicode maps are broken, so the glyph codes
never become letters.

A check of the form "did we get any text?" answers **yes, 930 lines** and hands
the researcher a corpus of control characters. That is precisely the silent
failure this whole package exists to prevent, and it appeared within an hour of
PDF work beginning.

So the test is not whether text came out. It is whether what came out is
language::

    if the extracted text contains almost no letters, the extraction failed,
    however much of it there is.

**Page boundaries come free.** Every other input format forces the furniture
rules to infer where pages begin, from an ascending run of page numbers — the
most fragile inference in the package, and the one that destroyed 63 lines of a
ballad collection in Week 2. A PDF states it. Extraction records the boundaries
so the rules can use a fact instead of a guess.

`pypdf` is the only dependency this package has, and it is optional: absent, a
PDF is refused with an instruction rather than a traceback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Below this proportion of letters, the extracted text is not language.
#:
#: Real prose runs 70–80% letters; the rest is spaces and punctuation. The
#: Sinclair file scores 0.0%. Nothing observed sits between, so this is set well
#: clear of both rather than tuned, and the reason to prefer a low value is that
#: **the cost of a false alarm is a message, and the cost of a miss is a corpus
#: of control characters.**
MIN_LETTER_RATIO = 0.35

#: Shortest extraction worth judging. A one-page PDF of a title alone is not
#: evidence that the file is broken.
MIN_CHARS_TO_JUDGE = 200

#: Proportion of pages that must carry text before a file counts as having a
#: text layer at all. A scan with an accidental text box on one page has not
#: been OCR'd.
MIN_PAGES_WITH_TEXT = 0.5

TEXT = "text"
OCR = "ocr"
UNMAPPED = "unmapped"
IMAGE = "image"

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


@dataclass
class Extraction:
    """What came out of a PDF, and whether it can be used."""

    kind: str                       # TEXT | OCR | UNMAPPED | IMAGE
    lines: list[str] = field(default_factory=list)
    #: 0-based line index at which each page begins. The gift of this format.
    page_starts: list[int] = field(default_factory=list)
    pages: int = 0
    letter_ratio: float = 0.0
    note: str = ""

    @property
    def usable(self) -> bool:
        return self.kind in (TEXT, OCR)


def letter_ratio(text: str) -> float:
    """Proportion of characters that are letters in any script.

    Unicode-aware on purpose: a Yoruba or Polish text is not less readable for
    having characters outside ASCII, and an ASCII-only test would report a
    perfectly good extraction as broken.
    """
    if not text:
        return 0.0
    return len(_LETTER.findall(text)) / len(text)


def available() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def extract(path: str | Path) -> Extraction:
    """Read a PDF, and say plainly what kind of PDF it turned out to be."""
    if not available():
        return Extraction(
            kind=IMAGE,
            note="PDF support needs pypdf, which is not installed. "
                 "Install it with: pip install pypdf")

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError, EmptyFileError

    path = Path(path)
    try:
        reader = PdfReader(str(path))
    except EmptyFileError:
        return Extraction(kind=IMAGE, note="This file is empty (0 bytes). "
                                           "The copy or download did not finish.")
    except (PdfReadError, OSError) as e:
        return Extraction(kind=IMAGE,
                          note=f"This file could not be opened as a PDF: {e}")

    lines: list[str] = []
    page_starts: list[int] = []
    with_text = 0
    for page in reader.pages:
        page_starts.append(len(lines))
        try:
            text = page.extract_text() or ""
        except Exception:
            # One unreadable page must not lose the other three hundred.
            text = ""
        if text.strip():
            with_text += 1
        lines.extend(text.splitlines())

    n = len(reader.pages)
    joined = "\n".join(lines)
    ratio = letter_ratio(joined)
    base = dict(lines=lines, page_starts=page_starts, pages=n, letter_ratio=ratio)

    if n and with_text / n < MIN_PAGES_WITH_TEXT:
        return Extraction(
            kind=IMAGE, **base,
            note=f"Only {with_text} of {n} pages carry any text. This is a "
                 f"scan without an OCR layer, so there is nothing to extract. "
                 f"Running OCR on it first would produce a file this tool can "
                 f"read.")

    if len(joined) >= MIN_CHARS_TO_JUDGE and ratio < MIN_LETTER_RATIO:
        return Extraction(
            kind=UNMAPPED, **base,
            note=f"This PDF has a text layer and it is not readable: only "
                 f"{100 * ratio:.1f}% of the extracted characters are letters, "
                 f"across {n} pages. The fonts are embedded without a working "
                 f"character map, so the text comes out as placeholder codes. "
                 f"**The page images are intact** — running OCR on the file "
                 f"would recover the text.")

    # An OCR layer over a scan and a born-digital text layer both extract
    # cleanly, and are told apart downstream by the damage in the text rather
    # than by anything in the file. Reported as OCR only where the producer
    # says so, because guessing here would be a claim the file does not support.
    producer = ""
    try:
        producer = " ".join(str(v) for v in (reader.metadata or {}).values())
    except Exception:
        pass
    scanned = bool(re.search(r"abbyy|tesseract|finereader|scan|ocr",
                             producer, re.I))
    return Extraction(
        kind=OCR if scanned else TEXT, **base,
        note=f"{n} pages, {len(lines):,} lines, "
             f"{100 * ratio:.0f}% letters."
             + (" Produced by OCR software." if scanned else ""))
