const PG_HEADER="pg_header", PG_LICENCE="pg_licence", FRONT_MATTER="front_matter",
      BODY="body", BACK_MATTER="back_matter", UNKNOWN="unknown";

const LABELS=[
  {id:PG_HEADER,   name:"Gutenberg header", fg:"var(--c-head)",  bg:"var(--c-head-bg)"},
  {id:FRONT_MATTER,name:"Front matter",     fg:"var(--c-front)", bg:"var(--c-front-bg)"},
  {id:BODY,        name:"Body",             fg:"var(--c-body)",  bg:"var(--c-body-bg)"},
  {id:BACK_MATTER, name:"Back matter",      fg:"var(--c-back)",  bg:"var(--c-back-bg)"},
  {id:PG_LICENCE,  name:"Licence text",     fg:"var(--c-lic)",   bg:"var(--c-lic-bg)"},
  {id:UNKNOWN,     name:"Unclassified",     fg:"var(--c-unk)",   bg:"var(--c-unk-bg)"},
];
const LMAP=Object.fromEntries(LABELS.map(l=>[l.id,l]));

/* Gutenberg apparatus outranks body: a licence block inside a chapter's line
   range is still licence text. Mirrors PRECEDENCE in segment.py. */
const PRECEDENCE={[UNKNOWN]:0,[FRONT_MATTER]:1,[BACK_MATTER]:1,[BODY]:2,
                  [PG_HEADER]:3,[PG_LICENCE]:3};

const PG_START=/\*{3}\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}/i;
const PG_END  =/\*{3}\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}/i;
const PG_START_OLD=/\*{3}\s*START OF THE PROJECT GUTENBERG/i;
const PG_END_OLD  =/\*{3}\s*END OF THE PROJECT GUTENBERG/i;

/* Producer/transcriber credit. The prototype had a rule like this and it was
   bug B1 — it ran to the end of any paragraph starting with these words,
   anywhere. This one is bounded twice: to a single blank-line block, and to a
   window at the head or tail where such apparatus actually lives. */
const TRANSCRIBER_OPENING=new RegExp("^\\s*(?:"+
  "Transcribed\\s+from|Transcribed\\s+by|Produced\\s+by|Prepared\\s+by|"+
  "Scanned\\s+(?:and|by)|Digitized\\s+by|Digitised\\s+by|"+
  "E-?text\\s+prepared\\s+by|Proofread(?:ing|ers?)?\\s+by|"+
  "Credits\\s*:|Updated\\s+editions\\s+will"+
  ")\\b","i");
/* A line that is *only* "Transcriber's Note(s)". Unambiguous, so it needs no
   positional guard. The apostrophe class matters: Gutenberg uses the
   typographic form almost universally, and matching only the straight form
   meant this rule silently failed on the files it was written for. */
