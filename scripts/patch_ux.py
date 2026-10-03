"""One-off: match-day mode, opponent preview, postponement notices, tap-to-expand table rows,
share images, and venue pins/parking from DATA.venues. Safe to run twice."""
import sys

CSS = r"""
/* match day */
.today{padding:6px 0}
.trow{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr) 92px;gap:10px;align-items:center;padding:10px 14px;border-top:1px solid var(--line);font-size:14px}
.trow:first-child{border-top:0}
.trow .h{text-align:right;min-width:0}
.trow .a{min-width:0}
.trow .sc{font-family:var(--display);font-weight:800;font-size:22px;min-width:56px;text-align:center;font-variant-numeric:tabular-nums}
.trow .sc.ko{font-size:18px;color:var(--muted)}
.trow .st{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;text-align:right;color:var(--muted)}
.trow .st.ft{color:var(--accent)}
.trow .st.live{color:var(--warn,#FFB547)}
.trow.mine{background:var(--mine)}
.trow.mine .h,.trow.mine .a{font-weight:700}
/* opponent preview */
.opp{border-top:1px solid var(--line);padding:12px 18px;display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--fg-2)}
.opp .who{color:var(--fg);font-weight:600}
.opp .form{display:inline-flex;gap:3px;vertical-align:middle}
.ppnote{border-top:1px solid var(--line);padding:10px 18px;font-size:14px;color:var(--fg)}
.ppnote b{color:#FF8A5C}
.k.pp,.badge-pp{background:color-mix(in srgb, #FF8A5C 18%, transparent);color:#FF8A5C;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.parking{font-size:13px;color:var(--muted)}
/* expandable table rows on phones */
tr.detail td{background:var(--panel);font-size:13px;color:var(--fg-2);padding:8px 16px 12px;text-align:left}
tr.detail .dl{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center}
tr.detail b{color:var(--fg)}
tr[data-row]{cursor:pointer}
@media (min-width:641px){ tr.detail{display:none!important} tr[data-row]{cursor:default} }
/* share */
.sharebtn{margin-left:auto;padding:6px 12px;border-radius:999px;border:1px solid var(--line-2);background:transparent;color:var(--fg-2);font:inherit;font-size:13px;font-weight:600;cursor:pointer}
.sharebtn:hover{border-color:var(--accent);color:var(--fg)}
"""

TODAY_HTML = """    <section aria-labelledby="today-h" id="today-sec" hidden>
      <div class="sec-head"><h2 id="today-h">Today</h2><span class="note" id="today-note"></span><button type="button" class="sharebtn" data-share="today">Share</button></div>
      <div class="panel today" id="today"></div>
    </section>

"""

