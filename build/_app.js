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


function drawRegister(){
  if(!REGISTER_URL) return;                    // nothing configured, nothing shown
  const link=`<a href="${REGISTER_URL}" target="_blank" rel="noopener noreferrer">`;
  const gate=$("#reg-gate");
  if(gate) gate.innerHTML=
    `Using CorpusPrep? ${link}Let us know</a>, or ask to hear about new `+
    `versions. It is optional, the form opens in a new tab, and this page `+
    `sends nothing.`;
  const foot=$("#reg-foot");
  if(foot) foot.innerHTML=
    `${link}Tell us how you use CorpusPrep</a> (optional, external form)`;
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
      <button data-open="${i}" title="Choose this file again. Your browser cannot reopen it on its own.">
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

/* ---- welcome page and log details ----
   Name and institution are optional and fill one line of the processing log,
   "Prepared by". The welcome page asks for them once; after that they can be
   changed from the sidebar ("Edit log details") without going back. Both sets
   of fields write through setDetails, so they cannot disagree. */
function drawWho(){
  $("#who").innerHTML=`${USER?`<span class="nm">${esc(USER.name)}${
      USER.inst?" · "+esc(USER.inst):""}</span>`:""}
    <button class="linkish" id="who-edit" type="button">Edit log details</button>`;
  $("#who-edit").onclick=()=>{
    const d=$("#details-panel");
    d.open=true;
    if(d.scrollIntoView) d.scrollIntoView({block:"nearest"});
    $("#d-name").focus();
  };
}
function setDetails(name,inst){
  name=(name||"").trim(); inst=(inst||"").trim();
  USER=name?{name,inst}:null;
  remember({user:(name||inst)?{name,inst}:undefined, signedOut:false});
  for(const [n,i] of [["#g-name","#g-inst"],["#d-name","#d-inst"]]){
    if($(n).value!==name) $(n).value=name;
    if($(i).value!==inst) $(i).value=inst;
  }
  drawWho();
  if(CLEANED) drawLog();
}
function showWorkspace(){
  remember({seen:true});
  $("#gate").style.display="none";
  $("#app").style.display="flex";
  drawWho();
  drawRecent();
}
["#d-name","#d-inst"].forEach(s=>$(s).addEventListener("input",
  ()=>setDetails($("#d-name").value,$("#d-inst").value)));
// Start works with or without a name: the details are optional.
$("#g-go").onclick=()=>{
  setDetails($("#g-name").value,$("#g-inst").value);
  showWorkspace();
};
["#g-name","#g-inst"].forEach(s=>$(s).addEventListener("keydown",
  e=>{if(e.key==="Enter")$("#g-go").click()}));
// Skipping on a borrowed machine leaves whoever is remembered untouched, and
// keeps their name off this session's log.
$("#g-skip").onclick=()=>{
  USER=null;
  remember({signedOut:true});
  showWorkspace();
};

/* ---- cite from the first screen ---------------------------------------
   The same two texts the Log tab prints, and deliberately the same concept
   DOI: this file does not know which archived release it was built from, so a
   version DOI here would be a claim it cannot support. The note says where the
   version DOI lives, because that is the one a methods section needs.

   Built on demand rather than at load. The citation carries the running
   version, and reading CORPUSPREP_VERSION at click time cannot go stale. */
function drawGateCite(id){
  const el=$("#"+id);
  if(!el) return;
  el.innerHTML=`
    <div class="row"><b>Reference</b>
      <button data-gcopy="apa">Copy</button></div>
    <pre>${esc(citationText())}</pre>
    <div class="row"><b>BibTeX</b>
      <button data-gcopy="bib">Copy</button></div>
    <pre>${esc(citationBibtex())}</pre>
    <p class="note">This DOI always points to the newest release. In a methods
      section, cite the DOI of the exact version you used instead. The
      <a href="https://corpusprep.org/CITING.html" target="_blank"
      rel="noopener">citing guide</a> shows where to find it.</p>`;
  $$("#"+id+" [data-gcopy]").forEach(b=>b.onclick=async()=>{
    const text=b.dataset.gcopy==="apa"?citationText():citationBibtex();
    try{
      await navigator.clipboard.writeText(text);
      b.textContent="Copied";
    }catch(e){
      // The clipboard is not granted in every browser or every context. The
      // text is selectable, so say so rather than appearing to have worked.
      b.textContent="Select and copy";
    }
    setTimeout(()=>{b.textContent="Copy"},2000);
  });
}
for(const [tid,pid,label] of [["g-cite-toggle","g-cite","Cite this"],
                               ["f-cite-toggle","f-cite","Cite CorpusPrep"]]){
  const t=$("#"+tid), p=$("#"+pid);
  if(t&&p) t.onclick=()=>{
    const open=p.hidden;
    if(open) drawGateCite(pid);
    p.hidden=!open;
    t.setAttribute("aria-expanded",String(open));
    t.textContent=open?"Hide citation":label;
  };
}

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
        extraNotes.push(`Read from PDF. ${ex.meta.note}`);
        // The page boundaries are the gift of this format. Every other input
        // makes the furniture rules infer where pages begin; a PDF states it.
        extraNotes.push(`Page breaks were taken from the file `+
          `(${ex.meta.pdf_pages} pages), which makes page numbers and running `+
          `heads easier to find.`);
      } else {
        extraNotes.push(`Text taken from ${ex.meta.container}. Formatting, images `+
          `and footnotes were left out, and paragraphs were kept.`);
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
    `${ui.lines.size} lines look like app labels (such as Like or Reply) `+
    `rather than text someone wrote. They are flagged, not removed, and the `+
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
  $("#wrap").classList.remove("nofile");
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
      <span class="t">What We Found</span>
      <span class="s">${DOC.regions.length} sections · ${
        depth>1?`${depth} levels deep`:"one level"}${
        unknown?` · ${unknown} unclassified`:""}</span>
    </div>
    <div class="bar-track">${bar}</div>
    <div class="sum-grid">
      ${cell(DOC.stats.tokens,"Words")}
      ${cell(chapters||sections,chapters?"Chapters":"Sections")}
      ${cell(front,"Front matter")}
      ${cell(back,"Back matter")}
      ${cell(apparatus,"Publisher blocks")}
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
           decided from this text</b>${
           left?` · ${left} left as printed`:""}`
        : "this text has fixed line lengths"}</span>
    </div>
    <p class="furn-lead">The line break was added by the printer, but the hyphen
      may be real. Each case is checked against the words used elsewhere in
      this text, and anything unclear keeps its hyphen.${
      CLEANED&&left?` <b>${left}</b> did. Nothing is required of you.`:""}</p>
    <div class="fn-opts">
      <label class="fn-opt ${on?"on":""}">
        <input type="checkbox" id="dh-on" ${on?"checked":""}>
        <span class="fn-t">Rejoin broken words</span>
        <span class="fn-d">Hyphens are checked one by one.</span></label>
      <label class="fn-opt ${CFG.reflow?"on":""}">
        <input type="checkbox" id="rf-on" ${CFG.reflow?"checked":""}>
        <span class="fn-t">Rejoin paragraphs</span>
        <span class="fn-d">Joins short lines back into paragraphs. Verse and
          drama are left alone.</span></label>
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
          loose?` · ${loose} label${loose===1?"":"s"} with no matching note`:""}`
        : "this text has footnotes"}</span>
    </div>
    <p class="furn-lead">A marker counts only when a matching note exists, which
      keeps most stage directions out. Unmatched labels are not removed.${
      CLEANED&&loose?` There ${loose===1?"is":"are"} ${loose} here.`:""}</p>
    <div class="fn-opts">
      ${opt("retain","Keep","For studying the edition.")}
      ${opt("remove","Remove","For studying the work itself.")}
      ${opt("extract","Save to a separate file","For studying both.")}
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
        <td class="why">repeats the first word of the next page, on
          ${DOC.catchwords.size} of ${DOC.catchwordMatches.length} pages</td></tr>`:"");
  const on=!!CFG.dropFurniture;
  return `<div class="furn-notice ${on?"on":""}">
    <div class="furn-head">
      <span class="t">Possible page furniture</span>
      <span class="s">${CLEANED
        ? `${DOC.furniture.size} lines · pages of about
           ${Math.round(DOC.pageLength)} lines`
        : "this text seems to come from printed pages"}</span>
    </div>
    <p class="furn-lead">Page numbers and running heads repeat at a steady
      interval, page after page. A refrain repeats unevenly, so it is left
      alone.${DOC.catchwords.size?" This text also has catchwords.":""}${
      !CLEANED?" After cleaning, each flagged line is listed here with the"
      +" reason.":""}</p>
    ${CLEANED?`<table class="furn-table">
      <thead><tr><th>Repeated line</th><th>Times</th><th>Reason</th></tr></thead>
      <tbody>${rows}</tbody></table>`:""}
    <p class="furn-foot">${on
      ? "These lines will be removed when you clean. The JSON log lists them."
      : "To remove them, tick <b>Drop page furniture</b> under Sections to Keep."}
      This check has only been tried on test examples so far, not real scans,
      so please look over the list first.</p>
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
/* Reading a file used to happen in silence. A PDF is parsed page by page and
   a large one takes a while, so the page sat there looking broken while it
   worked — and looking identical to a page that had genuinely stalled. A
   reader cannot tell "slow" from "hung" unless the tool says which it is. */
