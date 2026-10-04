import sys
f = sys.argv[1]; t = open(f).read()
def rep(a, b):
    global t
    assert t.count(a) == 1, a[:80]; t = t.replace(a, b)

# 1. Move the section to sit under the top box, and rename it
sec = '''    <section aria-labelledby="today-h" id="today-sec" hidden>
      <div class="sec-head"><h2 id="today-h">Today</h2><span class="note" id="today-note"></span><button type="button" class="sharebtn" data-share="today">Share</button></div>
      <div class="panel today" id="today"></div>
    </section>
'''
rep(sec, '')
rep('''    <div class="panel next" id="next"></div>
  </section>
''', '''    <div class="panel next" id="next"></div>
  </section>

''' + sec.replace('>Today</h2>', '>Match Day</h2>').replace('    <section', '  <section').replace('\n      <div', '\n    <div').replace('\n    </section>', '\n  </section>'))

# 2. Match day games: our division (my team's, else the one being viewed), plus cup ties involving its teams
i = t.index('function renderToday() {'); j = t.index('function oppPreview(opp)')
t = t[:i] + r'''function matchDayGames() {
  const di = mine && teamDiv[mine] !== undefined ? teamDiv[mine] : (typeof view === 'number' ? view : null);
  if (di === null) return null;
  const d = DATA.divisions[di], key = ddmm(new Date()), inDiv = new Set(d.teams.map(x => x[0])), items = [];
  const addR = (r, comp) => items.push({ h: r[1], a: r[2], hs: r[3], as: r[4], ko: null, st: '', comp });
  const addF = (f, comp) => items.push({ h: f[2], a: f[3], hs: null, as: null, ko: f[1], st: f[6], comp });
  d.results.filter(r => r[0] === key).forEach(r => addR(r, ''));
  d.fixtures.filter(f => f[0] === key).forEach(f => addF(f, ''));
  DATA.cups.forEach(c => {
    c.results.filter(r => r[0] === key && (inDiv.has(r[1]) || inDiv.has(r[2]))).forEach(r => addR(r, c.county ? (r[6] || c.name) : c.name));
    c.fixtures.filter(f => f[0] === key && (inDiv.has(f[2]) || inDiv.has(f[3]))).forEach(f => addF(f, c.county ? (f[7] || c.name) : c.name));
  });
  const me = g => g.h === mine || g.a === mine;
  items.sort((x, y) => me(y) - me(x) || (x.hs === null) - (y.hs === null) || (x.ko || '99').localeCompare(y.ko || '99'));
  return { d, items };
}
function renderToday() {
  const sec = document.getElementById('today-sec'), md = matchDayGames();
  if (!md || !md.items.length) { sec.hidden = true; return; }
  sec.hidden = false;
  const now = new Date(), mins = s => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
  const nowM = now.getHours() * 60 + now.getMinutes();
  document.getElementById('today-note').textContent = `${md.d.name} · from FA Full-Time · checked ${DATA.fetched}`;
  document.getElementById('today').innerHTML = md.items.map(g => {
    const m = g.h === mine || g.a === mine;
    let sc, st;
    if (g.hs !== null && g.hs !== undefined) { sc = `<span class="sc">${g.hs}–${g.as}</span>`; st = '<span class="st ft">Full time</span>'; }
    else if (g.st) { sc = '<span class="sc ko">–</span>'; st = `<span class="st"><span class="badge-pp">${esc(g.st)}</span></span>`; }
    else if (g.ko && nowM >= mins(g.ko) + 100) { sc = '<span class="sc ko">v</span>'; st = '<span class="st"></span>'; }
    else if (g.ko && nowM >= mins(g.ko)) { sc = '<span class="sc ko">v</span>'; st = '<span class="st live">Playing now</span>'; }
    else { sc = `<span class="sc ko">${g.ko ? esc(g.ko) : 'TBC'}</span>`; st = '<span class="st">Kick-off</span>'; }
    return `<div class="trow ${m ? 'mine' : ''}"><span class="h">${esc(g.h)}</span>${sc}<span class="a">${esc(g.a)}</span>${st}${g.comp ? `<span class="cp">${esc(g.comp)}</span>` : ''}</div>`;
  }).join('');
}
''' + t[j:]
rep('.trow .st.live{', '.trow .cp{grid-column:1/-1;font-size:11px;color:var(--muted);text-align:center;margin-top:-6px}\n.trow .st.live{')

# 3. Top box becomes "Match day" when my team plays today
rep('''  const el = document.getElementById('next');
  if (!mine) {''', '''  const el = document.getElementById('next'), tk = ddmm(new Date());
  document.getElementById('next-h').textContent = 'Your next match';
  if (mine) {
    let done = null;
    DATA.divisions.forEach(d => d.results.forEach(r => { if (r[0] === tk && r[3] !== null && (r[1] === mine || r[2] === mine)) done = { r, comp: d.name }; }));
    DATA.cups.forEach(c => c.results.forEach(r => { if (r[0] === tk && r[3] !== null && r[3] !== undefined && (r[1] === mine || r[2] === mine)) done = { r, comp: c.county ? (r[6] || c.name) : c.name }; }));
    if (done || (mineF[0] && mineF[0].f[0] === tk)) document.getElementById('next-h').textContent = 'Match day';
    if (done) {
      const [, h, a, hs, as] = done.r, gf = h === mine ? hs : as, ga = h === mine ? as : hs, res = gf > ga ? 'Won' : gf < ga ? 'Lost' : 'Drew';
      const nx = mineF.find(x => x.f[0] !== tk);
      el.innerHTML = `<div class="row">
      <div class="teams">${esc(h)} v ${esc(a)}<small>Today · ${esc(done.comp)} · ${res}</small></div>
      <div class="kowrap"><div class="eyebrow">Full time</div><div class="ko">${hs}–${as}</div></div>
    </div>` + (nx ? `<div class="sub"><span>Next: ${esc(nx.f[2])} v ${esc(nx.f[3])}, ${dayLabel(nx.f[0])}${nx.f[1] ? ', ' + esc(nx.f[1]) : ''}</span></div>` : '');
      return;
    }
  }
  if (!mine) {''')

# 4. Share image for match day uses the same games
rep('''  } else {
    const key = kind === 'today' ? ddmm(new Date()) : null;''', '''  } else if (kind === 'today') {
    const md = matchDayGames() || { d, items: [] };
    title = md.d.name.toUpperCase(); sub = 'Match day · ' + dayLabel(ddmm(new Date()));
    rows = md.items.map(g => ({ h: g.h, s: g.hs !== null && g.hs !== undefined ? `${g.hs}–${g.as}` : g.st ? 'P–P' : (g.ko || 'TBC'), a: g.a, me: g.h === mine || g.a === mine, ko: !(g.hs !== null && g.hs !== undefined) }));
  } else {
    const key = null;''')
open(f, 'w').write(t); print('ok', f)
