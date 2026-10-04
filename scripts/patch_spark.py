"""Matchday preview card, weekend round-up with streaks and milestones, and 'what a win would do'."""
import sys
f = sys.argv[1]; t = open(f).read()
def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (f, a[:70], t.count(a)); t = t.replace(a, b)

# --- CSS
rep('/* opponent preview */', '''/* what's at stake, round-up */
.stake{border-top:1px solid var(--line);padding:12px 18px;display:flex;flex-direction:column;gap:4px;font-size:14px;color:var(--fg-2)}
.stake b{color:var(--fg)}
.stake .eyebrow{margin-bottom:2px}
.next .sub .sharebtn{margin-left:auto}
.ru-note{font-size:13px;color:var(--muted)}
/* opponent preview */''')

# --- Round-up section after Latest results
rep('''    <section aria-labelledby="stats-h">''', '''    <section aria-labelledby="ru-h" id="ru-sec" hidden>
      <div class="sec-head"><h2 id="ru-h">Weekend round-up</h2><span class="note" id="ru-date"></span><button type="button" class="sharebtn" data-share="roundup">Share</button></div>
      <div class="stats" id="ru"></div>
    </section>

    <section aria-labelledby="stats-h">''')

# --- Logic, before renderView
rep('function renderView() {', r'''// Next game for my team (league or cup), soonest first
function nextMine() {
  if (!mine) return null;
  const all = [];
  DATA.divisions.forEach(d => d.fixtures.forEach(f => all.push({ f, comp: d.name, div: d })));
  DATA.cups.forEach(c => c.fixtures.forEach(f => all.push({ f, comp: f[7] || c.name, div: null })));
  return all.filter(({ f }) => !f[6] && toDate(f[0]) >= today && (f[2] === mine || f[3] === mine))
    .sort((a, b) => toDate(a.f[0]) - toDate(b.f[0]) || (a.f[1] || '99').localeCompare(b.f[1] || '99'))[0] || null;
}
// Where a team sits now: position, points, last five results
function standing(name) {
  const i = teamDiv[name]; if (i === undefined) return null;
  const d = DATA.divisions[i], k = d.teams.findIndex(x => x[0] === name), tm = d.teams[k];
  return { pos: k + 1, pts: tm[7], p: tm[1], gd: tm[5] - tm[6], form: (formMap(d)[name] || []).slice(-5), div: d };
}
// What a win or draw in the next league game would do to my position (others' points unchanged)
function stakeHtml(nx) {
  if (!nx || !nx.div || teamDiv[mine] === undefined || DATA.divisions[teamDiv[mine]] !== nx.div) return '';
  const d = nx.div, me = standing(mine); if (!me || !me.p && !d.teams.some(x => x[1])) return '';
  const opp = nx.f[2] === mine ? nx.f[3] : nx.f[2], op = standing(opp);
  const posWith = (add, gdAdd, oppAdd) => 1 + d.teams.filter(x => x[0] !== mine && ((x[7] + (x[0] === opp ? oppAdd : 0)) > me.pts + add ||
    (x[7] + (x[0] === opp ? oppAdd : 0)) === me.pts + add && (x[5] - x[6]) > me.gd + gdAdd)).length;
  const w = posWith(3, 1, 0), dr = posWith(1, 0, 1);
  const lines = [];
  const move = (p, word) => p < me.pos ? `${word}: up to <b>${ordinal(p)}</b>` : p === me.pos ? `${word}: stay <b>${ordinal(p)}</b>` : `${word}: <b>${ordinal(p)}</b>`;
  lines.push(`${move(w, 'Win')} · ${move(dr, 'Draw')}`);
  if (op && op.pos < me.pos && op.pts - me.pts < 3) lines.push(`A win takes you above ${esc(opp)}.`);
  else if (op && op.pos < me.pos && op.pts - me.pts === 3) lines.push(`A win pulls you level on points with ${esc(opp)}.`);
  else if (op && op.pos > me.pos && me.pts - op.pts < 3) lines.push(`Lose and ${esc(opp)} could go above you.`);
  return `<div class="stake"><div class="eyebrow">What's at stake</div><div>${lines.join('</div><div>')}</div><div class="ru-note">Now ${ordinal(me.pos)} on ${me.pts} pts. "Up to" assumes the teams around you don't win.</div></div>`;
}

// Weekend round-up for a division: the latest round with scores
function roundup(i) {
  const d = DATA.divisions[i];
  const scored = d.results.filter(r => r[3] !== null && r[3] !== undefined);
  if (!scored.length) return null;
  const date = scored.map(r => r[0]).sort((a, b) => toDate(b) - toDate(a))[0];
  const games = scored.filter(r => r[0] === date);
  const items = [];
  const line = r => `${r[1]} ${r[3]}–${r[4]} ${r[2]}`;
  const winner = r => r[3] > r[4] ? r[1] : r[3] < r[4] ? r[2] : null;
  const big = games.filter(r => r[3] !== r[4]).sort((a, b) => Math.abs(b[3] - b[4]) - Math.abs(a[3] - a[4]) || (b[3] + b[4]) - (a[3] + a[4]))[0];
  if (big) items.push({ k: 'Biggest win', team: winner(big), v: `${Math.max(big[3], big[4])}–${Math.min(big[3], big[4])}`, sub: line(big) });
  // Upset: winner was well below the loser in the table before this round
  const before = {};
  d.teams.forEach((x, k) => before[x[0]] = { pts: x[7], base: k });
  games.forEach(r => { const w = winner(r); if (w) before[w].pts -= 3; else { before[r[1]] && (before[r[1]].pts -= 1); before[r[2]] && (before[r[2]].pts -= 1); } });
  const order = Object.keys(before).sort((a, b) => before[b].pts - before[a].pts || before[a].base - before[b].base);
  const pos = n => order.indexOf(n) + 1;
  const ups = games.filter(r => winner(r)).map(r => { const w = winner(r), l = w === r[1] ? r[2] : r[1]; return { r, w, l, gap: pos(w) - pos(l) }; })
    .filter(x => x.gap >= 3 && before[x.w] && before[x.l]).sort((a, b) => b.gap - a.gap)[0];
  if (ups) items.push({ k: 'Upset of the round', team: ups.w, v: `${ordinal(pos(ups.w))} beat ${ordinal(pos(ups.l))}`, sub: line(ups.r) });
  // Comeback: behind at half-time, won (or rescued a draw)
  const cb = games.map(r => { const h = htOf(r[5]); if (!h) return null; const w = winner(r);
    if (w === r[1] && h[0] < h[1]) return { r, team: r[1], h, kind: 'won' };
    if (w === r[2] && h[1] < h[0]) return { r, team: r[2], h, kind: 'won' };
    if (!w && h[0] !== h[1]) return { r, team: h[0] < h[1] ? r[1] : r[2], h, kind: 'drew' };
    return null; }).filter(Boolean).sort((a, b) => (a.kind === 'won' ? 0 : 1) - (b.kind === 'won' ? 0 : 1))[0];
  if (cb) items.push({ k: 'Comeback of the round', team: cb.team, v: `HT ${cb.h[0]}–${cb.h[1]}`, sub: `${cb.kind === 'won' ? 'Behind at half-time, won' : 'Behind at half-time, rescued a draw'} · ${line(cb.r)}` });
  const fest = games.slice().sort((a, b) => (b[3] + b[4]) - (a[3] + a[4]))[0];
  if (fest && (!big || fest !== big) && fest[3] + fest[4] >= 5) items.push({ k: 'Goal fest', team: `${fest[1]} v ${fest[2]}`, v: String(fest[3] + fest[4]), sub: `Finished ${fest[3]}–${fest[4]}`, link: fest[1] });
  // Streaks and milestones, good news only
  const fm = formMap(d), seen = new Set(items.map(x => x.team));
  const streaks = [];
  d.teams.forEach(([n]) => {
    const f = fm[n] || []; if (!f.length) return;
    let w = 0; for (let k = f.length - 1; k >= 0 && f[k] === 'W'; k--) w++;
    let u = 0; for (let k = f.length - 1; k >= 0 && f[k] !== 'L'; k--) u++;
    if (w === f.length && w >= 3) streaks.push({ k: 'Perfect start', team: n, v: `${w} from ${w}`, sub: `won every league game so far`, s: 100 + w });
    else if (w >= 3) streaks.push({ k: 'On a run', team: n, v: `W${w}`, sub: `${w} league wins in a row`, s: 50 + w });
    else if (u >= 3) streaks.push({ k: 'Unbeaten run', team: n, v: `${u} games`, sub: `unbeaten in the league`, s: 20 + u });
  });
  const firsts = [];
  games.forEach(r => [[r[1], r[3], r[4]], [r[2], r[4], r[3]]].forEach(([n, gf, ga]) => {
    const f = fm[n] || []; if (f.length < 2) return;
    const prior = d.results.filter(x => x[3] !== null && x[0] !== date && toDate(x[0]) < toDate(date) && (x[1] === n || x[2] === n));
    if (gf > ga && !prior.some(x => (x[1] === n ? x[3] > x[4] : x[4] > x[3]))) firsts.push({ k: 'First win', team: n, v: '1st', sub: `first league win of the season, ${line(r)}`, s: 15 });
    else if (ga === 0 && !prior.some(x => (x[1] === n ? x[4] : x[3]) === 0)) firsts.push({ k: 'First clean sheet', team: n, v: '0', sub: `kept their first clean sheet, ${line(r)}`, s: 10 });
  }));
  streaks.concat(firsts).sort((a, b) => b.s - a.s).filter(x => !seen.has(x.k + x.team) && (seen.add(x.k + x.team), true)).slice(0, 3).forEach(x => items.push(x));
  return { date, games: games.length, goals: games.reduce((s, r) => s + r[3] + r[4], 0), items };
}
function renderRoundup() {
  const sec = document.getElementById('ru-sec');
  const ru = typeof view === 'number' ? roundup(view) : null;
  sec.hidden = !ru || !ru.items.length;
  if (sec.hidden) return;
  document.getElementById('ru-date').textContent = `${dayLabel(ru.date)} · ${ru.goals} goals in ${ru.games} game${ru.games > 1 ? 's' : ''}`;
  document.getElementById('ru').innerHTML = ru.items.map(({ k, team, v, sub, link }) => {
    const target = link || team, clickable = target in teamDiv;
    const inner = `<div class="eyebrow">${esc(k)}</div><div class="v"><span class="club">${esc(team)}</span><span class="num">${esc(v)}</span></div><div class="sub">${esc(sub)}</div>`;
    return clickable ? `<button type="button" class="panel stat tp" data-team="${esc(target)}">${inner}</button>` : `<div class="panel stat">${inner}</div>`;
  }).join('');
}

function renderView() {''')
rep('''  renderTalkingPoints();
  renderFixtures(comp.fixtures, county);''', '''  renderTalkingPoints();
  renderRoundup();
  renderFixtures(comp.fixtures, county);''')

