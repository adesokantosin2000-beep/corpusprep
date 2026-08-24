"""
corpusprep.dehyphenate
======================

Repair of words broken across a line break by a typesetter's hyphen.

    ... it was an exam-
    ple of the kind ...          ->   ... it was an example of the kind ...

**Two decisions, not one.** The line break is always an artefact of
typesetting. The hyphen may be entirely real:

    to-          ->  to-morrow     a real nineteenth-century compound
    morrow           tomorrow      wrong: invents a modern word

*Jane Eyre* contains 1,146 hyphenated compounds, `to-night` forty-two times.
So the fragments are always rejoined, because that break is certainly spurious,
and the hyphen's fate is decided separately on evidence.

**The evidence is the document's own vocabulary, not a wordlist.** A 234,000
word list of modern English recognises only 65% of the word types in *Jane
Eyre*, rejecting `adapted` and `adding` alongside `againe` and `accurst`. A
rule requiring dictionary confirmation would refuse a third of the legitimate
joins and would fail worst on the historical material this tool exists for.

If `example` occurs elsewhere in *this* text, the joined form is attested in
this text's own orthography. Nothing is bundled and no licence question arises.
See `design/DECISIONS.md`.

Nothing here guesses silently. Where the evidence is absent or contradictory
the hyphen is kept and the case is flagged for review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Word characters, Unicode-aware, including the apostrophes that carry so much
#: of early modern English: `graith'd`, `o'`, `nextan'`.
_WORD = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)

#: A hyphenation hyphen is ATTACHED to its word. A hyphen preceded by
#: whitespace is a dash used as punctuation, and *Jane Eyre* has 143 of those
#: and no hyphenation at all. Without this guard every one would be mangled.
TAIL = re.compile(r"(?<=[^\W\d_])([\w'’]*)-\s*$", re.UNICODE)

#: The next line must begin with a word for there to be anything to join to.
HEAD = re.compile(r"^\s*([^\W\d_][\w'’]*)", re.UNICODE)

#: Decisions a break can receive.
JOIN = "join"            # attested joined: drop the hyphen
KEEP = "keep"            # attested hyphenated: keep the hyphen
AMBIGUOUS = "ambiguous"  # both attested: rejoin, keep hyphen, flag
UNKNOWN = "unknown"      # neither attested: rejoin, keep hyphen, flag


@dataclass
class Break:
    """One word broken across a line break."""

    line: int                 # 1-based line carrying the trailing hyphen
    left: str                 # fragment before the hyphen
    right: str                # fragment after the break
    joined: str               # left + right
    hyphenated: str           # left + "-" + right
    decision: str = UNKNOWN
    reason: str = ""

    @property
    def resolved(self) -> str:
        """The word as it will appear once rejoined."""
        return self.joined if self.decision == JOIN else self.hyphenated

    @property
    def needs_review(self) -> bool:
        return self.decision in (AMBIGUOUS, UNKNOWN)


def vocabulary(lines: list[str]) -> set[str]:
    """Every word form attested in the document, lowercased.

    Built once and used as the evidence base for every decision, which is what
    makes the rule adapt to the text's own spelling rather than to a
    lexicographer's idea of English in some other century.
    """
    vocab: set[str] = set()
    for line in lines:
        for m in _WORD.finditer(line):
            vocab.add(m.group(0).lower().strip("-"))
    return vocab


def find(lines: list[str], skip: set[int] | None = None,
         extra_vocab: set[str] | None = None) -> list[Break]:
    """Find every word broken across a line break, and decide each.

    ``extra_vocab`` is an optional user-supplied wordlist. The default
    behaviour deliberately does not depend on one.
    """
    skip = skip or set()
    vocab = vocabulary(lines)
    if extra_vocab:
        vocab = vocab | {w.lower() for w in extra_vocab}

    out: list[Break] = []
    for i in range(len(lines) - 1):
        n = i + 1
        if n in skip or n + 1 in skip:
            continue
        tail = TAIL.search(lines[i])
        if not tail:
            continue
        head = HEAD.match(lines[i + 1])
        if not head:
            continue

        # Recover the whole left fragment, not just what the pattern captured.
        stripped = lines[i].rstrip()[:-1]
        lm = _WORD.search(stripped[::-1])
        left = stripped[len(stripped) - lm.end():] if lm else tail.group(1)
        right = head.group(1)
        if not left or not right:
            continue

        b = Break(line=n, left=left, right=right,
                  joined=left + right, hyphenated=left + "-" + right)

        j = b.joined.lower().strip("-")
        h = b.hyphenated.lower().strip("-")
        # The joined form must be attested somewhere OTHER than here, so a
        # single occurrence cannot vouch for itself.
        j_seen = j in vocab
        h_seen = h in vocab

        if j_seen and h_seen:
            b.decision = AMBIGUOUS
            b.reason = (f"both {b.joined!r} and {b.hyphenated!r} occur "
                        f"elsewhere in this text")
        elif j_seen:
            b.decision = JOIN
            b.reason = f"{b.joined!r} occurs elsewhere in this text"
        elif h_seen:
            b.decision = KEEP
            b.reason = f"{b.hyphenated!r} occurs elsewhere in this text"
        else:
            b.decision = UNKNOWN
            b.reason = (f"neither {b.joined!r} nor {b.hyphenated!r} occurs "
                        f"elsewhere in this text")
        out.append(b)
    return out


def find_in_document(doc, extra_vocab: set[str] | None = None) -> list[Break]:
    """Find broken words in a segmented Document, ignoring Gutenberg apparatus."""
    skip = {
        i + 1
        for r in doc.regions
        if r.label in ("pg_header", "pg_licence")
        for i in range(r.start, r.end)
    }
    return find(doc.lines, skip, extra_vocab)


def apply(lines: list[str], breaks: list[Break]) -> list[str]:
    """Rejoin every broken word, returning new lines.

    The break is repaired in all cases, including the flagged ones, because a
    word split across two lines is broken however the hyphen is resolved. What
    varies is only whether the hyphen survives.
    """
    by_line = {b.line: b for b in breaks}
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        j = i
        # Keep absorbing while the line we have just built still ends in a
        # break. Consecutive broken lines are common in hard-wrapped text, and
        # an earlier version merged line 31 into 32 and then skipped past 32's
        # own break, leaving one word in eight still split.
        while j + 1 < len(lines):
            b = by_line.get(j + 1)
            if b is None:
                break
            head = HEAD.match(lines[j + 1])
            if head is None:
                break
            stripped = cur.rstrip()
            # Replace the trailing `left-` with the resolved word, then carry
            # the remainder of the following line up.
            cut = len(stripped) - len(b.left) - 1
            if cut < 0 or not stripped.endswith(b.left + "-"):
                break
            cur = stripped[:cut] + b.resolved + lines[j + 1][head.end():]
            j += 1
        out.append(cur)
        i = j + 1
    return out
