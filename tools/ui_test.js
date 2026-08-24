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

function open() {
  const dom = new JSDOM(fs.readFileSync(PAGE, 'utf8'),
    { runScripts: 'dangerously', pretendToBeVisual: true });
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
                           'digitisation apparatus', 'running heads']) {
      const e = cap(feature);
      check(`"${feature}" is not still marked planned`, !!e && !planned(e),
            e ? 'marked planned' : 'missing from the list entirely');
    }

    // And the other direction, which is the one that misleads a researcher
    // into starting work the tool cannot finish.
    for (const feature of ['reads pdf', 'repairs ocr characters']) {
      const e = cap(feature);
      check(`"${feature}" is honestly marked planned`, planned(e),
            e ? 'claimed as available' : 'missing');
    }
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
