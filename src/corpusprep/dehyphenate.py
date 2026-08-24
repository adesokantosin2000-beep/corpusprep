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

**When the evidence runs out, the hyphen the source printed is kept**, and that
is the end of it. The reader is told, not asked.

Keeping is right for two reasons. It preserves the source, which is this whole
package's default posture. And the resulting error is the visible one:
`object-ionable` is obviously wrong in a word list, whereas `crosslegged` looks
like a real word and survives proofreading. **The safer mistake is the one that
can be seen.**
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

#: Longest unattested tail still treated as a suffix rather than a word.
#: See `decide()` for why length alone would be the wrong test.
SUFFIX_MAX_LEN = 3

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


def word_counts(lines: list[str]) -> dict[str, int]:
    """How often each word form occurs, so a fragment cannot vouch for itself.

    `def-inite` puts `def` and `inite` into the text. Asking "is `inite` a
    word here?" against a plain vocabulary answers yes, because the broken
    fragment is sitting in the document being searched. Counting occurrences
    lets a fragment be discounted against its own appearances.
    """
    counts: dict[str, int] = {}
    for line in lines:
        for m in _WORD.finditer(line):
            w = m.group(0).lower().strip("-")
            counts[w] = counts.get(w, 0) + 1
    return counts


def find(lines: list[str], skip: set[int] | None = None,
         extra_vocab: set[str] | None = None) -> list[Break]:
    """Find every word broken across a line break, and decide each.

    ``extra_vocab`` is an optional wordlist **from outside this document**.
    The default behaviour deliberately does not depend on one.

    It must not be the vocabulary of the text being searched. The document
    contains the broken fragments, so passing its own vocabulary counts each
    fragment twice while the fragment discount subtracts it once, and every
    fragment is promoted to a real word. Doing that here turned 171 joins into
    84 and 6 kept hyphens into 96.
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

        out.append(Break(line=n, left=left, right=right,
                         joined=left + right, hyphenated=left + "-" + right))

    # Second pass. The decision needs to know every fragment in the document,
    # so that a fragment cannot vouch for itself, which means it cannot be
    # taken until all of them have been found.
    counts = word_counts(lines)
    if extra_vocab:
        for w in extra_vocab:
            w = w.lower().strip("-")
            counts[w] = counts.get(w, 0) + 1
    frag: dict[str, int] = {}
    for b in out:
        for f in (b.left.lower().strip("-"), b.right.lower()):
            frag[f] = frag.get(f, 0) + 1

    def attested(w: str) -> bool:
        """A word occurring only as a broken fragment is not attested."""
        w = w.lower().strip("-")
        return counts.get(w, 0) > frag.get(w, 0)

    for b in out:
        decide(b, attested)
    return out


def decide(b: "Break", attested) -> None:
    """Settle one break from the evidence, strongest first.

    The first two rules ask whether the finished word already exists in this
    text. They are the strongest evidence available and were the whole rule
    originally, which worked on a complete book and left a short extract almost
    entirely unanswered: 96 of 180 breaks on a 260-paragraph sample.

    The rules that follow use the fragments themselves, and the observation
    that settles most of the rest is that **a compound is built out of words
    and a broken word is not**. `drawing-room` is `drawing` plus `room`;
    `def-inite` is `def` plus `inite`, and `inite` is not a word anywhere.

    The asymmetry matters. A compound's LEFT half is always a real word, so a
    left fragment that is not attested cannot be a compound and must be a
    broken word. That single rule answers `impio-us`, `geni-us` and `fav-our`,
    all of which have a real word on the right and would otherwise look like
    compounds.
    """
    j, h = b.joined, b.hyphenated
    left, right = b.left, b.right

    if attested(j):
        b.decision = JOIN
        b.reason = f"{j!r} occurs elsewhere in this text"
    elif attested(h):
        b.decision = KEEP
        b.reason = f"{h!r} occurs elsewhere in this text"
    elif not attested(left):
        # A compound's first half is a word. This one is not, so the hyphen is
        # a typesetter's and the word is broken.
        b.decision = JOIN
        b.reason = (f"{left!r} is not a word in this text, so this is a broken "
                    f"word rather than a compound")
    elif attested(right):
        b.decision = KEEP
        b.reason = (f"{left!r} and {right!r} are both words here, so this reads "
                    f"as a compound")
    elif len(right) <= SUFFIX_MAX_LEN:
        # A short unattested tail is a suffix, not a word: `-ed`, `-ly`, `-mit`.
        #
        # Length alone would be wrong, because `check-in` and `set-up` are real
        # compounds with two-letter second halves. What separates them is that
        # `in` and `up` are ordinary words and appear all over any English
        # text, so they are attested and never reach this branch. Only a tail
        # that is BOTH short AND absent from the document is a bound morpheme.
        b.decision = JOIN
        b.reason = (f"{right!r} is a suffix rather than a word, so this is a "
                    f"broken word")
    else:
        # Left is a word, right is a substantial form that does not appear
        # elsewhere. Either a compound whose second half is rare in this text,
        # or a broken word that happened to split at a word boundary.
        # Genuinely undecidable from this text alone.
        b.decision = UNKNOWN
        b.reason = (f"{left!r} is a word here but {right!r} is not, so this "
                    f"could be either")



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
