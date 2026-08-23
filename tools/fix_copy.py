#!/usr/bin/env python3
"""
fix_copy.py — remove em dashes from user-facing strings.

Docstrings and code comments are left alone; they are for developers, not
users. Only string literals that reach the screen or a generated report are
rewritten, and the replacement is chosen per case (colon, full stop, or
restructured clause) rather than substituting a comma everywhere.

Run after editing copy:  python fix_copy.py --check
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "corpusprep"

REPLACEMENTS = {
    "src/corpusprep/__main__.py": [
        ("(chapters collapsed — use --all to list every one)",
         "(chapters collapsed; use --all to list every one)"),
    ],
    "src/corpusprep/report.py": [
        ("# CorpusPrep — Preprocessing Log", "# CorpusPrep: Preprocessing Log"),
        ("uncovered line range(s)** — this is a segmenter bug: ",
         "uncovered line range(s)**. This indicates a fault in segmentation: "),
        ("f\"| {d.label} — {title[:38]} |", "f\"| {d.label}: {title[:38]} |"),
        ("{title or '—'}", "{title or '(untitled)'}"),
        ("if r.baseline else \"—\"", "if r.baseline else \"n/a\""),
    ],
    "src/corpusprep/formats.py": [
        ("numbers — the exact problems CorpusPrep cannot repair yet. ",
         "numbers, which are the exact problems CorpusPrep cannot yet repair. "),
        ("not supported — re-save as .docx.",
         "not supported. Re-save the file as .docx."),
    ],
    "src/corpusprep/variants.py": [
        ("studies where the author's preface counts as authorial text.",
         "studies in which the author's preface counts as authorial text."),
    ],
}


def user_facing_em_dashes(path: pathlib.Path) -> list[tuple[int, str]]:
    """String literals containing an em dash, excluding docstrings.

    Regex patterns that match an em dash in the source text are legitimate and
    are skipped by looking for the escape syntax that only appears in patterns.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                docs.add(ds)

    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        v = node.value
        if "—" not in v or v in docs:
            continue
        if "\\s" in v or "[:." in v or "A-Z" in v:      # regex fragment
            continue
        out.append((node.lineno, v[:76]))
    return out


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    changed = 0

    if not check_only:
        for rel, pairs in REPLACEMENTS.items():
            f = ROOT / rel
            if not f.exists():
                print(f"  missing file: {rel}")
                continue
            t = f.read_text(encoding="utf-8")
            before = t
            for a, b in pairs:
                if a not in t:
                    print(f"  not found in {rel}: {a[:56]!r}")
                t = t.replace(a, b)
            if t != before:
                f.write_text(t, encoding="utf-8")
                changed += 1

    remaining = []
    for f in sorted(PKG.glob("*.py")):
        for lineno, text in user_facing_em_dashes(f):
            remaining.append(f"  {f.name}:{lineno}  {text!r}")

    if not check_only:
        print(f"files rewritten: {changed}")
    print(f"user-facing em dashes remaining: {len(remaining)}")
    for r in remaining:
        print(r)
    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
