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

#: Longest line that can plausibly be furniture.
MAX_LEN = 60
#: Fewest repeats before a group is considered at all.
MIN_OCCURRENCES = 5
#: Highest coefficient of variation accepted as "regular".
MAX_CV = 0.25
#: How far a group's interval may sit from the estimated page length.
PAGE_GAP_TOLERANCE = 0.25
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


def estimate_page_length(candidates: list[Candidate]) -> float:
    """Estimate the document's page length from the most regular series.

    Taking the modal gap across all candidates would be swayed by whichever
    phrase happens to be common. The most regular series is a better witness,
    since regularity is the property that makes something furniture at all.
    """
    regular = [c for c in candidates if c.cv < MAX_CV and c.median_gap > 0]
    if not regular:
        return 0.0
    regular.sort(key=lambda c: (c.cv, -len(c.lines)))
    best = regular[0].median_gap
    # Heads alternating verso and recto recur every two pages, so the most
    # regular series may be measuring a double page.
    halves = [c.median_gap for c in regular
              if abs(c.median_gap * 2 - best) / best < PAGE_GAP_TOLERANCE]
    return min(halves) if halves else best


def judge(candidates: list[Candidate], page_length: float) -> list[Candidate]:
    """Decide which candidates are furniture, recording why for each."""
    for c in candidates:
        if c.cv >= MAX_CV:
            c.reason = (f"irregular: gaps vary by {c.cv:.0%}, "
                        f"above the {MAX_CV:.0%} limit")
            continue
        if page_length <= 0:
            c.reason = "no page length could be estimated"
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
         ) -> tuple[set[int], list[Candidate], float]:
    """Return (furniture line numbers, all candidates, page length estimate).

    Every candidate is returned, accepted or not, with the reason recorded.
    A rule the user cannot interrogate is a rule the user cannot trust.
    """
    candidates = collect(lines, skip)
    page_length = estimate_page_length(candidates)
    judge(candidates, page_length)
    marked = {i for c in candidates if c.accepted for i in c.lines}
    return marked, candidates, page_length
