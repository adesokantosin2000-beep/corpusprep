"""
corpusprep.interface
====================

Interface furniture: the labels an application printed, not the text a person
wrote.

A tester's corpus of comments was 45% URL by character. With the URLs removed,
about 3% of what remained was `Like`, `Reply`, `2 likes`, `View replies (4)` —
recurring the way a running head recurs, and just as much apparatus.

**The obvious rule is a list of words, and it destroys prose.** `Like`,
`Reply`, `Share` and `Follow` are ordinary English. A novel contains the line
`Reply.` in dialogue, and a wordlist deletes it. This has already been learned
twice in this package: short lines and repeated lines were the prototype's two
rules and both destroyed prose, which is why page furniture is found by its
*interval* instead.

**The discriminating signal here is position, not vocabulary.** An interface
prints its labels *after* the thing they act on. In a comment thread the body
comes first and the controls come last, so a label sits in the tail of its
record with nothing but other labels after it. A one-word comment — `Same`,
`Beautiful` — sits at the head, however often it repeats.

So the rule reads the trailing run of each record and asks which short lines
recur there across the thread. Ordinary text is never in a trailing run unless
the record has no controls at all, and a stray body line will not then clear
the recurrence bar.

**The rule is licensed by the document, not by the line.** Nothing is called
interface furniture until the file itself looks like a scraped feed: handles,
relative timestamps, one record after another. Without that, `find()` returns
nothing at all — the same shape as page furniture, which will not claim a text
is page-imaged without an ascending page-number sequence.

Detection never deletes. These lines are reported and removed only by a variant
that asks for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Longest line that can be a control label.
MAX_LEN = 24
#: Most words a control label can have. `View replies (19)` is three.
MAX_WORDS = 4
#: Fewest records a key must end before it is furniture at all.
MIN_RECORDS_WITH = 3
#: Share of the thread's records a key must end. A genuine one-word comment
#: repeats; it does not repeat in four records out of five.
MIN_SHARE = 0.20
#: Fewest records before the file is treated as a scraped feed.
#:
#: Three comments is not evidence. With so few records a control that ends
#: every one of them and a coincidence are the same observation, and the rule
#: should say nothing rather than guess. `social_markdown.md`, which has three,
#: is declined deliberately.
MIN_RECORDS = 5

#: `[name](url)` as a Markdown converter writes a handle, or a bare `@name`.
_HANDLE = re.compile(r"^\s*\[@?[\w.]+\]\(\S+\)\s*$|^\s*@[\w.]+\s*$")
#: `9 w`, `36 w`, `2 d`, `1 y` — a relative timestamp, linked or bare.
_RELTIME = re.compile(r"^\s*\[?\s*\d{1,3}\s*[smhdwy]\s*\]?(\(\S+\))?\s*$",
                      re.IGNORECASE)
_DIGITS = re.compile(r"\d+")
_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)


@dataclass
class Series:
    """One recurring control label."""

    key: str
    lines: list[int] = field(default_factory=list)   # 1-based
    records: int = 0
    reason: str = ""


def looks_like_handle(line: str) -> bool:
    return bool(_HANDLE.match(line))


def looks_like_relative_time(line: str) -> bool:
    return bool(_RELTIME.match(line))


def normalise(line: str) -> str:
    """Fold a label to the family it belongs to.

    `2 likes` and `340 likes` are one control, so digits become `#`. Case and
    edge punctuation are dropped for the same reason.
    """
    s = _DIGITS.sub("#", line.strip().lower())
    return _EDGE.sub("", s)


def label_shaped(line: str) -> bool:
    """Short enough and few enough words to be a control rather than a sentence."""
    s = line.strip()
    return bool(s) and len(s) <= MAX_LEN and len(s.split()) <= MAX_WORDS


def records(lines: list[str]) -> list[tuple[int, int]]:
    """Record spans as 0-based inclusive index pairs.

    A record starts at a handle line, or at a relative timestamp where the
    export carries no handles. Anything before the first marker is preamble and
    belongs to no record.
    """
    starts = [i for i, l in enumerate(lines) if looks_like_handle(l)]
    if len(starts) < MIN_RECORDS:
        starts = [i for i, l in enumerate(lines) if looks_like_relative_time(l)]
    if len(starts) < MIN_RECORDS:
        return []
    return [(a, b - 1) for a, b in zip(starts, starts[1:] + [len(lines)])]


def _trailing(lines: list[str], lo: int, hi: int,
              skip: set[int]) -> list[int]:
    """The run of control-shaped lines at the end of one record.

    **A record is never all controls.** Something was commented on, or there
    would be no record, so the walk stops before it eats the last line of the
    body. Without that guard a one-word comment sitting directly above the
    controls — `Same`, `Beautiful` — is inside the trailing run in every
    record it appears in, and no amount of counting afterwards can tell it
    from a control, because by then it looks exactly like one.
    """
    body = [k for k in range(lo, hi + 1)
            if lines[k].strip()
            and not looks_like_handle(lines[k])
            and not looks_like_relative_time(lines[k])]
    out: list[int] = []
    for k in reversed(body):
        if k + 1 in skip or not label_shaped(lines[k]):
            break
        if len(out) + 1 >= len(body):
            break
        out.append(k)
    out.reverse()
    return out


def find(lines: list[str], skip: set[int] | None = None
         ) -> tuple[set[int], list[Series]]:
    """Interface furniture, by line number, with the series that explain it."""
    skip = skip or set()
    spans = records(lines)
    if len(spans) < MIN_RECORDS:
        return set(), []

    seen: dict[str, Series] = {}
    tails: list[list[int]] = []
    for lo, hi in spans:
        tail = _trailing(lines, lo, hi, skip)
        tails.append(tail)
        for key in {normalise(lines[k]) for k in tail}:
            seen.setdefault(key, Series(key=key)).records += 1
        for k in tail:
            seen[normalise(lines[k])].lines.append(k + 1)

    floor = max(MIN_RECORDS_WITH, round(MIN_SHARE * len(spans)))
    confirmed = {k: s for k, s in seen.items() if s.records >= floor}
    for s in confirmed.values():
        s.reason = (f"ends {s.records} of {len(spans)} records, "
                    f"after the text rather than among it")

    # A label that appears on only a few records — `See translation`, `Edited`
    # — cannot clear the share on its own, and a rule that let it through on
    # its count alone would let a repeated one-word comment through too.
    #
    # What separates them is company. An occasional control still sits in the
    # same trailing run as the controls that recur on every record; a comment
    # never does, because a comment is the text those controls come after. So a
    # key is admitted on corroboration only when *every* time it appears, it
    # appears beside a series already confirmed.
    for key, s in seen.items():
        if key in confirmed or s.records < MIN_RECORDS_WITH:
            continue
        company = 0
        for tail in tails:
            keys = {normalise(lines[k]) for k in tail}
            if key not in keys:
                continue
            if keys & confirmed.keys():
                company += 1
        if company == s.records:
            s.reason = (f"ends {s.records} of {len(spans)} records, always "
                        f"beside a control that ends most of them")
            confirmed[key] = s

    out = sorted(confirmed.values(), key=lambda s: (-s.records, s.key))
    return {n for s in out for n in s.lines}, out


def find_in_document(doc) -> tuple[set[int], list[Series]]:
    skip = {
        i + 1
        for r in doc.regions
        if r.label in ("pg_header", "pg_licence")
        for i in range(r.start, r.end)
    }
    return find(doc.lines, skip)