# --- Next match box: stake + preview share button
rep("""${venue && parkingFor(venue) ? `<span class="parking">Parking: ${esc(parkingFor(venue))}</span>` : ''}</div>${ppHtml}${oppPreview(h === mine ? a : h)}`;""",
    """${venue && parkingFor(venue) ? `<span class="parking">Parking: ${esc(parkingFor(venue))}</span>` : ''}<button type="button" class="sharebtn" data-share="preview">Share preview</button></div>${ppHtml}${stakeHtml(mineF[0] && { ...mineF[0], div: DATA.divisions.find(dd => dd.name === mineF[0].comp) || null })}${oppPreview(h === mine ? a : h)}`;""")

# --- Share images: preview and round-up
rep("""  const d = DATA.divisions[view];
  let title, sub, rows = [];""", """  const d = DATA.divisions[typeof view === 'number' ? view : (teamDiv[mine] || 0)];
  let title, sub, rows = [];
  const foot = () => {
    x.textAlign = 'left'; x.fillStyle = '#222A33'; x.fillRect(72, H - 150, W - 144, 2);
    x.fillStyle = acc; x.font = `700 34px ${B}`; x.fillText(SITE, 72, H - 92);
    x.fillStyle = '#9AA4B0'; x.font = `500 26px ${B}`; x.fillText('From FA Full-Time · ' + (DATA.fetched || ''), 72, H - 50);
  };
  const formRow = (f, x0, y) => f.forEach((r, k) => { x.fillStyle = r === 'W' ? '#4ADE80' : r === 'L' ? '#F59E0B' : '#8A94A0'; x.fillRect(x0 + k * 62, y, 54, 54); x.fillStyle = '#0E1217'; x.font = `800 32px ${D}`; x.textAlign = 'center'; x.fillText(r, x0 + k * 62 + 27, y + 39); x.textAlign = 'left'; });
  if (kind === 'preview') {
    const nx = nextMine(); if (!nx) return c;
    const [date, ko, h, a, venue] = nx.f;
    x.fillStyle = acc; x.font = `800 112px ${D}`; x.fillText('MATCHDAY', 72, 270);
    x.fillStyle = '#C3CAD3'; x.font = `500 34px ${B}`; x.fillText(`${dayLabel(date)} · ${ko ? ko + ' kick-off' : 'kick-off TBC'} · ${nx.comp}`, 72, 326);
    x.fillStyle = '#FFFFFF'; fitText(x, h.toUpperCase(), 936, 92, 800, D); x.fillText(h.toUpperCase(), 72, 470);
    x.fillStyle = '#9AA4B0'; x.font = `700 44px ${D}`; x.fillText('V', 72, 540);
    x.fillStyle = '#FFFFFF'; fitText(x, a.toUpperCase(), 936, 92, 800, D); x.fillText(a.toUpperCase(), 72, 630);
    if (venue) { x.fillStyle = '#C3CAD3'; fitText(x, venueName(venue), 936, 34, 500, B); x.fillText(venueName(venue), 72, 700); }
    [[h, 790], [a, 960]].forEach(([n, y]) => {
      const s = standing(n); x.fillStyle = '#ECEFF3'; fitText(x, n, 520, 34, 700, B); x.fillText(n, 72, y + 40);
      if (s) { x.fillStyle = '#9AA4B0'; x.font = `500 28px ${B}`; x.fillText(`${ordinal(s.pos)} · ${s.pts} pts`, 72, y + 84); formRow(s.form, 680, y); }
    });
    const prev = (teamSummary(h).g || []).filter(g => g.opp === a).pop();
    if (prev) { x.fillStyle = '#C3CAD3'; x.font = `500 30px ${B}`; const tx = `Last time: ${prev.home ? h : a} ${prev.home ? prev.gf : prev.ga}–${prev.home ? prev.ga : prev.gf} ${prev.home ? a : h}, ${dayLabel(prev.date)}`; fitText(x, tx, 936, 30, 500, B); x.fillText(tx, 72, 1130); }
    foot(); return c;
  }
  if (kind === 'roundup') {
    const ru = roundup(typeof view === 'number' ? view : teamDiv[mine]); if (!ru) return c;
    x.fillStyle = acc; x.font = `800 112px ${D}`; x.fillText('ROUND-UP', 72, 270);
    x.fillStyle = '#C3CAD3'; x.font = `500 34px ${B}`; x.fillText(`${d.name} · ${dayLabel(ru.date)} · ${ru.goals} goals`, 72, 326);
    ru.items.slice(0, 6).forEach((it, k) => {
      const y = 430 + k * 125;
      x.fillStyle = acc; x.font = `700 26px ${B}`; x.fillText(it.k.toUpperCase(), 72, y);
      x.fillStyle = '#FFFFFF'; const main = `${it.team} · ${it.v}`; fitText(x, main, 936, 44, 700, B); x.fillText(main, 72, y + 50);
      x.fillStyle = '#9AA4B0'; fitText(x, it.sub, 936, 26, 500, B); x.fillText(it.sub, 72, y + 88);
    });
    foot(); return c;
  }""")
open(f, 'w').write(t); print('ok', f)