function loading(msg){
  const el=$("#load-note");
  if(!el) return;
  if(msg===null){ el.hidden=true; el.textContent=""; return; }
  el.hidden=false; el.textContent=msg;
}

function handleFile(f){
  if(!f) return;
  const mb=f.size/1048576;
  loading(`Reading ${f.name} (${mb<0.1?"<0.1":mb.toFixed(1)} MB)\u2026`);
  if(/\.pdf$/i.test(f.name))
    loading(`Reading ${f.name} (${mb.toFixed(1)} MB). A PDF is read page by `+
            `page, so a long one takes a moment. The first PDF also fetches `+
            `the PDF reader (pdf.js).`);
  f.arrayBuffer()
    .then(b=>loadText(f.name,b))
    .finally(()=>loading(null));
}

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
  if(d.conf<.6) w.push(`The encoding is uncertain (${d.enc}). Check the result for garbled characters.`);
  if(d.repl)    w.push(`${d.repl} unreadable character(s) were replaced. The file may be damaged.`);
  d.notes.forEach(n=>w.push(n));
  if(d.gaps.length) w.push(`${d.gaps.length} stretch(es) of text were not given a section. That is a bug in CorpusPrep, so please report it.`);
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
    :"Your own choice of sections.";
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
  $("#run-note").textContent="Working through the text. This can take a "
    +"few seconds for a long book.";

  // Yield twice so the browser paints the working state before the main
  // thread is occupied. One yield is not always enough: the style change and
  // the paint are separate frames, and a single setTimeout can land between
  // them, which showed the spinner only after the work had finished.
  //
  // The race matters. A window that is not in front gets no animation frames
  // at all, so waiting on them alone means the clean never starts: the button
  // says Cleaning and nothing happens until the window is brought forward.
  // Seen while testing, and a plausible way to lose a demonstration. The
  // timeout is the floor, the frames are the nicety.
  await Promise.race([
    new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(
      ()=>setTimeout(r,0)))),
    new Promise(r=>setTimeout(r,250)),
  ]);

  const t0=performance.now();
  try{
    RESULT=render(DOC.lines,DOC.regions,CFG,DOC.furniture,DOC.footnotes);
    RESULT.base=render(DOC.lines,DOC.regions,PRESETS["verbatim"]).stats;
    CLEANED=true;
  }catch(e){
    b.classList.remove("busy"); b.disabled=false;
    $("#run-label").textContent="Clean text";
    $("#run-note").textContent="Cleaning stopped with an error ("+e.message
      +"). Your original text is unchanged.";
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
    n.textContent="Done. See Compare, or download from the Processing Log tab. "
      +"Change anything above to clean again.";
  } else if(RESULT===null&&b.dataset.ran==="1"){
    label.textContent="Apply changes";
    b.className="btn-run stale";
    n.textContent="You changed the selection. Clean again to update the result.";
  } else {
    label.textContent="Clean text";
    b.className="btn-run";
    n.textContent=drops
      ? `${drops} of ${DOC.regions.length} sections will be removed when you `
        +`press Clean text.`
      : "Every section is currently kept.";
  }
}

