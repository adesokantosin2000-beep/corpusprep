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

    @property
    def dropped_lines(self) -> int:
        return sum(r.n_lines for r in self.dropped)


def render(doc: Document, variant: Variant) -> VariantResult:
    """Produce the cleaned text for one variant."""
    from .segment import is_chapter_heading

    kept: list[Region] = []
    dropped: list[Region] = []
    out: list[str] = []
    furniture_removed = 0

    for region in doc.regions:
        if not variant.keeps(region.label):
            dropped.append(region)
            continue
        kept.append(region)

        for offset, line in enumerate(doc.lines[region.start:region.end]):
            # `start` is a 0-based index; furniture is recorded 1-based.
            if variant.drop_furniture and doc.is_furniture(region.start + offset + 1):
                furniture_removed += 1
                continue
            if variant.drop_headings and is_chapter_heading(line):
                continue
            if variant.strip_trailing_space:
                line = _TRAILING.sub("", line)
            if variant.collapse_inner_space:
                line = _INNER.sub(" ", line)
            out.append(line)

        out.append("")  # Blank line between regions

    text = "\n".join(out)

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
    }

    return VariantResult(
        variant=variant, text=text, kept=kept, dropped=dropped, stats=stats
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
