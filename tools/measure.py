#!/usr/bin/env python3
"""
measure.py — score the segmenter against hand-marked answer keys.

    python tools/measure.py                 every key
    python tools/measure.py romeo_juliet    one text
    python tools/measure.py --errors        list every misclassified line
    python tools/measure.py --baseline      write tests/keys/BASELINE.md

Every stage in Phase 2 is a detector, and a detector without a measured error
rate is an opinion. This is what turns "it works" into a number.

**Scoring is per line, not per region.** A region-level score would reward
getting the count right while placing the boundaries wrong, which is precisely
the failure that matters: a boundary off by ten lines silently moves ten lines
of prose into or out of the corpus.

Lines not covered by a key are excluded rather than counted as correct. Use
that deliberately for passages you are genuinely unsure about, so that honest
uncertainty does not inflate the result.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from corpusprep import load, segment  # noqa: E402

KEYS = ROOT / "tests" / "keys"
FIXTURES = ROOT / "tests" / "fixtures"

LABELS = ["pg_header", "pg_licence", "front_matter", "body",
          "back_matter", "unknown"]

RANGE = re.compile(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s+(\S+)\s*(.*)$")


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def read_key(path: Path) -> dict[int, str]:
    """Return {line_number: label}. Later ranges override earlier ones."""
    truth: dict[int, str] = {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#")[0].strip() if not raw.lstrip().startswith("#") else ""
        if not line:
            continue
        m = RANGE.match(line)
        if not m:
            raise SystemExit(f"{path.name}:{n}: cannot parse {raw.strip()!r}")
        start, end, label = int(m.group(1)), m.group(2), m.group(3)
        end = int(end) if end else start
        if label not in LABELS:
            raise SystemExit(
                f"{path.name}:{n}: unknown label {label!r}. "
                f"Valid: {', '.join(LABELS)}"
            )
        if end < start:
            raise SystemExit(f"{path.name}:{n}: range ends before it starts")
        for i in range(start, end + 1):
            truth[i] = label
    return truth


def find_fixture(stem: str) -> Path | None:
    for p in sorted(FIXTURES.iterdir()):
        if p.stem == stem:
            return p
    return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def predicted_labels(path: Path) -> tuple[dict[int, str], list[str]]:
    doc = segment(load(path))
    pred: dict[int, str] = {}
    for r in doc.regions:
        for i in range(r.start, r.end):
            pred[i + 1] = r.label          # keys are 1-based
    return pred, doc.lines


def score(truth: dict[int, str], pred: dict[int, str], lines: list[str]):
    """Compare on content lines only. Blank lines carry no text to misplace."""
    counts = {l: {"tp": 0, "fp": 0, "fn": 0} for l in LABELS}
    errors: list[tuple[int, str, str, str]] = []
    compared = correct = 0

    for lineno, want in sorted(truth.items()):
        if lineno > len(lines) or not lines[lineno - 1].strip():
            continue
        got = pred.get(lineno, "(none)")
        compared += 1
        if got == want:
            correct += 1
            counts[want]["tp"] += 1
        else:
            counts[want]["fn"] += 1
            if got in counts:
                counts[got]["fp"] += 1
            errors.append((lineno, want, got, lines[lineno - 1][:60]))

    return counts, compared, correct, errors


def prf(c: dict[str, int]) -> tuple[float, float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else float("nan")
    return p, r, f


def pct(x: float) -> str:
    return "  n/a " if x != x else f"{100 * x:5.1f}%"


def pct_exact(x: float, errors: int) -> str:
    """Never round a figure with known errors up to a clean 100%.

    6,227 correct out of 6,228 is 99.98%, and printing "100.0%" beside
    "1 misclassified" is the kind of flattering summary this harness exists
    to prevent."""
    if x != x:
        return "n/a"
    if errors and round(100 * x, 1) >= 100.0:
        return f"{100 * x:.2f}%"
    return f"{100 * x:.1f}%"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def run(key_path: Path, show_errors: bool):
    # Parse the key first. Validating only when a matching fixture happens to
    # exist would let a malformed key sit unnoticed until the day its text is
    # added, which is the worst moment to discover it.
    truth = read_key(key_path)

    fixture = find_fixture(key_path.stem)
    if fixture is None:
        print(f"\n{key_path.name}")
        print(f"  key is valid ({len(truth):,} lines marked) but no fixture "
              f"named {key_path.stem!r} was found")
        return None

    pred, lines = predicted_labels(fixture)
    counts, compared, correct, errors = score(truth, pred, lines)

    acc = correct / compared if compared else float("nan")
    print(f"\n{fixture.name}")
    print(f"  {compared:,} content lines scored, {correct:,} correct, "
          f"accuracy {pct(acc)}")

    present = [l for l in LABELS if any(counts[l].values())]
    if present:
        print(f"\n  {'LABEL':<14} {'PREC':>7} {'RECALL':>7} {'F1':>7}   "
              f"{'TP':>5} {'FP':>4} {'FN':>4}")
        for l in present:
            p, r, f = prf(counts[l])
            c = counts[l]
            print(f"  {l:<14} {pct(p)} {pct(r)} {pct(f)}   "
                  f"{c['tp']:>5} {c['fp']:>4} {c['fn']:>4}")

    if errors:
        print(f"\n  {len(errors)} misclassified line(s)")
        shown = errors if show_errors else errors[:5]
        for lineno, want, got, text in shown:
            print(f"    line {lineno:>5}: expected {want}, got {got}")
            print(f"                 {text!r}")
        if not show_errors and len(errors) > 5:
            print(f"    ... {len(errors) - 5} more. Use --errors to list them.")

    return {"file": fixture.name, "compared": compared,
            "correct": correct, "accuracy": acc,
            "counts": counts, "errors": len(errors)}


def main(argv: list[str]) -> int:
    show_errors = "--errors" in argv
    baseline = "--baseline" in argv
    wanted = [a for a in argv[1:] if not a.startswith("--")]

    keys = sorted(KEYS.glob("*.key"))
    if wanted:
        keys = [k for k in keys if any(w in k.stem for w in wanted)]
    if not keys:
        print(f"No answer keys found in {KEYS.relative_to(ROOT)}")
        return 2

    print("Segmentation accuracy against hand-marked keys")
    print("=" * 62)

    results = [r for r in (run(k, show_errors) for k in keys) if r]

    tot_c = sum(r["compared"] for r in results)
    tot_ok = sum(r["correct"] for r in results)
    tot_err = sum(r["errors"] for r in results)
    overall = tot_ok / tot_c if tot_c else float("nan")

    print("\n" + "=" * 62)
    print(f"  {len(results)} texts, {tot_c:,} content lines, "
          f"{tot_err} misclassified, overall accuracy "
          f"{pct_exact(overall, tot_err)}")

    if baseline:
        write_baseline(results, tot_c, tot_ok, tot_err, overall)

    # A non-zero exit only under --strict. Known, documented errors should not
    # make the tool look broken every time it runs; --strict is for the day
    # this becomes a regression gate.
    if "--strict" in argv and tot_err:
        return 1
    return 0


def write_baseline(results, tot_c, tot_ok, tot_err, overall):
    from datetime import datetime
    out = KEYS / "BASELINE.md"
    L = ["# Segmentation baseline", "",
         f"Recorded {datetime.now().strftime('%d %B %Y')}, before any Phase 2 work.",
         "",
         "Measured by `python tools/measure.py` against the hand-marked keys in",
         "this folder. Scoring is per content line, so a boundary placed wrongly",
         "counts against every line it displaces.", "",
         "| Text | Lines scored | Correct | Accuracy | Errors |",
         "|---|---|---|---|---|"]
    for r in results:
        L.append(f"| `{r['file']}` | {r['compared']:,} | {r['correct']:,} | "
                 f"{pct_exact(r['accuracy'], r['errors'])} | {r['errors']} |")
    L += ["", f"**Overall: {pct_exact(overall, tot_err)} across {tot_c:,} "
              f"content lines, {tot_err} misclassified.**", "",
          "## Known errors at baseline",
          "",
          "**`pg921-images-3.epub` line 23, `DE PROFUNDIS`.** The work's title is",
          "labelled `body` rather than `front_matter`. De Profundis is a single",
          "continuous letter with no chapter divisions, so the segmenter takes its",
          "documented fallback and treats everything from the start of content as",
          "body. The title line is swept in with it.",
          "",
          "This is a limitation rather than a defect: with no structural heading to",
          "anchor on, there is nothing to separate a title from the first line of",
          "prose. A rule guessing that a short standalone opening line is a title",
          "would be plausible and is exactly the kind of speculative detector that",
          "produces false positives elsewhere. It is left unfixed deliberately, to",
          "be decided on evidence during Phase 2 rather than tuned against the",
          "first example encountered.",
          "",
          "## How to use this",
          "",
          "Every stage added in Phase 2 must be measured against these same keys.",
          "A stage that improves one text while quietly degrading another is a",
          "regression, and only a fixed baseline makes that visible.",
          "",
          "When a stage changes what a correct answer looks like, update the keys",
          "and say so here. Do not silently re-baseline: the point of the figure",
          "is that it can be compared across months."]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
