#!/usr/bin/env python3
"""
make_interface_fixture.py — generate a synthetic scraped comment thread.

    python tools/make_interface_fixture.py

Writes `tests/fixtures/social_thread.txt` and `tests/keys/social_thread.interface`.

**Synthetic, and that limits what it can prove.** A tester's real corpus was
45% URL by character and, after those were removed, about 3% interface labels —
`Like`, `Reply`, `2 likes` — recurring the way running heads recur. There is no
shareable copy of that corpus, so this stands in for it with exact ground truth.

The generator works to make the task harder, not easier:

- comments vary in length, so the labels do not fall at a fixed interval
- some comments have no `Like` line and some have no reply count, so the
  labels do not appear once per record either
- a genuine one-word comment (`Same`) repeats often enough to tempt a rule
  that counts repetitions and nothing else
- one commenter writes the word `Reply` inside a sentence, and another writes
  a whole comment that is only the word `Beautiful`, which recurs
- handles, relative timestamps and URLs are present, because the rule is only
  licensed to fire on a document that looks like a scraped feed

Deterministic: a fixed seed, so the fixture and its key never drift.
"""

from __future__ import annotations

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "social_thread.txt"
KEY = ROOT / "tests" / "keys" / "social_thread.interface"

HANDLES = ["alpha_writer", "beta_curated_by_m", "gamma.official", "delta_v24",
           "eps.ilon", "zeta_reads", "eta.makes", "theta_studio", "iota_journal",
           "kappa.and.co", "lambda_notes", "mu_archive"]

BODIES = [
    "Love what you're making here, this is genuinely lovely",
    "One more level of unattainability. Terrifying that we deny our humanness.",
    "Yes definitely — 100% agree with @alpha_writer",
    "the lighting in this one is unreal",
    "been following since 2019 and it is still my favourite",
    "Can you do a tutorial on this please",
    "I keep coming back to this one",
    "the colours here are extraordinary",
    "This is the best thing on my feed today",
    "please drop the playlist",
    "your feed is so consistent, every time",
    "I said I would reply to this properly and here I am",   # the word, in prose
    "Same",
    "Beautiful",
    "the composition on the third one especially",
    "what camera do you use for these",
]

rng = random.Random(20260828)

lines: list[str] = []
truth: list[int] = []          # 1-based line numbers of interface furniture


def emit(text: str, furniture: bool = False) -> None:
    lines.append(text)
    if furniture:
        truth.append(len(lines))


lines.append("Comment thread, exported 2026-08-28")
lines.append("https://www.example.com/p/AbCdEf/")
lines.append("")

for i in range(40):
    handle = HANDLES[i % len(HANDLES)]
    emit(f"[{handle}](https://www.example.com/{handle}/)")
    emit(f" [{rng.randint(1, 90)} {rng.choice('whdy')}]"
         f"(https://www.example.com/p/AbCdEf/c/{rng.randrange(10**15, 10**16)}/)")

    for line in rng.sample(BODIES, rng.choice([1, 1, 1, 2])):
        emit(line)

    # Not every comment carries every label: the rule must not require one.
    if rng.random() < 0.85:
        emit("Like", furniture=True)
    if rng.random() < 0.30:
        n = rng.randint(2, 340)
        emit(f"{n} like{'s' if n != 1 else ''}", furniture=True)
    emit("Reply", furniture=True)
    if rng.random() < 0.25:
        emit(f"View replies ({rng.randint(2, 19)})", furniture=True)
    if rng.random() < 0.10:
        emit("See translation", furniture=True)
    emit("")

while lines and not lines[-1].strip():
    lines.pop()

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

ranges: list[str] = []
start = prev = None
for n in truth:
    if start is None:
        start = prev = n
    elif n == prev + 1:
        prev = n
    else:
        ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = n
if start is not None:
    ranges.append(f"{start}" if start == prev else f"{start}-{prev}")

KEY.write_text(
    "# social_thread.txt — the interface furniture, recorded as it was written.\n"
    "#\n"
    "# Every line listed here is a label the interface printed, not something a\n"
    "# person wrote. Comment bodies are never listed, including the one that\n"
    "# uses the word 'reply' in a sentence and the one-word comments 'Same'\n"
    "# and 'Beautiful', which repeat often enough to tempt a rule that counts\n"
    "# repetitions and nothing else.\n\n"
    + "\n".join(ranges) + "\n", encoding="utf-8")

text_lines = sum(1 for l in lines if l.strip())
print(f"wrote {OUT.relative_to(ROOT)}: {len(lines)} lines, "
      f"{text_lines} text lines, {len(truth)} interface "
      f"({100 * len(truth) / text_lines:.1f}%)")
print(f"wrote {KEY.relative_to(ROOT)}: {len(ranges)} ranges")
