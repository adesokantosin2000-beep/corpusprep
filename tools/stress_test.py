#!/usr/bin/env python3
"""
stress_test.py — throw a folder of texts at CorpusPrep and see what breaks.

Usage:
    python stress_test.py                  # tests every .txt in this folder
    python stress_test.py path/to/corpora  # or a folder you choose

Produces a traffic-light table. You are looking for AMBER and RED rows —
those are the files whose failures tell you what to build next.

    GREEN   Segmented cleanly. Body found, front matter separated,
            token loss plausible.
    AMBER   Worked, but something looks off. Inspect manually.
    RED     Failed, or the result is not usable.

Nothing is modified. This only reads.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from corpusprep import load, render_all, segment
from corpusprep.document import BACK_MATTER, BODY, FRONT_MATTER, PG_LICENCE

# Token loss above this in body-only is suspicious — but only for a text big
# enough for the ratio to mean anything. A 200-word fixture that is mostly
# licence boilerplate will legitimately "lose" 86%, so thresholds are only
# applied above MIN_TOKENS_FOR_LOSS_CHECK.
LOSS_WARN = 8.0
LOSS_FAIL = 25.0
MIN_TOKENS_FOR_LOSS_CHECK = 2000


def assess(path: Path) -> dict:
    """Run one file and return a verdict."""
    row = {"file": path.name, "status": "GREEN", "notes": []}

    try:
        doc = segment(load(path))
    except Exception as exc:  # noqa: BLE001
        row["status"] = "RED"
        row["notes"].append(f"crashed on import/segment: {exc}")
        row["traceback"] = traceback.format_exc()
        return row

    stats = doc.stats()
    row["tokens"] = stats["word_tokens"]
    row["types"] = stats["word_types"]
    row["lines"] = stats["lines"]
    row["encoding"] = doc.encoding

    labels = [r.label for r in doc.regions]
    kinds = [r.kind for r in doc.regions]
    row["chapters"] = kinds.count("chapter")
    row["regions"] = len(doc.regions)

    # --- checks -----------------------------------------------------------

    if stats["word_tokens"] == 0:
        row["status"] = "RED"
        row["notes"].append("no word tokens — file empty or unreadable")
        return row

    gaps = doc.coverage_gaps()
    if gaps:
        row["status"] = "RED"
        row["notes"].append(f"{len(gaps)} uncovered content range(s) — segmenter bug")

    if row["chapters"] == 0:
        row["status"] = "AMBER" if row["status"] == "GREEN" else row["status"]
        row["notes"].append("no chapter headings found — whole text kept as body")

    if BODY not in labels:
        row["status"] = "RED"
        row["notes"].append("no body region at all")

    if FRONT_MATTER not in labels:
        row["status"] = "AMBER" if row["status"] == "GREEN" else row["status"]
        row["notes"].append("no front matter detected (may be correct)")

    if doc.meta.get("encoding_confidence", 1.0) < 0.6:
        row["status"] = "AMBER" if row["status"] == "GREEN" else row["status"]
        row["notes"].append(f"low encoding confidence ({doc.encoding})")

    if doc.meta.get("replacement_chars"):
        row["status"] = "AMBER" if row["status"] == "GREEN" else row["status"]
        row["notes"].append(f"{doc.meta['replacement_chars']} undecodable byte(s)")

    # --- variant sanity ---------------------------------------------------

    try:
        results = {r.variant.name: r for r in
                   render_all(doc, ["verbatim", "body-only"])}
        v = results["verbatim"].stats["word_tokens"]
        b = results["body-only"].stats["word_tokens"]
        loss = 100.0 * (v - b) / v if v else 0.0
        row["loss"] = loss

        if v < MIN_TOKENS_FOR_LOSS_CHECK:
            row["notes"].append(
                f"body-only dropped {loss:.1f}% of tokens "
                f"(too small to judge — under {MIN_TOKENS_FOR_LOSS_CHECK:,} tokens)"
            )
        elif loss >= LOSS_FAIL:
            row["status"] = "RED"
            row["notes"].append(f"body-only lost {loss:.1f}% of tokens — likely eating prose")
        elif loss >= LOSS_WARN:
            row["status"] = "AMBER" if row["status"] == "GREEN" else row["status"]
            row["notes"].append(f"body-only lost {loss:.1f}% of tokens — check what went")

        # Every output line must exist in the source. Catches invented text.
        # Compared on stripped forms, because trailing-space removal is an
        # intended transformation, not invention.
        src_lines = {ln.strip() for ln in doc.lines}
        invented = [ln for ln in results["body-only"].text.splitlines()
                    if ln.strip() and ln.strip() not in src_lines]
        if invented:
            row["status"] = "RED"
            row["notes"].append(f"{len(invented)} output line(s) not in source")
            row["invented"] = invented[:3]

    except Exception as exc:  # noqa: BLE001
        row["status"] = "RED"
        row["notes"].append(f"crashed rendering variants: {exc}")
        row["traceback"] = traceback.format_exc()

    # Useful context, not a fault
    if PG_LICENCE in labels:
        row["notes"].append("licence text found and removed")
    if BACK_MATTER in labels:
        row["notes"].append("back matter found")

    return row


def main(argv: list[str]) -> int:
    folder = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    files = sorted(
        p for p in folder.glob("*.txt")
        if "__" not in p.name and not p.name.endswith("_log.md")
    )

    if not files:
        print(f"No .txt files found in {folder}")
        print("Drop some corpora in and run again.")
        return 1

    print(f"\nCorpusPrep stress test — {len(files)} file(s) in {folder}\n")
    print(f"  {'STATUS':<7} {'FILE':<34} {'TOKENS':>9} {'CHAPS':>6} {'LOSS%':>7}")
    print("  " + "-" * 72)

    rows = [assess(p) for p in files]

    for r in rows:
        loss = f"{r['loss']:.1f}" if "loss" in r else "—"
        print(f"  {r['status']:<7} {r['file'][:34]:<34} "
              f"{r.get('tokens', 0):>9,} {r.get('chapters', 0):>6} {loss:>7}")

    print()
    for r in rows:
        if r["notes"]:
            print(f"  {r['file']}")
            for n in r["notes"]:
                print(f"      - {n}")
            print()

    counts = {s: sum(1 for r in rows if r["status"] == s)
              for s in ("GREEN", "AMBER", "RED")}
    print(f"  {counts['GREEN']} green, {counts['AMBER']} amber, {counts['RED']} red\n")

    tb = [r for r in rows if "traceback" in r]
    if tb:
        print("  Tracebacks:\n")
        for r in tb:
            print(f"  --- {r['file']} ---")
            print(r["traceback"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
