#!/usr/bin/env python3
"""
install_hooks.py — install the git hooks in tools/hooks/.

    python tools/install_hooks.py            install
    python tools/install_hooks.py --status   show what is installed
    python tools/install_hooks.py --remove   uninstall

Git hooks live in `.git/hooks/`, which is not part of the repository, so they
have to be installed once per clone. That is why they are kept in `tools/hooks/`
and copied into place rather than committed directly.

What gets installed:

    pre-commit    tests and build check, about two seconds. Blocks the commit
                  if either fails.
    pre-push      parity and accuracy, about five seconds. Blocks the push if
                  the Python and JavaScript engines have drifted.
    post-commit   pushes automatically after a successful commit.

The division is deliberate. Fast checks run on every commit; slower ones run
only when work leaves the machine.

**What this does not do is commit for you.** An automatic timed commit would
produce a history of meaningless messages and would happily record broken
states. The commit history is part of this project's record, and a stream of
"auto-commit 14:32" entries would destroy its value. You decide when a change
is worth recording and what to call it; the hooks only remove the step that
gets forgotten.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "hooks"
HOOKS = ["pre-commit", "pre-push", "post-commit"]


def hooks_dir() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit("Not a git repository, or git is not installed.")
    p = Path(out)
    return p if p.is_absolute() else ROOT / p


def install() -> int:
    dest = hooks_dir()
    dest.mkdir(parents=True, exist_ok=True)

    for name in HOOKS:
        src = SOURCE / name
        if not src.exists():
            print(f"  missing source hook: {src}")
            return 1
        target = dest / name

        if target.exists() and target.read_text(encoding="utf-8") != src.read_text(encoding="utf-8"):
            backup = target.with_suffix(".backup")
            shutil.copy2(target, backup)
            print(f"  existing {name} backed up to {backup.name}")

        shutil.copy2(src, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  installed {name}")

    print(f"\nInstalled into {dest}")
    print("\nFrom now on `git commit` runs the checks and pushes automatically.")
    print("To bypass on a particular commit, use --no-verify.")
    return 0


def remove() -> int:
    dest = hooks_dir()
    for name in HOOKS:
        target = dest / name
        if target.exists():
            target.unlink()
            print(f"  removed {name}")
            backup = target.with_suffix(".backup")
            if backup.exists():
                shutil.move(str(backup), str(target))
                print(f"  restored previous {name} from backup")
    return 0


def status() -> int:
    dest = hooks_dir()
    print(f"Hooks directory: {dest}\n")
    for name in HOOKS:
        target = dest / name
        src = SOURCE / name
        if not target.exists():
            state = "not installed"
        elif target.read_text(encoding="utf-8") == src.read_text(encoding="utf-8"):
            state = "installed, current"
        else:
            state = "installed, DIFFERS from tools/hooks/"
        print(f"  {name:<14} {state}")
    return 0


def main(argv: list[str]) -> int:
    if "--status" in argv:
        return status()
    if "--remove" in argv:
        return remove()
    return install()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
