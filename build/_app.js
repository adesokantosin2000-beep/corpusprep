/* =========================================================================
   APP
   ========================================================================= */

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let DOC=null, CFG=null, RESULT=null, USER=null;

/* Cleaning is never automatic. Loading a file segments and displays it; no
   output exists until the user requests it. CLEANED tracks whether RESULT
   reflects the current selection, so changing a preset marks it stale rather
   than silently regenerating. */
let CLEANED=false;

/* Compact label for the margin of the segmentation view. Defined here rather
   than on LABELS so the engine block stays untouched by presentation. */
const SHORT={pg_header:"Apparatus", pg_licence:"Licence", front_matter:"Front matter",
             body:"Body", back_matter:"Back matter", unknown:"Unclassified"};

/* ---- capabilities -------------------------------------------------------
   `ready:false` entries are specified in the design but not implemented. They
   are shown, and marked, deliberately: a researcher who discovers a missing
   capability mid-project trusts the tool less than one who was told up front.
   Update these flags as the stages land. */
/* What this version does, and what it does not.

   **This list went stale in the direction that flatters, which is the
   direction that matters.** It existed so that a researcher meets the limits
   before choosing the tool rather than halfway through a project, and for
   three releases it carried page furniture, de-hyphenation and reflow as
   "planned" after all three had shipped — while describing de-hyphenation as
   "wordlist-validated", which is precisely the approach that was tried,
   measured and rejected.

   Reported by the user, not by any test. It is checked now: the test suite
   asserts that everything marked available is reachable, and the release
   checklist includes this list.

   A capability list that is not maintained is worse than none, because it is
   read as a claim about the present. */
const CAPABILITIES=[
  {ready:1, t:"Detects front matter and back matter",
   d:"Title pages, prefaces, dramatis personae, contents, appendices and indexes."},
  {ready:1, t:"Segments chapters and sections",
   d:"Chapter, Book, Part, Act and Scene divisions, numbered sections and bare numeral runs. Headings split across two lines, or welded to the front of a page in scanned text, are also found. The division words of several other languages are recognised too \u2014 Kapitel, Glava, Kapitola and their neighbours \u2014 from a fixed list, which is only as wide as the list: a language whose word is absent yields no structure and the report says so."},
  {ready:1, t:"Recovers chapters from running heads",
   d:"For scans where OCR destroyed every heading, the chapter titles are read from the head repeated on each page."},
  {ready:1, t:"Identifies publisher and licence apparatus",
   d:"Gutenberg headers, licence text and transcriber credits, whether or not sentinel markers are present."},
  {ready:1, t:"Identifies digitisation apparatus",
   d:"Internet Archive and Google Books notices, and pages the scanner itself reports as unreadable."},
  {ready:1, t:"Identifies page numbers, headers and footers",
   d:"Detected by regularity rather than appearance, so a refrain is never mistaken for a running head. Its measured figure comes from a generated scan rather than a hand-marked real one, which is why no preset removes what it finds: off unless requested, with every line proposed for removal listed with its grounds."},
  {ready:1, t:"Detects catchwords",
   d:"The early modern practice of printing the next page's first word at the foot of the page. Measured against a generated fixture only, where it produced three false positives, so read them before removing them."},
  {ready:1, t:"Detects footnotes",
   d:"Keep them, remove them, or extract them to a parallel file. A marker counts only when a note carries the same label, so stage directions are left alone."},
  {ready:1, t:"Rejoins hyphenated line breaks",
   d:"Settled from the document\u2019s own vocabulary rather than a bundled wordlist, which recognises only 65% of the word types in a Victorian novel. Whatever cannot be settled keeps the hyphen as printed."},
  {ready:1, t:"Reflows hard-wrapped paragraphs",
   d:"99.5% of paragraphs recovered exactly in measurement. Verse, drama and tabular material are identified first and left alone."},
  {ready:1, t:"Preserves or removes structural elements on request",
   d:"Retain or remove any section. Five presets are provided, or sections may be selected individually."},
  {ready:1, t:"Reads TXT, Markdown, DOCX, EPUB and HTML",
   d:"Encoding, byte-order marks and line endings resolved on import. Markdown link targets are discarded and the link text kept, because a URL is not language."},
  {ready:1, t:"Detects interface furniture",
   d:"Experimental. The labels an application prints around text a person wrote \u2014 Like, Reply, 2 likes, View replies. Found by position rather than by word, since all of those are ordinary English: a control sits after the text of a record, a one-word comment does not. Nothing is claimed unless the file itself is shaped like a scraped feed. Validated so far against one synthetic thread only; detected and reported, never removed."},
  {ready:1, t:"Records every decision in a log",
   d:"Markdown and JSON, including token and type counts, suitable for citation. A run in which no rule fires says which rules were tried and why each declined, rather than reporting a zero."},
  {ready:1, t:"Reads PDF",
   d:"Page boundaries are taken from the file, so running heads and page numbers are found from a stated fact rather than an inferred one. A PDF whose text layer is unreadable is refused with the reason rather than returned as noise. This is the one feature that needs the internet: pdf.js is fetched once, on demand. Your document is never uploaded."},
  {ready:0, t:"Repairs OCR characters",
   d:"Broken ligatures, stray marks and mis-scanned characters. Damaged pages are currently identified and reported, not corrected."},
  {ready:0, t:"Detects titled sections without numbering",
   d:"A collection whose parts are titled but neither numbered nor introduced by a division word currently yields no structure, and the report says so."},
];

const TICK_ON=`<svg class="tick" width="14" height="14" viewBox="0 0 24 24" fill="none"
  stroke="#37564a" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 6L9 17l-5-5"/></svg>`;
const TICK_OFF=`<svg class="tick" width="14" height="14" viewBox="0 0 24 24" fill="none"
  stroke="#a09a8e" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"
  stroke-dasharray="3 3"/></svg>`;

function drawRegister(){
  if(!REGISTER_URL) return;                    // nothing configured, nothing shown
  const link=`<a href="${REGISTER_URL}" target="_blank" rel="noopener noreferrer">`;
  const gate=$("#reg-gate");
  if(gate) gate.innerHTML=
    `Optional: ${link}tell us you are using CorpusPrep</a>, or ask to hear when `+
    `it changes. Opens a form in a new tab. Nothing is sent from this page.`;
  const side=$("#reg-side");
  if(side) side.innerHTML=
    `${link}Tell us you are using this</a> \u00b7 optional, opens in a new tab.`;
}

function drawCapabilities(){
  const ready=CAPABILITIES.filter(c=>c.ready).length;
  $("#cap-count").textContent=`${ready} available, ${CAPABILITIES.length-ready} planned`;
  $("#caps").innerHTML=CAPABILITIES.map(c=>`
    <div class="cap ${c.ready?"":"soon"}">
      ${c.ready?TICK_ON:TICK_OFF}
      <div class="body">
        <div class="t">${c.t}${c.ready?"":'<span class="tag">planned</span>'}</div>
        <div class="d">${c.d}</div>
      </div></div>`).join("");
}

/* ---- local persistence -------------------------------------------------
   Held on this machine only. No server exists, so nothing is transmitted;
   this is what provides continuity between sessions without uploading a
   single line of anyone's corpus. */
