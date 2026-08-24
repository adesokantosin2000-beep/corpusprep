"""
corpusprep.furniture
====================

Detection of page furniture: running heads, running feet and page numbers.

Text taken from scanned or typeset pages carries the book or chapter title at
the top of every page and a page number at the bottom. In a four-hundred-page
novel that is eight hundred spurious lines, and each one corrupts word counts,
collocation spans and sentence splitting.

**The signal is regularity, not appearance.** A running head is not a line that
looks like a header; it is a line that recurs at a roughly constant interval,
because that interval is the page length. Three tempting rules all destroy
prose instead:

    short lines          also dialogue, verse, exclamations
    all-capital lines    also emphatic prose, inscriptions, telegrams
    repeated lines       also refrains and formulaic dialogue

The original prototype used the first two and destroyed prose on both counts.
The third is no better: a ballad refrain may repeat more often than the running
head does, and is unquestionably part of the text.

Regularity separates them. A refrain recurs wherever the poet chose; a running
head recurs every page. See `design/DECISIONS.md` for the full reasoning.

Nothing here deletes. Furniture is recorded as a set of line numbers and
removal is a later, explicit step, exactly as with regions.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from difflib import SequenceMatcher

#: Longest line that can plausibly be furniture.
MAX_LEN = 60
#: Fewest repeats before a group is considered at all.
MIN_OCCURRENCES = 5
#: Highest coefficient of variation accepted as "regular".
MAX_CV = 0.25
#: How far a group's interval may sit from the estimated page length.
PAGE_GAP_TOLERANCE = 0.25

#: How near two pieces of evidence must be to count as the same chapter start.
#: In a page-per-line file a line is a page, so this is "within two pages" —
#: the slack a heading and its first running head can differ by, and no more.
PAGE_GAP = 2
#: Similarity above which a small group is treated as an OCR-corrupted
#: variant of a larger one and folded into it.
NEAR_DUPLICATE = 0.85

#: Characters an OCR engine commonly confuses with digits. A page number read
#: as `l3` rather than `13` still leaves a letter behind after digit-stripping,
#: so it never joins the page-number series and is silently kept.
_DIGIT_LOOKALIKE = str.maketrans({"l": "1", "I": "1", "|": "1", "i": "1",
                                  "O": "0", "o": "0", "D": "0",
                                  "S": "5", "s": "5", "B": "8", "Z": "2"})
#: Longest line that can be a page number once decoration is stripped.
MAX_PAGE_NUMBER_LEN = 6

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_DIGITS = re.compile(r"\d+")
_WS = re.compile(r"\s+")


def normalise(line: str) -> str:
    """Reduce a line to what makes two running heads comparable.

    Digits are removed deliberately: `JANE EYRE 42` and `JANE EYRE 43` are the
    same running head on consecutive pages, and would not group otherwise.
    """
    s = _DIGITS.sub(" ", line)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip().lower()


def looks_like_page_number(line: str) -> bool:
    """True for a bare page number, including common OCR misreadings.

    `l3` for 13 and `O` for 0 are routine in scanned text. Without this the
    corrupted instances drop out of the page-number series, and the gap they
    leave is what pushes the series over the irregularity limit.
    """
    s = _PUNCT.sub("", line).strip()
    if not s or len(s) > MAX_PAGE_NUMBER_LEN:
        return False
    # A single character must be a real digit. Lookalike substitution would
    # otherwise read a lone `I` as 1, and a lone `I` is far more often the
    # pronoun, or a roman numeral marking a chapter, than a page number.
    if len(s) == 1:
        return s.isdigit()
    # At least half the characters must ALREADY be digits.
    #
    # Substitution models OCR corrupting a digit or two inside a number. It
    # must not be allowed to manufacture a number out of a word: without this
    # test `So` maps to 50 and `Bo` to 80, and any common short word that
    # happens to recur at the page interval is deleted as a page number. This
    # was found by the early modern fixture, where `So` is a catchword.
    real = sum(ch.isdigit() for ch in s)
    if real * 2 < len(s):
        return False
    return s.translate(_DIGIT_LOOKALIKE).isdigit()


def _cv(values: list[int]) -> float:
    """Coefficient of variation: how irregular a series of gaps is."""
    if len(values) < 2:
        return float("inf")
    mean = statistics.fmean(values)
    if mean == 0:
        return float("inf")
    return statistics.pstdev(values) / mean


@dataclass
class Candidate:
    """A group of identical-after-normalisation lines."""

    text: str                       # representative original line
    normal: str
    lines: list[int]                # 1-based line numbers
    is_numeric: bool = False        # page-number series
    gaps: list[int] = field(default_factory=list)
    cv: float = float("inf")
    median_gap: float = 0.0
    accepted: bool = False
    reason: str = ""


def collect(lines: list[str], skip: set[int] | None = None) -> list[Candidate]:
    """Group short repeated lines. No judgement yet."""
    skip = skip or set()
    groups: dict[str, list[int]] = {}
    originals: dict[str, str] = {}
    numeric: dict[str, bool] = {}

    for i, raw in enumerate(lines, 1):
        if i in skip:
            continue
        s = raw.strip()
        if not s or len(s) > MAX_LEN:
            continue
        # Page numbers first: they form one series together, which is what
        # they are. Checked before normalisation so that OCR misreadings such
        # as `l3` are recognised rather than left as the stray letter `l`.
        if looks_like_page_number(s):
            key = "\x00page-number"
            numeric[key] = True
            # A descriptive label rather than the first number seen. The review
            # table is meant to be read, and a row headed "1" tells the reader
            # nothing about what is being proposed for removal.
            originals[key] = "(page numbers)"
        else:
            key = normalise(s)
            if not key:
                continue
        groups.setdefault(key, []).append(i)
        originals.setdefault(key, s)

    groups, originals = _merge_near_duplicates(groups, originals)

    out = []
    for key, where in groups.items():
        if len(where) < MIN_OCCURRENCES:
            continue
        c = Candidate(text=originals[key], normal=key, lines=sorted(where),
                      is_numeric=numeric.get(key, False))
        c.gaps = [b - a for a, b in zip(c.lines, c.lines[1:])]
        c.cv = _cv(c.gaps)
        c.median_gap = statistics.median(c.gaps) if c.gaps else 0.0
        out.append(c)
    return out


def _merge_near_duplicates(groups: dict[str, list[int]],
                           originals: dict[str, str]):
    """Fold OCR-corrupted variants back into the series they belong to.

    Scanning misreads characters, so `JANE EYRE` becomes `IANE EYRE` on one
    page in ten. Left separate, the corrupted instance is missing from its
    series, which doubles one gap and inflates the irregularity score enough
    to reject a perfectly good running head.

    That is not a threshold problem and must not be fixed by loosening the
    threshold: a looser limit would start admitting refrains. The cause is
    that the series was split, so the cure is to reassemble it.

    Small groups are merged into large ones they closely resemble. Merging is
    one-directional, so two large distinct heads are never combined.
    """
    from difflib import SequenceMatcher

    keys = sorted(groups, key=lambda k: -len(groups[k]))
    absorbed: set[str] = set()

    for i, big in enumerate(keys):
        if big in absorbed or big.startswith("\x00"):
            continue
        for small in keys[i + 1:]:
            if small in absorbed or small.startswith("\x00"):
                continue
            # Only ever absorb the clearly smaller party, so that two genuine
            # heads of similar frequency stay apart.
            if len(groups[small]) * 3 > len(groups[big]):
                continue
            if SequenceMatcher(None, big, small).ratio() >= NEAR_DUPLICATE:
                groups[big].extend(groups[small])
                absorbed.add(small)

    for k in absorbed:
        del groups[k]
        originals.pop(k, None)
    for k in groups:
        groups[k].sort()
    return groups, originals


def page_number_value(line: str) -> int | None:
    """The numeric value of a page-number line, or None."""
    s = _PUNCT.sub("", line).strip()
    if not s or len(s) > MAX_PAGE_NUMBER_LEN:
        return None
    if len(s) == 1:
        return int(s) if s.isdigit() else None
    if sum(ch.isdigit() for ch in s) * 2 < len(s):
        return None
    t = s.translate(_DIGIT_LOOKALIKE)
    return int(t) if t.isdigit() else None


def ascending_run(values: list[int]) -> list[int]:
    """Indices of the longest ascending subsequence, gaps allowed.

    Page numbers count up. Missing and misread pages leave holes, so the run
    need not be consecutive, but it must never go backwards.
    """
    if not values:
        return []
    n = len(values)
    best = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if values[j] < values[i] and best[j] + 1 > best[i]:
                best[i] = best[j] + 1
                prev[i] = j
    end = max(range(n), key=lambda i: best[i])
    out = []
    while end != -1:
        out.append(end)
        end = prev[end]
    return out[::-1]


def restrict_to_ascending(c: Candidate, lines: list[str]) -> bool:
    """Keep only the lines of a numeric series that count upwards.

    **This is what makes page numbers independent evidence.** Any recurring
    line can be regular; only a page number counts up, and a refrain cannot
    fake an ascending sequence. Without this test the rule below has nothing
    to anchor on.
    """
    vals = [page_number_value(lines[i - 1]) for i in c.lines]
    pairs = [(ln, v) for ln, v in zip(c.lines, vals) if v is not None]
    if len(pairs) < MIN_OCCURRENCES:
        return False
    keep = ascending_run([v for _, v in pairs])
    if len(keep) < MIN_OCCURRENCES:
        return False
    c.lines = [pairs[i][0] for i in keep]
    c.gaps = [b - a for a, b in zip(c.lines, c.lines[1:])]
    c.cv = _cv(c.gaps)
    c.median_gap = statistics.median(c.gaps) if c.gaps else 0.0
    return True


def estimate_page_length(candidates: list[Candidate]) -> float:
    """Estimate the page length **from the page-number series alone**.

    An earlier version took the most regular series of any kind. That was
    circular, and real text exposed it immediately: in a poem of fixed stanza
    length the refrain recurs perfectly regularly, becomes the page-length
    estimate, and then validates itself against it. On a real ballad
    collection it marked 63 lines of verse as furniture.

    A page number is the one candidate with independent evidence behind it,
    because it counts upwards and a refrain cannot imitate that. So the page
    length comes only from there. **If no ascending page-number sequence
    exists, the document is not page-imaged and no running head can be
    corroborated**, which is the honest answer rather than a guess.
    """
    numeric = [c for c in candidates
               if c.is_numeric and c.cv < MAX_CV and c.median_gap > 0]
    if not numeric:
        return 0.0
    numeric.sort(key=lambda c: (c.cv, -len(c.lines)))
    return numeric[0].median_gap


def judge(candidates: list[Candidate], page_length: float) -> list[Candidate]:
    """Decide which candidates are furniture, recording why for each."""
    for c in candidates:
        if c.cv >= MAX_CV:
            c.reason = (f"irregular: gaps vary by {c.cv:.0%}, "
                        f"above the {MAX_CV:.0%} limit")
            continue
        if page_length <= 0:
            c.reason = ("no ascending page-number sequence in this text, so "
                        "there is no page structure to corroborate against")
            continue
        ratio = c.median_gap / page_length
        near = min(abs(ratio - n) for n in (1, 2, 3))
        if near > PAGE_GAP_TOLERANCE:
            c.reason = (f"regular but off-page: recurs every "
                        f"{c.median_gap:.0f} lines, page is "
                        f"{page_length:.0f}")
            continue
        c.accepted = True
        c.reason = (f"recurs every {c.median_gap:.0f} lines "
                    f"({ratio:.1f} pages), gaps vary by {c.cv:.0%}")
    return candidates


# ---------------------------------------------------------------------------
# Catchwords
# ---------------------------------------------------------------------------
#
# In books printed between roughly 1500 and 1800 the last line of each page
# carries, set to the right, the first word of the following page. It let the
# binder confirm the sheets were gathered in order. Anyone working with EEBO or
# ECCO transcriptions meets one on every page.
#
# This rule is unlike the running-head rule above. A running head has to be
# inferred from position, which is why that detector needs thresholds and why
# they are still guesses. A catchword carries its own proof: it IS the first
# word of the next page, and that can be checked rather than estimated.

#: Longest catchword accepted, in words.
CATCHWORD_MAX_WORDS = 3
#: Longest catchword accepted, in characters.
CATCHWORD_MAX_LEN = 30
#: Fewest matching pages before the rule fires at all.
CATCHWORD_MIN_PAGES = 4
#: Share of pages that must match before the book is judged to use catchwords.
CATCHWORD_MIN_RATIO = 0.35

#: The long s is standard in this period and survives in many transcriptions.
#: Without folding it, `ſaying` and `saying` are different words and every
#: catchword containing one fails to match.
_LONG_S = str.maketrans({"ſ": "s", "\u017f": "s"})


def _words(line: str) -> list[str]:
    """Comparable words: long s folded, punctuation dropped, lowercased."""
    s = line.translate(_LONG_S)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip().lower().split()


@dataclass
class CatchwordMatch:
    """One page boundary examined, whether or not it yielded a catchword."""

    line: int                       # 1-based line of the candidate
    text: str
    opens: str                      # first line of the following page
    accepted: bool = False
    reason: str = ""


def find_catchwords(lines: list[str], page_breaks: list[int],
                    furniture: set[int], skip: set[int] | None = None
                    ) -> tuple[set[int], list[CatchwordMatch]]:
    """Find catchwords, given where the pages break.

    ``page_breaks`` is the page-number line numbers already found above, so the
    page boundaries come free rather than being estimated a second time.

    Returns an empty set for any book that does not use catchwords. That is the
    result to check first and the one easiest to get wrong: a rule firing on two
    pages in three hundred still reads as "working" in a summary count.
    """
    skip = set(skip or ())
    ignore = furniture | skip
    n_lines = len(lines)

    def step(i: int, delta: int) -> int | None:
        """Nearest real line from ``i``, passing over blanks and furniture."""
        while 1 <= i <= n_lines:
            if i not in ignore and lines[i - 1].strip():
                return i
            i += delta
        return None

    matches: list[CatchwordMatch] = []
    for p in sorted(page_breaks):
        c = step(p - 1, -1)
        nxt = step(p + 1, +1)
        if c is None or nxt is None:
            continue

        text = lines[c - 1].strip()
        opens = lines[nxt - 1].strip()
        m = CatchwordMatch(line=c, text=text, opens=opens)
        matches.append(m)

        cw = _words(text)
        # The length guard, and the only place this rule can destroy text.
        # A page may legitimately end with a full line whose last word opens
        # the next page, and in verse with a refrain that happens often. A
        # catchword is a fragment set alone on its own line; a line of prose
        # that happens to repeat is not one, however well it matches.
        if not cw or len(cw) > CATCHWORD_MAX_WORDS or len(text) > CATCHWORD_MAX_LEN:
            m.reason = (f"too long to be a catchword: {len(cw)} words, "
                        f"{len(text)} characters")
            continue

        if _words(opens)[:len(cw)] == cw:
            m.accepted = True
            m.reason = f"opens the next page: {opens[:40]!r}"
        else:
            m.reason = "does not open the next page"

    hits = [m for m in matches if m.accepted]
    ratio = len(hits) / len(matches) if matches else 0.0

    # One match is coincidence; thirty is a printing convention. Without this
    # test a modern book yields a handful of accidental matches and loses real
    # lines to a rule that should never have fired on it.
    if len(hits) < CATCHWORD_MIN_PAGES or ratio < CATCHWORD_MIN_RATIO:
        for m in hits:
            m.accepted = False
            m.reason = (f"matched, but only {len(hits)} of {len(matches)} pages "
                        f"do ({ratio:.0%}); this book does not use catchwords")
        return set(), matches

    return {m.line for m in hits}, matches


def find_in_document(doc) -> tuple[set[int], list[Candidate], float]:
    """Find furniture in a segmented Document, searching the body only.

    Restricting the search matters more than it sounds. A title page carries
    the book's title, which is character-for-character the running head, and an
    imprint date, which looks exactly like a page number. Searched whole, a
    scanned novel has its title page mistaken for furniture and deleted.

    Furniture is a property of the printed page body. Front and back matter
    have their own conventions and are excluded.
    """
    skip = {
        i + 1
        for r in doc.regions
        if r.label != "body"
        for i in range(r.start, r.end)
    }
    return find(doc.lines, skip)


def find(lines: list[str], skip: set[int] | None = None
         ) -> tuple[set[int], list[Candidate], float, list[CatchwordMatch]]:
    """Return (furniture lines, candidates, page length, catchword matches).

    Every candidate is returned, accepted or not, with the reason recorded.
    A rule the user cannot interrogate is a rule the user cannot trust.
    """
    candidates = collect(lines, skip)
    # Numeric series must prove they count upwards before they can be treated
    # as page numbers, and everything downstream depends on that proof.
    for c in candidates:
        if c.is_numeric and not restrict_to_ascending(c, lines):
            c.is_numeric = False
            c.cv = float("inf")
            c.reason = "numbers do not form an ascending sequence"
    page_length = estimate_page_length(candidates)
    judge(candidates, page_length)
    marked = {i for c in candidates if c.accepted for i in c.lines}

    # Catchwords run second because they need the page breaks the first pass
    # found. Page numbers are where a page ends, so no second estimate of the
    # page boundary is needed and none is made.
    breaks = [i for c in candidates if c.accepted and c.is_numeric
              for i in c.lines]
    catch, catch_matches = find_catchwords(lines, breaks, marked, skip)
    marked |= catch
    return marked, candidates, page_length, catch_matches


# ---------------------------------------------------------------------------
# Furniture as a line PREFIX
# ---------------------------------------------------------------------------
#
# Everything above assumes furniture occupies its own line. That holds for
# plain-text transcription, where a page break is a line break. It is false of
# page-per-line OCR, where a whole page arrives as one paragraph and the
# running head is simply its first words:
#
#     WONDERFUL EMERALD CITY OF OZ  loi  fore I have no brains, and I c...
#
# `loi` is the page number 101, misread. On the first real scan tested, 92 of
# 269 non-blank lines carried a prefix like this and the detector found none.
#
# The signal is unchanged: a running head RECURS. A chapter heading appears
# once. That difference is what makes this safe, and it is the only guard the
# rule needs beyond the shape of the text.

#: Below this median line length the file is not page-per-line, and the
#: line-based rules above are the right ones. Running this as well would risk
#: editing lines for no gain.
PAGE_PER_LINE_MIN_MEDIAN = 200
#: Highest variation in line length still consistent with one line per page.
#: Set between the two populations above, not at the edge of either.
PAGE_PER_LINE_MAX_CV = 0.75

#: A running head must recur at least this often. A chapter heading appears
#: once, which is precisely what keeps it safe from this rule.
PREFIX_MIN_OCCURRENCES = 3

#: Similarity above which a prefix group is treated as an OCR-damaged copy of
#: a larger one. Looser than the line rule's threshold because a running head
#: is long, so a few wrong characters matter proportionally less.
PREFIX_NEAR_DUPLICATE = 0.80

#: Two or more words in capitals at the start of a line, optionally preceded
#: by a page number.
#:
#: The leading number matters more than it looks. Books set the book title on
#: the verso and the chapter title on the recto, and the page number sits on
#: the outer edge — which puts it BEFORE the title on a left-hand page:
#:
#:     46 THE WONDERFUL WIZARD OF OZ  from some wild animal hidden...
#:     WONDERFUL EMERALD CITY OF OZ  loi  fore I have no brains...
#:
#: Requiring a capital first caught only the recto pages. On the first real
#: scan that was 74 heads found and **88 missed**, so the half that was
#: invisible was the larger half.
#:
#: The number is written loosely because OCR mangles it: `6o` for 60, `l` for
#: 1. It is safe here only because two or more capitalised words must follow.
#: The page number is captured separately from the title, because the two must
#: be grouped differently. `normalise` removes digits so that `JANE EYRE 42`
#: and `JANE EYRE 43` count as one head, but OCR leaves residue a digit-strip
#: cannot reach: `6o` for 60 keeps its `o`, and `io6` for 106 keeps `io`. Fold
#: those into the key and one running head becomes several, each too rare to
#: reach the threshold. Seven pages escaped that way before this split.
PREFIX = re.compile(
    r"^\s*(?:([0-9IVXLilo|/S]{1,4})\s+)?"
    r"((?:[A-Z][A-Z0-9.,'\u2019\u201c\u201d\"\-]*\s+){1,9}"
    r"[A-Z][A-Z0-9.,'\u2019\u201c\u201d\"\-]*)\s")

#: A page number may follow the head. `loi` for 101 and `iii` for 111 are
#: routine, so this is deliberately loose: it is only stripped when it sits
#: between a confirmed running head and the page text.
TRAILING_PAGE_NO = re.compile(r"^\s*([0-9IVXLCilvx|/l]{1,6})\s+(?=[A-Za-z\"'])")


@dataclass
class PrefixEdit:
    """A running head to be removed from the FRONT of a line, not the line."""

    line: int              # 1-based
    prefix: str            # the text to remove
    end: int               # character offset just past it
    reason: str = ""


def is_page_per_line(lines: list[str]) -> bool:
    """Whether each line holds a whole page rather than a typeset line.

    **Length alone does not establish this, and for a while this function
    pretended it did.** It tested only that the median line was long, which is
    equally true of a file stored one *paragraph* per line — the normal shape
    of a Standard Ebooks or Gutenberg transcription. Emma passed it at a median
    of 231 characters and Frankenstein at 396. Nothing went wrong, because the
    prefix rule additionally needs a capitalised prefix recurring three times
    and neither book has one, and because both were segmented by an earlier
    tier. Both of those were luck rather than design.

    Uniformity is the property that actually separates them. **A page holds a
    fixed amount of type; a paragraph holds as much as the author wrote.**
    Measured over the corpus:

        Treasure Island (scan)     median 1363   cv 0.34
        Oz (scan)                  median 1080   cv 0.61
        --------------------------------------------------
        Frankenstein (paragraphs)  median  396   cv 0.88
        Emma (paragraphs)          median  231   cv 1.35
        Jane Eyre (paragraphs)     median  129   cv 1.23

    The two populations do not overlap on either measure, and both are now
    required. Length keeps the rule cheap; uniformity is what makes it true.
    """
    lens = [len(l.strip()) for l in lines if l.strip()]
    if len(lens) < 20:
        return False
    if statistics.median(lens) < PAGE_PER_LINE_MIN_MEDIAN:
        return False
    mean = statistics.fmean(lens)
    return bool(mean) and statistics.pstdev(lens) / mean <= PAGE_PER_LINE_MAX_CV


def find_prefix_furniture(lines: list[str], skip: set[int] | None = None
                          ) -> list[PrefixEdit]:
    """Find running heads welded to the start of page-per-line text.

    **This edits lines rather than removing them, and that is the dangerous
    part.** Removing a line wrongly loses a page, which is obvious. Removing a
    prefix wrongly loses the first few words of a page, which is quiet, and a
    quiet error in a corpus tool is the worse of the two.

    So the bar is deliberately higher than for the line rules: the text must be
    page-per-line, and the prefix must recur. Anything appearing once is left
    exactly where it is.
    """
    skip = skip or set()
    if not is_page_per_line(lines):
        return []

    groups: dict[str, list[tuple[int, str, int]]] = {}
    for i, line in enumerate(lines, 1):
        if i in skip:
            continue
        m = PREFIX.match(line)
        if not m:
            continue
        # Grouped on the TITLE only; the page number varies by definition.
        groups.setdefault(normalise(m.group(2)), []).append(
            (i, m.group(0).strip(), m.end(2)))

    # Fold OCR variants back into the series they belong to.
    #
    # This scan mangles a head about one page in six: `WIZARB>` for WIZARD,
    # `W0NBERFUL` for WONDERFUL, `QZ` for OZ, `DOROXrHY` for DOROTHY. Each
    # damaged copy forms its own group, too rare to reach the threshold, and
    # survives into the corpus.
    #
    # **This is the fourth time OCR damage has split a series this package was
    # right about**, and the cure has been the same every time. It is worth
    # reaching for before anything else when a rule finds most of something and
    # misses a scattering.
    #
    # Merging is one-directional, smallest into largest, so two genuinely
    # different running heads of similar frequency are never combined.
    _merge_prefix_variants(groups)

    out: list[PrefixEdit] = []
    for key, hits in groups.items():
        if len(hits) < PREFIX_MIN_OCCURRENCES:
            continue
        for line_no, text, end in hits:
            rest = lines[line_no - 1][end:]
            n = TRAILING_PAGE_NO.match(rest)
            stop = end + (n.end(1) if n else 0)
            out.append(PrefixEdit(
                line=line_no, prefix=lines[line_no - 1][:stop].strip(), end=stop,
                reason=f"this heading opens {len(hits)} pages, so it is a "
                       f"running head rather than part of the text"))
    out.sort(key=lambda e: e.line)
    return out


#: Fewest disjoint series before a document's chapters are read from its
#: running heads. Two proves nothing: any book title plus any one repeated
#: phrase makes two. Requiring several means the series have to *partition*
#: the text, which is a property of chapters and of very little else.
MIN_HEAD_CHAPTERS = 3


def find_head_chapters(lines: list[str], start: int = 0, end: int | None = None,
                       skip=lambda i: False) -> list[tuple[int, str]]:
    """Recover chapter boundaries from the running heads themselves.

    **The last resort, and on badly scanned books the only one that works.**

    The Internet Archive scan of *The New Wizard of Oz* contains no chapter
    headings whatever. Every chapter opens with a decorative drop-capital, and
    OCR destroys the whole line trying to read it::

        ^^^^ Dorothy awoke ^^^|[ %, the sun was shining through the trees
        11 §W^^ little party of travel*^ ^ lers awakened the next morning

    The title that belongs above those lines is simply gone. But the same title
    is printed at the top of *every page* of its chapter, so it survives twenty
    times over in the running heads. **A heading is set once; a running head is
    repeated on every page, and in damaged material that redundancy is the
    stronger evidence.**

    So a new running-head series is a chapter boundary.

    ### Telling a chapter title from the book title

    Both are running heads, and the book title is also the more frequent, so
    frequency is no help. The difference is structural: a chapter's series
    occupies a contiguous stretch and **no two chapters overlap**, while the
    book title runs the length of the whole volume and therefore overlaps every
    chapter there is.

    The book title is discarded by that property alone, with no threshold and
    no list of stop-words: the most-overlapping series is dropped repeatedly
    until the survivors are mutually disjoint. On the Oz scan this removes
    `THE WONDERFUL WIZARD OF OZ`, which overlaps eighteen others, and then
    `THE WONDERFUL`, a truncated variant of it that overlaps twelve. Neither is
    special-cased; both fail the same test.

    Returns (line index, title) pairs, 0-based, in order. The title reported is
    the most frequent spelling in the series rather than the first, because the
    first may be the one OCR mangled.
    """
    end = len(lines) if end is None else end
    if not is_page_per_line(lines):
        return []

    groups: dict[str, list[tuple[int, str]]] = {}
    for i in range(start, end):
        if skip(i):
            continue
        m = PREFIX.match(lines[i])
        if m:
            groups.setdefault(normalise(m.group(2)), []).append((i, m.group(2)))

    _merge_prefix_variants(groups)
    series = {k: sorted(v) for k, v in groups.items()
              if len(v) >= PREFIX_MIN_OCCURRENCES}
    if len(series) <= MIN_HEAD_CHAPTERS:
        return []

    spans = {k: (v[0][0], v[-1][0]) for k, v in series.items()}

    def clashes(k: str) -> int:
        a = spans[k]
        return sum(1 for o, b in spans.items()
                   if o != k and a[0] <= b[1] and b[0] <= a[1])

    # Drop the most-entangled series until nothing overlaps anything. The book
    # title overlaps every chapter and so always goes first; a chapter overlaps
    # only the book title and so always survives it.
    while spans:
        worst = max(spans, key=lambda k: (clashes(k), spans[k][1] - spans[k][0]))
        if clashes(worst) == 0:
            break
        del spans[worst]

    if len(spans) < MIN_HEAD_CHAPTERS:
        return []

    out = []
    for k in spans:
        # Most frequent spelling, earliest wins a tie.
        #
        # `max(set(forms), key=forms.count)` looks equivalent and is not: it
        # iterates a set, so a tie is broken by hash order. Treasure Island has
        # END OF THE FIRST DAY'S FIGHTING twice with a typographic apostrophe
        # and twice with a straight one, and the two engines picked different
        # winners. **A tie-break that is not written down is a tie-break the
        # other implementation cannot copy.**
        forms = [f for _, f in series[k]]
        title, best = forms[0], 0
        for f in forms:
            n = forms.count(f)
            if n > best:
                title, best = f, n
        out.append((series[k][0][0], title))
    return sorted(out)


def _merge_prefix_variants(groups: dict) -> None:
    """Fold OCR variants of a running head back into the series they belong to.

    Shared by the furniture rule and the chapter rule so the two can never
    disagree about what counts as one series.
    """
    keys = sorted(groups, key=lambda k: -len(groups[k]))
    absorbed: set[str] = set()
    for i, big in enumerate(keys):
        if big in absorbed:
            continue
        for small in keys[i + 1:]:
            if small in absorbed:
                continue
            if len(groups[small]) * 2 > len(groups[big]):
                continue
            if SequenceMatcher(None, big, small).ratio() >= PREFIX_NEAR_DUPLICATE:
                groups[big].extend(groups[small])
                absorbed.add(small)
    for k in absorbed:
        del groups[k]
    for v in groups.values():
        v.sort()


def apply_prefix_edits(lines: list[str], edits: list[PrefixEdit]) -> list[str]:
    """Remove confirmed running heads from the front of their lines."""
    by_line = {e.line: e for e in edits}
    out = []
    for i, line in enumerate(lines, 1):
        e = by_line.get(i)
        out.append(line[e.end:].lstrip() if e else line)
    return out
