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
const CAPABILITIES=[
  {ready:1, t:"Detects front matter and back matter",
   d:"Title pages, prefaces, dramatis personae, contents, appendices and indexes."},
  {ready:1, t:"Segments chapters and sections",
   d:"Chapter, Book, Part, Act and Scene divisions, numbered sections and bare numeral runs."},
  {ready:1, t:"Identifies publisher and licence apparatus",
   d:"Gutenberg headers, licence text and transcriber credits, whether or not sentinel markers are present."},
  {ready:1, t:"Preserves or removes structural elements on request",
   d:"Retain or remove any section. Five presets are provided, or sections may be selected individually."},
  {ready:1, t:"Reads TXT, DOCX, EPUB and HTML",
   d:"Encoding, byte-order marks and line endings resolved on import."},
  {ready:1, t:"Records every decision in a log",
   d:"Markdown and JSON, including token and type counts, suitable for citation."},
  {ready:0, t:"Identifies page numbers, headers and footers",
   d:"Statistical detection of repeating page furniture. Specified, not yet implemented."},
  {ready:0, t:"Cleans OCR artefacts",
   d:"Broken ligatures, stray marks and mis-scanned characters, flagged for review."},
  {ready:0, t:"Rejoins hyphenated line breaks",
   d:"Wordlist-validated de-hyphenation, with ambiguous cases queued for review."},
  {ready:0, t:"Reflows hard-wrapped paragraphs",
   d:"Paragraph reconstruction that leaves verse and drama line breaks intact."},
];

const TICK_ON=`<svg class="tick" width="14" height="14" viewBox="0 0 24 24" fill="none"
  stroke="#37564a" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 6L9 17l-5-5"/></svg>`;
const TICK_OFF=`<svg class="tick" width="14" height="14" viewBox="0 0 24 24" fill="none"
  stroke="#a09a8e" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"
  stroke-dasharray="3 3"/></svg>`;

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
const STORE="corpusprep.v1";
function load_(){ try{return JSON.parse(localStorage.getItem(STORE))||{}}catch(e){return {}} }
function save_(o){ try{localStorage.setItem(STORE,JSON.stringify(o))}catch(e){} }
function remember(patch){ save_({...load_(),...patch}); }

function pushRecent(name,tokens){
  const s=load_(), list=(s.recent||[]).filter(r=>r.name!==name);
  list.unshift({name,tokens,at:Date.now()});
  save_({...s,recent:list.slice(0,6)});
  drawRecent();
}
function drawRecent(){
  const list=load_().recent||[];
  const guide=$("#guide");
  if(!list.length){
    $("#recent-wrap").style.display="none";
    if(guide&&!DOC) guide.style.display="";   // first run: guidance fills the space
    return;
  }
  if(guide&&!DOC) guide.style.display="none"; // returning user: recents replace it
  $("#recent-wrap").style.display="";
  $("#recent").innerHTML=list.map(r=>`
    <button title="Reopen this file from disk to load it again">
      <span class="t">${esc(r.name)}</span>
      <span class="d">${r.tokens.toLocaleString()}</span>
    </button>`).join("");
}