/* ---- optional registration --------------------------------------------
   Where to send someone who wants to say they are using this, or to hear when
   it changes. One form serves both: splitting them into two links splits the
   reader's attention and asks twice for the same thing.

   **Empty by default, and nothing renders when it is empty**, so a fork of
   this repository does not quietly point its users at somebody else's form.
   Set it to the URL of a form you own — any service will do; the page only
   ever links out to it.

   Three rules this link must not break, because they are the tool's whole
   proposition:

     - It is a LINK. The page transmits nothing, ever. Not the reader's name,
       not the file they opened, not the fact that they opened one.
     - It is not prefilled. Prefilling would put whatever they typed into the
       URL, so clicking would send it — a silent transmission wearing the
       clothes of a convenience.
     - It is optional and says so. A researcher who cannot register, because
       their ethics approval or their institution says not to, must lose
       nothing by ignoring it.

   Suggested fields for the form: name, institution, email, what they are
   preparing, and a tick-box for release announcements. The last one is what
   turns "who is using it" into "who can be told when it changes".          */
const REGISTER_URL="https://forms.gle/yBA7dzXp9zacZabP9";

const STORE="corpusprep.v1";
function load_(){ try{return JSON.parse(localStorage.getItem(STORE))||{}}catch(e){return {}} }
function save_(o){ try{localStorage.setItem(STORE,JSON.stringify(o))}catch(e){} }
function remember(patch){ save_({...load_(),...patch}); }

/* ---- recent files: off ------------------------------------------------
   The list holds a filename and a token count so a returning reader
   recognises what they last worked on. It cannot do the thing everyone
   expects of it — reopen the work — because a browser cannot read a file
   again without the reader choosing it, and nothing here ever held the file.

   Every reader will click it expecting their cleaned text back, and every one
   of them will be disappointed. That is not a fault to fix; it is what the
   feature is.

   The deciding argument is not the disappointment, it is the storage. **This
   is the only place in the tool that keeps anything about the reader's
   corpus.** A filename can be an informant's pseudonym or an unpublished
   title, and it was sitting in browser storage on what may well be a shared
   machine, in a tool whose whole proposition is that the reader's material
   stays under their control.

   Hidden rather than deleted: the code, the markup and the tests all remain,
   and this flag is the only thing between them and a working list. If a
   version ever remembers a file's *settings* — so that re-choosing it returns
   the reader to their preset and selections — the recognition becomes worth
   something and this can come back.

   Off means off: nothing new is recorded, and anything already stored on a
   reader's machine is purged the next time they open the page. Hiding the
   panel while leaving the names behind would keep the liability and lose the
   feature, which is the worst of both. */
const RECENT_LIST=false;

function pushRecent(name,tokens){
  if(!RECENT_LIST) return;
  const s=load_(), list=(s.recent||[]).filter(r=>r.name!==name);
  list.unshift({name,tokens,at:Date.now()});
  save_({...s,recent:list.slice(0,6)});
  drawRecent();
}
function drawRecent(){
  if(!RECENT_LIST){
    // Purge on sight, not merely hide. A reader who used an earlier version
    // has filenames stored on this machine and never agreed to keep them.
    const s=load_();
    if(s.recent) save_({...s,recent:undefined});
    const wrap=$("#recent-wrap");
    if(wrap) wrap.style.display="none";
    const g=$("#guide");
    if(g&&!DOC) g.style.display="";
    return;
  }
  const list=load_().recent||[];
  const guide=$("#guide");
  if(!list.length){
    // Emptied, not just hidden. Hiding the wrapper left the last row sitting
    // in the DOM, where a stylesheet change or a screen reader would still
    // find the filename it was supposed to have forgotten.
    $("#recent").innerHTML="";
    $("#recent-wrap").style.display="none";
    if(guide&&!DOC) guide.style.display="";   // first run: guidance fills the space
    return;
  }
  if(guide&&!DOC) guide.style.display="none"; // returning user: recents replace it
  $("#recent-wrap").style.display="";
  /* These were `<button>` elements with the tooltip "Reopen this file from
     disk to load it again" and no click handler anywhere in the file. They
     looked like controls, promised an action, and did nothing — and there was
     no way to remove an entry either.

     **A browser cannot reopen a file by name.** Nothing here ever held the
     file: only its name and token count, so that a returning reader recognises
     what they worked on. Re-reading it needs the reader to choose it, which is
     the file picker. So the button now opens the picker and the tooltip says
     that, rather than implying the tool can do something it cannot.

     The list is per-machine and holds six entries. Removing one matters more
     than it looks: the name of a file can itself be sensitive — an informant's
     pseudonym, an unpublished title — and a reader on a shared machine needs
     to be able to take it off the screen. */
  $("#recent").innerHTML=list.map((r,i)=>`
    <div class="rec-row">
      <button data-open="${i}" title="Choose this file again — the browser cannot reopen it for you">
        <span class="t">${esc(r.name)}</span>
        <span class="d">${r.tokens.toLocaleString()}</span>
      </button>
      <button class="rec-x" data-forget="${i}"
              title="Remove ${esc(r.name)} from this list" aria-label="Remove ${esc(r.name)} from this list">&times;</button>
    </div>`).join("");

  $$("#recent [data-open]").forEach(b=>b.onclick=()=>$("#file").click());
  $$("#recent [data-forget]").forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    forgetRecent(+b.dataset.forget);
  });
}

function forgetRecent(i){
  const s=load_(), list=(s.recent||[]).slice();
  if(i<0||i>=list.length) return;
  list.splice(i,1);
  save_({...s,recent:list});
  drawRecent();
}

/* ---- sign in ---- */
function initials(n){
  const p=n.trim().split(/\s+/).filter(Boolean);
  return ((p[0]&&p[0][0]||"?")+(p.length>1?p[p.length-1][0]:"")).toUpperCase();
}
function enter(user){
  USER=user;
  // A skipped sign-in must not overwrite a remembered one: the reader may be
  // going through the door labelled "without signing in" on a borrowed
  // machine, and their own name should still be there next time.
  remember(user ? {user, signedOut:false} : {signedOut:true});
  $("#gate").style.display="none";
  $("#app").style.display="flex";
  $("#who").innerHTML = user
    ? `<span class="avatar">${esc(initials(user.name))}</span>
       <span>${esc(user.name)}${user.inst?" · "+esc(user.inst):""}</span>
       <button class="linkish" id="who-out" title="Return to the sign-in screen">Sign out</button>`
    : `<span>Not signed in</span>
       <button class="linkish" id="who-out" title="Return to the sign-in screen">Sign in</button>`;
  const out=$("#who-out");
  if(out) out.onclick=()=>{
    USER=null;
    remember({signedOut:true});
    $("#app").style.display="none";
    $("#gate").style.display="";
  };
  drawRecent();
  if(CFG) refreshPreview();
}
$("#g-go").onclick=()=>{
  const name=$("#g-name").value.trim();
  if(!name){ $("#g-name").focus(); return }
  enter({name,inst:$("#g-inst").value.trim()});
};
["#g-name","#g-inst"].forEach(s=>$(s).addEventListener("keydown",
  e=>{if(e.key==="Enter")$("#g-go").click()}));
$("#g-skip").onclick=()=>enter(null);

/* ---- import ---- */
function decode(buf){
  const b=new Uint8Array(buf);
  let hadBom=false, enc="utf-8", conf=.9;
  if(b[0]===0xEF&&b[1]===0xBB&&b[2]===0xBF){hadBom=true;enc="utf-8-sig";conf=1}
  let text;
  try{ text=new TextDecoder("utf-8",{fatal:true}).decode(b); }
  catch(e){ enc="windows-1252"; conf=.5; text=new TextDecoder("windows-1252").decode(b); }
  const crlf=(text.match(/\r\n/g)||[]).length;
  const lf=(text.match(/\n/g)||[]).length-crlf;
  const cr=(text.match(/\r/g)||[]).length-crlf;
  const newline=crlf>=lf&&crlf>=cr?"\\r\\n":(cr>lf?"\\r":"\\n");
  if(text.charCodeAt(0)===0xFEFF){text=text.slice(1);hadBom=true}
  text=text.replace(/\r\n/g,"\n").replace(/\r/g,"\n");
  const repl=(text.match(/\uFFFD/g)||[]).length;
  return {lines:text.split("\n"),enc,hadBom,conf,newline,repl};
}

