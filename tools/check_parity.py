#!/usr/bin/env python3
"""
check_parity.py — prove the web app and the Python package agree.

The web version re-implements the segmentation logic in JavaScript so the page
loads instantly and works offline. That buys speed at the cost of having the
same rules written twice. This script is what stops the two drifting: it runs
the *same files* through both and compares every number.

Run it after touching either implementation.

    python check_parity.py                      # default fixtures
    python check_parity.py mytext.txt other.txt

Requires Node.js. If Node isn't installed the script says so and exits.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

WEB = ROOT / "docs" / "index.html"
VARIANTS = ["verbatim", "full", "body-only", "body-no-headings"]

# Node harness: pulls the engine out of the HTML and runs it headlessly.
NODE_HARNESS = r"""
const fs=require('fs'), path=require('path');

/* Container formats (.docx/.epub/.html) need a DOM. Browsers have one; Node
   does not, so those files are skipped unless jsdom happens to be installed.
   Plain .txt parity — the important case — always runs. */
let haveDOM=false;
for(const p of ['jsdom','/tmp/node_modules/jsdom']){
  try{ const {JSDOM}=require(p); global.DOMParser=new JSDOM("").window.DOMParser;
       global.Blob=require('buffer').Blob; haveDOM=true; break; }catch(e){}
}

const html=fs.readFileSync(process.argv[2],'utf8');
const eng=html.indexOf('const PG_HEADER=');
const engEnd=html.indexOf('/* =========================================================================\n   FORMATS');
const fmt=html.indexOf('class UnsupportedFormat');
const fmtEnd=html.indexOf('/* =========================================================================\n   APP');
if(eng<0||engEnd<0||fmt<0||fmtEnd<0){
  console.error('could not locate engine/format blocks in index.html');process.exit(2);}
const M=new Function(html.slice(eng,engEnd)+html.slice(fmt,fmtEnd)+
  '; return {segment,render,PRESETS,coverageGaps,countTT,extractFile,'+
  'findFurnitureIn,looksLikePageNumber,findCatchwords,findFootnotesIn};')();

const CONTAINER=/\.(docx|epub|html|htm|xhtml)$/i;

