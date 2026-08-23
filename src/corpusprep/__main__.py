"""
Command-line interface.

    python -m corpusprep inspect FILE
    python -m corpusprep clean   FILE [--out DIR] [--variants a,b,c]
    python -m corpusprep clean   FILE --keep body,front_matter --name mine
    python -m corpusprep list-variants
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .document import count_tokens_types
from .importer import load
from .report import write as write_log
from .segment import segment
from .variants import BUILTIN, DEFAULT_SET, custom_variant, render, render_all


def _fmt(n: int) -> str:
    return f"{n:,}"


def cmd_inspect(args) -> int:
    doc = segment(load(args.file))
    s = doc.stats()

    print(f"\nSource      : {doc.source_path.name}")
    print(f"Encoding    : {doc.encoding} "
          f"(confidence {doc.meta.get('encoding_confidence', 0):.1f})"
          f"{'  [BOM stripped]' if doc.had_bom else ''}")
    print(f"Line endings: {doc.newline!r}")
    print(f"Size        : {_fmt(s['characters'])} chars, {_fmt(s['lines'])} lines, "
          f"{_fmt(s['word_tokens'])} tokens, {_fmt(s['word_types'])} types")

    for n in doc.notes:
        print(f"  ! {n}")

    print(f"\nRegions ({len(doc.regions)}):\n")
    print(f"  {'#':>3}  {'LABEL':<13} {'KIND':<18} {'LINES':>13} {'WORDS':>9}  TITLE")
    print("  " + "-" * 88)

    shown = 0
    for i, r in enumerate(doc.regions, 1):
        tokens, _ = count_tokens_types(doc.region_text(r))
        # Collapse long runs of chapters unless --all
        if r.kind == "chapter" and not args.all and 3 < i < len(doc.regions) - 1:
            shown += 1
            if shown == 1:
                print(f"  {'...':>3}  (chapters collapsed; use --all to list every one)")
            continue
        indent = "  " * (r.level - 1)
        # A parent's own span holds only its heading, so show the subtree total.
        kids = doc.children(i - 1)
        shown = doc.subtree_words(i - 1) if kids else tokens
        marker = "+" if kids else " "
        title = indent + (r.title[:34 - len(indent)] + "…"
                          if len(r.title) > 34 - len(indent) else r.title)
        print(f"  {i:>3}  {r.label:<13} {r.kind[:18]:<18} "
              f"{str(r.start + 1) + '-' + str(r.end):>13} "
              f"{marker}{_fmt(shown):>8}  {title}")

    counts: dict[str, int] = {}
    words: dict[str, int] = {}
    for r in doc.regions:
        counts[r.label] = counts.get(r.label, 0) + 1
        t, _ = count_tokens_types(doc.region_text(r))
        words[r.label] = words.get(r.label, 0) + t

    print("\nSummary by label:\n")
    for label in ["pg_header", "front_matter", "body", "back_matter", "pg_licence", "unknown"]:
        if label in counts:
            print(f"  {label:<14} {counts[label]:>3} region(s)  "
                  f"{_fmt(words[label]):>10} words")

    gaps = doc.coverage_gaps()
    print()
    if gaps:
        print(f"  !! {len(gaps)} uncovered line range(s): {gaps[:5]}")
    else:
        print("  OK: every line is covered by exactly one region.")
    print()
    return 0


def cmd_clean(args) -> int:
    doc = segment(load(args.file))
    out_dir = Path(args.out)
    stem = Path(args.file).stem

    if args.keep:
        labels = [x.strip() for x in args.keep.split(",") if x.strip()]
        try:
            v = custom_variant(args.name or "custom", labels,
                               drop_headings=args.drop_headings)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        results = [render(doc, v)]
        base = render(doc, BUILTIN["verbatim"])
        results[0].baseline = base.stats
    else:
        names = [x.strip() for x in args.variants.split(",") if x.strip()]
        bad = [n for n in names if n not in BUILTIN]
        if bad:
            print(f"error: unknown variant(s): {', '.join(bad)}", file=sys.stderr)
            print(f"       available: {', '.join(BUILTIN)}", file=sys.stderr)
            return 2
        results = render_all(doc, names)

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nSource: {doc.source_path.name}  "
          f"({_fmt(doc.stats()['word_tokens'])} tokens)\n")

    for r in results:
        path = out_dir / f"{stem}__{r.variant.name}.txt"
        path.write_text(r.text, encoding="utf-8")
        s = r.stats
        delta = ""
        if r.baseline and r.baseline["word_tokens"]:
            d = s["word_tokens"] - r.baseline["word_tokens"]
            delta = f"  ({100.0 * d / r.baseline['word_tokens']:+.1f}% tokens)"
        print(f"  {path.name:<44} {_fmt(s['word_tokens']):>9} tokens"
              f"  {_fmt(s['word_types']):>8} types{delta}")

    md, js = write_log(doc, results, out_dir, stem)
    print(f"\n  Log: {md.name}")
    print(f"       {js.name}\n")
    return 0


def cmd_list(args) -> int:
    print()
    for name, v in BUILTIN.items():
        kept = ", ".join(k for k, ok in v.keep.items() if ok)
        print(f"  {name}")
        print(f"      {v.description}")
        print(f"      keeps: {kept}")
        print()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="corpusprep",
        description="Corpus preparation: segment, select, clean, log.",
    )
    p.add_argument("--version", action="version", version=f"corpusprep {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("inspect", help="show how a file segments, change nothing")
    pi.add_argument("file")
    pi.add_argument("--all", action="store_true", help="list every chapter")
    pi.set_defaults(func=cmd_inspect)

    pc = sub.add_parser("clean", help="write cleaned variants and a log")
    pc.add_argument("file")
    pc.add_argument("--out", default="cleaned", help="output directory")
    pc.add_argument("--variants", default=",".join(DEFAULT_SET),
                    help="comma-separated built-in variant names")
    pc.add_argument("--keep", help="custom: comma-separated labels to retain")
    pc.add_argument("--name", help="name for the custom variant")
    pc.add_argument("--drop-headings", action="store_true",
                    help="also strip CHAPTER heading lines")
    pc.set_defaults(func=cmd_clean)

    pl = sub.add_parser("list-variants", help="describe the built-in variants")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
