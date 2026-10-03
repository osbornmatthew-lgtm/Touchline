// Touchline: pull EJA Under 16 data from FA Full-Time.
// Run in a browser tab on https://fulltime.thefa.com (same origin). Writes the data as JSON into a <pre>
// inside <main> and returns a one-line summary of counts.
const S = '817991894';
const P = h => new DOMParser().parseFromString(h, 'text/html');
const get = async u => P(await fetch(u).then(r => r.text()));
const txt = e => e ? e.innerText.replace(/\s+/g, ' ').trim() : '';
const clean = n => { let s = n.replace(/\s+U1[0-9]\b.*$/, '').replace(/\s*\((Youth|Ltd|Youth Development)\)/g, '').trim(); let p; do { p = s; s = s.replace(/\s+(Youth|Y|FC|F\.C\.?|Community|Academy)$/, '').trim(); } while (s !== p); return s; };
const tc = v => v.toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\bFc\b/g, 'FC').replace(/\bAnd\b/g, 'and').replace(/\bFdc\b/g, 'FDC').replace(/\bFa\b/g, 'FA').replace(/'S\b/g, "'s");
const venue = v => (!v || /\bU1[0-9]\b|#\d/.test(v)) ? null : tc(v);
const fid = el => { const a = el && el.querySelector('a[href*="displayFixture"]'); return a ? +(((a.getAttribute('href') || '').match(/id=(\d+)/) || [])[1]) || null : null; };
const DIVS = [['U16 Black','1_626466325',71055166],['U16 Blue','1_940550859',833400234],['U16 Brown','1_540512685',362745292],['U16 Green','1_467206401',610727353],['U16 Purple','1_706654984',786917750],['U16 Red','1_882985552',209907016],['U16 Yellow','1_132116272',66673950]];
const opts = [...(await get(`/fixtures.html?selectedSeason=${S}`)).querySelector('select[name=selectedFixtureGroupKey]').options].map(o => [o.value, o.text.trim()]);
const keyOf = re => (opts.find(o => re.test(o[1])) || [])[0];
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
const events = async (id, home, away) => {
  if (!id) return [];
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
for (const [name, key, div] of DIVS) {
  const td = await get(`/table.html?selectedSeason=${S}&selectedDivision=${div}`);
  const tables = td.querySelectorAll('table');
  const teams = [...tables[tables.length - 1].querySelectorAll('tbody tr')].map(r => { const v = [...r.children].map(c => c.innerText.trim()).filter(x => x !== ''); const n = v.length; return [clean(v[1]), +v[2], +v[n-7], +v[n-6], +v[n-5], +v[n-4], +v[n-3], +v[n-1]]; });
  const R = await results(key, 1);
  for (const x of R) x.row.push(x.id, x.row[3] === null ? [] : await events(x.id, x.row[1], x.row[2]));
  out.divisions.push({ name, teams, results: R.map(x => x.row), fixtures: (await fixtures(key, 1)).map(x => x.row) });
  (await results(key, 3)).filter(x => x.type.startsWith('CC')).forEach(x => ccR.set(x.row[0] + x.raw.join(), [...x.row, x.type.slice(3)]));
  (await fixtures(key, 3)).filter(x => x.type.startsWith('CC')).forEach(x => ccF.set(x.row[0] + x.raw.join(), [...x.row, x.type.slice(3)]));
}
const u16 = n => /\bU16\b/.test(n);
for (const [label, re] of [['League Cup', /League Cup U16/], ['RT Litho Cup', /RT litho/i]]) {
  const k = keyOf(re); if (!k) continue;
  out.cups.push({ name: label, results: (await results(k, 1)).filter(x => x.raw.some(u16)).map(x => x.row), fixtures: (await fixtures(k, 1)).filter(x => x.raw.some(u16)).map(x => x.row) });
}
const shortName = s => s.replace(/\s+(sponsored|supported) by .*$/i, '');
out.cups.push({ name: 'County Cups', county: true, results: [...ccR.values()].map(r => { r[6] = shortName(r[6]); return r; }), fixtures: [...ccF.values()].map(f => { f[7] = shortName(f[7]); return f; }) });
const pre = document.createElement('pre'); pre.textContent = JSON.stringify(out);
document.body.innerHTML = ''; const mm = document.createElement('main'); mm.appendChild(pre); document.body.appendChild(mm);
const timed = out.divisions.reduce((n, d) => n + d.results.reduce((k, r) => k + (r[7] || []).length, 0), 0);
out.divisions.map(d => d.name + ':' + d.teams.length + 't/' + d.results.length + 'r/' + d.fixtures.length + 'f').concat(out.cups.map(c => c.name + ':' + c.results.length + 'r/' + c.fixtures.length + 'f'), ['timed goals:' + timed]).join('; ')
