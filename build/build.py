#!/usr/bin/env python3
"""
build.py — assemble docs/index.html from its three sources.

    python build/build.py            rebuild
    python build/build.py --check    verify the committed page matches its
                                     sources, changing nothing

The web application is one self-contained file so it can be opened by
double-click and served from anywhere. That makes it awkward to edit at 80 KB,
so it is authored in three parts and concatenated:

    _shell.html   markup and stylesheet, ending at the opening <script>
    _engine.js    the segmentation engine, mirroring src/corpusprep/
    _app.js       interface behaviour

**Edit the sources, never docs/index.html.** The page is generated, and a hand
edit to it is silently lost on the next build.

The split matters beyond convenience. `_engine.js` is the half that must agree
with the Python package, and keeping it in its own file makes that boundary
visible. `tools/check_parity.py` still reads the *built* page rather than this
source, because what deserves testing is what is actually deployed.
"""

from __future__ import annotations

import pathlib
import re
import sys

BUILD = pathlib.Path(__file__).resolve().parent
ROOT = BUILD.parent
OUT = ROOT / "docs" / "index.html"

PARTS = ["_shell.html", "_engine.js", "_app.js"]
TAIL = "\n</script>\n</body>\n</html>\n"


def _package_version() -> str:
    """Read `__version__` without importing the package."""
    src = (ROOT / "src" / "corpusprep" / "_version.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', src)
    if not m:
        raise SystemExit("could not find __version__ in src/corpusprep/_version.py")
    return m.group(1)


def assemble() -> str:
    """Plain concatenation. No trimming, no reformatting.

    The sources are stored with their exact whitespace at the seams, so that
    a rebuild reproduces the page byte for byte. Anything cleverer here would
    make `--check` report spurious differences.
    """
    # The version is injected rather than written into the sources, so the
    # package and the page cannot drift apart. They already had.
    version = _package_version()
    pieces = []
    for name in PARTS:
        p = BUILD / name
        if not p.exists():
            raise SystemExit(f"missing source: {p}")
        pieces.append(p.read_text(encoding="utf-8"))
        # The shell ends at the opening <script>, so the version constant goes
        # immediately after it. An earlier version prepended it to the whole
        # file, which put a bare `const` in front of <!DOCTYPE html> where the
        # browser rendered it as text and every reference to it threw.
        if name == "_shell.html":
            pieces.append(f'const CORPUSPREP_VERSION="{version}";\n')
    return "".join(pieces) + TAIL


def main(argv: list[str]) -> int:
    built = assemble()

    if "--check" in argv:
        if not OUT.exists():
            print("docs/index.html does not exist. Run without --check.")
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current == built:
            print(f"docs/index.html matches its sources ({len(built) // 1024} KB)")
            return 0
        print("docs/index.html DIFFERS from its sources.")
        print("Either it was edited by hand, or the sources changed without a rebuild.")
        print(f"  built:   {len(built):,} characters")
        print(f"  on disk: {len(current):,} characters")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(built, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(built) // 1024} KB)")
    print("Now run: python tools/check_parity.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