async function loadText(name,buf){
  let d, extraNotes=[];
  try{
    const ex=await extractFile(name,buf);
    if(ex){
      const text=ex.text.replace(/\r\n/g,"\n").replace(/\r/g,"\n");
      d={lines:text.split("\n"),enc:`utf-8 (from ${ex.meta.container})`,
         hadBom:false,conf:1,newline:"\\n",repl:(text.match(/\uFFFD/g)||[]).length,
         pageStarts:ex.meta.page_starts||null};
      if(ex.meta.container==="pdf"){
        extraNotes.push(`Read from PDF: ${ex.meta.note}`);
        // The page boundaries are the gift of this format. Every other input
        // makes the furniture rules infer where pages begin; a PDF states it.
        extraNotes.push(`Page boundaries were taken from the file itself `+
          `(${ex.meta.pdf_pages} pages), so running heads and page numbers are `+
          `identified from a stated boundary rather than one inferred from the `+
          `text.`);
      } else {
        extraNotes.push(`Text extracted from ${ex.meta.container}. Formatting, images `+
          `and footnotes were discarded. Paragraph structure was preserved.`);
      }
    } else d=decode(buf);
  }catch(err){
    // An unreadable PDF is not an error in the tool; it is a fact about the
    // file, and the reader needs the reason rather than a stack trace.
    showError((err instanceof UnsupportedFormat||err instanceof UnreadablePDF)
      ? err.message : `Could not read ${name}: ${err.message}`);
    return;
  }

  let seg=segment(d.lines);
  const tt=countTT(d.lines.join("\n"));
  // Detection, not removal. The result is shown for review and is removed
  // only if the reader ticks the box below the section list.
  const fu=findFurnitureIn(d.lines,seg.regions,d.pageStarts);
  const ui=findInterfaceIn(d.lines,seg.regions);
  if(ui.lines.size) extraNotes=[...extraNotes,
    `${ui.lines.size} lines look like interface furniture (the labels an `+
    `application printed, not text anyone wrote). Detected, not removed: the `+
    `log lists every one.`];
  DOC={name,...d,regions:seg.regions,notes:[...extraNotes,...seg.notes],
       interface:ui.lines,interfaceSeries:ui.series,
       furniture:fu.furniture,
       furnSeries:fu.candidates.filter(c=>c.accepted),
       catchwords:fu.catchwords,catchwordMatches:fu.catchwordMatches,
       footnotes:findFootnotesIn(d.lines,seg.regions),
       breaks:findHyphenBreaksIn(d.lines,seg.regions),
       pageLength:fu.pageLength,
       stats:{chars:d.lines.join("\n").length,lines:d.lines.length,
              tokens:tt.tokens,types:tt.types},
       gaps:coverageGaps(d.lines,seg.regions)};

  const pref=load_().preset;
  const start=(pref&&PRESETS[pref])?pref:"body-only";
  CFG=JSON.parse(JSON.stringify(PRESETS[start])); CFG.name=start;
  // Deliberately not remembered between documents. Furniture removal is a
  // judgement about one particular text, and a setting carried over from the
  // last file would delete lines in this one without being asked again.
  CFG.dropFurniture=0;
  // Footnotes are content, not printing debris. The default keeps them.
  CFG.footnotes="retain";
  CFG.dehyphenate=0;
  CFG.reflow=0;
  // Decisions are per-document and start empty. Carrying them between texts
  // would apply one book's judgements to another without asking.
  CFG.decisions=new Map();
  QUEUE=null; QPOS=0;
  $("#preset").value=start;

  $("#err").style.display="none";
  $("#run-wrap").style.display="";
  $("#side").style.display="";
  $("#guide").style.display="none";
  $("#welcome").style.display="none";
  $("#segview").style.display="";
  $("#hdr-doc").innerHTML=`<b>${esc(name)}</b>`;
  pushRecent(name,DOC.stats.tokens);
  CLEANED=false; RESULT=null;
  $("#run-clean").dataset.ran="";
  drawMeta(); drawToggles(); refreshPreview();
}

/* ---- what the segmenter found ---- */

/* Before cleaning, this panel describes the SOURCE and nothing else.
   
   It used to report how many sections would be removed and how many broken
   words had been settled, which is detection rather than cleaning and is
   true either way. Reported next to an unpressed button it still reads as a
   result, and the whole proposition here is that the reader decides what
   happens and then sees what happened. **A number that looks like an outcome
   is an outcome as far as the reader is concerned.**
   
   So the counts are held until the button has been pressed. What stays is
   what the reader needs in order to choose: the structure, the section list,
   and the options themselves. */
function drawSummary(){
  const R=DOC.regions;
  const n=k=>R.filter(r=>r.kind===k).length;
  const byLabel=l=>R.filter(r=>r.label===l).length;
  const chapters=n("chapter"), sections=n("section");
  const apparatus=byLabel("pg_header")+byLabel("pg_licence");
  const front=byLabel("front_matter"), back=byLabel("back_matter");
  const depth=Math.max(...R.map(r=>r.level));
  const unknown=byLabel("unknown");

  // Proportion bar: how the source divides by label.
  const words={};
  R.forEach(r=>{words[r.label]=(words[r.label]||0)
    +countTT(DOC.lines.slice(r.start,r.end).join("\n")).tokens});
  const total=Object.values(words).reduce((a,b)=>a+b,0)||1;
  const bar=LABELS.filter(l=>words[l.id]).map(l=>
    `<div class="bar-seg" style="width:${100*words[l.id]/total}%;background:${l.fg}"
      title="${l.name}: ${words[l.id].toLocaleString()} words"></div>`).join("");

  const cell=(v,k)=>`<div class="sum"><div class="v ${v?"":"zero"}">${
    typeof v==="number"?v.toLocaleString():v}</div><div class="k">${k}</div></div>`;

  $("#summary").innerHTML=`<div class="summary">
    <div class="summary-top">
      <span class="t">Segmentation summary</span>
      <span class="s">${DOC.regions.length} sections · ${
        depth>1?`${depth} levels of nesting`:"no nesting detected"}${
        unknown?` · ${unknown} unclassified`:""}</span>
    </div>
    <div class="bar-track">${bar}</div>
    <div class="sum-grid">
      ${cell(DOC.stats.tokens,"Words")}
      ${cell(chapters||sections,chapters?"Chapters":"Sections")}
      ${cell(front,"Front-matter blocks")}
      ${cell(back,"Back-matter blocks")}
      ${cell(apparatus,"Apparatus blocks")}
      ${CLEANED?cell(plannedDrops().length,"Removed"):""}
    </div>${furnitureNotice()}${footnoteNotice()}${hyphenNotice()}</div>`;
}

/* Words broken across a line break, and the queue for the ones the text
   cannot answer itself. */
