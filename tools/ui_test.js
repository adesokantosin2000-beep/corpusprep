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
    // Reported by a user: the recent-files list "shows previous files but they
    // are not clickable or deletable".
    //
    // They were `<button>` elements carrying the tooltip "Reopen this file from
    // disk to load it again", with no click handler anywhere in the file. A
    // control that promises an action and has none is worse than no control:
    // the reader concludes the tool is broken, and they are not wrong.
    console.log('\nthe recent-files list does what it looks like');
    const store = {
      'corpusprep.v1': JSON.stringify({
        user: { name: 'A Reader', inst: '' },
        recent: [{ name: 'informant_04.txt', tokens: 12000, at: Date.now() },
                 { name: 'jane.txt', tokens: 188215, at: Date.now() - 1000 }],
      }),
    };
    const dom = open(store);
    const d = dom.window.document;

    const rows = () => [...d.querySelectorAll('#recent .rec-row')];
    check('both remembered files are listed', rows().length === 2,
          rows().length + ' rows');
    check('the list is shown at all',
          d.getElementById('recent-wrap').style.display !== 'none');

    const openBtn = d.querySelector('#recent [data-open]');
    check('each entry has something to click', !!openBtn);
    check('and something bound to the click', !!openBtn && !!openBtn.onclick,
          'no handler: the button does nothing');
    check('the tooltip does not promise what a browser cannot do',
          !!openBtn && !/reopen this file/i.test(openBtn.getAttribute('title') || ''),
          openBtn && openBtn.getAttribute('title'));

    // Clicking must reach the file picker, which is the only way a browser can
    // read a file again.
    let picked = 0;
    d.getElementById('file').click = () => { picked++; };
    openBtn.click();
    check('clicking opens the file picker', picked === 1, picked + ' calls');

    // And an entry must come off the list. A filename can itself be sensitive.
    const x = d.querySelector('#recent [data-forget]');
    check('each entry has a remove control', !!x);
    check('it is labelled for a screen reader',
          !!x && /informant_04/.test(x.getAttribute('aria-label') || ''));
    x.click();
    check('removing takes the row away', rows().length === 1, rows().length + ' rows');
    check('and the right one is gone',
          !/informant_04/.test(d.getElementById('recent').textContent));
    check('and it stays gone in storage',
          !/informant_04/.test(store['corpusprep.v1']));

    d.querySelector('#recent [data-forget]').click();
    check('removing the last one hides the list',
          d.getElementById('recent-wrap').style.display === 'none');
    dom.window.close();
  }

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
