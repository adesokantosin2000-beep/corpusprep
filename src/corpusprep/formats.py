"""
corpusprep.formats
==================

Extract plain text from container formats — .docx, .epub, .html — using the
standard library only. No pip install, which keeps the "runs on a bare Python"
property intact.

All three are structurally similar: a zip of XML (docx, epub) or a single XML-ish
document (html). In every case we walk the markup and emit one line per
paragraph, because paragraph structure is the one thing worth preserving —
the segmenter downstream depends on blank-line-delimited blocks.

**PDF lives in `corpusprep.pdf`, not here.** It was deliberately absent while
extraction produced hyphenated line-breaks, hard-wrapped lines, running heads
and scattered page numbers with nothing able to repair them — supporting import
before supporting repair lets people build bad corpora while trusting the tool,
which is worse than declining. De-hyphenation and reflow now exist, so it is
supported, in its own module because a PDF needs something no container format
does: a judgement about whether what was extracted is language at all.
"""

from __future__ import annotations

import html as _html
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

SUPPORTED = {".txt", ".text", ".docx", ".epub", ".html", ".htm", ".xhtml",
             ".md", ".markdown", ".mdown", ".mkd", ".pdf"}

# WordprocessingML / OPF namespaces
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"
OPF_NS = "{http://www.idpf.org/2007/opf}"


class UnsupportedFormat(Exception):
    """Raised for formats we deliberately do not handle."""


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def extract_docx(path: Path) -> tuple[str, dict]:
    """Return (text, meta) from a Word document.

    Paragraphs become lines. Headings are detected from the paragraph style
    name and emitted with blank lines around them, so the segmenter sees them
    as standalone blocks the way it would in a plain-text file.
    """
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "word/document.xml" not in names:
            raise UnsupportedFormat(
                "Not a Word document (word/document.xml missing). "
                ".doc files from Word 97-2003 are a different format and are "
                "not supported. Re-save the file as .docx."
            )
        xml = z.read("word/document.xml")

    root = ET.fromstring(xml)
    lines: list[str] = []
    n_head = 0

    for para in root.iter(f"{W}p"):
        # Style name, e.g. "Heading1", "Title"
        style = ""
        pr = para.find(f"{W}pPr")
        if pr is not None:
            st = pr.find(f"{W}pStyle")
            if st is not None:
                style = st.get(f"{W}val", "") or ""

        # Text runs; <w:tab/> and <w:br/> are structural, not textual
        parts: list[str] = []
        for node in para.iter():
            tag = node.tag
            if tag == f"{W}t":
                parts.append(node.text or "")
            elif tag == f"{W}tab":
                parts.append(" ")
            elif tag == f"{W}br":
                parts.append(" ")
        text = "".join(parts).strip()

        is_heading = bool(re.match(r"(Heading|Title|Subtitle)", style, re.I))
        if is_heading and text:
            n_head += 1
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text)
            lines.append("")
        else:
            lines.append(text)

    return "\n".join(lines), {
        "container": "docx",
        "paragraphs": len(lines),
        "styled_headings": n_head,
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "section", "article", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "figcaption", "td", "th",
}
DROP_TAGS = {"script", "style", "noscript", "head", "svg", "template"}