function hyphenNotice(){
  if(!DOC.breaks||!DOC.breaks.length) return "";
  const flagged=DOC.breaks.filter(dhNeedsReview);
  const on=!!CFG.dehyphenate;
  const items=reviewItems(DOC.breaks,[]);
  const left=items.filter(i=>!CFG.decisions.has(i.kind+" "+i.key)).length;
  return `<div class="furn-notice ${on?"on":""}">
    <div class="furn-head">
      <span class="t">Words broken across lines</span>
      <span class="s">${CLEANED
        ? `${DOC.breaks.length} found · <b>${DOC.breaks.length-flagged.length}
           settled from this text itself</b>${
           left?` · ${left} kept exactly as printed`:""}`
        : "this text is hard-wrapped"}</span>
    </div>
    <p class="furn-lead">The line break is an artefact; the hyphen may be real.
      Each case is settled from this text's own vocabulary, and anything it
      cannot settle keeps the hyphen exactly as printed.${
      CLEANED&&left?` <b>${left}</b> did. Nothing is required of you.`:""}</p>
    <div class="fn-opts">
      <label class="fn-opt ${on?"on":""}">
        <input type="checkbox" id="dh-on" ${on?"checked":""}>
        <span class="fn-t">Rejoin broken words</span>
        <span class="fn-d">The hyphen is decided separately.</span></label>
      <label class="fn-opt ${CFG.reflow?"on":""}">
        <input type="checkbox" id="rf-on" ${CFG.reflow?"checked":""}>
        <span class="fn-t">Rejoin paragraphs</span>
        <span class="fn-d">Undoes fixed-width wrapping. Verse and drama are
          left alone.</span></label>
    </div>
    ${CLEANED&&left?`<div class="rv-bar">
      <button class="btn-sm ghost" id="rv-start">Look at the ${left} kept
        hyphen${left===1?"":"s"}</button>
      <button class="btn-sm ghost" id="rv-save">Download queue</button>
      <label class="btn-sm ghost file">Load queue
        <input type="file" id="rv-load" accept=".tsv,.txt" hidden></label>
    </div>`:CLEANED?`<div class="rv-bar">
      <button class="btn-sm ghost" id="rv-save">Download decisions</button></div>`:""}
  </div>`;
}

/* The reviewer. Keyboard-driven, because two hundred items answered by mouse
   is a job nobody finishes. */
let QUEUE=null, QPOS=0;

function reviewOpen(){
  QUEUE=reviewItems(DOC.breaks,[]).filter(i=>!CFG.decisions.has(i.kind+" "+i.key));
  QPOS=0;
  if(!QUEUE.length) return;
  $("#rv-modal").style.display="flex";
  reviewDraw();
  document.addEventListener("keydown",reviewKeys);
}

function reviewClose(){
  $("#rv-modal").style.display="none";
  document.removeEventListener("keydown",reviewKeys);
  QUEUE=null;
  drawToggles(); refreshPreview();
}

function reviewDecide(value){
  if(!QUEUE||QPOS>=QUEUE.length) return;
  const it=QUEUE[QPOS];
  if(value===null) CFG.decisions.delete(it.kind+" "+it.key);
  else CFG.decisions.set(it.kind+" "+it.key,value);
  QPOS++;
  if(QPOS>=QUEUE.length) reviewClose(); else reviewDraw();
}

function reviewKeys(e){
  if(e.key==="Escape"){ reviewClose(); return }
  const k=e.key.toLowerCase();
  if(k==="j"){ e.preventDefault(); reviewDecide("join") }
  else if(k==="k"){ e.preventDefault(); reviewDecide("keep") }
  else if(k==="s"||e.key==="ArrowRight"){ e.preventDefault(); QPOS++;
    if(QPOS>=QUEUE.length) reviewClose(); else reviewDraw() }
  else if(e.key==="ArrowLeft"){ e.preventDefault(); if(QPOS>0){QPOS--;reviewDraw()} }
}

function reviewDraw(){
  const it=QUEUE[QPOS];
  if(!it) return;
  const parts=it.key.split("-");
  const joined=parts.join("");
  $("#rv-body").innerHTML=`
    <div class="rv-count">${QPOS+1} of ${QUEUE.length}</div>
    <div class="rv-why">${esc(it.why)}</div>
    <div class="rv-choices">
      <button class="rv-pick" data-v="join">
        <kbd>J</kbd><span class="rv-word">${esc(joined)}</span>
        <span class="rv-lab">one word</span></button>
      <button class="rv-pick" data-v="keep">
        <kbd>K</kbd><span class="rv-word">${esc(it.key)}</span>
        <span class="rv-lab">keep the hyphen</span></button>
    </div>
    <div class="rv-help"><kbd>J</kbd> join · <kbd>K</kbd> keep ·
      <kbd>S</kbd> skip · <kbd>&larr;</kbd> back · <kbd>Esc</kbd> finish</div>`;
  $$("#rv-body .rv-pick").forEach(b=>
    b.addEventListener("click",()=>reviewDecide(b.dataset.v)));
}