JS = r"""
// ---- match day, opponent preview, postponements, row details, share images, venue pins ----
const pad2 = n => String(n).padStart(2, '0');
const ddmm = d => pad2(d.getDate()) + '/' + pad2(d.getMonth() + 1);
const VINFO = DATA.venues || {};
function venueLink(venue) {
  const fix = VENUES[venue], info = VINFO[venue] || {};
  if (fix) return { q: fix.q };
  if (info.ll) return { ll: info.ll };
  if (info.a) return { q: info.a };
  return { q: venue + ', Essex, UK' };
}
function parkingFor(venue) { return VENUES[venue] ? '' : ((VINFO[venue] || {}).p || ''); }
function renderToday() {
  const sec = document.getElementById('today-sec');
  if (typeof view === 'string') { sec.hidden = true; return; }
  const d = DATA.divisions[view], key = ddmm(new Date());
  const res = d.results.filter(r => r[0] === key);
  const fx = d.fixtures.filter(f => f[0] === key);
  if (!res.length && !fx.length) { sec.hidden = true; return; }
  sec.hidden = false;
  const now = new Date(), mins = s => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
  const nowM = now.getHours() * 60 + now.getMinutes();
  const items = res.map(r => ({ h: r[1], a: r[2], hs: r[3], as: r[4], ko: null, st: '' }))
    .concat(fx.map(f => ({ h: f[2], a: f[3], hs: null, as: null, ko: f[1], st: f[6] })))
    .sort((x, y) => (x.hs === null) - (y.hs === null) || (x.ko || '99').localeCompare(y.ko || '99'));
  document.getElementById('today-note').textContent = `Scores from FA Full-Time · last checked ${DATA.fetched}`;
  document.getElementById('today').innerHTML = items.map(g => {
    const m = g.h === mine || g.a === mine;
    let sc, st;
    if (g.hs !== null) { sc = `${g.hs}–${g.as}`; st = '<span class="st ft">Full time</span>'; }
    else if (g.st) { sc = '<span class="sc ko">–</span>'; st = `<span class="st"><span class="badge-pp">${esc(g.st)}</span></span>`; }
    else if (g.ko && nowM >= mins(g.ko) + 100) { sc = '<span class="sc ko">?</span>'; st = '<span class="st live">Result due</span>'; }
    else if (g.ko && nowM >= mins(g.ko)) { sc = '<span class="sc ko">v</span>'; st = '<span class="st live">Playing now</span>'; }
    else { sc = `<span class="sc ko">${g.ko ? esc(g.ko) : 'TBC'}</span>`; st = '<span class="st">Kick-off</span>'; }
    if (!sc.startsWith('<span')) sc = `<span class="sc">${sc}</span>`;
    return `<div class="trow ${m ? 'mine' : ''}"><span class="h">${esc(g.h)}</span>${sc}<span class="a">${esc(g.a)}</span>${st}</div>`;
  }).join('');
}
function oppPreview(opp) {
  const bits = [];
  const di = teamDiv[opp];
  if (di !== undefined) {
    const d = DATA.divisions[di], ti = d.teams.findIndex(t => t[0] === opp), t = d.teams[ti];
    const fm = (formMap(d)[opp] || []).slice(-5).map(x => `<i class="${x}">${x}</i>`).join('');
    bits.push(`<div><span class="who">${esc(opp)}</span> · ${ordinal(ti + 1)} in ${esc(d.name)} · ${t[7]} pts${fm ? ` · <span class="form">${fm}</span>` : ''}</div>`);
    const s = teamSummary(opp), last = s.g[s.g.length - 1];
    if (last) bits.push(`<div>Last game: ${last.res === 'W' ? 'beat' : last.res === 'L' ? 'lost to' : 'drew with'} ${esc(last.opp)} ${Math.max(last.gf, last.ga)}–${Math.min(last.gf, last.ga)}</div>`);
  }
  const prev = teamSummary(mine).g.filter(x => x.opp === opp).pop();
  if (prev) bits.push(`<div>Last time you met: ${prev.home ? SCORE(mine, opp, prev.gf, prev.ga) : SCORE(opp, mine, prev.ga, prev.gf)}, ${dayLabel(prev.date)}</div>`);
  return bits.length ? `<div class="opp"><div class="eyebrow">Opponent</div>${bits.join('')}</div>` : '';
}
function postponedFor(name) {
  const out = [];
  DATA.divisions.forEach(d => d.fixtures.forEach(f => { if (f[6] && (f[2] === name || f[3] === name) && toDate(f[0]) >= today) out.push(f); }));
  DATA.cups.forEach(c => c.fixtures.forEach(f => { if (f[6] && (f[2] === name || f[3] === name) && toDate(f[0]) >= today) out.push(f); }));
  return out.sort((a, b) => toDate(a[0]) - toDate(b[0]));
}
document.addEventListener('click', e => {
  const tr = e.target.closest('tr[data-row]');
  if (!tr || e.target.closest('.teambtn') || window.matchMedia('(min-width:641px)').matches) return;
  const det = tr.nextElementSibling;
  if (det && det.classList.contains('detail')) det.hidden = !det.hidden;
});

// Share images (Web Share on phones, download elsewhere)
const MARK = new Path2D('M12 6H36L90 80H12Z M24 18H29.9L66.4 68H24Z'), BAR = new Path2D('M12 86H90V98H12Z');
function fitText(ctx, t, max, size, weight, family) {
  let s = size; do { ctx.font = `${weight} ${s}px ${family}`; s -= 2; } while (ctx.measureText(t).width > max && s > 18);
  return t;
}
async function drawCard(kind) {
  const W = 1080, H = 1350, c = document.createElement('canvas'); c.width = W; c.height = H;
  const x = c.getContext('2d');
  try { await Promise.all([document.fonts.load('800 80px "Barlow Condensed"'), document.fonts.load('600 40px "IBM Plex Sans"')]); } catch (e) {}
  const D = "'Barlow Condensed', 'Arial Narrow', sans-serif", B = "'IBM Plex Sans', system-ui, sans-serif";
  const acc = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#C9F24A';
  x.fillStyle = '#0E1217'; x.fillRect(0, 0, W, H);
  x.save(); x.translate(72, 64); x.scale(0.62, 0.62); x.fillStyle = '#FFFFFF'; x.fill(MARK, 'evenodd'); x.fillStyle = '#C9F24A'; x.fill(BAR); x.restore();
  x.fillStyle = '#FFFFFF'; x.font = `800 52px ${D}`; x.textBaseline = 'alphabetic'; x.fillText('TOUCHLINE', 140, 110);
  const tw = x.measureText('TOUCHLINE').width; x.fillStyle = '#9AA4B0'; x.fillRect(140 + tw + 16, 66, 3, 48); x.font = `600 46px ${D}`; x.fillText('EJA', 140 + tw + 34, 110);
  const d = DATA.divisions[view];
  let title, sub, rows = [];
  if (kind === 'table') {
    title = d.name.toUpperCase(); sub = 'League table · ' + (DATA.updated || '');
    const { rows: r } = buildTable(view);
    rows = r.slice(0, 12).map(t => ({ l: `${t.pos}`, n: t.name, m: `${t.p}`, g: gdTxt(t.gd), r: `${t.pts}`, me: t.name === mine }));
  } else {
    const key = kind === 'today' ? ddmm(new Date()) : null;
    const scored = d.results.filter(r => r[3] !== null && (!key || r[0] === key));
    const date = key || (groupByDate(scored, false)[0] || [])[0];
    title = d.name.toUpperCase(); sub = (kind === 'today' ? 'Today · ' : 'Results · ') + (date ? dayLabel(date) : '');
    rows = scored.filter(r => r[0] === date).map(r => ({ h: r[1], s: `${r[3]}–${r[4]}`, a: r[2], me: r[1] === mine || r[2] === mine }));
    if (kind === 'today') d.fixtures.filter(f => f[0] === date).forEach(f => rows.push({ h: f[2], s: f[6] ? 'P–P' : (f[1] || 'TBC'), a: f[3], me: f[2] === mine || f[3] === mine, ko: true }));
  }
  x.fillStyle = acc; x.font = `800 112px ${D}`; x.fillText(title, 72, 270);
  x.fillStyle = '#C3CAD3'; x.font = `500 34px ${B}`; x.fillText(sub, 72, 326);
  const top = 390, rh = kind === 'table' ? 70 : 88;
  rows.slice(0, kind === 'table' ? 12 : 10).forEach((r, i) => {
    const y = top + i * rh;
    if (r.me) { x.fillStyle = 'rgba(201,242,74,0.14)'; x.fillRect(48, y - rh + 22, W - 96, rh - 6); x.fillStyle = acc; x.fillRect(48, y - rh + 22, 8, rh - 6); }
    x.fillStyle = '#ECEFF3';
    if (kind === 'table') {
      x.font = `700 38px ${B}`; x.fillText(r.l, 80, y); fitText(x, r.n, 560, 38, r.me ? 700 : 500, B); x.fillText(r.n, 150, y);
      x.font = `500 36px ${B}`; x.fillStyle = '#9AA4B0'; x.textAlign = 'right'; x.fillText(r.m, 790, y); x.fillText(r.g, 900, y);
      x.fillStyle = '#ECEFF3'; x.font = `800 48px ${D}`; x.fillText(r.r, 1010, y); x.textAlign = 'left';
    } else {
      x.textAlign = 'right'; fitText(x, r.h, 380, 36, r.me ? 700 : 500, B); x.fillText(r.h, 440, y);
      x.textAlign = 'center'; x.font = `800 ${r.ko ? 40 : 56}px ${D}`; x.fillStyle = r.ko ? '#9AA4B0' : '#FFFFFF'; x.fillText(r.s, 540, y + 4);
      x.textAlign = 'left'; x.fillStyle = '#ECEFF3'; fitText(x, r.a, 380, 36, r.me ? 700 : 500, B); x.fillText(r.a, 640, y);
    }
  });
  if (kind === 'table') { x.fillStyle = '#9AA4B0'; x.font = `600 26px ${B}`; x.textAlign = 'right'; x.fillText('P', 790, top - 62); x.fillText('GD', 900, top - 62); x.fillText('PTS', 1010, top - 62); x.textAlign = 'left'; }
  x.fillStyle = '#222A33'; x.fillRect(72, H - 120, W - 144, 2);
  x.fillStyle = '#9AA4B0'; x.font = `500 30px ${B}`; x.fillText('From FA Full-Time · ' + (DATA.fetched || ''), 72, H - 64);
  x.fillStyle = acc; x.font = `700 30px ${B}`; x.textAlign = 'right'; x.fillText('touchline-eja.netlify.app', W - 72, H - 64); x.textAlign = 'left';
  return c;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-share]'); if (!b) return;
  const kind = b.dataset.share; b.disabled = true;
  try {
    const c = await drawCard(kind);
    const blob = await new Promise(r => c.toBlob(r, 'image/png'));
    const file = new File([blob], `touchline-${kind}.png`, { type: 'image/png' });
    track('share/' + kind);
    if (navigator.canShare && navigator.canShare({ files: [file] })) { try { await navigator.share({ files: [file], text: 'touchline-eja.netlify.app' }); } catch (err) {} }
    else { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = file.name; document.body.appendChild(a); a.click(); a.remove(); }
  } finally { b.disabled = false; }
});
"""


