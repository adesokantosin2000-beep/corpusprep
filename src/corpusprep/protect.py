"""
corpusprep.protect
==================

Protected spans: lines that must never be rejoined.

Reflow cannot begin until this exists. Verse, drama and tabular material carry
their line breaks as part of the composition, and a reflow that treats them as
typesetting artefacts destroys the work.

**The question is not the genre of the text. It is who broke the line.**

    broken by a typesetter    stops mid-phrase, continues in lower case
    broken by the author      stops at a phrase boundary, next line capitalised

That reframing matters because genre cannot be measured reliably and the break
can. The obvious signal, line-length variance, does not work: verse scores 0.31
on the fixtures and hard-wrapped prose 0.27, with unwrapped prose highest of all
at 1.23. There is no threshold in there. The two-signal test separates verse and
drama from wrapped prose by a factor of twenty, 60-77% against 3%.

Neither signal works alone. Line-initial capitals alone catch every sentence
start; line-final punctuation alone scores 95% on unwrapped prose, where each
line is a whole paragraph. Together they describe the break rather than the
text.

**Protection is computed per span, not per document**, because a novel contains
a quoted ballad and a play contains prose scenes. See `design/DECISIONS.md`.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

#: Characters that close a phrase. A line ending on one was probably finished
#: rather than merely full.
_CLOSERS = ('.', ',', ';', ':', '!', '?', '"', "'", '’', '”', '--',
            '—')

#: Lines either side used to judge one line. Small enough to find a six-line
#: stanza, large enough that one capitalised sentence start proves nothing.
WINDOW = 6
#: Share of authorial-looking breaks in the window before a line is protected.
MIN_RATE = 0.45
#: A protected run shorter than this is noise, not a passage.
MIN_SPAN = 3
#: Share of authorial-looking breaks a block needs to be protected *by its
#: neighbours* when it cannot carry itself. Half the standing threshold, which
#: is still seven times what hard-wrapped prose scores.
CORROBORATE = MIN_RATE / 2
#: Above this 95th-percentile line length the text is not hard-wrapped at all,
#: so there is nothing to rejoin and nothing to protect.
UNWRAPPED_P95 = 200
#: Share of lines that must be blank before blank lines are suspected of being
#: line spacing rather than structure.
SPACED_MIN_BLANK = 0.40
#: Share of text lines that must stand alone between blanks for that suspicion
#: to hold. Alternating stanzas of three would clear the density test on their
#: own; only uniform one-line-per-block layout is line spacing.
SPACED_MIN_ALONE = 0.80

_INDENT = re.compile(r"^[ \t]+")


@dataclass
class Span:
    """A run of consecutive protected lines. 1-based, inclusive."""

    start: int
    end: int
    reason: str = ""

    @property
    def lines(self) -> list[int]:
        return list(range(self.start, self.end + 1))

    def __len__(self) -> int:
        return self.end - self.start + 1


def is_wrapped(lines: list[str]) -> bool:
    """Whether the text was hard-wrapped at all.

    A file storing one line per paragraph has nothing to rejoin. Answering that
    first avoids asking a question the document never posed.
    """
    lens = [len(l.rstrip()) for l in lines if l.strip()]
    if len(lens) < 10:
        return False
    p95 = sorted(lens)[int(len(lens) * 0.95)]
    return p95 < UNWRAPPED_P95


def authorial_break(a: str, b: str) -> bool:
    """Did the author end line ``a``, rather than the margin?

    Both halves are required. A capital alone marks every sentence start; a
    closing mark alone is true of every paragraph in an unwrapped file.
    """
    a, b = a.rstrip(), b.strip()
    if not a or not b:
        return False
    if not a.endswith(_CLOSERS):
        return False
    first = b[0]
    return first.isupper() or not first.isalpha()


def break_profile(lines: list[str]) -> list[bool]:
    """One judgement per line: was its own break authorial?

    The last line of the file and any line followed by a blank get ``False``,
    since there is no break to judge. Blank lines separate stanzas as well as
    paragraphs, so they carry no evidence either way.
    """
    out: list[bool] = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        out.append(authorial_break(line, nxt))
    return out


def _runs(lines: list[str]) -> tuple[list[int], list[int]]:
    """Lengths of the consecutive blank runs and text runs, in order."""
    blank_runs: list[int] = []
    text_runs: list[int] = []
    n = len(lines)
    i = 0
    while i < n:
        blank = not lines[i].strip()
        j = i
        while j + 1 < n and (not lines[j + 1].strip()) == blank:
            j += 1
        (blank_runs if blank else text_runs).append(j - i + 1)
        i = j + 1
    return blank_runs, text_runs


def spacing_run(lines: list[str]) -> int | None:
    """The blank-run length that is line spacing, or ``None`` for structure.

    **A blank line is a structural boundary only when blank lines are not the
    norm.** PDF extraction commonly puts one between every line of the file; at
    that density, uniformly alternating, blanks are the typesetter's leading
    rendered as whitespace and carry no structure at all.

    Both tests are needed. Density alone would misread a poem printed as
    three-line stanzas with three-line gaps, where the blanks *are* structure;
    requiring that text lines stand alone is what separates leading from
    stanza breaks.

    Returns the modal blank-run length, which is the run to discard. Longer
    runs are the real boundaries and survive.
    """
    n = len(lines)
    if n < 10:
        return None
    blank = sum(1 for l in lines if not l.strip())
    if blank / n < SPACED_MIN_BLANK:
        return None
    blank_runs, text_runs = _runs(lines)
    if not blank_runs or not text_runs:
        return None
    alone = sum(r for r in text_runs if r == 1)
    if alone / sum(text_runs) < SPACED_MIN_ALONE:
        return None
    return statistics.mode(blank_runs)


def _despace(lines: list[str], run: int) -> tuple[list[str], list[int]]:
    """Drop the spacing blanks, keeping longer runs as one blank line.

    Returns the compacted lines and, for each of them, the index it came from
    in the original, so spans can be reported in the caller's line numbers.
    """
    out: list[str] = []
    index: list[int] = []
    n = len(lines)
    i = 0
    while i < n:
        if lines[i].strip():
            out.append(lines[i])
            index.append(i)
            i += 1
            continue
        j = i
        while j + 1 < n and not lines[j + 1].strip():
            j += 1
        if (j - i + 1) > run:
            # A gap wider than the leading is a paragraph or stanza boundary.
            # It must survive, or one protected seed extends over the whole
            # file and prose is protected along with the verse.
            out.append("")
            index.append(i)
        i = j + 1
    return out, index


def find(lines: list[str], skip: set[int] | None = None) -> list[Span]:
    """Find protected spans, seeing through line spacing first.

    Everything below assumes a blank line means something. Where blank lines
    are merely how the file was extracted, they are removed before the rule
    runs and the spans are mapped back afterwards, so the rule sees the text
    as it was set rather than as it was extracted.
    """
    skip = skip or set()
    run = spacing_run(lines)
    if run is None:
        return _find(lines, skip)
    compact, index = _despace(lines, run)
    sub_skip = {k + 1 for k, src in enumerate(index) if src + 1 in skip}
    return [Span(start=index[s.start - 1] + 1,
                 end=index[s.end - 1] + 1,
                 reason=s.reason)
            for s in _find(compact, sub_skip)]


def _blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Blank-delimited blocks as 0-based inclusive index pairs."""
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip():
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(lines) - 1))
    return out


