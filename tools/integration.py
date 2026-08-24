"""
integration.py — run the whole pipeline over every real text and report.

    python tools/integration.py

Week 12's instruction was to run the complete pipeline across fifteen varied
texts and log everything that breaks. This is the runner for that, kept rather
than thrown away, because the value of an integration pass is in repeating it.

It asserts almost nothing. The unit tests and the measurement harness are where
claims live; this exists to make failures *visible* across the whole corpus at
once, including the ones nobody thought to write a test for. Several of the
faults in `design/integration-failures.md` were found by reading this table and
noticing a number that looked wrong, not by any check failing.

The one thing it does enforce is the invariant that must never break: every
content line belongs to exactly one region, and the body must not lose text
that the source contained.
"""

from __future__ import annotations

import statistics
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from corpusprep import analyse                                     # noqa: E402
from corpusprep.furniture import (find_head_chapters,              # noqa: E402
                                  find_prefix_furniture, is_page_per_line)
from corpusprep.variants import BUILTIN, render                    # noqa: E402

#: The real books. Synthetic fixtures are excluded on purpose: they were
#: written by the same person as the rules, so they cannot surprise anyone.
TEXTS = [
    "CBronte_Jane.txt",
    "romeo_juliet.txt",
    "romeo_juliet_notes.txt",
    "pg9405_ballads.txt",
    "pg1232_prince.txt",
    "pg921-images-3.epub",
    "mary-shelley_frankenstein.epub",
    "h-rider-haggard_king-solomons-mines.epub",
    "jane-austen_emma_advanced.epub",
    "newwizardoz00densgoog.epub",
    "treasureisland0000unse_k0j8.epub",
]

#: Chapter counts taken from the works themselves, not from any output of this
#: package. Where a book's structure is not a simple chapter list the entry is
#: None and the count is reported without judgement.
EXPECTED_CHAPTERS = {
    "mary-shelley_frankenstein.epub": 24,
    "h-rider-haggard_king-solomons-mines.epub": 20,
    "jane-austen_emma_advanced.epub": 55,
    "newwizardoz00densgoog.epub": 24,
    "treasureisland0000unse_k0j8.epub": 34,
    "CBronte_Jane.txt": 38,
}


def main() -> int:
    fx = ROOT / "tests" / "fixtures"
    rows, problems = [], []

    for name in TEXTS:
        path = fx / name
        if not path.exists():
            problems.append(f"{name}: not present")
            continue
        t0 = time.time()
        try:
            doc = analyse(path)
        except Exception:
            problems.append(f"{name}: LOAD FAILED\n" + traceback.format_exc())
            continue

        body = [r for r in doc.regions if r.label == "body"]
        named = [r for r in body if "continued" not in r.title]
        lens = [len(l.strip()) for l in doc.lines if l.strip()]

        try:
            verb = render(doc, BUILTIN["verbatim"])
            bod = render(doc, BUILTIN["body-only"])
        except Exception:
            problems.append(f"{name}: RENDER FAILED\n" + traceback.format_exc())
            continue

        # The invariant. Anything else here is a judgement; this is not.
        #
        # Use the Document's own check rather than a fresh one. The first
        # version here compared adjacent regions after sorting, which reports
        # a gap for every nested region a book has — ten minutes lost to a
        # runner that was wrong about a rule the package gets right.
        gaps = doc.coverage_gaps()
        if gaps:
            problems.append(f"{name}: {len(gaps)} gaps in the region cover")

        vt = verb.stats["word_tokens"]
        bt = bod.stats["word_tokens"]
        want = EXPECTED_CHAPTERS.get(name)
        rows.append(dict(
            name=name, secs=time.time() - t0, lines=len(doc.lines),
            median=statistics.median(lens) if lens else 0,
            ppl=is_page_per_line(doc.lines),
            prefix=len(find_prefix_furniture(doc.lines)),
            heads=len(find_head_chapters(doc.lines)),
            regions=len(doc.regions), chapters=len(named), want=want,
            evidence=(body[0].evidence if body else "-"),
            verb=vt, body=bt, kept=(100.0 * bt / vt if vt else 0.0),
        ))

    print("=" * 108)
    print(f"{'text':42s} {'lines':>6s} {'med':>5s} {'ppl':>4s} {'pfx':>5s} "
          f"{'chap':>9s} {'tokens':>9s} {'body %':>7s}  evidence")
    print("-" * 108)
    for r in rows:
        ch = f"{r['chapters']}"
        if r["want"]:
            ch += f"/{r['want']}"
        flag = "" if (not r["want"] or r["chapters"] == r["want"]) else " <"
        print(f"{r['name'][:42]:42s} {r['lines']:6d} {r['median']:5.0f} "
              f"{'yes' if r['ppl'] else '.':>4s} {r['prefix']:5d} {ch:>9s} "
              f"{r['verb']:9,d} {r['kept']:6.1f}%  {r['evidence'][:26]}{flag}")
    print("=" * 108)

    ok = sum(1 for r in rows if r["want"] and r["chapters"] == r["want"])
    known = sum(1 for r in rows if r["want"])
    print(f"  {len(rows)} texts, {ok} of {known} with a known chapter count "
          f"segmented exactly")
    for p in problems:
        print("\n  PROBLEM  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
