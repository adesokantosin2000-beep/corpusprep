"""
corpusprep.segment
==================

Segment a Document into labelled regions: Gutenberg apparatus, licence text,
front matter, body, back matter.

Detection strategy, in order of reliability:

1. **Explicit PG markers** (``*** START OF THE PROJECT GUTENBERG EBOOK ***``).
   Unambiguous when present. Many circulating files have already had them
   stripped, so this cannot be the only mechanism.

2. **Licence-text detection by keyword density.** Catches PG legal blocks even
   when the sentinel markers are gone. Requires several independent legal
   phrases in one paragraph, so ordinary prose mentioning "copyright" is safe.

3. **Structural headings.** The first ``CHAPTER``/``BOOK``/``PART`` heading
   marks the start of the body. Everything before it (after any PG apparatus)
   is front matter; anything after the last chapter that looks like apparatus
   is back matter.

Nothing is deleted here. Every line ends up inside exactly one region, and
that invariant is checked. Removal is a separate, explicit step.
"""

from __future__ import annotations

import re
from dataclasses import replace

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

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

PG_START = re.compile(
    r"\*{3}\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}", re.I
)
PG_END = re.compile(
    r"\*{3}\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}", re.I
)
#: Pre-2006 files used a different sentinel.
PG_START_OLD = re.compile(r"\*{3}\s*START OF THE PROJECT GUTENBERG.*", re.I)
PG_END_OLD = re.compile(r"\*{3}\s*END OF THE PROJECT GUTENBERG.*", re.I)

#: Opening of a transcriber / producer credit block.
#:
#: The original prototype had a rule like this and it was bug B1 — the pattern
#: ran to the end of the paragraph wherever it appeared, so any novel paragraph
#: beginning "Note:" or "Produced…" was silently destroyed. This version is
#: safe for two structural reasons:
#:
#:   1. It only labels a *block* (blank-line delimited); it can never run past
#:      the block it starts in.
#:   2. It only looks in a window at the head or tail of the content, where
#:      this apparatus actually lives. A paragraph mid-novel is never touched.
#:
#: And, as everywhere else here, labelling is not deleting.
TRANSCRIBER_OPENING = re.compile(
    r"^\s*(?:"
    r"Transcribed\s+from|Transcribed\s+by|Produced\s+by|Prepared\s+by|"
    r"Scanned\s+(?:and|by)|Digitized\s+by|Digitised\s+by|"
    r"E-?text\s+prepared\s+by|Proofread(?:ing|ers?)?\s+by|"
    r"Transcriber['’\u02bc]?s?\s+Notes?\b|Credits\s*:|Updated\s+editions\s+will"
    r")\b",
    re.IGNORECASE,
)

#: A line that is *only* the words "Transcriber's Note(s)". Unlike the prefix
#: patterns above this is unambiguous — no sentence of prose is exactly this —
#: so it needs no positional guard and is recognised anywhere in the text.
#: Note the apostrophe class: Gutenberg files use the typographic form (’)
#: almost universally, and matching only the straight form (') meant this rule
#: silently failed on the very files it was written for.
TRANSCRIBER_HEADING = re.compile(
    r"^\s*Transcriber['’ʼ]?s?\s+Notes?\s*[.:]?\s*$", re.IGNORECASE
)

#: How far from the start/end of the content to look for producer credits.
TRANSCRIBER_WINDOW = 40

#: Phrases that appear in PG legal text and effectively nowhere else.
LICENCE_PHRASES = [
    "project gutenberg",
    "literary archive foundation",
    "public domain",
    "no restrictions whatsoever",
    "gutenberg.org",
    "gutenberg-tm",
    "redistribution is subject",
    "terms of the project gutenberg license",
    "this ebook is for the use of anyone",
    "you may copy it, give it away",
    "trademark",
    "donations to the project gutenberg",
]

#: Apparatus added by mass-digitisation projects, not by any publisher.
#:
#: Reported from a real Internet Archive scan whose `body-only` output carried
#: the Archive's EPUB notice, Google's full usage guidelines and a per-page OCR
#: confidence note. None of it is Gutenberg, so none of it was recognised.
#:
#: **This is not front matter.** A researcher studying an edition may well want
#: its preface and dedication; nobody wants the scanner's notice. The two are
#: different in kind and are labelled differently.
#:
#: These strings are verbatim boilerplate reproduced identically across
#: millions of volumes, so matching them is exact rather than statistical.
SCAN_APPARATUS_PHRASES = [
    # Internet Archive
    "produced in epub format by the internet archive",
    "the book pages were scanned and converted to epub",
    "this process relies on optical character recognition",
    "the internet archive was founded in 1996",
    "created with hocr-to-epub",
    # Google Books
    "this is a digital copy of a book that was preserved",
    "carefully scanned by google",
    "about google book search",
    "google book search helps readers discover",
    "refrain from automated querying",
    "maintain attribution",
    "the google \u201cwatermark\u201d you see on each file",
    "books.google.com",
    "http : //books . google . com",
    # HathiTrust and similar
    "digitized by the internet archive",
    "original from",
    # Per-page OCR confidence, emitted by the Archive's pipeline
    "the text on this page is estimated to be only",
]

