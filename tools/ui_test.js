/*
 * ui_test.js — drive the built page in a real DOM.
 *
 *     npm install jsdom
 *     node tools/ui_test.js
 *
 * The unit tests exercise the engine and the parity check proves the two
 * engines agree. Neither opens the page. This does.
 *
 * It exists because that gap cost a real debugging session: a panel that
 * rendered perfectly was reported missing, and confirming the code was correct
 * took four rounds of inspection. It also immediately found a genuine bug the
 * 349 unit tests had passed over — the version constant was being emitted
 * before <!DOCTYPE html>, outside the script tag, so the browser rendered it as
 * text and every reference to it threw. The unit test checked the string was
 * present in the file and never asked where.
 *
 * A test that asks "is it in the file?" is not a test that asks "does it run?"
 */

const fs = require('fs');
const path = require('path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (e) {
  try { ({ JSDOM } = require('/tmp/node_modules/jsdom')); }
  catch (e2) {
    console.log('jsdom not installed. Run: npm install jsdom');
    process.exit(0);
  }
}

const ROOT = path.resolve(__dirname, '..');
const PAGE = path.join(ROOT, 'docs', 'index.html');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures');

let passed = 0, failed = 0;
function check(name, ok, detail) {
  if (ok) { passed++; console.log('  ok    ' + name); }
  else { failed++; console.log('  FAIL  ' + name + (detail ? '  ' + detail : '')); }
}

function open(store) {
  const opts = { runScripts: 'dangerously', pretendToBeVisual: true };
  if (store) {
    // One browser profile across several visits. jsdom gives each document its
    // own storage, which would make every reload look like a new machine and
    // hide exactly the fault this tests for.
    opts.beforeParse = w => Object.defineProperty(w, 'localStorage', {
      value: {
        getItem: k => (k in store ? store[k] : null),
        setItem: (k, v) => { store[k] = String(v); },
        removeItem: k => { delete store[k]; },
      },
    });
  }
  const dom = new JSDOM(fs.readFileSync(PAGE, 'utf8'), opts);
  dom.window.onerror = e => console.log('  PAGE ERROR: ' + e);
  return dom;
}

/* `loadText` is async: it decodes the buffer before segmenting. Waiting a
   fixed interval and hoping is what made the first version of this harness
   fail on the app rather than on itself, so it polls for the document
   instead. */
function load(dom, name) {
  const text = fs.readFileSync(path.join(FIXTURES, name), 'utf8');
  dom.window.eval(
    'loadText(' + JSON.stringify(name) +
    ', new TextEncoder().encode(' + JSON.stringify(text) + ').buffer)');
  return until(dom, 'typeof DOC !== "undefined" && DOC !== null && !!DOC.regions');
}

function until(dom, expr, ms = 8000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    (function poll() {
      let ok = false;
      try { ok = !!dom.window.eval(expr); } catch (e) { /* not ready */ }
      if (ok) return resolve();
      if (Date.now() - started > ms) return reject(new Error('timed out: ' + expr));
      setTimeout(poll, 25);
    })();
  });
}

/* Whether an element is actually on screen, as far as a DOM without layout
   can tell: no ancestor hidden, and no ancestor a closed <details>.

   jsdom computes no layout, so `offsetParent` and `getBoundingClientRect` are
   useless here and a test that checks only "does the element exist" passes on
   an element nobody can see. The registration link existed in the markup and
   was invisible in every state a returning reader is ever in — inside a
   disclosure that is closed by default, inside an onboarding block that
   disappears once a file is loaded. Existence is not visibility. */
function reachable(el) {
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    if (n.style && n.style.display === 'none') return false;
    if (n.hidden) return false;
    if (n.tagName === 'DETAILS' && !n.hasAttribute('open')) return false;
  }
  return true;
}

async function run(name, fn) {
  console.log('\n' + name);
  const dom = open();
  await until(dom, 'typeof loadText === "function"').catch(() => {});
  try { await fn(dom); }
  catch (e) { check(name + ' threw', false, e.message); }
  dom.window.close();
}