function reviewSave(){
  const items=reviewItems(DOC.breaks,[]);
  for(const it of items){
    const d=CFG.decisions.get(it.kind+" "+it.key);
    if(d) it.decision=d;
  }
  const blob=new Blob([reviewWrite(items)],{type:"text/tab-separated-values"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download=(DOC.name.replace(/\.[^.]+$/,""))+"__review.tsv";
  a.click(); URL.revokeObjectURL(a.href);
}

/* What the footnote rule found, and the three things that can be done with it.

   A footnote is editorial content, not printing debris, so removal is not the
   obvious answer and the choice belongs to the reader. Unpaired labels are
   listed separately and are never removed by any route. */
function footnoteNotice(){
  if(!DOC.footnotes||!DOC.footnotes.length) return "";
  const paired=DOC.footnotes.filter(f=>f.paired);
  const loose=DOC.footnotes.length-paired.length;
  if(!paired.length&&!loose) return "";
  const route=CFG.footnotes||"retain";
  const opt=(v,label,desc)=>`<label class="fn-opt ${route===v?"on":""}">
      <input type="radio" name="fn-route" value="${v}" ${route===v?"checked":""}>
      <span class="fn-t">${label}</span><span class="fn-d">${desc}</span></label>`;
  return `<div class="furn-notice fn-notice">
    <div class="furn-head">
      <span class="t">Footnotes</span>
      <span class="s">${CLEANED
        ? `${paired.length} note${paired.length===1?"":"s"} matched to a marker${
          loose?` · ${loose} bracketed label${loose===1?"":"s"} could not be
          matched`:""}`
        : "this text carries footnotes"}</span>
    </div>
    <p class="furn-lead">A marker counts only when a note elsewhere carries the
      same label, so stage directions are left alone. Anything unmatched is
      never removed.${CLEANED&&loose?` ${loose} here.`:""}</p>
    <div class="fn-opts">
      ${opt("retain","Keep","Study the edition.")}
      ${opt("remove","Remove","Study the work.")}
      ${opt("extract","Extract to a second file","Study both.")}
    </div>
  </div>`;
}

/* What the furniture detector found, and on what grounds.

   Shown whether or not the reader intends to remove it. A detector that acts
   silently cannot be checked, and the cost of a wrong removal here is deleted
   prose. The reasoning is printed in full so that a mistaken judgement is
   visible before it is acted on rather than discovered afterwards. */
function furnitureNotice(){
  if(!DOC.furniture||!DOC.furniture.size) return "";
  const rows=DOC.furnSeries.map(c=>
    `<tr><td class="mono">${esc(c.text.slice(0,40))}</td>
         <td class="num">${c.lines.length}</td>
         <td class="why">${esc(c.reason)}</td></tr>`).join("")
    +(DOC.catchwords.size?`<tr>
        <td class="mono">(catchwords)</td>
        <td class="num">${DOC.catchwords.size}</td>
        <td class="why">each repeats the first word of the following page, on
          ${DOC.catchwords.size} of ${DOC.catchwordMatches.length} pages</td></tr>`:"");
  const on=!!CFG.dropFurniture;
  return `<div class="furn-notice ${on?"on":""}">
    <div class="furn-head">
      <span class="t">Possible page furniture</span>
      <span class="s">${CLEANED
        ? `${DOC.furniture.size} lines · estimated page length
           ${Math.round(DOC.pageLength)} lines`
        : "this text appears to come from printed pages"}</span>
    </div>
    <p class="furn-lead">Running heads and page numbers recur at the page
      interval; a refrain recurs irregularly and is left alone.${
      DOC.catchwords.size?" This text also uses catchwords.":""}${
      !CLEANED?" Every line proposed for removal is listed with its grounds"
      +" once cleaning has run.":""}</p>
    ${CLEANED?`<table class="furn-table">
      <thead><tr><th>Recurring line</th><th>Times</th><th>Grounds</th></tr></thead>
      <tbody>${rows}</tbody></table>`:""}
    <p class="furn-foot">${on
      ? "These lines will be removed when you clean. Every one is listed in the log."
      : "Nothing is removed unless you tick <b>Drop page furniture</b> in the section list."}
      This rule has so far been tested against constructed examples rather than
      real scans, so please check the list above before relying on it.</p>
  </div>`;
}

// Stamp the build version into the header on load.
(function(){
  const el=document.getElementById("hdr-ver");
  if(el&&typeof CORPUSPREP_VERSION!=="undefined") el.textContent="v"+CORPUSPREP_VERSION;
})();

document.addEventListener("click",e=>{
  if(!e.target) return;
  if(e.target.id==="rv-start"){ reviewOpen() }
  else if(e.target.id==="rv-save"){ reviewSave() }
  else if(e.target.id==="rv-close"){ reviewClose() }
});

document.addEventListener("change",e=>{
  if(e.target&&e.target.id==="rf-on"){
    CFG.reflow=e.target.checked?1:0;
    CFG.name=matchPreset()||"custom";
    $("#preset").value=CFG.name;
    refreshPreview();
    return;
  }
  if(e.target&&e.target.id==="dh-on"){
    CFG.dehyphenate=e.target.checked?1:0;
    CFG.name=matchPreset()||"custom";
    $("#preset").value=CFG.name;
    refreshPreview();
    return;
  }
  if(e.target&&e.target.id==="rv-load"&&e.target.files&&e.target.files[0]){
    e.target.files[0].text().then(txt=>{
      const parsed=reviewParse(txt);
      for(const [k,v] of parsed) CFG.decisions.set(k,v);
      drawToggles(); refreshPreview();
    });
    return;
  }
  if(e.target&&e.target.name==="fn-route"){
    CFG.footnotes=e.target.value;
    CFG.name=matchPreset()||"custom";
    $("#preset").value=CFG.name;
    refreshPreview();
  }
});

function showError(msg){ const e=$("#err"); e.textContent=msg; e.style.display=""; }
function handleFile(f){ if(f) f.arrayBuffer().then(b=>loadText(f.name,b)); }

/* ---- sidebar ---- */
function drawMeta(){
  const d=DOC,s=d.stats;
  let h=`<span class="fn">${esc(d.name)}</span>
   <dl>
     <dt>Characters</dt><dd class="num">${s.chars.toLocaleString()}</dd>
     <dt>Lines</dt><dd class="num">${s.lines.toLocaleString()}</dd>
     <dt>Word tokens</dt><dd class="num">${s.tokens.toLocaleString()}</dd>
     <dt>Word types</dt><dd class="num">${s.types.toLocaleString()}</dd>
     <dt>Encoding</dt><dd>${esc(d.enc)}${d.hadBom?" · BOM":""}</dd>
   </dl>`;
  const w=[];
  if(d.conf<.6) w.push(`Encoding identified with low confidence (${d.enc}). Inspect the output for character corruption.`);
  if(d.repl)    w.push(`${d.repl} undecodable byte(s) replaced. The source file may be damaged.`);
  d.notes.forEach(n=>w.push(n));
  if(d.gaps.length) w.push(`${d.gaps.length} uncovered content range(s). This indicates a fault in segmentation.`);
  $("#meta").innerHTML=h+w.map(x=>`<div class="warn">${esc(x)}</div>`).join("");
}

function drawToggles(){
  const counts={},words={};
  for(const r of DOC.regions){
    counts[r.label]=(counts[r.label]||0)+1;
    words[r.label]=(words[r.label]||0)+countTT(DOC.lines.slice(r.start,r.end).join("\n")).tokens;
  }
  $("#toggles").innerHTML=LABELS.filter(l=>counts[l.id]).map(l=>`
    <label class="toggle ${CFG.keep[l.id]?"":"off"}" data-l="${l.id}">
      <input type="checkbox" ${CFG.keep[l.id]?"checked":""}>
      <span class="swatch" style="background:${l.fg}"></span>
      <span>${l.name}</span>
      <span class="n">${words[l.id].toLocaleString()}</span>
    </label>`).join("")
    +`<label class="toggle ${CFG.dropHeadings?"":"off"}" data-l="__h">
        <input type="checkbox" ${CFG.dropHeadings?"checked":""}>
        <span class="swatch" style="background:var(--rule)"></span>
        <span>Drop heading lines</span></label>`
    +(DOC.furniture.size?`
      <label class="toggle ${CFG.dropFurniture?"":"off"}" data-l="__f">
        <input type="checkbox" ${CFG.dropFurniture?"checked":""}>
        <span class="swatch" style="background:var(--rule)"></span>
        <span>Drop page furniture</span>
        <span class="n">${DOC.furniture.size}</span>
      </label>`:"");

  $$("#toggles .toggle").forEach(el=>{
    el.querySelector("input").addEventListener("change",e=>{
      const k=el.dataset.l;
      if(k==="__h") CFG.dropHeadings=e.target.checked?1:0;
      else if(k==="__f") CFG.dropFurniture=e.target.checked?1:0;
      else CFG.keep[k]=e.target.checked?1:0;
      el.classList.toggle("off",!e.target.checked);
      CFG.name=matchPreset()||"custom";
      $("#preset").value=CFG.name;
      remember({preset:CFG.name});
      refreshPreview();
    });
  });
}

function matchPreset(){
  // A preset never drops furniture, so a selection that does is custom by
  // definition. Reporting a preset name here would mislabel the log.
  if(CFG.dropFurniture) return null;
  if(CFG.footnotes&&CFG.footnotes!=="retain") return null;
  if(CFG.dehyphenate||CFG.reflow) return null;
  for(const [n,p] of Object.entries(PRESETS)){
    if(p.dropHeadings!==CFG.dropHeadings) continue;
    if(LABELS.every(l=>!!p.keep[l.id]===!!CFG.keep[l.id])) return n;
  }
  return null;
}

/* Which sections the current selection would remove. Computed without
   rendering any text, so reviewing a preset is not the same as cleaning. */
function plannedDrops(){
  return DOC.regions.filter(r=>!CFG.keep[r.label]);
}

/* Called on load and whenever the selection changes. Updates the review
   surfaces only. Any previously produced output becomes stale. */
function refreshPreview(){
  if(CLEANED){ CLEANED=false; RESULT=null; }
  $("#preset-desc").textContent=PRESETS[CFG.name]?PRESETS[CFG.name].desc
    :"A custom selection of sections.";
  drawSummary(); drawStats(); drawRegions(); drawRunState(); drawGates();
}

/* Shortest time the working state stays visible.
   
   Cleaning a Gutenberg novel takes about 40 ms and a 45 MB scan several
   seconds, so on small files the indicator would flash and be missed, and on
   large ones the page would simply stop answering with no explanation. A floor
   makes the feedback consistent without inventing a delay: anything slower
   than this shows for exactly as long as it actually takes. */
const MIN_BUSY_MS=700;

/* The explicit action. Nothing above this line produces cleaned text. */
async function runClean(){
  const b=$("#run-clean");
  b.classList.add("busy");
  b.disabled=true;
  $("#run-label").textContent="Cleaning…";
  $("#run-note").textContent="Working through the text. Nothing has been "
    +"written yet.";

  // Yield twice so the browser paints the working state before the main
  // thread is occupied. One yield is not always enough: the style change and
  // the paint are separate frames, and a single setTimeout can land between
  // them, which showed the spinner only after the work had finished.
  await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(
    ()=>setTimeout(r,0))));

  const t0=performance.now();
  try{
    RESULT=render(DOC.lines,DOC.regions,CFG,DOC.furniture,DOC.footnotes);
    RESULT.base=render(DOC.lines,DOC.regions,PRESETS["verbatim"]).stats;
    CLEANED=true;
  }catch(e){
    b.classList.remove("busy"); b.disabled=false;
    $("#run-label").textContent="Clean text";
    $("#run-note").textContent="Cleaning failed: "+e.message
      +". The source text is untouched.";
    throw e;
  }

  const left=MIN_BUSY_MS-(performance.now()-t0);
  if(left>0) await new Promise(r=>setTimeout(r,left));

  b.classList.remove("busy");
  b.disabled=false;
  drawSummary(); drawStats(); drawRegions();
  drawCompare(); drawLog(); drawRunState(); drawGates();
}

