"""Season predictor: projected final table from current form and games left."""
import sys
f = sys.argv[1]; t = open(f).read()
def rep(a, b):
    global t
    assert t.count(a) == 1, (f, a[:70]); t = t.replace(a, b)

# projection: blend season points-per-game with the last five, carry over the games each team has left
i = t.index('function projection(i) {'); j = t.index('function renderStats(rows, n) {')
t = t[:i] + r'''function projection(i) {
  const d = DATA.divisions[i], G = (d.teams.length - 1) * 2, fm = formMap(d);
  const minP = Math.min(...d.teams.map(x => x[1]).filter(p => p > 0));
  const list = d.teams.map(([name, p, , , , gf, ga, pts], k) => {
    const last = (fm[name] || []).slice(-5), lp = last.reduce((s, r) => s + (r === 'W' ? 3 : r === 'D' ? 1 : 0), 0);
    const rate = p ? (last.length ? (pts / p + lp / last.length) / 2 : pts / p) : 0;
    const left = Math.max(0, G - p);
    return { name, k, now: k + 1, played: p, left, rate, pts: pts + rate * left, gd: gf - ga };
  }).sort((a, b) => b.pts - a.pts || b.gd - a.gd || a.k - b.k);
  const out = {}; list.forEach((x, j) => { x.pos = j + 1; x.round = Math.round(x.pts); out[x.name] = { pos: j + 1, pts: x.round }; });
  return { by: out, list, top: list[0] && list[0].name, games: G, early: !isFinite(minP) || minP < 6 };
}
function renderSeason() {
  const sec = document.getElementById('proj-sec');
  if (typeof view !== 'number') { sec.hidden = true; return; }
  const pj = projection(view);
  sec.hidden = !pj.list.some(x => x.played);
  if (sec.hidden) return;
  document.getElementById('proj-note').textContent = `Final table after ${pj.games} games on current form${pj.early ? ' · early days' : ''}`;
  document.getElementById('proj').innerHTML = pj.list.map(x => {
    const mv = x.now - x.pos, arrow = mv > 0 ? `<span class="up">▲${mv}</span>` : mv < 0 ? `<span class="down">▼${-mv}</span>` : '<span class="same">–</span>';
    return `<div class="prow ${x.name === mine ? 'mine' : ''}"><span class="pp">${x.pos}</span><span class="pt">${crest(x.name)}<button type="button" class="teambtn" data-team="${esc(x.name)}">${esc(x.name)}</button></span><span class="pm">${arrow}</span><span class="pn">Now ${ordinal(x.now)}</span><span class="pv">${x.round}</span></div>`;
  }).join('') + `<p class="pfoot">Points each team would end on if they keep picking up points at their current rate (season average blended with their last five). It doesn't yet allow for who they still have to play.</p>`;
}
''' + t[j:]

rep('''    <section aria-labelledby="latest-h">''', '''    <section aria-labelledby="proj-h" id="proj-sec" hidden>
      <div class="sec-head"><h2 id="proj-h">Season predictor</h2><span class="note" id="proj-note"></span><button type="button" class="sharebtn" data-share="projection">Share</button></div>
      <div class="panel" id="proj"></div>
    </section>

    <section aria-labelledby="latest-h">''')
rep('''  renderRoundup();''', '''  renderRoundup();
  renderSeason();''')
rep('/* what\'s at stake, round-up */', '''/* season predictor */
.prow{display:grid;grid-template-columns:34px minmax(0,1fr) 44px 64px 40px;gap:8px;align-items:center;padding:6px 14px;border-top:1px solid var(--line);font-size:14px;min-height:50px}
.prow:first-child{border-top:0}
.prow.mine{background:var(--mine);box-shadow:inset 4px 0 0 var(--accent)}
.prow .pp{font-weight:600;color:var(--fg)}
.prow .pt{display:flex;align-items:center;gap:8px;min-width:0;white-space:nowrap;overflow:hidden}
.prow .pt .crest{width:24px;height:24px;font-size:10px}
.prow .pm{font-size:12px;font-weight:700;text-align:center}
.prow .up{color:var(--win)} .prow .down{color:var(--loss)} .prow .same{color:var(--muted)}
.prow .pn{font-size:12px;color:var(--muted);text-align:right}
.prow .pv{font-family:var(--display);font-weight:700;font-size:20px;text-align:right;color:var(--fg)}
.pfoot{margin:0;padding:10px 14px 14px;font-size:12px;color:var(--muted);border-top:1px solid var(--line)}
/* what's at stake, round-up */''')

# share image
rep("""  if (kind === 'table') {
    title = d.name.toUpperCase(); sub = 'League table · ' + (DATA.updated || '');""", """  if (kind === 'projection') {
    const pj = projection(view);
    title = d.name.toUpperCase(); sub = `Predicted final table · on current form${pj.early ? ' · early days' : ''}`;
    rows = pj.list.slice(0, 12).map(t => ({ l: `${t.pos}`, n: t.name, m: ordinal(t.now), g: t.now - t.pos > 0 ? '▲' + (t.now - t.pos) : t.now - t.pos < 0 ? '▼' + (t.pos - t.now) : '–', r: `${t.round}`, me: t.name === mine }));
    kind = 'table'; var projHead = true;
  } else if (kind === 'table') {
    title = d.name.toUpperCase(); sub = 'League table · ' + (DATA.updated || '');""")
rep("""x.fillText('P', 790, top - 70); x.fillText('GD', 900, top - 70); x.fillText('PTS', 1010, top - 70);""",
    """x.fillText(typeof projHead !== 'undefined' && projHead ? 'NOW' : 'P', 790, top - 70); x.fillText(typeof projHead !== 'undefined' && projHead ? '' : 'GD', 900, top - 70); x.fillText('PTS', 1010, top - 70);""")
open(f, 'w').write(t); print('ok', f)