def _is_strong(protected: list[bool], lines: list[str],
               block: tuple[int, int]) -> bool:
    """Whether a block is protected firmly enough to vouch for its neighbour.

    **A single protected line is not a passage.** The per-line judgements
    include ones that never become a span, and letting those vouch for
    anything is how corroboration reached three paragraphs of *Jane Eyre*: a
    lone flagged line in wrapped prose seeded the block beside it, which seeded
    the next. A voucher must be most of a block and at least a span's worth.
    """
    lo, hi = block
    body = [k for k in range(lo, hi + 1) if lines[k].strip()]
    if not body:
        return False
    yes = sum(1 for k in body if protected[k])
    return yes >= MIN_SPAN and yes / len(body) >= 0.5


def _flanked(protected: list[bool], lines: list[str],
             blocks: list[tuple[int, int]], idx: int) -> bool:
    """Whether the block at ``idx`` has a firmly protected block beside it.

    One side is enough. The first stanza of a poem has its title above it and
    the rest of the poem below, and it is as much part of the poem as the rest.
    """
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(blocks) and _is_strong(protected, lines, blocks[j]):
            return True
    return False


def _find(lines: list[str], skip: set[int] | None = None) -> list[Span]:
    """Find spans whose line breaks look deliberate.

    Returns an empty list for text that is not hard-wrapped, and for prose,
    which is the answer that matters most: a false positive here means a
    paragraph is left in fragments for ever.
    """
    skip = skip or set()
    if not is_wrapped(lines):
        return []

    profile = break_profile(lines)
    n = len(lines)
    protected: list[bool] = [False] * n

    for i in range(n):
        if i + 1 in skip or not lines[i].strip():
            continue
        # The window stops at a blank line in each direction. A blank line is a
        # structural boundary, and evidence from the block on the other side is
        # not evidence about this one.
        #
        # Without this an eight-line stanza sitting between two paragraphs is
        # judged mostly on the paragraphs, and enjambed verse — where alternate
        # lines run on without punctuation — is lost entirely. That is a
        # windowing fault, not a threshold that needs loosening: a looser
        # threshold would start protecting prose, which is the one error this
        # rule must never make.
        lo = i
        while lo > 0 and lines[lo - 1].strip() and i - lo < WINDOW:
            lo -= 1
        hi = i
        while hi + 1 < n and lines[hi + 1].strip() and hi - i < WINDOW:
            hi += 1
        window = [profile[j] for j in range(lo, hi + 1) if lines[j].strip()]
        if not window:
            continue
        if sum(window) / len(window) >= MIN_RATE:
            protected[i] = True

    # A stanza is not judged in isolation from the poem it sits in.
    #
    # The window stops at a blank line, so a stanza that rhymes abab with the
    # odd lines unpunctuated carries only half its breaks and scores under the
    # threshold — 38% for an eight-line stanza, where the last line scores
    # nothing because no line follows it to vouch for the break. Four such
    # stanzas in ten poems were missed while the stanzas either side of them
    # were protected.
    #
    # **The answer is not a lower threshold.** 45% is what holds wrapped prose
    # at 3%, and prose protected is the error that cannot be recovered from.
    # The evidence not being used is the neighbouring block, so that is what is
    # added here: a block already flanked by protected verse needs only half
    # the rate to join it.
    #
    # Seeded once from what the rule found on its own, never iterated. A block
    # protected by corroboration does not go on to corroborate the next one, or
    # a single stanza would carry protection to the end of the file.
    blocks = _blocks(lines)
    joined: list[int] = []
    for idx, (lo, hi) in enumerate(blocks):
        body = [k for k in range(lo, hi + 1) if lines[k].strip()]
        if not body or len(body) < MIN_SPAN or any(protected[k] for k in body):
            continue
        if sum(profile[k] for k in body) / len(body) < CORROBORATE:
            continue
        if not _flanked(protected, lines, blocks, idx):
            continue
        joined += body
    for k in joined:
        protected[k] = True

    # Indentation corroborates but never decides on its own: a block quotation
    # of prose is indented too, and must still be reflowed.
    indents = [len(_INDENT.match(l).group(0)) if _INDENT.match(l) else 0
               for l in lines if l.strip()]
    common = statistics.mode(indents) if indents else 0

    spans: list[Span] = []
    i = 0
    while i < n:
        if not protected[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and (protected[j + 1] or not lines[j + 1].strip()):
            j += 1
        # Trim blank lines from either end; a stanza gap belongs inside a span
        # but not at its edges.
        a, b = i, j
        while a <= b and not lines[a].strip():
            a += 1
        while b >= a and not lines[b].strip():
            b -= 1
        # Extend to the enclosing blank-delimited blocks. A stanza is an
        # indivisible unit: protecting five lines of it and reflowing the other
        # three is not a partial success but a corruption, and the last line of
        # a passage is always the weakest evidence because nothing follows it
        # to vouch for the break.
        while a > 0 and lines[a - 1].strip():
            a -= 1
        while b + 1 < n and lines[b + 1].strip():
            b += 1

        if b >= a and (b - a + 1) >= MIN_SPAN:
            body = [lines[k] for k in range(a, b + 1) if lines[k].strip()]
            rate = sum(profile[k] for k in range(a, b + 1)
                       if lines[k].strip()) / max(1, len(body))
            ind = sum(1 for l in body
                      if _INDENT.match(l) and len(_INDENT.match(l).group(0)) > common)
            reason = (f"{rate:.0%} of these line breaks fall at a phrase "
                      f"boundary followed by a capital")
            if ind == len(body) and body:
                reason += ", and every line is indented"
            spans.append(Span(start=a + 1, end=b + 1, reason=reason))
        i = max(j, b) + 1

    # Extending to block boundaries can make two separate seeds land on the
    # same block, so overlapping or touching spans are merged. Without this the
    # same passage is reported twice and its line count double-counted.
    merged: list[Span] = []
    for s in sorted(spans, key=lambda s: (s.start, s.end)):
        if merged and s.start <= merged[-1].end + 1:
            if s.end > merged[-1].end:
                merged[-1] = Span(start=merged[-1].start, end=s.end,
                                  reason=merged[-1].reason)
            continue
        merged.append(s)
    return merged


def find_in_document(doc) -> list[Span]:
    """Find protected spans in a segmented Document, ignoring apparatus."""
    skip = {
        i + 1
        for r in doc.regions
        if r.label in ("pg_header", "pg_licence")
        for i in range(r.start, r.end)
    }
    return find(doc.lines, skip)


def protected_lines(spans: list[Span]) -> set[int]:
    return {n for s in spans for n in s.lines}