/* The comparison and log views describe an output that does not exist until
   cleaning has been run, so they are held closed until then. */
function drawGates(){
  const on=CLEANED;
  $("#gate-cmp-h").textContent=DOC?"Ready to Review":"No File Selected";
  $("#gate-cmp-p").textContent=DOC
    ?"Choose which sections to keep, then select Clean text."
    :"Open a file on the Sections tab to begin.";
  $("#gate-cmp").style.display=on?"none":"";
  $("#cmp-body").style.display=on?"":"none";
  $("#gate-log").style.display=on?"none":"";
  $("#logview").style.display=on?"":"none";
}

function drawStats(){
  if(!CLEANED){
    $("#stats").innerHTML=`<div class="fig" style="grid-column:1/-1">
      <div class="v zero">Not cleaned yet</div>
      <div class="k">The numbers appear after cleaning</div></div>`;
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
  const cover=DOC.gaps.length?"some lines have no section"
                             :"every line has a section";
  $("#seg-sub").textContent=CLEANED
    ? `${DOC.regions.length} sections · ${drops} removed · ${cover}`
    : `${DOC.regions.length} sections · ${cover} · click any section to see its text`;

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
/* Both panes are built in chunks rather than as one block of text.

   A 415 page Jane Eyre put 13,216 lines into each side, which came to about
   1.6 MB of markup in a single element, and scrolling it made the browser
   report that the page was not responding. Two things were wrong. The element
   was far too large to lay out, and the scroll handler read scrollHeight and
   clientHeight from both panes on every scroll event, which forces a
   synchronous layout each time.

   The lines are now grouped into blocks of CMP_CHUNK. Each block carries
   `content-visibility:auto`, so the browser skips layout and paint for the
   blocks that are off screen, and `contain-intrinsic-size`, so the scrollbar
   is about the right length before they have been measured. Wrapping is
   unaffected, which matters because these lines wrap.

   The sync handler now measures once and then runs at most once per frame. */
const CMP_CHUNK=250;
const CMP_LINE_PX=21;          // 12px type at a line height of 1.75

function cmpFill(el,lines,dropSet){
  const parts=[];
  for(let i=0;i<lines.length;i+=CMP_CHUNK){
    const slice=lines.slice(i,i+CMP_CHUNK);
    const body=slice.map((l,k)=>
      dropSet&&dropSet.has(i+k)?`<mark>${esc(l)}</mark>`:esc(l)).join("\n");
    parts.push(`<div class="cmp-chunk" style="contain-intrinsic-size:auto `+
               `${slice.length*CMP_LINE_PX}px">${body}</div>`);
  }
  el.innerHTML=parts.join("")||"";
}

function drawCompare(){
  $("#src-i").textContent=`${DOC.stats.tokens.toLocaleString()} tokens`;
  $("#out-i").textContent=`${RESULT.stats.tokens.toLocaleString()} tokens · ${CFG.name||"custom"}`;

  const dropSet=new Set();
  RESULT.dropped.forEach(r=>{for(let i=r.start;i<r.end;i++) dropSet.add(i)});
  cmpFill($("#src-t"),DOC.lines,dropSet);
  cmpFill($("#out-t"),RESULT.text.split("\n"),null);

  const a=$("#src-t"),b=$("#out-t");
  let lock=false,queued=false;
  const sync=(from,to)=>()=>{
    if(lock||queued) return;
    queued=true;
    requestAnimationFrame(()=>{
      queued=false; lock=true;
      const fromRange=Math.max(1,from.scrollHeight-from.clientHeight);
      const toRange=to.scrollHeight-to.clientHeight;
      to.scrollTop=(from.scrollTop/fromRange)*toRange;
      // Released on the next frame so the scroll event this causes on the
      // other pane does not bounce straight back.
      requestAnimationFrame(()=>{lock=false});
    });
  };
  a.onscroll=sync(a,b); b.onscroll=sync(b,a);
}

/* ---- citation ----------------------------------------------------------
   Two DOIs, and they are not interchangeable. The CONCEPT DOI always resolves
   to the newest release; the VERSION DOI is minted per release and pins the
   exact code that produced a result. `design/` argues, correctly, that a
   methods section needs the second — an analysis run against v0.5.0 is not
   reproducible against v0.6.0, because v0.5.0 was silently dropping 5,500
   words of Frankenstein.

   **So this page does not print a version DOI it cannot verify.** It knows the
   version it is running and it knows the concept DOI; it does not know whether
   a release was archived for this particular build. Printing one anyway would
   hand a researcher a DOI that resolves to different code than they ran, which
   is worse than printing none — it is a citation that looks right and is not.

   It prints the version it is, the concept DOI, and one sentence telling the
   reader where the version DOI lives. */
const CONCEPT_DOI="10.5281/zenodo.22083931";
const CITE_AUTHOR="Adesokan, T.";
const CITE_TITLE="CorpusPrep: corpus preparation for linguists";

function citationText(){
  const v=typeof CORPUSPREP_VERSION!=="undefined"?CORPUSPREP_VERSION:"";
  const y=new Date().getFullYear();
  return `${CITE_AUTHOR} (${y}). ${CITE_TITLE} (version ${v}) `+
         `[Computer software]. Zenodo. https://doi.org/${CONCEPT_DOI}`;
}

function citationBibtex(){
  const v=typeof CORPUSPREP_VERSION!=="undefined"?CORPUSPREP_VERSION:"";
  const y=new Date().getFullYear();
  return `@software{adesokan_corpusprep,\n`+
         `  author    = {Adesokan, Tosin},\n`+
         `  title     = {{${CITE_TITLE}}},\n`+
         `  version   = {${v}},\n`+
         `  year      = {${y}},\n`+
         `  publisher = {Zenodo},\n`+
         `  doi       = {${CONCEPT_DOI}},\n`+
         `  url       = {https://doi.org/${CONCEPT_DOI}}\n}`;
}

function drawCite(){
  const el=$("#cite");
  if(!el) return;
  const v=typeof CORPUSPREP_VERSION!=="undefined"?CORPUSPREP_VERSION:"unknown";
  el.innerHTML=`
    <h4>Citing This Run</h4>
    <p class="why">You used <b>version ${esc(v)}</b>. Please note it down, since
      behaviour changes between releases and results from one version are not
      reproducible with another.</p>
    <div class="row"><b>Reference</b>
      <button class="linkish" data-copy="apa">Copy</button></div>
    <pre id="cite-apa">${esc(citationText())}</pre>
    <div class="row"><b>BibTeX</b>
      <button class="linkish" data-copy="bib">Copy</button></div>
    <pre id="cite-bib">${esc(citationBibtex())}</pre>
    <p class="note">The DOI above is the <b>concept DOI</b> and always points
      to the newest release. In a methods section, cite the <b>version DOI</b>
      for ${esc(v)} instead. It points to the exact code you used, and you will
      find it on that release's page in the archive. The
      <a href="https://corpusprep.org/CITING.html" target="_blank"
      rel="noopener">citing guide</a> explains more.</p>`;
  $$("#cite [data-copy]").forEach(b=>b.onclick=async()=>{
    const text=b.dataset.copy==="apa"?citationText():citationBibtex();
    try{
      // Not every browser and not every context grants the clipboard. A copy
      // button that silently does nothing is worse than one that admits it.
      await navigator.clipboard.writeText(text);
      b.textContent="Copied";
    }catch(e){
      b.textContent="Select and copy";
    }
    setTimeout(()=>{b.textContent="Copy"},2000);
  });
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
      "each a whole utterance, such as a comment, a caption or a line "+
      "of a transcript, are not wrapped, and rejoining them would be damage.");
  out.push("**No word broken across a line.** De-hyphenation looks for a word "+
    "ending in a hyphen at a line end; there were none.");
  return out;
}

const NO_OP_CLOSING=
  "**What this means for your corpus.** The rules here are built for printed "+
  "books turned into text: Gutenberg files, PDF extractions, library scans. "+
  "What there is to remove is their apparatus: running heads, page numbers, "+
  "editorial front matter, hyphens at line ends. Text that was born "+
  "digital has none of it, and the honest answer is that your file is already "+
  "as clean as this tool can make it.\n\nIf your material carries a "+
  "different kind of apparatus, such as interface labels, timestamps, "+
  "usernames or boilerplate that repeats, that is worth reporting, because "+
  "it is the sort "+
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
    m+=`result, not a failure. It is only useful, though, if you can see what was `;
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
  drawCite();
  const dt=b.tokens?100*(s.tokens-b.tokens)/b.tokens:0;
  const dc=b.chars?100*(s.chars-b.chars)/b.chars:0;
  let h=`<div class="canvas-head"><h3>Processing Log</h3>
    <p>The settings used, the sections removed, and token and type counts before
    and after. Download it for your methods section.</p></div>`
    +(quietNotes.length?`<div class="warn"><strong>Nothing was removed.</strong>
      Here is what CorpusPrep checked for.<ul>${quietNotes.map(n=>`<li>${esc(n.replace(/\*\*/g,"").replace(/[`*]/g,""))}</li>`).join("")}</ul>
      CorpusPrep is built for printed books converted to text. Text that was
      created digitally usually has none of this material. If your file has a
      different kind, such as app labels, timestamps, usernames or repeated
      boilerplate, please let us know.</div>`:"")
    +`

   <h4>Provenance</h4><table>
   <tr><td class="lbl">Source</td><td>${esc(d.name)}</td></tr>
   ${USER?`<tr><td class="lbl">Prepared by</td><td>${esc(USER.name)}${USER.inst?", "+esc(USER.inst):""}</td></tr>`:""}
   <tr><td class="lbl">Generated</td><td>${new Date().toISOString().slice(0,16).replace("T"," ")}</td></tr>
   <tr><td class="lbl">Encoding</td><td>${esc(d.enc)}${d.hadBom?" · BOM removed":""} · confidence ${d.conf.toFixed(1)}</td></tr>
   <tr><td class="lbl">Line endings</td><td class="mono">${d.newline} → \\n</td></tr>
   <tr><td class="lbl">Preset</td><td>${esc(CFG.name||"custom")}</td></tr>
   <tr><td class="lbl">Coverage</td><td>${d.gaps.length?"⚠ "+d.gaps.length+" stretch(es) with no section":"Every line has a section"}</td></tr>
   </table>

   <h4>Result</h4>
   <table><tr><th></th><th>Source</th><th>Cleaned</th><th>Change</th></tr>
   <tr><td class="lbl">Characters</td><td>${b.chars.toLocaleString()}</td><td>${s.chars.toLocaleString()}</td><td>${dc.toFixed(1)}%</td></tr>
   <tr><td class="lbl">Word tokens</td><td>${b.tokens.toLocaleString()}</td><td>${s.tokens.toLocaleString()}</td><td>${dt.toFixed(1)}%</td></tr>
   <tr><td class="lbl">Word types</td><td>${b.types.toLocaleString()}</td><td>${s.types.toLocaleString()}</td><td>n/a</td></tr></table>

   <div class="note">${Math.abs(dc)>1&&Math.abs(dt)<3
     ? "Many characters went but very few words did, so <b>the clutter was removed and the prose was kept</b>. This is what a good run looks like."
     : Math.abs(dt)>=8
     ? "<b>A lot of words were removed.</b> Check the sections listed below before you use this corpus."
     : "Very little changed, so very little was removed."}</div>

   <h4>Sections Removed</h4>
   <p class="sub">${RESULT.dropped.length} of ${DOC.regions.length} sections</p>`;
  if(!RESULT.dropped.length) h+=`<p style="color:var(--muted);font-size:13.5px">None.</p>`;
  else{
    h+=`<table><tr><th>Section</th><th>Lines</th><th>Words</th><th>How it was identified</th></tr>`;
    RESULT.dropped.forEach(r=>{
      const w=countTT(DOC.lines.slice(r.start,r.end).join("\n")).tokens;
      h+=`<tr><td>${esc(r.title||r.kind)}</td><td>${r.start+1}–${r.end}</td>
          <td>${w.toLocaleString()}</td><td class="lbl" style="width:auto">${esc(r.evidence)}</td></tr>`;
    });
    h+=`</table>`;
  }
  h+=`<div class="dl">
    <button class="btn sm" onclick="dl('txt')">Download cleaned text</button>
    <button class="btn sm ghost" onclick="dl('md')">Download log (Markdown)</button>
    <button class="btn sm ghost" onclick="dl('json')">Download log (JSON)</button></div>`;
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

// The button inside the drop zone gives keyboard users a real control; a click
// on it bubbles here, so the picker opens once either way.
$("#drop").onclick=()=>$("#file").click();
$("#open-another").onclick=()=>$("#file").click();
$("#file").onchange=e=>{ handleFile(e.target.files[0]); e.target.value=""; };
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

/* ---- restore saved details ----
   A returning reader skips the welcome page and keeps their details, so a
   reload never loses the "Prepared by" line. Someone who chose "Skip for now"
   is not given a remembered name back, which matters on a shared machine. */
(function(){
  const s=load_();
  if(s.user){ $("#g-name").value=s.user.name||""; $("#g-inst").value=s.user.inst||""; }
  if(s.user&&!s.signedOut){
    $("#d-name").value=s.user.name||""; $("#d-inst").value=s.user.inst||"";
    USER=s.user.name?{name:s.user.name,inst:s.user.inst||""}:null;
  }
  drawWho();
  drawRegister();
  drawRecent();
  if(s.seen||(s.user&&!s.signedOut)) showWorkspace();
})();
