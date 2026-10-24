// Touchline: one-off fetch of past EJA seasons (final tables and results, all age groups) from FA Full-Time.
// Run in a browser tab on https://fulltime.thefa.com. Set window.__thcfg = { SEASONS: [[id, '2025-26'], ...] } first.
// Past seasons never change, so this runs once per season; the result is saved as data/history/<season>.json.
// Result: window.__thout = { '2025-26': { divisions: [{ name, teams: [[team, P, W, D, L, GF, GA, Pts]] }],
//   results: [[dd/mm, home, away, hs, as, note, competition, age]] }, ... }
const HC = window.__thcfg || {};
const SEASONS = HC.SEASONS || [['239620789', '2025-26'], ['392615098', '2024-25'], ['456453103', '2023-24']];
const P = h => new DOMParser().parseFromString(h, 'text/html');
const sleep = ms => new Promise(r => setTimeout(r, ms));
let requests = 0;
const get = async u => {
  for (let i = 0; ; i++) {
    const r = await fetch(u, { credentials: 'same-origin' }); requests++;
    if (r.ok) { await sleep(500 + Math.random() * 700); return P(await r.text()); }
    if (i >= 2 || r.status === 404) throw new Error(`HTTP ${r.status} on ${u}`);
    await sleep(r.status === 403 ? 60000 : 10000);
  }
};
const txt = e => e ? e.innerText.replace(/\s+/g, ' ').trim() : '';
// Same name rules as scrape.js
const clean0 = n => { let s = n.replace(/\s+U1[0-9]\b.*$/, '').replace(/\s*\((Youth|Ltd|Youth Development)\)/g, '').trim(); let p; do { p = s; s = s.replace(/\s+(Youth|Y|FC|F\.C\.?|Community|Academy)$/, '').trim(); } while (s !== p); return s; };
const cleanU18 = n => {
  const m = n.match(/^(.*?)\s+(?:Youth\s+|Y\s+)?(U1[78])\b(.*)$/i); if (!m) return clean0(n);
  const club = clean0(m[1].replace(/\s*\((Youth|Ltd|Youth Development)\)/g, ''));
  let side = m[3].replace(/\bEJA\b/gi, '').replace(/\bU18\b/gi, '').replace(/[()]/g, ' ').replace(/\s+/g, ' ').trim();
  if (m[2].toUpperCase() === 'U17' && !/U17/i.test(side)) side = ('U17 ' + side).trim();
  side = side.replace(/\b([a-z])/g, c => c.toUpperCase());
  return side ? club + ' ' + side : club;
};
const ageOf = s => { const m = String(s).match(/\bU1([3-8])\b/i); return m ? 'U1' + (m[1] === '7' ? '8' : m[1]) : null; };
const cleanFor = (n, age) => age === 'U18' ? cleanU18(n) : clean0(n);
const out = {};
for (const [S, label] of SEASONS) {
  const tb = await get(`/table.html?selectedSeason=${S}`);
  const divs = [...tb.querySelector('select[name=selectedDivision]').options].map(o => [o.value, o.text.trim()]).filter(d => /^U1[3-8] /.test(d[1]));
  const divisions = [];
  for (const [id, name] of divs) {
    const td = await get(`/table.html?selectedSeason=${S}&selectedDivision=${id}`);
    const tables = td.querySelectorAll('table'); if (!tables.length) continue;
    const age = ageOf(name);
    const teams = [...tables[tables.length - 1].querySelectorAll('tbody tr')].map(r => { const v = [...r.children].map(c => c.innerText.trim()).filter(x => x !== ''); const n = v.length; return [cleanFor(v[1], age), +v[2], +v[n-7], +v[n-6], +v[n-5], +v[n-4], +v[n-3], +v[n-1]]; }).filter(t => t[0]);
    divisions.push({ name, teams });
  }
  const rs = await get(`/results.html?selectedSeason=${S}`);
  const groups = [...rs.querySelector('select[name=selectedFixtureGroupKey]').options].map(o => [o.value, o.text.trim()]).filter(g => g[0]);
  const results = [], full = [];
  for (const [key, gname] of groups) {
    const d = await get(`/results.html?selectedSeason=${S}&selectedFixtureGroupKey=${key}&selectedRelatedFixtureOption=1&itemsPerPage=100`);
    const rows = [...d.querySelectorAll('.tbody > div')];
    if (rows.length >= 100) full.push(gname);
    rows.forEach(r => {
      const m = txt(r.querySelector('.score-col')).match(/^(\d+)\s*-\s*(\d+)/); if (!m) return;
      const h = txt(r.querySelector('.home-team-col .team-name')), a = txt(r.querySelector('.road-team-col .team-name'));
      const age = ageOf(gname) || ageOf(h) || ageOf(a); if (!age) return;
      results.push([txt(r.querySelector('.datetime-col')).slice(0, 5), cleanFor(h, age), cleanFor(a, age), +m[1], +m[2], txt(r.querySelector('.additional-scores-col')).replace(/^\(|\)$/g, ''), gname.replace(/`/g, "'"), age]);
    });
  }
  // the same game can appear under two groups: keep one
  const seen = new Set();
  out[label] = { divisions, results: results.filter(r => { const k = r.slice(0, 5).join('|'); if (seen.has(k)) return false; seen.add(k); return true; }), full };
}
window.__thout = out;
Object.entries(out).map(([k, v]) => `${k}: ${v.divisions.length} divisions, ${v.results.length} results${v.full.length ? ', 100+ in ' + v.full.join(' / ') : ''}`).join('; ') + `; requests ${requests}`