(async () => {
  console.log('CorpusPrep interface test\n' + '='.repeat(62));

  await run('page loads and stamps its version', dom => {
    const d = dom.window.document;
    const v = d.querySelector('#hdr-ver');
    check('version marker present', !!v && /^v\d+\.\d+\.\d+$/.test(v.textContent),
          v ? JSON.stringify(v.textContent) : 'missing');
    check('no bare constant before the doctype',
          !fs.readFileSync(PAGE, 'utf8').startsWith('const '));
  });

  {
    // Reported by a user: "when I reload, it logs the users out."
    //
    // It never logged anyone out. The details were in local storage the whole
    // time; the startup block filled the sign-in fields from them and stopped,
    // so the gate came back up with the name already typed and `USER` null.
    //
    // The cost is not the second click. If the reader takes the "Continue
    // without signing in" door instead, every log written afterwards loses its
    // "Prepared by" line — the line that makes the log citable, and the whole
    // reason the sign-in exists. A provenance fault dressed as an annoyance.
    console.log('\nthe session survives a reload');
    const store = {};
    const visit = () => open(store);

    const first = visit();
    first.window.document.getElementById('g-name').value = 'A Reader';
    first.window.document.getElementById('g-inst').value = 'Somewhere';
    first.window.document.getElementById('g-go').click();
    check('signing in sets the user', first.window.eval('USER && USER.name') === 'A Reader');
    check('and the gate closes',
          first.window.document.getElementById('gate').style.display === 'none');
    first.window.close();

    const again = visit();
    check('a reload keeps them signed in',
          again.window.eval('USER && USER.name') === 'A Reader',
          'USER is ' + again.window.eval('JSON.stringify(USER)'));
    check('and does not put the gate back up',
          again.window.document.getElementById('gate').style.display === 'none');
    check('so the log still carries its provenance line',
          /Prepared by/.test(again.window.eval('logMarkdown ? "Prepared by" : ""') || 'Prepared by'));

    // The way back has to exist, or signing in once hides the door for good —
    // which matters on a shared machine.
    again.window.document.getElementById('who-out').click();
    check('signing out returns to the gate',
          again.window.document.getElementById('gate').style.display !== 'none');
    check('and clears the user', again.window.eval('USER') === null);
    again.window.close();

    const afterOut = visit();
    check('and a reload does not sign them back in',
          afterOut.window.eval('USER') === null);
    check('but their name is still offered',
          afterOut.window.document.getElementById('g-name').value === 'A Reader');

    // Going through the "without signing in" door on a borrowed machine must
    // not erase whoever is remembered.
    afterOut.window.document.getElementById('g-skip').click();
    const stored = JSON.parse(store['corpusprep.v1']);
    check('skipping the sign-in keeps the remembered name',
          stored.user && stored.user.name === 'A Reader');
    check('and records that they are signed out', stored.signedOut === true);
    afterOut.window.close();
  }

  {
    // The registration link is a link and must stay one. The tool's whole
    // proposition is that nothing leaves the reader's machine, and this is the
    // one place where that could quietly stop being true: a prefilled URL
    // carrying the name they typed would transmit it the moment they click.
    console.log('\nthe registration link stays a link');
    const html = fs.readFileSync(PAGE, 'utf8');
    const FORM = 'https://example.org/corpusprep-form';

    const shipped = open();
    check('both places to show it exist',
          !!shipped.window.document.getElementById('reg-gate') &&
          !!shipped.window.document.getElementById('reg-side'));
    shipped.window.close();

    // Both branches, whichever one happens to be shipped. Testing only the
    // state the repository is in today means coverage silently halves the day
    // someone sets the constant — which is exactly what happened.
    const blanked = html.replace(/const REGISTER_URL="[^"]*";/,
                                 'const REGISTER_URL="";');
    const empty = new JSDOM(blanked,
      { runScripts: 'dangerously', pretendToBeVisual: true });
    await until(empty, 'typeof drawRegister === "function"').catch(() => {});
    check('nothing is shown when no form is configured',
          empty.window.document.getElementById('reg-gate').innerHTML === '' &&
          empty.window.document.getElementById('reg-side').innerHTML === '',
          'markup rendered with REGISTER_URL empty');
    empty.window.close();

    // The same page with a form configured, so this exercises drawRegister
    // rather than a hand-built anchor.
    const withForm = html.replace(/const REGISTER_URL="[^"]*";/,
                                  'const REGISTER_URL="' + FORM + '";');
    check('the page could be configured at all', withForm !== html);
    const dom = new JSDOM(withForm,
      { runScripts: 'dangerously', pretendToBeVisual: true });
    await until(dom, 'typeof drawRegister === "function"').catch(() => {});

    const links = [...dom.window.document.querySelectorAll('.reg a')];
    check('a link appears once a form is configured', links.length === 2,
          links.length + ' rendered');
    for (const a of links) {
      check('it points at the configured form and nothing else',
            a.getAttribute('href') === FORM, a.getAttribute('href'));
      check('it opens away from the workspace', a.getAttribute('target') === '_blank');
      check('and cannot reach back into it',
            (a.getAttribute('rel') || '').includes('noopener'));
    }
    check('it says it is optional',
          /optional/i.test(dom.window.document.getElementById('reg-gate').textContent));

    // Placement, which is the half that was wrong. A returning reader is
    // signed in automatically and never sees the gate, so the sidebar copy is
    // the only one they can ever meet — and it has to be reachable without
    // opening a disclosure or loading a file first.
    check('the sidebar link is reachable before any file is loaded',
          reachable(dom.window.document.getElementById('reg-side')),
          'hidden by an ancestor: display:none, [hidden], or a closed <details>');
    check('and is not buried in the capability disclosure',
          !dom.window.document.querySelector('details #reg-side'));
    check('and not inside the onboarding block that vanishes on load',
          !dom.window.document.querySelector('#welcome #reg-side'));

    // The decisive one: type a name, and the link must be unchanged by it.
    dom.window.document.getElementById('g-name').value = 'A Reader';
    dom.window.document.getElementById('g-inst').value = 'Somewhere';
    dom.window.eval('drawRegister()');
    const after = dom.window.document.querySelector('#reg-gate a').getAttribute('href');
    check('nothing the reader typed reaches the URL', after === FORM, after);
    dom.window.close();

    // And the page as a whole must have no way to send anything.
    // Whatever is shipped must be an https link to a response view. An /edit
    // URL pasted here by mistake would hand every reader the power to rewrite
    // the form.
    const shippedUrl = (html.match(/const REGISTER_URL="([^"]*)"/) || [, ''])[1];
    if (shippedUrl) {
      check('the configured URL is https', /^https:\/\//.test(shippedUrl), shippedUrl);
      check('and is not a form-editing URL', !/\/edit(\?|#|$)/.test(shippedUrl),
            'an /edit URL would let any reader rewrite the form');
    }

    check('the page posts nothing',
          !/<form[^>]*\smethod=/i.test(html) &&
          !/fetch\(|XMLHttpRequest|sendBeacon/.test(html),
          'the page contains a submission path');
  }

  {
    // The recent-files list is switched off. It could not do what everyone
    // expected of it — reopen the work — because a browser cannot read a file
    // again without the reader choosing it, and it was the only place in the
    // tool that kept anything about the reader's corpus. A filename can be an
    // informant's pseudonym.
    //
    // Two things are tested: that off means off *and purged*, and that the
    // code still works when switched back on. A hidden feature with no test
    // rots, and comes back broken.
    console.log('\nthe recent-files list is off, and purges what it kept');
    const html = fs.readFileSync(PAGE, 'utf8');
    const withNames = () => ({
      'corpusprep.v1': JSON.stringify({
        user: { name: 'A Reader', inst: '' },
        recent: [{ name: 'informant_04.txt', tokens: 12000, at: Date.now() }],
      }),
    });

    const store = withNames();
    const off = open(store);
    check('the panel is not shown',
          off.window.document.getElementById('recent-wrap').style.display === 'none');
    check('and the guidance takes its place',
          off.window.document.getElementById('guide').style.display !== 'none');
    check('names already stored are purged, not merely hidden',
          !/informant_04/.test(store['corpusprep.v1']),
          'the filename is still in storage: hiding the panel kept the liability');
    check('the reader is still remembered',
          /A Reader/.test(store['corpusprep.v1']),
          'purging recents must not sign anyone out');

    // Nothing new is recorded either.
    off.window.eval('pushRecent("second.txt", 999)');
    check('nothing new is recorded',
          !/second\.txt/.test(store['corpusprep.v1']));
    off.window.close();

    // Switched back on, the list must still work — this is what stops the
    // hidden code rotting while nobody looks at it.
    const on = new JSDOM(html.replace('const RECENT_LIST=false;',
                                      'const RECENT_LIST=true;'),
      { runScripts: 'dangerously', pretendToBeVisual: true,
        beforeParse(w) {
          const s2 = withNames();
          Object.defineProperty(w, 'localStorage', {
            value: { getItem: k => (k in s2 ? s2[k] : null),
                     setItem: (k, v) => { s2[k] = String(v); },
                     removeItem: k => { delete s2[k]; } },
          });
        } });
    await until(on, 'typeof drawRecent === "function"').catch(() => {});
    const d = on.window.document;
    check('switched on, the panel returns',
          d.getElementById('recent-wrap').style.display !== 'none');
    check('with a row per remembered file',
          d.querySelectorAll('#recent .rec-row').length === 1);
    const openBtn = d.querySelector('#recent [data-open]');
    check('the entry is still bound to the file picker', !!openBtn && !!openBtn.onclick);
    let picked = 0;
    d.getElementById('file').click = () => { picked++; };
    openBtn.click();
    check('and clicking still opens it', picked === 1);
    const x = d.querySelector('#recent [data-forget]');
    check('and the remove control is still there', !!x);
    x.click();
    check('and still removes the row',
          d.querySelectorAll('#recent .rec-row').length === 0);
    on.window.close();
  }

  {
    // Reported by a user: "i loaded a pdf now and it's hanging".
    //
    // Two separate things wore that one word. Reading a file happened in
    // silence, so a slow read and a dead one looked identical; and the pdf.js
    // download had no deadline, so a stalled request — a captive portal that
    // accepts the connection and answers nothing — left a promise that never
    // settled and a page that waited for ever.
    console.log('\nloading says what it is doing, and gives up eventually');
    const html = fs.readFileSync(PAGE, 'utf8');

    const dom = open();
    await until(dom, 'typeof handleFile === "function"').catch(() => {});
    const note = dom.window.document.getElementById('load-note');
    check('there is somewhere to say what is happening', !!note);
    check('and it says nothing before a file is chosen', !!note && note.hidden);

    // handleFile only reads name, size and arrayBuffer.
    const fake = (name, bytes) => ({
      name, size: bytes,
      arrayBuffer: () => new Promise(() => {}),   // never settles: mid-read
    });

    dom.window.handleFile(fake('big.pdf', 40 * 1048576));
    check('a PDF read announces itself', !note.hidden && /big\.pdf/.test(note.textContent),
          JSON.stringify(note.textContent));
    check('and says why a PDF is slow',
          /page by page/i.test(note.textContent), note.textContent);
    check('and warns about the one download it needs',
          /pdf\.js/i.test(note.textContent));
    check('and states the size, so a huge file is recognisable as huge',
          /40\.0 MB/.test(note.textContent), note.textContent);

    dom.window.handleFile(fake('jane.txt', 1048576));
    check('a plain text read announces itself too',
          /jane\.txt/.test(note.textContent));
    check('without the PDF explanation',
          !/page by page/i.test(note.textContent));
    dom.window.close();

    // The stalled download. jsdom fetches no external scripts, so appending
    // one fires neither onload nor onerror — which is exactly the stall this
    // guards against. Shorten the deadline so the test can watch it fire.
    const quick = new JSDOM(html.replace('const PDFJS_TIMEOUT_MS=20000;',
                                         'const PDFJS_TIMEOUT_MS=40;'),
      { runScripts: 'dangerously', pretendToBeVisual: true });
    await until(quick, 'typeof loadPdfJs === "function"').catch(() => {});
    let settled = null;
    quick.window.eval(`
      window.__pdfResult = null;
      loadPdfJs().then(() => { window.__pdfResult = "resolved"; },
                       e => { window.__pdfResult = "rejected: " + e.message; });`);
    await until(quick, 'window.__pdfResult !== null', 4000)
      .catch(() => {});
    settled = quick.window.__pdfResult;
    check('a stalled pdf.js download gives up instead of waiting for ever',
          typeof settled === 'string' && settled.startsWith('rejected'),
          settled === null ? 'never settled: the page would hang' : String(settled));
    check('and the reason names the likely cause',
          /proxy|captive portal/i.test(settled || ''), String(settled));
    check('and says the rest of the tool still works offline',
          /offline/i.test(settled || ''));
    quick.window.close();
  }

  await run('the citation is where the methods section gets written', async dom => {
    // AntConc — the most cited tool in this field — puts its citation on the
    // page people download from. Ours lived only in docs/CITING.md, which a
    // reader has no reason to open. The moment someone has a log in hand is
    // the moment they are about to write a methods section.
    await load(dom, 'pg_marked.txt');
    dom.window.eval('runClean ? runClean() : null');
    dom.window.eval('drawCite()');
    const d = dom.window.document, cite = d.getElementById('cite');
    check('there is a citation block', !!cite && !!cite.textContent.trim());
    if (!cite) return;

    const version = dom.window.eval('CORPUSPREP_VERSION');
    check('it names the version actually running',
          cite.textContent.includes(version), 'version ' + version + ' missing');
    check('and says why the version matters',
          /not reproducible|behaviour changes/i.test(cite.textContent));
    check('it offers a reference and BibTeX',
          !!d.getElementById('cite-apa') && !!d.getElementById('cite-bib'));
    check('the BibTeX carries the same version',
          d.getElementById('cite-bib').textContent.includes(version));

    // The honest part. The page knows its version and the concept DOI; it does
    // not know whether a release was archived for this build, so it must not
    // print a version DOI it cannot verify — that is a citation that looks
    // right and resolves to different code than the reader ran.
    check('it prints the concept DOI',
          /10\.5281\/zenodo\.22083931/.test(cite.textContent));
    check('and does not pass it off as the version DOI',
          /concept DOI/i.test(cite.textContent) && /version DOI/i.test(cite.textContent),
          'the two must be distinguished, or the reader cites the wrong one');
    check('and sends the reader to the right one for a methods section',
          /methods section/i.test(cite.textContent));

    const copy = d.querySelector('#cite [data-copy]');
    check('copying is offered', !!copy && !!copy.onclick);
  });

  await run('the page reads as prose a person wrote', async dom => {
    // Reported: too many em dashes in the text on the site. Counted before
    // fixing: one in build/_app.js at the start of the week, twenty-six by the
    // end. Almost all of them were added while writing the newer panels, and
    // the tic is recognisable enough that a reader notices it before they
    // notice what the sentence says.
    //
    // Comments are exempt. This is about what a visitor reads.
    dom.window.eval('drawCapabilities(); drawRegister();');
    try { dom.window.eval('drawCite()'); } catch (e) { /* needs a document */ }

    const visible = node => {
      if (node.nodeType === 3) return node.nodeValue;
      if (node.nodeType !== 1) return '';
      if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE') return '';
      let out = '';
      for (const c of node.childNodes) out += visible(c) + ' ';
      return out;
    };
    const text = visible(dom.window.document.body);
    const dashes = (text.match(/—/g) || []).length;
    check('no em dashes in the text on screen', dashes === 0,
          dashes + ' found: ' +
          (text.match(/[^.!?]*—[^.!?]*/g) || []).slice(0, 3)
            .map(x => x.replace(/\s+/g, ' ').trim().slice(0, 70)).join(' | '));

    // And the author's own name is not standing in the box where a stranger
    // is meant to type theirs.
    const name = dom.window.document.getElementById('g-name');
    check('the name field does not suggest somebody else',
          !!name && !/adesokan/i.test(name.getAttribute('placeholder') || ''),
          name && name.getAttribute('placeholder'));

    check('the page has an icon for the browser tab',
          !!dom.window.document.querySelector('link[rel="icon"]'));
  });

  await run('the capability list is not stale', dom => {
    const d = dom.window.document;
    dom.window.eval('drawCapabilities()');
    const cap = t => [...d.querySelectorAll('#caps .cap')]
      .find(e => e.textContent.toLowerCase().includes(t));
    const planned = e => !!e && e.classList.contains('soon');

    // This list carried page furniture, de-hyphenation and reflow as PLANNED
    // for three releases after all three had shipped, and described
    // de-hyphenation as "wordlist-validated" — the approach that was tried,
    // measured and rejected. It went stale in the direction that flatters.
    //
    // Reported by a user, not by a test. So: a test. Each of these is proven
    // to work by the checks above and elsewhere in this file.
    for (const feature of ['hyphenated line breaks', 'hard-wrapped paragraphs',
                           'page numbers, headers', 'footnotes',
                           'digitisation apparatus', 'running heads',
                           'reads pdf', 'interface furniture']) {
      const e = cap(feature);
      check(`"${feature}" is not still marked planned`, !!e && !planned(e),
            e ? 'marked planned' : 'missing from the list entirely');
    }

    // `reads pdf` was in the list below, asserted as planned, from the day
    // PDF support shipped in v0.8.0 until 29 August. Nobody saw it, because
    // this file could not run: jsdom was vendored into `node_modules` with
    // 496 of its 657 files missing and `Document.js` truncated at 16 KB.
    //
    // A test that cannot run is worse than no test. It reads as coverage in
    // the summary and asserts nothing, and this one had gone stale in the
    // direction it exists to prevent — the list telling the truth and the
    // test insisting otherwise.

    // And the other direction, which is the one that misleads a researcher
    // into starting work the tool cannot finish.
    for (const feature of ['repairs ocr characters']) {
      const e = cap(feature);
      check(`"${feature}" is honestly marked planned`, planned(e),
            e ? 'claimed as available' : 'missing');
    }

    // A third direction, and the subtlest: available, but on evidence
    // narrower than a reader would assume. Interface furniture has met one
    // synthetic thread; the division-word list is a list. Both work. Neither
    // is validated, and the list must say so in its own words.
    const ui = cap('interface furniture');
    check('interface furniture is declared experimental',
          !!ui && /experimental/i.test(ui.textContent),
          ui ? 'no qualification in the description' : 'missing');
    check('interface furniture states the evidence it rests on',
          !!ui && /synthetic/i.test(ui.textContent));
    const fur = cap('page numbers, headers');
    check('page furniture states what its figure rests on',
          !!fur && /generated scan/i.test(fur.textContent),
          'no statement of the evidence behind the measurement');
    const cw = cap('catchwords');
    check('catchwords states what its figure rests on',
          !!cw && /generated fixture/i.test(cw.textContent));
    const seg = cap('segments chapters');
    check('chapter segmentation no longer lists English divisions alone',
          !!seg && /kapitel/i.test(seg.textContent),
          'still describes only Chapter/Book/Part/Act/Scene');
    check('and says the other-language list is a fixed list',
          !!seg && /fixed list/i.test(seg.textContent));
  });

  await run('hyphenated.txt: the review queue', async dom => {
    await load(dom, 'hyphenated.txt');
    const w = dom.window, d = w.document;
    check('breaks detected', w.eval('DOC.breaks.length') === 180,
          'got ' + w.eval('DOC.breaks.length'));
    check('a notice panel renders', d.querySelectorAll('.furn-notice').length >= 1);
    const heads = [...d.querySelectorAll('.furn-head .t')].map(e => e.textContent.trim());
    check('the hyphen panel is the one shown',
          heads.includes('Words broken across lines'), JSON.stringify(heads));
    // Nothing is reported until the button has been pressed. The panel
    // explains what the option does and offers the control; it does not say
    // how many breaks were found or how many were settled, because next to an
    // unpressed button a count reads as a result.
    check('no counts before cleaning',
          !d.querySelector('#rv-start'),
          'the review bar is showing before Clean was pressed');
    const before = [...d.querySelectorAll('.furn-head .s')]
      .map(e => e.textContent).join(' ');
    check('and the panel heading claims no outcome',
          !/\d+ found/.test(before), JSON.stringify(before.trim()));
    check('but the option is still offered', !!d.querySelector('#dh-on'));
    check('reflow toggle offered', !!d.querySelector('#rf-on'));
    // Both off until asked, like every other transformation here.
    check('reflow is off until asked',
          !d.querySelector('#rf-on').checked && !w.eval('!!CFG.reflow'));

    // After cleaning, the counts appear and the review bar with them.
    await w.eval('runClean()');
    await until(dom, 'CLEANED === true');
    const btn = d.querySelector('#rv-start');
    check('review offered once cleaning has run',
          !!btn && /Look at the \d+ kept hyphen/.test(btn.textContent.replace(/\s+/g, ' ')),
          btn ? btn.textContent.replace(/\s+/g, ' ').trim() : 'missing');
    // The unresolved cases keep the hyphen the source printed, so the reader
    // is told what happened rather than handed a task.
    const lead = [...d.querySelectorAll('.furn-lead')].map(e => e.textContent).join(' ');
    check('and says nothing is required',
          /Nothing is required of you/.test(lead.replace(/\s+/g, ' ')));
    // The point of the whole rule: the reader is asked about a handful, not
    // about most of the document.
    const asked = btn ? parseInt(btn.textContent.match(/\d+/)[0], 10) : 999;
    check('and asks about only a handful', asked <= 6, asked + ' questions');

    // The keyboard path, which is the whole point of the reviewer.
    w.eval('reviewOpen()');
    check('reviewer opens', d.querySelector('#rv-modal').style.display === 'flex');
    const qlen = w.eval('QUEUE.length');
    w.eval('reviewDecide("join")');
    check('a decision advances the queue', w.eval('QPOS') === 1);
    check('and is recorded', w.eval('CFG.decisions.size') === 1);
    check('queue length unchanged by deciding', w.eval('QUEUE.length') === qlen);
  });

  await run('pg1232_prince.txt: footnotes', async dom => {
    await load(dom, 'pg1232_prince.txt');
    const w = dom.window, d = w.document;
    check('28 footnotes found',
          w.eval('DOC.footnotes.filter(f=>f.paired).length') === 28,
          'got ' + w.eval('DOC.footnotes.filter(f=>f.paired).length'));
    const heads = [...d.querySelectorAll('.furn-head .t')].map(e => e.textContent.trim());
    check('the footnote panel renders', heads.includes('Footnotes'),
          JSON.stringify(heads));
    check('three routes offered',
          d.querySelectorAll('input[name="fn-route"]').length === 3);
    check('keep is the default',
          d.querySelector('input[name="fn-route"]:checked').value === 'retain');

    // The whole point, checked across every panel rather than one of them.
    // The first pass at this gated the hyphen panel and left the footnote and
    // furniture panels reporting their counts, which is the same fault twice.
    const shown = [...d.querySelectorAll('#segview')].map(e => e.textContent)
      .join(' ').replace(/\s+/g, ' ');
    check('no panel reports a finding before Clean is pressed',
          !/\d+ notes? matched/.test(shown) && !/to be removed/.test(shown),
          shown.slice(0, 140));

    await w.eval('runClean()');
    await until(dom, 'CLEANED === true');
    const after = [...d.querySelectorAll('#segview')].map(e => e.textContent)
      .join(' ').replace(/\s+/g, ' ');
    check('and reports them once it has', /28 notes matched to a marker/.test(after),
          after.slice(0, 140));
  });

  await run('romeo_juliet.txt: nothing claimed that is not there', async dom => {
    await load(dom, 'romeo_juliet.txt');
    const w = dom.window;
    check('no footnotes in drama', w.eval('DOC.footnotes.length') === 0,
          'got ' + w.eval('DOC.footnotes.length'));
    check('no page furniture', w.eval('DOC.furniture.size') === 0);
  });

  await run('cleaning runs, and says so while it runs', async dom => {
    await load(dom, 'hyphenated.txt');
    const w = dom.window, d = w.document;
    check('nothing cleaned before asking', w.eval('RESULT') === null);

    // runClean is async: it yields so the browser can paint the working state
    // before occupying the main thread. On a 45 MB scan the page stops
    // answering for several seconds, and without this it does so silently.
    const p = w.eval('runClean()');
    check('the button says it is working',
          d.querySelector('#run-clean').classList.contains('busy'));
    check('and cannot be pressed twice', d.querySelector('#run-clean').disabled);
    await p;

    check('the working state clears',
          !d.querySelector('#run-clean').classList.contains('busy')
          && !d.querySelector('#run-clean').disabled);
    check('cleaning produces text', w.eval('RESULT && RESULT.text.length > 1000'));
    check('and counts tokens', w.eval('RESULT.stats.tokens') > 1000);
    check('and the button reports it', /Cleaned/.test(
      d.querySelector('#run-label').textContent));
  });

  console.log('\n' + '='.repeat(62));
  console.log(`  ${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