class _HTMLText(HTMLParser):
    """Collect visible text, one line per block element."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.buf: list[str] = []
        self.skip = 0
        self.headings = 0

    def _flush(self) -> None:
        t = "".join(self.buf).strip()
        self.buf.clear()
        if t:
            self.out.append(re.sub(r"[ \t]{2,}", " ", t))

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self._flush()
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                self.headings += 1
                self.out.append("")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self._flush()
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                self.out.append("")

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def close(self):
        super().close()
        self._flush()


def extract_html(source: str) -> tuple[str, dict]:
    p = _HTMLText()
    p.feed(source)
    p.close()
    text = "\n".join(p.out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, {"container": "html", "headings": p.headings}


# ---------------------------------------------------------------------------
# EPUB
# ---------------------------------------------------------------------------

def extract_epub(path: Path) -> tuple[str, dict]:
    """Return (text, meta) from an EPUB, following the spine reading order."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()

        # Locate the OPF via META-INF/container.xml
        opf_path = None
        if "META-INF/container.xml" in names:
            root = ET.fromstring(z.read("META-INF/container.xml"))
            rf = root.find(f".//{CONTAINER_NS}rootfile")
            if rf is not None:
                opf_path = rf.get("full-path")
        if opf_path is None:
            opf_path = next((n for n in names if n.endswith(".opf")), None)
        if opf_path is None:
            raise UnsupportedFormat("Not a readable EPUB (no OPF package file).")

        opf = ET.fromstring(z.read(opf_path))
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""

        # id -> href
        manifest = {}
        for item in opf.iter(f"{OPF_NS}item"):
            manifest[item.get("id")] = item.get("href")

        # Reading order from the spine
        order = []
        for ref in opf.iter(f"{OPF_NS}itemref"):
            href = manifest.get(ref.get("idref"))
            if href:
                order.append(base + href)

        if not order:
            order = [n for n in names if n.endswith((".xhtml", ".html", ".htm"))]

        chunks, files = [], 0
        for name in order:
            if name not in names:
                continue
            try:
                raw = z.read(name).decode("utf-8", errors="replace")
            except KeyError:
                continue
            txt, _ = extract_html(raw)
            if txt.strip():
                chunks.append(txt.strip())
                files += 1

    return "\n\n".join(chunks), {"container": "epub", "documents": files}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

