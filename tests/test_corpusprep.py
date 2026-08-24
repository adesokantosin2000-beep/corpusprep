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
    # One known miss, and it is a deliberate trade. Page 8 is scanned as a
    # lone `B`, and a single character must be a real digit to count as a page
    # number, because a lone `B` is far more often a letter. A miss leaves a
    # visible artefact the user can report; a false positive deletes prose.
    check("at most one furniture line missed", len(truth - pred) <= 1,
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


def test_no_furniture_in_real_texts():
    """Real texts with no page furniture must yield none.

    This is the test that matters most, and the one a synthetic fixture cannot
    provide. `pg9405_ballads.txt` is a real ballad collection in which a
    dialogue poem of fixed stanza length repeats `HE`, `SHE` and two refrains
    thirteen times each, at a perfectly constant interval.

    An earlier version of the detector marked 63 lines of that verse as
    furniture. It had estimated a page length from a text with no pages, taking
    the most regular repeated line as its yardstick and then confirming that
    line against itself.
    """
    from corpusprep.furniture import find_in_document

    for name in ("pg9405_ballads.txt", "CBronte_Jane.txt", "romeo_juliet.txt",
                 "pg_marked.txt"):
        fx = FIXTURES / name
        if not fx.exists():
            continue
        doc = segment(load(fx))
        marked, _c, page, catch = find_in_document(doc)
        check(f"no furniture found in {name}", not marked,
              f"{len(marked)} lines marked, e.g. "
              f"{[doc.lines[i-1].strip()[:30] for i in sorted(marked)[:3]]}")
        check(f"no page structure claimed for {name}", page == 0,
              f"page length {page} estimated for a text with no page numbers")
        check(f"no catchwords in {name}",
              not [m for m in catch if m.accepted])


def test_page_numbers_must_ascend():
    """A refrain can be regular; only a page number counts upwards."""
    from corpusprep.furniture import ascending_run, page_number_value

    check("ascending kept", len(ascending_run([1, 2, 3, 4, 5])) == 5)
    check("out-of-order dropped", len(ascending_run([1, 2, 13, 4, 5])) == 4)
    check("constant sequence is not ascending",
          len(ascending_run([7, 7, 7, 7])) == 1)
    check("descending reduces to one", len(ascending_run([9, 7, 5, 3])) == 1)
    check("gaps allowed", len(ascending_run([1, 2, 5, 9, 14])) == 5)
    check("value read through OCR damage", page_number_value("l3") == 13)
    check("lone letter is not a value", page_number_value("B") is None)


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
    # 59 of the 60 furniture lines: page 8 is scanned as a lone `B` and is
    # deliberately not recovered. See test_furniture_detection.
    check("furniture detected on import", len(doc.furniture) == 59,
          f"got {len(doc.furniture)}")

    off = render(doc, BUILTIN["body-only"])
    check("default variant removes no furniture",
          off.stats["furniture_removed"] == 0)
    check("running head still present when not asked for",
          "JANE EYRE" in off.text)

    on = render(doc, _replace(BUILTIN["body-only"], drop_furniture=True))
    check("opt-in variant removes furniture",
          on.stats["furniture_removed"] == 59,
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
          len(js["furniture"]["detected_lines"]) == 59)


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


def test_footnote_pairing_on_real_text():
    """Machiavelli's *The Prince*, where the numbering restarts each chapter."""
    from corpusprep.footnotes import find_in_document

    fx = FIXTURES / "pg1232_prince.txt"
    if not fx.exists():
        print("  SKIP  Prince fixture not present")
        return

    doc = segment(load(fx))
    fns = find_in_document(doc)
    paired = [f for f in fns if f.paired]

    check("footnotes found in real text", len(paired) == 28, f"got {len(paired)}")
    check("nothing left unpaired here", len(fns) == len(paired),
          f"{len(fns) - len(paired)} unpaired")

    # Label 1 alone occurs fourteen times: seven markers and seven notes, in
    # seven different chapters. Pairing globally by label would join a marker
    # in one chapter to a note in another, so every pair must be local.
    ones = [f for f in paired if f.label == "1"]
    check("label 1 reused across chapters", len(ones) >= 6, f"got {len(ones)}")
    for f in ones:
        check(f"note for [1] at {f.body_start} follows its own marker",
              f.body_start > f.marker_line)
        check(f"and is near it, not in another chapter",
              f.body_start - f.marker_line < 200,
              f"gap of {f.body_start - f.marker_line} lines")


def test_stage_directions_are_not_footnotes():
    """A corpus of drama without its stage directions is a different work."""
    from corpusprep.footnotes import find_in_document

    fx = FIXTURES / "romeo_juliet.txt"
    if not fx.exists():
        return
    doc = segment(load(fx))
    bracketed = sum(l.count("[") for l in doc.lines)
    fns = find_in_document(doc)
    check("drama has bracketed material to trip over", bracketed > 0)
    check("but none of it is treated as a footnote", not fns,
          f"{len(fns)} found, e.g. {[f.label for f in fns[:3]]}")


def test_unpaired_marker_is_reported_not_removed():
    """The case where the tool does not know what it is looking at.

    `pg9405_ballads.txt` contains the line "That day made many [a] fatherlesse
    child". That `[a]` is editorial, not a footnote, and nothing answers it.
    """
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "pg9405_ballads.txt"
    if not fx.exists():
        return
    doc = analyse(fx)
    unpaired = [f for f in doc.footnotes if not f.paired]
    check("the lone bracketed label is reported", len(unpaired) == 1,
          f"got {len(unpaired)}")

    r = render(doc, _replace(BUILTIN["body-only"], footnotes="remove"))
    check("and survives even the remove route", "[a] fatherlesse" in r.text)
    check("while the real footnote marker is stripped", "[FN#1]" not in r.text)


def test_footnote_routes():
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "pg1232_prince.txt"
    if not fx.exists():
        return
    doc = analyse(fx)
    v = BUILTIN["body-only"]

    keep = render(doc, v)
    check("retain is the default", v.footnotes == "retain")
    check("retain leaves markers alone", "[1]" in keep.text)
    check("retain removes no notes", keep.stats["footnotes_removed"] == 0)

    gone = render(doc, _replace(v, footnotes="remove"))
    check("remove strips markers", "[1]" not in gone.text)
    check("remove drops note bodies",
          gone.stats["footnote_lines_removed"] > 0)
    # The marker comes off the word; the word stays.
    check("the annotated word survives", "intrattenere" in gone.text)
    check("no parallel file from remove", gone.footnote_text is None)

    out = render(doc, _replace(v, footnotes="extract"))
    check("extract produces a parallel file", out.footnote_text)
    check("with one line per note",
          len(out.footnote_text.strip().split(chr(10))) == 28)
    check("extract and remove leave the same corpus",
          out.stats["word_tokens"] == gone.stats["word_tokens"])


def _hyphen_key():
    import re as _re
    fk = Path(__file__).parent / "keys" / "hyphenated.hyphens"
    out = {}
    for raw in fk.read_text(encoding="utf-8").splitlines():
        s = raw.split("#")[0].strip()
        if s and "\t" in s:
            n, w = s.split("\t")
            out[int(n)] = w
    return out


def test_dehyphenation_detection():
    """Every broken word found, and no dash mistaken for one."""
    from corpusprep import dehyphenate as D

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        print("  SKIP  hyphenation fixture not present")
        return
    truth = _hyphen_key()
    lines = load(fx).lines
    breaks = D.find(lines)
    found = {b.line for b in breaks}

    check("every broken word found", not (truth.keys() - found),
          f"missed {sorted(truth.keys() - found)[:5]}")
    check("no dash treated as hyphenation", not (found - truth.keys()),
          f"spurious {sorted(found - truth.keys())[:5]}")


def test_dash_at_line_end_is_not_hyphenation():
    """*Jane Eyre* has 143 lines ending in a hyphen and no hyphenation at all.

    They are dashes used as punctuation. The discriminator is that a
    hyphenation hyphen is attached to its word; a dash is preceded by a space.
    Without this guard all 143 would be mangled.
    """
    from corpusprep import dehyphenate as D

    fx = FIXTURES / "CBronte_Jane.txt"
    if not fx.exists():
        return
    lines = load(fx).lines
    ending = sum(1 for l in lines if l.rstrip().endswith("-"))
    check("the novel really does end lines with hyphens", ending > 100,
          f"only {ending}")
    check("but none is treated as a broken word", not D.find(lines),
          f"{len(D.find(lines))} false breaks")


def test_dehyphenation_never_wrong_when_it_acts():
    """The acceptance criterion: accurate, with the remainder flagged."""
    from corpusprep import dehyphenate as D

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    truth = _hyphen_key()
    lines = load(fx).lines

    for label, extra in (("own vocabulary", None),
                         ("whole novel", D.vocabulary(load(FIXTURES / "CBronte_Jane.txt").lines))):
        breaks = D.find(lines, extra_vocab=extra)
        decided = [b for b in breaks if not b.needs_review]
        wrong = [b for b in decided
                 if truth.get(b.line, "").lower() != b.resolved.lower()]
        check(f"never wrong when it decides ({label})", not wrong,
              f"{len(wrong)} wrong, e.g. {[(b.line, b.resolved) for b in wrong[:3]]}")
        check(f"it does decide a useful share ({label})",
              len(decided) >= len(breaks) * 0.4,
              f"only {len(decided)} of {len(breaks)}")

    # More evidence must never mean fewer decisions.
    few = len([b for b in D.find(lines) if not b.needs_review])
    many = len([b for b in D.find(lines, extra_vocab=D.vocabulary(
        load(FIXTURES / "CBronte_Jane.txt").lines)) if not b.needs_review])
    check("more vocabulary resolves more cases", many > few, f"{few} -> {many}")


def test_real_compounds_keep_their_hyphen():
    """`half-comprehended` must not become `halfcomprehended`."""
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    truth = _hyphen_key()
    compounds = [w for w in truth.values() if "-" in w]
    check("the fixture contains real compounds", len(compounds) >= 5)

    doc = analyse(fx)
    out = render(doc, _replace(BUILTIN["verbatim"], dehyphenate=True))
    for w in compounds:
        check(f"{w} keeps its hyphen", w.replace("-", "") not in out.text)


def test_dehyphenation_leaves_no_word_split():
    """Consecutive broken lines must all be repaired, not just the first."""
    import re as _re
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    doc = analyse(fx)
    out = render(doc, _replace(BUILTIN["verbatim"], dehyphenate=True))
    left = [l for l in out.text.split("\n") if _re.search(r"\w-$", l)]
    check("no word left split across lines", not left,
          f"{len(left)} remain, e.g. {left[:2]}")
    check("dashes still there", any(l.endswith(" -") for l in out.text.split("\n")))


def test_dehyphenation_is_off_by_default():
    from corpusprep.variants import BUILTIN
    for name, v in BUILTIN.items():
        check(f"{name} does not dehyphenate by default", not v.dehyphenate)


def test_review_queue_round_trip():
    """Write a queue, read it back, get the same items."""
    import tempfile
    from corpusprep import analyse, review

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    doc = analyse(fx)
    items = review.from_document(doc)
    check("the queue has items to review", len(items) > 10, f"{len(items)}")

    tmp = Path(tempfile.mkdtemp()) / "q.tsv"
    review.write(items, tmp)
    check("an untouched queue yields no decisions", not review.read(tmp))

    text = tmp.read_text(encoding="utf-8")
    answered = "\n".join(("join" + l[1:]) if l.startswith("?") else l
                          for l in text.splitlines())
    tmp.write_text(answered, encoding="utf-8")
    back = review.read(tmp)
    check("every answer reads back", len(back) == len(items),
          f"{len(back)} of {len(items)}")
    check("nothing outstanding on a second run",
          not review.outstanding(items, back))


def test_empty_queue_changes_nothing():
    """The property that makes the file safe to generate and experiment with."""
    from dataclasses import replace as _replace
    from corpusprep import analyse
    from corpusprep.variants import BUILTIN, render

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    v = _replace(BUILTIN["verbatim"], dehyphenate=True)
    plain = render(analyse(fx), v)
    with_empty = render(analyse(fx, {}), v)
    check("an empty decision set leaves output byte-identical",
          plain.text == with_empty.text)


def test_review_decisions_resolve_everything():
    """Answered on its merits, the queue takes the rule to complete accuracy."""
    from corpusprep import dehyphenate as D, review

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    truth = _hyphen_key()
    lines = load(fx).lines
    breaks = D.find(lines)

    decisions = {}
    for b in breaks:
        if b.needs_review and b.line in truth:
            decisions[("hyphen", b.hyphenated)] = (
                "keep" if "-" in truth[b.line] else "join")

    review.apply_to_breaks(breaks, decisions)
    wrong = [b for b in breaks
             if truth.get(b.line, "").lower() != b.resolved.lower()]
    check("all breaks correct after review", not wrong,
          f"{len(wrong)} wrong")
    check("nothing left flagged",
          not [b for b in breaks if b.needs_review])


def test_review_identity_is_content_not_line_number():
    """A decision must survive the lines moving underneath it."""
    from corpusprep import dehyphenate as D, review

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    lines = load(fx).lines
    first = next(b for b in D.find(lines) if b.needs_review)
    decisions = {("hyphen", first.hyphenated): "join"}

    # Shift every line down by inserting a header, as removing apparatus would.
    shifted = ["A NEW TITLE", "", ""] + lines
    breaks = D.find(shifted)
    moved = next(b for b in breaks if b.hyphenated == first.hyphenated)
    check("the item genuinely moved", moved.line != first.line,
          f"both at {moved.line}")
    review.apply_to_breaks(breaks, decisions)
    check("but the decision still applies", not moved.needs_review,
          "decision lost when lines shifted")


def test_review_exact_replacement():
    """The escape hatch for cases neither option covers."""
    from corpusprep import dehyphenate as D, review

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    breaks = D.find(load(fx).lines)
    one = next(b for b in breaks if b.needs_review)
    review.apply_to_breaks(breaks, {("hyphen", one.hyphenated): "Rimoth-Gilead"})
    check("an exact replacement is used verbatim",
          one.resolved == "Rimoth-Gilead", one.resolved)
    check("and the reason records that it was your choice",
          "your decision" in one.reason)


def test_prepare_writes_the_queue():
    import tempfile
    from corpusprep import prepare

    fx = FIXTURES / "hyphenated.txt"
    if not fx.exists():
        return
    out = Path(tempfile.mkdtemp())
    prepare(fx, out, ["verbatim"])
    q = out / "hyphenated__review.tsv"
    check("a review queue is written beside the output", q.exists())
    body = [l for l in q.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]
    check("and it has rows", len(body) > 10, f"{len(body)}")
    check("every row is tab-separated", all("\t" in l for l in body))


def test_version_is_single_sourced():
    """The package, the built page and the citation file must agree.

    They did not. The preprocessing log reported 0.1.0 while the web
    application reported 0.2.0, so two runs of the same tool produced logs
    claiming different provenance. In software whose entire proposition is that
    its output can be audited, that is a defect and not an untidiness.
    """
    import re as _re
    from corpusprep import __version__

    root = Path(__file__).resolve().parent.parent

    check("version looks like a version",
          _re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__)

    cff = (root / "CITATION.cff").read_text(encoding="utf-8")
    m = _re.search(r"^version:\s*(\S+)", cff, _re.M)
    check("CITATION.cff agrees", m and m.group(1) == __version__,
          f"cff says {m.group(1) if m else 'nothing'}, package says {__version__}")

    page = root / "docs" / "index.html"
    if page.exists():
        html = page.read_text(encoding="utf-8")
        check("the built page agrees",
              f'CORPUSPREP_VERSION="{__version__}"' in html,
              "built page carries a different version")
        check("no version literal was left behind in the page",
              'version:"0.' not in html.replace(f'"{__version__}"', ""))

    # Exactly one file may carry the literal.
    carriers = []
    for f in (root / "src" / "corpusprep").glob("*.py"):
        if _re.search(r'__version__\s*=\s*"', f.read_text(encoding="utf-8")):
            carriers.append(f.name)
    check("exactly one file defines the version", carriers == ["_version.py"],
          str(carriers))


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
