"""
corpusprep.document
===================

Core data structures.

Design rule: a Document is never mutated in place. Every operation returns a
new object. This makes undo free and keeps the audit trail honest.

A Document is a list of lines plus an ordered list of Regions covering those
lines. Regions are *labels*, not edits — nothing is ever deleted at detection
time. Deletion happens only when the user selects which regions to keep.

That separation is deliberate. The prototype script's worst bug was a
detection rule that deleted as a side effect; here, detection and deletion
cannot be confused because they are different steps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Region labels
# ---------------------------------------------------------------------------

PG_HEADER = "pg_header"        # Project Gutenberg header block
PG_LICENCE = "pg_licence"      # PG licence / legal text (header or footer)
FRONT_MATTER = "front_matter"  # Title, author, preface, dedication, contents
BODY = "body"                  # The actual work
BACK_MATTER = "back_matter"    # Appendix, index, notes, colophon
UNKNOWN = "unknown"

#: Default keep/drop policy. Conservative: only PG apparatus is dropped by
#: default, because it is the only category we can identify with certainty.
DEFAULT_KEEP = {
    PG_HEADER: False,
    PG_LICENCE: False,
    FRONT_MATTER: True,
    BODY: True,
    BACK_MATTER: True,
    UNKNOWN: True,
}

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)


def word_tokens(text: str) -> list[str]:
    """Tokenise into word forms. Deliberately simple and stable.

    Not a linguistic tokeniser — its job is to give comparable counts before
    and after cleaning so we can detect accidental prose loss.
    """
    return _WORD_RE.findall(text)


def count_tokens_types(text: str) -> tuple[int, int]:
    toks = word_tokens(text)
    return len(toks), len({t.lower() for t in toks})


# ---------------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Region:
    """A labelled, contiguous span of lines.

    ``start`` and ``end`` are 0-based line indices, ``end`` exclusive.

    Hierarchy note: regions stay **flat and non-overlapping** — that invariant
    is what guarantees no line is counted twice or lost. Nesting is expressed
    as metadata (``level`` and ``parent``) rather than by containment, so an
    Act's own span covers only its heading while its Scenes sit beside it as
    separate regions pointing back at it. Aggregate figures for an Act come
    from summing its descendants; see ``Document.subtree``.
    """

    label: str
    kind: str            # Finer-grained: "preface", "chapter", "title", ...
    title: str           # Human-readable heading text, or ""
    start: int
    end: int
    confidence: float = 1.0
    evidence: str = ""   # Why the segmenter labelled it this way
    level: int = 1       # 1 = top (Act, Book); 2 = nested (Scene, Chapter)
    parent: int | None = None   # Index into Document.regions, or None

    @property
    def n_lines(self) -> int:
        return self.end - self.start

    def text(self, lines: list[str]) -> str:
        return "\n".join(lines[self.start:self.end])

    def describe(self) -> str:
        t = self.title or self.kind
        indent = "  " * (self.level - 1)
        return f"{indent}[{self.label}/{self.kind}] {t} (lines {self.start + 1}-{self.end})"


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Document:
    """An imported text plus its segmentation and provenance."""

    source_path: Path
    lines: list[str]
    encoding: str = "utf-8"
    had_bom: bool = False
    newline: str = "\n"
    regions: list[Region] = field(default_factory=list)
    #: 1-based line numbers judged to be page furniture: running heads, feet
    #: and page numbers. Deliberately NOT a region. Regions are contiguous and
    #: non-overlapping, and every line belongs to exactly one; that invariant
    #: is what guarantees nothing is lost. A running head sits *inside* a
    #: chapter, every thirty-odd lines, so labelling it as a region would
    #: shatter one chapter into hundreds of fragments.
    #:
    #: Furniture is therefore orthogonal to segmentation: a line is body *and*
    #: furniture at once. See design/DECISIONS.md.
    furniture: set[int] = field(default_factory=set)
    #: Footnotes found, paired and unpaired alike. Like furniture this is a
    #: line-level property rather than a region: a marker sits inside a word
    #: inside a paragraph inside a chapter.
    footnotes: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    # -- construction -------------------------------------------------------

    def with_regions(self, regions: Iterable[Region]) -> "Document":
        return replace(self, regions=list(regions))

    def with_furniture(self, lines: Iterable[int]) -> "Document":
        return replace(self, furniture=set(lines))

    def with_footnotes(self, found: list) -> "Document":
        return replace(self, footnotes=list(found))

    def with_note(self, note: str) -> "Document":
        return replace(self, notes=[*self.notes, note])

    # -- access -------------------------------------------------------------

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def is_furniture(self, line_no: int) -> bool:
        """``line_no`` is 1-based, matching the numbering users see."""
        return line_no in self.furniture

    def region_text(self, region: Region) -> str:
        return region.text(self.lines)

    def regions_by_label(self, label: str) -> list[Region]:
        return [r for r in self.regions if r.label == label]

    def children(self, index: int) -> list[int]:
        """Indices of regions whose direct parent is ``index``."""
        return [i for i, r in enumerate(self.regions) if r.parent == index]

    def subtree(self, index: int) -> list[int]:
        """``index`` plus all its descendants, in document order."""
        out = [index]
        stack = [index]
        while stack:
            cur = stack.pop()
            for c in self.children(cur):
                out.append(c)
                stack.append(c)
        return sorted(set(out))

    def subtree_words(self, index: int) -> int:
        """Total word tokens in a region and everything nested under it.

        This is how an Act reports a meaningful size: its own span holds only
        the heading line, so the figure that matters is the sum over its Scenes.
        """
        total = 0
        for i in self.subtree(index):
            r = self.regions[i]
            total += count_tokens_types(self.region_text(r))[0]
        return total

    def has_hierarchy(self) -> bool:
        return any(r.level > 1 for r in self.regions)

    # -- statistics ---------------------------------------------------------

    def stats(self) -> dict:
        text = self.text
        tokens, types = count_tokens_types(text)
        return {
            "characters": len(text),
            "lines": len(self.lines),
            "word_tokens": tokens,
            "word_types": types,
        }

    def coverage_gaps(self) -> list[tuple[int, int]]:
        """Ranges of *content* lines not covered by any region.

        Blank lines between regions are ignored — they carry no text and are
        regenerated on output. What matters is that no line containing words
        is unaccounted for. If this is ever non-empty, the segmenter has a bug
        and text could be silently lost, so the report surfaces it loudly.
        """
        covered = [False] * len(self.lines)
        for r in self.regions:
            for i in range(r.start, min(r.end, len(covered))):
                covered[i] = True

        gaps: list[tuple[int, int]] = []
        start = None
        for i, c in enumerate(covered):
            uncovered_content = (not c) and bool(self.lines[i].strip())
            if uncovered_content and start is None:
                start = i
            elif not uncovered_content and start is not None:
                gaps.append((start, i))
                start = None
        if start is not None:
            gaps.append((start, len(covered)))
        return gaps
