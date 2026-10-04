"""Projected finish (points per game), drop home/away tiles, predictor button above the table on phones."""
import sys
f = sys.argv[1]; t = open(f).read()
def rep(a, b):
    global t
    assert t.count(a) == 1, (f, a[:70]); t = t.replace(a, b)
rep("function renderStats(rows, n) {", r'''// Projected final table: points per game so far carried over a full double round-robin.
// Opponent strength is not weighted yet (planned once teams have played about 8).
function projection(i) {
  const d = DATA.divisions[i], G = (d.teams.length - 1) * 2;
  const minP = Math.min(...d.teams.map(x => x[1]).filter(p => p > 0));
  const list = d.teams.map(([name, p, , , , , , pts], k) => ({ name, k, pts: p ? pts + pts / p * Math.max(0, G - p) : pts }))
    .sort((a, b) => b.pts - a.pts || a.k - b.k);
  const out = {}; list.forEach((x, j) => out[x.name] = { pos: j + 1, pts: Math.round(x.pts) });
  return { by: out, top: list[0] && list[0].name, games: G, early: !isFinite(minP) || minP < 6 };
}
function renderStats(rows, n) {''')
rep("""  if (me) cards.push([mine, 'Position', ordinal(me.pos), `${me.pts} points · ${me.pts === top.pts ? 'level with the top' : (top.pts - me.pts) + ' behind the leader'}`]);""",
"""  if (me) cards.push([mine, 'Position', ordinal(me.pos), `${me.pts} points · ${me.pts === top.pts ? 'level with the top' : (top.pts - me.pts) + ' behind the leader'}`]);
  if (!n && typeof view === 'number') {
    const pj = projection(view), who = me ? mine : pj.top;
    if (who && pj.by[who]) cards.push([me ? 'Projected finish' : 'Projected champions', who, ordinal(pj.by[who].pos), `about ${pj.by[who].pts} pts over ${pj.games} games on current form${pj.early ? ' · early days' : ''}`]);
  }""")
rep("""    ['Home', rec(s.home), s.home.n ? `${s.home.p} pts` : 'No home games yet'],
    ['Away', rec(s.away), s.away.n ? `${s.away.p} pts` : 'No away games yet'],""",
"""    ...(() => { const pj = projection(i).by[name], pe = projection(i).early; return [
      ['Projected finish', pj ? ordinal(pj.pos) : '–', pj ? `about ${pj.pts} pts on current form${pe ? ' · early days' : ''}` : 'No games yet'],
      ['Current run', s.g.length ? runText(s.g) : '–', 'league games']]; })(),""")
rep("@media (min-width:641px){ tr.detail{display:none!important} tr[data-row]{cursor:default} }",
    "@media (min-width:641px){ tr.detail{display:none!important} tr[data-row]{cursor:default} }\n@media (max-width:640px){ .split > .pred{order:-1} }")
open(f, 'w').write(t); print('ok', f)