# ---------------------------------------------------------------------------
# Body headings
#
# Three tiers, tried in order of reliability. Only the first tier that yields
# results is used, so a book with real CHAPTER headings is never confused by
# stray numerals elsewhere.
#
#   1. Keyword headings   "Chapter 1", "ACT II", "Book the Third"
#   2. Numbered sections  "1. Introduction", "2.1 Method"
#   3. Bare numerals      "1" / "I" alone on a line, but only when they form
#                         an ascending sequence — which is what stops an
#                         isolated year like 1847 being mistaken for one.
# ---------------------------------------------------------------------------

#: Division words. Case-insensitive, so "Chapter One" works as well as
#: "CHAPTER ONE" — the original pattern was case-sensitive, which silently
#: failed on the majority of real books.
DIVISION_WORDS = (
    "CHAPTER|BOOK|PART|VOLUME|CANTO|SECTION|LETTER|ACT|SCENE|STAVE|"
    "EPISODE|FYTTE|MOVEMENT|INTERLUDE|LECTURE|SERMON|TALE|NIGHT"
)

_CARDINAL = (
    "ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|"
    "THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|"
    "THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY|HUNDRED"
)
_ORDINAL = (
    "FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    "ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|"
    "SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH|THIRTIETH|LAST"
)

#: What may follow a division word. Deliberately *not* "any word" — that is
#: what would let "Part of the reason…" match as a heading.
_ENUM = (
    rf"(?:[IVXLCDM]+|\d{{1,4}}|"
    rf"(?:THE\s+)?(?:{_CARDINAL}|{_ORDINAL})(?:[-\s](?:{_CARDINAL}|{_ORDINAL}))?)"
)

CHAPTER_HEADING = re.compile(
    rf"^\s*({DIVISION_WORDS})\s*[:.—\-]?\s*({_ENUM})\b\s*[.:;—–\-]?\s*(.{{0,200}})?$",
    re.IGNORECASE,
)

#: "1. Introduction", "2.1 Method" — academic and report structure.
NUMBERED_SECTION = re.compile(
    r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-ZÀ-Þ][^\n]{1,60})$"
)

#: A line that is nothing but a numeral: "1", "IV", "12."
BARE_NUMERAL = re.compile(r"^\s*([IVXLCDM]{1,7}|\d{1,3})\s*\.?\s*$")

#: "Participant: P04", "DOI: 10.1000/…" — metadata blocks at the head of
#: transcripts, journal articles and scraped pages.
METADATA_LINE = re.compile(r"^\s*([A-Z][A-Za-z /&'’-]{1,28})\s*:\s*\S.*$")

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

#: Front-matter headings. Must be uppercase to match — this is why the rule
#: cannot eat ordinary prose.
FRONT_HEADING = re.compile(
    r"^\s*("
    r"PREFACE|INTRODUCTION|INTRODUCTORY NOTE|CONTENTS|TABLE OF CONTENTS|"
    r"DEDICATION|FOREWORD|ADVERTISEMENT|PROLOGUE|TO THE READER|"
    r"AUTHOR['’\u02bc]?S NOTE|EDITOR['’\u02bc]?S NOTE|PUBLISHER['’\u02bc]?S NOTE|ILLUSTRATIONS|"
    r"LIST OF [A-Z ]+|NOTE TO THE [A-Z ]+|NOTE\b[A-Z ]*|PREFATORY [A-Z ]+"
    r")\s*\.?\s*$"
)

#: Named front matter that is conventionally set in title case, not caps —
#: "Dramatis Personæ", "Contents". Matched case-insensitively, but the line
#: must consist of the name and nothing else (note the anchored `$`), so a
#: sentence merely beginning with one of these words is never caught.
NAMED_FRONT_HEADING = re.compile(
    r"^\s*(?:THE\s+)?("
    r"PROLOGUE|CONTENTS|TABLE\s+OF\s+CONTENTS|"
    r"DRAMATIS\s+PERSON(?:AE|Æ|E)|PERSONS\s+REPRESENTED|"
    r"CHARACTERS(?:\s+IN\s+THE\s+PLAY)?|ARGUMENT|"
    r"DEDICATION|PREFACE|FOREWORD|INTRODUCTION"
    r")\s*[.:]?\s*$",
    re.IGNORECASE,
)

#: Largest line gap allowed between consecutive contents entries. Entries are
#: listed a line or two apart (allowing a blank between acts); real headings
#: are separated by whole chapters.
MAX_CONTENTS_GAP = 4
#: Shortest run that can count as a table of contents.
MIN_CONTENTS_ENTRIES = 3
#: Fraction of entries that must reappear later in the text.
CONTENTS_MATCH_RATIO = 0.6

CONTENTS_HEADING = re.compile(
    r"^\s*(?:TABLE\s+OF\s+)?CONTENTS\s*[.:]?\s*$", re.IGNORECASE
)

BACK_HEADING = re.compile(
    r"^\s*("
    r"APPENDIX|GLOSSARY|INDEX|BIBLIOGRAPHY|NOTES|ENDNOTES|POSTSCRIPT|"
    r"AFTERWORD|COLOPHON|TRANSCRIBER['’\u02bc]?S NOTES?|FOOTNOTES"
    r")\b.*$"
)

