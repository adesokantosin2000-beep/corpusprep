"""
pdf_triage.py — sort a folder of PDFs into the ones you can use and the ones
you cannot, before you waste an afternoon on one.

    python tools/pdf_triage.py "C:\\path\\to\\pdfs"
    python tools/pdf_triage.py ~/corpus --csv report.csv

**This turned out to be the product, not a diagnostic.** PDF support was built
on the assumption that the value was extraction. The first seven real PDFs said
otherwise: two were usable, one had a text layer containing no language, three
were images with no text layer, and one was an empty download. Five of seven
could not be extracted at all.

A researcher with a folder of scans does not primarily need text out of them.
They need to know, in seconds rather than an afternoon, **which files are worth
opening and which need OCR run on them first.**

Four outcomes, and the third is the one nobody designs for:

    text        a usable text layer
    ocr         a text layer written by OCR over page images
    unmapped    a text layer that extracts cleanly and contains no language
    image       no text layer; nothing to extract

`unmapped` is the dangerous case. Extraction succeeds, raises nothing, and
returns hundreds of lines in which every character is a placeholder code,
because the embedded fonts carry no working character map. Any check of the
form *did we get text?* answers **yes** and hands over a corpus of control
characters.

Nothing is written and nothing is modified. This only reads.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from corpusprep import pdf                                       # noqa: E402

#: What to tell the reader to do about each outcome. The classification is
#: only useful if it ends in an instruction.
ADVICE = {
    pdf.TEXT: "ready to clean",
    pdf.OCR: "ready to clean (OCR layer; expect damage)",
    pdf.UNMAPPED: "RUN OCR — the text layer is unreadable",
    pdf.IMAGE: "RUN OCR — no text layer",
}


def triage(paths: list[Path]) -> list[dict]:
    rows = []
    for p in sorted(paths):
        e = pdf.extract(p)
        words = sum(len(l.split()) for l in e.lines)
        # "Run OCR" is useless advice for a 0-byte file, and a classification
        # that ends in the wrong instruction is worse than no classification.
        advice = ADVICE.get(e.kind, "")
        if e.pages == 0:
            advice = ("nothing to read — the file is empty or not a PDF; "
                      "download it again")
        rows.append({
            "file": p.name,
            "kind": e.kind,
            "usable": e.usable,
            "pages": e.pages,
            "lines": len(e.lines),
            "letters_pct": round(100 * e.letter_ratio, 1),
            "words": words,
            "advice": advice,
            "note": e.note,
        })
    return rows


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    csv_out = None
    for i, a in enumerate(argv):
        if a == "--csv" and i + 1 < len(argv):
            csv_out = Path(argv[i + 1])

    if not args:
        print(__doc__.strip().splitlines()[2].strip())
        print("\n  Give it a folder, or one or more PDF files.")
        return 2

    paths: list[Path] = []
    for a in args:
        if a == csv_out and csv_out is not None:
            continue
        q = Path(a).expanduser()
        if q.is_dir():
            paths.extend(q.rglob("*.pdf"))
        elif q.suffix.lower() == ".pdf":
            paths.append(q)

    if not paths:
        print("No PDFs found there.")
        return 1

    if not pdf.available():
        print("PDF support needs pypdf:  pip install pypdf")
        return 1

    rows = triage(paths)

    width = min(52, max(len(r["file"]) for r in rows))
    print("=" * (width + 56))
    print(f"{'file':{width}s} {'kind':9s} {'pages':>5s} {'let%':>5s} "
          f"{'words':>8s}  what to do")
    print("-" * (width + 56))
    for r in rows:
        print(f"{r['file'][:width]:{width}s} {r['kind']:9s} {r['pages']:5d} "
              f"{r['letters_pct']:5.0f} {r['words']:8,d}  {r['advice']}")
    print("=" * (width + 56))

    n = len(rows)
    usable = sum(1 for r in rows if r["usable"])
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1

    print(f"  {n} PDFs · {usable} usable ({100 * usable / n:.0f}%) · "
          f"{n - usable} need OCR first")
    for k in (pdf.TEXT, pdf.OCR, pdf.UNMAPPED, pdf.IMAGE):
        if by_kind.get(k):
            print(f"      {by_kind[k]:4d}  {k:9s} {ADVICE[k]}")

    # The number that matters to someone deciding whether to bother.
    unmapped = by_kind.get(pdf.UNMAPPED, 0)
    if unmapped:
        print(f"\n  {unmapped} file(s) would pass a word-count check and "
              f"contain no language at all.")

    # The unusable ones are the reason this exists, so name them.
    bad = [r for r in rows if not r["usable"]]
    if bad:
        print("\n  Needing OCR before this tool can help:")
        for r in bad:
            print(f"      {r['file'][:60]}")

    if csv_out:
        with csv_out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\n  Written to {csv_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