function drawRunState(){
  const b=$("#run-clean"), n=$("#run-note");
  if(!DOC){ return }
  const drops=plannedDrops().length;
  const label=$("#run-label")||b;
  if(CLEANED){
    label.textContent="Cleaned";
    b.className="btn-run done";
    n.textContent="The cleaned text and its log are ready. Adjust the selection "
      +"above to clean again.";
  } else if(RESULT===null&&b.dataset.ran==="1"){
    label.textContent="Apply changes";
    b.className="btn-run stale";
    n.textContent="The selection has changed since the last run.";
  } else {
    label.textContent="Clean text";
    b.className="btn-run";
    n.textContent=drops
      ? `${drops} of ${DOC.regions.length} sections will be removed. Nothing is `
        +`produced until you run this.`
      : "No sections are currently marked for removal.";
  }
}

/* The comparison and log views describe an output that does not exist until
   cleaning has been run, so they are held closed until then. */
function drawGates(){
  const on=CLEANED;
  $("#gate-cmp").style.display=on?"none":"";
  $("#cmp-body").style.display=on?"":"none";
  $("#gate-log").style.display=on?"none":"";
  $("#logview").style.display=on?"":"none";
}

function drawStats(){
  if(!CLEANED){
    $("#stats").innerHTML=`<div class="fig" style="grid-column:1/-1">
      <div class="v zero">Not yet cleaned</div>
      <div class="k">Run cleaning to see the result</div></div>`;
    return;
  }
  const s=RESULT.stats,b=RESULT.base;
  const d=b.tokens?100*(s.tokens-b.tokens)/b.tokens:0;
  const cls=Math.abs(d)<3?"ok":Math.abs(d)<15?"warn":"bad";
  $("#stats").innerHTML=`
    <div class="fig"><div class="v">${s.tokens.toLocaleString()}<span class="d ${cls}">${d>=0?"+":""}${d.toFixed(1)}%</span></div>
      <div class="k">Word tokens</div></div>
    <div class="fig"><div class="v">${s.types.toLocaleString()}</div><div class="k">Word types</div></div>
    <div class="fig"><div class="v">${s.chars.toLocaleString()}</div><div class="k">Characters</div></div>
    <div class="fig"><div class="v">${s.kept}<span style="color:var(--faint)">/${DOC.regions.length}</span></div>
      <div class="k">Sections kept</div></div>`;
}

/* ---- segmentation ---- */
function drawRegions(){
  const counts={};
  for(const r of DOC.regions) counts[r.label]=(counts[r.label]||0)+1;
  const drops=plannedDrops().length;
  const cover=DOC.gaps.length?"warning: uncovered lines present"
                             :"every line accounted for";
  $("#seg-sub").textContent=CLEANED
    ? `${DOC.regions.length} sections identified · ${drops} removed by the `
      +`current selection · ${cover}`
    : `${DOC.regions.length} sections identified · ${cover}`;

  $("#legend").innerHTML=LABELS.filter(l=>counts[l.id]).map(l=>
    `<span><span class="swatch" style="background:${l.fg}"></span>${l.name}</span>`).join("");

  $("#regions").innerHTML=DOC.regions.map((r,i)=>{
    const l=LMAP[r.label], keep=!!CFG.keep[r.label];
    const txt=DOC.lines.slice(r.start,r.end);
    const prev=txt.slice(0,40).join("\n");
    const more=txt.length>40?`\n\n… ${txt.length-40} more lines`:"";
    const w=countTT(txt.join("\n")).tokens;
    const kids=childrenOf(DOC.regions,i);
    const shown=kids.length?subtreeWords(DOC.lines,DOC.regions,i):w;
    const size=kids.length?`${shown.toLocaleString()} w · ${kids.length} parts`
                          :`${w.toLocaleString()} w`;
    return `<div class="region ${keep?"":(CLEANED?"dropped":"unselected")}" data-i="${i}">
      <div class="region-head" style="padding-left:${(r.level-1)*26}px">
        <span class="bar" style="background:${l.fg}"></span>
        <span class="k" style="color:${l.fg}">${SHORT[r.label]||l.name}</span>
        <span class="t">${esc(r.title||r.kind)}</span>
        <span class="i">${r.start+1}–${r.end} · ${size}${
          keep||!CLEANED?"":` · <span class="removed">removed</span>`}</span>
      </div>
      <div class="region-body">${esc(prev)}${esc(more)}
        <div class="evid">${esc(r.evidence)} · confidence ${r.confidence.toFixed(2)}</div>
      </div></div>`;
  }).join("");

  $$("#regions .region-head").forEach(h=>
    h.addEventListener("click",()=>h.parentElement.classList.toggle("open")));
}

/* ---- compare ---- */
function drawCompare(){
  $("#src-i").textContent=`${DOC.stats.tokens.toLocaleString()} tokens`;
  $("#out-i").textContent=`${RESULT.stats.tokens.toLocaleString()} tokens · ${CFG.name||"custom"}`;

  const dropSet=new Set();
  RESULT.dropped.forEach(r=>{for(let i=r.start;i<r.end;i++) dropSet.add(i)});
  $("#src-t").innerHTML=DOC.lines.map((l,i)=>
    dropSet.has(i)?`<mark>${esc(l)}</mark>`:esc(l)).join("\n");
  $("#out-t").textContent=RESULT.text;

  const a=$("#src-t"),b=$("#out-t");
  let lock=false;
  const sync=(from,to)=>()=>{ if(lock)return; lock=true;
    const r=from.scrollTop/Math.max(1,from.scrollHeight-from.clientHeight);
    to.scrollTop=r*(to.scrollHeight-to.clientHeight); lock=false; };
  a.onscroll=sync(a,b); b.onscroll=sync(b,a);
}

/* ---- log ---- */
/* What to say when every rule declined.

   A tester cleaned a corpus of Instagram comments and the page told her two
   things: that 0 tokens had been removed, and that no structural headings were
   found. Both were true and neither was useful. Silence is not a result.

   Mirrors report.no_op_notes().                                            */