/* ---- sign in ---- */
function initials(n){
  const p=n.trim().split(/\s+/).filter(Boolean);
  return ((p[0]&&p[0][0]||"?")+(p.length>1?p[p.length-1][0]:"")).toUpperCase();
}
function enter(user){
  USER=user;
  remember({user});
  $("#gate").style.display="none";
  $("#app").style.display="flex";
  $("#who").innerHTML = user
    ? `<span class="avatar">${esc(initials(user.name))}</span>
       <span>${esc(user.name)}${user.inst?" · "+esc(user.inst):""}</span>`
    : `<span>Not signed in</span>`;
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
         hadBom:false,conf:1,newline:"\\n",repl:(text.match(/\uFFFD/g)||[]).length};
      extraNotes.push(`Text extracted from ${ex.meta.container}. Formatting, images `+
        `and footnotes were discarded. Paragraph structure was preserved.`);
    } else d=decode(buf);
  }catch(err){
    showError(err instanceof UnsupportedFormat?err.message:
      `Could not read ${name}: ${err.message}`);
    return;
  }

  const seg=segment(d.lines);
  const tt=countTT(d.lines.join("\n"));
  // Detection, not removal. The result is shown for review and is removed
  // only if the reader ticks the box below the section list.
  const fu=findFurnitureIn(d.lines,seg.regions);
  DOC={name,...d,regions:seg.regions,notes:[...extraNotes,...seg.notes],
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
    <p class="furn-lead">A line break inside a word is always an artefact, but
      the hyphen may be real: <b>to-morrow</b> is a word and <b>tomorrow</b> is a
      different one. Each case is settled from the surrounding text — whether
      the finished word appears elsewhere, and whether both halves are words in
      their own right, since a compound is built out of words and a broken word
      is not.${!CLEANED?" Anything the text cannot settle keeps the hyphen "
      +"exactly as the source prints it."
      :left?` <b>${left}</b> could not be settled that way, so ${
      left===1?"it is":"they are"} left with the hyphen exactly as the source
      prints ${left===1?"it":"them"}. Nothing is required of you.`:` Every one
      was settled.`}</p>
    <div class="fn-opts">
      <label class="fn-opt ${on?"on":""}">
        <input type="checkbox" id="dh-on" ${on?"checked":""}>
        <span class="fn-t">Rejoin broken words</span>
        <span class="fn-d">Repairs the line break. The hyphen is decided
          separately.</span></label>
      <label class="fn-opt ${CFG.reflow?"on":""}">
        <input type="checkbox" id="rf-on" ${CFG.reflow?"checked":""}>
        <span class="fn-t">Rejoin paragraphs</span>
        <span class="fn-d">Undoes fixed-width line wrapping. Verse, drama and
          tables are left alone. 99.5% accurate; see the log.</span></label>
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
      <span class="s">${paired.length} note${paired.length===1?"":"s"}
        matched to a marker${loose?` · ${loose} bracketed label${loose===1?"":"s"}
        could not be matched`:""}</span>
    </div>
    <p class="furn-lead">A marker is treated as a footnote only when a note
      elsewhere carries the same label. Stage directions, illustrations and
      other bracketed material have no matching note and are left alone.${
      loose?` The ${loose} unmatched label${loose===1?"":"s"} will not be
      removed by any option below.`:""}</p>
    <div class="fn-opts">
      ${opt("retain","Keep footnotes","Markers and notes stay. Study the edition.")}
      ${opt("remove","Remove footnotes","Markers stripped, notes dropped. Study the work.")}
      ${opt("extract","Extract to a second file","Notes saved separately. Study both.")}
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
      <span class="s">${DOC.furniture.size} lines · estimated page length
        ${Math.round(DOC.pageLength)} lines</span>
    </div>
    <p class="furn-lead">These lines recur at the page interval, which is the
      pattern a running head or page number makes. Ordinary repeated text, such
      as a refrain, recurs irregularly and is not listed here.${
      DOC.catchwords.size?` This text also appears to use <b>catchwords</b>, the
      early modern practice of printing the next page's first word at the foot
      of the page.`:""}</p>
    <table class="furn-table">
      <thead><tr><th>Recurring line</th><th>Times</th><th>Grounds</th></tr></thead>
      <tbody>${rows}</tbody></table>
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
  const dt=b.tokens?100*(s.tokens-b.tokens)/b.tokens:0;
  const dc=b.chars?100*(s.chars-b.chars)/b.chars:0;
  let h=`<div class="canvas-head"><h3>Preprocessing log</h3>
    <p>A record of every decision taken, suitable for citation in a methods section.</p></div>

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

/* ---- restore session ---- */
(function(){
  const s=load_();
  if(s.user){ $("#g-name").value=s.user.name||""; $("#g-inst").value=s.user.inst||""; }
  drawCapabilities();
  drawRecent();
})();
