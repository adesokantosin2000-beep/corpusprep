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
  '; return {segment,render,PRESETS,coverageGaps,countTT,extractFile};')();

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
    out[path.basename(f)]={
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

    out = {}
    for f in files:
        doc = segment(load(f))
        res = {}
        for v in VARIANTS:
            r = render(doc, BUILTIN[v])
            res[v] = {"tokens": r.stats["word_tokens"], "types": r.stats["word_types"]}
        t, _ = count_tokens_types(doc.text)
        out[f.name] = {
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
    scalar = ["regions", "chapters", "gaps", "source_tokens"]

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