function noOpNotes(){
  const d=DOC,s=RESULT.stats;
  const fired=RESULT.dropped.length||s.furnitureRemoved||s.headsStripped||
              s.noteLines||s.hyphensJoined||s.hyphensFlagged||s.paragraphsJoined
              ||(d.interface&&d.interface.size)||(d.furniture&&d.furniture.size);
  if(fired) return [];
  const text=d.lines.filter(l=>l.trim()).map(l=>l.replace(/\s+$/,"").length)
                    .sort((a,b)=>a-b);
  const med=text.length?text[Math.floor(text.length/2)]:0;
  const labels=new Set(d.regions.map(r=>r.label));
  const out=[];
  if(!labels.has("pg_header")&&!labels.has("pg_licence"))
    out.push("**No Project Gutenberg apparatus.** The header and licence "+
      "blocks are matched verbatim, so this file did not come from Gutenberg, "+
      "or came from it already stripped.");
  out.push("**No structural headings.** Nothing matched `Chapter`, `Book`, "+
    "`Part`, `Act`, `Scene`, `Letter`, a roman numeral or a bare ascending "+
    "numeral standing on its own line. A text with no divisions is not a "+
    "defective text; it means body-only and verbatim are necessarily the "+
    "same file.");
  if(!d.furniture||!d.furniture.size)
    out.push("**No page furniture.** Running heads are found by their "+
      "*interval*, which needs an ascending page-number sequence to establish "+
      "a page length. Born-digital text has no pages, so this rule can never "+
      "fire on it.");
  if(!isWrapped(d.lines))
    out.push("**Nothing to rejoin.** The text is not hard-wrapped (median "+
      "line "+med+" characters, one line per paragraph), so reflow and "+
      "protected spans had no question to answer.");
  else
    out.push("**Nothing to rejoin.** Lines are short (median "+med+" "+
      "characters), which is the shape wrapped text has, but no block looked "+
      "like one paragraph broken across several lines. Short lines that are "+
      "each a whole utterance — a comment, a caption, a line of a transcript "+
      "— are not wrapped, and rejoining them would be damage.");
  out.push("**No word broken across a line.** De-hyphenation looks for a word "+
    "ending in a hyphen at a line end; there were none.");
  return out;
}

const NO_OP_CLOSING=
  "**What this means for your corpus.** The rules here are built for printed "+
  "books turned into text: Gutenberg files, PDF extractions, library scans. "+
  "Their apparatus — running heads, page numbers, editorial front matter, "+
  "hyphens at line ends — is what there is to remove. Text that was born "+
  "digital has none of it, and the honest answer is that your file is already "+
  "as clean as this tool can make it.\n\nIf your material carries a "+
  "different kind of apparatus — interface labels, timestamps, usernames, "+
  "boilerplate that repeats — that is worth reporting, because it is the sort "+
  "of thing a rule can be built for and none of the rules here were.";

function logMarkdown(){
  const d=DOC,s=RESULT.stats,b=RESULT.base;
  const delta=b.tokens?(100*(s.tokens-b.tokens)/b.tokens).toFixed(1):"0.0";
  let m=`# CorpusPrep: Preprocessing Log\n\n`;
  m+=`**Source:** \`${d.name}\`  \n`;
  m+=`**Generated:** ${new Date().toISOString().slice(0,16).replace("T"," ")}  \n`;
  if(USER) m+=`**Prepared by:** ${USER.name}${USER.inst?", "+USER.inst:""}  \n`;
  m+=`**Encoding:** ${d.enc} (confidence ${d.conf.toFixed(1)})${d.hadBom?", BOM removed":""}  \n`;
  m+=`**Line endings:** ${d.newline} → normalised to \\n  \n**Preset:** ${CFG.name||"custom"}\n\n`;
  m+=`## 1. Source\n\n- Characters: ${d.stats.chars.toLocaleString()}\n`;
  m+=`- Lines: ${d.stats.lines.toLocaleString()}\n- Word tokens: ${d.stats.tokens.toLocaleString()}\n`;
  m+=`- Word types: ${d.stats.types.toLocaleString()}\n\n`;
  m+=`## 2. Segmentation\n\n| # | Label | Kind | Title | Lines | Words | Conf |\n|---|---|---|---|---|---|---|\n`;
  d.regions.forEach((r,i)=>{
    const w=countTT(d.lines.slice(r.start,r.end).join("\n")).tokens;
    m+=`| ${i+1} | ${r.label} | ${r.kind} | ${"  ".repeat(r.level-1)}${r.title||"(untitled)"} | ${r.start+1}–${r.end} | ${w.toLocaleString()} | ${r.confidence.toFixed(2)} |\n`;
  });
  m+=`\n${d.gaps.length?`Warning: ${d.gaps.length} uncovered content range(s). This indicates a fault in segmentation.`
    :"Every line is covered by exactly one region."}\n\n`;
  m+=`## 3. Result\n\n| | Source | Cleaned | Change |\n|---|---|---|---|\n`;
  m+=`| Characters | ${b.chars.toLocaleString()} | ${s.chars.toLocaleString()} | ${(100*(s.chars-b.chars)/b.chars).toFixed(1)}% |\n`;
  m+=`| Word tokens | ${b.tokens.toLocaleString()} | ${s.tokens.toLocaleString()} | ${delta}% |\n`;
  m+=`| Word types | ${b.types.toLocaleString()} | ${s.types.toLocaleString()} | n/a |\n\n`;
  const quiet=noOpNotes();
  if(quiet.length){
    m+=`## Nothing was removed, and here is what was looked for\n\n`;
    m+=`Every rule in this tool examined the text and declined. That is a `;
    m+=`result, not a failure — but it is only useful if you can see what was `;
    m+=`asked.\n\n`;
    quiet.forEach(n=>m+=`- ${n}\n`);
    m+=`\n${NO_OP_CLOSING}\n\n`;
  }
  if(d.interfaceSeries&&d.interfaceSeries.length){
    m+=`### Interface furniture\n\n`;
    m+=`${d.interface.size} lines look like labels an application printed `;
    m+=`rather than text anyone wrote.\n\n`;
    m+=`| Control | Times | Why it was judged furniture |\n|---|---|---|\n`;
    d.interfaceSeries.forEach(x=>
      m+=`| \`${x.key}\` | ${x.lines.length} | ${x.reason} |\n`);
    m+=`\n**Detected, not removed.** Every word here is ordinary English, so `;
    m+=`the rule declines entirely unless the file is shaped like a scraped `;
    m+=`feed, and even then takes only lines sitting after the text of a `;
    m+=`record rather than among it.\n\n`;
  }
  m+=`## 4. Sections removed\n\n`;
  if(!RESULT.dropped.length) m+=`None.\n\n`;
  else{
    m+=`| Section | Lines | Basis for identification |\n|---|---|---|\n`;
    RESULT.dropped.forEach(r=>m+=`| ${r.label}: ${r.title||r.kind} | ${r.start+1}–${r.end} | ${r.evidence} |\n`);
    m+=`\n`;
  }
  m+=`---\n\n*A substantial reduction in characters accompanied by negligible token `;
  m+=`loss indicates that apparatus was removed rather than prose. Token loss above `;
  m+=`a few per cent in body-only warrants investigation before the corpus is used.*\n`;
  return m;
}