MAX_HEADING_LEN = 80
#: A heading may run longer than `MAX_HEADING_LEN` only if it reads as a title
#: rather than as prose. Machiavelli's chapters reach 125 characters, and six
#: of them were invisible to the detector until this existed.
MAX_TITLED_HEADING_LEN = 200


def _is_upper(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def is_chapter_heading(line: str) -> bool:
    """True for "Chapter 1", "ACT II", "Book the Third", etc.

    The guard that matters: any text following the enumerator must begin with
    a capital. That is what separates a heading ("Chapter 1. The Beginning")
    from a sentence that happens to open with a division word ("Section 3 of
    the act states that…"), which the case-insensitive match would otherwise
    accept.

    **Length is a poor stand-in for that guard, and it was doing the work.**
    A limit of 80 characters silently rejected six of Machiavelli's chapter
    headings, the longest running to 125 characters, and with them the whole
    contents list they belonged to. The list then fragmented, so its entries
    were read as real chapters and 473 lines of the translator's biography
    were labelled as Chapter XXVI.

    A longer line is now allowed, provided its title is **entirely upper
    case**. Prose does not sustain capitals for ninety characters, and the
    pattern already requires the line to open with a division word and an
    enumerator, so `CHAPTER IV. WHY THE KINGDOM OF DARIUS...` is admitted while
    `Chapter 5 was the morning everything changed for her, and she...` is not.
    """
    s = line.strip()
    if not s:
        return False
    if len(s) > MAX_HEADING_LEN:
        if len(s) > MAX_TITLED_HEADING_LEN or not _is_upper(s):
            return False
    m = CHAPTER_HEADING.match(s)
    if not m:
        return False
    trailing = (m.group(3) or "").strip()
    if trailing and not re.match(r"[A-ZÀ-Þ\"'‘’“”(\[—–-]", trailing):
        return False
    return True


def roman_to_int(s: str) -> int | None:
    total = prev = 0
    for ch in reversed(s.upper()):
        v = _ROMAN.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def _numeral_value(s: str) -> int | None:
    s = s.strip().rstrip(".")
    if s.isdigit():
        return int(s)
    return roman_to_int(s)


def find_numbered_sections(lines, start, end, skip=lambda i: False) -> list[int]:
    """Find "1. Introduction" / "2.1 Method" style headings.

    Requires at least two, and that the first is numbered 1 — a document with
    a single stray "3. " line is not a structured document.
    """
    hits = []
    for i in range(start, end):
        if skip(i):
            continue
        s = lines[i].strip()
        if not s or len(s) > MAX_HEADING_LEN:
            continue
        m = NUMBERED_SECTION.match(s)
        if m and (not s.endswith((".", ",", ";")) or s.count(" ") <= 6):
            hits.append((i, m.group(1)))
    if len(hits) < 2:
        return []
    if not hits[0][1].split(".")[0] == "1":
        return []
    return [i for i, _ in hits]


def find_numeral_sequence(lines, start, end, skip=lambda i: False) -> list[int]:
    """Find chapters marked only by a bare numeral on its own line.

    Safe because it requires an **ascending run beginning at 1**, at least
    three long. An isolated year such as 1847 has no such run, which is
    exactly why bug B4 cannot come back through this route.
    """
    cands = []
    for i in range(start, end):
        if skip(i):
            continue
        s = lines[i].strip()
        if not s or not BARE_NUMERAL.match(s):
            continue
        v = _numeral_value(s)
        if v is not None and 1 <= v <= 200:
            cands.append((i, v))

    best: list[int] = []
    run: list[int] = []
    expect = 1
    for i, v in cands:
        if v == expect:
            run.append(i)
            expect += 1
        elif v == 1:
            if len(run) > len(best):
                best = run
            run, expect = [i], 2
    if len(run) > len(best):
        best = run
    return best if len(best) >= 3 else []


def find_metadata_block(lines, start, end) -> tuple[int, int] | None:
    """Find a "Key: value" header block at the top of the document.

    Common in transcripts, journal extracts and scraped pages. Requires two or
    more consecutive such lines within the opening of the document, so a line
    of dialogue like "INT: so tell me…" in the middle of a text is not caught.
    """
    limit = min(end, start + 30)
    run_start = None
    for i in range(start, limit):
        s = lines[i].strip()
        if s and METADATA_LINE.match(s) and len(s) <= 120:
            if run_start is None:
                run_start = i
        elif s:
            if run_start is not None and i - run_start >= 2:
                return (run_start, i)
            run_start = None
    if run_start is not None and limit - run_start >= 2:
        return (run_start, limit)
    return None


def heading_key(line: str) -> str:
    """A heading reduced to its division word and number.

    Used only to match a contents entry against the heading it points to. The
    two rarely share a title: a contents list prints

        CHAPTER I. HOW MANY KINDS OF PRINCIPALITIES THERE ARE

    while the chapter itself is headed simply

        CHAPTER I.

    Comparing the printed strings finds nothing in common, which is how a
    26-entry contents list came to be read as 26 chapters. The number is what
    the two genuinely share.
    """
    m = CHAPTER_HEADING.match(line.strip())
    if not m:
        return line.strip().lower()
    return f"{m.group(1).lower()} {m.group(2).lower()}"


def split_contents_list(lines, idx: list[int]) -> tuple[list[int], list[int]]:
    """Separate a table-of-contents run from the real headings.

    A contents list is a run of headings at the very start whose titles all
    *reappear* further down. That duplication is the signal — far more robust
    than looking for the word "Contents", which many editions omit.

    Returns (contents_indices, body_indices).
    """
    if len(idx) < MIN_CONTENTS_ENTRIES + 1:
        return [], idx

    # Matched on division word and number rather than on the printed line: a
    # contents entry carries a title the heading itself usually omits.
    titles = [heading_key(lines[i]) for i in idx]

    # 1. Take the opening run of headings packed close together. Contents
    #    entries sit a line or two apart; real headings are separated by whole
    #    chapters, so the first big gap ends the list.
    run = 1
    while run < len(idx) and (idx[run] - idx[run - 1]) <= MAX_CONTENTS_GAP:
        run += 1

    if run < MIN_CONTENTS_ENTRIES or run >= len(idx):
        return [], idx

    # 2. Confirm by duplication — most of those titles must appear again
    #    further down. A *majority*, not all: requiring every entry to reappear
    #    means one undetected body heading disables the whole rule, which is
    #    how a play's contents ended up being treated as the play.
    rest = set(titles[run:])
    hits = sum(1 for t in titles[:run] if t in rest)
    if hits / run >= CONTENTS_MATCH_RATIO:
        return idx[:run], idx[run:]

    # A weaker duplication ratio is still a contents list if the headings have
    # no room for a chapter between them.
    #
    # **A real chapter heading is followed by prose.** Twenty-six headings
    # inside twenty-six lines is a list of chapters, not a sequence of them,
    # and nothing else in a book looks like that.
    #
    # The ratio alone is unreliable on a text that stops early. Machiavelli's
    # contents list names twenty-six chapters; an extract holding the first
    # twelve matches only 46% of them, and was read as twenty-six one-line
    # chapters followed by a chapter containing the whole biography.
    #
    # Some duplication is still required. A document that is ONLY a contents
    # list should keep it, since removing it would leave nothing at all.
    body_between = sum(
        1 for k in range(idx[0], idx[run - 1])
        if lines[k].strip() and not is_chapter_heading(lines[k])
    )
    dense = body_between <= run // 4
    if dense and hits >= max(2, run // 4):
        return idx[:run], idx[run:]

    return [], idx


def find_body_headings(lines, start, end, skip=lambda i: False):
    """Return (indices, kind, evidence) using the most reliable tier available."""
    kw = [i for i in range(start, end) if not skip(i) and is_chapter_heading(lines[i])]
    if kw:
        return kw, "chapter", "division heading"

    ns = find_numbered_sections(lines, start, end, skip)
    if ns:
        return ns, "section", "numbered section heading"

    seq = find_numeral_sequence(lines, start, end, skip)
    if seq:
        return seq, "chapter", "bare numeral in ascending sequence"

    return [], None, None


def is_front_heading(line: str) -> bool:
    """True for a front-matter heading.

    Two routes: the generic list requires ALL CAPS (its patterns end in
    wildcards, so case-insensitivity there would over-match); the named list
    allows title case because "Dramatis Personæ" and "Contents" are almost
    never set in capitals, and those patterns match the whole line exactly.
    """
    s = line.strip()
    if not s or len(s) > MAX_HEADING_LEN:
        return False
    if NAMED_FRONT_HEADING.match(s):
        return True
    return _is_upper(s) and bool(FRONT_HEADING.match(s))


def is_back_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > MAX_HEADING_LEN or not _is_upper(s):
        return False
    return bool(BACK_HEADING.match(s))


# ---------------------------------------------------------------------------
# Licence detection
# ---------------------------------------------------------------------------

def licence_score(text: str) -> int:
    """Count distinct PG legal phrases in a block."""
    low = text.lower()
    return sum(1 for p in LICENCE_PHRASES if p in low)


#: The Internet Archive prints its own OCR confidence above each page it is
#: unsure of. Below this figure the page is noise rather than text.
#:
#: Not a guess. On the first real scan tested, 28 pages carried a note, every
#: one under 50% and the median at 5.1%, and the text beneath them reads:
#:
#:     / .•;?(^ V //'^i .^< .r/<vrr./;-/ , , r '.:ii«fe3*«i'*— - -c'
#:
#: A page like that contributes nothing but noise tokens to a word count.
OCR_MIN_ACCURACY = 50.0

#: `The text on this page is estimated to be only 4.93% accurate`
OCR_ACCURACY_NOTE = re.compile(
    r"text on this page is estimated to be only\s*([\d.]+)\s*% accurate",
    re.IGNORECASE)


def ocr_accuracy(line: str) -> float | None:
    """The scanner's own confidence for the page that follows, if stated."""
    m = OCR_ACCURACY_NOTE.search(line)
    return float(m.group(1)) if m else None


def find_unreadable_pages(lines: list[str],
                          threshold: float = OCR_MIN_ACCURACY
                          ) -> list[tuple[int, int, float]]:
    """Pages the scanner itself reports as unreadable: (start, end, accuracy).

    **This is measured evidence rather than inference.** Every other rule in
    this package has to work out what a line is; here the digitisation pipeline
    has already done the work and written down the answer, and the tool's only
    job is to believe it.

    The note precedes the page it describes, so the block returned is the run
    of text after the note, up to the next blank line.
    """
    out: list[tuple[int, int, float]] = []
    for i, line in enumerate(lines):
        acc = ocr_accuracy(line)
        if acc is None or acc >= threshold:
            continue
        # The region starts at the note itself. In practice the note and the
        # page it describes sit in the same blank-delimited block, so starting
        # after it would let the generic apparatus rule claim both first and
        # report "Digitisation notice" where it could report the actual figure.
        k = i + 1
        while k < len(lines) and lines[k].strip():
            k += 1
        out.append((i, k, acc))
    return out


def scan_apparatus_score(text: str) -> int:
    """Count distinct digitisation-project phrases in a block.

    Separate from `licence_score` because the two are different things. A
    Gutenberg licence is a condition of use; an Internet Archive notice or a
    Google Books usage statement is machinery from the scanning pipeline, and
    it appears in books that have no licence attached at all.
    """
    low = text.lower()
    return sum(1 for p in SCAN_APPARATUS_PHRASES if p in low)


def is_scan_apparatus(text: str) -> bool:
    """One phrase is enough: these are verbatim, not statistical.

    Every string in `SCAN_APPARATUS_PHRASES` is boilerplate reproduced
    identically across millions of scans. A single match is conclusive in a way
    that one legal-sounding word never is, so no threshold is needed.
    """
    return scan_apparatus_score(text) >= 1


def _blocks(lines: list[str], start: int, end: int):
    """Yield (a, b) for each blank-line-delimited block in [start, end)."""
    a = None
    for i in range(start, end + 1):
        blank = i >= end or not lines[i].strip()
        if not blank and a is None:
            a = i
        elif blank and a is not None:
            yield (a, i)
            a = None


def find_transcriber_notes(lines, start, end, window=TRANSCRIBER_WINDOW):
    """Find producer and transcriber credit blocks. Returns (a, b) spans.

    Two routes, with different safety requirements:

    * An unambiguous full-line heading ("Transcriber's Notes") is recognised
      anywhere. Where the heading stands alone, the following block is taken
      with it, since that is where the note itself lives.
    * A prefix match ("Produced by…", "Credits:") could begin a line of real
      prose, so it is bounded twice over: to a single blank-line block, and to
      a window at the head or tail of the content. Those two bounds are what
      make this safe where the prototype's version was not.
    """
    found: list[tuple[int, int]] = []
    blocks = list(_blocks(lines, start, end))

    for i, (a, b) in enumerate(blocks):
        if not TRANSCRIBER_HEADING.match(lines[a]):
            continue
        # Heading alone on its block: the note follows in the next block.
        span_end = blocks[i + 1][1] if (b - a == 1 and i + 1 < len(blocks)) else b
        found.append((a, span_end))

    zones = [
        (start, min(end, start + window)),
        (max(start, end - window), end),
    ]
    for zs, ze in zones:
        if ze <= zs:
            continue
        for a, b in _blocks(lines, zs, ze):
            if TRANSCRIBER_OPENING.match(lines[a]) and not any(
                s <= a < e for s, e in found
            ):
                found.append((a, b))

    return sorted(found)


def find_licence_blocks(lines: list[str], min_score: int = 2) -> list[tuple[int, int, int]]:
    """Find (start, end, score) for paragraph blocks that read as PG licence.

    Blocks are separated by blank lines. A block qualifies only if it scores
    on at least ``min_score`` distinct phrases *and* mentions Gutenberg —
    so a novel discussing copyright is never caught.
    """
    blocks: list[tuple[int, int, int]] = []
    start = None
    for i, line in enumerate(lines + [""]):
        if line.strip():
            if start is None:
                start = i
        else:
            if start is not None:
                text = "\n".join(lines[start:i])
                score = licence_score(text)
                low = text.lower()
                if score >= min_score and ("gutenberg" in low or "pglaf" in low):
                    blocks.append((start, i, score))
                start = None
    return blocks


def find_scan_apparatus(lines: list[str]) -> list[tuple[int, int, int]]:
    """Find blocks added by a digitisation project rather than a publisher.

    Reported from a real Internet Archive scan, whose `body-only` output
    carried the Archive's EPUB notice, Google's usage guidelines and a per-page
    OCR confidence line. None of it is Gutenberg, so nothing recognised it.

    Unlike the licence rule this needs no score threshold. Every phrase is
    verbatim boilerplate reproduced identically across millions of volumes, so
    one match is conclusive; a licence phrase like "public domain" is not,
    because a novel may discuss it.
    """
    blocks: list[tuple[int, int, int]] = []
    start = None
    for i, line in enumerate(lines + [""]):
        if line.strip():
            if start is None:
                start = i
        else:
            if start is not None:
                score = scan_apparatus_score("\n".join(lines[start:i]))
                if score >= 1:
                    blocks.append((start, i, score))
                start = None
    return blocks


# ---------------------------------------------------------------------------
# Main segmenter
# ---------------------------------------------------------------------------

def _find_marker(lines: list[str], *patterns) -> int | None:
    for i, line in enumerate(lines):
        for p in patterns:
            if p.search(line):
                return i
    return None


def _find_marker_last(lines: list[str], *patterns) -> int | None:
    for i in range(len(lines) - 1, -1, -1):
        for p in patterns:
            if p.search(lines[i]):
                return i
    return None


def segment(doc: Document) -> Document:
    """Label every line of the document. Returns a new Document."""
    lines = doc.lines
    n = len(lines)
    regions: list[Region] = []

    # --- 1. Project Gutenberg apparatus -----------------------------------
    pg_start = _find_marker(lines, PG_START, PG_START_OLD)
    pg_end = _find_marker_last(lines, PG_END, PG_END_OLD)

    content_start = 0
    content_end = n

    if pg_start is not None:
        regions.append(Region(
            label=PG_HEADER, kind="pg_header", title="Project Gutenberg header",
            start=0, end=pg_start + 1, confidence=1.0,
            evidence="explicit START marker",
        ))
        content_start = pg_start + 1

    if pg_end is not None and pg_end >= content_start:
        regions.append(Region(
            label=PG_LICENCE, kind="pg_footer", title="Project Gutenberg licence",
            start=pg_end, end=n, confidence=1.0,
            evidence="explicit END marker",
        ))
        content_end = pg_end

    # --- 2. Licence blocks without markers --------------------------------
    licence_spans: list[tuple[int, int]] = []
    if pg_start is None or pg_end is None:
        for s, e, score in find_licence_blocks(lines[content_start:content_end]):
            s += content_start
            e += content_start
            licence_spans.append((s, e))
            regions.append(Region(
                label=PG_LICENCE, kind="licence_block",
                title="Licence text (unmarked)",
                start=s, end=e, confidence=min(1.0, 0.5 + 0.15 * score),
                evidence=f"{score} licence phrases, no sentinel marker",
            ))

    # --- 2a. Pages the scanner reports as unreadable ----------------------
    #
    # The only rule here that does not have to infer anything: the digitisation
    # pipeline states its own confidence, and this believes it.
    for s, e, acc in find_unreadable_pages(lines[content_start:content_end]):
        s += content_start
        e += content_start
        if any(a <= s < b for a, b in licence_spans):
            continue
        licence_spans.append((s, e))
        regions.append(Region(
            label=PG_LICENCE, kind="ocr_rejected",
            title=f"Unreadable page ({acc:g}% accurate)",
            start=s, end=e, confidence=1.0,
            evidence=f"the scanner reports this page as {acc:g}% accurate, "
                     f"below the {OCR_MIN_ACCURACY:g}% floor",
        ))

    # --- 2b0. Digitisation-project apparatus ------------------------------
    #
    # Runs whether or not Gutenberg markers were found: an Internet Archive or
    # Google scan carries this material and no Gutenberg licence at all.
    #
    # Labelled as apparatus rather than front matter deliberately. A researcher
    # studying an edition may want its preface; nobody wants the scanner's
    # notice, and the two should not share a switch.
    for s, e, score in find_scan_apparatus(lines[content_start:content_end]):
        s += content_start
        e += content_start
        if any(a <= s < b for a, b in licence_spans):
            continue
        licence_spans.append((s, e))
        regions.append(Region(
            label=PG_LICENCE, kind="scan_apparatus",
            title="Digitisation notice",
            start=s, end=e, confidence=0.95,
            evidence=f"{score} verbatim phrase(s) from a scanning pipeline "
                     f"(Internet Archive, Google Books or similar)",
        ))

    # --- 2b. Transcriber / producer credits -------------------------------
    # These sit *after* the START marker, so they escape the header region,
    # and they often name pglaf.org without ever saying "gutenberg" — which
    # is why the licence scorer alone misses them.
    for a, b in find_transcriber_notes(lines, content_start, content_end):
        licence_spans.append((a, b))
        regions.append(Region(
            label=PG_HEADER, kind="transcriber_note",
            title=lines[a].strip()[:60],
            start=a, end=b, confidence=0.9,
            evidence="producer/transcriber credit block near start or end",
        ))

    def _in_licence(i: int) -> bool:
        return any(s <= i < e for s, e in licence_spans)

    # --- 3. Metadata header ----------------------------------------------
    # Detected before body headings, so it is found even in texts with no
    # chapter structure at all — transcripts and article extracts, which are
    # precisely the files that have a metadata block and nothing else.
    meta_span = find_metadata_block(lines, content_start, content_end)
    if meta_span:
        regions.append(Region(
            label=FRONT_MATTER, kind="metadata", title="Metadata header",
            start=meta_span[0], end=meta_span[1], confidence=.85,
            evidence="consecutive 'Key: value' lines at head of document",
        ))

    # --- 4. Body start: first structural heading --------------------------
    heading_idx, heading_kind, heading_evidence = find_body_headings(
        lines, content_start, content_end, _in_licence
    )

    # A table of contents repeats the headings it lists. Without this, body
    # would begin inside the contents and the real front matter after it —
    # Dramatis Personae, prologue — would be mislabelled as body.
    contents_idx, heading_idx = split_contents_list(lines, heading_idx)
    contents_span: tuple[int, int] | None = None
    if contents_idx:
        # Absorb a "Contents" heading sitting above the list — and anything
        # between it and the first entry, which will be further entries
        # ("THE PROLOGUE.") rather than sections in their own right.
        c_start = contents_idx[0]
        probe, seen = c_start - 1, 0
        while probe >= content_start and seen < 8:
            s = lines[probe].strip()
            if s:
                seen += 1
                if CONTENTS_HEADING.match(s):
                    c_start = probe
                    break
            probe -= 1

        contents_span = (c_start, contents_idx[-1] + 1)
        regions.append(Region(
            label=FRONT_MATTER, kind="contents", title="Contents",
            start=contents_span[0], end=contents_span[1],
            confidence=0.8,
            evidence=f"{len(contents_idx)} headings repeated later in the text",
        ))

    body_start = heading_idx[0] if heading_idx else None

    if body_start is None:
        # No headings of any kind. Keep everything as body rather than
        # guessing — a wrong guess here would silently discard the work.
        rest_start = meta_span[1] if meta_span else content_start
        if content_end > rest_start:
            regions.append(Region(
                label=BODY, kind="body", title="(whole text)",
                start=rest_start, end=content_end, confidence=0.4,
                evidence="no structural headings found; whole text kept as body",
            ))
        note = (
            "No structural headings found. Tried: division headings "
            "(Chapter/Book/Part/Act/Scene…), numbered sections (1. Introduction) "
            "and bare numeral sequences. The whole text was kept as body and "
            "nothing was removed."
        )
        if meta_span:
            note += " A metadata header was found and can be removed separately."
        return _finalise(doc, regions, note=note)

    # --- 5. Front matter, sub-segmented by headings -----------------------
    if body_start > content_start:
        # Headings *inside* the contents list are entries, not sections.
        def _in_contents(i: int) -> bool:
            return bool(contents_span and contents_span[0] <= i < contents_span[1])

        fm_lines = range(content_start, body_start)
        heads = [i for i in fm_lines
                 if is_front_heading(lines[i])
                 and not _in_licence(i) and not _in_contents(i)]

        # Anything before the first front-matter heading is title/byline.
        # Split around the metadata block rather than straddling it, so each
        # piece gets its own accurate title.
        first = heads[0] if heads else body_start
        spans = [(content_start, first)]
        if meta_span and content_start <= meta_span[0] < first:
            spans = [(content_start, meta_span[0]), (meta_span[1], first)]

        for a, b in spans:
            seg = _trim_blank(lines, a, min(b, first))
            if seg:
                regions.append(Region(
                    label=FRONT_MATTER, kind="titlepage",
                    title=_first_nonblank(lines, *seg) or "Title page",
                    start=seg[0], end=seg[1], confidence=0.8,
                    evidence="text before first front-matter heading",
                ))

        for idx, h in enumerate(heads):
            end = heads[idx + 1] if idx + 1 < len(heads) else body_start
            regions.append(Region(
                label=FRONT_MATTER, kind=lines[h].strip().lower().replace(" ", "_"),
                title=lines[h].strip(),
                start=h, end=end, confidence=0.9,
                evidence="uppercase front-matter heading",
            ))

    # --- 6. Body, sub-segmented by chapter --------------------------------
    chapter_starts = [i for i in heading_idx if i >= body_start]

    back_start = None
    for i in range(body_start, content_end):
        if is_back_heading(lines[i]) and not _in_licence(i):
            back_start = i
            break

    body_end = back_start if back_start is not None else content_end

    for idx, cs in enumerate(chapter_starts):
        if cs >= body_end:
            break
        ce = chapter_starts[idx + 1] if idx + 1 < len(chapter_starts) else body_end
        ce = min(ce, body_end)
        regions.append(Region(
            label=BODY, kind=heading_kind or "chapter", title=lines[cs].strip(),
            start=cs, end=ce,
            confidence=1.0 if heading_kind == "chapter" else 0.85,
            evidence=heading_evidence or "chapter heading",
        ))

    # --- 7. Back matter ---------------------------------------------------
    if back_start is not None and back_start < content_end:
        regions.append(Region(
            label=BACK_MATTER, kind="back_matter", title=lines[back_start].strip(),
            start=back_start, end=content_end, confidence=0.7,
            evidence="back-matter heading",
        ))

    return _finalise(doc, regions)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trim_blank(lines: list[str], start: int, end: int) -> tuple[int, int] | None:
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return (start, end) if end > start else None


def _first_nonblank(lines: list[str], start: int, end: int) -> str:
    for i in range(start, min(end, len(lines))):
        if lines[i].strip():
            return lines[i].strip()
    return ""


#: Which label wins when two regions claim the same line. Gutenberg apparatus
#: outranks everything, because a licence block sitting inside a chapter's
#: line range is still licence text and must not be exported as prose.
PRECEDENCE = {
    UNKNOWN: 0,
    FRONT_MATTER: 1,
    BACK_MATTER: 1,
    BODY: 2,
    PG_HEADER: 3,
    PG_LICENCE: 3,
}


#: Structural depth of each division word. Lower number = higher in the
#: hierarchy. Only the ranks actually present in a text are used, and they are
#: renumbered from 1 — so a novel using only CHAPTER gets a flat level 1, while
#: a play using ACT and SCENE gets two levels.
DIVISION_RANK = {
    "VOLUME": 1,
    "BOOK": 2, "PART": 2, "ACT": 2,
    "CHAPTER": 3, "SCENE": 3, "CANTO": 3, "STAVE": 3, "LETTER": 3,
    "SECTION": 3, "EPISODE": 3, "FYTTE": 3, "MOVEMENT": 3,
    "INTERLUDE": 3, "LECTURE": 3, "SERMON": 3, "TALE": 3, "NIGHT": 3,
}

_DIVISION_FIRST_WORD = re.compile(rf"^\s*({DIVISION_WORDS})\b", re.IGNORECASE)


def _rank_of(region: Region) -> int | None:
    """Structural rank of a body region, or None if it is not a division."""
    if region.label != BODY:
        return None
    if region.kind == "section":
        # "2.1 Method" is one level deeper than "2. Method".
        m = re.match(r"^\s*(\d+(?:\.\d+)*)", region.title)
        if m:
            return m.group(1).count(".") + 1
        return 1
    m = _DIVISION_FIRST_WORD.match(region.title)
    if m:
        return DIVISION_RANK.get(m.group(1).upper(), 3)
    return None


def assign_hierarchy(doc: Document) -> Document:
    """Compute ``level`` and ``parent`` for every region.

    Runs after regions are final, so it never disturbs the flat, gap-free
    cover that the rest of the design depends on. Nesting is pure metadata:
    an Act keeps its own one-line span, and its Scenes point at it.
    """
    regions = doc.regions
    ranks = [_rank_of(r) for r in regions]

    present = sorted({r for r in ranks if r is not None})
    if len(present) <= 1:
        # One division type (or none) — nothing to nest.
        return doc

    # Renumber the ranks actually used to 1..n, so BOOK/CHAPTER and ACT/SCENE
    # both come out as levels 1 and 2 regardless of their absolute ranks.
    level_of = {rank: i + 1 for i, rank in enumerate(present)}

    out: list[Region] = []
    stack: list[tuple[int, int]] = []   # (level, index)

    for i, (r, rank) in enumerate(zip(regions, ranks)):
        if rank is None:
            out.append(replace(r, level=1, parent=None))
            stack.clear()
            continue

        lvl = level_of[rank]
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        parent = stack[-1][1] if stack else None
        out.append(replace(r, level=lvl, parent=parent))
        stack.append((lvl, i))

    return doc.with_regions(out)


def _finalise(doc: Document, regions: list[Region], note: str | None = None) -> Document:
    """Resolve overlaps, fill gaps with UNKNOWN, and return a clean cover.

    Two guarantees come out of this function:

    * **No overlaps.** Each line belongs to exactly one region, decided by
      ``PRECEDENCE``. A region split by a higher-precedence one is emitted as
      two regions rather than silently absorbing it.
    * **No orphans.** Any content line no rule claimed is labelled UNKNOWN,
      which defaults to *keep*. Unclassified text is never lost.
    """
    n = len(doc.lines)
    owner: list[Region | None] = [None] * n

    # Lowest precedence first, so higher-precedence regions overwrite.
    for r in sorted(regions, key=lambda r: (PRECEDENCE.get(r.label, 0), r.start)):
        for i in range(max(0, r.start), min(r.end, n)):
            cur = owner[i]
            if cur is None or PRECEDENCE.get(r.label, 0) >= PRECEDENCE.get(cur.label, 0):
                owner[i] = r

    # Claim any unowned content line as UNKNOWN.
    unknown = Region(
        label=UNKNOWN, kind="unclassified", title="",
        start=0, end=0, confidence=0.0,
        evidence="no rule matched; retained by default",
    )
    for i in range(n):
        if owner[i] is None and doc.lines[i].strip():
            owner[i] = unknown

    # Group consecutive lines with the same owner into emitted regions.
    out: list[Region] = []
    i = 0
    while i < n:
        r = owner[i]
        if r is None:
            i += 1
            continue
        j = i
        while j < n and owner[j] is r:
            j += 1
        span = _trim_blank(doc.lines, i, j)
        if span:
            # When a higher-precedence region splits one in two, the second
            # piece must take its title from its own text, not inherit the
            # original's.
            title = r.title
            if span[0] != r.start:
                # The tail of a split region must not inherit the original's
                # title: the text after an interruption is not the chapter
                # whose heading sat before it.
                if r.kind in {"titlepage", "unclassified"}:
                    title = _first_nonblank(doc.lines, *span) or r.title
                elif r.kind in {"chapter", "section"}:
                    title = f"{r.title} (continued)" if r.title else r.title
            out.append(Region(
                label=r.label, kind=r.kind, title=title,
                start=span[0], end=span[1],
                confidence=r.confidence, evidence=r.evidence,
            ))
        i = j

    result = assign_hierarchy(doc.with_regions(out))
    if note:
        result = result.with_note(note)
    return result