(async()=>{
  const out={_haveDOM:haveDOM,_skipped:[]};
  for(const f of process.argv.slice(3)){
    let text;
    if(CONTAINER.test(f)){
      if(!haveDOM){ out._skipped.push(path.basename(f)); continue; }
      const buf=fs.readFileSync(f);
      const ab=buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength);
      text=(await M.extractFile(path.basename(f),ab)).text;
    } else {
      text=fs.readFileSync(f).toString('utf8');
      if(text.charCodeAt(0)===0xFEFF) text=text.slice(1);
    }
    text=text.replace(/\r\n/g,"\n").replace(/\r/g,"\n");
    const lines=text.split("\n");
    const seg=M.segment(lines);
    const res={};
    for(const p of ["verbatim","full","body-only","body-no-headings"]){
      const r=M.render(lines,seg.regions,M.PRESETS[p]);
      res[p]={tokens:r.stats.tokens,types:r.stats.types};
    }
    // Furniture is detected on every file, including those with none. A text
    // with no running heads must produce an empty set on both sides; silent
    // disagreement about *absence* is as much a drift as one about presence.
    const fu=M.findFurnitureIn(lines,seg.regions);
    out[path.basename(f)]={
      furniture:[...fu.furniture].sort((a,b)=>a-b).join(","),
      catchwords:[...fu.catchwords].sort((a,b)=>a-b).join(","),
      footnotes:M.findFootnotesIn(lines,seg.regions)
        .map(f=>f.label+":"+(f.markerLine||0)+">"+(f.bodyStart||0)+":"+(f.paired?1:0))
        .sort().join(","),
      furniture_page:Math.round(fu.pageLength*10)/10,
      regions:seg.regions.length,
      chapters:seg.regions.filter(r=>r.kind==='chapter').length,
      labels:seg.regions.map(r=>r.label).join(","),
      titles:seg.regions.map(r=>r.title).join("|"),
      gaps:M.coverageGaps(lines,seg.regions).length,
      source_tokens:M.countTT(text).tokens,
      variants:res};
  }
  console.log(JSON.stringify(out));
})();
"""


def run_python(files: list[Path]) -> dict:
    from corpusprep import BUILTIN, load, render, segment
    from corpusprep.document import count_tokens_types
    from corpusprep.footnotes import find_in_document as find_footnotes
    from corpusprep.furniture import find_in_document

    out = {}
    for f in files:
        doc = segment(load(f))
        marked, _cands, page, _catch = find_in_document(doc)
        cw = sorted(m.line for m in _catch if m.accepted)
        fn = sorted(f"{f.label}:{f.marker_line or 0}>{f.body_start or 0}:"
                    f"{1 if f.paired else 0}" for f in find_footnotes(doc))
        res = {}
        for v in VARIANTS:
            r = render(doc, BUILTIN[v])
            res[v] = {"tokens": r.stats["word_tokens"], "types": r.stats["word_types"]}
        t, _ = count_tokens_types(doc.text)
        out[f.name] = {
            "furniture": ",".join(str(i) for i in sorted(marked)),
            "catchwords": ",".join(str(i) for i in cw),
            "footnotes": ",".join(fn),
            "furniture_page": round(page, 1),
            "regions": len(doc.regions),
            "chapters": len([r for r in doc.regions if r.kind == "chapter"]),
            "labels": ",".join(r.label for r in doc.regions),
            "titles": "|".join(r.title for r in doc.regions),
            "gaps": len(doc.coverage_gaps()),
            "source_tokens": t,
            "variants": res,
        }
    return out


def run_node(files: list[Path]) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(NODE_HARNESS)
        harness = fh.name
    try:
        proc = subprocess.run(
            ["node", harness, str(WEB), *[str(f) for f in files]],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        print("Node.js not found. Install Node to run the parity check.")
        print("The web app itself does not need Node — this script does.")
        sys.exit(3)
    finally:
        os.unlink(harness)

    if proc.returncode != 0:
        print("Node harness failed:\n" + proc.stderr)
        sys.exit(3)
    return json.loads(proc.stdout)


def main(argv: list[str]) -> int:
    if not WEB.exists():
        print(f"Web app not found at {WEB}")
        return 2

    if len(argv) > 1:
        files = [Path(a) for a in argv[1:]]
    else:
        fx = ROOT / "tests" / "fixtures"
        files = [fx / "CBronte_Jane.txt", fx / "pg_marked.txt",
                 # The only fixture containing running heads. Without it the
                 # furniture comparison below would pass on empty sets, which
                 # proves nothing.
                 fx / "scanned_novel.txt",
                 # Catchwords. Also the negative case for the other fixtures,
                 # which must yield none.
                 fx / "early_modern.txt",
                 # Real text. The negative control a generator cannot supply.
                 fx / "pg9405_ballads.txt",
                 fx / "romeo_juliet.txt",
                 # Real footnotes, with labels restarting every chapter.
                 fx / "pg1232_prince.txt",
                 fx / "sample.docx", fx / "sample.epub", fx / "sample.html"]

    files = [f for f in files if f.exists()]
    if not files:
        print("No input files found.")
        return 2

    js = run_node(files)
    skipped = js.pop("_skipped", [])
    have_dom = js.pop("_haveDOM", False)
    files = [f for f in files if f.name not in skipped]
    py = run_python(files)

    print(f"\nParity check — Python package vs web app\n{'=' * 62}")
    if skipped:
        print(f"\n  Skipped (Node has no DOM; install jsdom to include them):")
        print(f"    {', '.join(skipped)}")

    ok = True
    scalar = ["regions", "chapters", "gaps", "source_tokens", "furniture_page"]

    for name in py:
        print(f"\n{name}")
        for k in scalar:
            match = py[name][k] == js[name][k]
            ok &= match
            flag = "OK  " if match else "DIFF"
            print(f"  {flag}  {k:<16} python={py[name][k]}  js={js[name][k]}")

        for k in ["labels", "titles"]:
            match = py[name][k] == js[name][k]
            ok &= match
            print(f"  {'OK  ' if match else 'DIFF'}  {k + ' sequence':<16}")

        # Compared as exact line-number sets. A count would hide the case where
        # both sides find the same number of lines but disagree about which.
        # Compared separately, not merged. Two rules disagreeing in opposite
        # directions would cancel out in a union and read as agreement.
        for field in ("furniture", "catchwords", "footnotes"):
            a = set(filter(None, py[name][field].split(",")))
            b = set(filter(None, js[name][field].split(",")))
            ok &= a == b
            detail = f"{len(a)} lines" if a == b else \
                f"python-only={sorted(a - b)[:6]} js-only={sorted(b - a)[:6]}"
            print(f"  {'OK  ' if a == b else 'DIFF'}  {field + ' lines':<16} {detail}")

        for v in VARIANTS:
            a, b = py[name]["variants"][v], js[name]["variants"][v]
            match = a == b
            ok &= match
            print(f"  {'OK  ' if match else 'DIFF'}  {v:<16} "
                  f"python={a['tokens']:,}/{a['types']:,}  "
                  f"js={b['tokens']:,}/{b['types']:,}")

    print("\n" + "=" * 62)
    print("  PASS — the two implementations agree\n" if ok
          else "  FAIL — implementations have drifted, fix before shipping\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