def patch(path):
    s = open(path, encoding='utf-8').read()
    if 'function renderToday' in s:
        print(path, 'already patched'); return

    def rep(a, b, count=1):
        nonlocal s
        assert s.count(a) == count, (path, a[:80], s.count(a))
        s = s.replace(a, b)

    rep('.sheet-body h3{', CSS + '.sheet-body h3{')
    # maps use pins/addresses from DATA.venues; corrections still win
    rep("""function mapLinks(venue) {
  const q = encodeURIComponent((VENUES[venue] && VENUES[venue].q) || venue + ', Essex, UK');
  return `<span class="maps"><a href="https://www.google.com/maps/search/?api=1&query=${q}" target="_blank" rel="noopener">Directions</a><a href="https://waze.com/ul?q=${q}&navigate=yes" target="_blank" rel="noopener">Waze</a></span>`;
}""", """function mapLinks(venue) {
  const t = venueLink(venue);
  const g = t.ll ? `https://www.google.com/maps/dir/?api=1&destination=${t.ll}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(t.q)}`;
  const w = t.ll ? `https://waze.com/ul?ll=${t.ll}&navigate=yes` : `https://waze.com/ul?q=${encodeURIComponent(t.q)}&navigate=yes`;
  return `<span class="maps"><a href="${g}" target="_blank" rel="noopener">Directions</a><a href="${w}" target="_blank" rel="noopener">Waze</a></span>`;
}""")
    rep("const CUP_ACCENT = '#C9F24A';", "const CUP_ACCENT = '#C9F24A';" + JS)
    # today section above the table
    rep('    <div class="split" id="table">', TODAY_HTML + '    <div class="split" id="table">')
    rep("else { renderLatest(comp.results); renderPicks(); renderTable(); }",
        "else { renderLatest(comp.results); renderPicks(); renderTable(); }\n  renderToday();")
    # share buttons
    rep('<div class="sec-head"><h2>Table</h2><span class="badge-pred" id="pred-badge" hidden></span></div>',
        '<div class="sec-head"><h2>Table</h2><span class="badge-pred" id="pred-badge" hidden></span><button type="button" class="sharebtn" data-share="table">Share</button></div>')
    rep('<span class="note" id="latest-date"></span></div>',
        '<span class="note" id="latest-date"></span><button type="button" class="sharebtn" data-share="results">Share</button></div>')
    # next match: parking, postponed notice, opponent preview
    rep("""    <div class="sub">${venue ? `<span>${esc(venueName(venue))}</span>` : '<span>Venue not yet listed</span>'}${venue ? mapLinks(venue) : id ? `<a href="${FT + id}" target="_blank" rel="noopener">Venue details</a>` : ''}</div>`;""",
        """    <div class="sub">${venue ? `<span>${esc(venueName(venue))}</span>` : '<span>Venue not yet listed</span>'}${venue ? mapLinks(venue) : id ? `<a href="${FT + id}" target="_blank" rel="noopener">Venue details</a>` : ''}${venue && parkingFor(venue) ? `<span class="parking">Parking: ${esc(parkingFor(venue))}</span>` : ''}</div>${ppHtml}${oppPreview(h === mine ? a : h)}`;""")
    rep("""  const { f: [date, ko, h, a, venue, id], comp } = mineF[0];""",
        """  const { f: [date, ko, h, a, venue, id], comp } = mineF[0];
  const pps = postponedFor(mine).filter(f => toDate(f[0]) <= toDate(date));
  const ppHtml = pps.map(f => `<div class="ppnote"><b>${esc(f[6])}:</b> ${esc(f[2])} v ${esc(f[3])}, ${dayLabel(f[0])}</div>`).join('');""")
    rep("""  if (!mineF.length) { el.innerHTML = `<div class="row"><div class="teams">No fixture listed yet<small>The next round has not been published on FA Full-Time</small></div></div>`; return; }""",
        """  if (!mineF.length) { el.innerHTML = `<div class="row"><div class="teams">No fixture listed yet<small>The next round has not been published on FA Full-Time</small></div></div>` + postponedFor(mine).map(f => `<div class="ppnote"><b>${esc(f[6])}:</b> ${esc(f[2])} v ${esc(f[3])}, ${dayLabel(f[0])}</div>`).join(''); return; }""")
    # team sheet: postponed games listed with a badge
    rep("""  const upHtml = up.length ? up.map(""", """  const ppl = postponedFor(name).map(f => `<li><span class="rt">${esc(f[2])} v ${esc(f[3])}</span><span class="badge-pp">${esc(f[6])}</span><span class="rc">${dayLabel(f[0])}</span></li>`).join('');
  const upHtml = (up.length || ppl) ? ppl + up.map(""")
    # table rows: data-row + detail row
    rep("""    return `<tr class="${r.name === mine ? 'mine' : ''}">""", """    return `<tr data-row class="${r.name === mine ? 'mine' : ''}">""")
    rep("""      <td class="pts">${r.pts}</td><td class="l wide"><span class="form">${fm}</span></td><td class="gap">${gap}</td>
    </tr>`;""", """      <td class="pts">${r.pts}</td><td class="l wide"><span class="form">${fm}</span></td><td class="gap">${gap}</td>
    </tr><tr class="detail" hidden><td colspan="13"><div class="dl"><span>Won <b>${r.w}</b></span><span>Drawn <b>${r.d}</b></span><span>Lost <b>${r.l}</b></span><span>Scored <b>${r.gf}</b></span><span>Conceded <b>${r.ga}</b></span>${fm ? `<span class="form">${fm}</span>` : ''}<button type="button" class="linkish" data-team="${esc(r.name)}">Team page</button></div></td></tr>`;""")
    rep("""    : ps.size > 1 ? 'Teams have played different numbers of games, so check the P column. Gap is points behind the leader.' : 'Gap is points behind the leader. Form shows the most recent result on the right.';""",
        """    : (ps.size > 1 ? 'Teams have played different numbers of games, so check the P column. Gap is points behind the leader.' : 'Gap is points behind the leader. Form shows the most recent result on the right.') + (window.matchMedia('(max-width:640px)').matches ? ' Tap a row for wins, draws and goals.' : '');""")
    open(path, 'w', encoding='utf-8').write(s)
    print(path, 'patched')


for p in sys.argv[1:]:
    patch(p)
