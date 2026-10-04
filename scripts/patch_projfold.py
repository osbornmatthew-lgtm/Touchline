import sys
f = sys.argv[1]; t = open(f).read()
def rep(a, b):
    global t
    assert t.count(a) == 1, (f, a[:70]); t = t.replace(a, b)
rep('''      <div class="panel" id="proj"></div>
    </section>''', '''      <div class="projsum" id="proj-sum"></div>
      <button type="button" class="predtoggle projtoggle" id="projtoggle" aria-expanded="false" aria-controls="proj">Show predicted final table</button>
      <div class="panel" id="proj" hidden></div>
    </section>''')
rep('.pfoot{margin:0;', '.projtoggle{display:block;min-height:44px;border-radius:999px;border:1px solid var(--accent);background:transparent;color:var(--fg);font:inherit;font-weight:600;cursor:pointer;width:100%}\n.projsum{font-size:15px;color:var(--fg-2)}\n.projsum b{color:var(--fg)}\n.pfoot{margin:0;')
rep("""  document.getElementById('proj').innerHTML = pj.list.map(x => {""", """  const me = pj.list.find(x => x.name === mine), top = pj.list[0];
  document.getElementById('proj-sum').innerHTML = me
    ? `<b>${esc(mine)}</b>: predicted <b>${ordinal(me.pos)}</b> on about ${me.round} pts (now ${ordinal(me.now)}). Predicted winners: <b>${esc(top.name)}</b>.`
    : `Predicted winners: <b>${esc(top.name)}</b> on about ${top.round} pts.`;
  document.getElementById('proj').innerHTML = pj.list.map(x => {""")
rep("""document.getElementById('predtoggle').addEventListener('click', e => {""", """document.getElementById('projtoggle').addEventListener('click', e => {
  const p = document.getElementById('proj'), open = p.hidden;
  p.hidden = !open; e.currentTarget.setAttribute('aria-expanded', open); e.currentTarget.textContent = open ? 'Hide predicted final table' : 'Show predicted final table';
  if (open) track('season-predictor');
});
document.getElementById('predtoggle').addEventListener('click', e => {""")
open(f, 'w').write(t); print('ok', f)
