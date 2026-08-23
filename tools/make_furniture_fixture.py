#!/usr/bin/env python3
"""
make_furniture_fixture.py — generate a synthetic page-imaged text.

    python tools/make_furniture_fixture.py

Writes `tests/fixtures/scanned_novel.txt` and its answer keys.

**This fixture is synthetic, and that limits what it can prove.** Every
Gutenberg text in the repository has had its page furniture removed by hand
during transcription, so none of them exercise a running-head detector. This
file supplies something to develop against with exact ground truth.

It cannot validate the detector. Thresholds tuned against a generator learn
that generator's regularities, and a real scan is messier in ways no generator
anticipates. Real OCR or PDF-derived text is still required before any figure
measured here means anything outside this repository.

The generator therefore works to make the task *harder*, not easier:

- page length varies, as real pages do when paragraphs break
- running heads alternate between verso and recto
- occasional OCR corruption in heads and page numbers
- a refrain that repeats often but irregularly, which a naive
  repetition-counting rule would wrongly delete
- short dialogue lines and a line of emphatic capitals, the two shapes that
  destroyed prose in the original prototype

Deterministic: a fixed seed, so the fixture and its keys never drift.
"""

from __future__ import annotations

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "scanned_novel.txt"
KEY = ROOT / "tests" / "keys" / "scanned_novel.key"
FURN = ROOT / "tests" / "keys" / "scanned_novel.furniture"

SEED = 1847
PAGES = 30
VERSO_HEAD = "JANE EYRE"
RECTO_HEAD = "A JOURNEY BY NIGHT"

PROSE = [
    "There was no possibility of taking a walk that day, and the wind rose.",
    "She sat by the window and watched the rain come across the moor.",
    "The house was silent but for the clock in the hall below.",
    "He turned the page and read the passage over a second time.",
    "Morning came grey and slow, and brought no comfort with it.",
    "The road ran east between hedgerows heavy with the night's water.",
    "Nobody spoke of the letter again, though everybody had read it.",
    "A candle guttered on the sill and went out without ceremony.",
    "The garden had gone to seed in the months since her leaving.",
    "He counted the hours until the coach would come, and then again.",
]
DIALOGUE = [
    '"I cannot," she said.',
    '"Then do not."',
    '"You are cold."',
    '"No, sir."',
    '"Wait here."',
]
REFRAIN = "And still the rain fell."
EMPHATIC = "I READ IT AGAIN AND AGAIN."


def main() -> int:
    rng = random.Random(SEED)
    lines: list[str] = []
    furniture: list[int] = []          # 1-based line numbers

    # Front matter, no furniture on these pages, as in a real book.
    lines += ["JANE EYRE", "", "AN AUTOBIOGRAPHY", "", "BY CURRER BELL", "",
              "LONDON", "SMITH, ELDER AND CO.", "1847", ""]
    front_end = len(lines)

    lines += ["CHAPTER I", ""]
    body_start = len(lines) - 1        # 1-based line of the chapter heading

    refrain_due = rng.randint(6, 14)
    for page in range(PAGES):
        verso = page % 2 == 0

        # Running head. Occasionally corrupted, as OCR does.
        head = VERSO_HEAD if verso else RECTO_HEAD
        if rng.random() < 0.10:
            i = rng.randrange(len(head))
            head = head[:i] + rng.choice("FIRLC") + head[i + 1:]
        lines.append(head)
        furniture.append(len(lines))
        lines.append("")

        # Body of the page. Length varies, as real pages do.
        for _ in range(rng.randint(24, 30)):
            refrain_due -= 1
            if refrain_due <= 0:
                lines.append(REFRAIN)
                refrain_due = rng.randint(6, 20)
            elif rng.random() < 0.18:
                lines.append(rng.choice(DIALOGUE))
            else:
                lines.append(rng.choice(PROSE))

        if page == 7:
            lines.append(EMPHATIC)

        # Page number, occasionally misread.
        lines.append("")
        num = str(page + 1)
        if rng.random() < 0.20:
            # Corrupt a digit that is ALREADY THERE. An earlier version built
            # `l3` by prefixing a letter to `3`, which invents a digit: the
            # line then reads as 13 sitting between 2 and 4. Real OCR misreads
            # the `1` in `13`; it does not hallucinate one. The ascending-run
            # test caught this, correctly rejecting an impossible sequence, and
            # the fault was in the generator rather than the rule.
            for digit, wrong in (("1", "l"), ("0", "O"), ("5", "S"),
                                 ("8", "B"), ("2", "Z")):
                if digit in num:
                    num = num.replace(digit, wrong, 1)
                    break
            else:
                num = rng.choice([num + ".", "(" + num + ")"])
        lines.append(num)
        furniture.append(len(lines))
        lines.append("")

    text = "\n".join(lines).rstrip("\n") + "\n"
    OUT.write_text(text, encoding="utf-8")

    total = len(text.rstrip("\n").split("\n"))

    KEY.write_text(f"""# Answer key: scanned_novel.txt
#
# SYNTHETIC. Generated by tools/make_furniture_fixture.py with seed {SEED}.
# Regenerate with: python tools/make_furniture_fixture.py
#
# Region labels only. Page furniture is line-level and orthogonal to regions,
# so it lives in scanned_novel.furniture instead. See design/DECISIONS.md.
#
# Note that furniture lines sit INSIDE the body region. That is the point:
# a running head interrupts a chapter without ending it.

1-{front_end}\tfront_matter\tTitle page and imprint
{body_start}-{total}\tbody\tCHAPTER I onward, running heads included
""", encoding="utf-8")

    runs, start, prev = [], None, None
    for n in furniture:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            runs.append((start, prev))
            start = prev = n
    if start is not None:
        runs.append((start, prev))

    FURN.write_text(f"""# Furniture key: scanned_novel.txt
#
# SYNTHETIC. Line numbers of page furniture: running heads and page numbers.
# Exact by construction, since the generator records them as it writes.
#
# {len(furniture)} furniture lines across {PAGES} pages.
#
# What must NOT appear here, and is the real test:
#   - "{REFRAIN}" repeats often but irregularly. A rule counting
#     repetitions alone would delete it.
#   - "{EMPHATIC}" is emphatic prose in capitals.
#   - Short dialogue such as '"No, sir."' recurs and is very short.

""" + "".join(f"{a}-{b}\n" if a != b else f"{a}\n" for a, b in runs),
                    encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}  ({total:,} lines, {PAGES} pages)")
    print(f"wrote {KEY.relative_to(ROOT)}")
    print(f"wrote {FURN.relative_to(ROOT)}  ({len(furniture)} furniture lines)")
    print(f"\nrefrain occurrences: {text.count(REFRAIN)} (must survive)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
