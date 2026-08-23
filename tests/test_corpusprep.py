"""
Regression tests for the CorpusPrep prototype.

Run with:  python -m tests.test_corpusprep      (no pytest needed)
       or: pytest tests/test_corpusprep.py

The first four tests are the confirmed bugs from the original
clean_jane_eyre.py. They exist to make sure the rewrite never
reintroduces them.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from corpusprep import BUILTIN, load, render, render_all, segment  # noqa: E402
from corpusprep.document import (BODY, FRONT_MATTER, PG_HEADER, PG_LICENCE,  # noqa: E402
                                  word_tokens)
from corpusprep.segment import find_licence_blocks, is_chapter_heading  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}  {detail}")


def _doc(text: str):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        p = Path(f.name)
    return segment(load(p))


# ---------------------------------------------------------------------------
# Regressions against the four confirmed prototype bugs
# ---------------------------------------------------------------------------

def test_b1_note_paragraph_survives():
    """B1: a paragraph starting 'Note:' must not be swallowed."""
    doc = _doc(
        "CHAPTER I\n\n"
        "Note: I could not tell what mood he was in.\n"
        "He turned to me with a sudden question.\n\n"
        "The next paragraph.\n"
    )
    out = render(doc, BUILTIN["body-only"]).text
    check("B1 'Note:' paragraph retained", "sudden question" in out)
    check("B1 following line retained", "next paragraph" in out.lower())


def test_b2_allcaps_prose_survives():
    """B2: emphatic all-caps prose must not be deleted as a header."""
    doc = _doc(
        "CHAPTER I\n\n"
        "I READ IT AGAIN AND AGAIN.\n\n"
        "Then I put the book down.\n"
    )
    out = render(doc, BUILTIN["body-only"]).text
    check("B2 all-caps prose retained", "I READ IT AGAIN AND AGAIN." in out)


def test_b3_chapter_headings_labelled():
    """B3: chapter detection must actually run (was dead code)."""
    doc = _doc("CHAPTER I\n\nOne.\n\nCHAPTER II\n\nTwo.\n")
    chapters = [r for r in doc.regions if r.kind == "chapter"]
    check("B3 both chapters detected", len(chapters) == 2,
          f"got {len(chapters)}")


def test_b4_standalone_number_survives():
    """B4: an isolated year in prose must not be removed as a page number."""
    doc = _doc("CHAPTER I\n\nThe date was\n1847\nand all was well.\n")
    out = render(doc, BUILTIN["body-only"]).text
    check("B4 standalone '1847' retained", "1847" in out)


# ---------------------------------------------------------------------------
# Core capabilities
# ---------------------------------------------------------------------------

def test_import_bom_and_crlf():
    with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as f:
        f.write("﻿CHAPTER I\r\n\r\nHello world.\r\n".encode("utf-8"))
        p = Path(f.name)
    doc = segment(load(p))
    check("import strips BOM", doc.had_bom and not doc.lines[0].startswith("﻿"))
    check("import records CRLF", doc.newline == "\r\n")
    check("import normalises to LF", "\r" not in doc.text)


def test_licence_detection_with_markers():
    doc = segment(load(FIXTURES / "pg_marked.txt"))
    labels = {r.label for r in doc.regions}
    check("PG header detected", PG_HEADER in labels)
    check("PG licence detected", PG_LICENCE in labels)
    check("front matter detected", FRONT_MATTER in labels)
    check("body detected", BODY in labels)


def test_licence_detection_without_markers():
    """Licence text must still be found when sentinels are stripped."""
    text = (
        "CHAPTER I\n\nThe story begins.\n\n"
        "This eBook is for the use of anyone anywhere at no cost and with\n"
        "almost no restrictions whatsoever. You may copy it, give it away\n"
        "under the terms of the Project Gutenberg License at www.gutenberg.org\n"
    )
    doc = _doc(text)
    check("unmarked licence detected",
          any(r.label == PG_LICENCE for r in doc.regions))
    out = render(doc, BUILTIN["body-only"]).text
    check("unmarked licence removed from body-only",
          "gutenberg.org" not in out.lower())


def test_transcriber_note_detected():
    """Producer credits sit *after* the START marker and often name pglaf.org
    without ever saying "gutenberg", so the licence scorer alone misses them."""
    doc = _doc(
        "*** START OF THE PROJECT GUTENBERG EBOOK DE PROFUNDIS ***\n\n"
        "Transcribed from the 1913 Methuen & Co. edition by David\n"
        "Price, email ccx074@pglaf.org.  Note that later editions of\n"
        "De Profundis contained more material.  The most complete\n"
        "editions are still in copyright in the U.S.A.\n\n"
        "DE PROFUNDIS\n\n"
        "Suffering is one very long moment.\n"
    )
    notes = [r for r in doc.regions if r.kind == "transcriber_note"]
    check("transcriber note detected", len(notes) == 1, f"got {len(notes)}")

    out = render(doc, BUILTIN["body-only"]).text
    check("transcriber note removed in body-only", "pglaf" not in out)
    check("prose after the note retained", "very long moment" in out)

    verb = render(doc, BUILTIN["verbatim"]).text
    check("transcriber note kept in verbatim", "pglaf" in verb)


def test_transcribers_note_curly_apostrophe():
    """Gutenberg uses the typographic apostrophe almost universally.

    Matching only the straight form (') meant this rule silently failed on the
    very files it was written for. All three forms must be accepted.
    """
    from corpusprep.segment import TRANSCRIBER_HEADING

    for form in ["Transcriber's Notes", "Transcriber’s Notes",
                 "Transcriberʼs Note", "TRANSCRIBER’S NOTES"]:
        check(f"heading matched: {form}", bool(TRANSCRIBER_HEADING.match(form)))

    doc = _doc(
        "CHAPTER I\n\nThe story runs on for a while.\n\n"
        "Transcriber’s Notes\n\n"
        "New original cover art included with this eBook is granted to the\n"
        "public domain. Obvious typographical errors have been corrected.\n"
    )
    notes = [r for r in doc.regions if r.kind == "transcriber_note"]
    check("note detected with curly apostrophe", len(notes) == 1,
          f"got {len(notes)}")

    out = render(doc, BUILTIN["body-only"]).text
    check("heading removed", "Transcriber" not in out)
    check("note body removed too", "cover art" not in out)
    check("prose retained", "story runs on" in out)
    check("kept in verbatim",
          "cover art" in render(doc, BUILTIN["verbatim"]).text)


def test_split_region_does_not_inherit_title():
    """Text after an interruption is not the chapter whose heading preceded it."""
    doc = _doc(
        "CHAPTER I\n\nFirst part of the chapter.\n\n"
        "Transcriber’s Notes\n\nA note from the transcriber.\n\n"
        "Second part of the chapter.\n"
    )
    tails = [r for r in doc.regions
             if r.kind == "chapter" and "continued" in r.title]
    check("split tail is marked as continued", len(tails) == 1,
          f"titles: {[r.title for r in doc.regions if r.kind == 'chapter']}")


def test_transcriber_rule_cannot_eat_prose():
    """B1 must not return through the transcriber-note route.

    The old rule ran to the end of any paragraph starting with one of these
    words, anywhere in the text. This one is bounded to a single block *and*
    to a window at the head or tail, so mid-novel prose is untouchable.
    """
    body = "\n\n".join(
        f"Paragraph {i} of ordinary narrative prose continues here."
        for i in range(60)
    )
    doc = _doc(
        "CHAPTER I\n\n" + body + "\n\n"
        "Produced by the labour of many hands, the great engine turned.\n"
        "It turned again, and the whole valley shook with the sound.\n\n"
        + body + "\n"
    )
    out = render(doc, BUILTIN["body-only"]).text
    check("mid-text 'Produced by' paragraph survives",
          "the great engine turned" in out)
    check("its continuation survives", "the whole valley shook" in out)


def test_tokeniser_handles_non_ascii():
    """Accented and ligatured words must count as single tokens.

    This is the Python half of a cross-implementation contract: JavaScript's
    \\w is ASCII-only, so the web app needs \\p{L} to agree. The parity check
    found a 9-token drift on De Profundis before this was pinned down.
    """
    from corpusprep.document import word_tokens

    got = word_tokens("æsthetic naïve résumé don't Zoë 1847")
    check("non-ASCII words tokenise whole",
          got == ["æsthetic", "naïve", "résumé", "don't", "Zoë"],
          f"got {got}")


def test_ordinary_copyright_not_flagged():
    """A novel mentioning copyright must not be mistaken for licence text."""
    blocks = find_licence_blocks([
        "He argued about copyright and the public domain for an hour,",
        "and the trademark dispute wearied everyone present.",
    ])
    check("ordinary prose not flagged as licence", blocks == [],
          f"got {blocks}")


def test_full_coverage_no_content_lost():
    doc = segment(load(FIXTURES / "pg_marked.txt"))
    check("no uncovered content lines", doc.coverage_gaps() == [],
          f"gaps: {doc.coverage_gaps()}")


def test_variants_differ_and_nest():
    doc = segment(load(FIXTURES / "pg_marked.txt"))
    results = {r.variant.name: r for r in
               render_all(doc, ["verbatim", "full", "body-only", "body-no-headings"])}

    v = results["verbatim"].stats["word_tokens"]
    f = results["full"].stats["word_tokens"]
    b = results["body-only"].stats["word_tokens"]
    nh = results["body-no-headings"].stats["word_tokens"]

    check("verbatim is the largest", v > f, f"{v} vs {f}")
    check("full larger than body-only", f > b, f"{f} vs {b}")
    check("no-headings smaller than body-only", nh < b, f"{nh} vs {b}")
    check("verbatim keeps licence text",
          "gutenberg" in results["verbatim"].text.lower())
    check("body-only drops licence text",
          "gutenberg" not in results["body-only"].text.lower())
    check("body-no-headings drops CHAPTER lines",
          "CHAPTER I" not in results["body-no-headings"].text)


def test_body_only_is_subset_of_source():
    """Every word kept must have existed in the source. No invented text."""
    doc = segment(load(FIXTURES / "pg_marked.txt"))
    out = render(doc, BUILTIN["body-only"]).text
    src_lines = {l.strip() for l in doc.lines}
    missing = [ln for ln in out.splitlines() if ln.strip() and ln.strip() not in src_lines]
    check("all output lines exist in source", not missing,
          f"{len(missing)} invented line(s)")


def test_container_formats():
    """.docx / .epub / .html must segment the same way as plain text."""
    from corpusprep.formats import UnsupportedFormat, extract

    expected = {"sample.docx": 2, "sample.epub": 2, "sample.html": 2}
    for fname, n_chapters in expected.items():
        p = FIXTURES / fname
        if not p.exists():
            print(f"  SKIP  {fname} not present")
            continue
        doc = segment(load(p))
        chapters = [r for r in doc.regions if r.kind == "chapter"]
        check(f"{fname}: {n_chapters} chapters found",
              len(chapters) == n_chapters, f"got {len(chapters)}")
        check(f"{fname}: front matter found",
              any(r.label == FRONT_MATTER for r in doc.regions))
        check(f"{fname}: no uncovered content", doc.coverage_gaps() == [])
        check(f"{fname}: import note recorded",
              any("extracted from" in n for n in doc.notes))

        out = render(doc, BUILTIN["body-only"]).text
        check(f"{fname}: body text extracted",
              "no possibility of taking a walk" in out)
        check(f"{fname}: front matter removed in body-only",
              "PREFACE" not in out)


def test_html_drops_script_and_style():
    """Script and style content must never reach the corpus."""
    from corpusprep.formats import extract_html

    text, _ = extract_html(
        "<html><head><style>p{color:red}</style>"
        "<script>var secret='leak'</script></head>"
        "<body><p>Real prose &amp; more.</p></body></html>"
    )
    check("script content dropped", "leak" not in text)
    check("style content dropped", "color:red" not in text)
    check("entities decoded", "&" in text and "&amp;" not in text)
    check("prose retained", "Real prose" in text)


def test_pdf_and_doc_refused_with_reason():
    """Unsupported formats must explain why, not fail obscurely."""
    from corpusprep.formats import UnsupportedFormat, extract

    for ext, word in [(".pdf", "hyphenated"), (".doc", "re-save")]:
        try:
            extract("nonexistent" + ext)
            check(f"{ext} refused", False, "no exception raised")
        except UnsupportedFormat as e:
            check(f"{ext} refused with explanation", word in str(e).lower(),
                  f"message was: {e}")
        except Exception as e:  # noqa: BLE001
            check(f"{ext} refused with explanation", False,
                  f"wrong exception: {type(e).__name__}")


def test_drama_nesting():
    """Acts must contain their scenes, not sit beside them."""
    p = FIXTURES / "drama_with_contents.txt"
    if not p.exists():
        print("  SKIP  drama fixture not present")
        return
    doc = segment(load(p))

    acts = [(i, r) for i, r in enumerate(doc.regions)
            if r.label == BODY and r.title.upper().startswith("ACT")]
    scenes = [(i, r) for i, r in enumerate(doc.regions)
              if r.label == BODY and r.title.upper().startswith("SCENE")]

    check("5 acts found", len(acts) == 5, f"got {len(acts)}")
    check("acts are level 1", all(r.level == 1 for _, r in acts))
    check("scenes are level 2", all(r.level == 2 for _, r in scenes))
    check("every scene has an act as parent",
          all(r.parent is not None for _, r in scenes))
    check("scene parents are acts",
          all(doc.regions[r.parent].title.upper().startswith("ACT")
              for _, r in scenes))

    # An act's own span is just its heading; its real size is the subtree.
    i, act1 = acts[0]
    own = len(word_tokens(doc.region_text(act1)))
    sub = doc.subtree_words(i)
    check("act subtree is larger than its own span", sub > own,
          f"own={own} subtree={sub}")


def test_contents_list_not_treated_as_body():
    """A table of contents repeats its headings — body must start after it."""
    p = FIXTURES / "drama_with_contents.txt"
    if not p.exists():
        print("  SKIP  drama fixture not present")
        return
    doc = segment(load(p))
    contents = [r for r in doc.regions if r.kind == "contents"]
    check("contents list detected", len(contents) == 1, f"got {len(contents)}")

    body = [r for r in doc.regions if r.label == BODY]
    check("body starts after the contents",
          body and contents and body[0].start > contents[0].start)
    # Count whole lines, not substrings — "ACT I" is a prefix of "ACT II".
    out = render(doc, BUILTIN["body-only"]).text
    n = sum(1 for ln in out.splitlines() if ln.strip() == "ACT I")
    check("each act heading appears once, not twice", n == 1,
          f"'ACT I' on {n} lines — contents list not separated")


def test_book_chapter_nesting():
    p = FIXTURES / "book_chapter_nesting.txt"
    if not p.exists():
        print("  SKIP  book fixture not present")
        return
    doc = segment(load(p))
    books = [r for r in doc.regions if r.title.upper().startswith("BOOK")]
    chaps = [r for r in doc.regions if r.title.upper().startswith("CHAPTER")]
    check("books are level 1", books and all(r.level == 1 for r in books))
    check("chapters are level 2", chaps and all(r.level == 2 for r in chaps))


def test_flat_novel_stays_flat():
    """A text using only one division word must not gain a fake hierarchy."""
    doc = _doc("A Novel\n\nCHAPTER I\n\nOne.\n\nCHAPTER II\n\nTwo.\n")
    check("single division type stays flat",
          all(r.level == 1 for r in doc.regions))
    check("no parents assigned",
          all(r.parent is None for r in doc.regions))


def test_romeo_juliet_body_starts_at_act_one():
    """The whole point, on a real Gutenberg play: body-only must begin at
    ACT I with every scrap of apparatus before it removed."""
    p = FIXTURES / "romeo_juliet.txt"
    if not p.exists():
        print("  SKIP  Romeo and Juliet fixture not present")
        return
    doc = segment(load(p))
    out = render(doc, BUILTIN["body-only"]).text

    check("body-only opens with ACT I",
          out.splitlines()[0].strip() == "ACT I",
          f"opens with {out.splitlines()[0]!r}")

    for junk in ["Project Gutenberg", "Title: Romeo", "Credits:", "Contents",
                 "Dramatis", "ESCALUS", "THE PROLOGUE", "Two households",
                 "trademark", "gutenberg.org"]:
        check(f"'{junk}' removed", junk not in out)

    check("play dialogue retained", "we will not carry coals" in out)
    check("last scene retained", "churchyard" in out.lower())


def test_contents_detection_is_robust():
    """Contents detection must not collapse when a body heading is missed.

    The first version required an unbroken prefix of entries that all reappear,
    and capped the run at half the headings. On a play the contents mirrors the
    body one-for-one, so that cap sat exactly on the boundary — a single
    asymmetry disabled the rule and the contents list became the play.
    Density now defines the run; duplication only confirms it.
    """
    from corpusprep.segment import split_contents_list

    entries = ["ACT I"] + [f"Scene {r}. Place {r}." for r in "I II III IV V".split()]
    entries += ["ACT II"] + [f"Scene {r}. Spot {r}." for r in "I II III IV V VI".split()]
    entries += ["ACT III"] + [f"Scene {r}. Room {r}." for r in "I II III IV V".split()]

    def build(skip=()):
        lines, idx = [], []
        for t in entries:                       # contents: one line apart
            idx.append(len(lines))
            lines.append(t)
        for k, t in enumerate(entries):         # body: far apart
            lines += [""] * 120
            if k in skip:
                lines.append("~ heading not detected ~")
                continue
            idx.append(len(lines))
            lines.append(t.upper())
        return lines, idx

    n = len(entries)
    for label, skip in [("nothing missed", set()),
                        ("one missed", {5}),
                        ("several missed", {3, 7, 11, 14})]:
        lines, idx = build(skip)
        contents, body = split_contents_list(lines, idx)
        check(f"contents found with {label}", len(contents) == n,
              f"got {len(contents)} of {n}")
        check(f"body starts at ACT I with {label}",
              bool(body) and lines[body[0]].upper() == "ACT I",
              f"starts at {lines[body[0]] if body else None!r}")

    # And must stay silent on a novel that simply has no contents list.
    lines, idx = [], []
    for i in range(1, 20):
        lines += [""] * 200
        idx.append(len(lines))
        lines.append(f"CHAPTER {i}")
    contents, _ = split_contents_list(lines, idx)
    check("no false contents on a plain novel", contents == [],
          f"found {len(contents)}")


def test_named_front_matter_title_case():
    """'Dramatis Personæ' and 'Contents' are set in title case, not caps."""
    from corpusprep.segment import is_front_heading as F

    for s in ["Dramatis Personæ", "Dramatis Personae", "Contents",
              "THE PROLOGUE", "Prologue", "Characters in the Play"]:
        check(f"named front heading: {s}", F(s))

    for s in ["Contents of the letter were startling.",
              "The prologue to that affair was brief.",
              "Dramatis Personae were listed on the back of the programme.",
              "Introduction to Linguistics, 3rd edn"]:
        check(f"not a heading: {s[:34]}…", not F(s))


def test_furniture_detection():
    """Running heads and page numbers on a synthetic scanned text.

    The fixture is deliberately hostile: the refrain repeats 64 times, more
    often than the 60 furniture lines, so a rule counting repetitions alone
    fails outright.
    """
    import re as _re
    from corpusprep.furniture import find_in_document

    fx = FIXTURES / "scanned_novel.txt"
    fk = Path(__file__).parent / "keys" / "scanned_novel.furniture"
    if not fx.exists() or not fk.exists():
        print("  SKIP  scanned fixture not present")
        return

    truth = set()
    for raw in fk.read_text(encoding="utf-8").splitlines():
        s = raw.split("#")[0].strip()
        if not s:
            continue
        m = _re.match(r"^(\d+)(?:-(\d+))?$", s)
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        truth.update(range(a, b + 1))

    doc = segment(load(fx))
    pred, _, page, _catch = find_in_document(doc)

    check("page length estimated", 25 <= page <= 40, f"got {page}")
    check("no furniture missed", not (truth - pred),
          f"missed {sorted(truth - pred)[:5]}")
    check("no prose marked as furniture", not (pred - truth),
          f"wrongly marked {sorted(pred - truth)[:5]}")

    refrain = {i for i, l in enumerate(doc.lines, 1)
               if l.strip() == "And still the rain fell."}
    check("frequent refrain survives", not (refrain & pred),
          f"{len(refrain & pred)} of {len(refrain)} refrain lines deleted")

    dialogue = {i for i, l in enumerate(doc.lines, 1)
                if l.strip().startswith('"')}
    check("short dialogue survives", not (dialogue & pred))


def test_furniture_ignores_front_matter():
    """A title page carries the same words as the running head."""
    from corpusprep.furniture import find_in_document

    fx = FIXTURES / "scanned_novel.txt"
    if not fx.exists():
        print("  SKIP  scanned fixture not present")
        return
    doc = segment(load(fx))
    pred, _, _, _ = find_in_document(doc)
    check("title page line 1 not treated as a running head", 1 not in pred)
    check("imprint date not treated as a page number", 9 not in pred)


def test_page_number_ocr_variants():
    """`l3` for 13 is routine in scanned text and must still be recognised."""
    from corpusprep.furniture import looks_like_page_number as f

    for s in ["13", "l3", "l8", "(7)", "42.", "1847"]:
        check(f"page number recognised: {s!r}", f(s))
    for s in ["JANE EYRE", "and", "I", "O", "the end"]:
        check(f"not a page number: {s!r}", not f(s))


def test_furniture_never_removed_by_default():
    """The invariant: an unvalidated detector must not delete on its own.

    Every built-in variant must leave furniture alone. Removal is a decision
    the user makes explicitly and the log records.
    """
    from corpusprep.variants import BUILTIN
    for name, v in BUILTIN.items():
        check(f"{name} does not drop furniture by default", not v.drop_furniture)


def test_furniture_removal_is_opt_in_and_spares_prose():
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "scanned_novel.txt"
    if not fx.exists():
        print("  SKIP  scanned fixture not present")
        return

    doc = analyse(fx)
    check("furniture detected on import", len(doc.furniture) == 60,
          f"got {len(doc.furniture)}")

    off = render(doc, BUILTIN["body-only"])
    check("default variant removes no furniture",
          off.stats["furniture_removed"] == 0)
    check("running head still present when not asked for",
          "JANE EYRE" in off.text)

    on = render(doc, _replace(BUILTIN["body-only"], drop_furniture=True))
    check("opt-in variant removes furniture",
          on.stats["furniture_removed"] == 60,
          f"got {on.stats['furniture_removed']}")
    check("running head gone once asked for", "JANE EYRE" not in on.text)

    # The three shapes that the original prototype destroyed.
    check("refrain survives removal", "And still the rain fell." in on.text)
    check("emphatic capitals survive", "I READ IT AGAIN AND AGAIN." in on.text)
    check("dialogue survives", '"No, sir."' in on.text)


def test_furniture_reported_with_reasons():
    """A rule the user cannot interrogate is a rule the user cannot trust."""
    from corpusprep import analyse, render_all
    from corpusprep.report import build_markdown, build_json

    fx = FIXTURES / "scanned_novel.txt"
    if not fx.exists():
        print("  SKIP  scanned fixture not present")
        return

    doc = analyse(fx)
    md = build_markdown(doc, render_all(doc, ["verbatim", "body-only"]))
    check("log has a furniture section", "### Page furniture" in md)
    check("log states detection did not delete", "Detected, not removed" in md)
    check("log gives a reason per series", "recurs every" in md)

    js = build_json(doc, render_all(doc, ["verbatim"]))
    check("json lists furniture line numbers",
          len(js["furniture"]["detected_lines"]) == 60)


def test_catchword_detection():
    """Early modern catchwords, on a fixture built to trap the rule."""
    from corpusprep.furniture import find_in_document

    fx = FIXTURES / "early_modern.txt"
    fk = Path(__file__).parent / "keys" / "early_modern.catchwords"
    if not fx.exists() or not fk.exists():
        print("  SKIP  early modern fixture not present")
        return

    truth = {int(l.split("#")[0]) for l in fk.read_text(encoding="utf-8").splitlines()
             if l.split("#")[0].strip()}
    doc = segment(load(fx))
    _marked, _c, _p, catch = find_in_document(doc)
    found = {m.line for m in catch if m.accepted}

    check("every catchword found", not (truth - found),
          f"missed {sorted(truth - found)[:5]}")
    check("no prose marked as a catchword", not (found - truth),
          f"wrongly marked {sorted(found - truth)[:5]}")

    # The trap: a full line of prose whose first word genuinely opens the next
    # page. It satisfies the content test completely. Only the length guard
    # stands between it and deletion.
    trap = next(i for i, l in enumerate(doc.lines, 1)
                if l.startswith("And so the whole company"))
    check("full line of prose spared despite matching", trap not in found)
    m = next((x for x in catch if x.line == trap), None)
    check("and the reason given is its length",
          m is not None and "too long" in m.reason,
          m.reason if m else "boundary never examined")

    # Two pages carry no catchword. A rule demanding every page match would
    # reject the whole book over an omission.
    check("omitted catchwords do not defeat the rule", len(found) == 18,
          f"found {len(found)}")


def test_catchwords_absent_from_modern_text():
    """The result easiest to get wrong: finding nothing when there is nothing.

    A rule firing on two pages in three hundred still reads as working in a
    summary count, so the negative case is tested explicitly.
    """
    from corpusprep.furniture import find_in_document

    for name in ("scanned_novel.txt", "CBronte_Jane.txt", "pg_marked.txt"):
        fx = FIXTURES / name
        if not fx.exists():
            continue
        _m, _c, _p, catch = find_in_document(segment(load(fx)))
        hits = [x for x in catch if x.accepted]
        check(f"no catchwords in {name}", not hits,
              f"{len(hits)} found: {[x.text for x in hits[:3]]}")


def test_page_number_guard_against_word_lookalikes():
    """Digit substitution must not manufacture a number out of a word.

    `So` maps to 50 and `Bo` to 80 under the OCR lookalike table. Before this
    guard, any short word recurring at the page interval was deleted as a page
    number. Found by the early modern fixture, where `So` is a catchword.
    """
    from corpusprep.furniture import looks_like_page_number as f

    for s in ["13", "l3", "l8", "1847", "(7)", "42."]:
        check(f"still a page number: {s!r}", f(s))
    for s in ["So", "Bo", "lo", "Is", "SO", "OO", "II", "I", "and"]:
        check(f"word not read as a page number: {s!r}", not f(s))


def test_chapter_heading_precision():
    """Heading vocabulary must be wide, but must not swallow prose."""
    should_match = [
        "CHAPTER I", "Chapter 1", "Chapter One", "chapter 12",
        "CHAPTER XXXVIII -- CONCLUSION", "Chapter 3: A Meeting",
        "ACT ONE", "Act II", "SCENE III", "Book the Third",
        "PART FIRST", "Stave One", "Letter IV", "VOLUME II",
        "CHAPTER 1. The Beginning",
    ]
    should_not = [
        "The chapter was long and he read it twice.",
        '"Chapter and verse," he said.',
        "Section 3 of the act states that all persons shall comply.",
        "Part of the reason was simple enough.",
        "Chapter and verse was his motto.",
        "Act quickly or lose everything.",
        "Book a table for two at seven.",
        "Scene after scene of pure chaos followed.",
        "I read the letter twice over.",
    ]
    missed = [s for s in should_match if not is_chapter_heading(s)]
    false_pos = [s for s in should_not if is_chapter_heading(s)]
    check(f"all {len(should_match)} heading forms matched", not missed,
          f"missed: {missed}")
    check(f"no false positives on {len(should_not)} prose lines", not false_pos,
          f"matched: {false_pos}")


def test_case_insensitive_headings():
    """Regression: the original pattern was case-sensitive and silently
    failed on 'Chapter 1', which is how most real books are set."""
    doc = _doc("Some Book\n\nChapter One\n\nIt began.\n\n"
               "Chapter Two\n\nThen it did not.\n")
    chapters = [r for r in doc.regions if r.kind == "chapter"]
    check("title-case 'Chapter One' detected", len(chapters) == 2,
          f"got {len(chapters)}")


def test_drama_headings():
    doc = _doc("A PLAY\n\nACT ONE\n\nSIDI: You are late.\n\n"
               "ACT TWO\n\nSIDI: So you returned.\n")
    check("ACT headings detected",
          len([r for r in doc.regions if r.kind == "chapter"]) == 2)


def test_numbered_sections():
    doc = _doc("A Paper\n\n1. Introduction\n\nResearch has expanded.\n\n"
               "2. Method\n\nThe corpus comprises 400 essays.\n")
    secs = [r for r in doc.regions if r.kind == "section"]
    check("numbered sections detected", len(secs) == 2, f"got {len(secs)}")


def test_bare_numeral_sequence():
    """Bare numerals count as chapters only in an ascending run from 1."""
    doc = _doc("A Novel\n\n1\n\nIt was April.\n\n2\n\nCabbage.\n\n3\n\nHe stopped.\n")
    check("ascending 1,2,3 read as chapters",
          len([r for r in doc.regions if r.kind == "chapter"]) == 3)

    # The B4 guard, via the new route: a lone year must not start a sequence.
    doc2 = _doc("CHAPTER I\n\nThe date was\n1847\nand all was well.\n")
    out = render(doc2, BUILTIN["body-only"]).text
    check("lone 1847 still not treated as a heading", "1847" in out)

    doc3 = _doc("A Text\n\n1847\n\nSome prose here.\n\n1923\n\nMore prose.\n")
    check("non-sequential years form no chapters",
          len([r for r in doc3.regions if r.kind == "chapter"]) == 0)


def test_metadata_header():
    """Transcripts and article extracts get their header block separated."""
    doc = _doc(
        "Interview 04\nDate: 3 March 2026\nParticipant: P04\n"
        "Interviewer: TA\nDuration: 42 minutes\n\n"
        "INT: So tell me about how you use English at home.\n\n"
        "P04: At home we mix it.\n"
    )
    meta = [r for r in doc.regions if r.kind == "metadata"]
    check("metadata block found in a text with no chapters", len(meta) == 1,
          f"got {len(meta)}")
    if meta:
        out = render(doc, BUILTIN["body-only"]).text
        check("metadata removed from body-only", "Duration: 42" not in out)
        check("interview content retained", "we mix it" in out)


def test_jane_eyre_real_file():
    src = FIXTURES / "CBronte_Jane.txt"
    if not src.exists():
        print("  SKIP  Jane Eyre file not present")
        return
    doc = segment(load(src))
    results = {r.variant.name: r for r in
               render_all(doc, ["verbatim", "body-only"])}

    v = results["verbatim"].stats["word_tokens"]
    b = results["body-only"].stats["word_tokens"]
    loss = 100.0 * (v - b) / v

    check("Jane Eyre: 38 chapters found",
          len([r for r in doc.regions if r.kind == "chapter"]) == 38)
    check("Jane Eyre: front matter found",
          any(r.label == FRONT_MATTER for r in doc.regions))
    check("Jane Eyre: no uncovered content", doc.coverage_gaps() == [])
    check("Jane Eyre: body-only loses <1% tokens", loss < 1.0, f"lost {loss:.2f}%")
    check("Jane Eyre: preface removed from body-only",
          "CURRER BELL" not in results["body-only"].text)
    check("Jane Eyre: first sentence intact",
          "There was no possibility of taking a walk that day."
          in results["body-only"].text)
    check("Jane Eyre: last sentence intact",
          "Amen; even so come, Lord Jesus!"
          in results["body-only"].text)


def main() -> int:
    print("\nCorpusPrep test suite\n" + "=" * 60)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"\n{name}")
            fn()
    print("\n" + "=" * 60)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed\n")
    if FAILED:
        for f in FAILED:
            print(f"  FAILED: {f}")
        print()
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
