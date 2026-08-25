"""
measure_rules.py — precision and recall for each detection rule.

    python tools/measure_rules.py

`measure.py` scores *region labelling*: is this line front matter or body. That
is one rule of nine, and it was the only one with a published figure. The
answer keys for the others have existed since the week each rule was built and
nothing read them.

This reads them. For every rule with a key it reports precision, recall and F1
against hand-marked or generated-exact ground truth, and for every rule without
one it says so rather than leaving a blank the reader will fill in optimistically.

**Where the number comes from matters more than the number.** Each rule below
is labelled with the kind of evidence behind it:

    exact        the fixture generator recorded the answer as it wrote
    hand         marked by a person from the source, not from this tool's output
    derived      ground truth is the original file, recovered by round trip
    none         no key exists; the figure would be an assertion

A rule measured only against `exact` data has been measured against its
author's assumptions. That is enough to develop against and not enough to
publish, and the report says which is which.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

KEYS = ROOT / "tests" / "keys"
FIXTURES = ROOT / "tests" / "fixtures"


def read_lines(path: Path) -> list[int]:
    """Line numbers from a key file, one per line, `a-b` ranges expanded."""
    out: list[int] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.split("#")[0].strip()
        if not s:
            continue
        s = s.split("\t")[0].strip()
        if "-" in s:
            a, b = s.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(s))
    return out


def read_pairs(path: Path) -> dict[int, str]:
    """`line<TAB>expected` from a key file."""
    out: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.split("#")[0].strip()
        if not s or "\t" not in s:
            continue
        n, want = s.split("\t", 1)
        out[int(n)] = want.strip()
    return out


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score_set(truth: set[int], pred: set[int]) -> tuple[int, int, int]:
    return len(truth & pred), len(pred - truth), len(truth - pred)


# ---------------------------------------------------------------------------
# One function per rule. Each returns (tp, fp, fn) or None if it cannot run.
# ---------------------------------------------------------------------------

def rule_furniture():
    key, fx = KEYS / "scanned_novel.furniture", FIXTURES / "scanned_novel.txt"
    if not (key.exists() and fx.exists()):
        return None
    from corpusprep import furniture
    lines = fx.read_text(encoding="utf-8").splitlines()
    found, _, _, _ = furniture.find(lines)
    return score_set(set(read_lines(key)), set(found))


def rule_catchwords():
    key, fx = KEYS / "early_modern.catchwords", FIXTURES / "early_modern.txt"
    if not (key.exists() and fx.exists()):
        return None
    from corpusprep import furniture
    lines = fx.read_text(encoding="utf-8").splitlines()
    # The catchword matches are already computed by find(); recomputing them
    # here from a different set of page breaks would measure a pipeline the
    # package does not run.
    _, _, _, matches = furniture.find(lines)
    return score_set(set(read_lines(key)), {m.line for m in matches})


def rule_protected():
    key, fx = KEYS / "mixed_verse.protected", FIXTURES / "mixed_verse.txt"
    if not (key.exists() and fx.exists()):
        return None
    from corpusprep import protect
    lines = fx.read_text(encoding="utf-8").splitlines()
    return score_set(set(read_lines(key)),
                     set(protect.protected_lines(protect.find(lines))))


def rule_dehyphenate():
    """Not a set comparison: every break is found, the question is the answer.

    Scored as "of the breaks the tool decided, how many did it decide
    correctly", with the undecided ones counted separately — because a rule
    that refuses to guess is not wrong, it is silent, and averaging the two
    together hides the distinction this package is built on.
    """
    key, fx = KEYS / "hyphenated.hyphens", FIXTURES / "hyphenated.txt"
    if not (key.exists() and fx.exists()):
        return None
    from corpusprep import dehyphenate as dh
    lines = fx.read_text(encoding="utf-8").splitlines()
    want = read_pairs(key)
    breaks = {b.line: b for b in dh.find(lines)}
    right = wrong = silent = missing = 0
    for line, expected in want.items():
        b = breaks.get(line)
        if b is None:
            missing += 1
        elif b.needs_review:
            silent += 1
        elif b.resolved.lower() == expected.lower():
            right += 1
        else:
            wrong += 1
    return ("decided", right, wrong, silent, missing)


RULES = [
    ("Region labelling",      "hand",    None,
     "scored by tools/measure.py: 99.99% over 7,654 lines"),
    ("Page furniture",        "exact",   rule_furniture, ""),
    ("Catchwords",            "exact",   rule_catchwords, ""),
    ("Protected spans",       "exact",   rule_protected, ""),
    ("De-hyphenation",        "exact",   rule_dehyphenate, ""),
    ("Paragraph reflow",      "derived", None,
     "round trip against Jane Eyre: 99.5% of paragraphs recovered exactly"),
    ("Chapter segmentation",  "hand",    None,
     "whole books in tools/integration.py: 5 of 6 exact"),
    ("Footnotes",             "none",    None,
     "real data in The Prince and Romeo and Juliet, no key file written"),
    ("Digitisation apparatus", "none",   None,
     "verbatim boilerplate; matching is exact, so precision is not the question"),
    ("Chapter recovery from heads", "hand", None,
     "Oz 18 of 24, Treasure Island 33 of 34; two scans is not a sample"),
]


def main() -> int:
    print("=" * 74)
    print(f"{'rule':32s} {'evidence':9s} {'prec':>7s} {'recall':>7s} {'F1':>7s}")
    print("-" * 74)

    notes = []
    for name, kind, fn, note in RULES:
        if fn is None:
            print(f"{name:32s} {kind:9s} {'—':>7s} {'—':>7s} {'—':>7s}")
            notes.append((name, note))
            continue
        got = fn()
        if got is None:
            print(f"{name:32s} {kind:9s} {'skip':>7s} {'skip':>7s} {'skip':>7s}")
            notes.append((name, "fixture or key not present"))
            continue
        if got[0] == "decided":
            _, right, wrong, silent, missing = got
            total = right + wrong
            acc = 100.0 * right / total if total else 0.0
            print(f"{name:32s} {kind:9s} {acc:6.1f}% {'n/a':>7s} {'n/a':>7s}")
            notes.append((name, f"{right} correct of {total} decided; "
                                f"{silent} left to the reader, {missing} not found"))
            continue
        tp, fp, fn_ = got
        p, r, f = prf(tp, fp, fn_)
        print(f"{name:32s} {kind:9s} {100*p:6.1f}% {100*r:6.1f}% {100*f:6.1f}%")
        if fp or fn_:
            notes.append((name, f"{fp} false positive(s), {fn_} missed"))

    print("=" * 74)
    for name, note in notes:
        if note:
            print(f"  {name}: {note}")

    print("""
  exact    the fixture generator recorded the answer as it wrote it
  hand     marked by a person from the source, not from this tool's output
  derived  ground truth is the original file, recovered by round trip
  none     no key exists; a figure here would be an assertion

  A rule measured only against `exact` data has been measured against its
  author's assumptions. Enough to develop against, not enough to publish.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