function drawLog(){
  const d=DOC,s=RESULT.stats,b=RESULT.base;
  const quietNotes=noOpNotes();
  const dt=b.tokens?100*(s.tokens-b.tokens)/b.tokens:0;
  const dc=b.chars?100*(s.chars-b.chars)/b.chars:0;
  let h=`<div class="canvas-head"><h3>Preprocessing log</h3>
    <p>A record of every decision taken, suitable for citation in a methods section.</p></div>`
    +(quietNotes.length?`<div class="warn"><strong>Nothing was removed, and here
      is what was looked for.</strong> Every rule examined the text and
      declined.<ul>${quietNotes.map(n=>`<li>${esc(n.replace(/\*\*/g,"").replace(/[`*]/g,""))}</li>`).join("")}</ul>
      The rules here are built for printed books turned into text. Text that was
      born digital carries none of that apparatus, and your file is already as
      clean as this tool can make it. If it carries a different kind — interface
      labels, timestamps, usernames, boilerplate that repeats — that is worth
      reporting.</div>`:"")
    +`

   <h4>Provenance</h4><table>
   <tr><td class="lbl">Source</td><td>${esc(d.name)}</td></tr>
   ${USER?`<tr><td class="lbl">Prepared by</td><td>${esc(USER.name)}${USER.inst?", "+esc(USER.inst):""}</td></tr>`:""}
   <tr><td class="lbl">Generated</td><td>${new Date().toISOString().slice(0,16).replace("T"," ")}</td></tr>
   <tr><td class="lbl">Encoding</td><td>${esc(d.enc)}${d.hadBom?" · BOM removed":""} · confidence ${d.conf.toFixed(1)}</td></tr>
   <tr><td class="lbl">Line endings</td><td class="mono">${d.newline} → \\n</td></tr>
   <tr><td class="lbl">Preset</td><td>${esc(CFG.name||"custom")}</td></tr>
   <tr><td class="lbl">Coverage</td><td>${d.gaps.length?"⚠ "+d.gaps.length+" uncovered range(s)":"Every line accounted for"}</td></tr>
   </table>

   <h4>Result</h4>
   <table><tr><th></th><th>Source</th><th>Cleaned</th><th>Change</th></tr>
   <tr><td class="lbl">Characters</td><td>${b.chars.toLocaleString()}</td><td>${s.chars.toLocaleString()}</td><td>${dc.toFixed(1)}%</td></tr>
   <tr><td class="lbl">Word tokens</td><td>${b.tokens.toLocaleString()}</td><td>${s.tokens.toLocaleString()}</td><td>${dt.toFixed(1)}%</td></tr>
   <tr><td class="lbl">Word types</td><td>${b.types.toLocaleString()}</td><td>${s.types.toLocaleString()}</td><td>n/a</td></tr></table>

   <div class="note">${Math.abs(dc)>1&&Math.abs(dt)<3
     ? "A substantial reduction in characters accompanied by negligible token loss indicates that <b>apparatus was removed rather than prose</b>. This is the expected signature of a sound run."
     : Math.abs(dt)>=8
     ? "<b>Token loss is high.</b> Examine the sections listed below before this corpus is used."
     : "Both character and token counts have changed little. Little was removed."}</div>

   <h4>Sections removed</h4>
   <p class="sub">${RESULT.dropped.length} of ${DOC.regions.length} sections</p>`;
  if(!RESULT.dropped.length) h+=`<p style="color:var(--muted);font-size:13.5px">None.</p>`;
  else{
    h+=`<table><tr><th>Section</th><th>Lines</th><th>Words</th><th>Basis for identification</th></tr>`;
    RESULT.dropped.forEach(r=>{
      const w=countTT(DOC.lines.slice(r.start,r.end).join("\n")).tokens;
      h+=`<tr><td>${esc(r.title||r.kind)}</td><td>${r.start+1}–${r.end}</td>
          <td>${w.toLocaleString()}</td><td class="lbl" style="width:auto">${esc(r.evidence)}</td></tr>`;
    });
    h+=`</table>`;
  }
  h+=`<div class="dl">
    <button class="btn sm" onclick="dl('txt')">Download cleaned text</button>
    <button class="btn sm ghost" onclick="dl('md')">Log (Markdown)</button>
    <button class="btn sm ghost" onclick="dl('json')">Log (JSON)</button></div>`;
  $("#logview").innerHTML=h;
}

function dl(kind){
  const stem=DOC.name.replace(/\.(txt|docx|epub|html?|xhtml|md)$/i,"");
  let data,name,type="text/plain";
  if(kind==="txt"){data=RESULT.text;name=`${stem}__${CFG.name||"custom"}.txt`}
  else if(kind==="md"){data=logMarkdown();name=`${stem}_log.md`;type="text/markdown"}
  else{
    data=JSON.stringify({tool:"corpusprep-web",version:CORPUSPREP_VERSION,
      generated:new Date().toISOString(), prepared_by:USER||null,
      source:{name:DOC.name,encoding:DOC.enc,had_bom:DOC.hadBom,stats:DOC.stats,notes:DOC.notes},
      regions:DOC.regions.map(r=>({label:r.label,kind:r.kind,title:r.title,
        start_line:r.start+1,end_line:r.end,level:r.level,parent:r.parent,
        confidence:r.confidence,evidence:r.evidence})),
      coverage_gaps:DOC.gaps,
      preset:{name:CFG.name||"custom",keep:CFG.keep,drop_headings:!!CFG.dropHeadings,
              drop_furniture:!!CFG.dropFurniture},
      furniture:{detected:[...DOC.furniture].sort((a,b)=>a-b),
                 page_length:Math.round(DOC.pageLength*10)/10,
                 removed:CFG.dropFurniture?RESULT.stats.furnitureRemoved:0,
                 series:DOC.furnSeries.map(c=>({text:c.text,
                        occurrences:c.lines.length,reason:c.reason}))},
      result:RESULT.stats},null,2);
    name=`${stem}_log.json`;type="application/json";
  }
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([data],{type}));
  a.download=name; a.click(); URL.revokeObjectURL(a.href);
}

function esc(s){return String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}

/* ---- wiring ---- */
$("#run-clean").onclick=()=>{
  if(!DOC||CLEANED) return;
  $("#run-clean").dataset.ran="1";
  runClean();
};

$("#drop").onclick=()=>$("#file").click();
$("#file").onchange=e=>handleFile(e.target.files[0]);
["dragover","dragenter"].forEach(ev=>$("#drop").addEventListener(ev,e=>{e.preventDefault();$("#drop").classList.add("over")}));
["dragleave","drop"].forEach(ev=>$("#drop").addEventListener(ev,e=>{e.preventDefault();$("#drop").classList.remove("over")}));
$("#drop").addEventListener("drop",e=>handleFile(e.dataTransfer.files[0]));

$("#preset").onchange=e=>{
  const p=PRESETS[e.target.value];
  if(!p){ $("#preset").value=CFG.name||"custom"; return }
  CFG=JSON.parse(JSON.stringify(p)); CFG.name=e.target.value;
  remember({preset:CFG.name});
  drawToggles(); refreshPreview();
};

$$("nav button").forEach(b=>b.onclick=()=>{
  $$("nav button").forEach(x=>x.classList.remove("on")); b.classList.add("on");
  $$(".tabpane").forEach(p=>p.classList.remove("on"));
  $("#tab-"+b.dataset.tab).classList.add("on");
});

/* ---- restore session ----
   This filled the sign-in fields and stopped, so a reload put the gate back up
   with the name typed in and `USER` still null. Nothing was lost — the details
   were in local storage the whole time — but the reader had to sign in again
   on every reload, and if they took the "Continue without signing in" door
   instead, every log written afterwards silently lost its "Prepared by" line.
   That line is the reason the sign-in exists: it is what makes the log a
   document someone can cite. So this was a provenance fault wearing the
   clothes of an annoyance.

   `signedOut` is what keeps the gate reachable now that it is skipped by
   default: without it, signing in once would hide the door for good, which
   matters on a shared machine. */
(function(){
  const s=load_();
  if(s.user){ $("#g-name").value=s.user.name||""; $("#g-inst").value=s.user.inst||""; }
  drawCapabilities();
  drawRegister();
  drawRecent();
  if(s.user&&!s.signedOut) enter(s.user);
})();
