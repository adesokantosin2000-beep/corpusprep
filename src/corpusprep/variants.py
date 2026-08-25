"""
corpusprep.variants
===================

Build multiple cleaned versions from one segmented source.

A Variant is a named selection of regions plus a set of normalisation
options. Producing several at once is the point: it lets you check whether a
cleaning decision actually affects your results, instead of assuming it
doesn't. ``verbatim`` in particular is the control — same encoding and line
endings as the others, but nothing removed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .document import (
    BACK_MATTER,
    BODY,
    DEFAULT_KEEP,
    FRONT_MATTER,
    PG_HEADER,
    PG_LICENCE,
    UNKNOWN,
    Document,
    Region,
    count_tokens_types,
)


#: The cleaning stages, in the only order that works.
#:
#: **This is a dependency list, not a preference.** Each stage consumes
#: evidence the next one no longer has, so a wrong order does not merely
#: produce different output — it produces quietly worse output, with no error.
#:
#: The order shipped in the Week 9 commit was wrong. Reflow ran before
#: de-hyphenation, dissolved the line breaks de-hyphenation exists to repair,
#: and recovered 81 of 166 broken words instead of 162. Nothing failed. The
#: comment saying "must run before" was already in the file.
#:
#: So the order is now asserted rather than commented: `STAGE_ORDER` is
#: checked against the source of both engines, and against the measured
#: difference the wrong order makes. See `test_stage_order_is_enforced`.
STAGE_ORDER = (
    ("regions",     "select and remove whole sections"),
    ("furniture",   "strip running heads welded to the front of a line, "
                    "because they sit at a line boundary reflow will dissolve"),
    ("dehyphenate", "repair words broken across a line break, while the "
                    "breaks still exist"),
    ("reflow",      "rejoin paragraphs, removing those breaks"),
    ("whitespace",  "normalise blank lines last, on finished text"),
)


@dataclass
class Variant:
    """A named cleaning configuration."""

    name: str
    description: str
    keep: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_KEEP))
    # Normalisation options
    strip_trailing_space: bool = True
    collapse_blank_lines: bool = True
    max_blank_lines: int = 1
    collapse_inner_space: bool = False   # Off: destroys verse indentation
    drop_headings: bool = False          # Remove CHAPTER lines themselves
    # Remove detected running heads and page numbers.
    #
    # Off by default in every built-in variant, including the aggressive ones.
    # The detector has so far been measured only against synthetic text, and a
    # rule that has never met a real scan must not delete prose on its own
    # authority. Turning this on is a decision the user makes and the log
    # records. It becomes a candidate for a default once measured against real
    # OCR output.
    drop_furniture: bool = False
    # What to do with footnotes: "retain", "remove" or "extract".
    #
    # Page furniture is an artefact of printing and nobody wants it. A footnote
    # is editorial content, and whether it belongs in the corpus depends on the
    # research question, so removal is not the obvious default. It stays
    # "retain" until the researcher says otherwise.
    footnotes: str = "retain"
    # Rejoin words broken across a line break.
    #
    # Off by default like every other repair. The break itself is always an
    # artefact, but whether the hyphen survives is a judgement, and on a short
    # text the evidence is often absent. Cases the rule cannot decide are
    # flagged rather than guessed.
    dehyphenate: bool = False
    # Rejoin paragraphs a typesetter broke into fixed-width lines.
    #
    # Off by default, and more emphatically than the others. Reflow is the one
    # stage the original assessment said cannot be solved completely, it is
    # measured at 96.2% rather than 100%, and its known faults are listed in
    # design/reflow-failures.md. It is offered, not recommended.
    reflow: bool = False

    def keeps(self, label: str) -> bool:
        return self.keep.get(label, True)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "keep": self.keep,
            "options": {
                "strip_trailing_space": self.strip_trailing_space,
                "collapse_blank_lines": self.collapse_blank_lines,
                "max_blank_lines": self.max_blank_lines,
                "collapse_inner_space": self.collapse_inner_space,
                "drop_headings": self.drop_headings,
                "drop_furniture": self.drop_furniture,
                "footnotes": self.footnotes,
                "dehyphenate": self.dehyphenate,
                "reflow": self.reflow,
            },
        }


# ---------------------------------------------------------------------------
# Built-in variants
# ---------------------------------------------------------------------------

def _keep(**over) -> dict[str, bool]:
    d = dict(DEFAULT_KEEP)
    d.update(over)
    return d


BUILTIN: dict[str, Variant] = {
    "verbatim": Variant(
        name="verbatim",
        description=(
            "Control version. Encoding and line endings normalised; nothing "
            "removed. Use as the baseline to measure every other variant against."
        ),
        keep=_keep(pg_header=True, pg_licence=True),
        collapse_blank_lines=False,
    ),
    "full": Variant(
        name="full",
        description=(
            "Everything except Project Gutenberg apparatus. Front matter and "
            "back matter retained."
        ),
        keep=_keep(),
    ),
    "body-and-front": Variant(
        name="body-and-front",
        description=(
            "Front matter plus body, no back matter, no PG apparatus. For "
            "studies in which the author's preface counts as authorial text."
        ),
        keep=_keep(back_matter=False),
    ),
    "body-only": Variant(
        name="body-only",
        description=(
            "The work itself. Front matter, back matter and PG apparatus all "
            "removed. The usual choice for stylistic analysis."
        ),
        keep=_keep(front_matter=False, back_matter=False),
    ),
    "body-no-headings": Variant(
        name="body-no-headings",
        description=(
            "Body only, with CHAPTER heading lines also stripped. For word "
            "lists and frequency counts where headings would skew the data."
        ),
        keep=_keep(front_matter=False, back_matter=False),
        drop_headings=True,
    ),
}

DEFAULT_SET = ["verbatim", "full", "body-only", "body-no-headings"]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_TRAILING = re.compile(r"[ \t]+$")
_INNER = re.compile(r"[ \t]{2,}")


@dataclass
class VariantResult:
    variant: Variant
    text: str
    kept: list[Region]
    dropped: list[Region]
    stats: dict
    baseline: dict | None = None
    #: Populated only by the "extract" route: the notes, as a parallel file.
    footnote_text: str | None = None

    @property
    def dropped_lines(self) -> int:
        return sum(r.n_lines for r in self.dropped)


def render(doc: Document, variant: Variant) -> VariantResult:
    """Produce the cleaned text for one variant."""
    from .footnotes import strip_markers
    from .segment import is_chapter_heading

    kept: list[Region] = []
    dropped: list[Region] = []
    out: list[str] = []
    # STAGE regions
    furniture_removed = 0

    # Only labels that were successfully paired may be stripped. An unpaired
    # marker is the case where the tool does not know what it is looking at,
    # and no route touches it.
    handle_notes = variant.footnotes in ("remove", "extract")
    paired = [f for f in doc.footnotes if f.paired] if handle_notes else []
    note_labels = {f.label for f in paired}
    note_lines = {n for f in paired for n in f.body_lines}
    extracted: list[str] = []
    notes_removed = 0

    for region in doc.regions:
        if not variant.keeps(region.label):
            dropped.append(region)
            continue
        kept.append(region)

        for offset, line in enumerate(doc.lines[region.start:region.end]):
            # `start` is a 0-based index; furniture is recorded 1-based.
            line_no = region.start + offset + 1
            if variant.drop_furniture and doc.is_furniture(line_no):
                furniture_removed += 1
                continue
            if line_no in note_lines:
                notes_removed += 1
                continue
            if handle_notes and note_labels:
                stripped = strip_markers(line, note_labels)
                if stripped != line:
                    notes_removed += 0  # markers are counted per note, below
                line = stripped
            if variant.drop_headings and is_chapter_heading(line):
                continue
            if variant.strip_trailing_space:
                line = _TRAILING.sub("", line)
            if variant.collapse_inner_space:
                line = _INNER.sub(" ", line)
            out.append(line)

        out.append("")  # Blank line between regions

    # Running heads welded to the front of a line are removed here, before
    # de-hyphenation and reflow, because they sit at a line boundary that
    # reflow is about to dissolve.
    # STAGE furniture
    prefix_heads = 0
    if variant.drop_furniture and doc.prefix_furniture:
        from .furniture import apply_prefix_edits, PrefixEdit
        keep = {i + 1 for i, _ in enumerate(out)}
        # The edits are indexed against the document, not against the kept
        # regions, so they are re-found on the output rather than mapped.
        from .furniture import find_prefix_furniture as _fpf
        edits = _fpf(out)
        prefix_heads = len(edits)
        out = apply_prefix_edits(out, edits)

    # ---- stage order is not arbitrary ----------------------------------
    #
    # De-hyphenation MUST run before reflow.
    #
    # De-hyphenation works on words broken across a line break, and reflow
    # removes exactly those breaks. Run the other way round, reflow joins the
    # fragments first and de-hyphenation finds nothing left to repair: on the
    # hyphenated fixture it saw 0 of 180 breaks and recovered 81 of 166 words,
    # against 162 in the right order.
    #
    # The dependency is enforced here, in the code, rather than described in
    # documentation that a later edit can quietly contradict.

    # STAGE dehyphenate
    hyphen_joined = 0
    hyphen_flagged = 0
    if variant.dehyphenate:
        from . import dehyphenate as _dh
        # Evidence comes from the text being produced, and NOT from
        # `doc.lines`.
        #
        # Passing the document's own vocabulary here looks like it supplies
        # more evidence and in fact destroys it. The document contains the
        # broken fragments, so every fragment is counted twice while
        # `attested()` discounts it once: `inite` becomes a real word and the
        # break reads as a compound. It turned 171 joins into 84.
        #
        # `extra_vocab` is for a wordlist from OUTSIDE the document. A word
        # attested only in a region the reader chose to delete is not part of
        # the corpus being produced anyway.
        breaks = _dh.find(out)
        if doc.decisions:
            from . import review as _rv
            _rv.apply_to_breaks(breaks, doc.decisions)
        hyphen_joined = sum(1 for b in breaks if not b.needs_review)
        hyphen_flagged = sum(1 for b in breaks if b.needs_review)
        out = _dh.apply(out, breaks)

    # STAGE reflow
    paragraphs_joined = 0
    if variant.reflow:
        from . import protect as _pt, reflow as _rf
        # Protected spans are recomputed on the output rather than mapped
        # forward from the document: verse that survived region selection is
        # still verse, and its line numbers have moved.
        prot = _pt.protected_lines(_pt.find(out))
        r = _rf.reflow(out, prot)
        paragraphs_joined = r.blocks_joined
        out = r.lines

    text = "\n".join(out)

    # STAGE whitespace
    if variant.collapse_blank_lines:
        pattern = r"\n{%d,}" % (variant.max_blank_lines + 2)
        text = re.sub(pattern, "\n" * (variant.max_blank_lines + 1), text)

    text = text.strip() + "\n"

    tokens, types = count_tokens_types(text)
    stats = {
        "characters": len(text),
        "lines": text.count("\n"),
        "word_tokens": tokens,
        "word_types": types,
        "regions_kept": len(kept),
        "regions_dropped": len(dropped),
        "furniture_removed": furniture_removed,
        "running_heads_stripped": prefix_heads,
        "footnotes_removed": len(paired),
        "footnote_lines_removed": notes_removed,
        "hyphens_joined": hyphen_joined,
        "hyphens_flagged": hyphen_flagged,
        "paragraphs_joined": paragraphs_joined,
    }

    if variant.footnotes == "extract":
        # A parallel file, and a usable object in its own right: a corpus of
        # one editor's annotations, separated from the work it annotates.
        extracted = [f"[{f.label}]\t{f.text}" for f in paired]

    return VariantResult(
        variant=variant, text=text, kept=kept, dropped=dropped, stats=stats,
        footnote_text=("\n".join(extracted) + "\n") if extracted else None,
    )


def render_all(doc: Document, names: list[str]) -> list[VariantResult]:
    results = [render(doc, BUILTIN[n]) for n in names if n in BUILTIN]
    # Attach the verbatim baseline so every variant can report its delta.
    base = next((r for r in results if r.variant.name == "verbatim"), None)
    if base:
        for r in results:
            r.baseline = base.stats
    return results


def custom_variant(name: str, keep_labels: list[str], **options) -> Variant:
    """Build a variant from an explicit list of labels to keep."""
    valid = {PG_HEADER, PG_LICENCE, FRONT_MATTER, BODY, BACK_MATTER, UNKNOWN}
    unknown = set(keep_labels) - valid
    if unknown:
        raise ValueError(
            f"Unknown region label(s): {', '.join(sorted(unknown))}. "
            f"Valid labels: {', '.join(sorted(valid))}"
        )
    keep = {label: (label in keep_labels) for label in valid}
    return Variant(
        name=name,
        description=f"Custom selection: {', '.join(sorted(keep_labels))}",
        keep=keep,
        **options,
    )
