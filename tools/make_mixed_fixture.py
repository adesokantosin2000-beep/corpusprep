#!/usr/bin/env python3
"""
make_mixed_fixture.py — real prose, hard-wrapped, with real verse embedded.

    python tools/make_mixed_fixture.py

Writes `tests/fixtures/mixed_verse.txt` and `tests/keys/mixed_verse.protected`.

**Both halves are real text.** The prose is *Jane Eyre*, hard-wrapped to 66
columns as a typesetter would. The verse is lifted intact from the ballad
collection, stanza breaks and indentation preserved.

A fixture of pure verse and a fixture of pure prose would both pass a detector
that simply guessed the same answer for every line. **The boundary is the only
difficult part**, so this fixture is nothing but boundaries: prose, then verse,
then prose again, five times over.

Ground truth is exact, because the generator records which lines it copied from
the ballad.

Deterministic: a fixed seed, so the fixture and its key never drift.
"""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROSE_SRC = ROOT / "tests" / "fixtures" / "CBronte_Jane.txt"
VERSE_SRC = ROOT / "tests" / "fixtures" / "pg9405_ballads.txt"
OUT = ROOT / "tests" / "fixtures" / "mixed_verse.txt"
KEY = ROOT / "tests" / "keys" / "mixed_verse.protected"

SEED = 1847
WIDTH = 66
BLOCKS = 5             # verse passages to embed
STANZAS = 6            # lines of verse per passage, roughly
PROSE_PARAS = 4        # paragraphs of prose between passages


def main() -> int:
    for p in (PROSE_SRC, VERSE_SRC):
        if not p.exists():
            print(f"source not found: {p}")
            return 1

    rng = random.Random(SEED)

    paras = [p.strip() for p in PROSE_SRC.read_text(encoding="utf-8").split("\n")
             if len(p.strip()) > 200]
    verse_all = VERSE_SRC.read_text(encoding="utf-8").split("\n")

    # Take runs of genuine verse: indented lines, blank lines kept, so the
    # stanza shape survives exactly as printed.
    runs: list[list[str]] = []
    cur: list[str] = []
    for ln in verse_all:
        if ln.startswith("     ") and ln.strip():
            cur.append(ln)
        elif cur:
            if len(cur) >= STANZAS:
                runs.append(cur[:STANZAS * 2])
            cur = []
    rng.shuffle(runs)

    lines: list[str] = []
    protected: list[int] = []
    pi = 0

    for block in range(BLOCKS):
        for _ in range(PROSE_PARAS):
            if pi >= len(paras):
                break
            for w in textwrap.wrap(paras[pi], WIDTH):
                lines.append(w)
            lines.append("")
            pi += 1

        if block < len(runs):
            lines.append("")
            for ln in runs[block]:
                lines.append(ln)
                protected.append(len(lines))
            lines.append("")

    # A final stretch of prose, so the last block is not an edge case.
    for _ in range(PROSE_PARAS):
        if pi >= len(paras):
            break
        for w in textwrap.wrap(paras[pi], WIDTH):
            lines.append(w)
        lines.append("")
        pi += 1

    text = "\n".join(lines).rstrip("\n") + "\n"
    OUT.write_text(text, encoding="utf-8")

    total = len(text.rstrip("\n").split("\n"))
    runs_out, start, prev = [], None, None
    for n in protected:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            runs_out.append((start, prev))
            start = prev = n
    if start is not None:
        runs_out.append((start, prev))

    KEY.write_text(f"""# Protected-span key: mixed_verse.txt
#
# Line numbers of verse embedded in hard-wrapped prose. Exact by construction.
#
# Prose: CBronte_Jane.txt, wrapped to {WIDTH} columns.
# Verse: pg9405_ballads.txt, copied intact.
# Both are real text; only the arrangement is invented.
#
# {len(protected)} protected lines in {len(runs_out)} passages, out of {total}.
#
# The point of this fixture is the BOUNDARY. A detector that answered the same
# for every line would score well on pure verse or pure prose and fail here.

""" + "".join(f"{a}-{b}\n" if a != b else f"{a}\n" for a, b in runs_out),
                    encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}  ({total:,} lines)")
    print(f"wrote {KEY.relative_to(ROOT)}")
    print(f"  {len(protected)} verse lines in {len(runs_out)} passages")
    print(f"  {total - len(protected)} lines of wrapped prose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