const TRANSCRIBER_HEADING=/^\s*Transcriber['’ʼ]?s?\s+Notes?\s*[.:]?\s*$/i;
const TRANSCRIBER_WINDOW=40;

const LICENCE_PHRASES=["project gutenberg","literary archive foundation","public domain",
  "no restrictions whatsoever","gutenberg.org","gutenberg-tm","redistribution is subject",
  "terms of the project gutenberg license","this ebook is for the use of anyone",
  "you may copy it, give it away","trademark","donations to the project gutenberg"];

/* Body headings — three tiers, most reliable first. Only the first tier that
   yields results is used, so a book with real chapter headings is never
   confused by stray numerals elsewhere. Mirrors segment.py. */
const DIVISION_WORDS="CHAPTER|BOOK|PART|VOLUME|CANTO|SECTION|LETTER|ACT|SCENE|STAVE|"+
  "EPISODE|FYTTE|MOVEMENT|INTERLUDE|LECTURE|SERMON|TALE|NIGHT";
const _CARDINAL="ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|"+
  "THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|"+
  "THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY|HUNDRED";
const _ORDINAL="FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"+
  "ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|"+
  "SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH|THIRTIETH|LAST";
/* Not "any word" — that is what would let "Part of the reason…" match. */
const _ENUM=`(?:[IVXLCDM]+|\\d{1,4}|(?:THE\\s+)?(?:${_CARDINAL}|${_ORDINAL})`+
  `(?:[-\\s](?:${_CARDINAL}|${_ORDINAL}))?)`;

const CHAPTER_HEADING=new RegExp(
  `^\\s*(${DIVISION_WORDS})\\s*[:.—\\-]?\\s*(${_ENUM})\\b\\s*[.:;—–\\-]?\\s*(.{0,70})?$`,"i");
const NUMBERED_SECTION=/^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-ZÀ-Þ][^\n]{1,60})$/;
const BARE_NUMERAL=/^\s*([IVXLCDM]{1,7}|\d{1,3})\s*\.?\s*$/;
const METADATA_LINE=/^\s*([A-Z][A-Za-z /&'-]{1,28})\s*:\s*\S.*$/;
const _ROMAN={I:1,V:5,X:10,L:50,C:100,D:500,M:1000};
const FRONT_HEADING=/^\s*(PREFACE|INTRODUCTION|INTRODUCTORY NOTE|CONTENTS|TABLE OF CONTENTS|DEDICATION|FOREWORD|ADVERTISEMENT|PROLOGUE|TO THE READER|AUTHOR'?S NOTE|EDITOR'?S NOTE|PUBLISHER'?S NOTE|ILLUSTRATIONS|LIST OF [A-Z ]+|NOTE TO THE [A-Z ]+|NOTE\b[A-Z ]*|PREFATORY [A-Z ]+)\s*\.?\s*$/;
/* Named front matter conventionally set in title case, not caps. Matched
   case-insensitively, but the line must be the name and nothing else (note the
   anchored $), so a sentence merely starting with the word is never caught. */
const NAMED_FRONT_HEADING=/^\s*(?:THE\s+)?(PROLOGUE|CONTENTS|TABLE\s+OF\s+CONTENTS|DRAMATIS\s+PERSON(?:AE|Æ|E)|PERSONS\s+REPRESENTED|CHARACTERS(?:\s+IN\s+THE\s+PLAY)?|ARGUMENT|DEDICATION|PREFACE|FOREWORD|INTRODUCTION)\s*[.:]?\s*$/i;
const CONTENTS_HEADING=/^\s*(?:TABLE\s+OF\s+)?CONTENTS\s*[.:]?\s*$/i;
const BACK_HEADING=/^\s*(APPENDIX|GLOSSARY|INDEX|BIBLIOGRAPHY|NOTES|ENDNOTES|POSTSCRIPT|AFTERWORD|COLOPHON|TRANSCRIBER'?S NOTES?|FOOTNOTES)\b.*$/;
const MAX_HEADING_LEN=80;

/* Must match Python's [^\W\d_]+ under re.UNICODE, i.e. letters and combining
   marks but not digits or underscore.
   NOT [^\W\d_] here: JavaScript's \w is ASCII-only even with the /u flag, so
   that form splits "\u00e6sthetic" and "na\u00efve" into pieces while Python keeps them
   whole. The parity check caught this as a 9-token drift on a real text. */
const WORD_RE=/[\p{L}\p{M}]+(?:['\u2019][\p{L}\p{M}]+)*/gu;
function tokens(t){return t.match(WORD_RE)||[]}
function countTT(t){const w=tokens(t);return{tokens:w.length,types:new Set(w.map(x=>x.toLowerCase())).size}}

function isUpper(s){const L=[...s].filter(c=>/\p{L}/u.test(c));return L.length>0&&L.every(c=>c===c.toUpperCase())}

/* The guard that matters: text after the enumerator must begin with a capital.
   That separates "Chapter 1. The Beginning" from "Section 3 of the act…". */
function isChapterHeading(l){
  const s=l.trim();
  if(!s||s.length>MAX_HEADING_LEN) return false;
  const m=CHAPTER_HEADING.exec(s);
  if(!m) return false;
  const trailing=(m[3]||"").trim();
  if(trailing&&!/^[A-ZÀ-Þ"'‘’“”(\[—–-]/.test(trailing)) return false;
  return true;
}

function romanToInt(s){
  let total=0,prev=0;
  for(const ch of [...s.toUpperCase()].reverse()){
    const v=_ROMAN[ch];
    if(v===undefined) return null;
    total+= v<prev ? -v : v;
    prev=Math.max(prev,v);
  }
  return total||null;
}
function numeralValue(s){
  s=s.trim().replace(/\.$/,"");
  if(/^\d+$/.test(s)) return parseInt(s,10);
  return romanToInt(s);
}

function findNumberedSections(lines,start,end,skip){
  const hits=[];
  for(let i=start;i<end;i++){
    if(skip(i)) continue;
    const s=lines[i].trim();
    if(!s||s.length>MAX_HEADING_LEN) continue;
    const m=NUMBERED_SECTION.exec(s);
    if(m&&(!/[.,;]$/.test(s)||(s.split(" ").length-1)<=6)) hits.push([i,m[1]]);
  }
  if(hits.length<2) return [];
  if(hits[0][1].split(".")[0]!=="1") return [];
  return hits.map(h=>h[0]);
}

/* Requires an ascending run beginning at 1, at least three long — which is
   exactly what stops an isolated year like 1847 being read as a chapter. */
function findNumeralSequence(lines,start,end,skip){
  const cands=[];
  for(let i=start;i<end;i++){
    if(skip(i)) continue;
    const s=lines[i].trim();
    if(!s||!BARE_NUMERAL.test(s)) continue;
    const v=numeralValue(s);
    if(v!==null&&v>=1&&v<=200) cands.push([i,v]);
  }
  let best=[],run=[],expect=1;
  for(const [i,v] of cands){
    if(v===expect){run.push(i);expect++}
    else if(v===1){ if(run.length>best.length) best=run; run=[i]; expect=2 }
  }
  if(run.length>best.length) best=run;
  return best.length>=3?best:[];
}

/* "Participant: P04", "DOI: …" — the header block on transcripts, article
   extracts and scraped pages. Needs 2+ consecutive lines near the top, so a
   line of dialogue mid-text is not caught. */
function findMetadataBlock(lines,start,end){
  const limit=Math.min(end,start+30);
  let runStart=null;
  for(let i=start;i<limit;i++){
    const s=lines[i].trim();
    if(s&&METADATA_LINE.test(s)&&s.length<=120){ if(runStart===null) runStart=i }
    else if(s){
      if(runStart!==null&&i-runStart>=2) return [runStart,i];
      runStart=null;
    }
  }
  if(runStart!==null&&limit-runStart>=2) return [runStart,limit];
  return null;
}

/* A table of contents repeats the headings it lists — that duplication is the
   signal, far more robust than looking for the word "Contents", which many
   editions omit. Without this, body begins inside the contents list. */
const MAX_CONTENTS_GAP=4;        // lines between consecutive entries
const MIN_CONTENTS_ENTRIES=3;
const CONTENTS_MATCH_RATIO=0.6;  // share that must reappear later

function splitContentsList(lines,idx){
  if(idx.length<MIN_CONTENTS_ENTRIES+1) return [[],idx];
  const titles=idx.map(i=>lines[i].trim().toLowerCase());

  // 1. Opening run of headings packed close together. Contents entries sit a
  //    line or two apart; real headings are separated by whole chapters.
  let run=1;
  while(run<idx.length&&(idx[run]-idx[run-1])<=MAX_CONTENTS_GAP) run++;
  if(run<MIN_CONTENTS_ENTRIES||run>=idx.length) return [[],idx];

  // 2. Confirm by duplication — a *majority*, not all. Requiring every entry
  //    to reappear means one undetected body heading disables the rule.
  const rest=new Set(titles.slice(run));
  let hits=0;
  for(const t of titles.slice(0,run)) if(rest.has(t)) hits++;
  if(hits/run<CONTENTS_MATCH_RATIO) return [[],idx];

  return [idx.slice(0,run),idx.slice(run)];
}

/* Structural depth per division word. Only ranks actually present are used,
   renumbered from 1 — so ACT/SCENE and BOOK/CHAPTER both give levels 1 and 2,
   while a novel using only CHAPTER stays flat. */
const DIVISION_RANK={VOLUME:1,BOOK:2,PART:2,ACT:2,
  CHAPTER:3,SCENE:3,CANTO:3,STAVE:3,LETTER:3,SECTION:3,EPISODE:3,
  FYTTE:3,MOVEMENT:3,INTERLUDE:3,LECTURE:3,SERMON:3,TALE:3,NIGHT:3};
const _DIVISION_FIRST_WORD=new RegExp(`^\\s*(${DIVISION_WORDS})\\b`,"i");

function rankOf(r){
  if(r.label!==BODY) return null;
  if(r.kind==="section"){
    const m=/^\s*(\d+(?:\.\d+)*)/.exec(r.title);
    return m ? (m[1].split(".").length-1)+1 : 1;
  }
  const m=_DIVISION_FIRST_WORD.exec(r.title);
  if(m) return DIVISION_RANK[m[1].toUpperCase()] ?? 3;
  return null;
}

/* Regions stay flat and non-overlapping — that invariant is what guarantees no
   line is counted twice or lost. Nesting is metadata only. */
function assignHierarchy(regions){
  const ranks=regions.map(rankOf);
  const present=[...new Set(ranks.filter(r=>r!==null))].sort((a,b)=>a-b);
  if(present.length<=1) return regions;
  const levelOf={}; present.forEach((r,i)=>levelOf[r]=i+1);

  const stack=[];
  return regions.map((r,i)=>{
    const rank=ranks[i];
    if(rank===null){ stack.length=0; return {...r,level:1,parent:null} }
    const lvl=levelOf[rank];
    while(stack.length&&stack[stack.length-1][0]>=lvl) stack.pop();
    const parent=stack.length?stack[stack.length-1][1]:null;
    stack.push([lvl,i]);
    return {...r,level:lvl,parent};
  });
}

function childrenOf(regions,i){
  const out=[];
  regions.forEach((r,j)=>{ if(r.parent===i) out.push(j) });
  return out;
}
function subtreeWords(lines,regions,i){
  let total=0; const stack=[i];
  while(stack.length){
    const cur=stack.pop();
    total+=countTT(lines.slice(regions[cur].start,regions[cur].end).join("\n")).tokens;
    for(const c of childrenOf(regions,cur)) stack.push(c);
  }
  return total;
}

function findBodyHeadings(lines,start,end,skip){
  const kw=[];
  for(let i=start;i<end;i++) if(!skip(i)&&isChapterHeading(lines[i])) kw.push(i);
  if(kw.length) return [kw,"chapter","division heading"];
  const ns=findNumberedSections(lines,start,end,skip);
  if(ns.length) return [ns,"section","numbered section heading"];
  const seq=findNumeralSequence(lines,start,end,skip);
  if(seq.length) return [seq,"chapter","bare numeral in ascending sequence"];
  return [[],null,null];
}
/* Two routes: the generic list needs ALL CAPS (its patterns end in wildcards,
   so case-insensitivity would over-match); the named list allows title case
   because those patterns match the whole line exactly. */
function isFrontHeading(l){
  const s=l.trim();
  if(!s||s.length>MAX_HEADING_LEN) return false;
  if(NAMED_FRONT_HEADING.test(s)) return true;
  return isUpper(s)&&FRONT_HEADING.test(s);
}
function isBackHeading(l){const s=l.trim();return !!s&&s.length<=MAX_HEADING_LEN&&isUpper(s)&&BACK_HEADING.test(s)}

function licenceScore(t){const lo=t.toLowerCase();return LICENCE_PHRASES.filter(p=>lo.includes(p)).length}

/* Requires >=2 distinct legal phrases AND the word "gutenberg", so a novel
   discussing copyright or a trademark dispute is never flagged. */
function findLicenceBlocks(lines,min=2){
  const out=[]; let start=null;
  for(let i=0;i<=lines.length;i++){
    const line=i<lines.length?lines[i]:"";
    if(line.trim()){ if(start===null) start=i; }
    else if(start!==null){
      const t=lines.slice(start,i).join("\n"), s=licenceScore(t), lo=t.toLowerCase();
      if(s>=min && (lo.includes("gutenberg")||lo.includes("pglaf"))) out.push([start,i,s]);
      start=null;
    }
  }
  return out;
}

function* blocks(lines,start,end){
  let a=null;
  for(let i=start;i<=end;i++){
    const blank=i>=end||!lines[i].trim();
    if(!blank&&a===null) a=i;
    else if(blank&&a!==null){ yield [a,i]; a=null }
  }
}

function findTranscriberNotes(lines,start,end,window=TRANSCRIBER_WINDOW){
  const found=[];
  const bl=[...blocks(lines,start,end)];

  // Unambiguous heading: recognised anywhere. Where it stands alone, the
  // following block is taken with it, since that is where the note lives.
  bl.forEach(([a,b],i)=>{
    if(!TRANSCRIBER_HEADING.test(lines[a])) return;
    const end2=(b-a===1&&i+1<bl.length)?bl[i+1][1]:b;
    found.push([a,end2]);
  });

  // Prefix match: could begin real prose, so bounded to one block and to a
  // window at the head or tail of the content.
  const zones=[[start,Math.min(end,start+window)],[Math.max(start,end-window),end]];
  for(const [zs,ze] of zones){
    if(ze<=zs) continue;
    for(const [a,b] of blocks(lines,zs,ze)){
      if(TRANSCRIBER_OPENING.test(lines[a])&&!found.some(f=>f[0]<=a&&a<f[1]))
        found.push([a,b]);
    }
  }
  return found.sort((x,y)=>x[0]-y[0]);
}

function trimBlank(lines,a,b){
  while(a<b && !lines[a].trim()) a++;
  while(b>a && !lines[b-1].trim()) b--;
  return b>a?[a,b]:null;
}
function findMarker(lines,pats){for(let i=0;i<lines.length;i++)for(const p of pats)if(p.test(lines[i]))return i;return null}
function findMarkerLast(lines,pats){for(let i=lines.length-1;i>=0;i--)for(const p of pats)if(p.test(lines[i]))return i;return null}

function R(label,kind,title,start,end,confidence,evidence){
  return {label,kind,title,start,end,confidence,evidence,level:1,parent:null};
}

function segment(lines){
  const n=lines.length, regions=[], notes=[];
  const pgStart=findMarker(lines,[PG_START,PG_START_OLD]);
  const pgEnd=findMarkerLast(lines,[PG_END,PG_END_OLD]);
  let cStart=0,cEnd=n;

  if(pgStart!==null){
    regions.push(R(PG_HEADER,"pg_header","Project Gutenberg header",0,pgStart+1,1,"explicit START marker"));
    cStart=pgStart+1;
  }
  if(pgEnd!==null && pgEnd>=cStart){
    regions.push(R(PG_LICENCE,"pg_footer","Project Gutenberg licence",pgEnd,n,1,"explicit END marker"));
    cEnd=pgEnd;
  }

  const licSpans=[];
  if(pgStart===null||pgEnd===null){
    for(const [s,e,sc] of findLicenceBlocks(lines.slice(cStart,cEnd))){
      const a=s+cStart,b=e+cStart;
      licSpans.push([a,b]);
      regions.push(R(PG_LICENCE,"licence_block","Licence text (unmarked)",a,b,
        Math.min(1,.5+.15*sc),sc+" licence phrases, no sentinel marker"));
    }
  }
  /* Transcriber credits sit *after* the START marker, so they escape the
     header region, and often name pglaf.org without saying "gutenberg". */
  for(const [a,b] of findTranscriberNotes(lines,cStart,cEnd)){
    licSpans.push([a,b]);
    regions.push(R(PG_HEADER,"transcriber_note",lines[a].trim().slice(0,60),
      a,b,.9,"producer/transcriber credit block near start or end"));
  }

  const inLic=i=>licSpans.some(([s,e])=>s<=i&&i<e);

  /* Metadata header is detected before body headings, so it is found even in
     texts with no chapter structure — transcripts and article extracts. */
  const metaSpan=findMetadataBlock(lines,cStart,cEnd);
  if(metaSpan) regions.push(R(FRONT_MATTER,"metadata","Metadata header",
    metaSpan[0],metaSpan[1],.85,"consecutive 'Key: value' lines at head of document"));

  let [headingIdx,headingKind,headingEvidence]=findBodyHeadings(lines,cStart,cEnd,inLic);

  const [contentsIdx,realIdx]=splitContentsList(lines,headingIdx);
  headingIdx=realIdx;
  let contentsSpan=null;
  if(contentsIdx.length){
    // Absorb a "Contents" heading above the list, and anything between it and
    // the first entry — those will be further entries, not real sections.
    let cStartC=contentsIdx[0], probe=cStartC-1, seen=0;
    while(probe>=cStart&&seen<8){
      const s=lines[probe].trim();
      if(s){ seen++; if(CONTENTS_HEADING.test(s)){cStartC=probe;break} }
      probe--;
    }
    contentsSpan=[cStartC,contentsIdx[contentsIdx.length-1]+1];
    regions.push(R(FRONT_MATTER,"contents","Contents",contentsSpan[0],contentsSpan[1],.8,
      `${contentsIdx.length} headings repeated later in the text`));
  }

  let bodyStart=headingIdx.length?headingIdx[0]:null;

  if(bodyStart===null){
    const restStart=metaSpan?metaSpan[1]:cStart;
    if(cEnd>restStart) regions.push(R(BODY,"body","(whole text)",restStart,cEnd,.4,
      "no structural headings found; whole text kept as body"));
    let note="No structural headings found. Tried: division headings "+
      "(Chapter/Book/Part/Act/Scene…), numbered sections (1. Introduction) and "+
      "bare numeral sequences. The whole text was kept as body and nothing was removed.";
    if(metaSpan) note+=" A metadata header was found and can be removed separately.";
    notes.push(note);
    return finalise(lines,regions,notes);
  }

  if(bodyStart>cStart){
    // Headings *inside* the contents list are entries, not sections.
    const inContents=i=>!!contentsSpan&&contentsSpan[0]<=i&&i<contentsSpan[1];
    const heads=[];
    for(let i=cStart;i<bodyStart;i++)
      if(isFrontHeading(lines[i])&&!inLic(i)&&!inContents(i)) heads.push(i);
    const first=heads.length?heads[0]:bodyStart;

    // Split the title page around the metadata block rather than straddling
    // it, so each piece gets its own accurate title.
    let spans=[[cStart,first]];
    if(metaSpan&&cStart<=metaSpan[0]&&metaSpan[0]<first)
      spans=[[cStart,metaSpan[0]],[metaSpan[1],first]];

    for(const [a,b] of spans){
      const sp=trimBlank(lines,a,Math.min(b,first));
      if(sp){
        let t="Title page";
        for(let i=sp[0];i<sp[1];i++) if(lines[i].trim()){t=lines[i].trim();break}
        regions.push(R(FRONT_MATTER,"titlepage",t,sp[0],sp[1],.8,"text before first front-matter heading"));
      }
    }
    heads.forEach((h,ix)=>{
      const end=ix+1<heads.length?heads[ix+1]:bodyStart;
      regions.push(R(FRONT_MATTER,lines[h].trim().toLowerCase().replace(/ /g,"_"),
        lines[h].trim(),h,end,.9,"uppercase front-matter heading"));
    });
  }

  const chapters=headingIdx.filter(i=>i>=bodyStart);

  let backStart=null;
  for(let i=bodyStart;i<cEnd;i++) if(isBackHeading(lines[i])&&!inLic(i)){backStart=i;break}
  const bodyEnd=backStart!==null?backStart:cEnd;

  chapters.forEach((cs,ix)=>{
    if(cs>=bodyEnd) return;
    let ce=ix+1<chapters.length?chapters[ix+1]:bodyEnd;
    ce=Math.min(ce,bodyEnd);
    regions.push(R(BODY,headingKind||"chapter",lines[cs].trim(),cs,ce,
      headingKind==="chapter"?1:.85,headingEvidence||"chapter heading"));
  });

  if(backStart!==null&&backStart<cEnd)
    regions.push(R(BACK_MATTER,"back_matter",lines[backStart].trim(),backStart,cEnd,.7,"back-matter heading"));

  return finalise(lines,regions,notes);
}

/* Resolve overlaps by precedence, then claim any orphan content line as
   UNKNOWN (which defaults to keep). Mirrors _finalise in segment.py. */
function finalise(lines,regions,notes){
  const n=lines.length, owner=new Array(n).fill(null);
  const sorted=[...regions].sort((a,b)=>(PRECEDENCE[a.label]-PRECEDENCE[b.label])||(a.start-b.start));
  for(const r of sorted)
    for(let i=Math.max(0,r.start);i<Math.min(r.end,n);i++){
      const cur=owner[i];
      if(cur===null||PRECEDENCE[r.label]>=PRECEDENCE[cur.label]) owner[i]=r;
    }

  const unk=R(UNKNOWN,"unclassified","",0,0,0,"no rule matched; retained by default");
  for(let i=0;i<n;i++) if(owner[i]===null&&lines[i].trim()) owner[i]=unk;

  const out=[]; let i=0;
  while(i<n){
    const r=owner[i];
    if(r===null){i++;continue}
    let j=i; while(j<n&&owner[j]===r) j++;
    const sp=trimBlank(lines,i,j);
    if(sp){
      // A split piece takes its title from its own text, not the original's.
      let title=r.title;
      if(sp[0]!==r.start){
        // The tail of a split region must not inherit the original's title.
        if(r.kind==="titlepage"||r.kind==="unclassified"){
          for(let k=sp[0];k<sp[1];k++) if(lines[k].trim()){title=lines[k].trim();break}
        } else if((r.kind==="chapter"||r.kind==="section")&&r.title){
          title=r.title+" (continued)";
        }
      }
      out.push(R(r.label,r.kind,title,sp[0],sp[1],r.confidence,r.evidence));
    }
    i=j;
  }
  return {regions:assignHierarchy(out),notes};
}

function coverageGaps(lines,regions){
  const n=lines.length, cov=new Array(n).fill(false);
  for(const r of regions) for(let i=r.start;i<Math.min(r.end,n);i++) cov[i]=true;
  const gaps=[]; let s=null;
  for(let i=0;i<n;i++){
    const bad=!cov[i]&&!!lines[i].trim();
    if(bad&&s===null) s=i; else if(!bad&&s!==null){gaps.push([s,i]);s=null}
  }
  if(s!==null) gaps.push([s,n]);
  return gaps;
}

/* ---- page furniture ----------------------------------------------------
   Running heads, running feet and page numbers.

   The signal is REGULARITY, not appearance. A running head recurs at the page
   interval; a refrain recurs wherever the author chose. Rules based on short
   lines, capitals or plain repetition all destroy prose instead.

   Mirrors src/corpusprep/furniture.py. Parameter names are kept identical so
   that any drift between the two shows up as a readable diff.
   Nothing here deletes: furniture is a set of 1-based line numbers.          */

const FURN_MAX_LEN=60;          // longest line that can be furniture
const FURN_MIN_OCCURRENCES=5;   // fewest repeats to consider
const FURN_MAX_CV=0.25;         // highest irregularity accepted
const FURN_PAGE_TOLERANCE=0.25; // how far a gap may sit from the page estimate
const FURN_NEAR_DUPLICATE=0.85; // similarity at which an OCR variant is folded in
const FURN_MAX_PAGENO_LEN=6;

// Characters OCR commonly confuses with digits. A page number read as `l3`
// still leaves a letter behind after digit-stripping, so it never joins the
// page-number series and is silently kept.
const DIGIT_LOOKALIKE={l:"1",I:"1","|":"1",i:"1",O:"0",o:"0",D:"0",
                       S:"5",s:"5",B:"8",Z:"2"};

// `\p{L}\p{M}` rather than `\w`: JavaScript's `\w` is ASCII-only, which once
// split words such as aesthetic and naive and cost a nine-token parity drift.
const FURN_PUNCT=/[^\p{L}\p{M}\p{N}\s]/gu;

function furnNormalise(line){
  // Digits are removed deliberately: `JANE EYRE 42` and `JANE EYRE 43` are the
  // same running head on consecutive pages and would not group otherwise.
  return line.replace(/\d+/g," ").replace(FURN_PUNCT," ")
             .replace(/\s+/g," ").trim().toLowerCase();
}

function looksLikePageNumber(line){
  const s=line.replace(FURN_PUNCT,"").trim();
  if(!s||s.length>FURN_MAX_PAGENO_LEN) return false;
  // A single character must be a real digit. Lookalike substitution would read
  // a lone `I` as 1, and a lone `I` is far more often the pronoun, or a roman
  // numeral marking a chapter, than a page number.
  if(s.length===1) return /^\d$/.test(s);
  // At least half the characters must ALREADY be digits.
  //
  // Substitution models OCR corrupting a digit or two inside a number. It must
  // not be allowed to manufacture a number out of a word: without this test
  // `So` maps to 50 and `Bo` to 80, and any common short word that happens to
  // recur at the page interval is deleted as a page number.
  let real=0;
  for(const ch of s) if(ch>="0"&&ch<="9") real++;
  if(real*2<s.length) return false;
  let out="";
  for(const ch of s) out+=(DIGIT_LOOKALIKE[ch]!==undefined?DIGIT_LOOKALIKE[ch]:ch);
  return /^\d+$/.test(out);
}

function furnCV(gaps){
  if(gaps.length<2) return Infinity;
  const mean=gaps.reduce((a,b)=>a+b,0)/gaps.length;
  if(mean===0) return Infinity;
  const v=gaps.reduce((a,b)=>a+(b-mean)*(b-mean),0)/gaps.length;
  return Math.sqrt(v)/mean;
}

function furnMedian(xs){
  if(!xs.length) return 0;
  const s=[...xs].sort((a,b)=>a-b), m=s.length>>1;
  return s.length%2?s[m]:(s[m-1]+s[m])/2;
}

// Equivalent to Python's difflib.SequenceMatcher.ratio(), which is 2*M/T over
// the matching blocks. Implemented directly rather than approximated, so the
// merge decision cannot drift from the Python side.
function seqRatio(a,b){
  if(!a.length&&!b.length) return 1;
  const matching=(x,y)=>{
    if(!x.length||!y.length) return 0;
    let best=0,bi=0,bj=0;
    let prev=new Array(y.length+1).fill(0);
    for(let i=0;i<x.length;i++){
      const cur=new Array(y.length+1).fill(0);
      for(let j=0;j<y.length;j++){
        if(x[i]===y[j]){
          cur[j+1]=prev[j]+1;
          if(cur[j+1]>best){best=cur[j+1];bi=i+1-cur[j+1];bj=j+1-cur[j+1]}
        }
      }
      prev=cur;
    }
    if(!best) return 0;
    return best+matching(x.slice(0,bi),y.slice(0,bj))
               +matching(x.slice(bi+best),y.slice(bj+best));
  };
  return 2*matching(a,b)/(a.length+b.length);
}

function mergeNearDuplicates(groups,originals){
  /* Fold OCR-corrupted variants back into the series they belong to.

     Scanning misreads characters, so `JANE EYRE` becomes `IANE EYRE` on one
     page in ten. Left separate, the corrupted instance is missing from its
     series, which doubles one gap and inflates the irregularity score enough
     to reject a perfectly good running head.

     That is a data problem, not a threshold problem, and must not be fixed by
     loosening FURN_MAX_CV: a looser limit would start admitting refrains.

     Merging is one-directional, so two large distinct heads are never
     combined.                                                              */
  const keys=Object.keys(groups).sort((a,b)=>groups[b].length-groups[a].length);
  const absorbed=new Set();
  for(let i=0;i<keys.length;i++){
    const big=keys[i];
    if(absorbed.has(big)||big.charCodeAt(0)===0) continue;
    for(let j=i+1;j<keys.length;j++){
      const small=keys[j];
      if(absorbed.has(small)||small.charCodeAt(0)===0) continue;
      // Only ever absorb the clearly smaller party, so that two genuine heads
      // of similar frequency stay apart.
      if(groups[small].length*3>groups[big].length) continue;
      if(seqRatio(big,small)>=FURN_NEAR_DUPLICATE){
        groups[big]=groups[big].concat(groups[small]);
        absorbed.add(small);
      }
    }
  }
  for(const k of absorbed){delete groups[k];delete originals[k]}
  for(const k in groups) groups[k].sort((a,b)=>a-b);
}

function furnCollect(lines,skip){
  skip=skip||new Set();
  const groups=Object.create(null),originals=Object.create(null),
        numeric=Object.create(null);
  const PAGENO=" page-number";
  for(let i=0;i<lines.length;i++){
    const n=i+1;
    if(skip.has(n)) continue;
    const s=lines[i].trim();
    if(!s||s.length>FURN_MAX_LEN) continue;
    let key;
    // Page numbers first: they form one series together, which is what they
    // are. Checked before normalisation so OCR misreadings such as `l3` are
    // recognised rather than left as the stray letter `l`.
    // A descriptive label rather than the first number seen. The review table
    // is meant to be read, and a row headed "1" tells the reader nothing about
    // what is being proposed for removal.
    if(looksLikePageNumber(s)){ key=PAGENO; numeric[key]=true;
                                originals[key]="(page numbers)"; }
    else { key=furnNormalise(s); if(!key) continue; }
    (groups[key]||(groups[key]=[])).push(n);
    if(originals[key]===undefined) originals[key]=s;
  }
  mergeNearDuplicates(groups,originals);

  const out=[];
  for(const key in groups){
    const where=groups[key];
    if(where.length<FURN_MIN_OCCURRENCES) continue;
    const gaps=[];
    for(let k=1;k<where.length;k++) gaps.push(where[k]-where[k-1]);
    out.push({text:originals[key],normal:key,lines:where,
              isNumeric:!!numeric[key],gaps,cv:furnCV(gaps),
              medianGap:furnMedian(gaps),accepted:false,reason:""});
  }
  return out;
}

function pageNumberValue(line){
  const s=line.replace(FURN_PUNCT,"").trim();
  if(!s||s.length>FURN_MAX_PAGENO_LEN) return null;
  if(s.length===1) return /^\d$/.test(s)?parseInt(s,10):null;
  let real=0;
  for(const ch of s) if(ch>="0"&&ch<="9") real++;
  if(real*2<s.length) return null;
  let out="";
  for(const ch of s) out+=(DIGIT_LOOKALIKE[ch]!==undefined?DIGIT_LOOKALIKE[ch]:ch);
  return /^\d+$/.test(out)?parseInt(out,10):null;
}

// Indices of the longest ascending subsequence, gaps allowed. Page numbers
// count up; missing and misread pages leave holes, but never go backwards.
function ascendingRun(values){
  const n=values.length;
  if(!n) return [];
  const best=new Array(n).fill(1), prev=new Array(n).fill(-1);
  for(let i=0;i<n;i++) for(let j=0;j<i;j++)
    if(values[j]<values[i]&&best[j]+1>best[i]){best[i]=best[j]+1;prev[i]=j}
  let end=0;
  for(let i=1;i<n;i++) if(best[i]>best[end]) end=i;
  const out=[];
  while(end!==-1){out.push(end);end=prev[end]}
  return out.reverse();
}

/* Keep only the lines of a numeric series that count upwards.

   This is what makes page numbers independent evidence. Any recurring line can
   be regular; only a page number counts up, and a refrain cannot fake an
   ascending sequence. Without this test the rule below has nothing to anchor
   on.                                                                       */
function restrictToAscending(c,lines){
  const pairs=[];
  for(const ln of c.lines){
    const v=pageNumberValue(lines[ln-1]);
    if(v!==null) pairs.push([ln,v]);
  }
  if(pairs.length<FURN_MIN_OCCURRENCES) return false;
  const keep=ascendingRun(pairs.map(p=>p[1]));
  if(keep.length<FURN_MIN_OCCURRENCES) return false;
  c.lines=keep.map(i=>pairs[i][0]);
  c.gaps=[];
  for(let k=1;k<c.lines.length;k++) c.gaps.push(c.lines[k]-c.lines[k-1]);
  c.cv=furnCV(c.gaps);
  c.medianGap=furnMedian(c.gaps);
  return true;
}

/* Estimate the page length FROM THE PAGE-NUMBER SERIES ALONE.

   An earlier version took the most regular series of any kind. That was
   circular, and real text exposed it immediately: in a poem of fixed stanza
   length the refrain recurs perfectly regularly, becomes the page-length
   estimate, and then validates itself against it. On a real ballad collection
   it marked 63 lines of verse as furniture.

   If no ascending page-number sequence exists, the document is not
   page-imaged and no running head can be corroborated.                      */
function estimatePageLength(cands){
  const numeric=cands.filter(c=>c.isNumeric&&c.cv<FURN_MAX_CV&&c.medianGap>0);
  if(!numeric.length) return 0;
  numeric.sort((a,b)=>a.cv-b.cv||b.lines.length-a.lines.length);
  return numeric[0].medianGap;
}

function furnJudge(cands,pageLength){
  const pc=x=>Math.round(x*100)+"%";
  for(const c of cands){
    if(c.cv>=FURN_MAX_CV){
      c.reason="irregular: gaps vary by "+pc(c.cv)+", above the "
              +pc(FURN_MAX_CV)+" limit";
      continue;
    }
    if(pageLength<=0){
      c.reason="no ascending page-number sequence in this text, so there is "
              +"no page structure to corroborate against";
      continue;
    }
    const ratio=c.medianGap/pageLength;
    const near=Math.min(...[1,2,3].map(n=>Math.abs(ratio-n)));
    if(near>FURN_PAGE_TOLERANCE){
      c.reason="regular but off-page: recurs every "+Math.round(c.medianGap)
              +" lines, page is "+Math.round(pageLength);
      continue;
    }
    c.accepted=true;
    c.reason="recurs every "+Math.round(c.medianGap)+" lines ("
            +ratio.toFixed(1)+" pages), gaps vary by "+pc(c.cv);
  }
  return cands;
}

/* ---- catchwords --------------------------------------------------------
   In books printed between roughly 1500 and 1800 the last line of each page
   carries the first word of the following page, so the binder could confirm
   the sheets were gathered in order.

   Unlike a running head, a catchword carries its own proof: it IS the first
   word of the next page, and that can be checked rather than estimated.
   Mirrors the Python in src/corpusprep/furniture.py.                       */

const CATCHWORD_MAX_WORDS=3;
const CATCHWORD_MAX_LEN=30;
const CATCHWORD_MIN_PAGES=4;
const CATCHWORD_MIN_RATIO=0.35;

// The long s is standard in this period and survives in many transcriptions.
// Unfolded, `saying` and the long-s form are different words and every
// catchword containing one fails to match.
function catchWords(line){
  return line.replace(/ſ/g,"s").replace(FURN_PUNCT," ")
             .replace(/\s+/g," ").trim().toLowerCase().split(" ").filter(Boolean);
}

function findCatchwords(lines,pageBreaks,furniture,skip){
  const ignore=new Set(furniture);
  if(skip) for(const i of skip) ignore.add(i);
  const n=lines.length;

  // Nearest real line, passing over blanks and furniture.
  const step=(i,d)=>{
    while(i>=1&&i<=n){
      if(!ignore.has(i)&&lines[i-1].trim()) return i;
      i+=d;
    }
    return null;
  };

  const matches=[];
  for(const p of [...pageBreaks].sort((a,b)=>a-b)){
    const c=step(p-1,-1), nx=step(p+1,1);
    if(c===null||nx===null) continue;
    const text=lines[c-1].trim(), opens=lines[nx-1].trim();
    const m={line:c,text,opens,accepted:false,reason:""};
    matches.push(m);

    const cw=catchWords(text);
    // The length guard, and the only place this rule can destroy text. A page
    // may legitimately end with a full line whose last word opens the next
    // page. A catchword is a fragment set alone on its own line.
    if(!cw.length||cw.length>CATCHWORD_MAX_WORDS||text.length>CATCHWORD_MAX_LEN){
      m.reason="too long to be a catchword: "+cw.length+" words, "
              +text.length+" characters";
      continue;
    }
    const head=catchWords(opens).slice(0,cw.length);
    if(head.length===cw.length&&head.every((w,i)=>w===cw[i])){
      m.accepted=true;
      m.reason='opens the next page: "'+opens.slice(0,40)+'"';
    } else {
      m.reason="does not open the next page";
    }
  }

  const hits=matches.filter(m=>m.accepted);
  const ratio=matches.length?hits.length/matches.length:0;
  // One match is coincidence; thirty is a printing convention. Without this
  // test a modern book yields a handful of accidental matches and loses real
  // lines to a rule that should never have fired on it.
  if(hits.length<CATCHWORD_MIN_PAGES||ratio<CATCHWORD_MIN_RATIO){
    for(const m of hits){
      m.accepted=false;
      m.reason="matched, but only "+hits.length+" of "+matches.length
              +" pages do ("+Math.round(ratio*100)+"%); this book does not "
              +"use catchwords";
    }
    return {catchwords:new Set(),matches};
  }
  return {catchwords:new Set(hits.map(m=>m.line)),matches};
}

function findFurniture(lines,skip){
  // Every candidate is returned, accepted or not, with its reason recorded.
  // A rule the user cannot interrogate is a rule the user cannot trust.
  const cands=furnCollect(lines,skip);
  // Numeric series must prove they count upwards before they can be treated
  // as page numbers, and everything downstream depends on that proof.
  for(const c of cands)
    if(c.isNumeric&&!restrictToAscending(c,lines)){
      c.isNumeric=false; c.cv=Infinity;
      c.reason="numbers do not form an ascending sequence";
    }
  const pageLength=estimatePageLength(cands);
  furnJudge(cands,pageLength);
  const marked=new Set();
  for(const c of cands) if(c.accepted) for(const i of c.lines) marked.add(i);

  // Catchwords run second because they need the page breaks the first pass
  // found. Page numbers are where a page ends, so no second estimate of the
  // page boundary is needed and none is made.
  const breaks=[];
  for(const c of cands) if(c.accepted&&c.isNumeric) breaks.push(...c.lines);
  const cw=findCatchwords(lines,breaks,marked,skip);
  for(const i of cw.catchwords) marked.add(i);
  return {furniture:marked,candidates:cands,pageLength,
          catchwords:cw.catchwords,catchwordMatches:cw.matches};
}

function findFurnitureIn(lines,regions){
  /* Search the body only.

     A title page carries the book's title, which is character-for-character
     the running head, and an imprint date, which looks exactly like a page
     number. Searched whole, a scanned novel has its title page mistaken for
     furniture and deleted. Front and back matter have their own conventions
     and are excluded.                                                       */
  const skip=new Set();
  for(const r of regions)
    if(r.label!=="body")
      for(let i=r.start;i<r.end;i++) skip.add(i+1);
  return findFurniture(lines,skip);
}

/* ---- variants ---- */
const PRESETS={
  "verbatim":       {keep:{pg_header:1,pg_licence:1,front_matter:1,body:1,back_matter:1,unknown:1},dropHeadings:0,collapse:0,
                     desc:"Control version. Encoding and line endings normalised; nothing removed."},
  "full":           {keep:{pg_header:0,pg_licence:0,front_matter:1,body:1,back_matter:1,unknown:1},dropHeadings:0,collapse:1,
                     desc:"Everything except Project Gutenberg apparatus."},
  "body-and-front": {keep:{pg_header:0,pg_licence:0,front_matter:1,body:1,back_matter:0,unknown:1},dropHeadings:0,collapse:1,
                     desc:"Front matter plus body, for studies in which the author's preface counts as authorial text."},
  "body-only":      {keep:{pg_header:0,pg_licence:0,front_matter:0,body:1,back_matter:0,unknown:1},dropHeadings:0,collapse:1,
                     desc:"The work itself. Usual choice for stylistic analysis."},
  "body-no-headings":{keep:{pg_header:0,pg_licence:0,front_matter:0,body:1,back_matter:0,unknown:1},dropHeadings:1,collapse:1,
                     desc:"Body with CHAPTER heading lines stripped too. For word lists and frequency counts."},
};

function render(lines,regions,cfg,furniture){
  const kept=[],dropped=[],out=[];
  // Off unless the caller passes both the flag and the line set. The detector
  // has been measured against synthetic text only, and a rule that has never
  // met a real scan must not delete prose on its own authority.
  const dropFurn=!!(cfg.dropFurniture&&furniture);
  let furnitureRemoved=0;
  for(const r of regions){
    if(!cfg.keep[r.label]){dropped.push(r);continue}
    kept.push(r);
    for(let i=r.start;i<r.end;i++){
      let ln=lines[i];
      if(dropFurn&&furniture.has(i+1)){furnitureRemoved++;continue}
      if(cfg.dropHeadings&&isChapterHeading(ln)) continue;
      out.push(ln.replace(/[ \t]+$/,""));
    }
    out.push("");
  }
  let text=out.join("\n");
  if(cfg.collapse) text=text.replace(/\n{3,}/g,"\n\n");
  text=text.trim()+"\n";
  const tt=countTT(text);
  return {text,kept,dropped,stats:{chars:text.length,lines:text.split("\n").length-1,
    tokens:tt.tokens,types:tt.types,kept:kept.length,dropped:dropped.length,
    furnitureRemoved}};
}

/* =========================================================================
   FORMATS — .docx / .epub / .html extraction, mirroring corpusprep/formats.py

   No libraries. ZIP entries are inflated with the browser's native
   DecompressionStream, so the page stays a single self-contained file.

   PDF is deliberately absent: extraction yields hyphenated line-breaks,
   hard-wrapped lines, running headers and stray page numbers — the exact
   problems this tool cannot repair yet. Importing before repairing would let
   people build bad corpora while trusting the output.
   ========================================================================= */

class UnsupportedFormat extends Error{}

/* ---- minimal ZIP reader ---- */
async function unzip(buf){
  const dv=new DataView(buf), u8=new Uint8Array(buf);
  // Locate End Of Central Directory (scan back over the max comment length)
  let eocd=-1;
  for(let i=u8.length-22;i>=Math.max(0,u8.length-65557);i--){
    if(dv.getUint32(i,true)===0x06054b50){eocd=i;break}
  }
  if(eocd<0) throw new UnsupportedFormat("Not a valid zip-based file (docx/epub).");

  const count=dv.getUint16(eocd+10,true);
  let off=dv.getUint32(eocd+16,true);
  const files={};

  for(let n=0;n<count;n++){
    if(dv.getUint32(off,true)!==0x02014b50) break;
    const method=dv.getUint16(off+10,true);
    const compSize=dv.getUint32(off+20,true);
    const nameLen=dv.getUint16(off+28,true);
    const extraLen=dv.getUint16(off+30,true);
    const commentLen=dv.getUint16(off+32,true);
    const localOff=dv.getUint32(off+42,true);
    const name=new TextDecoder("utf-8").decode(u8.subarray(off+46,off+46+nameLen));

    // Local header: recompute the data offset (its extra field may differ)
    const lNameLen=dv.getUint16(localOff+26,true);
    const lExtraLen=dv.getUint16(localOff+28,true);
    const dataStart=localOff+30+lNameLen+lExtraLen;
    const raw=u8.subarray(dataStart,dataStart+compSize);

    files[name]= method===0 ? raw : await inflateRaw(raw);
    off+=46+nameLen+extraLen+commentLen;
  }
  return files;
}

async function inflateRaw(bytes){
  if(typeof DecompressionStream==="undefined")
    throw new UnsupportedFormat(
      "This browser cannot decompress .docx/.epub files. Use a recent "+
      "Chrome, Edge, Firefox or Safari, or convert the file to .txt.");
  const ds=new DecompressionStream("deflate-raw");
  const stream=new Blob([bytes]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

const dec=b=>new TextDecoder("utf-8").decode(b);

/* ---- HTML → text (mirrors _HTMLText in formats.py) ---- */
const BLOCK_TAGS=new Set(["p","div","br","li","tr","section","article","blockquote",
  "h1","h2","h3","h4","h5","h6","pre","figcaption","td","th"]);
const DROP_TAGS=new Set(["script","style","noscript","head","svg","template"]);

function htmlToText(source){
  const doc=new DOMParser().parseFromString(source,"text/html");
  const out=[]; let buf=[], skip=0, headings=0;

  const flush=()=>{
    const t=buf.join("").trim(); buf=[];
    if(t) out.push(t.replace(/[ \t]{2,}/g," "));
  };
  const isH=t=>t.length===2&&t[0]==="h"&&/\d/.test(t[1]);

  (function walk(node){
    for(const child of node.childNodes){
      if(child.nodeType===3){ if(!skip) buf.push(child.data); continue }
      if(child.nodeType!==1) continue;
      const tag=child.tagName.toLowerCase();
      if(DROP_TAGS.has(tag)){ skip++; walk(child); skip=Math.max(0,skip-1); continue }
      if(BLOCK_TAGS.has(tag)){ flush(); if(isH(tag)){headings++; out.push("")} }
      walk(child);
      if(BLOCK_TAGS.has(tag)){ flush(); if(isH(tag)) out.push("") }
    }
  })(doc);
  flush();

  let text=out.join("\n").replace(/\n{3,}/g,"\n\n");
  return {text,meta:{container:"html",headings}};
}

/* ---- DOCX ---- */
async function docxToText(buf){
  const files=await unzip(buf);
  if(!files["word/document.xml"])
    throw new UnsupportedFormat(
      "Not a Word document (word/document.xml missing). Legacy .doc files "+
      "from Word 97-2003 are a different format. Re-save the file as .docx.");

  const xml=new DOMParser().parseFromString(dec(files["word/document.xml"]),"application/xml");
  const W="http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const lines=[]; let nHead=0;

  for(const p of xml.getElementsByTagNameNS(W,"p")){
    let style="";
    const pr=p.getElementsByTagNameNS(W,"pStyle")[0];
    if(pr) style=pr.getAttributeNS(W,"val")||pr.getAttribute("w:val")||"";

    const parts=[];
    (function walk(n){
      for(const c of n.childNodes){
        if(c.nodeType!==1) continue;
        const ln=c.localName;
        if(ln==="t") parts.push(c.textContent||"");
        else if(ln==="tab"||ln==="br") parts.push(" ");
        else walk(c);
      }
    })(p);
    const text=parts.join("").trim();

    if(/^(Heading|Title|Subtitle)/i.test(style)&&text){
      nHead++;
      if(lines.length&&lines[lines.length-1]!=="") lines.push("");
      lines.push(text); lines.push("");
    } else lines.push(text);
  }
  return {text:lines.join("\n"),meta:{container:"docx",styled_headings:nHead}};
}

/* ---- EPUB ---- */
async function epubToText(buf){
  const files=await unzip(buf);
  const names=Object.keys(files);

  let opfPath=null;
  if(files["META-INF/container.xml"]){
    const c=new DOMParser().parseFromString(dec(files["META-INF/container.xml"]),"application/xml");
    const rf=c.getElementsByTagName("rootfile")[0];
    if(rf) opfPath=rf.getAttribute("full-path");
  }
  if(!opfPath) opfPath=names.find(n=>n.endsWith(".opf"));
  if(!opfPath) throw new UnsupportedFormat("Not a readable EPUB (no OPF package file).");

  const opf=new DOMParser().parseFromString(dec(files[opfPath]),"application/xml");
  const base=opfPath.includes("/")?opfPath.slice(0,opfPath.lastIndexOf("/")+1):"";

  const manifest={};
  for(const it of opf.getElementsByTagName("item"))
    manifest[it.getAttribute("id")]=it.getAttribute("href");

  let order=[];
  for(const ir of opf.getElementsByTagName("itemref")){
    const href=manifest[ir.getAttribute("idref")];
    if(href) order.push(base+href);
  }
  if(!order.length) order=names.filter(n=>/\.(xhtml|html|htm)$/i.test(n));

  const chunks=[]; let n=0;
  for(const name of order){
    if(!files[name]) continue;
    const {text}=htmlToText(dec(files[name]));
    if(text.trim()){chunks.push(text.trim()); n++}
  }
  return {text:chunks.join("\n\n"),meta:{container:"epub",documents:n}};
}

/* ---- dispatch ---- */
async function extractFile(name,buf){
  const ext=(name.match(/\.[^.]+$/)||[""])[0].toLowerCase();
  if(ext===".pdf") throw new UnsupportedFormat(
    "PDF is not supported yet. PDF text extraction produces hyphenated "+
    "line-breaks, hard-wrapped lines, running headers and stray page numbers "+
    "which are the exact problems CorpusPrep cannot yet repair. Export to .docx or "+
    ".txt first.");
  if(ext===".doc") throw new UnsupportedFormat(
    "Legacy .doc (Word 97-2003) is a binary format and is not supported. "+
    "Open it in Word and re-save as .docx.");
  if(ext===".docx") return docxToText(buf);
  if(ext===".epub") return epubToText(buf);
  if([".html",".htm",".xhtml"].includes(ext)){
    let src; try{src=new TextDecoder("utf-8",{fatal:true}).decode(buf)}
    catch(e){src=new TextDecoder("windows-1252").decode(buf)}
    return htmlToText(src);
  }
  return null; // plain text — handled by decode()
}

