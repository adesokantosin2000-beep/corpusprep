"""
corpusprep.review
=================

The review queue: where every uncertain rule defers to the researcher.

Detection rules in this package refuse to guess. De-hyphenation flags a break
it cannot resolve; footnote pairing reports a marker nothing answers. Until
those deferrals have somewhere to go, refusing to guess simply means refusing
to help.

**Items are identified by content, never by line number.** Remove a Gutenberg
header and every line below it shifts, so a saved decision keyed on position
would silently reattach to the wrong word. The key is the thing in question,
`def-inite`, which survives every transformation that moves lines about.

That choice has a second benefit worth more than stability: **decisions are
reusable across documents.** A researcher preparing forty volumes of one
edition answers `to-morrow` once, and volume two arrives already answered.

The file is tab-separated and hand-editable on purpose. A queue nobody opens is
a queue nobody uses, so it opens in a text editor, a spreadsheet, or `awk`.

The queue supplies missing confidence. **It never invents behaviour**: an
answer of `join` produces exactly what the tool would have produced had it been
sure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: The undecided marker. An item carrying this is asked again next run.
UNDECIDED = "?"

HEADER = """\
# CorpusPrep review queue
#
# One decision per line, tab-separated. Edit the first column and re-import.
# Lines beginning with # are ignored, as are blank lines.
#
# DECISION is one of:
#
#   ?        undecided. The tool will ask again and change nothing meanwhile.
#   join     write the two fragments as one word, without the hyphen
#   keep     keep the hyphen
#   <text>   use exactly this instead, for anything the options above miss
#
# Items are identified by the ITEM column, not by line number, so a decision
# survives editing the source and applies to every occurrence in this corpus
# and in any other you run against this file.
#
# DECISION\tTYPE\tITEM\tWHY
"""


@dataclass
class Item:
    """One thing the tool declined to decide."""

    kind: str                  # "hyphen", "footnote", ...
    key: str                   # content identity, e.g. "def-inite"
    why: str = ""              # the rule's own explanation
    decision: str = UNDECIDED
    #: Where it occurs, for display only. Never used for identity.
    lines: list[int] = field(default_factory=list)

    @property
    def answered(self) -> bool:
        return self.decision != UNDECIDED and self.decision.strip() != ""

    def id(self) -> tuple[str, str]:
        return (self.kind, self.key)


def write(items: list[Item], path: str | Path,
          existing: dict[tuple[str, str], str] | None = None) -> Path:
    """Write a queue, carrying forward any decisions already made.

    Answered items are kept in the file rather than dropped. The queue is a
    record of what was decided as well as a list of what is outstanding, and a
    reviewer needs to be able to change their mind.
    """
    existing = existing or {}
    path = Path(path)
    rows = []
    for it in sorted(items, key=lambda i: (i.kind, i.key)):
        decision = existing.get(it.id(), it.decision) or UNDECIDED
        where = (f"  (lines {', '.join(str(n) for n in it.lines[:4])}"
                 f"{'...' if len(it.lines) > 4 else ''})" if it.lines else "")
        rows.append(f"{decision}\t{it.kind}\t{it.key}\t{it.why}{where}")
    path.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def read(path: str | Path) -> dict[tuple[str, str], str]:
    """Read a queue into ``{(kind, key): decision}``.

    Undecided rows are omitted, so an untouched queue yields an empty mapping
    and therefore changes nothing. That property is what makes the file safe to
    generate and experiment with.
    """
    out: dict[tuple[str, str], str] = {}
    p = Path(path)
    if not p.exists():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        decision, kind, key = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not kind or not key:
            continue
        if decision and decision != UNDECIDED:
            out[(kind, key)] = decision
    return out


def parse(text: str) -> dict[tuple[str, str], str]:
    """Same as :func:`read`, for a queue held in memory."""
    out: dict[tuple[str, str], str] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        decision, kind, key = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if kind and key and decision and decision != UNDECIDED:
            out[(kind, key)] = decision
    return out


# ---------------------------------------------------------------------------
# Building a queue from what the rules flagged
# ---------------------------------------------------------------------------

def from_document(doc) -> list[Item]:
    """Collect everything the rules declined to decide, deduplicated by key.

    The same broken word usually occurs several times. It is one question, so
    it appears once and is answered once.
    """
    by_key: dict[tuple[str, str], Item] = {}

    for b in getattr(doc, "hyphen_breaks", []) or []:
        if not b.needs_review:
            continue
        it = by_key.setdefault(("hyphen", b.hyphenated),
                               Item(kind="hyphen", key=b.hyphenated, why=b.reason))
        it.lines.append(b.line)

    for f in getattr(doc, "footnotes", []) or []:
        if f.paired:
            continue
        line = f.marker_line or f.body_start
        key = f"[{f.label}]"
        it = by_key.setdefault(("footnote", key),
                               Item(kind="footnote", key=key, why=f.reason))
        if line:
            it.lines.append(line)

    return sorted(by_key.values(), key=lambda i: (i.kind, i.key))


def apply_to_breaks(breaks: list, decisions: dict[tuple[str, str], str]) -> int:
    """Apply decisions to hyphen breaks. Returns how many were answered.

    An answer supplies the confidence the rule lacked; it does not introduce a
    transformation the rule could not otherwise perform.
    """
    from .dehyphenate import JOIN, KEEP

    answered = 0
    for b in breaks:
        if not b.needs_review:
            continue
        d = decisions.get(("hyphen", b.hyphenated))
        if not d:
            continue
        low = d.strip().lower()
        if low == "join":
            b.decision = JOIN
            b.reason = "joined by your decision"
        elif low == "keep":
            b.decision = KEEP
            b.reason = "hyphen kept by your decision"
        else:
            # An exact replacement. Recorded on the break so that `resolved`
            # returns it, without adding a third code path downstream.
            b.decision = JOIN
            b.joined = d.strip()
            b.reason = f"replaced with {d.strip()!r} by your decision"
        answered += 1
    return answered


def outstanding(items: list[Item],
                decisions: dict[tuple[str, str], str]) -> list[Item]:
    """The items still unanswered, which is what a second run should ask."""
    return [i for i in items if i.id() not in decisions]
