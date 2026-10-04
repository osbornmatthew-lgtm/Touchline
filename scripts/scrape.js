// Touchline: pull league data from FA Full-Time. EJA Under 16 by default; set window.__tlcfg first for another league
// ({ S: season id, DIVS: [[name, fixture group key, division id]], CUPS: [[label, regex source, flags]], AGE: 'U13' }).
// Run in a browser tab on https://fulltime.thefa.com (same origin). Writes the data as JSON into a <pre>
// inside <main> and returns a one-line summary of counts. The home runner (runner/touchline.py) runs this same file
// in a headless browser, adding the options below so a match-day check only fetches what can have changed.
//
// Optional settings (all can be left out; a plain run fetches everything, one request at a time as before):
//   ONLY_DIVS: ['U16 Red']        only these divisions (null = all)
//   ONLY_CUPS: ['League Cup']     only these cups ([] = none, null = all)
//   EVENTS: { fixtureId: { s: '3-1', e: [[min, 'H', 'G']] } }   goal times already known; reused while the score matches
//   KNOWN_VENUES: ['Name', ...]   venues already looked up; not fetched again
//   LIMIT: 2                      requests in flight at once (default 1)
//   DELAY: [500, 1200]            pause range in ms after each request, per slot (default none)
//   RETRIES: 2                    retries on 429, 5xx or a network error; one slow retry on 403, then give up
//   DEADLINE_MS: 600000           give up after this long
//   NO_DOM: true                  leave the page alone (the runner reads window.__tlout instead)
const CFG = (typeof window !== 'undefined' && window.__tlcfg) || {};
const S = CFG.S || '817991894';
const P = h => new DOMParser().parseFromString(h, 'text/html');
const T0 = Date.now(), LIMIT = CFG.LIMIT || 1, DELAY = CFG.DELAY || [0, 0], RETRIES = CFG.RETRIES ?? 2, DEADLINE = CFG.DEADLINE_MS || 600000;
const stats = { requests: 0, retries: 0, matchPages: 0, eventsReused: 0, venuePages: 0 };
let free = LIMIT, pauseUntil = 0, fatal = null; const waiting = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const acquire = () => free > 0 ? (free--, Promise.resolve()) : new Promise(r => waiting.push(r));
const release = () => setTimeout(() => { const w = waiting.shift(); if (w) w(); else free++; }, DELAY[0] + Math.random() * (DELAY[1] - DELAY[0]));
// Polite fetch: a few requests at a time, a pause after each, and back off (everyone waits) on 403 or 429.
const fetchText = async u => {
  for (let attempt = 0; ; attempt++) {
    if (fatal) throw fatal;
    if (Date.now() - T0 > DEADLINE) throw (fatal = new Error('gave up after ' + Math.round(DEADLINE / 1000) + 's'));
    await acquire();
    let status, wait = 0;
    try {
      if (pauseUntil > Date.now()) await sleep(pauseUntil - Date.now());
      const ac = new AbortController(), t = setTimeout(() => ac.abort(), 30000);
      try {
        const r = await fetch(u, { signal: ac.signal, credentials: 'same-origin' });
        stats.requests++;
        if (r.ok) return await r.text();
        status = r.status; wait = (+r.headers.get('Retry-After') || 0) * 1000;
      } finally { clearTimeout(t); }
    } catch (e) { status = status || 'network error'; } finally { release(); }
    const blocked = status === 403, retryable = blocked || status === 429 || status === 'network error' || status >= 500;
    if (!retryable || attempt >= (blocked ? 1 : RETRIES)) {
      const err = new Error(`HTTP ${status} on ${u.split('?')[0]}`);
      if (retryable) fatal = err;  // still blocked or throttled after backing off: stop the whole run, don't keep knocking
      throw err;
    }
    stats.retries++;
    pauseUntil = Math.max(pauseUntil, Date.now() + Math.max(wait, blocked ? 60000 : status === 429 ? 20000 : 5000) * (attempt + 1));
  }
};
const get = async u => P(await fetchText(u));
const txt = e => e ? e.innerText.replace(/\s+/g, ' ').trim() : '';
// EJA names end with the age group ("Aveley U16"); other leagues name the side after it ("Blackmore Youth U13 Blue"), so keep that.
const KEEP_SIDE = CFG.KEEP_SIDE ?? !!CFG.DIVS;
const clean = n => { let s = KEEP_SIDE ? n.replace(/\s+(?:Youth\s+|Y\s+)?U1[0-9]\b/, '') : n.replace(/\s+U1[0-9]\b.*$/, '').replace(/\s*\((Youth|Ltd|Youth Development)\)/g, '').trim(); let p; do { p = s; s = s.replace(/\s+(Youth|Y|FC|F\.C\.?|Community|Academy)$/, '').trim(); } while (s !== p); return s; };
const tc = v => v.toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\bFc\b/g, 'FC').replace(/\bAnd\b/g, 'and').replace(/\bFdc\b/g, 'FDC').replace(/\bFa\b/g, 'FA').replace(/'S\b/g, "'s").replace(/\.Com\b/g, '.com').replace(/\bTechsoc\b/g, 'TechSoc');
const venue = v => (!v || /\bU1[0-9]\b|#\d/.test(v)) ? null : tc(v);
const fid = el => { const a = el && (el.querySelector('a[href*="displayFixture"]') || el.querySelector('a[href*="id="]')); return a ? +(((a.getAttribute('href') || '').match(/id=(\d+)/) || [])[1]) || null : null; };
const DIVS = CFG.DIVS || [['U16 Black','1_626466325',71055166],['U16 Blue','1_940550859',833400234],['U16 Brown','1_540512685',362745292],['U16 Green','1_467206401',610727353],['U16 Purple','1_706654984',786917750],['U16 Red','1_882985552',209907016],['U16 Yellow','1_132116272',66673950]];
const CUPS = CFG.CUPS ? CFG.CUPS.map(([l, s, fl]) => [l, new RegExp(s, fl || '')]) : [['League Cup', /League Cup U16/], ['RT Litho Cup', /RT litho/i]];
const results = async (key, opt) => [...(await get(`/results.html?selectedSeason=${S}&selectedFixtureGroupKey=${key}&selectedRelatedFixtureOption=${opt}&itemsPerPage=100`)).querySelectorAll('.tbody > div')].map(r => {
  const m = txt(r.querySelector('.score-col')).match(/^(\d+)\s*-\s*(\d+)/);
  const h = txt(r.querySelector('.home-team-col .team-name')), a = txt(r.querySelector('.road-team-col .team-name'));
  return { type: txt(r.querySelector('.type-col')), raw: [h, a], id: fid(r), row: [txt(r.querySelector('.datetime-col')).slice(0, 5), clean(h), clean(a), m ? +m[1] : null, m ? +m[2] : null, txt(r.querySelector('.additional-scores-col')).replace(/^\(|\)$/g, '')] };
}).filter(x => x.raw[0] || x.raw[1]);
const fixtures = async (key, opt) => [...(await get(`/fixtures.html?selectedSeason=${S}&selectedFixtureGroupKey=${key}&selectedRelatedFixtureOption=${opt}&itemsPerPage=100`)).querySelectorAll('table tbody tr')].map(r => {
  const c = [...r.children]; if (c.length < 9) return null;
  const dt = txt(c[1]); const ko = dt.slice(9, 14);
  return { type: txt(c[0]), raw: [txt(c[2]), txt(c[6])], row: [dt.slice(0, 5), (!ko || ko === '00:00') ? null : ko, clean(txt(c[2])), clean(txt(c[6])), venue(txt(c[7])), fid(r), txt(c[9])] };
}).filter(Boolean);
// Goal times: [minute, 'H' or 'A', 'G' goal | 'P' penalty | 'O' own goal]
const KNOWN_EVENTS = CFG.EVENTS || {};
const events = async (id, home, away, hs, as) => {
  if (!id) return [];
  const known = KNOWN_EVENTS[id];
  if (known && known.s === hs + '-' + as) { stats.eventsReused++; return known.e; }
  stats.matchPages++;
  const d = await get('/displayFixture.html?id=' + id);
  const t = [...d.querySelectorAll('table')].find(x => /\bTime\b/.test(x.innerText) && /\bStat\b/.test(x.innerText));
  if (!t) return [];
  return [...t.querySelectorAll('tbody tr')].map(tr => [...tr.children].map(c => c.innerText.trim())).map(([mn, team, stat]) => {
    const side = clean(team || '') === home ? 'H' : clean(team || '') === away ? 'A' : null;
    const kind = /own/i.test(stat) ? 'O' : /pen/i.test(stat) ? 'P' : /goal/i.test(stat) ? 'G' : null;
    const min = parseInt(mn, 10);
    return (side && kind && !isNaN(min)) ? [min, side, kind] : null;
  }).filter(Boolean);
};
const out = { divisions: [], cups: [] };
const ccR = new Map(), ccF = new Map();
// Divisions run side by side (the request limit above still applies); results are added in the original order.
const doDivs = DIVS.filter(([name]) => !CFG.ONLY_DIVS || CFG.ONLY_DIVS.includes(name));
const perDiv = await Promise.all(doDivs.map(async ([name, key, div]) => {
  const [td, R, F, R3, F3] = await Promise.all([get(`/table.html?selectedSeason=${S}&selectedDivision=${div}`), results(key, 1), fixtures(key, 1), results(key, 3), fixtures(key, 3)]);
  const tables = td.querySelectorAll('table');
  const teams = [...tables[tables.length - 1].querySelectorAll('tbody tr')].map(r => { const v = [...r.children].map(c => c.innerText.trim()).filter(x => x !== ''); const n = v.length; return [clean(v[1]), +v[2], +v[n-7], +v[n-6], +v[n-5], +v[n-4], +v[n-3], +v[n-1]]; });
  const ev = await Promise.all(R.map(x => x.row[3] === null ? [] : events(x.id, x.row[1], x.row[2], x.row[3], x.row[4])));
  R.forEach((x, i) => x.row.push(x.id, ev[i]));
  return { div: { name, teams, results: R.map(x => x.row), fixtures: F.map(x => x.row) }, R3, F3 };
}));
for (const { div, R3, F3 } of perDiv) {
  out.divisions.push(div);
  R3.filter(x => x.type.startsWith('CC')).forEach(x => ccR.set(x.row[0] + x.raw.join(), [...x.row, x.type.slice(3)]));
  F3.filter(x => x.type.startsWith('CC')).forEach(x => ccF.set(x.row[0] + x.raw.join(), [...x.row, x.type.slice(3)]));
}
const AGE = new RegExp('\\b' + (CFG.AGE || 'U16') + '\\b'); const u16 = n => AGE.test(n);
const doCups = CUPS.filter(([label]) => !CFG.ONLY_CUPS || CFG.ONLY_CUPS.includes(label));
if (doCups.length) {
  const opts = [...(await get(`/fixtures.html?selectedSeason=${S}`)).querySelector('select[name=selectedFixtureGroupKey]').options].map(o => [o.value, o.text.trim()]);
  const keyOf = re => (opts.find(o => re.test(o[1])) || [])[0];
  const got = await Promise.all(doCups.map(async ([label, re]) => {
    const k = keyOf(re); if (!k) return null;
    const [R, F] = await Promise.all([results(k, 1), fixtures(k, 1)]);
    return { name: label, results: R.filter(x => x.raw.some(u16)).map(x => x.row), fixtures: F.filter(x => x.raw.some(u16)).map(x => x.row) };
  }));
  got.filter(Boolean).forEach(c => out.cups.push(c));
}
const shortName = s => s.replace(/\s+(sponsored|supported) by .*$/i, '');
out.cups.push({ name: 'County Cups', county: true, results: [...ccR.values()].map(r => { r[6] = shortName(r[6]); return r; }), fixtures: [...ccF.values()].map(f => { f[7] = shortName(f[7]); return f; }) });
// Venue address, map pin and parking: one lookup per venue name (corrections in the page still win)
const pc = t => tc(t).replace(/\b([a-z]{1,2}\d[a-z\d]?)\s*(\d[a-z]{2})\b/i, (m, x, y) => x.toUpperCase() + ' ' + y.toUpperCase());
const vids = new Map(), known = new Set(CFG.KNOWN_VENUES || []);
out.divisions.flatMap(d => d.fixtures).concat(out.cups.flatMap(c => c.fixtures)).forEach(f => { if (f[4] && f[5] && !vids.has(f[4]) && !known.has(f[4])) vids.set(f[4], f[5]); });
out.venues = {}; const misses = [];
await Promise.all([...vids].map(async ([name, id]) => {
  try {
    stats.venuePages++;
    const d = await get('/displayFixture.html?id=' + id);
    const addr = txt(d.querySelector('address'));
    const ll = ((d.querySelector('a[href*="maps.google"]') || { getAttribute: () => '' }).getAttribute('href') || '').match(/ll=(-?[\d.]+),(-?[\d.]+)/);
    const park = [...d.querySelectorAll('p')].map(txt).find(t => /^Car park:/i.test(t));
    const v = {};
    if (addr) v.a = pc(addr);
    if (ll && +ll[1] && +ll[2]) v.ll = (+ll[1]).toFixed(5) + ',' + (+ll[2]).toFixed(5);
    if (park) v.p = park.replace(/^Car park:\s*/i, '');
    if (Object.keys(v).length) out.venues[name] = v; else misses.push(name);
  } catch (e) { if (fatal) throw e; }
}));
// Keep venue order the same as a one-at-a-time run (first fixture that mentions each venue).
out.venues = Object.fromEntries([...vids.keys()].filter(n => out.venues[n]).map(n => [n, out.venues[n]]));
if (typeof window !== 'undefined') window.__tlout = { data: out, meta: { ...stats, venueMisses: misses, ms: Date.now() - T0 } };
if (!CFG.NO_DOM) { const pre = document.createElement('pre'); pre.textContent = JSON.stringify(out);
document.body.innerHTML = ''; const mm = document.createElement('main'); mm.appendChild(pre); document.body.appendChild(mm); }
const timed = out.divisions.reduce((n, d) => n + d.results.reduce((k, r) => k + (r[7] || []).length, 0), 0);
out.divisions.map(d => d.name + ':' + d.teams.length + 't/' + d.results.length + 'r/' + d.fixtures.length + 'f').concat(out.cups.map(c => c.name + ':' + c.results.length + 'r/' + c.fixtures.length + 'f'), ['timed goals:' + timed, 'venues:' + Object.keys(out.venues).length, 'requests:' + stats.requests]).join('; ')