#: A Markdown inline link: `[text](target)`.
#:
#: The target is not language and nobody typed it. Written non-greedily and
#: with a character class that stops at `)`, so two links on one line do not
#: swallow the prose between them.
MD_LINK = re.compile(r"\[([^\]]*)\]\(\s*<?([^)\s]*)>?[^)]*\)")
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
#: A bare URL sitting in running text.
MD_BARE_URL = re.compile(r"(?<![\(\[])\bhttps?://\S+")
#: Reference-style definitions: `[1]: https://…` on a line of their own.
MD_REF_DEF = re.compile(r"(?m)^\s{0,3}\[[^\]]+\]:\s*\S+.*$")
#: ATX headings, `## Like this`. The hashes are markup; the words are not.
MD_ATX = re.compile(r"(?m)^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
#: Emphasis, code spans and strikethrough — asterisks, backticks, tildes.
MD_EMPH = re.compile(r"(\*{1,3}|~~|`+)(?=\S)(.+?)(?<=\S)\1", re.S)

#: Underscore emphasis, which may NOT sit inside a word.
#:
#: CommonMark forbids intraword `_` for exactly the reason that bit here:
#: `snake_case` identifiers. Treating `_` like `*` turned the handle
#: `@michaelaseewald_v24` into `@michaelaseewaldv24`, silently renaming a
#: person — the first version of this reader corrupted a username while
#: removing 46% of the file it was meant to clean, which is the kind of quiet
#: damage this package exists to prevent.
#:
#: Usernames, hashtags and file paths are full of underscores, and social
#: media is precisely where this reader is most needed.
MD_EMPH_US = re.compile(r"(?<![^\W_])(_{1,3})(?=\S)(.+?)(?<=\S)\1(?![^\W_])", re.S)
#: Blockquote and list markers at the start of a line.
MD_MARKER = re.compile(r"(?m)^\s{0,3}(?:>+\s?|[-*+]\s+|\d{1,3}[.)]\s+)")
#: A table row or a rule made of punctuation.
MD_RULE = re.compile(r"(?m)^\s{0,3}(?:[-*_]\s?){3,}\s*$")


def extract_markdown(source: str) -> tuple[str, dict]:
    """Return (text, meta) from Markdown, keeping the words and dropping the markup.

    **This exists because a tester's corpus was 45% URL.**

    She exported an Instagram comment thread through a Markdown converter and
    cleaned it with CorpusPrep, which removed nothing. The file looks like this::

        [bymiracohen](https://www.instagram.com/bymiracohen/)
         [9 w](https://www.instagram.com/p/C6-u-LzNtxQ/c/18439282027191808/)
        Love what you're creating 🌍 fellow AI here navigating the world

    Loaded as plain text — which is what a `.md` file was, since nothing here
    read Markdown — every character of every link target became a word. Her
    twelve most frequent words were:

        https · www · instagram · com · c · gram · p · u · lzntxq ·
        shudu · explore · tags

    **Not one of them was typed by a human.** `lzntxq` is a fragment of the
    post's URL. After the targets are dropped the same file gives `that`,
    `shudu`, `ai`, `we`, `black` — which is her actual data.

    Nothing new in principle: `extract_html` has always discarded tags on the
    grounds that markup is not language. Markdown is markup with a friendlier
    face, and a tool that reads HTML but not Markdown has a gap rather than a
    boundary.

    **Link text is kept and the target discarded**, which is the one judgement
    here. `[@shudu.gram](https://instagram.com/shudu.gram/)` becomes
    `@shudu.gram`: the handle is something a person wrote and may well be the
    object of study, while the URL is scaffolding the converter added.
    """
    text = source
    text = MD_REF_DEF.sub("", text)
    text = MD_IMAGE.sub(r"\1", text)          # alt text is authored; the path is not
    text = MD_LINK.sub(r"\1", text)
    text = MD_BARE_URL.sub("", text)
    text = MD_RULE.sub("", text)
    text = MD_MARKER.sub("", text)

    headings: list[str] = []

    def _heading(m):
        headings.append(m.group(2))
        return m.group(2)

    text = MD_ATX.sub(_heading, text)
    # Emphasis last: the markers can wrap text the rules above have moved.
    for _ in range(3):                          # nested **_like this_**
        new = MD_EMPH_US.sub(r"\2", MD_EMPH.sub(r"\2", text))
        if new == text:
            break
        text = new

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n", {"container": "markdown", "headings": headings}


def extract(path: str | Path) -> tuple[str, dict]:
    """Extract plain text from a supported container format.

    Returns (text, meta). Raises UnsupportedFormat for anything else, with a
    message explaining why rather than a bare error.
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        # Reached only if something calls this directly with a PDF.
        # `importer.load` intercepts .pdf first and never gets here, so this
        # message is for a caller who has bypassed the front door.
        raise UnsupportedFormat(
            "PDF is not a container format and is not handled here. Use "
            "corpusprep.importer.load(), which routes PDFs to corpusprep.pdf, "
            "or call corpusprep.pdf.extract() directly."
        )
    if ext == ".doc":
        raise UnsupportedFormat(
            "Legacy .doc (Word 97-2003) is a binary format and is not "
            "supported. Open it in Word and re-save as .docx."
        )
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".epub":
        return extract_epub(path)
    if ext in {".md", ".markdown", ".mdown", ".mkd"}:
        raw = path.read_bytes()
        try:
            src = raw.decode("utf-8")
        except UnicodeDecodeError:
            src = raw.decode("cp1252", errors="replace")
        return extract_markdown(src)
    if ext in {".html", ".htm", ".xhtml"}:
        raw = path.read_bytes()
        try:
            src = raw.decode("utf-8")
        except UnicodeDecodeError:
            src = raw.decode("cp1252", errors="replace")
        return extract_html(src)

    raise UnsupportedFormat(
        f"Unsupported file type '{ext}'. "
        f"Supported: {', '.join(sorted(SUPPORTED))}"
    )


def is_container(path: str | Path) -> bool:
    """True if the file needs extraction rather than plain decoding."""
    return Path(path).suffix.lower() in {
        ".docx", ".epub", ".html", ".htm", ".xhtml",
        ".md", ".markdown", ".mdown", ".mkd",
    }
