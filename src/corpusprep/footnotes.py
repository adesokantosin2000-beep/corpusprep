"""
corpusprep.footnotes
====================

Detection of footnote markers and footnote bodies.

A footnote leaves two marks on a text, and they damage a corpus differently.

The **marker** is welded to a word, so `graith'd[FN#1]` is a single token to
every downstream tool and never matches `graith'd`. The **body** is editorial
prose by a modern scholar sitting inside what is supposed to be a fifteenth
century ballad, inflating every count with the wrong century's vocabulary.

**The signal is a content relationship, not a threshold.** A marker is a
footnote marker if, and only if, something elsewhere carries the same label and
reads as a note. That pairing is verifiable, which is what separates this rule
from the running-head rule and its four tuned parameters.

The pairing requirement is also what keeps the rule away from everything else
that lives inside square brackets:

    [Exit.]  [Enter Romeo]      stage directions, part of the play
    [Illustration]  [sic]       editorial apparatus, but not notes
    [eBook #1513]               Gutenberg boilerplate

None of them has a matching body, so none of them is touched. A corpus of drama
without its stage directions is a corpus of a different work.

Nothing here deletes. Detection records pairs; removal is a later, explicit
choice between three routes, exactly as with regions and furniture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: A label is numeric, one or two letters, a roman numeral, or the `FN#1` form
#: some transcribers use. Anything longer is a word, and words are not labels:
#: this is what keeps `[Illustration]` and `[Exit.]` out of the rule entirely.
_LABEL = r"(?:\d{1,4}|[A-Za-z]{1,2}|FN#\d{1,4})"

#: A marker sits inside a line, usually welded to the word it annotates.
MARKER = re.compile(rf"\[({_LABEL})\]|\{{({_LABEL})\}}")

#: A body opens its line with the label and continues with the note itself.
BODY = re.compile(rf"^\s*[\[{{]({_LABEL})[\]}}]\s*[:.]?\s+(?P<text>\S.*)$")

#: The form Project Gutenberg uses widely, where the note is wrapped whole.
PG_BODY = re.compile(
    r"^\s*\[Footnote\s+([A-Za-z0-9#]{1,6})\s*[:.]?\s*(?P<text>.*)$",
    re.IGNORECASE)

#: Longest a body may run before the rule stops believing it is a note.
MAX_BODY_LINES = 40


def _norm(label: str) -> str:
    return label.strip().lower().lstrip("0") or "0"


@dataclass
class Footnote:
    """One marker, one body, and whether they were successfully paired."""

    label: str
    marker_line: int | None = None      # 1-based, None if the body is orphaned
    body_start: int | None = None       # 1-based
    body_end: int | None = None         # 1-based, inclusive
    text: str = ""
    paired: bool = False
    reason: str = ""

    @property
    def body_lines(self) -> list[int]:
        if self.body_start is None:
            return []
        return list(range(self.body_start, (self.body_end or self.body_start) + 1))


def find_bodies(lines: list[str], skip: set[int] | None = None
                ) -> list[tuple[int, int, str, str]]:
    """Locate footnote bodies: (start, end, label, text).

    A body runs until a blank line or the next body, whichever comes first.
    Continuation lines are part of the note and must travel with it, or
    extraction would leave half a sentence behind in the corpus.
    """
    skip = skip or set()
    out: list[tuple[int, int, str, str]] = []
    i = 0
    while i < len(lines):
        n = i + 1
        if n in skip:
            i += 1
            continue
        m = PG_BODY.match(lines[i]) or BODY.match(lines[i])
        if not m:
            i += 1
            continue
        label = _norm(m.group(1))
        text = [m.group("text").strip()]
        j = i + 1
        while (j < len(lines) and lines[j].strip()
               and not (PG_BODY.match(lines[j]) or BODY.match(lines[j]))
               and j - i < MAX_BODY_LINES):
            text.append(lines[j].strip())
            j += 1
        out.append((n, j, label, " ".join(text).strip()))
        i = j
    return out


def find_markers(lines: list[str], body_lines: set[int],
                 skip: set[int] | None = None) -> list[tuple[int, str]]:
    """Locate inline markers: (line, label).

    Lines that are themselves footnote bodies are excluded, so a body's own
    opening label is never mistaken for a marker referring to itself.
    """
    skip = set(skip or ()) | body_lines
    out: list[tuple[int, str]] = []
    for i, raw in enumerate(lines, 1):
        if i in skip or not raw.strip():
            continue
        for m in MARKER.finditer(raw):
            label = m.group(1) or m.group(2)
            # A label alone on its line is a page number or a list bullet, not
            # a marker. A marker is attached to the text it annotates.
            if raw.strip() in (f"[{label}]", f"{{{label}}}"):
                continue
            out.append((i, _norm(label)))
    return out


def pair(markers: list[tuple[int, str]],
         bodies: list[tuple[int, int, str, str]]) -> list[Footnote]:
    """Pair each body with the nearest preceding unpaired marker of its label.

    **Pairing cannot be done by label alone, and real text is what proved it.**
    In Machiavelli's *The Prince* the numbering restarts every chapter, so `[1]`
    occurs fourteen times: seven markers and seven bodies, spread across seven
    chapters. Matching globally by label would pair a marker in chapter two with
    a note belonging to chapter nine.

    Walking the document in order and consuming the most recent unclaimed marker
    resolves this without needing to know where the chapters are.
    """
    pending: dict[str, list[int]] = {}
    out: list[Footnote] = []
    events = ([("m", ln, label, None, None) for ln, label in markers]
              + [("b", s, label, e, text) for s, e, label, text in bodies])
    events.sort(key=lambda ev: (ev[1], 0 if ev[0] == "m" else 1))

    for kind, ln, label, end, text in events:
        if kind == "m":
            pending.setdefault(label, []).append(ln)
            continue
        stack = pending.get(label) or []
        fn = Footnote(label=label, body_start=ln, body_end=end, text=text)
        if stack:
            fn.marker_line = stack.pop()
            fn.paired = True
            fn.reason = (f"marker at line {fn.marker_line} is answered by this "
                         f"note {ln - fn.marker_line} lines below")
        else:
            fn.reason = "a note with no marker referring to it"
        out.append(fn)

    # Markers left over never received an answer.
    for label, stack in pending.items():
        for ln in stack:
            out.append(Footnote(label=label, marker_line=ln,
                                reason="marker with no matching note"))
    out.sort(key=lambda f: (f.marker_line or f.body_start or 0))
    return out


def find(lines: list[str], skip: set[int] | None = None) -> list[Footnote]:
    """Return every footnote found, paired and unpaired alike.

    The unpaired are returned deliberately. **An unpaired marker is exactly the
    case where the tool does not know what it is looking at**, which is
    precisely when it must not act. They are reported so the reader can judge,
    and no route removes them.
    """
    bodies = find_bodies(lines, skip)
    body_lines = {n for s, e, _, _ in bodies for n in range(s, e + 1)}
    markers = find_markers(lines, body_lines, skip)
    return pair(markers, bodies)


def find_in_document(doc) -> list[Footnote]:
    """Find footnotes in a segmented Document, ignoring Gutenberg apparatus.

    The licence block is full of bracketed references and section numbers, and
    it is not part of anybody's corpus.
    """
    skip = {
        i + 1
        for r in doc.regions
        if r.label in ("pg_header", "pg_licence")
        for i in range(r.start, r.end)
    }
    return find(doc.lines, skip)


def strip_markers(line: str, labels: set[str]) -> str:
    """Remove confirmed markers from a line, leaving the word they hung on.

    Only labels that were successfully paired are stripped. An unrecognised
    bracketed thing is left exactly where it is.
    """
    def sub(m: re.Match) -> str:
        label = _norm(m.group(1) or m.group(2))
        return "" if label in labels else m.group(0)

    return MARKER.sub(sub, line)
