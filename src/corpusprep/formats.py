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

**PDF is deliberately absent.** Extraction from PDF produces hyphenated
line-breaks, hard-wrapped lines, running headers and scattered page numbers —
exactly the problems CorpusPrep cannot yet fix. Supporting import before
supporting repair would let people build bad corpora while trusting the tool,
which is worse than declining. Add it once reflow and de-hyphenation exist.
"""

from __future__ import annotations

import html as _html
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

SUPPORTED = {".txt", ".text", ".docx", ".epub", ".html", ".htm", ".xhtml", ".md"}

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

def extract(path: str | Path) -> tuple[str, dict]:
    """Extract plain text from a supported container format.

    Returns (text, meta). Raises UnsupportedFormat for anything else, with a
    message explaining why rather than a bare error.
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        raise UnsupportedFormat(
            "PDF is not supported yet. PDF text extraction produces hyphenated "
            "line-breaks, hard-wrapped lines, running headers and stray page "
            "numbers, which are the exact problems CorpusPrep cannot yet repair. "
            "Support is planned once de-hyphenation and reflow exist. "
            "For now, export the PDF to .docx or .txt first."
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
        ".docx", ".epub", ".html", ".htm", ".xhtml"
    }
